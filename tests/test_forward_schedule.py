"""Offline scheduling invariants; no research, market data, or simulator execution."""
import copy
from datetime import timedelta
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "skills/finrunbook-investor/scripts/forward_schedule.py"
SPEC = importlib.util.spec_from_file_location("forward_schedule", SCRIPT)
scheduler = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(scheduler)
NOW = scheduler.timestamp("2026-09-09T14:00:00Z")
PROFILE = dict(id="value", regular_interval_hours=48, min_interval_hours=1,
               max_runs_per_day=3, retry_cooldown_hours=4, event_types=["filing"])


def event(identity="one", at=NOW, experts=None):
    return dict(id=identity, type="filing", available_at=scheduler.iso(at), expert_ids=experts or ["value"])


def attempted(at=NOW, outcome="completed", finished=None, ids=None):
    state = scheduler.empty_state()
    attempt = dict(id="attempt-one", started_at=scheduler.iso(at), event_ids=ids or [], outcome=outcome)
    state["last_attempt_at"] = scheduler.iso(at)
    if outcome:
        attempt["finished_at"] = scheduler.iso(finished or at)
        if outcome == "completed":
            state["last_successful_research_at"] = state["last_decision_at"] = attempt["finished_at"]
            state["processed_event_ids"] = list(ids or [])
    else:
        state["active_attempt"] = attempt["id"]
    state["attempts"].append(attempt)
    return state


class AssessmentTests(unittest.TestCase):
    def test_initial_and_independent_experts(self):
        self.assertTrue(scheduler.assess(PROFILE, scheduler.empty_state(), [], NOW)["due"])
        self.assertFalse(scheduler.assess(PROFILE, attempted(), [], NOW)["due"])
        other = dict(PROFILE, id="growth")
        self.assertTrue(scheduler.assess(other, scheduler.empty_state(), [], NOW)["due"])

    def test_no_daily_requirement_and_regular_elapsed_time(self):
        state = attempted()
        self.assertFalse(scheduler.assess(PROFILE, state, [], NOW + timedelta(days=1))["due"])
        self.assertTrue(scheduler.assess(PROFILE, state, [], NOW + timedelta(days=2))["due"])

    def test_events_are_new_targeted_and_available(self):
        state = attempted(ids=["one"])
        events = [event(), event("two"), event("future", NOW + timedelta(days=1)), event("other", experts=["growth"])]
        result = scheduler.assess(PROFILE, state, events, NOW + timedelta(hours=2))
        self.assertTrue(result["due"])
        self.assertEqual(result["event_ids"], ["two"])
        self.assertFalse(scheduler.assess(PROFILE, state, [event()], NOW + timedelta(hours=2))["due"])

    def test_future_event_becomes_eligible_only_after_available(self):
        state = attempted()
        future = event(at=NOW + timedelta(hours=3))
        self.assertFalse(scheduler.assess(PROFILE, state, [future], NOW + timedelta(hours=2))["due"])
        self.assertTrue(scheduler.assess(PROFILE, state, [future], NOW + timedelta(hours=3))["due"])

    def test_min_interval_and_next_review(self):
        state = attempted()
        state["next_review_at"] = scheduler.iso(NOW)
        result = scheduler.assess(PROFILE, state, [event()], NOW)
        self.assertFalse(result["due"])
        self.assertIn("min_interval", result["reasons"])
        self.assertEqual(result["next_eligible_at"], scheduler.iso(NOW + timedelta(hours=1)))
        self.assertTrue(scheduler.assess(PROFILE, state, [], NOW + timedelta(hours=1))["due"])

    def test_retry_transient_outcomes_from_finish(self):
        for outcome in ("failed", "cancelled"):
            with self.subTest(outcome=outcome):
                state = attempted(outcome=outcome, finished=NOW + timedelta(hours=2), ids=["one"])
                result = scheduler.assess(PROFILE, state, [event()], NOW + timedelta(hours=5))
                self.assertFalse(result["due"])
                self.assertEqual(result["event_ids"], ["one"])
                self.assertIn("retry_cooldown", result["reasons"])
                self.assertTrue(scheduler.assess(PROFILE, state, [], NOW + timedelta(hours=6))["due"])

    def test_blocked_requires_genuinely_new_evidence_after_cooldown(self):
        state = attempted(outcome="blocked", finished=NOW + timedelta(hours=2), ids=["one"])
        state["next_review_at"] = scheduler.iso(NOW + timedelta(hours=3))
        for events in ([], [event()], [event("other", experts=["growth"])],
                       [event("future", at=NOW + timedelta(days=4))]):
            with self.subTest(events=events):
                result = scheduler.assess(PROFILE, state, events, NOW + timedelta(days=3))
                self.assertFalse(result["due"])
                self.assertIn("awaiting_new_evidence", result["reasons"])
                self.assertIsNone(result["next_eligible_at"])
        new_events = [event(), event("new", at=NOW + timedelta(hours=3))]
        before = scheduler.assess(PROFILE, state, new_events, NOW + timedelta(hours=5))
        self.assertFalse(before["due"])
        self.assertIn("retry_cooldown", before["reasons"])
        self.assertTrue(scheduler.assess(PROFILE, state, new_events, NOW + timedelta(hours=6))["due"])

    def test_event_arriving_during_blocked_work_can_unlock_retry(self):
        state = attempted(outcome="blocked", finished=NOW + timedelta(hours=2), ids=["one"])
        events = [event(), event("during-work", at=NOW + timedelta(hours=1))]
        result = scheduler.assess(PROFILE, state, events, NOW + timedelta(hours=6))
        self.assertTrue(result["due"])
        self.assertEqual(result["event_ids"], ["during-work", "one"])

    def test_ny_daily_cap_counts_failed_and_resets_at_local_midnight(self):
        at = scheduler.timestamp("2026-09-10T02:00:00Z")  # Sep 9 in New York.
        state = attempted(at=at, outcome="failed")
        profile = dict(PROFILE, max_runs_per_day=1, retry_cooldown_hours=1)
        before = scheduler.assess(profile, state, [event()], at + timedelta(hours=1))
        self.assertFalse(before["due"])
        self.assertIn("daily_cap", before["reasons"])
        self.assertEqual(before["next_eligible_at"], "2026-09-10T04:00:00Z")
        self.assertTrue(scheduler.assess(profile, state, [event()], at + timedelta(hours=2))["due"])

    def test_daily_cap_next_midnight_handles_dst(self):
        at = scheduler.timestamp("2026-11-01T04:10:00Z")
        state = attempted(at)
        state["next_review_at"] = scheduler.iso(at)
        result = scheduler.assess(dict(PROFILE, max_runs_per_day=1), state, [], at + timedelta(hours=2))
        self.assertEqual(result["next_eligible_at"], "2026-11-02T05:00:00Z")
        self.assertFalse(result["due"])
        self.assertIn("next_review", result["reasons"])
        self.assertIn("daily_cap", result["reasons"])

    def test_active_attempt_blocks_duplicates(self):
        result = scheduler.assess(PROFILE, attempted(outcome=None), [event()], NOW + timedelta(days=2))
        self.assertFalse(result["due"])
        self.assertIn("active_attempt", result["reasons"])
        self.assertIsNone(result["next_eligible_at"])

    def test_assessment_is_pure(self):
        state, events = attempted(), [event()]
        before = copy.deepcopy((PROFILE, state, events))
        scheduler.assess(PROFILE, state, events, NOW + timedelta(hours=2))
        self.assertEqual((PROFILE, state, events), before)

    def test_invalid_parameters(self):
        for field, bad in [("min_interval_hours", 0), ("regular_interval_hours", float("inf")),
                           ("retry_cooldown_hours", -1), ("max_runs_per_day", True),
                           ("max_runs_per_day", 1.5), ("event_types", ["filing", "filing"]),
                           ("min_interval_hours", 49)]:
            with self.subTest(field=field, value=bad), self.assertRaises(ValueError):
                scheduler.assess(dict(PROFILE, **{field: bad}), scheduler.empty_state(), [], NOW)

    def test_naive_clocks_and_time_regressions_rejected(self):
        with self.assertRaises(ValueError):
            scheduler.assess(PROFILE, scheduler.empty_state(), [], "2026-09-09T14:00:00")
        with self.assertRaises(ValueError):
            scheduler.assess(PROFILE, attempted(), [], NOW - timedelta(seconds=1))
        with self.assertRaises(ValueError):
            scheduler.assess(PROFILE, scheduler.empty_state(), [dict(event(), available_at="2026-09-09")], NOW)

    def test_invalid_event_metadata_and_duplicate_ids(self):
        for events in ([dict(event(), narrative="someone else's view")], [event(), event()], [dict(event(), expert_ids="value")]):
            with self.assertRaises(ValueError):
                scheduler.assess(PROFILE, scheduler.empty_state(), events, NOW)

    def test_inconsistent_attempt_state_rejected(self):
        state = attempted(outcome=None)
        state["active_attempt"] = "unknown"
        with self.assertRaisesRegex(ValueError, "active attempt"):
            scheduler.assess(PROFILE, state, [], NOW)
        state = attempted()
        state["last_attempt_at"] = None
        with self.assertRaisesRegex(ValueError, "attempt history"):
            scheduler.assess(PROFILE, state, [], NOW)


@unittest.skipUnless(importlib.util.find_spec("exchange_calendars"), "requires portfolio environment")
class CalendarTests(unittest.TestCase):
    def profile(self, cadence="daily"):
        calendar = {"name": "XNYS", "cadence": cadence, "local_time": "08:45"}
        if cadence == "every_n_sessions":
            calendar.update(sessions=3, anchor_session="2026-09-08")
        return dict(PROFILE, calendar=calendar)

    def check(self, at, success=None, cadence="daily", events=None):
        state = attempted(at=scheduler.timestamp(success)) if success else scheduler.empty_state()
        return scheduler.assess(self.profile(cadence), state, events or [], at)

    def test_dst_opening_window_and_late_tick(self):
        for day, utc in (("2026-03-06", "13:45"), ("2026-03-09", "12:45"),
                         ("2026-10-30", "12:45"), ("2026-11-02", "13:45")):
            at = scheduler.timestamp(f"{day}T{utc}:00Z")
            self.assertFalse(self.check(at - timedelta(seconds=1))["due"])
            self.assertTrue(self.check(at)["due"])
            self.assertTrue(self.check(at + timedelta(hours=2))["due"])

    def test_holidays_weekends_and_early_close(self):
        for day in ("2026-04-03", "2026-07-03", "2026-09-07", "2026-11-26", "2026-11-28"):
            self.assertFalse(self.check(day + "T16:00:00Z")["due"], day)
        self.assertTrue(self.check("2026-11-27T13:45:00Z")["due"])
        self.assertTrue(self.check("2026-11-27T19:00:00Z")["due"])
        self.assertEqual(self.check("2026-09-07T16:00:00Z")["next_eligible_at"],
                         "2026-09-08T12:45:00Z")

    def test_success_earlier_in_day_deduplicates_regular_window(self):
        result = self.check("2026-09-09T18:00:00Z", "2026-09-09T09:00:00Z")
        self.assertFalse(result["due"])
        self.assertTrue(result["calendar"]["period_satisfied"])
        self.assertEqual(result["next_eligible_at"], "2026-09-10T12:45:00Z")

    def test_weekly_holiday_and_missed_windows_coalesce(self):
        self.assertTrue(self.check("2026-09-08T12:45:00Z", "2026-08-17T15:00:00Z", "weekly")["due"])
        result = self.check("2026-09-10T20:00:00Z", "2026-09-09T14:00:00Z", "weekly")
        self.assertFalse(result["due"])
        self.assertEqual(result["next_eligible_at"], "2026-09-14T12:45:00Z")

    def test_three_session_windows_skip_weekend_and_coalesce(self):
        for day in ("2026-09-09", "2026-09-10"):
            self.assertFalse(self.check(day + "T18:00:00Z", "2026-09-08T14:00:00Z", "every_n_sessions")["due"])
        self.assertTrue(self.check("2026-09-11T12:45:00Z", "2026-09-08T14:00:00Z", "every_n_sessions")["due"])
        self.assertFalse(self.check("2026-09-14T17:00:00Z", "2026-09-11T14:00:00Z", "every_n_sessions")["due"])
        self.assertTrue(self.check("2026-09-16T12:45:00Z", "2026-09-11T14:00:00Z", "every_n_sessions")["due"])
        self.assertFalse(self.check("2026-10-01T16:00:00Z", "2026-10-01T12:50:00Z", "every_n_sessions")["due"])

    def test_holiday_events_reviews_and_stops_remain_independent(self):
        at = scheduler.timestamp("2026-09-07T16:00:00Z")
        state = attempted(at=at - timedelta(days=3))
        state["next_review_at"] = scheduler.iso(at)
        result = scheduler.assess(self.profile(), state, [], at)
        self.assertTrue(result["due"])
        self.assertIn("next_review", result["reasons"])
        state["stopped"] = True
        self.assertFalse(scheduler.assess(self.profile(), state, [event(at=at)], at)["due"])
        state["stopped"] = False
        state["next_review_at"] = None
        self.assertTrue(scheduler.assess(self.profile(), state, [event(at=at)], at)["due"])

    def test_calendar_does_not_override_attempt_limits(self):
        at = scheduler.timestamp("2026-09-09T12:45:00Z")
        profile = dict(self.profile(), max_runs_per_day=1)
        state = attempted(at=at, outcome="failed")
        result = scheduler.assess(profile, state, [event(at=at)], at + timedelta(minutes=1))
        self.assertFalse(result["due"])
        for reason in ("min_interval", "daily_cap", "retry_cooldown"):
            self.assertIn(reason, result["reasons"])
        state["attempts"][0]["outcome"] = "blocked"
        result = scheduler.assess(profile, state, [], at + timedelta(days=1))
        self.assertIn("awaiting_new_evidence", result["reasons"])
        self.assertFalse(result["due"])


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.policy, self.state, self.events = [self.root / name for name in ("policy.json", "state.json", "events.json")]
        self.policy.write_text(json.dumps(dict(schema_version=1, timezone="America/New_York",
                                               experts=[PROFILE, dict(PROFILE, id="growth")])))
        self.events.write_text(json.dumps([event()]))
        self.call("init")

    def call(self, command, *extra, at=NOW):
        argv = [command, "--state", str(self.state)]
        if command != "finish":
            argv += ["--policy", str(self.policy)]
        if command in {"check", "start"}:
            argv += ["--events", str(self.events)]
        with patch.object(scheduler, "now_utc", return_value=at):
            return scheduler.run(scheduler.parser().parse_args(argv + list(extra)))

    def artifacts(self):
        report, decision = self.root / "report.html", self.root / "decision.json"
        report.write_text("a report fixture, not financially validated")
        decision.write_text("{}")
        return ["--report", str(report), "--decision", str(decision)]

    def complete(self, attempt, *extra, at=NOW):
        return self.call("finish", "--expert", "value", "--attempt", attempt["id"], "--outcome", "completed", *extra, at=at)

    def test_init_is_exclusive(self):
        original = self.state.read_bytes()
        with self.assertRaises(FileExistsError):
            self.call("init")
        self.assertEqual(self.state.read_bytes(), original)

    def test_early_success_retains_future_review_commitment(self):
        for replacement in (None, NOW + timedelta(days=5)):
            first = self.call("start", "--expert", "value")
            whole = scheduler.read_json(self.state)
            commitment = scheduler.iso(NOW + timedelta(days=2))
            whole["experts"]["value"]["next_review_at"] = commitment
            scheduler.write_json(self.state, whole)
            extra = ["--next-review-at", scheduler.iso(replacement)] if replacement else []
            self.complete(first, *self.artifacts(), *extra, at=NOW + timedelta(minutes=5))
            self.assertEqual(scheduler.read_json(self.state)["experts"]["value"]["next_review_at"], commitment)
            # Reset only this temporary fixture for the second variant.
            scheduler.write_json(self.state, {"schema_version": 1,
                "experts": {"value": scheduler.empty_state(), "growth": scheduler.empty_state()}})

    def test_finish_consumes_only_dispatched_events_and_supports_multiple_daily_runs(self):
        first = self.call("start", "--expert", "value")
        self.events.write_text(json.dumps([event(), event("during-work")]))
        self.complete(first, *self.artifacts(), at=NOW + timedelta(minutes=5))
        state = scheduler.read_json(self.state)["experts"]
        self.assertEqual(state["value"]["processed_event_ids"], ["one"])
        self.assertEqual(state["growth"], scheduler.empty_state())
        second = self.call("start", "--expert", "value", at=NOW + timedelta(hours=1))
        self.assertEqual(second["event_ids"], ["during-work"])
        self.assertNotEqual(first["id"], second["id"])
        self.assertEqual(len(scheduler.read_json(self.state)["experts"]["value"]["attempts"]), 2)

    def test_failed_attempt_preserves_previous_success_and_events(self):
        first = self.call("start", "--expert", "value")
        self.complete(first, *self.artifacts())
        self.events.write_text(json.dumps([event("new")]))
        second = self.call("start", "--expert", "value", at=NOW + timedelta(hours=1))
        self.call("finish", "--expert", "value", "--attempt", second["id"], "--outcome", "failed", at=NOW + timedelta(hours=2))
        own = scheduler.read_json(self.state)["experts"]["value"]
        self.assertEqual(own["last_successful_research_at"], scheduler.iso(NOW))
        self.assertEqual(own["last_decision_at"], scheduler.iso(NOW))
        self.assertEqual(own["processed_event_ids"], ["one"])
        self.assertIsNone(own["active_attempt"])

    def test_idempotent_finish_and_conflicting_repeat(self):
        first = self.call("start", "--expert", "value")
        args = self.artifacts() + ["--next-review-at", scheduler.iso(NOW + timedelta(hours=1))]
        receipt = self.complete(first, *args)
        original = self.state.read_bytes()
        self.assertEqual(self.complete(first, *args, at=NOW + timedelta(hours=2)), receipt)
        self.assertEqual(self.state.read_bytes(), original)
        with self.assertRaisesRegex(ValueError, "conflicting"):
            self.call("finish", "--expert", "value", "--attempt", first["id"], "--outcome", "failed")
        self.assertEqual(len(receipt["report"]["sha256"]), 64)
        (self.root / "report.html").write_text("changed")
        with self.assertRaisesRegex(ValueError, "conflicting"):
            self.complete(first, *args)

    def test_completion_requires_existing_artifacts_and_correct_attempt(self):
        first = self.call("start", "--expert", "value")
        for args in ([], ["--report", str(self.root / "missing"), "--decision", str(self.root)]):
            with self.assertRaises(ValueError):
                self.complete(first, *args)
        with self.assertRaisesRegex(ValueError, "unknown attempt"):
            self.call("finish", "--expert", "growth", "--attempt", first["id"], "--outcome", "failed")
        with self.assertRaisesRegex(ValueError, "next review"):
            self.complete(first, *self.artifacts(), "--next-review-at", scheduler.iso(NOW - timedelta(seconds=1)))
        self.assertEqual(scheduler.read_json(self.state)["experts"]["value"]["active_attempt"], first["id"])

    def test_check_is_read_only_and_optional_journal_is_append_only(self):
        original = self.state.read_bytes()
        self.call("check")
        self.assertFalse((self.root / "checks").exists())
        self.call("check", "--log", "--expert", "value")
        self.call("check", "--log", "--expert", "value")
        self.assertEqual(len(list((self.root / "checks").glob("*.json"))), 2)
        self.assertEqual(self.state.read_bytes(), original)

    def test_dispatch_and_check_preserve_loaded_policy_and_event_provenance(self):
        check = self.call("check", "--log", "--expert", "value")["experts"]["value"]
        first = self.call("start", "--expert", "value")
        snapshot = first["provenance"]
        self.assertEqual(snapshot, check["provenance"])
        self.assertEqual(snapshot["profile"], PROFILE)
        self.assertEqual(snapshot["profile_sha256"], scheduler.canonical_hash(PROFILE))
        self.assertEqual(snapshot["event_metadata_sha256"], scheduler.canonical_hash([event()]))
        policy = scheduler.read_json(self.policy)
        policy["experts"][0]["regular_interval_hours"] = 96
        self.policy.write_text(json.dumps(policy))
        self.events.write_text(json.dumps([event("later")]))
        recorded = scheduler.read_json(self.state)["experts"]["value"]["attempts"][0]
        self.assertEqual(recorded["provenance"], snapshot)
        changed = self.call("check", "--expert", "value")["experts"]["value"]["provenance"]
        self.assertNotEqual(changed["profile_sha256"], snapshot["profile_sha256"])
        self.assertNotEqual(changed["event_metadata_sha256"], snapshot["event_metadata_sha256"])
        self.assertEqual(scheduler.canonical_hash(dict(reversed(list(PROFILE.items())))), snapshot["profile_sha256"])

    def test_short_exclusive_lock_prevents_overlap(self):
        with scheduler.locked(self.state):
            with self.assertRaisesRegex(ValueError, "locked"):
                self.call("start", "--expert", "value")

    def test_unsuccessful_finish_is_idempotent(self):
        first = self.call("start", "--expert", "value")
        args = ["--expert", "value", "--attempt", first["id"], "--outcome", "blocked"]
        receipt = self.call("finish", *args)
        self.assertEqual(self.call("finish", *args, at=NOW + timedelta(hours=1)), receipt)
        self.assertEqual(len(scheduler.read_json(self.state)["experts"]["value"]["attempts"]), 1)

    def test_parallel_cli_start_has_one_winner_and_records_actual_time(self):
        self.events.write_text("[]")
        command = [sys.executable, str(SCRIPT), "start", "--state", str(self.state), "--policy", str(self.policy),
                   "--events", str(self.events), "--expert", "value"]
        before = scheduler.now_utc()
        children = [subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for _ in range(2)]
        outputs = [child.communicate(timeout=10) for child in children]
        self.assertEqual(sorted(child.returncode for child in children), [0, 2], outputs)
        own = scheduler.read_json(self.state)["experts"]["value"]
        self.assertEqual(len(own["attempts"]), 1)
        self.assertLessEqual(before, scheduler.timestamp(own["last_attempt_at"]))
        self.assertLessEqual(scheduler.timestamp(own["last_attempt_at"]), scheduler.now_utc())

    def test_unknown_expert_policy_mismatch_and_no_historical_cli_clock(self):
        with self.assertRaisesRegex(ValueError, "unknown expert"):
            self.call("start", "--expert", "unknown")
        policy = scheduler.read_json(self.policy)
        policy["timezone"] = "UTC"
        self.policy.write_text(json.dumps(policy))
        with self.assertRaisesRegex(ValueError, "America/New_York"):
            self.call("check")
        result = subprocess.run([sys.executable, str(SCRIPT), "--help"], capture_output=True, text=True, check=True)
        self.assertIn("finish", result.stdout)
        self.assertNotIn("--now", result.stdout)


if __name__ == "__main__":
    unittest.main()
