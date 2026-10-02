"""M7 Sales Dashboard HTTP Server & REST API.

Standard library HTTP server with zero database dependency.
Serves the MalikAxiom SaaS command center UI and REST endpoints.
"""

from __future__ import annotations

import csv
import json
import logging
import mimetypes
import os
import sys
import threading
import urllib.parse
from dataclasses import asdict
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from .analytics import DashboardAnalytics
from .data_loader import DashboardDataLoader, LeadRecord

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).resolve().parent / "static"


class DashboardHandler(BaseHTTPRequestHandler):
    """Handles REST API and static asset requests for the M7 Sales Dashboard."""

    data_loader: DashboardDataLoader = DashboardDataLoader()

    def log_message(self, format: str, *args: Any) -> None:
        # Suppress routine 200/304 logs from flooding console
        if len(args) > 1 and str(args[1]) in ("200", "304") and not logger.isEnabledFor(logging.DEBUG):
            return
        logger.info("%s - %s", self.address_string(), format % args)

    def do_GET(self) -> None:
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        query = urllib.parse.parse_qs(parsed_url.query)

        # Route API endpoints
        if path.startswith("/api/"):
            self._handle_api(path, query)
            return

        # Route static files
        self._serve_static(path)

    def do_POST(self) -> None:
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path

        if path == "/api/refresh":
            leads, files = self.data_loader.load_all(force_reload=True)
            self._send_json({
                "status": "OK",
                "message": "Data refreshed from filesystem",
                "total_leads": len(leads),
                "total_files": len(files),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            return

        self._send_error(HTTPStatus.NOT_FOUND, "Endpoint not found")

    def _handle_api(self, path: str, query: dict[str, list[str]]) -> None:
        leads_map, files = self.data_loader.load_all()

        date_filter = query.get("date_filter", ["ALL_TIME"])[0]
        custom_start = query.get("custom_start", [""])[0]
        custom_end = query.get("custom_end", [""])[0]

        if path == "/api/overview":
            overview = DashboardAnalytics.calculate_overview(
                leads_map, files, date_filter, custom_start, custom_end
            )
            overview["last_scan_time"] = self.data_loader._last_scan_time
            self._send_json(overview)
            return

        elif path == "/api/activity/today":
            events = DashboardAnalytics.get_today_activity(leads_map, files)
            self._send_json({"events": events, "count": len(events)})
            return

        elif path == "/api/attention":
            items = DashboardAnalytics.get_needs_attention(leads_map)
            self._send_json({"items": items, "count": len(items)})
            return

        elif path == "/api/leads":
            self._handle_leads_list(leads_map, query)
            return

        elif path.startswith("/api/leads/"):
            raw_id = path.removeprefix("/api/leads/").strip()
            lead_id = urllib.parse.unquote(raw_id)
            self._handle_single_lead(leads_map, lead_id)
            return

        elif path == "/api/whatsapp":
            self._handle_whatsapp_page(leads_map, query)
            return

        elif path == "/api/cold-calling":
            self._handle_cold_calling_page(leads_map, query)
            return

        elif path == "/api/instagram":
            self._handle_instagram_page(leads_map, query)
            return

        elif path == "/api/pipeline":
            self._handle_pipeline_kanban(leads_map, query)
            return

        elif path == "/api/sources":
            files_data = [
                {
                    "path": f.path,
                    "filename": f.filename,
                    "relative_path": f.relative_path,
                    "file_type": f.file_type,
                    "milestone": f.milestone,
                    "scenario": f.scenario,
                    "size_bytes": f.size_bytes,
                    "size_display": f"{f.size_bytes / 1024:.1f} KB" if f.size_bytes >= 1024 else f"{f.size_bytes} B",
                    "modified_time": f.modified_time,
                    "record_count": f.record_count,
                    "status": f.status,
                    "error_message": f.error_message,
                    "discovered_date": f.discovered_date,
                }
                for f in sorted(files, key=lambda x: x.modified_epoch, reverse=True)
            ]
            self._send_json({"files": files_data, "total_files": len(files)})
            return

        elif path == "/api/sources/preview":
            raw_path = query.get("path", [""])[0]
            self._handle_source_preview(raw_path)
            return

        elif path == "/api/health":
            self._send_json({
                "status": "HEALTHY",
                "version": "1.0.0",
                "system": "MalikAxiom Lead AI M7 Command Center",
                "total_leads_cached": len(leads_map),
                "total_files_discovered": len(files),
                "last_scan_time": self.data_loader._last_scan_time,
                "project_root": str(self.data_loader.project_root),
            })
            return

        self._send_error(HTTPStatus.NOT_FOUND, f"API endpoint {path} not found")

    def _handle_leads_list(self, leads_map: dict[str, LeadRecord], query: dict[str, list[str]]) -> None:
        search = query.get("search", [""])[0].strip().lower()
        channel = query.get("channel", [""])[0].strip()
        potential = query.get("potential", [""])[0].strip()
        priority = query.get("priority", [""])[0].strip()
        status = query.get("status", [""])[0].strip()
        stage = query.get("stage", [""])[0].strip()
        city = query.get("city", [""])[0].strip()
        milestone = query.get("milestone", [""])[0].strip()
        tab = query.get("tab", query.get("filter", [""]))[0].strip().upper()

        date_filter = query.get("date_filter", ["ALL_TIME"])[0]
        custom_start = query.get("custom_start", [""])[0]
        custom_end = query.get("custom_end", [""])[0]

        page = max(1, int(query.get("page", [1])[0]))
        limit = min(200, max(10, int(query.get("limit", [50])[0])))
        sort_by = query.get("sort_by", ["discovered_at"])[0]
        sort_dir = query.get("sort_dir", ["desc"])[0].lower()

        filtered: list[LeadRecord] = []
        for lead in leads_map.values():
            if not DashboardAnalytics._lead_matches_date_range(lead, date_filter, custom_start, custom_end):
                continue

            # Tab / Preset filter
            if tab and tab not in ("ALL", ""):
                if tab == "ACTIVE" and not lead.is_active:
                    continue
                elif tab in ("CONTACT FIRST", "CONTACT_FIRST") and not (lead.outreach_priority == "CONTACT FIRST" and lead.is_active):
                    continue
                elif tab in ("CONTACT LATER", "CONTACT_LATER") and not (lead.outreach_priority == "CONTACT LATER" and lead.is_active):
                    continue
                elif tab in ("HIGH POTENTIAL", "HIGH_POTENTIAL", "HIGH") and not (lead.sales_potential == "HIGH" and lead.is_active):
                    continue
                elif tab == "SENT" and lead.m6_status != "SENT":
                    continue
                elif tab == "FAILED" and lead.m6_status != "FAILED":
                    continue
                elif tab in ("NOT READY", "NOT_READY") and lead.m6_status not in ("NOT_READY", "NO_WHATSAPP_NUMBER"):
                    continue
                elif tab in ("ARCHIVE", "ARCHIVED") and not lead.is_archived:
                    continue
                elif tab in ("SKIP", "SKIPPED") and not lead.is_skipped:
                    continue

            if search:
                haystack = f"{lead.business_name} {lead.lead_id} {lead.phone} {lead.whatsapp} {lead.email} {lead.location} {lead.city} {lead.instagram} {lead.primary_service} {lead.why_this_lead} {lead.archive_skip_reason} {lead.review_reason} {lead.duplicate_reason} {lead.m6_error} {lead.source_file}".lower()
                if search not in haystack:
                    continue

            if channel and lead.outreach_channel.lower() != channel.lower():
                continue
            if potential and lead.sales_potential.upper() != potential.upper():
                continue
            
            # Priority filtering
            if priority:
                if priority.upper() in ("ARCHIVE", "ARCHIVED"):
                    if not lead.is_archived:
                        continue
                elif priority.upper() in ("SKIP", "SKIPPED"):
                    if not lead.is_skipped:
                        continue
                elif lead.outreach_priority.upper() != priority.upper():
                    continue

            # Status filtering
            if status:
                if status.upper() in ("ARCHIVE", "ARCHIVED"):
                    if not lead.is_archived:
                        continue
                elif status.upper() in ("SKIP", "SKIPPED"):
                    if not lead.is_skipped:
                        continue
                elif lead.m6_status.upper() != status.upper():
                    continue

            # Stage filtering
            if stage:
                if stage.upper() in ("ARCHIVE", "ARCHIVED"):
                    if not (lead.is_archived or lead.sales_stage == "ARCHIVED"):
                        continue
                elif stage.upper() in ("SKIP", "SKIPPED"):
                    if not (lead.is_skipped or lead.sales_stage == "SKIPPED"):
                        continue
                elif lead.sales_stage.upper() != stage.upper():
                    continue

            if city and lead.city.lower() != city.lower():
                continue

            if milestone:
                if milestone == "M5_MASTER" and not lead.in_master:
                    continue
                elif milestone == "M5_CONTACT_FIRST" and not (lead.in_contact_first or lead.outreach_priority == "CONTACT FIRST"):
                    continue
                elif milestone == "M5_CONTACT_LATER" and not (lead.in_contact_later or lead.outreach_priority == "CONTACT LATER"):
                    continue
                elif milestone == "M5_INSTAGRAM" and not lead.in_manual_instagram:
                    continue
                elif milestone == "M6_WHATSAPP" and not (lead.m6_status != "PENDING" or lead.m6_recipient):
                    continue

            filtered.append(lead)

        # Sorting
        def sort_key(l: LeadRecord) -> Any:
            val = getattr(l, sort_by, "")
            return (val is not None, str(val).lower())

        filtered.sort(key=sort_key, reverse=(sort_dir == "desc"))

        total_matching = len(filtered)
        total_pages = max(1, (total_matching + limit - 1) // limit)
        start_idx = (page - 1) * limit
        page_leads = filtered[start_idx : start_idx + limit]

        tab_counts = {
            "ALL": len(leads_map),
            "ACTIVE": sum(1 for l in leads_map.values() if l.is_active),
            "CONTACT_FIRST": sum(1 for l in leads_map.values() if l.outreach_priority == "CONTACT FIRST" and l.is_active),
            "CONTACT_LATER": sum(1 for l in leads_map.values() if l.outreach_priority == "CONTACT LATER" and l.is_active),
            "HIGH_POTENTIAL": sum(1 for l in leads_map.values() if l.sales_potential == "HIGH" and l.is_active),
            "SENT": sum(1 for l in leads_map.values() if l.m6_status == "SENT"),
            "FAILED": sum(1 for l in leads_map.values() if l.m6_status == "FAILED"),
            "NOT_READY": sum(1 for l in leads_map.values() if l.m6_status in ("NOT_READY", "NO_WHATSAPP_NUMBER")),
            "ARCHIVE": sum(1 for l in leads_map.values() if l.is_archived),
            "SKIP": sum(1 for l in leads_map.values() if l.is_skipped),
        }

        def lead_to_dict(l: LeadRecord) -> dict[str, Any]:
            d = asdict(l)
            d["is_archived"] = l.is_archived
            d["is_skipped"] = l.is_skipped
            d["is_active"] = l.is_active
            d["is_m6_eligible"] = l.is_m6_eligible
            d["archive_skip_reason"] = l.archive_skip_reason
            d["opportunity"] = l.opportunity
            d["gaps"] = l.gaps
            d["pitch_hook"] = l.pitch_hook
            d["source_files"] = l.source_files
            return d

        self._send_json({
            "leads": [lead_to_dict(l) for l in page_leads],
            "tab_counts": tab_counts,
            "pagination": {
                "page": page,
                "limit": limit,
                "total_matching": total_matching,
                "total_pages": total_pages,
            },
        })

    def _handle_single_lead(self, leads_map: dict[str, LeadRecord], lead_id: str) -> None:
        def lead_to_dict(l: LeadRecord) -> dict[str, Any]:
            d = asdict(l)
            d["is_archived"] = l.is_archived
            d["is_skipped"] = l.is_skipped
            d["is_active"] = l.is_active
            d["is_m6_eligible"] = l.is_m6_eligible
            d["archive_skip_reason"] = l.archive_skip_reason
            d["opportunity"] = l.opportunity
            d["gaps"] = l.gaps
            d["pitch_hook"] = l.pitch_hook
            d["source_files"] = l.source_files
            return d

        if lead_id in leads_map:
            self._send_json({"lead": lead_to_dict(leads_map[lead_id])})
            return
        # Try finding by lowercase
        for l in leads_map.values():
            if l.lead_id.lower() == lead_id.lower():
                self._send_json({"lead": lead_to_dict(l)})
                return
        self._send_error(HTTPStatus.NOT_FOUND, f"Lead {lead_id} not found")

    def _handle_whatsapp_page(self, leads_map: dict[str, LeadRecord], query: dict[str, list[str]]) -> None:
        date_filter = query.get("date_filter", ["ALL_TIME"])[0]
        custom_start = query.get("custom_start", [""])[0]
        custom_end = query.get("custom_end", [""])[0]
        status_filter = query.get("status", [""])[0].upper()
        priority_filter = query.get("priority", [""])[0].upper()
        city_filter = query.get("city", [""])[0]
        search = query.get("search", [""])[0].lower()

        # Step 1: Gather ALL WhatsApp-relevant leads in date range to compute accurate summary counts
        wa_all: list[LeadRecord] = []
        for lead in leads_map.values():
            if not DashboardAnalytics._lead_matches_date_range(lead, date_filter, custom_start, custom_end):
                continue
            if not lead.phone and not lead.m6_recipient and not lead.m6_status and lead.outreach_channel != "WhatsApp":
                continue
            wa_all.append(lead)

        counts = {
            "TOTAL_WHATSAPP_ELIGIBLE": len([l for l in wa_all if (l.phone or l.m6_recipient)]),
            "SENT": sum(1 for l in wa_all if l.m6_status == "SENT"),
            "FAILED": sum(1 for l in wa_all if l.m6_status == "FAILED"),
            "PENDING": sum(1 for l in wa_all if l.m6_status in ("PENDING", "")),
            "NO_WHATSAPP_NUMBER": sum(1 for l in wa_all if l.m6_status == "NO_WHATSAPP_NUMBER"),
            "NOT_READY": sum(1 for l in wa_all if l.m6_status in ("NOT_READY", "NO_WHATSAPP_NUMBER")),
            "AWAITING_MANUAL_SEND": sum(1 for l in wa_all if l.m6_status == "AWAITING_MANUAL_SEND"),
            "ARCHIVE": sum(1 for l in wa_all if l.is_archived),
            "SKIP": sum(1 for l in wa_all if l.is_skipped),
        }

        # Step 2: Filter records for the table
        wa_leads: list[dict[str, Any]] = []
        for lead in wa_all:
            if status_filter:
                if status_filter in ("ARCHIVE", "ARCHIVED"):
                    if not lead.is_archived:
                        continue
                elif status_filter in ("SKIP", "SKIPPED"):
                    if not lead.is_skipped:
                        continue
                elif status_filter == "PENDING":
                    if lead.m6_status not in ("PENDING", ""):
                        continue
                elif status_filter == "NOT_READY":
                    if lead.m6_status not in ("NOT_READY", "NO_WHATSAPP_NUMBER"):
                        continue
                elif lead.m6_status.upper() != status_filter:
                    continue

            if priority_filter:
                if priority_filter in ("ARCHIVE", "ARCHIVED"):
                    if not lead.is_archived:
                        continue
                elif priority_filter in ("SKIP", "SKIPPED"):
                    if not lead.is_skipped:
                        continue
                elif lead.outreach_priority.upper() != priority_filter:
                    continue

            if city_filter and lead.city.lower() != city_filter.lower():
                continue

            if search:
                haystack = f"{lead.business_name} {lead.lead_id} {lead.phone} {lead.m6_recipient} {lead.city} {lead.m6_error} {lead.outreach_message} {lead.archive_skip_reason}".lower()
                if search not in haystack:
                    continue

            d = asdict(lead)
            d["is_archived"] = lead.is_archived
            d["is_skipped"] = lead.is_skipped
            d["is_active"] = lead.is_active
            d["is_m6_eligible"] = lead.is_m6_eligible
            d["archive_skip_reason"] = lead.archive_skip_reason
            wa_leads.append(d)

        wa_leads.sort(key=lambda x: (x.get("m6_sent_at") or x.get("m6_last_attempt_at") or ""), reverse=True)

        self._send_json({"leads": wa_leads, "counts": counts, "total": len(wa_leads)})

    def _handle_cold_calling_page(self, leads_map: dict[str, LeadRecord], query: dict[str, list[str]]) -> None:
        date_filter = query.get("date_filter", ["ALL_TIME"])[0]
        custom_start = query.get("custom_start", [""])[0]
        custom_end = query.get("custom_end", [""])[0]
        search = query.get("search", [""])[0].lower().strip()
        raw_tab = query.get("tab", query.get("priority", ["ALL"]))[0].upper().replace(" ", "_")
        potential = query.get("potential", [""])[0].upper()
        city = query.get("city", [""])[0]

        # Step 1: Filter base callable pool (Strictly active, phone verified, CONTACT FIRST / LATER, no terminal/excluded M6 states)
        callable_pool: list[LeadRecord] = []
        for l in leads_map.values():
            if not DashboardAnalytics._lead_matches_date_range(l, date_filter, custom_start, custom_end):
                continue
            if not l.is_active or not l.phone:
                continue
            if l.is_archived or l.is_skipped:
                continue
            if l.m6_status in ("SENT", "FAILED", "NOT_READY", "NO_WHATSAPP_NUMBER", "SKIPPED_LIMIT", "SKIPPED_ALREADY_SENT", "SKIPPED_NO_WHATSAPP"):
                continue
            if l.final_action in ("ARCHIVE", "SKIP") or l.outreach_priority in ("ARCHIVE", "SKIP"):
                continue
            if l.sales_potential == "SKIP":
                continue

            # Must strictly have CONTACT FIRST or CONTACT LATER priority
            is_cf = (l.outreach_priority == "CONTACT FIRST" or (l.in_contact_first and l.outreach_priority != "CONTACT LATER"))
            is_cl = (l.outreach_priority == "CONTACT LATER" or (l.in_contact_later and l.outreach_priority != "CONTACT FIRST"))
            if not (is_cf or is_cl):
                continue

            callable_pool.append(l)

        # Tab counts across entire date-filtered callable base pool
        counts = {
            "ALL": len(callable_pool),
            "CONTACT_FIRST": sum(1 for l in callable_pool if l.outreach_priority == "CONTACT FIRST" or (l.in_contact_first and l.outreach_priority != "CONTACT LATER")),
            "CONTACT_LATER": sum(1 for l in callable_pool if not (l.outreach_priority == "CONTACT FIRST" or (l.in_contact_first and l.outreach_priority != "CONTACT LATER"))),
        }

        # Step 2: Filter records by tab, potential, city, search
        calling_leads: list[dict[str, Any]] = []
        for l in callable_pool:
            is_first = (l.outreach_priority == "CONTACT FIRST" or (l.in_contact_first and l.outreach_priority != "CONTACT LATER"))
            if raw_tab in ("CONTACT_FIRST", "CONTACT FIRST") and not is_first:
                continue
            elif raw_tab in ("CONTACT_LATER", "CONTACT LATER") and is_first:
                continue

            if potential and l.sales_potential.upper() != potential:
                continue

            if city and l.city.lower() != city.lower():
                continue

            if search:
                haystack = f"{l.lead_id} {l.business_name} {l.phone} {l.whatsapp} {l.city} {l.location} {l.instagram} {l.website} {l.outreach_priority} {l.detected_opportunity} {l.why_this_lead} {l.pitch_hook} {l.outreach_opening} {l.outreach_subject} {l.outreach_message} {l.source_file}".lower()
                if search not in haystack:
                    continue

            d = asdict(l)
            d["is_archived"] = l.is_archived
            d["is_skipped"] = l.is_skipped
            d["is_active"] = l.is_active
            d["is_m6_eligible"] = l.is_m6_eligible
            d["archive_skip_reason"] = l.archive_skip_reason
            d["opportunity"] = l.opportunity
            d["gaps"] = l.gaps
            d["pitch_hook"] = l.pitch_hook
            d["source_files"] = l.source_files
            calling_leads.append(d)

        # Step 3: Sort order: CONTACT FIRST first, then CONTACT LATER; then High potential, then business name
        calling_leads.sort(
            key=lambda x: (
                0 if (x.get("outreach_priority") == "CONTACT FIRST" or (x.get("in_contact_first") and x.get("outreach_priority") != "CONTACT LATER")) else 1,
                0 if x.get("sales_potential") == "HIGH" else 1,
                (x.get("business_name") or x.get("lead_id") or "").lower(),
            )
        )

        self._send_json({"leads": calling_leads, "total": len(calling_leads), "counts": counts})

    def _handle_instagram_page(self, leads_map: dict[str, LeadRecord], query: dict[str, list[str]]) -> None:
        date_filter = query.get("date_filter", ["ALL_TIME"])[0]
        custom_start = query.get("custom_start", [""])[0]
        custom_end = query.get("custom_end", [""])[0]
        search = query.get("search", [""])[0].lower()
        potential = query.get("potential", [""])[0].upper()
        city = query.get("city", [""])[0]

        ig_leads = []
        for l in leads_map.values():
            if not DashboardAnalytics._lead_matches_date_range(l, date_filter, custom_start, custom_end):
                continue

            if not (l.in_manual_instagram or l.outreach_channel == "Instagram DM" or l.instagram):
                continue

            if potential and l.sales_potential.upper() != potential:
                continue

            if city and l.city.lower() != city.lower():
                continue

            if search:
                haystack = f"{l.business_name} {l.lead_id} {l.instagram} {l.city} {l.gaps} {l.outreach_message} {l.detected_opportunity} {l.pitch_hook}".lower()
                if search not in haystack:
                    continue

            d = asdict(l)
            d["is_archived"] = l.is_archived
            d["is_skipped"] = l.is_skipped
            d["is_active"] = l.is_active
            d["is_m6_eligible"] = l.is_m6_eligible
            d["archive_skip_reason"] = l.archive_skip_reason
            ig_leads.append(d)

        ig_leads.sort(
            key=lambda x: (
                x.get("sales_potential") == "HIGH",
                bool(x.get("instagram")),
            ),
            reverse=True,
        )

        counts = {
            "TOTAL": len(ig_leads),
            "HIGH_POTENTIAL": sum(1 for l in ig_leads if l.get("sales_potential") == "HIGH"),
            "MODERATE": sum(1 for l in ig_leads if l.get("sales_potential") == "MODERATE"),
        }

        self._send_json({"leads": ig_leads, "total": len(ig_leads), "counts": counts})

    def _handle_pipeline_kanban(self, leads_map: dict[str, LeadRecord], query: dict[str, list[str]]) -> None:
        stages = {
            "NEW": [],
            "RESEARCHED": [],
            "QUALIFIED": [],
            "READY_TO_CONTACT": [],
            "CONTACTED": [],
            "REPLIED": [],
            "INTERESTED": [],
            "WON": [],
            "LOST": [],
        }

        for lead in leads_map.values():
            stg = lead.sales_stage if lead.sales_stage in stages else "NEW"
            stages[stg].append({
                "lead_id": lead.lead_id,
                "business_name": lead.business_name,
                "city": lead.city,
                "phone": lead.phone,
                "potential": lead.sales_potential,
                "qualification_score": lead.qualification_score,
                "priority": lead.outreach_priority,
                "channel": lead.outreach_channel,
                "m6_status": lead.m6_status,
                "last_contact": lead.last_contacted_at,
            })

        self._send_json({"stages": stages, "total_leads": len(leads_map)})

    def _handle_source_preview(self, raw_path: str) -> None:
        if not raw_path:
            self._send_error(HTTPStatus.BAD_REQUEST, "File path is required")
            return

        target = Path(raw_path)
        if not target.is_absolute():
            target = (self.data_loader.project_root / target).resolve()

        # Security check: must be inside project root
        try:
            target.relative_to(self.data_loader.project_root.resolve())
        except ValueError:
            self._send_error(HTTPStatus.FORBIDDEN, "Access denied: Path outside workspace")
            return

        if not target.is_file():
            self._send_error(HTTPStatus.NOT_FOUND, "File not found")
            return

        ext = target.suffix.lower()
        preview_data: dict[str, Any] = {
            "filename": target.name,
            "path": str(target),
            "size_bytes": target.stat().st_size,
            "file_type": ext.lstrip(".").upper(),
            "lines": [],
            "rows": [],
            "raw_json": None,
        }

        try:
            if ext == ".csv":
                with target.open(encoding="utf-8", errors="replace") as f:
                    r = csv.DictReader(f)
                    preview_data["headers"] = r.fieldnames or []
                    preview_data["rows"] = [row for _, row in zip(range(100), r)]
            elif ext == ".json":
                with target.open(encoding="utf-8", errors="replace") as f:
                    preview_data["raw_json"] = json.load(f)
            else:
                with target.open(encoding="utf-8", errors="replace") as f:
                    preview_data["lines"] = [line.rstrip("\n") for _, line in zip(range(150), f)]
            self._send_json(preview_data)
        except Exception as exc:
            self._send_error(HTTPStatus.INTERNAL_SERVER_ERROR, f"Error reading file: {exc}")

    def _serve_static(self, path: str) -> None:
        rel = path.lstrip("/") or "index.html"
        file_path = (STATIC_DIR / rel).resolve()

        try:
            file_path.relative_to(STATIC_DIR.resolve())
        except ValueError:
            self._send_error(HTTPStatus.FORBIDDEN, "Forbidden")
            return

        if file_path.is_dir():
            index_candidate = file_path / "index.html"
            if index_candidate.is_file():
                file_path = index_candidate

        if not file_path.is_file():
            # If path is inside /demo2 or starts with demo2, fallback to demo2/index.html
            if rel.startswith("demo2"):
                file_path = STATIC_DIR / "demo2" / "index.html"
            # If path is inside /demo or starts with demo, fallback to demo/index.html
            elif rel.startswith("demo"):
                file_path = STATIC_DIR / "demo" / "index.html"
            else:
                # SPA fallback to dashboard index.html
                file_path = STATIC_DIR / "index.html"

        if not file_path.is_file():
            self._send_error(HTTPStatus.NOT_FOUND, "Static asset not found")
            return

        mime_type, _ = mimetypes.guess_type(str(file_path))
        mime_type = mime_type or "application/octet-stream"

        try:
            data = file_path.read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", f"{mime_type}; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-cache, must-revalidate")
            self.end_headers()
            self.wfile.write(data)
        except Exception as exc:
            self._send_error(HTTPStatus.INTERNAL_SERVER_ERROR, f"Error serving static file: {exc}")

    def _send_json(self, data: Any, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(data, indent=2, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)

    def _send_error(self, status: HTTPStatus, message: str) -> None:
        self._send_json({"error": message, "status": status.value}, status=status)


def run_dashboard_server(
    host: str = "127.0.0.1",
    port: int = 8080,
    open_browser: bool = False,
    project_root: Path | None = None,
) -> None:
    """Start the M7 Sales Dashboard server."""
    DashboardHandler.data_loader = DashboardDataLoader(project_root)
    server_address = (host, port)

    try:
        httpd = ThreadingHTTPServer(server_address, DashboardHandler)
    except OSError as exc:
        if "Address already in use" in str(exc):
            # Try port + 1
            port = port + 1
            server_address = (host, port)
            httpd = ThreadingHTTPServer(server_address, DashboardHandler)
        else:
            raise

    url = f"http://{host}:{port}"
    print("==================================================")
    print("🚀 MalikAxiom Lead AI — M7 Sales Command Center")
    print(f"📊 Dashboard URL: {url}")
    print(f"📁 Watching Root: {DashboardHandler.data_loader.project_root}")
    print("⚡ Auto-refresh: Enabled (polling background files)")
    print("==================================================")
    print("Press Ctrl+C to stop the dashboard server.")

    if open_browser:
        import webbrowser
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping dashboard server...")
    finally:
        httpd.server_close()
        print("Dashboard server stopped.")


if __name__ == "__main__":
    run_dashboard_server()

