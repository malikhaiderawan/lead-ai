"""Milestone 3 — Knowledge Loader.

Loads and parses the 6 knowledge .md files from the knowledge/ directory
and exposes them as structured Python data for the qualification engine.

No external dependencies. Standard library only.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

KNOWLEDGE_DIR = Path(__file__).resolve().parent.parent / "knowledge"


# ---------------------------------------------------------------------------
# Public structured data returned by the loader
# ---------------------------------------------------------------------------

# Service catalog entry
# Each entry has: id, name, triggers (evidence keywords), description
SERVICES: list[dict[str, Any]] = [
    {
        "id": "business_digitalization",
        "name": "Business Digitalization — 20,000 PKR",
        "short_name": "Business Digitalization",
        "triggers": [
            "no_website",
            "no_social",
            "minimal_digital",
            "no_google",
            "weak_presence",
            "offline_business",
        ],
        "description": (
            "Flagship 20K PKR package. Responsive website, Google Business Profile, "
            "Maps, Search Console, basic SEO, Instagram/Facebook/TikTok setup, "
            "5 branded posts, 3 reels, and premium basic branding."
        ),
        "fit_profiles": ["A"],  # ideal client profile letters
    },
    {
        "id": "ecommerce",
        "name": "E-Commerce / Shopify",
        "short_name": "E-Commerce",
        "triggers": [
            "sells_products",
            "no_ecommerce",
            "social_seller",
            "retail_business",
            "catalog_missing",
            "no_online_ordering",
        ],
        "description": (
            "Shopify stores, custom e-commerce sites, product/catalog systems, "
            "payment integrations, delivery/order systems."
        ),
        "fit_profiles": ["B"],
    },
    {
        "id": "web_development",
        "name": "Web Development / Website Revamp",
        "short_name": "Web Development",
        "triggers": [
            "outdated_website",
            "weak_website",
            "website_unreachable",
            "website_exists_but_poor",
            "needs_revamp",
        ],
        "description": (
            "Simple business websites, landing pages, responsive/custom websites, "
            "custom web applications, backend/API systems, e-commerce websites."
        ),
        "fit_profiles": ["C"],
    },
    {
        "id": "business_automation",
        "name": "Business Automation",
        "short_name": "Business Automation",
        "triggers": [
            "manual_processes",
            "repetitive_tasks",
            "order_handling",
            "workflow_inefficiency",
        ],
        "description": (
            "Repetitive task automation, customer/order workflows, business process "
            "automation, API integrations, internal business tools."
        ),
        "fit_profiles": ["D"],
    },
    {
        "id": "mobile_development",
        "name": "Mobile Development",
        "short_name": "Mobile Development",
        "triggers": [
            "established_business",
            "customer_facing_app",
            "mobile_app_use_case",
        ],
        "description": (
            "Android, iOS, and cross-platform applications. "
            "6 years of mobile development experience."
        ),
        "fit_profiles": ["E"],
    },
    {
        "id": "ai_integration",
        "name": "AI Development & Integration",
        "short_name": "AI Integration",
        "triggers": [
            "ai_use_case",
            "data_processing",
            "intelligent_workflow",
        ],
        "description": (
            "AI integrations, AI-powered features, AI business workflows, "
            "integration of AI into existing products/business systems."
        ),
        "fit_profiles": ["F"],
    },
    {
        "id": "social_media_content",
        "name": "AI-Assisted Social Media Content",
        "short_name": "Social Media Content",
        "triggers": [
            "no_social",
            "inactive_social",
            "no_content",
        ],
        "description": (
            "AI-assisted social media posts, reels, basic ongoing digital content "
            "supporting a professional online presence."
        ),
        "fit_profiles": ["A", "B", "C"],
    },
]


# Ideal client profiles mapping
IDEAL_CLIENT_PROFILES: list[dict[str, Any]] = [
    {
        "letter": "A",
        "name": "Offline / Raw Business",
        "description": "Real, active business with little or no professional digital presence.",
        "primary_service_id": "business_digitalization",
    },
    {
        "letter": "B",
        "name": "Social Seller Without a Store",
        "description": "Sells products via social DMs but has no proper online store.",
        "primary_service_id": "ecommerce",
    },
    {
        "letter": "C",
        "name": "Outdated Digital Presence",
        "description": "Has a website but it's outdated, non-responsive, or weak.",
        "primary_service_id": "web_development",
    },
    {
        "letter": "D",
        "name": "Process-Heavy Manual Operations",
        "description": "Repetitive tasks, manual order/customer handling, or disconnected tools.",
        "primary_service_id": "business_automation",
    },
    {
        "letter": "E",
        "name": "Established Business With App Use Case",
        "description": "Legitimate, established business with strong customer-facing mobile app reason.",
        "primary_service_id": "mobile_development",
    },
    {
        "letter": "F",
        "name": "Clear AI Use Case",
        "description": "Observable workflow or product where AI would genuinely add value.",
        "primary_service_id": "ai_integration",
    },
]


# Sales potential definitions
SALES_POTENTIAL_DEFINITIONS: dict[str, str] = {
    "HIGH": (
        "Active/genuine business, clear digital opportunity, "
        "strong fit with one or more MalikAxiom services, "
        "enough evidence to justify outreach."
    ),
    "MODERATE": (
        "Possible opportunity exists but urgency is unclear, "
        "evidence incomplete, or service fit is not particularly strong."
    ),
    "LOW": (
        "Business appears legitimate but opportunity is weak; "
        "digital presence already relatively strong, no obvious immediate fit."
    ),
    "SKIP": (
        "Irrelevant, duplicate, inactive, unverifiable, "
        "or clearly unsuitable for MalikAxiom."
    ),
}


# Confidence definitions
CONFIDENCE_DEFINITIONS: dict[str, str] = {
    "HIGH": "Multiple verified facts; active business signal confirmed; gap clearly observed.",
    "MEDIUM": "Some verified facts but key details unknown (e.g., website unreachable).",
    "LOW": "Mostly unknown information; minimal verified data available.",
}


# Company info (static — loaded once from company.md for accuracy)
COMPANY_INFO: dict[str, str] = {
    "name": "MalikAxiom Technology",
    "website": "https://malikaxiomtech.com/",
    "email": "hello@malikaxiomtech.com",
    "whatsapp": "+923130466400",
    "flagship_price": "20,000 PKR",
}


def get_service_by_id(service_id: str) -> dict[str, Any] | None:
    """Return a service dict by its id, or None if not found."""
    for svc in SERVICES:
        if svc["id"] == service_id:
            return svc
    return None


def get_service_short_name(service_id: str) -> str:
    """Return the short display name for a service id."""
    svc = get_service_by_id(service_id)
    return svc["short_name"] if svc else service_id


def knowledge_files_present() -> list[str]:
    """Return list of missing knowledge files (empty = all present)."""
    required = [
        "company.md",
        "services.md",
        "business_digitalization.md",
        "ideal_clients.md",
        "qualification_rules.md",
        "outreach_rules.md",
    ]
    return [f for f in required if not (KNOWLEDGE_DIR / f).is_file()]


def load_knowledge_text(filename: str) -> str:
    """Return raw text content of a knowledge file."""
    path = KNOWLEDGE_DIR / filename
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8")


def _extract_section(text: str, heading: str) -> str:
    """Extract a markdown section by heading (## or ###)."""
    pattern = re.compile(
        r"(?:^|\n)(#{1,3}\s+" + re.escape(heading) + r")\s*\n(.*?)(?=\n#{1,3}\s|\Z)",
        re.DOTALL | re.IGNORECASE,
    )
    m = pattern.search(text)
    if m:
        return m.group(2).strip()
    return ""
