#!/usr/bin/env python3
"""Independent forward paper account; stdlib only, no market/network/model access.

All account mutations use a sidecar advisory lock and atomic file replacement.
The account JSON is the transaction boundary and includes the preserved ledger.
External records are attestations supplied by a trusted collector/reviewer, not
authenticated market feeds. Never use this adapter for real brokerage orders.
"""
import argparse
import copy
from datetime import datetime, timezone
from decimal import Decimal, ROUND_FLOOR
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from contextlib import contextmanager


class Invalid(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise Invalid(message)


def stamp(value):
    require(isinstance(value, str), "timestamp must be a string")
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise Invalid("invalid timestamp") from exc
    require(result.tzinfo is not None, "timestamp needs timezone")
    return result.astimezone(timezone.utc)


def utcnow():
    return datetime.now(timezone.utc).isoformat()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def decimal(value):
    require(not isinstance(value, bool), "boolean is not a number")
    try:
        number = Decimal(str(value))
    except Exception as exc:
        raise Invalid("invalid number") from exc
    require(number.is_finite(), "number must be finite")
    return number


def money(value):
    return str(value.quantize(Decimal("0.000001")))


def snapshot(account):
    keys = ("schema_version", "expert_id", "account_id", "skill_path", "skill_hash",
            "currency", "universe", "funded_at", "initial_capital", "cash", "positions",
            "marks", "observed_at", "pending_intent_id", "revision")
    return {key: copy.deepcopy(account[key]) for key in keys}


def snapshot_receipt(account):
    result = snapshot(account)
    return {"snapshot": result, "account_snapshot_hash": digest(result)}


def init_account(expert_id, account_id, skill_path, now=None, symbols=("MSFT", "AAPL")):
    require(bool(expert_id) and bool(account_id), "expert/account IDs required")
    now = now or utcnow()
    stamp(now)
    require(bool(symbols) and len(set(symbols)) == len(symbols), "nonempty unique universe required")
    require(all(isinstance(s, str) and re.fullmatch(r"[A-Z][A-Z0-9.\-]{0,14}", s) for s in symbols), "invalid universe symbol")
    result = {"schema_version": 1, "expert_id": expert_id, "account_id": account_id,
              "skill_path": str(Path(skill_path).resolve()), "skill_hash": file_hash(skill_path),
              "currency": "USD", "universe": sorted(symbols), "funded_at": now, "initial_capital": "100000.000000",
              "cash": "100000.000000", "positions": {}, "marks": {}, "observed_at": now,
              "pending_intent_id": None, "revision": 0, "decisions": [], "intents": [],
              "ledger": [{"type": "funding", "at": now, "amount": "100000.000000"}],
              "settlements": {}, "observation_events": {}, "review_events": []}
    return result


def validate(account, candidate):
    """Deterministic structural/binding checks, not financial judgment."""
    required = ("expert_id", "account_id", "task_id", "skill_hash", "report_path",
                "report_hash", "evidence_path", "evidence_hash", "evidence_cutoff",
                "account_snapshot_hash", "action", "rationale", "next_review_condition")
    require(all(key in candidate for key in required), "missing candidate fields")
    require("sealed_at" not in candidate, "only controller supplies seal time")
    require(candidate["expert_id"] == account["expert_id"], "wrong expert")
    require(candidate["account_id"] == account["account_id"], "wrong account")
    for key in ("task_id", "rationale", "next_review_condition"):
        require(isinstance(candidate[key], str) and bool(candidate[key].strip()), key + " required")
    require(candidate["skill_hash"] == account["skill_hash"] == file_hash(account["skill_path"]), "skill hash mismatch")
    require(candidate["account_snapshot_hash"] == digest(snapshot(account)), "stale account snapshot")
    require(candidate["report_hash"] == file_hash(candidate["report_path"]), "report hash mismatch")
    require(candidate["evidence_hash"] == file_hash(candidate["evidence_path"]), "evidence hash mismatch")
    cutoff = stamp(candidate["evidence_cutoff"])
    evidence = read(candidate["evidence_path"])
    require(isinstance(evidence.get("sources"), list) and evidence["sources"], "evidence sources required")
    for source in evidence["sources"]:
        require(stamp(source["available_at"]) <= stamp(source["retrieved_at"]) <= cutoff,
                "source unavailable or retrieved after cutoff")
    require(candidate["action"] in ("rebalance", "no_change"), "invalid decision action")
    if candidate["action"] == "no_change":
        require(not any(key in candidate for key in ("target_weights", "replaces_intent_id")),
                "no_change cannot alter targets or cancel pending intent")
    else:
        require(candidate.get("execution_policy") in ("next_regular_session_open", "fresh_reference_price_ledger"),
                "unsupported execution policy")
        weights = candidate.get("target_weights")
        require(isinstance(weights, dict), "target_weights map required (empty = liquidation)")
        for ticker, value in weights.items():
            require(bool(re.fullmatch(r"[A-Z][A-Z0-9.\-]{0,14}", ticker)), "invalid ticker")
            require(ticker in account["universe"], "target outside enrolled universe")
            require(Decimal(0) <= decimal(value) <= Decimal("0.30"), "target outside 0..30%")
        require(sum((decimal(v) for v in weights.values()), Decimal(0)) <= 1, "target leverage")
        limits = candidate.get("price_limits")
        require(isinstance(limits, dict), "explicit price_limits required")
        symbols = set(weights) | set(account["positions"])
        require(symbols <= set(limits), "price limits missing for target/existing holding")
        for symbol in symbols:
            require(0 < decimal(limits[symbol]["min"]) <= decimal(limits[symbol]["max"]), "invalid price bounds")
        require(candidate.get("replaces_intent_id") == account["pending_intent_id"],
                "replacement must explicitly name current pending intent")
    return {"schema_version": 1, "status": "PASS", "candidate_hash": digest(candidate),
            "account_snapshot_hash": digest(snapshot(account)),
            "checks": ["identity", "artifact_hashes", "evidence_timestamps", "action_schema", "portfolio_limits"]}


def review_status(review, candidate, now):
    require(review.get("candidate_hash") == digest(candidate), "review candidate mismatch")
    require(review.get("author_task_id") == candidate["task_id"], "review author mismatch")
    require(isinstance(review.get("reviewer_task_id"), str) and review["reviewer_task_id"]
            and review["reviewer_task_id"] != candidate["task_id"], "independent reviewer required")
    require(review.get("parent_history_inherited") is False, "review must declare fresh context")
    require(stamp(candidate["evidence_cutoff"]) <= stamp(review["reviewed_at"]) <= stamp(now), "review time invalid")
    findings = review.get("findings", [])
    require(isinstance(findings, list) and findings, "review findings required")
    ids = [finding["id"] for finding in findings]
    require(len(ids) == len(set(ids)), "duplicate review finding")
    for key in ("material_evidence", "calculations", "report_decision"):
        require(any(f["id"] == key and f.get("required") is True for f in findings), "missing required review: " + key)
    for finding in findings:
        require(isinstance(finding.get("required"), bool) and finding.get("status") in ("PASS", "WARN", "FAIL"), "invalid finding")
    require(not any(f["required"] and f["status"] == "FAIL" for f in findings), "required financial review failed")
    status = "PASS_WITH_WARNINGS" if any(f["status"] != "PASS" for f in findings) else "PASS"
    require(review.get("status", status) == status, "review aggregate disagrees with findings")
    return status


def seal(account, candidate, validation, review, now=None):
    now = now or utcnow()
    require(stamp(now) >= stamp(account["funded_at"]), "seal cannot predate account funding")
    require(stamp(account["observed_at"]) <= stamp(now), "seal cannot predate account observation")
    candidate_hash = digest(candidate)
    for existing in account["decisions"]:
        if existing["candidate_hash"] == candidate_hash:
            require(existing["validation_hash"] == digest(validation) and existing["review_hash"] == digest(review), "conflicting seal retry")
            return copy.deepcopy(existing)
    require(validation == validate(account, candidate), "invalid deterministic validation receipt")
    require(stamp(candidate["evidence_cutoff"]) < stamp(now), "seal must follow evidence cutoff")
    status = review_status(review, candidate, now)
    identity = {"candidate_hash": candidate_hash, "validation_hash": digest(validation),
                "review_hash": digest(review), "sealed_at": now}
    record = dict(identity, decision_id="decision-" + digest(identity)[:24], status=status,
                  candidate=copy.deepcopy(candidate), review=copy.deepcopy(review), validation=copy.deepcopy(validation))
    record["execution_rules"] = {"paper_only": True, "long_only": True, "whole_shares": True,
                                 "max_security_weight": "0.30", "adverse_slippage_bps": 10,
                                 "leverage": False, "fees": "0", "basket_atomic": True,
                                 "risk_breach_policy": "leave_unfilled_and_request_review"}
    if candidate["action"] == "rebalance":
        old_id = account["pending_intent_id"]
        if old_id:
            old = next(i for i in account["intents"] if i["intent_id"] == old_id)
            old["status"] = "replaced"
            account["ledger"].append({"type": "replace_intent", "at": now, "old_intent_id": old_id,
                                      "decision_id": record["decision_id"]})
        intent_id = "intent-" + digest(identity)[:24]
        account["intents"].append({"intent_id": intent_id, "decision_id": record["decision_id"], "status": "pending"})
        account["pending_intent_id"] = intent_id
        record["intent_id"] = intent_id
    account["decisions"].append(record)
    account["ledger"].append({"type": "sealed_decision", **identity, "decision_id": record["decision_id"], "action": candidate["action"]})
    account["revision"] += 1
    return copy.deepcopy(record)


def pending(reason, **extra):
    return {"status": "pending", "reason": reason, **extra}


def settle(account, observations, now=None):
    """Ingest immutable observation versions, including pending/rejected ones.

    Repeating an event returns its original receipt. New data for that decision
    and session requires a new event_id, supersedes_event_id naming the latest
    version, and a nonempty correction_reason. Completed fills cannot be revised.
    This wrapper persists audit records in memory even when raising Invalid;
    the CLI saves those records before reporting a rejection.
    """
    now = now or utcnow()
    observation_hash = digest(observations)
    event_id = observations.get("event_id")
    valid_id = isinstance(event_id, str) and bool(event_id)
    event_key = event_id if valid_id else "invalid-event-" + observation_hash
    events = account.setdefault("observation_events", {})
    existing = events.get(event_key)
    if existing and existing["observation_hash"] == observation_hash:
        receipt = copy.deepcopy(existing["receipt"])
        if receipt["status"] == "rejected":
            raise Invalid(receipt["reason"])
        return receipt
    try:
        require(not existing, "event ID reused with different observations")
        require(valid_id, "observation event ID required")
        session_id = (observations.get("session") or {}).get("id")
        # Ledger order survives JSON key sorting. Ignore conflicting submissions
        # whose payload differs from the immutable event registered under that ID.
        previous = [item for item in account["ledger"]
                    if item.get("type") == "observation_ingested"
                    and events.get(item.get("event_id"), {}).get("observation_hash") == item["observation_hash"]
                    and item["observations"].get("account_id") == observations.get("account_id")
                    and item["observations"].get("decision_id") == observations.get("decision_id")
                    and ((item["observations"].get("session") or {}).get("id") in (session_id, None))]
        supersedes = observations.get("supersedes_event_id")
        if previous:
            latest = previous[-1]
            require(supersedes == latest["event_id"], "new session observations must explicitly supersede latest event")
            require(latest["receipt"]["status"] != "filled", "cannot supersede completed fills")
        elif supersedes is not None:
            raise Invalid("superseded event does not belong to this account/decision/session")
        if supersedes is not None:
            require(isinstance(observations.get("correction_reason"), str)
                    and bool(observations["correction_reason"].strip()), "observation correction reason required")
        receipt = _settle_observed(account, observations, now)
    except (Invalid, KeyError, TypeError, ValueError) as exc:
        receipt = {"status": "rejected", "reason": str(exc), "event_id": event_id}
        _record_observation(account, events, event_key, observations, observation_hash, receipt, now,
                            conflict=existing is not None)
        raise Invalid(str(exc)) from exc
    _record_observation(account, events, event_key, observations, observation_hash, receipt, now)
    return receipt


def _record_observation(account, events, key, observations, observation_hash, receipt, now, conflict=False):
    record = {"event_id": observations.get("event_id"), "observation_hash": observation_hash,
              "observations": copy.deepcopy(observations), "receipt": copy.deepcopy(receipt), "recorded_at": now}
    if not conflict:
        events[key] = record
    # Conflict attempts preserve the original event and their own rejected payload.
    if not any(e.get("type") == "observation_ingested" and e.get("observation_hash") == observation_hash
               for e in account["ledger"]):
        account["ledger"].append({"type": "observation_ingested", **copy.deepcopy(record)})
        account["revision"] += 1


def _settle_observed(account, observations, now=None):
    """Settle only an explicitly attested next session; never infer holidays.

    Observation shape: event_id, account_id, decision_id, observed_at,
    session:{id,regular:true,open_at,previous_regular_open_at,
    next_for_decision_id,source}, sizing:{as_of,observed_at,
    last_eligible_close_for_decision_id,source,prices},
    prices:{SYMBOL:{open,tradable:true,corporate_actions_checked:true}}.
    Price observations are subsequently collected, while sizing uses the last
    closing snapshot already known at the decision seal. All required symbols
    must be present and all checks pass; partial baskets are never applied.
    """
    now = now or utcnow()
    require(observations.get("account_id") == account["account_id"], "observation account mismatch")
    require(bool(observations.get("event_id")), "observation event ID required")
    event_key = observations["event_id"]
    old = account["settlements"].get(event_key)
    if old:
        require(old["observation_hash"] == digest(observations), "event ID reused with different observations")
        return copy.deepcopy(old["receipt"])
    intent_id = account["pending_intent_id"]
    if not intent_id:
        return pending("no_active_intent")
    intent = next(i for i in account["intents"] if i["intent_id"] == intent_id)
    decision = next(d for d in account["decisions"] if d["decision_id"] == intent["decision_id"])
    require(decision["candidate"]["execution_policy"] == "next_regular_session_open",
            "fresh-reference decisions require the execution queue")
    require(observations.get("decision_id") == decision["decision_id"], "observation decision mismatch")
    session = observations.get("session")
    if not session or not observations.get("observed_at"):
        return pending("missing_session_observation")
    required_session = ("id", "regular", "open_at", "previous_regular_open_at", "next_for_decision_id", "source")
    if not all(key in session for key in required_session):
        return pending("incomplete_trusted_session_record")
    require(session["regular"] is True and bool(session["source"]), "trusted regular session required")
    require(session["next_for_decision_id"] == decision["decision_id"], "session not attested as next for decision")
    opened, sealed = stamp(session["open_at"]), stamp(decision["sealed_at"])
    require(stamp(session["previous_regular_open_at"]) <= sealed < opened, "not next future regular open")
    require(stamp(decision["candidate"]["evidence_cutoff"]) < opened, "execution precedes evidence cutoff")
    if stamp(now) < opened:
        return pending("session_open_not_yet_observed")
    require(opened <= stamp(observations["observed_at"]) <= stamp(now), "invalid observation time")
    key = digest([account["account_id"], decision["decision_id"], session["id"]])
    require(not any(entry.get("execution_key") == key for entry in account["ledger"]), "session already settled")
    sizing = observations.get("sizing", {})
    sizing_keys = ("as_of", "observed_at", "last_eligible_close_for_decision_id", "source", "prices")
    if not all(k in sizing for k in sizing_keys):
        return pending("missing_sizing_close")
    require(sizing["last_eligible_close_for_decision_id"] == decision["decision_id"] and bool(sizing["source"]), "untrusted sizing snapshot")
    require(stamp(sizing["as_of"]) <= stamp(sizing["observed_at"]) <= sealed, "sizing price not known at seal")
    candidate = decision["candidate"]
    weights = candidate["target_weights"]
    symbols = sorted(set(weights) | set(account["positions"]))
    prices = observations.get("prices", {})
    if any(s not in prices or s not in sizing["prices"] for s in symbols):
        return pending("missing_prices")
    if any(not isinstance(prices[s], dict) or "open" not in prices[s] for s in symbols):
        return pending("missing_open_prices")
    for symbol in symbols:
        if prices[symbol].get("corporate_actions_checked") is not True:
            return pending("corporate_actions_not_verified", symbol=symbol)
        if prices[symbol].get("unsupported_corporate_action"):
            return pending("unsupported_corporate_action", symbol=symbol)
        if prices[symbol].get("tradable") is not True:
            return pending("not_tradable", symbol=symbol)
        require(decimal(prices[symbol]["open"]) > 0 and decimal(sizing["prices"][symbol]) > 0, "nonpositive price")
    cash = decimal(account["cash"])
    sizing_nav = cash + sum((decimal(sizing["prices"][s]) * n for s, n in account["positions"].items()), Decimal(0))
    targets = {s: int((sizing_nav * decimal(weights.get(s, 0)) / decimal(sizing["prices"][s])).to_integral_value(rounding=ROUND_FLOOR)) for s in symbols}
    fills = []
    for symbol in symbols:
        delta = targets[symbol] - account["positions"].get(symbol, 0)
        if not delta:
            continue
        raw = decimal(prices[symbol]["open"])
        fill_price = raw * (Decimal("1.001") if delta > 0 else Decimal("0.999"))
        limits = candidate["price_limits"][symbol]
        if not decimal(limits["min"]) <= fill_price <= decimal(limits["max"]):
            return review_pending(account, decision, session, "price_limit", now, symbol)
        cash -= delta * fill_price
        fills.append({"symbol": symbol, "shares": delta, "side": "buy" if delta > 0 else "sell",
                      "observed_open": str(raw), "fill_price": str(fill_price), "fees": "0",
                      "slippage_cost": str(abs(delta) * raw * Decimal("0.001"))})
    if cash < 0:
        return review_pending(account, decision, session, "insufficient_cash", now)
    nav = cash + sum((targets[s] * decimal(prices[s]["open"]) for s in symbols), Decimal(0))
    if nav <= 0 or any(targets[s] * decimal(prices[s]["open"]) > Decimal("0.30") * nav for s in symbols):
        return review_pending(account, decision, session, "fill_time_security_cap", now)
    account["cash"] = str(cash)
    account["positions"] = {s: n for s, n in targets.items() if n}
    account["marks"] = {s: str(prices[s]["open"]) for s in account["positions"]}
    account["observed_at"] = observations["observed_at"]
    receipt = {"status": "filled", "execution_key": key, "event_id": event_key,
               "decision_id": decision["decision_id"], "intent_id": intent_id,
               "session_id": session["id"], "filled_at": session["open_at"],
               "recorded_at": now, "fills": fills, "cash": account["cash"],
               "positions": copy.deepcopy(account["positions"]), "nav": money(nav),
               "return_since_funding": str(nav / decimal(account["initial_capital"]) - 1)}
    account["ledger"].append({"type": "settlement", **copy.deepcopy(receipt), "observations": copy.deepcopy(observations)})
    intent["status"] = "filled"
    account["pending_intent_id"] = None
    account["settlements"][event_key] = {"observation_hash": digest(observations), "receipt": copy.deepcopy(receipt)}
    account["revision"] += 1
    return receipt


def review_pending(account, decision, session, reason, now, symbol=None):
    event = {"id": digest([decision["decision_id"], session["id"], reason, symbol]),
             "decision_id": decision["decision_id"], "session_id": session["id"],
             "reason": reason, "symbol": symbol, "at": now}
    if not any(e["id"] == event["id"] for e in account["review_events"]):
        account["review_events"].append(event)
        account["ledger"].append({"type": "review_required", **event})
    return pending(reason, review_event_id=event["id"])


def atomic_write(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w") as stream:
            json.dump(data, stream, indent=2, sort_keys=True, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


@contextmanager
def locked(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with Path(str(path) + ".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield


def reject_output_alias(output, protected):
    """Protect direct paths, symlinks and existing hardlink aliases."""
    if not output:
        return
    output_path = Path(output)
    for item in protected:
        if not item:
            continue
        input_path = Path(item)
        alias = output_path.resolve() == input_path.resolve()
        if not alias and output_path.exists() and input_path.exists():
            alias = os.path.samefile(output_path, input_path)
        require(not alias, "output cannot overwrite account, lockfile or input artifact")


def artifact_paths(candidate):
    return [candidate[key] for key in ("report_path", "evidence_path") if candidate.get(key)]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("init", "snapshot", "validate", "seal", "settle"):
        item = sub.add_parser(command)
        item.add_argument("--account", required=True)
        item.add_argument("--output")
        if command == "init":
            item.add_argument("--expert", required=True)
            item.add_argument("--account-id", required=True)
            item.add_argument("--skill", required=True)
            item.add_argument("--symbols", nargs="+", required=True)
        if command in ("validate", "seal"):
            item.add_argument("--candidate", required=True)
        if command == "seal":
            item.add_argument("--validation", required=True)
            item.add_argument("--review", required=True)
        if command == "settle":
            item.add_argument("--observations", required=True)
    args = parser.parse_args(argv)
    try:
        protected = [args.account, str(args.account) + ".lock"] + [getattr(args, k) for k in ("candidate", "validation", "review", "observations", "skill") if getattr(args, k, None)]
        reject_output_alias(args.output, protected)
        with locked(args.account):
            if args.command == "init":
                require(not Path(args.account).exists(), "account already exists")
                account = init_account(args.expert, args.account_id, args.skill, symbols=args.symbols)
                result = snapshot_receipt(account)
            else:
                account = read(args.account)
                protected.append(account["skill_path"])
                for decision in account["decisions"]:
                    protected.extend(artifact_paths(decision["candidate"]))
                candidate = read(args.candidate) if args.command in ("validate", "seal") else None
                if candidate is not None:
                    protected.extend(artifact_paths(candidate))
                reject_output_alias(args.output, protected)
                if args.command == "snapshot":
                    result = snapshot_receipt(account)
                elif args.command == "validate":
                    result = validate(account, candidate)
                elif args.command == "seal":
                    result = seal(account, candidate, read(args.validation), read(args.review))
                else:
                    try:
                        result = settle(account, read(args.observations))
                    except Invalid:
                        atomic_write(args.account, account)
                        raise
            if args.command in ("init", "seal", "settle"):
                atomic_write(args.account, account)
        if args.output:
            atomic_write(args.output, result)
        print(json.dumps(result, indent=2, sort_keys=True))
    except (Invalid, KeyError, TypeError, OSError, json.JSONDecodeError) as exc:
        parser.exit(2, "forward_account: " + str(exc) + "\n")


if __name__ == "__main__":
    main()
