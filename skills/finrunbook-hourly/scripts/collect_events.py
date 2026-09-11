#!/usr/bin/env python3
"""Bounded official-feed collection. Metadata triggers only; no LLMs or trades."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import copy
from email.utils import parsedate_to_datetime
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import threading
import time
import uuid
from urllib.parse import urlparse, quote
import xml.etree.ElementTree as ET

from check_due import ROOT, resolve, schedule

SEC_LOCK = threading.Lock()
SEC_LAST_REQUEST = 0.0
DENIAL_BACKOFF_SECONDS = 3600
MAX_DENIAL_BACKOFF_SECONDS = 86400


def sanitized_excerpt(value, limit=500):
    """Persist only bounded diagnostic text, never response credentials/contact data."""
    value = value.decode("utf-8", errors="replace") if isinstance(value, bytes) else str(value)
    value = re.sub(r"<[^>]*>", " ", value[:8192])
    value = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", value)
    value = re.sub(r"(?i)(authorization|cookie)\s*[:=][^\r\n]*", r"\1=[redacted]", value)
    value = re.sub(r"(?i)(authorization|cookie|token|api[_-]?key|password|secret)\s*[:=]\s*[^\s,;<]+",
                   r"\1=[redacted]", value)
    value = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[redacted-contact]", value)
    value = re.sub(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", "[redacted-ip]", value)
    value = re.sub(r"(https?://[^\s?]+)\?[^\s]+", r"\1?[redacted-query]", value)
    return " ".join(value.split())[:limit]


class SourceRequestError(ValueError):
    def __init__(self, message, http_status=None, body=b""):
        super().__init__(sanitized_excerpt(message))
        self.http_status = http_status
        self.body_excerpt = sanitized_excerpt(body)


def failure_detail(exc, spec):
    status = getattr(exc, "http_status", None)
    if status is None:
        match = re.search(r"\bHTTP\s+(\d{3})\b", str(exc), re.I)
        status = int(match.group(1)) if match else None
    hint = "Check the official endpoint and network availability; retry on a later collection."
    if status == 403:
        hint = ("Provider denied access. Respect the denial and the retry time; inspect provider access policy. "
                + ("Configure SEC_USER_AGENT only with your actual application/contact identity; never invent a contact."
                   if spec["kind"] == "sec" else "Use the provider's supported feed or request provider assistance."))
    elif status == 429:
        hint = "Provider rate limit; reduce request frequency and respect provider retry guidance."
    detail = {"error": sanitized_excerpt(exc), "http_status": status,
              "body_excerpt": sanitized_excerpt(getattr(exc, "body_excerpt", "")),
              "recovery_hint": hint}
    detail["failure_signature"] = schedule.canonical_hash(
        [type(exc).__name__, status, detail["error"] if status is None or status == 200 else "http_failure"])
    return detail


def safe_url(url):
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in {
            "www.sec.gov", "data.sec.gov", "www.bls.gov", "www.federalreserve.gov"}:
        raise ValueError("unsupported source URL")
    return url


def fetch(url, config):
    # curl's wall-clock timeout covers DNS, connect and body (not only socket inactivity).
    agent = os.environ.get("SEC_USER_AGENT") or config["user_agent"]
    safe_url(url)
    if urlparse(url).hostname in {"www.sec.gov", "data.sec.gov"}:
        global SEC_LAST_REQUEST
        with SEC_LOCK:
            time.sleep(max(0, SEC_LAST_REQUEST + 0.2 - time.monotonic()))
            SEC_LAST_REQUEST = time.monotonic()
    result = subprocess.run([
        "curl", "--silent", "--show-error", "--proto", "=https",
        "--max-time", str(config["timeout_seconds"]), "--max-filesize",
        str(config["max_response_bytes"]), "--user-agent", agent,
        "--write-out", "\n%{http_code}", safe_url(url)
    ], capture_output=True, timeout=config["timeout_seconds"] + 2)
    body, separator, code = result.stdout.rpartition(b"\n")
    status = (int(code) or None) if separator and re.fullmatch(rb"\d{3}", code) else None
    if result.returncode:
        raise SourceRequestError("source request failed: " + result.stderr.decode(errors="replace"), status, body)
    if status is None or not 200 <= status < 300:
        raise SourceRequestError(f"source request failed: HTTP {status}", status, body)
    if len(body) > config["max_response_bytes"]:
        raise SourceRequestError("source response too large", status)
    return body


def published(value):
    try:
        return schedule.iso(schedule.timestamp(value))
    except (ValueError, TypeError, AttributeError):
        parsed = parsedate_to_datetime(value)
        if parsed.tzinfo is None:
            raise ValueError("publication timestamp lacks timezone")
        return schedule.iso(parsed)


def rss_items(raw, spec):
    if b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
        raise ValueError("unsupported XML declarations")
    root = ET.fromstring(raw)
    tag = root.tag.rsplit("}", 1)[-1]
    atom = "{http://www.w3.org/2005/Atom}"
    if tag == "rss":
        entries = root.findall("./channel/item")
    elif root.tag == atom + "feed":
        entries = root.findall(atom + "entry")
    else:
        raise ValueError("response is not an RSS/Atom feed")
    out = []
    for entry in entries:
        if tag == "rss":
            title, link = entry.findtext("title"), entry.findtext("link")
            date = entry.findtext("pubDate")
            identity = entry.findtext("guid") or link
        else:
            title = entry.findtext(atom + "title")
            links = entry.findall(atom + "link")
            link = next((e.get("href") for e in links if e.get("rel", "alternate") == "alternate"), None)
            date = entry.findtext(atom + "published") or entry.findtext(atom + "updated")
            identity = entry.findtext(atom + "id") or link
        if not title or not identity or not date or not link:
            raise ValueError("feed item lacks title, stable identity, date or source link")
        date = published(date)
        # Date distinguishes successive releases at a reused latest-release URL.
        out.append({"key": schedule.canonical_hash([identity, date]), "published_at": date,
                    "title": title, "url": safe_url(link), "types": [spec["type"]]})
    return out


def sec_items(raw, spec):
    data = json.loads(raw)
    if int(data["cik"]) != spec["cik"]:
        raise ValueError("SEC issuer identity mismatch")
    r = data["filings"]["recent"]
    fields = ("accessionNumber", "form", "primaryDocument", "acceptanceDateTime")
    if any(not isinstance(r[k], list) for k in fields) or len({len(r[k]) for k in fields}) != 1:
        raise ValueError("SEC recent columns are not aligned")
    out = []
    for i, accession in enumerate(r["accessionNumber"]):
        form = r["form"][i]
        if form not in {"10-K", "10-Q", "10-K/A", "10-Q/A", "8-K", "8-K/A"}:
            continue
        if not re.fullmatch(r"\d{10}-\d{2}-\d{6}", accession):
            raise ValueError("invalid SEC accession")
        types = {"10-K": ["annual_filing"], "10-Q": ["quarterly_filing"]}.get(form, [])
        if form.endswith("/A"):
            types = ["amendment"]  # An amendment alone is not proof of a restatement.
        elif form == "8-K":
            types = ["material_disclosure"]
            items = set(re.findall(r"\d\.\d{2}", (r.get("items") or [""] * len(r["form"]))[i]))
            if "2.02" in items:
                types.append("earnings")
        doc = r["primaryDocument"][i]
        if not doc or "/" in doc or ".." in doc:
            raise ValueError("invalid SEC document name")
        out.append({"key": accession, "published_at": published(r["acceptanceDateTime"][i]),
                    "title": f"{spec['symbol']} {form}", "form": form, "types": types,
                    "url": f"https://www.sec.gov/Archives/edgar/data/{spec['cik']}/{accession.replace('-', '')}/{quote(doc)}"})
    return out


def sources(config, registry, root):
    universes, errors = {}, []
    for row in registry["experts"]:
        try:
            account = schedule.read_json(resolve(root, row["account"]))
            if account["expert_id"] != row["id"] or account["account_id"] != row["account_id"]:
                raise ValueError("account identity mismatch")
            schedule.strings(account["universe"], "universe")
            universes[row["id"]] = set(account["universe"])
        except (ValueError, TypeError, KeyError, OSError) as exc:
            errors.append({"expert_id": row["id"], "error": str(exc)})
    symbols = set().union(*universes.values()) if universes else set()
    specs = [dict(feed, kind="rss") for feed in config["feeds"]]
    if errors:
        # Advancing a shared issuer's seen-set with incomplete routing would lose
        # its event for the unreadable account after that account recovers.
        errors.append({"error": "SEC collection deferred: account routing incomplete; issuer watermarks unchanged"})
        return specs, errors
    for symbol in sorted(symbols & config["companies"].keys()):
        cik = config["companies"][symbol]
        specs.append({"id": f"sec-{symbol}", "kind": "sec", "symbol": symbol, "cik": cik,
                      "url": f"https://data.sec.gov/submissions/CIK{cik:010d}.json",
                      "expert_ids": sorted(k for k, v in universes.items() if symbol in v)})
    unknown = sorted(symbols - config["companies"].keys() - set(config["excluded_funds"]))
    if unknown:
        errors.append({"error": "unmapped company symbols", "symbols": unknown})
    return specs, errors


def merge_source(state, spec, items, observed_at, raw_path, raw_hash, profiles):
    """First success baselines; later new dated items become durable eligible events."""
    now = schedule.timestamp(observed_at)
    previous = state["sources"].get(spec["id"])
    seen = set(previous["seen"]) if previous else set()
    baseline = previous is None
    new_count = 0
    # Do not mark future-dated entries seen; they can become available later.
    for item in items:
        if schedule.timestamp(item["published_at"]) > now:
            continue
        key = item["key"]
        if key in seen:
            continue
        seen.add(key)
        if baseline:
            continue
        # Late discovery of an older archive item is not a new release.
        if schedule.timestamp(item["published_at"]) < schedule.timestamp(previous["baseline_at"]):
            continue
        for kind in item["types"]:
            targets = sorted(k for k in spec["expert_ids"]
                             if k in profiles and kind in profiles[k]["event_types"])
            if not targets:
                continue
            identity = "official-" + schedule.canonical_hash([spec["id"], key, kind])[:32]
            if identity in state["evidence"]:
                continue
            event = {"id": identity, "type": kind, "available_at": observed_at, "expert_ids": targets}
            state["events"].append(event)
            state["evidence"][identity] = {**item, "source_id": spec["id"],
                "feed_url": spec["url"], "first_observed_at": observed_at,
                "raw_path": str(raw_path), "raw_sha256": raw_hash,
                "availability_basis": "first successful local observation; not claimed publication latency"}
            new_count += 1
    state["sources"][spec["id"]] = {"seen": sorted(seen),
        "baseline_at": previous["baseline_at"] if previous else observed_at,
        "last_success_at": observed_at, "url": spec["url"]}
    return {"status": "baselined" if baseline else "ok", "new_events": new_count,
            "items": len(items), "observed_at": observed_at}


def collect(root, config, registry_path, policy_path, state_path, fetcher=fetch):
    registry = schedule.read_json(registry_path)
    profiles = schedule.profiles_at(policy_path)
    specs, config_errors = sources(config, registry, root)
    snapshot_dir = state_path.parent / "collections" / uuid.uuid4().hex
    with schedule.locked(state_path):
        state = (schedule.read_json(state_path) if state_path.exists() else
                 {"schema_version": 1, "sources": {}, "events": [], "evidence": {}})
        if state["schema_version"] != 1:
            raise ValueError("unsupported collector state")
        state = copy.deepcopy(state)
        health = state.setdefault("source_health", {})
        results = []
        checked_at = schedule.now_utc()

        ready_specs = []
        for spec in specs:
            previous = health.get(spec["id"], {})
            retry = previous.get("next_retry_at")
            if retry and schedule.timestamp(retry) > checked_at:
                results.append({**previous, "source_id": spec["id"], "status": "backoff",
                                "coverage": "unavailable", "notification_required": False})
            else:
                ready_specs.append(spec)

        def load(spec):
            raw = None
            try:
                raw = fetcher(spec["url"], config)
                items = sec_items(raw, spec) if spec["kind"] == "sec" else rss_items(raw, spec)
                return raw, items, schedule.iso(schedule.now_utc()), None
            except Exception as exc:
                if raw is not None and not isinstance(exc, SourceRequestError):
                    exc = SourceRequestError(str(exc), 200, raw)
                return None, None, schedule.iso(schedule.now_utc()), failure_detail(exc, spec)

        # Two workers cap request fan-out; no retries. 17 current sources: <=90s worst case.
        with ThreadPoolExecutor(max_workers=2) as pool:
            for spec, (raw, items, observed, error) in zip(ready_specs, pool.map(load, ready_specs)):
                previous = health.get(spec["id"], {})
                if error:
                    streak = (previous.get("consecutive_denials", 0) + 1) if error["http_status"] == 403 else 0
                    delay = min(MAX_DENIAL_BACKOFF_SECONDS,
                                DENIAL_BACKOFF_SECONDS * 2 ** min(max(0, streak - 1), 16)) if streak else 0
                    current = {**error, "status": "error", "coverage": "unavailable",
                        "consecutive_failures": previous.get("consecutive_failures", 0) + 1,
                        "consecutive_denials": streak,
                        "first_failure_at": previous.get("first_failure_at") or observed,
                        "last_attempt_at": observed, "last_success_at": previous.get("last_success_at")
                            or state["sources"].get(spec["id"], {}).get("last_success_at"),
                        "next_retry_at": schedule.iso(schedule.timestamp(observed)
                            + schedule.timedelta(seconds=delay)) if delay else None,
                        "notification_required": previous.get("failure_signature") != error["failure_signature"]}
                    health[spec["id"]] = current
                    results.append({"source_id": spec["id"], **current})
                    continue  # Never advance a failed source baseline/watermark.
                raw_hash = hashlib.sha256(raw).hexdigest()
                raw_path = state_path.parent / "raw" / (raw_hash + ".json")
                # JSON wrapper preserves exact source bytes (UTF-8 feeds) for reproducibility.
                if not raw_path.exists():
                    schedule.write_json(raw_path, {"url": spec["url"], "retrieved_at": observed,
                                                   "body": raw.decode("utf-8"), "body_sha256": raw_hash}, exclusive=True)
                merged = merge_source(state, spec, items, observed, raw_path, raw_hash, profiles)
                recovered = previous.get("status") == "error"
                current = {"status": "ok", "coverage": "available", "last_success_at": observed,
                           "last_attempt_at": observed, "consecutive_failures": 0,
                           "consecutive_denials": 0, "next_retry_at": None,
                           "recovered": recovered, "notification_required": recovered}
                if recovered:
                    current["outage_since"] = previous.get("first_failure_at")
                    current["recovery_note"] = "Collection recovered; the outage interval was not continuously monitored."
                health[spec["id"]] = current
                results.append({"source_id": spec["id"], **current, **merged})
        active_ids = set(profiles) & {r["id"] for r in registry["experts"]}
        # Preserve old events durably; scheduler consumption handles repeat suppression.
        events = [{**e, "expert_ids": [k for k in e["expert_ids"] if k in active_ids]}
                  for e in state["events"]]
        events = [e for e in events if e["expert_ids"]]
        results.sort(key=lambda row: next(i for i, spec in enumerate(specs) if spec["id"] == row["source_id"]))
        errors = len(config_errors) + sum(r["status"] in {"error", "backoff"} for r in results)
        config_signature = schedule.canonical_hash(config_errors) if config_errors else None
        config_changed = state.get("config_error_signature") != config_signature
        state["config_error_signature"] = config_signature
        receipt = {"schema_version": 1, "collected_at": schedule.iso(schedule.now_utc()),
            "status": "partial" if errors else "ok", "error_count": errors,
            "notification_required": config_changed or any(r["notification_required"] for r in results),
            "config_sha256": schedule.canonical_hash(config), "config_errors": config_errors,
            "sources": results, "new_events": sum(r.get("new_events", 0) for r in results),
            "events_path": str(snapshot_dir / "events.json"),
            "evidence_path": str(snapshot_dir / "evidence-index.json"),
            "receipt_path": str(snapshot_dir / "collection.json"),
            "excluded": "fund filings, prices/risk signals, news/social, inferred corporate-event classifications"}
        schedule.write_json(snapshot_dir / "events.json", events, exclusive=True)
        schedule.write_json(snapshot_dir / "evidence-index.json", state["evidence"], exclusive=True)
        schedule.write_json(snapshot_dir / "collection.json", receipt, exclusive=True)
        # State last: a failed publication does not consume newly discovered events.
        schedule.write_json(state_path, state)
        return receipt


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--registry", default="portfolio/experts.json")
    p.add_argument("--config", default="skills/finrunbook-hourly/references/event-sources.json")
    p.add_argument("--state", default="runs/hourly-event-cache/state.json")
    p.add_argument("--policy", default="skills/finrunbook-investor/references/forward-profiles.json")
    a = p.parse_args()
    try:
        config = schedule.read_json(resolve(ROOT, a.config))
        receipt = collect(ROOT, config, resolve(ROOT, a.registry), resolve(ROOT, a.policy), resolve(ROOT, a.state))
        print(json.dumps(receipt, indent=2))
        return 2 if receipt["error_count"] else 0
    except (ValueError, TypeError, KeyError, OSError) as exc:
        p.exit(1, f"error: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
