#!/usr/bin/env python3
"""Initialize a FinRunbook run directory using only the Python standard library."""

from __future__ import annotations

import argparse
import html
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


def resolve_report_language(
    request: str, output_language: str | None, request_language: str | None,
) -> tuple[str, str]:
    """Prefer the router's semantic language choice; keep CLI fallback bounded.

    The agent parses explicit output-language instructions into --language and
    the current request's main language into --request-language. This helper is
    not a general natural-language preference parser or multilingual detector.
    Without either flag, recognize predominantly Chinese prose, allowing Latin
    tickers/financial terms, and otherwise use the English fallback.
    """
    if output_language:
        return output_language, "explicit-output-language"
    if request_language:
        return request_language, "request-language"

    # Source URLs and code are not evidence of the user's writing language.
    prose = re.sub(r"```[\s\S]*?```|https?://\S+", " ", request)
    han = sum("\u3400" <= char <= "\u4dbf" or "\u4e00" <= char <= "\u9fff" for char in prose)
    latin_words = len(re.findall(r"[A-Za-z]+(?:['-][A-Za-z]+)*", prose))
    other_east_asian = any("\u3040" <= char <= "\u30ff" or "\uac00" <= char <= "\ud7af" for char in prose)
    if han >= 2 and han >= latin_words and not other_east_asian:
        return "zh-CN", "request-script-heuristic"
    return "en", "english-fallback"


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Create a structured FinRunbook research run")
    result.add_argument("--subject", required=True, help="Company, sector, asset, or question subject")
    result.add_argument("--request", required=True, help="User's raw research request")
    result.add_argument("--task-type", default="unspecified")
    result.add_argument(
        "--report-archetype",
        choices=["finance-report", "research-memo", "datasheet"],
        default="finance-report",
    )
    result.add_argument("--decision-use", default="investment research")
    result.add_argument("--as-of-date")
    result.add_argument("--start-date")
    result.add_argument("--end-date")
    result.add_argument("--audience", default="finance professional")
    result.add_argument("--language", help="Explicit output language requested by the user; overrides --request-language")
    result.add_argument("--request-language", help="Main language of the current request, resolved by the router (e.g. zh-CN, en, es). Without either flag, use a Chinese-prose heuristic, otherwise English.")
    result.add_argument("--format", action="append", dest="formats")
    result.add_argument("--depth", choices=["brief", "standard", "deep"], default="standard")
    result.add_argument("--assumption", action="append", default=[])
    result.add_argument("--source-constraint", action="append", default=[])
    result.add_argument("--runs-dir", type=Path, help="Override the working directory's run/ directory")
    result.add_argument("--run-id", help="Override the generated run ID")
    result.add_argument("--compact", action="store_true", help="Finrun 0.5: one inline review, reproducible arithmetic, no separate editorial receipt")
    return result


def main() -> int:
    args = parser().parse_args()
    script_path = Path(__file__).resolve()
    repo_root = script_path.parents[3]
    runs_dir = args.runs_dir.resolve() if args.runs_dir else Path.cwd() / "run"
    if (repo_root / '.codex-plugin/plugin.json').exists() and runs_dir.resolve().is_relative_to(repo_root):
        raise SystemExit('choose a workspace outside the installed plugin')
    now = utc_now()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    run_id = args.run_id or f"{stamp}-{slugify(args.subject)}"
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9._-]{2,119}", run_id):
        raise SystemExit("--run-id must be 3-120 safe filename characters")

    formats = list(dict.fromkeys(args.formats or (
        ["interactive-html", "json"]
        if args.report_archetype == "finance-report"
        else (["csv", "json"] if args.report_archetype == "datasheet" else ["markdown"])
    )))
    if args.report_archetype == "finance-report" and "markdown" in formats:
        raise SystemExit("finance-report cannot use Markdown as a final output; use interactive-html, PDF, PPTX, or select research-memo")
    if "interactive-html" in formats and "json" not in formats:
        formats.append("json")

    artifact_paths = {
        "interactive-html": "report/index.html",
        "json": "report/report-data.json",
        "markdown": "report.md",
        "pdf": "report/report.pdf",
        "xlsx": "report/model.xlsx",
        "pptx": "report/report.pptx",
        "csv": "report/datasheet.csv",
    }
    unknown_formats = [item for item in formats if item not in artifact_paths]
    if unknown_formats:
        raise SystemExit(f"unsupported output format(s): {', '.join(unknown_formats)}")
    language, language_source = resolve_report_language(args.request, args.language, args.request_language)
    artifacts = [
        {
            "path": artifact_paths[item],
            "format": item,
            "language": language,
            "status": "draft",
            "fact_ids": [],
        }
        for item in formats
    ]

    run_dir = runs_dir / run_id
    try:
        run_dir.mkdir(parents=True, exist_ok=False)
    except FileExistsError:
        raise SystemExit(f"run already exists: {run_dir}")
    (run_dir / "artifacts").mkdir()

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
            "report_archetype": args.report_archetype,
            "decision_use": args.decision_use,
            "as_of_date": args.as_of_date,
            "start_date": args.start_date,
            "end_date": args.end_date,
            "audience": args.audience,
            "language": language,
            "language_resolution": {
                "source": language_source,
                "request_language": args.request_language,
                "fallback": "en",
            },
            "output_formats": formats,
            "depth": args.depth,
            "source_constraints": source_constraints,
            "clarifications": [],
            "assumptions": args.assumption,
        },
        "plan": {
            "selected_skills": [],
            "steps": [],
            "output_contract": {
                "coverage_universe_rule": None,
                "comparison_periods": [],
                "common_metrics": [],
                "sector_kpis": [],
                "required_bridge_or_ranking": None,
                "valuation_required": None,
                "planned_artifacts": [item["path"] for item in artifacts],
            },
            "status": "draft",
        },
        "sources": [],
        "evidence": [],
        "facts": [],
        "calculations": [],
        "artifacts": artifacts,
        "editorial_review": {
            "required": True,
            "status": "pending",
            "completed_at": None,
            "reviewer": None,
            "languages": [],
            "upstream_skills": [],
            "reviewed_artifacts": [],
            "change_log_path": "editorial-review.json",
            "protected_items_preserved": None,
            "unresolved_issues": [],
        },
        "validation": {
            "status": "NOT_RUN",
            "validated_at": None,
            "validator_version": None,
            "issues": [],
        },
    }

    if args.compact:
        record['workflow'] = 'finrun-0.5'
        record.pop('editorial_review')
        record['review'] = {'status': 'pending', 'reviewer': None, 'notes': []}
    record_path = run_dir / "research-record.json"
    record_path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if "markdown" in formats:
        report = (
            f"# {args.subject}\n\n"
            "> Status: draft — evidence collection and validation are not complete.\n\n"
            f"**Research question:** {args.request}\n\n"
            f"**Report archetype:** {args.report_archetype}\n\n"
            f"**Decision use:** {args.decision_use}\n\n"
            "<!-- finrunbook:validation:start -->\n"
            "> Validation: NOT RUN\n"
            "<!-- finrunbook:validation:end -->\n\n"
            "<!-- finrunbook:sources:start -->\n"
            "## Sources\n\n"
            "No sources recorded yet.\n"
            "<!-- finrunbook:sources:end -->\n"
        )
        (run_dir / "report.md").write_text(report, encoding="utf-8")

    if "json" in formats:
        report_dir = run_dir / "report"
        report_dir.mkdir(exist_ok=True)
        presentation = {
            "schema_version": "1.0.0",
            "meta": {
                "run_id": run_id,
                "title": args.subject,
                "decision_use": args.decision_use,
                "as_of_date": args.as_of_date,
                "language": language,
                "coverage_universe": None,
                "status": "draft",
                "available_periods": [],
            },
            "executive_view": {
                "headline": None,
                "summary": None,
                "decisive_metrics": [],
                "implications": [],
                "view_change_conditions": [],
            },
            "sections": [],
            "methodology": [],
            "sources": [],
            "validation": {"status": "NOT_RUN", "validated_at": None, "warnings": []},
        }
        (report_dir / "report-data.json").write_text(
            json.dumps(presentation, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    if "interactive-html" in formats:
        report_dir = run_dir / "report"
        report_dir.mkdir(exist_ok=True)
        title = html.escape(args.subject)
        page = f"""<!doctype html>
<html lang="{html.escape(language)}">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title></head>
<body><main id="finrunbook-report"><h1>{title}</h1><p>Draft report. The presentation renderer has not completed this run.</p></main>
<script>fetch('./report-data.json').then(r=>r.json()).then(d=>{{document.title=d.meta.title||document.title;}});</script>
</body></html>
"""
        (report_dir / "index.html").write_text(page, encoding="utf-8")
    print(run_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
