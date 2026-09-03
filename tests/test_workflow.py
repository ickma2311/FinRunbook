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
    def create_run(self, runs_dir: Path, run_id: str) -> Path:
        process = subprocess.run(
            [
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
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        return Path(process.stdout.strip())

    def test_supported_run_passes_and_report_gets_sources(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            run_dir = self.create_run(Path(directory), "test-supported-run")
            record_path = run_dir / "research-record.json"
            record = json.loads(record_path.read_text(encoding="utf-8"))
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


if __name__ == "__main__":
    unittest.main()

