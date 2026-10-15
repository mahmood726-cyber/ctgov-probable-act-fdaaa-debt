#!/usr/bin/env python3
"""Review queue for potential CT.gov results gaps; NEVER ACT/legal compliance determinations.

For a JSONL ClinicalTrials.gov API-v2 export, produce one row per record,
using the registry's ACTUAL primary completion date and the presence of
posted results. FDAAA applicability, certifications, delays, extensions,
IND/IDE jurisdiction and responsible-party exemptions are not established.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
from datetime import date, timedelta
from pathlib import Path

NCT_PATTERN = re.compile(r"^NCT\d{8}$")
SOURCES = (
    "https://www.law.cornell.edu/cfr/text/42/11.22",
    "https://www.law.cornell.edu/cfr/text/42/11.44",
    "https://cdn.clinicaltrials.gov/documents/ACT_Checklist.pdf",
)


def get_path(obj: dict, *path):
    for key in path:
        if not isinstance(obj, dict):
            return None
        obj = obj.get(key)
    return obj


def exact_date(value):
    """Only day-precise ISO 8601 dates are suitable for a 365-day screen."""
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d\d-\d\d", value):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def bool_or_unknown(value):
    # None means unknown; absent regulatory flags are NOT false.
    return value if type(value) is bool else None


def review_record(study, *, as_of: date):
    if not isinstance(study, dict):
        raise ValueError("Expected a CT.gov study object")
    nct_id = get_path(study, "protocolSection", "identificationModule", "nctId")
    if not isinstance(nct_id, str) or not NCT_PATTERN.fullmatch(nct_id):
        raise ValueError("Study lacks a valid NCT ID")
    protocol = study.get("protocolSection") or {}
    status = protocol.get("statusModule") or {}
    oversight = protocol.get("oversightModule") or {}
    design = protocol.get("designModule") or {}
    arm = protocol.get("armsInterventionsModule") or {}
    locations = get_path(protocol, "contactsLocationsModule", "locations") or []
    if not isinstance(locations, list):
        raise ValueError("Malformed locations list")

    raw_pcd = get_path(status, "primaryCompletionDateStruct", "date")
    pcd_kind = get_path(status, "primaryCompletionDateStruct", "type")
    pcd = exact_date(raw_pcd) if pcd_kind == "ACTUAL" else None
    start = exact_date(get_path(status, "startDateStruct", "date"))
    results_post_date = exact_date(get_path(status, "resultsFirstPostDateStruct", "date"))
    has_results = study.get("hasResults")
    if type(has_results) is not bool:
        has_results = None

    # Date of first results POSTING is distinct from final results submission
    # and does not itself prove timely compliance or approval by QA.
    elapsed = (as_of - pcd).days if pcd and pcd <= as_of else None
    if elapsed is None:
        gap = None
        clock = "UNASSESSABLE_ACTUAL_PCD_REQUIRED"
    elif has_results is None:
        gap = None
        clock = "UNASSESSABLE_RESULTS_STATUS_UNKNOWN"
    elif has_results:
        gap = False
        clock = "RESULTS_POSTED_IN_REGISTRY"
    else:
        gap = elapsed >= 365
        clock = "ONE_YEAR_ELAPSED_NO_POSTED_RESULTS" if gap else "UNDER_ONE_YEAR_NO_POSTED_RESULTS"

    fda_drug = bool_or_unknown(oversight.get("isFdaRegulatedDrug"))
    fda_device = bool_or_unknown(oversight.get("isFdaRegulatedDevice"))
    us_site = any(
        isinstance(location, dict) and
        str(location.get("country", "")).strip().lower() in
        {"united states", "united states of america", "usa"}
        for location in locations
    )
    intervention_types = sorted({
        intervention.get("type", "") for intervention in (arm.get("interventions") or [])
        if isinstance(intervention, dict) and intervention.get("type")
    })
    phases = sorted({
        phase for phase in (design.get("phases") or [])
        if isinstance(phase, str)
    })

    signals = []
    if gap is True:
        signals.append("one_year_registry_gap")
    if design.get("studyType") == "INTERVENTIONAL":
        signals.append("interventional")
    if fda_drug is True or fda_device is True:
        signals.append("fda_regulated_product_reported")
    if us_site:
        signals.append("us_facility_reported")
    if ("DRUG" in intervention_types or "BIOLOGICAL" in intervention_types) and "PHASE1" not in phases:
        signals.append("drug_or_biologic_non_phase1_proxy")
    if "DEVICE" in intervention_types:
        signals.append("device_intervention_proxy")

    caution = []
    if bool_or_unknown(oversight.get("isFdaRegulatedDrug")) is None and bool_or_unknown(oversight.get("isFdaRegulatedDevice")) is None:
        caution.append("regulatory_product_flags_unknown")
    if not locations:
        caution.append("registry_locations_unavailable")
    if pcd is None:
        caution.append("no_day_precise_actual_primary_completion")
    if start is None:
        caution.append("start_date_incomplete_or_unknown")
    if has_results is None:
        caution.append("posted_results_indicator_missing")
    if results_post_date and not has_results:
        caution.append("posted_results_date_conflicts_with_indicator")

    priority = (
        "REVIEW_CANDIDATE" if gap is True
        and design.get("studyType") == "INTERVENTIONAL"
        and (fda_drug is True or fda_device is True or us_site)
        else "DESCRIPTIVE_ONLY"
    )
    return {
        "nctId": nct_id,
        "as_of_date": as_of.isoformat(),
        "source_record_primary_completion_date": raw_pcd,
        "primary_completion_date_type": pcd_kind,
        "source_results_first_post_date": get_path(status, "resultsFirstPostDateStruct", "date"),
        "hasResults": has_results,
        "days_since_actual_primary_completion": elapsed,
        "registry_posting_clock": clock,
        "one_year_elapsed_without_posted_results": gap,
        "study_type": design.get("studyType"),
        "phases": phases,
        "intervention_types": intervention_types,
        "is_fda_regulated_drug": fda_drug,
        "is_fda_regulated_device": fda_device,
        "us_site_observed": us_site,
        "review_signals": signals,
        "data_caveats": caution,
        "review_priority": priority,
        "act_eligibility": "UNDETERMINED",
        "results_legal_overdue_status": "UNDETERMINED",
        "assumptions": (
            "A 365-day registry gap is only a screen. ACT jurisdiction, "
            "responsible party, version-specific law, extensions, "
            "certifications, delays and legal reporting deadlines "
            "require case-by-case adjudication."
        ),
    }


def read_rows(path: Path):
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if line.strip():
                try:
                    yield json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"Malformed JSON at source line {line_number}") from exc


def sha256(path: Path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for part in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(part)
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="ClinicalTrials.gov API v2 study JSONL or .jsonl.gz")
    parser.add_argument("--as-of", type=str, required=True, help="Reference date YYYY-MM-DD")
    parser.add_argument("--output", type=Path, required=True)
    options = parser.parse_args()

    as_of = exact_date(options.as_of)
    if as_of is None:
        parser.error("--as-of must be an exact YYYY-MM-DD date")
    if options.input.resolve() == options.output.resolve():
        parser.error("Refusing to overwrite the source records")
    options.output.parent.mkdir(parents=True, exist_ok=True)
    temp = options.output.with_suffix(options.output.suffix + ".partial")
    ids = set()
    num = 0
    try:
        with temp.open("w", encoding="utf-8") as out:
            for record in read_rows(options.input):
                derived = review_record(record, as_of=as_of)
                if derived["nctId"] in ids:
                    raise ValueError("Duplicate source NCT ID: " + derived["nctId"])
                ids.add(derived["nctId"])
                out.write(json.dumps(derived, ensure_ascii=False, sort_keys=True) + "\n")
                num += 1
        if not num:
            raise ValueError("Empty source input: refusing to publish a review queue")
        temp.replace(options.output)
    finally:
        temp.unlink(missing_ok=True)
    meta_path = options.output.with_suffix(options.output.suffix + ".metadata.json")
    meta_path.write_text(json.dumps({
        "created_as_of": as_of.isoformat(),
        "records": num,
        "source_input_sha256": sha256(options.input),
        "derived_output_sha256": sha256(options.output),
        "purpose": "registry-gap research review queue, never a legal violation determination",
        "act_eligibility": "UNDETERMINED",
        "sources": SOURCES,
    }, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {num} registry-gap review rows to {options.output}")


if __name__ == "__main__":
    main()
