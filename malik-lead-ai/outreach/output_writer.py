"""Milestone 4 — Outreach Output Writers.

Writes OutreachRecord lists to:
    - outreach_results.json   (full machine-readable records)
    - outreach_results.csv    (spreadsheet-friendly flat view)
    - outreach_results.md     (human-readable Markdown for manual review before sending)

Standard library only.
"""

from __future__ import annotations

import csv
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .composer import OutreachRecord

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# JSON
# ---------------------------------------------------------------------------

def _record_to_dict(r: OutreachRecord) -> dict[str, Any]:
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
        "primary_service": r.primary_service,
        "digital_maturity": r.digital_maturity,
        "recommended_channel": r.recommended_channel,
        "outreach_priority": r.outreach_priority,
        "subject": r.subject,
        "opening": r.opening,
        "message": r.message,
        "cta": r.cta,
        "personalization_points": r.personalization_points,
        "message_notes": r.message_notes,
        "is_mock": r.is_mock,
        "generation_error": r.generation_error,
        "outreach_timestamp": r.outreach_timestamp,
    }


def write_json(path: Path, records: list[OutreachRecord]) -> None:
    payload = [_record_to_dict(r) for r in records]
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info("Wrote JSON: %s (%d records)", path, len(payload))


# ---------------------------------------------------------------------------
# CSV
# ---------------------------------------------------------------------------

def _record_to_row(r: OutreachRecord) -> dict[str, Any]:
    full_message = ""
    if r.opening and r.message:
        full_message = f"{r.opening}\n\n{r.message}\n\n{r.cta}".strip()
    elif r.message:
        full_message = f"{r.message}\n\n{r.cta}".strip()

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
        "outreach_priority": r.outreach_priority,
        "recommended_channel": r.recommended_channel,
        "primary_service": r.primary_service,
        "subject": r.subject,
        "full_message": full_message,
        "cta": r.cta,
        "personalization_points": " | ".join(r.personalization_points),
        "message_notes": r.message_notes,
        "is_mock": str(r.is_mock),
        "generation_error": r.generation_error or "",
        "outreach_timestamp": r.outreach_timestamp,
    }


def write_csv(path: Path, records: list[OutreachRecord]) -> None:
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

_PRIORITY_EMOJI = {
    "CONTACT FIRST": "🔥",
    "CONTACT LATER": "⚡",
    "SKIP": "🚫",
}

_POTENTIAL_EMOJI = {
    "HIGH": "🔥",
    "MODERATE": "⚡",
    "LOW": "📋",
    "SKIP": "🚫",
}

_CHANNEL_EMOJI = {
    "WhatsApp": "📱",
    "Instagram DM": "📸",
    "Facebook": "💬",
    "Email": "📧",
    "Contact Form": "📝",
    "unknown": "❓",
}


def _render_message_box(r: OutreachRecord, f: Any) -> None:
    """Render the full message in a quote block for easy copy-paste."""
    parts: list[str] = []
    if r.opening:
        parts.append(r.opening)
    if r.message:
        parts.append("")
        parts.append(r.message)
    if r.cta:
        parts.append("")
        parts.append(r.cta)

    full = "\n".join(parts).strip()
    if not full:
        f.write("_No message generated._\n")
        return

    # Render as a quoted block — easy to copy
    f.write("**Message to send:**\n\n")
    if r.subject:
        f.write(f"📧 **Subject:** {r.subject}\n\n")
    for line in full.splitlines():
        f.write(f"> {line}\n" if line else ">\n")
    f.write("\n")


def _section(
    records: list[OutreachRecord],
    priority: str,
    f: Any,
    include_skipped_list: bool = False,
) -> None:
    emoji = _PRIORITY_EMOJI.get(priority, "")
    filtered = [r for r in records if r.outreach_priority == priority]
    count = len(filtered)

    f.write(f"\n---\n\n## {emoji} {priority} ({count} leads)\n\n")

    if not filtered:
        f.write("_No leads in this category._\n")
        return

    # For SKIP, just list them without full message blocks
    if priority == "SKIP" and not include_skipped_list:
        f.write("These leads did not meet the threshold for outreach:\n\n")
        for r in filtered:
            name = r.business_name or r.lead_id
            reason = r.message_notes or "No outreach generated."
            f.write(f"- **{name}** — {reason}\n")
        f.write("\n")
        return

    for r in filtered:
        ch_emoji = _CHANNEL_EMOJI.get(r.recommended_channel, "")
        pot_emoji = _POTENTIAL_EMOJI.get(r.sales_potential, "")
        loc = f", {r.location}" if r.location else ""
        cat = f" · {r.category}" if r.category else ""

        f.write(f"### {r.business_name or r.lead_id}{loc}{cat}\n\n")

        # Summary table
        f.write("| Field | Value |\n")
        f.write("|---|---|\n")
        f.write(f"| **Potential** | {pot_emoji} {r.sales_potential} |\n")
        f.write(f"| **Channel** | {ch_emoji} {r.recommended_channel} |\n")
        f.write(f"| **Primary Service** | {r.primary_service} |\n")
        if r.phone:
            f.write(f"| **Phone** | `{r.phone}` |\n")
        f.write("\n")

        # Personalization points
        if r.personalization_points and not r.is_mock:
            f.write("**Why this message:**\n")
            for pt in r.personalization_points:
                f.write(f"- {pt}\n")
            f.write("\n")

        # The message itself
        if r.generation_error:
            f.write(f"⚠️ **Generation error:** `{r.generation_error}`\n\n")
        else:
            _render_message_box(r, f)

        # Internal notes
        if r.message_notes:
            f.write(f"💡 **Internal note:** {r.message_notes}\n\n")

        f.write("\n")


def write_report(
    path: Path,
    records: list[OutreachRecord],
    counts: dict[str, int],
    source_file: str,
    mock: bool = False,
) -> None:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    total = len(records)
    actionable = counts.get("CONTACT FIRST", 0) + counts.get("CONTACT LATER", 0)

    with path.open("w", encoding="utf-8") as f:
        f.write("# MalikAxiom Outreach Messages\n\n")

        if mock:
            f.write(
                "> ⚠️ **MOCK MODE** — Messages below are pipeline test placeholders. "
                "Run without `--mock` for real message generation.\n\n"
            )

        f.write(f"**Generated:** {now}  \n")
        f.write(f"**Source:** `{source_file}`  \n")
        f.write(f"**Total leads:** {total} | **Actionable:** {actionable}  \n\n")

        f.write(
            "> Messages are generated for **manual review and sending only**. "
            "No automated messaging is performed.\n\n"
        )

        # Summary table
        f.write("## Summary\n\n")
        f.write("| Priority | Count | What to do |\n")
        f.write("|---|---|---|\n")
        f.write(
            f"| 🔥 CONTACT FIRST | {counts.get('CONTACT FIRST', 0)} | "
            "Send message as soon as possible |\n"
        )
        f.write(
            f"| ⚡ CONTACT LATER | {counts.get('CONTACT LATER', 0)} | "
            "Send exploratory message when ready |\n"
        )
        f.write(
            f"| 🚫 SKIP | {counts.get('SKIP', 0)} | "
            "No outreach — insufficient opportunity or evidence |\n"
        )
        f.write("\n")

        # Outreach channel guide
        f.write("## Before You Send\n\n")
        f.write(
            "- Copy the message for the recommended channel.\n"
            "- Review the **Internal note** before sending.\n"
            "- Do not add promises of revenue, ROI, or guaranteed results.\n"
            "- Keep the first message focused on the **primary service only**.\n"
            "- Secondary services can be raised only if the conversation develops naturally.\n\n"
        )

        # CONTACT FIRST
        _section(records, "CONTACT FIRST", f)

        # CONTACT LATER
        _section(records, "CONTACT LATER", f)

        # SKIP (just a list, no message blocks)
        _section(records, "SKIP", f)

        f.write("\n---\n\n")
        f.write("_Report generated by **MalikAxiom Lead AI** — Milestone 4._  \n")
        f.write(
            "_All messages are based on publicly researched evidence only. "
            "No automated sending is performed._\n"
        )

    logger.info("Wrote Markdown report: %s", path)
