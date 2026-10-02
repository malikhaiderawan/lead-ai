"""M6 — WhatsApp recipient normalisation.

Rules (see task spec §18):

* Pakistani numbers are normalised consistently to E.164: ``+923136162007``.
* Accepted Pakistan shapes:
    ``0313 6162007``  → ``+923136162007``
    ``+92 313 6162007`` / ``923136162007`` / ``3136162007`` (10-digit mobile)
* Multiple numbers in one cell (M5 often stores ``"0313 6162007, +92 313 6162007"``)
  are split and the first WhatsApp-capable one is used.
* Pakistani landlines are rejected (WhatsApp needs a mobile).
* Non-Pakistani numbers are NOT guessed or altered → ``NOT_READY``.
* Anything ambiguous → ``NOT_READY``.
"""

from __future__ import annotations

import re

from .config import WHATSAPP_E164

_SEPARATORS = re.compile(r"[,;/\n|]+")
_PHONE_CHARS = re.compile(r"[^0-9+]")


def split_phone_candidates(raw: str) -> list[str]:
    """Split a cell that may contain several phone numbers."""
    if not raw:
        return []
    parts = [p.strip() for p in _SEPARATORS.split(raw)]
    return [p for p in parts if p]


def normalize_pakistani_mobile(raw: str) -> tuple[str | None, str]:
    """Normalise ONE phone string to PK E.164.

    Returns ``(e164_or_None, reason)``. ``reason`` is empty on success.
    """
    if not raw or not raw.strip():
        return None, "empty_number"

    text = raw.strip()
    cleaned = _PHONE_CHARS.sub("", text)
    plus_count = cleaned.count("+")
    had_intl_prefix = text.replace(" ", "").replace("-", "").startswith(("+", "00"))

    if plus_count > 1:
        return None, "malformed_number"
    if cleaned.startswith("+"):
        cleaned = cleaned[1:]

    if not cleaned.isdigit():
        return None, "malformed_number"

    # 00 international prefix → + (but only when it was really an intl prefix)
    if cleaned.startswith("00") and len(cleaned) > 12:
        cleaned = cleaned[2:]

    if cleaned.startswith("92"):
        national = cleaned[2:]
    elif cleaned.startswith("0"):
        national = cleaned[1:]
    elif len(cleaned) == 10 and cleaned.startswith("3"):
        national = cleaned
    elif len(cleaned) > 11:
        # Long number that does not start with 92 → different country.
        return None, "non_pakistani_number_not_supported"
    elif had_intl_prefix and not cleaned.startswith("92"):
        return None, "non_pakistani_number_not_supported"
    else:
        national = cleaned

    if not national:
        return None, "malformed_number"

    if len(national) == 10 and national.startswith("3"):
        return f"+92{national}", ""

    if len(national) in (9, 10) and national[0] in "24589":
        # Pakistani landline (area codes 21, 42, 51, 91, ...) — WhatsApp cannot
        # be assumed on a landline, so M6 refuses instead of guessing.
        return None, "pakistani_landline_not_whatsapp"

    if len(national) in (9, 10, 11):
        return None, "invalid_pakistani_mobile_number"

    return None, "country_not_determinable"


def wa_digits(e164: str) -> str:
    """``+923136162007`` → ``923136162007`` (needed for wa.me links)."""
    return _PHONE_CHARS.sub("", e164).lstrip("+")


def resolve_recipient(field_values: list[tuple[str, str]]) -> tuple[str, str, str]:
    """Pick the first WhatsApp-capable recipient from ``[(field_name, value), ...]``.

    Returns ``(e164, field_name, reason)``; ``e164`` is empty when nothing
    usable was found and ``reason`` explains why.
    """
    reasons: list[str] = []
    for field_name, value in field_values:
        for candidate in split_phone_candidates(value):
            e164, reason = normalize_pakistani_mobile(candidate)
            if e164:
                return e164, field_name, ""
            reasons.append(f"{field_name}:{reason}")
    if not reasons:
        return "", "", "no_phone_number_found"
    return "", "", "no_valid_whatsapp_number (" + ", ".join(reasons) + ")"


__all__ = [
    "split_phone_candidates",
    "normalize_pakistani_mobile",
    "resolve_recipient",
    "wa_digits",
    "WHATSAPP_E164",
]
