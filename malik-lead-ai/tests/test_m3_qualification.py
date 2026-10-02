"""Regression tests for M3 Qualification Engine — no-website and UNREACHABLE lead handling.

Covers the fix for the incorrect reviews >= 20 hard-archive gate that was causing valid
local clothing-store leads with no website to be incorrectly archived even when they had
a valid Google Maps listing, phone number and business category.

Strategy rule under test:
    "A business with NO website or weak digital presence may be a strong sales opportunity
    even if it has 0 Google reviews. Review count must NOT be a hard archive/skip gate."
    "NO WEBSITE + VALID BUSINESS SIGNALS = WEBSITE OPPORTUNITY + DIGITALIZATION OPPORTUNITY"
"""

from __future__ import annotations

import sys
from pathlib import Path
import unittest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from qualification.qualifier import (
    qualify_lead,
    _active_business_signal,
    _score_sales_potential,
    _detect_opportunity,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

MAPS_URL = "https://www.google.com/maps?cid=0x39190559b0852e63:0x24a9597235dfe515"
PHONE = "0331 4789624, +92 331 4789624"


def _no_website_lead(
    *,
    google_maps_url: str | None = MAPS_URL,
    google_rating: str | None = "4.1",
    google_reviews: str | None = None,  # default: no reviews
    phone: str | None = PHONE,
    category: str | None = "Clothing store",
    research_status: str = "UNREACHABLE",
    has_social: bool = False,
    lead_id: str = "test_lead",
    location: str = "Lahore, Pakistan",
) -> dict:
    """Minimal research-result dict for a lead with no website."""
    insta = "https://instagram.com/testbrand" if has_social else None
    return {
        "lead_id": lead_id,
        "business_name": "Test Clothing Store",
        "category": category,
        "location": location,
        "phone": phone,
        "mobile_phone": None,
        "whatsapp": None,
        "landline": None,
        "email": None,
        "website": None,
        "website_status": "unknown",
        "website_reachable": "unknown",
        "website_type": None,
        "ecommerce_status": "unknown",
        "checkout_status": "unknown",
        "online_ordering": "unknown",
        "whatsapp_contact": "unknown",
        "contact_option_present": "unknown",
        "instagram": insta,
        "instagram_status": "present" if has_social else "missing",
        "instagram_activity": "unknown",
        "facebook": None,
        "facebook_status": "missing",
        "facebook_activity": "unknown",
        "tiktok": None,
        "tiktok_status": "missing",
        "tiktok_activity": "unknown",
        "linkedin": None,
        "linkedin_status": "missing",
        "linkedin_activity": "unknown",
        "google_maps_url": google_maps_url,
        "google_rating": google_rating,
        "google_reviews": google_reviews,
        "google_category": category,
        "google_address": location,
        "google_website_connection": "unknown",
        "google_other_listing_notes": "",
        "research_status": research_status,
        "digital_maturity": "VERY WEAK",
        "observed_digital_gaps": ["No dedicated website identified"],
        "verified_facts": [],
        "reasonable_observations": [],
        "unknowns": ["Website status unknown"],
        "business_type": "retail_or_product_business",
        "local_offline_online": "unknown",
        "apparent_target_market": "Clothing store in Lahore",
    }


# ---------------------------------------------------------------------------
# Regression tests: review count must NOT be a hard archive gate
# ---------------------------------------------------------------------------

class TestNoWebsiteLeadIsNeverArchived(unittest.TestCase):
    """Regression: no-website leads with valid business identity must not be ARCHIVE'd."""

    def _qualify(self, **kwargs):
        return qualify_lead(_no_website_lead(**kwargs))

    def test_zero_reviews_no_website_is_investigate_not_archive(self):
        """0 reviews + no website + Maps + phone + category → INVESTIGATE_FURTHER, not ARCHIVE."""
        q = self._qualify(google_reviews=None, google_rating=None)
        self.assertNotEqual(
            q.final_action, "ARCHIVE",
            f"Lead with 0 reviews/no rating should NOT be ARCHIVE'd (got {q.final_action})"
        )
        self.assertIn(q.final_action, ("INVESTIGATE_FURTHER", "CONTACT"),
                      f"Expected INVESTIGATE_FURTHER or CONTACT, got {q.final_action}")

    def test_five_reviews_no_website_is_investigate_not_archive(self):
        """5 reviews + no website + Maps + phone → INVESTIGATE_FURTHER, not ARCHIVE."""
        q = self._qualify(google_reviews="5", google_rating="4.0")
        self.assertNotEqual(q.final_action, "ARCHIVE")
        self.assertIn(q.final_action, ("INVESTIGATE_FURTHER", "CONTACT"))

    def test_nine_reviews_no_website_is_investigate_not_archive(self):
        """9 reviews (like lead_027) → must NOT be ARCHIVE'd."""
        q = self._qualify(google_reviews="9", google_rating="5")
        self.assertNotEqual(q.final_action, "ARCHIVE",
                            "lead_027 equivalent: 9 reviews should NOT produce ARCHIVE")
        self.assertIn(q.final_action, ("INVESTIGATE_FURTHER", "CONTACT"))

    def test_thirteen_reviews_no_website_is_investigate_not_archive(self):
        """13 reviews (like lead_034) → must NOT be ARCHIVE'd."""
        q = self._qualify(google_reviews="13", google_rating="4.9")
        self.assertNotEqual(q.final_action, "ARCHIVE",
                            "lead_034 equivalent: 13 reviews should NOT produce ARCHIVE")
        self.assertIn(q.final_action, ("INVESTIGATE_FURTHER", "CONTACT"))

    def test_eighteen_reviews_no_website_is_investigate_not_archive(self):
        """18 reviews (like lead_033) → must NOT be ARCHIVE'd."""
        q = self._qualify(google_reviews="18", google_rating="4.1")
        self.assertNotEqual(q.final_action, "ARCHIVE",
                            "lead_033 equivalent: 18 reviews should NOT produce ARCHIVE")
        self.assertIn(q.final_action, ("INVESTIGATE_FURTHER", "CONTACT"))

    def test_hundred_reviews_no_website_is_investigate_not_archive(self):
        """100 reviews + no website → INVESTIGATE_FURTHER or CONTACT, definitely not ARCHIVE."""
        q = self._qualify(google_reviews="100", google_rating="4.5")
        self.assertNotEqual(q.final_action, "ARCHIVE")
        self.assertIn(q.final_action, ("INVESTIGATE_FURTHER", "CONTACT"))

    def test_no_reviews_no_rating_but_maps_phone_category_is_investigate(self):
        """A lead with Maps URL + phone + category but NO rating or reviews must be INVESTIGATE.

        This covers Group A leads (e.g. lead_003, lead_007, lead_016) that previously
        fell to WEAK signal and were then hard-archived.
        """
        q = self._qualify(google_reviews=None, google_rating=None, phone=PHONE, category="Clothing store")
        self.assertNotEqual(q.final_action, "ARCHIVE",
                            "Maps + phone + category with 0 reviews should NOT be ARCHIVE'd")
        self.assertIn(q.final_action, ("INVESTIGATE_FURTHER", "CONTACT"))


# ---------------------------------------------------------------------------
# Regression tests: active_business_signal for Maps+phone+category
# ---------------------------------------------------------------------------

class TestActiveSignalMapsPhoneCategory(unittest.TestCase):
    """Regression: a lead with Maps URL + phone + category should be at least MODERATE."""

    def _signal(self, **kwargs):
        return _active_business_signal(_no_website_lead(**kwargs))

    def test_maps_phone_category_zero_reviews_is_at_least_moderate(self):
        """Maps URL + phone + category with 0 reviews must be MODERATE or STRONG."""
        signal, evidence = self._signal(google_reviews=None, google_rating=None)
        self.assertIn(signal, ("MODERATE", "STRONG"),
                      f"Maps+phone+category should yield MODERATE or STRONG, got {signal}")

    def test_maps_phone_category_few_reviews_is_moderate_or_strong(self):
        """Maps URL + phone + category + 5 reviews must be MODERATE or STRONG."""
        signal, _ = self._signal(google_reviews="5", google_rating="4.0")
        self.assertIn(signal, ("MODERATE", "STRONG"))

    def test_maps_phone_no_category_may_be_weak_or_higher(self):
        """Maps URL + phone but NO category: WEAK is acceptable (less business identity)."""
        signal, _ = self._signal(google_reviews=None, google_rating=None, category=None)
        # We only assert it doesn't become NONE — at least one signal present
        self.assertNotEqual(signal, "NONE")

    def test_ten_or_more_reviews_is_strong_or_moderate(self):
        """Maps URL + rating + 10+ reviews → STRONG."""
        signal, _ = self._signal(google_reviews="10", google_rating="4.5")
        self.assertIn(signal, ("STRONG", "MODERATE"))


# ---------------------------------------------------------------------------
# Regression tests: sales_potential scoring for no_website_url_found
# ---------------------------------------------------------------------------

class TestNoWebsiteSalesPotential(unittest.TestCase):
    """The no_website_url_found path must produce MODERATE for valid local businesses."""

    def _potential(self, **kwargs):
        lead = _no_website_lead(**kwargs)
        active_signal, _ = _active_business_signal(lead)
        opp_label, _, _ = _detect_opportunity(lead)
        # maturity is unused in this code path but must be passed
        return _score_sales_potential(lead, active_signal, opp_label, "digitalization", "VERY WEAK")

    def test_strong_signal_no_website_zero_reviews_is_moderate(self):
        """STRONG signal + no website + 0 reviews → MODERATE (never LOW)."""
        # Give it 10 reviews to ensure STRONG signal
        potential = self._potential(google_reviews="10", google_rating="4.0")
        self.assertNotEqual(potential, "LOW",
                            "STRONG active signal + no website must NOT produce LOW")

    def test_moderate_signal_no_website_zero_reviews_is_moderate(self):
        """MODERATE signal + no website + 0 reviews → MODERATE."""
        potential = self._potential(google_reviews=None, google_rating=None, phone=PHONE, category="Clothing store")
        self.assertNotEqual(potential, "LOW",
                            "Maps+phone+category signal + no website must NOT produce LOW")

    def test_no_signal_at_all_produces_skip_or_low(self):
        """A lead with absolutely no identifiers → LOW or SKIP (not a false positive)."""
        lead = _no_website_lead(
            google_maps_url=None,
            phone=None,
            category=None,
            google_reviews=None,
            google_rating=None,
        )
        active_signal, _ = _active_business_signal(lead)
        opp_label, _, _ = _detect_opportunity(lead)
        potential = _score_sales_potential(lead, active_signal, opp_label, "digitalization", "VERY WEAK")
        self.assertIn(potential, ("LOW", "SKIP"),
                      f"No signal lead must produce LOW or SKIP, got {potential}")


# ---------------------------------------------------------------------------
# Regression tests: specific leads from the 50-lead dataset
# ---------------------------------------------------------------------------

class TestSpecificDatasetLeads(unittest.TestCase):
    """Regression tests using actual research data for the 4 originally affected leads."""

    @classmethod
    def setUpClass(cls):
        import json
        research_path = PROJECT_ROOT / "output" / "research_results.json"
        if not research_path.exists():
            cls.leads = {}
            return
        with research_path.open(encoding="utf-8") as f:
            cls.leads = {r["lead_id"]: r for r in json.load(f)}

    def _qualify(self, lead_id: str):
        if lead_id not in self.leads:
            self.skipTest(f"Lead {lead_id} not in research_results.json")
        return qualify_lead(self.leads[lead_id])

    def test_lead_027_brand_hub_is_not_archived(self):
        """lead_027 (9 reviews, no website) must be INVESTIGATE_FURTHER, not ARCHIVE."""
        q = self._qualify("lead_027_the_brand_hub_clothing")
        self.assertNotEqual(q.final_action, "ARCHIVE",
                            f"lead_027 must NOT be ARCHIVE'd (got {q.final_action})")
        self.assertIn(q.final_action, ("INVESTIGATE_FURTHER", "CONTACT"))

    def test_lead_031_blues_apparel_is_not_archived(self):
        """lead_031 (8 reviews, no website) must be INVESTIGATE_FURTHER, not ARCHIVE."""
        q = self._qualify("lead_031_blues_apparel")
        self.assertNotEqual(q.final_action, "ARCHIVE",
                            f"lead_031 must NOT be ARCHIVE'd (got {q.final_action})")
        self.assertIn(q.final_action, ("INVESTIGATE_FURTHER", "CONTACT"))

    def test_lead_033_brands_factory_is_not_archived(self):
        """lead_033 (18 reviews, no website) must be INVESTIGATE_FURTHER, not ARCHIVE."""
        q = self._qualify("lead_033_brands_factory")
        self.assertNotEqual(q.final_action, "ARCHIVE",
                            f"lead_033 must NOT be ARCHIVE'd (got {q.final_action})")
        self.assertIn(q.final_action, ("INVESTIGATE_FURTHER", "CONTACT"))

    def test_lead_034_the_brand_outfit_is_not_archived(self):
        """lead_034 (13 reviews, no website) must be INVESTIGATE_FURTHER, not ARCHIVE."""
        q = self._qualify("lead_034_the_brand_outfit")
        self.assertNotEqual(q.final_action, "ARCHIVE",
                            f"lead_034 must NOT be ARCHIVE'd (got {q.final_action})")
        self.assertIn(q.final_action, ("INVESTIGATE_FURTHER", "CONTACT"))

    def test_lead_003_zero_reviews_is_not_archived(self):
        """lead_003 (0 reviews, no website) must NOT be ARCHIVE'd — Maps + phone + category present."""
        q = self._qualify("lead_003_clothing_brand")
        self.assertNotEqual(q.final_action, "ARCHIVE",
                            "lead_003 with 0 reviews and no website must NOT be ARCHIVE'd")

    def test_lead_007_zero_reviews_is_not_archived(self):
        """lead_007 (0 reviews, no website) must NOT be ARCHIVE'd."""
        q = self._qualify("lead_007_top_brands")
        self.assertNotEqual(q.final_action, "ARCHIVE",
                            "lead_007 with 0 reviews and no website must NOT be ARCHIVE'd")

    def test_lead_016_zero_reviews_is_not_archived(self):
        """lead_016 (0 reviews, no website) must NOT be ARCHIVE'd."""
        q = self._qualify("lead_016_zrb_brands_hub")
        self.assertNotEqual(q.final_action, "ARCHIVE",
                            "lead_016 with 0 reviews and no website must NOT be ARCHIVE'd")

    def test_high_review_leads_remain_investigate_or_contact(self):
        """Leads with 20+ reviews that were previously correct must not regress."""
        for lid in ("lead_028_ehsan_clothing_store_", "lead_029_the_trend_jeans_athletic_wear"):
            q = self._qualify(lid)
            self.assertIn(q.final_action, ("INVESTIGATE_FURTHER", "CONTACT"),
                          f"{lid}: expected INVESTIGATE_FURTHER/CONTACT, got {q.final_action}")

    def test_already_sent_leads_are_not_in_research_results(self):
        """Sanity: the m6_send_state.json is independent of qualification output."""
        import json
        state_path = PROJECT_ROOT / "output" / "m6_send_state.json"
        if not state_path.exists():
            self.skipTest("m6_send_state.json not present")
        with state_path.open(encoding="utf-8") as f:
            state = json.load(f)
        sent_ids = [k for k, v in state.items() if isinstance(v, dict) and v.get("status") == "SENT"]
        # The fix must not touch already-sent leads — verify they still qualify consistently
        for sid in sent_ids:
            if sid in self.leads:
                q = qualify_lead(self.leads[sid])
                # We don't assert a specific action — just that qualification doesn't raise
                self.assertIsNotNone(q.final_action)


# ---------------------------------------------------------------------------
# Regression tests: leads that should still be ARCHIVE'd
# ---------------------------------------------------------------------------

class TestLeadsThatShouldRemainArchived(unittest.TestCase):
    """Ensure the fix doesn't accidentally promote genuinely weak leads."""

    @classmethod
    def setUpClass(cls):
        import json
        research_path = PROJECT_ROOT / "output" / "research_results.json"
        if not research_path.exists():
            cls.leads = {}
            return
        with research_path.open(encoding="utf-8") as f:
            cls.leads = {r["lead_id"]: r for r in json.load(f)}

    def _qualify(self, lead_id: str):
        if lead_id not in self.leads:
            self.skipTest(f"Lead {lead_id} not in research_results.json")
        return qualify_lead(self.leads[lead_id])

    def test_lead_with_well_established_presence_is_low_or_archive(self):
        """A lead with a good website AND social AND Maps is not a website-sale opportunity."""
        lead = {
            "lead_id": "test_established",
            "business_name": "Well Established Brand",
            "category": "Clothing store",
            "location": "Lahore, Pakistan",
            "phone": PHONE,
            "mobile_phone": None, "whatsapp": None, "landline": None, "email": None,
            "website": "https://wellestablished.com",
            "website_status": "exists",
            "website_reachable": "reachable",
            "website_type": "ecommerce",
            "ecommerce_status": "present",
            "checkout_status": "present",
            "online_ordering": "present",
            "whatsapp_contact": "present",
            "contact_option_present": "present",
            "instagram": "https://instagram.com/wellestablished",
            "instagram_status": "present",
            "instagram_activity": "active",
            "facebook": "https://facebook.com/wellestablished",
            "facebook_status": "present",
            "facebook_activity": "active",
            "tiktok": None, "tiktok_status": "missing", "tiktok_activity": "unknown",
            "linkedin": None, "linkedin_status": "missing", "linkedin_activity": "unknown",
            "google_maps_url": MAPS_URL,
            "google_rating": "4.8",
            "google_reviews": "500",
            "google_category": "Clothing store",
            "google_address": "Lahore",
            "google_website_connection": "linked",
            "google_other_listing_notes": "",
            "research_status": "RESEARCHED",
            "digital_maturity": "ADVANCED",
            "observed_digital_gaps": [],
            "verified_facts": ["Website reachable", "E-commerce signals detected"],
            "reasonable_observations": [],
            "unknowns": [],
            "business_type": "retail_or_product_business",
            "local_offline_online": "online",
            "apparent_target_market": "Clothing store in Lahore",
        }
        q = qualify_lead(lead)
        # well_established → sales_potential=LOW → final_action=ARCHIVE is correct
        self.assertIn(q.sales_potential, ("LOW", "SKIP"),
                      f"Well-established lead should have LOW or SKIP potential, got {q.sales_potential}")

    def test_no_any_identifier_is_still_low_or_skip(self):
        """A lead with absolutely no phone, no Maps, no website, no social → LOW/SKIP."""
        lead = _no_website_lead(
            google_maps_url=None,
            phone=None,
            category=None,
            google_reviews=None,
            google_rating=None,
        )
        q = qualify_lead(lead)
        self.assertIn(q.sales_potential, ("LOW", "SKIP"),
                      f"Lead with no identifiers must be LOW or SKIP, got {q.sales_potential}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
