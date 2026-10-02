"""Milestone 3 — Output Writers.

Writes QualificationRecord lists to:
    - qualification_results.json  (full machine-readable records)
    - qualification_results.csv   (spreadsheet-friendly flat view)
    - qualified_leads_report.md   (human-readable Markdown for MalikAxiom team)

Pure standard library only.
"""

from __future__ import annotations

import csv
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .qualifier import QualificationRecord

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# JSON
# ---------------------------------------------------------------------------

def _record_to_dict(r: QualificationRecord) -> dict[str, Any]:
    return {
        "lead_id": r.lead_id,
        "business_name": r.business_name,
        "category": r.category,
        "location": r.location,
        "phone": r.phone,
        "mobile_phone": r.mobile_phone,
        "whatsapp": r.whatsapp,
        "landline": r.landline,
        "email": r.email,
        "website": r.website,
        "linkedin": r.linkedin,
        "instagram": r.instagram,
        "facebook": r.facebook,
        "tiktok": r.tiktok,
        "youtube": r.youtube,
        "sales_potential": r.sales_potential,
        "confidence": r.confidence,
        "why_this_lead": r.why_this_lead,
        "business_summary": r.business_summary,
        "primary_service": r.primary_service,
        "primary_service_reason": r.primary_service_reason,
        "secondary_services": r.secondary_services,
        "secondary_service_reasons": r.secondary_service_reasons,
        "detected_opportunity": r.detected_opportunity,
        "digital_maturity": r.digital_maturity,
        "outreach_channel": r.outreach_channel,
        "outreach_angle": r.outreach_angle,
        "final_action": r.final_action,
        "evidence_used": r.evidence_used,
        "uncertainties": r.uncertainties,
        "qualification_timestamp": r.qualification_timestamp,
    }


def write_json(path: Path, records: list[QualificationRecord]) -> None:
    payload = [_record_to_dict(r) for r in records]
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info("Wrote JSON: %s (%d records)", path, len(payload))


# ---------------------------------------------------------------------------
# CSV
# ---------------------------------------------------------------------------

def _record_to_row(r: QualificationRecord) -> dict[str, Any]:
    return {
        "lead_id": r.lead_id,
        "business_name": r.business_name or "",
        "category": r.category or "",
        "location": r.location or "",
        "phone": r.phone or "",
        "mobile_phone": r.mobile_phone or "",
        "whatsapp": r.whatsapp or "",
        "landline": r.landline or "",
        "email": r.email or "",
        "website": r.website or "",
        "linkedin": r.linkedin or "",
        "instagram": r.instagram or "",
        "facebook": r.facebook or "",
        "tiktok": r.tiktok or "",
        "youtube": r.youtube or "",
        "sales_potential": r.sales_potential,
        "confidence": r.confidence,
        "final_action": r.final_action,
        "primary_service": r.primary_service,
        "outreach_channel": r.outreach_channel,
        "digital_maturity": r.digital_maturity,
        "why_this_lead": r.why_this_lead,
        "business_summary": r.business_summary,
        "primary_service_reason": r.primary_service_reason,
        "secondary_services": " | ".join(r.secondary_services),
        "secondary_service_reasons": " | ".join(r.secondary_service_reasons),
        "detected_opportunity": r.detected_opportunity,
        "outreach_angle": r.outreach_angle,
        "evidence_used": " | ".join(r.evidence_used),
        "uncertainties": " | ".join(r.uncertainties),
        "qualification_timestamp": r.qualification_timestamp,
    }


def write_csv(path: Path, records: list[QualificationRecord]) -> None:
    if not records:
        path.write_text("", encoding="utf-8")
        logger.info("Wrote empty CSV: %s", path)
        return

    rows = [_record_to_row(r) for r in records]
    fieldnames = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    logger.info("Wrote CSV: %s (%d rows, %d columns)", path, len(rows), len(fieldnames))


# ---------------------------------------------------------------------------
# Markdown Report
# ---------------------------------------------------------------------------

_POTENTIAL_EMOJI = {
    "HIGH": "🔥",
    "MODERATE": "⚡",
    "LOW": "📋",
    "SKIP": "🚫",
}

_CONFIDENCE_LABEL = {
    "HIGH": "High Evidence",
    "MEDIUM": "Medium Evidence",
    "LOW": "Low Evidence",
}

_ACTION_LABEL = {
    "CONTACT": "✅ Contact Now",
    "INVESTIGATE_FURTHER": "🔍 Investigate Further",
    "ARCHIVE": "📁 Archive",
    "SKIP": "🚫 Skip",
}


def _section(
    records: list[QualificationRecord],
    potential: str,
    f: Any,
) -> None:
    emoji = _POTENTIAL_EMOJI.get(potential, "")
    filtered = [r for r in records if r.sales_potential == potential]
    count = len(filtered)

    f.write(f"\n---\n\n## {emoji} {potential} Potential Leads ({count})\n\n")

    if not filtered:
        f.write("_No leads in this category._\n")
        return

    for r in filtered:
        action_label = _ACTION_LABEL.get(r.final_action, r.final_action)
        confidence_label = _CONFIDENCE_LABEL.get(r.confidence, r.confidence)
        loc = f", {r.location}" if r.location else ""
        cat = f" · {r.category}" if r.category else ""

        f.write(f"### {r.business_name or r.lead_id}{loc}{cat}\n\n")
        f.write(f"| Field | Value |\n")
        f.write(f"|---|---|\n")
        f.write(f"| **Sales Potential** | {emoji} {r.sales_potential} |\n")
        f.write(f"| **Confidence** | {confidence_label} |\n")
        f.write(f"| **Final Action** | {action_label} |\n")
        f.write(f"| **Outreach Channel** | {r.outreach_channel or 'unknown'} |\n")
        f.write(f"| **Primary Service** | {r.primary_service} |\n")
        f.write(f"| **Digital Maturity** | {r.digital_maturity} |\n")
        if r.phone:
            f.write(f"| **Phone** | {r.phone} |\n")
        f.write("\n")

        f.write(f"**Why this lead:**\n> {r.why_this_lead}\n\n")

        f.write(f"**Business summary:**  \n{r.business_summary}\n\n")

        f.write(f"**Detected opportunity:**  \n{r.detected_opportunity}\n\n")

        f.write(f"**Primary service recommendation:**  \n{r.primary_service_reason}\n\n")

        if r.secondary_services:
            f.write("**Secondary services (follow-on):**\n")
            for svc, reason in zip(r.secondary_services, r.secondary_service_reasons):
                f.write(f"- **{svc}:** {reason}\n")
            f.write("\n")

        if r.outreach_angle:
            f.write(f"**Outreach angle:**  \n_{r.outreach_angle}_\n\n")

        if r.evidence_used:
            f.write("**Evidence used:**\n")
            for e in r.evidence_used:
                f.write(f"- {e}\n")
            f.write("\n")

        if r.uncertainties:
            f.write("**Uncertainties / gaps:**\n")
            for u in r.uncertainties:
                f.write(f"- {u}\n")
            f.write("\n")

        f.write("\n")


def write_report(
    path: Path,
    records: list[QualificationRecord],
    counts: dict[str, int],
    source_file: str,
) -> None:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    total = len(records)

    with path.open("w", encoding="utf-8") as f:
        f.write("# MalikAxiom Lead Qualification Report\n\n")
        f.write(f"**Generated:** {now}  \n")
        f.write(f"**Source:** `{source_file}`  \n")
        f.write(f"**Total leads processed:** {total}  \n\n")

        f.write("## Summary\n\n")
        f.write("| Potential | Count | Recommended Action |\n")
        f.write("|---|---|---|\n")
        f.write(
            f"| 🔥 HIGH | {counts.get('HIGH', 0)} | Contact as soon as possible |\n"
        )
        f.write(
            f"| ⚡ MODERATE | {counts.get('MODERATE', 0)} | Investigate further or contact |\n"
        )
        f.write(
            f"| 📋 LOW | {counts.get('LOW', 0)} | Archive — no immediate opportunity |\n"
        )
        f.write(
            f"| 🚫 SKIP | {counts.get('SKIP', 0)} | Discard |\n"
        )
        f.write("\n")

        f.write("> **Note on confidence:** Confidence reflects the *strength of evidence*, ")
        f.write("not sales potential. A lead can be HIGH potential with MEDIUM confidence ")
        f.write("(strong opportunity but limited data), or LOW potential with HIGH confidence ")
        f.write("(strong evidence that there is no current gap).\n\n")

        # Output sections in priority order
        for potential in ("HIGH", "MODERATE", "LOW", "SKIP"):
            _section(records, potential, f)

        f.write("\n---\n\n")
        f.write("_Report generated by **MalikAxiom Lead AI** — Milestone 3._  \n")
        f.write("_Rules engine powered by knowledge base files in `knowledge/`._\n")

    logger.info("Wrote Markdown report: %s", path)
