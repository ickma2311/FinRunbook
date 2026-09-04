"""Offline packaging checks, not a financial or independent source audit."""

import json
import re
import unittest
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

SITE = Path(__file__).resolve().parents[1] / "examples"
EXAMPLES = ("apple-business-quality", "cloud-computing")


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

    def test_landing_page_links_both_examples(self):
        links = Links()
        links.feed((SITE / "index.html").read_text(encoding="utf-8"))
        for slug in EXAMPLES:
            self.assertIn(f"{slug}/report/", links.urls)

    def test_html_and_static_javascript_links_resolve(self):
        for source in SITE.rglob("*.html"):
            links = Links()
            links.feed(source.read_text(encoding="utf-8"))
            for url in links.urls:
                self.assert_local_url(source, url)
        for source in SITE.rglob("*.js"):
            text = source.read_text(encoding="utf-8")
            urls = re.findall(r'(?:href|src)="([^"\n]+)"', text)
            urls += re.findall(r"fetch\(['\"]([^'\"]+)['\"]\)", text)
            for url in urls:
                if "${" not in url:
                    self.assert_local_url(source, url)

    def test_report_packages_and_existing_receipts(self):
        for slug in EXAMPLES:
            root = SITE / slug
            for name in ("index.html", "style.css", "app.js", "report-data.json"):
                self.assertTrue((root / "report" / name).is_file())
            data = json.loads((root / "report/report-data.json").read_text())
            record = json.loads((root / "research-record.json").read_text())
            self.assertEqual(data["validation"]["status"], "PASS")
            self.assertEqual(data["meta"]["language"], "en")
            for key in ("facts", "evidence", "sources", "calculations"):
                self.assertTrue(data[key])
                self.assertEqual(data[key], record[key])
            for name in ("validation.json", "model-audit.json", "browser-tests.json"):
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
            self.assertNotRegex(text, r"/Users/|/private/|/home/|-----BEGIN .*PRIVATE KEY-----")
            self.assertNotRegex(text, r"(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}|sk-[A-Za-z0-9_-]{30,})")
            if path.suffix == ".json":
                json.loads(text)


if __name__ == "__main__":
    unittest.main()
