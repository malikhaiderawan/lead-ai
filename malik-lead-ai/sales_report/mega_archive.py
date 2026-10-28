"""Milestone 5 — Mega Archive & Batch Snapshot Manager.

Maintains cumulative lead archives across all pipeline runs:
    output/mega_contact_first.csv       — All CONTACT FIRST leads ever processed (with call status & notes)
    output/mega_contact_later.csv       — All CONTACT LATER leads ever processed
    output/mega_cold_calling_leads.xlsx — Multi-tab calling workbook (Mega Contact First, Mega Contact Later, Call Sheet)
    output/batches/                     — Batch snapshots for every individual run

Deduplication:
    Keyed by normalized phone number (or clean business name + location if phone is missing).
    Preserves user call_status and call_notes across multiple runs.
"""

from __future__ import annotations

import csv
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from qualification.qualifier import _is_known_enterprise_brand

logger = logging.getLogger(__name__)

MEGA_COLUMNS: list[str] = [
    "lead_id",
    "business_name",
    "phone",
    "mobile_phone",
    "whatsapp",
    "category",
    "location",
    "sales_action",
    "sales_potential",
    "primary_service",
    "cold_call_pitch_hook",
    "why_this_lead",
    "outreach_channel",
    "outreach_message",
    "call_status",
    "call_notes",
    "batch_source",
    "date_added",
    "google_rating",
    "google_reviews",
    "website",
    "google_maps_url",
]


def _safe_str(val: Any, default: str = "") -> str:
    if val is None:
        return default
    s = str(val).strip()
    return s if s and s.lower() not in ("null", "none") else default


def _normalize_phone_key(phone: str | None) -> str:
    if not phone:
        return ""
    digits = re.sub(r"\D", "", phone)
    if digits.startswith("92") and len(digits) >= 11:
        return digits[-10:]
    if digits.startswith("0") and len(digits) >= 10:
        return digits[-10:]
    return digits


def _get_lead_dedup_key(rec: dict[str, Any]) -> str:
    phone = _safe_str(rec.get("phone") or rec.get("whatsapp") or rec.get("mobile_phone"))
    norm_phone = _normalize_phone_key(phone)
    if norm_phone:
        return f"phone:{norm_phone}"
    name = _safe_str(rec.get("business_name")).lower()
    clean_name = re.sub(r"[^\w\s]", "", name)
    loc = _safe_str(rec.get("location")).lower()
    return f"name:{clean_name}|{loc}"


def _generate_pitch_hook(rec: dict[str, Any]) -> str:
    name = _safe_str(rec.get("business_name"), "Business")
    raw_cat = _safe_str(rec.get("business_type") or rec.get("category") or rec.get("business_category"), "").split(",")[0].strip()
    name_lower = name.lower()

    if not raw_cat or raw_cat.lower() in ("unknown", "n/a", "none", "", "business", "brand"):
        if any(k in name_lower for k in ("clothing", "cloth", "boutique", "fashion", "garment", "wear", "suit", "couture", "pret", "tailor", "collection", "fabrics", "shoes", "leather", "jewelry", "jeweller", "store", "shop")):
            cat = "clothing"
        elif any(k in name_lower for k in ("clinic", "dental", "dentist", "doctor", "hospital", "physio", "derma", "health", "medical")):
            cat = "clinic"
        elif any(k in name_lower for k in ("restaurant", "cafe", "food", "bakery", "bistro", "pizza", "burger", "grill")):
            cat = "restaurant"
        elif any(k in name_lower for k in ("salon", "spa", "beauty", "parlour", "barber")):
            cat = "salon"
        else:
            cat = "retail"
    else:
        cat = raw_cat

    cat_lower = cat.lower()
    site_val = str(rec.get("website") or "").strip().lower()
    has_site = bool(site_val and site_val not in ("none", "null", "n/a", "") and not any(s in site_val for s in ("facebook.com", "instagram.com", "fb.me", "tiktok.com")))

    # Retail / Clothing / Fashion / Shoes / Jewelry / Products
    if any(k in cat_lower for k in ("clothing", "cloth", "boutique", "fashion", "garment", "wear", "shoes", "leather", "jewelry", "jeweller", "store", "shop", "retail", "brand")):
        if not has_site:
            return f"We help clothing and retail brands convert their social media followers into automated online orders with a custom storefront & WhatsApp checkout."
        return f"We help retail and clothing stores add automated product catalogs and 1-click WhatsApp ordering to increase direct sales."

    # Healthcare / Clinics / Doctors / Dental
    if any(k in cat_lower for k in ("clinic", "doctor", "dental", "dentist", "hospital", "physio", "derma", "health", "medical")):
        if not has_site:
            return f"We help medical practices and clinics establish a trusted Google & mobile presence with instant WhatsApp appointment booking."
        return f"We help medical clinics optimize their online patient booking flow and local Google ranking."

    # Food / Cafe / Restaurant / Bakery
    if any(k in cat_lower for k in ("restaurant", "cafe", "food", "bakery", "bistro", "pizza", "burger", "grill")):
        return f"We help food and dining businesses set up direct digital menus and WhatsApp ordering to eliminate high delivery aggregator commissions."

    # Salon / Spa / Beauty
    if any(k in cat_lower for k in ("salon", "spa", "beauty", "parlour", "barber")):
        return f"We help salons and beauty studios automate customer appointment bookings and showcase client transformations on mobile."

    # General / Default
    clean_cat = cat if not cat.lower().endswith("business") else cat[:-8].strip()
    clean_cat = clean_cat or "local"
    if not has_site:
        return f"We help {clean_cat} businesses launch a high-converting digital storefront and professional Google presence starting from PKR 10,000."
    return f"We help {clean_cat} businesses upgrade their digital presence with AI brand assistance and 24/7 customer capture."


def _load_existing_mega(csv_path: Path) -> tuple[list[dict[str, str]], dict[str, dict[str, str]]]:
    if not csv_path.is_file():
        return [], {}
    rows: list[dict[str, str]] = []
    lookup: dict[str, dict[str, str]] = {}
    with csv_path.open("r", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for r in reader:
            rows.append(r)
            k = _get_lead_dedup_key(r)
            if k:
                lookup[k] = r
    return rows, lookup


def update_mega_archives(
    output_dir: Path,
    current_records: list[dict[str, Any]],
    batch_source: str = "clinics.csv",
) -> dict[str, Any]:
    """
    Update Mega CSVs and Batch snapshots.
    Preserves existing user call statuses/notes.
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    batches_dir = out / "batches"
    batches_dir.mkdir(parents=True, exist_ok=True)

    now_ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    file_ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    clean_batch_name = Path(batch_source).stem if batch_source else "leads"

    # Separate current batch
    cf_current = [r for r in current_records if r.get("outreach_priority") == "CONTACT FIRST"]
    cl_current = [r for r in current_records if r.get("outreach_priority") == "CONTACT LATER"]

    # 1. Write Batch Snapshots
    batch_cf_csv = batches_dir / f"contact_first_{clean_batch_name}_{file_ts}.csv"
    batch_cl_csv = batches_dir / f"contact_later_{clean_batch_name}_{file_ts}.csv"
    batch_all_csv = batches_dir / f"master_batch_{clean_batch_name}_{file_ts}.csv"

    _write_simple_csv(batch_cf_csv, cf_current, batch_source, now_ts)
    _write_simple_csv(batch_cl_csv, cl_current, batch_source, now_ts)
    _write_simple_csv(batch_all_csv, current_records, batch_source, now_ts)
    logger.info("Saved batch snapshots (contact_first, contact_later, master) in %s", batches_dir)

    # 2. Update Mega Contact First
    mega_cf_path = out / "mega_contact_first.csv"
    existing_cf_rows, cf_lookup = _load_existing_mega(mega_cf_path)

    updated_cf_rows = list(existing_cf_rows)
    for rec in cf_current:
        k = _get_lead_dedup_key(rec)
        if k in cf_lookup:
            # Preserve call_status & call_notes, update missing info
            old = cf_lookup[k]
            old["why_this_lead"] = _safe_str(rec.get("why_this_lead")) or old.get("why_this_lead", "")
            old["outreach_message"] = _safe_str(rec.get("outreach_message")) or old.get("outreach_message", "")
        else:
            new_row = _build_mega_row(rec, "CONTACT FIRST", batch_source, now_ts)
            updated_cf_rows.append(new_row)
            cf_lookup[k] = new_row

    # Ensure no enterprise/national brands persist in mega contact first
    updated_cf_rows = [r for r in updated_cf_rows if not _is_known_enterprise_brand(r.get("business_name"))]

    _write_mega_csv(mega_cf_path, updated_cf_rows)

    # 3. Update Mega Contact Later
    mega_cl_path = out / "mega_contact_later.csv"
    existing_cl_rows, cl_lookup = _load_existing_mega(mega_cl_path)

    updated_cl_rows = list(existing_cl_rows)
    for rec in cl_current:
        k = _get_lead_dedup_key(rec)
        if k in cl_lookup:
            old = cl_lookup[k]
            old["why_this_lead"] = _safe_str(rec.get("why_this_lead")) or old.get("why_this_lead", "")
        else:
            new_row = _build_mega_row(rec, "CONTACT LATER", batch_source, now_ts)
            updated_cl_rows.append(new_row)
            cl_lookup[k] = new_row

    _write_mega_csv(mega_cl_path, updated_cl_rows)

    # 4. Generate Mega Cold Calling Excel Workbook
    mega_xlsx_path = out / "mega_cold_calling_leads.xlsx"
    _export_mega_excel(mega_xlsx_path, updated_cf_rows, updated_cl_rows)

    return {
        "mega_contact_first_count": len(updated_cf_rows),
        "mega_contact_later_count": len(updated_cl_rows),
        "batch_cf_path": str(batch_cf_csv),
        "mega_xlsx_path": str(mega_xlsx_path),
    }


def _build_mega_row(
    rec: dict[str, Any],
    action: str,
    batch_source: str,
    date_added: str,
) -> dict[str, str]:
    return {
        "lead_id": _safe_str(rec.get("lead_id")),
        "business_name": _safe_str(rec.get("business_name")),
        "phone": _safe_str(rec.get("phone")),
        "mobile_phone": _safe_str(rec.get("mobile_phone")),
        "whatsapp": _safe_str(rec.get("whatsapp")),
        "category": _safe_str(rec.get("category")),
        "location": _safe_str(rec.get("location")),
        "sales_action": action,
        "sales_potential": _safe_str(rec.get("sales_potential")),
        "primary_service": _safe_str(rec.get("primary_service")),
        "cold_call_pitch_hook": _generate_pitch_hook(rec),
        "why_this_lead": _safe_str(rec.get("why_this_lead")),
        "outreach_channel": _safe_str(rec.get("outreach_channel")),
        "outreach_message": _safe_str(rec.get("outreach_message")),
        "call_status": "PENDING",
        "call_notes": "",
        "batch_source": batch_source,
        "date_added": date_added,
        "google_rating": _safe_str(rec.get("google_rating")),
        "google_reviews": _safe_str(rec.get("google_reviews")),
        "website": _safe_str(rec.get("website")),
        "google_maps_url": _safe_str(rec.get("google_maps_url")),
    }


def _write_simple_csv(path: Path, records: list[dict[str, Any]], batch_source: str, now_ts: str) -> None:
    rows = [_build_mega_row(r, _safe_str(r.get("outreach_priority")), batch_source, now_ts) for r in records]
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=MEGA_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _write_mega_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=MEGA_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    logger.info("Updated mega CSV: %s (%d total records)", path, len(rows))


def _export_mega_excel(
    xlsx_path: Path,
    cf_rows: list[dict[str, str]],
    cl_rows: list[dict[str, str]],
) -> None:
    try:
        import openpyxl
        from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
        from openpyxl.utils import get_column_letter
    except ImportError:
        logger.info("openpyxl not available — mega Excel skipped")
        return

    wb = openpyxl.Workbook()
    # Remove default sheet
    wb.remove(wb.active)

    font_header = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    fill_header_cf = PatternFill("solid", fgColor="1B365D")  # Navy Blue
    fill_header_cl = PatternFill("solid", fgColor="4B6F96")  # Steel Blue

    thin_border = Border(
        left=Side(style="thin", color="D9D9D9"),
        right=Side(style="thin", color="D9D9D9"),
        top=Side(style="thin", color="D9D9D9"),
        bottom=Side(style="thin", color="D9D9D9"),
    )

    cold_call_cols = [
        ("business_name", "Business / Doctor Name", 30),
        ("phone", "Phone Number", 22),
        ("call_status", "Call Status (Select/Edit)", 18),
        ("call_notes", "Call Notes & Objections", 35),
        ("cold_call_pitch_hook", "Quick Pitch Hook (Read this)", 45),
        ("primary_service", "Service", 22),
        ("category", "Category", 22),
        ("location", "Location / Area", 25),
        ("google_rating", "Rating", 10),
        ("google_reviews", "Reviews", 10),
        ("batch_source", "Batch Source", 16),
        ("date_added", "Date Added", 18),
    ]

    # --- Sheet 1: 🔥 Mega Contact First ---
    ws_cf = wb.create_sheet(title="🔥 Mega Contact First")
    ws_cf.views.sheetView[0].showGridLines = True

    ws_cf.append([col[1] for col in cold_call_cols])
    for col_idx, cell in enumerate(ws_cf[1], 1):
        cell.font = font_header
        cell.fill = fill_header_cf
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    for row_data in cf_rows:
        row_vals = [row_data.get(col[0], "") for col in cold_call_cols]
        ws_cf.append(row_vals)
        cur_row = ws_cf.max_row
        for col_idx, cell in enumerate(ws_cf[cur_row], 1):
            cell.border = thin_border
            cell.alignment = Alignment(vertical="center")
            if cold_call_cols[col_idx - 1][0] == "call_status":
                cell.font = Font(name="Calibri", size=11, bold=True, color="C00000")
                cell.alignment = Alignment(horizontal="center", vertical="center")

    for col_idx, col_info in enumerate(cold_call_cols, 1):
        ws_cf.column_dimensions[get_column_letter(col_idx)].width = col_info[2]

    # --- Sheet 2: ⚡ Mega Contact Later ---
    ws_cl = wb.create_sheet(title="⚡ Mega Contact Later")
    ws_cl.views.sheetView[0].showGridLines = True

    ws_cl.append([col[1] for col in cold_call_cols])
    for col_idx, cell in enumerate(ws_cl[1], 1):
        cell.font = font_header
        cell.fill = fill_header_cl
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    for row_data in cl_rows:
        row_vals = [row_data.get(col[0], "") for col in cold_call_cols]
        ws_cl.append(row_vals)
        cur_row = ws_cl.max_row
        for col_idx, cell in enumerate(ws_cl[cur_row], 1):
            cell.border = thin_border
            cell.alignment = Alignment(vertical="center")

    for col_idx, col_info in enumerate(cold_call_cols, 1):
        ws_cl.column_dimensions[get_column_letter(col_idx)].width = col_info[2]

    wb.save(xlsx_path)
    logger.info("Saved Mega Cold Calling Excel: %s", xlsx_path)
