"""Milestone 2 — Public search engine researcher for brand and profile discovery.

Performs intelligent public search queries (using DuckDuckGo / public web search)
to discover official websites, social profiles, business positioning, and contact signals
when they are missing or need cross-verification.

Standard library only.
"""

from __future__ import annotations

import html
import logging
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

# Common directory / aggregator domains to filter out when searching for an official site
_DIRECTORY_DOMAINS = frozenset({
    "facebook.com", "instagram.com", "twitter.com", "x.com", "linkedin.com",
    "tiktok.com", "youtube.com", "pinterest.com", "yelp.com", "yellowpages.com",
    "tripadvisor.com", "wikipedia.org", "marham.pk", "oladoc.com", "instacare.pk",
    "shafa.pk", "daraz.pk", "pakwheels.com", "zameen.com", "olx.com.pk",
    "foodpanda.pk", "dunya.tv", "geo.tv", "tribune.com.pk", "dawn.com",
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


def _extract_duckduckgo_results(html_text: str) -> list[SearchResultItem]:
    """Parse DuckDuckGo HTML results into structured items."""
    items: list[SearchResultItem] = []

    # Pattern for results in html.duckduckgo.com/html/
    blocks = re.findall(
        r'<div[^>]*class="[^"]*result__body[^"]*"[^>]*>(.*?)</div>',
        html_text,
        re.DOTALL | re.IGNORECASE,
    )

    if not blocks:
        # Fallback pattern for lite.duckduckgo.com or table layouts
        table_blocks = re.findall(
            r'<tr[^>]*>.*?<a[^>]*class="result-link"[^>]*href="([^"]+)"[^>]*>(.*?)</a>.*?<td[^>]*class="result-snippet"[^>]*>(.*?)</td>.*?</tr>',
            html_text,
            re.DOTALL | re.IGNORECASE,
        )
        for href, title_html, snip_html in table_blocks:
            clean_url = _clean_ddg_url(href)
            clean_title = _strip_html(title_html)
            clean_snip = _strip_html(snip_html)
            if clean_url:
                items.append(SearchResultItem(title=clean_title, url=clean_url, snippet=clean_snip))
        if items:
            return items

    for block in blocks:
        url_match = re.search(r'<a[^>]*class="[^"]*(?:result__a|result__url|result__snippet)[^"]*"[^>]*href="([^"]+)"', block, re.IGNORECASE)
        if not url_match:
            url_match = re.search(r'href="([^"]+)"', block, re.IGNORECASE)

        title_match = re.search(r'<a[^>]*class="[^"]*result__a[^"]*"[^>]*>(.*?)</a>', block, re.IGNORECASE | re.DOTALL)
        snippet_match = re.search(r'<a[^>]*class="[^"]*result__snippet[^"]*"[^>]*>(.*?)</a>', block, re.IGNORECASE | re.DOTALL)
        if not snippet_match:
            snippet_match = re.search(r'<div[^>]*class="[^"]*result__snippet[^"]*"[^>]*>(.*?)</div>', block, re.IGNORECASE | re.DOTALL)

        if url_match:
            raw_url = url_match.group(1)
            clean_url = _clean_ddg_url(raw_url)
            clean_title = _strip_html(title_match.group(1)) if title_match else ""
            clean_snip = _strip_html(snippet_match.group(1)) if snippet_match else ""
            if clean_url:
                items.append(SearchResultItem(title=clean_title, url=clean_url, snippet=clean_snip))
    return items


def _clean_ddg_url(raw_url: str) -> str:
    """Extract destination URL from DuckDuckGo redirect link."""
    if "uddg=" in raw_url:
        m = re.search(r'uddg=([^&]+)', raw_url)
        if m:
            return urllib.parse.unquote(m.group(1))
    if raw_url.startswith("//"):
        return "https:" + raw_url
    if raw_url.startswith("/"):
        return "https://duckduckgo.com" + raw_url
    return raw_url


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


def execute_search_query(query: str, timeout: float = SEARCH_TIMEOUT) -> tuple[str, list[SearchResultItem], str]:
    """Execute a single search query.

    Returns:
        (status, list_of_items, error_detail)
    """
    search_url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
    req = urllib.request.Request(
        search_url,
        headers={
            "User-Agent": DEFAULT_USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            status_code = response.status
            if status_code == 200:
                body = response.read(150_000)
                raw_html = body.decode("utf-8", errors="replace")
                items = _extract_duckduckgo_results(raw_html)
                if items:
                    return ResourceStatus.FOUND, items, ""
                return ResourceStatus.NOT_FOUND, [], "Zero search results parsed"
            if status_code in (403, 429):
                return ResourceStatus.BLOCKED, [], f"Search blocked HTTP {status_code}"
            return ResourceStatus.CHECK_FAILED, [], f"Search HTTP {status_code}"
    except urllib.error.HTTPError as exc:
        if exc.code in (403, 429):
            return ResourceStatus.BLOCKED, [], f"Search blocked HTTP {exc.code}: {exc.reason}"
        return ResourceStatus.CHECK_FAILED, [], f"HTTP error {exc.code}: {exc.reason}"
    except Exception as exc:  # noqa: BLE001
        return ResourceStatus.CHECK_FAILED, [], f"{type(exc).__name__}: {str(exc)[:150]}"


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
