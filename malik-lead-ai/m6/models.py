"""M6 — data models.

``M5Lead`` wraps one row of M5's final actionable output. ``M6Plan`` is the
per-lead execution plan (eligibility → recipient → message → validation →
duplicate status → send result).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


def _s(value: Any, default: str = "") -> str:
    """Safe string: None / 'None' / 'null' / 'nan' become the default."""
    if value is None:
        return default
    text = str(value).strip()
    if not text or text.lower() in ("null", "none", "nan"):
        return default
    return text


@dataclass(frozen=True)
class M5Lead:
    """One M5 output row (read-only view, keeps every original field)."""

    lead_id: str
    raw: Mapping[str, str]
    source_file: str = ""

    def text(self, key: str, default: str = "") -> str:
        return _s(self.raw.get(key), default)

    def flag(self, key: str) -> bool:
        """M5 writes booleans as 'yes'/'no' in CSV."""
        return self.text(key).lower() in ("yes", "true", "1", "y")

    @property
    def business_name(self) -> str:
        return self.text("business_name")

    @property
    def final_action(self) -> str:
        return self.text("final_action")

    @property
    def outreach_priority(self) -> str:
        return self.text("outreach_priority")

    @property
    def primary_service(self) -> str:
        return self.text("primary_service")

    @property
    def detected_opportunity(self) -> str:
        return self.text("detected_opportunity")

    @property
    def m5_channel(self) -> str:
        return self.text("outreach_channel")

    @property
    def m5_timestamp(self) -> str:
        return self.text("report_timestamp")


@dataclass
class ValidationResult:
    """Outcome of M6's pre-send validation."""

    status: str = "NOT_READY"                      # PASS | NOT_READY
    reasons: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.status == "PASS"

    def add(self, reason: str) -> None:
        self.reasons.append(reason)

    def as_text(self) -> str:
        if self.ok:
            return "PASS"
        if not self.reasons:
            return "NOT_READY"
        return "NOT_READY: " + "; ".join(self.reasons)

    def to_dict(self) -> dict[str, Any]:
        return {"status": self.status, "reasons": list(self.reasons)}


@dataclass
class SendResult:
    """What a channel did (or did not do)."""

    status: str                                    # SENT | FAILED | AWAITING_MANUAL_SEND
    detail: str = ""
    sent_at: str = ""                              # ISO-8601 UTC, only when status == SENT
    verification: str = ""                         # manual_confirmation | browser_verification
    link: str = ""                                 # click-to-chat link when applicable

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "detail": self.detail,
            "sent_at": self.sent_at,
            "verification": self.verification,
            "link": self.link,
        }



@dataclass
class M6Plan:
    """Everything M6 knows about one M5 lead before/after sending."""

    lead: M5Lead
    priority: str = ""
    final_action: str = ""

    eligible: bool = False
    eligibility_reason: str = ""

    channel: str = ""
    recipient: str = ""                            # E.164, e.g. "+923136162007"
    recipient_source: str = ""                     # whatsapp | mobile_phone | phone
    channel_note: str = ""

    message: str = ""
    body_word_count: int = 0
    message_note: str = ""
    wa_link: str = ""
    opportunity_line: str = ""
    pricing_included: bool = False

    validation: ValidationResult = field(default_factory=ValidationResult)
    duplicate_kind: str = ""                       # "" | ALREADY_SENT | ALREADY_OPENED | PREVIOUS_FAILURE | MAX_ATTEMPTS
    duplicate_reason: str = ""
    prior_attempts: int = 0

    send_status: str = ""
    send_error: str = ""
    sent_at: str = ""
    attempt_number: int = 0
    send_verification: str = ""

    @property
    def lead_id(self) -> str:
        return self.lead.lead_id

    @property
    def business_name(self) -> str:
        return self.lead.business_name

    @property
    def needs_send(self) -> bool:
        """True only when this plan would actually transmit a message."""
        return (
            self.eligible
            and self.validation.ok
            and not self.duplicate_kind
            and not self.send_status
        )

    def to_record(self, *, run_id: str, timestamp: str, dry_run: bool) -> dict[str, Any]:
        """Flat, persistable record (results JSON/CSV and state history)."""
        raw = self.lead.raw
        return {
            "lead_id": self.lead_id,
            "business_name": self.business_name,
            "business_type": self.lead.text("business_type"),
            "location": self.lead.text("location"),
            "recipient": self.recipient,
            "recipient_source": self.recipient_source,
            "channel": self.channel,
            "service": self.lead.primary_service,
            "potential": self.lead.text("sales_potential"),
            "confidence": self.lead.text("confidence"),
            "action": self.final_action,
            "priority": self.priority,
            "m5_channel": self.lead.m5_channel,
            "opportunity": self.lead.detected_opportunity,
            "outreach_angle": self.lead.text("outreach_angle"),
            "message": self.message,
            "body_word_count": self.body_word_count,
            "message_note": self.message_note,
            "validation_status": self.validation.status,
            "validation_reasons": "; ".join(self.validation.reasons),
            "duplicate_status": self.duplicate_kind,
            "duplicate_reason": self.duplicate_reason,
            "send_status": self.send_status,
            "sent_at": self.sent_at,
            "send_verification": self.send_verification,
            "error": self.send_error,
            "attempt": self.attempt_number,
            "dry_run": dry_run,
            "wa_link": self.wa_link,
            "review_flag": raw.get("review_flag", ""),
            "possible_duplicate": raw.get("possible_duplicate", ""),
            "contact_quality_issues": raw.get("contact_quality_issues", ""),
            "m5_source_file": self.lead.source_file,
            "m5_report_timestamp": self.lead.m5_timestamp,
            "run_id": run_id,
            "timestamp": timestamp,
        }
