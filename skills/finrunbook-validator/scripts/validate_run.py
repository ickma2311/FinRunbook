#!/usr/bin/env python3
"""Validate and annotate a FinRunbook run using the Python standard library."""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


VALIDATOR_VERSION = "0.4.0"
REQUIRED_TOP_LEVEL = (
    "schema_version",
    "run",
    "request",
    "plan",
    "sources",
    "evidence",
    "facts",
    "calculations",
    "artifacts",
    "validation",
)
ID_PATTERNS = {
    "source": re.compile(r"^SRC-\d{3,}$"),
    "evidence": re.compile(r"^EVD-\d{3,}$"),
    "fact": re.compile(r"^FACT-\d{3,}$"),
    "calculation": re.compile(r"^CALC-\d{3,}$"),
}
FACT_STATUSES = {
    "company-reported",
    "provider-reported",
    "verified",
    "calculated",
    "inferred",
    "conflicting",
    "insufficient-evidence",
}
ARTIFACT_STATUSES = {"draft", "validated", "blocked"}
MANAGED_VALIDATION = re.compile(
    r"<!-- finrunbook:validation:start -->.*?<!-- finrunbook:validation:end -->",
    re.DOTALL,
)
MANAGED_SOURCES = re.compile(
    r"<!-- finrunbook:sources:start -->.*?<!-- finrunbook:sources:end -->",
    re.DOTALL,
)
CITATION = re.compile(r"\[\^(SRC-\d{3,})\]")
PLACEHOLDER = re.compile(r"\[(?:SOURCE NEEDED|CITATION NEEDED)\]|\b(?:TODO|TBD)\b", re.IGNORECASE)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def issue(severity: str, code: str, message: str, path: str) -> dict[str, str]:
    return {"severity": severity, "code": code, "message": message, "path": path}


def nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def valid_timestamp(value: Any) -> bool:
    if not nonempty_string(value):
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def collect_reference_ids(value: Any, singular: str, plural: str) -> set[str]:
    """Collect explicit provenance IDs from nested presentation data."""
    collected: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            if key == singular and isinstance(child, str):
                collected.add(child)
            elif key == plural and isinstance(child, list):
                collected.update(item for item in child if isinstance(item, str))
            collected.update(collect_reference_ids(child, singular, plural))
    elif isinstance(value, list):
        for child in value:
            collected.update(collect_reference_ids(child, singular, plural))
    return collected


def safe_artifact_path(run_dir: Path, relative: Any) -> Path | None:
    if not nonempty_string(relative):
        return None
    candidate = (run_dir / relative).resolve()
    try:
        candidate.relative_to(run_dir.resolve())
    except ValueError:
        return None
    return candidate


def check_editorial_review(record: dict[str, Any], run_dir: Path) -> list[dict[str, str]]:
    """Check the review receipt, not the quality or semantic equivalence of prose."""
    if "editorial_review" not in record:
        return []  # Older run records did not declare this gate.
    review = record["editorial_review"]
    if not isinstance(review, dict) or not isinstance(review.get("required"), bool):
        return [issue("error", "editorial.invalid_review", "editorial_review requires a boolean required field", "editorial_review")]
    if not review["required"]:
        return []
    if review.get("status") != "completed":
        return [issue("error", "editorial.incomplete_review", "required editorial review is not completed", "editorial_review.status")]

    issues: list[dict[str, str]] = []
    for field, valid in (
        ("completed_at", valid_timestamp(review.get("completed_at"))),
        ("reviewer", nonempty_string(review.get("reviewer"))),
        ("protected_items_preserved", review.get("protected_items_preserved") is True),
        ("unresolved_issues", review.get("unresolved_issues") == []),
    ):
        if not valid:
            issues.append(issue("error", "editorial.incomplete_review", f"editorial review has invalid or unresolved {field}", f"editorial_review.{field}"))

    lists: dict[str, list[str]] = {}
    for field in ("languages", "reviewed_artifacts"):
        value = review.get(field)
        if not isinstance(value, list) or not value or not all(nonempty_string(item) for item in value):
            issues.append(issue("error", "editorial.incomplete_review", f"review requires a nonempty {field} list of strings", f"editorial_review.{field}"))
            lists[field] = []
        else:
            lists[field] = value

    for relative in lists["reviewed_artifacts"]:
        path = safe_artifact_path(run_dir, relative)
        if Path(relative).is_absolute() or path is None or not path.is_file():
            issues.append(issue("error", "editorial.invalid_artifact", "reviewed artifact must be an existing run-relative file", "editorial_review.reviewed_artifacts"))
    for artifact in record.get("artifacts", []) if isinstance(record.get("artifacts"), list) else []:
        if not isinstance(artifact, dict):
            continue
        if artifact.get("path") not in lists["reviewed_artifacts"]:
            issues.append(issue("error", "editorial.unreviewed_artifact", "artifact is not covered by the editorial receipt", "editorial_review.reviewed_artifacts"))
        if artifact.get("language") and artifact["language"] not in lists["languages"]:
            issues.append(issue("error", "editorial.unreviewed_language", "artifact language is not covered by the editorial receipt", "editorial_review.languages"))

    upstream = review.get("upstream_skills")
    if not isinstance(upstream, list):
        issues.append(issue("error", "editorial.invalid_upstream", "upstream_skills must be a list of editors actually used", "editorial_review.upstream_skills"))
        upstream = []
    covered: set[tuple[str, str]] = set()
    for editor in upstream:
        valid = (
            isinstance(editor, dict)
            and all(nonempty_string(editor.get(field)) for field in ("name", "path", "commit"))
            and re.fullmatch(r"[0-9a-fA-F]{40}", editor["commit"])
            and isinstance(editor.get("languages"), list)
            and bool(editor["languages"])
            and all(nonempty_string(language) for language in editor["languages"])
        )
        if not valid:
            issues.append(issue("error", "editorial.invalid_upstream", "editor requires name, path, full commit SHA, and applied languages", "editorial_review.upstream_skills"))
            continue
        covered.update((editor["name"], language) for language in editor["languages"])
    for language in lists["languages"]:
        base_language = language.replace("_", "-").lower().split("-")[0]
        expected = {"en": "writing-clearly-and-concisely", "zh": "readable-human-writing"}.get(base_language)
        if expected and (expected, language) not in covered:
            issues.append(issue("error", "editorial.missing_language_editor", f"{language} review requires a recorded {expected} pass", "editorial_review.upstream_skills"))

    relative = review.get("change_log_path")
    log_path = safe_artifact_path(run_dir, relative)
    if not nonempty_string(relative) or Path(relative).is_absolute() or log_path is None or not log_path.is_file():
        issues.append(issue("error", "editorial.missing_change_log", "review requires an existing run-relative JSON change log", "editorial_review.change_log_path"))
    else:
        try:
            log = json.loads(log_path.read_text(encoding="utf-8"))
            changes = log.get("changes") if isinstance(log, dict) else None
            valid = isinstance(changes, list) and log.get("result") == ("edited" if changes else "no-change")
            if valid:
                valid = all(
                    isinstance(change, dict)
                    and all(nonempty_string(change.get(field)) for field in ("field", "reason"))
                    and all(isinstance(change.get(field), str) for field in ("before", "after"))
                    for change in changes
                )
            if not valid:
                raise ValueError("change log requires result and a matching changes array with field, before, after, and reason")
        except (OSError, ValueError) as error:
            issues.append(issue("error", "editorial.invalid_change_log", str(error), "editorial_review.change_log_path"))
    return issues


def atomic_json(path: Path, value: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def check_market_data(record: dict[str, Any], run_dir: Path) -> list[dict[str, str]]:
    source_items = record.get("sources")
    has_receipts = "market_data" in record or any(
        isinstance(source, dict) and source.get("market_data_batch_id")
        for source in (source_items if isinstance(source_items, list) else [])
    )
    if not has_receipts:
        return []
    helper = Path(__file__).resolve().parents[2] / "finrunbook-market-data/scripts/market_data.py"
    try:
        spec = importlib.util.spec_from_file_location("finrunbook_market_data_checks", helper)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.validate_market_data(record, run_dir)
    except (OSError, ImportError, AttributeError, TypeError, ValueError) as error:
        return [issue("error", "market_data.check_unavailable", str(error), "market_data")]


def atomic_text(path: Path, value: str) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(value, encoding="utf-8")
    temporary.replace(path)


def index_records(
    records: Any,
    kind: str,
    collection_path: str,
    issues: list[dict[str, str]],
) -> dict[str, dict[str, Any]]:
    if not isinstance(records, list):
        issues.append(issue("error", "schema.not_list", "must be a list", collection_path))
        return {}
    result: dict[str, dict[str, Any]] = {}
    for position, record in enumerate(records):
        item_path = f"{collection_path}[{position}]"
        if not isinstance(record, dict):
            issues.append(issue("error", "schema.not_object", "must be an object", item_path))
            continue
        record_id = record.get("id")
        if not nonempty_string(record_id) or not ID_PATTERNS[kind].fullmatch(record_id):
            issues.append(issue("error", f"{kind}.invalid_id", f"invalid {kind} ID", f"{item_path}.id"))
            continue
        if record_id in result:
            issues.append(issue("error", f"{kind}.duplicate_id", f"duplicate ID {record_id}", f"{item_path}.id"))
            continue
        result[record_id] = record
    return result


def replace_managed_block(text: str, pattern: re.Pattern[str], block: str) -> str:
    if pattern.search(text):
        return pattern.sub(block, text, count=1)
    return text.rstrip() + "\n\n" + block + "\n"


def clean_markdown_text(value: Any) -> str:
    text = str(value or "Untitled source")
    return text.replace("[", "\\[").replace("]", "\\]").replace("\n", " ").strip()


def render_sources(sources: list[dict[str, Any]]) -> str:
    lines = ["<!-- finrunbook:sources:start -->", "## Sources", ""]
    if not sources:
        lines.append("No sources recorded.")
    for source in sorted(sources, key=lambda item: str(item.get("id", ""))):
        source_id = source.get("id", "SRC-UNKNOWN")
        title = clean_markdown_text(source.get("title"))
        url = source.get("url")
        if nonempty_string(url):
            label = f"[{title}]({url})"
        else:
            label = f"{title} (`{source.get('local_path', 'location unavailable')}`)"
        details = [clean_markdown_text(source.get("publisher") or "Unknown publisher")]
        if nonempty_string(source.get("filing_type")):
            details.append(str(source["filing_type"]))
        if nonempty_string(source.get("published_at")):
            details.append(f"published {source['published_at']}")
        if nonempty_string(source.get("period_end")):
            details.append(f"period ended {source['period_end']}")
        details.append(f"retrieved {source.get('retrieved_at', 'unknown')}")
        lines.append(f"[^{source_id}]: {label} — {'; '.join(details)}.")
    lines.append("<!-- finrunbook:sources:end -->")
    return "\n".join(lines)


def render_validation(status: str, checked_at: str, errors: int, warnings: int) -> str:
    return "\n".join(
        [
            "<!-- finrunbook:validation:start -->",
            f"> Validation: **{status}** — {errors} error(s), {warnings} warning(s); checked {checked_at}.",
            "<!-- finrunbook:validation:end -->",
        ]
    )


def validate(run_dir: Path) -> tuple[dict[str, Any], int]:
    record_path = run_dir / "research-record.json"
    if not record_path.is_file():
        result = {
            "validator_version": VALIDATOR_VERSION,
            "status": "FAIL",
            "validated_at": utc_now(),
            "summary": {"errors": 1, "warnings": 0},
            "issues": [issue("error", "record.missing", "research-record.json is missing", "research-record.json")],
        }
        atomic_json(run_dir / "validation.json", result)
        return result, 1

    issues: list[dict[str, str]] = []
    try:
        record = json.loads(record_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as error:
        result = {
            "validator_version": VALIDATOR_VERSION,
            "status": "FAIL",
            "validated_at": utc_now(),
            "summary": {"errors": 1, "warnings": 0},
            "issues": [issue("error", "record.invalid_json", str(error), "research-record.json")],
        }
        atomic_json(run_dir / "validation.json", result)
        return result, 1

    if not isinstance(record, dict):
        result = {
            "validator_version": VALIDATOR_VERSION,
            "status": "FAIL",
            "validated_at": utc_now(),
            "summary": {"errors": 1, "warnings": 0},
            "issues": [issue("error", "record.not_object", "root must be an object", "research-record.json")],
        }
        atomic_json(run_dir / "validation.json", result)
        return result, 1

    for field in REQUIRED_TOP_LEVEL:
        if field not in record:
            issues.append(issue("error", "schema.missing_field", f"missing top-level field {field}", field))
    if record.get("schema_version") != "1.0.0":
        issues.append(issue("error", "schema.unsupported_version", "expected schema_version 1.0.0", "schema_version"))

    run = record.get("run") if isinstance(record.get("run"), dict) else {}
    request = record.get("request") if isinstance(record.get("request"), dict) else {}
    plan = record.get("plan") if isinstance(record.get("plan"), dict) else {}
    if not nonempty_string(run.get("id")):
        issues.append(issue("error", "run.missing_id", "run ID is required", "run.id"))
    for field in ("created_at", "updated_at"):
        if not valid_timestamp(run.get(field)):
            issues.append(issue("error", "run.invalid_timestamp", f"invalid {field}", f"run.{field}"))
    if not nonempty_string(request.get("raw")):
        issues.append(issue("error", "request.missing_raw", "raw user request is required", "request.raw"))
    if not nonempty_string(request.get("subject")):
        issues.append(issue("error", "request.missing_subject", "research subject is required", "request.subject"))

    report_archetype = request.get("report_archetype")
    if report_archetype is not None and report_archetype not in {"finance-report", "research-memo"}:
        issues.append(issue("error", "request.invalid_report_archetype", "report_archetype must be finance-report or research-memo", "request.report_archetype"))

    if report_archetype == "finance-report":
        output_formats = request.get("output_formats")
        if not isinstance(output_formats, list):
            issues.append(issue("error", "request.invalid_output_formats", "finance-report requires an output_formats list", "request.output_formats"))
            output_formats = []
        if "markdown" in output_formats:
            issues.append(issue("error", "request.finance_report_markdown", "Markdown is not a final finance-report format", "request.output_formats"))
        if not {"interactive-html", "pdf", "pptx"}.intersection(output_formats):
            issues.append(issue("error", "request.missing_report_surface", "finance-report requires interactive-html, PDF, or PPTX as a presentation surface", "request.output_formats"))
        if "interactive-html" in output_formats and "json" not in output_formats:
            issues.append(issue("error", "request.missing_presentation_data", "interactive-html requires a JSON presentation artifact", "request.output_formats"))

        output_contract = plan.get("output_contract")
        if not isinstance(output_contract, dict):
            issues.append(issue("error", "plan.missing_finance_output_contract", "finance-report requires plan.output_contract", "plan.output_contract"))
        else:
            required_strings = ("coverage_universe_rule", "required_bridge_or_ranking")
            for field in required_strings:
                if not nonempty_string(output_contract.get(field)):
                    issues.append(issue("error", "plan.incomplete_finance_output_contract", f"finance-report output contract lacks {field}", f"plan.output_contract.{field}"))
            required_lists = ("comparison_periods", "common_metrics", "planned_artifacts")
            for field in required_lists:
                value = output_contract.get(field)
                if not isinstance(value, list) or not value:
                    issues.append(issue("error", "plan.incomplete_finance_output_contract", f"finance-report output contract requires a nonempty {field} list", f"plan.output_contract.{field}"))
            if request.get("task_type") == "sector":
                sector_kpis = output_contract.get("sector_kpis")
                if not isinstance(sector_kpis, list) or not sector_kpis:
                    issues.append(issue("error", "plan.incomplete_finance_output_contract", "sector finance-report requires a nonempty sector_kpis list", "plan.output_contract.sector_kpis"))
            if not isinstance(output_contract.get("valuation_required"), bool):
                issues.append(issue("error", "plan.incomplete_finance_output_contract", "finance-report must explicitly set valuation_required to true or false", "plan.output_contract.valuation_required"))

    issues.extend(check_editorial_review(record, run_dir))
    issues.extend(check_market_data(record, run_dir))

    selected_skills = plan.get("selected_skills", [])
    if not isinstance(selected_skills, list):
        issues.append(issue("error", "plan.invalid_skills", "selected_skills must be a list", "plan.selected_skills"))
    else:
        for position, skill in enumerate(selected_skills):
            if not isinstance(skill, dict):
                issues.append(issue("error", "plan.invalid_skill", "skill entry must be an object", f"plan.selected_skills[{position}]"))
                continue
            for field in ("name", "path", "purpose"):
                if not nonempty_string(skill.get(field)):
                    issues.append(issue("warning", "plan.skill_metadata", f"selected skill lacks {field}", f"plan.selected_skills[{position}].{field}"))
            if str(skill.get("path", "")).startswith("vendor/") and not nonempty_string(skill.get("commit")):
                issues.append(issue("warning", "plan.skill_revision", "vendor skill lacks pinned commit", f"plan.selected_skills[{position}].commit"))

    source_items = record.get("sources", [])
    evidence_items = record.get("evidence", [])
    fact_items = record.get("facts", [])
    calculation_items = record.get("calculations", [])
    sources = index_records(source_items, "source", "sources", issues)
    evidence = index_records(evidence_items, "evidence", "evidence", issues)
    facts = index_records(fact_items, "fact", "facts", issues)
    calculations = index_records(calculation_items, "calculation", "calculations", issues)

    seen_locations: dict[str, str] = {}
    for source_id, source in sources.items():
        source_path = f"sources[{source_id}]"
        for field in ("title", "publisher"):
            if not nonempty_string(source.get(field)):
                issues.append(issue("error", "source.missing_metadata", f"source lacks {field}", f"{source_path}.{field}"))
        if not valid_timestamp(source.get("retrieved_at")):
            issues.append(issue("error", "source.invalid_retrieved_at", "retrieved_at must be an ISO timestamp", f"{source_path}.retrieved_at"))
        url = source.get("url")
        local_path = source.get("local_path")
        if not nonempty_string(url) and not nonempty_string(local_path):
            issues.append(issue("error", "source.missing_location", "source needs url or local_path", source_path))
        if nonempty_string(url) and not re.match(r"^https?://", url):
            issues.append(issue("error", "source.invalid_url", "source URL must start with http:// or https://", f"{source_path}.url"))
        location = str(url or local_path or "")
        if location in seen_locations:
            issues.append(issue("warning", "source.duplicate_location", f"same location as {seen_locations[location]}", source_path))
        elif location:
            seen_locations[location] = source_id
        if source.get("primary") is False:
            issues.append(issue("warning", "source.secondary", "secondary source; confirm whether primary evidence exists", source_path))
        if not nonempty_string(source.get("license_or_terms")):
            issues.append(issue("warning", "source.terms_unknown", "data-use terms are not recorded", f"{source_path}.license_or_terms"))

    for evidence_id, item in evidence.items():
        item_path = f"evidence[{evidence_id}]"
        source_id = item.get("source_id")
        if source_id not in sources:
            issues.append(issue("error", "evidence.unknown_source", f"unknown source {source_id}", f"{item_path}.source_id"))
        if not nonempty_string(item.get("locator")):
            issues.append(issue("error", "evidence.missing_locator", "precise locator is required", f"{item_path}.locator"))
        if not nonempty_string(item.get("content")):
            issues.append(issue("error", "evidence.missing_content", "evidence content is required", f"{item_path}.content"))

    for calculation_id, calculation in calculations.items():
        calculation_path = f"calculations[{calculation_id}]"
        for field in ("description", "expression", "units"):
            if not nonempty_string(calculation.get(field)):
                issues.append(issue("error", "calculation.missing_field", f"calculation lacks {field}", f"{calculation_path}.{field}"))
        if "result" not in calculation:
            issues.append(issue("error", "calculation.missing_result", "calculation result is required", f"{calculation_path}.result"))
        inputs = calculation.get("input_fact_ids")
        if not isinstance(inputs, list) or not inputs:
            issues.append(issue("error", "calculation.missing_inputs", "input_fact_ids must be a nonempty list", f"{calculation_path}.input_fact_ids"))
        else:
            for fact_id in inputs:
                if fact_id not in facts:
                    issues.append(issue("error", "calculation.unknown_fact", f"unknown input fact {fact_id}", f"{calculation_path}.input_fact_ids"))

    for fact_id, fact in facts.items():
        fact_path = f"facts[{fact_id}]"
        if not nonempty_string(fact.get("statement")):
            issues.append(issue("error", "fact.missing_statement", "fact statement is required", f"{fact_path}.statement"))
        status = fact.get("status")
        if status not in FACT_STATUSES:
            issues.append(issue("error", "fact.invalid_status", f"invalid fact status {status}", f"{fact_path}.status"))
        material = fact.get("material")
        if not isinstance(material, bool):
            issues.append(issue("error", "fact.invalid_material", "material must be boolean", f"{fact_path}.material"))
            material = True
        source_ids = fact.get("source_ids")
        evidence_ids = fact.get("evidence_ids")
        if not isinstance(source_ids, list):
            issues.append(issue("error", "fact.invalid_sources", "source_ids must be a list", f"{fact_path}.source_ids"))
            source_ids = []
        if not isinstance(evidence_ids, list):
            issues.append(issue("error", "fact.invalid_evidence", "evidence_ids must be a list", f"{fact_path}.evidence_ids"))
            evidence_ids = []
        for source_id in source_ids:
            if source_id not in sources:
                issues.append(issue("error", "fact.unknown_source", f"unknown source {source_id}", f"{fact_path}.source_ids"))
        for evidence_id in evidence_ids:
            if evidence_id not in evidence:
                issues.append(issue("error", "fact.unknown_evidence", f"unknown evidence {evidence_id}", f"{fact_path}.evidence_ids"))
            elif evidence[evidence_id].get("source_id") not in source_ids:
                issues.append(issue("error", "fact.evidence_source_mismatch", f"{evidence_id} source is not listed on fact", f"{fact_path}.evidence_ids"))
        if material and (not source_ids or not evidence_ids) and status != "calculated":
            issues.append(issue("error", "fact.unsupported_material", "material fact requires source and evidence IDs", fact_path))
        if status in {"verified", "company-reported", "provider-reported"} and not evidence_ids:
            issues.append(issue("error", "fact.status_without_evidence", f"{status} requires evidence", fact_path))
        if status == "calculated" and fact.get("calculation_id") not in calculations:
            issues.append(issue("error", "fact.missing_calculation", "calculated fact requires a valid calculation_id", f"{fact_path}.calculation_id"))
        if status == "inferred" and not nonempty_string(fact.get("reasoning")):
            issues.append(issue("warning", "fact.inference_reasoning", "inference lacks explicit reasoning", f"{fact_path}.reasoning"))
        if "value" in fact:
            if not nonempty_string(fact.get("period")):
                issues.append(issue("warning", "fact.numeric_period", "numeric fact lacks period", f"{fact_path}.period"))
            if not nonempty_string(fact.get("units")):
                issues.append(issue("warning", "fact.numeric_units", "numeric fact lacks units", f"{fact_path}.units"))

    artifacts = record.get("artifacts", [])
    markdown_artifacts: list[tuple[dict[str, Any], Path, str]] = []
    report_data_artifacts: list[tuple[dict[str, Any], Path, dict[str, Any]]] = []
    if not isinstance(artifacts, list):
        issues.append(issue("error", "artifacts.not_list", "artifacts must be a list", "artifacts"))
        artifacts = []
    for position, artifact in enumerate(artifacts):
        artifact_path = f"artifacts[{position}]"
        if not isinstance(artifact, dict):
            issues.append(issue("error", "artifact.not_object", "artifact must be an object", artifact_path))
            continue
        status = artifact.get("status")
        if status not in ARTIFACT_STATUSES:
            issues.append(issue("error", "artifact.invalid_status", f"invalid status {status}", f"{artifact_path}.status"))
        output_path = safe_artifact_path(run_dir, artifact.get("path"))
        if output_path is None:
            issues.append(issue("error", "artifact.invalid_path", "artifact path is missing or escapes run directory", f"{artifact_path}.path"))
            continue
        if not output_path.is_file():
            issues.append(issue("error", "artifact.missing_file", "artifact file does not exist", f"{artifact_path}.path"))
            continue
        artifact_facts = artifact.get("fact_ids", [])
        if not isinstance(artifact_facts, list):
            issues.append(issue("error", "artifact.invalid_fact_ids", "fact_ids must be a list", f"{artifact_path}.fact_ids"))
        else:
            for fact_id in artifact_facts:
                if fact_id not in facts:
                    issues.append(issue("error", "artifact.unknown_fact", f"unknown fact {fact_id}", f"{artifact_path}.fact_ids"))
        if artifact.get("format") == "markdown" or output_path.suffix.lower() in {".md", ".markdown"}:
            try:
                text = output_path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                issues.append(issue("error", "artifact.invalid_encoding", "Markdown must be UTF-8", f"{artifact_path}.path"))
                continue
            analytical_text = MANAGED_SOURCES.sub("", MANAGED_VALIDATION.sub("", text))
            cited_sources = set(CITATION.findall(analytical_text))
            for source_id in cited_sources:
                if source_id not in sources:
                    issues.append(issue("error", "artifact.unknown_citation", f"citation {source_id} is not in source ledger", f"{artifact_path}.path"))
            used_fact_ids = set(artifact_facts) if isinstance(artifact_facts, list) else set()
            material_source_ids = {
                source_id
                for fact_id in used_fact_ids
                if fact_id in facts and facts[fact_id].get("material") is True
                for source_id in facts[fact_id].get("source_ids", [])
            }
            for source_id in sorted(material_source_ids - cited_sources):
                issues.append(issue("warning", "artifact.uncited_material_source", f"material source {source_id} is not cited in analytical text", f"{artifact_path}.path"))
            placeholders = sorted(set(match.group(0) for match in PLACEHOLDER.finditer(analytical_text)))
            if placeholders:
                severity = "error" if status == "validated" else "warning"
                issues.append(issue(severity, "artifact.placeholder", f"unresolved placeholders: {', '.join(placeholders)}", f"{artifact_path}.path"))
            markdown_artifacts.append((artifact, output_path, text))

        if output_path.name == "report-data.json":
            try:
                presentation = json.loads(output_path.read_text(encoding="utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as error:
                issues.append(issue("error", "artifact.invalid_report_data", str(error), f"{artifact_path}.path"))
                continue
            if not isinstance(presentation, dict):
                issues.append(issue("error", "artifact.invalid_report_data", "report-data.json root must be an object", f"{artifact_path}.path"))
                continue
            meta = presentation.get("meta") if isinstance(presentation.get("meta"), dict) else {}
            executive_view = presentation.get("executive_view") if isinstance(presentation.get("executive_view"), dict) else {}
            sections = presentation.get("sections")
            if presentation.get("schema_version") != "1.0.0":
                issues.append(issue("error", "artifact.report_data_schema", "report-data.json requires schema_version 1.0.0", f"{artifact_path}.path"))
            for field in ("title", "decision_use", "language", "coverage_universe"):
                if not nonempty_string(meta.get(field)):
                    issues.append(issue("error", "artifact.incomplete_report_data", f"report metadata lacks {field}", f"{artifact_path}.path"))
            for field in ("headline", "summary"):
                if not nonempty_string(executive_view.get(field)):
                    issues.append(issue("error", "artifact.incomplete_report_data", f"executive view lacks {field}", f"{artifact_path}.path"))
            if not isinstance(sections, list) or not sections:
                issues.append(issue("error", "artifact.incomplete_report_data", "report requires at least one analytical section", f"{artifact_path}.path"))

            used_fact_ids = set(artifact_facts) if isinstance(artifact_facts, list) else set()
            data_fact_ids = collect_reference_ids(presentation, "fact_id", "fact_ids")
            data_source_ids = collect_reference_ids(presentation, "source_id", "source_ids")
            data_calculation_ids = collect_reference_ids(presentation, "calculation_id", "calculation_ids")
            for fact_id in sorted(data_fact_ids):
                if fact_id not in facts:
                    issues.append(issue("error", "artifact.unknown_fact", f"report data references unknown fact {fact_id}", f"{artifact_path}.path"))
            for source_id in sorted(data_source_ids):
                if source_id not in sources:
                    issues.append(issue("error", "artifact.unknown_citation", f"report data references unknown source {source_id}", f"{artifact_path}.path"))
            for calculation_id in sorted(data_calculation_ids):
                if calculation_id not in calculations:
                    issues.append(issue("error", "artifact.unknown_calculation", f"report data references unknown calculation {calculation_id}", f"{artifact_path}.path"))
            for fact_id in sorted(used_fact_ids - data_fact_ids):
                issues.append(issue("error", "artifact.unmapped_fact", f"artifact fact {fact_id} is absent from report-data.json", f"{artifact_path}.path"))
            material_source_ids = {
                source_id
                for fact_id in used_fact_ids
                if fact_id in facts and facts[fact_id].get("material") is True
                for source_id in facts[fact_id].get("source_ids", [])
            }
            for source_id in sorted(material_source_ids - data_source_ids):
                issues.append(issue("error", "artifact.uncited_material_source", f"material source {source_id} is absent from report-data.json", f"{artifact_path}.path"))
            report_data_artifacts.append((artifact, output_path, presentation))

        if artifact.get("format") == "interactive-html" or output_path.suffix.lower() == ".html":
            try:
                html_text = output_path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                issues.append(issue("error", "artifact.invalid_encoding", "HTML must be UTF-8", f"{artifact_path}.path"))
                continue
            if 'id="finrunbook-report"' not in html_text or "report-data.json" not in html_text:
                issues.append(issue("error", "artifact.invalid_interactive_report", "interactive report must expose the FinRunbook root and load report-data.json", f"{artifact_path}.path"))
            if "Draft report. The presentation renderer has not completed this run." in html_text:
                issues.append(issue("error", "artifact.unrendered_scaffold", "interactive report is still the initialization scaffold", f"{artifact_path}.path"))

    if not facts:
        issues.append(issue("error", "record.no_facts", "research run has no recorded facts", "facts"))
    if not sources:
        issues.append(issue("error", "record.no_sources", "research run has no recorded sources", "sources"))

    errors = sum(item["severity"] == "error" for item in issues)
    warnings = sum(item["severity"] == "warning" for item in issues)
    status = "FAIL" if errors else ("PASS_WITH_WARNINGS" if warnings else "PASS")
    checked_at = utc_now()

    validation_block = render_validation(status, checked_at, errors, warnings)
    sources_block = render_sources(list(sources.values()))
    for artifact, output_path, text in markdown_artifacts:
        updated = replace_managed_block(text, MANAGED_VALIDATION, validation_block)
        updated = replace_managed_block(updated, MANAGED_SOURCES, sources_block)
        atomic_text(output_path, updated.rstrip() + "\n")
        artifact["status"] = "blocked" if status == "FAIL" else "validated"
    for artifact, output_path, presentation in report_data_artifacts:
        presentation["validation"] = {
            "status": status,
            "validated_at": checked_at,
            "errors": errors,
            "warnings": warnings,
        }
        atomic_json(output_path, presentation)
        artifact["status"] = "blocked" if status == "FAIL" else "validated"
    for artifact in artifacts:
        if isinstance(artifact, dict):
            artifact["status"] = "blocked" if status == "FAIL" else "validated"

    numbered_issues = []
    for position, item in enumerate(issues, start=1):
        numbered_issues.append({"id": f"ISSUE-{position:03d}", **item})
    validation = {
        "validator_version": VALIDATOR_VERSION,
        "status": status,
        "validated_at": checked_at,
        "summary": {
            "errors": errors,
            "warnings": warnings,
            "sources": len(sources),
            "evidence": len(evidence),
            "facts": len(facts),
            "calculations": len(calculations),
            "artifacts": len(artifacts),
        },
        "checks": [
            "record structure",
            "stable IDs and reference integrity",
            "source metadata",
            "evidence locators",
            "fact support and status",
            "calculation provenance",
            "artifact files, fact references, citations, and placeholders",
            "finance-report output contract",
            "interactive report and presentation-data provenance",
            "editorial completion receipt and language coverage (when required)",
            "market-data snapshots, input mappings and recomputed metrics (when declared)",
        ],
        "semantic_review_required": True,
        "issues": numbered_issues,
    }
    record["validation"] = {
        "status": status,
        "validated_at": checked_at,
        "validator_version": VALIDATOR_VERSION,
        "issues": numbered_issues,
    }
    if isinstance(run, dict):
        run["updated_at"] = checked_at
        run["status"] = "validation_failed" if status == "FAIL" else "complete"
    atomic_json(record_path, record)
    atomic_json(run_dir / "validation.json", validation)
    return validation, 1 if status == "FAIL" else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate and annotate a FinRunbook run")
    parser.add_argument("run_directory", type=Path)
    args = parser.parse_args()
    run_dir = args.run_directory.resolve()
    if not run_dir.is_dir():
        parser.error(f"run directory does not exist: {run_dir}")
    result, exit_code = validate(run_dir)
    print(json.dumps({"status": result["status"], **result["summary"]}, ensure_ascii=False))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
