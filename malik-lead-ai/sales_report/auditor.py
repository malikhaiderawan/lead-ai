"""Milestone 5 — Lead Auditor.

Performs lightweight data-quality checks on merged lead records.
Mutates records in-place by setting:
    review_flag, review_reason,
    possible_duplicate, duplicate_reason,
    contact_quality_issues

Rules:
    - Never changes sales_potential or qualification decisions
    - Never invents contact details
    - Never converts UNKNOWN evidence to facts
    - Only flags for human review; does not auto-correct

Standard library only.
"""

from __future__ import annotations

import logging
import re
from typing import Any
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe(val: Any, default: str = "") -> str:
    if val is None:
        return default
    s = str(val).strip()
    return s if s and s.lower() not in ("null", "none") else default


def _norm_name(name: str) -> str:
    """Normalize business name for duplicate comparison."""
    return re.sub(r"[^a-z0-9]", "", name.lower().strip())


def _norm_phone(phone: str) -> str:
    """Normalize phone: strip spaces, dashes, parens."""
    return re.sub(r"[^0-9+]", "", phone.strip())


# Platform domains that host many different businesses at different paths.
# Comparing just the domain for these is meaningless for duplicate detection.
_SHARED_PLATFORM_DOMAINS: frozenset[str] = frozenset({
    "facebook.com",
    "instagram.com",
    "tiktok.com",
    "youtube.com",
    "linkedin.com",
    "twitter.com",
    "x.com",
    "l.instagram.com",
    "business.facebook.com",
    "m.facebook.com",
})


def _norm_domain(url: str) -> str:
    """
    Extract and normalize netloc from URL.
    Returns empty string for known shared-platform domains — comparing
    just 'facebook.com' or 'instagram.com' is not meaningful for deduplication.
    """
    url = url.strip()
    if not url:
        return ""
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    try:
        netloc = urlparse(url).netloc.lower().removeprefix("www.")
        if netloc in _SHARED_PLATFORM_DOMAINS:
            return ""   # Suppress — platform domain, not a meaningful dedup key
        return netloc
    except Exception:  # noqa: BLE001
        return url.lower()


def _norm_instagram(url: str) -> str:
    """Normalize Instagram URL/handle."""
    url = url.strip().lower()
    if any(cdn in url for cdn in ("cdninstagram.com", "fbcdn.net", "rsrc.php")):
        return ""  # Ignore CDN / asset links
    if any(url.endswith(ext) for ext in (".webp", ".png", ".jpg", ".jpeg", ".svg", ".gif")):
        return ""  # Ignore image assets
    url = url.removeprefix("https://").removeprefix("http://")
    url = url.removeprefix("www.").removeprefix("instagram.com/")
    url = url.strip("/")
    return url


def _phone_looks_valid(phone: str) -> bool:
    """Basic validation: must start with + or be 10+ digits."""
    p = _norm_phone(phone)
    if not p:
        return False
    if p.startswith("+"):
        return len(p) >= 10
    return len(p) >= 10


# Guaranteed-outcome phrases to detect in messages
_GUARANTEE_TERMS = [
    "guarantee revenue", "guarantee profit", "guarantee sales",
    "guarantee roi", "guarantee customers", "will increase sales",
    "will grow your business", "skyrocket", "revolutionize",
    "10x your", "game changer", "guaranteed results",
]


# ---------------------------------------------------------------------------
# Review flags — suspicious HIGH leads
# ---------------------------------------------------------------------------

def _flag_suspicious_high(rec: dict[str, Any]) -> tuple[bool, str]:
    """
    Return (should_flag, reason) if a HIGH lead looks over-qualified.
    Only flags; never changes the decision.
    """
    if rec.get("sales_potential", "").upper() != "HIGH":
        return False, ""

    ecommerce     = _safe(rec.get("_ecommerce_status")).lower()
    reachable     = _safe(rec.get("_website_reachable")).lower()
    digital       = _safe(rec.get("digital_maturity")).upper()
    opportunity   = _safe(rec.get("detected_opportunity")).lower()
    ig_status     = _safe(rec.get("_instagram_status")).lower()
    fb_status     = _safe(rec.get("_facebook_status")).lower()

    reasons: list[str] = []

    # E-commerce already present AND M3 recommended e-commerce service.
    # If M3 recommended something else (e.g., Business Digitalization), the flag
    # is misleading — M3 already made a correct decision about what to sell.
    primary_svc = _safe(rec.get("primary_service")).lower()
    ecommerce_recommended = "e-commerce" in primary_svc or "ecommerce" in primary_svc
    if ecommerce == "present" and reachable not in ("unreachable", "") and ecommerce_recommended:
        reasons.append(
            "E-commerce already present and website is reachable — verify specific gap before pitching e-commerce"
        )

    # Very strong digital presence + e-commerce + M3 recommended e-commerce
    if digital in ("STRONG", "ADVANCED") and ecommerce == "present" and ecommerce_recommended:
        reasons.append(
            f"Digital maturity is {digital} with e-commerce present — limited immediate e-commerce opportunity"
        )

    # well_established signal from opportunity detector
    if "well_established" in opportunity:
        reasons.append("Qualifier detected well-established digital setup")

    # All three channels fully verified
    if (
        ecommerce == "present"
        and ig_status == "present"
        and fb_status == "present"
        and reachable not in ("unreachable", "")
    ):
        reasons.append(
            "Website reachable + e-commerce present + Instagram + Facebook — strong setup, weak gap"
        )

    if reasons:
        return True, "HIGH flagged for review: " + "; ".join(reasons)
    return False, ""


# ---------------------------------------------------------------------------
# Review flags — suspicious LOW / SKIP leads
# ---------------------------------------------------------------------------

def _flag_suspicious_low_skip(rec: dict[str, Any]) -> tuple[bool, str]:
    """
    Return (should_flag, reason) if a LOW/SKIP lead appears under-qualified.
    """
    potential = rec.get("sales_potential", "").upper()
    if potential not in ("LOW", "SKIP"):
        return False, ""

    ecommerce   = _safe(rec.get("_ecommerce_status")).lower()
    ig_status   = _safe(rec.get("_instagram_status")).lower()
    fb_status   = _safe(rec.get("_facebook_status")).lower()
    biz_type    = _safe(rec.get("business_type")).lower()
    website     = _safe(rec.get("website"))

    reviews_raw = rec.get("_google_reviews")
    try:
        review_count = int(str(reviews_raw).strip()) if reviews_raw else 0
    except (ValueError, TypeError):
        review_count = 0

    reasons: list[str] = []

    # Active retail/product business, no e-commerce, has social presence
    if (
        "retail" in biz_type or "product" in biz_type
    ) and ecommerce != "present" and (ig_status == "present" or fb_status == "present"):
        reasons.append(
            "Active retail/product business with social presence but no e-commerce detected"
        )

    # 30+ reviews, active business, no e-commerce
    if review_count >= 30 and ecommerce != "present" and website:
        reasons.append(
            f"{review_count} Google reviews — active business with potential digital gap"
        )

    if reasons:
        return True, f"{potential} flagged for review: " + "; ".join(reasons)
    return False, ""


# ---------------------------------------------------------------------------
# Message validation
# ---------------------------------------------------------------------------

def _validate_message(rec: dict[str, Any]) -> tuple[bool, str]:
    """
    Return (has_issue, reason) if the outreach message fails quality checks.
    Only run on CONTACT FIRST / CONTACT LATER leads.
    """
    priority = rec.get("outreach_priority", "")
    if priority == "SKIP":
        return False, ""

    message = _safe(rec.get("outreach_message"))
    biz_name = _safe(rec.get("business_name"))
    is_mock = bool(rec.get("is_mock"))

    issues: list[str] = []

    # Empty message for actionable lead
    if not message:
        issues.append("Outreach message is empty for actionable lead")

    if message:
        msg_lower = message.lower()

        # Business name should appear
        if biz_name and biz_name.lower() not in msg_lower:
            issues.append(f"Business name '{biz_name}' not found in message")

        # No guarantee language
        for term in _GUARANTEE_TERMS:
            if term in msg_lower:
                issues.append(f"Prohibited language detected: '{term}'")

        # Mock label in a real run
        if not is_mock and "[mock]" in msg_lower:
            issues.append("Message contains [MOCK] label — run 'outreach' without --mock")

    if issues:
        return True, "Message validation: " + "; ".join(issues)
    return False, ""


# ---------------------------------------------------------------------------
# Contact quality checks
# ---------------------------------------------------------------------------

def _check_contact_quality(rec: dict[str, Any]) -> str:
    """Return a pipe-separated string of contact quality issues, or empty string."""
    issues: list[str] = []

    channel = _safe(rec.get("outreach_channel")).strip()
    phone   = _safe(rec.get("phone"))
    ig      = _safe(rec.get("instagram"))
    fb      = _safe(rec.get("facebook"))

    # Channel vs evidence consistency
    if channel == "WhatsApp" and not phone:
        issues.append("WhatsApp recommended but no phone number in data")
    elif channel == "Instagram DM" and not ig:
        issues.append("Instagram DM recommended but no Instagram URL in data")
    elif channel == "Facebook" and not fb:
        issues.append("Facebook recommended but no Facebook URL in data")

    # Phone format check
    if phone and not _phone_looks_valid(phone):
        issues.append(f"Phone number appears malformed: '{phone}'")

    return " | ".join(issues)


# ---------------------------------------------------------------------------
# Duplicate detection
# ---------------------------------------------------------------------------

def _detect_duplicates(records: list[dict[str, Any]]) -> None:
    """
    Mark possible duplicates in-place.
    Checks: normalized business name, normalized phone, normalized website domain,
            normalized Instagram handle.
    Never deletes records.
    """
    seen_names:   dict[str, str] = {}  # norm_name → lead_id
    seen_phones:  dict[str, str] = {}  # norm_phone → lead_id
    seen_domains: dict[str, str] = {}  # norm_domain → lead_id
    seen_ig:      dict[str, str] = {}  # norm_ig → lead_id

    for rec in records:
        lead_id   = rec["lead_id"]
        dup_reasons: list[str] = []

        # Name — only flag if the normalized name is genuinely specific (not a generic term)
        # AND there is at least one corroborating identifier (phone, website, social handle).
        name = _norm_name(_safe(rec.get("business_name")))
        _generic_name_terms = frozenset({
            "brandedwear", "clothingbrand", "brandsstore", "fashionstore",
            "clothingstore", "brandstore", "brandswear", "topbrands",
            "multibrandstore", "store", "shop", "boutique", "collection",
        })
        phone_val = _norm_phone(_safe(rec.get("phone")))
        website_val = _safe(rec.get("website"))
        ig_val = _norm_instagram(_safe(rec.get("instagram")))
        has_corroborating_id = bool(phone_val or website_val or ig_val)
        if name and len(name) > 4 and name not in _generic_name_terms:
            if name in seen_names and seen_names[name] != lead_id:
                if has_corroborating_id:
                    # Strong: name + at least one other ID present
                    dup_reasons.append(
                        f"Same business name as {seen_names[name]} (name-only match — verify manually)"
                    )
                # If no corroborating ID exists, skip — name alone is too weak
            else:
                seen_names[name] = lead_id

        # Phone
        phone = _norm_phone(_safe(rec.get("phone")))
        if phone and len(phone) >= 7:
            if phone in seen_phones and seen_phones[phone] != lead_id:
                dup_reasons.append(
                    f"Same phone as {seen_phones[phone]}"
                )
            else:
                seen_phones[phone] = lead_id

        # Website domain
        domain = _norm_domain(_safe(rec.get("website")))
        if domain and "example" not in domain:  # ignore placeholder domains
            if domain in seen_domains and seen_domains[domain] != lead_id:
                dup_reasons.append(
                    f"Same website domain ({domain}) as {seen_domains[domain]}"
                )
            else:
                seen_domains[domain] = lead_id

        # Instagram handle — skip if it resolves to a platform root or generic path
        ig = _norm_instagram(_safe(rec.get("instagram")))
        _ig_generic = frozenset({"", "instagram", "wix", "l", "https"})
        if ig and len(ig) > 3 and ig not in _ig_generic:
            if ig in seen_ig and seen_ig[ig] != lead_id:
                dup_reasons.append(
                    f"Same Instagram handle as {seen_ig[ig]}"
                )
            else:
                seen_ig[ig] = lead_id

        if dup_reasons:
            rec["possible_duplicate"] = True
            rec["duplicate_reason"]   = " | ".join(dup_reasons)
            logger.info("Possible duplicate: %s — %s", lead_id, rec["duplicate_reason"])


# ---------------------------------------------------------------------------
# Main audit function
# ---------------------------------------------------------------------------

def audit_leads(records: list[dict[str, Any]]) -> dict[str, int]:
    """
    Run all audit checks on the merged records list.
    Mutates records in-place.

    Returns:
        dict with counts: {
            "review_flagged": N,
            "possible_duplicates": N,
            "contact_issues": N,
        }
    """
    counts = {"review_flagged": 0, "possible_duplicates": 0, "contact_issues": 0}

    # Duplicate detection first (needs all records)
    _detect_duplicates(records)
    counts["possible_duplicates"] = sum(1 for r in records if r.get("possible_duplicate"))

    for rec in records:
        flag_reasons: list[str] = []

        # Suspicious HIGH
        flagged, reason = _flag_suspicious_high(rec)
        if flagged:
            flag_reasons.append(reason)

        # Suspicious LOW/SKIP
        flagged, reason = _flag_suspicious_low_skip(rec)
        if flagged:
            flag_reasons.append(reason)

        # Message validation
        flagged, reason = _validate_message(rec)
        if flagged:
            flag_reasons.append(reason)

        # Contact quality
        contact_issues = _check_contact_quality(rec)
        if contact_issues:
            rec["contact_quality_issues"] = contact_issues
            flag_reasons.append(f"Contact issues: {contact_issues}")
            counts["contact_issues"] += 1

        if flag_reasons:
            rec["review_flag"]   = True
            rec["review_reason"] = " | ".join(flag_reasons)
            counts["review_flagged"] += 1
            logger.info(
                "Review flagged: %-35s %s",
                _safe(rec.get("business_name")),
                rec["review_reason"][:80],
            )

    logger.info(
        "Audit complete: %d review flags, %d possible duplicates, %d contact issues",
        counts["review_flagged"],
        counts["possible_duplicates"],
        counts["contact_issues"],
    )
    return counts
