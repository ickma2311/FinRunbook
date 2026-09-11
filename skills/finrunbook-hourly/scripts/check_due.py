#!/usr/bin/env python3
"""Check registered Arena schedules. No research, network, account writes or timer."""
import argparse
import importlib.util
import json
from pathlib import Path
import uuid

ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location(
    "hourly_schedule", ROOT / "skills/finrunbook-investor/scripts/forward_schedule.py")
schedule = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(schedule)


def resolve(root, value):
    if not isinstance(value, (str, Path)) or not str(value).strip():
        raise ValueError("configured file path required")
    path = Path(value)
    return path.resolve() if path.is_absolute() else (root / path).resolve()


def check_registry(root, registry_path, policy_path, events_path=None, now=None):
    registry = schedule.read_json(registry_path)
    if registry.get("schema_version") != 1 or not isinstance(registry.get("experts"), list):
        raise ValueError("registry requires schema_version 1 and experts list")
    ids = [row["id"] for row in registry["experts"]]
    schedule.strings(ids, "registry expert ids")
    if not ids:
        raise ValueError("registry has no experts")
    profiles = schedule.profiles_at(policy_path)
    events = schedule.read_json(events_path) if events_path else []
    # Validate the entire event feed even if no registered state is readable.
    now = schedule.timestamp(now) if now else schedule.now_utc()
    event_profile = {k: v for k, v in next(iter(profiles.values())).items() if k != "calendar"}
    schedule.assess(event_profile, schedule.empty_state(), events, now)
    results = []
    for row in registry["experts"]:
        result = {"expert_id": row["id"], "due": False}
        try:
            state_path = resolve(root, row.get("schedule_state"))
            account_path = resolve(root, row.get("account"))
            if not account_path.is_file():
                raise ValueError("registered account file is missing")
            account = schedule.read_json(account_path)
            if (account.get("expert_id") != row["id"] or not row.get("account_id")
                    or account.get("account_id") != row["account_id"]):
                raise ValueError("registered account identity mismatch")
            result.update(schedule_state=str(state_path), account=str(account_path))
            with schedule.locked(state_path):
                state = schedule.state_at(state_path)
                own = state["experts"][row["id"]]
                # Existing states may register one expert or a shared subset.
                policy = {"schema_version": 1, "timezone": "America/New_York",
                          "experts": [profiles[key] for key in state["experts"]]}
                assessment = schedule.assess(profiles[row["id"]], own, events, now)
                if not assessment["due"] and not assessment["reasons"]:
                    assessment["reasons"] = ["no_due_trigger"]
                result.update(assessment, status="due" if assessment["due"] else "skipped",
                              last_successful_research_at=own["last_successful_research_at"],
                              last_attempt_at=own["last_attempt_at"],
                              next_review_at=own["next_review_at"],
                              active_attempt=own["active_attempt"],
                              state_sha256=schedule.canonical_hash(state),
                              provenance=schedule.provenance(profiles[row["id"]], events),
                              dispatch_policy=policy)
        except (ValueError, TypeError, KeyError, AttributeError, OSError, OverflowError) as exc:
            result.update(due=False, status="error", reasons=["configuration_or_state_error"],
                          error=str(exc))
        results.append(result)
    return {"schema_version": 1, "checked_at": schedule.iso(now),
            "mode": "schedule_and_supplied_events" if events_path else "schedule_only",
            "registry_sha256": schedule.canonical_hash(registry),
            "events": events, "experts": results,
            "due_experts": [r["expert_id"] for r in results if r["due"]],
            "error_count": sum(r["status"] == "error" for r in results)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", default="portfolio/experts.json")
    parser.add_argument("--policy", default="skills/finrunbook-investor/references/forward-profiles.json")
    parser.add_argument("--events", help="Optional existing neutral event JSON array")
    parser.add_argument("--collect-events", action="store_true", help="Collect official feeds before checking schedules")
    parser.add_argument("--log", action="store_true", help="Save immutable tick inputs and check receipt")
    args = parser.parse_args(argv)
    try:
        if args.events and args.collect_events:
            raise ValueError("choose --events or --collect-events, not both")
        collection = None
        events_path = resolve(ROOT, args.events) if args.events else None
        if args.collect_events:
            try:
                from collect_events import collect
                config = schedule.read_json(ROOT / "skills/finrunbook-hourly/references/event-sources.json")
                collection = collect(ROOT, config, resolve(ROOT, args.registry),
                                     resolve(ROOT, args.policy), ROOT / "runs/hourly-event-cache/state.json")
                events_path = Path(collection["events_path"])
                # Validate freshly published input before selecting event mode.
                events = schedule.read_json(events_path)
                profile = next(iter(schedule.profiles_at(resolve(ROOT, args.policy)).values()))
                schedule.assess({k: v for k, v in profile.items() if k != "calendar"},
                                schedule.empty_state(), events, schedule.now_utc())
            except Exception as exc:
                from collect_events import sanitized_excerpt
                collection = {"status": "failed", "error_count": 1,
                              "error": sanitized_excerpt(exc), "sources": [],
                              "notification_required": True,
                              "coverage": "unavailable", "events_path": None}
                events_path = None
        result = check_registry(ROOT, resolve(ROOT, args.registry), resolve(ROOT, args.policy),
                                events_path)
        if collection:
            result["collection"] = collection
        if args.log:
            tick = "tick-" + uuid.uuid4().hex
            output = ROOT / "runs/hourly" / tick
            result.update(tick_id=tick, receipt_path=str(output / "check.json"),
                          events_path=str(output / "events.json"))
            schedule.write_json(output / "events.json", result["events"], exclusive=True)
            for i, row in enumerate(result["experts"]):
                if "dispatch_policy" in row:
                    path = output / f"policy-{i}.json"
                    schedule.write_json(path, row["dispatch_policy"], exclusive=True)
                    row["policy_path"] = str(path)
            schedule.write_json(output / "check.json", result, exclusive=True)
        # Keep model-visible output short; full profiles and state provenance stay on disk.
        summary = {k: v for k, v in result.items() if k not in {"events", "experts"}}
        summary["experts"] = [{k: v for k, v in row.items()
                               if k not in {"dispatch_policy", "provenance"}}
                              for row in result["experts"]]
        print(json.dumps(summary, indent=2))
        return 2 if result["error_count"] or (collection and collection["error_count"]) else 0
    except (ValueError, TypeError, KeyError, AttributeError, OSError, OverflowError) as exc:
        parser.exit(1, f"error: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
