"""Offline radar initialization/resumption tests; no social data or research claims."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NEW_BATCH = ROOT / "skills/finrun/scripts/new_batch.py"
NEW_RUN = ROOT / "skills/finrun/scripts/new_run.py"


class RadarTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.runs = Path(self.temp.name)

    def call(self, *args, success=True):
        result = subprocess.run([sys.executable, str(NEW_BATCH), "--runs-dir", str(self.runs), *args],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0 if success else 2, result.stdout + result.stderr)
        return result

    def create(self, *extra):
        result = self.call("--request", "发现热门金融问题并生成中文报告", "--language", "zh-CN",
                           "--timezone", "America/Los_Angeles", "--as-of", "2026-09-04T00:30:00Z", *extra)
        directory = Path(result.stdout.strip())
        return directory, json.loads((directory / "radar.json").read_text())

    def test_resolved_language_local_date_and_fixed_utc_window(self):
        directory, data = self.create()
        self.assertEqual(directory.name, "20260903-radar")
        self.assertEqual(data["batch"]["local_date"], "2026-09-03")
        self.assertEqual(data["batch"]["timezone"], "America/Los_Angeles")
        self.assertEqual(data["batch"]["window_start"], "2026-09-03T00:30:00Z")
        self.assertEqual(data["batch"]["window_end"], "2026-09-04T00:30:00Z")
        self.assertEqual(data["request"]["language"], "zh-CN")
        self.assertEqual(data["request"]["mode"], "research")
        self.assertEqual(data["request"]["max_reports"], 5)
        self.assertFalse(data["request"]["schedule_enabled"])
        self.assertFalse(data["request"]["publish"])
        self.assertEqual(data["batch"]["status"], "discovering")
        self.assertEqual(data["coverage"], [])
        self.assertEqual(data["topics"], [])
        self.assertEqual(data["delivery"]["completed_reports"], 0)
        self.assertEqual([p.name for p in directory.iterdir()], ["radar.json"])

    def test_dst_window_uses_elapsed_hours_not_naive_local_time(self):
        _, data = self.create("--as-of", "2026-11-01T17:00:00Z")
        self.assertEqual(data["batch"]["window_start"], "2026-10-31T17:00:00Z")
        self.assertEqual(data["batch"]["local_date"], "2026-11-01")

    def test_default_sources_separate_discovery_evidence_and_disabled_platforms(self):
        _, data = self.create()
        self.assertEqual(data["schema_version"], "1.1.0")
        self.assertEqual(data["request"]["requested_platforms"],
                         ["hacker-news", "gdelt", "google-trends-rss"])
        self.assertEqual(data["request"]["evidence_sources"], ["sec-edgar", "company-ir"])
        self.assertEqual(data["request"]["disabled_platforms"], ["x"])
        self.assertEqual(data["discussions"], [])
        self.assertEqual(data["signals"], [])
        # Configured source names are not evidence of successful collection.
        self.assertEqual(data["coverage"], [])

    def test_explicit_sources_replace_defaults_without_enabling_side_effects(self):
        _, data = self.create("--sources", "gdelt", "youtube", "gdelt")
        self.assertEqual(data["request"]["requested_platforms"], ["gdelt", "youtube"])
        self.assertEqual(data["request"]["disabled_platforms"], ["x"])
        self.assertFalse(data["request"]["schedule_enabled"])
        self.assertFalse(data["request"]["publish"])
        self.assertEqual(data["coverage"], [])

    def test_explicit_x_configuration_does_not_claim_access(self):
        _, data = self.create("--sources", "x")
        self.assertEqual(data["request"]["requested_platforms"], ["x"])
        self.assertEqual(data["request"]["disabled_platforms"], [])
        self.assertEqual(data["coverage"], [])
        self.assertEqual(data["delivery"]["completed_reports"], 0)

    def test_scan_only_and_bounded_count(self):
        _, data = self.create("--mode", "scan-only", "--max-reports", "3", "--lookback-hours", "48")
        self.assertEqual(data["request"]["mode"], "scan-only")
        self.assertEqual(data["request"]["max_reports"], 3)
        self.assertEqual(data["batch"]["window_start"], "2026-09-02T00:30:00Z")

    def test_existing_batch_is_never_overwritten(self):
        directory, _ = self.create()
        before = (directory / "radar.json").read_bytes()
        self.call("--request", "replace", "--language", "en", "--batch-id", directory.name, success=False)
        self.assertEqual((directory / "radar.json").read_bytes(), before)

    def test_resume_preserves_progress_and_language_without_new_defaults(self):
        directory, data = self.create()
        data["topics"] = [{"id": "TOPIC-001", "research": {"status": "running", "run_id": "child-01"}}]
        data["batch"]["status"] = "researching"
        (directory / "radar.json").write_text(json.dumps(data))
        before = (directory / "radar.json").read_bytes()
        result = self.call("--resume", "--batch-id", directory.name)
        self.assertEqual(Path(result.stdout.strip()), directory)
        self.assertEqual((directory / "radar.json").read_bytes(), before)

    def test_resume_rejects_scope_changes(self):
        directory, _ = self.create()
        for option, value in (("--language", "en"), ("--mode", "scan-only"), ("--timezone", "UTC"),
                              ("--as-of", "2026-09-05T00:30:00Z"), ("--max-reports", "3"),
                              ("--lookback-hours", "48"), ("--request", "different"),
                              ("--sources", "reddit")):
            with self.subTest(option=option):
                self.call("--resume", "--batch-id", directory.name, option, value, success=False)

    def test_resume_with_same_sources_preserves_multi_signal_progress(self):
        directory, data = self.create("--sources", "gdelt", "google-trends-rss")
        data["signals"] = [{"id": "SIGNAL-001", "signal_kind": "primary_event",
                            "metrics": {}, "url": "https://example.org/synthetic-filing"}]
        data["topics"] = [{"id": "TOPIC-001", "selection_basis": "event-led",
                           "discussion_ids": [], "signal_ids": ["SIGNAL-001"],
                           "heat": {"level": "unverified"}}]
        manifest = directory / "radar.json"
        manifest.write_text(json.dumps(data))
        before = manifest.read_bytes()
        self.call("--resume", "--batch-id", directory.name,
                  "--sources", "gdelt", "google-trends-rss")
        self.assertEqual(manifest.read_bytes(), before)

    def test_legacy_resume_does_not_migrate_sources_or_rewrite_results(self):
        directory, data = self.create()
        data["schema_version"] = "1.0.0"
        data["request"]["requested_platforms"] = ["reddit", "x", "hacker-news"]
        del data["request"]["evidence_sources"]
        del data["request"]["disabled_platforms"]
        del data["signals"]
        data["batch"]["status"] = "complete"
        manifest = directory / "radar.json"
        manifest.write_text(json.dumps(data))
        before = manifest.read_bytes()
        self.call("--resume", "--batch-id", directory.name)
        self.call("--resume", "--batch-id", directory.name,
                  "--sources", "reddit", "x", "hacker-news")
        self.call("--resume", "--batch-id", directory.name,
                  "--sources", "gdelt", success=False)
        self.assertEqual(manifest.read_bytes(), before)

    def test_resume_needs_a_real_explicit_manifest(self):
        self.call("--resume", success=False)
        self.call("--resume", "--batch-id", "missing-batch", success=False)
        self.assertEqual(list(self.runs.iterdir()), [])

    def test_invalid_arguments_create_no_batch(self):
        cases = [[], ["--request", "test"], ["--request", "test", "--language", "../en"],
                 ["--as-of", "2026-09-04"], ["--timezone", "Not/AZone"],
                 ["--lookback-hours", "0"], ["--max-reports", "6"], ["--batch-id", "../escape"],
                 ["--sources"], ["--sources", "unknown-provider"]]
        for args in cases:
            with self.subTest(args=args):
                self.call(*args, success=False)
        self.assertEqual(list(self.runs.iterdir()), [])

    def test_resume_rejects_invalid_manifest(self):
        directory, _ = self.create()
        for payload in ([], {}, {"kind": "other", "batch": {}, "request": {}},
                        {"kind": "finrunbook-radar-batch", "schema_version": "1.0.0",
                         "batch": {"id": "wrong-id"}, "request": {}}):
            (directory / "radar.json").write_text(json.dumps(payload))
            self.call("--resume", "--batch-id", directory.name, success=False)

    def test_symlink_batch_is_not_followed(self):
        target = self.runs / "other"
        target.mkdir()
        (self.runs / "linked-batch").symlink_to(target, target_is_directory=True)
        self.call("--request", "test", "--language", "en", "--batch-id", "linked-batch", success=False)
        self.call("--resume", "--batch-id", "linked-batch", success=False)
        self.assertEqual(list(target.iterdir()), [])

    def test_resume_rejects_unsupported_schema_without_modification(self):
        directory, data = self.create()
        manifest = directory / "radar.json"
        for version in ("2.0.0", None, []):
            with self.subTest(version=version):
                data["schema_version"] = version
                manifest.write_text(json.dumps(data))
                before = manifest.read_bytes()
                self.call("--resume", "--batch-id", directory.name, success=False)
                self.assertEqual(manifest.read_bytes(), before)

    def test_child_initialization_contract_keeps_separate_namespaces_and_language(self):
        directory, batch = self.create()
        for number in range(1, 4):
            child_id = f"{directory.name}-topic-{number:02d}"
            result = subprocess.run([sys.executable, str(NEW_RUN), "--runs-dir", str(self.runs),
                                     "--run-id", child_id, "--subject", f"Test topic {number}",
                                     "--request", "Synthetic routing test, not real financial research",
                                     "--language", batch["request"]["language"]], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            child = json.loads((self.runs / child_id / "research-record.json").read_text())
            self.assertEqual(child["request"]["language"], "zh-CN")
            self.assertEqual(child["request"]["report_archetype"], "finance-report")
            self.assertEqual(child["validation"]["status"], "NOT_RUN")
            self.assertTrue((self.runs / child_id / "report/index.html").is_file())
        self.assertEqual(batch["delivery"]["completed_reports"], 0)


if __name__ == "__main__":
    unittest.main()
