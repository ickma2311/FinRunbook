#!/usr/bin/env python3
"""Initialize or reopen a daily research controller; no network or model calls."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


SUPPORTED_SCHEMAS = ("1.0.0", "1.1.0")
DISCOVERY_SOURCES = ("hacker-news", "gdelt", "google-trends-rss", "reddit", "youtube", "x")


def utc_text(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_time(value: str) -> datetime:
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError("--as-of needs a timezone offset or Z")
    return result.astimezone(timezone.utc).replace(microsecond=0)


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--request", help="Raw user instruction; required for a new batch")
    p.add_argument("--language", help="Resolved output language, e.g. en or zh-CN; required for a new batch")
    p.add_argument("--timezone", help="IANA timezone, e.g. America/Los_Angeles; defaults to UTC")
    p.add_argument("--as-of", help="Fixed scan cutoff as an ISO timestamp with timezone; defaults to now")
    p.add_argument("--lookback-hours", type=int, help="Discovery window, 1–168 hours; defaults to 24")
    p.add_argument("--max-reports", type=int, choices=(3, 4, 5), help="Report cap; defaults to 5")
    p.add_argument("--mode", choices=("research", "scan-only"), help="Defaults to research")
    p.add_argument("--sources", nargs="+", choices=DISCOVERY_SOURCES,
                   help="Explicit discovery set; defaults to hacker-news gdelt google-trends-rss. Records scope only, not access permission")
    p.add_argument("--batch-id", help="Safe directory ID; defaults to YYYYMMDD-radar in the chosen timezone")
    p.add_argument("--resume", action="store_true", help="Reopen an explicit existing batch without changing it")
    p.add_argument("--runs-dir", type=Path, help="Override the working directory's run/ directory")
    return p


def revision(root: Path) -> str | None:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=root,
                              capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def initialize(args: argparse.Namespace) -> Path:
    root = Path(__file__).resolve().parents[3]
    runs = (args.runs_dir or Path.cwd() / "run").resolve()
    if args.resume and not args.batch_id:
        raise ValueError("--resume requires the existing --batch-id")
    if args.language is not None and not re.fullmatch(r"[A-Za-z]{2,8}(?:-[A-Za-z0-9]{1,8})*", args.language):
        raise ValueError("--language must be a language tag such as en or zh-CN")
    if args.lookback_hours is not None and not 1 <= args.lookback_hours <= 168:
        raise ValueError("--lookback-hours must be between 1 and 168")
    if args.timezone:
        ZoneInfo(args.timezone)
    cutoff = parse_time(args.as_of) if args.as_of else datetime.now(timezone.utc).replace(microsecond=0)
    zone_name = args.timezone or "UTC"
    local_date = cutoff.astimezone(ZoneInfo(zone_name)).date()
    batch_id = args.batch_id or f"{local_date:%Y%m%d}-radar"
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{2,119}", batch_id):
        raise ValueError("--batch-id must be 3–120 safe filename characters")
    directory = runs / batch_id
    manifest = directory / "radar.json"
    if directory.is_symlink() or manifest.is_symlink():
        raise ValueError("batch directories and manifests must not be symlinks")

    if args.resume:
        if not manifest.is_file():
            raise ValueError("batch does not exist; resume never creates a replacement")
        data = json.loads(manifest.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or not isinstance(data.get("batch"), dict) or not isinstance(data.get("request"), dict):
            raise ValueError("invalid radar manifest structure")
        if data.get("kind") != "finrunbook-radar-batch" or data.get("schema_version") not in SUPPORTED_SCHEMAS:
            raise ValueError("not a supported radar batch")
        if data.get("batch", {}).get("id") != batch_id:
            raise ValueError("manifest ID does not match its directory")
        settings = {"raw": args.request, "language": args.language, "mode": args.mode,
                    "max_reports": args.max_reports, "lookback_hours": args.lookback_hours,
                    "requested_platforms": list(dict.fromkeys(args.sources)) if args.sources else None}
        for key, value in settings.items():
            if value is not None and data.get("request", {}).get(key) != value:
                raise ValueError(f"resume would change {key}; preserve the recorded scope")
        if args.timezone and data["batch"].get("timezone") != args.timezone:
            raise ValueError("resume would change timezone")
        if args.as_of and data["batch"].get("window_end") != utc_text(cutoff):
            raise ValueError("resume would change the fixed scan cutoff")
        return directory

    if not args.request or not args.request.strip() or not args.language:
        raise ValueError("new batches require --request and the resolved --language")
    data = json.loads((Path(__file__).resolve().parents[1] / "assets/radar.template.json").read_text(encoding="utf-8"))
    now = utc_text(datetime.now(timezone.utc))
    lookback = args.lookback_hours if args.lookback_hours is not None else 24
    data["batch"].update({
        "id": batch_id, "local_date": local_date.isoformat(), "timezone": zone_name,
        "started_at": now, "updated_at": now,
        "window_start": utc_text(cutoff - timedelta(hours=lookback)),
        "window_end": utc_text(cutoff), "repository_revision": revision(root),
    })
    data["request"].update({
        "raw": args.request, "language": args.language, "mode": args.mode or "research",
        "lookback_hours": lookback, "max_reports": args.max_reports or 5,
    })
    if args.sources:
        data["request"]["requested_platforms"] = list(dict.fromkeys(args.sources))
        data["request"]["disabled_platforms"] = [
            source for source in data["request"]["disabled_platforms"] if source not in args.sources
        ]
    # An existing directory is a resumption decision, never an overwrite target.
    directory.mkdir(parents=True, exist_ok=False)
    with manifest.open("x", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    return directory


def main() -> int:
    p = parser()
    args = p.parse_args()
    try:
        result = initialize(args)
    except (OSError, ValueError, ZoneInfoNotFoundError) as exc:
        p.exit(2, f"error: {exc}\n")
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
