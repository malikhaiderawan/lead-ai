"""Milestone 2 — Deep social presence researcher.

Performs evidence-based inspection of public social profiles (Instagram, Facebook,
TikTok, LinkedIn, YouTube) to extract:
- OpenGraph metadata, bio text, and business positioning
- Follower count & post count signals when publicly exposed
- Link-in-bio (Linktree, Taplink, Beacons, web store, wa.me links)
- Commercial order/booking CTAs (e.g. "DM for orders", "WhatsApp bookings", "Nationwide COD")
- Discovered contact phone numbers and website URLs
- Accurate 5-state status reporting (FOUND, NOT_FOUND, CHECK_FAILED, BLOCKED, UNKNOWN)

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

SOCIAL_TIMEOUT = 12.0
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)

PLATFORMS = ("instagram", "facebook", "tiktok", "linkedin", "youtube")


@dataclass
class SocialResearch:
    """Rich structured findings for one social media platform."""

    platform: str
    url: str | None
    status: str                         # present / missing / unknown (backward compatible)
    reachable: str                      # reachable / unreachable / unknown
    resource_status: str = ResourceStatus.UNKNOWN   # 5-state: FOUND | NOT_FOUND | CHECK_FAILED | BLOCKED | UNKNOWN
    http_status: str | None = None
    activity_signal: str = "unknown"
    appearance_signal: str = "unknown"
    obvious_business_activity: str = "unknown"

    # Deep social intelligence
    bio_text: str = ""
    public_metrics_snippet: str = ""
    link_in_bio: str | None = None
    whatsapp_cta: str | None = None
    commercial_signals: list[str] = field(default_factory=list)
    extracted_phones: list[str] = field(default_factory=list)
    extracted_website: str | None = None
    evidence: list[Evidence] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "platform": self.platform,
            "url": self.url,
            "status": self.status,
            "reachable": self.reachable,
            "resource_status": self.resource_status,
            "http_status": self.http_status,
            "activity_signal": self.activity_signal,
            "appearance_signal": self.appearance_signal,
            "obvious_business_activity": self.obvious_business_activity,
            "bio_text": self.bio_text,
            "public_metrics_snippet": self.public_metrics_snippet,
            "link_in_bio": self.link_in_bio,
            "whatsapp_cta": self.whatsapp_cta,
            "commercial_signals": self.commercial_signals,
            "extracted_phones": self.extracted_phones,
            "extracted_website": self.extracted_website,
            "evidence": [e.to_dict() for e in self.evidence],
        }


def _clean_url(value: str) -> str | None:
    """Normalize raw social URL or handle to clean absolute URL."""
    val = (value or "").strip()
    if not val:
        return None

    # Strip doubled scheme prefixes
    for scheme_pair in ("https://https://", "http://http://", "https://http://", "http://https://"):
        if val.lower().startswith(scheme_pair):
            val = val[len("https://"):]
            break

    # If it's a bare handle or partial path
    if not val.startswith(("http://", "https://")):
        val = "https://" + val.lstrip("@").lstrip("/")

    try:
        parsed = urllib.parse.urlparse(val)
        if not parsed.netloc:
            return None
        return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    except Exception:
        return None


def _extract_meta_content(html_str: str, property_name: str) -> str:
    pattern = rf'<meta[^>]*(?:property|name)=["\']{re.escape(property_name)}["\'][^>]*content=["\']([^"\']*)["\']'
    m = re.search(pattern, html_str, re.IGNORECASE)
    if not m:
        pattern_rev = rf'<meta[^>]*content=["\']([^"\']*)["\'][^>]*(?:property|name)=["\']{re.escape(property_name)}["\']'
        m = re.search(pattern_rev, html_str, re.IGNORECASE)
    if m:
        text = html.unescape(m.group(1).strip())
        return re.sub(r'\s+', ' ', text)
    return ""


def research_social(
    platform: str,
    url: str | None,
    timeout: float = SOCIAL_TIMEOUT,
) -> SocialResearch:
    """Deeply inspect a social profile URL for public business evidence."""
    result = SocialResearch(
        platform=platform,
        url=url,
        status="unknown",
        reachable="unknown",
        resource_status=ResourceStatus.UNKNOWN,
    )

    if not url or not url.strip():
        result.status = "missing"
        result.resource_status = ResourceStatus.UNKNOWN
        result.evidence.append(
            Evidence(class_=EvidenceClass.UNKNOWN, statement=f"No {platform} URL was provided.")
        )
        return result

    clean = _clean_url(url)
    if not clean:
        result.status = "unknown"
        result.resource_status = ResourceStatus.UNKNOWN
        result.evidence.append(
            Evidence(class_=EvidenceClass.UNKNOWN, statement=f"The provided {platform} URL did not look valid: {url!r}")
        )
        return result

    result.url = clean
    result.status = "present"

    req = urllib.request.Request(
        clean,
        headers={
            "User-Agent": DEFAULT_USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            status_code = response.status
            result.http_status = str(status_code)
            result.reachable = "reachable" if status_code < 500 else "unreachable"

            if status_code == 200:
                result.resource_status = ResourceStatus.FOUND
                result.activity_signal = "accessible"
                body = response.read(120_000)
                raw_html = body.decode("utf-8", errors="replace")

                # Extract OpenGraph / Meta Data
                og_title = _extract_meta_content(raw_html, "og:title")
                og_desc = _extract_meta_content(raw_html, "og:description")
                meta_desc = _extract_meta_content(raw_html, "description")

                desc = og_desc or meta_desc
                result.bio_text = desc

                # Look for follower metrics in description (e.g. "1,200 Followers, 50 Posts...")
                metrics_match = re.search(r'([\d.,KMkm+]+\s*(?:Followers|likes|subscribers|followers|posts))', desc, re.IGNORECASE)
                if metrics_match:
                    result.public_metrics_snippet = metrics_match.group(1).strip()

                # Commercial intent signals
                desc_lower = desc.lower()
                for signal in (
                    "dm for orders", "dm for details", "dm for prices", "worldwide shipping",
                    "nationwide delivery", "cash on delivery", "cod available", "whatsapp orders",
                    "custom orders", "bridal couture", "bespoke", "book appointment",
                ):
                    if signal in desc_lower:
                        result.commercial_signals.append(signal)

                if result.commercial_signals:
                    result.obvious_business_activity = "active_commercial_presence"

                # Extract Phone / WhatsApp numbers in bio
                phones = re.findall(r'(?:\+92|03\d{2})[\s\-]?\d{7}', desc)
                for p in phones:
                    p_clean = re.sub(r'[\s\-]', '', p)
                    if p_clean not in result.extracted_phones:
                        result.extracted_phones.append(p_clean)

                # Extract link-in-bio
                link_match = re.search(r'(https?://[^\s)]+)', desc)
                if link_match:
                    link_val = link_match.group(1).rstrip(".,)")
                    if not any(soc in link_val.lower() for soc in ("instagram.com", "facebook.com")):
                        result.link_in_bio = link_val
                        if "wa.me" in link_val or "api.whatsapp.com" in link_val:
                            result.whatsapp_cta = link_val
                        else:
                            result.extracted_website = link_val

                # Evidence creation
                evidence_stmt = f"{platform.capitalize()} profile confirmed accessible ({clean})."
                if result.public_metrics_snippet:
                    evidence_stmt += f" Observed metrics: {result.public_metrics_snippet}."
                if result.commercial_signals:
                    evidence_stmt += f" Commercial CTAs detected: {', '.join(result.commercial_signals)}."

                result.evidence.append(
                    Evidence(
                        class_=EvidenceClass.VERIFIED_FACT,
                        statement=evidence_stmt,
                        source_url=clean,
                    )
                )

            elif status_code in (403, 429):
                result.resource_status = ResourceStatus.BLOCKED
                result.activity_signal = "blocked_or_login_required"
                result.evidence.append(
                    Evidence(
                        class_=EvidenceClass.UNKNOWN,
                        statement=f"{platform.capitalize()} profile access blocked (HTTP {status_code}). Profile exists but requires authentication or is rate-limited.",
                        source_url=clean,
                    )
                )
            elif status_code == 404:
                result.resource_status = ResourceStatus.NOT_FOUND
                result.activity_signal = "not_found"
                result.evidence.append(
                    Evidence(
                        class_=EvidenceClass.VERIFIED_FACT,
                        statement=f"{platform.capitalize()} profile returned HTTP 404 (Page does not exist).",
                        source_url=clean,
                    )
                )
            else:
                result.resource_status = ResourceStatus.CHECK_FAILED
                result.evidence.append(
                    Evidence(
                        class_=EvidenceClass.UNKNOWN,
                        statement=f"{platform.capitalize()} check returned HTTP {status_code}.",
                        source_url=clean,
                    )
                )

    except urllib.error.HTTPError as exc:
        result.http_status = str(exc.code)
        if exc.code in (403, 429):
            result.resource_status = ResourceStatus.BLOCKED
            result.activity_signal = "blocked_or_login_required"
            result.reachable = "reachable"
            result.evidence.append(
                Evidence(
                    class_=EvidenceClass.UNKNOWN,
                    statement=f"{platform.capitalize()} profile exists but access was blocked (HTTP {exc.code}: {exc.reason}).",
                    source_url=clean,
                )
            )
        elif exc.code == 404:
            result.resource_status = ResourceStatus.NOT_FOUND
            result.activity_signal = "not_found"
            result.reachable = "unreachable"
            result.evidence.append(
                Evidence(
                    class_=EvidenceClass.VERIFIED_FACT,
                    statement=f"{platform.capitalize()} profile returned HTTP 404 (Not Found).",
                    source_url=clean,
                )
            )
        else:
            result.resource_status = ResourceStatus.CHECK_FAILED
            result.reachable = "unreachable"
            result.evidence.append(
                Evidence(
                    class_=EvidenceClass.UNKNOWN,
                    statement=f"{platform.capitalize()} check encountered HTTP {exc.code} ({exc.reason}).",
                    source_url=clean,
                )
            )
    except Exception as exc:  # noqa: BLE001
        result.resource_status = ResourceStatus.CHECK_FAILED
        result.reachable = "unreachable"
        result.evidence.append(
            Evidence(
                class_=EvidenceClass.UNKNOWN,
                statement=f"The {platform} page could not be reached ({type(exc).__name__}).",
                detail=str(exc)[:150],
                source_url=clean,
            )
        )

    return result


__all__ = ["SocialResearch", "research_social", "PLATFORMS"]
