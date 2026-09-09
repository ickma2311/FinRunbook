"""Offline synthetic fixtures verify accounting mechanics, not investments."""
import copy
import contextlib
import io
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "skills/finrunbook-investor/scripts/forward_account.py"
SPEC = importlib.util.spec_from_file_location("forward_account", SCRIPT)
accounting = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(accounting)


class ForwardAccountTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.skill = self.root / "SKILL.md"
        self.skill.write_text("Fixture own method\n")
        self.report = self.root / "report.json"
        self.report.write_text('{"report":"fixture only"}')
        self.evidence = self.root / "evidence.json"
        self.evidence.write_text(json.dumps({"sources": [{"available_at": "2026-09-01T10:00:00Z", "retrieved_at": "2026-09-09T14:00:00Z"}]}))
        self.account = accounting.init_account("quality", "quality-paper", self.skill, "2026-09-09T13:00:00Z", symbols=("AAA", "BBB", "CCC", "DDD"))

    def candidate(self, action="rebalance"):
        result = {"expert_id": "quality", "account_id": "quality-paper", "task_id": "author-1",
                  "skill_hash": accounting.file_hash(self.skill), "report_path": str(self.report),
                  "report_hash": accounting.file_hash(self.report), "evidence_path": str(self.evidence),
                  "evidence_hash": accounting.file_hash(self.evidence), "evidence_cutoff": "2026-09-09T14:30:00Z",
                  "account_snapshot_hash": accounting.digest(accounting.snapshot(self.account)),
                  "action": action, "rationale": "Synthetic test", "next_review_condition": "Next filing"}
        if action == "rebalance":
            result.update(target_weights={"AAA": 0.2, "BBB": 0.2},
                          execution_policy="next_regular_session_open",
                          price_limits={"AAA": {"min": 50, "max": 200}, "BBB": {"min": 50, "max": 200}})
        return result

    def review(self, candidate):
        return {"candidate_hash": accounting.digest(candidate), "author_task_id": candidate["task_id"],
                "reviewer_task_id": "review-1", "parent_history_inherited": False,
                "reviewed_at": "2026-09-09T14:45:00Z",
                "findings": [{"id": key, "required": True, "status": "PASS"}
                             for key in ("material_evidence", "calculations", "report_decision")]}

    def seal(self, candidate=None, now="2026-09-09T15:00:00Z"):
        candidate = candidate or self.candidate()
        return accounting.seal(self.account, candidate, accounting.validate(self.account, candidate), self.review(candidate), now)

    def observations(self, decision):
        return {"event_id": "fixture-open-1", "account_id": "quality-paper",
                "decision_id": decision["decision_id"], "observed_at": "2026-09-10T13:30:01Z",
                "session": {"id": "fixture-session-next", "regular": True,
                            "open_at": "2026-09-10T13:30:00Z", "previous_regular_open_at": "2026-09-09T13:30:00Z",
                            "next_for_decision_id": decision["decision_id"], "source": "synthetic-fixture"},
                "sizing": {"as_of": "2026-09-08T20:00:00Z", "observed_at": "2026-09-08T20:01:00Z",
                           "last_eligible_close_for_decision_id": decision["decision_id"],
                           "source": "synthetic-fixture", "prices": {"AAA": 100, "BBB": 100}},
                "prices": {ticker: {"open": 100, "tradable": True, "corporate_actions_checked": True}
                           for ticker in ("AAA", "BBB")}}

    def settle(self, observations):
        return accounting.settle(self.account, observations, "2026-09-10T13:31:00Z")

    def test_init_enrollment_and_independence(self):
        self.assertEqual(self.account["cash"], "100000.000000")
        other = accounting.init_account("macro", "macro-paper", self.skill, "2026-09-09T13:00:00Z")
        before = copy.deepcopy(other)
        self.seal()
        self.assertEqual(other, before)

    def test_hash_bound_and_stale_snapshot(self):
        candidate = self.candidate()
        self.report.write_text("changed")
        with self.assertRaisesRegex(accounting.Invalid, "report hash"):
            accounting.validate(self.account, candidate)
        candidate = self.candidate()
        self.account["revision"] += 1
        with self.assertRaisesRegex(accounting.Invalid, "stale"):
            accounting.validate(self.account, candidate)

    def test_changed_skill_rejected(self):
        candidate = self.candidate()
        self.skill.write_text("new method")
        with self.assertRaisesRegex(accounting.Invalid, "skill hash"):
            accounting.validate(self.account, candidate)

    def test_bad_timestamp_or_future_source_blocks(self):
        candidate = self.candidate()
        candidate["evidence_cutoff"] = "2026-09-09T13:30:00Z"
        with self.assertRaisesRegex(accounting.Invalid, "source unavailable"):
            accounting.validate(self.account, candidate)
        candidate = self.candidate()
        with self.assertRaisesRegex(accounting.Invalid, "seal must follow"):
            self.seal(candidate, candidate["evidence_cutoff"])

    def test_evidence_can_predate_funding_but_seal_cannot(self):
        self.account["funded_at"] = "2026-09-09T14:40:00Z"
        candidate = self.candidate()
        self.assertEqual(accounting.validate(self.account, candidate)["status"], "PASS")
        before = copy.deepcopy(self.account)
        with self.assertRaisesRegex(accounting.Invalid, "predate account funding"):
            self.seal(candidate, "2026-09-09T14:35:00Z")
        self.assertEqual(self.account, before)
        self.assertEqual(self.seal(candidate)["status"], "PASS")

    def test_seal_cannot_predate_account_observation(self):
        self.account["observed_at"] = "2026-09-09T15:01:00Z"
        candidate = self.candidate()
        before = copy.deepcopy(self.account)
        with self.assertRaisesRegex(accounting.Invalid, "predate account observation"):
            self.seal(candidate)
        self.assertEqual(self.account, before)

    def test_no_independent_or_failing_review_blocks(self):
        candidate = self.candidate()
        validation = accounting.validate(self.account, candidate)
        review = self.review(candidate)
        review["reviewer_task_id"] = candidate["task_id"]
        before = copy.deepcopy(self.account)
        with self.assertRaisesRegex(accounting.Invalid, "independent"):
            accounting.seal(self.account, candidate, validation, review, "2026-09-09T15:00:00Z")
        review = self.review(candidate)
        review["findings"][0]["status"] = "FAIL"
        with self.assertRaisesRegex(accounting.Invalid, "financial review failed"):
            accounting.seal(self.account, candidate, validation, review, "2026-09-09T15:00:00Z")
        self.assertEqual(self.account, before)

    def test_optional_gap_warns_and_aggregate_cannot_lie(self):
        candidate = self.candidate()
        review = self.review(candidate)
        review["findings"].append({"id": "optional_detail", "required": False, "status": "FAIL"})
        validation = accounting.validate(self.account, candidate)
        review["status"] = "PASS"
        with self.assertRaisesRegex(accounting.Invalid, "aggregate"):
            accounting.seal(self.account, candidate, validation, review, "2026-09-09T15:00:00Z")
        review.pop("status")
        receipt = accounting.seal(self.account, candidate, validation, review, "2026-09-09T15:00:00Z")
        self.assertEqual(receipt["status"], "PASS_WITH_WARNINGS")

    def test_validation_receipt_cannot_be_forged(self):
        candidate = self.candidate()
        validation = accounting.validate(self.account, candidate)
        validation["checks"] = []
        with self.assertRaisesRegex(accounting.Invalid, "validation receipt"):
            accounting.seal(self.account, candidate, validation, self.review(candidate), "2026-09-09T15:00:00Z")

    def test_duplicate_seal_is_noop(self):
        candidate = self.candidate()
        validation, review = accounting.validate(self.account, candidate), self.review(candidate)
        first = accounting.seal(self.account, candidate, validation, review, "2026-09-09T15:00:00Z")
        before = copy.deepcopy(self.account)
        second = accounting.seal(self.account, candidate, validation, review, "2026-09-09T15:01:00Z")
        self.assertEqual(first, second)
        self.assertEqual(before, self.account)

    def test_no_change_retains_pending(self):
        first = self.seal()
        self.seal(self.candidate("no_change"), "2026-09-09T15:10:00Z")
        self.assertEqual(first["intent_id"], self.account["pending_intent_id"])
        self.assertEqual(len(self.account["intents"]), 1)

    def test_replacement_must_be_explicit_and_preserves_history(self):
        first = self.seal()
        replacement = self.candidate()
        with self.assertRaisesRegex(accounting.Invalid, "explicitly name"):
            accounting.validate(self.account, replacement)
        replacement["replaces_intent_id"] = first["intent_id"]
        second = self.seal(replacement, "2026-09-09T15:10:00Z")
        self.assertEqual(self.account["pending_intent_id"], second["intent_id"])
        self.assertEqual(self.account["intents"][0]["status"], "replaced")
        self.assertEqual(self.account["decisions"][0], first)

    def test_future_or_missing_open_remains_pending(self):
        observations = self.observations(self.seal())
        before = copy.deepcopy(self.account)
        result = accounting.settle(self.account, observations, "2026-09-09T15:01:00Z")
        self.assertEqual(result["status"], "pending")
        observations.pop("session")
        self.assertEqual(accounting.settle(copy.deepcopy(before), observations, "2026-09-10T13:31:00Z")["status"], "pending")
        self.assertEqual(self.account["cash"], before["cash"])
        self.assertEqual(self.account["positions"], before["positions"])
        self.assertEqual(len(self.account["observation_events"]), 1)

    def test_already_occurred_or_non_next_open_rejected(self):
        observations = self.observations(self.seal())
        observations["session"]["open_at"] = "2026-09-09T13:30:00Z"
        with self.assertRaisesRegex(accounting.Invalid, "next future"):
            self.settle(observations)
        observations = self.observations(self.account["decisions"][0])
        observations.update(event_id="fixture-correction", supersedes_event_id="fixture-open-1", correction_reason="Fix fixture session record")
        observations["session"]["previous_regular_open_at"] = "2026-09-10T13:30:00Z"
        with self.assertRaisesRegex(accounting.Invalid, "next future"):
            self.settle(observations)

    def test_missing_price_and_corporate_actions_block_without_mutation(self):
        observations = self.observations(self.seal())
        before = copy.deepcopy(self.account)
        observations["prices"].pop("BBB")
        self.assertEqual(self.settle(observations)["reason"], "missing_prices")
        observations = self.observations(self.account["decisions"][0])
        observations.update(event_id="fixture-correction", supersedes_event_id="fixture-open-1", correction_reason="Complete missing fixture price")
        observations["prices"]["AAA"]["corporate_actions_checked"] = False
        self.assertEqual(self.settle(observations)["reason"], "corporate_actions_not_verified")
        self.assertEqual(before["cash"], self.account["cash"])
        self.assertEqual(before["positions"], self.account["positions"])
        self.assertEqual(len(self.account["observation_events"]), 2)

    def test_sizing_must_be_known_at_seal(self):
        observations = self.observations(self.seal())
        observations["sizing"]["observed_at"] = "2026-09-10T13:29:00Z"
        with self.assertRaisesRegex(accounting.Invalid, "not known at seal"):
            self.settle(observations)

    def test_fill_reconciles_slippage_and_is_idempotent(self):
        observations = self.observations(self.seal())
        result = self.settle(observations)
        self.assertEqual(result["status"], "filled")
        self.assertEqual(result["positions"], {"AAA": 200, "BBB": 200})
        self.assertEqual(result["cash"], "59960.000000")
        self.assertEqual(result["nav"], "99960.000000")
        before = copy.deepcopy(self.account)
        self.assertEqual(self.settle(observations), result)
        self.assertEqual(before, self.account)
        observations["prices"]["AAA"]["open"] = 101
        with self.assertRaisesRegex(accounting.Invalid, "event ID reused"):
            self.settle(observations)

    def test_gap_risk_or_price_breach_is_atomic_pending(self):
        observations = self.observations(self.seal())
        observations["prices"]["AAA"]["open"] = 160
        result = self.settle(observations)
        self.assertEqual(result["reason"], "fill_time_security_cap")
        self.assertEqual(self.account["cash"], "100000.000000")
        self.assertEqual(self.account["positions"], {})
        self.settle(observations)
        self.assertEqual(len(self.account["review_events"]), 1)
        observations["prices"]["AAA"]["open"] = 210
        observations.update(event_id="fixture-correction", supersedes_event_id="fixture-open-1", correction_reason="Correct observed fixture price")
        self.assertEqual(self.settle(observations)["reason"], "price_limit")

    def test_no_leverage_even_with_valid_target_weights(self):
        candidate = self.candidate()
        candidate["target_weights"] = {s: 0.25 for s in ("AAA", "BBB", "CCC", "DDD")}
        candidate["price_limits"] = {s: {"min": 50, "max": 200} for s in candidate["target_weights"]}
        observations = self.observations(self.seal(candidate))
        for symbol in ("CCC", "DDD"):
            observations["sizing"]["prices"][symbol] = 100
            observations["prices"][symbol] = {"open": 100, "tradable": True, "corporate_actions_checked": True}
        self.assertEqual(self.settle(observations)["reason"], "insufficient_cash")
        self.assertEqual(self.account["positions"], {})

    def test_empty_target_liquidates_with_adverse_sell_slippage(self):
        self.settle(self.observations(self.seal()))
        candidate = self.candidate()
        candidate["target_weights"] = {}
        candidate["evidence_cutoff"] = "2026-09-10T14:00:00Z"
        review = self.review(candidate)
        review["reviewed_at"] = "2026-09-10T14:30:00Z"
        decision = accounting.seal(self.account, candidate, accounting.validate(self.account, candidate), review, "2026-09-10T15:00:00Z")
        observations = self.observations(decision)
        observations.update(event_id="fixture-open-2", observed_at="2026-09-11T13:30:01Z")
        observations["session"].update(id="fixture-session-2", open_at="2026-09-11T13:30:00Z", previous_regular_open_at="2026-09-10T13:30:00Z")
        result = accounting.settle(self.account, observations, "2026-09-11T13:31:00Z")
        self.assertEqual(result["positions"], {})
        self.assertEqual(result["cash"], "99920.000000")
        self.assertTrue(all(f["side"] == "sell" for f in result["fills"]))

    def test_target_limits_and_no_change_schema(self):
        candidate = self.candidate()
        candidate["target_weights"]["AAA"] = 0.31
        with self.assertRaisesRegex(accounting.Invalid, "30%"):
            accounting.validate(self.account, candidate)
        candidate = self.candidate("no_change")
        candidate["target_weights"] = {}
        with self.assertRaisesRegex(accounting.Invalid, "no_change cannot"):
            accounting.validate(self.account, candidate)

    def test_outside_universe_is_rejected(self):
        candidate = self.candidate()
        candidate["target_weights"]["SPY"] = 0.1
        with self.assertRaisesRegex(accounting.Invalid, "outside enrolled universe"):
            accounting.validate(self.account, candidate)

    def test_atomic_round_trip_preserves_ledger(self):
        self.settle(self.observations(self.seal()))
        path = self.root / "account.json"
        accounting.atomic_write(path, self.account)
        self.assertEqual(accounting.read(path), self.account)
        self.assertEqual([e["type"] for e in self.account["ledger"]], ["funding", "sealed_decision", "settlement", "observation_ingested"])

    def test_failed_observation_cannot_be_mutated_to_fill(self):
        observations = self.observations(self.seal())
        observations["prices"]["AAA"]["open"] = 210
        original = copy.deepcopy(observations)
        self.assertEqual(self.settle(observations)["reason"], "price_limit")
        original_record = copy.deepcopy(self.account["observation_events"]["fixture-open-1"])
        observations["prices"]["AAA"]["open"] = 100
        with self.assertRaisesRegex(accounting.Invalid, "event ID reused"):
            self.settle(observations)
        self.assertEqual(self.account["observation_events"]["fixture-open-1"], original_record)
        self.assertEqual(self.account["positions"], {})
        conflict = self.account["ledger"][-1]
        self.assertEqual(conflict["receipt"]["status"], "rejected")
        self.assertEqual(conflict["observations"], observations)
        observations.update(event_id="fixture-correction", supersedes_event_id="fixture-open-1", correction_reason="Collector corrected bad fixture price")
        self.assertEqual(self.settle(observations)["status"], "filled")
        self.assertEqual(self.account["observation_events"]["fixture-open-1"]["observations"], original)
        self.assertEqual(len(self.account["observation_events"]), 2)

    def test_incomplete_future_event_requires_new_version_when_data_arrives(self):
        observations = self.observations(self.seal())
        observations["prices"] = {}
        first = accounting.settle(self.account, observations, "2026-09-09T15:01:00Z")
        self.assertEqual(first["reason"], "session_open_not_yet_observed")
        self.assertEqual(self.settle(observations), first)
        complete = self.observations(self.account["decisions"][0])
        complete.update(event_id="fixture-complete", supersedes_event_id="fixture-open-1", correction_reason="Next open subsequently observed")
        self.assertEqual(self.settle(complete)["status"], "filled")
        self.assertEqual(self.account["observation_events"]["fixture-open-1"]["receipt"], first)

    def test_new_event_cannot_silently_replace_same_session_observation(self):
        observations = self.observations(self.seal())
        observations["prices"] = {}
        self.settle(observations)
        new_observations = self.observations(self.account["decisions"][0])
        new_observations["event_id"] = "fixture-new-unlinked"
        with self.assertRaisesRegex(accounting.Invalid, "explicitly supersede"):
            self.settle(new_observations)
        self.assertEqual(self.account["positions"], {})
        self.assertEqual(self.account["observation_events"]["fixture-new-unlinked"]["receipt"]["status"], "rejected")

    def test_observation_supersession_order_survives_sorted_json_reload(self):
        decision = self.seal()
        original = self.observations(decision)
        original.update(event_id="z-original", prices={})
        self.assertEqual(self.settle(original)["status"], "pending")
        correction = self.observations(decision)
        correction.update(event_id="a-correction", supersedes_event_id="z-original",
                          correction_reason="One price is now available")
        correction["prices"].pop("BBB")
        self.assertEqual(self.settle(correction)["status"], "pending")
        account_path = self.root / "reloaded-account.json"
        accounting.atomic_write(account_path, self.account)
        self.account = accounting.read(account_path)
        self.assertEqual(list(self.account["observation_events"]), ["a-correction", "z-original"])
        actual = self.observations(decision)
        actual.update(event_id="b-actual", supersedes_event_id="a-correction",
                      correction_reason="All prices now observed")
        self.assertEqual(self.settle(actual)["status"], "filled")
        accounting.atomic_write(account_path, self.account)
        self.account = accounting.read(account_path)
        before = copy.deepcopy(self.account)
        self.assertEqual(self.settle(actual)["status"], "filled")
        self.assertEqual(self.account, before)
        self.assertEqual([e["event_id"] for e in self.account["ledger"] if e["type"] == "observation_ingested"],
                         ["z-original", "a-correction", "b-actual"])

    def test_cli_rejected_observation_is_persisted(self):
        observations = self.observations(self.seal())
        observations["account_id"] = "wrong-account"
        account_path = self.root / "account.json"
        observation_path = self.root / "observations.json"
        accounting.atomic_write(account_path, self.account)
        accounting.atomic_write(observation_path, observations)
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            accounting.main(["settle", "--account", str(account_path), "--observations", str(observation_path)])
        stored = accounting.read(account_path)
        self.assertEqual(stored["observation_events"]["fixture-open-1"]["receipt"]["status"], "rejected")
        self.assertEqual(stored["positions"], {})

    def test_cli_output_cannot_overwrite_transitive_inputs_or_aliases(self):
        account_path = self.root / "account.json"
        candidate_path = self.root / "candidate.json"
        accounting.atomic_write(account_path, self.account)
        accounting.atomic_write(candidate_path, self.candidate())
        lock_path = Path(str(account_path) + ".lock")
        lock_path.touch()
        symlink = self.root / "report-symlink.json"
        symlink.symlink_to(self.report)
        hardlink = self.root / "report-hardlink.json"
        os.link(self.report, hardlink)
        hardlink_lock = self.root / "lock-hardlink"
        os.link(lock_path, hardlink_lock)
        outputs = [self.report, self.evidence, self.skill, lock_path, symlink, hardlink, hardlink_lock]
        preserved = {p: p.read_bytes() for p in [account_path, candidate_path, self.report, self.evidence, self.skill, lock_path]}
        for output in outputs:
            with self.subTest(output=output), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as caught:
                    accounting.main(["validate", "--account", str(account_path), "--candidate", str(candidate_path), "--output", str(output)])
                self.assertEqual(caught.exception.code, 2)
                self.assertEqual({p: p.read_bytes() for p in preserved}, preserved)

    def test_cli_seal_output_alias_rejected_before_account_mutation(self):
        account_path = self.root / "account.json"
        candidate_path = self.root / "candidate.json"
        validation_path = self.root / "validation.json"
        review_path = self.root / "review.json"
        candidate = self.candidate()
        for path, data in [(account_path, self.account), (candidate_path, candidate),
                           (validation_path, accounting.validate(self.account, candidate)),
                           (review_path, self.review(candidate))]:
            accounting.atomic_write(path, data)
        before = account_path.read_bytes()
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            accounting.main(["seal", "--account", str(account_path), "--candidate", str(candidate_path),
                             "--validation", str(validation_path), "--review", str(review_path),
                             "--output", str(self.report)])
        self.assertEqual(account_path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
