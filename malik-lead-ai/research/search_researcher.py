"""Milestone 2 — Public search engine researcher for brand and profile discovery.

Performs intelligent public search queries (using Serper Google Search API / Brave API)
to discover official websites, social profiles, business positioning, and contact signals
when they are missing or need cross-verification.

Standard library only.
"""

from __future__ import annotations

import html
import json
import logging
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any

from .evidence import Evidence, EvidenceClass, ResourceStatus

logger = logging.getLogger(__name__)

SEARCH_TIMEOUT = 10.0
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)

# Common directory / aggregator / social domains to filter out when searching for an official site
_DIRECTORY_DOMAINS = frozenset({
    "facebook.com", "instagram.com", "twitter.com", "x.com", "linkedin.com",
    "tiktok.com", "youtube.com", "pinterest.com", "threads.net", "threads.com",
    "yelp.com", "yellowpages.com", "tripadvisor.com", "wikipedia.org", "trustpilot.com",
    "reddit.com", "quora.com", "medium.com", "marham.pk", "oladoc.com", "instacare.pk",
    "shafa.pk", "daraz.pk", "pakwheels.com", "zameen.com", "olx.com.pk",
    "foodpanda.pk", "dunya.tv", "geo.tv", "tribune.com.pk", "dawn.com",
    "linktr.ee", "linktree.com", "bio.link", "lnk.bio", "beacons.ai", "taplink.cc",
})


@dataclass
class SearchResultItem:
    title: str
    url: str
    snippet: str


@dataclass
class SearchResearch:
    """Structured search engine research findings for one lead."""

    status: str                         # FOUND | NOT_FOUND | CHECK_FAILED | BLOCKED | UNKNOWN
    queries_performed: list[str] = field(default_factory=list)
    results: list[SearchResultItem] = field(default_factory=list)
    discovered_links: dict[str, str] = field(default_factory=dict)   # platform -> url
    discovered_website: str | None = None
    discovered_phones: list[str] = field(default_factory=list)
    discovered_emails: list[str] = field(default_factory=list)
    search_snippets: list[str] = field(default_factory=list)
    evidence: list[Evidence] = field(default_factory=list)
    error_detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "queries_performed": self.queries_performed,
            "discovered_links": self.discovered_links,
            "discovered_website": self.discovered_website,
            "discovered_phones": self.discovered_phones,
            "discovered_emails": self.discovered_emails,
            "search_snippets": self.search_snippets[:5],
            "evidence": [e.to_dict() for e in self.evidence],
            "error_detail": self.error_detail,
        }


def _strip_html(text: str) -> str:
    clean = re.sub(r'<[^>]+>', '', text)
    clean = html.unescape(clean)
    return re.sub(r'\s+', ' ', clean).strip()


def _extract_domain(url: str) -> str:
    try:
        parsed = urllib.parse.urlparse(url)
        host = parsed.netloc.lower()
        if host.startswith("www."):
            host = host[4:]
        return host
    except Exception:
        return ""


def _search_serper(query: str, api_key: str, timeout: float = SEARCH_TIMEOUT) -> tuple[str, list[SearchResultItem], str]:
    """Execute search query using Serper.dev Google Search API."""
    payload = json.dumps({"q": query, "num": 10}).encode("utf-8")
    req = urllib.request.Request(
        "https://google.serper.dev/search",
        data=payload,
        headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            if response.status == 200:
                body = response.read(150_000)
                data = json.loads(body.decode("utf-8", errors="replace"))
                items: list[SearchResultItem] = []
                for org in data.get("organic", []):
                    title = _strip_html(org.get("title", ""))
                    link = org.get("link", "").strip()
                    snippet = _strip_html(org.get("snippet", ""))
                    if link:
                        items.append(SearchResultItem(title=title, url=link, snippet=snippet))
                if items:
                    return ResourceStatus.FOUND, items, ""
                return ResourceStatus.NOT_FOUND, [], "Zero organic search results"
            return ResourceStatus.CHECK_FAILED, [], f"Serper HTTP {response.status}"
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            return ResourceStatus.BLOCKED, [], f"Serper auth error HTTP {exc.code}"
        return ResourceStatus.CHECK_FAILED, [], f"Serper HTTP error {exc.code}: {exc.reason}"
    except Exception as exc:
        return ResourceStatus.CHECK_FAILED, [], f"Serper {type(exc).__name__}: {str(exc)[:150]}"


def _search_brave(query: str, api_key: str, timeout: float = SEARCH_TIMEOUT) -> tuple[str, list[SearchResultItem], str]:
    """Fallback search query using Brave Search API."""
    url = "https://api.search.brave.com/res/v1/web/search"
    params = urllib.parse.urlencode({"q": query, "count": 10})
    req = urllib.request.Request(
        f"{url}?{params}",
        headers={"Accept": "application/json", "X-Subscription-Token": api_key},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            if response.status == 200:
                body = response.read(150_000)
                data = json.loads(body.decode("utf-8", errors="replace"))
                items: list[SearchResultItem] = []
                for res in data.get("web", {}).get("results", []):
                    title = _strip_html(res.get("title", ""))
                    link = res.get("url", "").strip()
                    snippet = _strip_html(res.get("description", ""))
                    if link:
                        items.append(SearchResultItem(title=title, url=link, snippet=snippet))
                if items:
                    return ResourceStatus.FOUND, items, ""
                return ResourceStatus.NOT_FOUND, [], "Zero Brave search results"
            return ResourceStatus.CHECK_FAILED, [], f"Brave HTTP {response.status}"
    except Exception as exc:
        return ResourceStatus.CHECK_FAILED, [], f"Brave {type(exc).__name__}: {str(exc)[:150]}"


def execute_search_query(query: str, timeout: float = SEARCH_TIMEOUT) -> tuple[str, list[SearchResultItem], str]:
    """Execute a single search query via Serper Google Search (or Brave fallback).

    DuckDuckGo scraper has been removed to avoid bot-blocking.
    """
    serper_key = os.environ.get("SERPER_API_KEY", "").strip()
    if serper_key:
        return _search_serper(query, serper_key, timeout=timeout)

    brave_key = os.environ.get("BRAVE_API_KEY", "").strip() or os.environ.get("BRAVE_SEARCH_API_KEY", "").strip()
    if brave_key:
        return _search_brave(query, brave_key, timeout=timeout)

    return ResourceStatus.CHECK_FAILED, [], "No search API key found (SERPER_API_KEY required)"


def research_search(
    business_name: str | None,
    location: str | None = None,
    category: str | None = None,
    existing_website: str | None = None,
    existing_instagram: str | None = None,
    existing_facebook: str | None = None,
    timeout: float = SEARCH_TIMEOUT,
) -> SearchResearch:
    """Intelligently research a business via search engine discovery and cross-verification."""
    result = SearchResearch(status=ResourceStatus.UNKNOWN)

    name = (business_name or "").strip()
    if not name or name.lower() in ("unknown", "n/a", "none"):
        result.status = ResourceStatus.UNKNOWN
        result.evidence.append(
            Evidence(class_=EvidenceClass.UNKNOWN, statement="No business name provided for search research.")
        )
        return result

    loc = (location or "").strip()
    loc_clean = ""
    if loc and loc.lower() not in ("unknown", "n/a", "none"):
        # Take first city hint or first 2 words of address
        for city in ("Islamabad", "Rawalpindi", "Lahore", "Karachi", "Faisalabad", "Multan", "Peshawar", "Sialkot", "Gujranwala"):
            if city.lower() in loc.lower():
                loc_clean = city
                break
        if not loc_clean:
            loc_clean = loc.split(",")[0].strip()

    # Determine what queries to perform
    queries: list[str] = []
    base_query = f"{name} {loc_clean}".strip()
    queries.append(base_query)

    # If website or key socials are missing, craft targeted discovery queries
    if not existing_instagram:
        queries.append(f"{name} {loc_clean} Instagram".strip())
    if not existing_facebook and not existing_instagram:
        queries.append(f"{name} {loc_clean} Facebook".strip())
    if not existing_website and len(queries) < 3:
        queries.append(f"{name} {loc_clean} website online store".strip())

    all_items: list[SearchResultItem] = []
    statuses: list[str] = []
    errors: list[str] = []

    # Execute search queries
    for q in queries[:2]:  # Efficient, high-value queries
        result.queries_performed.append(q)
        st, items, err = execute_search_query(q, timeout=timeout)
        statuses.append(st)
        if err:
            errors.append(err)
        if items:
            all_items.extend(items)

    result.results = all_items

    # Aggregate overall status
    if any(s == ResourceStatus.FOUND for s in statuses):
        result.status = ResourceStatus.FOUND
    elif any(s == ResourceStatus.BLOCKED for s in statuses):
        result.status = ResourceStatus.BLOCKED
        result.error_detail = "; ".join(errors)
    elif any(s == ResourceStatus.CHECK_FAILED for s in statuses):
        result.status = ResourceStatus.CHECK_FAILED
        result.error_detail = "; ".join(errors)
    else:
        result.status = ResourceStatus.NOT_FOUND

    # Process search results
    seen_urls: set[str] = set()
    for item in all_items:
        u = item.url.strip()
        if not u or u in seen_urls:
            continue
        seen_urls.add(u)
        u_lower = u.lower()
        domain = _extract_domain(u)

        # Collect search snippets for business understanding
        if item.snippet and len(item.snippet) > 15:
            result.search_snippets.append(f"[{item.title}] {item.snippet}")

        # Extract phones from search snippet / title
        phone_matches = re.findall(r'(?:\+92|03\d{2})[\s\-]?\d{7}', item.snippet + " " + item.title)
        for pm in phone_matches:
            clean_pm = re.sub(r'[\s\-]', '', pm)
            if clean_pm not in result.discovered_phones:
                result.discovered_phones.append(clean_pm)

        # Extract emails from search snippet
        email_matches = re.findall(r'[\w.+-]+@[\w-]+\.[a-zA-Z]{2,}', item.snippet)
        for em in email_matches:
            em_clean = em.lower().strip()
            if em_clean not in result.discovered_emails and not em_clean.endswith((".png", ".jpg", ".webp")):
                result.discovered_emails.append(em_clean)

        # Classify social profiles discovered in search
        if "instagram.com/" in u_lower and "instagram" not in result.discovered_links:
            # Skip hashtag, explore, or search pages
            if not any(x in u_lower for x in ("/explore/", "/tags/", "/p/", "/reel/")):
                result.discovered_links["instagram"] = u
        elif "facebook.com/" in u_lower and "facebook" not in result.discovered_links:
            if not any(x in u_lower for x in ("/share/", "/photo", "/groups/")):
                result.discovered_links["facebook"] = u
        elif "linkedin.com/company/" in u_lower and "linkedin" not in result.discovered_links:
            result.discovered_links["linkedin"] = u
        elif "tiktok.com/@" in u_lower and "tiktok" not in result.discovered_links:
            result.discovered_links["tiktok"] = u
        elif ("youtube.com/@" in u_lower or "youtube.com/channel/" in u_lower) and "youtube" not in result.discovered_links:
            result.discovered_links["youtube"] = u

        # Discovered website candidates (if lead had no website in input)
        if not existing_website and not result.discovered_website:
            if domain and domain not in _DIRECTORY_DOMAINS and "." in domain:
                # Check if brand name matches or is contained in domain or title
                clean_brand = re.sub(r'[^a-zA-Z0-9]', '', name.lower())
                clean_dom = re.sub(r'[^a-zA-Z0-9]', '', domain)
                if clean_brand[:6] in clean_dom or clean_dom in clean_brand:
                    result.discovered_website = u
                    result.discovered_links["website"] = u

    # Build evidence items
    if result.status == ResourceStatus.FOUND:
        result.evidence.append(
            Evidence(
                class_=EvidenceClass.VERIFIED_FACT,
                statement=f"Search engine query '{queries[0]}' returned {len(all_items)} public result items.",
                detail=f"Discovered links: {list(result.discovered_links.keys())}",
            )
        )
        if result.discovered_website:
            result.evidence.append(
                Evidence(
                    class_=EvidenceClass.REASONABLE_OBSERVATION,
                    statement=f"Search engine identified official website candidate: {result.discovered_website}",
                    source_url=result.discovered_website,
                )
            )
    elif result.status == ResourceStatus.BLOCKED:
        result.evidence.append(
            Evidence(
                class_=EvidenceClass.UNKNOWN,
                statement="Search queries were throttled or blocked by the remote search service.",
                detail=result.error_detail,
            )
        )
    elif result.status == ResourceStatus.CHECK_FAILED:
        result.evidence.append(
            Evidence(
                class_=EvidenceClass.UNKNOWN,
                statement="Search query could not be executed due to network or DNS resolution failure.",
                detail=result.error_detail,
            )
        )
    else:
        result.evidence.append(
            Evidence(
                class_=EvidenceClass.UNKNOWN,
                statement=f"Search engine returned zero public listings for '{queries[0]}'.",
            )
        )

    return result


__all__ = ["SearchResearch", "SearchResultItem", "research_search", "execute_search_query"]
