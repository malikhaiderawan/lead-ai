"""Milestone 2 — Master Deep Web Researcher.

Orchestrates deep, evidence-based, multi-source investigation for every lead:
1. Search Engine Discovery & Cross-Verification (DuckDuckGo / Web search)
2. Website Deep Exploration (Multi-page: About, Shop/Products, Services, Cart, Checkout, Contact, Pricing, FAQ)
3. Products & Services Commercial Offering Synthesis
4. E-Commerce & Checkout Flow Analysis (Catalog, Cart, Checkout, COD, Gateways, Platform)
5. Social Presence Deep Inspection (Instagram, Facebook, TikTok, LinkedIn, YouTube)
6. Business Positioning & Maturity Evaluation
7. Contact Information 5-State Verification Matrix (Phone, WhatsApp, Email, Address)
8. Observable Digital Gaps Identification (Evidence-grounded, zero hallucinations)
9. MalikAxiom Service Opportunity Mapping with concrete rationale
10. Final 8-Point Structured Research Synthesis

Standard library only. No artificial sleep or delays.
"""

from __future__ import annotations

import csv
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .evidence import Evidence, EvidenceClass, ResourceStatus
from .google_researcher import GoogleResearch, research_google
from .input_loader import load_leads, resolve_name
from .search_researcher import SearchResearch, research_search
from .social_researcher import PLATFORMS, SocialResearch, research_social
from .website_researcher import WebsiteResearch, research_website

logger = logging.getLogger(__name__)

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"


@dataclass
class ResearchRecord:
    """One fully structured, deep research record for one lead."""

    lead_id: str
    business_name: str | None
    category: str | None
    location: str | None
    phone: str | None
    mobile_phone: str | None
    whatsapp: str | None
    landline: str | None
    email: str | None
    youtube: str | None
    google_maps_url: str | None
    original_source_data: dict[str, Any]
    source_file: str
    row_number: int

    # Website
    website: str | None
    website_status: str
    website_type: str | None
    website_quality_observation: str
    ecommerce_status: str
    checkout_status: str
    online_ordering: str
    whatsapp_contact: str
    contact_option_present: str
    obvious_broken_signals: list[str]
    important_observable_features: list[str]
    website_evidence: list[dict[str, str]]

    # Social
    instagram: str | None
    instagram_status: str
    instagram_activity: str
    facebook: str | None
    facebook_status: str
    facebook_activity: str
    tiktok: str | None
    tiktok_status: str
    tiktok_activity: str
    linkedin: str | None
    linkedin_status: str
    linkedin_activity: str
    social_evidence: list[dict[str, str]]

    # Google
    google_rating: str | None
    google_reviews: str | None
    google_address: str | None
    google_category: str | None
    google_website_connection: str
    google_other_listing_notes: str
    google_evidence: list[dict[str, str]]

    # Business understanding
    business_type: str | None
    local_offline_online: str
    apparent_target_market: str
    digital_maturity: str

    # Evidence buckets
    observed_digital_gaps: list[str]
    verified_facts: list[str]
    reasonable_observations: list[str]
    unknowns: list[str]

    # New deep research intelligence fields
    products_services_summary: str = ""
    ecommerce_details: dict[str, Any] = field(default_factory=dict)
    social_details: dict[str, Any] = field(default_factory=dict)
    contact_details: dict[str, Any] = field(default_factory=dict)
    search_findings: dict[str, Any] = field(default_factory=dict)
    digital_gaps_details: list[dict[str, Any]] = field(default_factory=list)
    malikaxiom_opportunities: list[dict[str, Any]] = field(default_factory=list)
    research_synthesis: dict[str, Any] = field(default_factory=dict)
    research_coverage: dict[str, bool] = field(default_factory=dict)
    youtube_status: str = "unknown"
    youtube_activity: str = "unknown"

    research_status: str = "UNRESEARCHED"
    research_timestamp: str = ""
    error_note: str = ""
    _reachable_snapshot: str = "unknown"
    _http_status_snapshot: str | None = None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _synthesize_products_and_services(
    record: ResearchRecord,
    web_res: WebsiteResearch,
    search_res: SearchResearch,
) -> str:
    """Synthesize what the business actually sells and provides based on observed facts."""
    items: list[str] = []

    if web_res.products_services_found:
        items.extend(web_res.products_services_found[:6])

    if search_res.search_snippets:
        for snip in search_res.search_snippets[:3]:
            m = re.findall(r'(?:offers|provides|specializes in|collection of|known for|serving)\s+([^.,;]+)', snip, re.IGNORECASE)
            for match in m:
                clean_m = match.strip()
                if 5 < len(clean_m) < 60 and clean_m not in items:
                    items.append(clean_m)

    cat = (record.category or "").strip()
    name = (record.business_name or "Business").strip()

    if items:
        summary = f"{name} offers: {', '.join(items[:6])}."
        if web_res.price_ranges_observed:
            summary += f" Observed price points: {', '.join(web_res.price_ranges_observed[:3])}."
        return summary
    if cat:
        return f"{name} operates in the {cat} sector."
    return f"Commercial offerings for {name} could not be confirmed from public sources."


def _evaluate_contact_matrix(
    record: ResearchRecord,
    web_res: WebsiteResearch,
    social_results: dict[str, SocialResearch],
    search_res: SearchResearch,
) -> dict[str, Any]:
    """Build a comprehensive 5-state contact verification matrix with provenance and conflict tracking."""
    matrix: dict[str, Any] = {
        "phone": {
            "value": record.phone or record.mobile_phone,
            "status": ResourceStatus.UNKNOWN,
            "sources": [],
            "all_values": [],
            "conflicts_detected": False,
        },
        "whatsapp": {
            "value": record.whatsapp,
            "status": ResourceStatus.UNKNOWN,
            "sources": [],
            "all_values": [],
            "conflicts_detected": False,
        },
        "email": {
            "value": record.email,
            "status": ResourceStatus.UNKNOWN,
            "sources": [],
            "all_values": [],
            "conflicts_detected": False,
        },
        "address": {
            "value": record.location or record.google_address,
            "status": ResourceStatus.UNKNOWN,
            "sources": [],
            "all_values": [],
            "conflicts_detected": False,
        },
        "website": {
            "value": record.website,
            "status": ResourceStatus.UNKNOWN,
            "sources": [],
            "all_values": [],
            "conflicts_detected": False,
        },
    }

    def _add_contact_val(channel: str, val: str | None, src: str) -> None:
        if not val or not str(val).strip():
            return
        clean_val = str(val).strip()
        matrix[channel]["status"] = ResourceStatus.FOUND
        if src not in matrix[channel]["sources"]:
            matrix[channel]["sources"].append(src)
        if not any(entry.get("value") == clean_val for entry in matrix[channel]["all_values"]):
            matrix[channel]["all_values"].append({"value": clean_val, "source": src})
        if not matrix[channel]["value"]:
            matrix[channel]["value"] = clean_val
        elif matrix[channel]["value"] != clean_val:
            matrix[channel]["conflicts_detected"] = True

    # 1. Input phone / mobile / landline
    if record.phone:
        _add_contact_val("phone", record.phone, "input_data")
    if record.mobile_phone:
        _add_contact_val("phone", record.mobile_phone, "input_mobile")
    if record.landline:
        _add_contact_val("phone", record.landline, "input_landline")

    # Website phones
    if web_res.contacts_extracted.get("phones"):
        for p in web_res.contacts_extracted["phones"]:
            _add_contact_val("phone", p, "website_page")

    # Search discovered phones
    if search_res.discovered_phones:
        for sp in search_res.discovered_phones:
            _add_contact_val("phone", sp, "search_discovery")

    # 2. WhatsApp
    if record.whatsapp:
        _add_contact_val("whatsapp", record.whatsapp, "input_data")
    if web_res.contacts_extracted.get("whatsapp"):
        for wa in web_res.contacts_extracted["whatsapp"]:
            _add_contact_val("whatsapp", wa, "website_whatsapp")
    for s_res in social_results.values():
        if s_res.whatsapp_cta:
            _add_contact_val("whatsapp", s_res.whatsapp_cta, f"{s_res.platform}_bio")

    # 3. Email
    if record.email:
        _add_contact_val("email", record.email, "input_data")
    if web_res.contacts_extracted.get("emails"):
        for em in web_res.contacts_extracted["emails"]:
            _add_contact_val("email", em, "website_page")
    if search_res.discovered_emails:
        for sem in search_res.discovered_emails:
            _add_contact_val("email", sem, "search_discovery")

    # 4. Address
    if record.location:
        _add_contact_val("address", record.location, "input_data")
    if record.google_address:
        _add_contact_val("address", record.google_address, "google_maps")

    # 5. Website
    if record.website:
        if web_res.reachable == "reachable":
            matrix["website"]["status"] = ResourceStatus.FOUND
        elif web_res.http_status in ("403", "429"):
            matrix["website"]["status"] = ResourceStatus.BLOCKED
        elif web_res.http_status == "404":
            matrix["website"]["status"] = ResourceStatus.NOT_FOUND
        else:
            matrix["website"]["status"] = ResourceStatus.CHECK_FAILED
        _add_contact_val("website", record.website, "input_or_discovery")

    return matrix


def _identify_digital_gaps(
    record: ResearchRecord,
    web_res: WebsiteResearch,
    social_results: dict[str, SocialResearch],
    contact_matrix: dict[str, Any],
) -> list[dict[str, Any]]:
    """Identify concrete, observable, evidence-grounded digital gaps with full provenance."""
    gaps: list[dict[str, Any]] = []

    has_web = record.website and record.website_status == "exists"
    has_social = any(s.status == "present" for s in social_results.values())
    social_names = [p.capitalize() for p, s in social_results.items() if s.status == "present"]

    # 1. No Website Gap
    if not record.website or record.website_status in ("unknown", "does_not_exist", "missing"):
        if has_social:
            gaps.append({
                "gap_id": "no_website_active_social",
                "gap": "Active Social Presence Without Dedicated Website",
                "title": "Active Social Presence Without Dedicated Website",
                "description": f"The business maintains an active social presence on {', '.join(social_names)} but lacks a dedicated storefront/website to capture organic search traffic and automate order placement.",
                "evidence": f"Social profiles verified on {', '.join(social_names)}; no official website identified in input or targeted search discovery.",
                "source": "cross_channel_check",
                "confidence": "HIGH",
            })
        else:
            gaps.append({
                "gap_id": "no_digital_presence",
                "gap": "Missing Professional Digital Presence",
                "title": "Missing Professional Digital Presence",
                "description": "No dedicated website or active social presence was verified, limiting business visibility to offline walk-ins and word-of-mouth.",
                "evidence": "No website or active social channels identified in input data or public search discovery.",
                "source": "cross_channel_check",
                "confidence": "HIGH",
            })

    # 2. Website Reachability / Technical Gaps
    if record.website and web_res.reachable == "unreachable":
        gaps.append({
            "gap_id": "website_unreachable",
            "gap": "Website Technical Reachability Issue",
            "title": "Website Technical Reachability Issue",
            "description": f"The business domain ({record.website}) is registered but unreachable or returning connection errors (HTTP {web_res.http_status or 'error'}).",
            "evidence": f"Connection check to {record.website} failed: {web_res.http_status or 'unreachable'}.",
            "source": "website_inspection",
            "confidence": "HIGH",
        })

    # 3. E-commerce / Ordering Flow Gaps
    if has_web and web_res.reachable == "reachable":
        if web_res.order_flow_type == "WHATSAPP_ORDERING":
            gaps.append({
                "gap_id": "manual_whatsapp_orders",
                "gap": "Manual WhatsApp Order Capture Bottleneck",
                "title": "Manual WhatsApp Order Capture Bottleneck",
                "description": "Products are showcased online, but orders are routed through manual back-and-forth WhatsApp chats without automated cart/checkout, creating drop-offs during high traffic.",
                "evidence": "Observed direct WhatsApp order CTAs without automated cart or payment gateway integration.",
                "source": "website_commerce_inspection",
                "confidence": "HIGH",
            })
        elif web_res.order_flow_type == "CATALOG_WITH_CART_ONLY":
            gaps.append({
                "gap_id": "cart_without_checkout",
                "gap": "Shopping Cart Present Without Online Checkout",
                "title": "Shopping Cart Present Without Online Checkout",
                "description": "Customers can add items to cart, but no automated online checkout or payment gateway was accessible.",
                "evidence": "Cart functionality detected, but checkout/order placement page returned error or was not reachable.",
                "source": "website_commerce_inspection",
                "confidence": "HIGH",
            })
        elif web_res.ecommerce_presence == "present" and web_res.checkout_order_capability != "present":
            gaps.append({
                "gap_id": "catalog_without_checkout",
                "gap": "Product Catalog Display Without Direct Purchasing",
                "title": "Product Catalog Display Without Direct Purchasing",
                "description": "Products and collections are listed online, but customers cannot place orders directly through a cart/checkout system.",
                "evidence": "Product catalog detected on site, but checkout capability was not found.",
                "source": "website_commerce_inspection",
                "confidence": "HIGH",
            })
        elif web_res.ecommerce_presence == "not_detected" and any(k in (record.category or "").lower() for k in ("clothing", "store", "boutique", "retail", "shop", "fashion", "apparel", "wear", "tailor", "suit", "brand")):
            gaps.append({
                "gap_id": "retail_missing_ecommerce",
                "gap": "Retail / Product Business Lacking E-Commerce Store",
                "title": "Retail / Product Business Lacking E-Commerce Store",
                "description": "The business operates in retail/fashion/bespoke products but does not offer an online browsing or purchasing storefront.",
                "evidence": "Product/retail category confirmed, but website contains no e-commerce catalog or checkout.",
                "source": "website_commerce_inspection",
                "confidence": "HIGH",
            })
        elif web_res.order_flow_type == "INFORMATIONAL_ONLY" and web_res.apparent_type == "likely_service_business_site":
            gaps.append({
                "gap_id": "service_missing_booking",
                "gap": "Service Website Lacking Online Booking or Inquiry Flow",
                "title": "Service Website Lacking Online Booking or Inquiry Flow",
                "description": "The service website lacks an integrated online consultation/service booking or quotation system.",
                "evidence": "Service website active but no booking or inquiry workflow detected.",
                "source": "website_service_inspection",
                "confidence": "HIGH",
            })

        # Payment options gap
        if web_res.checkout_order_capability == "present" and not web_res.payment_methods_detected:
            gaps.append({
                "gap_id": "unclear_payment_methods",
                "gap": "Unclear Payment & Delivery Terms",
                "title": "Unclear Payment & Delivery Terms",
                "description": "Checkout is present but accepted payment methods (Cash on Delivery, JazzCash, Cards) are not clearly displayed, reducing customer trust.",
                "evidence": "No explicit payment method signals detected on checkout or policy pages.",
                "source": "website_checkout_inspection",
                "confidence": "MEDIUM",
            })

        # Technical UX gaps
        for tg in web_res.technical_gaps:
            gaps.append({
                "gap_id": "technical_ux_gap",
                "gap": tg,
                "title": tg,
                "description": f"Website exhibits observable digital gap: {tg}.",
                "evidence": f"Detected during multi-page site inspection of {record.website}.",
                "source": "website_technical_inspection",
                "confidence": "HIGH",
            })

    # 4. WhatsApp / Quick Contact Gap
    if contact_matrix["whatsapp"]["status"] != ResourceStatus.FOUND and contact_matrix["phone"]["status"] == ResourceStatus.FOUND:
        gaps.append({
            "gap_id": "missing_whatsapp_cta",
            "gap": "Missing 1-Click WhatsApp Ordering / Inquiries",
            "title": "Missing 1-Click WhatsApp Ordering / Inquiries",
            "description": "Business has phone contact but lacks 1-click WhatsApp chat integration for instant customer capture.",
            "evidence": "Phone number present but no direct wa.me link or WhatsApp widget detected on website.",
            "source": "contact_channels_check",
            "confidence": "HIGH",
        })

    return gaps


def _map_malikaxiom_opportunities(
    record: ResearchRecord,
    gaps: list[dict[str, Any]],
    web_res: WebsiteResearch,
) -> list[dict[str, Any]]:
    """Map observed digital gaps to concrete, grounded MalikAxiom service offerings with complete lineage."""
    opps: list[dict[str, Any]] = []

    cat_lower = (record.category or "").lower()
    is_retail_or_clothing = any(k in cat_lower for k in ("clothing", "store", "boutique", "retail", "shop", "fashion", "apparel", "wear", "tailor"))

    for g in gaps:
        gid = g["gap_id"]

        if gid in ("no_website_active_social", "no_digital_presence"):
            if is_retail_or_clothing:
                opps.append({
                    "service": "E-Commerce Development",
                    "package": "Mobile Online Store & COD Integration",
                    "why_relevant": f"The business has an established name/social presence ({g['evidence']}) but no dedicated online store. Building a modern mobile e-commerce store enables 24/7 automated order collection.",
                    "evidence_grounding": g["evidence"],
                    "gap_addressed": g["gap"],
                    "evidence_source": g["source"],
                    "solution_summary": "Full-stack mobile-responsive e-commerce store with COD, JazzCash, EasyPaisa, and WhatsApp checkout integration.",
                })
            else:
                opps.append({
                    "service": "Web Development",
                    "package": "Professional Business Website",
                    "why_relevant": "Establishing a professional mobile-friendly website creates search credibility and generates customer inquiries directly.",
                    "evidence_grounding": g["evidence"],
                    "gap_addressed": g["gap"],
                    "evidence_source": g["source"],
                    "solution_summary": "High-converting modern website with lead capture, Google SEO optimization, and WhatsApp chat routing.",
                })

        elif gid in ("manual_whatsapp_orders", "catalog_without_checkout", "cart_without_checkout", "retail_missing_ecommerce"):
            opps.append({
                "service": "E-Commerce Development",
                "package": "1-Click WhatsApp & Online Store Automation",
                "why_relevant": f"Observed gap: {g['description']}. Implementing automated cart and 1-click WhatsApp order confirmation saves manual messaging time and boosts conversions.",
                "evidence_grounding": g["evidence"],
                "gap_addressed": g["gap"],
                "evidence_source": g["source"],
                "solution_summary": "Automated order catalog with 1-click WhatsApp checkout routing and inventory management.",
            })

        elif gid == "service_missing_booking":
            opps.append({
                "service": "Business Automation",
                "package": "Online Consultation & Service Booking Flow",
                "why_relevant": "The service website lacks an automated booking or quote request flow. Adding structured scheduling captures leads without manual phone coordination.",
                "evidence_grounding": g["evidence"],
                "gap_addressed": g["gap"],
                "evidence_source": g["source"],
                "solution_summary": "Direct online appointment and quotation scheduling system.",
            })

        elif gid == "website_unreachable":
            opps.append({
                "service": "Web Development",
                "package": "Website Modernization & Hosting Setup",
                "why_relevant": "The existing website is unreachable or broken. Redeploying on high-speed, secure infrastructure restores customer access and credibility.",
                "evidence_grounding": g["evidence"],
                "gap_addressed": g["gap"],
                "evidence_source": g["source"],
                "solution_summary": "Complete website re-architecture, secure SSL setup, and ultra-fast cloud hosting.",
            })

        elif gid == "missing_whatsapp_cta":
            opps.append({
                "service": "Business Automation",
                "package": "1-Click WhatsApp Lead & Inquiry Integration",
                "why_relevant": "Adding 1-click WhatsApp floating widgets and quick response links connects mobile visitors directly to sales reps in seconds.",
                "evidence_grounding": g["evidence"],
                "gap_addressed": g["gap"],
                "evidence_source": g["source"],
                "solution_summary": "1-click floating WhatsApp widgets with pre-filled product/service inquiry templates.",
            })

    # Add content/growth service for retail/consumer brands
    if is_retail_or_clothing and not any(o["service"] == "Content Creation & Marketing" for o in opps):
        opps.append({
            "service": "Content Creation & Marketing",
            "package": "Reels & Video Content Creation (To Drive Traffic)",
            "why_relevant": f"Fashion and retail businesses in {record.location or 'Pakistan'} rely heavily on high-engagement short-form reels and product showcases to drive organic buyers to online stores.",
            "evidence_grounding": f"Retail category: {record.category}.",
            "gap_addressed": "Visual Engagement & Traffic Acquisition",
            "evidence_source": "category_evaluation",
            "solution_summary": "Professional reel production, catalog video hooks, and targeted ad campaign creative.",
        })

    # Default fallback opportunity if none matched
    if not opps:
        opps.append({
            "service": "Business Digitalization",
            "package": "Digital Presence Optimization",
            "why_relevant": "Strengthening online visibility, local search discoverability, and customer communication channels.",
            "evidence_grounding": "General local business evaluation.",
            "gap_addressed": "General Digital Optimization",
            "evidence_source": "multi_channel_audit",
            "solution_summary": "Comprehensive digital presence audit and conversion rate optimization.",
        })

    return opps


def _build_final_synthesis(
    record: ResearchRecord,
    web_res: WebsiteResearch,
    social_results: dict[str, SocialResearch],
    contact_matrix: dict[str, Any],
    gaps: list[dict[str, Any]],
    opps: list[dict[str, Any]],
) -> dict[str, Any]:
    """Synthesize the 8 core dimensions required by section 13."""
    name = record.business_name or "Business"

    # 1. Business
    business_summary = f"{name} is a {record.category or 'local business'} located in {record.location or 'Pakistan'}."
    if record.apparent_target_market and record.apparent_target_market != "unknown":
        business_summary += f" Target market appears to be {record.apparent_target_market}."

    # 2. Products / Services
    prod_summary = record.products_services_summary

    # 3. Digital Presence
    channels = []
    if record.website and web_res.reachable == "reachable":
        channels.append(f"Website ({record.website})")
    for p, s in social_results.items():
        if s.status == "present":
            channels.append(f"{p.capitalize()} ({s.url})")
    if record.google_maps_url:
        channels.append("Google Maps Listing")
    digital_presence = f"Active channels: {', '.join(channels)}" if channels else "Minimal or no verified digital channels observed."

    # 4. E-commerce
    ecom_summary = f"Platform: {web_res.detected_platform}. Order flow: {web_res.order_flow_type}."
    if web_res.payment_methods_detected:
        ecom_summary += f" Payment methods: {', '.join(web_res.payment_methods_detected)}."
    else:
        ecom_summary += " No online payment gateways detected."

    # 5. Social Presence
    social_signals = []
    for p, s in social_results.items():
        if s.status == "present":
            sig = f"{p.capitalize()}: {s.activity_signal}"
            if s.public_metrics_snippet:
                sig += f" ({s.public_metrics_snippet})"
            social_signals.append(sig)
    social_presence = "; ".join(social_signals) if social_signals else "No verified social presence confirmed."

    # 6. Contact
    available_contacts = []
    for ctype, cinfo in contact_matrix.items():
        if cinfo["status"] == ResourceStatus.FOUND:
            available_contacts.append(f"{ctype.capitalize()}: {cinfo['value']}")
    contact_summary = "; ".join(available_contacts) if available_contacts else "No direct public contact verified."

    # 7. Digital Gaps
    gap_summaries = [f"• {g['title']}: {g['description']}" for g in gaps]

    # 8. MalikAxiom Opportunity
    opp_summaries = [f"• {o['service']} ({o['package']}): {o['why_relevant']}" for o in opps]

    return {
        "business": business_summary,
        "products_services": prod_summary,
        "digital_presence": digital_presence,
        "ecommerce": ecom_summary,
        "social_presence": social_presence,
        "contact": contact_summary,
        "digital_gaps": gap_summaries,
        "malikaxiom_opportunities": opp_summaries,
    }


def _classify_maturity(record: ResearchRecord) -> str:
    """Classify digital maturity from observed multi-source facts."""
    has_website = record.website_status == "exists" and record._reachable_snapshot == "reachable"
    has_ecom = record.ecommerce_status == "present"
    has_ig = record.instagram_status == "present"
    has_fb = record.facebook_status == "present"
    has_tt = record.tiktok_status == "present"
    has_li = record.linkedin_status == "present"
    has_google = record.google_maps_url is not None
    social_count = sum([has_ig, has_fb, has_tt, has_li])

    if has_website and has_google and social_count >= 2 and has_ecom:
        return "ADVANCED"
    if has_website and (has_google or social_count >= 2):
        return "STRONG"
    if has_website or (has_google and social_count >= 1):
        return "MODERATE"
    if has_google or social_count >= 1:
        return "BASIC"
    if social_count == 0 and not has_google:
        return "WEAK"
    return "VERY WEAK"


def _business_type_guess(record: ResearchRecord) -> str | None:
    cat = (record.category or "").strip().lower()
    if not cat:
        return None

    food_terms = ("cafe", "restaurant", "food", "coffee", "bakery", "dining", "hotel")
    retail_terms = ("clothing", "store", "boutique", "shop", "fashion", "apparel", "garments", "retail", "wear", "tailor", "dress")
    service_terms = (
        "services", "consultancy", "consulting", "agency", "studio", "repair",
        "cleaning", "beauty", "salon", "clinic", "hospital", "doctor", "medical",
        "health", "dental", "dentist", "dermatologist", "care", "physiotherapy",
        "treatment", "center", "centre", "healthcare", "spa", "therapy",
    )

    if any(t in cat for t in food_terms):
        return "food_and_dining_business"
    if any(t in cat for t in retail_terms):
        return "retail_or_product_business"
    if any(t in cat for t in service_terms):
        return "service_business"
    return None


def _presence_model(record: ResearchRecord) -> str:
    has_website = record.website_status == "exists" and record._reachable_snapshot == "reachable"
    has_google = record.google_maps_url is not None
    has_social = any(
        s == "present"
        for s in [record.instagram_status, record.facebook_status, record.tiktok_status, record.linkedin_status]
    )
    if has_website and has_google and has_social:
        return "online_with_social_and_listing"
    if has_website and has_google:
        return "online_with_listing"
    if has_website and has_social:
        return "online_with_social"
    if has_website:
        return "online_only"
    if has_google and has_social:
        return "social_and_listing_only"
    if has_google:
        return "listing_only"
    if has_social:
        return "social_only"
    return "minimal_or_none_observed"


def _target_market_note(record: ResearchRecord) -> str:
    cat = (record.category or "").strip()
    loc = (record.location or "").strip()
    if cat and loc and loc.lower() not in ("unknown",):
        return f"{cat} in {loc}"
    if cat:
        return cat
    if loc and loc.lower() not in ("unknown",):
        return f"business in {loc}"
    return "unknown"


def build_record(lead: dict[str, Any], lead_id: str) -> ResearchRecord:
    """Build the raw research skeleton from input before deep multi-source checks."""
    raw = lead["raw"]
    cmap = lead["source_column_map"]

    def get(concept: str) -> str | None:
        hdr = cmap.get(concept)
        if not hdr or hdr not in raw:
            return None
        value = raw[hdr]
        return value.strip() if value and value.strip() else None

    website = get("website")
    instagram = get("instagram")
    facebook = get("facebook")
    tiktok = get("tiktok")
    linkedin = get("linkedin")
    youtube = get("youtube")
    google_maps_url = get("google_maps_url")
    rating = get("rating")
    review_count = get("reviews")
    address = get("address")
    category = get("category")
    phone = get("phone") or get("website_phones") or get("mobile_phone") or get("landline")
    mobile_phone = get("mobile_phone")
    whatsapp = get("whatsapp")
    landline = get("landline")
    email = get("email")
    name = get("business_name") or get("title") or get("business") or get("name") or get("company")

    return ResearchRecord(
        lead_id=lead_id,
        business_name=name,
        category=category,
        location=address,
        phone=phone,
        mobile_phone=mobile_phone,
        whatsapp=whatsapp,
        landline=landline,
        email=email,
        youtube=youtube,
        google_maps_url=google_maps_url,
        original_source_data={k: v for k, v in raw.items()},
        source_file=lead.get("source_file", ""),
        row_number=lead.get("row_number", 0),

        website=website,
        website_status="unknown",
        website_type=None,
        website_quality_observation="",
        ecommerce_status="unknown",
        checkout_status="unknown",
        online_ordering="unknown",
        whatsapp_contact="unknown",
        contact_option_present="unknown",
        obvious_broken_signals=[],
        important_observable_features=[],
        website_evidence=[],

        instagram=instagram,
        instagram_status="unknown",
        instagram_activity="unknown",
        facebook=facebook,
        facebook_status="unknown",
        facebook_activity="unknown",
        tiktok=tiktok,
        tiktok_status="unknown",
        tiktok_activity="unknown",
        linkedin=linkedin,
        linkedin_status="unknown",
        linkedin_activity="unknown",
        social_evidence=[],

        google_rating=rating,
        google_reviews=review_count,
        google_address=address,
        google_category=category,
        google_website_connection="unknown",
        google_other_listing_notes="",
        google_evidence=[],

        business_type=None,
        local_offline_online="unknown",
        apparent_target_market="unknown",
        digital_maturity="unknown",
        observed_digital_gaps=[],
        verified_facts=[],
        reasonable_observations=[],
        unknowns=[],
        research_status="UNRESEARCHED",
        research_timestamp="",
    )


def _make_lead_id(lead: dict[str, Any]) -> str:
    name = resolve_name(lead)
    row = lead.get("row_number", "?")
    if name:
        slug = "".join(ch if ch.isalnum() else "_" for ch in name.lower())[:40]
        return f"lead_{row:03d}_{slug}"
    return f"lead_{row:03d}_unknown"


def _research_one(lead: dict[str, Any], lead_id: str, timeout: float = 12.0) -> ResearchRecord:
    """Perform deep, multi-source investigation for one lead across the full flow."""
    record = build_record(lead, lead_id)

    # 1. Search Engine Discovery & Cross-Verification
    search_res = research_search(
        business_name=record.business_name,
        location=record.location,
        category=record.category,
        existing_website=record.website,
        existing_instagram=record.instagram,
        existing_facebook=record.facebook,
        timeout=min(timeout, 8.0),
    )
    record.search_findings = search_res.to_dict()

    # Apply discovered profiles if lead lacked them in input
    if not record.website and search_res.discovered_website:
        record.website = search_res.discovered_website
    if not record.instagram and search_res.discovered_links.get("instagram"):
        record.instagram = search_res.discovered_links["instagram"]
    if not record.facebook and search_res.discovered_links.get("facebook"):
        record.facebook = search_res.discovered_links["facebook"]
    if not record.tiktok and search_res.discovered_links.get("tiktok"):
        record.tiktok = search_res.discovered_links["tiktok"]
    if not record.linkedin and search_res.discovered_links.get("linkedin"):
        record.linkedin = search_res.discovered_links["linkedin"]
    if not record.youtube and search_res.discovered_links.get("youtube"):
        record.youtube = search_res.discovered_links["youtube"]

    # 2. Deep Multi-Page Website Exploration
    website_res = research_website(record.website, timeout=timeout)
    record.website_status = website_res.status
    record._reachable_snapshot = website_res.reachable
    record._http_status_snapshot = website_res.http_status
    record.website_type = website_res.apparent_type
    record.website_quality_observation = website_res.quality_observation
    record.ecommerce_status = website_res.ecommerce_presence
    record.checkout_status = website_res.checkout_order_capability
    record.online_ordering = website_res.checkout_order_capability
    record.whatsapp_contact = website_res.whatsapp_contact_option
    record.contact_option_present = website_res.contact_option_present
    record.obvious_broken_signals = website_res.obvious_broken_signals
    record.important_observable_features = website_res.observable_features
    record.website_evidence = [e.to_dict() for e in website_res.evidence]

    # Adopt links discovered on website
    if website_res.extracted_links:
        for platform in ("instagram", "facebook", "linkedin", "tiktok", "youtube"):
            if not getattr(record, platform, None) and website_res.extracted_links.get(platform):
                setattr(record, platform, website_res.extracted_links[platform])
        if not record.whatsapp and website_res.extracted_links.get("whatsapp"):
            record.whatsapp = website_res.extracted_links["whatsapp"]
        if not record.email and website_res.extracted_links.get("email"):
            record.email = website_res.extracted_links["email"]
        if not record.phone and website_res.extracted_links.get("phone"):
            record.phone = website_res.extracted_links["phone"]

    # Store rich e-commerce details
    record.ecommerce_details = {
        "detected_platform": website_res.detected_platform,
        "order_flow_type": website_res.order_flow_type,
        "payment_methods": website_res.payment_methods_detected,
        "cod_supported": website_res.cod_supported,
        "online_payment_supported": website_res.online_payment_supported,
        "price_ranges": website_res.price_ranges_observed,
        "pages_checked": website_res.pages_checked,
    }

    # 3. Social Presence Deep Investigation
    social_results: dict[str, SocialResearch] = {}
    for platform in PLATFORMS:
        url = getattr(record, platform, None)
        res = research_social(platform, url, timeout=min(timeout, 10.0))
        social_results[platform] = res
        setattr(record, f"{platform}_status", res.status)
        setattr(record, f"{platform}_activity", res.activity_signal)
        record.social_evidence.extend([e.to_dict() for e in res.evidence])

        # Adopt any WhatsApp/phone/website found in social bios
        if not record.whatsapp and res.whatsapp_cta:
            record.whatsapp = res.whatsapp_cta
        if not record.website and res.extracted_website:
            record.website = res.extracted_website
        if not record.phone and res.extracted_phones:
            record.phone = res.extracted_phones[0]

    record.social_details = {
        platform: {
            "url": res.url,
            "status": res.status,
            "resource_status": res.resource_status,
            "metrics": res.public_metrics_snippet,
            "commercial_signals": res.commercial_signals,
            "link_in_bio": res.link_in_bio,
        }
        for platform, res in social_results.items()
    }

    # 4. Google Maps & Listing Investigation
    google_res = research_google(
        record.google_maps_url,
        record.google_rating,
        record.google_reviews,
        record.google_address,
        record.google_category,
        record.website,
    )
    record.google_website_connection = google_res.website_connection
    record.google_other_listing_notes = google_res.other_listing_notes
    record.google_evidence = [e.to_dict() for e in google_res.evidence]

    # 5. Products & Services Commercial Offering
    record.products_services_summary = _synthesize_products_and_services(record, website_res, search_res)

    # 6. Business Positioning & Maturity
    record.business_type = _business_type_guess(record)
    record.local_offline_online = _presence_model(record)
    record.apparent_target_market = _target_market_note(record)
    record.digital_maturity = _classify_maturity(record)

    # 7. Contact Matrix (5-State standard)
    contact_matrix = _evaluate_contact_matrix(record, website_res, social_results, search_res)
    record.contact_details = contact_matrix

    # 8. Digital Gaps Identification
    gaps = _identify_digital_gaps(record, website_res, social_results, contact_matrix)
    record.digital_gaps_details = gaps
    record.observed_digital_gaps = [f"{g['title']}: {g['description']}" for g in gaps]

    # 9. MalikAxiom Opportunities Mapping
    opps = _map_malikaxiom_opportunities(record, gaps, website_res)
    record.malikaxiom_opportunities = opps

    # 10. Evidence Lineage & Separation
    facts: list[str] = []
    if record.website and record.website_status == "exists":
        facts.append(f"Website exists: {record.website}")
    if record._http_status_snapshot:
        facts.append(f"Website returned HTTP {record._http_status_snapshot}")
    for ev in record.website_evidence:
        if ev.get("class") == EvidenceClass.VERIFIED_FACT:
            facts.append(ev.get("statement", ""))
    for ev in record.social_evidence:
        if ev.get("class") == EvidenceClass.VERIFIED_FACT:
            facts.append(ev.get("statement", ""))
    for ev in record.google_evidence:
        if ev.get("class") == EvidenceClass.VERIFIED_FACT:
            facts.append(ev.get("statement", ""))
    for ev in search_res.evidence:
        if ev.class_ == EvidenceClass.VERIFIED_FACT:
            facts.append(ev.statement)
    record.verified_facts = [f for f in facts if f]

    obs_list: list[str] = []
    if record.website_type:
        obs_list.append(f"Apparent website type: {record.website_type}")
    if record.ecommerce_status == "present":
        obs_list.append("E-commerce or product/catalog signals detected on website.")
    if record.checkout_status == "present":
        obs_list.append("Checkout/order capability signals detected on website.")
    if record.contact_option_present == "present":
        obs_list.append("Contact options appear present on website.")
    for o in opps:
        obs_list.append(f"Potential Opportunity: {o['service']} — {o['why_relevant']}")
    record.reasonable_observations = obs_list

    unknowns_list: list[str] = []
    if record.website_status == "unknown":
        unknowns_list.append("Website status unknown")
    if record.website and record._reachable_snapshot == "unreachable":
        unknowns_list.append(f"Website ({record.website}) could not be reached; content-level signals unknown")
    for p in PLATFORMS:
        if getattr(record, f"{p}_status") == "unknown":
            unknowns_list.append(f"{p.capitalize()} status unknown")
    if not record.google_rating:
        unknowns_list.append("Google rating not supplied")
    if not record.google_reviews:
        unknowns_list.append("Google review count not supplied")
    record.unknowns = unknowns_list

    # 11. Final 8-Point Synthesis
    record.research_synthesis = _build_final_synthesis(
        record, website_res, social_results, contact_matrix, gaps, opps
    )

    # 12. Research Coverage Tracker across 10 Evaluated Dimensions
    record.research_coverage = {
        "search_discovery": bool(record.search_findings),
        "website_investigation": bool(website_res.pages_checked or website_res.status in ("not_found", "unreachable", "exists", "empty")),
        "products_services": bool(record.products_services_summary),
        "ecommerce_checkout": bool(record.ecommerce_details),
        "social_presence": len(social_results) > 0,
        "google_presence": bool(google_res),
        "business_positioning": bool(record.digital_maturity and record.digital_maturity != "unknown"),
        "contact_matrix": bool(record.contact_details),
        "digital_gaps": len(record.digital_gaps_details) > 0,
        "malikaxiom_opportunities": len(record.malikaxiom_opportunities) > 0,
    }

    # Classify overall research status
    website_actually_unreachable = (
        website_res.reachable == "unreachable" and website_res.status == "exists"
    )
    website_status_unknown = (
        website_res.status == "unknown" and not record.website
    )
    has_social_unknown = any(
        getattr(record, f"{p}_status") == "unknown"
        for p in PLATFORMS
    )

    if website_status_unknown:
        record.research_status = "RESEARCHED" if not has_social_unknown else "PARTIALLY_RESEARCHED"
    elif website_actually_unreachable:
        record.research_status = "WEBSITE_UNREACHABLE"
    elif has_social_unknown:
        record.research_status = "PARTIALLY_RESEARCHED"
    else:
        record.research_status = "RESEARCHED"

    record.research_timestamp = _now_iso()
    return record


def run_research(
    csv_path: Path,
    output_dir: Path | None = None,
    timeout: float = 12.0,
) -> tuple[Path, Path, int, int, int, int, int]:
    """Execute the deep web research stage across all leads.

    Returns:
        (json_path, csv_path, total, fully_researched, partial, unreachable, errors)
    """
    out_dir = Path(output_dir) if output_dir else OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    leads = load_leads(csv_path)
    logger.info("Starting deep research for %d leads from %s", len(leads), csv_path.name)

    records: list[ResearchRecord] = []
    fully_researched = 0
    partial = 0
    unreachable = 0
    errors = 0

    for idx, lead in enumerate(leads, start=1):
        name = resolve_name(lead) or "Unknown Lead"
        lead_id = _make_lead_id(lead)
        logger.info("Deep researching %d/%d — %s", idx, len(leads), name)

        try:
            record = _research_one(lead, lead_id, timeout=timeout)
            status = record.research_status
            if status == "RESEARCHED":
                fully_researched += 1
            elif status == "PARTIALLY_RESEARCHED":
                partial += 1
            elif status == "WEBSITE_UNREACHABLE":
                unreachable += 1
            else:
                errors += 1
            records.append(record)
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "Unhandled error researching lead %s (row %s): %s",
                lead_id,
                lead.get("row_number"),
                exc,
            )
            errors += 1
            records.append(_error_record(lead_id, lead, str(exc)[:500]))

    json_path = out_dir / "research_results.json"
    csv_path = out_dir / "research_results.csv"
    _write_json(json_path, records)
    _write_csv(csv_path, records)

    return json_path, csv_path, len(leads), fully_researched, partial, unreachable, errors


def _error_record(lead_id: str, lead: dict[str, Any], error_note: str) -> ResearchRecord:
    return ResearchRecord(
        lead_id=lead_id,
        business_name=resolve_name(lead),
        category=None,
        location=None,
        phone=None,
        mobile_phone=None,
        whatsapp=None,
        landline=None,
        email=None,
        youtube=None,
        google_maps_url=None,
        original_source_data={k: v for k, v in lead["raw"].items()},
        source_file=lead.get("source_file", ""),
        row_number=lead.get("row_number", 0),
        website=None,
        website_status="unknown",
        website_type=None,
        website_quality_observation="",
        ecommerce_status="unknown",
        checkout_status="unknown",
        online_ordering="unknown",
        whatsapp_contact="unknown",
        contact_option_present="unknown",
        obvious_broken_signals=[],
        important_observable_features=[],
        website_evidence=[],
        instagram=None,
        instagram_status="unknown",
        instagram_activity="unknown",
        facebook=None,
        facebook_status="unknown",
        facebook_activity="unknown",
        tiktok=None,
        tiktok_status="unknown",
        tiktok_activity="unknown",
        linkedin=None,
        linkedin_status="unknown",
        linkedin_activity="unknown",
        social_evidence=[],
        google_rating=None,
        google_reviews=None,
        google_address=None,
        google_category=None,
        google_website_connection="unknown",
        google_other_listing_notes="",
        google_evidence=[],
        business_type=None,
        local_offline_online="unknown",
        apparent_target_market="unknown",
        digital_maturity="unknown",
        observed_digital_gaps=[],
        verified_facts=[],
        reasonable_observations=[],
        unknowns=["Research failed with an unhandled error"],
        research_status="ERROR",
        research_timestamp=_now_iso(),
        error_note=error_note,
    )


def _research_summary(record: ResearchRecord) -> str:
    """Build a rich, factual research summary."""
    name = record.business_name or "Unknown business"
    cat = record.category or "business"
    loc = record.location or "unknown location"

    parts: list[str] = [f"{name} ({cat}) in {loc}"]

    if record.products_services_summary:
        parts.append(record.products_services_summary)

    presence = []
    if record.website and record.website_status == "exists" and record._reachable_snapshot == "reachable":
        presence.append(f"Reachable website ({record.website}) [{record.ecommerce_details.get('detected_platform', 'Web')}]")
    elif record.website:
        presence.append(f"Website {record.website} ({record._reachable_snapshot})")
    else:
        presence.append("No website URL")

    social = [p.capitalize() for p in PLATFORMS if getattr(record, f"{p}_status", "unknown") == "present"]
    if social:
        presence.append(f"Social: {', '.join(social)}")

    if record.google_maps_url:
        presence.append(f"Google Maps Listing ({record.google_rating or 'unrated'})")

    parts.append("; ".join(presence))

    if record.observed_digital_gaps:
        parts.append(f"Gaps identified: {len(record.observed_digital_gaps)}")

    return " | ".join(parts)


def _record_to_row(record: ResearchRecord) -> dict[str, Any]:
    """Flat row for CSV output."""
    return {
        "lead_id": record.lead_id,
        "business_name": record.business_name or "",
        "category": record.category or "",
        "location": record.location or "",
        "phone": record.phone or "",
        "mobile_phone": record.mobile_phone or "",
        "whatsapp": record.whatsapp or "",
        "landline": record.landline or "",
        "email": record.email or "",
        "website": record.website or "",
        "website_status": record.website_status,
        "website_type": record.website_type or "",
        "website_quality_observation": record.website_quality_observation,
        "ecommerce_status": record.ecommerce_status,
        "checkout_status": record.checkout_status,
        "online_ordering": record.online_ordering,
        "instagram": record.instagram or "",
        "instagram_status": record.instagram_status,
        "instagram_activity": record.instagram_activity,
        "facebook": record.facebook or "",
        "facebook_status": record.facebook_status,
        "facebook_activity": record.facebook_activity,
        "tiktok": record.tiktok or "",
        "tiktok_status": record.tiktok_status,
        "tiktok_activity": record.tiktok_activity,
        "linkedin": record.linkedin or "",
        "linkedin_status": record.linkedin_status,
        "linkedin_activity": record.linkedin_activity,
        "youtube": record.youtube or "",
        "google_rating": record.google_rating or "",
        "google_reviews": record.google_reviews or "",
        "google_maps_url": record.google_maps_url or "",
        "digital_maturity": record.digital_maturity,
        "business_type": record.business_type or "",
        "local_offline_online": record.local_offline_online,
        "apparent_target_market": record.apparent_target_market,
        "products_services_summary": record.products_services_summary,
        "detected_platform": record.ecommerce_details.get("detected_platform", ""),
        "order_flow_type": record.ecommerce_details.get("order_flow_type", ""),
        "payment_methods": ", ".join(record.ecommerce_details.get("payment_methods", [])),
        "observed_digital_gaps": " | ".join(record.observed_digital_gaps),
        "malikaxiom_opportunities": " | ".join([f"{o['service']} ({o['package']})" for o in record.malikaxiom_opportunities]),
        "verified_facts": " | ".join(record.verified_facts),
        "reasonable_observations": " | ".join(record.reasonable_observations),
        "unknowns": " | ".join(record.unknowns),
        "research_coverage_score": f"{sum(1 for v in record.research_coverage.values() if v)}/{len(record.research_coverage)}" if record.research_coverage else "0/10",
        "research_summary": _research_summary(record),
        "research_status": record.research_status,
        "research_timestamp": record.research_timestamp,
        "error_note": record.error_note,
    }


def _record_to_dict(record: ResearchRecord) -> dict[str, Any]:
    """Rich dict for JSON output."""
    return {
        "lead_id": record.lead_id,
        "business_name": record.business_name,
        "category": record.category,
        "location": record.location,
        "phone": record.phone,
        "mobile_phone": record.mobile_phone,
        "whatsapp": record.whatsapp,
        "landline": record.landline,
        "email": record.email,
        "google_maps_url": record.google_maps_url,
        "original_source_data": record.original_source_data,
        "source_file": record.source_file,
        "row_number": record.row_number,

        "website": record.website,
        "website_status": record.website_status,
        "website_reachable": record._reachable_snapshot,
        "http_status": record._http_status_snapshot,
        "website_type": record.website_type,
        "website_quality_observation": record.website_quality_observation,
        "ecommerce_status": record.ecommerce_status,
        "checkout_status": record.checkout_status,
        "online_ordering": record.online_ordering,
        "whatsapp_contact": record.whatsapp_contact,
        "contact_option_present": record.contact_option_present,
        "obvious_broken_signals": record.obvious_broken_signals,
        "important_observable_features": record.important_observable_features,
        "website_evidence": record.website_evidence,

        "instagram": record.instagram,
        "instagram_status": record.instagram_status,
        "instagram_activity": record.instagram_activity,
        "facebook": record.facebook,
        "facebook_status": record.facebook_status,
        "facebook_activity": record.facebook_activity,
        "tiktok": record.tiktok,
        "tiktok_status": record.tiktok_status,
        "tiktok_activity": record.tiktok_activity,
        "linkedin": record.linkedin,
        "linkedin_status": record.linkedin_status,
        "linkedin_activity": record.linkedin_activity,
        "youtube": record.youtube,
        "social_evidence": record.social_evidence,

        "google_rating": record.google_rating,
        "google_reviews": record.google_reviews,
        "google_address": record.google_address,
        "google_category": record.google_category,
        "google_website_connection": record.google_website_connection,
        "google_other_listing_notes": record.google_other_listing_notes,
        "google_evidence": record.google_evidence,

        "business_type": record.business_type,
        "local_offline_online": record.local_offline_online,
        "apparent_target_market": record.apparent_target_market,
        "digital_maturity": record.digital_maturity,

        "products_services_summary": record.products_services_summary,
        "ecommerce_details": record.ecommerce_details,
        "social_details": record.social_details,
        "contact_details": record.contact_details,
        "search_findings": record.search_findings,
        "digital_gaps_details": record.digital_gaps_details,
        "malikaxiom_opportunities": record.malikaxiom_opportunities,
        "research_synthesis": record.research_synthesis,
        "research_coverage": record.research_coverage,

        "observed_digital_gaps": record.observed_digital_gaps,
        "verified_facts": record.verified_facts,
        "reasonable_observations": record.reasonable_observations,
        "unknowns": record.unknowns,

        "research_summary": _research_summary(record),
        "research_status": record.research_status,
        "research_timestamp": record.research_timestamp,
        "error_note": record.error_note,
    }


def _write_json(path: Path, records: list[ResearchRecord]) -> None:
    payload: list[dict[str, Any]] = [_record_to_dict(r) for r in records]
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info("Wrote JSON: %s (%d records)", path, len(payload))


def _write_csv(path: Path, records: list[ResearchRecord]) -> None:
    if not records:
        path.write_text("", encoding="utf-8")
        logger.info("Wrote empty CSV: %s", path)
        return

    rows: list[dict[str, Any]] = [_record_to_row(r) for r in records]
    fieldnames: list[str] = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    logger.info("Wrote CSV: %s (%d rows, %d columns)", path, len(rows), len(fieldnames))


__all__ = ["ResearchRecord", "run_research", "build_record"]
