#!/usr/bin/env python3
"""
MalikAxiom Lead AI — Instagram Startup & D2C Bio Harvester v2.0
Finds Instagram-only businesses (Pret, Boutiques, Bakeries, Salons, Jewelry, etc.)
via Brave Search API (primary) or Google Custom Search API (fallback).

Setup:
  export BRAVE_API_KEY="your_key_from_api-dashboard.search.brave.com"
  # OR
  export GOOGLE_CSE_KEY="your_key"
  export GOOGLE_CSE_CX="your_cx_id"

Usage (standalone):
  python3 tools/instagram_harvester.py --city Lahore --category "pret wear" --limit 20
  python3 tools/instagram_harvester.py --city London --country UK --category "jewelry brand"
"""

import sys
import os
import re
import csv
import ssl
import json
import time
import argparse
import urllib.request
import urllib.parse
from html import unescape

CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.7",
}

# Standardized 22 columns matching malik-lead-ai input/schema.md
COLUMNS = [
    "business_name", "phone", "website_phones", "email", "website",
    "facebook", "instagram", "linkedin", "twitter", "whatsapp",
    "youtube", "tiktok", "address", "category", "rating", "reviews",
    "hours", "latitude", "longitude", "place_id", "cid", "google_maps_url"
]


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def clean_phone(text, country_code="PK"):
    """Extract Pakistani mobile or international phone from text."""
    # Matches +92 300 1234567, 0300-1234567, 923001234567, 0092 3xx
    pk_match = re.search(r'(?:(?:\+|00)?92|0)?\s*(3\d{2})[-\s]?(\d{7})\b', text)
    if pk_match and (country_code == "PK" or not country_code):
        return f"+92{pk_match.group(1)}{pk_match.group(2)}"
    
    # UK phone: +44 7xxx xxxxxx or 07xxx xxxxxx
    if country_code == "UK":
        uk_match = re.search(r'(?:(?:\+44|0044)\s?|0)(7\d{3}[-\s]?\d{6})\b', text)
        if uk_match:
            digits = re.sub(r'[^\d]', '', uk_match.group(1))
            return f"+44{digits}"

    # UAE phone: +971 5x xxx xxxx or 05x xxx xxxx
    if country_code == "AE":
        ae_match = re.search(r'(?:(?:\+971|00971)\s?|0)(5\d{1}[-\s]?\d{7})\b', text)
        if ae_match:
            digits = re.sub(r'[^\d]', '', ae_match.group(1))
            return f"+971{digits}"

    # Generic international fallback (+1, +44, +971, +92, etc.)
    gen_match = re.search(r'(?:\+|00)\d{1,4}[-\s]?\d{2,4}[-\s]?\d{4,8}', text)
    if gen_match:
        clean = re.sub(r'[^\d+]', '', gen_match.group(0))
        if len(clean) >= 10:
            return clean

    # Fallback to PK match if nothing else matched
    if pk_match:
        return f"+92{pk_match.group(1)}{pk_match.group(2)}"

    return ""


def clean_name_from_title(title):
    """Clean Instagram title like 'Noor Pret Studio (@noorpret) • Instagram photos and videos'"""
    title = unescape(title)
    title = re.sub(r'•\s*Instagram.*$', '', title, flags=re.I)
    title = re.sub(r'\(@[a-zA-Z0-9._]+\)', '', title)
    title = re.sub(r'Photo by .*? on .*?\.', '', title, flags=re.I)
    title = title.replace('| Instagram', '').replace('- Instagram', '')
    # Strip emojis and leading symbols
    title = re.sub(r'^[^\w]+', '', title)
    return title.strip() or "Instagram Brand"


def clean_handle(url):
    """Extract clean handle from Instagram URL if it's a direct profile."""
    match = re.search(r'instagram\.com/([a-zA-Z0-9._]+)', url)
    if match:
        handle = match.group(1).rstrip('/')
        if handle.lower() not in ('p', 'explore', 'stories', 'reel', 'reels', 'tv', 'direct', 'accounts', 'about'):
            return handle.lower()
    return ""


def extract_handle_from_text(text):
    """Extract handle mentioned in title or snippet e.g. (@brand) or @brand"""
    m = re.search(r'\(@([a-zA-Z0-9._]+)\)', text)
    if m:
        return m.group(1).lower()
    m = re.search(r'@([a-zA-Z0-9._]{3,30})', text)
    if m:
        h = m.group(1).lower()
        if h not in ('instagram', 'threads', 'facebook', 'gmail', 'yahoo', 'outlook'):
            return h
    return ""


# Social and messaging platforms that DO NOT count as having a website
# (Having a Facebook page, WhatsApp link, or Threads is NOT a website!)
_SOCIAL_PATTERNS = [
    r'(?:https?://)?(?:www\.)?instagram\.com[/\w._-]*',
    r'(?:https?://)?(?:www\.)?facebook\.com[/\w._-]*',
    r'(?:https?://)?(?:www\.)?fb\.com[/\w._-]*',
    r'(?:https?://)?(?:www\.)?fb\.me[/\w._-]*',
    r'(?:https?://)?(?:www\.)?wa\.me[/\w._-]*',
    r'(?:https?://)?(?:www\.)?api\.whatsapp\.com[/\w._-]*',
    r'(?:https?://)?(?:www\.)?whatsapp\.com[/\w._-]*',
    r'(?:https?://)?(?:www\.)?threads\.net[/\w._-]*',
    r'(?:https?://)?(?:www\.)?tiktok\.com[/\w._-]*',
    r'(?:https?://)?(?:www\.)?youtube\.com[/\w._-]*',
    r'(?:https?://)?(?:www\.)?youtu\.be[/\w._-]*',
    r'(?:https?://)?(?:www\.)?twitter\.com[/\w._-]*',
    r'(?:https?://)?(?:www\.)?x\.com[/\w._-]*',
]
_SOCIAL_RE = re.compile('|'.join(_SOCIAL_PATTERNS), re.I)

# Patterns that indicate a real independent website IS present in bio/snippet
_WEBSITE_PATTERNS = [
    r'https?://[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',             # http/https with actual domain
    r'www\.[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',                 # www.something.domain
    r'\b[a-zA-Z0-9.-]+\.(com|net|org|io|co|shop|store|pk|uk|ae|us|ca|de|fr)\b',  # domain extensions
]
_WEBSITE_RE = re.compile('|'.join(_WEBSITE_PATTERNS), re.I)


def has_website_in_bio(text: str) -> bool:
    """Return True if the text suggests the account already has an independent website.
    Pure social media links (Facebook, WhatsApp wa.me, Threads, TikTok) do NOT count as a website.
    """
    # Strip all social media and messaging links first
    cleaned = _SOCIAL_RE.sub('', text)
    return bool(_WEBSITE_RE.search(cleaned))


# Well-known official brand accounts — not our target leads
_BRAND_BLOCKLIST = {
    "rolex", "cartier", "omega", "patek", "patekphilippe", "audemarspiguet",
    "hublot", "breitling", "iwc", "tudor", "tagheuer", "longines",
    "panerai", "jaegerlecoultre", "vacheron", "blancpain", "seiko",
    "tissot", "swatch", "casio", "gshock", "fossil", "citizens",
    "popular",  # DDG junk
}

# Reject handles that look like snippet text (too long, or contain spaces after cleanup)
_MIN_HANDLE_LEN = 3
_MAX_HANDLE_LEN = 30


def _make_lead(url, title_raw, snippet_raw, country_code="PK"):
    """Build a lead dict from raw search result strings.
    
    Returns None if the URL is not a direct profile page (e.g. a post/reel URL
    where we cannot extract a reliable handle).
    """
    combined_raw = f"{title_raw} {snippet_raw}"

    # ── Only accept profile URLs, skip posts/reels/explore ───────────────
    handle = clean_handle(url)
    is_profile_url = bool(handle)  # clean_handle only returns value for profile URLs

    if not is_profile_url:
        # Fallback: try to get handle from title (@mention)
        handle = extract_handle_from_text(combined_raw)
        if not handle:
            # Cannot determine real handle — skip to avoid fake handles
            return None

    # ── Validate handle ───────────────────────────────────────────
    if handle in _BRAND_BLOCKLIST:
        return None
    if not (_MIN_HANDLE_LEN <= len(handle) <= _MAX_HANDLE_LEN):
        return None
    # Reject handles with digits only (likely post IDs)
    if re.match(r'^\d+$', handle):
        return None

    title = clean_name_from_title(re.sub(r'<[^>]+>', '', title_raw))
    snippet = unescape(re.sub(r'<[^>]+>', '', snippet_raw))
    phone = clean_phone(f"{title} {snippet}", country_code=country_code)

    return {
        "handle": handle,
        "name": title or handle,
        "url": f"https://www.instagram.com/{handle}/",
        "source_url": url,
        "snippet": snippet,
        "phone": phone,
        "has_website": has_website_in_bio(f"{title} {snippet}"),
    }


# ─────────────────────────────────────────────────────────────────────────────
# ENGINE 1: Brave Search API (recommended — free 2000/month)
# Get key: https://api-dashboard.search.brave.com/
# ─────────────────────────────────────────────────────────────────────────────

def search_brave(query, api_key, count=20):
    """Search using Brave Search API — returns clean list of lead dicts."""
    results = []
    url = "https://api.search.brave.com/res/v1/web/search"
    params = urllib.parse.urlencode({
        "q": query,
        "count": min(count, 20),
        "search_lang": "en",
        "country": "ALL",
        "result_filter": "web",
    })
    full_url = f"{url}?{params}"
    req = urllib.request.Request(full_url, headers={
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
        "X-Subscription-Token": api_key,
    })
    try:
        with urllib.request.urlopen(req, context=CTX, timeout=12) as resp:
            data = json.loads(resp.read())
        web_results = data.get("web", {}).get("results", [])
        for r in web_results:
            url_val = r.get("url", "")
            if "instagram.com/" not in url_val:
                continue
            lead = _make_lead(url_val, r.get("title", ""), r.get("description", ""))
            if lead:
                results.append(lead)
    except Exception as e:
        print(f"    [Brave] Error: {e}", file=sys.stderr)
    return results


# ─────────────────────────────────────────────────────────────────────────────
# ENGINE 2: Google Search via Serper.dev (2,500 free searches, 10s Google Login)
# URL: https://serper.dev
# ─────────────────────────────────────────────────────────────────────────────

def search_serper(query, api_key, count=20, country_code="PK"):
    """Search Google via Serper.dev API with pagination support."""
    results = []
    url = "https://google.serper.dev/search"
    num_per_page = 20
    pages_needed = max(1, (count + num_per_page - 1) // num_per_page)

    clean_query = query.replace('"', '').replace("'", "").strip()
    for page in range(1, pages_needed + 1):
        payload = json.dumps({"q": clean_query, "num": num_per_page, "page": page}).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=payload,
            headers={
                "X-API-KEY": api_key,
                "Content-Type": "application/json",
            }
        )
        try:
            with urllib.request.urlopen(req, context=CTX, timeout=12) as resp:
                data = json.loads(resp.read())
            organic = data.get("organic", [])
            for r in organic:
                url_val = r.get("link", "")
                if "instagram.com/" not in url_val:
                    continue
                lead = _make_lead(url_val, r.get("title", ""), r.get("snippet", ""), country_code=country_code)
                if lead:
                    results.append(lead)
            if len(organic) < 5 or len(results) >= count:
                break
            time.sleep(0.3)
        except Exception as e:
            print(f"    [Serper/Google] Error on page {page}: {e}", file=sys.stderr)
            break
    return results


# ─────────────────────────────────────────────────────────────────────────────
# ENGINE 3: Google Custom Search API (free 100/day)
# Setup: https://programmablesearchengine.google.com/
# ─────────────────────────────────────────────────────────────────────────────

def search_google_cse(query, api_key, cx, count=10):
    """Search via Google Custom Search JSON API."""
    results = []
    params = urllib.parse.urlencode({
        "key": api_key,
        "cx": cx,
        "q": query,
        "num": min(count, 10),
    })
    url = f"https://www.googleapis.com/customsearch/v1?{params}"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, context=CTX, timeout=12) as resp:
            data = json.loads(resp.read())
        for item in data.get("items", []):
            url_val = item.get("link", "")
            if "instagram.com/" not in url_val:
                continue
            snippet = item.get("snippet", "")
            lead = _make_lead(url_val, item.get("title", ""), snippet)
            if lead:
                results.append(lead)
    except Exception as e:
        print(f"    [Google CSE] Error: {e}", file=sys.stderr)
    return results


# ─────────────────────────────────────────────────────────────────────────────
# ENGINE 3: DuckDuckGo HTML (no-key fallback — may be blocked sometimes)
# ─────────────────────────────────────────────────────────────────────────────

def search_duckduckgo(query, max_pages=2):
    """DuckDuckGo HTML scrape — zero-key fallback (bot-detection prone)."""
    results = []
    seen_urls = set()

    for page in range(max_pages):
        data = urllib.parse.urlencode({"q": query, "s": page * 30}).encode("utf-8")
        req = urllib.request.Request(
            "https://html.duckduckgo.com/html/", data=data, headers=HEADERS
        )
        try:
            with urllib.request.urlopen(req, context=CTX, timeout=12) as resp:
                html = resp.read().decode("utf-8", errors="ignore")

            # Bot detection check
            if "anomaly.js" in html or "botnet" in html:
                print("    [DDG] Bot-detection triggered — skipping DDG.", file=sys.stderr)
                break

            # Primary regex
            matches = re.findall(
                r'<a class="result__url"[^>]*href="([^"]+)".*?<h2[^>]*>.*?<a[^>]*>(.*?)</a>.*?<a class="result__snippet[^>]*>(.*?)</a>',
                html, re.DOTALL
            )
            if not matches:
                # Fallback extraction
                hrefs = re.findall(r'href="(https?://[^"]*instagram\.com[^"]*)"', html)
                titles = re.findall(r'<a class="result__a"[^>]*>(.*?)</a>', html, re.DOTALL)
                snippets = re.findall(r'<a class="result__snippet[^>]*>(.*?)</a>', html, re.DOTALL)
                matches = [
                    (hrefs[i], titles[i] if i < len(titles) else "", snippets[i] if i < len(snippets) else "")
                    for i in range(len(hrefs))
                ]

            for raw_url, raw_title, raw_snippet in matches:
                parsed_url = raw_url
                if "uddg=" in raw_url:
                    ud = re.search(r'uddg=([^&]+)', raw_url)
                    if ud:
                        parsed_url = urllib.parse.unquote(ud.group(1))
                if "instagram.com/" not in parsed_url:
                    continue
                handle = clean_handle(parsed_url)
                if not handle or handle in seen_urls:
                    continue
                seen_urls.add(handle)
                lead = _make_lead(parsed_url, raw_title, raw_snippet)
                if lead:
                    results.append(lead)

            time.sleep(1.2)
        except Exception:
            break

    return results


# ─────────────────────────────────────────────────────────────────────────────
# ORCHESTRATOR
# ─────────────────────────────────────────────────────────────────────────────

def harvest_instagram_leads(
    city="Lahore",
    category="clothing brand",
    limit=20,
    output_file=None,
    country_label="Pakistan",
    country_code="PK",
    no_website=True,
):
    """
    Harvest Instagram startup leads for a given city & category.

    Args:
        no_website: If True (default), only collect accounts that do NOT appear
                    to have a website link in their bio / search snippet.
                    This is the core filter for selling website services.

    Engine priority:
      1. Google Search API (Serper.dev — 2,500 free queries)
      2. Brave Search API  (if BRAVE_API_KEY env set)
      3. Google CSE API    (if GOOGLE_CSE_KEY + GOOGLE_CSE_CX env set)
      4. DuckDuckGo HTML   (zero-key fallback)
    """
    brave_key = os.environ.get("BRAVE_API_KEY", "").strip() or os.environ.get("BRAVE_SEARCH_API_KEY", "").strip()
    serper_key = os.environ.get("SERPER_API_KEY", "").strip()
    google_key = os.environ.get("GOOGLE_CSE_KEY", "").strip()
    google_cx = os.environ.get("GOOGLE_CSE_CX", "").strip()

    print(f"\n🔍 Harvesting Instagram leads: '{category}' in {city}, {country_label}")
    if no_website:
        print("   🚫 Website filter ON  — skipping accounts that already have a website")

    # ── Query templates (generic + category-aware) ────────────────────────
    # Simple queries work best with Serper — avoid -site:, quotes, complex OR logic
    base_queries = [
        f'instagram.com {city} {category}',
        f'instagram {city} {category} DM to order',
        f'instagram {city} {category} WhatsApp order',
        f'instagram {city} {category} cash on delivery COD',
        f'instagram {city} {category} DM for price',
        f'instagram {city} {category} delivery all over Pakistan',
        f'{city} {category} instagram boutique shop',
        f'instagram {city} {category} reseller dealer',
        f'{city} {category} instagram buy sell',
        f'{city} {category} online store instagram order',
    ]

    # ── Watches-specific extra queries ───────────────────────────────────
    watches_terms = ["watch", "watches", "timepiece", "luxury watch", "watch reseller"]
    is_watches = any(t in category.lower() for t in watches_terms)
    if is_watches:
        base_queries += [
            f'instagram {city} watches DM WhatsApp order',
            f'instagram {city} watch collection buy sell',
            f'instagram {city} watches dealer available',
            f'instagram {city} watch store Shahalam market',
            f'{city} watch seller instagram delivery',
        ]
        print(f"   ⌚ Watches niche detected — added {5} watch-specific queries")

    # ── Category relevance keywords (to reject off-topic results) ────────
    # Build a set of keywords that MUST appear in handle OR name for watches
    _CATEGORY_KEYWORDS: list[str] = []
    if is_watches:
        _CATEGORY_KEYWORDS = [
            "watch", "watches", "timepiece", "horology", "rolex", "tudor",
            "omega", "patek", "ap ", "audemars", "cartier", "hublot",
            "breitling", "chronograph", "luxury", "lux", "diamond",
            "jewelry", "jewel", "jewellery", "gold", "silver", "gems",
        ]

    def _is_relevant(item: dict) -> bool:
        """Basic relevance check — reject if clearly off-topic."""
        if not _CATEGORY_KEYWORDS:
            return True
        combined = (item.get("handle", "") + " " + item.get("name", "") + " " + item.get("snippet", "")).lower()
        return any(kw in combined for kw in _CATEGORY_KEYWORDS)

    all_leads = []
    seen_handles = set()
    skipped_website = 0

    def _collect(items, source_label):
        nonlocal skipped_website
        added = 0
        for item in items:
            if item["handle"] in seen_handles or len(all_leads) >= limit:
                continue
            # ── Relevance filter ───────────────────────────────────────
            if not _is_relevant(item):
                print(f"  ✗ [{source_label}] SKIP (off-topic)    @{item['handle']} — {item['name'][:40]}")
                continue
            # ── No-website filter ──────────────────────────────────────
            if no_website and item.get("has_website", False):
                skipped_website += 1
                print(f"  ✗ [{source_label}] SKIP (has website)  @{item['handle']}")
                continue
            seen_handles.add(item["handle"])
            all_leads.append(item)
            added += 1
            website_flag = "🌐" if item.get("has_website") else "✅ NO-WEB"
            print(f"  ✓ [{source_label}] {item['name']} (@{item['handle']}) | ☎ {item['phone'] or '—'} | {website_flag}")
        return added

    # ── Engine 1: Serper.dev Google API (Primary, 2500 Free) ─────────────
    if serper_key and len(all_leads) < limit:
        print("  [Google / Serper] Searching real Google index...")
        for q in base_queries:
            if len(all_leads) >= limit:
                break
            items = search_serper(q, serper_key, count=20, country_code=country_code)
            _collect(items, "Google")
            time.sleep(0.4)

    # ── Engine 2: Brave Search API ────────────────────────────────────────
    if brave_key and len(all_leads) < limit:
        print("  [Brave API] Searching...")
        for q in base_queries[:4]:
            if len(all_leads) >= limit:
                break
            items = search_brave(q, brave_key, count=20)
            _collect(items, "Brave")
            time.sleep(0.5)

    # ── Engine 3: Google Custom Search API ───────────────────────────────
    if google_key and google_cx and len(all_leads) < limit:
        print("  [Google CSE] Searching...")
        for q in base_queries[:4]:
            if len(all_leads) >= limit:
                break
            items = search_google_cse(q, google_key, google_cx, count=10)
            _collect(items, "GCSE")
            time.sleep(0.8)

    # ── Engine 4: DuckDuckGo HTML (only if no API keys configured) ───────
    if len(all_leads) < limit and not (serper_key or brave_key or (google_key and google_cx)):
        print("  ⚠️  No API keys found — using DuckDuckGo (may be blocked).")
        for q in base_queries[:3]:
            if len(all_leads) >= limit:
                break
            items = search_duckduckgo(q, max_pages=2)
            _collect(items, "DDG")
            time.sleep(1.0)

    if no_website:
        print(f"\n  📊 Filter stats: {len(all_leads)} qualified (no-website) | {skipped_website} skipped (had website)")

    # ── Save CSV ─────────────────────────────────────────────────────────
    if not output_file:
        output_file = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "input", "instagram_leads.csv"
        )

    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    with open(output_file, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        for item in all_leads:
            row = {col: "" for col in COLUMNS}
            row["business_name"] = item["name"]
            row["phone"] = item["phone"]
            row["whatsapp"] = item["phone"]
            row["instagram"] = item["url"]
            row["category"] = category
            row["address"] = f"{city}, {country_label}"
            writer.writerow(row)

    print(f"\n✅ Harvested {len(all_leads)} leads → {output_file}")
    print(f"💡 Next: python3 main.py pipeline input/{os.path.basename(output_file)}\n")
    return len(all_leads), output_file


# ─────────────────────────────────────────────────────────────────────────────
# CLI (standalone usage)
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="MalikAxiom Instagram Lead Harvester",
        epilog="Set BRAVE_API_KEY env for reliable results. Free at api-dashboard.search.brave.com"
    )
    parser.add_argument("--city", default="Lahore", help="Target city")
    parser.add_argument("--country", default="PK", help="Country code (PK, UK, US, AE...)")
    parser.add_argument("--category", default="pret clothing", help="Business niche")
    parser.add_argument("--limit", type=int, default=20, help="Max leads to collect")
    parser.add_argument("--output", default=None, help="Output CSV path")

    args = parser.parse_args()

    _country_map = {
        "PK": "Pakistan", "UK": "United Kingdom", "US": "United States",
        "AE": "UAE", "CA": "Canada", "AU": "Australia", "IN": "India",
        "SA": "Saudi Arabia", "DE": "Germany", "FR": "France",
    }
    country_label = _country_map.get(args.country.upper(), args.country.upper())

    harvest_instagram_leads(
        city=args.city,
        category=args.category,
        limit=args.limit,
        output_file=args.output,
        country_label=country_label,
    )
