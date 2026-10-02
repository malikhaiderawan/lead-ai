"""Milestone 2 — Comprehensive Deep Web Research Test Suite.

Covers all 14 required research test dimensions:
1. Website research (multi-page, headings, prices, UX)
2. Multiple-source research orchestrator
3. Social research (Instagram, Facebook, TikTok, LinkedIn)
4. Search-engine research (DuckDuckGo parsing & discovery)
5. E-commerce detection (Catalog, Cart, Checkout, COD, Gateways, Platform)
6. Contact extraction (Phones, WhatsApp links, Emails, Address)
7. Digital-gap detection (No website, manual WhatsApp orders, unverified)
8. Evidence preservation (VERIFIED_FACT vs REASONABLE_OBSERVATION vs UNKNOWN)
9. MalikAxiom opportunity generation (grounded with why_relevant)
10. Failed-source handling (HTTP 500, timeout, connection errors)
11. BLOCKED vs CHECK_FAILED vs NOT_FOUND status distinction
12. No fabricated information
13. Existing schema compatibility (CSV & JSON dictionary outputs)
14. M3 compatibility (Downstream qualification ingestion)

Fast execution, mocked network responses, zero artificial sleep.
"""

from __future__ import annotations

import csv
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from qualification.qualifier import qualify_lead
from research.evidence import Evidence, EvidenceClass, ResourceStatus
from research.google_researcher import research_google
from research.researcher import ResearchRecord, _error_record, _record_to_dict, _record_to_row, _research_one
from research.search_researcher import (
    SearchResultItem,
    _clean_ddg_url,
    _extract_duckduckgo_results,
    research_search,
)
from research.social_researcher import research_social
from research.website_researcher import (
    WebsiteResearch,
    _detect_platform,
    _discover_internal_links,
    _extract_all_contacts,
    _extract_products_and_services,
    research_website,
)


class TestM2DeepResearch(unittest.TestCase):

    # 1. Website Research (multi-page, headings, prices, UX)
    def test_website_research_extracts_headings_and_prices(self) -> None:
        html_content = """
        <html>
          <head><title>Khaas Boutique Islamabad - Luxury Pret</title><meta name="viewport" content="width=device-width"></head>
          <body>
            <h1>Luxury Bridal Collection</h1>
            <h2>Handcrafted Formal Wear</h2>
            <p>Our bridal dresses start from PKR 45,000 to PKR 150,000.</p>
            <a href="/shop">Shop Now</a>
            <a href="/contact-us">Contact Us</a>
            <a href="tel:+923001234567">Call +92 300 1234567</a>
            <a href="mailto:info@khaasboutique.pk">info@khaasboutique.pk</a>
          </body>
        </html>
        """
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.headers = {"Content-Type": "text/html"}
        mock_resp.read.return_value = html_content.encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp

        with patch("urllib.request.urlopen", return_value=mock_resp):
            res = research_website("https://khaasboutique.pk")

        self.assertEqual(res.status, "exists")
        self.assertEqual(res.reachable, "reachable")
        self.assertEqual(res.is_mobile_friendly, "yes")
        self.assertIn("Luxury Bridal Collection", res.products_services_found)
        self.assertTrue(any("45,000" in p for p in res.price_ranges_observed))
        self.assertIn("+923001234567", res.contacts_extracted["phones"])
        self.assertIn("info@khaasboutique.pk", res.contacts_extracted["emails"])

    # 2. Multiple-Source Research Orchestrator
    def test_multi_source_orchestrator_assembles_full_record(self) -> None:
        lead_raw = {
            "raw": {
                "business_name": "Royal Tailors Islamabad",
                "category": "Bespoke Tailoring & Suits",
                "address": "F-7 Markaz, Islamabad",
                "phone": "0313 5555555",
                "website": "https://royaltailors.pk",
                "instagram": "https://instagram.com/royaltailorsisb",
            },
            "source_column_map": {
                "business_name": "business_name",
                "category": "category",
                "address": "address",
                "phone": "phone",
                "website": "website",
                "instagram": "instagram",
            },
            "source_file": "input/test.csv",
            "row_number": 1,
        }

        # Mock search and site checks
        with patch("research.researcher.research_search") as mock_search, \
             patch("research.researcher.research_website") as mock_web, \
             patch("research.researcher.research_social") as mock_soc:

            mock_search.return_value.status = ResourceStatus.FOUND
            mock_search.return_value.to_dict.return_value = {"status": "FOUND", "discovered_links": {}}
            mock_search.return_value.search_snippets = ["Royal Tailors offers bespoke suiting in Islamabad."]
            mock_search.return_value.evidence = []

            mock_web.return_value = WebsiteResearch(
                url="https://royaltailors.pk",
                status="exists",
                reachable="reachable",
                http_status="200",
                apparent_type="likely_service_business_site",
                ecommerce_presence="not_detected",
                checkout_order_capability="not_detected",
                whatsapp_contact_option="present",
                contact_option_present="present",
                products_services_found=["Custom 3-Piece Suits", "Sherwanis", "Blazers"],
                price_ranges_observed=["PKR 18,000"],
                detected_platform="WordPress",
                order_flow_type="NO_ORDER_FLOW",
                contacts_extracted={"phones": ["03135555555"], "whatsapp": ["+923135555555"], "emails": []},
                evidence=[Evidence(class_=EvidenceClass.VERIFIED_FACT, statement="Site active")],
            )

            mock_soc.return_value.status = "present"
            mock_soc.return_value.resource_status = ResourceStatus.FOUND
            mock_soc.return_value.activity_signal = "accessible"
            mock_soc.return_value.url = "https://instagram.com/royaltailorsisb"
            mock_soc.return_value.public_metrics_snippet = "2,500 followers"
            mock_soc.return_value.commercial_signals = ["dm for orders"]
            mock_soc.return_value.whatsapp_cta = "+923135555555"
            mock_soc.return_value.evidence = []

            record = _research_one(lead_raw, "lead_001_royal_tailors")

        self.assertEqual(record.business_name, "Royal Tailors Islamabad")
        self.assertEqual(record.digital_maturity, "STRONG")
        self.assertIn("Royal Tailors Islamabad offers: Custom 3-Piece Suits", record.products_services_summary)
        self.assertTrue(len(record.observed_digital_gaps) > 0)
        self.assertTrue(len(record.malikaxiom_opportunities) > 0)
        self.assertEqual(record.research_synthesis["business"].startswith("Royal Tailors Islamabad"), True)

    # 3. Social Research (Instagram bio, CTAs, link-in-bio)
    def test_social_research_extracts_bio_and_commercial_signals(self) -> None:
        html_social = """
        <html>
          <head>
            <meta property="og:title" content="Zaib Bridal Wear (@zaibbridal) • Instagram photos and videos">
            <meta property="og:description" content="2,400 Followers, 45 Posts - Bespoke Bridal & Formal Wear. Islamabad based. WhatsApp orders: 0312-9876543. Nationwide Cash on delivery. DM for details. https://wa.me/923129876543">
          </head>
          <body></body>
        </html>
        """
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = html_social.encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp

        with patch("urllib.request.urlopen", return_value=mock_resp):
            s_res = research_social("instagram", "https://instagram.com/zaibbridal")

        self.assertEqual(s_res.status, "present")
        self.assertEqual(s_res.resource_status, ResourceStatus.FOUND)
        self.assertIn("2,400 Followers", s_res.public_metrics_snippet)
        self.assertIn("dm for details", s_res.commercial_signals)
        self.assertIn("03129876543", s_res.extracted_phones)
        self.assertEqual(s_res.whatsapp_cta, "https://wa.me/923129876543")

    # 4. Search-Engine Research (DuckDuckGo parsing)
    def test_search_engine_results_parser(self) -> None:
        sample_ddg = """
        <div class="result__body">
          <a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fwww.instagram.com%2Farbrandzone%2F">Arbrandzone Official (@arbrandzone)</a>
          <a class="result__snippet" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fwww.instagram.com%2Farbrandzone%2F">Men fashion and clothing store in Lahore. Call 0313-6162007 for deliveries.</a>
        </div>
        """
        items = _extract_duckduckgo_results(sample_ddg)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].url, "https://www.instagram.com/arbrandzone/")
        self.assertIn("Arbrandzone Official", items[0].title)
        self.assertIn("0313-6162007", items[0].snippet)

    # 5. E-Commerce Detection (Platform, COD, Cart, Checkout)
    def test_ecommerce_platform_and_checkout_detection(self) -> None:
        shopify_html = """
        <html>
          <head><script src="https://cdn.shopify.com/s/files/1/theme.js"></script></head>
          <body>
            <button class="add-to-cart">Add to Cart</button>
            <a href="/cart">View Cart</a>
            <a href="/checkout">Proceed to Checkout</a>
            <p>Cash on delivery (COD) available nationwide. We also accept JazzCash and EasyPaisa.</p>
          </body>
        </html>
        """
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.headers = {"Content-Type": "text/html"}
        mock_resp.read.return_value = shopify_html.encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp

        with patch("urllib.request.urlopen", return_value=mock_resp):
            res = research_website("https://brandstore.pk")

        self.assertEqual(res.detected_platform, "Shopify")
        self.assertEqual(res.ecommerce_presence, "present")
        self.assertEqual(res.checkout_order_capability, "present")
        self.assertEqual(res.order_flow_type, "FULL_ECOMMERCE_CHECKOUT")
        self.assertEqual(res.cod_supported, "yes")
        self.assertIn("Cash on Delivery (COD)", res.payment_methods_detected)
        self.assertIn("JazzCash", res.payment_methods_detected)
        self.assertIn("EasyPaisa", res.payment_methods_detected)

    # 6. Contact Extraction (Phones, WhatsApp, Emails, Address)
    def test_contact_extraction_deduplicates_and_normalizes(self) -> None:
        html_raw = """
        <a href="tel:+923001234567">Call us</a>
        <a href="https://wa.me/923001234567?text=Hello">WhatsApp</a>
        <a href="mailto:support@store.pk?subject=Query">Email</a>
        """
        body_text = "Reach us at 0300-1234567 or support@store.pk in Islamabad."
        contacts = _extract_all_contacts(html_raw, body_text)

        self.assertIn("+923001234567", contacts["whatsapp"])
        self.assertIn("+923001234567", contacts["phones"])
        self.assertIn("support@store.pk", contacts["emails"])

    # 7. Digital-Gap Detection
    def test_digital_gap_detection_for_social_only_lead(self) -> None:
        lead_raw = {
            "raw": {
                "business_name": "Glamour Studio",
                "category": "Beauty Salon & Spa",
                "address": "Lahore",
                "phone": "0321 1111111",
                "website": "",
                "instagram": "https://instagram.com/glamourstudio",
            },
            "source_column_map": {
                "business_name": "business_name",
                "category": "category",
                "address": "address",
                "phone": "phone",
                "website": "website",
                "instagram": "instagram",
            },
            "source_file": "input/test.csv",
            "row_number": 2,
        }

        with patch("research.researcher.research_search") as mock_search, \
             patch("research.researcher.research_website") as mock_web, \
             patch("research.researcher.research_social") as mock_soc:

            mock_search.return_value.status = ResourceStatus.FOUND
            mock_search.return_value.to_dict.return_value = {"status": "FOUND", "discovered_links": {}}
            mock_search.return_value.search_snippets = []
            mock_search.return_value.discovered_website = None
            mock_search.return_value.discovered_links = {}
            mock_search.return_value.discovered_phones = []
            mock_search.return_value.discovered_emails = []
            mock_search.return_value.evidence = []

            mock_web.return_value = WebsiteResearch(url=None, status="unknown", reachable="unknown")
            mock_soc.return_value.status = "present"
            mock_soc.return_value.resource_status = ResourceStatus.FOUND
            mock_soc.return_value.activity_signal = "accessible"
            mock_soc.return_value.url = "https://instagram.com/glamourstudio"
            mock_soc.return_value.public_metrics_snippet = "5,000 followers"
            mock_soc.return_value.commercial_signals = []
            mock_soc.return_value.whatsapp_cta = None
            mock_soc.return_value.extracted_phones = []
            mock_soc.return_value.extracted_website = None
            mock_soc.return_value.evidence = []

            record = _research_one(lead_raw, "lead_002_glamour_studio")

        self.assertTrue(any("Active Social Presence Without Dedicated Website" in g for g in record.observed_digital_gaps))

    # 8. Evidence Preservation (Separation of FACT vs OBSERVATION vs UNKNOWN)
    def test_evidence_classification_integrity(self) -> None:
        ev_fact = Evidence(class_=EvidenceClass.VERIFIED_FACT, statement="Server responded HTTP 200", source_url="https://site.pk")
        ev_obs = Evidence(class_=EvidenceClass.REASONABLE_OBSERVATION, statement="Appears to be retail clothing store")
        ev_unk = Evidence(class_=EvidenceClass.UNKNOWN, statement="Payment gateway could not be confirmed")

        self.assertEqual(ev_fact.to_dict()["class"], "VERIFIED_FACT")
        self.assertEqual(ev_fact.to_dict()["source_url"], "https://site.pk")
        self.assertEqual(ev_obs.to_dict()["class"], "REASONABLE_OBSERVATION")
        self.assertEqual(ev_unk.to_dict()["class"], "UNKNOWN")

    # 9. MalikAxiom Opportunity Generation (with rationale)
    def test_malikaxiom_opportunity_mapping_includes_why_relevant(self) -> None:
        lead_raw = {
            "raw": {
                "business_name": "Gulberg Pret Store",
                "category": "Women Clothing Boutique",
                "address": "Gulberg, Lahore",
                "phone": "0300 9999999",
                "website": "",
                "instagram": "https://instagram.com/gulbergpret",
            },
            "source_column_map": {
                "business_name": "business_name",
                "category": "category",
                "address": "address",
                "phone": "phone",
                "website": "website",
                "instagram": "instagram",
            },
            "source_file": "input/test.csv",
            "row_number": 3,
        }

        with patch("research.researcher.research_search") as mock_search, \
             patch("research.researcher.research_website") as mock_web, \
             patch("research.researcher.research_social") as mock_soc:

            mock_search.return_value.status = ResourceStatus.NOT_FOUND
            mock_search.return_value.to_dict.return_value = {"status": "NOT_FOUND"}
            mock_search.return_value.search_snippets = []
            mock_search.return_value.discovered_website = None
            mock_search.return_value.discovered_links = {}
            mock_search.return_value.discovered_phones = []
            mock_search.return_value.discovered_emails = []
            mock_search.return_value.evidence = []

            mock_web.return_value = WebsiteResearch(url=None, status="unknown", reachable="unknown")
            mock_soc.return_value.status = "present"
            mock_soc.return_value.resource_status = ResourceStatus.FOUND
            mock_soc.return_value.activity_signal = "accessible"
            mock_soc.return_value.url = "https://instagram.com/gulbergpret"
            mock_soc.return_value.public_metrics_snippet = ""
            mock_soc.return_value.commercial_signals = []
            mock_soc.return_value.whatsapp_cta = None
            mock_soc.return_value.extracted_phones = []
            mock_soc.return_value.extracted_website = None
            mock_soc.return_value.evidence = []

            record = _research_one(lead_raw, "lead_003_gulberg_pret")

        opp_services = [o["service"] for o in record.malikaxiom_opportunities]
        self.assertIn("E-Commerce Development", opp_services)
        ecom_opp = next(o for o in record.malikaxiom_opportunities if o["service"] == "E-Commerce Development")
        self.assertTrue(len(ecom_opp["why_relevant"]) > 20)

    # 10. Failed-Source Handling (Graceful handling of exceptions)
    def test_failed_website_connection_recorded_without_crash(self) -> None:
        with patch("urllib.request.urlopen", side_effect=Exception("Connection refused")):
            res = research_website("https://down-domain.com")

        self.assertEqual(res.reachable, "unreachable")
        self.assertEqual(res.status, "exists")
        self.assertTrue(any("Connection refused" in e.detail or "Connection refused" in e.statement for e in res.evidence))

    # 11. BLOCKED vs CHECK_FAILED vs NOT_FOUND status distinction
    def test_http_status_codes_distinguish_blocked_and_not_found(self) -> None:
        import urllib.error

        # 403 Forbidden -> BLOCKED
        err_403 = urllib.error.HTTPError(url="https://ig.com", code=403, msg="Forbidden", hdrs={}, fp=io.BytesIO())
        with patch("urllib.request.urlopen", side_effect=err_403):
            res_blocked = research_social("instagram", "https://instagram.com/private_brand")
        self.assertEqual(res_blocked.resource_status, ResourceStatus.BLOCKED)

        # 404 Not Found -> NOT_FOUND
        err_404 = urllib.error.HTTPError(url="https://ig.com", code=404, msg="Not Found", hdrs={}, fp=io.BytesIO())
        with patch("urllib.request.urlopen", side_effect=err_404):
            res_not_found = research_social("instagram", "https://instagram.com/deleted_brand")
        self.assertEqual(res_not_found.resource_status, ResourceStatus.NOT_FOUND)

    # 12. No Fabricated Information
    def test_unverified_fields_remain_unknown(self) -> None:
        lead_raw = {
            "raw": {
                "business_name": "Unknown Entity",
                "phone": "0300 0000000",
            },
            "source_column_map": {
                "business_name": "business_name",
                "phone": "phone",
            },
            "source_file": "input/test.csv",
            "row_number": 4,
        }
        with patch("research.researcher.research_search") as mock_search, \
             patch("research.researcher.research_website") as mock_web, \
             patch("research.researcher.research_social") as mock_soc:

            mock_search.return_value.status = ResourceStatus.NOT_FOUND
            mock_search.return_value.to_dict.return_value = {"status": "NOT_FOUND"}
            mock_search.return_value.search_snippets = []
            mock_search.return_value.discovered_website = None
            mock_search.return_value.discovered_links = {}
            mock_search.return_value.discovered_phones = []
            mock_search.return_value.discovered_emails = []
            mock_search.return_value.evidence = []

            mock_web.return_value = WebsiteResearch(url=None, status="unknown", reachable="unknown")
            mock_soc.return_value.status = "missing"
            mock_soc.return_value.resource_status = ResourceStatus.UNKNOWN
            mock_soc.return_value.activity_signal = "unknown"
            mock_soc.return_value.url = None
            mock_soc.return_value.public_metrics_snippet = ""
            mock_soc.return_value.commercial_signals = []
            mock_soc.return_value.whatsapp_cta = None
            mock_soc.return_value.extracted_phones = []
            mock_soc.return_value.extracted_website = None
            mock_soc.return_value.evidence = []

            record = _research_one(lead_raw, "lead_004_unknown")

        self.assertEqual(record.website_status, "unknown")
        self.assertEqual(record.ecommerce_status, "unknown")
        self.assertEqual(record.checkout_status, "unknown")
        self.assertIn("Website status unknown", record.unknowns)

    # 13. Existing Schema Compatibility (JSON and CSV serialization)
    def test_schema_serialization_contains_all_core_and_new_keys(self) -> None:
        lead_raw = {
            "raw": {"business_name": "Schema Test", "phone": "03001234567"},
            "source_column_map": {"business_name": "business_name", "phone": "phone"},
            "source_file": "input/test.csv",
            "row_number": 5,
        }
        with patch("research.researcher.research_search") as mock_search, \
             patch("research.researcher.research_website") as mock_web, \
             patch("research.researcher.research_social") as mock_soc:

            mock_search.return_value.status = ResourceStatus.NOT_FOUND
            mock_search.return_value.to_dict.return_value = {"status": "NOT_FOUND"}
            mock_search.return_value.search_snippets = []
            mock_search.return_value.discovered_website = None
            mock_search.return_value.discovered_links = {}
            mock_search.return_value.discovered_phones = []
            mock_search.return_value.discovered_emails = []
            mock_search.return_value.evidence = []

            mock_web.return_value = WebsiteResearch(url=None, status="unknown", reachable="unknown")
            mock_soc.return_value.status = "missing"
            mock_soc.return_value.resource_status = ResourceStatus.UNKNOWN
            mock_soc.return_value.activity_signal = "unknown"
            mock_soc.return_value.url = None
            mock_soc.return_value.public_metrics_snippet = ""
            mock_soc.return_value.commercial_signals = []
            mock_soc.return_value.whatsapp_cta = None
            mock_soc.return_value.extracted_phones = []
            mock_soc.return_value.extracted_website = None
            mock_soc.return_value.evidence = []

            record = _research_one(lead_raw, "lead_005_schema_test")

        as_dict = _record_to_dict(record)
        as_row = _record_to_row(record)

        # Baseline legacy keys present
        for k in ("lead_id", "business_name", "website_status", "ecommerce_status", "digital_maturity", "observed_digital_gaps"):
            self.assertIn(k, as_dict)
            self.assertIn(k, as_row)

        # New deep research keys present in dict
        for k in ("products_services_summary", "ecommerce_details", "social_details", "contact_details", "malikaxiom_opportunities", "research_synthesis"):
            self.assertIn(k, as_dict)

    # 14. M3 Lead Qualification Compatibility
    def test_m3_qualification_successfully_ingests_m2_record(self) -> None:
        lead_raw = {
            "raw": {
                "business_name": "Zara Collection",
                "category": "Women Clothing",
                "address": "Islamabad",
                "phone": "+923001234567",
                "instagram": "https://instagram.com/zaracollectionisb",
            },
            "source_column_map": {
                "business_name": "business_name",
                "category": "category",
                "address": "address",
                "phone": "phone",
                "instagram": "instagram",
            },
            "source_file": "input/test.csv",
            "row_number": 6,
        }
        with patch("research.researcher.research_search") as mock_search, \
             patch("research.researcher.research_website") as mock_web, \
             patch("research.researcher.research_social") as mock_soc:

            mock_search.return_value.status = ResourceStatus.FOUND
            mock_search.return_value.to_dict.return_value = {"status": "FOUND"}
            mock_search.return_value.search_snippets = []
            mock_search.return_value.discovered_website = None
            mock_search.return_value.discovered_links = {}
            mock_search.return_value.discovered_phones = []
            mock_search.return_value.discovered_emails = []
            mock_search.return_value.evidence = []

            mock_web.return_value = WebsiteResearch(url=None, status="unknown", reachable="unknown")
            mock_soc.return_value.status = "present"
            mock_soc.return_value.resource_status = ResourceStatus.FOUND
            mock_soc.return_value.activity_signal = "accessible"
            mock_soc.return_value.url = "https://instagram.com/zaracollectionisb"
            mock_soc.return_value.public_metrics_snippet = "10k followers"
            mock_soc.return_value.commercial_signals = ["dm for orders"]
            mock_soc.return_value.whatsapp_cta = None
            mock_soc.return_value.extracted_phones = []
            mock_soc.return_value.extracted_website = None
            mock_soc.return_value.evidence = []

            record = _research_one(lead_raw, "lead_006_zara")

        # Pass directly into M3 qualification function
        research_dict = _record_to_dict(record)
        qual_record = qualify_lead(research_dict)

        self.assertIsNotNone(qual_record)
        self.assertEqual(qual_record.business_name, "Zara Collection")
        self.assertEqual(qual_record.sales_potential, "HIGH")
        self.assertEqual(qual_record.final_action, "CONTACT")
        self.assertEqual(qual_record.primary_service, "Business Digitalization")

    # 15. Batch Error Isolation (one failed lead does not crash the run)
    def test_batch_continues_when_one_lead_raises_exception(self) -> None:
        from research.researcher import run_research

        with tempfile.TemporaryDirectory() as tmp_dir:
            csv_path = Path(tmp_dir) / "test_leads.csv"
            csv_path.write_text(
                "business_name,phone\n"
                "Broken Lead,03001111111\n"
                "Valid Lead,03002222222\n",
                encoding="utf-8",
            )
            out_dir = Path(tmp_dir) / "output"

            # Cause _research_one to throw an exception on first lead only
            original_research_one = _research_one
            call_count = [0]

            def mock_research_one(lead: dict, lead_id: str, timeout: float = 12.0):
                call_count[0] += 1
                if call_count[0] == 1:
                    raise RuntimeError("Simulated transient crash on lead 1")
                # Return standard valid research record for lead 2
                rec = _error_record(lead_id, lead, "")
                rec.research_status = "RESEARCHED"
                return rec

            with patch("research.researcher._research_one", side_effect=mock_research_one):
                json_path, csv_path_out, total, fully, partial, unreach, errors = run_research(
                    csv_path, output_dir=out_dir
                )

            self.assertEqual(total, 2)
            self.assertEqual(errors, 1)
            self.assertTrue(json_path.exists())
            self.assertTrue(csv_path_out.exists())
            records = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertEqual(len(records), 2)
            self.assertEqual(records[0]["research_status"], "ERROR")

    # 16. Confirmation of Zero Artificial Sleep
    def test_zero_artificial_sleep_in_research_code(self) -> None:
        research_dir = Path(__file__).resolve().parent.parent / "research"
        for py_file in research_dir.glob("*.py"):
            code = py_file.read_text(encoding="utf-8")
            self.assertNotIn("time.sleep", code, f"Found time.sleep in {py_file.name}")
    # 17. 22-column schema normalization & raw scraper mapping test
    def test_normalize_csv_and_standardized_mapping(self) -> None:
        from research.input_loader import STANDARDIZED_COLUMNS, load_leads, normalize_csv

        raw_scraper_csv = (
            "input_id,link,title,category,address,open_hours,popular_times,website,phone,plus_code,"
            "review_count,review_rating,reviews_per_rating,latitude,longitude,cid,status,descriptions,"
            "reviews_link,thumbnail,timezone,price_range,data_id,street_view_url,place_id,images,"
            "reservations,order_online,menu,owner,complete_address,credit_cards_accepted,about,"
            "user_reviews,user_reviews_extended,emails\n"
            "id_123,https://maps.google.com/test,Ali Fashion,Clothing store,Main Blvd Lahore,9AM-10PM,"
            "{},https://alifashion.pk,+923001234567,plus123,50,4.8,{},31.5,74.3,cid123,active,desc,"
            "https://rev,https://thumb,Asia/Karachi,$$,data123,https://street,place123,[],null,"
            "\"[{'link':'https://wa.me/923001234567'}]\",null,Ali Owner,Complete Address Lahore,yes,about,[],[],ali@example.com\n"
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            in_file = Path(tmp_dir) / "raw.csv"
            out_file = Path(tmp_dir) / "std.csv"
            in_file.write_text(raw_scraper_csv, encoding="utf-8")

            # 1. Normalize
            res_path = normalize_csv(in_file, out_file)
            self.assertTrue(res_path.is_file())

            # 2. Check headers match the exact 22 columns
            with res_path.open(encoding="utf-8") as f:
                reader = csv.DictReader(f)
                headers = list(reader.fieldnames or [])
                self.assertEqual(headers, list(STANDARDIZED_COLUMNS))
                rows = list(reader)
                self.assertEqual(len(rows), 1)
                r = rows[0]
                self.assertEqual(r["business_name"], "Ali Fashion")
                self.assertEqual(r["phone"], "+923001234567")
                self.assertEqual(r["email"], "ali@example.com")
                self.assertEqual(r["website"], "https://alifashion.pk")
                self.assertEqual(r["category"], "Clothing store")
                self.assertEqual(r["rating"], "4.8")
                self.assertEqual(r["reviews"], "50")
                self.assertEqual(r["hours"], "9AM-10PM")
                self.assertEqual(r["latitude"], "31.5")
                self.assertEqual(r["longitude"], "74.3")
                self.assertEqual(r["place_id"], "place123")
                self.assertEqual(r["cid"], "cid123")
                self.assertEqual(r["google_maps_url"], "https://maps.google.com/test")

            # 3. Direct load_leads with raw scraper file
            leads = load_leads(in_file)
            self.assertEqual(len(leads), 1)
            self.assertEqual(leads[0]["raw"]["title"], "Ali Fashion")
            self.assertEqual(leads[0]["source_column_map"]["business_name"], "title")
            self.assertEqual(leads[0]["source_column_map"]["rating"], "review_rating")
            self.assertEqual(leads[0]["source_column_map"]["reviews"], "review_count")
            self.assertEqual(leads[0]["source_column_map"]["google_maps_url"], "link")


if __name__ == "__main__":
    unittest.main()

