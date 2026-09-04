#!/usr/bin/env python3
"""Read-only market collection, reproducible metrics and FinRunbook receipts.

Only the Yahoo adapter needs third-party packages. Validation and tests use the
standard library and never fetch data. Snapshot bars are client-normalized data.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sys
import tempfile
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote
from zoneinfo import ZoneInfo


SCHEMA_VERSION = "1.0.0"
INTERVALS = {"1d": 86400, "1m": 60, "5m": 300, "15m": 900, "30m": 1800, "60m": 3600}
PRICE_FIELDS = {"close": "close", "adj-close": "adj_close"}
TERMS = "Unofficial Yahoo access via yfinance; personal research only; commercial/data redistribution rights not established. https://github.com/ranaroussi/yfinance"


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def timestamp(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timezone-aware timestamp required")
    return parsed


def finite(value):
    return isinstance(value, (float, int)) and not isinstance(value, bool) and math.isfinite(value)


def volume_units(series):
    return ("shares" if series.get("metadata", {}).get("instrumentType") in {"EQUITY", "ETF"}
            else "provider-volume-units")


def atomic_json(path, value):
    data = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(data)
    try:
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def local_path(root, relative):
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise ValueError("expected run-relative path")
    candidate = (root / relative).resolve()
    candidate.relative_to(root.resolve())
    return candidate


def validate_request(request):
    start, end = date.fromisoformat(request["start"]), date.fromisoformat(request["end"])
    if start >= end:
        raise ValueError("start must precede exclusive end")
    if request["interval"] not in INTERVALS or request["price_basis"] not in PRICE_FIELDS:
        raise ValueError("unsupported interval or price basis")
    if request["interval"] != "1d" and request["price_basis"] != "close":
        raise ValueError("intraday requests require --price-basis close")
    if request["interval"] == "1d" and request["include_extended"]:
        raise ValueError("extended sessions require an intraday interval")
    if not finite(request["max_age_hours"]) or request["max_age_hours"] <= 0:
        raise ValueError("max-age-hours must be positive and finite")
    symbols = request["symbols"] + ([request["benchmark"]] if request.get("benchmark") else [])
    if not symbols or any(not re.fullmatch(r"[A-Za-z0-9^][A-Za-z0-9.^=_-]{0,39}", s) for s in symbols):
        raise ValueError("explicit valid provider tickers required")


def yahoo_history(symbol, request, cache_dir):
    import yfinance as yf  # Optional dependency; no import during offline validation.

    yf.set_tz_cache_location(str(cache_dir))
    # Pinned yfinance 1.2 uses this setting instead of deprecated raise_errors.
    previous_hide_exceptions = yf.config.debug.hide_exceptions
    yf.config.debug.hide_exceptions = False
    params = dict(start=request["start"], end=request["end"], interval=request["interval"],
                  auto_adjust=False, back_adjust=False, actions=True, repair=False,
                  keepna=True, rounding=False, prepost=request["include_extended"],
                  timeout=20)
    result = {"symbol": symbol, "provider": "Yahoo Finance", "client": f"yfinance {yf.__version__}",
              "params": params, "source_url": f"https://finance.yahoo.com/quote/{quote(symbol, safe='')}/history/",
              "client_settings": {"hide_exceptions": False},
              "status": "error", "bars": [], "metadata": {}, "errors": []}
    try:
        ticker = yf.Ticker(symbol)
        frame = ticker.history(**params)
        # Public metadata access may make an additional bounded request in yfinance.
        metadata = ticker.history_metadata or {}
        result["metadata"] = {key: metadata.get(key) for key in
                              ("symbol", "exchangeName", "fullExchangeName", "currency",
                               "exchangeTimezoneName", "instrumentType")}
        result["exchange"] = metadata.get("exchangeName")
        result["currency"] = metadata.get("currency")
        result["timezone"] = metadata.get("exchangeTimezoneName")
        fields = {"Open": "open", "High": "high", "Low": "low", "Close": "close",
                  "Adj Close": "adj_close", "Volume": "volume", "Dividends": "dividends",
                  "Stock Splits": "splits"}
        for stamp, row in frame.iterrows():
            bar = {"timestamp": stamp.isoformat()}
            for source, field in fields.items():
                raw = row.get(source)
                value = float(raw) if raw is not None else None
                bar[field] = value if finite(value) else None
            result["bars"].append(bar)
        result["status"] = "ok" if result["bars"] else "empty"
    except Exception as error:
        result["errors"].append(f"{type(error).__name__}: {error}")
    finally:
        yf.config.debug.hide_exceptions = previous_hide_exceptions
    return result


ADAPTERS = {"yahoo": yahoo_history}


def quality_checks(snapshot):
    """Reject bad bars; report gaps without claiming exchange-calendar coverage."""
    request, checked_at = snapshot["request"], timestamp(snapshot["retrieved_at"])
    field = PRICE_FIELDS[request["price_basis"]]
    issues = []

    def add(level, code, message, index):
        issues.append({"severity": level, "code": code, "message": message, "series": index})

    for si, series in enumerate(snapshot["series"]):
        if series["status"] != "ok" or not series["bars"]:
            add("error", "series_unavailable", f"{series['symbol']}: {series['status']}; {series.get('errors', [])}", si)
            continue
        if any(not series.get(key) for key in ("provider", "client", "source_url", "exchange", "currency", "timezone")):
            add("error", "missing_metadata", "Provider, exchange, currency and timezone are required", si)
            continue
        try:
            zone = ZoneInfo(series["timezone"])
        except (ValueError, KeyError):
            add("error", "invalid_timezone", "Unknown exchange timezone", si)
            continue
        returned_symbol = series.get("metadata", {}).get("symbol")
        if returned_symbol and returned_symbol.upper() != series["symbol"].upper():
            add("error", "symbol_mismatch", "Returned ticker differs from requested ticker", si)
        stamps, invalid = [], False
        for bar in series["bars"]:
            try:
                stamp = timestamp(bar["timestamp"])
            except (KeyError, TypeError, ValueError):
                invalid = True
                break
            stamps.append(stamp)
            day = stamp.astimezone(zone).date().isoformat()
            prices = [bar.get(key) for key in ("open", "high", "low", "close")]
            invalid |= not (request["start"] <= day < request["end"]) or stamp > checked_at
            invalid |= not finite(bar.get(field)) or (finite(bar.get(field)) and bar[field] <= 0)
            invalid |= any(value is not None and (not finite(value) or value <= 0) for value in prices)
            if all(finite(value) for value in prices):
                opening, high, low, close = prices
                invalid |= low > min(opening, close) or high < max(opening, close) or low > high
            volume = bar.get("volume")
            invalid |= volume is not None and (not finite(volume) or volume < 0)
        invalid |= any(a >= b for a, b in zip(stamps, stamps[1:]))
        if invalid:
            add("error", "invalid_bars", "Invalid/duplicate/unordered/out-of-window timestamp, price, OHLC or volume; no repair applied", si)
            continue
        eligible = completed_indices(series, request, checked_at)
        if len(eligible) < len(series["bars"]):
            add("warning", "incomplete_bars", "Same-day daily or unfinished intraday bars excluded from summary calculations", si)
        if len(eligible) < 2:
            add("warning", "insufficient_bars", "Fewer than two completed observations; no return/drawdown comparison", si)
        end_boundary = datetime.combine(date.fromisoformat(request["end"]), datetime.min.time(), tzinfo=zone)
        target = min(end_boundary, checked_at)
        if (target - stamps[-1]).total_seconds() > request["max_age_hours"] * 3600:
            add("warning", "endpoint_gap", "Last returned bar exceeds the allowed endpoint gap; do not call this a current quote", si)
        if (stamps[0].astimezone(zone).date() - date.fromisoformat(request["start"])).days > 7:
            add("warning", "start_gap", "History begins more than seven days after requested start; review retention/listing limits", si)
        if any(bar.get("splits") or bar.get("dividends") for bar in series["bars"]):
            add("warning", "corporate_actions", "Corporate actions present; check adjustment basis before interpreting moves", si)
    return issues


def completed_indices(series, request, checked_at):
    zone = ZoneInfo(series["timezone"])
    result = []
    for index, bar in enumerate(series["bars"]):
        stamp = timestamp(bar["timestamp"])
        complete = (stamp.astimezone(zone).date() < checked_at.astimezone(zone).date()
                    if request["interval"] == "1d"
                    else stamp + timedelta(seconds=INTERVALS[request["interval"]]) <= checked_at)
        if complete:
            result.append(index)
    return result


def cell_value(snapshot, cell):
    return snapshot["series"][cell["series"]]["bars"][cell["bar"]][cell["field"]]


def analyses(snapshot, quality):
    request = snapshot["request"]
    field = PRICE_FIELDS[request["price_basis"]]
    bad = {item["series"] for item in quality if item["severity"] == "error"}
    eligible, output = {}, []
    for si, series in enumerate(snapshot["series"]):
        if si not in bad:
            eligible[si] = completed_indices(series, request, timestamp(snapshot["retrieved_at"]))

    def cells(si, indexes, name=field):
        return [{"series": si, "bar": i, "field": name} for i in indexes]

    def add(si, kind, inputs, value, expression, units, period):
        output.append({"series": si, "metric": kind, "inputs": inputs, "result": value,
                       "expression": expression, "units": units, "period": period,
                       "price_basis": request["price_basis"], "currency": snapshot["series"][si]["currency"]})

    for si, indexes in eligible.items():
        if len(indexes) < 2:
            if indexes:
                index = indexes[-1]
                bar = snapshot["series"][si]["bars"][index]
                add(si, "last_completed_price", cells(si, [index]), bar[field],
                    "last_completed_price", snapshot["series"][si]["currency"], bar["timestamp"])
            continue
        bars = snapshot["series"][si]["bars"]
        values = [bars[i][field] for i in indexes]
        period = f"{bars[indexes[0]]['timestamp']} / {bars[indexes[-1]]['timestamp']}"
        add(si, "return_pct", cells(si, [indexes[0], indexes[-1]]),
            (values[-1] / values[0] - 1) * 100, "(last / first - 1) * 100", "percent", period)
        peak, drawdown = values[0], 0.0
        for price in values:
            peak = max(peak, price)
            drawdown = min(drawdown, (price / peak - 1) * 100)
        add(si, "max_close_drawdown_pct", cells(si, indexes), drawdown,
            "min(price / cumulative_max(price) - 1) * 100", "percent", period)
        if request["interval"] == "1d" and len(indexes) >= 21:
            volumes = [bars[i].get("volume") for i in indexes[-21:]]
            if all(finite(v) and v >= 0 for v in volumes) and sum(volumes[:-1]) > 0:
                add(si, "volume_vs_prior20", cells(si, indexes[-21:], "volume"),
                    volumes[-1] / (sum(volumes[:-1]) / 20), "last_volume / mean(prior_20_volumes)",
                    "multiple", f"{bars[indexes[-21]]['timestamp']} / {bars[indexes[-1]]['timestamp']}")
    benchmark = request.get("benchmark")
    bi = next((i for i, s in enumerate(snapshot["series"]) if s["symbol"] == benchmark), None)
    if bi in eligible:
        base = snapshot["series"][bi]
        for si, indexes in eligible.items():
            if si == bi:
                continue
            series = snapshot["series"][si]
            if any(series[key] != base[key] for key in ("currency", "timezone")):
                continue
            left = {timestamp(series["bars"][i]["timestamp"]): i for i in indexes}
            right = {timestamp(base["bars"][i]["timestamp"]): i for i in eligible[bi]}
            common = sorted(left.keys() & right.keys())
            if len(common) < 2:
                continue
            inputs = cells(si, [left[common[0]], left[common[-1]]]) + cells(bi, [right[common[0]], right[common[-1]]])
            a0, a1, b0, b1 = [cell_value(snapshot, cell) for cell in inputs]
            add(si, "excess_return_pp", inputs, ((a1 / a0 - 1) - (b1 / b0 - 1)) * 100,
                "((asset_last / asset_first - 1) - (benchmark_last / benchmark_first - 1)) * 100",
                "percentage-points", f"{common[0].isoformat()} / {common[-1].isoformat()}")
    return output


def evaluate_snapshot(snapshot):
    quality = quality_checks(snapshot)
    computed = analyses(snapshot, quality)
    if snapshot["request"].get("benchmark"):
        for si, item in enumerate(snapshot["series"]):
            if item["symbol"] != snapshot["request"]["benchmark"] and not any(a["series"] == si and a["metric"] == "excess_return_pp" for a in computed):
                quality.append({"severity": "warning", "code": "benchmark_unavailable", "series": si,
                                "message": "No comparable benchmark result; verify common timestamps, currency and timezone"})
    return quality, computed


def build_snapshot(request, fetcher, cache_dir):
    series = []
    symbols = list(dict.fromkeys(request["symbols"] + ([request["benchmark"]] if request.get("benchmark") else [])))
    for symbol in symbols:
        try:
            series.append(fetcher(symbol, request, cache_dir))
        except Exception as error:
            series.append({"symbol": symbol, "provider": request["provider"], "status": "error", "bars": [],
                           "errors": [f"{type(error).__name__}: {error}"]})
    snapshot = {"schema_version": SCHEMA_VERSION, "request": request,
                "retrieved_at": utc_now(), "series": series}
    quality, computed = evaluate_snapshot(snapshot)
    snapshot.update(quality_issues=quality, analyses=computed)
    return snapshot


def next_id(record, collection, prefix):
    maximum = max((int(item["id"].split("-")[-1]) for item in record[collection]
                   if re.fullmatch(prefix + r"-\d+", item.get("id", ""))), default=0)
    return f"{prefix}-{maximum + 1:03d}"


def attach_snapshot(record, snapshot, relative, digest, batch_id):
    receipt = {"id": batch_id, "path": relative, "sha256": digest, "required": True,
               "source_ids": [], "input_mappings": [], "analysis_mappings": []}
    for si, series in enumerate(snapshot["series"]):
        sid = next_id(record, "sources", "SRC")
        record["sources"].append({"id": sid, "type": "market-data",
            "title": f"{series['symbol']} {snapshot['request']['interval']} history ({batch_id})",
            "publisher": series["provider"], "url": series.get("source_url"), "local_path": relative,
            "retrieved_at": snapshot["retrieved_at"], "as_of_date": snapshot["retrieved_at"][:10],
            "primary": False, "sha256": digest, "license_or_terms": TERMS,
            "notes": "Normalized client response; not a point-in-time vintage or independently verified exchange feed",
            "market_data_batch_id": batch_id, "series_index": si})
        receipt["source_ids"].append(sid)
    by_cell = {}
    for ai, analysis in enumerate(snapshot["analyses"]):
        input_ids, evidence_ids, source_ids = [], [], []
        for cell in analysis["inputs"]:
            key = (cell["series"], cell["bar"], cell["field"])
            sid = receipt["source_ids"][cell["series"]]
            if key not in by_cell:
                eid, fid = next_id(record, "evidence", "EVD"), next_id(record, "facts", "FACT")
                series = snapshot["series"][cell["series"]]
                value = cell_value(snapshot, cell)
                period = series["bars"][cell["bar"]]["timestamp"]
                units = volume_units(series) if cell["field"] == "volume" else series["currency"]
                locator = f"/series/{cell['series']}/bars/{cell['bar']}/{cell['field']}"
                record["evidence"].append({"id": eid, "source_id": sid, "locator": f"{relative}#{locator}",
                    "content": f"{series['symbol']} {period} {cell['field']} = {value}",
                    "period": period, "units": units, "extracted_at": snapshot["retrieved_at"]})
                record["facts"].append({"id": fid, "statement": f"{series['symbol']} provider {cell['field']} at {period}: {value}",
                    "status": "provider-reported", "material": False, "source_ids": [sid], "evidence_ids": [eid],
                    "value": value, "units": units, "currency": series["currency"], "period": period,
                    "price_basis": snapshot["request"]["price_basis"]})
                mapping = {"cell": cell, "fact_id": fid, "evidence_id": eid}
                receipt["input_mappings"].append(mapping)
                by_cell[key] = mapping
            mapping = by_cell[key]
            input_ids.append(mapping["fact_id"])
            evidence_ids.append(mapping["evidence_id"])
            source_ids.append(sid)
        cid, fid = next_id(record, "calculations", "CALC"), next_id(record, "facts", "FACT")
        symbol = snapshot["series"][analysis["series"]]["symbol"]
        description = f"{symbol} {analysis['metric']} ({analysis['price_basis']})"
        record["calculations"].append({"id": cid, "description": description,
            "expression": analysis["expression"], "input_fact_ids": input_ids,
            "result": analysis["result"], "units": analysis["units"], "rounding": "none; round at presentation",
            "period": analysis["period"], "currency": analysis["currency"],
            "price_basis": analysis["price_basis"], "market_data_batch_id": batch_id, "analysis_index": ai})
        record["facts"].append({"id": fid, "statement": f"{description}: {analysis['result']} {analysis['units']}",
            "status": "calculated", "material": True, "source_ids": list(dict.fromkeys(source_ids)),
            "evidence_ids": list(dict.fromkeys(evidence_ids)), "calculation_id": cid,
            "value": analysis["result"], "units": analysis["units"], "period": analysis["period"],
            "price_basis": analysis["price_basis"]})
        receipt["analysis_mappings"].append({"analysis": ai, "calculation_id": cid, "fact_id": fid})
    record.setdefault("market_data", {"schema_version": SCHEMA_VERSION, "batches": []})["batches"].append(receipt)
    return receipt


def collect(run_dir, request, fetcher=None):
    validate_request(request)
    run_dir = run_dir.resolve()
    record_path = local_path(run_dir, "research-record.json")
    if not record_path.is_file():
        raise ValueError("initialize a FinRunbook run before collecting market data")
    lock = local_path(run_dir, ".market-data.lock")
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise ValueError("another collector holds .market-data.lock; do not edit this run concurrently")
    os.close(descriptor)
    try:
        record = json.loads(record_path.read_text(encoding="utf-8"))
        for key in ("sources", "evidence", "facts", "calculations", "artifacts"):
            if not isinstance(record.get(key), list):
                raise ValueError(f"record requires a {key} list")
        as_of = record.get("request", {}).get("as_of_date")
        if as_of and date.fromisoformat(request["end"]) > date.fromisoformat(as_of[:10]) + timedelta(days=1):
            raise ValueError("request end exceeds the report as-of date")
        directory = local_path(run_dir, "artifacts/market-data")
        directory.mkdir(parents=True, exist_ok=True)
        cache = local_path(run_dir, "artifacts/market-data/.cache")
        cache.mkdir(exist_ok=True)
        snapshot = build_snapshot(request, fetcher or ADAPTERS[request["provider"]], cache)
        batch_id = "MD-" + uuid.uuid4().hex[:16]
        relative = f"artifacts/market-data/{batch_id}.json"
        path = local_path(run_dir, relative)
        atomic_json(path, snapshot)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        attach_snapshot(record, snapshot, relative, digest, batch_id)
        record["run"].update(updated_at=utc_now(), status="in_progress")
        record["validation"] = {"status": "NOT_RUN", "validated_at": None, "issues": [],
                                "reason": "Market data changed; regenerate and revalidate deliverables"}
        for artifact in record["artifacts"]:
            artifact["status"] = "draft"
        if record.get("editorial_review", {}).get("required"):
            record["editorial_review"].update(status="pending", completed_at=None)
        atomic_json(record_path, record)
        atomic_json(local_path(run_dir, "validation.json"), record["validation"])
        presentation_path = local_path(run_dir, "report/report-data.json")
        if presentation_path.is_file():
            presentation = json.loads(presentation_path.read_text(encoding="utf-8"))
            presentation["validation"] = record["validation"]
            atomic_json(presentation_path, presentation)
        errors = sum(i["severity"] == "error" for i in snapshot["quality_issues"])
        return {"batch_id": batch_id, "path": str(path), "status": "error" if errors else "ok",
                "errors": errors, "warnings": sum(i["severity"] == "warning" for i in snapshot["quality_issues"]),
                "series": len(snapshot["series"]), "calculations": len(snapshot["analyses"])}, int(errors > 0)
    finally:
        lock.unlink(missing_ok=True)


def validate_market_data(record, run_dir):
    """Fail closed on missing/tampered snapshots and mismatched ledger values."""
    if "market_data" not in record:
        if any(s.get("market_data_batch_id") for s in record.get("sources", []) if isinstance(s, dict)):
            return [{"severity": "error", "code": "market_data.missing_registry", "message": "Market-data sources require their batch registry", "path": "market_data"}]
        return []
    issues = []

    def add(severity, code, message, path="market_data"):
        issues.append({"severity": severity, "code": "market_data." + code, "message": message, "path": path})

    try:
        registry = record["market_data"]
        if registry["schema_version"] != SCHEMA_VERSION or not isinstance(registry["batches"], list) or not registry["batches"]:
            raise ValueError("invalid market data registry")
        sources = {s["id"]: s for s in record["sources"]}
        facts = {f["id"]: f for f in record["facts"]}
        evidence = {e["id"]: e for e in record["evidence"]}
        calculations = {c["id"]: c for c in record["calculations"]}
        batch_ids = set()
        for batch in registry["batches"]:
            location = batch["path"]
            try:
                if batch["id"] in batch_ids:
                    raise ValueError("duplicate batch ID")
                batch_ids.add(batch["id"])
                path = local_path(run_dir, location)
                content = path.read_bytes()
                digest = hashlib.sha256(content).hexdigest()
                if digest != batch["sha256"]:
                    raise ValueError("snapshot SHA-256 mismatch")
                snapshot = json.loads(content)
                if snapshot["schema_version"] != SCHEMA_VERSION:
                    raise ValueError("unsupported snapshot schema")
                validate_request(snapshot["request"])
                required = batch["required"]
                if not isinstance(required, bool):
                    raise ValueError("required must be boolean")
                if not required:
                    if not batch.get("exclusion_reason"):
                        raise ValueError("excluded batch requires an exclusion reason")
                    if any(f.get("material") and set(f.get("source_ids", [])) & set(batch["source_ids"]) for f in facts.values()):
                        raise ValueError("excluded batch still supports material facts")
                quality, expected = evaluate_snapshot(snapshot)
                if quality != snapshot["quality_issues"]:
                    raise ValueError("stored quality flags differ from recomputed flags")
                if expected != snapshot["analyses"]:
                    raise ValueError("stored analyses differ from recomputed snapshot values")
                # Recompute core flags instead of trusting a stored clean receipt.
                for item in quality:
                    add(item["severity"] if required else "warning", item["code"], item["message"], location)
                if len(batch["source_ids"]) != len(snapshot["series"]):
                    raise ValueError("source/series count mismatch")
                for si, sid in enumerate(batch["source_ids"]):
                    source = sources[sid]
                    if (source.get("sha256") != digest or source.get("local_path") != location
                            or source.get("market_data_batch_id") != batch["id"] or source.get("series_index") != si
                            or source.get("retrieved_at") != snapshot["retrieved_at"]
                            or source.get("publisher") != snapshot["series"][si]["provider"]
                            or source.get("url") != snapshot["series"][si].get("source_url")
                            or source.get("primary") is not False):
                        raise ValueError("source snapshot provenance mismatch")
                mapped_cells = {}
                for mapping in batch["input_mappings"]:
                    cell = mapping["cell"]
                    key = (cell["series"], cell["bar"], cell["field"])
                    if any(not isinstance(i, int) or isinstance(i, bool) or i < 0 for i in key[:2]) or key[2] not in {"close", "adj_close", "volume"}:
                        raise ValueError("invalid input cell")
                    if key in mapped_cells:
                        raise ValueError("duplicate input cell mapping")
                    fact, ev = facts[mapping["fact_id"]], evidence[mapping["evidence_id"]]
                    sid = batch["source_ids"][cell["series"]]
                    series = snapshot["series"][cell["series"]]
                    locator = f"{location}#/series/{cell['series']}/bars/{cell['bar']}/{cell['field']}"
                    if (fact.get("value") != cell_value(snapshot, cell) or fact.get("status") != "provider-reported"
                            or fact.get("source_ids") != [sid] or fact.get("evidence_ids") != [ev["id"]]
                            or ev.get("source_id") != sid or ev.get("locator") != locator
                            or fact.get("period") != series["bars"][cell["bar"]]["timestamp"]
                            or fact.get("units") != (volume_units(series) if cell["field"] == "volume" else series["currency"])
                            or fact.get("price_basis") != snapshot["request"]["price_basis"]
                            or fact.get("currency") != series["currency"]):
                        raise ValueError("input fact/evidence does not match snapshot cell")
                    mapped_cells[key] = mapping["fact_id"]
                seen_analyses = set()
                for mapping in batch["analysis_mappings"]:
                    ai = mapping["analysis"]
                    if not isinstance(ai, int) or isinstance(ai, bool) or ai < 0 or ai in seen_analyses:
                        raise ValueError("invalid/duplicate analysis mapping")
                    seen_analyses.add(ai)
                    analysis = expected[ai]
                    calculation, fact = calculations[mapping["calculation_id"]], facts[mapping["fact_id"]]
                    inputs = [mapped_cells[(c["series"], c["bar"], c["field"])] for c in analysis["inputs"]]
                    expected_sources = list(dict.fromkeys(s for fid in inputs for s in facts[fid]["source_ids"]))
                    expected_evidence = list(dict.fromkeys(e for fid in inputs for e in facts[fid]["evidence_ids"]))
                    if (calculation.get("input_fact_ids") != inputs or calculation.get("market_data_batch_id") != batch["id"]
                            or calculation.get("analysis_index") != ai or fact.get("calculation_id") != calculation["id"]
                            or fact.get("status") != "calculated" or fact.get("value") != analysis["result"]
                            or fact.get("source_ids") != expected_sources or fact.get("evidence_ids") != expected_evidence
                            or any(calculation.get(k) != analysis[k] for k in ("result", "expression", "units", "period", "price_basis", "currency"))
                            or any(fact.get(k) != analysis[k] for k in ("units", "period", "price_basis"))):
                        raise ValueError("calculation ledger differs from recomputed metric")
                if seen_analyses != set(range(len(expected))):
                    raise ValueError("missing analysis mappings")
            except (OSError, ValueError, KeyError, TypeError, IndexError, AttributeError) as error:
                add("error", "invalid_batch", str(error), location)
        if any(s.get("market_data_batch_id") and s["market_data_batch_id"] not in batch_ids for s in sources.values()):
            add("error", "missing_registry", "A market-data source references a missing batch")
    except (ValueError, KeyError, TypeError, AttributeError) as error:
        add("error", "invalid_registry", str(error))
    return issues


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_directory", type=Path)
    parser.add_argument("--symbols", nargs="+", required=True)
    parser.add_argument("--benchmark")
    parser.add_argument("--provider", choices=ADAPTERS, default="yahoo")
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True, help="Exclusive end date")
    parser.add_argument("--interval", choices=INTERVALS, default="1d")
    parser.add_argument("--price-basis", choices=PRICE_FIELDS, default="adj-close")
    parser.add_argument("--include-extended", action="store_true")
    parser.add_argument("--max-age-hours", type=float, default=168)
    args = parser.parse_args()
    request = {"provider": args.provider, "symbols": list(dict.fromkeys(s.upper() for s in args.symbols)),
               "benchmark": args.benchmark.upper() if args.benchmark else None, "start": args.start,
               "end": args.end, "interval": args.interval, "price_basis": args.price_basis,
               "include_extended": args.include_extended, "max_age_hours": args.max_age_hours}
    try:
        result, code = collect(args.run_directory, request)
    except (ValueError, OSError, KeyError, TypeError) as error:
        parser.error(str(error))
    print(json.dumps(result, ensure_ascii=False))
    return code


if __name__ == "__main__":
    sys.exit(main())
