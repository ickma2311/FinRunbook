"""Synthetic collector tests: no network, inference, account writes or trades."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace
from datetime import timedelta

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = ROOT / "skills/finrunbook-hourly/scripts"
sys.path.insert(0, str(SCRIPT_DIR))
import collect_events as e
from check_due import check_registry

BASE = "2026-09-09T12:00:00Z"
NOW = "2026-09-10T13:00:00Z"
PROFILE = {"id": "macro", "regular_interval_hours": 24, "min_interval_hours": 2,
           "retry_cooldown_hours": 4, "max_runs_per_day": 3,
           "event_types": ["macro_release", "policy_change"]}
SPEC = {"id": "bls-cpi", "url": "https://www.bls.gov/feed/cpi.rss",
        "kind": "rss", "type": "macro_release", "expert_ids": ["macro"]}


def item(key="release", at=NOW):
    return {"key": key, "published_at": at, "title": "CPI release",
            "url": "https://www.bls.gov/news.release/cpi.htm", "types": ["macro_release"]}


class MergeTests(unittest.TestCase):
    def setUp(self):
        self.state = {"schema_version": 1, "sources": {}, "events": [], "evidence": {}}

    def merge(self, items, at=NOW):
        return e.merge_source(self.state, SPEC, items, at, "/tmp/raw.json", "hash", {"macro": PROFILE})

    def test_baseline_does_not_emit_archive(self):
        self.assertEqual(self.merge([item()])["status"], "baselined")
        self.assertEqual(self.state["events"], [])

    def test_new_event_deduplicated_and_preserved(self):
        self.merge([], BASE)
        self.assertEqual(self.merge([item()])["new_events"], 1)
        self.assertEqual(self.merge([item()])["new_events"], 0)
        self.merge([])
        self.assertEqual(len(self.state["events"]), 1)
        self.assertEqual(set(self.state["events"][0]), {"id", "type", "available_at", "expert_ids"})
        self.assertEqual(self.state["events"][0]["available_at"], NOW)

    def test_future_not_consumed(self):
        self.merge([], BASE)
        self.merge([item(at="2026-09-11T13:00:00Z")])
        self.assertNotIn("release", self.state["sources"][SPEC["id"]]["seen"])
        self.merge([item(at="2026-09-11T13:00:00Z")], "2026-09-11T14:00:00Z")
        self.assertEqual(len(self.state["events"]), 1)

    def test_late_archive_not_new(self):
        self.merge([], BASE)
        self.merge([item(at="2026-09-08T13:00:00Z")])
        self.assertEqual(self.state["events"], [])

    def test_routing_filters_expert_profile(self):
        self.merge([], BASE)
        x = item(); x["types"] = ["earnings"]
        self.merge([x])
        self.assertEqual(self.state["events"], [])

    def test_event_makes_recent_success_due_then_consumed(self):
        self.merge([], BASE); self.merge([item()])
        s = e.schedule.empty_state()
        s.update(last_attempt_at=BASE, last_successful_research_at="2026-09-10T08:00:00Z",
                 attempts=[{"id": "one", "started_at": BASE, "finished_at": "2026-09-10T08:00:00Z",
                            "event_ids": [], "outcome": "completed"}])
        self.assertFalse(e.schedule.assess(PROFILE, s, [], NOW)["due"])
        self.assertTrue(e.schedule.assess(PROFILE, s, self.state["events"], NOW)["due"])
        s["processed_event_ids"] = [self.state["events"][0]["id"]]
        self.assertFalse(e.schedule.assess(PROFILE, s, self.state["events"], NOW)["due"])


class ParserTests(unittest.TestCase):
    def test_http_denial_retains_sanitized_body_and_status(self):
        response = SimpleNamespace(returncode=0, stderr=b"", stdout=(
            b'<html>Access denied 192.0.2.4 contact@example.com token=secret-value</html>\n403'))
        with patch.object(e.subprocess, "run", return_value=response):
            with self.assertRaises(e.SourceRequestError) as caught:
                e.fetch(SPEC["url"], {"user_agent": "fixture", "timeout_seconds": 1,
                                      "max_response_bytes": 4096})
        detail = e.failure_detail(caught.exception, SPEC)
        self.assertEqual(detail["http_status"], 403)
        self.assertIn("Access denied", detail["body_excerpt"])
        for secret in ("192.0.2.4", "contact@example.com", "secret-value"):
            self.assertNotIn(secret, detail["body_excerpt"])
        self.assertNotIn("secret-token", e.sanitized_excerpt("Authorization: Bearer secret-token"))

    def test_rss_and_reused_release_url(self):
        raw = b'<rss><channel><item><title>CPI</title><link>https://www.bls.gov/news.release/cpi.htm</link><pubDate>Thu, 10 Sep 2026 08:30:00 -0400</pubDate></item></channel></rss>'
        a = e.rss_items(raw, SPEC)[0]
        b = e.rss_items(raw.replace(b'10 Sep', b'11 Sep'), SPEC)[0]
        self.assertNotEqual(a["key"], b["key"])
        self.assertEqual(a["published_at"], "2026-09-10T12:30:00Z")

    def test_atom(self):
        raw = b'<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>CPI</title><id>one</id><link href="https://www.bls.gov/news.release/cpi.htm"/><updated>2026-09-10T12:30:00Z</updated></entry></feed>'
        self.assertEqual(len(e.rss_items(raw, SPEC)), 1)

    def test_html_and_missing_dates_rejected(self):
        for raw in (b'<html>Access denied</html>', b'<rss><channel><item><title>X</title></item></channel></rss>'):
            with self.assertRaises(ValueError): e.rss_items(raw, SPEC)

    def test_sec_earnings_amendment_and_identity(self):
        data = {"cik": "320193", "filings": {"recent": {
            "accessionNumber": ["0000320193-26-000001", "0000320193-26-000002"],
            "form": ["8-K", "10-K/A"], "items": ["2.02,9.01", ""],
            "primaryDocument": ["earnings.htm", "amend.htm"], "acceptanceDateTime": [NOW, NOW]}}}
        spec = {"cik": 320193, "symbol": "AAPL"}
        items = e.sec_items(json.dumps(data), spec)
        self.assertEqual(items[0]["types"], ["material_disclosure", "earnings"])
        self.assertEqual(items[1]["types"], ["amendment"])
        spec["cik"] = 1
        with self.assertRaises(ValueError): e.sec_items(json.dumps(data), spec)

    def test_source_allowlist(self):
        with self.assertRaises(ValueError): e.safe_url("http://localhost/private")


class CollectionTests(unittest.TestCase):
    def test_persistent_denial_backoff_changed_failure_and_recovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            e.schedule.write_json(root / "account.json", {"expert_id": "macro", "account_id": "m", "universe": []})
            e.schedule.write_json(root / "registry.json", {"schema_version": 1, "experts": [
                {"id": "macro", "account_id": "m", "account": "account.json"}]})
            e.schedule.write_json(root / "policy.json", {"schema_version": 1,
                "timezone": "America/New_York", "experts": [PROFILE]})
            config = {"companies": {}, "excluded_funds": [], "feeds": [SPEC]}
            now = e.schedule.timestamp(NOW)
            calls = []
            response_status = 403
            def fake(url, config):
                calls.append(url)
                if response_status:
                    raise e.SourceRequestError(f"HTTP {response_status}", response_status, b"Access denied")
                return b'<rss><channel></channel></rss>'
            def collect(at):
                with patch.object(e.schedule, "now_utc", return_value=at):
                    return e.collect(root, config, root / "registry.json", root / "policy.json",
                                     root / "cache/state.json", fake)
            first = collect(now)
            self.assertTrue(first["notification_required"])
            self.assertEqual(first["sources"][0]["next_retry_at"], e.schedule.iso(now + timedelta(hours=1)))
            skipped = collect(now + timedelta(minutes=30))
            self.assertEqual(len(calls), 1)
            self.assertEqual(skipped["status"], "partial")
            self.assertEqual(skipped["error_count"], 1)
            self.assertEqual(skipped["sources"][0]["status"], "backoff")
            self.assertFalse(skipped["notification_required"])
            second = collect(now + timedelta(hours=1))
            self.assertFalse(second["notification_required"])
            self.assertEqual(second["sources"][0]["next_retry_at"], e.schedule.iso(now + timedelta(hours=3)))
            for count in range(3, 9):
                at = e.schedule.timestamp(second["sources"][0]["next_retry_at"])
                second = collect(at)
                delay = e.schedule.timestamp(second["sources"][0]["next_retry_at"]) - at
                self.assertEqual(delay.total_seconds(), min(86400, 3600 * 2 ** (count - 1)))
            response_status = 500
            at = e.schedule.timestamp(second["sources"][0]["next_retry_at"])
            changed = collect(at)
            self.assertTrue(changed["notification_required"])
            self.assertEqual(changed["sources"][0]["http_status"], 500)
            response_status = None
            recovered = collect(at + timedelta(minutes=1))
            self.assertTrue(recovered["notification_required"])
            self.assertTrue(recovered["sources"][0]["recovered"])
            self.assertEqual(recovered["sources"][0]["status"], "baselined")
            self.assertFalse(collect(at + timedelta(minutes=2))["notification_required"])
            self.assertEqual(e.schedule.read_json(recovered["events_path"]), [])

    def test_incomplete_account_routing_does_not_advance_shared_issuers(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            e.schedule.write_json(root / "good.json", {"expert_id": "quality", "account_id": "q", "universe": ["AAPL"]})
            config = {"companies": {"AAPL": 320193}, "excluded_funds": [], "feeds": [SPEC]}
            registry = {"experts": [{"id": "quality", "account_id": "q", "account": "good.json"},
                                    {"id": "growth", "account_id": "g", "account": "missing.json"}]}
            specs, errors = e.sources(config, registry, root)
            self.assertTrue(errors)
            self.assertFalse(any(x["kind"] == "sec" for x in specs))
            self.assertEqual(specs[0]["id"], "bls-cpi")

    def test_partial_failure_preserves_success_and_valid_feed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            e.schedule.write_json(root / "account.json", {"expert_id": "macro", "account_id": "m", "universe": ["SPY"]})
            e.schedule.write_json(root / "registry.json", {"schema_version": 1, "experts": [{"id": "macro", "account_id": "m", "account": "account.json"}]})
            e.schedule.write_json(root / "policy.json", {"schema_version": 1, "timezone": "America/New_York", "experts": [PROFILE]})
            config = {"companies": {}, "excluded_funds": ["SPY"], "feeds": [SPEC, {**SPEC, "id": "failed", "url": "https://www.bls.gov/feed/ppi.rss"}]}
            def fake(url, config):
                if "ppi" in url: raise ValueError("HTTP 403")
                return b'<rss><channel></channel></rss>'
            receipt = e.collect(root, config, root / "registry.json", root / "policy.json", root / "cache/state.json", fake)
            self.assertEqual(receipt["status"], "partial")
            state = e.schedule.read_json(root / "cache/state.json")
            self.assertIn("bls-cpi", state["sources"])
            self.assertNotIn("failed", state["sources"])
            self.assertEqual(e.schedule.read_json(receipt["events_path"]), [])
            before = (root / "account.json").read_bytes()
            second = e.collect(root, config, root / "registry.json", root / "policy.json", root / "cache/state.json", fake)
            self.assertEqual(second["sources"][0]["status"], "ok")
            self.assertEqual(before, (root / "account.json").read_bytes())


if __name__ == "__main__":
    unittest.main()
