"""Milestone 2 — Lead input loader with flexible column-name mapping."""

from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Standardized 22 columns in exact target order
STANDARDIZED_COLUMNS: tuple[str, ...] = (
    "business_name",
    "phone",
    "website_phones",
    "email",
    "website",
    "facebook",
    "instagram",
    "linkedin",
    "twitter",
    "whatsapp",
    "youtube",
    "tiktok",
    "address",
    "category",
    "rating",
    "reviews",
    "hours",
    "latitude",
    "longitude",
    "place_id",
    "cid",
    "google_maps_url",
)

# Each concept accepts these column name variants (case-insensitive, trimmed).
COLUMN_MAPPING: dict[str, tuple[str, ...]] = {
    "business_name": ("business_name", "title", "business", "name", "company", "store_name", "shop_name", "brand_name"),
    "phone": ("phone", "phone_number", "contact", "telephone", "gen_phone", "google phones", "google_phones", "phones", "contact_number", "whatsapp_number", "whatsapp_phone", "wa_number"),
    "website_phones": ("website_phones", "website phones", "web_phone", "web_phones"),
    "email": ("email", "emails", "email_address", "contact_email", "mail", "email_addresses"),
    "website": ("website", "site", "url", "website_url", "web_url"),
    "facebook": ("facebook", "facebook_url", "fb", "fb_url", "facebook_link"),
    "instagram": ("instagram", "instagram_url", "instagram_handle", "ig", "instagram_link"),
    "linkedin": ("linkedin", "linkedin_url", "linkedin_page", "linkedin_link"),
    "twitter": ("twitter", "twitter_url", "x", "x_url", "twitter_handle"),
    "whatsapp": ("whatsapp", "wa", "whatsapp_number", "whatsapp_phone", "wa_number"),
    "youtube": ("youtube", "youtube_url", "youtube_channel", "yt", "youtube_page", "youtube_link"),
    "tiktok": ("tiktok", "tiktok_url", "tiktok_handle", "tiktok_link"),
    "address": ("complete_address", "address", "location", "city", "town", "street_address", "plus_code"),
    "category": ("category", "business_category", "type", "categories", "industry"),
    "rating": ("review_rating", "rating", "google_rating", "stars", "star_rating"),
    "reviews": ("review_count", "reviews", "google_reviews", "reviews_count", "total_reviews"),
    "hours": ("open_hours", "hours", "popular_times", "operating_hours", "business_hours", "timezone"),
    "latitude": ("latitude", "lat"),
    "longitude": ("longitude", "lng", "long", "lon"),
    "place_id": ("place_id", "data_id"),
    "cid": ("cid", "input_id"),
    "google_maps_url": ("link", "google_maps_url", "maps_url", "maps", "maps url", "google maps url", "street_view_url", "reviews_link"),
    "mobile_phone": ("mobile_phone", "mobile", "mobile_number", "cell", "cell_phone"),
    "landline": ("landline", "landline_number", "office_phone", "fixed_line"),
}

# First/normalized name for each concept (used as output field name).
CONCEPT_KEYS: tuple[str, ...] = tuple(COLUMN_MAPPING.keys())


def _normalize_header(value: str) -> str:
    """Normalize a CSV header for fuzzy matching."""
    return value.strip().lower().replace("\ufeff", "").replace(" ", "_").replace("-", "_")


def _find_column(headers: list[str], variants: tuple[str, ...]) -> str | None:
    """Return the actual header for a concept, or None if absent."""
    normalized: dict[str, str] = {_normalize_header(h): h for h in headers}
    for variant in variants:
        norm_var = _normalize_header(variant)
        if norm_var in normalized:
            return normalized[norm_var]
    return None


def load_leads(csv_path: Path | str) -> list[dict[str, Any]]:
    """
    Load leads from a CSV file.

    Returns a list of dicts, each with:
      - ``raw``: the original row (all columns, trimmed)
      - ``name``: the resolved business name (or None)
      - ``source_column_map``: which actual header was used per concept
    """
    path = Path(csv_path)
    if not path.is_file():
        raise FileNotFoundError(f"Input CSV not found: {path}")

    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        if not reader.fieldnames:
            raise ValueError(f"CSV has no header row: {path}")

        headers: list[str] = list(reader.fieldnames)
        mappings: dict[str, str | None] = {
            concept: _find_column(headers, variants)
            for concept, variants in COLUMN_MAPPING.items()
        }

    logger.info("Loaded CSV %s with %d columns: %s", path.name, len(headers), headers)

    leads: list[dict[str, Any]] = []
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row_number, row in enumerate(reader, start=2):  # 1 is header
            raw: dict[str, str] = {}
            for key, value in row.items():
                if key is None:
                    continue
                val_str = ", ".join(str(v) for v in value if v) if isinstance(value, list) else (str(value) if value is not None else "")
                raw[str(key).strip()] = val_str.strip()

            lead: dict[str, Any] = {
                "raw": raw,
                "row_number": row_number,
                "source_file": str(path),
                "source_column_map": {
                    concept: mappings[concept] for concept in CONCEPT_KEYS
                },
            }
            leads.append(lead)

    return leads


def resolve_name(lead: dict[str, Any]) -> str | None:
    """Return a display name for progress output; prefers business_name."""
    raw = lead.get("raw", {})
    source_map = lead.get("source_column_map", {})
    actual = source_map.get("business_name")
    if actual and actual in raw and raw[actual].strip():
        return raw[actual].strip()
    # Fallback to direct raw key inspection
    for key in ("business_name", "title", "business", "name", "company"):
        for rk, rv in raw.items():
            if _normalize_header(rk) == key and rv and rv.strip():
                return rv.strip()
    return None


def normalize_csv(input_path: Path | str, output_path: Path | str | None = None) -> Path:
    """
    Read any CSV (raw scraper output or custom format) and produce a standardized CSV
    with the exact 22 columns in fixed order:
      business_name,phone,website_phones,email,website,facebook,instagram,linkedin,
      twitter,whatsapp,youtube,tiktok,address,category,rating,reviews,hours,latitude,
      longitude,place_id,cid,google_maps_url
    """
    import re

    in_path = Path(input_path)
    if not in_path.is_file():
        raise FileNotFoundError(f"Input CSV not found: {in_path}")

    out_path = Path(output_path) if output_path else in_path

    with in_path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        if not reader.fieldnames:
            raise ValueError(f"CSV has no header row: {in_path}")
        headers = list(reader.fieldnames)
        mappings = {
            col: _find_column(headers, COLUMN_MAPPING.get(col, (col,)))
            for col in STANDARDIZED_COLUMNS
        }
        rows = list(reader)

    standardized_rows: list[dict[str, str]] = []
    for row in rows:
        std_row: dict[str, str] = {}
        for col in STANDARDIZED_COLUMNS:
            actual_hdr = mappings.get(col)
            val = ""
            if actual_hdr and actual_hdr in row:
                val = str(row[actual_hdr] or "").strip()
            # Special extraction fallbacks if empty
            if not val:
                if col == "whatsapp":
                    for fallback_hdr in ("order_online", "reservations"):
                        fb_val = str(row.get(fallback_hdr) or "")
                        if "wa.me/" in fb_val or "whatsapp" in fb_val:
                            m = re.search(r'https?://wa\.me/(\+?\d+)', fb_val)
                            if m:
                                val = m.group(1)
                                break
                elif col == "business_name":
                    for fallback_hdr in ("title", "name", "business", "company"):
                        if fallback_hdr in row and row[fallback_hdr]:
                            val = str(row[fallback_hdr]).strip()
                            break
            std_row[col] = val
        standardized_rows.append(std_row)

    with out_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(STANDARDIZED_COLUMNS))
        writer.writeheader()
        writer.writerows(standardized_rows)

    logger.info("Standardized CSV saved to: %s (%d rows)", out_path, len(standardized_rows))
    return out_path
