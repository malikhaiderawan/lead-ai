"""M6 — outreach execution engine.

The engine is channel-agnostic: it knows nothing about browsers. It:

    1. loads M5's final output,
    2. gates on M5's decision (CONTACT FIRST only by default),
    3. resolves and normalises the WhatsApp recipient,
    4. builds the first-touch message from M5 evidence,
    5. validates it (NOT_READY → never sent),
    6. checks the persistent send state for duplicates,
    7. calls ``channel.send(recipient, message)`` at most once per lead,
    8. records everything (state + results JSON/CSV + append-only log).

Safety properties enforced here (not in the channel):

* ``--dry-run`` never calls the channel and never writes state,
* real sends require explicit human confirmation (prompt, ``--yes`` or TTY),
* a run never sends more than ``MAX_SENDS_PER_RUN`` messages,
* no more than ``MAX_SENDS_PER_DAY`` first touches in one UTC day (across runs),
* a randomised ``MIN_SECONDS_BETWEEN_SENDS`` … ``MIN_SECONDS_BETWEEN_SENDS +
  SEND_INTERVAL_JITTER_SECONDS`` gap between two sends (3–5 min by default),
* M6 never retries by itself.
"""

from __future__ import annotations

import logging
import random
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from .channels import ChannelError, OutreachChannel, build_channel
from .config import (
    CHANNEL_ALIASES,
    CHANNEL_WHATSAPP,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_SEND_LIMIT,
    MAX_SENDS_PER_DAY,
    MAX_SENDS_PER_RUN,
    MIN_SECONDS_BETWEEN_SENDS,
    SEND_INTERVAL_JITTER_SECONDS,
    M6_LOG_FILENAME,
    NO_WHATSAPP_DETAIL,
    NO_WHATSAPP_LABEL,
    NO_WHATSAPP_PHONE_REASONS,
    STATUS_AWAITING_MANUAL,
    STATUS_DRY_RUN,
    STATUS_FAILED,
    STATUS_NO_WHATSAPP,
    STATUS_NOT_ELIGIBLE,
    STATUS_NOT_READY,
    STATUS_SENT,
    STATUS_SKIPPED_ALREADY_SENT,
    STATUS_SKIPPED_LIMIT,
    STATUS_SKIPPED_NO_WHATSAPP,
    SUPPORTED_M5_CHANNELS,
)
from .eligibility import check_eligibility, resolve_priority_label
from .logging_setup import configure_run_logging
from .message_builder import MessageBuildError, build_first_message
from .models import M5Lead, M6Plan, SendResult, ValidationResult
from .phone import resolve_recipient
from .send_tracker import SendTracker
from .source_loader import M5SourceError, load_m5_leads, resolve_source_path
from .storage import utc_now_iso
from .validator import validate_message

logger = logging.getLogger("m6.engine")

_RECIPIENT_FIELDS: tuple[str, ...] = ("whatsapp", "mobile_phone", "phone")


# ---------------------------------------------------------------------------
# Run configuration / report
# ---------------------------------------------------------------------------

@dataclass
class M6RunConfig:
    """Everything the CLI can influence about one M6 run."""

    output_dir: Path = DEFAULT_OUTPUT_DIR
    source: str | None = None
    lead_ids: tuple[str, ...] = ()
    dry_run: bool = False
    include_actions: frozenset[str] = frozenset()
    limit: int = DEFAULT_SEND_LIMIT
    retry_failed: bool = False
    force_resend: bool = False
    confirm_manual_send: bool = False
    include_pricing: bool = True
    skip_review_flagged: bool = False
    allow_channel_inference: bool = False
    channel: str = CHANNEL_WHATSAPP
    open_browser: bool = True
    yes: bool = False
    log_file: Path | None = None
    min_interval_s: int = MIN_SECONDS_BETWEEN_SENDS
    jitter_s: int = SEND_INTERVAL_JITTER_SECONDS
    quiet: bool = False

    def resolved_limit(self) -> int:
        limit = self.limit if self.limit and self.limit > 0 else DEFAULT_SEND_LIMIT
        return min(limit, MAX_SENDS_PER_RUN)


@dataclass
class M6RunReport:
    """What happened during the run (used for CLI output + tests)."""

    run_id: str = ""
    source_file: str = ""
    total_m5_leads: int = 0
    candidates: list[M6Plan] = field(default_factory=list)   # eligible (M5 says contact)
    skipped: list[M6Plan] = field(default_factory=list)      # not eligible by M5 decision
    records: list[dict[str, Any]] = field(default_factory=list)
    dry_run: bool = False
    aborted: bool = False
    abort_reason: str = ""
    state_path: Path | None = None
    results_json_path: Path | None = None
    results_csv_path: Path | None = None
    log_path: Path | None = None

    def count(self, status: str) -> int:
        return sum(1 for record in self.records if record.get("send_status") == status)

    def status_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for record in self.records:
            key = str(record.get("send_status", "")) or "UNKNOWN"
            counts[key] = counts.get(key, 0) + 1
        return counts

    @property
    def sent_count(self) -> int:
        return self.count(STATUS_SENT)


# ---------------------------------------------------------------------------
# Confirmation prompts (human control)
# ---------------------------------------------------------------------------

def default_batch_confirm(count: int, *, prompt: Callable[[str], str] | None = None) -> bool:
    """Require an explicit 'SEND' before any real message leaves the machine."""
    reader = prompt or input
    try:
        answer = reader(f"Type SEND to transmit {count} real WhatsApp message(s): ")
    except EOFError:
        return False
    return answer.strip().upper() == "SEND"


def default_manual_confirm(plan: M6Plan, *, prompt: Callable[[str], str] | None = None) -> bool:
    """Ask the human whether the WhatsApp message was actually sent."""
    reader = prompt or input
    try:
        answer = reader(f"Did you press Send in WhatsApp for {plan.business_name}? [y/N] ")
    except EOFError:
        return False
    return answer.strip().lower() in ("y", "yes")


# ---------------------------------------------------------------------------
# Channel + recipient resolution
# ---------------------------------------------------------------------------

def _canonical_m5_channel(value: str) -> str:
    """Map M5's outreach_channel to M6's channel vocabulary.

    Empty string means "M5 did not specify a channel".
    """
    text = (value or "").strip().lower()
    if text in SUPPORTED_M5_CHANNELS:
        return CHANNEL_WHATSAPP
    if not text or text in ("unknown", "n/a", "none"):
        return ""
    return text.replace(" ", "_")


#: Duplicate kinds that map to a dedicated skip status, so the *reason* stays
#: visible in the results file instead of a generic "already sent" message.
_SKIP_STATUS_BY_DUPLICATE: dict[str, str] = {
    "NO_WHATSAPP": STATUS_SKIPPED_NO_WHATSAPP,
}


def no_whatsapp_reason(validation: ValidationResult) -> str:
    """Return the reason when validation proved this number has no WhatsApp.

    Only reasons already produced by ``m6.phone`` are treated as evidence
    (Pakistani landline, no usable number, ...); anything else is NOT_READY.
    """
    for reason in validation.reasons:
        lowered = reason.lower()
        if any(marker in lowered for marker in NO_WHATSAPP_PHONE_REASONS):
            return reason
    return ""


def plan_lead(
    lead: M5Lead,
    config: M6RunConfig,
    tracker: SendTracker,
    *,
    channel_name: str = CHANNEL_WHATSAPP,
) -> M6Plan:
    """Build the full execution plan for one M5 lead (no side effects)."""
    plan = M6Plan(lead=lead, final_action=lead.final_action, priority=resolve_priority_label(lead))

    eligible, reason = check_eligibility(lead, config.include_actions)
    plan.eligible = eligible
    plan.eligibility_reason = reason
    if not eligible:
        return plan

    plan.channel = channel_name

    # --- M5 channel trust: never silently switch platform -------------------
    m5_channel = _canonical_m5_channel(lead.m5_channel)
    if m5_channel and m5_channel != CHANNEL_WHATSAPP:
        plan.validation = ValidationResult("NOT_READY", [f"channel_not_supported_in_m6_v1:{m5_channel}"])
        return plan
    if not m5_channel:
        if not config.allow_channel_inference:
            plan.validation = ValidationResult("NOT_READY", ["channel_unknown_in_m5"])
            return plan
        plan.channel_note = "channel inferred from the available phone number (--allow-channel-inference)"

    # --- opt-in review-flag gate -------------------------------------------
    if config.skip_review_flagged and lead.flag("review_flag"):
        plan.validation = ValidationResult("NOT_READY", [
            f"review_flagged_by_m5: {lead.text('review_reason')[:120]}"
        ])
        return plan

    # --- recorded no-WhatsApp fact: never re-plan a dead-end number ---------
    # The fact can only be recorded for the lead, so it is checked before the
    # recipient/message work. ``--force-resend`` (explicit --lead-id) overrides.
    if not config.force_resend:
        recorded = tracker.lead_entry(lead.lead_id) or {}
        if str(recorded.get("status", "")) == STATUS_NO_WHATSAPP:
            plan.duplicate_kind = "NO_WHATSAPP"
            plan.duplicate_reason = (
                f"lead {lead.lead_id} is recorded as {STATUS_NO_WHATSAPP} "
                f"({recorded.get('error') or NO_WHATSAPP_DETAIL}) — never retried automatically"
            )
            plan.validation = ValidationResult("NOT_READY", [
                f"no_whatsapp_number_recorded: {recorded.get('error') or NO_WHATSAPP_DETAIL}"
            ])
            return plan

    # --- recipient ----------------------------------------------------------
    field_values = [(name, lead.text(name)) for name in _RECIPIENT_FIELDS]
    e164, source_field, recipient_reason = resolve_recipient(field_values)
    plan.recipient = e164
    plan.recipient_source = source_field

    # --- message + validation ----------------------------------------------
    try:
        built = build_first_message(lead, include_pricing=config.include_pricing)
    except MessageBuildError as exc:
        plan.validation = ValidationResult("NOT_READY", [f"message_build_failed:{exc}"])
        return plan

    plan.message = built.text
    plan.body_word_count = built.body_word_count
    plan.message_note = built.note
    plan.opportunity_line = built.opportunity_line
    plan.pricing_included = built.pricing_included

    if not e164:
        plan.validation = ValidationResult("NOT_READY", [f"recipient_not_ready: {recipient_reason}"])
        return plan

    from .channels.whatsapp import build_wa_link

    plan.wa_link = build_wa_link(e164, built.text)
    plan.validation = validate_message(
        built, lead,
        recipient=e164,
        channel=channel_name,
        already_sent=False,
    )
    plan.prior_attempts = tracker.attempts_for(plan.lead_id)
    plan.duplicate_kind, plan.duplicate_reason = tracker.check_duplicate(
        plan.lead_id, channel_name, e164,
        retry_failed=config.retry_failed, force_resend=config.force_resend,
    )
    return plan


# ---------------------------------------------------------------------------
# Printing
# ---------------------------------------------------------------------------

def format_plan_block(plan: M6Plan, *, dry_run: bool, index: int | None = None) -> list[str]:
    """The human-readable per-lead block (see task spec §15)."""
    lead = plan.lead
    lines: list[str] = []
    if index is not None:
        lines.append(f"--- [{index}] " + "-" * 52)
    lines.append(f"Lead: {plan.lead_id}")
    lines.append(f"Business: {plan.business_name or '(missing)'}")
    lines.append(
        f"Action: {plan.priority or plan.final_action} "
        f"(M5 final_action={lead.final_action or 'n/a'}, priority={lead.outreach_priority or 'n/a'})"
    )
    lines.append(
        f"Channel: {plan.channel or '(none)'}" + (f" — {plan.channel_note}" if plan.channel_note else "")
    )
    lines.append(
        f"Recipient: {plan.recipient or '(none)'}"
        + (f"  (from M5 field: {plan.recipient_source})" if plan.recipient_source else "")
    )
    lines.append(f"Service: {lead.primary_service or '(none)'}")
    lines.append(f"Potential: {lead.text('sales_potential') or '(none)'}")
    lines.append("")
    lines.append("Opportunity:")
    lines.append("  " + (lead.detected_opportunity or "(none)"))
    lines.append("")
    if plan.message:
        lines.append("Message:")
        lines.extend("  " + line for line in plan.message.splitlines())
        lines.append("")
        lines.append(
            f"Body word count: {plan.body_word_count}"
            + (f"  | note: {plan.message_note}" if plan.message_note else "")
        )
    lines.append(f"Validation: {plan.validation.as_text()}")
    if plan.duplicate_kind:
        lines.append(f"Duplicate check: {plan.duplicate_kind} — {plan.duplicate_reason}")
    else:
        lines.append("Duplicate check: not previously contacted")
    if dry_run:
        lines.append(f"Send status: {STATUS_DRY_RUN}")
    else:
        status_line = plan.send_status or "NOT SENT"
        if plan.sent_at:
            status_line += f" (sent_at={plan.sent_at})"
        if plan.send_error:
            status_line += f" — {plan.send_error}"
        lines.append(f"Send status: {status_line}")
    if plan.wa_link:
        lines.append(f"WhatsApp link: {plan.wa_link}")
    return lines


def print_plan(plan: M6Plan, *, dry_run: bool, index: int | None = None, out: Callable[[str], None] = print) -> None:
    for line in format_plan_block(plan, dry_run=dry_run, index=index):
        out(line)
    out("")


def print_run_header(
    config: M6RunConfig,
    report: M6RunReport,
    channel: OutreachChannel,
    *,
    out: Callable[[str], None] = print,
) -> None:
    out("[M6 DRY RUN]" if config.dry_run else "[M6 EXECUTE]")
    out("")
    out(f"Source (M5): {report.source_file or '(none)'}")
    out(f"M5 leads loaded: {report.total_m5_leads}")
    out(f"Channel: {channel.describe()}")
    out(f"Send limit this run: {config.resolved_limit()} (hard cap {MAX_SENDS_PER_RUN})")
    if config.include_pricing:
        out("Pricing sentence: ENABLED (--include-pricing)")
    if config.include_actions:
        out(f"Extra actions allowed: {', '.join(sorted(config.include_actions))}")
    if config.lead_ids:
        out(f"Lead filter: {', '.join(config.lead_ids)}")
    out("")


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run_outreach_execution(
    config: M6RunConfig,
    *,
    channel: OutreachChannel | None = None,
    tracker: SendTracker | None = None,
    batch_confirm: Callable[[int], bool] | None = None,
    manual_confirm: Callable[[M6Plan], bool] | None = None,
    sleeper: Callable[[float], None] = time.sleep,
    out: Callable[[str], None] = print,
) -> M6RunReport:
    """Execute (or dry-run) M6 for the eligible M5 leads."""
    output_dir = Path(config.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    log_path = Path(config.log_file) if config.log_file else output_dir / M6_LOG_FILENAME
    configure_run_logging(log_path, level=logging.WARNING if config.quiet else logging.INFO)

    run_id = utc_now_iso().replace(":", "").replace("-", "")[:15]
    report = M6RunReport(run_id=run_id, dry_run=config.dry_run, log_path=log_path)

    # 1. M5 input ----------------------------------------------------------
    path = resolve_source_path(output_dir, config.source)
    leads = load_m5_leads(path)
    report.source_file = str(path)
    report.total_m5_leads = len(leads)

    if config.lead_ids:
        wanted = {str(x).strip() for x in config.lead_ids}
        leads = [lead for lead in leads if lead.lead_id in wanted]
        found = {lead.lead_id for lead in leads}
        for missing in sorted(wanted - found):
            logger.error("--lead-id %s not found in %s", missing, path.name)
            out(f"WARNING: lead_id {missing} not found in {path.name}")

    # 2. Channel + tracker -------------------------------------------------
    channel_name = CHANNEL_ALIASES.get(config.channel, config.channel)
    active_channel = channel or build_channel(
        channel_name,
        open_browser=config.open_browser,
        profile_dir=None,
        # The engine owns inter-send pacing (it also applies the random
        # jitter), so the channel must NOT pace again — that would double
        # every wait.
        min_interval_s=0,
        headless=False,
    )
    active_channel.ensure_ready()
    tracker = tracker or SendTracker(output_dir)
    report.state_path = tracker.state_path
    report.results_json_path = tracker.results_json_path
    report.results_csv_path = tracker.results_csv_path

    print_run_header(config, report, active_channel, out=out)

    # 3. Plan every lead (still no transmission) --------------------------
    for lead in leads:
        plan = plan_lead(lead, config, tracker, channel_name=channel_name)
        if plan.eligible:
            report.candidates.append(plan)
        else:
            report.skipped.append(plan)
            logger.info(
                "NOT_ELIGIBLE %s (%s) — %s", plan.lead_id, plan.business_name, plan.eligibility_reason
            )

    ready = [p for p in report.candidates if p.validation.ok and not p.duplicate_kind]
    limit = config.resolved_limit()

    # Daily ceiling across ALL runs: WhatsApp's enforcement looks at daily
    # first-contact volume, not only per-run volume, so several small runs in
    # one day must not add up to a bulk pattern.
    sent_today = tracker.sent_today()
    remaining_today = max(0, MAX_SENDS_PER_DAY - sent_today)
    if limit > remaining_today:
        logger.info(
            "Daily cap active: %d/%d already sent today (UTC) — this run is limited to %d.",
            sent_today, MAX_SENDS_PER_DAY, remaining_today,
        )
        out(
            f"Daily safety cap: {sent_today}/{MAX_SENDS_PER_DAY} first touches already sent "
            f"today (UTC) — limiting this run to {remaining_today}."
        )
    will_send = ready[:min(limit, remaining_today)]

    # 4. Dry run ----------------------------------------------------------
    if config.dry_run:
        for index, plan in enumerate(report.candidates, start=1):
            plan.send_status = STATUS_DRY_RUN
            print_plan(plan, dry_run=True, index=index, out=out)
        print_summary(config, report, ready, out=out)
        logger.info(
            "DRY RUN complete: %d candidates, %d ready (nothing sent)", len(report.candidates), len(ready)
        )
        return report

    # 5. Daily cap + human confirmation before any real send ---------------
    if not will_send and ready and remaining_today <= 0:
        report.aborted = True
        report.abort_reason = "daily_cap_reached"
        logger.warning(
            "Daily safety cap reached: %d/%d first touches sent today (UTC) — nothing sent.",
            sent_today, MAX_SENDS_PER_DAY,
        )
        out(
            f"Daily safety cap reached ({sent_today}/{MAX_SENDS_PER_DAY} sent today, UTC).\n"
            "Nothing was sent. Sending more today risks another WhatsApp restriction — "
            "resume tomorrow."
        )
        print_summary(config, report, ready, out=out)
        return report

    if will_send and not config.yes:
        if batch_confirm:
            approved = batch_confirm(len(will_send))
        elif sys.stdin.isatty():
            approved = default_batch_confirm(len(will_send))
        else:
            approved = False
            out(
                "Refusing to send from a non-interactive shell without confirmation.\n"
                "Re-run with --yes, or use --dry-run to inspect first."
            )
        if not approved:
            report.aborted = True
            report.abort_reason = "user_did_not_confirm"
            logger.warning("Aborted before sending: no confirmation")
            out("Aborted — nothing was sent.")
            return report

    # 6. Send -------------------------------------------------------------
    last_send_at: float | None = None
    for index, plan in enumerate(report.candidates, start=1):
        in_limit = plan in will_send
        attempt_now = in_limit and plan.validation.ok and not plan.duplicate_kind
        if attempt_now and last_send_at is not None and config.min_interval_s > 0:
            # Minimum 3 minutes plus a random extra 0–120s, so the cadence is
            # not a fixed metronome (a constant interval is a fingerprint).
            gap = config.min_interval_s + random.uniform(0, max(0, config.jitter_s))
            elapsed = time.monotonic() - last_send_at
            if elapsed < gap:
                wait_for = gap - elapsed
                logger.info("Pacing: waiting %.0fs before the next send", wait_for)
                out(f"Waiting {wait_for / 60:.1f} min before the next message…")
                sleeper(wait_for)
        if attempt_now:
            last_send_at = time.monotonic()

        record = _process_candidate(
            plan, config, tracker, active_channel,
            run_id=run_id, index=index, in_limit=in_limit,
            manual_confirm=manual_confirm, out=out,
        )
        report.records.append(record)

    print_summary(config, report, ready, out=out)
    return report


def _process_candidate(
    plan: M6Plan,
    config: M6RunConfig,
    tracker: SendTracker,
    channel: OutreachChannel,
    *,
    run_id: str,
    index: int,
    in_limit: bool,
    manual_confirm: Callable[[M6Plan], bool] | None,
    out: Callable[[str], None],
) -> dict[str, Any]:
    """Send (or skip) one candidate and persist the outcome."""
    timestamp = utc_now_iso()

    # Re-check duplicates at send time: an earlier lead in THIS run may already
    # have consumed the same recipient (or the same lead_id may appear twice).
    if plan.eligible and plan.validation.ok:
        fresh_kind, fresh_reason = tracker.check_duplicate(
            plan.lead_id, plan.channel, plan.recipient,
            retry_failed=config.retry_failed, force_resend=config.force_resend,
        )
        if fresh_kind:
            plan.duplicate_kind, plan.duplicate_reason = fresh_kind, fresh_reason

    if plan.duplicate_kind:
        plan.send_status = _SKIP_STATUS_BY_DUPLICATE.get(
            plan.duplicate_kind, STATUS_SKIPPED_ALREADY_SENT
        )
        plan.send_error = plan.duplicate_reason
        plan.attempt_number = plan.prior_attempts
        logger.info("%s %s — %s", plan.send_status, plan.lead_id, plan.duplicate_reason)
    elif not plan.validation.ok:
        missing_whatsapp = no_whatsapp_reason(plan.validation)
        if missing_whatsapp:
            plan.send_status = STATUS_NO_WHATSAPP
            plan.send_error = f"{NO_WHATSAPP_DETAIL} — {missing_whatsapp}"
            plan.attempt_number = plan.prior_attempts
            logger.warning(
                "%s %s — %s (never retried automatically)",
                STATUS_NO_WHATSAPP, plan.lead_id, plan.send_error,
            )
        else:
            plan.send_status = STATUS_NOT_READY
            plan.send_error = "; ".join(plan.validation.reasons)
            plan.attempt_number = plan.prior_attempts
            logger.warning("NOT_READY %s — %s", plan.lead_id, plan.send_error)
    elif not in_limit:
        plan.send_status = STATUS_SKIPPED_LIMIT
        plan.send_error = f"run send limit reached ({config.resolved_limit()})"
        plan.attempt_number = plan.prior_attempts
        logger.info("SKIPPED_LIMIT %s — %s", plan.lead_id, plan.send_error)
    else:
        plan.attempt_number = plan.prior_attempts + 1
        try:
            result = channel.send(plan.recipient, plan.message, lead=plan.lead)
        except ChannelError as exc:
            result = SendResult(status=STATUS_FAILED, detail=f"channel_error: {exc}", verification="failed")
        except Exception as exc:  # noqa: BLE001
            result = SendResult(status=STATUS_FAILED, detail=f"unexpected_error: {exc}", verification="failed")

        plan.send_status = result.status
        plan.sent_at = result.sent_at
        plan.send_verification = result.verification
        plan.send_error = "" if result.status == STATUS_SENT else result.detail

        if result.status == STATUS_AWAITING_MANUAL and config.confirm_manual_send:
            confirmer = manual_confirm
            if confirmer is None and sys.stdin.isatty():
                confirmer = default_manual_confirm
            if confirmer and confirmer(plan):
                from .channels.whatsapp import confirmed_result

                confirmed = confirmed_result(link=result.link)
                plan.send_status = confirmed.status
                plan.sent_at = confirmed.sent_at
                plan.send_verification = confirmed.verification
                plan.send_error = ""
        logger.info(
            "%s %s → %s (%s)",
            plan.send_status, plan.lead_id, plan.recipient or "no-recipient", result.detail or "",
        )

    print_plan(plan, dry_run=False, index=index, out=out)
    record = plan.to_record(run_id=run_id, timestamp=timestamp, dry_run=False)
    tracker.record(record)
    return record


def print_summary(
    config: M6RunConfig,
    report: M6RunReport,
    ready: list[M6Plan],
    *,
    out: Callable[[str], None] = print,
) -> None:
    counts = report.status_counts()
    out("[M6 SUMMARY]")
    out(f"  Run ID:              {report.run_id}")
    out(f"  Source (M5):         {report.source_file}")
    out(f"  M5 leads loaded:     {report.total_m5_leads}")
    out(f"  Eligible (M5 ready): {len(report.candidates)}")
    out(f"  Not eligible:        {len(report.skipped)}")
    out(f"  Ready to send:       {len(ready)}")

    shown_any = False
    for status in (
        STATUS_SENT, STATUS_AWAITING_MANUAL, STATUS_FAILED, STATUS_NO_WHATSAPP,
        STATUS_NOT_READY, STATUS_SKIPPED_ALREADY_SENT, STATUS_SKIPPED_NO_WHATSAPP,
        STATUS_SKIPPED_LIMIT, STATUS_DRY_RUN,
    ):
        if counts.get(status):
            out(f"  {status:<22} {counts[status]}")
            shown_any = True
    if counts.get(STATUS_NO_WHATSAPP) or counts.get(STATUS_SKIPPED_NO_WHATSAPP):
        out("")
        out(
            f"  {NO_WHATSAPP_LABEL}: recorded as having no WhatsApp account — "
            "never attempted again automatically."
        )
    if not shown_any:
        if config.dry_run:
            out(f"  {len(report.candidates)} candidate(s) validated for a future run (dry run: nothing sent)")
        else:
            out("  (no candidate leads processed)")

    if report.skipped:
        out("")
        out("  Not eligible (M5 decision respected — nothing sent):")
        for plan in report.skipped[:30]:
            out(f"    - {plan.lead_id:<42} {plan.eligibility_reason}")
        if len(report.skipped) > 30:
            out(f"    ... and {len(report.skipped) - 30} more (see the log file)")

    if report.aborted:
        out("")
        out(f"  ABORTED: {report.abort_reason}")

    out("")
    if not config.dry_run:
        out(f"  State:        {report.state_path}")
        out(f"  Results JSON: {report.results_json_path}")
        out(f"  Results CSV:  {report.results_csv_path}")
        out(f"  Log:          {report.log_path}")
    else:
        out("  Dry run: nothing was sent and no send state was written.")


# ---------------------------------------------------------------------------
# Manual confirmation + state inspection helpers
# ---------------------------------------------------------------------------

def mark_lead_sent(
    lead_id: str,
    *,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    note: str = "Confirmed by the user (--mark-sent).",
    out: Callable[[str], None] = print,
) -> int:
    """Record that the user sent (or confirmed) one lead's message manually."""
    tracker = SendTracker(Path(output_dir))
    entry = tracker.lead_entry(lead_id)
    if entry is None:
        out(f"Lead {lead_id} is not tracked yet — run outreach-execute for it first.")
        return 1
    previous = str(entry.get("status", ""))
    if previous == STATUS_SENT:
        out(f"Lead {lead_id} is already recorded as SENT at {entry.get('sent_at', 'n/a')} — nothing changed.")
        return 0
    updated = tracker.mark_sent(lead_id, note=note)
    out(f"Lead {lead_id} marked as SENT (previous status: {previous or 'unknown'}).")
    out(f"  recipient: {updated.get('recipient', '')}")
    out(f"  sent_at:   {updated.get('sent_at', '')}")
    out(f"  state:     {tracker.state_path}")
    logger.info("Marked %s as SENT (was %s)", lead_id, previous or "unknown")
    return 0


def mark_no_whatsapp(
    lead_id: str,
    *,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    reason: str = "",
    note: str = "Recorded by the user (--mark-no-whatsapp).",
    out: Callable[[str], None] = print,
) -> int:
    """Record one lead as NO_WHATSAPP_NUMBER (dead end — never retried)."""
    tracker = SendTracker(Path(output_dir))
    entry = tracker.lead_entry(lead_id)
    if entry is None:
        out(f"Lead {lead_id} is not tracked yet — run outreach-execute for it first.")
        return 1
    previous = str(entry.get("status", ""))
    if previous == STATUS_NO_WHATSAPP:
        out(f"Lead {lead_id} is already recorded as {STATUS_NO_WHATSAPP} — nothing changed.")
        return 0
    updated = tracker.mark_no_whatsapp(lead_id, reason=reason, note=note)
    out(f"Lead {lead_id} marked as {STATUS_NO_WHATSAPP} ({NO_WHATSAPP_LABEL}).")
    out(f"  previous status: {previous or 'unknown'}")
    out(f"  recipient:       {updated.get('recipient', '') or '(none)'}")
    out(f"  reason:          {updated.get('error', '')}")
    out(f"  will be skipped in every future run (no retry)")
    out(f"  state:           {tracker.state_path}")
    logger.info("Marked %s as %s (was %s)", lead_id, STATUS_NO_WHATSAPP, previous or "unknown")
    return 0


def reclassify_no_whatsapp(
    *,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    out: Callable[[str], None] = print,
) -> int:
    """Move already-recorded 'no valid WhatsApp number' leads to the clear status.

    Only leads whose RECORDED reason is a phone-level no-WhatsApp fact
    (Pakistani landline, no usable number) are changed. Nothing is guessed and
    leads that are already SENT / AWAITING_MANUAL_SEND / NO_WHATSAPP are left
    alone.
    """
    tracker = SendTracker(Path(output_dir))
    candidates = tracker.no_whatsapp_candidates()
    out(f"[M6 RECLASSIFY] {NO_WHATSAPP_LABEL}")
    out(f"  State: {tracker.state_path}")
    out(f"  Recorded no-WhatsApp candidates: {len(candidates)}")
    if not candidates:
        out("  Nothing to change.")
        return 0
    for lead_id, recorded in candidates:
        tracker.mark_no_whatsapp(
            lead_id,
            reason=f"{NO_WHATSAPP_DETAIL} — {recorded}" if recorded else NO_WHATSAPP_DETAIL,
            note="Reclassified from a recorded phone-level reason (--reclassify-no-whatsapp).",
        )
        out(f"    - {lead_id:<42} {STATUS_NO_WHATSAPP}")
        logger.info("Reclassified %s as %s (%s)", lead_id, STATUS_NO_WHATSAPP, recorded)
    out(f"  Updated {len(candidates)} lead(s) — these numbers are never attempted again.")
    return 0


def show_state(
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    *,
    out: Callable[[str], None] = print,
    limit: int = 50,
) -> int:
    """Print the persistent send state (read-only)."""
    tracker = SendTracker(Path(output_dir))
    summary = tracker.summary()
    out("[M6 SEND STATE]")
    out(f"  File:   {tracker.state_path}")
    out(f"  Leads tracked:       {summary.get('_total_leads_tracked', 0)}")
    out(f"  Total send attempts: {summary.get('_total_attempts', 0)}")
    out("")
    for status, count in sorted(summary.items()):
        if not status.startswith("_"):
            out(f"  {status:<24} {count}")
    out("")
    out("  Leads:")
    for lead_id, entry in list(tracker.state.get("leads", {}).items())[:limit]:
        out(
            f"    - {lead_id:<42} {str(entry.get('status', '')):<22} "
            f"attempts={entry.get('attempts', 0)} recipient={entry.get('recipient', '')}"
        )
    if len(tracker.state.get("leads", {})) > limit:
        out(f"    ... and {len(tracker.state['leads']) - limit} more")
    return 0


def run_outreach_command(config: M6RunConfig, *, out: Callable[[str], None] = print, **kwargs) -> int:
    """CLI-facing wrapper: run M6 and translate the report into an exit code."""
    try:
        report = run_outreach_execution(config, out=out, **kwargs)
    except (M5SourceError, ChannelError) as exc:
        out(str(exc))
        return 1
    return 1 if report.aborted else 0


__all__ = [
    "M6RunConfig",
    "M6RunReport",
    "plan_lead",
    "no_whatsapp_reason",
    "run_outreach_execution",
    "run_outreach_command",
    "mark_lead_sent",
    "mark_no_whatsapp",
    "reclassify_no_whatsapp",
    "show_state",
    "format_plan_block",
    "print_plan",
]
