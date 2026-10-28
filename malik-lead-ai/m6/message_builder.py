"""M6 — first-touch message builder.

The message is TEMPLATE + EVIDENCE. Nothing is invented:

* business name          → M5 ``business_name``
* observation            → classified from M5 website/social evidence
* service / opportunity  → M5 ``primary_service`` (from M3/M4) — never chosen here
* benefit wording        → fixed mapping per M5 service
* contact signature      → fixed constants in ``m6.config``

If M5 does not carry a service, M6 raises ``MessageBuildError`` and the lead
becomes ``NOT_READY`` instead of guessing an opportunity.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .config import (
    GREETING,
    INTRO_SENTENCE,
    MAX_BODY_WORDS,
    MAX_BODY_WORDS_WITH_PRICING,
    PRICING_ELIGIBLE_SERVICE,
    PRICING_SENTENCE,
    SIGNATURE_LINES,
    SOFT_CTA,
)
from .models import M5Lead
from .social import detect_social_platforms, has_own_website

# Neutral, allowed benefit wording per M5 service. Unknown services fall back
# to the neutral sentence — M6 never invents a specific promise.
_SERVICE_BENEFITS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("digitalization", "digitalisation"), "help you establish a stronger digital foundation"),
    (("web", "website"), "help strengthen your website and online visibility"),
    (("e-commerce", "ecommerce", "shopify"), "help make your products easier to browse and order online"),
    (("mobile", "app"), "help make your services easier to access on mobile"),
    (("automation",), "help reduce repetitive manual work in your operations"),
    (("ai",), "help you apply AI in a practical, business-focused way"),
    (("social", "content"), "help you keep a consistent, professional social presence"),
    (("game",), "help you take a game idea forward"),
)
_DEFAULT_BENEFIT = "help strengthen your online presence"

# Allowed claims: knowledge/business_digitalization.md + outreach_rules.md.
# No revenue, profit, ROI, ranking or follower promises appear here.

_LOCATION_PK_HINTS = (
    "pakistan", "lahore", "karachi", "islamabad", "rawalpindi", "faisalabad",
    "multan", "peshawar", "quetta", "gujranwala", "sialkot", "hyderabad",
    "sargodha", "bahawalpur", "sukkur", "larkana", "sheikhupura", "gujrat",
)
_LOCAL_BUSINESS_TYPES = (
    "retail", "shop", "salon", "restaurant", "local", "product", "service",
    "clinic", "hospital", "doctor", "medical", "health", "dental", "dentist",
    "dermatologist", "care", "physiotherapy", "treatment", "center", "centre",
    "consultant", "agency", "boutique", "business", "clothing", "apparel", "tailor",
    "tailoring", "fashion", "brand", "store", "garments", "wear", "outfit", "dress",
    "bridal", "collection", "abaya", "hijab", "shoes", "bags", "fabrics", "textile",
)


class MessageBuildError(ValueError):
    """Raised when the message cannot be built from M5 evidence."""


@dataclass
class BuiltMessage:
    """The composed message plus the parts M6 validates separately."""

    text: str
    service: str
    observation: str
    opportunity_line: str
    benefit: str
    body_word_count: int
    max_body_words: int
    pricing_included: bool
    note: str = ""


def clean_business_name(name: str) -> str:
    """Normalize business name for clean customer-facing presentation.

    Removes trailing dots, quotes, pipes, duplicate spaces, and formats obvious
    lowercase names while preserving established brand casing and acronyms.
    """
    if not name:
        return ""
    text = name.strip().strip("\"'`|")
    text = re.sub(r'[\s.,;:\"\'`|\-]+$', '', text)
    text = re.sub(r'\s+', ' ', text)

    _LOWER_WORDS = frozenset({"and", "or", "in", "at", "of", "the", "for", "by", "with", "to", "on"})
    words = text.split(" ")
    if len(words) <= 7 and not any(c in text for c in ("|", "-", "&", "(", ")", "/")):
        if not any(w.isupper() and len(w) > 1 for w in words):
            cleaned = []
            for i, w in enumerate(words):
                if i > 0 and w.lower() in _LOWER_WORDS:
                    cleaned.append(w.lower())
                else:
                    cleaned.append(w.capitalize() if w.islower() else w)
            text = " ".join(cleaned)

    return text.strip().strip("\"'`|")


def _join_platforms(platforms: list[str]) -> str:
    if len(platforms) == 1:
        return platforms[0]
    if len(platforms) == 2:
        return f"{platforms[0]} and {platforms[1]}"
    return ", ".join(platforms[:-1]) + f" and {platforms[-1]}"


def build_observation(lead: M5Lead) -> tuple[str, str, str, str]:
    """Select evidence-grounded (observation, opportunity_line, intro, cta) tuple."""
    raw_dict = dict(lead.raw)
    platforms = detect_social_platforms(raw_dict)
    own_site = has_own_website(raw_dict)
    service = (lead.primary_service or "").strip().lower()
    raw_name = (lead.business_name or "").strip()
    business_name = clean_business_name(raw_name)

    if "e-commerce" in service or "ecommerce" in service:
        obs = f"I came across {business_name} and noticed you have products available online."
        opp = (
            "We help brands grow with complete digital setups — dedicated online stores, "
            "video reel content creation, and targeted ads campaigns."
        )
        intro = "I'm Haider from MalikAxiom Technology. We build professional e-commerce websites and growth solutions."
        cta = f"Would you be open to a quick chat about growing {business_name} online?"
        return obs, opp, intro, cta

    if own_site:
        obs = f"I came across {business_name} and had a look at your online presence."
        opp = (
            "We help businesses grow through tailored digital strategies — including modern websites, "
            "e-commerce solutions, video reel content creation, and targeted ads campaigns."
        )
        intro = f"I'd be happy to share a few growth ideas tailored for {business_name}."
        cta = "Would you be open to a quick chat?"
        return obs, opp, intro, cta

    if platforms:
        platform_str = _join_platforms(platforms)
        obs = f"I came across {business_name} and noticed you're already active on {platform_str}."
        opp = (
            "We help businesses turn social traffic into sales with dedicated websites, "
            "video reel content creation, and targeted ads campaigns."
        )
        intro = "I'm Haider from MalikAxiom Technology. We build mobile-friendly websites and digital growth solutions."
        cta = f"Would you be open to a quick chat about a growth strategy for {business_name}?"
        return obs, opp, intro, cta

    if "automation" in service:
        obs = f"I came across {business_name} and noticed your operational workflow."
        opp = (
            "Custom automated workflows can help streamline your daily operations "
            "and save manual effort."
        )
        intro = "I'm Haider from MalikAxiom Technology. We build custom automation solutions for growing businesses."
        cta = "Would you be open to a quick chat?"
        return obs, opp, intro, cta

    if "ai" in service:
        obs = f"I came across {business_name} and had a look at your business operations."
        opp = (
            "Integrating practical AI tools can help streamline customer queries "
            "and improve response efficiency."
        )
        intro = "I'm Haider from MalikAxiom Technology. We integrate practical AI features for growing businesses."
        cta = "Would you be open to a quick chat?"
        return obs, opp, intro, cta

    # No social platforms detected, no own website.
    # These are local businesses (Maps listing, phone, category) with no digital presence.
    # State directly that they don't have a website yet — this IS the opportunity.
    location_raw = (lead.text("location") or lead.text("address") or lead.text("google_address") or "").strip() if hasattr(lead, "text") else ""
    category_raw = (lead.text("category") or lead.text("google_category") or "").strip() if hasattr(lead, "text") else ""
    category_clean = category_raw.split(",")[0].split("|")[0].strip() if category_raw else ""
    _loc_part = ""
    if location_raw:
        # Use only the city-level part (first recognisable Pakistani city or first comma-part)
        for city_hint in ("Lahore", "Karachi", "Islamabad", "Rawalpindi", "Faisalabad",
                          "Multan", "Peshawar", "Gujranwala", "Sialkot"):
            if city_hint.lower() in location_raw.lower():
                _loc_part = f" in {city_hint}"
                break
        if not _loc_part:
            _first = location_raw.split(",")[0].strip()
            if _first:
                _loc_part = f" in {_first}"
    _cat_part = f" — a {category_clean} business{_loc_part} —" if category_clean and len(category_clean) < 30 else (_loc_part if _loc_part else "")
    if _cat_part and _cat_part.startswith(" —"):
        obs = f"I came across {business_name}{_cat_part} and noticed you don't have a dedicated website yet."
    elif _cat_part:
        obs = f"I came across {business_name}{_cat_part} and noticed you don't have a dedicated website yet."
    else:
        obs = f"I came across {business_name} and noticed you don't have a dedicated website yet."
    opp = (
        "Having a professional website makes it easier for customers to find you, "
        "and when combined with video reel content creation and ads campaigns, helps grow your business."
    )
    intro = "I'm Haider from MalikAxiom Technology. We build mobile-friendly websites and digital solutions for local businesses."
    cta = f"Would you be open to a quick chat about a website for {business_name}?"
    return obs, opp, intro, cta


def benefit_for_service(service: str) -> str:
    text = (service or "").lower()
    for keywords, benefit in _SERVICE_BENEFITS:
        if any(keyword in text for keyword in keywords):
            return benefit
    return _DEFAULT_BENEFIT


def pricing_applies(lead: M5Lead) -> bool:
    """Pricing applies for entry-level Pakistani business leads."""
    service = (lead.primary_service or "").strip().lower()
    if (
        PRICING_ELIGIBLE_SERVICE.lower() not in service
        and "web" not in service
        and "digital" not in service
        and "e-commerce" not in service
        and "ecommerce" not in service
    ):
        return False
    location = (lead.text("location") or lead.text("address") or lead.text("google_address") or "").lower()
    phone = (lead.text("phone") or lead.text("mobile_phone") or lead.text("whatsapp") or "").strip()
    is_pk = any(hint in location for hint in _LOCATION_PK_HINTS) or phone.startswith("+92") or phone.startswith("03") or phone.startswith("92")
    if not is_pk:
        return False
    business_type = (lead.text("business_type") or "").lower()
    category = (lead.text("category") or lead.text("google_category") or "").lower()
    raw_name = (lead.business_name or "").lower()
    return (
        any(hint in business_type or hint in category or hint in raw_name for hint in _LOCAL_BUSINESS_TYPES)
        or not business_type
    )


def build_demo_message(lead: M5Lead, *, include_pricing: bool = True) -> BuiltMessage:
    """Compose the M7 Personalized Boutique Storefront Demo WhatsApp outreach message."""
    raw_name = (lead.business_name or "").strip()
    if not raw_name:
        raise MessageBuildError("m5_business_name_missing")
    business_name = clean_business_name(raw_name)

    from dashboard.demo_generator import (
        build_demo_whatsapp_message,
        generate_personalized_demo_url,
    )

    demo_url = generate_personalized_demo_url(business_name)
    text = build_demo_whatsapp_message(business_name, demo_url, include_pricing=include_pricing)
    service = (lead.primary_service or "").strip() or "Business Digitalization"
    body = text.rsplit("MalikAxiom Technology", 1)[0].strip()

    return BuiltMessage(
        text=text,
        service=service,
        observation="Aapka Instagram dekha — collection kaafi classy hai 👌",
        opportunity_line="live premium storefront demo specially prepare kiya hai",
        benefit="Live boutique storefront demo with 24/7 AI Brand Assistant",
        body_word_count=len(body.split()),
        max_body_words=200,
        pricing_included=include_pricing,
        note="m7_storefront_demo_template",
    )


def build_first_message(
    lead: M5Lead,
    *,
    include_pricing: bool = True,
    template: str = "standard",
) -> BuiltMessage:
    """Compose a concise, natural, lead-specific outreach message for one M5 lead."""
    if template == "demo":
        return build_demo_message(lead, include_pricing=include_pricing)

    raw_name = (lead.business_name or "").strip()
    if not raw_name:
        raise MessageBuildError("m5_business_name_missing")
    business_name = clean_business_name(raw_name)

    service = (lead.primary_service or "").strip()
    if not service or service.lower() in ("none", "unknown", "n/a", "skip"):
        raise MessageBuildError("m5_primary_service_missing")

    obs, opp, intro, cta = build_observation(lead)
    benefit = benefit_for_service(service)

    use_pricing = bool(include_pricing) and pricing_applies(lead)
    full_opp_line = opp
    if use_pricing:
        full_opp_line = f"{opp} Website solutions start from PKR 10,000."

    lines: list[str] = [
        GREETING,
        "",
        obs,
        "",
        full_opp_line,
        "",
        intro,
        "",
        cta,
    ]

    body = "\n".join(lines).strip()
    text = body + "\n\n" + "\n".join(SIGNATURE_LINES)

    return BuiltMessage(
        text=text,
        service=service,
        observation=obs,
        opportunity_line=full_opp_line,
        benefit=benefit,
        body_word_count=len(body.split()),
        max_body_words=MAX_BODY_WORDS_WITH_PRICING if use_pricing else MAX_BODY_WORDS,
        pricing_included=use_pricing,
        note="",
    )


def body_of(message: str) -> str:
    """Everything before the signature block."""
    index = message.find(SIGNATURE_LINES[0])
    return (message[:index] if index != -1 else message).strip()


def word_count(text: str) -> int:
    return len(re.findall(r"\S+", text or ""))


__all__ = [
    "BuiltMessage",
    "MessageBuildError",
    "clean_business_name",
    "build_first_message",
    "build_demo_message",
    "build_observation",
    "benefit_for_service",
    "pricing_applies",
    "body_of",
    "word_count",
]
