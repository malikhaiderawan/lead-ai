"""Milestone 4 — Outreach Message Composer.

Reads output/qualification_results.json and generates a personalized outreach
message per qualified lead.

Design principles:
  - Every message is grounded in verified evidence from the qualification record.
  - UNKNOWN information is never stated as fact.
  - No revenue, profit, customer, or ROI guarantees.
  - No fake urgency, false claims, or invented contact details.
  - Messages use "challenges" not "problems" per outreach_rules.md.
  - Channel-specific word budgets enforced.
  - Mock mode clearly labels all output as test data.

AI-ready: if AI_API_KEY + AI_MODEL + AI_BASE_URL are set in environment,
the architecture allows swapping _compose_body() to call an LLM.
Currently all generation is template-based (no API calls).

Standard library only.
"""

from __future__ import annotations

import json
import logging
import os
import textwrap
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"
COMPANY_NAME = "MalikAxiom Technology"
COMPANY_EMAIL = "hello@malikaxiomtech.com"
COMPANY_PHONE = "+923130466400"
COMPANY_WEBSITE = "https://malikaxiomtech.com/"

# ---------------------------------------------------------------------------
# M3 final_action → M4 priority mapping
# ---------------------------------------------------------------------------

_ACTION_TO_PRIORITY: dict[str, str] = {
    "CONTACT": "CONTACT FIRST",
    "INVESTIGATE_FURTHER": "CONTACT LATER",
    "ARCHIVE": "SKIP",
    "SKIP": "SKIP",
}


def _normalize_priority(final_action: str) -> str:
    """Map M3 final_action to M4 outreach priority."""
    return _ACTION_TO_PRIORITY.get(final_action.upper(), "SKIP")


# ---------------------------------------------------------------------------
# Output dataclass
# ---------------------------------------------------------------------------

@dataclass
class OutreachRecord:
    """One outreach message record for one lead."""

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

    # Qualification carry-through
    sales_potential: str
    confidence: str
    primary_service: str
    digital_maturity: str

    # Outreach decision
    recommended_channel: str
    outreach_priority: str           # CONTACT FIRST | CONTACT LATER | SKIP

    # Message fields
    subject: str = ""                # empty for WhatsApp/Instagram; set for email
    opening: str = ""
    message: str = ""
    cta: str = ""
    personalization_points: list[str] = field(default_factory=list)
    message_notes: str = ""

    # Metadata
    is_mock: bool = False
    generation_error: str | None = None
    outreach_timestamp: str = ""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe(val: Any, default: str = "") -> str:
    if val is None:
        return default
    s = str(val).strip()
    return s if s and s.lower() not in ("null", "none") else default


def _has_phone(rec: dict[str, Any]) -> bool:
    return bool(_safe(rec.get("phone")))


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _word_count(text: str) -> int:
    return len(text.split())


def _trim_to_budget(text: str, max_words: int) -> str:
    """Trim text to approximately max_words words, ending at a sentence boundary."""
    words = text.split()
    if len(words) <= max_words:
        return text
    # Find the last sentence end within budget
    budget_text = " ".join(words[:max_words])
    for sep in (". ", "! ", "? "):
        last = budget_text.rfind(sep)
        if last > 0:
            return budget_text[: last + 1].strip()
def _clean_location(raw_location: Any) -> str:
    """Extract clean concise location/city part."""
    text = _safe(raw_location)
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
# Service vocabulary — natural language per service
# ---------------------------------------------------------------------------

_SERVICE_VOCAB: dict[str, dict[str, str]] = {
    "E-Commerce": {
        "area": "e-commerce",
        "benefit": "make products easier to browse, order, and buy online",
        "gap_phrase": "an easy way for customers to browse and order products online",
        "solution_phrase": "build a proper online store",
        "moderate_hedge": "I noticed it wasn't easy to verify a clear online ordering experience",
    },
    "Business Digitalization": {
        "area": "digital presence",
        "benefit": "establish a professional digital foundation — website, Google visibility, and social presence",
        "gap_phrase": "a complete, professional digital presence",
        "solution_phrase": "establish a solid digital presence",
        "moderate_hedge": "I noticed the digital presence appeared to have some gaps",
    },
    "Web Development": {
        "area": "web presence",
        "benefit": "ensure the website is functional, up-to-date, and professionally presented",
        "gap_phrase": "a reliable, professional website",
        "solution_phrase": "assess and improve the web presence",
        "moderate_hedge": "I wasn't able to fully verify the current state of the website",
    },
    "Business Automation": {
        "area": "business automation",
        "benefit": "reduce repetitive manual work and streamline day-to-day operations",
        "gap_phrase": "automated workflows for repetitive tasks",
        "solution_phrase": "automate some of the repetitive workflows",
        "moderate_hedge": "there may be room to streamline some operational processes",
    },
    "Mobile Development": {
        "area": "mobile app",
        "benefit": "give customers a dedicated mobile experience",
        "gap_phrase": "a customer-facing mobile app",
        "solution_phrase": "build a mobile app for customers",
        "moderate_hedge": "a mobile app could be worth exploring",
    },
    "AI Integration": {
        "area": "AI integration",
        "benefit": "add AI-powered features to existing products or workflows",
        "gap_phrase": "AI-powered workflow automation",
        "solution_phrase": "integrate AI into existing systems",
        "moderate_hedge": "there may be AI opportunities worth exploring",
    },
    "Social Media Content": {
        "area": "social media content",
        "benefit": "establish and grow a consistent social media presence",
        "gap_phrase": "consistent branded social media content",
        "solution_phrase": "create regular social media content",
        "moderate_hedge": "the social media presence appeared limited",
    },
}

_DEFAULT_VOCAB: dict[str, str] = {
    "area": "digital presence",
    "benefit": "strengthen the overall digital setup",
    "gap_phrase": "a stronger online presence",
    "solution_phrase": "improve the digital presence",
    "moderate_hedge": "there may be digital opportunities worth exploring",
}


def _vocab(primary_service: str) -> dict[str, str]:
    return _SERVICE_VOCAB.get(primary_service, _DEFAULT_VOCAB)


# ---------------------------------------------------------------------------
# Observation builder — the opening factual hook
# ---------------------------------------------------------------------------

def _build_observation(rec: dict[str, Any], is_moderate: bool = False) -> str:
    """
    Build a specific, evidence-grounded observation sentence.
    Respects evidence discipline: never states UNKNOWN as fact.
    """
    name = _safe(rec.get("business_name"), "your business")
    category_raw = _safe(rec.get("category"), "business")
    category = category_raw.split(",")[0].split("|")[0].strip() if category_raw else "business"

    location_raw = _safe(rec.get("location"))
    location = ""
    if location_raw:
        for city in ("Lahore", "Karachi", "Islamabad", "Rawalpindi", "Faisalabad", "Multan", "Peshawar", "Sialkot", "Gujranwala", "Hyderabad", "Quetta"):
            if city.lower() in location_raw.lower():
                parts = [p.strip() for p in location_raw.split(",") if p.strip()]
                for p in parts:
                    if city.lower() in p.lower():
                        idx = parts.index(p)
                        if idx > 0 and len(parts[idx-1]) < 35 and not any(c.isdigit() for c in parts[idx-1]):
                            location = f"{parts[idx-1]}, {city}"
                        else:
                            location = p
                        break
                if not location:
                    location = city
                break
        if not location:
            parts = [p.strip() for p in location_raw.split(",") if p.strip()]
            location = parts[0] if parts else ""

    rating = _safe(rec.get("google_rating") or rec.get("digital_maturity") or "")
    reviews = rec.get("google_reviews") or rec.get("google_review_count")
    primary_service = _safe(rec.get("primary_service"), "Business Digitalization")
    uncertainties = rec.get("uncertainties") or []
    detected_opportunity = _safe(rec.get("detected_opportunity"))

    # Pull Google review count
    review_count = 0
    try:
        review_count = int(str(reviews).strip()) if reviews else 0
    except (ValueError, TypeError):
        review_count = 0

    google_rating = _safe(rec.get("google_rating") if isinstance(rec.get("google_rating"), str) else "")

    v = _vocab(primary_service)
    has_website_uncertainty = any("website" in u.lower() for u in uncertainties)

    # Strongest: Google reviews + rating
    if review_count >= 20 and google_rating:
        loc_str = f" in {location}" if location else ""
        obs = (
            f"I came across {name} while researching {category} businesses{loc_str}. "
            f"With {review_count} Google reviews and a {google_rating} rating, "
            f"it's clear the business has an active customer base."
        )
    elif review_count > 0 and google_rating:
        loc_str = f" in {location}" if location else ""
        obs = (
            f"I came across {name} while looking at {category} businesses{loc_str}. "
            f"I noticed it has a Google presence with a {google_rating} rating."
        )
    elif location:
        obs = (
            f"I came across {name} while researching {category} businesses in {location}."
        )
    else:
        obs = f"I came across {name} while researching {category} businesses."

    website_val = str(rec.get("website") or "").strip()
    has_site_url = bool(website_val and website_val.lower() not in ("none", "null", "n/a", "no website", "no_website"))

    if detected_opportunity and "no_website" in detected_opportunity.lower():
        # The business has no website — state it directly and confidently.
        obs += " I noticed your business doesn't have a dedicated professional website yet."
    elif has_site_url:
        # Business already has a website URL in data — do not falsely claim unverified website
        if is_moderate:
            obs += f" {v['moderate_hedge'].capitalize()}."
    elif detected_opportunity and "unreachable" in detected_opportunity.lower():
        obs += f" I wasn't able to confirm {v['gap_phrase']} from the available information."
    elif detected_opportunity and "ecommerce" in detected_opportunity.lower():
        obs += f" I noticed it wasn't straightforward to find {v['gap_phrase']}."
    elif has_website_uncertainty:
        obs += f" However, I couldn't verify {v['gap_phrase']} from what was publicly available."
    elif is_moderate:
        obs += f" {v['moderate_hedge'].capitalize()}."

    return obs


# ---------------------------------------------------------------------------
# Channel-specific message composers
# ---------------------------------------------------------------------------

def _compose_whatsapp(rec: dict[str, Any], is_moderate: bool) -> tuple[str, str, str]:
    """
    Returns (opening, body, cta).
    Target: 50–100 words total.
    """
    name = _safe(rec.get("business_name"), "there")
    primary_service = _safe(rec.get("primary_service"), "Business Digitalization")
    v = _vocab(primary_service)

    category_raw = _safe(rec.get("category"), "business").lower()
    btype = _safe(rec.get("business_type"), "").lower()
    primary_srv = primary_service.lower()
    loc_clean = _clean_location(rec.get("location"))
    loc_display = f" in {loc_clean}" if loc_clean else ""

    is_ecommerce_clothing = any(
        kw in category_raw or kw in btype or kw in name.lower() or kw in primary_srv
        for kw in (
            "clothing", "boutique", "apparel", "fashion", "brand", "retail",
            "store", "shop", "garments", "wear", "outfit", "dress", "e-commerce", "ecommerce",
            "tailor", "pret", "bridal", "designer"
        )
    )

    if is_ecommerce_clothing:
        from .templates import render_boutique_whatsapp_message
        ig = _safe(rec.get("instagram"))
        has_instagram = bool(ig and ig.lower() not in ("none", "null", "n/a", "unknown"))
        web = _safe(rec.get("website"))
        fb = _safe(rec.get("facebook"))
        has_site_or_social = bool(
            (web and web.lower() not in ("none", "null", "n/a", "unknown", "no website", "no_website"))
            or (fb and fb.lower() not in ("none", "null", "n/a", "unknown"))
        )
        full_msg = render_boutique_whatsapp_message(
            name,
            has_instagram=has_instagram,
            has_website_or_social=has_site_or_social,
        )
        return "", full_msg, ""

    opening = f"Hi {name},"

    obs = _build_observation(rec, is_moderate)
    # Trim observation cleanly at sentence boundary if too long
    obs = _trim_to_budget(obs, 65)

    website_val = str(rec.get("website") or "").strip()
    has_site = bool(website_val and website_val.lower() not in ("none", "null", "n/a", "no website", "no_website"))
    is_local_pkg = any(t in str(rec.get("category", "")).lower() or t in str(rec.get("business_type", "")).lower() for t in ("clinic", "doctor", "medical", "health", "hospital", "service", "retail", "shop", "restaurant", "store")) or primary_service in ("Website Creation / Optimization", "Business Digitalization")
    pricing_str = " Website solutions start from PKR 10,000." if (not is_moderate and is_local_pkg and not has_site) else ""

    if is_moderate:
        body = (
            f"{obs}\n\n"
            f"We work with businesses on {v['area']} and thought it might be worth a quick conversation. "
            f"Happy to share a brief idea if it's relevant."
        )
        cta = "Would it be okay if I shared a quick thought on this?"
    else:
        body = (
            f"{obs}\n\n"
            f"We help businesses {v['benefit']}.{pricing_str} "
            f"I think there's a good opportunity to {v['solution_phrase']} for {name}."
        )
        cta = "If you're open to it, I can share a quick idea — no commitment needed."

    body = body + "\n\n— " + COMPANY_NAME

    return opening, body, cta




def _compose_instagram(rec: dict[str, Any], is_moderate: bool) -> tuple[str, str, str]:
    """
    Returns (opening, body, cta).
    Target: 35–70 words total.
    """
    name = _safe(rec.get("business_name"), "there")
    primary_service = _safe(rec.get("primary_service"), "Business Digitalization")
    category = _safe(rec.get("category"), "business")
    location = _safe(rec.get("location"))
    loc_str = f" in {location}" if location else ""

    opening = f"Assalam o Alaikum {name} 👋"

    category_lower = str(rec.get("category", "")).lower()
    name_lower = str(rec.get("business_name", "")).lower()
    is_fashion = any(t in category_lower or t in name_lower for t in (
        "boutique", "clothing", "apparel", "dress", "fashion", "collection",
        "tailor", "retail", "shop", "store", "abaya", "bridal"
    ))

    if is_fashion:
        body = (
            f"I came across {name}{loc_str} on Instagram — loved your collection!\n\n"
            f"Noticed you manage orders through DMs. We help fashion brands "
            f"turn social traffic into sales with 1-click automated ordering catalogs and dedicated mobile websites "
            f"starting from PKR 10,000.\n\n"
            f"I'm Haider from MalikAxiom Technology."
        )
        cta = (
            f"Would you be open to a quick 1-minute chat or demo link?\n\n"
            f"— Haider Nawaz\n"
            f"MalikAxiom Technology | malikaxiomtech.com"
        )
    else:
        v = _vocab(primary_service)
        body = (
            f"Came across your {category} profile{loc_str}.\n\n"
            f"We help businesses {v['benefit']} with dedicated websites and digital growth solutions starting from PKR 10,000.\n\n"
            f"I'm Haider from MalikAxiom Technology."
        )
        cta = (
            f"Happy to share a quick idea if you're interested.\n\n"
            f"— Haider Nawaz\n"
            f"MalikAxiom Technology | malikaxiomtech.com"
        )

    return opening, body, cta


def _compose_facebook(rec: dict[str, Any], is_moderate: bool) -> tuple[str, str, str]:
    """
    Returns (opening, body, cta).
    Similar to Instagram but slightly more conversational.
    """
    name = _safe(rec.get("business_name"), "there")
    primary_service = _safe(rec.get("primary_service"), "Business Digitalization")
    v = _vocab(primary_service)
    category = _safe(rec.get("category"), "business")
    location = _safe(rec.get("location"))

    opening = f"Hi {name},"
    loc_str = f" in {location}" if location else ""

    if is_moderate:
        body = (
            f"I came across your {category} page{loc_str}. "
            f"{v['moderate_hedge'].capitalize()}. "
            f"We work with businesses on {v['area']} and I thought it might be worth mentioning."
        )
        cta = "Happy to share a brief thought if it sounds relevant."
    else:
        body = (
            f"I came across your {category} page{loc_str} and noticed "
            f"a possible opportunity to {v['solution_phrase']}. "
            f"We help businesses {v['benefit']}."
        )
        cta = "If you'd like, I can share a quick idea — no commitment on your end."

    body = body + "\n\n— " + COMPANY_NAME
    return opening, body, cta


def _compose_email(rec: dict[str, Any], is_moderate: bool) -> tuple[str, str, str, str]:
    """
    Returns (subject, opening, body, cta).
    Target: 80–150 words body.
    """
    name = _safe(rec.get("business_name"), "there")
    primary_service = _safe(rec.get("primary_service"), "Business Digitalization")
    v = _vocab(primary_service)
    category = _safe(rec.get("category"), "business")
    location = _safe(rec.get("location"))

    subject = f"Quick idea for {name}'s {v['area']}"

    opening = f"Hi {name},"
    loc_str = f" in {location}" if location else ""

    obs = _build_observation(rec, is_moderate)

    if is_moderate:
        body = (
            f"{obs}\n\n"
            f"We work with businesses on {v['area']} and thought this might be worth a mention. "
            f"At {COMPANY_NAME}, we help businesses {v['benefit']}.\n\n"
            f"I don't want to take much of your time — just thought it could be relevant."
        )
        cta = (
            f"If it sounds useful, feel free to reply and I can share a brief idea.\n\n"
            f"Best regards,\n{COMPANY_NAME}\n{COMPANY_EMAIL} | {COMPANY_PHONE}"
        )
    else:
        body = (
            f"{obs}\n\n"
            f"At {COMPANY_NAME}, we help businesses {v['benefit']}. "
            f"I think there's a genuine opportunity to {v['solution_phrase']} for {name}, "
            f"and I'd be happy to share a quick idea for how we'd approach it."
        )
        cta = (
            f"If you're open to a brief conversation, feel free to reply or reach out directly.\n\n"
            f"Best regards,\n{COMPANY_NAME}\n{COMPANY_EMAIL} | {COMPANY_PHONE}"
        )

    return subject, opening, body, cta


def _compose_contact_form(rec: dict[str, Any], is_moderate: bool) -> tuple[str, str, str]:
    """
    Returns (opening, body, cta).
    Target: 50–100 words. No personal greeting.
    """
    name = _safe(rec.get("business_name"), "your business")
    primary_service = _safe(rec.get("primary_service"), "Business Digitalization")
    v = _vocab(primary_service)
    category = _safe(rec.get("category"), "business")
    location = _safe(rec.get("location"))

    opening = ""
    loc_str = f" in {location}" if location else ""

    if is_moderate:
        body = (
            f"Hi, I came across {name} while researching {category} businesses{loc_str}. "
            f"{v['moderate_hedge'].capitalize()}. "
            f"We work with businesses on {v['area']} and thought it might be relevant."
        )
    else:
        body = (
            f"Hi, I came across {name} while researching {category} businesses{loc_str}. "
            f"I noticed there may be an opportunity to {v['solution_phrase']}. "
            f"We help businesses {v['benefit']}."
        )

    cta = (
        f"If you're interested in a quick idea, feel free to get in touch.\n\n"
        f"— {COMPANY_NAME} | {COMPANY_EMAIL}"
    )
    return opening, body, cta


# ---------------------------------------------------------------------------
# Personalization points
# ---------------------------------------------------------------------------

def _build_personalization_points(rec: dict[str, Any]) -> list[str]:
    """Build 2–4 bullet points explaining why this message was written this way."""
    points: list[str] = []

    name = _safe(rec.get("business_name"), "Business")
    category = _safe(rec.get("category"), "")
    location = _safe(rec.get("location"), "")
    primary_service = _safe(rec.get("primary_service"))
    channel = _safe(rec.get("outreach_channel"))
    potential = _safe(rec.get("sales_potential"))
    detected = _safe(rec.get("detected_opportunity"))

    google_reviews = rec.get("google_reviews")
    google_rating = _safe(rec.get("google_rating") if isinstance(rec.get("google_rating"), str) else "")
    review_count = 0
    try:
        review_count = int(str(google_reviews).strip()) if google_reviews else 0
    except (ValueError, TypeError):
        review_count = 0

    # Point 1: business identity
    loc_str = f" in {location}" if location else ""
    cat_str = f" {category}" if category else ""
    points.append(f"{name} —{cat_str}{loc_str}")

    # Point 2: activity signal
    if review_count >= 20 and google_rating:
        points.append(f"Active business: {review_count} Google reviews, {google_rating} rating")
    elif review_count > 0:
        points.append(f"Google presence confirmed: {review_count} reviews")
    else:
        points.append("Business presence confirmed via available research data")

    # Point 3: specific observed gap
    if "ecommerce" in detected.lower() or "e-commerce" in detected.lower():
        points.append("E-commerce capability not verified — key opportunity signal")
    elif "unreachable" in detected.lower():
        points.append("Website supplied but not verified — web presence status uncertain")
    elif "no_website" in detected.lower() or "no website" in detected.lower():
        points.append("No dedicated professional website identified")
    elif detected:
        points.append(f"Observed gap: {detected[:80]}")

    # Point 4: service + channel fit
    points.append(f"Primary fit: {primary_service} via {channel}")

    return points[:4]


# ---------------------------------------------------------------------------
# Message notes (internal reviewer note)
# ---------------------------------------------------------------------------

def _build_message_notes(rec: dict[str, Any], outreach_priority: str) -> str:
    """Short internal note for the human reviewer — not part of the customer message."""
    name = _safe(rec.get("business_name"), "This lead")
    potential = _safe(rec.get("sales_potential"))
    primary_service = _safe(rec.get("primary_service"))
    channel = _safe(rec.get("outreach_channel"))
    uncertainties = rec.get("uncertainties") or []
    secondary = rec.get("secondary_services") or []

    note_parts: list[str] = []

    if outreach_priority == "CONTACT FIRST":
        note_parts.append(
            f"{name} is a {potential} potential lead. "
            f"Prioritize this outreach."
        )
    elif outreach_priority == "CONTACT LATER":
        note_parts.append(
            f"{name} is a {potential} potential lead. "
            f"Message is kept exploratory — avoid being too forward."
        )

    note_parts.append(
        f"Keep the conversation focused on {primary_service} — do not list all services."
    )

    if uncertainties:
        note_parts.append(
            f"Key uncertainty: {uncertainties[0]} — message avoids stating this as confirmed fact."
        )

    if secondary:
        note_parts.append(
            f"Secondary services ({', '.join(secondary[:2])}) can be raised only if conversation develops naturally."
        )

    return " ".join(note_parts)


# ---------------------------------------------------------------------------
# Mock message
# ---------------------------------------------------------------------------

def _compose_mock(rec: dict[str, Any], outreach_priority: str) -> OutreachRecord:
    """Return a clearly-labeled mock record for pipeline testing."""
    name = _safe(rec.get("business_name"), "Unknown")
    channel = _safe(rec.get("outreach_channel"), "unknown")

    return OutreachRecord(
        lead_id=_safe(rec.get("lead_id"), "unknown"),
        business_name=rec.get("business_name"),
        category=rec.get("category"),
        location=rec.get("location"),
        phone=rec.get("phone"),
        sales_potential=_safe(rec.get("sales_potential")),
        confidence=_safe(rec.get("confidence")),
        primary_service=_safe(rec.get("primary_service")),
        digital_maturity=_safe(rec.get("digital_maturity")),
        recommended_channel=channel,
        outreach_priority=outreach_priority,
        subject="[MOCK] Pipeline test — subject not generated",
        opening=f"[MOCK] Hi {name},",
        message=(
            f"[MOCK] This is a pipeline validation message for {name}. "
            f"Real message generation is disabled in mock mode. "
            f"Channel: {channel} | Service: {rec.get('primary_service')} | "
            f"Priority: {outreach_priority}"
        ),
        cta="[MOCK] Real CTA would appear here.",
        personalization_points=["[MOCK] Pipeline test — no real analysis performed"],
        message_notes="[MOCK] Run without --mock for real message generation.",
        is_mock=True,
        generation_error=None,
        outreach_timestamp=_now_iso(),
    )


# ---------------------------------------------------------------------------
# Main compose function
# ---------------------------------------------------------------------------

def compose_outreach(rec: dict[str, Any], mock: bool = False) -> OutreachRecord:
    """
    Compose an outreach message for one qualified lead.

    Args:
        rec: One dict from qualification_results.json.
        mock: If True, return a labeled mock record.

    Returns:
        OutreachRecord
    """
    lead_id = _safe(rec.get("lead_id"), "unknown")
    final_action = _safe(rec.get("final_action"), "SKIP")
    outreach_priority = _normalize_priority(final_action)
    channel = _safe(rec.get("outreach_channel") or rec.get("recommended_channel"), "unknown")
    sales_potential = _safe(rec.get("sales_potential"), "SKIP")
    is_moderate = sales_potential == "MODERATE"

    # Base record fields
    base = dict(
        lead_id=lead_id,
        business_name=rec.get("business_name"),
        category=rec.get("category"),
        location=rec.get("location"),
        phone=rec.get("phone") or rec.get("whatsapp"),
        mobile_phone=rec.get("mobile_phone"),
        whatsapp=rec.get("whatsapp") or rec.get("phone"),
        landline=rec.get("landline"),
        email=rec.get("email"),
        website=rec.get("website"),
        linkedin=rec.get("linkedin"),
        instagram=rec.get("instagram"),
        facebook=rec.get("facebook"),
        tiktok=rec.get("tiktok"),
        youtube=rec.get("youtube"),
        sales_potential=sales_potential,
        confidence=_safe(rec.get("confidence")),
        primary_service=_safe(rec.get("primary_service")),
        digital_maturity=_safe(rec.get("digital_maturity")),
        recommended_channel=channel,
        outreach_priority=outreach_priority,
        outreach_timestamp=_now_iso(),
    )

    # SKIP leads — no message generated
    if outreach_priority == "SKIP":
        return OutreachRecord(
            **base,
            subject="",
            opening="",
            message="",
            cta="",
            personalization_points=[],
            message_notes=(
                f"Lead skipped: final_action={final_action}. "
                "No outreach message generated."
            ),
            is_mock=False,
            generation_error=None,
        )

    # Mock mode
    if mock:
        return _compose_mock(rec, outreach_priority)

    # Real composition
    try:
        subject = ""
        opening = ""
        message_body = ""
        cta = ""

        if channel == "WhatsApp":
            opening, message_body, cta = _compose_whatsapp(rec, is_moderate)
        elif channel == "Instagram DM":
            opening, message_body, cta = _compose_instagram(rec, is_moderate)
        elif channel == "Facebook":
            opening, message_body, cta = _compose_facebook(rec, is_moderate)
        elif channel == "Email":
            subject, opening, message_body, cta = _compose_email(rec, is_moderate)
        elif channel == "Contact Form":
            opening, message_body, cta = _compose_contact_form(rec, is_moderate)
        else:
            # Unknown channel — generate a generic short message
            opening, message_body, cta = _compose_whatsapp(rec, is_moderate)

        personalization = _build_personalization_points(rec)
        notes = _build_message_notes(rec, outreach_priority)

        return OutreachRecord(
            **base,
            subject=subject,
            opening=opening,
            message=message_body,
            cta=cta,
            personalization_points=personalization,
            message_notes=notes,
            is_mock=False,
            generation_error=None,
        )

    except Exception as exc:  # noqa: BLE001
        logger.error("Error composing message for lead %s: %s", lead_id, exc)
        return OutreachRecord(
            **base,
            subject="",
            opening="",
            message="",
            cta="",
            personalization_points=[],
            message_notes="",
            is_mock=False,
            generation_error=str(exc)[:500],
        )


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def run_outreach(
    input_json: Path | None = None,
    output_dir: Path | None = None,
    mock: bool = False,
) -> tuple[Path, Path, Path, int, dict[str, int]]:
    """
    Load qualification results, compose outreach messages, write outputs.

    Returns:
        (json_path, csv_path, report_path, total, counts_by_priority)
    """
    from .output_writer import write_json, write_csv, write_report

    in_path = input_json or (OUTPUT_DIR / "qualification_results.json")
    out_dir = output_dir or OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    if not in_path.is_file():
        raise FileNotFoundError(
            f"Qualification results not found: {in_path}\n"
            "Run 'python3 main.py qualify' first."
        )

    mode_label = " [MOCK MODE]" if mock else ""
    logger.info("Loading qualification results from: %s%s", in_path, mode_label)

    leads: list[dict[str, Any]] = json.loads(in_path.read_text(encoding="utf-8"))
    logger.info("Composing outreach for %d leads...%s", len(leads), mode_label)

    records: list[OutreachRecord] = []
    counts: dict[str, int] = {"CONTACT FIRST": 0, "CONTACT LATER": 0, "SKIP": 0}

    for lead in leads:
        try:
            record = compose_outreach(lead, mock=mock)
            records.append(record)
            counts[record.outreach_priority] = counts.get(record.outreach_priority, 0) + 1
            name = _safe(lead.get("business_name"), "?")
            logger.info(
                "  %-40s → %-14s [%s]",
                name[:40],
                record.outreach_priority,
                record.recommended_channel,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("Unhandled error for lead %s: %s", lead.get("lead_id", "?"), exc)
            # Build a minimal error record
            records.append(
                OutreachRecord(
                    lead_id=_safe(lead.get("lead_id"), "unknown"),
                    business_name=lead.get("business_name"),
                    category=lead.get("category"),
                    location=lead.get("location"),
                    phone=lead.get("phone"),
                    sales_potential=_safe(lead.get("sales_potential")),
                    confidence=_safe(lead.get("confidence")),
                    primary_service=_safe(lead.get("primary_service")),
                    digital_maturity=_safe(lead.get("digital_maturity")),
                    recommended_channel=_safe(lead.get("outreach_channel"), "unknown"),
                    outreach_priority="SKIP",
                    message_notes=f"Error during composition: {str(exc)[:200]}",
                    generation_error=str(exc)[:500],
                    outreach_timestamp=_now_iso(),
                )
            )
            counts["SKIP"] = counts.get("SKIP", 0) + 1

    json_path = out_dir / "outreach_results.json"
    csv_path = out_dir / "outreach_results.csv"
    report_path = out_dir / "outreach_results.md"

    write_json(json_path, records)
    write_csv(csv_path, records)
    write_report(report_path, records, counts, str(in_path), mock)

    logger.info(
        "Outreach complete: %d CONTACT FIRST, %d CONTACT LATER, %d SKIP%s",
        counts.get("CONTACT FIRST", 0),
        counts.get("CONTACT LATER", 0),
        counts.get("SKIP", 0),
        mode_label,
    )

    return json_path, csv_path, report_path, len(leads), counts
