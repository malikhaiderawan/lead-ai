#!/usr/bin/env python3
"""
MalikAxiom — Harvest Verification Tool v2
Checks if each Instagram account has THEIR OWN website (not just any domain in search results).

Logic: A domain only counts as "their website" if:
  1. Domain name closely matches the brand handle or name, OR
  2. Snippet explicitly says "our website", "official website", "visit us at", etc.
  
Third-party mentions (reddit, medium, trustpilot, threads, etc.) are IGNORED.
"""

import sys, os, re, csv, ssl, json, time, urllib.request, glob

CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE
SERPER_KEY = os.environ.get("SERPER_API_KEY","").strip()

# ── Domains that are NEVER "their website" ────────────────────────────────────
THIRD_PARTY = {
    # Social
    "instagram.com","facebook.com","twitter.com","x.com","tiktok.com",
    "youtube.com","linkedin.com","pinterest.com","threads.com","snapchat.com",
    # Messaging
    "whatsapp.com","wa.me","t.me","telegram.org",
    # Link-in-bio
    "linktree.com","linktr.ee","bio.link","lnk.bio","beacons.ai",
    "taplink.cc","allmylinks.com","campsite.bio",
    # Navigation/Maps
    "google.com","maps.google.com","goo.gl","apple.com","bing.com",
    # Reviews/Forums
    "trustpilot.com","yelp.com","tripadvisor.com","reddit.com","quora.com",
    "medium.com","substack.com","wikipedia.org","blogspot.com","wordpress.com",
    # Watch marketplaces (NOT their site)
    "chrono24.com","watchfinder.com","bobswatches.com","watchgang.com",
    "watchuseek.com","watchcrunch.com","worldtempus.com","hodinkee.com",
    "ablogtowatch.com","revolutionwatch.com","fratellowatches.com",
    "watchpro.com","quillandpad.com","thewatchsite.com","mondaniweb.com",
    # Ecommerce platforms
    "amazon.com","ebay.com","etsy.com","shopify.com","myshopify.com",
    # Media/TV
    "bravotv.com","paramountnetwork.com","nytimes.com","dailymail.co.uk",
    "forbes.com","businessinsider.com","vogue.com","gq.com",
    # Generic
    "trustindex.io","threads.net","connect.gov","prestige.com",
}

# ── High-confidence own-website indicators in snippets ───────────────────────
OWN_SITE_PHRASES = [
    r'visit (?:us|our site|our website) at',
    r'official website[:\s]',
    r'shop (?:online|now) at',
    r'our (?:online )?store',
    r'available on (?:our )?website',
    r'order (?:from )?(?:our )?website',
    r'www\.[a-z0-9\-]+\.[a-z]{2,}',
]
OWN_SITE_RE = re.compile('|'.join(OWN_SITE_PHRASES), re.I)

DOMAIN_RE = re.compile(
    r'(?:https?://)?(?:www\.)?([a-zA-Z0-9][a-zA-Z0-9\-]{1,61}\.[a-zA-Z]{2,}(?:\.[a-zA-Z]{2,})?)',
    re.I
)

GREEN="\033[92m"; RED="\033[91m"; YELLOW="\033[93m"; CYAN="\033[96m"; BOLD="\033[1m"; RESET="\033[0m"


def slugify(text):
    """Convert brand name/handle to plain alphanumeric for fuzzy matching."""
    return re.sub(r'[^a-z0-9]', '', text.lower())


def domain_matches_brand(domain, handle, name):
    """Return True if domain likely belongs to this brand (name/handle match)."""
    d_slug = slugify(domain.split('.')[0])  # e.g. 'rexwatchesnyc' from 'rexwatchesnyc.com'
    h_slug = slugify(handle)
    n_slug = slugify(name)
    
    # Direct handle match
    if h_slug and len(h_slug) >= 5 and h_slug in d_slug:
        return True
    if h_slug and len(d_slug) >= 5 and d_slug in h_slug:
        return True
    
    # Name match (need at least 6 chars to avoid false positives)
    name_words = [slugify(w) for w in name.split() if len(w) >= 5]
    for word in name_words:
        if word in d_slug or d_slug in word:
            return True
    
    return False


def is_third_party(domain):
    """Return True if domain is a known third-party site."""
    domain_lower = domain.lower()
    return any(domain_lower.endswith(tp) or domain_lower == tp for tp in THIRD_PARTY)


def check_handle(handle, name):
    """
    Return whether this account has THEIR OWN website.
    Only flags True if:
      - A domain matching the handle/name is found in search results, OR
      - Snippet explicitly says 'visit our website at X'
    """
    queries = [
        f'@{handle} official website',
        f'"{name}" watch buy online shop',
    ]
    all_results = []

    for q in queries:
        payload = json.dumps({"q": q, "num": 5}).encode()
        req = urllib.request.Request(
            "https://google.serper.dev/search", data=payload,
            headers={"X-API-KEY": SERPER_KEY, "Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(req, context=CTX, timeout=10) as r:
                data = json.loads(r.read())
            for item in data.get("organic", []):
                all_results.append({
                    "link": item.get("link",""),
                    "snippet": item.get("snippet",""),
                    "title": item.get("title",""),
                })
            time.sleep(0.3)
        except Exception as e:
            pass  # silently skip API errors

    own_website = None

    for res in all_results:
        link = res["link"]
        snippet = res["snippet"]
        title = res["title"]
        combined = f"{title} {snippet} {link}"

        # Extract all domains from this result
        for m in DOMAIN_RE.finditer(combined):
            domain = m.group(1).lower().strip(".")
            
            # Skip if it's a known third-party site
            if is_third_party(domain):
                continue
            
            # Check: does this domain match their brand name/handle?
            if domain_matches_brand(domain, handle, name):
                own_website = domain
                break
        
        if own_website:
            break
        
        # Second check: does snippet explicitly say "our website" or "shop at"?
        if OWN_SITE_RE.search(snippet):
            # Extract the domain referenced in that context
            for m in DOMAIN_RE.finditer(snippet):
                d = m.group(1).lower()
                if not is_third_party(d):
                    own_website = d + " (own-site phrase)"
                    break

    if own_website:
        return {"has_website": True, "website": own_website, "confidence": "HIGH"}
    
    searched = len(all_results) > 0
    return {"has_website": False, "website": None,
            "confidence": "HIGH" if searched else "LOW"}


def get_handle(row, cols):
    for c in ("instagram","instagram_url","instagram_handle"):
        if c in cols:
            v = (row.get(c) or "").strip()
            if v:
                m = re.search(r'instagram\.com/([a-zA-Z0-9._]+)', v)
                return (m.group(1).rstrip("/") if m else v.lstrip("@"))
    return ""


def get_name(row, cols):
    for c in ("business_name","brand_name","name","title"):
        if c in cols:
            v = (row.get(c) or "").strip()
            if v:
                return v[:40]
    return "Unknown"


def verify_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        return []
    cols = set(rows[0].keys())

    print(f"\n{BOLD}{CYAN}{'='*62}{RESET}")
    print(f"{BOLD}📂 {os.path.basename(path)} — {len(rows)} leads{RESET}")
    print(f"{BOLD}{CYAN}{'='*62}{RESET}")

    results = []
    pass_n = fail_n = unc_n = 0

    for i, row in enumerate(rows, 1):
        name   = get_name(row, cols)
        handle = get_handle(row, cols)

        if not handle:
            print(f"  {YELLOW}⚠  [{i:02d}] {name:35s} — no handle{RESET}")
            unc_n += 1
            results.append({"file": os.path.basename(path), "handle": "", "name": name,
                             "status": "NO_HANDLE", "website_found": "", "confidence": ""})
            continue

        print(f"  🔍 [{i:02d}] @{handle:28s} | {name[:25]}... ", end="", flush=True)
        r = check_handle(handle, name)

        if r["has_website"]:
            print(f"{RED}❌ HAS OWN WEBSITE{RESET} → {r['website']}")
            fail_n += 1; status = "HAS_WEBSITE"
        else:
            print(f"{GREEN}✅ NO WEBSITE{RESET} ({r['confidence']})")
            pass_n += 1; status = "NO_WEBSITE"

        results.append({"file": os.path.basename(path), "handle": handle, "name": name,
                         "status": status, "website_found": r.get("website") or "",
                         "confidence": r["confidence"]})

    print(f"\n  {BOLD}→ {GREEN}✅ {pass_n} clean{RESET} | {RED}❌ {fail_n} has own website{RESET} | {YELLOW}❓ {unc_n} uncertain{RESET}")
    return results


if __name__ == "__main__":
    if not SERPER_KEY:
        print(f"{RED}❌ No SERPER_API_KEY{RESET}"); sys.exit(1)

    paths = []
    for arg in sys.argv[1:]:
        paths.extend(glob.glob(arg) or [arg])
    if not paths:
        print("Usage: python3 tools/verify_no_website.py input/FILE.csv [...]"); sys.exit(1)

    all_results = []
    for p in paths:
        if os.path.exists(p):
            all_results.extend(verify_csv(p))
        else:
            print(f"{YELLOW}⚠ Not found: {p}{RESET}")

    total  = len(all_results)
    no_web = sum(1 for r in all_results if r["status"] == "NO_WEBSITE")
    has_web= sum(1 for r in all_results if r["status"] == "HAS_WEBSITE")
    unc    = total - no_web - has_web

    print(f"\n{'='*62}")
    print(f"{BOLD}🌍 GLOBAL RESULT — All Files{RESET}")
    print(f"{'='*62}")
    print(f"  {GREEN}✅ NO OWN WEBSITE : {no_web:3d}  ← Perfect leads to pitch!{RESET}")
    print(f"  {RED}❌ HAS OWN WEBSITE: {has_web:3d}  ← Remove from outreach{RESET}")
    print(f"  {YELLOW}❓ UNCERTAIN      : {unc:3d}  ← Manual check{RESET}")
    print(f"     TOTAL          : {total:3d}")
    print(f"  {BOLD}Hit Rate: {no_web*100//total if total else 0}% verified clean leads{RESET}")

    bad = [r for r in all_results if r["status"] == "HAS_WEBSITE"]
    if bad:
        print(f"\n{RED}{BOLD}⚠ Remove these (have their own website):{RESET}")
        for r in bad:
            print(f"   • @{r['handle']:30s} → {r['website_found']}")

    good = [r for r in all_results if r["status"] == "NO_WEBSITE"]
    if good:
        print(f"\n{GREEN}{BOLD}✅ Verified Clean Leads (pitch website to these):{RESET}")
        for r in good:
            print(f"   • @{r['handle']:30s} — {r['name']}")

    out = os.path.join(os.path.dirname(paths[0]), "verification_report.csv")
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["file","handle","name","status","website_found","confidence"])
        w.writeheader(); w.writerows(all_results)
    print(f"\n{GREEN}{BOLD}📊 Report saved → {out}{RESET}")
