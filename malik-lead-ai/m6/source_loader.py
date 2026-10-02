"""M6 — M5 output loader.

M6's single source of truth for *which* lead may be contacted, *what* the
opportunity is, and *what service* to mention is M5's final report:

    output/malikaxiom_sales_leads.csv   (master, has lead_id — preferred)
    output/contact_first.csv            (fallback; lead_id derived stably)

M6 never re-scores, re-qualifies, or re-composes outreach. It only reads.
"""

from __future__ import annotations

import csv
import logging
import re
from pathlib import Path

from .config import (
    DEFAULT_OUTPUT_DIR,
    M5_CONTACT_FIRST_CSV,
    M5_MASTER_CSV,
    PROJECT_ROOT,
)
from .models import M5Lead
from .phone import split_phone_candidates, normalize_pakistani_mobile

logger = logging.getLogger(__name__)

# Columns M6 expects from M5 (informational — missing ones become '').
EXPECTED_M5_COLUMNS: tuple[str, ...] = (
    "lead_id", "business_name", "business_type", "location",
    "phone", "mobile_phone", "whatsapp", "landline", "email", "website",
    "linkedin", "instagram", "facebook", "tiktok", "youtube",
    "research_status", "digital_maturity", "sales_potential", "confidence",
    "why_this_lead", "detected_opportunity", "primary_service",
    "primary_service_reason", "secondary_services",
    "outreach_priority", "outreach_channel", "outreach_angle",
    "personalization_points", "outreach_message", "message_notes",
    "final_action", "uncertainties", "review_flag", "review_reason",
    "possible_duplicate", "duplicate_reason", "contact_quality_issues",
    "report_timestamp",
)

# Columns without which M6 cannot decide anything (unless the file is M5's
# contact_first.csv working list, whose rows are CONTACT FIRST by definition).
_REQUIRED_ANY: tuple[tuple[str, ...], ...] = (
    ("business_name",),
    ("final_action", "outreach_priority"),
)


class M5SourceError(RuntimeError):
    """M6 cannot find or read a usable M5 output file."""


def resolve_source_path(output_dir: Path | None = None, source: str | Path | None = None) -> Path:
    """Return the M5 file M6 should read.

    Priority: explicit --source (CWD → project root → output dir) → master CSV
    in the output dir → contact_first.csv in the output dir.
    """
    out_dir = output_dir or DEFAULT_OUTPUT_DIR
    if source:
        given = Path(source)
        candidates = [given] if given.is_absolute() else [
            Path.cwd() / given,
            PROJECT_ROOT / given,
            out_dir.parent / given,
            out_dir / given,
        ]
        for candidate in candidates:
            if candidate.is_file():
                return candidate
        raise M5SourceError(f"M5 source file not found: {source}")

    master = out_dir / M5_MASTER_CSV
    if master.is_file():
        return master
    fallback = out_dir / M5_CONTACT_FIRST_CSV
    if fallback.is_file():
        logger.warning(
            "M5 master CSV not found; falling back to %s (no lead_id column — "
            "stable ids will be derived from business name + phone)",
            fallback.name,
        )
        return fallback

    # Custom output dir given but M5 files live in the project output/ dir.
    if out_dir.resolve() != DEFAULT_OUTPUT_DIR.resolve():
        project_master = DEFAULT_OUTPUT_DIR / M5_MASTER_CSV
        if project_master.is_file():
            logger.info("Using M5 output from %s", project_master)
            return project_master
        project_fallback = DEFAULT_OUTPUT_DIR / M5_CONTACT_FIRST_CSV
        if project_fallback.is_file():
            return project_fallback

    raise M5SourceError(
        f"No M5 output found in {out_dir} or {DEFAULT_OUTPUT_DIR}. Expected "
        f"'{M5_MASTER_CSV}' or '{M5_CONTACT_FIRST_CSV}'.\n"
        "Run 'python3 main.py sales-report' first."
    )


def _slug(text: str, max_len: int = 40) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", (text or "").lower()).strip("_")
    return slug[:max_len].strip("_") or "unknown"


def derive_lead_id(business_name: str, phone: str) -> str:
    """Stable fallback id for M5 files that do not carry lead_id."""
    digits = ""
    for candidate in split_phone_candidates(phone or ""):
        e164, _reason = normalize_pakistani_mobile(candidate)
        if e164:
            digits = e164.lstrip("+")
            break
    suffix = digits[-6:] if digits else "nonum"
    return f"m5_{_slug(business_name)}_{suffix}"


def _load_rows(path: Path) -> list[dict[str, str]]:
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            return [
                {str(k).strip(): ("" if v is None else str(v)) for k, v in row.items() if k}
                for row in csv.DictReader(handle)
            ]
    except Exception as exc:  # noqa: BLE001
        raise M5SourceError(f"Failed to read M5 output {path}: {exc}") from exc


def _is_contact_first_list(path: Path, columns: set[str]) -> bool:
    """True for M5's contact_first.csv working list (CONTACT FIRST rows only)."""
    return path.name == M5_CONTACT_FIRST_CSV or (
        "outreach_channel" in columns and "why_this_lead" in columns
        and "final_action" not in columns and "outreach_priority" not in columns
    )


def load_m5_leads(path: Path) -> list[M5Lead]:
    """Load M5 CSV output into ``M5Lead`` objects (order preserved)."""
    if not path.is_file():
        raise M5SourceError(f"M5 source file not found: {path}")

    rows = _load_rows(path)
    if not rows:
        raise M5SourceError(f"M5 output is empty: {path}")

    columns = set(rows[0].keys())
    if not any(col in columns for col in ("final_action", "outreach_priority")):
        if _is_contact_first_list(path, columns):
            # contact_first.csv contains CONTACT FIRST rows by construction, so
            # the eligible action is implied by the file itself — never guessed
            # from any other signal.
            logger.warning(
                "%s has no action columns; treating all %d rows as CONTACT FIRST "
                "(this file only ever holds CONTACT FIRST leads)",
                path.name, len(rows),
            )
            for item in rows:
                item["final_action"] = item.get("final_action") or "CONTACT"
                item["outreach_priority"] = item.get("outreach_priority") or "CONTACT FIRST"
        else:
            raise M5SourceError(
                f"{path.name} does not look like M5 output: missing final_action or "
                "outreach_priority. Run 'python3 main.py sales-report'."
            )

    leads: list[M5Lead] = []
    for index, clean in enumerate(rows, start=1):
        business_name = clean.get("business_name", "").strip()
        lead_id = clean.get("lead_id", "").strip()
        if not lead_id:
            lead_id = derive_lead_id(business_name, clean.get("phone", ""))
        if not business_name and not lead_id:
            logger.warning("Skipping blank M5 row #%d", index)
            continue
        leads.append(M5Lead(lead_id=lead_id, raw=clean, source_file=path.name))

    logger.info("Loaded %d leads from M5 output: %s", len(leads), path)
    return leads


__all__ = [
    "EXPECTED_M5_COLUMNS",
    "M5SourceError",
    "resolve_source_path",
    "load_m5_leads",
    "derive_lead_id",
]
