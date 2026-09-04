from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NEW_RUN = ROOT / "skills" / "finrunbook" / "scripts" / "new_run.py"
VALIDATE = ROOT / "skills" / "finrunbook-validator" / "scripts" / "validate_run.py"


class WorkflowTest(unittest.TestCase):
    def complete_editorial_fixture(self, run_dir: Path) -> None:
        """Supply test metadata only; this is not a real editorial audit."""
        record_path = run_dir / "research-record.json"
        record = json.loads(record_path.read_text(encoding="utf-8"))
        language = record["request"]["language"]
        editor = (
            {"name": "readable-human-writing", "path": "vendor/readable-human-writing/SKILL.md",
             "commit": "cc669c7427ed921ffe15fae6fd91d8d4b9280676"}
            if language.startswith("zh") else
            {"name": "writing-clearly-and-concisely",
             "path": "vendor/agent-toolkit/skills/writing-clearly-and-concisely/SKILL.md",
             "commit": "3027f20f3181758385a1bb8c022d4041dfb4de84"}
        )
        record["editorial_review"].update({
            "status": "completed",
            "completed_at": "2026-09-03T12:00:00Z",
            "reviewer": "unit-test fixture (not an actual editorial audit)",
            "languages": [language],
            "upstream_skills": [{**editor, "languages": [language]}],
            "reviewed_artifacts": [artifact["path"] for artifact in record["artifacts"]],
            "protected_items_preserved": True,
            "unresolved_issues": [],
        })
        record_path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        (run_dir / "editorial-review.json").write_text(
            json.dumps({"result": "no-change", "changes": []}) + "\n", encoding="utf-8",
        )

    def validation_codes(self, run_dir: Path) -> set[str]:
        process = subprocess.run(
            [sys.executable, str(VALIDATE), str(run_dir)], capture_output=True, text=True,
        )
        self.assertIn(process.returncode, (0, 1), process.stdout + process.stderr)
        result = json.loads((run_dir / "validation.json").read_text(encoding="utf-8"))
        return {item["code"] for item in result["issues"]}

    def create_run(self, runs_dir: Path, run_id: str, extra_args: list[str] | None = None) -> Path:
        command = [
            sys.executable,
            str(NEW_RUN),
            "--subject",
            "Example Corp",
            "--request",
            "Explain the revenue change",
            "--run-id",
            run_id,
            "--runs-dir",
            str(runs_dir),
        ]
        command.extend(extra_args or [])
        process = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
        )
        return Path(process.stdout.strip())

    def test_supported_run_passes_and_report_gets_sources(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            run_dir = self.create_run(
                Path(directory),
                "test-supported-run",
                ["--report-archetype", "research-memo", "--format", "markdown"],
            )
            record_path = run_dir / "research-record.json"
            record = json.loads(record_path.read_text(encoding="utf-8"))
            self.assertEqual(record["request"]["report_archetype"], "research-memo")
            self.assertEqual(record["request"]["decision_use"], "investment research")
            self.assertEqual(record["request"]["audience"], "finance professional")
            self.assertIn("output_contract", record["plan"])
            record["sources"] = [
                {
                    "id": "SRC-001",
                    "type": "regulatory-filing",
                    "title": "Example Corp Annual Report",
                    "publisher": "Example Corp",
                    "url": "https://example.com/annual-report",
                    "retrieved_at": "2026-09-03T12:00:00Z",
                    "primary": True,
                    "license_or_terms": "Public issuer filing",
                }
            ]
            record["evidence"] = [
                {
                    "id": "EVD-001",
                    "source_id": "SRC-001",
                    "locator": "Income statement, revenue row",
                    "content": "Revenue increased year over year.",
                }
            ]
            record["facts"] = [
                {
                    "id": "FACT-001",
                    "statement": "Revenue increased year over year.",
                    "status": "verified",
                    "material": True,
                    "source_ids": ["SRC-001"],
                    "evidence_ids": ["EVD-001"],
                }
            ]
            record["artifacts"][0]["fact_ids"] = ["FACT-001"]
            record_path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
            report_path = run_dir / "report.md"
            report = report_path.read_text(encoding="utf-8")
            report = report.replace(
                "<!-- finrunbook:validation:start -->",
                "Revenue increased year over year.[^SRC-001]\n\n<!-- finrunbook:validation:start -->",
            )
            report_path.write_text(report, encoding="utf-8")
            self.complete_editorial_fixture(run_dir)

            process = subprocess.run(
                [sys.executable, str(VALIDATE), str(run_dir)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
            result = json.loads((run_dir / "validation.json").read_text(encoding="utf-8"))
            self.assertEqual(result["status"], "PASS")
            updated_report = report_path.read_text(encoding="utf-8")
            self.assertIn("[^SRC-001]: [Example Corp Annual Report]", updated_report)
            self.assertIn("Validation: **PASS**", updated_report)

    def test_finance_report_defaults_to_interactive_package(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            run_dir = self.create_run(Path(directory), "test-finance-web-run")
            record = json.loads((run_dir / "research-record.json").read_text(encoding="utf-8"))
            self.assertEqual(record["request"]["report_archetype"], "finance-report")
            self.assertEqual(record["request"]["output_formats"], ["interactive-html", "json"])
            self.assertEqual(record["request"]["language"], "en")
            self.assertTrue(record["editorial_review"]["required"])
            self.assertEqual(record["editorial_review"]["status"], "pending")
            self.assertEqual(record["editorial_review"]["upstream_skills"], [])
            self.assertEqual(
                record["plan"]["output_contract"]["planned_artifacts"],
                ["report/index.html", "report/report-data.json"],
            )
            self.assertTrue((run_dir / "report" / "index.html").is_file())
            self.assertTrue((run_dir / "report" / "report-data.json").is_file())
            self.assertFalse((run_dir / "report.md").exists())

    def test_supported_interactive_report_passes_with_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            run_dir = self.create_run(Path(directory), "test-supported-web-run")
            record_path = run_dir / "research-record.json"
            record = json.loads(record_path.read_text(encoding="utf-8"))
            record["plan"]["output_contract"] = {
                "coverage_universe_rule": "Single named issuer",
                "comparison_periods": ["FY2024", "FY2025"],
                "common_metrics": ["Revenue"],
                "sector_kpis": [],
                "required_bridge_or_ranking": "Revenue change bridge",
                "valuation_required": False,
                "planned_artifacts": ["report/index.html", "report/report-data.json"],
            }
            record["sources"] = [{
                "id": "SRC-001",
                "type": "regulatory-filing",
                "title": "Example Corp Annual Report",
                "publisher": "Example Corp",
                "url": "https://example.com/annual-report",
                "retrieved_at": "2026-09-03T12:00:00Z",
                "primary": True,
                "license_or_terms": "Public issuer filing",
            }]
            record["evidence"] = [{
                "id": "EVD-001",
                "source_id": "SRC-001",
                "locator": "Income statement, revenue row",
                "content": "Revenue increased year over year.",
            }]
            record["facts"] = [{
                "id": "FACT-001",
                "statement": "Revenue increased year over year.",
                "status": "verified",
                "material": True,
                "source_ids": ["SRC-001"],
                "evidence_ids": ["EVD-001"],
            }]
            for artifact in record["artifacts"]:
                artifact["fact_ids"] = ["FACT-001"]
            record_path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")

            report_data_path = run_dir / "report" / "report-data.json"
            report_data = json.loads(report_data_path.read_text(encoding="utf-8"))
            report_data["meta"]["coverage_universe"] = "Example Corp"
            report_data["executive_view"]["headline"] = "Revenue increased"
            report_data["executive_view"]["summary"] = "Reported revenue increased year over year."
            report_data["sections"] = [{
                "id": "dashboard",
                "type": "analysis",
                "fact_ids": ["FACT-001"],
                "source_ids": ["SRC-001"],
            }]
            report_data["sources"] = [{"source_id": "SRC-001"}]
            report_data_path.write_text(json.dumps(report_data, indent=2) + "\n", encoding="utf-8")
            (run_dir / "report" / "index.html").write_text(
                '<!doctype html><main id="finrunbook-report"></main><script>fetch("./report-data.json")</script>',
                encoding="utf-8",
            )
            self.complete_editorial_fixture(run_dir)

            process = subprocess.run(
                [sys.executable, str(VALIDATE), str(run_dir)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
            result = json.loads((run_dir / "validation.json").read_text(encoding="utf-8"))
            self.assertEqual(result["status"], "PASS")
            updated_data = json.loads(report_data_path.read_text(encoding="utf-8"))
            self.assertEqual(updated_data["validation"]["status"], "PASS")

    def test_empty_run_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            run_dir = self.create_run(Path(directory), "test-empty-run")
            process = subprocess.run(
                [sys.executable, str(VALIDATE), str(run_dir)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(process.returncode, 1)
            result = json.loads((run_dir / "validation.json").read_text(encoding="utf-8"))
            self.assertEqual(result["status"], "FAIL")
            codes = {item["code"] for item in result["issues"]}
            self.assertIn("record.no_facts", codes)
            self.assertIn("record.no_sources", codes)
            self.assertIn("plan.incomplete_finance_output_contract", codes)
            self.assertIn("artifact.incomplete_report_data", codes)
            self.assertIn("artifact.unrendered_scaffold", codes)
            self.assertIn("editorial.incomplete_review", codes)

    def test_report_language_precedence_and_artifact_consistency(self) -> None:
        cases = [
            ("tesla-chinese", "分析tesla，金融情况，股价泡沫，人员变动，竞争对手挤压，电动车未来趋势等等，目标是判断我是不是要在400这个价位买入并长期持有", [], "zh-CN", "request-script-heuristic"),
            ("english", "Analyze Tesla financial performance and valuation", [], "en", "english-fallback"),
            ("english-quoted-term", "Analyze Tesla and explain the Chinese term 股票 in the report", [], "en", "english-fallback"),
            ("chinese-finance-terms", "分析 SaaS 行业的 ARR、NRR 和 FCF", [], "zh-CN", "request-script-heuristic"),
            ("explicit-english", "分析特斯拉，用英文输出", ["--request-language", "zh-CN", "--language", "en"], "en", "explicit-output-language"),
            ("explicit-chinese", "Analyze Tesla and write the report in Chinese", ["--request-language", "en", "--language", "zh-CN"], "zh-CN", "explicit-output-language"),
            ("spanish-request", "Analiza las finanzas de Tesla", ["--request-language", "es"], "es", "request-language"),
            ("japanese-request", "テスラの財務状況を分析してください", ["--request-language", "ja"], "ja", "request-language"),
            ("short-request", "TSLA $400", [], "en", "english-fallback"),
            ("router-inference", "分析 Tesla. Source excerpt: Tesla manufactures electric vehicles and energy storage products around the world.", ["--request-language", "zh-CN"], "zh-CN", "request-language"),
        ]
        for run_id, request, flags, expected, source in cases:
            with self.subTest(run_id=run_id), tempfile.TemporaryDirectory() as directory:
                run_dir = self.create_run(Path(directory), run_id, ["--request", request, *flags])
                record = json.loads((run_dir / "research-record.json").read_text(encoding="utf-8"))
                presentation = json.loads((run_dir / "report/report-data.json").read_text(encoding="utf-8"))
                self.assertEqual(record["request"]["raw"], request)
                self.assertEqual(record["request"]["language"], expected)
                self.assertEqual(record["request"]["language_resolution"]["source"], source)
                self.assertTrue(all(artifact["language"] == expected for artifact in record["artifacts"]))
                self.assertEqual(presentation["meta"]["language"], expected)
                self.assertIn(f'<html lang="{expected}">', (run_dir / "report/index.html").read_text(encoding="utf-8"))

    def test_inferred_chinese_report_requires_chinese_editor(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            run_dir = self.create_run(Path(directory), "chinese-inferred", ["--request", "分析软件行业"])
            self.complete_editorial_fixture(run_dir)
            record = json.loads((run_dir / "research-record.json").read_text(encoding="utf-8"))
            self.assertEqual(record["request"]["language"], "zh-CN")
            self.assertEqual(record["editorial_review"]["upstream_skills"][0]["name"], "readable-human-writing")
            self.assertFalse(any(code.startswith("editorial.") for code in self.validation_codes(run_dir)))
            record["editorial_review"]["upstream_skills"][0]["name"] = "writing-clearly-and-concisely"
            (run_dir / "research-record.json").write_text(json.dumps(record), encoding="utf-8")
            self.assertIn("editorial.missing_language_editor", self.validation_codes(run_dir))

    def test_explicit_chinese_language_uses_chinese_editor(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            run_dir = self.create_run(Path(directory), "chinese-report", ["--language", "zh-CN"])
            self.complete_editorial_fixture(run_dir)
            self.assertFalse(any(code.startswith("editorial.") for code in self.validation_codes(run_dir)))
            record_path = run_dir / "research-record.json"
            record = json.loads(record_path.read_text(encoding="utf-8"))
            record["editorial_review"]["upstream_skills"] = []
            record_path.write_text(json.dumps(record), encoding="utf-8")
            self.assertIn("editorial.missing_language_editor", self.validation_codes(run_dir))

    def test_editorial_receipt_cannot_skip_required_checks(self) -> None:
        cases = [
            ("missing-log", "change_log_path", "missing.json", "editorial.missing_change_log"),
            ("outside-log", "change_log_path", "../outside.json", "editorial.missing_change_log"),
            ("changed-facts", "protected_items_preserved", False, "editorial.incomplete_review"),
            ("unresolved", "unresolved_issues", ["Unsupported certainty"], "editorial.incomplete_review"),
            ("unreviewed", "reviewed_artifacts", ["report/index.html"], "editorial.unreviewed_artifact"),
            ("wrong-locale", "languages", ["zh-CN"], "editorial.unreviewed_language"),
        ]
        for run_id, field, value, expected in cases:
            with self.subTest(case=run_id), tempfile.TemporaryDirectory() as directory:
                run_dir = self.create_run(Path(directory), run_id)
                self.complete_editorial_fixture(run_dir)
                record_path = run_dir / "research-record.json"
                record = json.loads(record_path.read_text(encoding="utf-8"))
                record["editorial_review"][field] = value
                record_path.write_text(json.dumps(record), encoding="utf-8")
                self.assertIn(expected, self.validation_codes(run_dir))

    def test_editorial_log_requires_edits_or_explicit_no_change(self) -> None:
        for log in ({"result": "edited", "changes": []}, {"changes": []}, {"result": "edited", "changes": [{}]}, []):
            with self.subTest(log=log), tempfile.TemporaryDirectory() as directory:
                run_dir = self.create_run(Path(directory), "invalid-editorial-log")
                self.complete_editorial_fixture(run_dir)
                (run_dir / "editorial-review.json").write_text(json.dumps(log), encoding="utf-8")
                self.assertIn("editorial.invalid_change_log", self.validation_codes(run_dir))

    def test_legacy_run_without_editorial_field_remains_readable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            run_dir = self.create_run(Path(directory), "legacy-run")
            record_path = run_dir / "research-record.json"
            record = json.loads(record_path.read_text(encoding="utf-8"))
            record.pop("editorial_review")
            record_path.write_text(json.dumps(record), encoding="utf-8")
            self.assertFalse(any(code.startswith("editorial.") for code in self.validation_codes(run_dir)))


if __name__ == "__main__":
    unittest.main()
