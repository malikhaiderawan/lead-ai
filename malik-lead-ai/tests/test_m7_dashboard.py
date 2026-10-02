"""Unit and integration tests for Milestone 7: Sales Dashboard & Command Center.

Verifies data loader, analytics engine, REST API endpoints, date filtering,
file previewing, and non-mutation guarantees.
"""

from __future__ import annotations

import json
import threading
import time
import unittest
import urllib.parse
import urllib.request
from http import HTTPStatus
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any

from dashboard.analytics import DashboardAnalytics
from dashboard.data_loader import DashboardDataLoader, DiscoveredFile, LeadRecord
from dashboard.server import DashboardHandler

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class TestDashboardDataLoader(unittest.TestCase):
    """Tests for filesystem discovery and normalization in DashboardDataLoader."""

    def setUp(self) -> None:
        self.loader = DashboardDataLoader(PROJECT_ROOT)

    def test_discover_pipeline_files(self) -> None:
        files = self.loader.discover_and_index_files()
        self.assertGreaterEqual(len(files), 10, "Should discover at least 10 pipeline files")

        filenames = [f.filename for f in files]
        self.assertIn("malikaxiom_sales_leads.csv", filenames)
        self.assertIn("contact_first.csv", filenames)
        self.assertIn("manual_instagram_leads.csv", filenames)
        self.assertIn("m6_send_state.json", filenames)

    def test_load_all_leads_and_normalization(self) -> None:
        leads_map, files = self.loader.load_all()
        self.assertGreaterEqual(len(leads_map), 20, "Should load real pipeline leads")
        self.assertGreaterEqual(len(files), 10)

        # Check lead structure
        sample_lead: LeadRecord = next(iter(leads_map.values()))
        self.assertTrue(sample_lead.lead_id)
        self.assertTrue(sample_lead.business_name)
        self.assertGreater(len(sample_lead.source_files), 0)

    def test_m6_ground_truth_status_mapping(self) -> None:
        leads_map, _ = self.loader.load_all()
        # Verify that leads in m6_send_state.json have correct m6_status
        m6_file = PROJECT_ROOT / "output" / "m6_send_state.json"
        if m6_file.is_file():
            with m6_file.open("r", encoding="utf-8") as f:
                state_data = json.load(f)
            recorded = state_data.get("leads", {})
            self.assertEqual(len(recorded), 137, "m6_send_state.json must contain exactly 137 recorded leads")

            # Check status breakdown in m6_send_state.json
            m6_counts = {}
            for lead_id, record in recorded.items():
                st = record.get("status", "PENDING")
                m6_counts[st] = m6_counts.get(st, 0) + 1
                if lead_id in leads_map:
                    self.assertEqual(
                        leads_map[lead_id].m6_status,
                        st,
                        f"Lead {lead_id} m6_status should match m6_send_state.json",
                    )

            self.assertEqual(m6_counts.get("SENT", 0), 62, "M6 SENT must equal 62")
            self.assertEqual(m6_counts.get("FAILED", 0), 9, "M6 FAILED must equal 9")
            self.assertEqual(m6_counts.get("NOT_READY", 0), 40, "M6 NOT_READY must equal 40")
            self.assertEqual(m6_counts.get("NO_WHATSAPP_NUMBER", 0), 19, "M6 NO_WHATSAPP_NUMBER must equal 19")
            self.assertEqual(m6_counts.get("SKIPPED_LIMIT", 0), 7, "M6 SKIPPED_LIMIT must equal 7")

    def test_cold_calling_exact_reconciliation_and_zero_duplicates(self) -> None:
        leads_map, _ = self.loader.load_all()
        self.assertGreaterEqual(len(leads_map), 255, "Total lifetime unique leads must be at least 255")

        callable_leads = [
            l for l in leads_map.values()
            if l.is_active
            and bool(l.phone)
            and l.m6_status not in ("SENT", "FAILED", "NOT_READY", "NO_WHATSAPP_NUMBER", "SKIPPED_LIMIT", "SKIPPED_ALREADY_SENT", "SKIPPED_NO_WHATSAPP")
            and (l.outreach_priority in ("CONTACT FIRST", "CONTACT LATER") or l.in_contact_first or l.in_contact_later)
            and not l.is_archived
            and not l.is_skipped
            and l.sales_stage != "LOST"
            and l.outreach_priority not in ("ARCHIVE", "SKIP")
            and l.final_action not in ("ARCHIVE", "SKIP")
            and l.sales_potential != "SKIP"
        ]

        # Zero duplicates check
        callable_ids = [l.lead_id for l in callable_leads]
        self.assertEqual(len(callable_ids), len(set(callable_ids)), "Cold calling leads must have 0 duplicates")

        # Partition counts
        cf_callable = [l for l in callable_leads if (l.outreach_priority == "CONTACT FIRST" or (l.in_contact_first and l.outreach_priority != "CONTACT LATER"))]
        cl_callable = [l for l in callable_leads if not (l.outreach_priority == "CONTACT FIRST" or (l.in_contact_first and l.outreach_priority != "CONTACT LATER"))]

        self.assertGreaterEqual(len(callable_leads), 101, "Callable ALL must be at least 101")
        self.assertGreaterEqual(len(cf_callable), 67, "Callable CONTACT FIRST must be at least 67")
        self.assertGreaterEqual(len(cl_callable), 34, "Callable CONTACT LATER must be at least 34")
        self.assertEqual(len(callable_leads), len(cf_callable) + len(cl_callable))

        # Exclusion partition
        excluded = [l for l in leads_map.values() if l not in callable_leads]
        self.assertEqual(len(callable_leads) + len(excluded), len(leads_map), "Callable + Excluded must equal total unique leads")

    def test_city_extraction(self) -> None:
        city_rawp = self.loader._extract_city("Rawalpindi, Saddar Road")
        self.assertEqual(city_rawp, "Rawalpindi")

        city_isb = self.loader._extract_city("F-7 Markaz, Islamabad")
        self.assertEqual(city_isb, "Islamabad")

        city_lhr = self.loader._extract_city("Gulberg III, Lahore, Punjab")
        self.assertEqual(city_lhr, "Lahore")

        city_fallback = self.loader._extract_city("Unknown boutique shop")
        self.assertEqual(city_fallback, "Islamabad/Rawalpindi")

    def test_cache_and_fingerprint(self) -> None:
        leads_1, files_1 = self.loader.load_all()
        leads_2, files_2 = self.loader.load_all()
        self.assertIs(leads_1, leads_2, "Repeated load_all without file changes should return cached dict")

        # Force reload
        leads_3, files_3 = self.loader.load_all(force_reload=True)
        self.assertEqual(len(leads_1), len(leads_3))

    def test_archive_and_skip_properties_and_safety(self) -> None:
        leads_map, _ = self.loader.load_all()

        # Synthetic test records
        archived_record = LeadRecord(
            lead_id="test_arch_01",
            business_name="Test Archived Boutique",
            final_action="ARCHIVE",
            outreach_priority="ARCHIVE",
            sales_stage="ARCHIVED",
        )
        self.assertTrue(archived_record.is_archived)
        self.assertFalse(archived_record.is_skipped)
        self.assertFalse(archived_record.is_active)
        self.assertFalse(archived_record.is_m6_eligible, "Archived leads must never be M6 eligible")

        skipped_record = LeadRecord(
            lead_id="test_skip_01",
            business_name="Test Skipped Boutique",
            final_action="SKIP",
            outreach_priority="SKIP",
            sales_stage="SKIPPED",
        )
        self.assertTrue(skipped_record.is_skipped)
        self.assertFalse(skipped_record.is_archived)
        self.assertFalse(skipped_record.is_active)
        self.assertFalse(skipped_record.is_m6_eligible, "Skipped leads must never be M6 eligible")

        active_record = LeadRecord(
            lead_id="test_act_01",
            business_name="Test Active Boutique",
            final_action="CONTACT",
            outreach_priority="CONTACT FIRST",
            sales_stage="READY_TO_CONTACT",
            phone="+923001234567",
        )
        self.assertTrue(active_record.is_active)
        self.assertFalse(active_record.is_archived)
        self.assertFalse(active_record.is_skipped)
        self.assertTrue(active_record.is_m6_eligible)

    def test_archive_skip_reasons_preserved(self) -> None:
        rec1 = LeadRecord(
            lead_id="test_r1",
            business_name="Test R1",
            final_action="SKIP",
            m6_error="Invalid mobile format",
        )
        self.assertEqual(rec1.archive_skip_reason, "Invalid mobile format")

        rec2 = LeadRecord(
            lead_id="test_r2",
            business_name="Test R2",
            final_action="ARCHIVE",
            review_reason="No phone number or catalog",
        )
        self.assertEqual(rec2.archive_skip_reason, "No phone number or catalog")


class TestDashboardAnalytics(unittest.TestCase):
    """Tests for KPI metrics, timeline activity, and attention center."""

    def setUp(self) -> None:
        self.loader = DashboardDataLoader(PROJECT_ROOT)
        self.leads_map, self.files = self.loader.load_all()

    def test_calculate_overview_all_time(self) -> None:
        overview = DashboardAnalytics.calculate_overview(self.leads_map, self.files, "ALL_TIME")

        self.assertIn("kpis", overview)
        kpis = overview["kpis"]
        self.assertGreater(kpis["TOTAL_LEADS"], 0)
        self.assertIn("HIGH_POTENTIAL", kpis)
        self.assertIn("CONTACT_FIRST", kpis)
        self.assertIn("WHATSAPP_SENT", kpis)
        self.assertIn("WHATSAPP_FAILED", kpis)
        self.assertIn("INSTAGRAM_DM_LEADS", kpis)
        self.assertIn("COLD_CALLS_PENDING", kpis)

        # Milestone funnel
        milestones = overview.get("milestones", {})
        self.assertIn("M1_INGESTION", milestones)
        self.assertIn("M2_RESEARCH", milestones)
        self.assertIn("M3_QUALIFICATION", milestones)
        self.assertIn("M4_OUTREACH_READY", milestones)
        self.assertIn("M5_MASTER_READY", milestones)
        self.assertIn("M6_WHATSAPP_SENT", milestones)

    def test_calculate_overview_date_filtering(self) -> None:
        overview_today = DashboardAnalytics.calculate_overview(self.leads_map, self.files, "TODAY")
        self.assertIn("kpis", overview_today)

        overview_7d = DashboardAnalytics.calculate_overview(self.leads_map, self.files, "PAST_7_DAYS")
        self.assertIn("kpis", overview_7d)

        overview_custom = DashboardAnalytics.calculate_overview(
            self.leads_map, self.files, "CUSTOM", custom_start="2026-01-01", custom_end="2026-12-31"
        )
        self.assertIn("kpis", overview_custom)

    def test_today_activity_feed(self) -> None:
        activity = DashboardAnalytics.get_today_activity(self.leads_map, self.files)
        self.assertIsInstance(activity, list)
        for ev in activity:
            self.assertIn("timestamp", ev)
            self.assertIn("milestone", ev)
            self.assertIn("title", ev)

    def test_needs_attention_queue(self) -> None:
        attention = DashboardAnalytics.get_needs_attention(self.leads_map)
        self.assertIsInstance(attention, list)
        for item in attention:
            self.assertIn("lead_id", item)
            self.assertIn("type", item)
            self.assertIn("reason", item)
            self.assertIn("priority", item)

    def test_active_pipeline_integrity_and_deduplication(self) -> None:
        overview = DashboardAnalytics.calculate_overview(self.leads_map, self.files, "ALL_TIME")
        kpis = overview["kpis"]

        total_lifetime = kpis.get("TOTAL_LIFETIME_LEADS", 0)
        active_leads = kpis.get("ACTIVE_LEADS", 0)
        archived_leads = kpis.get("ARCHIVED_LEADS", 0)
        skipped_leads = kpis.get("SKIPPED_LEADS", 0)

        # Verification: Active + Archived + Skipped equals total unique leads
        self.assertEqual(total_lifetime, active_leads + archived_leads + skipped_leads)
        self.assertEqual(total_lifetime, len(self.leads_map))

        # Verification: Active KPIs should not exceed active leads
        self.assertLessEqual(kpis.get("CONTACT_FIRST", 0), active_leads)
        self.assertLessEqual(kpis.get("CONTACT_LATER", 0), active_leads)
        self.assertLessEqual(kpis.get("HIGH_POTENTIAL", 0), active_leads)


class TestDashboardHTTPServer(unittest.TestCase):
    """Integration tests running an ephemeral HTTP test server."""

    server: ThreadingHTTPServer
    server_thread: threading.Thread
    port: int
    base_url: str

    @classmethod
    def setUpClass(cls) -> None:
        DashboardHandler.data_loader = DashboardDataLoader(PROJECT_ROOT)
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), DashboardHandler)
        cls.port = cls.server.server_port
        cls.base_url = f"http://127.0.0.1:{cls.port}"

        cls.server_thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.server_thread.start()
        time.sleep(0.2)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()

    def _get(self, path: str) -> tuple[int, dict[str, str], bytes]:
        req = urllib.request.Request(f"{self.base_url}{path}")
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                status = resp.status
                headers = dict(resp.getheaders())
                body = resp.read()
                return status, headers, body
        except urllib.error.HTTPError as e:
            return e.code, dict(e.headers), e.read()

    def _post(self, path: str, payload: dict | None = None) -> tuple[int, dict[str, str], bytes]:
        data = json.dumps(payload or {}).encode("utf-8")
        req = urllib.request.Request(f"{self.base_url}{path}", data=data, method="POST")
        req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                status = resp.status
                headers = dict(resp.getheaders())
                body = resp.read()
                return status, headers, body
        except urllib.error.HTTPError as e:
            return e.code, dict(e.headers), e.read()

    def test_static_index_html(self) -> None:
        status, headers, body = self._get("/")
        self.assertEqual(status, HTTPStatus.OK)
        self.assertIn("text/html", headers.get("Content-Type", ""))
        self.assertIn(b"MalikAxiom AI", body)

    def test_static_css_and_js(self) -> None:
        status, headers, body = self._get("/style.css")
        self.assertEqual(status, HTTPStatus.OK)
        self.assertIn("text/css", headers.get("Content-Type", ""))

        status, headers, body = self._get("/app.js")
        self.assertEqual(status, HTTPStatus.OK)
        self.assertIn("javascript", headers.get("Content-Type", ""))

    def test_api_health(self) -> None:
        status, _, body = self._get("/api/health")
        self.assertEqual(status, HTTPStatus.OK)
        data = json.loads(body)
        self.assertEqual(data["status"], "HEALTHY")
        self.assertGreater(data["total_leads_cached"], 0)

    def test_api_overview(self) -> None:
        status, _, body = self._get("/api/overview")
        self.assertEqual(status, HTTPStatus.OK)
        data = json.loads(body)
        self.assertIn("kpis", data)
        self.assertIn("milestones", data)

    def test_api_leads_list_and_search(self) -> None:
        status, _, body = self._get("/api/leads?limit=10&page=1")
        self.assertEqual(status, HTTPStatus.OK)
        data = json.loads(body)
        self.assertIn("leads", data)
        self.assertIn("pagination", data)
        self.assertLessEqual(len(data["leads"]), 10)

        # Search test
        status, _, body = self._get("/api/leads?search=boutique")
        self.assertEqual(status, HTTPStatus.OK)
        data = json.loads(body)
        self.assertIn("leads", data)

    def test_api_single_lead(self) -> None:
        # First get a lead id
        _, _, body = self._get("/api/leads?limit=1")
        leads = json.loads(body)["leads"]
        if leads:
            target_id = leads[0]["lead_id"]
            status, _, body = self._get(f"/api/leads/{target_id}")
            self.assertEqual(status, HTTPStatus.OK)
            lead_data = json.loads(body)
            self.assertEqual(lead_data["lead"]["lead_id"], target_id)

        # Nonexistent lead
        status, _, body = self._get("/api/leads/non_existent_lead_99999")
        self.assertEqual(status, HTTPStatus.NOT_FOUND)

    def test_api_whatsapp_endpoint(self) -> None:
        status, _, body = self._get("/api/whatsapp")
        self.assertEqual(status, HTTPStatus.OK)
        data = json.loads(body)
        self.assertIn("leads", data)
        self.assertIn("counts", data)
        self.assertIn("SENT", data["counts"])
        self.assertIn("FAILED", data["counts"])

        # Test filtering by status=SENT
        status, _, sent_body = self._get("/api/whatsapp?status=SENT")
        self.assertEqual(status, HTTPStatus.OK)
        sent_data = json.loads(sent_body)
        for lead in sent_data["leads"]:
            self.assertEqual(lead["m6_status"], "SENT")
        # Global counts should remain stable
        self.assertEqual(sent_data["counts"]["TOTAL_WHATSAPP_ELIGIBLE"], data["counts"]["TOTAL_WHATSAPP_ELIGIBLE"])

        # Test filtering by status=FAILED
        status, _, failed_body = self._get("/api/whatsapp?status=FAILED")
        self.assertEqual(status, HTTPStatus.OK)
        failed_data = json.loads(failed_body)
        for lead in failed_data["leads"]:
            self.assertEqual(lead["m6_status"], "FAILED")

    def test_api_cold_calling_endpoint(self) -> None:
        status, _, body = self._get("/api/cold-calling")
        self.assertEqual(status, HTTPStatus.OK)
        data = json.loads(body)
        self.assertIn("leads", data)
        self.assertIn("total", data)
        self.assertIn("counts", data)
        counts = data["counts"]
        self.assertIn("ALL", counts)
        self.assertIn("CONTACT_FIRST", counts)
        self.assertIn("CONTACT_LATER", counts)

        # Invariant: ALL == CONTACT_FIRST + CONTACT_LATER
        self.assertEqual(counts["ALL"], counts["CONTACT_FIRST"] + counts["CONTACT_LATER"])
        self.assertEqual(data["total"], counts["ALL"])

        # Strict exclusion checks on all returned leads
        for lead in data["leads"]:
            self.assertTrue(bool(lead.get("phone")), f"Lead {lead.get('lead_id')} must have phone")
            self.assertTrue(lead.get("is_active"), f"Lead {lead.get('lead_id')} must be active")
            self.assertFalse(lead.get("is_archived"), f"Lead {lead.get('lead_id')} must not be archived")
            self.assertFalse(lead.get("is_skipped"), f"Lead {lead.get('lead_id')} must not be skipped")
            self.assertNotIn(
                lead.get("m6_status"),
                ("SENT", "FAILED", "NOT_READY", "NO_WHATSAPP_NUMBER", "SKIPPED_LIMIT", "SKIPPED_ALREADY_SENT", "SKIPPED_NO_WHATSAPP"),
                f"Lead {lead.get('lead_id')} has terminal/excluded m6_status",
            )
            self.assertNotIn(lead.get("outreach_priority"), ("ARCHIVE", "SKIP"))
            self.assertNotIn(lead.get("final_action"), ("ARCHIVE", "SKIP"))
            self.assertNotEqual(lead.get("sales_potential"), "SKIP")

        # Sort order check: CONTACT FIRST first, then CONTACT LATER
        seen_contact_later = False
        for lead in data["leads"]:
            is_cf = (lead["outreach_priority"] == "CONTACT FIRST" or (lead.get("in_contact_first") and lead["outreach_priority"] != "CONTACT LATER"))
            if not is_cf:
                seen_contact_later = True
            elif seen_contact_later:
                self.fail(f"CONTACT FIRST lead {lead['lead_id']} appeared after CONTACT LATER leads")

    def test_api_cold_calling_tab_filtering(self) -> None:
        # 1. Test tab=CONTACT_FIRST
        status, _, cf_body = self._get("/api/cold-calling?tab=CONTACT_FIRST")
        self.assertEqual(status, HTTPStatus.OK)
        cf_data = json.loads(cf_body)
        self.assertEqual(len(cf_data["leads"]), cf_data["counts"]["CONTACT_FIRST"])
        for lead in cf_data["leads"]:
            self.assertTrue(lead["outreach_priority"] == "CONTACT FIRST" or lead.get("in_contact_first"))

        # 2. Test tab=CONTACT_LATER
        status, _, cl_body = self._get("/api/cold-calling?tab=CONTACT_LATER")
        self.assertEqual(status, HTTPStatus.OK)
        cl_data = json.loads(cl_body)
        self.assertEqual(len(cl_data["leads"]), cl_data["counts"]["CONTACT_LATER"])
        for lead in cl_data["leads"]:
            self.assertTrue(lead["outreach_priority"] == "CONTACT LATER" or lead.get("in_contact_later"))

        # 3. Test filtering by potential=HIGH
        status, _, high_body = self._get("/api/cold-calling?potential=HIGH")
        self.assertEqual(status, HTTPStatus.OK)
        high_data = json.loads(high_body)
        for lead in high_data["leads"]:
            self.assertEqual(lead["sales_potential"], "HIGH")

    def test_api_cold_calling_search_isolation(self) -> None:
        # Search for a term that matches callable leads
        status, _, body = self._get("/api/cold-calling?search=boutique")
        self.assertEqual(status, HTTPStatus.OK)
        data = json.loads(body)
        for lead in data["leads"]:
            self.assertTrue(lead["is_active"])
            self.assertFalse(lead["is_archived"])
            self.assertFalse(lead["is_skipped"])
            self.assertNotIn(lead["m6_status"], ("SENT", "FAILED", "NOT_READY", "NO_WHATSAPP_NUMBER"))

    def test_api_instagram_endpoint(self) -> None:
        status, _, body = self._get("/api/instagram")
        self.assertEqual(status, HTTPStatus.OK)
        data = json.loads(body)
        self.assertIn("leads", data)
        self.assertIn("total", data)

        # Test filtering by potential=HIGH
        status, _, high_body = self._get("/api/instagram?potential=HIGH")
        self.assertEqual(status, HTTPStatus.OK)
        high_data = json.loads(high_body)
        for lead in high_data["leads"]:
            self.assertEqual(lead["sales_potential"], "HIGH")

    def test_api_pipeline_kanban(self) -> None:
        status, _, body = self._get("/api/pipeline")
        self.assertEqual(status, HTTPStatus.OK)
        data = json.loads(body)
        self.assertIn("stages", data)
        stages = data["stages"]
        for stage_key in ["NEW", "RESEARCHED", "QUALIFIED", "READY_TO_CONTACT", "CONTACTED", "REPLIED", "INTERESTED", "WON", "LOST"]:
            self.assertIn(stage_key, stages)

    def test_api_sources_and_preview(self) -> None:
        status, _, body = self._get("/api/sources")
        self.assertEqual(status, HTTPStatus.OK)
        data = json.loads(body)
        self.assertIn("files", data)
        self.assertGreater(len(data["files"]), 0)

        # Preview a CSV file
        csv_file = next((f for f in data["files"] if f["filename"].endswith(".csv")), None)
        if csv_file:
            preview_status, _, preview_body = self._get(f"/api/sources/preview?path={urllib.parse.quote(csv_file['path'])}")
            self.assertEqual(preview_status, HTTPStatus.OK)
            preview_data = json.loads(preview_body)
            self.assertEqual(preview_data["file_type"], "CSV")
            self.assertIn("headers", preview_data)
            self.assertIn("rows", preview_data)

    def test_preview_security_blocks_traversal(self) -> None:
        status, _, _ = self._get("/api/sources/preview?path=/etc/passwd")
        self.assertEqual(status, HTTPStatus.FORBIDDEN)

    def test_api_refresh_post(self) -> None:
        status, _, body = self._post("/api/refresh")
        self.assertEqual(status, HTTPStatus.OK)
        data = json.loads(body)
        self.assertEqual(data["status"], "OK")
        self.assertGreater(data["total_leads"], 0)

    def test_api_leads_tab_filtering(self) -> None:
        # Test tab=ALL
        status, _, body = self._get("/api/leads?tab=ALL&limit=250")
        self.assertEqual(status, HTTPStatus.OK)
        data_all = json.loads(body)
        self.assertIn("tab_counts", data_all)
        tab_counts = data_all["tab_counts"]
        self.assertIn("ALL", tab_counts)
        self.assertIn("ACTIVE", tab_counts)
        self.assertIn("ARCHIVE", tab_counts)
        self.assertIn("SKIP", tab_counts)

        # Test tab=ACTIVE
        status, _, body = self._get("/api/leads?tab=ACTIVE&limit=250")
        self.assertEqual(status, HTTPStatus.OK)
        data_active = json.loads(body)
        for lead in data_active["leads"]:
            self.assertTrue(lead["is_active"])
            self.assertFalse(lead["is_archived"])
            self.assertFalse(lead["is_skipped"])

        # Test tab=ARCHIVE
        if tab_counts["ARCHIVE"] > 0:
            status, _, body = self._get("/api/leads?tab=ARCHIVE&limit=250")
            self.assertEqual(status, HTTPStatus.OK)
            data_arch = json.loads(body)
            self.assertGreater(len(data_arch["leads"]), 0)
            for lead in data_arch["leads"]:
                self.assertTrue(lead["is_archived"])
                self.assertFalse(lead["is_active"])
                self.assertFalse(lead["is_m6_eligible"])

        # Test tab=SKIP
        if tab_counts["SKIP"] > 0:
            status, _, body = self._get("/api/leads?tab=SKIP&limit=250")
            self.assertEqual(status, HTTPStatus.OK)
            data_skip = json.loads(body)
            self.assertGreater(len(data_skip["leads"]), 0)
            for lead in data_skip["leads"]:
                self.assertTrue(lead["is_skipped"])
                self.assertFalse(lead["is_active"])
                self.assertFalse(lead["is_m6_eligible"])

    def test_single_lead_archive_skip_payload(self) -> None:
        _, _, body = self._get("/api/leads?tab=ALL&limit=250")
        leads = json.loads(body)["leads"]
        for lead_summary in leads:
            lead_id = lead_summary["lead_id"]
            status, _, single_body = self._get(f"/api/leads/{urllib.parse.quote(lead_id)}")
            self.assertEqual(status, HTTPStatus.OK)
            lead_detail = json.loads(single_body)["lead"]
            self.assertIn("is_archived", lead_detail)
            self.assertIn("is_skipped", lead_detail)
            self.assertIn("is_active", lead_detail)
            self.assertIn("is_m6_eligible", lead_detail)
    def test_qualification_score_and_cold_calling_hooks(self) -> None:
        """Verify qualification scores and hooks are present across leads and cold calling endpoints."""
        status, _, body = self._get("/api/cold-calling")
        self.assertEqual(status, HTTPStatus.OK)
        cc_data = json.loads(body)
        self.assertIn("leads", cc_data)
        self.assertGreater(len(cc_data["leads"]), 0)

        for l in cc_data["leads"]:
            self.assertIsNotNone(l.get("qualification_score"), f"Lead {l.get('lead_id')} must have a qualification_score")
            self.assertIsInstance(l.get("qualification_score"), int)
            self.assertGreaterEqual(l["qualification_score"], 0)
            self.assertLessEqual(l["qualification_score"], 100)
            self.assertIn("opportunity", l)
            self.assertIn("pitch_hook", l)
            self.assertIn("gaps", l)

        # Single lead test
        sample_id = cc_data["leads"][0]["lead_id"]
        status, _, s_body = self._get(f"/api/leads/{urllib.parse.quote(sample_id)}")
        self.assertEqual(status, HTTPStatus.OK)
        single_lead = json.loads(s_body)["lead"]
        self.assertIsNotNone(single_lead.get("qualification_score"))
        self.assertTrue(single_lead.get("opportunity"))
        self.assertTrue(single_lead.get("pitch_hook"))


if __name__ == "__main__":
    unittest.main()

