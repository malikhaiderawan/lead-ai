"""M6 — configuration constants.

Everything in this file is a hard, human-owned value. No AI/LLM output may
override it. If a value needs changing, it is changed here, once.

Contact details are FIXED. M6's validator fails any message whose contact
block differs from these values (see ``m6.validator``).

NOTE on pricing: the knowledge base (``knowledge/business_digitalization.md``)
documents the flagship Business Digitalization package at 20,000 PKR, while
the current local low-budget strategy uses "starting from around PKR 10,000"
for entry-level work. ``PRICING_SENTENCE`` below is the *only* pricing wording
M6 is allowed to send, it is DISABLED by default (``--include-pricing``), and
it is never applied to non-Pakistani / non-entry-level leads. M6 never
promises a fixed price.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

M6_VERSION: Final[str] = "1.0.0"

PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT_DIR: Final[Path] = PROJECT_ROOT / "output"

# ---------------------------------------------------------------------------
# M5 inputs (M6 reads these; it never rewrites them)
# ---------------------------------------------------------------------------

M5_MASTER_CSV: Final[str] = "malikaxiom_sales_leads.csv"
M5_CONTACT_FIRST_CSV: Final[str] = "contact_first.csv"

# ---------------------------------------------------------------------------
# M6 artifacts (created / appended by M6 only)
# ---------------------------------------------------------------------------

M6_STATE_FILENAME: Final[str] = "m6_send_state.json"
M6_RESULTS_JSON: Final[str] = "m6_outreach_results.json"
M6_RESULTS_CSV: Final[str] = "m6_outreach_results.csv"
M6_LOG_FILENAME: Final[str] = "m6_outreach.log"

# ---------------------------------------------------------------------------
# Fixed MalikAxiom identity — never modified by AI, never hallucinated
# ---------------------------------------------------------------------------

COMPANY_NAME: Final[str] = "MalikAxiom Technology"
FOUNDER_NAME: Final[str] = "Haider Nawaz"
WEBSITE_DOMAIN: Final[str] = "malikaxiomtech.com"
WHATSAPP_DISPLAY: Final[str] = "0313 0466400"
WHATSAPP_E164: Final[str] = "+923130466400"
EMAIL: Final[str] = "hello@malikaxiomtech.com"

GREETING: Final[str] = "Assalam o Alaikum 👋"

INTRO_SENTENCE: Final[str] = (
    "I'm Haider from MalikAxiom Technology. We help businesses strengthen "
    "their digital presence through websites, e-commerce, automation and AI solutions."
)

SOFT_CTA: Final[str] = "Would you be open to a quick chat?"

# FIRST-TOUCH signature: name + company only.
#
# The website link and the email address are deliberately NOT part of a
# first-touch message. WhatsApp treats "near-identical text containing a URL,
# sent to many strangers" as a spam signature, and link-carrying cold messages
# are a primary cause of account restrictions. The approved link/email live in
# ``CONTACT_LINK_LINES`` and belong to a follow-up message sent BY A HUMAN after
# the lead replies — M6 never appends them to a first touch.
SIGNATURE_LABEL: Final[str] = f"— {FOUNDER_NAME}"
SIGNATURE_LINES: Final[tuple[str, ...]] = (
    SIGNATURE_LABEL,
    COMPANY_NAME,
    f"🌐 {WEBSITE_DOMAIN}",
    f"✉️ {EMAIL}",
)

#: Approved company contact lines for FOLLOW-UP messages (once the lead has
#: replied and therefore expects the link). Never auto-appended by M6.
CONTACT_LINK_LINES: Final[tuple[str, ...]] = (
    f"🌐 {WEBSITE_DOMAIN}",
    f"✉️ {EMAIL}",
)

#: A first-touch message carries approved domain and email in the signature block.
FIRST_TOUCH_ALLOWS_LINKS: Final[bool] = True

REQUIRED_CONTACT_TOKENS: Final[tuple[str, ...]] = (
    COMPANY_NAME,
    FOUNDER_NAME,
    WEBSITE_DOMAIN,
    EMAIL,
)

ALLOWED_EMAILS: Final[frozenset[str]] = frozenset({EMAIL})
ALLOWED_LINK_HOSTS: Final[frozenset[str]] = frozenset(
    {
        "malikaxiomtech.com",
        "www.malikaxiomtech.com",
        "malikaxiomtech.com/",
        "wa.me",
        "web.whatsapp.com",
        "website-demo-five-navy.vercel.app",
        "website-demo-five-navy.vercel.app/",
    }
)
DEMO_REQUIRED_CONTACT_TOKENS: Final[tuple[str, ...]] = (
    COMPANY_NAME,
    WEBSITE_DOMAIN,
    "Haider",
)

# Only used when the user explicitly passes --include-pricing.
PRICING_SENTENCE: Final[str] = (
    "We also have practical starter solutions for small businesses, starting "
    "from around PKR 10,000 depending on the requirements."
)

# Service whose local, entry-level variant may carry the pricing sentence.
PRICING_ELIGIBLE_SERVICE: Final[str] = "Business Digitalization"

# Terms that would be an unsupported / prohibited claim in an M6 message.
BANNED_CLAIM_PHRASES: Final[tuple[str, ...]] = (
    "guarantee", "guaranteed", "guarantees",
    "revenue", "profit", "roi", "return on investment",
    "increase your sales", "boost your sales", "double your",
    "cheapest", "best price", "lowest price", "cheap website", "low-cost",
    "only 10k", "only rs", "100%", "risk free", "no risk",
    "outdated", "losing customers", "poor branding", "customer complaints",
    "low sales", "missing features", "fake", "urgent", "limited time",
    "problem", "problems",  # knowledge base rule: use "challenges"
    "there may be an opportunity",
    "couldn't verify a complete digital presence",
    "could not verify a complete digital presence",
    "unlock your potential",
    "take your business to the next level",
    "cutting-edge",
    "we are a leading",
    "help businesses leverage",
)

# Placeholder / missing-value tokens that make a message unsendable.
PLACEHOLDER_TOKENS: Final[tuple[str, ...]] = (
    "none", "n/a", "na", "null", "nan", "undefined", "tbd", "todo",
    "xxx", "yyyy", "placeholder", "insert ", "your business name",
    "lorem ipsum",
)

# ---------------------------------------------------------------------------
# Message budget (body = message before the signature)
# ---------------------------------------------------------------------------

MIN_BODY_WORDS: Final[int] = 45
MAX_BODY_WORDS: Final[int] = 90
MAX_BODY_WORDS_WITH_PRICING: Final[int] = 110
MAX_MESSAGE_CHARS: Final[int] = 1500

# ---------------------------------------------------------------------------
# Channels
# ---------------------------------------------------------------------------

CHANNEL_WHATSAPP: Final[str] = "whatsapp"
CHANNEL_WHATSAPP_PLAYWRIGHT: Final[str] = "whatsapp_playwright"

# v1 supports WhatsApp only. M5 channel values that exist today:
#   WhatsApp, Instagram DM, Facebook, Email, Contact Form, unknown
SUPPORTED_M5_CHANNELS: Final[frozenset[str]] = frozenset({"whatsapp", "wa", "whats app"})

# CLI channel aliases -> internal channel implementation names
CHANNEL_ALIASES: Final[dict[str, str]] = {
    "assist": CHANNEL_WHATSAPP,
    "whatsapp": CHANNEL_WHATSAPP,
    "link": CHANNEL_WHATSAPP,
    "playwright": CHANNEL_WHATSAPP_PLAYWRIGHT,
}

# ---------------------------------------------------------------------------
# Eligibility / safety limits
# ---------------------------------------------------------------------------

DEFAULT_ELIGIBLE_ACTIONS: Final[tuple[str, ...]] = ("CONTACT FIRST", "CONTACT LATER")

# Never allow an accidental blast. M6 refuses to send more than this per run.
#
# Lowered from 25 after a real WhatsApp restriction: 25 per run at a 20-second
# gap produced exactly the machine-like cold-outreach pattern that WhatsApp's
# anti-spam enforcement flags on unofficial automation.
MAX_SENDS_PER_RUN: Final[int] = 10
DEFAULT_SEND_LIMIT: Final[int] = MAX_SENDS_PER_RUN

# Absolute ceiling across ALL runs in one calendar day (UTC). WhatsApp looks at
# daily first-contact volume, not only per-run volume — several small runs in
# the same day still add up to a bulk pattern.
MAX_SENDS_PER_DAY: Final[int] = 20

# Hard cap on attempts per lead — M6 never retries forever.
MAX_ATTEMPTS_PER_LEAD: Final[int] = 3

# Base gap between two sends: 3 minutes.
MIN_SECONDS_BETWEEN_SENDS: Final[int] = 180

# Random extra wait added to every gap so the cadence is not a uniform
# metronome (a constant interval is itself a detectable fingerprint).
#
#   real wait = MIN_SECONDS_BETWEEN_SENDS + rand(0, SEND_INTERVAL_JITTER_SECONDS)
#             = 180s … 300s   (3–5 minutes)
SEND_INTERVAL_JITTER_SECONDS: Final[int] = 120

# Send statuses that block any further attempt (duplicate-send protection).
BLOCKING_STATUSES: Final[frozenset[str]] = frozenset(
    {"SENT", "AWAITING_MANUAL_SEND", "NO_WHATSAPP_NUMBER"}
)

# Send statuses (persisted)
STATUS_SENT: Final[str] = "SENT"
STATUS_FAILED: Final[str] = "FAILED"
STATUS_AWAITING_MANUAL: Final[str] = "AWAITING_MANUAL_SEND"
STATUS_SKIPPED_ALREADY_SENT: Final[str] = "SKIPPED_ALREADY_SENT"
STATUS_NOT_READY: Final[str] = "NOT_READY"
STATUS_NOT_ELIGIBLE: Final[str] = "NOT_ELIGIBLE"
STATUS_SKIPPED_LIMIT: Final[str] = "SKIPPED_LIMIT"
STATUS_DRY_RUN: Final[str] = "NOT SENT — DRY RUN"

# ---------------------------------------------------------------------------
# No-WhatsApp numbers (dead-end recipients)
# ---------------------------------------------------------------------------
# A "no WhatsApp" outcome is a recorded FACT, not a retryable error:
#   * the number is a Pakistani landline (WhatsApp needs a mobile),
#   * no usable phone number exists in the M5 row at all,
#   * WhatsApp Web itself rejects the number, or
#   * a human confirmed the number has no WhatsApp account.
# Because it is a fact, the status is BLOCKING: M6 never attempts that number
# again, even with ``--retry-failed``. Only an explicit ``--force-resend``
# together with an explicit ``--lead-id`` can override it.

STATUS_NO_WHATSAPP: Final[str] = "NO_WHATSAPP_NUMBER"
STATUS_SKIPPED_NO_WHATSAPP: Final[str] = "SKIPPED_NO_WHATSAPP"

#: Plain-language label used in logs and reports.
NO_WHATSAPP_LABEL: Final[str] = "NO WHATSAPP NUMBER"

#: Substring of the channel's failure detail when it detects a no-WhatsApp state.
NO_WHATSAPP_DETAIL: Final[str] = "No WhatsApp account for this number"

#: Wording WhatsApp Web itself shows for a number without an account.
NO_WHATSAPP_MARKERS: Final[tuple[str, ...]] = (
    "phone number shared via url is invalid",
    "is not on whatsapp",
    "not a valid whatsapp",
    "invalid whatsapp number",
)

#: Phone-level reasons that already prove a number can never be a WhatsApp
#: recipient (see ``m6.phone``). Matching is case-insensitive substring based.
#: Deliberately narrow: a landline can never host WhatsApp, and "no number at
#: all" is the same fact. Malformed / foreign / undeterminable numbers are data
#: quality problems, so they stay ``NOT_READY`` — M6 never guesses.
NO_WHATSAPP_PHONE_REASONS: Final[tuple[str, ...]] = (
    "pakistani_landline_not_whatsapp",
    "no_phone_number_found",
)
