"""Synthetic fixtures only: no Yahoo data or network required."""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/finrunbook-market-data/scripts/market_data.py"
VALIDATE = ROOT / "skills/finrunbook-validator/scripts/validate_run.py"
SPEC = importlib.util.spec_from_file_location("market_data", SCRIPT)
market = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(market)
NOW = "2026-09-03T14:00:00+00:00"


def request(**kwargs):
    return {"provider": "yahoo", "symbols": ["TEST"], "benchmark": None,
            "start": "2026-08-01", "end": "2026-09-01", "interval": "1d",
            "price_basis": "adj-close", "include_extended": False,
            "max_age_hours": 168, **kwargs}


def series(symbol="TEST", values=None, start="2026-08-01", currency="USD"):
    values = values if values is not None else [100 + i for i in range(31)]
    result = {"symbol": symbol, "provider": "Synthetic provider (unit test)",
              "client": "synthetic 1.0", "params": {}, "source_url": f"https://example.com/{symbol}",
              "exchange": "TEST", "currency": currency, "timezone": "America/New_York",
              "metadata": {"symbol": symbol, "instrumentType": "EQUITY"}, "status": "ok", "errors": [], "bars": []}
    for i, value in enumerate(values):
        day = date.fromisoformat(start) + timedelta(days=i)
        result["bars"].append({"timestamp": day.isoformat() + "T00:00:00-04:00",
                              "open": value, "high": value + 1, "low": value - 1,
                              "close": value, "adj_close": value, "volume": 100,
                              "dividends": 0, "splits": 0})
    result["bars"][-1]["volume"] = 300
    return result


def fake_fetcher(items):
    def fetch(symbol, req, cache):
        return copy.deepcopy(items[symbol])
    return fetch


def init_record(directory):
    record = {"schema_version": "1.0.0", "run": {"id": "synthetic-market-test",
              "created_at": NOW, "updated_at": NOW, "status": "in_progress"},
              "request": {"raw": "Synthetic integration test", "subject": "TEST",
                          "as_of_date": "2026-09-03", "report_archetype": "research-memo"},
              "plan": {"selected_skills": []}, "sources": [], "evidence": [], "facts": [],
              "calculations": [], "artifacts": [], "validation": {"status": "NOT_RUN"}}
    (directory / "research-record.json").write_text(json.dumps(record), encoding="utf-8")
    return record


class MarketDataTest(unittest.TestCase):
    def snapshot(self, items=None, req=None):
        with patch.object(market, "utc_now", return_value=NOW):
            return market.build_snapshot(req or request(), fake_fetcher(items or {"TEST": series()}), Path("unused"))

    def collect(self, root, req=None, items=None):
        with patch.object(market, "utc_now", return_value=NOW):
            result, code = market.collect(root, req or request(), fake_fetcher(items or {"TEST": series()}))
        record = json.loads((root / "research-record.json").read_text())
        return result, code, record

    def test_known_metrics(self):
        data = self.snapshot()
        metrics = {m["metric"]: m["result"] for m in data["analyses"]}
        self.assertAlmostEqual(metrics["return_pct"], 30)
        self.assertEqual(metrics["max_close_drawdown_pct"], 0)
        self.assertEqual(metrics["volume_vs_prior20"], 3)
        drawdown = self.snapshot({"TEST": series(values=[100, 120, 90, 110])})
        metrics = {m["metric"]: m["result"] for m in drawdown["analyses"]}
        self.assertAlmostEqual(metrics["return_pct"], 10)
        self.assertAlmostEqual(metrics["max_close_drawdown_pct"], -25)
        self.assertNotIn("volume_vs_prior20", metrics)

    def test_adjusted_basis_is_explicit_and_never_falls_back(self):
        raw = series(values=[100, 50, 55])
        for bar, adjusted in zip(raw["bars"], [50, 50, 55]):
            bar["adj_close"] = adjusted
        adjusted = self.snapshot({"TEST": raw})
        close = self.snapshot({"TEST": raw}, request(price_basis="close"))
        self.assertAlmostEqual(adjusted["analyses"][0]["result"], 10)
        self.assertAlmostEqual(close["analyses"][0]["result"], -45)
        raw["bars"][0]["adj_close"] = None
        missing = self.snapshot({"TEST": raw})
        self.assertEqual(missing["analyses"], [])
        self.assertIn("invalid_bars", {i["code"] for i in missing["quality_issues"]})

    def test_incomplete_daily_bar_is_retained_but_not_used(self):
        raw = series(start="2026-09-01", values=[100, 110, 5])
        data = self.snapshot({"TEST": raw}, request(start="2026-09-01", end="2026-09-04"))
        self.assertEqual(len(data["series"][0]["bars"]), 3)
        self.assertAlmostEqual(data["analyses"][0]["result"], 10)
        self.assertIn("incomplete_bars", {i["code"] for i in data["quality_issues"]})

    def test_incomplete_intraday_bar(self):
        raw = series(values=[100, 110, 5])
        for bar, stamp in zip(raw["bars"], ["2026-09-03T09:50:00-04:00", "2026-09-03T09:55:00-04:00", "2026-09-03T10:00:00-04:00"]):
            bar["timestamp"] = stamp
        data = self.snapshot({"TEST": raw}, request(start="2026-09-03", end="2026-09-04", interval="5m", price_basis="close"))
        self.assertAlmostEqual(data["analyses"][0]["result"], 10)
        self.assertTrue(all(m["metric"] != "volume_vs_prior20" for m in data["analyses"]))

    def test_benchmark_uses_common_observations_only(self):
        asset = series(values=[50, 100, 110, 120])
        benchmark = series("BENCH", values=[100, 105, 110], start="2026-08-02")
        data = self.snapshot({"TEST": asset, "BENCH": benchmark}, request(benchmark="BENCH"))
        excess = next(a for a in data["analyses"] if a["metric"] == "excess_return_pp")
        self.assertAlmostEqual(excess["result"], 10)
        self.assertIn("2026-08-02", excess["period"])
        self.assertEqual(excess["inputs"][0]["bar"], 1)
        benchmark["currency"] = "EUR"
        data = self.snapshot({"TEST": asset, "BENCH": benchmark}, request(benchmark="BENCH"))
        self.assertFalse(any(a["metric"] == "excess_return_pp" for a in data["analyses"]))
        self.assertIn("benchmark_unavailable", {i["code"] for i in data["quality_issues"]})

    def test_bad_bars_fail_closed(self):
        cases = [
            lambda s: s["bars"][0].update(adj_close=float("nan")),
            lambda s: s["bars"][0].update(volume=-1),
            lambda s: s["bars"][0].update(high=1),
            lambda s: s["bars"][0].update(timestamp="2026-07-01T00:00:00-04:00"),
            lambda s: s["bars"][0].update(timestamp=s["bars"][1]["timestamp"]),
            lambda s: s.update(currency=None),
            lambda s: s["metadata"].update(symbol="WRONG"),
        ]
        for mutate in cases:
            raw = series()
            mutate(raw)
            with self.subTest(mutate=mutate):
                data = self.snapshot({"TEST": raw})
                self.assertEqual(data["analyses"], [])
                self.assertTrue(any(i["severity"] == "error" for i in data["quality_issues"]))

    def test_empty_error_and_short_history_are_distinct(self):
        for status in ("error", "empty"):
            raw = series()
            raw.update(status=status, bars=[])
            self.assertTrue(any(i["severity"] == "error" for i in self.snapshot({"TEST": raw})["quality_issues"]))
        data = self.snapshot({"TEST": series(values=[100])})
        self.assertFalse(any(i["severity"] == "error" for i in data["quality_issues"]))
        self.assertEqual([m["metric"] for m in data["analyses"]], ["last_completed_price"])
        self.assertEqual(data["analyses"][0]["result"], 100)
        self.assertIn("insufficient_bars", {i["code"] for i in data["quality_issues"]})

    def test_contract_rejects_unsupported_inputs(self):
        for req in [request(start="2026-09-01"), request(interval="5m"), request(include_extended=True),
                    request(symbols=["../TEST"]), request(max_age_hours=float("nan"))]:
            with self.subTest(req=req), self.assertRaises(ValueError):
                market.validate_request(req)

    def test_yahoo_adapter_preserves_parameters_and_failure_without_network(self):
        calls = []
        config = SimpleNamespace(debug=SimpleNamespace(hide_exceptions=True))
        metadata = {"symbol": "TEST", "exchangeName": "TEST", "currency": "USD",
                    "exchangeTimezoneName": "America/New_York", "instrumentType": "EQUITY"}
        stamp = SimpleNamespace(isoformat=lambda: "2026-08-01T00:00:00-04:00")
        row = {"Open": 100, "High": 101, "Low": 99, "Close": 100, "Adj Close": 98,
               "Volume": 10, "Dividends": 0, "Stock Splits": 0}

        def history(**params):
            self.assertFalse(config.debug.hide_exceptions)
            calls.append(params)
            return SimpleNamespace(iterrows=lambda: iter([(stamp, row)]))

        ticker = SimpleNamespace(history=history, history_metadata=metadata)
        fake_yf = SimpleNamespace(config=config, __version__="synthetic", Ticker=lambda symbol: ticker,
                                  set_tz_cache_location=lambda path: None)
        with patch.dict(sys.modules, {"yfinance": fake_yf}):
            result = market.yahoo_history("TEST", request(), Path("unused"))
            self.assertEqual(result["status"], "ok")
            self.assertEqual(result["bars"][0]["adj_close"], 98)
            self.assertTrue(config.debug.hide_exceptions)
            self.assertEqual(calls[0]["end"], "2026-09-01")
            for flag in ("auto_adjust", "back_adjust", "repair", "rounding", "prepost"):
                self.assertFalse(calls[0][flag])
            self.assertTrue(calls[0]["actions"])
            self.assertTrue(calls[0]["keepna"])
            self.assertEqual(calls[0]["timeout"], 20)
            def fail(**params):
                raise RuntimeError("synthetic rate limit")
            ticker.history = fail
            result = market.yahoo_history("TEST", request(), Path("unused"))
            self.assertEqual(result["status"], "error")
            self.assertEqual(result["bars"], [])
            self.assertIn("synthetic rate limit", result["errors"][0])
            self.assertTrue(config.debug.hide_exceptions)

    def test_append_only_ledger_and_full_validator(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            init_record(root)
            first, code, record = self.collect(root)
            self.assertEqual(code, 0)
            self.assertFalse(market.validate_market_data(record, root))
            first_bytes = Path(first["path"]).read_bytes()
            old_ids = [f["id"] for f in record["facts"]]
            second, code, record = self.collect(root)
            self.assertEqual(code, 0)
            self.assertNotEqual(first["path"], second["path"])
            self.assertEqual(Path(first["path"]).read_bytes(), first_bytes)
            self.assertEqual([f["id"] for f in record["facts"]][:len(old_ids)], old_ids)
            self.assertEqual(len({f["id"] for f in record["facts"]}), len(record["facts"]))
            self.assertFalse(market.validate_market_data(record, root))
            process = subprocess.run([sys.executable, str(VALIDATE), str(root)], capture_output=True, text=True)
            self.assertEqual(process.returncode, 0, process.stderr + process.stdout)
            result = json.loads((root / "validation.json").read_text())
            self.assertEqual(result["status"], "PASS_WITH_WARNINGS")  # Secondary-source caveat.
            self.assertFalse(any(i["code"].startswith("market_data.") for i in result["issues"]))

    def test_failed_fetch_is_recorded_and_blocks_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            init_record(root)
            raw = series("FAIL")
            raw.update(status="error", bars=[], errors=["synthetic timeout"])
            result, code, record = self.collect(root, request(symbols=["TEST", "FAIL"]), {"TEST": series(), "FAIL": raw})
            self.assertEqual(code, 1)
            self.assertTrue(Path(result["path"]).is_file())
            self.assertEqual(len(record["sources"]), 2)
            self.assertTrue(any(i["severity"] == "error" for i in market.validate_market_data(record, root)))
            record["market_data"]["batches"][0]["required"] = False
            record["market_data"]["batches"][0]["exclusion_reason"] = "synthetic exclusion attempt"
            self.assertTrue(any(i["severity"] == "error" for i in market.validate_market_data(record, root)))

    def test_changed_values_receipts_and_paths_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            init_record(root)
            result, _, pristine = self.collect(root)
            for mutation in [
                lambda r: r["facts"][0].update(value=999),
                lambda r: r["calculations"][0].update(result=999),
                lambda r: r["sources"][0].update(sha256="wrong"),
                lambda r: r["sources"][0].update(primary=True),
                lambda r: r["evidence"][0].update(locator="wrong"),
                lambda r: r["market_data"]["batches"][0].update(path="../outside.json"),
                lambda r: r["market_data"]["batches"][0].update(analysis_mappings=[]),
                lambda r: r.pop("market_data"),
            ]:
                record = copy.deepcopy(pristine)
                mutation(record)
                self.assertTrue(any(i["severity"] == "error" for i in market.validate_market_data(record, root)))
            path = Path(result["path"])
            snapshot = json.loads(path.read_text())
            snapshot["analyses"][0]["result"] = 999
            path.write_text(json.dumps(snapshot))
            self.assertTrue(any(i["severity"] == "error" for i in market.validate_market_data(pristine, root)))
            pristine["market_data"]["batches"][0]["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
            # Updating the hash cannot conceal an incorrectly calculated result.
            self.assertTrue(any("recomputed" in i["message"] for i in market.validate_market_data(pristine, root)))

    def test_new_data_invalidates_old_receipts_and_keeps_language(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            record = init_record(root)
            record["request"]["language"] = "zh-CN"
            record["editorial_review"] = {"required": True, "status": "completed", "completed_at": NOW}
            record["artifacts"] = [{"path": "report/report-data.json", "format": "json", "status": "validated"}]
            (root / "research-record.json").write_text(json.dumps(record))
            (root / "report").mkdir()
            (root / "report/report-data.json").write_text(json.dumps({"validation": {"status": "PASS"}}))
            _, _, record = self.collect(root)
            self.assertEqual(record["request"]["language"], "zh-CN")
            self.assertEqual(record["validation"]["status"], "NOT_RUN")
            self.assertEqual(record["editorial_review"]["status"], "pending")
            self.assertEqual(record["artifacts"][0]["status"], "draft")
            self.assertEqual(json.loads((root / "report/report-data.json").read_text())["validation"]["status"], "NOT_RUN")

    def test_asof_guard_and_lock_do_not_change_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            init_record(root)
            original = (root / "research-record.json").read_bytes()
            with self.assertRaises(ValueError):
                self.collect(root, request(end="2026-09-05"))
            self.assertEqual((root / "research-record.json").read_bytes(), original)
            lock = root / ".market-data.lock"
            lock.touch()
            with self.assertRaises(ValueError):
                self.collect(root)
            self.assertTrue(lock.exists())


if __name__ == "__main__":
    unittest.main()
