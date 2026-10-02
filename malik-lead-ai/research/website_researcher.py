"""Milestone 2 — Deep multi-page website researcher.

Performs deep, evidence-based investigation of business websites across:
- Homepage + internal subpages (About, Shop/Products, Services, Cart/Checkout, Contact, Pricing, FAQ)
- Commercial offering & product/service catalog extraction
- E-commerce order flow (Add-to-cart, Cart, Checkout, Payment methods, COD, Gateways, Store platform)
- Mobile responsiveness, technical health, and UX gap detection
- Comprehensive contact discovery (Phones, WhatsApp, Emails, Physical addresses, Social links)

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

WEBSITE_TIMEOUT = 12.0
SUBPAGE_TIMEOUT = 6.0
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)

# E-commerce keywords
ECOMMERCE_SIGNALS = (
    "cart", "checkout", "add to cart", "add-to-cart", "shop", "products",
    "product", "order", "payment", "buy", "category", "catalog", "price",
    "pay", "cod", "cash on delivery", "online store", "bag", "my cart",
)

WHATSAPP_SIGNALS = ("whatsapp", "wa.me", "api.whatsapp.com", "03", "+92")

# Payment method markers
_PAYMENT_PATTERNS = {
    "Cash on Delivery (COD)": ("cash on delivery", "cod available", "cash on delivery (cod)", "cod"),
    "JazzCash": ("jazzcash", "jazz cash"),
    "EasyPaisa": ("easypaisa", "easy paisa"),
    "Bank Transfer (IBFT)": ("bank transfer", "direct bank transfer", "ibft", "account title", "iban"),
    "Credit / Debit Card": ("credit card", "debit card", "visa", "mastercard", "unionpay"),
    "PayFast / Safepay": ("payfast", "safepay", "hbl pay", "alfa"),
    "Shopify Payments / Stripe": ("shopify payments", "stripe", "powered by stripe"),
    "PayPal": ("paypal",),
}

# Subpage classification patterns
_SUBPAGE_TYPES = {
    "about": (r'/about', r'/about-us', r'/who-we-are', r'/our-story', r'/company'),
    "shop": (r'/shop', r'/products', r'/collections', r'/store', r'/catalog', r'/category', r'/all-products', r'/items'),
    "services": (r'/services', r'/what-we-do', r'/treatments', r'/packages', r'/solutions', r'/menu'),
    "cart": (r'/cart', r'/bag', r'/my-cart', r'/basket'),
    "checkout": (r'/checkout', r'/order/checkout', r'/onepage', r'/pay'),
    "contact": (r'/contact', r'/contact-us', r'/reach-us', r'/get-in-touch', r'/location', r'/find-us'),
    "pricing": (r'/pricing', r'/rates', r'/fees', r'/plans', r'/price-list'),
    "faq_shipping": (r'/faq', r'/faqs', r'/shipping', r'/delivery', r'/payment-methods', r'/terms', r'/returns', r'/exchange', r'/policy'),
}


@dataclass
class PageFetchResult:
    url: str
    status_code: int
    content_type: str
    body_text: str
    html_raw: str
    error: str = ""


@dataclass
class WebsiteResearch:
    """Rich structured website research findings for one lead."""

    url: str | None
    status: str                         # exists | missing | unknown
    reachable: str                      # reachable | unreachable | unknown
    http_status: str | None = None
    apparent_type: str | None = None
    quality_observation: str = ""
    is_mobile_friendly: str = "unknown"
    ecommerce_presence: str = "unknown"
    product_catalog_presence: str = "unknown"
    checkout_order_capability: str = "unknown"
    whatsapp_contact_option: str = "unknown"
    contact_option_present: str = "unknown"
    obvious_broken_signals: list[str] = field(default_factory=list)
    observable_features: list[str] = field(default_factory=list)
    evidence: list[Evidence] = field(default_factory=list)
    raw_title: str | None = None
    content_length: int | None = None
    extracted_links: dict[str, str] = field(default_factory=dict)

    # Deep multi-page & commercial intelligence fields
    pages_checked: list[str] = field(default_factory=list)
    products_services_found: list[str] = field(default_factory=list)
    price_ranges_observed: list[str] = field(default_factory=list)
    detected_platform: str = "unknown"
    order_flow_type: str = "unknown"
    payment_methods_detected: list[str] = field(default_factory=list)
    cod_supported: str = "unknown"
    online_payment_supported: str = "unknown"
    technical_gaps: list[str] = field(default_factory=list)
    contacts_extracted: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "status": self.status,
            "reachable": self.reachable,
            "http_status": self.http_status,
            "apparent_type": self.apparent_type,
            "quality_observation": self.quality_observation,
            "is_mobile_friendly": self.is_mobile_friendly,
            "ecommerce_presence": self.ecommerce_presence,
            "product_catalog_presence": self.product_catalog_presence,
            "checkout_order_capability": self.checkout_order_capability,
            "whatsapp_contact_option": self.whatsapp_contact_option,
            "contact_option_present": self.contact_option_present,
            "obvious_broken_signals": self.obvious_broken_signals,
            "observable_features": self.observable_features,
            "raw_title": self.raw_title,
            "content_length": self.content_length,
            "extracted_links": self.extracted_links,
            "pages_checked": self.pages_checked,
            "products_services_found": self.products_services_found,
            "price_ranges_observed": self.price_ranges_observed,
            "detected_platform": self.detected_platform,
            "order_flow_type": self.order_flow_type,
            "payment_methods_detected": self.payment_methods_detected,
            "cod_supported": self.cod_supported,
            "online_payment_supported": self.online_payment_supported,
            "technical_gaps": self.technical_gaps,
            "contacts_extracted": self.contacts_extracted,
            "evidence": [e.to_dict() for e in self.evidence],
        }


def is_url_like(value: str) -> bool:
    if not value or not isinstance(value, str):
        return False
    parsed = urllib.parse.urlparse(value.strip())
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def normalize_url(value: str) -> str:
    value = (value or "").strip()
    if not value:
        return ""
    if not value.startswith(("http://", "https://")):
        value = "https://" + value
    try:
        parsed = urllib.parse.urlparse(value)
        scheme = parsed.scheme or "https"
        host = parsed.netloc or parsed.path
        path = parsed.path or "/"
        qs = ("?" + parsed.query) if parsed.query else ""
        return f"{scheme}://{host}{path}{qs}"
    except Exception:
        return ""


def _fetch_page(url: str, timeout: float = WEBSITE_TIMEOUT) -> PageFetchResult:
    """Fetch one URL and return raw HTML, text, and status."""
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": DEFAULT_USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            status_code = response.status
            ct = response.headers.get("Content-Type", "")
            raw_bytes = response.read(250_000)
            raw_html = raw_bytes.decode("utf-8", errors="replace")
            # Strip tags for text search
            clean_text = re.sub(r'<script[^>]*>.*?</script>', ' ', raw_html, flags=re.DOTALL | re.IGNORECASE)
            clean_text = re.sub(r'<style[^>]*>.*?</style>', ' ', clean_text, flags=re.DOTALL | re.IGNORECASE)
            clean_text = re.sub(r'<[^>]+>', ' ', clean_text)
            clean_text = html.unescape(clean_text)
            clean_text = re.sub(r'\s+', ' ', clean_text).strip()
            return PageFetchResult(
                url=url,
                status_code=status_code,
                content_type=ct,
                body_text=clean_text,
                html_raw=raw_html,
            )
    except urllib.error.HTTPError as exc:
        return PageFetchResult(url=url, status_code=exc.code, content_type="", body_text="", html_raw="", error=f"HTTP {exc.code} {exc.reason}")
    except Exception as exc:  # noqa: BLE001
        return PageFetchResult(url=url, status_code=0, content_type="", body_text="", html_raw="", error=f"{type(exc).__name__}: {str(exc)[:120]}")


def _discover_internal_links(base_url: str, html_content: str) -> dict[str, str]:
    """Discover high-value internal subpages (Shop, About, Services, Cart, Checkout, Contact)."""
    parsed_base = urllib.parse.urlparse(base_url)
    base_host = parsed_base.netloc.lower()

    discovered: dict[str, str] = {}
    hrefs = re.findall(r'href=["\']([^"\']+)["\']', html_content, re.IGNORECASE)

    for href in hrefs:
        href_clean = href.strip()
        if not href_clean or href_clean.startswith(("#", "javascript:", "mailto:", "tel:")):
            continue
        full_url = urllib.parse.urljoin(base_url, href_clean)
        parsed_full = urllib.parse.urlparse(full_url)
        if parsed_full.netloc.lower() != base_host:
            continue

        path_lower = parsed_full.path.lower()
        for ptype, patterns in _SUBPAGE_TYPES.items():
            if ptype not in discovered:
                if any(re.search(pat, path_lower) for pat in patterns):
                    discovered[ptype] = full_url

    return discovered


def _detect_platform(html_raw: str) -> str:
    """Identify underlying CMS or e-commerce platform."""
    lowered = html_raw.lower()
    if "cdn.shopify.com" in lowered or "shopify.theme" in lowered or "myshopify.com" in lowered:
        return "Shopify"
    if "wp-content" in lowered or "woocommerce" in lowered or "wp-json" in lowered:
        return "WooCommerce / WordPress"
    if "mage/" in lowered or "varien" in lowered or "magento" in lowered:
        return "Magento"
    if "wix.com" in lowered or "wixsite" in lowered:
        return "Wix"
    if "squarespace" in lowered:
        return "Squarespace"
    if "route=product" in lowered or "opencart" in lowered:
        return "OpenCart"
    if "prestashop" in lowered:
        return "PrestaShop"
    if "__next_data__" in lowered or "react" in lowered:
        return "Custom (React / Next.js)"
    return "Custom / Standard HTML"


def _extract_products_and_services(all_texts: list[str], html_raw: str) -> tuple[list[str], list[str]]:
    """Extract notable products, service headings, and observed price signals."""
    items: list[str] = []
    prices: list[str] = []

    # Headings extraction from HTML
    headings = re.findall(r'<h[1-4][^>]*>(.*?)</h[1-4]>', html_raw, re.IGNORECASE | re.DOTALL)
    for h in headings:
        clean_h = re.sub(r'<[^>]+>', '', h).strip()
        clean_h = html.unescape(clean_h)
        if 4 < len(clean_h) < 60 and not any(k in clean_h.lower() for k in ("menu", "search", "subscribe", "footer", "cart", "account", "login", "cookie")):
            if clean_h not in items:
                items.append(clean_h)

    # Price pattern extraction
    combined_text = " ".join(all_texts)
    price_matches = re.findall(r'(?:PKR|Rs\.?|₨|\$|£|EUR)\s?[\d,]+(?:\.\d{2})?', combined_text, re.IGNORECASE)
    for p in price_matches:
        p_clean = re.sub(r'\s+', ' ', p).strip()
        if p_clean not in prices:
            prices.append(p_clean)

    return items[:10], prices[:8]


def _extract_payment_methods(all_texts: list[str]) -> list[str]:
    combined = " ".join(all_texts).lower()
    methods: list[str] = []
    for name, patterns in _PAYMENT_PATTERNS.items():
        if any(p in combined for p in patterns):
            methods.append(name)
    return methods


def _extract_all_contacts(all_html: str, all_text: str) -> dict[str, Any]:
    """Extract phone numbers, WhatsApp, emails, and address snippets."""
    contacts: dict[str, Any] = {
        "phones": [],
        "whatsapp": [],
        "emails": [],
        "addresses": [],
    }

    # WhatsApp links
    wa_matches = re.findall(r'(?:wa\.me/|api\.whatsapp\.com/send\?phone=|whatsapp\.com/)([\d+]+)', all_html, re.IGNORECASE)
    for w in wa_matches:
        clean_w = w.strip().lstrip("+")
        if clean_w.startswith("92") and len(clean_w) == 12:
            formatted = f"+{clean_w}"
            if formatted not in contacts["whatsapp"]:
                contacts["whatsapp"].append(formatted)

    # Tel links
    tel_matches = re.findall(r'href=["\']tel:([^"\']+)["\']', all_html, re.IGNORECASE)
    for t in tel_matches:
        t_clean = re.sub(r'[\s\-()]', '', t).strip()
        if t_clean not in contacts["phones"]:
            contacts["phones"].append(t_clean)

    # Regex phones in text
    pk_phones = re.findall(r'(?:\+92|03\d{2})[\s\-]?\d{7}', all_text)
    for p in pk_phones:
        p_clean = re.sub(r'[\s\-]', '', p).strip()
        if p_clean not in contacts["phones"]:
            contacts["phones"].append(p_clean)

    # Emails
    mailto_matches = re.findall(r'href=["\']mailto:([^"?\']+)["\']', all_html, re.IGNORECASE)
    for m in mailto_matches:
        m_clean = m.strip().lower()
        if m_clean not in contacts["emails"]:
            contacts["emails"].append(m_clean)

    text_emails = re.findall(r'[\w.+-]+@[\w-]+\.[a-zA-Z]{2,}', all_text)
    for em in text_emails:
        em_clean = em.strip().lower()
        if em_clean not in contacts["emails"] and not em_clean.endswith((".png", ".jpg", ".webp", ".svg", ".css")):
            contacts["emails"].append(em_clean)

    return contacts


def research_website(url: str | None, timeout: float = WEBSITE_TIMEOUT) -> WebsiteResearch:
    """Deeply research a website with multi-page discovery and commercial extraction."""
    result = WebsiteResearch(url=url, status="unknown", reachable="unknown")

    if not url or not url.strip():
        result.status = "unknown"
        result.reachable = "unknown"
        result.evidence.append(
            Evidence(class_=EvidenceClass.UNKNOWN, statement="No website URL was provided for this lead.")
        )
        return result

    clean = normalize_url(url)
    if not clean:
        result.status = "unknown"
        result.reachable = "unknown"
        result.evidence.append(
            Evidence(class_=EvidenceClass.UNKNOWN, statement=f"The provided website URL did not look valid: {url!r}")
        )
        return result

    result.url = clean
    result.pages_checked.append(clean)

    # 1. Fetch Homepage
    main_page = _fetch_page(clean, timeout=timeout)
    if main_page.status_code == 0:
        result.reachable = "unreachable"
        result.status = "exists"
        result.evidence.append(
            Evidence(
                class_=EvidenceClass.UNKNOWN,
                statement=f"Website could not be accessed ({main_page.error}).",
                detail=main_page.error,
                source_url=clean,
            )
        )
        return result

    result.http_status = str(main_page.status_code)
    result.content_length = len(main_page.html_raw)

    if main_page.status_code >= 400:
        result.reachable = "unreachable" if main_page.status_code >= 500 else "reachable"
        result.status = "exists"
        is_blocked = main_page.status_code in (403, 429)
        result.evidence.append(
            Evidence(
                class_=EvidenceClass.VERIFIED_FACT if main_page.status_code in (401, 403, 404, 500, 502, 503) else EvidenceClass.UNKNOWN,
                statement=f"Website returned HTTP {main_page.status_code} ({main_page.error}).",
                detail=f"Access issue: {main_page.error}" if is_blocked else main_page.error,
                source_url=clean,
            )
        )
        return result

    result.status = "exists"
    result.reachable = "reachable"
    result.evidence.append(
        Evidence(
            class_=EvidenceClass.VERIFIED_FACT,
            statement=f"Website returned HTTP {main_page.status_code} ({main_page.content_type}).",
            detail=f"Bytes read: {result.content_length}",
            source_url=clean,
        )
    )

    # Extract title
    result.raw_title = _extract_title(main_page.html_raw)

    # 2. Discover and fetch high-value subpages (About, Shop, Services, Cart, Checkout, Contact)
    discovered_subpages = _discover_internal_links(clean, main_page.html_raw)
    subpage_results: list[PageFetchResult] = []

    # Explore up to 4 high-value subpages
    priority_order = ("shop", "checkout", "contact", "services", "about", "pricing")
    fetched_count = 0
    for ptype in priority_order:
        if ptype in discovered_subpages and fetched_count < 4:
            sub_url = discovered_subpages[ptype]
            if sub_url not in result.pages_checked:
                result.pages_checked.append(sub_url)
                sub_res = _fetch_page(sub_url, timeout=SUBPAGE_TIMEOUT)
                if sub_res.status_code == 200:
                    subpage_results.append(sub_res)
                    fetched_count += 1

    # Aggregate text and HTML across all explored pages
    all_pages = [main_page] + subpage_results
    all_texts = [p.body_text for p in all_pages]
    combined_lowered = " ".join([p.html_raw.lower() for p in all_pages])

    # 3. Detect Platform
    result.detected_platform = _detect_platform(main_page.html_raw)
    if result.detected_platform != "Custom / Standard HTML":
        result.evidence.append(
            Evidence(
                class_=EvidenceClass.VERIFIED_FACT,
                statement=f"Website technology detected: {result.detected_platform}.",
                source_url=clean,
            )
        )

    # 4. Extract Products, Services, and Price Ranges
    products, prices = _extract_products_and_services(all_texts, main_page.html_raw)
    result.products_services_found = products
    result.price_ranges_observed = prices

    if products:
        result.evidence.append(
            Evidence(
                class_=EvidenceClass.VERIFIED_FACT,
                statement=f"Detected commercial offerings: {', '.join(products[:5])}.",
                source_url=clean,
            )
        )
    if prices:
        result.evidence.append(
            Evidence(
                class_=EvidenceClass.VERIFIED_FACT,
                statement=f"Observed pricing signals on site: {', '.join(prices[:4])}.",
                source_url=clean,
            )
        )

    # 5. E-Commerce & Checkout Intelligence
    has_cart_kw = any(k in combined_lowered for k in ("cart", "add to cart", "add-to-cart", "my cart", "bag", "basket"))
    has_checkout_kw = any(k in combined_lowered for k in ("checkout", "place order", "proceed to checkout", "order now", "complete order"))
    has_shop_kw = any(k in combined_lowered for k in ("shop", "products", "catalog", "collections", "buy now"))
    has_wa_order = any(k in combined_lowered for k in ("order on whatsapp", "order via whatsapp", "whatsapp to order", "dm to order", "chat to buy")) or ("wa.me" in combined_lowered and (has_shop_kw or "shop" in discovered_subpages))

    result.ecommerce_presence = "present" if (has_shop_kw or has_cart_kw or "shop" in discovered_subpages) else "not_detected"
    result.product_catalog_presence = "present" if (has_shop_kw or "shop" in discovered_subpages) else "not_detected"
    result.checkout_order_capability = "present" if (has_checkout_kw or "checkout" in discovered_subpages) else "not_detected"

    # Payment methods
    result.payment_methods_detected = _extract_payment_methods(all_texts)
    result.cod_supported = "yes" if "Cash on Delivery (COD)" in result.payment_methods_detected else ("no" if result.checkout_order_capability == "present" else "unknown")
    result.online_payment_supported = "yes" if any(m != "Cash on Delivery (COD)" for m in result.payment_methods_detected) else ("no" if result.checkout_order_capability == "present" else "unknown")

    # Order flow type
    if result.checkout_order_capability == "present" and result.ecommerce_presence == "present":
        result.order_flow_type = "FULL_ECOMMERCE_CHECKOUT"
        result.evidence.append(
            Evidence(
                class_=EvidenceClass.VERIFIED_FACT,
                statement="Verified full e-commerce checkout flow on website.",
                detail=f"Payment methods: {', '.join(result.payment_methods_detected) if result.payment_methods_detected else 'Not explicitly stated'}",
                source_url=discovered_subpages.get("checkout", clean),
            )
        )
    elif (has_cart_kw or "cart" in discovered_subpages) and result.ecommerce_presence == "present" and result.checkout_order_capability != "present":
        result.order_flow_type = "CATALOG_WITH_CART_ONLY"
        result.evidence.append(
            Evidence(
                class_=EvidenceClass.REASONABLE_OBSERVATION,
                statement="Shopping cart detected but automated checkout page was not reachable.",
                source_url=discovered_subpages.get("cart", clean),
            )
        )
    elif has_wa_order and result.ecommerce_presence == "present":
        result.order_flow_type = "WHATSAPP_ORDERING"
        result.evidence.append(
            Evidence(
                class_=EvidenceClass.REASONABLE_OBSERVATION,
                statement="Products are browsed online but ordering is routed manually through WhatsApp.",
                source_url=clean,
            )
        )
    elif result.ecommerce_presence == "present":
        result.order_flow_type = "CATALOG_INQUIRY_ONLY"
    elif result.apparent_type == "likely_service_business_site":
        result.order_flow_type = "INFORMATIONAL_ONLY"
    else:
        result.order_flow_type = "NO_ORDER_FLOW"

    # 6. Mobile & Technical UX Gaps
    result.is_mobile_friendly = "yes" if "viewport" in combined_lowered else "unknown"
    if result.is_mobile_friendly != "yes":
        result.technical_gaps.append("Missing mobile viewport meta tag")

    if not clean.startswith("https://"):
        result.technical_gaps.append("Insecure HTTP connection (No SSL)")

    if result.ecommerce_presence == "present" and result.checkout_order_capability != "present":
        result.technical_gaps.append("Product catalog exists but lacks automated online checkout")

    if result.checkout_order_capability == "present" and not result.payment_methods_detected:
        result.technical_gaps.append("Checkout page does not clearly display accepted payment options")

    # Features and classifications
    result.observable_features = _observable_features(combined_lowered)
    result.apparent_type = _guess_type(combined_lowered, result.observable_features)
    result.quality_observation = _quality_note(combined_lowered, result.observable_features)
    result.whatsapp_contact_option = _presence_flag(combined_lowered, WHATSAPP_SIGNALS)
    result.contact_option_present = _contact_present_flag(combined_lowered)

    # 7. Extract Contacts and Social Links
    all_raw_html = " ".join([p.html_raw for p in all_pages])
    combined_body = " ".join(all_texts)
    result.extracted_links = _extract_links(all_raw_html)
    result.contacts_extracted = _extract_all_contacts(all_raw_html, combined_body)

    return result


def _extract_title(html_str: str) -> str | None:
    m = re.search(r'<title[^>]*>(.*?)</title>', html_str, flags=re.IGNORECASE | re.DOTALL)
    if not m:
        return None
    title = m.group(1).strip()
    title = html.unescape(title)
    return re.sub(r'\s+', ' ', title)[:200]


def _observable_features(lowered: str) -> list[str]:
    features: list[str] = []
    if "<form" in lowered:
        features.append("has_form")
    if 'name="email"' in lowered or 'type="email"' in lowered:
        features.append("has_email_field")
    if "map" in lowered and "google" in lowered:
        features.append("mentions_google_maps")
    if "instagram" in lowered:
        features.append("mentions_instagram")
    if "facebook" in lowered:
        features.append("mentions_facebook")
    if "whatsapp" in lowered or "wa.me" in lowered:
        features.append("mentions_whatsapp")
    if "tel:" in lowered:
        features.append("has_tel_link")
    if "og:" in lowered or "twitter:" in lowered:
        features.append("has_meta_tags")
    if "footer" in lowered:
        features.append("has_footer")
    if "contact" in lowered:
        features.append("mentions_contact")
    if "checkout" in lowered:
        features.append("has_checkout")
    if "cart" in lowered:
        features.append("has_cart")
    return features


def _guess_type(lowered: str, features: list[str]) -> str | None:
    if any(k in lowered for k in ("shop", "cart", "checkout", "products", "product", "buy", "payment")):
        return "likely_e_commerce_or_product_site"
    if "restaurant" in lowered or "cafe" in lowered or "menu" in lowered or "order online" in lowered:
        return "likely_food_or_service_business"
    if "blog" in lowered or "news" in lowered or "article" in lowered:
        return "likely_content_site"
    if "portfolio" in lowered or "work" in lowered or "services" in lowered or "clinic" in lowered:
        return "likely_service_business_site"
    return None


def _quality_note(lowered: str, features: list[str]) -> str:
    notes: list[str] = []
    if not features:
        notes.append("Page returned but no obvious structural signals were detected.")
    if "has_form" not in features and "mentions_contact" not in features:
        notes.append("No obvious contact form was detected.")
    if "viewport" not in lowered:
        notes.append("Viewport meta tag was not detected, so mobile-friendliness could not be confirmed.")
    if not notes:
        notes.append("Page structure is well-formed with active contact and content elements.")
    return " ".join(notes)


def _presence_flag(lowered: str, signals: tuple[str, ...]) -> str:
    for signal in signals:
        if signal in lowered:
            return "present"
    return "not_detected"


_CONTACT_SIGNALS: tuple[str, ...] = (
    "contact", "mailto:", "tel:", "call us", "get in touch",
    "reach us", "reach out", "email us", "contact us", "phone", "whatsapp", "wa.me",
)


def _contact_present_flag(lowered: str) -> str:
    return _presence_flag(lowered, _CONTACT_SIGNALS)


def _extract_links(html_raw: str) -> dict[str, str]:
    extracted: dict[str, str] = {}
    hrefs = re.findall(r'href=["\']([^"\']+)["\']', html_raw, re.IGNORECASE)
    _CDN_DOMAINS = ("cdninstagram.com", "fbcdn.net", "static.xx.fbcdn.net")

    for href in hrefs:
        h = href.strip()
        h_lower = h.lower()
        if any(cdn in h_lower for cdn in _CDN_DOMAINS):
            continue
        if "instagram.com/" in h_lower and "instagram" not in extracted:
            if not any(h_lower.endswith(ext) for ext in (".webp", ".png", ".jpg", ".jpeg", ".svg", ".gif")):
                extracted["instagram"] = h
        elif "facebook.com/" in h_lower and "facebook" not in extracted:
            if not any(h_lower.endswith(ext) for ext in (".webp", ".png", ".jpg", ".jpeg", ".svg", ".gif")):
                extracted["facebook"] = h
        elif "linkedin.com/" in h_lower and "linkedin" not in extracted:
            extracted["linkedin"] = h
        elif "tiktok.com/" in h_lower and "tiktok" not in extracted:
            extracted["tiktok"] = h
        elif ("youtube.com/" in h_lower or "youtu.be/" in h_lower) and "youtube" not in extracted:
            extracted["youtube"] = h
        elif ("wa.me/" in h_lower or "api.whatsapp.com/" in h_lower or "whatsapp.com/" in h_lower) and "whatsapp" not in extracted:
            extracted["whatsapp"] = h
        elif h_lower.startswith("mailto:") and "email" not in extracted:
            email_val = h[7:].split("?")[0].strip()
            if email_val:
                extracted["email"] = email_val
        elif h_lower.startswith("tel:") and "phone" not in extracted:
            phone_val = h[4:].strip()
            if phone_val:
                extracted["phone"] = phone_val
    return extracted


__all__ = ["WebsiteResearch", "PageFetchResult", "research_website", "normalize_url", "is_url_like"]
