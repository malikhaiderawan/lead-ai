"""M6 — small URL / social-presence classifiers.

These helpers interpret *existing* M5 fields (website / instagram / facebook …)
so that the message builder can word an observation truthfully.

They mirror the shared-platform logic already used by
``sales_report.auditor`` (same intent, kept local so M6 does not depend on
M5 internals). They never create new facts — they only tell M6 whether a URL
is the business's own website, a social profile, or an asset/CDN link.
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

# Domains that host many different businesses at different paths.
SHARED_PLATFORM_DOMAINS: frozenset[str] = frozenset({
    "facebook.com", "m.facebook.com", "business.facebook.com", "fb.com", "l.facebook.com", "lm.facebook.com",
    "instagram.com", "l.instagram.com",
    "tiktok.com", "youtube.com", "youtu.be",
    "linkedin.com", "twitter.com", "x.com", "wa.me", "whatsapp.com",
})

_PLATFORM_LABELS: dict[str, str] = {
    "instagram.com": "Instagram",
    "l.instagram.com": "Instagram",
    "facebook.com": "Facebook",
    "m.facebook.com": "Facebook",
    "business.facebook.com": "Facebook",
    "fb.com": "Facebook",
    "l.facebook.com": "Facebook",
    "lm.facebook.com": "Facebook",
    "tiktok.com": "TikTok",
    "linkedin.com": "LinkedIn",
    "youtube.com": "YouTube",
    "youtu.be": "YouTube",
    "twitter.com": "Twitter",
    "x.com": "Twitter",
}

VALID_PLATFORM_NAMES: frozenset[str] = frozenset({
    "Instagram", "Facebook", "TikTok", "LinkedIn", "YouTube", "Twitter"
})

_ASSET_HINTS = ("cdninstagram.com", "fbcdn.net", "rsrc.php", "static.")
_ASSET_EXTENSIONS = (".webp", ".png", ".jpg", ".jpeg", ".svg", ".gif", ".ico", ".css", ".js")


def classify_url(url: str) -> tuple[str, str]:
    """Classify a URL: ``("own_website"|"social"|"asset"|"unknown", label)``."""
    text = (url or "").strip()
    if not text:
        return "unknown", ""

    lowered = text.lower()
    if any(hint in lowered for hint in _ASSET_HINTS):
        return "asset", ""
    if lowered.endswith(_ASSET_EXTENSIONS):
        return "asset", ""

    candidate = text if text.startswith(("http://", "https://")) else "https://" + text
    try:
        netloc = urlparse(candidate).netloc.lower()
        path = urlparse(candidate).path
    except Exception:  # noqa: BLE001
        return "unknown", ""

    host = netloc.removeprefix("www.").removeprefix("m.")
    if host in _PLATFORM_LABELS:
        if not path or path in ("/", ""):
            return "social_root", _PLATFORM_LABELS[host]
        return "social", _PLATFORM_LABELS[host]
    if host in SHARED_PLATFORM_DOMAINS:
        return "social", host.split(".")[0].capitalize()
    return "own_website", host


def detect_social_platforms(raw_fields: dict[str, str]) -> list[str]:
    """Which social platforms does M5 evidence actually show? (sorted, unique)."""
    found: set[str] = set()
    for field in ("instagram", "facebook", "tiktok", "linkedin", "youtube"):
        value = (raw_fields.get(field) or "").strip()
        if not value:
            continue
        kind, label = classify_url(value)
        if kind in ("social", "social_root") and label:
            resolved = label if label in VALID_PLATFORM_NAMES else field.capitalize()
            if resolved in VALID_PLATFORM_NAMES:
                found.add(resolved)
    # A social URL sometimes lands in the `website` column (M2 behaviour for
    # Arbrandzone: website = instagram.com/arbrandzone).
    kind, label = classify_url(raw_fields.get("website", ""))
    if kind in ("social", "social_root") and label:
        if label in VALID_PLATFORM_NAMES:
            found.add(label)
    return sorted(found)


def has_own_website(raw_fields: dict[str, str]) -> bool:
    """True only when M5 evidence shows the business's own (non-social) site."""
    kind, _label = classify_url(raw_fields.get("website", ""))
    return kind == "own_website"


def is_social_only(raw_fields: dict[str, str]) -> bool:
    return not has_own_website(raw_fields) and bool(detect_social_platforms(raw_fields))


_CATEGORY_PATTERN = re.compile(r"\bis an active ([^.]{2,80}?) in ")


def extract_category_from_text(text: str) -> str:
    """Extract the evidence-based category phrase M3 wrote, e.g. 'Clothing store'.

    Returns '' when no such phrase exists — M6 then simply omits the category
    instead of guessing one.
    """
    if not text:
        return ""
    match = _CATEGORY_PATTERN.search(text)
    if not match:
        return ""
    category = match.group(1).strip()
    if category.lower() in ("business", "company"):
        return ""
    return category


__all__ = [
    "classify_url",
    "detect_social_platforms",
    "has_own_website",
    "is_social_only",
    "extract_category_from_text",
    "SHARED_PLATFORM_DOMAINS",
]
