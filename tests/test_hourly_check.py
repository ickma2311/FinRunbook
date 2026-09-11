"""Offline hourly eligibility tests; no models, market data or paper trades."""
import copy
import importlib.util
from pathlib import Path
import tempfile
import unittest
import io
import json
import sys
from contextlib import redirect_stdout
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "hourly_check", ROOT / "skills/finrunbook-hourly/scripts/check_due.py")
hourly = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(hourly)
s = hourly.schedule
NOW = s.timestamp("2026-09-09T21:00:00Z")


class HourlyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.profiles = [{"id": key, "regular_interval_hours": 24,
                          "min_interval_hours": 2, "retry_cooldown_hours": 4,
                          "max_runs_per_day": 2, "event_types": ["earnings"]}
                         for key in ("quality", "trend")]
        self.states = {key: s.empty_state() for key in ("quality", "trend")}
        self.registry = {"schema_version": 1, "experts": [
            {"id": key, "account": key + ".json", "account_id": key + "-account",
             "schedule_state": "state.json"} for key in self.states]}
        self.write("policy.json", {"schema_version": 1, "timezone": "America/New_York",
                                   "experts": self.profiles})
        for key in self.states:
            self.write(key + ".json", {"expert_id": key, "account_id": key + "-account"})
        self.save()

    def write(self, name, value):
        s.write_json(self.root / name, value)

    def save(self):
        self.write("registry.json", self.registry)
        self.write("state.json", {"schema_version": 1, "experts": self.states})

    def check(self, events=None):
        if events is not None:
            self.write("events.json", events)
        return hourly.check_registry(self.root, self.root / "registry.json",
                                     self.root / "policy.json",
                                     self.root / "events.json" if events is not None else None, NOW)

    def attempt(self, key, outcome="completed"):
        own = self.states[key]
        started = "2026-09-09T10:00:00Z"
        attempt = {"id": "attempt-" + key, "started_at": started,
                   "event_ids": [], "outcome": outcome}
        own.update(last_attempt_at=started, attempts=[attempt])
        if outcome is None:
            own["active_attempt"] = attempt["id"]
        else:
            attempt["finished_at"] = "2026-09-09T11:00:00Z"
            if outcome == "completed":
                own["last_successful_research_at"] = attempt["finished_at"]
        self.save()

    def test_initial_due_and_no_source_mutation(self):
        before = {p: p.read_bytes() for p in self.root.glob("*.json")}
        result = self.check()
        self.assertEqual(result["due_experts"], ["quality", "trend"])
        self.assertEqual(result["mode"], "schedule_only")
        self.assertEqual(before, {p: p.read_bytes() for p in before})

    def test_fatal_collection_still_assesses_independently_due_experts(self):
        script_dir = str(ROOT / "skills/finrunbook-hourly/scripts")
        with patch.dict(sys.modules), patch.object(sys, "path", [script_dir] + sys.path):
            import collect_events
            self.write("skills/finrunbook-hourly/references/event-sources.json", {})
            self.attempt("quality")
            with patch.object(hourly, "ROOT", self.root), patch.object(s, "now_utc", return_value=NOW), \
                 patch.object(collect_events, "collect", side_effect=ValueError("fixture collection locked")):
                output = io.StringIO()
                with redirect_stdout(output):
                    status = hourly.main(["--registry", "registry.json", "--policy", "policy.json", "--collect-events"])
            receipt = json.loads(output.getvalue())
            self.assertEqual(status, 2)
            self.assertEqual(receipt["due_experts"], ["trend"])
            self.assertEqual(receipt["mode"], "schedule_only")
            self.assertEqual(receipt["collection"]["status"], "failed")
            self.assertIsNone(receipt["collection"]["events_path"])

    def test_success_without_trade_skips(self):
        self.attempt("quality")
        self.assertEqual(self.check()["due_experts"], ["trend"])

    def test_active_attempt_prevents_duplicate(self):
        self.attempt("trend", None)
        result = self.check()
        self.assertEqual(result["due_experts"], ["quality"])
        self.assertIn("active_attempt", result["experts"][1]["reasons"])

    def test_blocked_waits_for_new_event(self):
        self.attempt("quality", "blocked")
        self.assertNotIn("quality", self.check()["due_experts"])
        event = {"id": "new-filing", "type": "earnings",
                 "available_at": "2026-09-09T20:00:00Z", "expert_ids": ["quality"]}
        self.assertIn("quality", self.check([event])["due_experts"])
        event["available_at"] = "2026-09-10T20:00:00Z"
        self.assertNotIn("quality", self.check([event])["due_experts"])

    def test_bad_state_isolated(self):
        self.states["quality"]["attempts"] = None
        self.save()
        result = self.check()
        self.assertEqual(result["due_experts"], ["trend"])
        self.assertEqual(result["error_count"], 1)

    def test_missing_state_not_initial_research(self):
        self.registry["experts"][0]["schedule_state"] = "missing.json"
        self.save()
        self.assertEqual(self.check()["due_experts"], ["trend"])
        self.assertFalse((self.root / "missing.json").exists())

    def test_wrong_account_identity_blocked(self):
        self.write("quality.json", {"expert_id": "trend", "account_id": "quality-account"})
        self.assertEqual(self.check()["due_experts"], ["trend"])

    def test_duplicate_registry_rejected(self):
        self.registry["experts"].append(copy.deepcopy(self.registry["experts"][0]))
        self.save()
        with self.assertRaises(ValueError):
            self.check()

    def test_invalid_event_feed_not_silently_ignored(self):
        with self.assertRaises(ValueError):
            self.check([{"narrative": "buy gold"}])

    def test_dispatch_policy_matches_state_subset(self):
        self.write("own-state.json", {"schema_version": 1,
                                      "experts": {"quality": self.states["quality"]}})
        self.registry["experts"][0]["schedule_state"] = "own-state.json"
        self.save()
        policy = self.check()["experts"][0]["dispatch_policy"]
        self.assertEqual([p["id"] for p in policy["experts"]], ["quality"])


if __name__ == "__main__":
    unittest.main()
