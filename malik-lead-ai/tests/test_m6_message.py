"""M6 message + validation tests (task spec tests 7–11, 18, 26)."""

from __future__ import annotations

import unittest

from tests.support import make_lead

from m6.message_builder import MAX_BODY_WORDS, build_first_message, pricing_applies
from m6.phone import normalize_pakistani_mobile, resolve_recipient, split_phone_candidates
from m6.validator import validate_message


class TestMessageBuilder(unittest.TestCase):
    # Test 11 — M3 says Business Digitalization → M6 preserves it
    def test_service_from_m5_is_preserved(self) -> None:
        lead = make_lead(primary_service="Business Digitalization")
        built = build_first_message(lead)
        self.assertEqual(built.service, "Business Digitalization")
        self.assertIn("website", built.text.lower())

    # Test 10 — e-commerce lead keeps e-commerce; M6 invents no other opportunity
    def test_ecommerce_lead_is_not_converted_to_another_opportunity(self) -> None:
        lead = make_lead(
            lead_id="lead_ecom",
            business_name="Shoply Store",
            primary_service="E-Commerce",
            detected_opportunity="Sells products through social media only",
        )
        built = build_first_message(lead)
        self.assertEqual(built.service, "E-Commerce")
        self.assertIn("e-commerce", built.text.lower())

    def test_missing_m5_service_never_guesses(self) -> None:
        from m6.message_builder import MessageBuildError

        with self.assertRaises(MessageBuildError):
            build_first_message(make_lead(primary_service=""))

    # Test 5 (message part) — weak evidence → neutral wording, no invented problems
    def test_weak_evidence_uses_neutral_wording(self) -> None:
        built = build_first_message(make_lead(website="", instagram="", facebook=""))
        self.assertIn("Having a professional website makes it easier for customers to find you", built.text)
        for banned in ("outdated", "losing customers", "poor branding", "guarantee"):
            self.assertNotIn(banned, built.text.lower())

    def test_message_stays_within_word_budget(self) -> None:
        cases = (
            {"website": "https://instagram.com/arbrandzone", "instagram": "https://instagram.com/arbrandzone"},
            {"website": "", "instagram": "", "facebook": ""},
            {"website": "https://arbrandzone.pk", "instagram": "https://instagram.com/arbrandzone"},
        )
        for kwargs in cases:
            with self.subTest(kwargs=kwargs):
                built = build_first_message(make_lead(**kwargs))
                self.assertGreaterEqual(built.body_word_count, 45)
                self.assertLessEqual(built.body_word_count, MAX_BODY_WORDS)

    def test_pricing_included_in_template(self) -> None:
        lead = make_lead(primary_service="Business Digitalization")
        built = build_first_message(lead)
        self.assertTrue(built.pricing_included)
        self.assertIn("PKR 10,000", built.text)


class TestValidator(unittest.TestCase):
    def _validate(self, lead, message: str, **kwargs):
        built = build_first_message(lead)
        built.text = message
        return validate_message(
            built, lead, recipient=kwargs.pop("recipient", "+923136162007"),
            channel=kwargs.pop("channel", "whatsapp"), **kwargs,
        )

    def test_valid_message_passes(self) -> None:
        lead = make_lead()
        built = build_first_message(lead)
        result = validate_message(built, lead, recipient="+923136162007", channel="whatsapp")
        self.assertTrue(result.ok, result.as_text())

    # Test 7 — placeholder in the message
    def test_placeholder_business_name_fails(self) -> None:
        lead = make_lead()
        message = build_first_message(lead).text.replace("Arbrandzone", "[Business Name]")
        result = self._validate(lead, message)
        self.assertFalse(result.ok)
        self.assertTrue(any("placeholder" in r for r in result.reasons), result.reasons)

    # Test 8 — 'None' leaked into the message
    def test_none_token_fails(self) -> None:
        lead = make_lead()
        result = self._validate(lead, build_first_message(lead).text.replace("Arbrandzone", "None"))
        self.assertFalse(result.ok)
        self.assertTrue(any("placeholder_token_found" in r for r in result.reasons), result.reasons)

    # Test 9 — wrong email in the contact block
    def test_wrong_contact_details_fail(self) -> None:
        lead = make_lead()
        message = build_first_message(lead).text.replace(
            "hello@malikaxiomtech.com", "sales@example.com"
        )
        result = self._validate(lead, message)
        self.assertFalse(result.ok)
        self.assertTrue(any("unexpected_email" in r for r in result.reasons), result.reasons)

    def test_unapproved_service_in_opportunity_fails(self) -> None:
        lead = make_lead(primary_service="E-Commerce")
        built = build_first_message(lead)
        built.opportunity_line = "I noticed an opportunity around Mobile Development for you."
        built.text = built.text.replace(
            "We can build a professional, mobile-friendly online store for your business "
            "to help you establish a stronger online presence. Website solutions start from PKR 10,000.",
            built.opportunity_line,
        )
        result = validate_message(built, lead, recipient="+923136162007", channel="whatsapp")
        self.assertFalse(result.ok)
        self.assertTrue(
            any("unapproved_service_in_opportunity" in r for r in result.reasons), result.reasons
        )

    def test_missing_recipient_or_channel_fails(self) -> None:
        lead = make_lead()
        built = build_first_message(lead)
        self.assertFalse(validate_message(built, lead, recipient="", channel="whatsapp").ok)
        self.assertFalse(validate_message(built, lead, recipient="+923136162007", channel="").ok)

    def test_whatsapp_execution_channels_are_supported(self) -> None:
        lead = make_lead()
        built = build_first_message(lead)
        for channel in ("whatsapp", "whatsapp_playwright"):
            with self.subTest(channel=channel):
                result = validate_message(
                    built, lead, recipient="+923136162007", channel=channel
                )
                self.assertTrue(result.ok, result.as_text())
        unsupported = validate_message(
            built, lead, recipient="+923136162007", channel="email"
        )
        self.assertFalse(unsupported.ok)
        self.assertIn("unsupported_channel:email", unsupported.reasons)

    def test_invalid_recipient_format_fails(self) -> None:
        lead = make_lead()
        built = build_first_message(lead)
        result = validate_message(built, lead, recipient="03136162007", channel="whatsapp")
        self.assertFalse(result.ok)

    def test_duplicate_flag_fails(self) -> None:
        lead = make_lead()
        built = build_first_message(lead)
        result = validate_message(
            built, lead, recipient="+923136162007", channel="whatsapp", already_sent=True
        )
        self.assertFalse(result.ok)
        self.assertIn("duplicate_send_already_recorded", result.reasons)

    def test_banned_claim_fails(self) -> None:
        lead = make_lead()
        built = build_first_message(lead)
        message = built.text.replace(
            "Assalam o Alaikum 👋",
            "Assalam o Alaikum 👋\nWe guarantee revenue growth.",
        )
        result = self._validate(lead, message)
        self.assertFalse(result.ok)
        self.assertTrue(any("banned_claim_phrase" in r for r in result.reasons), result.reasons)


class TestPhoneNormalization(unittest.TestCase):
    """Spec §18 — safe Pakistani normalisation, no guessing for other countries."""

    def test_pakistani_shapes_normalise_consistently(self) -> None:
        shapes = ("0313 6162007", "+923136162007", "923136162007", "03136162007",
                  "3136162007", "+92 313 6162007", "00923136162007")
        for raw in shapes:
            with self.subTest(raw=raw):
                e164, reason = normalize_pakistani_mobile(raw)
                self.assertEqual(e164, "+923136162007", f"{raw} → {reason}")

    def test_multi_number_cell_uses_first_valid(self) -> None:
        e164, field, reason = resolve_recipient([("phone", "0313 6162007, +92 313 6162007")])
        self.assertEqual(e164, "+923136162007")
        self.assertEqual(field, "phone")
        self.assertEqual(reason, "")

    def test_foreign_and_invalid_numbers_are_not_guessed(self) -> None:
        for raw in ("+971501234567", "+447700900123", "12345", "not-a-number", ""):
            with self.subTest(raw=raw):
                e164, _reason = normalize_pakistani_mobile(raw)
                self.assertIsNone(e164)

    def test_pakistani_landline_is_not_treated_as_whatsapp(self) -> None:
        e164, reason = normalize_pakistani_mobile("0423 111 2222")
        self.assertIsNone(e164)
        self.assertIn("landline", reason)

    def test_split_phone_candidates(self) -> None:
        self.assertEqual(
            split_phone_candidates("0313 6162007, +92 313 6162007"),
            ["0313 6162007", "+92 313 6162007"],
        )


class TestBusinessNameCleaning(unittest.TestCase):
    def test_clean_business_name_trailing_punctuation(self) -> None:
        from m6.message_builder import clean_business_name
        self.assertEqual(clean_business_name("Ehsan clothing store."), "Ehsan Clothing Store")
        self.assertEqual(clean_business_name("SR Salon and Makeup Lounge\""), "SR Salon and Makeup Lounge")
        self.assertEqual(clean_business_name("NUMRA - Makeup Studio & Salon"), "NUMRA - Makeup Studio & Salon")
        self.assertEqual(clean_business_name("vanity salon and spa"), "Vanity Salon and Spa")
        self.assertEqual(
            clean_business_name("Branded Clothes Wholesale in Lahore | Zaib Collection"),
            "Branded Clothes Wholesale in Lahore | Zaib Collection"
        )


class TestUnicodeAndEncodingRegression(unittest.TestCase):
    """Regression tests for UTF-8 emoji preservation and wa.me URL encoding/decoding."""

    def test_emojis_preserved_without_replacement_characters(self) -> None:
        lead = make_lead()
        built = build_first_message(lead)
        self.assertIn("👋", built.text)
        self.assertIn("🌐", built.text)
        self.assertIn("✉️", built.text)
        self.assertNotIn("📱", built.text)  # WhatsApp line removed
        self.assertNotIn("\ufffd", built.text)  # No replacement character

    def test_wame_url_encoding_and_decoding_roundtrip(self) -> None:
        import urllib.parse
        from m6.channels.whatsapp import build_wa_link

        lead = make_lead()
        built = build_first_message(lead)
        link = build_wa_link("+923136162007", built.text)

        self.assertTrue(link.startswith("https://wa.me/923136162007?text="))
        self.assertNotIn("\ufffd", link)

        # Decode back and verify exact string equality
        query_text = link.split("?text=", 1)[1]
        decoded = urllib.parse.unquote(query_text)
        self.assertEqual(decoded, built.text)
        self.assertIn("👋", decoded)
        self.assertIn("🌐", decoded)
        self.assertIn("✉️", decoded)
        self.assertNotIn("📱", decoded)
        self.assertNotIn("\ufffd", decoded)


class TestSentBubbleEmojiMatching(unittest.TestCase):
    """Regression: WhatsApp converts emoji to <img> inside sent bubbles.

    ``row.inner_text()`` therefore returns the message WITHOUT emoji, which
    caused verification to report FAILED for a message that was actually
    delivered (lead_020, 2026-09-25). ``_row_matches`` must still match.
    """

    def _row_without_emoji(self, message: str) -> str:
        # Simulates inner_text() of the sent bubble: emoji <img> omitted.
        return " ".join(message.replace("👋 ", "").replace("👋", "").split())

    def test_exact_match(self) -> None:
        from m6.channels.whatsapp_playwright import _row_matches

        message = "Assalam o Alaikum 👋\n\nI came across Test Store and noticed activity."
        self.assertTrue(_row_matches(message, " ".join(message.split())))

    def test_emoji_as_img_still_matches(self) -> None:
        from m6.channels.whatsapp_playwright import _row_matches

        message = "Assalam o Alaikum 👋\n\nI came across Test Store and noticed activity."
        self.assertTrue(_row_matches(message, self._row_without_emoji(message)))

    def test_full_template_message_matches_emoji_less_row(self) -> None:
        from m6.channels.whatsapp_playwright import _row_matches

        lead = make_lead()
        built = build_first_message(lead)
        self.assertTrue(_row_matches(built.text, self._row_without_emoji(built.text)))

    def test_unrelated_row_does_not_match(self) -> None:
        from m6.channels.whatsapp_playwright import _row_matches

        message = "Assalam o Alaikum 👋\n\nI came across Test Store."
        self.assertFalse(_row_matches(message, "Assalam o Alaikum, who is this?"))
        self.assertFalse(_row_matches(message, ""))

    def test_strip_emoji_removes_only_symbols(self) -> None:
        from m6.channels.whatsapp_playwright import _comparable

        self.assertEqual(_comparable("Hi 👋 there 🌐\nWorld ✉️"), "Hi there World")

    def test_replacement_character_ufffd_matches(self) -> None:
        from m6.channels.whatsapp_playwright import _comparable, _row_matches

        message = "Assalam o Alaikum 👋\n\nI came across Arbrandzone and noticed activity."
        row_with_ufffd = "Assalam o Alaikum \ufffd\n\nI came across Arbrandzone and noticed activity."
        self.assertTrue(_row_matches(message, row_with_ufffd))
        self.assertEqual(_comparable(row_with_ufffd), "Assalam o Alaikum I came across Arbrandzone and noticed activity.")


class TestNaturalMessageRegressions(unittest.TestCase):
    """12 specific regression tests for natural message generation & state safety."""

    def test_personalization_fields_used(self) -> None:
        lead = make_lead(business_name="Custom Boutique", instagram="https://instagram.com/customboutique")
        built = build_first_message(lead)
        self.assertIn("Custom Boutique", built.text)

    def test_website_present_observation(self) -> None:
        lead = make_lead(business_name="Active Store", website="https://activestore.com")
        built = build_first_message(lead)
        self.assertIn("had a look at your online presence", built.text)

    def test_website_missing_observation(self) -> None:
        lead = make_lead(business_name="Local Shop", website="", instagram="", facebook="")
        built = build_first_message(lead)
        self.assertIn("noticed you don't have a dedicated website yet", built.text)

    def test_social_only_observation(self) -> None:
        lead = make_lead(business_name="Social Brand", website="", instagram="https://instagram.com/socialbrand")
        built = build_first_message(lead)
        self.assertIn("noticed you're already active on Instagram", built.text)

    def test_ecommerce_service_messaging(self) -> None:
        lead = make_lead(business_name="Ecom Brand", primary_service="E-Commerce")
        built = build_first_message(lead)
        self.assertIn("e-commerce website", built.text.lower())

    def test_missing_research_data_handling(self) -> None:
        from m6.message_builder import MessageBuildError
        lead = make_lead(business_name="", primary_service="Web Development")
        with self.assertRaises(MessageBuildError):
            build_first_message(lead)

    def test_unsupported_claims_prevention(self) -> None:
        from m6.config import BANNED_CLAIM_PHRASES
        lead = make_lead()
        built = build_first_message(lead)
        for phrase in BANNED_CLAIM_PHRASES:
            self.assertNotIn(phrase.lower(), built.text.lower())

    def test_correct_business_name_used(self) -> None:
        lead = make_lead(business_name="Zaib Collection Lahore |")
        built = build_first_message(lead)
        self.assertIn("Zaib Collection Lahore", built.text)
        self.assertNotIn("Zaib Collection Lahore |", built.text)

    def test_no_generic_opportunity_filler(self) -> None:
        lead = make_lead()
        built = build_first_message(lead)
        self.assertNotIn("there may be an opportunity to strengthen your online presence", built.text)
        self.assertNotIn("couldn't verify a complete digital presence", built.text)

    def test_message_length_within_bounds(self) -> None:
        lead = make_lead()
        built = build_first_message(lead)
        words = len(built.text.split())
        self.assertGreaterEqual(words, 40)
        self.assertLessEqual(words, 120)

    def test_sent_lead_not_resent(self) -> None:
        from m6.send_tracker import SendTracker
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp_dir:
            tracker = SendTracker(Path(tmp_dir))
            tracker._update_state({
                "lead_id": "lead_017_arbrandzone",
                "recipient": "+923136162007",
                "channel": "whatsapp",
                "send_status": "SENT",
            })
            kind, reason = tracker.check_duplicate("lead_017_arbrandzone", "whatsapp", "+923136162007")
            self.assertEqual(kind, "ALREADY_SENT")

    def test_m6_state_intact(self) -> None:
        from m6.send_tracker import SendTracker
        from pathlib import Path
        tracker = SendTracker(Path("/home/hiader-nawaz/MalikAxiom-Lead Ai/malik-lead-ai/output"))
        entry17 = tracker.lead_entry("lead_017_arbrandzone")
        entry20 = tracker.lead_entry("lead_020_branded_clothes_wholesale_in_lahore___za")
        self.assertIsNotNone(entry17)
        self.assertEqual(entry17.get("status"), "SENT")
        self.assertIsNotNone(entry20)
        self.assertEqual(entry20.get("status"), "SENT")


if __name__ == "__main__":
    unittest.main(verbosity=2)

