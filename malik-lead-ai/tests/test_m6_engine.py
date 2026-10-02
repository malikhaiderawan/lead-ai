"""M6 engine tests (task spec tests 1–6, 12–16)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tests.support import RecordingChannel, make_lead, row, run_engine, write_m5_csv

from m6.config import (
    MAX_ATTEMPTS_PER_LEAD,
    M6_RESULTS_JSON,
    M6_STATE_FILENAME,
    STATUS_AWAITING_MANUAL,
    STATUS_FAILED,
    STATUS_NO_WHATSAPP,
    STATUS_SENT,
    STATUS_SKIPPED_ALREADY_SENT,
    STATUS_SKIPPED_NO_WHATSAPP,
)
from m6.channels.whatsapp_playwright import is_no_whatsapp_reason, no_whatsapp_marker
from m6.engine import (
    M6RunConfig,
    mark_lead_sent,
    mark_no_whatsapp,
    plan_lead,
    reclassify_no_whatsapp,
    run_outreach_execution,
)
from m6.send_tracker import SendTracker
from m6.source_loader import M5SourceError, load_m5_leads, resolve_source_path


class M6TestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    # -- helpers -------------------------------------------------------
    def state(self) -> dict:
        return json.loads((self.tmp / M6_STATE_FILENAME).read_text(encoding="utf-8"))

    def history(self) -> list[dict]:
        return json.loads((self.tmp / M6_RESULTS_JSON).read_text(encoding="utf-8"))


class TestEligibility(M6TestCase):
    # Test 1 — CONTACT_FIRST lead → eligible
    def test_contact_first_is_eligible_and_sent(self) -> None:
        report, channel, _ = run_engine(self.tmp, [row()])
        self.assertEqual(len(report.candidates), 1)
        self.assertEqual(len(report.skipped), 0)
        self.assertTrue(report.candidates[0].eligible)
        self.assertEqual(report.sent_count, 1)
        self.assertEqual(len(channel.calls), 1)
        self.assertEqual(channel.calls[0][0], "+923136162007")
        self.assertEqual(self.state()["leads"]["lead_017_arbrandzone"]["status"], STATUS_SENT)

    # Test 2 — CONTACT_LATER is eligible by default
    def test_contact_later_is_eligible_and_sent(self) -> None:
        late = row(lead_id="lead_late", business_name="Later Brand",
                   final_action="INVESTIGATE_FURTHER", outreach_priority="CONTACT LATER",
                   sales_potential="MODERATE")
        report, channel, _ = run_engine(self.tmp, [late])
        self.assertEqual(len(report.candidates), 1)
        self.assertEqual(len(report.skipped), 0)
        self.assertTrue(report.candidates[0].eligible)
        self.assertEqual(report.sent_count, 1)
        self.assertEqual(len(channel.calls), 1)
        self.assertEqual(channel.calls[0][0], "+923136162007")
        self.assertEqual(self.state()["leads"]["lead_late"]["status"], STATUS_SENT)

    # Test 3 — ARCHIVE is never contacted
    def test_archive_is_not_sent(self) -> None:
        archived = row(lead_id="lead_arch", business_name="Archived Brand",
                       final_action="ARCHIVE", outreach_priority="SKIP", sales_potential="LOW")
        report, channel, _ = run_engine(self.tmp, [archived])
        self.assertEqual(report.candidates, [])
        self.assertEqual(channel.calls, [])
        self.assertEqual(len(report.skipped), 1)

    # Test 4 — already SENT lead → duplicate blocked
    def test_already_sent_lead_is_not_sent_again(self) -> None:
        report, channel, _ = run_engine(self.tmp, [row()])
        self.assertEqual(len(channel.calls), 1)

        report2, channel2, _ = run_engine(self.tmp, [row()])
        self.assertEqual(len(channel2.calls), 0, "duplicate send must be blocked")
        self.assertEqual(report2.records[0]["send_status"], STATUS_SKIPPED_ALREADY_SENT)
        self.assertEqual(self.state()["leads"]["lead_017_arbrandzone"]["status"], STATUS_SENT)

    def test_explicit_action_filter_excludes_unselected(self) -> None:
        late = row(lead_id="lead_late", final_action="INVESTIGATE_FURTHER",
                   outreach_priority="CONTACT LATER")
        report, channel, _ = run_engine(self.tmp, [late], include_actions=frozenset({"CONTACT_FIRST"}))
        self.assertEqual(report.candidates, [])
        self.assertEqual(len(report.skipped), 1)
        self.assertEqual(channel.calls, [])

    # Test 5 — no phone number at all → NO_WHATSAPP_NUMBER (a recorded fact)
    # The number cannot receive WhatsApp, so it is a dead end: M6 records it
    # clearly instead of a vague NOT_READY and never attempts it again.
    def test_missing_whatsapp_number_is_no_whatsapp_number(self) -> None:
        no_number = row(lead_id="lead_nonum", whatsapp="", mobile_phone="", phone="")
        report, channel, _ = run_engine(self.tmp, [no_number])
        self.assertEqual(channel.calls, [])
        self.assertEqual(report.records[0]["send_status"], STATUS_NO_WHATSAPP)
        self.assertIn("recipient_not_ready", report.records[0]["error"])
        self.assertEqual(
            self.state()["leads"]["lead_nonum"]["status"], STATUS_NO_WHATSAPP
        )

    # Pakistani landline → NO_WHATSAPP_NUMBER, and it is never retried.
    def test_landline_is_no_whatsapp_number_and_is_never_retried(self) -> None:
        landline = row(lead_id="lead_landline", whatsapp="", mobile_phone="",
                       phone="042 35761234")
        report, channel, _ = run_engine(self.tmp, [landline])
        self.assertEqual(channel.calls, [])
        self.assertEqual(report.records[0]["send_status"], STATUS_NO_WHATSAPP)
        self.assertIn("pakistani_landline_not_whatsapp", report.records[0]["error"])
        self.assertEqual(
            self.state()["leads"]["lead_landline"]["status"], STATUS_NO_WHATSAPP
        )

        # A second run — even with --retry-failed — must not attempt it again.
        report2, channel2, _ = run_engine(
            self.tmp, [landline], channel=RecordingChannel(), retry_failed=True
        )
        self.assertEqual(channel2.calls, [])
        self.assertEqual(report2.records[0]["duplicate_status"], "NO_WHATSAPP")
        self.assertEqual(report2.records[0]["send_status"], STATUS_SKIPPED_NO_WHATSAPP)

    # Malformed / foreign numbers are data-quality problems, never "no WhatsApp".
    def test_ambiguous_numbers_stay_not_ready(self) -> None:
        for phone, lead_id in (
            ("12345", "lead_short"),
            ("+971501234567", "lead_foreign2"),
            ("0621 234567", "lead_invalid_mobile"),
        ):
            with self.subTest(phone=phone):
                ambiguous = row(lead_id=lead_id, whatsapp="", mobile_phone="", phone=phone)
                report, channel, _ = run_engine(self.tmp, [ambiguous])
                self.assertEqual(channel.calls, [])
                self.assertEqual(report.records[0]["send_status"], "NOT_READY")

    def test_non_whatsapp_channel_is_not_switched_silently(self) -> None:
        email_lead = row(lead_id="lead_email", outreach_channel="Email", email="x@example.com")
        report, channel, _ = run_engine(self.tmp, [email_lead])
        self.assertEqual(channel.calls, [])
        self.assertIn("channel_not_supported_in_m6_v1", report.records[0]["error"])

    def test_unknown_channel_requires_explicit_opt_in(self) -> None:
        unknown = row(lead_id="lead_unknown_channel", outreach_channel="unknown")
        report, channel, _ = run_engine(self.tmp, [unknown])
        self.assertEqual(channel.calls, [])
        self.assertIn("channel_unknown_in_m5", report.records[0]["error"])

        report2, channel2, _ = run_engine(
            self.tmp, [unknown], allow_channel_inference=True
        )
        self.assertEqual(len(channel2.calls), 1)

    # Test 6 — invalid phone → NOT_READY
    def test_invalid_phone_is_not_ready(self) -> None:
        bad_phone = row(lead_id="lead_badphone", whatsapp="", mobile_phone="", phone="12345")
        report, channel, _ = run_engine(self.tmp, [bad_phone])
        self.assertEqual(channel.calls, [])
        self.assertEqual(report.records[0]["send_status"], "NOT_READY")
        self.assertIn("no_valid_whatsapp_number", report.records[0]["error"])

    def test_foreign_phone_is_not_guessed(self) -> None:
        foreign = row(lead_id="lead_foreign", whatsapp="", mobile_phone="", phone="+971501234567")
        report, channel, _ = run_engine(self.tmp, [foreign])
        self.assertEqual(channel.calls, [])
        self.assertEqual(report.records[0]["send_status"], "NOT_READY")


class TestDuplicateProtection(M6TestCase):
    # Test 12 — two different Facebook pages must not collide
    def test_two_different_facebook_pages_do_not_collide(self) -> None:
        first = row(lead_id="lead_fb_a", business_name="Page A",
                    facebook="https://www.facebook.com/pageA", phone="0300 1111111")
        second = row(lead_id="lead_fb_b", business_name="Page B",
                     facebook="https://www.facebook.com/pageB", phone="0300 2222222")
        report, channel, _ = run_engine(self.tmp, [first, second])

        self.assertEqual(len(channel.calls), 2, "both leads must be sent independently")
        self.assertEqual(report.sent_count, 2)
        self.assertEqual(sorted(call[0] for call in channel.calls),
                         ["+923001111111", "+923002222222"])
        self.assertEqual(len(self.state()["recipients"]), 2)

    def test_shared_recipient_blocks_second_lead(self) -> None:
        first = row(lead_id="lead_shared_a", business_name="Shared A", phone="0300 3333333")
        second = row(lead_id="lead_shared_b", business_name="Shared B", phone="0300 3333333")
        report, channel, _ = run_engine(self.tmp, [first, second])
        self.assertEqual(len(channel.calls), 1)
        statuses = [record["send_status"] for record in report.records]
        self.assertIn(STATUS_SENT, statuses)
        self.assertIn(STATUS_SKIPPED_ALREADY_SENT, statuses)
        skipped = [r for r in report.records if r["send_status"] == STATUS_SKIPPED_ALREADY_SENT][0]
        self.assertIn("recipient", skipped["duplicate_reason"])

    def test_awaiting_manual_send_blocks_reopen(self) -> None:
        channel = RecordingChannel(status=STATUS_AWAITING_MANUAL, detail="chat opened")
        run_engine(self.tmp, [row()], channel=channel)
        self.assertEqual(len(channel.calls), 1)
        self.assertEqual(self.state()["leads"]["lead_017_arbrandzone"]["status"],
                         STATUS_AWAITING_MANUAL)

        report2, channel2, _ = run_engine(self.tmp, [row()])
        self.assertEqual(channel2.calls, [], "an opened chat must not be opened twice")
        self.assertEqual(report2.records[0]["send_status"], STATUS_SKIPPED_ALREADY_SENT)

    def test_mark_sent_records_manual_confirmation(self) -> None:
        channel = RecordingChannel(status=STATUS_AWAITING_MANUAL, detail="chat opened")
        run_engine(self.tmp, [row()], channel=channel)
        exit_code = mark_lead_sent("lead_017_arbrandzone", output_dir=self.tmp, out=lambda *_: None)
        self.assertEqual(exit_code, 0)
        entry = self.state()["leads"]["lead_017_arbrandzone"]
        self.assertEqual(entry["status"], STATUS_SENT)
        self.assertTrue(entry["sent_at"])

        _report3, channel3, _ = run_engine(self.tmp, [row()])
        self.assertEqual(channel3.calls, [])


class TestDryRunAndPersistence(M6TestCase):
    # Test 13 — dry run sends absolutely nothing and writes no state
    def test_dry_run_sends_nothing(self) -> None:
        report, channel, _ = run_engine(self.tmp, [row()], dry_run=True)
        self.assertEqual(channel.calls, [])
        self.assertEqual(report.records, [])
        self.assertFalse((self.tmp / M6_STATE_FILENAME).exists())
        self.assertFalse((self.tmp / M6_RESULTS_JSON).exists())
        self.assertEqual(len(report.candidates), 1)
        self.assertTrue(report.candidates[0].validation.ok)

    def test_real_send_without_confirmation_is_aborted(self) -> None:
        source = write_m5_csv(self.tmp / "m5.csv", [row()])
        channel = RecordingChannel()
        config = M6RunConfig(output_dir=self.tmp, source=str(source), yes=False, min_interval_s=0)
        report = run_outreach_execution(
            config, channel=channel, batch_confirm=lambda n: False, out=lambda *_: None
        )
        self.assertEqual(channel.calls, [])
        self.assertTrue(report.aborted)
        self.assertFalse((self.tmp / M6_STATE_FILENAME).exists())

    # Test 14 — successful send is persisted as SENT
    def test_successful_send_is_persisted(self) -> None:
        report, _channel, _ = run_engine(self.tmp, [row()])
        entry = self.state()["leads"]["lead_017_arbrandzone"]
        self.assertEqual(entry["status"], STATUS_SENT)
        self.assertEqual(entry["attempts"], 1)
        self.assertTrue(entry["sent_at"])
        self.assertEqual(self.state()["recipients"]["whatsapp:+923136162007"]["status"], STATUS_SENT)

        history = self.history()
        self.assertEqual(len(history), 1)
        record = history[0]
        for key in ("lead_id", "business_name", "recipient", "channel", "service",
                    "potential", "action", "opportunity", "message", "validation_status",
                    "send_status", "sent_at", "error"):
            self.assertIn(key, record)
        self.assertEqual(record["service"], "Business Digitalization")
        self.assertEqual(record["opportunity"],
                         "Active on Instagram but no website URL found in research data")
        self.assertEqual(record["validation_status"], "PASS")
        self.assertEqual(record["send_status"], STATUS_SENT)
        self.assertEqual(report.sent_count, 1)
        self.assertTrue((self.tmp / "m6_outreach_results.csv").exists())
        self.assertTrue((self.tmp / "m6_outreach.log").exists())

    # Test 15 — failed send is persisted as FAILED and needs an explicit retry
    def test_failed_send_is_persisted_and_not_auto_retried(self) -> None:
        failing = RecordingChannel(status=STATUS_FAILED, detail="browser could not open")
        _report, channel, _ = run_engine(self.tmp, [row()], channel=failing)
        self.assertEqual(len(channel.calls), 1)
        entry = self.state()["leads"]["lead_017_arbrandzone"]
        self.assertEqual(entry["status"], STATUS_FAILED)
        self.assertIn("browser could not open", entry["error"])

        report2, channel2, _ = run_engine(self.tmp, [row()])
        self.assertEqual(channel2.calls, [], "a FAILED lead must not be retried automatically")
        self.assertEqual(report2.records[0]["duplicate_status"], "PREVIOUS_FAILURE")

        _report3, channel3, _ = run_engine(self.tmp, [row()], retry_failed=True)
        self.assertEqual(len(channel3.calls), 1, "an explicit retry must be allowed")
        self.assertEqual(self.state()["leads"]["lead_017_arbrandzone"]["attempts"], 2)

    def test_attempt_limit_stops_retries(self) -> None:
        entry = {"attempts": MAX_ATTEMPTS_PER_LEAD, "status": STATUS_FAILED, "error": "x",
                 "lead_id": "lead_017_arbrandzone", "history": []}
        (self.tmp / M6_STATE_FILENAME).write_text(
            json.dumps({"version": 1, "leads": {"lead_017_arbrandzone": entry}, "recipients": {}}),
            encoding="utf-8",
        )
        report, channel, _ = run_engine(self.tmp, [row()], retry_failed=True)
        self.assertEqual(channel.calls, [])
        self.assertEqual(report.records[0]["duplicate_status"], "MAX_ATTEMPTS")

    # Test 16 — restarting the app keeps the previous SENT state
    def test_state_survives_restart(self) -> None:
        run_engine(self.tmp, [row()])
        # A brand-new tracker instance simulates a fresh process/app start.
        entry = SendTracker(self.tmp).lead_entry("lead_017_arbrandzone")
        self.assertIsNotNone(entry)
        self.assertEqual(entry["status"], STATUS_SENT)

        report, channel, _ = run_engine(self.tmp, [row()])
        self.assertEqual(channel.calls, [])
        self.assertEqual(report.records[0]["send_status"], STATUS_SKIPPED_ALREADY_SENT)
        self.assertEqual(self.state()["leads"]["lead_017_arbrandzone"]["status"], STATUS_SENT)

    def test_history_is_never_overwritten(self) -> None:
        run_engine(self.tmp, [row()])
        run_engine(self.tmp, [row()], retry_failed=True)
        history = self.history()
        self.assertEqual(len(history), 2)
        self.assertEqual([item["lead_id"] for item in history],
                         ["lead_017_arbrandzone", "lead_017_arbrandzone"])


class TestSourceAndLimits(M6TestCase):
    def test_missing_m5_output_raises_helpful_error(self) -> None:
        from unittest.mock import patch

        empty = self.tmp / "empty"
        empty.mkdir()
        with patch("m6.source_loader.DEFAULT_OUTPUT_DIR", empty):
            with self.assertRaises(M5SourceError) as ctx:
                resolve_source_path(empty, None)
        self.assertIn("sales-report", str(ctx.exception))

    def test_explicit_missing_source_is_reported(self) -> None:
        with self.assertRaises(M5SourceError) as ctx:
            resolve_source_path(self.tmp, self.tmp / "nope.csv")
        self.assertIn("not found", str(ctx.exception))

    def test_contact_first_csv_fallback_derives_stable_ids(self) -> None:
        path = self.tmp / "contact_first.csv"
        path.write_text(
            "business_name,phone,outreach_channel,outreach_priority,primary_service,final_action\n"
            "Arbrandzone,\"0313 6162007, +92 313 6162007\",WhatsApp,CONTACT FIRST,"
            "Business Digitalization,CONTACT\n",
            encoding="utf-8",
        )
        leads = load_m5_leads(path)
        self.assertEqual(len(leads), 1)
        self.assertTrue(leads[0].lead_id.startswith("m5_arbrandzone_"))
        self.assertEqual(load_m5_leads(path)[0].lead_id, leads[0].lead_id, "ids must be stable")

    def test_lead_id_filter_and_send_limit(self) -> None:
        rows = [
            row(lead_id="lead_a", business_name="Alpha", phone="0300 1111111"),
            row(lead_id="lead_b", business_name="Bravo", phone="0300 2222222"),
        ]
        _report, channel, source = run_engine(self.tmp, rows, lead_ids=("lead_b",))
        self.assertEqual([call[0] for call in channel.calls], ["+923002222222"])

        (self.tmp / M6_STATE_FILENAME).unlink(missing_ok=True)
        (self.tmp / M6_RESULTS_JSON).unlink(missing_ok=True)
        channel2 = RecordingChannel()
        config = M6RunConfig(output_dir=self.tmp, source=str(source), yes=True,
                             min_interval_s=0, limit=1)
        report = run_outreach_execution(config, channel=channel2, out=lambda *_: None)
        self.assertEqual(len(channel2.calls), 1, "the run limit must cap sends")
        self.assertEqual(report.count("SKIPPED_LIMIT"), 1)

    def test_dry_run_block_contains_required_fields(self) -> None:
        from m6.engine import format_plan_block

        report, _channel, _ = run_engine(self.tmp, [row()], dry_run=True)
        block = "\n".join(format_plan_block(report.candidates[0], dry_run=True, index=1))
        for expected in ("Lead: lead_017_arbrandzone", "Business: Arbrandzone",
                         "Action: CONTACT FIRST", "Channel: whatsapp",
                         "Recipient: +923136162007", "Service: Business Digitalization",
                         "Opportunity:", "Message:", "Validation: PASS",
                         "NOT SENT — DRY RUN", "https://wa.me/923136162007"):
            self.assertIn(expected, block)

    def test_pricing_flag_only_appends_short_line(self) -> None:
        plain, _c, _ = run_engine(self.tmp, [row()], dry_run=True, include_pricing=True)
        self.assertIn("PKR 10,000", plain.candidates[0].message)
        self.assertTrue(plain.candidates[0].validation.ok)

    def test_review_flagged_can_be_skipped_on_request(self) -> None:
        flagged = row(lead_id="lead_flagged", review_flag="yes", review_reason="suspicious HIGH")
        report, channel, _ = run_engine(self.tmp, [flagged], skip_review_flagged=True)
        self.assertEqual(channel.calls, [])
        self.assertEqual(report.records[0]["send_status"], "NOT_READY")
        self.assertIn("review_flagged_by_m5", report.records[0]["error"])

        (self.tmp / M6_STATE_FILENAME).unlink(missing_ok=True)
        (self.tmp / M6_RESULTS_JSON).unlink(missing_ok=True)
        report2, channel2, _ = run_engine(self.tmp, [flagged], skip_review_flagged=False)
        self.assertEqual(len(report2.candidates), 1)

    def test_plan_lead_never_changes_m5_service(self) -> None:
        lead = make_lead(primary_service="Web Development",
                         detected_opportunity="Existing website found in research data")
        tracker = SendTracker(self.tmp)
        config = M6RunConfig(output_dir=self.tmp, min_interval_s=0)
        plan = plan_lead(lead, config, tracker)
        self.assertEqual(plan.lead.primary_service, "Web Development")
        self.assertIn("website", plan.message.lower())


class TestPlaywrightChannelWiring(M6TestCase):
    """The automated WhatsApp Web execution channel must be first-class."""

    def test_recipient_key_canonicalizes_whatsapp_execution_channels(self) -> None:
        from m6.send_tracker import recipient_key

        for channel in ("whatsapp", "whatsapp_playwright", "playwright", "assist", "link"):
            with self.subTest(channel=channel):
                self.assertEqual(
                    recipient_key(channel, "+923136162007"), "whatsapp:+923136162007"
                )

    def test_plan_with_playwright_channel_passes_validation(self) -> None:
        tracker = SendTracker(self.tmp)
        config = M6RunConfig(output_dir=self.tmp, min_interval_s=0)
        plan = plan_lead(make_lead(), config, tracker, channel_name="whatsapp_playwright")
        self.assertTrue(plan.eligible)
        self.assertEqual(plan.channel, "whatsapp_playwright")
        self.assertTrue(plan.validation.ok, plan.validation.as_text())
        self.assertFalse(plan.duplicate_kind)

    def test_playwright_send_blocks_later_whatsapp_duplicate(self) -> None:
        first = row(lead_id="lead_pw_a", business_name="PW A", phone="0300 6666666")
        source = write_m5_csv(self.tmp / "m5.csv", [first])
        channel = RecordingChannel()
        config = M6RunConfig(
            output_dir=self.tmp, source=str(source), yes=True,
            min_interval_s=0, channel="playwright",
        )
        report = run_outreach_execution(config, channel=channel, out=lambda *_: None)
        self.assertEqual(len(channel.calls), 1)
        self.assertEqual(report.sent_count, 1)
        self.assertEqual(
            self.state()["recipients"]["whatsapp:+923006666666"]["status"], STATUS_SENT
        )

        # Same phone under a different lead, default channel → shared-recipient block.
        second = row(lead_id="lead_pw_b", business_name="PW B", phone="0300 6666666")
        write_m5_csv(self.tmp / "m5.csv", [first, second])
        channel2 = RecordingChannel()
        config2 = M6RunConfig(
            output_dir=self.tmp, source=str(source), yes=True, min_interval_s=0
        )
        report2 = run_outreach_execution(config2, channel=channel2, out=lambda *_: None)
        self.assertEqual(channel2.calls, [], "recipient already contacted via playwright")
        skipped = [r for r in report2.records if r["lead_id"] == "lead_pw_b"]
        self.assertEqual(len(skipped), 1)
        self.assertEqual(skipped[0]["send_status"], STATUS_SKIPPED_ALREADY_SENT)
        self.assertIn("recipient", skipped[0]["duplicate_reason"])


class TestNoWhatsApp(M6TestCase):
    """Numbers with no WhatsApp account: recorded clearly, never retried."""

    def test_recorded_no_whatsapp_blocks_later_runs(self) -> None:
        lead = row(lead_id="lead_failed_then_no_wa", business_name="Dead End")
        failing = RecordingChannel(status=STATUS_FAILED, detail="WhatsApp Web did not load")
        report, _, source = run_engine(self.tmp, [lead], channel=failing)
        self.assertEqual(report.records[0]["send_status"], STATUS_FAILED)

        # The user confirms the number has no WhatsApp account.
        exit_code = mark_no_whatsapp("lead_failed_then_no_wa", output_dir=self.tmp,
                                     out=lambda *_: None)
        self.assertEqual(exit_code, 0)
        entry = self.state()["leads"]["lead_failed_then_no_wa"]
        self.assertEqual(entry["status"], STATUS_NO_WHATSAPP)
        self.assertIn("error", entry)
        self.assertEqual(entry["attempts"], 1, "an attempt was already consumed")

        # Later runs — even with --retry-failed — must never call the channel again.
        channel2 = RecordingChannel()
        config = M6RunConfig(output_dir=self.tmp, source=str(source), yes=True,
                             min_interval_s=0, retry_failed=True)
        report2 = run_outreach_execution(config, channel=channel2, out=lambda *_: None)
        self.assertEqual(channel2.calls, [])
        self.assertEqual(report2.records[0]["duplicate_status"], "NO_WHATSAPP")
        self.assertEqual(report2.records[0]["send_status"], STATUS_SKIPPED_NO_WHATSAPP)
        self.assertEqual(
            self.state()["leads"]["lead_failed_then_no_wa"]["status"], STATUS_NO_WHATSAPP
        )

    def test_marking_a_no_whatsapp_lead_is_idempotent(self) -> None:
        lead = row(lead_id="lead_landline_2", whatsapp="", mobile_phone="",
                   phone="042 35761234")
        run_engine(self.tmp, [lead])
        first = mark_no_whatsapp("lead_landline_2", output_dir=self.tmp, out=lambda *_: None)
        second = mark_no_whatsapp("lead_landline_2", output_dir=self.tmp, out=lambda *_: None)
        self.assertEqual((first, second), (0, 0))
        self.assertEqual(self.state()["leads"]["lead_landline_2"]["attempts"], 0)

    def test_marking_an_untracked_lead_reports_an_error(self) -> None:
        exit_code = mark_no_whatsapp("lead_not_tracked", output_dir=self.tmp,
                                     out=lambda *_: None)
        self.assertEqual(exit_code, 1)

    def test_reclassify_uses_only_recorded_evidence(self) -> None:
        old_state = {
            "version": 1,
            "created_at": "",
            "updated_at": "",
            "leads": {
                # Recorded landline fact → must become NO_WHATSAPP_NUMBER.
                "lead_old_landline": {
                    "lead_id": "lead_old_landline", "attempts": 0, "history": [],
                    "status": "NOT_READY",
                    "error": "recipient_not_ready: no_valid_whatsapp_number "
                             "(phone:pakistani_landline_not_whatsapp, "
                             "phone:pakistani_landline_not_whatsapp)",
                },
                # Foreign number → data-quality problem, must stay NOT_READY.
                "lead_old_foreign": {
                    "lead_id": "lead_old_foreign", "attempts": 0, "history": [],
                    "status": "NOT_READY",
                    "error": "recipient_not_ready: no_valid_whatsapp_number "
                             "(phone:non_pakistani_number_not_supported)",
                },
                # Already contacted → untouched.
                "lead_old_sent": {
                    "lead_id": "lead_old_sent", "attempts": 1, "history": [],
                    "status": STATUS_SENT, "error": "",
                },
            },
            "recipients": {},
        }
        (self.tmp / M6_STATE_FILENAME).write_text(json.dumps(old_state), encoding="utf-8")

        exit_code = reclassify_no_whatsapp(output_dir=self.tmp, out=lambda *_: None)
        self.assertEqual(exit_code, 0)

        leads = self.state()["leads"]
        self.assertEqual(leads["lead_old_landline"]["status"], STATUS_NO_WHATSAPP)
        self.assertIn("pakistani_landline_not_whatsapp", leads["lead_old_landline"]["error"])
        self.assertEqual(leads["lead_old_landline"]["attempts"], 0,
                         "a reclassification is not a send attempt")
        self.assertEqual(leads["lead_old_foreign"]["status"], "NOT_READY")
        self.assertEqual(leads["lead_old_sent"]["status"], STATUS_SENT)

    def test_channel_marker_detection(self) -> None:
        self.assertTrue(no_whatsapp_marker("Phone number shared via url is invalid."))
        self.assertTrue(no_whatsapp_marker("this number is NOT on WhatsApp"))
        self.assertFalse(no_whatsapp_marker("No chat/compose box appeared within 120s"))
        self.assertFalse(no_whatsapp_marker(""))
        self.assertTrue(
            is_no_whatsapp_reason("No WhatsApp account for this number — no compose box")
        )
        self.assertFalse(
            is_no_whatsapp_reason("No chat/compose box appeared within 120s (WhatsApp Web did not load)")
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
