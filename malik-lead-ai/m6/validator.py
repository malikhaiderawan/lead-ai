"""M6 — pre-send validation.

A message only becomes sendable when every check passes. Any failure means
``NOT_READY`` and M6 does NOT send. Every failing reason is stored so the
user can see exactly why.

Checks (task spec §11 + §19):
    1. business name exists
    2. recipient exists (already-normalised PK WhatsApp number)
    3. channel exists and is supported by this M6 build
    4. the opportunity/service comes from M5 (M3/M4) — not from M6
    5. message is not empty and keeps the required structure
    6. message is not excessively long (body word budget + char budget)
    7. no placeholder (``[Business Name]``, ``{...}``, ``<...>``)
    8. no ``None`` / ``N/A`` / ``null`` / ``undefined`` tokens
    9. no unsupported claim (revenue/profit/ROI/price/urgency words)
   10. MalikAxiom contact details are exactly the approved ones, and no
       foreign phone / email / URL was injected
   10b. a first-touch message carries no link and no email address at all

   11. no duplicate send already recorded
"""

from __future__ import annotations

import re

from .config import (
    ALLOWED_EMAILS,
    ALLOWED_LINK_HOSTS,
    BANNED_CLAIM_PHRASES,
    CHANNEL_WHATSAPP,
    CHANNEL_WHATSAPP_PLAYWRIGHT,
    FIRST_TOUCH_ALLOWS_LINKS,
    GREETING,
    MAX_MESSAGE_CHARS,
    MIN_BODY_WORDS,
    PLACEHOLDER_TOKENS,
    REQUIRED_CONTACT_TOKENS,
    WHATSAPP_DISPLAY,
    WHATSAPP_E164,
)
from .message_builder import BuiltMessage, word_count
from .models import M5Lead, ValidationResult

# Service names that must never appear in the *opportunity* sentence unless
# they are the M5-approved service (M6 must not invent a different opportunity).
KNOWN_SERVICE_PHRASES: tuple[str, ...] = (
    "business digitalization", "business digitalisation",
    "web development", "mobile development", "mobile app",
    "e-commerce", "ecommerce", "shopify",
    "ai development", "ai integration", "business automation",
    "game development", "social media content",
)

_BRACKET_PLACEHOLDER = re.compile(r"[\[\{<][^\]\}>]{0,60}[\]\}>]")
_EMAIL_PATTERN = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]{2,}")
_URL_PATTERN = re.compile(r"(?:https?://|www\.)[^\s)]+")
_PHONE_PATTERN = re.compile(r"(?:\+?\d[\d\s()\-]{6,}\d)")
_ALLOWED_PHONE_FORMS = (WHATSAPP_DISPLAY, WHATSAPP_E164, WHATSAPP_E164.lstrip("+"))
_SIGNATURE_MARKER = "— Haider Nawaz"


def _token_present(text_lower: str, token: str) -> bool:
    """Word-boundary aware presence check (so 'na' never matches 'Nation')."""
    return re.search(rf"(?<![a-z0-9]){re.escape(token.lower())}(?![a-z0-9])", text_lower) is not None


def _host_of(url: str) -> str:
    text = url.strip().rstrip(".,);\"'")
    text = text.split("//", 1)[-1]
    return text.split("/", 1)[0].lower()



def validate_message(
    built: BuiltMessage,
    lead: M5Lead,
    *,
    recipient: str,
    channel: str,
    already_sent: bool = False,
) -> ValidationResult:
    """Run every M6 pre-send check and return the aggregated result."""
    result = ValidationResult(status="PASS")
    message = built.text or ""
    lowered = message.lower()

    # 1. business name -----------------------------------------------------
    from .message_builder import clean_business_name
    business_name = clean_business_name((lead.business_name or "").strip())
    if not business_name:
        result.add("missing_business_name")
    elif business_name.lower() in ("unknown", "n/a", "none"):
        result.add("placeholder_business_name")

    # 2. recipient ---------------------------------------------------------
    if not recipient:
        result.add("missing_recipient")
    elif not re.fullmatch(r"\+92\d{10}", recipient):
        result.add(f"invalid_recipient_format:{recipient}")

    # 3. channel -----------------------------------------------------------
    if not channel:
        result.add("missing_channel")
    elif channel not in (CHANNEL_WHATSAPP, CHANNEL_WHATSAPP_PLAYWRIGHT):
        result.add(f"unsupported_channel:{channel}")

    # 4. service must come from M5 ----------------------------------------
    m5_service = (lead.primary_service or "").strip()
    if not m5_service:
        result.add("missing_m5_service")
    elif built.service.strip().lower() != m5_service.lower():
        result.add(f"service_mismatch_with_m5:{built.service}!={m5_service}")
    else:
        svc_lowered = m5_service.lower()
        has_match = (
            svc_lowered in lowered
            or ("digital" in svc_lowered and ("digital" in lowered or "website" in lowered))
            or ("web" in svc_lowered and ("website" in lowered or "web" in lowered))
            or ("e-commerce" in svc_lowered and ("e-commerce" in lowered or "online store" in lowered or "ecommerce" in lowered))
            or ("automation" in svc_lowered and "automation" in lowered)
            or ("ai" in svc_lowered and "ai" in lowered)
        )
        if not has_match:
            result.add("message_does_not_mention_m5_service")
        else:
            opportunity = (built.opportunity_line or "").lower()
            for phrase in KNOWN_SERVICE_PHRASES:
                if phrase in opportunity and phrase not in m5_service.lower() and m5_service.lower() not in phrase:
                    is_allowed_combo = (
                        ("web" in phrase and ("digital" in m5_service.lower() or "web" in m5_service.lower()))
                        or (phrase in ("e-commerce", "ecommerce", "shopify") and ("digital" in m5_service.lower() or "web" in m5_service.lower() or "e-commerce" in m5_service.lower() or "ecommerce" in m5_service.lower()))
                        or (phrase in ("business digitalization", "business digitalisation") and ("web" in m5_service.lower() or "e-commerce" in m5_service.lower() or "digital" in m5_service.lower()))
                        or (phrase in ("business automation", "automation") and ("digital" in m5_service.lower() or "automation" in m5_service.lower() or "e-commerce" in m5_service.lower()))
                        or (phrase in ("social media content", "social content") and ("digital" in m5_service.lower() or "content" in m5_service.lower() or "social" in m5_service.lower()))
                    )
                    if not is_allowed_combo:
                        result.add(f"unapproved_service_in_opportunity:{phrase}")
                        break

    # 5. message structure -------------------------------------------------
    if not message.strip():
        result.add("empty_message")
    else:
        if not message.startswith(GREETING):
            result.add("missing_greeting")
        for token in REQUIRED_CONTACT_TOKENS:
            if token.lower() not in lowered:
                result.add(f"missing_contact_token:{token}")

    # 6. length ------------------------------------------------------------
    body = message.split(_SIGNATURE_MARKER, 1)[0]
    body_words = word_count(body)
    if body_words < MIN_BODY_WORDS:
        result.add(f"message_too_short:{body_words}w<{MIN_BODY_WORDS}w")
    if body_words > built.max_body_words:
        result.add(f"message_too_long:{body_words}w>{built.max_body_words}w")
    if len(message) > MAX_MESSAGE_CHARS:
        result.add(f"message_too_long_chars:{len(message)}>{MAX_MESSAGE_CHARS}")

    # 7. placeholders ------------------------------------------------------
    if _BRACKET_PLACEHOLDER.search(message):
        result.add("placeholder_bracket_found")
    for token in PLACEHOLDER_TOKENS:
        if _token_present(lowered, token):
            result.add(f"placeholder_token_found:{token}")
            break

    # 8/9. banned claims ---------------------------------------------------
    for phrase in BANNED_CLAIM_PHRASES:
        if _token_present(lowered, phrase):
            result.add(f"banned_claim_phrase:{phrase}")
            break

    # 10. contact integrity -------------------------------------------------
    result.reasons.extend(_check_contacts(message))

    # 10b. first-touch hygiene ---------------------------------------------
    # A first-touch message must carry NO clickable link and NO email address:
    # "same template + URL, sent cold to many strangers" is the exact pattern
    # WhatsApp's anti-spam enforcement restricts accounts for.
    if not FIRST_TOUCH_ALLOWS_LINKS:
        for url in _URL_PATTERN.findall(message):
            result.add(f"first_touch_link_not_allowed:{_host_of(url)}")
            break
        for email in _EMAIL_PATTERN.findall(message):
            result.add(f"first_touch_email_not_allowed:{email}")
            break

    # 11. duplicates --------------------------------------------------------
    if already_sent:
        result.add("duplicate_send_already_recorded")

    if result.reasons:
        result.status = "NOT_READY"
    return result



def _check_contacts(message: str) -> list[str]:
    """Verify the fixed contact block and reject foreign contact details."""
    reasons: list[str] = []

    stripped = message
    for allowed in _ALLOWED_PHONE_FORMS:
        stripped = stripped.replace(allowed, " ")

    for match in _PHONE_PATTERN.findall(stripped):
        digits = re.sub(r"\D", "", match)
        if len(digits) >= 7:
            reasons.append(f"unexpected_phone_number:{match.strip()}")
            break

    for email in _EMAIL_PATTERN.findall(message):
        if email.lower() not in ALLOWED_EMAILS:
            reasons.append(f"unexpected_email:{email}")
            break

    for url in _URL_PATTERN.findall(message):
        host = _host_of(url)
        if host not in ALLOWED_LINK_HOSTS:
            reasons.append(f"unexpected_link:{host}")
            break

    return reasons


__all__ = ["validate_message", "KNOWN_SERVICE_PHRASES"]
