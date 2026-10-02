"""Milestone 3 — Lead Qualification Engine.

Takes a list of research result dicts (from research_results.json) and produces
QualificationRecord objects with sales_potential, confidence, service matching,
outreach guidance, and final action.

Pure rule-based logic. No external APIs. No LLM calls.
All rules derived directly from the knowledge/ files.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .knowledge_loader import (
    SERVICES,
    get_service_by_id,
    get_service_short_name,
    knowledge_files_present,
)

logger = logging.getLogger(__name__)

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"


# ---------------------------------------------------------------------------
# Output dataclass
# ---------------------------------------------------------------------------

@dataclass
class QualificationRecord:
    """One fully qualified lead record."""

    lead_id: str
    business_name: str | None
    category: str | None
    location: str | None
    phone: str | None
    mobile_phone: str | None
    whatsapp: str | None
    landline: str | None
    email: str | None
    website: str | None
    linkedin: str | None
    instagram: str | None
    facebook: str | None
    tiktok: str | None
    youtube: str | None

    # Core qualification outputs
    sales_potential: str          # HIGH | MODERATE | LOW | SKIP
    confidence: str               # HIGH | MEDIUM | LOW
    why_this_lead: str
    business_summary: str

    # Service matching
    primary_service: str
    primary_service_reason: str
    secondary_services: list[str] = field(default_factory=list)
    secondary_service_reasons: list[str] = field(default_factory=list)

    # Opportunity
    detected_opportunity: str = ""
    digital_maturity: str = ""

    # Outreach
    outreach_channel: str = ""
    outreach_angle: str = ""

    # Action
    final_action: str = ""        # CONTACT | INVESTIGATE_FURTHER | ARCHIVE | SKIP

    # Evidence trail
    evidence_used: list[str] = field(default_factory=list)
    uncertainties: list[str] = field(default_factory=list)

    qualification_timestamp: str = ""


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _is_truthy(val: Any) -> bool:
    """Return True if a value is a non-empty, non-null string that isn't 'null'."""
    if val is None:
        return False
    s = str(val).strip().lower()
    return bool(s) and s not in ("null", "none", "unknown", "missing", "")


def _safe_str(val: Any, default: str = "") -> str:
    if val is None:
        return default
    s = str(val).strip()
    return s if s and s.lower() not in ("null", "none") else default


def _clean_category(raw_category: Any) -> str:
    """Extract clean primary category name (strip multi-category comma list)."""
    text = _safe_str(raw_category)
    if not text:
        return "business"
    first = text.split(",")[0].split("|")[0].strip()
    return first if first else "business"


def _clean_location(raw_location: Any) -> str:
    """Extract clean concise location/city part (strip long raw postal address)."""
    text = _safe_str(raw_location)
    if not text:
        return ""
    for city in ("Lahore", "Karachi", "Islamabad", "Rawalpindi", "Faisalabad", "Multan", "Peshawar", "Sialkot", "Gujranwala", "Hyderabad", "Quetta"):
        if city.lower() in text.lower():
            parts = [p.strip() for p in text.split(",") if p.strip()]
            for p in parts:
                if city.lower() in p.lower():
                    idx = parts.index(p)
                    if idx > 0 and len(parts[idx-1]) < 35 and not any(c.isdigit() for c in parts[idx-1]):
                        return f"{parts[idx-1]}, {city}"
                    return p
            return city
    parts = [p.strip() for p in text.split(",") if p.strip()]
    if len(parts) >= 2:
        return f"{parts[-2]}, {parts[-1]}"
    return parts[0] if parts else ""


# ---------------------------------------------------------------------------
# Generic / platform-level URL patterns — NOT real business social profiles.
# These are redirect endpoints, theme-author pages, developer doc pages, etc.
# ---------------------------------------------------------------------------
_GENERIC_SOCIAL_EXACT: frozenset[str] = frozenset({
    "https://www.instagram.com/",
    "https://www.instagram.com",
    "https://instagram.com/",
    "https://instagram.com",
    "http://instagram.com/",
    "http://instagram.com",
    "https://www.facebook.com/",
    "https://www.facebook.com",
    "https://facebook.com/",
    "https://facebook.com",
})

_GENERIC_SOCIAL_SUBSTRINGS: tuple[str, ...] = (
    "l.instagram.com/",                     # Instagram redirect gateway
    "instagram.com/wix",                    # Wix builder page
    "facebook.com/PavoThemes",             # WordPress theme author
    "facebook.com/wix",                    # Wix builder page
    "developers.facebook.com",             # Developer docs
    "business.facebook.com/latest/inb",    # Generic Facebook inbox URL
)

# Fix 1: Social-platform domains that should NEVER count as a standalone website
# even when M2 stores them in the `website` field.
# Examples: Embellish, NUMRA, Allure stored Facebook profile URLs as website.
#           Maliha Bukhari stored an Instagram profile URL as website.
_SOCIAL_PLATFORM_WEBSITE_DOMAINS: tuple[str, ...] = (
    "facebook.com/",
    "www.facebook.com/",
    "m.facebook.com/",
    "instagram.com/",
    "www.instagram.com/",
    "tiktok.com/",
    "www.tiktok.com/",
    "youtube.com/",
    "www.youtube.com/",
    "linkedin.com/",
    "www.linkedin.com/",
)


def _website_url_is_social_platform(lead: dict[str, Any]) -> bool:
    """
    Return True when the URL stored in the `website` field belongs to a
    recognised social-media platform domain.  In these cases M2 has mistakenly
    stored a social/platform profile URL in the website field instead of the
    social-platform field.  M3 must not count this as a standalone professional
    website.
    """
    url = _safe_str(lead.get("website"), "")
    if not url:
        return False
    # Strip scheme for domain matching
    stripped = url.lower()
    for prefix in ("https://", "http://"):
        if stripped.startswith(prefix):
            stripped = stripped[len(prefix):]
            break
    for domain in _SOCIAL_PLATFORM_WEBSITE_DOMAINS:
        if stripped.startswith(domain):
            return True
    return False


def _is_generic_social_url(url: str | None) -> bool:
    """Return True if the URL is a platform root or tool page, not a real profile."""
    if not url:
        return True
    url = url.strip()
    if url in _GENERIC_SOCIAL_EXACT:
        return True
    for fragment in _GENERIC_SOCIAL_SUBSTRINGS:
        if fragment in url:
            return True
    return False


def _platform_present(lead: dict[str, Any], platform: str) -> bool:
    """
    Return True when the platform status says 'present' (or a non-generic URL exists) AND
    the stored URL is not a known generic/platform-level URL.
    """
    status = _safe_str(lead.get(f"{platform}_status"))
    url = lead.get(platform)
    if status == "present":
        return not _is_generic_social_url(url)
    if url and not _is_generic_social_url(url):
        return True
    return False


_AGGREGATOR_DOMAINS: tuple[str, ...] = (
    "marham.pk",
    "oladoc.com",
    "instacare.pk",
    "sehat.com.pk",
    "practo.com",
    "dawaai.pk",
    "tabiyat.pk",
    "shafa.pk",
)

_AGGREGATOR_NAME_PATTERNS: tuple[str, ...] = (
    r"\bmarham\b",
    r"\boladoc\b",
    r"\bfind a doctor\b",
    r"\bfind doctor\b",
    r"\bdoctor booking\b",
    r"\binstacare\b",
    r"\bshafa\.pk\b",
)


def _is_aggregator_or_directory(lead: dict[str, Any]) -> bool:
    """Return True if lead is a healthcare aggregator / directory / booking portal."""
    import re
    name = _safe_str(lead.get("business_name")).lower()
    website = _safe_str(lead.get("website")).lower()
    for dom in _AGGREGATOR_DOMAINS:
        if dom in website or dom in name:
            return True
    for pat in _AGGREGATOR_NAME_PATTERNS:
        if re.search(pat, name, re.IGNORECASE) or re.search(pat, website, re.IGNORECASE):
            return True
    return False



def _has_any_social(lead: dict[str, Any]) -> bool:
    return any(
        _platform_present(lead, p)
        for p in ("instagram", "facebook", "tiktok", "linkedin")
    )



def _social_platforms_present(lead: dict[str, Any]) -> list[str]:
    platforms = []
    for p in ("instagram", "facebook", "tiktok", "linkedin"):
        if _platform_present(lead, p):
            platforms.append(p.capitalize())
    return platforms


def _website_exists(lead: dict[str, Any]) -> bool:
    """
    Return True when M2 confirmed a website URL exists AND that URL is not
    a social-platform URL mistakenly stored in the website field.
    """
    if _safe_str(lead.get("website_status")) != "exists":
        return False
    return not _website_url_is_social_platform(lead)


def _website_reachable(lead: dict[str, Any]) -> bool:
    if _website_url_is_social_platform(lead):
        return False
    return _safe_str(lead.get("website_reachable")) not in ("unreachable", "")


def _website_status_known(lead: dict[str, Any]) -> bool:
    """
    Return True when M2 actually resolved a non-social-platform website URL.
    'unknown' or a social-platform URL in the website field both mean we
    cannot conclude a standalone professional website exists.
    """
    if _safe_str(lead.get("website_status")) != "exists":
        return False
    return not _website_url_is_social_platform(lead)


def _has_google(lead: dict[str, Any]) -> bool:
    return _is_truthy(lead.get("google_maps_url"))


def _has_rating(lead: dict[str, Any]) -> bool:
    return _is_truthy(lead.get("google_rating"))


def _has_reviews(lead: dict[str, Any]) -> bool:
    r = lead.get("google_reviews")
    if not _is_truthy(r):
        return False
    try:
        return int(str(r).strip()) > 0
    except (ValueError, TypeError):
        return False


def _review_count(lead: dict[str, Any]) -> int:
    r = lead.get("google_reviews")
    if not _is_truthy(r):
        return 0
    try:
        return int(str(r).strip())
    except (ValueError, TypeError):
        return 0


def _has_phone(lead: dict[str, Any]) -> bool:
    return _is_truthy(lead.get("phone"))


def _ecommerce_present(lead: dict[str, Any]) -> bool:
    return _safe_str(lead.get("ecommerce_status")) == "present"


def _is_retail_business(lead: dict[str, Any]) -> bool:
    btype = _safe_str(lead.get("business_type")).lower()
    category = _safe_str(lead.get("category")).lower()
    retail_terms = (
        "clothing", "clothes", "store", "boutique", "shop", "fashion",
        "apparel", "garments", "retail", "products", "merchandise",
    )
    return "retail" in btype or any(t in category for t in retail_terms)


def _is_food_business(lead: dict[str, Any]) -> bool:
    btype = _safe_str(lead.get("business_type")).lower()
    category = _safe_str(lead.get("category")).lower()
    food_terms = ("cafe", "restaurant", "food", "coffee", "bakery", "dining", "hotel")
    return "food" in btype or any(t in category for t in food_terms)


def _maturity_level(maturity: str) -> int:
    """Return numeric level so we can compare maturity bands."""
    order = {
        "VERY WEAK": 0,
        "WEAK": 1,
        "BASIC": 2,
        "MODERATE": 3,
        "STRONG": 4,
        "ADVANCED": 5,
        "unknown": -1,
    }
    return order.get(maturity.upper() if maturity else "unknown", -1)


# ---------------------------------------------------------------------------
# Step 1 — Active business signal
# ---------------------------------------------------------------------------

def _active_business_signal(lead: dict[str, Any]) -> tuple[str, list[str]]:
    """
    Assess how confident we are that this is an active, real business.

    Returns:
        (level, evidence_list)
        level: "STRONG" | "MODERATE" | "WEAK" | "NONE"
    """
    evidence: list[str] = []

    has_google = _has_google(lead)
    has_rating = _has_rating(lead)
    has_reviews = _has_reviews(lead)
    has_social = _has_any_social(lead)
    has_phone = _has_phone(lead)
    has_website = _website_exists(lead)
    reviews = _review_count(lead)

    # Strongest signal: Google listing with reviews
    if has_google and has_rating and has_reviews and reviews >= 10:
        evidence.append(
            f"Google Maps listing with rating {lead.get('google_rating')} "
            f"and {reviews} reviews — confirms active business"
        )
        if has_phone:
            evidence.append("Phone number supplied")
        if has_social:
            socials = _social_platforms_present(lead)
            evidence.append(f"Social presence on {', '.join(socials)}")
        return "STRONG", evidence

    if has_google and (has_rating or has_reviews):
        evidence.append(
            f"Google Maps listing present"
            + (f" with rating {lead.get('google_rating')}" if has_rating else "")
            + (f" and {reviews} reviews" if has_reviews else "")
        )
        if has_social or has_website:
            if has_social:
                socials = _social_platforms_present(lead)
                evidence.append(f"Social presence on {', '.join(socials)}")
            if has_website:
                evidence.append("Website URL supplied")
        return "MODERATE", evidence

    if has_social:
        socials = _social_platforms_present(lead)
        evidence.append(f"Social presence on {', '.join(socials)}")
        if has_phone:
            evidence.append("Phone number supplied")
        return "MODERATE", evidence

    # Google Maps URL + valid phone + non-empty category = verifiable local business identity.
    # A business does not need reviews/rating to be a real, contactable business lead.
    # The absence of reviews only means we have less confirmation of activity, not that the
    # business is unreachable or invalid as a sales prospect.
    has_category = bool(_safe_str(lead.get("category")))
    if has_google and has_phone and has_category:
        evidence.append("Google Maps listing identified (business identity verified from input)")
        evidence.append("Phone number supplied")
        evidence.append(f"Business category: {_safe_str(lead.get('category'))}")
        return "MODERATE", evidence

    if has_google or has_social or has_website or has_phone:
        if has_google:
            evidence.append("Google Maps URL present in input")
        if has_social:
            socials = _social_platforms_present(lead)
            evidence.append(f"Social presence on {', '.join(socials)}")
        if has_website:
            evidence.append("Website URL present in input")
        if has_phone:
            evidence.append("Phone number present")
        return "WEAK", evidence

    return "NONE", ["No verifiable business presence found in research data"]


# ---------------------------------------------------------------------------
# Step 2 — Digital gap detection
# ---------------------------------------------------------------------------

def _detect_opportunity(lead: dict[str, Any]) -> tuple[str, str, list[str]]:
    """
    Identify the primary digital opportunity from evidence.

    Returns:
        (opportunity_label, opportunity_description, evidence_list)
    """
    evidence: list[str] = []
    maturity = _safe_str(lead.get("digital_maturity"), "unknown")
    ml = _maturity_level(maturity)

    has_website = _website_exists(lead)
    web_reachable = _website_reachable(lead)
    has_social = _has_any_social(lead)
    has_google = _has_google(lead)
    ecom_present = _ecommerce_present(lead)
    is_retail = _is_retail_business(lead)
    gaps: list[str] = lead.get("observed_digital_gaps", []) or []
    social_platforms = _social_platforms_present(lead)

    # Fix 1: website_status == "unknown" means M2 found NO website URL in the
    # input data at all — we cannot conclude there is no site.  This must be
    # treated as an UNKNOWN state requiring investigation, not a confirmed gap.
    website_status_known = _website_status_known(lead)

    if _is_aggregator_or_directory(lead):
        evidence.append("Identified as an online doctor booking / aggregator directory platform")
        return (
            "aggregator_directory_platform",
            "Platform is an online directory / doctor aggregator (e.g. Marham, Oladoc) — not an individual clinic or prospective web design client",
            evidence,
        )

    # --- No website URL in input data (status truly unknown) ---
    if not website_status_known and not has_website:
        evidence.append("No website URL was found in the research input data")
        if not has_social:
            evidence.append("No verified social media presence identified either")
            return (
                "no_website_url_found",
                "No website URL was present in the input data and no verified social presence "
                "was confirmed — digital presence is unknown and requires investigation",
                evidence,
            )
        if has_social:
            socials = social_platforms
            evidence.append(f"Has verified social presence on {', '.join(socials)} but no website URL in data")
            return (
                "no_website_has_social",
                f"Active on {', '.join(socials)} but no website URL found in research data",
                evidence,
            )

    # --- Website URL was found (status=exists) but could not be reached ---
    if has_website and not web_reachable:
        evidence.append("Website URL was provided but could not be reached during research")
        # NOTE: M2 currently stores http_status=None for ALL failure types
        # (DNS failures, timeouts, connection resets).  A 403 vs DNS distinction
        # is therefore NOT possible from current M2 data.  Do not attempt to
        # classify the website as broken or needing replacement — state is unknown.
        # If M2 is later extended to preserve HTTP status codes reliably, add
        # 403-specific handling here.
        evidence.append("Website content, quality, and e-commerce signals are unknown")
        return (
            "website_unreachable",
            "Website URL exists in data but could not be verified — "
            "the website's current state, quality, and capability are unknown",
            evidence,
        )

    # --- Website exists and reachable — check for e-commerce gap ---
    if has_website and web_reachable:
        if is_retail and not ecom_present:
            # Confirm: only flag e-commerce gap when M2 explicitly found NO e-commerce signals.
            # ecom_present=True means M2 detected checkout/cart/order signals on the site.
            # In that case, the business already has e-commerce — no gap to sell into.
            evidence.append("Website is reachable")
            evidence.append("Business is in a retail/product category")
            evidence.append("No e-commerce / online ordering signals were detected on the website")
            return (
                "retail_no_ecommerce",
                "Active retail/product business with a website that appears to lack e-commerce or online ordering capability",
                evidence,
            )
        if is_retail and ecom_present:
            ecom_details = lead.get("ecommerce_details") or {}
            flow_type = _safe_str(ecom_details.get("order_flow_type"))
            has_manual_flow = (
                flow_type in ("WHATSAPP_ORDERING", "CATALOG_WITH_CART_ONLY", "CATALOG_INQUIRY_ONLY")
                or any("manual" in str(g).lower() and "whatsapp" in str(g).lower() for g in gaps)
            )
            if has_manual_flow:
                evidence.append("Website is reachable with active product catalog")
                evidence.append("Order flow relies on manual WhatsApp messaging or lacks full automated checkout")
                return (
                    "manual_whatsapp_orders",
                    "Active product catalog using manual WhatsApp order processing — opportunity for 1-click WhatsApp order automation & checkout integration",
                    evidence,
                )
            # E-commerce already detected on a reachable website with checkout.
            evidence.append("Website is reachable and e-commerce/product signals were detected")
            evidence.append("Business already has an active online store or product catalog")
            # Fall through to social/google checks below — do NOT return early here.

        btype = _safe_str(lead.get("business_type")).lower()
        is_service = "service" in btype or any(kw in str(lead.get("category", "")).lower() for kw in ("clinic", "salon", "hospital", "dentist", "doctor", "consultancy", "cleaning", "spa", "therapy"))
        if is_service and any("booking" in str(g).lower() or "service_missing_booking" in str(g).lower() for g in gaps):
            evidence.append("Service business website is reachable")
            evidence.append("Lacks structured online appointment/consultation booking flow")
            return (
                "service_missing_booking",
                "Active service business website lacks automated online appointment scheduling / consultation booking flow",
                evidence,
            )

        # Strong site — limited gap
        evidence.append("Website appears to be present and reachable")
        if not has_social:
            evidence.append("No social media presence identified")
            return (
                "no_social",
                "Has a website but no identified social media presence",
                evidence,
            )
        if not has_google:
            evidence.append("No Google Maps listing confirmed")
            return (
                "no_google_presence",
                "Has website and social presence but no confirmed Google Maps listing",
                evidence,
            )
        # Everything looks established
        return (
            "well_established",
            "Business appears to have a well-established digital presence",
            evidence,
        )

    # Fallback
    return (
        "unknown_opportunity",
        "Insufficient data to determine a clear digital opportunity",
        evidence,
    )


# ---------------------------------------------------------------------------
# Step 3 — Service matching
# ---------------------------------------------------------------------------

def _match_primary_service(
    lead: dict[str, Any],
    opportunity_label: str,
    active_signal: str,
) -> tuple[str, str]:
    """
    Match the single best primary service based on evidence.

    Returns:
        (service_id, reason)
    """
    has_website = _website_exists(lead)
    web_reachable = _website_reachable(lead)
    is_retail = _is_retail_business(lead)
    ecom_present = _ecommerce_present(lead)
    maturity = _safe_str(lead.get("digital_maturity"), "unknown")
    ml = _maturity_level(maturity)

    name = _safe_str(lead.get("business_name"), "This business")
    category = _clean_category(lead.get("category"))
    location = _clean_location(lead.get("location"))
    loc_str = f" in {location}" if location else ""

    # Aggregator / Directory Platform → None
    if opportunity_label == "aggregator_directory_platform":
        return (
            "none",
            (
                f"{name} is an online healthcare directory or aggregator platform "
                "and is not an individual clinic/business prospect for website services."
            ),
        )

    # No website URL found in input data + no verified social → Business Digitalization
    if opportunity_label == "no_website_url_found":
        return (
            "business_digitalization",
            (
                f"{name} ({category}{loc_str}) has no website URL in the research data "
                "and no verified social media presence was confirmed. "
                "MalikAxiom's Business Digitalization package can establish a complete "
                "professional digital foundation — website, Google profile, and social accounts."
            ),
        )

    # Social present but no website URL → Business Digitalization
    if opportunity_label == "no_website_has_social":
        return (
            "business_digitalization",
            (
                f"{name} ({category}{loc_str}) has a social presence but no dedicated website. "
                "MalikAxiom's Business Digitalization package directly addresses this gap."
            ),
        )

    # Website exists but unreachable (DNS/network failure) → INVESTIGATE first,
    # primary service is Web Development but confidence is low
    if opportunity_label == "website_unreachable":
        return (
            "web_development",
            (
                f"{name}'s website could not be reached during research (DNS/network error). "
                "Whether the site is functional, up-to-date, or well-presented is unknown. "
                "Investigation is needed before a confident recommendation can be made."
            ),
        )

    # Note: website_access_blocked label is not generated by current M2 data
    # (http_status is always None for failures). No handler needed here.

    # Retail with website but no e-commerce → E-Commerce
    if opportunity_label == "retail_no_ecommerce":
        return (
            "ecommerce",
            (
                f"{name} is a {category} business with a website, but no e-commerce "
                "or online ordering signals were detected. MalikAxiom can add or build "
                "a proper product catalog and ordering system."
            ),
        )

    # Retail with catalog / manual WhatsApp orders → E-Commerce & WhatsApp Automation
    if opportunity_label == "manual_whatsapp_orders":
        return (
            "ecommerce",
            (
                f"{name} is a {category} business with an active catalog that takes orders manually via WhatsApp. "
                "MalikAxiom can implement 1-click WhatsApp checkout automation and order management to save staff time and boost conversions."
            ),
        )

    # Service business missing online booking flow → Business Automation
    if opportunity_label == "service_missing_booking":
        return (
            "business_automation",
            (
                f"{name} is a {category} business with a website that lacks automated appointment scheduling or quote booking. "
                "MalikAxiom can add structured online consultation and appointment booking flows."
            ),
        )

    # Has website + reachable but no social → Social media / Digitalization
    if opportunity_label == "no_social":
        return (
            "business_digitalization",
            (
                f"{name} has a website but no identified social media presence. "
                "MalikAxiom's digitalization package includes social account setup "
                "and branded content to complete the digital presence."
            ),
        )

    # Has website + social but no Google → still Digitalization (Google profile setup)
    if opportunity_label == "no_google_presence":
        return (
            "business_digitalization",
            (
                f"{name} has a website and social presence but no confirmed Google "
                "Maps / Business Profile listing. MalikAxiom's package includes "
                "Google Business Profile and Maps setup for improved local visibility."
            ),
        )

    # Well established — no clear primary fit
    return (
        "web_development",
        (
            f"{name} appears to have an established digital presence. "
            "Any service recommendation would need closer investigation of actual "
            "website quality, UX, and specific business challenges."
        ),
    )


def _match_secondary_services(
    lead: dict[str, Any],
    primary_service_id: str,
    opportunity_label: str,
) -> tuple[list[str], list[str]]:
    """
    Identify relevant secondary / follow-on services.

    Returns:
        (service_ids, reasons)
    """
    secondary: list[str] = []
    reasons: list[str] = []

    is_retail = _is_retail_business(lead)
    is_food = _is_food_business(lead)
    has_website = _website_exists(lead)
    has_social = _has_any_social(lead)
    ecom_present = _ecommerce_present(lead)
    has_reviews = _has_reviews(lead)
    reviews = _review_count(lead)

    # If primary is digitalization, e-commerce is a follow-on for retail ONLY if
    # the business does not already have an established e-commerce presence.
    if primary_service_id == "business_digitalization" and is_retail and not ecom_present:
        secondary.append("ecommerce")
        reasons.append(
            "As a retail/product business without an existing online store, "
            "an e-commerce catalog would be a natural next step after establishing a basic digital presence."
        )

    # If primary is e-commerce, web development is a related follow-on
    if primary_service_id == "ecommerce":
        if not has_website:
            secondary.append("business_digitalization")
            reasons.append(
                "A full business digitalization package could complement the e-commerce "
                "setup by also establishing social presence and Google Business Profile."
            )
        else:
            secondary.append("web_development")
            reasons.append(
                "Website revamp or improvement could complement a new e-commerce system."
            )

    # Social Media Content secondary service is intentionally NOT assigned here.
    # Reason: having a real social profile proves presence, not a content gap.
    # M2 does not currently collect social activity signals (follower count,
    # post frequency, last post date, engagement rate).  Without such evidence,
    # any social-media-content recommendation would be speculative.
    # When M2 is extended with activity-level signals, add logic here.
    social_platforms = _social_platforms_present(lead)

    # business_automation: only include when the research data contains an explicit
    # signal of manual/repetitive processes (observed_digital_gaps or business summary).
    # High review count alone is NOT sufficient evidence.
    gaps = lead.get("observed_digital_gaps") or []
    automation_keywords = ("manual", "booking", "appointment", "scheduling", "order tracking")
    has_automation_signal = any(
        any(kw in str(g).lower() for kw in automation_keywords)
        for g in gaps
    )
    if has_automation_signal and primary_service_id != "business_automation":
        secondary.append("business_automation")
        reasons.append(
            "Research data indicates manual/repetitive processes (booking, scheduling, or order "
            "tracking) — business automation could be a relevant follow-on service."
        )

    # Deduplicate and exclude primary
    seen: set[str] = {primary_service_id}
    filtered_ids: list[str] = []
    filtered_reasons: list[str] = []
    for sid, reason in zip(secondary, reasons):
        if sid not in seen:
            seen.add(sid)
            filtered_ids.append(sid)
            filtered_reasons.append(reason)

    # Translate IDs to display names for output
    display_names = [get_service_short_name(sid) for sid in filtered_ids]
    return display_names, filtered_reasons


# ---------------------------------------------------------------------------
# Step 4 — Sales potential scoring
# ---------------------------------------------------------------------------

def _score_sales_potential(
    lead: dict[str, Any],
    active_signal: str,
    opportunity_label: str,
    primary_service_id: str,
    maturity: str,
) -> str:
    """
    Assign sales_potential: HIGH | MODERATE | LOW | SKIP.
    """
    research_status = _safe_str(lead.get("research_status"), "")
    if research_status == "ERROR":
        return "SKIP"

    # No active business signal at all → SKIP
    if active_signal == "NONE":
        return "SKIP"

    # Aggregator / directory platforms → SKIP
    if opportunity_label == "aggregator_directory_platform":
        return "SKIP"

    # Well-established with no clear gap → LOW
    if opportunity_label == "well_established":
        return "LOW"

    reviews = _review_count(lead)
    ml = _maturity_level(maturity)

    # no_website_url_found: website URL was not found in research input.
    # No website is the prime website/digitalization sales target -> HIGH sales potential!
    # Strategy rule: a local business with a valid Google Maps record + phone + category is a
    # high-fit sales prospect for website creation / digitalization.
    #
    # STRONG / MODERATE active signal → HIGH (CONTACT FIRST)
    # WEAK signal but valid identity (Maps + phone + category) → HIGH (CONTACT FIRST)
    # WEAK signal with no usable identity → LOW (genuinely thin lead)
    if opportunity_label == "no_website_url_found":
        if active_signal in ("STRONG", "MODERATE"):
            return "HIGH"
        # WEAK: check whether we have a usable business identity before archiving
        has_google_local = _has_google(lead)
        has_phone_local = _has_phone(lead)
        has_social_local = _has_any_social(lead)
        has_category_local = bool(_safe_str(lead.get("category")))
        if (has_google_local and has_category_local and (has_phone_local or has_social_local)) or has_social_local:
            return "HIGH" if (has_phone_local or has_social_local) else "MODERATE"
        return "LOW"

    # no_website_has_social: confirmed social + no website → solid gap → HIGH
    if opportunity_label == "no_website_has_social":
        if active_signal in ("STRONG", "MODERATE"):
            return "HIGH"
        has_social = _has_any_social(lead)
        if has_social:
            return "HIGH"
        return "LOW"

    # Retail with working website but no e-commerce → HIGH (clear gap + fit)
    if opportunity_label == "retail_no_ecommerce":
        if active_signal in ("STRONG", "MODERATE"):
            return "HIGH"
        return "MODERATE"

    # Retail catalog with manual WhatsApp ordering → HIGH (clear automation & checkout gap)
    if opportunity_label == "manual_whatsapp_orders":
        if active_signal in ("STRONG", "MODERATE"):
            return "HIGH"
        return "MODERATE"

    # Service business missing online booking flow → HIGH / MODERATE
    if opportunity_label == "service_missing_booking":
        if active_signal in ("STRONG", "MODERATE"):
            return "HIGH"
        return "MODERATE"

    # Unreachable website → INVESTIGATE territory.
    # Website state is unknown; cap at MODERATE regardless of review count.
    if opportunity_label == "website_unreachable":
        if active_signal in ("STRONG", "MODERATE"):
            return "MODERATE"
        return "LOW"

    # Social / Google gaps with lower maturity
    if opportunity_label in ("no_social", "no_google_presence"):
        if ml <= 2:  # BASIC or below
            return "MODERATE"
        return "LOW"

    # Unknown opportunity → MODERATE if active, LOW otherwise
    if opportunity_label == "unknown_opportunity":
        if active_signal in ("STRONG", "MODERATE"):
            return "MODERATE"
        return "LOW"

    # Fallback
    if active_signal == "WEAK":
        return "LOW"

    return "MODERATE"


# ---------------------------------------------------------------------------
# Step 5 — Confidence scoring
# ---------------------------------------------------------------------------

def _score_confidence(lead: dict[str, Any], active_signal: str) -> str:
    """
    Assign confidence based on STRENGTH OF EVIDENCE (not sales potential).
    """
    verified_facts = lead.get("verified_facts", []) or []
    unknowns = lead.get("unknowns", []) or []
    web_reachable = _website_reachable(lead)
    has_website = _website_exists(lead)

    fact_count = len(verified_facts)
    unknown_count = len(unknowns)

    # HIGH confidence: strong active signal + multiple verified facts + key gaps observable
    if active_signal == "STRONG" and fact_count >= 2 and unknown_count <= 1:
        return "HIGH"

    # MEDIUM: some verified facts or moderate active signal
    if active_signal in ("STRONG", "MODERATE") or (fact_count >= 1 and unknown_count <= 3):
        return "MEDIUM"

    # LOW: mostly unknowns
    return "LOW"


# ---------------------------------------------------------------------------
# Step 6 — Outreach channel
# ---------------------------------------------------------------------------

def _outreach_channel(lead: dict[str, Any]) -> str:
    """
    Determine best outreach channel from available evidence.
    Priority: WhatsApp (when phone/mobile exists) > Instagram DM > Email > Facebook > Contact Form > LinkedIn > unknown
    """
    if _safe_str(lead.get("whatsapp")) or _has_phone(lead):
        return "WhatsApp"
    if _platform_present(lead, "instagram"):
        return "Instagram DM"
    if _safe_str(lead.get("email")):
        return "Email"
    if _platform_present(lead, "facebook"):
        return "Facebook"
    if _safe_str(lead.get("contact_option_present")) == "present":
        return "Contact Form"
    if _platform_present(lead, "linkedin"):
        return "LinkedIn"
    return "unknown"


# ---------------------------------------------------------------------------
# Step 7 — Outreach angle
# ---------------------------------------------------------------------------

def _outreach_angle(
    lead: dict[str, Any],
    opportunity_label: str,
    primary_service_id: str,
    sales_potential: str,
) -> str:
    """
    Build a 1–2 sentence outreach angle following the
    Observation → Opportunity → Solution pattern from outreach_rules.md.
    Uses 'challenges' not 'problems'. No invented facts.
    """
    if sales_potential == "SKIP":
        return ""

    name = _safe_str(lead.get("business_name"), "Your business")
    category = _clean_category(lead.get("category"))
    location = _clean_location(lead.get("location"))
    loc_str = f" in {location}" if location else ""
    rating = _safe_str(lead.get("google_rating"))
    reviews = _review_count(lead)

    if opportunity_label in ("no_digital_presence", "no_website_url_found"):
        return (
            f"{name} appears to be an active {category}{loc_str} but no website URL was found in the "
            f"research data and no verified social presence was confirmed. "
            f"MalikAxiom can establish a complete digital foundation — website, Google profile, "
            f"and social accounts — through the Business Digitalization package."
        )

    if opportunity_label == "no_website_has_social":
        social = ", ".join(_social_platforms_present(lead))
        return (
            f"{name} is active on {social} but has no dedicated professional website. "
            f"A proper website would help customers find, trust, and contact the business more easily."
        )

    if opportunity_label == "website_unreachable_retail_ecom_gap":
        return (
            f"{name} is a {category} business — "
            "whether customers can currently discover and order products online is unclear. "
            "MalikAxiom can build or revamp an e-commerce system to make that possible."
        )

    if opportunity_label == "website_unreachable":
        intro = ""
        if rating and reviews:
            intro = (
                f"{name} has {reviews} Google reviews and a {rating} rating — "
                "indicating an active customer base — "
            )
        else:
            intro = f"{name} appears to be an active {category}{loc_str} — "
        return (
            intro
            + "but its website could not be verified during research. "
            "MalikAxiom can assess and improve the web presence to ensure it performs reliably."
        )

    if opportunity_label == "retail_no_ecommerce":
        return (
            f"{name} is an active {category}{loc_str} business with a website, but online ordering "
            "capability could not be confirmed. MalikAxiom can add a product catalog and "
            "e-commerce system to capture online customers."
        )

    if opportunity_label == "manual_whatsapp_orders":
        return (
            f"{name} has an active product catalog but currently handles orders manually via WhatsApp messaging. "
            "MalikAxiom can implement 1-click automated WhatsApp checkout to streamline order taking and boost conversions."
        )

    if opportunity_label == "service_missing_booking":
        return (
            f"{name} is an active {category}{loc_str} with a website, but lacks automated appointment/consultation booking. "
            "MalikAxiom can integrate direct scheduling to capture client bookings 24/7."
        )

    if opportunity_label == "no_social":
        return (
            f"{name} has a website but no identified social media presence. "
            "MalikAxiom can set up professional social accounts and create branded content "
            "to grow the business's online reach."
        )

    if opportunity_label == "no_google_presence":
        return (
            f"{name} appears to have a website and social presence, but a Google Business Profile "
            "listing has not been confirmed. MalikAxiom can set this up for improved local visibility."
        )

    if opportunity_label == "well_established":
        return (
            f"{name} appears to have an established digital presence. "
            "Further investigation would be needed before a targeted outreach angle can be developed."
        )

    return (
        f"MalikAxiom offers technology and digitalization services that may benefit {name}. "
        "Further investigation is recommended before outreach."
    )


# ---------------------------------------------------------------------------
# Step 8 — Why this lead
# ---------------------------------------------------------------------------

def _why_this_lead(
    lead: dict[str, Any],
    opportunity_label: str,
    sales_potential: str,
    primary_service_id: str,
    primary_service_reason: str,
    active_signal: str,
) -> str:
    """
    Directly answers: 'Why did MalikAxiom Lead AI show me this lead?'
    Must be specific to this business's evidence. Never generic.
    """
    if sales_potential == "SKIP":
        return _skip_reason(lead, active_signal, opportunity_label)

    name = _safe_str(lead.get("business_name"), "This business")
    category = _clean_category(lead.get("category"))
    location = _clean_location(lead.get("location"))
    loc_str = f" in {location}" if location else ""
    rating = _safe_str(lead.get("google_rating"))
    reviews = _review_count(lead)
    social = ", ".join(_social_platforms_present(lead))
    service_name = get_service_short_name(primary_service_id)

    # Build a specific why-statement from the evidence
    parts: list[str] = []

    # Opening: what the business is and its active signal
    if reviews and rating:
        parts.append(
            f"{name} is an active {category}{loc_str} with {reviews} Google reviews "
            f"and a {rating} rating."
        )
    elif _has_google(lead):
        parts.append(
            f"{name} is an active {category}{loc_str} with a Google Maps listing."
        )
    elif social:
        parts.append(
            f"{name} is an active {category}{loc_str} with a presence on {social}."
        )
    else:
        parts.append(f"{name} appears to be a {category}{loc_str}.")

    # Middle: specific gap observed
    if opportunity_label == "no_website_url_found":
        parts.append(
            "However, no website URL was present in the research input data and no verified "
            "social media presence was confirmed — digital presence is unverified and requires "
            "investigation before outreach."
        )
    elif opportunity_label == "no_digital_presence":
        parts.append(
            "However, no professional website or complete digital presence was found — "
            "a clear opportunity for MalikAxiom's digitalization service."
        )
    elif opportunity_label == "no_website_has_social":
        parts.append(
            f"It has a social presence on {social} but no professional website — "
            "a gap that MalikAxiom's services directly address."
        )
    elif opportunity_label == "website_unreachable_retail_ecom_gap":
        parts.append(
            "As a retail/product business, whether it has working e-commerce or online "
            "ordering capability could not be confirmed — a potential revenue channel that "
            "MalikAxiom can help build."
        )
    elif opportunity_label == "website_unreachable":
        parts.append(
            "Its website could not be verified during research — the current state, "
            "quality, and capability of its web presence is unknown. Investigation is "
            "recommended before committing to outreach."
        )
    elif opportunity_label == "retail_no_ecommerce":
        parts.append(
            "As a retail/product business with a website, no e-commerce or online ordering "
            "signals were detected — a gap MalikAxiom can address with an e-commerce system."
        )
    elif opportunity_label == "manual_whatsapp_orders":
        parts.append(
            "It has an active online catalog but processes orders manually via WhatsApp — "
            "an ideal fit for MalikAxiom's 1-click WhatsApp checkout automation."
        )
    elif opportunity_label == "service_missing_booking":
        parts.append(
            "Its website lacks an online consultation/appointment booking flow — "
            "a direct fit for MalikAxiom's Business Automation service."
        )
    elif opportunity_label == "no_social":
        parts.append(
            "While it has a website, no social media presence was identified — "
            "MalikAxiom's digitalization package includes social setup and branded content."
        )
    elif opportunity_label == "no_google_presence":
        parts.append(
            "No confirmed Google Business Profile listing was found — "
            "MalikAxiom can establish this for improved local search visibility."
        )
    elif opportunity_label == "aggregator_directory_platform":
        parts.append(
            "This business is an online healthcare aggregator or doctor directory platform (e.g. Marham, Oladoc) "
            "and is not an individual client prospect for web development services."
        )
    elif opportunity_label == "well_established":
        parts.append(
            "Its digital presence appears established. No immediately obvious service fit "
            "was detected from the available evidence."
        )
    else:
        parts.append("The research data is insufficient to identify a specific opportunity.")

    # Closing: service recommendation link
    if sales_potential in ("HIGH", "MODERATE") and opportunity_label not in ("well_established", "aggregator_directory_platform"):
        parts.append(
            f"MalikAxiom's {service_name} service is a relevant fit for the observed gap."
        )

    return " ".join(parts)


def _skip_reason(lead: dict[str, Any], active_signal: str, opportunity_label: str) -> str:
    """Generate a clear reason why this lead was skipped."""
    research_status = _safe_str(lead.get("research_status"), "")
    if research_status == "ERROR":
        return "Research failed with an unhandled error — lead cannot be reliably qualified."
    if opportunity_label == "aggregator_directory_platform":
        return "Online healthcare directory / aggregator platform (e.g. Marham / Oladoc) — not a target client."
    if active_signal == "NONE":
        return (
            "No verifiable business presence was found in the research data. "
            "This lead cannot be reliably identified as an active business."
        )
    return "Insufficient evidence to establish a meaningful business opportunity for MalikAxiom."



# ---------------------------------------------------------------------------
# Step 9 — Final action
# ---------------------------------------------------------------------------

def _final_action(
    sales_potential: str,
    confidence: str,
    lead: dict[str, Any],
    outreach_channel: str,
) -> str:
    """
    CONTACT | INVESTIGATE_FURTHER | ARCHIVE | SKIP
    """
    if sales_potential == "SKIP":
        return "SKIP"
    if sales_potential == "LOW":
        return "ARCHIVE"

    has_contact = outreach_channel not in ("", "unknown")

    opportunity_label = lead.get("_opportunity_label_", "")  # set below in qualify_lead

    if sales_potential == "HIGH":
        # High with a reachable contact AND strong confidence → CONTACT
        if has_contact and confidence in ("HIGH", "MEDIUM"):
            return "CONTACT"
        return "INVESTIGATE_FURTHER"

    if sales_potential == "MODERATE":
        # Unreachable website or unverified digital presence: always investigate before contacting
        if opportunity_label in ("website_unreachable", "no_website_url_found"):
            return "INVESTIGATE_FURTHER"
        if confidence == "HIGH" and has_contact:
            return "CONTACT"
        return "INVESTIGATE_FURTHER"

    return "INVESTIGATE_FURTHER"


# ---------------------------------------------------------------------------
# Business summary
# ---------------------------------------------------------------------------

def _business_summary(lead: dict[str, Any]) -> str:
    """Concise factual summary of the business from research data only."""
    name = _safe_str(lead.get("business_name"), "Unknown business")
    category = _clean_category(lead.get("category"))
    location = _clean_location(lead.get("location"))
    rating = _safe_str(lead.get("google_rating"))
    reviews = _review_count(lead)
    social_platforms = _social_platforms_present(lead)
    has_website = _website_exists(lead)
    web_reachable = _website_reachable(lead)
    maturity = _safe_str(lead.get("digital_maturity"), "unknown")

    parts: list[str] = []
    parts.append(f"{name} is a {category}" + (f" in {location}" if location else "") + ".")

    if rating and reviews:
        parts.append(f"Google rating: {rating} ({reviews} reviews).")
    elif rating:
        parts.append(f"Google rating: {rating}.")

    if has_website:
        if web_reachable:
            parts.append("Has a website (reachable).")
        else:
            parts.append("Website URL supplied but was not reachable during research.")
    else:
        parts.append("No website URL found.")

    if social_platforms:
        parts.append(f"Social presence: {', '.join(social_platforms)}.")
    else:
        parts.append("No identified social media presence.")

    parts.append(f"Digital maturity assessed as: {maturity}.")

    return " ".join(parts)


# ---------------------------------------------------------------------------
# Collect evidence used
# ---------------------------------------------------------------------------

def _collect_evidence_used(
    lead: dict[str, Any],
    opportunity_label: str,
    active_evidence: list[str],
) -> list[str]:
    """Collect the most relevant evidence items that drove the decision."""
    evidence: list[str] = []

    # Start with active signal evidence
    evidence.extend(active_evidence[:4])

    # Add verified facts from research
    verified = lead.get("verified_facts", []) or []
    for fact in verified[:3]:
        if fact and fact not in evidence:
            evidence.append(fact)

    # Add relevant gaps
    gaps = lead.get("observed_digital_gaps", []) or []
    for gap in gaps[:3]:
        if gap and f"Gap: {gap}" not in evidence:
            evidence.append(f"Observed gap: {gap}")

    # Remove duplicates preserving order
    seen: set[str] = set()
    deduped: list[str] = []
    for e in evidence:
        if e not in seen:
            seen.add(e)
            deduped.append(e)

    return deduped


# ---------------------------------------------------------------------------
# Main qualification function
# ---------------------------------------------------------------------------

def qualify_lead(lead: dict[str, Any]) -> QualificationRecord:
    """
    Qualify a single research record and return a QualificationRecord.
    """
    lead_id = _safe_str(lead.get("lead_id"), "unknown")
    business_name = lead.get("business_name")
    category = lead.get("category")
    location = lead.get("location")
    phone = lead.get("phone")
    maturity = _safe_str(lead.get("digital_maturity"), "unknown")

    logger.debug("Qualifying lead: %s", lead_id)

    # Step 1 — Active business signal
    active_signal, active_evidence = _active_business_signal(lead)

    # Step 2 — Detect opportunity
    opportunity_label, opportunity_description, opp_evidence = _detect_opportunity(lead)

    # Step 3 — Match primary service
    primary_service_id, primary_service_reason = _match_primary_service(
        lead, opportunity_label, active_signal
    )
    primary_service_name = get_service_short_name(primary_service_id)

    # Step 4 — Match secondary services
    secondary_names, secondary_reasons = _match_secondary_services(
        lead, primary_service_id, opportunity_label
    )

    # Step 5 — Sales potential
    sales_potential = _score_sales_potential(
        lead, active_signal, opportunity_label, primary_service_id, maturity
    )

    # Step 6 — Confidence
    confidence = _score_confidence(lead, active_signal)

    # Step 7 — Outreach channel
    channel = _outreach_channel(lead)

    # Step 8 — Outreach angle
    angle = _outreach_angle(lead, opportunity_label, primary_service_id, sales_potential)

    # Step 9 — Why this lead
    why = _why_this_lead(
        lead, opportunity_label, sales_potential,
        primary_service_id, primary_service_reason, active_signal
    )

    # Step 10 — Final action
    # Pass opportunity_label via a temporary key so _final_action can inspect it
    # without changing its public signature (M4/M5 compatibility preserved).
    lead_with_label = {**lead, "_opportunity_label_": opportunity_label}
    action = _final_action(sales_potential, confidence, lead_with_label, channel)

    # Collect evidence and uncertainties
    evidence_used = _collect_evidence_used(lead, opportunity_label, active_evidence)
    uncertainties = list(lead.get("unknowns", []) or [])

    return QualificationRecord(
        lead_id=lead_id,
        business_name=_safe_str(business_name) or None,
        category=_safe_str(category) or None,
        location=_safe_str(location) or None,
        phone=_safe_str(phone) or None,
        mobile_phone=_safe_str(lead.get("mobile_phone")) or None,
        whatsapp=_safe_str(lead.get("whatsapp")) or None,
        landline=_safe_str(lead.get("landline")) or None,
        email=_safe_str(lead.get("email")) or None,
        website=_safe_str(lead.get("website")) or None,
        linkedin=_safe_str(lead.get("linkedin")) or None,
        instagram=_safe_str(lead.get("instagram")) or None,
        facebook=_safe_str(lead.get("facebook")) or None,
        tiktok=_safe_str(lead.get("tiktok")) or None,
        youtube=_safe_str(lead.get("youtube")) or None,
        sales_potential=sales_potential,
        confidence=confidence,
        why_this_lead=why,
        business_summary=_business_summary(lead),
        primary_service=primary_service_name,
        primary_service_reason=primary_service_reason,
        secondary_services=secondary_names,
        secondary_service_reasons=secondary_reasons,
        detected_opportunity=opportunity_description,
        digital_maturity=maturity,
        outreach_channel=channel,
        outreach_angle=angle,
        final_action=action,
        evidence_used=evidence_used,
        uncertainties=uncertainties,
        qualification_timestamp=_now_iso(),
    )


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def run_qualification(
    input_json: Path | None = None,
    output_dir: Path | None = None,
) -> tuple[Path, Path, Path, int, dict[str, int]]:
    """
    Load research results, qualify all leads, and write outputs.

    Returns:
        (json_path, csv_path, report_path, total, counts_by_potential)
    """
    # Import here to avoid circular
    from .output_writer import write_json, write_csv, write_report

    in_path = input_json or (OUTPUT_DIR / "research_results.json")
    out_dir = output_dir or OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    if not in_path.is_file():
        raise FileNotFoundError(
            f"Research results not found: {in_path}\n"
            "Run 'python3 main.py research input/leads.csv' first."
        )

    # Check knowledge files
    missing = knowledge_files_present()
    if missing:
        raise FileNotFoundError(
            f"Missing knowledge files: {missing}\n"
            "Ensure the knowledge/ directory is complete."
        )

    logger.info("Loading research results from: %s", in_path)
    leads: list[dict[str, Any]] = json.loads(in_path.read_text(encoding="utf-8"))
    logger.info("Qualifying %d leads...", len(leads))

    records: list[QualificationRecord] = []
    counts: dict[str, int] = {"HIGH": 0, "MODERATE": 0, "LOW": 0, "SKIP": 0}

    for lead in leads:
        try:
            record = qualify_lead(lead)
            records.append(record)
            counts[record.sales_potential] = counts.get(record.sales_potential, 0) + 1
            logger.info(
                "  %-40s → %-8s [%s]",
                (_safe_str(lead.get("business_name"), "?"))[:40],
                record.sales_potential,
                record.confidence,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("Error qualifying lead %s: %s", lead.get("lead_id", "?"), exc)
            # Create a SKIP record for failed leads
            records.append(
                QualificationRecord(
                    lead_id=_safe_str(lead.get("lead_id"), "unknown"),
                    business_name=_safe_str(lead.get("business_name")) or None,
                    category=_safe_str(lead.get("category")) or None,
                    location=_safe_str(lead.get("location")) or None,
                    phone=_safe_str(lead.get("phone")) or None,
                    mobile_phone=_safe_str(lead.get("mobile_phone")) or None,
                    whatsapp=_safe_str(lead.get("whatsapp")) or None,
                    landline=_safe_str(lead.get("landline")) or None,
                    email=_safe_str(lead.get("email")) or None,
                    website=_safe_str(lead.get("website")) or None,
                    linkedin=_safe_str(lead.get("linkedin")) or None,
                    instagram=_safe_str(lead.get("instagram")) or None,
                    facebook=_safe_str(lead.get("facebook")) or None,
                    tiktok=_safe_str(lead.get("tiktok")) or None,
                    youtube=_safe_str(lead.get("youtube")) or None,
                    sales_potential="SKIP",
                    confidence="LOW",
                    why_this_lead=f"Qualification failed with an error: {exc}",
                    business_summary="Qualification error.",
                    primary_service="None",
                    primary_service_reason="",
                    secondary_services=[],
                    secondary_service_reasons=[],
                    detected_opportunity="Qualification error",
                    digital_maturity="unknown",
                    outreach_channel="unknown",
                    outreach_angle="None",
                    final_action="SKIP",
                    evidence_used=[],
                    uncertainties=[str(exc)],
                    qualification_timestamp=_now_iso(),
                )
            )
            counts["SKIP"] = counts.get("SKIP", 0) + 1

    json_path = out_dir / "qualification_results.json"
    csv_path = out_dir / "qualification_results.csv"
    report_path = out_dir / "qualified_leads_report.md"

    write_json(json_path, records)
    write_csv(csv_path, records)
    write_report(report_path, records, counts, str(in_path))

    logger.info(
        "Qualification complete: %d HIGH, %d MODERATE, %d LOW, %d SKIP",
        counts.get("HIGH", 0),
        counts.get("MODERATE", 0),
        counts.get("LOW", 0),
        counts.get("SKIP", 0),
    )

    return json_path, csv_path, report_path, len(leads), counts
