"""M6 — persistent send tracking (duplicate-send protection).

State file: ``output/m6_send_state.json`` (atomic writes).

Two independent keys are tracked:

    lead_id                     → "did we already contact this M5 lead?"
    "whatsapp:+923136162007"    → "did we already contact this phone number?"

The recipient key is what protects against the same business appearing twice in
M5 under two different lead_ids. Identity is NEVER derived from social platform
URLs — two different Facebook pages can never collide.

Blocking rules:

    SENT                  → SKIPPED_ALREADY_SENT (never resend automatically)
    AWAITING_MANUAL_SEND  → SKIPPED_ALREADY_SENT (a chat was already opened)
    FAILED                → allowed only with an explicit retry flag
    attempts >= MAX       → hard stop (M6 never retries endlessly)

History file: ``output/m6_outreach_results.json`` (+ CSV projection) keeps every
attempt forever; it is appended to, never rewritten with less data.
"""

from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Any

from .config import (
    BLOCKING_STATUSES,
    CHANNEL_ALIASES,
    CHANNEL_WHATSAPP,
    CHANNEL_WHATSAPP_PLAYWRIGHT,
    MAX_ATTEMPTS_PER_LEAD,
    M6_RESULTS_CSV,
    M6_RESULTS_JSON,
    M6_STATE_FILENAME,
    NO_WHATSAPP_DETAIL,
    NO_WHATSAPP_PHONE_REASONS,
    STATUS_NO_WHATSAPP,
    STATUS_NOT_READY,
    STATUS_SENT,
    STATUS_SKIPPED_NO_WHATSAPP,
)
from .storage import load_json, save_json_atomic, utc_now_iso

logger = logging.getLogger(__name__)

RESULTS_COLUMNS: tuple[str, ...] = (
    "lead_id", "business_name", "business_type", "location",
    "recipient", "recipient_source", "channel", "service", "potential",
    "confidence", "action", "priority", "m5_channel",
    "opportunity", "outreach_angle", "message", "body_word_count", "message_note",
    "validation_status", "validation_reasons", "duplicate_status", "duplicate_reason",
    "send_status", "sent_at", "send_verification", "error", "attempt", "dry_run",
    "wa_link", "review_flag", "possible_duplicate", "contact_quality_issues",
    "m5_source_file", "m5_report_timestamp", "run_id", "timestamp",
)

STATE_VERSION = 1


def recipient_key(channel: str, recipient: str) -> str:
    """Stable key for the recipient dimension ('whatsapp:+923136162007').

    All WhatsApp execution channels (``whatsapp``, ``whatsapp_playwright`` and
    their CLI aliases) share ONE recipient dimension, so duplicate protection
    holds no matter which channel sent the first message.
    """
    name = (channel or "").strip().lower()
    name = CHANNEL_ALIASES.get(name, name)
    if name == CHANNEL_WHATSAPP_PLAYWRIGHT:
        name = CHANNEL_WHATSAPP
    return f"{name}:{(recipient or '').strip()}"


def _empty_state() -> dict[str, Any]:
    return {
        "version": STATE_VERSION,
        "created_at": utc_now_iso(),
        "updated_at": utc_now_iso(),
        "leads": {},
        "recipients": {},
    }



class SendTracker:
    """Reads/writes M6's persistent send state and attempt history."""

    def __init__(self, output_dir: Path) -> None:
        self.output_dir = Path(output_dir)
        self.state_path = self.output_dir / M6_STATE_FILENAME
        self.results_json_path = self.output_dir / M6_RESULTS_JSON
        self.results_csv_path = self.output_dir / M6_RESULTS_CSV
        self.state: dict[str, Any] = load_json(self.state_path, _empty_state())
        if not isinstance(self.state, dict) or "leads" not in self.state:
            logger.warning("Send state at %s was unreadable — starting fresh", self.state_path)
            self.state = _empty_state()
        self.state.setdefault("leads", {})
        self.state.setdefault("recipients", {})

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------
    def lead_entry(self, lead_id: str) -> dict[str, Any] | None:
        return self.state["leads"].get(lead_id)

    def recipient_entry(self, channel: str, recipient: str) -> dict[str, Any] | None:
        return self.state["recipients"].get(recipient_key(channel, recipient))

    def attempts_for(self, lead_id: str) -> int:
        entry = self.lead_entry(lead_id)
        return int(entry.get("attempts", 0)) if entry else 0

    def sent_on_date(self, day: str) -> int:
        """Count leads whose FIRST successful send falls on ``day``.

        ``day`` is a UTC calendar date, ``YYYY-MM-DD`` (the same prefix used by
        ``utc_now_iso()``). This is what enforces ``MAX_SENDS_PER_DAY``: WhatsApp
        evaluates daily first-contact volume, not just per-run volume.
        """
        prefix = (day or "").strip()
        if not prefix:
            return 0
        count = 0
        for entry in self.state.get("leads", {}).values():
            if not isinstance(entry, dict):
                continue
            stamp = str(entry.get("first_sent_at") or entry.get("sent_at") or "")
            if stamp.startswith(prefix):
                count += 1
        return count

    def sent_today(self) -> int:
        """Count leads already successfully contacted today (UTC)."""
        return self.sent_on_date(utc_now_iso()[:10])

    def check_duplicate(
        self,
        lead_id: str,
        channel: str,
        recipient: str,
        *,
        retry_failed: bool = False,
        force_resend: bool = False,
    ) -> tuple[str, str]:
        """Return ``(kind, reason)``; empty kind means "safe to send"."""
        if force_resend:
            return "", ""

        entry = self.lead_entry(lead_id)
        if entry:
            status = str(entry.get("status", ""))
            attempts = int(entry.get("attempts", 0))
            if status == STATUS_NO_WHATSAPP:
                return "NO_WHATSAPP", (
                    f"lead {lead_id} has no WhatsApp number "
                    f"({entry.get('error') or NO_WHATSAPP_DETAIL}) — never retried automatically"
                )
            if status in BLOCKING_STATUSES:
                kind = "ALREADY_SENT" if status == STATUS_SENT else "ALREADY_OPENED"
                return kind, f"lead {lead_id} already has status {status} (attempts={attempts})"
            if status == "FAILED":
                if attempts >= MAX_ATTEMPTS_PER_LEAD:
                    return "MAX_ATTEMPTS", (
                        f"lead {lead_id} reached the attempt limit "
                        f"({attempts}/{MAX_ATTEMPTS_PER_LEAD})"
                    )
                if not retry_failed:
                    return "PREVIOUS_FAILURE", (
                        f"lead {lead_id} has a FAILED attempt ({entry.get('error', 'n/a')}); "
                        "retry requires --retry-failed"
                    )

        other = self.recipient_entry(channel, recipient)
        if other and str(other.get("lead_id", "")) != lead_id:
            status = str(other.get("status", ""))
            if status == STATUS_NO_WHATSAPP:
                return "NO_WHATSAPP", (
                    f"recipient {recipient} was recorded as having no WhatsApp number "
                    f"(lead {other.get('lead_id')}) — never retried automatically"
                )
            if status in BLOCKING_STATUSES:
                kind = "ALREADY_SENT" if status == STATUS_SENT else "ALREADY_OPENED"
                return kind, (
                    f"recipient {recipient} was already contacted by "
                    f"{other.get('lead_id')} ({status})"
                )

        return "", ""


    # ------------------------------------------------------------------
    # Writes
    # ------------------------------------------------------------------
    def record(self, record: dict[str, Any]) -> None:
        """Persist one processed lead (status + attempt history)."""
        self._update_state(record)
        self._append_history(record)
        self._write_state()

    def mark_sent(self, lead_id: str, *, note: str = "Confirmed by the user.") -> dict[str, Any] | None:
        """Record a manual confirmation for a lead that was previously opened."""
        entry = self.lead_entry(lead_id)
        if not entry:
            return None
        now = utc_now_iso()
        entry["status"] = STATUS_SENT
        entry["sent_at"] = entry.get("sent_at") or now
        entry["last_attempt_at"] = now
        entry["error"] = ""
        entry["note"] = note
        entry.setdefault("history", []).append({
            "lead_id": lead_id,
            "send_status": STATUS_SENT,
            "timestamp": now,
            "attempt": entry.get("attempts", 0),
            "note": note,
        })
        key = recipient_key(entry.get("channel", ""), entry.get("recipient", ""))
        if key in self.state["recipients"]:
            self.state["recipients"][key]["status"] = STATUS_SENT
            self.state["recipients"][key]["sent_at"] = entry["sent_at"]
        self._write_state()
        return entry

    # ------------------------------------------------------------------
    # No-WhatsApp (dead-end recipient) helpers
    # ------------------------------------------------------------------
    def mark_no_whatsapp(
        self,
        lead_id: str,
        *,
        reason: str = "",
        note: str = "Recorded by the user (--mark-no-whatsapp).",
    ) -> dict[str, Any] | None:
        """Record that this lead's number has no WhatsApp account.

        The status becomes blocking, so the number is never attempted again.
        """
        entry = self.lead_entry(lead_id)
        if not entry:
            return None
        now = utc_now_iso()
        detail = reason or NO_WHATSAPP_DETAIL
        entry["status"] = STATUS_NO_WHATSAPP
        entry["error"] = detail
        entry["no_whatsapp_at"] = now
        entry["last_attempt_at"] = entry.get("last_attempt_at") or now
        entry["note"] = note
        entry.setdefault("history", []).append({
            "lead_id": lead_id,
            "send_status": STATUS_NO_WHATSAPP,
            "timestamp": now,
            "attempt": entry.get("attempts", 0),
            "error": detail,
            "note": note,
        })
        key = recipient_key(entry.get("channel", ""), entry.get("recipient", ""))
        if key in self.state["recipients"]:
            self.state["recipients"][key]["status"] = STATUS_NO_WHATSAPP
        self._write_state()
        return entry

    def no_whatsapp_candidates(self) -> list[tuple[str, str]]:
        """Tracked leads whose recorded reason already proves there is no WhatsApp.

        Returns ``[(lead_id, recorded_reason), ...]``. Only reasons already
        written into the state are used as evidence — nothing is guessed, and
        leads that were SENT / AWAITING_MANUAL_SEND / already NO_WHATSAPP are
        left untouched.
        """
        found: list[tuple[str, str]] = []
        for lead_id, entry in self.state.get("leads", {}).items():
            status = str(entry.get("status", ""))
            if status in BLOCKING_STATUSES:
                continue
            haystack = " ".join(
                [str(entry.get("error", ""))]
                + [str(item.get("error", "")) for item in entry.get("history", [])]
            ).lower()
            if not haystack.strip():
                continue
            for marker in NO_WHATSAPP_PHONE_REASONS:
                if marker in haystack:
                    found.append((lead_id, str(entry.get("error", "")) or marker))
                    break
        return found

    # ------------------------------------------------------------------
    # State helpers
    # ------------------------------------------------------------------
    _NON_ATTEMPT_STATUSES = (
        "NOT_ELIGIBLE", STATUS_NOT_READY, "SKIPPED_ALREADY_SENT", "SKIPPED_LIMIT",
        # A no-WhatsApp outcome is a recorded fact, not a retryable attempt —
        # it must never consume the per-lead attempt budget.
        STATUS_SKIPPED_NO_WHATSAPP, STATUS_NO_WHATSAPP,
    )

    #: A later run may never downgrade the persisted status of a lead. Keeping
    #: SENT/AWAITING_MANUAL_SEND sticky is what prevents duplicate messages;
    #: NO_WHATSAPP_NUMBER is sticky too, so a dead-end number is never retried.
    _STATUS_RANK = {
        "": 0,
        "SKIPPED_LIMIT": 0,
        "SKIPPED_ALREADY_SENT": 0,
        STATUS_SKIPPED_NO_WHATSAPP: 0,
        "NOT_READY": 1,
        "FAILED": 2,
        "AWAITING_MANUAL_SEND": 3,
        "SENT": 4,
        STATUS_NO_WHATSAPP: 5,
    }

    def _update_state(self, record: dict[str, Any]) -> None:
        lead_id = record.get("lead_id") or "unknown"
        entry = self.state["leads"].setdefault(lead_id, {
            "lead_id": lead_id,
            "first_seen_at": utc_now_iso(),
            "attempts": 0,
            "history": [],
        })
        if record.get("send_status") not in self._NON_ATTEMPT_STATUSES:
            entry["attempts"] = int(entry.get("attempts", 0)) + 1

        entry.update({
            "business_name": record.get("business_name", ""),
            "channel": record.get("channel", ""),
            "recipient": record.get("recipient", ""),
            "last_attempt_at": record.get("timestamp", utc_now_iso()),
            "m5_source_file": record.get("m5_source_file", ""),
            "service": record.get("service", ""),
            "last_message": record.get("message", ""),
        })

        incoming = str(record.get("send_status", ""))
        current = str(entry.get("status", ""))
        if self._STATUS_RANK.get(incoming, 0) >= self._STATUS_RANK.get(current, 0):
            entry["status"] = incoming
            if incoming == STATUS_NO_WHATSAPP:
                entry["error"] = record.get("error", "") or NO_WHATSAPP_DETAIL
                entry["no_whatsapp_at"] = record.get("timestamp") or utc_now_iso()
            elif incoming == "FAILED":
                entry["error"] = record.get("error", "")
        elif not entry.get("error"):
            entry["error"] = record.get("error", "")

        if record.get("send_status") == STATUS_SENT:
            entry["sent_at"] = record.get("sent_at") or utc_now_iso()
            entry.setdefault("first_sent_at", entry["sent_at"])
            entry["verification"] = record.get("send_verification", "")

        entry.setdefault("history", []).append({
            "run_id": record.get("run_id", ""),
            "timestamp": record.get("timestamp", ""),
            "attempt": entry["attempts"],
            "validation_status": record.get("validation_status", ""),
            "validation_reasons": record.get("validation_reasons", ""),
            "duplicate_status": record.get("duplicate_status", ""),
            "send_status": record.get("send_status", ""),
            "sent_at": record.get("sent_at", ""),
            "error": record.get("error", ""),
        })

        if not record.get("recipient"):
            return
        key = recipient_key(record.get("channel", ""), record.get("recipient", ""))
        recipient_entry = self.state["recipients"].setdefault(key, {
            "lead_id": lead_id,
            "channel": record.get("channel", ""),
            "recipient": record.get("recipient", ""),
            "first_seen_at": utc_now_iso(),
        })
        # Keep the strongest status ever recorded for this recipient.
        rank = {
            "NOT_READY": 1, "FAILED": 2, "AWAITING_MANUAL_SEND": 3, "SENT": 4,
            STATUS_NO_WHATSAPP: 5,
        }
        incoming = str(record.get("send_status", ""))
        if rank.get(incoming, 0) >= rank.get(str(recipient_entry.get("status", "")), 0):
            recipient_entry["status"] = incoming
            recipient_entry["lead_id"] = lead_id
            if record.get("sent_at"):
                recipient_entry["sent_at"] = record["sent_at"]

    def _append_history(self, record: dict[str, Any]) -> None:
        history = load_json(self.results_json_path, [])
        if not isinstance(history, list):
            history = []
        history.append(record)
        save_json_atomic(self.results_json_path, history)
        self._write_history_csv(history)

    def _write_state(self) -> None:
        self.state["updated_at"] = utc_now_iso()
        self.state["version"] = STATE_VERSION
        save_json_atomic(self.state_path, self.state)

    def _write_history_csv(self, history: list[dict[str, Any]]) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        with self.results_csv_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(RESULTS_COLUMNS), extrasaction="ignore")
            writer.writeheader()
            for row in history:
                writer.writerow({key: ("" if row.get(key) is None else row.get(key)) for key in RESULTS_COLUMNS})

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------
    def load_history(self) -> list[dict[str, Any]]:
        history = load_json(self.results_json_path, [])
        return history if isinstance(history, list) else []

    def summary(self) -> dict[str, int]:
        leads = self.state.get("leads", {})
        counts: dict[str, int] = {}
        for entry in leads.values():
            status = str(entry.get("status", "UNKNOWN")) or "UNKNOWN"
            counts[status] = counts.get(status, 0) + 1
        counts["_total_leads_tracked"] = len(leads)
        counts["_total_attempts"] = sum(int(e.get("attempts", 0)) for e in leads.values())
        return counts


__all__ = ["SendTracker", "recipient_key", "RESULTS_COLUMNS", "STATE_VERSION"]
