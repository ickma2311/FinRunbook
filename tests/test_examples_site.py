"""Offline packaging checks, not a financial or independent source audit."""

import json
import re
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


class ExamplesSiteTest(unittest.TestCase):
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
            self.assertEqual(data["validation"]["status"], "PASS")
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
                self.assertEqual(json.loads((root / name).read_text())["status"], "PASS")
            self.assertTrue((root / "editorial-review.json").is_file())
            self.assertTrue((root / "prompt.txt").is_file())

    def test_no_private_files_or_machine_paths(self):
        allowed_suffixes = {".html", ".css", ".js", ".json", ".txt", ".md"}
        forbidden_parts = {"runs", "raw", "artifacts", ".git", "node_modules"}
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


if __name__ == "__main__":
    unittest.main()
