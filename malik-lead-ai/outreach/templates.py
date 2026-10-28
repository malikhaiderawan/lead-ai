"""Milestone 4 — Configurable Outreach Templates for MalikAxiom Lead AI.

Allows updating outreach message wording, tone, pricing, and parameters
without modifying core pipeline orchestration logic.
"""

from __future__ import annotations

import re
import urllib.parse
from typing import Any

# Master deployed demo storefront URL
MASTER_DEMO_BASE_URL = "https://website-demo-five-navy.vercel.app/"

# ---------------------------------------------------------------------------
# Configurable WhatsApp Message Templates for Boutique / Clothing Leads
# ---------------------------------------------------------------------------

# Tier 1 Opening: When Instagram presence is verified
TIER_1_OPENING = "Aapka Instagram dekha — collection kaafi classy hai 👌 Is liye {business_name} ke naam se ek live premium storefront demo specially prepare kiya hai 👇🔥"

# Tier 2 Opening: When website, Facebook, or online catalog is verified (no Instagram)
TIER_2_OPENING = "Aapka brand aur online presence dekhi — kaafi classy hai 👌 Is liye {business_name} ke naam se ek live premium storefront demo specially prepare kiya hai 👇🔥"

# Tier 3 Opening: Minimal evidence (no website, no social profile — directory / Google Maps listing only)
TIER_3_OPENING = "Aapka business dekha — {business_name} ke liye ek live premium storefront demo specially prepare kiya hai 👇🔥"

BOUTIQUE_WHATSAPP_TEMPLATE_BODY = """Assalam o Alaikum {business_name} Team! 🌸

Main Haider from MalikAxiom Technology Lahore.

{opening}

🔗 {demo_url}

🤖 24/7 AI Brand Assistant — aapke brand se related customers ke questions ka jawab de sakta hai, including products, prices, sizes, fabric, delivery & more.

🛒 Seamless WhatsApp Ordering — product, size & color select karke direct order.

🎨 12+ Premium Themes — Themes button se apne logo/brand color ke saath live matching try karein.

💰 Complete setup starting from PKR 10,000

✨ Yeh sirf ek sample demo hai — design, colors aur layout aapki brand identity ke mutabiq customize ho sakta hai. Hamare paas aur bhi luxury layouts available hain.

Aapko concept kaisa laga? Agar aap kahen to main aapke saath complete features & setup share kar doon. 🤝

MalikAxiom Technology
🌐 malikaxiomtech.com"""

BOUTIQUE_WHATSAPP_TEMPLATE_WITH_INSTAGRAM = BOUTIQUE_WHATSAPP_TEMPLATE_BODY.replace("{opening}", TIER_1_OPENING)
BOUTIQUE_WHATSAPP_TEMPLATE_WITH_WEBSITE = BOUTIQUE_WHATSAPP_TEMPLATE_BODY.replace("{opening}", TIER_2_OPENING)
BOUTIQUE_WHATSAPP_TEMPLATE_NEUTRAL = BOUTIQUE_WHATSAPP_TEMPLATE_BODY.replace("{opening}", TIER_3_OPENING)


# ---------------------------------------------------------------------------
# Brand Name & URL Encoding Helpers
# ---------------------------------------------------------------------------

def clean_brand_name(raw_name: str) -> str:
    """Clean awkward punctuation, tagline clauses, and duplicate words from business name."""
    if not raw_name:
        return "Brand"
    s = raw_name.strip().strip("\"'“”‘’")

    # Split on primary separators like | or • or -
    for sep in (" | ", " • ", " - ", " – "):
        if sep in s:
            s = s.split(sep)[0].strip()
    if "|" in s:
        s = s.split("|")[0].strip()

    # Remove trailing city suffixes like ' - Lahore', ' Lahore'
    s = re.sub(r"\s*[-–]\s*(Lahore|Karachi|Islamabad|Rawalpindi)\b", "", s, flags=re.IGNORECASE)

    # Remove adjacent duplicate words (e.g. 'Store Store')
    s = re.sub(r"\b(\w+)\s+\1\b", r"\1", s, flags=re.IGNORECASE)

    # Clean redundant punctuation at ends
    s = re.sub(r"\s+", " ", s).strip()
    s = s.rstrip(" -:,|.")
    return s or raw_name.strip()


def build_demo_url(
    business_name: str,
    base_url: str = MASTER_DEMO_BASE_URL,
) -> str:
    """Generate properly URL-encoded demo storefront URL.

    Format: https://website-demo-five-navy.vercel.app/?brand={URL_ENCODED_BRAND}&title={URL_ENCODED_TITLE}
    """
    clean_brand = clean_brand_name(business_name)
    brand_enc = urllib.parse.quote(clean_brand, safe="")
    title_raw = f"{clean_brand} | Online Store"
    title_enc = urllib.parse.quote(title_raw, safe="")

    clean_base = base_url.rstrip("/") + "/"
    return f"{clean_base}?brand={brand_enc}&title={title_enc}"


def render_boutique_whatsapp_message(
    business_name: str,
    has_instagram: bool = False,
    has_website_or_social: bool = False,
    base_url: str = MASTER_DEMO_BASE_URL,
    evidence_tier: int | None = None,
) -> str:
    """Render the primary WhatsApp boutique message using the configured template.

    Evidence tiers:
      - Tier 1: Verified Instagram presence (claims Instagram reviewed)
      - Tier 2: Verified website or Facebook presence (claims brand / online presence reviewed)
      - Tier 3: Minimal evidence / Maps listing only (claims business reviewed, no false claims)
    """
    clean_brand = clean_brand_name(business_name)
    demo_url = build_demo_url(clean_brand, base_url=base_url)

    if evidence_tier == 1 or (evidence_tier is None and has_instagram):
        template = BOUTIQUE_WHATSAPP_TEMPLATE_WITH_INSTAGRAM
    elif evidence_tier == 2 or (evidence_tier is None and has_website_or_social):
        template = BOUTIQUE_WHATSAPP_TEMPLATE_WITH_WEBSITE
    else:
        template = BOUTIQUE_WHATSAPP_TEMPLATE_NEUTRAL

    return template.format(
        business_name=clean_brand,
        demo_url=demo_url,
    )
