#!/usr/bin/env python3
"""Initialize a FinRunbook run directory using only the Python standard library."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = "1.0.0"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", normalized).strip("-").lower()
    return (slug or "research")[:60]


def repository_revision(repo_root: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    revision = result.stdout.strip()
    return revision if revision and revision != "HEAD" else None


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Create a structured FinRunbook research run")
    result.add_argument("--subject", required=True, help="Company, sector, asset, or question subject")
    result.add_argument("--request", required=True, help="User's raw research request")
    result.add_argument("--task-type", default="unspecified")
    result.add_argument("--as-of-date")
    result.add_argument("--start-date")
    result.add_argument("--end-date")
    result.add_argument("--audience", default="informed generalist")
    result.add_argument("--language", default="en")
    result.add_argument("--format", action="append", dest="formats")
    result.add_argument("--depth", choices=["brief", "standard", "deep"], default="standard")
    result.add_argument("--assumption", action="append", default=[])
    result.add_argument("--source-constraint", action="append", default=[])
    result.add_argument("--runs-dir", type=Path, help="Override the repository's runs directory")
    result.add_argument("--run-id", help="Override the generated run ID")
    return result


def main() -> int:
    args = parser().parse_args()
    script_path = Path(__file__).resolve()
    repo_root = script_path.parents[3]
    runs_dir = args.runs_dir.resolve() if args.runs_dir else repo_root / "runs"
    now = utc_now()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    run_id = args.run_id or f"{stamp}-{slugify(args.subject)}"
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9._-]{2,119}", run_id):
        raise SystemExit("--run-id must be 3-120 safe filename characters")

    run_dir = runs_dir / run_id
    try:
        run_dir.mkdir(parents=True, exist_ok=False)
    except FileExistsError:
        raise SystemExit(f"run already exists: {run_dir}")
    (run_dir / "artifacts").mkdir()

    formats = args.formats or ["markdown"]
    source_constraints = args.source_constraint or ["primary sources first"]
    record = {
        "schema_version": SCHEMA_VERSION,
        "run": {
            "id": run_id,
            "created_at": now,
            "updated_at": now,
            "status": "in_progress",
            "repository_revision": repository_revision(repo_root),
        },
        "request": {
            "raw": args.request,
            "subject": args.subject,
            "task_type": args.task_type,
            "as_of_date": args.as_of_date,
            "start_date": args.start_date,
            "end_date": args.end_date,
            "audience": args.audience,
            "language": args.language,
            "output_formats": formats,
            "depth": args.depth,
            "source_constraints": source_constraints,
            "clarifications": [],
            "assumptions": args.assumption,
        },
        "plan": {"selected_skills": [], "steps": [], "status": "draft"},
        "sources": [],
        "evidence": [],
        "facts": [],
        "calculations": [],
        "artifacts": [
            {
                "path": "report.md",
                "format": "markdown",
                "language": args.language,
                "status": "draft",
                "fact_ids": [],
            }
        ],
        "validation": {
            "status": "NOT_RUN",
            "validated_at": None,
            "validator_version": None,
            "issues": [],
        },
    }

    record_path = run_dir / "research-record.json"
    record_path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report = (
        f"# {args.subject}\n\n"
        "> Status: draft — evidence collection and validation are not complete.\n\n"
        f"**Research question:** {args.request}\n\n"
        "<!-- finrunbook:validation:start -->\n"
        "> Validation: NOT RUN\n"
        "<!-- finrunbook:validation:end -->\n\n"
        "<!-- finrunbook:sources:start -->\n"
        "## Sources\n\n"
        "No sources recorded yet.\n"
        "<!-- finrunbook:sources:end -->\n"
    )
    (run_dir / "report.md").write_text(report, encoding="utf-8")
    print(run_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())

