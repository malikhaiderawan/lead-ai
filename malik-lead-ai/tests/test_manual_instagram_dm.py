"""Unit tests for Instagram DM fallback and manual_instagram_leads.csv export."""

from __future__ import annotations

import csv
import sys
import tempfile
from pathlib import Path
import unittest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from qualification.qualifier import qualify_lead
from outreach.composer import compose_outreach
from sales_report.output_writer import write_manual_instagram_csv, run_sales_report


class TestInstagramDMFallback(unittest.TestCase):
    def test_social_lead_without_phone_qualifies_as_contact(self):
        """A lead with no phone but active Instagram must qualify as CONTACT with Instagram DM."""
        lead_data = {
            "lead_id": "lead_insta_01",
            "business_name": "Zara Boutique & Pret",
            "category": "Women clothing store",
            "location": "Islamabad, Pakistan",
            "phone": None,
            "mobile_phone": None,
            "whatsapp": None,
            "website": None,
            "instagram": "https://instagram.com/zaraboutiquepret",
            "facebook": None,
            "google_maps_url": None,
            "google_rating": None,
            "google_reviews": None,
            "research_status": "RESEARCHED",
        }
        res = qualify_lead(lead_data)
        self.assertIn(res.sales_potential, ("HIGH", "MODERATE"))
        self.assertEqual(res.outreach_channel, "Instagram DM")
        self.assertEqual(res.final_action, "CONTACT")

    def test_outreach_message_composed_for_instagram_dm(self):
        """Instagram DM message must contain a problem-specific hook and Haider's signature."""
        q_record = {
            "lead_id": "lead_insta_02",
            "business_name": "Elegance Abayas",
            "category": "Abaya & Hijab Shop",
            "location": "Rawalpindi, Pakistan",
            "phone": None,
            "mobile_phone": None,
            "whatsapp": None,
            "instagram": "https://instagram.com/eleganceabayas",
            "sales_potential": "HIGH",
            "confidence": "HIGH",
            "primary_service": "Business Digitalization",
            "digital_maturity": "BASIC",
            "recommended_channel": "Instagram DM",
            "final_action": "CONTACT",
        }
        out_rec = compose_outreach(q_record)
        self.assertIn("Assalam o Alaikum", out_rec.opening)
        self.assertIn("Elegance Abayas", out_rec.message)
        self.assertIn("PKR 10,000", out_rec.message)
        self.assertIn("Haider Nawaz", out_rec.cta)

    def test_manual_instagram_csv_writer(self):
        """write_manual_instagram_csv exports social leads with action note."""
        records = [
            {
                "lead_id": "lead_01",
                "business_name": "Test Boutique",
                "location": "Lahore",
                "instagram": "https://instagram.com/testboutique",
                "facebook": "",
                "phone": "",
                "whatsapp": "",
                "sales_potential": "HIGH",
                "primary_service": "Business Digitalization",
                "why_this_lead": "Active instagram clothing brand with no website",
                "outreach_channel": "Instagram DM",
                "outreach_message": "Assalam o Alaikum Test Boutique...",
            },
            {
                "lead_id": "lead_02",
                "business_name": "WhatsApp Only Store",
                "location": "Karachi",
                "instagram": "",
                "facebook": "",
                "phone": "+923001234567",
                "whatsapp": "+923001234567",
                "sales_potential": "HIGH",
                "primary_service": "E-Commerce",
                "why_this_lead": "Active catalog",
                "outreach_channel": "WhatsApp",
                "outreach_message": "Assalam o Alaikum...",
            },
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "manual_instagram_leads.csv"
            count = write_manual_instagram_csv(csv_path, records)
            self.assertEqual(count, 1)

            with csv_path.open(encoding="utf-8") as fh:
                rows = list(csv.DictReader(fh))
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0]["business_name"], "Test Boutique")
                self.assertIn("Copy & send manually", rows[0]["manual_action_note"])


if __name__ == "__main__":
    unittest.main()
