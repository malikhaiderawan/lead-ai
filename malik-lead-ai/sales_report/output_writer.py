"""Milestone 5 — Sales Report Output Writers.

Writes three output files from merged + audited lead records:

    output/malikaxiom_sales_leads.csv   — master spreadsheet (all leads, all columns)
    output/contact_first.csv            — CONTACT FIRST leads only, minimal columns
    output/malikaxiom_sales_summary.md  — human-readable prioritized summary

Optionally writes XLSX if openpyxl is available (no forced install).

Standard library only (XLSX optional).
"""

from __future__ import annotations

import csv
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"

# ---------------------------------------------------------------------------
# Master CSV columns (in display order)
# ---------------------------------------------------------------------------

MASTER_CSV_COLUMNS: list[str] = [
    "lead_id",
    "business_name",
    "business_type",
    "location",
    "phone",
    "mobile_phone",
    "whatsapp",
    "landline",
    "email",
    "website",
    "linkedin",
    "instagram",
    "facebook",
    "tiktok",
    "youtube",
    "research_status",
    "digital_maturity",
    "sales_potential",
    "confidence",
    "why_this_lead",
    "detected_opportunity",
    "primary_service",
    "primary_service_reason",
    "secondary_services",
    "outreach_priority",
    "outreach_channel",
    "outreach_angle",
    "personalization_points",
    "outreach_message",
    "message_notes",
    "final_action",
    "uncertainties",
    "review_flag",
    "review_reason",
    "possible_duplicate",
    "duplicate_reason",
    "contact_quality_issues",
    "report_timestamp",
]

CONTACT_FIRST_COLUMNS: list[str] = [
    "business_name",
    "location",
    "phone",
    "mobile_phone",
    "whatsapp",
    "landline",
    "email",
    "website",
    "linkedin",
    "instagram",
    "facebook",
    "tiktok",
    "youtube",
    "sales_potential",
    "primary_service",
    "why_this_lead",
    "outreach_channel",
    "outreach_message",
]

MANUAL_INSTAGRAM_COLUMNS: list[str] = [
    "business_name",
    "location",
    "instagram",
    "facebook",
    "sales_potential",
    "primary_service",
    "why_this_lead",
    "outreach_channel",
    "outreach_message",
    "manual_action_note",
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe(val: Any, default: str = "") -> str:
    if val is None:
        return default
    s = str(val).strip()
    return s if s and s.lower() not in ("null", "none") else default


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _bool_str(val: Any) -> str:
    return "yes" if val else "no"


def _row_for_master(rec: dict[str, Any], ts: str) -> dict[str, str]:
    row: dict[str, str] = {}
    for col in MASTER_CSV_COLUMNS:
        if col == "report_timestamp":
            row[col] = ts
        elif col in ("review_flag", "possible_duplicate"):
            row[col] = _bool_str(rec.get(col))
        else:
            row[col] = _safe(rec.get(col))
    return row


# ---------------------------------------------------------------------------
# Master CSV
# ---------------------------------------------------------------------------

def write_master_csv(path: Path, records: list[dict[str, Any]]) -> None:
    ts = _now_iso()
    rows = [_row_for_master(r, ts) for r in records]
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=MASTER_CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    logger.info(
        "Wrote master CSV: %s (%d rows, %d columns)",
        path, len(rows), len(MASTER_CSV_COLUMNS),
    )


# ---------------------------------------------------------------------------
# XLSX (optional — skip if openpyxl not available)
# ---------------------------------------------------------------------------

def write_xlsx_if_available(csv_path: Path, records: list[dict[str, Any]]) -> Path | None:
    """Attempt to write XLSX; silently return None if openpyxl is missing."""
    try:
        import openpyxl  # type: ignore
        from openpyxl.styles import Font, PatternFill, Alignment  # type: ignore
    except ImportError:
        logger.info("openpyxl not installed — XLSX output skipped (CSV is the primary output)")
        return None

    xlsx_path = csv_path.with_suffix(".xlsx")
    ts = _now_iso()

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "MalikAxiom Sales Leads"

    header_font  = Font(bold=True, color="FFFFFF")
    header_fill  = PatternFill("solid", fgColor="1F4E79")
    header_align = Alignment(horizontal="center", wrap_text=True)

    _priority_fill = {
        "CONTACT FIRST": PatternFill("solid", fgColor="C6EFCE"),
        "CONTACT LATER": PatternFill("solid", fgColor="FFEB9C"),
        "SKIP":          PatternFill("solid", fgColor="FFC7CE"),
    }

    ws.append(MASTER_CSV_COLUMNS)
    for cell in ws[1]:
        cell.font  = header_font
        cell.fill  = header_fill
        cell.alignment = header_align

    for rec in records:
        row = _row_for_master(rec, ts)
        ws.append([row[col] for col in MASTER_CSV_COLUMNS])
        priority = _safe(rec.get("outreach_priority"))
        if priority in _priority_fill:
            for cell in ws[ws.max_row]:
                cell.fill = _priority_fill[priority]

    # Auto-width (approximate)
    for col_idx, col_name in enumerate(MASTER_CSV_COLUMNS, 1):
        ws.column_dimensions[
            openpyxl.utils.get_column_letter(col_idx)
        ].width = min(max(len(col_name) + 4, 12), 50)

    wb.save(xlsx_path)
    logger.info("Wrote XLSX: %s", xlsx_path)
    return xlsx_path


# ---------------------------------------------------------------------------
# Contact-First CSV
# ---------------------------------------------------------------------------

def write_contact_first_csv(path: Path, records: list[dict[str, Any]]) -> int:
    """Write CONTACT FIRST leads only, minimal columns. Returns count."""
    cf_records = [r for r in records if r.get("outreach_priority") == "CONTACT FIRST"]
    if not cf_records:
        path.write_text(
            ",".join(CONTACT_FIRST_COLUMNS) + "\n", encoding="utf-8"
        )
        logger.info("contact_first.csv: 0 CONTACT FIRST leads")
        return 0

    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=CONTACT_FIRST_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for rec in cf_records:
            writer.writerow({col: _safe(rec.get(col)) for col in CONTACT_FIRST_COLUMNS})

    logger.info("Wrote contact_first.csv: %s (%d leads)", path, len(cf_records))
    return len(cf_records)


def write_contact_later_csv(path: Path, records: list[dict[str, Any]]) -> int:
    """Write CONTACT LATER leads only, minimal columns. Returns count."""
    cl_records = [r for r in records if r.get("outreach_priority") == "CONTACT LATER"]
    if not cl_records:
        path.write_text(
            ",".join(CONTACT_FIRST_COLUMNS) + "\n", encoding="utf-8"
        )
        logger.info("contact_later.csv: 0 CONTACT LATER leads")
        return 0

    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=CONTACT_FIRST_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for rec in cl_records:
            writer.writerow({col: _safe(rec.get(col)) for col in CONTACT_FIRST_COLUMNS})

    logger.info("Wrote contact_later.csv: %s (%d leads)", path, len(cl_records))
    return len(cl_records)


def write_manual_instagram_csv(path: Path, records: list[dict[str, Any]]) -> int:
    """Write leads that need manual Instagram DM / social outreach. Returns count."""
    manual_records = [
        r for r in records
        if _safe(r.get("outreach_channel")) in ("Instagram DM", "Facebook", "LinkedIn")
        or (not _safe(r.get("phone")) and not _safe(r.get("whatsapp")) and (_safe(r.get("instagram")) or _safe(r.get("facebook"))))
    ]
    if not manual_records:
        path.write_text(
            ",".join(MANUAL_INSTAGRAM_COLUMNS) + "\n", encoding="utf-8"
        )
        logger.info("manual_instagram_leads.csv: 0 manual social leads")
        return 0

    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=MANUAL_INSTAGRAM_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for rec in manual_records:
            channel = _safe(rec.get("outreach_channel"), "Instagram DM")
            row = {col: _safe(rec.get(col)) for col in MANUAL_INSTAGRAM_COLUMNS}
            row["manual_action_note"] = f"[{channel}] No direct phone found — Copy & send manually on {channel.split()[0]}."
            writer.writerow(row)

    logger.info("Wrote manual_instagram_leads.csv: %s (%d leads)", path, len(manual_records))
    return len(manual_records)



# ---------------------------------------------------------------------------
# Summary Markdown
# ---------------------------------------------------------------------------

_POTENTIAL_EMOJI = {"HIGH": "🔥", "MODERATE": "⚡", "LOW": "📋", "SKIP": "🚫"}
_PRIORITY_EMOJI  = {"CONTACT FIRST": "🔥", "CONTACT LATER": "⚡", "SKIP": "🚫"}
_CHANNEL_EMOJI   = {
    "WhatsApp": "📱", "Instagram DM": "📸",
    "Facebook": "💬", "Email": "📧",
    "Contact Form": "📝", "unknown": "❓",
}


def _summary_stats(records: list[dict[str, Any]]) -> dict[str, int]:
    s: dict[str, int] = {
        "total": len(records),
        "HIGH": 0, "MODERATE": 0, "LOW": 0, "SKIP": 0,
        "CONTACT FIRST": 0, "CONTACT LATER": 0,
        "RESEARCHED": 0, "PARTIALLY_RESEARCHED": 0,
        "UNREACHABLE": 0, "UNKNOWN_STATUS": 0,
        "review_flagged": 0, "possible_duplicates": 0,
    }
    for r in records:
        sp = _safe(r.get("sales_potential")).upper()
        if sp in s:
            s[sp] += 1
        op = _safe(r.get("outreach_priority"))
        if op in s:
            s[op] += 1
        rs = _safe(r.get("research_status")).upper()
        if rs == "RESEARCHED":
            s["RESEARCHED"] += 1
        elif rs == "PARTIALLY_RESEARCHED":
            s["PARTIALLY_RESEARCHED"] += 1
        elif rs == "UNREACHABLE":
            s["UNREACHABLE"] += 1
        else:
            s["UNKNOWN_STATUS"] += 1
        if r.get("review_flag"):
            s["review_flagged"] += 1
        if r.get("possible_duplicate"):
            s["possible_duplicates"] += 1
    return s


def _render_lead_block(f: Any, idx: int, rec: dict[str, Any]) -> None:
    name     = _safe(rec.get("business_name"), "Unknown")
    location = _safe(rec.get("location"))
    category = _safe(rec.get("business_type") or rec.get("category", ""))
    sp       = _safe(rec.get("sales_potential"))
    service  = _safe(rec.get("primary_service"))
    channel  = _safe(rec.get("outreach_channel"))
    phone    = _safe(rec.get("phone"))
    website  = _safe(rec.get("website"))
    why      = _safe(rec.get("why_this_lead"))
    priority = _safe(rec.get("outreach_priority"))
    review   = rec.get("review_flag", False)
    dup      = rec.get("possible_duplicate", False)

    loc_str = f", {location}" if location else ""
    cat_str = f" · {category}" if category else ""
    sp_em   = _POTENTIAL_EMOJI.get(sp, "")
    ch_em   = _CHANNEL_EMOJI.get(channel, "")

    f.write(f"### {idx}. {name}{loc_str}{cat_str}\n\n")
    f.write(f"| | |\n|---|---|\n")
    f.write(f"| **Potential** | {sp_em} {sp} |\n")
    f.write(f"| **Service** | {service} |\n")
    f.write(f"| **Channel** | {ch_em} {channel} |\n")
    if phone:
        f.write(f"| **Phone** | `{phone}` |\n")
    if _safe(rec.get("mobile_phone")):
        f.write(f"| **Mobile** | `{rec['mobile_phone']}` |\n")
    if _safe(rec.get("whatsapp")):
        f.write(f"| **WhatsApp** | `{rec['whatsapp']}` |\n")
    if _safe(rec.get("landline")):
        f.write(f"| **Landline** | `{rec['landline']}` |\n")
    if _safe(rec.get("email")):
        f.write(f"| **Email** | `{rec['email']}` |\n")
    if website:
        f.write(f"| **Website** | {website} |\n")
    if _safe(rec.get("instagram")):
        f.write(f"| **Instagram** | {rec['instagram']} |\n")
    if _safe(rec.get("facebook")):
        f.write(f"| **Facebook** | {rec['facebook']} |\n")
    if _safe(rec.get("linkedin")):
        f.write(f"| **LinkedIn** | {rec['linkedin']} |\n")
    if _safe(rec.get("tiktok")):
        f.write(f"| **TikTok** | {rec['tiktok']} |\n")
    if _safe(rec.get("youtube")):
        f.write(f"| **YouTube** | {rec['youtube']} |\n")
    f.write(f"| **Action** | **{priority}** |\n")
    f.write("\n")

    if why:
        f.write(f"> {why}\n\n")

    if review:
        reason = _safe(rec.get("review_reason"))
        f.write(f"⚠️ **Review flag:** {reason}\n\n")

    if dup:
        dup_reason = _safe(rec.get("duplicate_reason"))
        f.write(f"🔁 **Possible duplicate:** {dup_reason}\n\n")

    f.write("\n")


def write_summary_markdown(
    path: Path,
    records: list[dict[str, Any]],
    audit_counts: dict[str, int],
    source_info: str = "",
) -> None:
    stats = _summary_stats(records)
    now   = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    contact_first  = [r for r in records if r.get("outreach_priority") == "CONTACT FIRST"]
    contact_later  = [r for r in records if r.get("outreach_priority") == "CONTACT LATER"]
    skipped        = [r for r in records if r.get("outreach_priority") == "SKIP"]

    with path.open("w", encoding="utf-8") as f:
        f.write("# MalikAxiom Sales Leads — Summary\n\n")
        f.write(f"**Generated:** {now}  \n")
        if source_info:
            f.write(f"**Source:** {source_info}  \n")
        f.write("\n")

        f.write("> Messages are for **manual review and sending only**. "
                "No automated messaging is performed.\n\n")

        # Stats block
        f.write("## Pipeline Stats\n\n")
        f.write("```\n")
        f.write(f"Total leads processed   : {stats['total']}\n")
        f.write(f"Research completed      : {stats['RESEARCHED']}\n")
        f.write(f"Research partial        : {stats['PARTIALLY_RESEARCHED']}\n")
        f.write(f"Research unreachable    : {stats['UNREACHABLE']}\n")
        f.write(f"Research unknown        : {stats['UNKNOWN_STATUS']}\n")
        f.write("\n")
        f.write(f"Sales Potential:\n")
        f.write(f"  HIGH     : {stats['HIGH']}\n")
        f.write(f"  MODERATE : {stats['MODERATE']}\n")
        f.write(f"  LOW      : {stats['LOW']}\n")
        f.write(f"  SKIP     : {stats['SKIP']}\n")
        f.write("\n")
        f.write(f"Outreach Priority:\n")
        f.write(f"  CONTACT FIRST  : {stats['CONTACT FIRST']}\n")
        f.write(f"  CONTACT LATER  : {stats['CONTACT LATER']}\n")
        f.write("\n")
        f.write(f"Quality flags:\n")
        f.write(f"  Review flags       : {stats['review_flagged']}\n")
        f.write(f"  Possible duplicates: {stats['possible_duplicates']}\n")
        f.write("```\n\n")

        # CONTACT FIRST
        f.write(f"---\n\n## 🔥 CONTACT FIRST ({len(contact_first)} leads)\n\n")
        if contact_first:
            f.write("These are your highest-priority leads. Start here.\n\n")
            for i, rec in enumerate(contact_first, 1):
                _render_lead_block(f, i, rec)
        else:
            f.write("_No CONTACT FIRST leads._\n\n")

        # CONTACT LATER
        f.write(f"---\n\n## ⚡ CONTACT LATER ({len(contact_later)} leads)\n\n")
        if contact_later:
            f.write("These leads have potential but need more verification or have weaker evidence.\n\n")
            for i, rec in enumerate(contact_later, 1):
                _render_lead_block(f, i, rec)
        else:
            f.write("_No CONTACT LATER leads._\n\n")

        # SKIP — compact list only
        f.write(f"---\n\n## 🚫 SKIP ({len(skipped)} leads)\n\n")
        if skipped:
            f.write(
                "These leads do not currently meet the outreach threshold. "
                "No message generated.\n\n"
            )
            for rec in skipped:
                name = _safe(rec.get("business_name"), rec.get("lead_id", "?"))
                loc  = _safe(rec.get("location"))
                sp   = _safe(rec.get("sales_potential"))
                loc_str = f", {loc}" if loc else ""
                f.write(f"- **{name}{loc_str}** — {sp} potential\n")
            f.write("\n")
        else:
            f.write("_No leads in SKIP category._\n\n")

        # Review flags summary
        flagged = [r for r in records if r.get("review_flag")]
        if flagged:
            f.write(f"---\n\n## ⚠️ Review Flags ({len(flagged)})\n\n")
            f.write("These leads have been automatically flagged for human review. "
                    "The qualification decision has NOT been changed — review manually.\n\n")
            for rec in flagged:
                name   = _safe(rec.get("business_name"), rec.get("lead_id", "?"))
                reason = _safe(rec.get("review_reason"))
                f.write(f"- **{name}**: {reason}\n")
            f.write("\n")

        # Duplicates summary
        dups = [r for r in records if r.get("possible_duplicate")]
        if dups:
            f.write(f"---\n\n## 🔁 Possible Duplicates ({len(dups)})\n\n")
            f.write("Review these leads manually before sending outreach. "
                    "Leads are NOT automatically removed.\n\n")
            for rec in dups:
                name   = _safe(rec.get("business_name"), rec.get("lead_id", "?"))
                reason = _safe(rec.get("duplicate_reason"))
                f.write(f"- **{name}**: {reason}\n")
            f.write("\n")

        f.write("---\n\n")
        f.write("_Report generated by **MalikAxiom Lead AI** — Milestone 5._  \n")
        f.write(
            "_All qualification and outreach decisions are based on publicly available "
            "research data only. No revenue, profit, or ROI is guaranteed._\n"
        )

    logger.info("Wrote summary Markdown: %s", path)


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def run_sales_report(
    output_dir: Path | None = None,
) -> tuple[Path, Path, Path, Path | None, int, dict[str, int]]:
    """
    Load merged pipeline outputs, run audit, write all sales report files.

    Returns:
        (master_csv, contact_first_csv, summary_md, xlsx_path_or_None,
         total, audit_counts)

    Raises:
        FileNotFoundError if M3 qualification results are missing.
    """
    from .merger  import merge_pipeline_outputs
    from .auditor import audit_leads
    from .mega_archive import update_mega_archives

    out = output_dir or OUTPUT_DIR
    out.mkdir(parents=True, exist_ok=True)

    logger.info("Loading and merging pipeline outputs from: %s", out)
    records = merge_pipeline_outputs(out)

    if not records:
        logger.warning("No records found — sales report will be empty")

    logger.info("Running audit on %d records...", len(records))
    audit_counts = audit_leads(records)

    master_csv            = out / "malikaxiom_sales_leads.csv"
    contact_first_csv     = out / "contact_first.csv"
    contact_later_csv     = out / "contact_later.csv"
    manual_instagram_csv  = out / "manual_instagram_leads.csv"
    summary_md            = out / "malikaxiom_sales_summary.md"

    write_master_csv(master_csv, records)
    cf_count = write_contact_first_csv(contact_first_csv, records)
    cl_count = write_contact_later_csv(contact_later_csv, records)
    ig_count = write_manual_instagram_csv(manual_instagram_csv, records)
    write_summary_markdown(
        summary_md,
        records,
        audit_counts,
        source_info=str(out),
    )

    xlsx_path = write_xlsx_if_available(master_csv, records)

    # Update Mega Cumulative Archives & Batch Snapshots
    batch_src = Path(records[0].get("source_file", "leads.csv")).name if records else "leads.csv"
    mega_info = update_mega_archives(out, records, batch_source=batch_src)

    logger.info(
        "Sales report complete: %d total, %d CONTACT FIRST, %d CONTACT LATER, %d review flags, %d duplicates",
        len(records),
        cf_count,
        cl_count,
        audit_counts.get("review_flagged", 0),
        audit_counts.get("possible_duplicates", 0),
    )

    return master_csv, contact_first_csv, summary_md, xlsx_path, len(records), audit_counts

