"""Offline packaging checks, not a financial or independent source audit."""

import json
import csv
import hashlib
import re
import subprocess
import unittest
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

SITE = Path(__file__).resolve().parents[1] / "examples"
CATALOG = json.loads((SITE / "catalog.json").read_text(encoding="utf-8"))
EXAMPLES = tuple(item["slug"] for item in CATALOG)


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.urls = []

    def handle_starttag(self, tag, attrs):
        self.urls.extend(value for key, value in attrs
                         if key in ("href", "src") and value)


class PreviewValues(HTMLParser):
    """Collect annotated preview cells, excluding their small-print labels."""

    def __init__(self):
        super().__init__()
        self.package = None
        self.cell = None
        self.small = False
        self.values = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "table":
            self.package = attrs.get("data-package")
        if tag == "td" and ("data-fact" in attrs or "data-output" in attrs):
            self.cell = {**attrs, "package": self.package, "text": ""}
        if tag == "small":
            self.small = True

    def handle_data(self, text):
        if self.cell is not None and not self.small:
            self.cell["text"] += text

    def handle_endtag(self, tag):
        if tag == "small":
            self.small = False
        if tag == "td" and self.cell is not None:
            self.values.append(self.cell)
            self.cell = None
        if tag == "table":
            self.package = None


class ExamplesSiteTest(unittest.TestCase):
    def test_gallery_previews_match_saved_evidence(self):
        preview = PreviewValues()
        preview.feed((SITE / "index.html").read_text())
        facts = [row for row in preview.values if "data-fact" in row]
        self.assertEqual(len(facts), 11)
        for row in facts:
            data = json.loads((SITE / row["package"] / "report/report-data.json").read_text())
            fact = next(f for f in data["facts"] if f["id"] == row["data-fact"])
            numeric = row["text"].replace(",", "").strip().lstrip(">").rstrip("%")
            decimals = len(numeric.split(".")[1]) if "." in numeric else 0
            self.assertAlmostEqual(float(numeric), fact["value"] * float(row["data-scale"]),
                                   delta=0.5 * 10 ** -decimals)
            if "strictly greater than" in fact["units"]:
                self.assertTrue(row["text"].strip().startswith(">"))
        cleaning = json.loads((SITE / "financial-data-cleaning/data.json").read_text())
        outputs = {row["id"]: row for row in cleaning["outputs"]}
        rows = [row for row in preview.values if "data-output" in row]
        self.assertEqual(len(rows), 4)
        for row in rows:
            expected = outputs[row["data-output"]]
            if expected["value"] is None:
                self.assertEqual(row["text"].strip(), "Missing")
            else:
                self.assertIn(format(expected["value"], ","), row["text"])
            if expected["operator"] == ">":
                self.assertTrue(row["text"].strip().startswith(">"))

    def test_local_previews_cannot_be_committed(self):
        result = subprocess.run(
            ["git", "ls-files", "--", "examples/local/"],
            cwd=SITE.parent, text=True, capture_output=True, check=True,
        )
        self.assertEqual(result.stdout.strip(), "",
                         "Local previews need a data-use review before publication")

    def assert_local_url(self, source, url):
        parts = urlsplit(url)
        if parts.scheme or parts.netloc or not parts.path:
            return
        self.assertFalse(parts.path.startswith("/"), f"Root-relative URL: {url}")
        target = (source.parent / unquote(parts.path)).resolve()
        self.assertTrue(target.is_relative_to(SITE.resolve()), f"Escaped site: {url}")
        if target.is_dir():
            target /= "index.html"
        self.assertTrue(target.is_file(), f"Missing target: {source}: {url}")

    def test_landing_page_links_every_example(self):
        links = Links()
        links.feed((SITE / "index.html").read_text(encoding="utf-8"))
        for slug in EXAMPLES:
            self.assertIn(f"{slug}/report/", links.urls)

    def test_catalog_includes_two_chinese_reports(self):
        self.assertEqual(len(EXAMPLES), len(set(EXAMPLES)))
        self.assertGreaterEqual(sum(item["language"] == "zh-CN" for item in CATALOG), 2)
        for slug in EXAMPLES:
            self.assertTrue((SITE / slug).is_dir())

    def test_html_and_static_javascript_links_resolve(self):
        for source in SITE.rglob("*.html"):
            links = Links()
            links.feed(source.read_text(encoding="utf-8"))
            for url in links.urls:
                if "${" not in url:
                    self.assert_local_url(source, url)
        for source in SITE.rglob("*.js"):
            text = source.read_text(encoding="utf-8")
            urls = re.findall(r'(?:href|src)="([^"\n]+)"', text)
            urls += re.findall(r"fetch\(['\"]([^'\"]+)['\"]\)", text)
            for url in urls:
                if "${" not in url:
                    self.assert_local_url(source, url)

    def test_report_packages_and_existing_receipts(self):
        for item in CATALOG:
            slug = item["slug"]
            root = SITE / slug
            required = ["index.html", "report-data.json"]
            if item["profile"] != "inline":
                required += ["style.css", "app.js"]
            for name in required:
                self.assertTrue((root / "report" / name).is_file())
            data = json.loads((root / "report/report-data.json").read_text())
            record = json.loads((root / "research-record.json").read_text())
            expected_status = item.get("validation_status", "PASS")
            self.assertIn(expected_status, ("PASS", "PASS_WITH_WARNINGS"))
            self.assertEqual(data["validation"]["status"], expected_status)
            self.assertEqual(data["meta"]["language"], item["language"])
            self.assertEqual(record["request"]["language"], item["language"])
            self.assertEqual(record["editorial_review"]["status"], "completed")
            self.assertEqual(len(record["sources"]), item["sources"])
            for key in ("facts", "evidence", "sources", "calculations"):
                self.assertTrue(record[key])
                if item["profile"] != "inline":
                    self.assertEqual(data[key], record[key])
            record_sources = {source["id"]: source for source in record["sources"]}
            for source in data["sources"]:
                self.assertEqual(source["url"], record_sources[source["id"]]["url"])
            receipts = ["validation.json", "browser-tests.json"]
            if item["model_receipt"]:
                receipts.append(item["model_receipt"])
            for name in receipts:
                receipt = json.loads((root / name).read_text())
                self.assertEqual(receipt["status"], expected_status if name == "validation.json" else "PASS")
                if name == "validation.json" and expected_status == "PASS_WITH_WARNINGS":
                    self.assertEqual(receipt["summary"]["errors"], 0)
                    warnings = [issue["code"] for issue in receipt["issues"]
                                if issue["severity"] == "warning"]
                    self.assertTrue(warnings)
                    self.assertEqual(sorted(warnings), sorted(item["expected_warning_codes"]))
                    self.assertEqual(receipt["summary"]["warnings"], len(warnings))
                    self.assertEqual(data["validation"]["warnings"], len(warnings))
                    self.assertIn("PASS_WITH_WARNINGS", (root / "README.md").read_text())
            self.assertTrue((root / "editorial-review.json").is_file())
            self.assertTrue((root / "prompt.txt").is_file())

    def test_market_history_excerpt_preserves_references_and_model(self):
        root = SITE / "sp500-20year-return-risk"
        data = json.loads((root / "report/report-data.json").read_text())
        record = json.loads((root / "research-record.json").read_text())
        receipt = json.loads((root / "publication-review.json").read_text())
        self.assertEqual(receipt["status"], "PASS")
        self.assertEqual(record["package_type"], "report-evidence-excerpt")
        self.assertNotIn("market_data", record)
        self.assertTrue(data["meta"]["public_distribution"])
        self.assertFalse((root / "artifacts").exists())
        for key, count in {"facts": 20, "evidence": 16, "sources": 9, "calculations": 8}.items():
            self.assertEqual(len(record[key]), count)
            self.assertEqual(record["publication"]["excerpt_counts"][key], count)
        digest = hashlib.sha256(json.dumps(data["model"], sort_keys=True).encode()).hexdigest()
        self.assertEqual(digest, receipt["unchanged_model_sha256"])
        ids = {key: {row["id"] for row in data[key]}
               for key in ("facts", "evidence", "sources", "calculations")}
        reference_fields = {"fact_ids": "facts", "input_fact_ids": "facts",
                            "source_ids": "sources", "evidence_ids": "evidence",
                            "calculation_ids": "calculations"}

        def visit(value):
            if isinstance(value, dict):
                for key, child in value.items():
                    if key in reference_fields:
                        self.assertTrue(set(child) <= ids[reference_fields[key]],
                                        f"Unresolved {key}: {child}")
                    elif key == "source_id":
                        self.assertIn(child, ids["sources"])
                    visit(child)
            elif isinstance(value, list):
                for child in value:
                    visit(child)
        visit(data)

    def test_no_private_files_or_machine_paths(self):
        allowed_suffixes = {".html", ".css", ".js", ".json", ".txt", ".md", ".csv"}
        forbidden_parts = {"run", "runs", "raw", "artifacts", ".git", "node_modules"}
        for path in SITE.rglob("*"):
            self.assertFalse(path.is_symlink(), f"Do not publish symlinks: {path}")
            self.assertFalse(forbidden_parts.intersection(path.relative_to(SITE).parts))
            if not path.is_file():
                continue
            self.assertIn(path.suffix, allowed_suffixes, f"Review public file: {path}")
            text = path.read_text(encoding="utf-8")
            self.assertFalse(bool(re.search(r"/Users/|/private/|/home/|-----BEGIN .*PRIVATE KEY-----", text)),
                             f"Machine path or private key in {path.name}")
            self.assertFalse(bool(re.search(r"(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}|(?<![A-Za-z0-9_/-])sk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{32,})", text)),
                             f"Possible credential in {path.name}")
            if path.suffix == ".json":
                json.loads(text)

    def test_earnings_export_matches_original_facts(self):
        root = SITE / "lululemon-earnings-update"
        data = json.loads((root / "report/report-data.json").read_text())
        facts = {f["id"]: f for f in data["facts"]}
        sources = {s["id"]: s for s in data["sources"]}
        with (root / "earnings-update.csv").open(newline="") as stream:
            rows = list(csv.DictReader(stream))
        self.assertTrue(rows)
        for row in rows:
            fact = facts[row["fact_id"]]
            self.assertEqual(float(row["value"]), fact["value"])
            self.assertEqual(row["period"], fact["period"])
            self.assertEqual(row["units"], fact["units"])
            self.assertEqual(row["calculation_id"], fact.get("calculation_id", ""))
            self.assertEqual(row["source_urls"], " | ".join(sources[i]["url"] for i in fact["source_ids"]))

    def test_cleaning_cases_preserve_sources_and_boundaries(self):
        root = SITE / "financial-data-cleaning"
        data = json.loads((root / "data.json").read_text())
        inputs = {r["id"]: r for r in data["inputs"]}
        outputs = {r["id"]: r for r in data["outputs"]}
        for row in inputs.values():
            original = json.loads((SITE / row["source_package"] / "report/report-data.json").read_text())
            fact = next(f for f in original["facts"] if f["id"] == row["fact_id"])
            self.assertEqual(row["value"], fact.get("value"))
            if row.get("record_type") != "coverage annotation":
                self.assertEqual(row["units"], fact["units"])
        # Separately specified expected values: catches sign, scale and period errors.
        self.assertEqual([r["value"] for r in data["outputs"][:4]], [131819, 680.802, 11102.6, 128725])
        self.assertEqual([r["value"] for r in data["outputs"][4:7]], [2415.631, 1461.878, 453.653])
        for row in data["outputs"][4:7]:
            h, q1, reported = [inputs[i] for i in row["input_ids"]]
            self.assertEqual(h["start_date"], q1["start_date"])
            self.assertEqual(h["scope"], q1["scope"])
            self.assertAlmostEqual((h["value"]-q1["value"])/1000, row["value"])
            self.assertAlmostEqual(reported["value"]/1000, row["value"])
            self.assertEqual(row["duration"], "13 weeks")
        threshold = next(r for r in outputs.values() if r["operator"] == ">")
        self.assertEqual(threshold["value"], 75000)
        self.assertEqual(threshold["end_date"], "2025-06-30")
        self.assertIn("excluded", threshold["status"])
        missing = next(r for r in outputs.values() if r["value"] is None)
        self.assertEqual(missing["status"], "missing; no imputation")
        self.assertGreater(sum(not x["resolved"] for x in data["exceptions"]), 0)
        with (root / "cleaned-data.csv").open(newline="") as stream:
            rows = list(csv.DictReader(stream))
        for row in rows:
            expected = outputs[row["id"]]
            self.assertEqual(row["value"], "" if expected["value"] is None else str(expected["value"]))
            self.assertEqual(json.loads(row["input_ids"]), expected["input_ids"])


if __name__ == "__main__":
    unittest.main()
