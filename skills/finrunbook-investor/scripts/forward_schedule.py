#!/usr/bin/env python3
"""Forward-only scheduling metadata. No model calls, financial approval, or trades."""
import argparse
from contextlib import contextmanager
from datetime import datetime, time, timedelta, timezone
from functools import lru_cache
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import tempfile
import uuid
from zoneinfo import ZoneInfo

UTC = timezone.utc
NY = ZoneInfo("America/New_York")
OUTCOMES = {"completed", "blocked", "failed", "cancelled"}


def timestamp(value):
    parsed = value if isinstance(value, datetime) else datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("timestamps must include a timezone")
    return parsed.astimezone(UTC)


def iso(value):
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def now_utc():
    return datetime.now(UTC)


def strings(values, label):
    if not isinstance(values, list) or any(not isinstance(v, str) or not v.strip() for v in values):
        raise ValueError(f"{label} must be a list of nonempty strings")
    if len(values) != len(set(values)):
        raise ValueError(f"duplicate {label}")


def validate_profile(profile):
    if not isinstance(profile.get("id"), str) or not profile["id"].strip():
        raise ValueError("expert id required")
    for key in ("regular_interval_hours", "min_interval_hours", "retry_cooldown_hours"):
        val = profile.get(key)
        if isinstance(val, bool) or not isinstance(val, (int, float)) or not math.isfinite(val) or val <= 0:
            raise ValueError(f"{key} must be finite and positive")
    cap = profile.get("max_runs_per_day")
    if isinstance(cap, bool) or not isinstance(cap, int) or cap < 1:
        raise ValueError("max_runs_per_day must be a positive integer")
    if profile["min_interval_hours"] > profile["regular_interval_hours"]:
        raise ValueError("min interval exceeds regular interval")
    strings(profile.get("event_types"), "event_types")
    calendar = profile.get("calendar")
    if calendar is not None:
        if (not isinstance(calendar, dict) or calendar.get("name") != "XNYS"
                or calendar.get("cadence") not in {"daily", "weekly", "every_n_sessions"}
                or calendar.get("local_time") != "08:45"):
            raise ValueError("calendar requires XNYS, supported cadence and 08:45 local_time")
        if calendar["cadence"] == "every_n_sessions":
            if type(calendar.get("sessions")) is not int or calendar["sessions"] < 1:
                raise ValueError("calendar sessions must be a positive integer")
            datetime.strptime(calendar["anchor_session"], "%Y-%m-%d")


@lru_cache(maxsize=8)
def market_calendar(start, end):
    try:
        import exchange_calendars
    except ImportError as exc:
        raise ValueError("XNYS scheduling requires exchange_calendars; use .venv-portfolio/bin/python") from exc
    return exchange_calendars.get_calendar("XNYS", start=start, end=end)


def calendar_window(profile, state, now):
    """One current market period, with no historical dispatch queue.

    Success anywhere in the current period satisfies regular research, including
    an early event-driven report. Missed periods coalesce at the next session's
    08:45 check; events/review commitments are assessed separately.
    """
    policy = profile["calendar"]
    today = now.astimezone(NY).date()
    anchor = datetime.strptime(policy.get("anchor_session", f"{today.year}-01-02"), "%Y-%m-%d").date()
    start = min(today - timedelta(days=370), anchor - timedelta(days=10))
    cal = market_calendar(str(start), str(today + timedelta(days=370)))
    sessions = [s.date() for s in cal.sessions]
    previous = max(i for i, day in enumerate(sessions) if day <= today)
    following = next(i for i, day in enumerate(sessions) if day > today)
    is_session = sessions[previous] == today
    cadence = policy["cadence"]
    if cadence == "daily":
        period_start = sessions[previous]
        next_period = sessions[previous + 1]
        period_id = str(period_start)
    elif cadence == "weekly":
        period_start = today - timedelta(days=today.weekday())
        next_week = period_start + timedelta(days=7)
        next_period = next(day for day in sessions if day >= next_week)
        period_id = str(period_start)
    else:
        if anchor not in sessions:
            raise ValueError("calendar anchor_session must be an XNYS session")
        anchor_index = sessions.index(anchor)
        index = anchor_index + ((previous - anchor_index) // policy["sessions"]) * policy["sessions"]
        if index < 0:
            raise ValueError("calendar history does not cover current period")
        period_start = sessions[index]
        next_period = sessions[index + policy["sessions"]]
        period_id = str(period_start)
    period_at = datetime.combine(period_start, time(), NY).astimezone(UTC)
    last_success = state["last_successful_research_at"]
    satisfied = last_success is not None and timestamp(last_success) >= period_at
    today_window = datetime.combine(today, time(8, 45), NY).astimezone(UTC)
    due = not satisfied and is_session and now >= today_window
    next_day = next_period if satisfied else today if is_session else sessions[following]
    next_at = datetime.combine(next_day, time(8, 45), NY).astimezone(UTC)
    return {"name": "XNYS", "cadence": cadence, "period_id": period_id,
            "period_start_at": iso(period_at), "period_satisfied": satisfied,
            "is_session": is_session, "regular_due": due,
            "next_regular_at": iso(max(now, next_at))}


def empty_state():
    return dict(last_attempt_at=None, last_successful_research_at=None, last_decision_at=None,
                next_review_at=None, processed_event_ids=[], active_attempt=None, attempts=[])


def validate_state(state, now):
    for key in ("last_attempt_at", "last_successful_research_at", "last_decision_at", "next_review_at"):
        value = state[key]
        if value is not None and timestamp(value) > now and key != "next_review_at":
            raise ValueError(f"clock regression: {key} is in the future")
    strings(state["processed_event_ids"], "processed_event_ids")
    if not isinstance(state["attempts"], list):
        raise ValueError("attempts must be a list")
    ids = set()
    unfinished = []
    for attempt in state["attempts"]:
        if not isinstance(attempt["id"], str) or not attempt["id"] or attempt["id"] in ids:
            raise ValueError("invalid or duplicate attempt id")
        ids.add(attempt["id"])
        started = timestamp(attempt["started_at"])
        if started > now:
            raise ValueError("clock regression: attempt is in the future")
        strings(attempt["event_ids"], "dispatch event_ids")
        if attempt.get("outcome") is None:
            unfinished.append(attempt["id"])
        elif attempt["outcome"] not in OUTCOMES or not started <= timestamp(attempt["finished_at"]) <= now:
            raise ValueError("invalid attempt outcome or finish timestamp")
    if unfinished != ([] if state["active_attempt"] is None else [state["active_attempt"]]):
        raise ValueError("active attempt does not match unfinished attempt")
    last = max((timestamp(a["started_at"]) for a in state["attempts"]), default=None)
    if last != (timestamp(state["last_attempt_at"]) if state["last_attempt_at"] else None):
        raise ValueError("last_attempt_at does not match attempt history")


def assess(profile, state, events, now):
    """Pure per-expert assessment; future event availability is not a trigger."""
    now = timestamp(now)
    validate_profile(profile)
    validate_state(state, now)
    if not isinstance(events, list):
        raise ValueError("events must be a list")
    fresh, seen = [], set()
    for event in events:
        if not isinstance(event, dict) or set(event) != {"id", "type", "available_at", "expert_ids"}:
            raise ValueError("events require only id, type, available_at, expert_ids; no narrative")
        strings([event["id"]], "event id")
        strings([event["type"]], "event type")
        strings(event["expert_ids"], "expert_ids")
        if event["id"] in seen:
            raise ValueError("duplicate event id")
        seen.add(event["id"])
        available = timestamp(event["available_at"])
        if (available <= now and profile["id"] in event["expert_ids"]
                and event["type"] in profile["event_types"] and event["id"] not in state["processed_event_ids"]):
            fresh.append(event["id"])
    reasons, scheduled = [], []
    calendar = None
    if profile.get("calendar"):
        calendar = calendar_window(profile, state, now)
        scheduled.append(timestamp(calendar["next_regular_at"]))
        if calendar["regular_due"]:
            reasons.append("initial_research" if state["last_successful_research_at"] is None else "calendar_window")
    elif state["last_successful_research_at"] is None:
        reasons.append("initial_research")
    else:
        regular = timestamp(state["last_successful_research_at"]) + timedelta(hours=profile["regular_interval_hours"])
        scheduled.append(regular)
        if now >= regular:
            reasons.append("regular_interval")
    if state["next_review_at"] is not None:
        review = timestamp(state["next_review_at"])
        scheduled.append(review)
        if now >= review:
            reasons.append("next_review")
    if fresh:
        reasons.append("new_event")
    earliest = now if reasons else min(scheduled)
    blockers = []
    if state["last_attempt_at"]:
        minimum = timestamp(state["last_attempt_at"]) + timedelta(hours=profile["min_interval_hours"])
        earliest = max(earliest, minimum)
        if now < minimum:
            blockers.append("min_interval")
    if state["attempts"]:
        latest = max(state["attempts"], key=lambda a: timestamp(a["started_at"]))
        if latest.get("outcome") == "blocked" and not set(fresh).difference(latest["event_ids"]):
            blockers.append("awaiting_new_evidence")
        if latest.get("outcome") in OUTCOMES - {"completed"}:
            retry = timestamp(latest["finished_at"]) + timedelta(hours=profile["retry_cooldown_hours"])
            earliest = max(earliest, retry)
            if now < retry:
                blockers.append("retry_cooldown")
    today = now.astimezone(NY).date()
    count = sum(timestamp(a["started_at"]).astimezone(NY).date() == today for a in state["attempts"])
    if count >= profile["max_runs_per_day"]:
        earliest = max(earliest, datetime.combine(today + timedelta(days=1), time(), NY).astimezone(UTC))
        blockers.append("daily_cap")
    if state["active_attempt"] is not None:
        blockers.append("active_attempt")
    if state.get("stopped") or state.get("stop_requested") or state.get("paused"):
        blockers.append("stopped")
    result = {"due": bool(reasons) and not blockers, "reasons": reasons + blockers,
            "event_ids": sorted(fresh),
            "next_eligible_at": None if state["active_attempt"] or any(
                b in blockers for b in ("awaiting_new_evidence", "stopped")) else iso(earliest)}
    if calendar:
        result["calendar"] = calendar
    return result


def canonical_hash(value):
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def provenance(profile, events):
    return {"profile": dict(profile), "profile_sha256": canonical_hash(profile),
            "event_metadata_sha256": canonical_hash(events)}


def read_json(path):
    with Path(path).open() as stream:
        return json.load(stream)


def profiles_at(path):
    policy = read_json(path)
    if policy.get("schema_version") != 1 or policy.get("timezone") != "America/New_York":
        raise ValueError("policy requires schema_version 1 and America/New_York timezone")
    if not isinstance(policy.get("experts"), list) or not policy["experts"]:
        raise ValueError("policy requires experts")
    result = {}
    for profile in policy["experts"]:
        validate_profile(profile)
        if profile["id"] in result:
            raise ValueError("duplicate expert id")
        result[profile["id"]] = profile
    return result


def state_at(path):
    state = read_json(path)
    if state.get("schema_version") != 1 or not isinstance(state.get("experts"), dict):
        raise ValueError("state requires schema_version 1 and experts object")
    return state


@contextmanager
def locked(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.with_name(path.name + ".lock").open("a") as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ValueError("state is locked; retry later") from exc
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def write_json(path, value, exclusive=False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix=".forward-", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump(value, stream, indent=2, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        if exclusive:
            os.link(temp, path)
        else:
            os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def artifact(path):
    if path is None or not Path(path).is_file():
        raise ValueError("completed research requires existing report and decision files")
    resolved = Path(path).resolve()
    digest = hashlib.sha256()
    with resolved.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return {"path": str(resolved), "sha256": digest.hexdigest()}


def finish(args, state, now, references):
    own = state["experts"][args.expert]
    validate_state(own, now)
    attempt = next((a for a in own["attempts"] if a["id"] == args.attempt), None)
    if attempt is None:
        raise ValueError("unknown attempt for this expert")
    review = iso(timestamp(args.next_review_at)) if args.next_review_at else None
    receipt = {"outcome": args.outcome, **references, "next_review_at": review}
    if args.outcome == "completed" and (receipt["report"] is None or receipt["decision"] is None):
        raise ValueError("completed research requires existing report and decision files")
    if attempt.get("outcome") is not None:
        if any(attempt.get(k) != v for k, v in receipt.items()):
            raise ValueError("conflicting repeated finish")
        return attempt, False
    if own["active_attempt"] != args.attempt:
        raise ValueError("attempt is not active")
    if review is not None and timestamp(review) < now:
        raise ValueError("next review must not precede actual finish time")
    attempt.update(receipt, finished_at=iso(now))
    own["active_attempt"] = None
    if args.outcome == "completed":
        own["processed_event_ids"] = sorted(set(own["processed_event_ids"]) | set(attempt["event_ids"]))
        own["last_successful_research_at"] = own["last_decision_at"] = iso(now)
        # An early event or regular report must not erase/postpone a future
        # promise. Keep the earlier outstanding review; clear fulfilled times.
        previous_review = own["next_review_at"]
        pending = [value for value in (review, previous_review)
                   if value is not None and timestamp(value) > now]
        own["next_review_at"] = min(pending, key=timestamp) if pending else review
    return attempt, True


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    commands = result.add_subparsers(dest="command", required=True)
    for name in ("init", "check", "start", "finish"):
        cmd = commands.add_parser(name)
        cmd.add_argument("--state", required=True, type=Path)
        if name != "finish":
            cmd.add_argument("--policy", required=True, type=Path)
        if name in {"check", "start"}:
            cmd.add_argument("--events", required=True, type=Path, help="JSON array of neutral event metadata")
        if name != "init":
            cmd.add_argument("--expert", required=name != "check")
        if name == "check":
            cmd.add_argument("--log", action="store_true", help="append a unique receipt under state-parent/checks")
        if name == "finish":
            cmd.add_argument("--attempt", required=True)
            cmd.add_argument("--outcome", choices=sorted(OUTCOMES), required=True)
            cmd.add_argument("--report", type=Path)
            cmd.add_argument("--decision", type=Path)
            cmd.add_argument("--next-review-at")
    return result


def run(args):
    profiles = profiles_at(args.policy) if args.command != "finish" else None
    events = read_json(args.events) if args.command in {"check", "start"} else None
    # Artifact reads can be large: finish hashes them before the short state lock.
    references = ({"report": artifact(args.report) if args.report else None,
                   "decision": artifact(args.decision) if args.decision else None}
                  if args.command == "finish" else None)
    with locked(args.state):
        now = now_utc()  # Actual dispatch time; no CLI historical clock override.
        if args.command == "init":
            state = {"schema_version": 1, "experts": {key: empty_state() for key in profiles}}
            write_json(args.state, state, exclusive=True)
            return {"state": str(args.state), "initialized_at": iso(now)}
        state = state_at(args.state)
        if profiles is not None and set(state["experts"]) != set(profiles):
            raise ValueError("policy and state expert ids differ")
        if args.expert is not None and args.expert not in state["experts"]:
            raise ValueError("unknown expert")
        if args.command == "finish":
            receipt, changed = finish(args, state, now, references)
            if changed:
                write_json(args.state, state)
            return receipt
        selected = [args.expert] if args.expert else list(profiles)
        checks = {key: {**assess(profiles[key], state["experts"][key], events, now),
                        "provenance": provenance(profiles[key], events)} for key in selected}
        if args.command == "check":
            receipt = {"checked_at": iso(now), "experts": checks}
            if args.log:
                write_json(args.state.parent / "checks" / f"{uuid.uuid4()}.json", receipt, exclusive=True)
            return receipt
        check = checks[args.expert]
        if not check["due"]:
            raise ValueError("expert is not due: " + ", ".join(check["reasons"]))
        own = state["experts"][args.expert]
        attempt = {"id": str(uuid.uuid4()), "started_at": iso(now), "event_ids": check["event_ids"],
                   "reasons": check["reasons"], "provenance": check["provenance"], "outcome": None}
        own["attempts"].append(attempt)
        own["active_attempt"] = attempt["id"]
        own["last_attempt_at"] = iso(now)
        write_json(args.state, state)
        return attempt


def main(argv=None):
    cli = parser()
    args = cli.parse_args(argv)
    try:
        print(json.dumps(run(args), indent=2, allow_nan=False))
    except (ValueError, TypeError, KeyError, AttributeError, OSError, OverflowError) as exc:
        cli.exit(2, f"error: {exc}\n")


if __name__ == "__main__":
    main()
