#!/usr/bin/env python3
"""Validate and annotate a FinRunbook run using the Python standard library."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


VALIDATOR_VERSION = "0.1.0"
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


def safe_artifact_path(run_dir: Path, relative: Any) -> Path | None:
    if not nonempty_string(relative):
        return None
    candidate = (run_dir / relative).resolve()
    try:
        candidate.relative_to(run_dir.resolve())
    except ValueError:
        return None
    return candidate


def atomic_json(path: Path, value: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


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
        if status in {"verified", "company-reported"} and not evidence_ids:
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

