"""Milestone 2 research module.

Deep, multi-source web research engine for lead qualification and outreach.
Includes multi-page website investigation, e-commerce flow analysis,
social intelligence extraction, search engine discovery, and evidence-based gap identification.
"""

from .evidence import Evidence, EvidenceClass, ResourceStatus
from .google_researcher import GoogleResearch, research_google
from .input_loader import load_leads, resolve_name
from .researcher import ResearchRecord, run_research
from .search_researcher import SearchResearch, research_search
from .social_researcher import PLATFORMS, SocialResearch, research_social
from .website_researcher import WebsiteResearch, research_website

__all__ = [
    "Evidence",
    "EvidenceClass",
    "ResourceStatus",
    "GoogleResearch",
    "research_google",
    "load_leads",
    "resolve_name",
    "ResearchRecord",
    "run_research",
    "SearchResearch",
    "research_search",
    "PLATFORMS",
    "SocialResearch",
    "research_social",
    "WebsiteResearch",
    "research_website",
]
