"""Shared test helpers for the M6 test-suite (standard library only)."""

from __future__ import annotations

import csv
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from m6.channels.base import OutreachChannel           # noqa: E402
from m6.engine import M6RunConfig, run_outreach_execution  # noqa: E402
from m6.models import M5Lead, SendResult               # noqa: E402

# A realistic M5 row: exactly the shape produced by sales_report/output_writer.
BASE_ROW: dict[str, str] = {
    "lead_id": "lead_017_arbrandzone",
    "business_name": "Arbrandzone",
    "business_type": "retail_or_product_business",
    "location": "Plot 605 D, Block D Faisal Town, Lahore, 54770, Pakistan",
    "phone": "0313 6162007, +92 313 6162007",
    "mobile_phone": "",
    "whatsapp": "",
    "landline": "",
    "email": "",
    "website": "https://instagram.com/arbrandzone",
    "linkedin": "",
    "instagram": "https://instagram.com/arbrandzone",
    "facebook": "",
    "tiktok": "",
    "youtube": "",
    "research_status": "RESEARCHED",
    "digital_maturity": "LOW",
    "sales_potential": "HIGH",
    "confidence": "HIGH",
    "why_this_lead": (
        "Arbrandzone is an active Clothing store in Faisal Town, Lahore with 136 Google "
        "reviews and a 4.6 rating. It has a social presence on Instagram but no "
        "professional website."
    ),
    "detected_opportunity": "Active on Instagram but no website URL found in research data",
    "primary_service": "Business Digitalization",
    "primary_service_reason": "Social-only presence and no website found.",
    "secondary_services": "",
    "outreach_priority": "CONTACT FIRST",
    "outreach_channel": "WhatsApp",
    "outreach_angle": "Active on Instagram, no dedicated professional website identified.",
    "personalization_points": "Arbrandzone — Clothing store in Lahore | Instagram active",
    "outreach_message": "Hi Arbrandzone, ...",
    "message_notes": "",
    "final_action": "CONTACT",
    "uncertainties": "",
    "review_flag": "no",
    "review_reason": "",
    "possible_duplicate": "no",
    "duplicate_reason": "",
    "contact_quality_issues": "",
    "report_timestamp": "2026-09-24T15:28:18.304200+00:00",
}

M5_COLUMNS: tuple[str, ...] = tuple(BASE_ROW.keys())


def row(**overrides: Any) -> dict[str, str]:
    """A copy of the base M5 row with overrides applied."""
    data = dict(BASE_ROW)
    for key, value in overrides.items():
        data[key] = "" if value is None else str(value)
    return data


def make_lead(**overrides: Any) -> M5Lead:
    data = row(**overrides)
    return M5Lead(lead_id=data["lead_id"], raw=data, source_file="test_m5.csv")


def write_m5_csv(path: Path, rows: list[dict[str, str]]) -> Path:
    """Write a synthetic M5 master CSV."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(M5_COLUMNS))
        writer.writeheader()
        for item in rows:
            writer.writerow({key: item.get(key, "") for key in M5_COLUMNS})
    return path


class RecordingChannel(OutreachChannel):
    """Fake channel that records what would have been sent."""

    name = "recording"
    automated = True

    def __init__(self, status: str = "SENT", detail: str = "recorded") -> None:
        self.calls: list[tuple[str, str]] = []
        self.status = status
        self.detail = detail
        self.fail_with: Exception | None = None

    def send(self, recipient: str, message: str, *, lead: M5Lead | None = None) -> SendResult:
        self.calls.append((recipient, message))
        if self.fail_with is not None:
            raise self.fail_with
        if self.status == "SENT":
            from m6.storage import utc_now_iso

            return SendResult(status="SENT", detail=self.detail, sent_at=utc_now_iso(),
                              verification="test", link=f"recording://{recipient}")
        return SendResult(status=self.status, detail=self.detail, verification="test",
                          link=f"recording://{recipient}")


def run_engine(
    tmp_dir: Path,
    rows: list[dict[str, str]],
    *,
    channel: OutreachChannel | None = None,
    **config_kwargs: Any,
) -> tuple[Any, RecordingChannel, Path]:
    """Write M5 rows to ``tmp_dir``, run M6, return (report, channel, source_path)."""
    source = write_m5_csv(tmp_dir / "m5.csv", rows)
    active_channel = channel or RecordingChannel()
    config_kwargs.setdefault("yes", True)
    config_kwargs.setdefault("min_interval_s", 0)
    config = M6RunConfig(output_dir=tmp_dir, source=str(source), **config_kwargs)
    report = run_outreach_execution(config, channel=active_channel, out=lambda *_: None)
    return report, active_channel, source
