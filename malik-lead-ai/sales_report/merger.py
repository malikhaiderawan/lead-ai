"""Milestone 5 — Lead Data Merger.

Loads the three existing pipeline output JSON files and merges them
into one unified dict per lead, keyed by lead_id.

Sources:
    output/research_results.json       — M2
    output/qualification_results.json  — M3
    output/outreach_results.json       — M4

Merge strategy:
    M3 qualification is the primary key source (lead_id).
    M2 and M4 are joined by lead_id.
    Missing M2/M4 data is filled with safe defaults.
    No lead is dropped due to a missing join.

Standard library only.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"


# ---------------------------------------------------------------------------
# Action normalization (M3 → M5 canonical priority)
# ---------------------------------------------------------------------------

_ACTION_TO_PRIORITY: dict[str, str] = {
    "CONTACT": "CONTACT FIRST",
    "INVESTIGATE_FURTHER": "CONTACT LATER",
    "ARCHIVE": "SKIP",
    "SKIP": "SKIP",
}


def normalize_priority(final_action: str, sales_potential: str = "") -> str:
    """Map M3 final_action to M5 outreach_priority."""
    base = _ACTION_TO_PRIORITY.get((final_action or "").upper(), "SKIP")
    # LOW potential that isn't already CONTACT FIRST → CONTACT LATER
    if base == "CONTACT FIRST" and (sales_potential or "").upper() == "LOW":
        return "CONTACT LATER"
    return base


# ---------------------------------------------------------------------------
# JSON loaders
# ---------------------------------------------------------------------------

def _load_json(path: Path, label: str) -> list[dict[str, Any]]:
    """Load a JSON list from path; return empty list with warning if missing."""
    if not path.is_file():
        logger.warning("%s not found: %s", label, path)
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            logger.warning("%s is not a JSON array: %s", label, path)
            return []
        logger.info("Loaded %d records from %s (%s)", len(data), label, path.name)
        return data
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to load %s: %s", label, exc)
        return []


def _index_by(records: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    """Index records by a string key, last-write-wins on collision."""
    result: dict[str, dict[str, Any]] = {}
    for r in records:
        k = r.get(key)
        if k:
            result[str(k)] = r
    return result


# ---------------------------------------------------------------------------
# Safe value helper
# ---------------------------------------------------------------------------

def _safe(val: Any, default: str = "") -> str:
    if val is None:
        return default
    s = str(val).strip()
    return s if s and s.lower() not in ("null", "none") else default


# ---------------------------------------------------------------------------
# Main merge function
# ---------------------------------------------------------------------------

def merge_pipeline_outputs(output_dir: Path | None = None) -> list[dict[str, Any]]:
    """
    Load and merge M2 + M3 + M4 JSON outputs into one list of unified dicts.

    Returns:
        List of merged lead dicts, ordered by outreach_priority then original order.

    Raises:
        FileNotFoundError: If M3 qualification_results.json is missing
                           (it is the primary key source).
    """
    out = output_dir or OUTPUT_DIR

    research_path = out / "research_results.json"
    qualify_path  = out / "qualification_results.json"
    outreach_path = out / "outreach_results.json"

    if not qualify_path.is_file():
        raise FileNotFoundError(
            f"Qualification results not found: {qualify_path}\n"
            "Run 'python3 main.py qualify' first."
        )

    qualify_records  = _load_json(qualify_path,  "M3 qualification")
    research_records = _load_json(research_path,  "M2 research")
    outreach_records = _load_json(outreach_path,  "M4 outreach")

    research_idx = _index_by(research_records, "lead_id")
    outreach_idx = _index_by(outreach_records, "lead_id")

    merged: list[dict[str, Any]] = []

    for q in qualify_records:
        lead_id = _safe(q.get("lead_id"))
        r = research_idx.get(lead_id, {})
        o = outreach_idx.get(lead_id, {})

        # Normalize action → priority
        final_action   = _safe(q.get("final_action"))
        sales_potential = _safe(q.get("sales_potential"))
        # M4 already normalizes; use M4 outreach_priority if present
        outreach_priority = _safe(
            o.get("outreach_priority") or normalize_priority(final_action, sales_potential)
        )

        # Build outreach_message from M4 opening + body + CTA
        opening  = _safe(o.get("opening"))
        body     = _safe(o.get("message"))
        cta      = _safe(o.get("cta"))
        if opening and body:
            outreach_message = f"{opening}\n\n{body}\n\n{cta}".strip()
        elif body:
            outreach_message = f"{body}\n\n{cta}".strip()
        else:
            outreach_message = ""

        # Personalization points → pipe-separated string for CSV
        pp = o.get("personalization_points") or []
        personalization_str = " | ".join(str(p) for p in pp)

        # Secondary services → comma-separated
        sec = q.get("secondary_services") or []
        secondary_str = ", ".join(str(s) for s in sec)

        # Uncertainties → pipe-separated
        unc = q.get("uncertainties") or []
        uncertainties_str = " | ".join(str(u) for u in unc)

        # Contact info
        website      = _safe(r.get("website") or q.get("website") or o.get("website") or "")
        phone        = _safe(q.get("phone") or r.get("phone") or o.get("phone") or "")
        mobile_phone = _safe(q.get("mobile_phone") or r.get("mobile_phone") or o.get("mobile_phone") or "")
        whatsapp     = _safe(q.get("whatsapp") or r.get("whatsapp") or o.get("whatsapp") or "")
        landline     = _safe(q.get("landline") or r.get("landline") or o.get("landline") or "")
        email        = _safe(r.get("email") or q.get("email") or o.get("email") or "")
        location     = _safe(q.get("location") or r.get("location") or o.get("location") or "")

        # Social presence fields
        instagram    = _safe(r.get("instagram") or q.get("instagram") or o.get("instagram") or "")
        facebook     = _safe(r.get("facebook") or q.get("facebook") or o.get("facebook") or "")
        linkedin     = _safe(r.get("linkedin") or q.get("linkedin") or o.get("linkedin") or "")
        tiktok       = _safe(r.get("tiktok") or q.get("tiktok") or o.get("tiktok") or "")
        youtube      = _safe(r.get("youtube") or q.get("youtube") or o.get("youtube") or "")

        merged.append({
            # Identity
            "lead_id":                lead_id,
            "business_name":          _safe(q.get("business_name")),
            "business_type":          _safe(r.get("business_type") or ""),
            "location":               location,
            "website":                website,
            "phone":                  phone,
            "mobile_phone":           mobile_phone,
            "whatsapp":               whatsapp,
            "landline":               landline,
            "email":                  email,
            "linkedin":               linkedin,
            "instagram":              instagram,
            "facebook":               facebook,
            "tiktok":                 tiktok,
            "youtube":                youtube,

            # Research
            "research_status":        _safe(r.get("research_status") or "UNKNOWN"),
            "digital_maturity":       _safe(q.get("digital_maturity") or r.get("digital_maturity") or ""),

            # Qualification
            "sales_potential":        sales_potential,
            "confidence":             _safe(q.get("confidence")),
            "why_this_lead":          _safe(q.get("why_this_lead")),
            "detected_opportunity":   _safe(q.get("detected_opportunity")),
            "primary_service":        _safe(q.get("primary_service")),
            "primary_service_reason": _safe(q.get("primary_service_reason")),
            "secondary_services":     secondary_str,
            "final_action":           final_action,

            # Outreach
            "outreach_priority":      outreach_priority,
            "outreach_channel":       _safe(o.get("recommended_channel") or q.get("outreach_channel") or ""),
            "outreach_angle":         _safe(q.get("outreach_angle")),
            "personalization_points": personalization_str,
            "outreach_message":       outreach_message,
            "message_notes":          _safe(o.get("message_notes")),

            # Quality
            "uncertainties":          uncertainties_str,
            "is_mock":                bool(o.get("is_mock")),
            "generation_error":       _safe(o.get("generation_error")),
            "source_file":            _safe(r.get("source_file") or q.get("source_file") or ""),
            "google_rating":          _safe(r.get("google_rating") or q.get("google_rating") or ""),
            "google_reviews":         _safe(r.get("google_reviews") or q.get("google_reviews") or ""),
            "google_maps_url":        _safe(r.get("google_maps_url") or q.get("google_maps_url") or ""),

            # Audit columns (filled by auditor)
            "review_flag":            False,
            "review_reason":          "",
            "possible_duplicate":     False,
            "duplicate_reason":       "",
            "contact_quality_issues": "",

            # Raw M3/M4 subfields for audit use
            "_ecommerce_status":      _safe(r.get("ecommerce_status")),
            "_instagram_status":      _safe(r.get("instagram_status")),
            "_facebook_status":       _safe(r.get("facebook_status")),
            "_website_reachable":     _safe(r.get("website_reachable")),
            "_google_reviews":        r.get("google_reviews") or r.get("google_review_count"),
        })

    # Sort: CONTACT FIRST → CONTACT LATER → SKIP
    _priority_order = {"CONTACT FIRST": 0, "CONTACT LATER": 1, "SKIP": 2}
    merged.sort(key=lambda x: _priority_order.get(x["outreach_priority"], 3))

    logger.info(
        "Merged %d leads: %d CONTACT FIRST, %d CONTACT LATER, %d SKIP",
        len(merged),
        sum(1 for m in merged if m["outreach_priority"] == "CONTACT FIRST"),
        sum(1 for m in merged if m["outreach_priority"] == "CONTACT LATER"),
        sum(1 for m in merged if m["outreach_priority"] == "SKIP"),
    )
    return merged
