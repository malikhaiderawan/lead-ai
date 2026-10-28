"""M7 — Personalized Boutique Demo Generator.

Generates deterministic, personalized URL links pointing to the deployed
master boutique demo (https://website-demo-five-navy.vercel.app/) using
a lead's business name and query parameters.

Isolated addition for M7:
- Zero database dependency.
- Does NOT import, copy, or modify the separate boutique demo project.
- Does NOT alter M1–M6 lead generation, qualification, outreach, or M6 send state.
- Does NOT automatically send any messages.
"""

from __future__ import annotations

import urllib.parse
from datetime import datetime, timezone
from typing import Any

MASTER_DEMO_BASE_URL = "https://website-demo-five-navy.vercel.app/"


def encode_uri_component(value: str) -> str:
    """Encode a string with exact parity to JavaScript's standard encodeURIComponent.

    Escapes all characters except: A-Z a-z 0-9 - _ . ! ~ * ' ( )
    """
    if not isinstance(value, str):
        value = str(value)
    return urllib.parse.quote(value, safe="-_.!~*'()")


def generate_personalized_demo_url(
    business_name: str,
    base_url: str = MASTER_DEMO_BASE_URL,
) -> str:
    """Generate a deterministic personalized demo URL for a given business name.

    Args:
        business_name: The raw business name string.
        base_url: The master deployed boutique demo base URL.

    Returns:
        The full, safely encoded URL with brand and title query parameters.

    Raises:
        ValueError: If business_name is missing, None, not a string, or whitespace only.
    """
    if business_name is None:
        raise ValueError("Missing business name: business_name cannot be None.")

    if not isinstance(business_name, str):
        raise ValueError(
            f"Invalid business name type: expected str, got {type(business_name).__name__}."
        )

    clean_name = business_name.strip()
    if not clean_name:
        raise ValueError("Empty business name: business_name cannot be empty or whitespace.")

    brand_encoded = encode_uri_component(clean_name)
    title_raw = f"{clean_name} | Online Store"
    title_encoded = encode_uri_component(title_raw)

    clean_base = base_url.rstrip("/") + "/"
    return f"{clean_base}?brand={brand_encoded}&title={title_encoded}"


def build_demo_whatsapp_message(
    business_name: str,
    demo_url: str,
    *,
    include_pricing: bool = True,
) -> str:
    """Construct the pre-composed WhatsApp outreach message containing the demo link."""
    clean_brand = business_name.strip() if business_name else "Brand"
    pricing_line = "💰 Complete setup starting from PKR 10,000\n\n" if include_pricing else ""
    return (
        f"Assalam o Alaikum {clean_brand} Team! 🌸\n\n"
        "Main Haider from MalikAxiom Technology Lahore.\n\n"
        f"Aapka Instagram dekha — collection kaafi classy hai 👌 Is liye {clean_brand} ke naam se ek live premium storefront demo specially prepare kiya hai 👇🔥\n\n"
        f"🔗 {demo_url}\n\n"
        "🤖 24/7 AI Brand Assistant — aapke brand se related customers ke har tarah ke questions ka jawab de sakta hai, including products, prices, sizes, fabric, delivery & more.\n\n"
        "🛒 Seamless WhatsApp Ordering — product, size & color select karke direct order.\n\n"
        "🎨 12+ Premium Themes — Themes button se apne logo/brand color ke saath live matching try karein.\n\n"
        f"{pricing_line}"
        "✨ Yeh sirf ek sample demo hai — design, colors aur layout aapki brand identity ke mutabiq fully customize ho sakta hai. Hamare paas aur bhi luxury layouts available hain.\n\n"
        "Aapko concept kaisa laga? Agar aap kahen to main aapke saath complete features & setup share kar doon. 🤝\n\n"
        "MalikAxiom Technology\n"
        "🌐 malikaxiomtech.com"
    )


def generate_demo_package(
    lead_id: str | None = None,
    business_name: str | None = None,
    phone: str | None = None,
    base_url: str = MASTER_DEMO_BASE_URL,
) -> dict[str, Any]:
    """Generate a complete M7 Demo package containing the URL and prepared drafts.

    Args:
        lead_id: Optional identifier of the lead.
        business_name: The business name to personalize for.
        phone: Optional recipient phone for drafting wa.me links.
        base_url: The master demo base URL.

    Returns:
        Dictionary containing demo_url, brand, title, whatsapp_message, etc.
    """
    if not business_name or not isinstance(business_name, str) or not business_name.strip():
        raise ValueError("A valid non-empty business name is required to generate demo package.")

    clean_name = business_name.strip()
    demo_url = generate_personalized_demo_url(clean_name, base_url=base_url)
    brand_param = encode_uri_component(clean_name)
    title_param = encode_uri_component(f"{clean_name} | Online Store")
    wa_message = build_demo_whatsapp_message(clean_name, demo_url)

    clean_phone = ""
    wa_direct_link = ""
    if phone:
        digits_only = "".join(ch for ch in str(phone) if ch.isdigit())
        if digits_only:
            clean_phone = digits_only
            wa_direct_link = f"https://wa.me/{clean_phone}?text={urllib.parse.quote(wa_message)}"

    return {
        "status": "OK",
        "lead_id": lead_id or "",
        "business_name": clean_name,
        "brand_param": brand_param,
        "title_param": title_param,
        "base_url": base_url,
        "demo_url": demo_url,
        "whatsapp_message": wa_message,
        "recipient_phone": clean_phone,
        "whatsapp_direct_link": wa_direct_link,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "is_deterministic": True,
    }
