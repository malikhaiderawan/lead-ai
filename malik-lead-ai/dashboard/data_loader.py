"""M7 Data Loader & File Auto-Discovery Engine.

Reads directly from the filesystem (CSV, XLSX, JSON, LOG, MD) without requiring any database.
Normalizes and indexes all M1–M6 pipeline outputs with full provenance and caching.
"""

from __future__ import annotations

import csv
import json
import logging
import os
import re
import sys
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

from .activity_manager import activity_manager

# Ensure vendored openpyxl is in sys.path if available
PROJECT_ROOT = Path(__file__).resolve().parent.parent
VENDOR_DIR = PROJECT_ROOT / "vendor"
if VENDOR_DIR.is_dir() and str(VENDOR_DIR) not in sys.path:
    sys.path.insert(0, str(VENDOR_DIR))


def _safe_str(val: Any, default: str = "") -> str:
    if val is None:
        return default
    s = str(val).strip()
    return s if s and s.lower() not in ("null", "none", "nan", "undefined") else default


def _parse_iso_timestamp(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        clean = ts.replace("Z", "+00:00")
        return datetime.fromisoformat(clean)
    except Exception:
        return None


@dataclass
class DiscoveredFile:
    """Metadata about a detected file in the pipeline."""

    path: str
    filename: str
    relative_path: str
    file_type: str              # CSV, JSON, XLSX, LOG, MD
    milestone: str              # M1, M2, M3, M4, M5, M6, Master, Batch, Logs, Other
    scenario: str               # General, Cold Calling, Instagram, WhatsApp, Batch Snapshot, etc.
    size_bytes: int
    modified_time: str
    modified_epoch: float
    record_count: int
    status: str                 # OK | PARSE_ERROR | EMPTY | UNREADABLE
    error_message: str = ""
    discovered_date: str = ""   # YYYY-MM-DD from filename or mtime


@dataclass
class LeadRecord:
    """Unified lead data model aggregating M1 through M7 information."""

    lead_id: str
    business_name: str
    business_type: str = ""
    business_category: str = ""
    location: str = ""
    city: str = ""
    address: str = ""

    # Contact fields
    phone: str = ""
    mobile_phone: str = ""
    whatsapp: str = ""
    landline: str = ""
    email: str = ""
    website: str = ""
    google_maps_url: str = ""

    # Social profiles
    instagram: str = ""
    facebook: str = ""
    tiktok: str = ""
    linkedin: str = ""
    youtube: str = ""

    # M1 Discovery & Source
    source: str = ""
    source_file: str = ""
    discovered_at: str = ""

    # M2 Deep Research
    research_status: str = "UNKNOWN"
    website_status: str = ""
    website_reachable: str = ""
    ecommerce_status: str = ""
    checkout_status: str = ""
    online_ordering: str = ""
    google_rating: str = ""
    google_reviews: int = 0
    digital_maturity: str = ""
    research_summary: str = ""
    verified_facts: list[str] = field(default_factory=list)
    observed_gaps: list[str] = field(default_factory=list)
    unknowns: list[str] = field(default_factory=list)
    researched_at: str = ""

    # M3 Qualification
    qualification_score: int | None = None
    qualification_status: str = ""
    sales_potential: str = "UNKNOWN"    # HIGH | MODERATE | LOW | SKIP
    confidence: str = "UNKNOWN"         # HIGH | MEDIUM | LOW
    why_this_lead: str = ""
    detected_opportunity: str = ""
    primary_service: str = ""
    primary_service_reason: str = ""
    secondary_services: list[str] = field(default_factory=list)
    final_action: str = ""              # CONTACT | INVESTIGATE_FURTHER | ARCHIVE | SKIP
    qualified_at: str = ""

    # M4 Outreach Composition
    outreach_channel: str = ""          # WhatsApp | Instagram DM | Facebook | Email
    outreach_priority: str = ""         # CONTACT FIRST | CONTACT LATER | SKIP
    outreach_subject: str = ""
    outreach_opening: str = ""
    outreach_message: str = ""
    outreach_cta: str = ""
    personalization_points: list[str] = field(default_factory=list)
    message_notes: str = ""
    composed_at: str = ""

    # M5 Sales Master & Scenarios
    in_master: bool = False
    in_contact_first: bool = False
    in_contact_later: bool = False
    in_manual_instagram: bool = False
    in_mega_cold_calling: bool = False
    batch_source: str = ""
    review_flag: bool = False
    review_reason: str = ""
    possible_duplicate: bool = False
    duplicate_reason: str = ""

    # M6 WhatsApp Execution Engine (Real Truth)
    m6_recipient: str = ""
    m6_status: str = "PENDING"          # SENT | FAILED | NOT_READY | SKIPPED_ALREADY_SENT | NO_WHATSAPP_NUMBER | PENDING | UNKNOWN
    m6_sent_at: str = ""
    m6_last_attempt_at: str = ""
    m6_attempts: int = 0
    m6_error: str = ""
    m6_note: str = ""
    m6_verification: str = ""
    m6_history: list[dict[str, Any]] = field(default_factory=list)

    # M7 Sales Pipeline State
    sales_stage: str = "NEW"            # NEW | RESEARCHED | QUALIFIED | READY_TO_CONTACT | CONTACTED | REPLIED | INTERESTED | DEMO_DISCUSSION | QUOTED | WON | LOST | FOLLOW_UP
    last_contacted_at: str = ""
    follow_up_at: str = ""
    reply_status: str = ""              # REPLIED | NO_REPLY | PENDING
    interested_status: str = ""         # INTERESTED | NOT_INTERESTED | MAYBE | UNKNOWN
    notes: str = ""
    revenue: float = 0.0

    # M7 Sales Activity & Call CRM
    call_status: str = "PENDING"        # PENDING | CONNECTED | NOT_CONNECTED
    category: str = ""                  # INTERESTED | SEND | NO_ANSWER | ""
    last_called_at: str = ""            # ISO timestamp of last call
    latest_note: str = ""               # Latest note entered
    activity_history: list[dict[str, Any]] = field(default_factory=list)

    # Data integrity & Conflict tracking
    conflicts: list[str] = field(default_factory=list)
    data_sources: list[str] = field(default_factory=list)
    last_updated_at: str = ""

    @property
    def gaps(self) -> str:
        if self.observed_gaps:
            return "; ".join(str(g) for g in self.observed_gaps if str(g).strip())
        if self.research_summary:
            return self.research_summary
        return ""

    @property
    def opportunity(self) -> str:
        if self.detected_opportunity:
            return self.detected_opportunity
        if self.why_this_lead:
            return self.why_this_lead
        if self.primary_service_reason:
            return self.primary_service_reason
        return ""

    @property
    def pitch_hook(self) -> str:
        # Avoid trivial greeting headers like "Hi Buy 7Days,"
        if self.outreach_opening and len(self.outreach_opening.strip()) > 20 and not self.outreach_opening.strip().lower().startswith(("hi ", "hello ", "dear ", "assalam")):
            return self.outreach_opening.strip()
        if self.outreach_subject and len(self.outreach_subject.strip()) > 10:
            return self.outreach_subject.strip()
        if self.outreach_message:
            lines = [l.strip() for l in self.outreach_message.split("\n") if l.strip()]
            for line in lines:
                if not line.lower().startswith(("hi ", "hello ", "dear ", "assalam")):
                    if len(line) > 20:
                        return line
            if lines:
                return lines[0][:120]
        return ""

    @property
    def source_files(self) -> list[str]:
        res = list(self.data_sources)
        if self.source_file and self.source_file not in res:
            res.insert(0, self.source_file)
        return res

    @property
    def is_archived(self) -> bool:
        if self.sales_stage == "ARCHIVED":
            return True
        if self.final_action == "ARCHIVE" or self.outreach_priority == "ARCHIVE":
            return True
        if self.m6_status == "NOT_ELIGIBLE" and "ARCHIVE" in (self.m6_error or "").upper():
            return True
        return False

    @property
    def is_skipped(self) -> bool:
        if self.is_archived:
            return False
        if self.sales_stage in ("SKIPPED", "SKIP"):
            return True
        if self.final_action == "SKIP" or self.outreach_priority == "SKIP" or self.sales_potential == "SKIP":
            return True
        # NOTE: m6_status == 'SKIPPED_LIMIT' means WhatsApp outreach reached a batch or daily limit,
        # NOT that the lead is disqualified. It remains an active, high-priority sales lead.
        if self.m6_status == "NOT_ELIGIBLE" and "SKIP" in (self.m6_error or "").upper():
            return True
        return False

    @property
    def is_active(self) -> bool:
        return not self.is_archived and not self.is_skipped and self.sales_stage != "LOST"

    @property
    def is_m6_eligible(self) -> bool:
        """Strict safety check: ARCHIVE and SKIP leads are NEVER eligible for WhatsApp outreach."""
        if self.is_archived or self.is_skipped:
            return False
        if self.final_action in ("ARCHIVE", "SKIP") or self.outreach_priority in ("ARCHIVE", "SKIP"):
            return False
        if self.sales_potential == "SKIP":
            return False
        return bool(self.phone or self.m6_recipient)

    @property
    def archive_skip_reason(self) -> str:
        if not (self.is_archived or self.is_skipped):
            return ""
        for r in (self.review_reason, self.duplicate_reason, self.m6_error, self.m6_note):
            if r and str(r).strip() and not str(r).strip().startswith("run send limit"):
                return str(r).strip()
        if self.is_archived:
            return "Marked as ARCHIVE during qualification"
        if self.is_skipped:
            return "Marked as SKIP during qualification"
        return ""


class DashboardDataLoader:
    """Scans and parses all pipeline files into unified, memory-cached data structures."""

    def __init__(self, project_root: Path | None = None):
        self.project_root = project_root or PROJECT_ROOT
        self.input_dir = self.project_root / "input"
        self.output_dir = self.project_root / "output"
        self.batches_dir = self.output_dir / "batches"

        self._lock = threading.Lock()
        self._cache_mtime_fingerprint: str = ""
        self._cached_files: list[DiscoveredFile] = []
        self._cached_leads: dict[str, LeadRecord] = {}
        self._cached_raw_m6_state: dict[str, Any] = {}
        self._last_scan_time: str = ""

    def discover_files(self) -> list[DiscoveredFile]:
        """Public alias for discovering and indexing all pipeline files."""
        return self._discover_all_files()

    def discover_and_index_files(self) -> list[DiscoveredFile]:
        """Public alias for discovering and indexing all pipeline files."""
        return self._discover_all_files()

    @staticmethod
    def _extract_city(loc_str: str) -> str:
        """Extract city name from location string."""
        if not loc_str:
            return "Islamabad/Rawalpindi"
        loc = loc_str.lower()
        for city in ("Islamabad", "Rawalpindi", "Lahore", "Karachi", "Faisalabad", "Multan", "Peshawar", "Sialkot", "Gujranwala", "Hyderabad", "Quetta", "Gujrat"):
            if city.lower() in loc:
                return city
        return "Islamabad/Rawalpindi"

    def get_fingerprint(self) -> str:
        """Compute quick hash/fingerprint of all file modification times to detect changes."""
        mtimes: list[str] = []
        dirs_to_check = [self.input_dir, self.output_dir, self.batches_dir]
        for d in dirs_to_check:
            if not d.exists():
                continue
            for entry in os.scandir(d):
                if entry.is_file() and not entry.name.startswith("."):
                    mtimes.append(f"{entry.name}:{entry.stat().st_mtime_ns}:{entry.stat().st_size}")
        return "|".join(sorted(mtimes))

    def load_all(self, force_reload: bool = False) -> tuple[dict[str, LeadRecord], list[DiscoveredFile]]:
        """Load all data from disk with automatic change detection caching."""
        with self._lock:
            current_fp = self.get_fingerprint()
            if not force_reload and self._cache_mtime_fingerprint == current_fp and self._cached_leads:
                return self._cached_leads, self._cached_files

            logger.info("M7 DataLoader: Refreshing pipeline data from filesystem...")
            files = self._discover_all_files()
            leads, raw_m6 = self._build_leads_index(files)

            self._cached_files = files
            self._cached_leads = leads
            self._cached_raw_m6_state = raw_m6
            self._cache_mtime_fingerprint = current_fp
            self._last_scan_time = datetime.now(timezone.utc).isoformat()

            logger.info(
                "M7 DataLoader: Loaded %d unified leads across %d discovered files.",
                len(leads), len(files)
            )
            return self._cached_leads, self._cached_files

    def _discover_all_files(self) -> list[DiscoveredFile]:
        """Scan input/, output/, output/batches/ and classify every discovered file."""
        discovered: list[DiscoveredFile] = []

        # 1. Input CSVs (M1)
        if self.input_dir.exists():
            for p in sorted(self.input_dir.glob("*")):
                if p.is_file() and not p.name.startswith("."):
                    discovered.append(self._inspect_file(p, default_milestone="M1", default_scenario="Raw Ingestion"))

        # 2. Output files (M2-M6, Master, etc.)
        if self.output_dir.exists():
            for p in sorted(self.output_dir.glob("*")):
                if p.is_file() and not p.name.startswith("."):
                    discovered.append(self._inspect_file(p, default_milestone="M5", default_scenario="Pipeline Output"))

        # 3. Batch snapshots
        if self.batches_dir.exists():
            for p in sorted(self.batches_dir.glob("*.csv")):
                if p.is_file():
                    discovered.append(self._inspect_file(p, default_milestone="Batch", default_scenario="Batch Snapshot"))

        return discovered

    def _inspect_file(self, path: Path, default_milestone: str = "Other", default_scenario: str = "General") -> DiscoveredFile:
        """Inspect file, count records, parse status, and classify milestone."""
        stat = path.stat()
        mtime_dt = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
        mtime_iso = mtime_dt.isoformat()
        rel_path = str(path.relative_to(self.project_root))
        size = stat.st_size
        name = path.name
        ext = path.suffix.lower()

        # Date from filename pattern (e.g. _20260929_181053) or mtime
        date_match = re.search(r"(\d{4})(\d{2})(\d{2})", name)
        if date_match:
            discovered_date = f"{date_match.group(1)}-{date_match.group(2)}-{date_match.group(3)}"
        else:
            discovered_date = mtime_dt.strftime("%Y-%m-%d")

        milestone = default_milestone
        scenario = default_scenario
        file_type = ext.lstrip(".").upper() or "FILE"

        if "research" in name:
            milestone = "M2"
            scenario = "Deep Web Research"
        elif "qualification" in name or "qualified" in name:
            milestone = "M3"
            scenario = "Lead Qualification"
        elif "outreach" in name and "m6" not in name:
            milestone = "M4"
            scenario = "Outreach Composition"
        elif "sales_leads" in name or "sales_summary" in name:
            milestone = "M5"
            scenario = "Master Sales Report"
        elif "contact_first" in name:
            milestone = "M5"
            scenario = "Contact First Action"
        elif "contact_later" in name:
            milestone = "M5"
            scenario = "Contact Later Follow-up"
        elif "manual_instagram" in name:
            milestone = "M5"
            scenario = "Instagram Outreach"
        elif "mega_cold_calling" in name:
            milestone = "M5"
            scenario = "Cold Calling Master"
        elif "mega_contact" in name:
            milestone = "M5"
            scenario = "Cumulative Archive"
        elif "m6_" in name or "whatsapp" in name.lower():
            milestone = "M6"
            scenario = "WhatsApp Execution"
        elif "batches" in rel_path:
            milestone = "Batch"
            scenario = "Historical Snapshot"
        elif "input" in rel_path:
            milestone = "M1"
            scenario = "Raw Input Leads"

        record_count = 0
        status = "OK"
        error_msg = ""

        try:
            if size == 0:
                status = "EMPTY"
                record_count = 0
            elif ext == ".csv":
                with path.open(encoding="utf-8", errors="replace") as f:
                    reader = csv.reader(f)
                    header = next(reader, None)
                    if header:
                        record_count = sum(1 for row in reader if any(cell.strip() for cell in row))
                    else:
                        status = "EMPTY"
            elif ext == ".json":
                with path.open(encoding="utf-8", errors="replace") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        record_count = len(data)
                    elif isinstance(data, dict):
                        record_count = len(data.get("leads", data))
            elif ext == ".xlsx":
                try:
                    import openpyxl  # type: ignore
                    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
                    ws = wb.active
                    if ws:
                        # Max rows minus header
                        row_count = max(0, (ws.max_row or 1) - 1)
                        record_count = row_count
                    wb.close()
                except Exception as ex:
                    record_count = 0
                    error_msg = f"Excel parse notice: {ex}"
            elif ext in (".log", ".txt", ".md"):
                with path.open(encoding="utf-8", errors="replace") as f:
                    record_count = sum(1 for _ in f)
        except Exception as exc:
            status = "PARSE_ERROR"
            error_msg = str(exc)

        return DiscoveredFile(
            path=str(path),
            filename=name,
            relative_path=rel_path,
            file_type=file_type,
            milestone=milestone,
            scenario=scenario,
            size_bytes=size,
            modified_time=mtime_iso,
            modified_epoch=stat.st_mtime,
            record_count=record_count,
            status=status,
            error_message=error_msg,
            discovered_date=discovered_date,
        )

    def _build_leads_index(self, files: list[DiscoveredFile]) -> tuple[dict[str, LeadRecord], dict[str, Any]]:
        """Merge all files into unified lead records without fabricating data."""
        leads_map: dict[str, LeadRecord] = {}
        raw_m6_state: dict[str, Any] = {}

        # 1. Load M6 send state first (to guarantee ground truth for WhatsApp)
        m6_state_file = self.output_dir / "m6_send_state.json"
        if m6_state_file.is_file() and m6_state_file.stat().st_size > 0:
            try:
                with m6_state_file.open(encoding="utf-8") as f:
                    raw_m6_state = json.load(f)
                    m6_leads_dict = raw_m6_state.get("leads", {})
                    for lid, item in m6_leads_dict.items():
                        lead = self._get_or_create_lead(leads_map, lid, item.get("business_name", ""))
                        lead.m6_recipient = _safe_str(item.get("recipient"))
                        lead.m6_status = _safe_str(item.get("status"), "PENDING")
                        lead.m6_sent_at = _safe_str(item.get("sent_at") or item.get("first_sent_at"))
                        lead.m6_last_attempt_at = _safe_str(item.get("last_attempt_at"))
                        lead.m6_attempts = int(item.get("attempts", 0))
                        lead.m6_error = _safe_str(item.get("error"))
                        lead.m6_note = _safe_str(item.get("note"))
                        lead.m6_verification = _safe_str(item.get("verification"))
                        lead.m6_history = item.get("history", [])
                        lead.data_sources.append("m6_send_state.json")
                        if lead.m6_status == "SENT":
                            lead.sales_stage = "CONTACTED"
                            lead.last_contacted_at = lead.m6_sent_at or lead.m6_last_attempt_at
            except Exception as exc:
                logger.warning("Error reading m6_send_state.json: %s", exc)

        # 1.5 Load M6 outreach results (attempt logs, validation reasons, errors)
        m6_outreach_json = self.output_dir / "m6_outreach_results.json"
        if m6_outreach_json.is_file():
            self._load_m6_outreach_results_json(m6_outreach_json, leads_map)

        # 2. Load M5 Master CSV (Primary sales master)
        master_csv = self.output_dir / "malikaxiom_sales_leads.csv"
        if master_csv.is_file():
            self._load_master_csv(master_csv, leads_map)

        # 3. Load M3 Qualification JSON (Full qualification reasoning & gaps)
        qual_json = self.output_dir / "qualification_results.json"
        if qual_json.is_file():
            self._load_qualification_json(qual_json, leads_map)

        # 4. Load M2 Research JSON (Deep research facts & evidence)
        research_json = self.output_dir / "research_results.json"
        if research_json.is_file():
            self._load_research_json(research_json, leads_map)

        # 5. Load M4 Outreach JSON (Composed outreach text & CTAs)
        outreach_json = self.output_dir / "outreach_results.json"
        if outreach_json.is_file():
            self._load_outreach_json(outreach_json, leads_map)

        # 6. Load Action CSVs (contact_first, contact_later, manual_instagram)
        cf_csv = self.output_dir / "contact_first.csv"
        if cf_csv.is_file():
            self._mark_action_file(cf_csv, leads_map, flag="in_contact_first")

        cl_csv = self.output_dir / "contact_later.csv"
        if cl_csv.is_file():
            self._mark_action_file(cl_csv, leads_map, flag="in_contact_later")

        ig_csv = self.output_dir / "manual_instagram_leads.csv"
        if ig_csv.is_file():
            self._load_manual_instagram_csv(ig_csv, leads_map)

        # 7. Load Mega Archives (Cumulative past leads)
        mega_cf = self.output_dir / "mega_contact_first.csv"
        if mega_cf.is_file():
            self._load_mega_csv(mega_cf, leads_map, default_priority="CONTACT FIRST")

        mega_cl = self.output_dir / "mega_contact_later.csv"
        if mega_cl.is_file():
            self._load_mega_csv(mega_cl, leads_map, default_priority="CONTACT LATER")

        # 8. Load Historical Batch CSVs (Ensure historical date traceability)
        if self.batches_dir.exists():
            for bfile in self.batches_dir.glob("*.csv"):
                self._load_batch_file(bfile, leads_map)

        # 8.5 Load M7 Sales Activity State (Persistent Call CRM & Notes)
        try:
            m7_activities = activity_manager.get_all_activities()
            for lid, act in m7_activities.items():
                if lid in leads_map:
                    lead = leads_map[lid]
                    lead.call_status = act.get("call_status", "PENDING")
                    lead.category = act.get("category", "")
                    lead.last_called_at = act.get("last_called_at", "")
                    lead.latest_note = act.get("latest_note", "")
                    lead.activity_history = act.get("history", [])
                    if act.get("m6_status"):
                        lead.m6_status = act["m6_status"]
                        if lead.m6_status == "SENT":
                            lead.sales_stage = "CONTACTED"
                            lead.last_contacted_at = lead.last_called_at or lead.m6_sent_at or ""
                        elif lead.m6_status == "ARCHIVE":
                            lead.sales_stage = "ARCHIVED"
                            lead.final_action = "ARCHIVE"
                        elif lead.m6_status == "SKIP":
                            lead.sales_stage = "SKIPPED"
                            lead.final_action = "SKIP"
                    if lead.latest_note and not lead.notes:
                        lead.notes = lead.latest_note
                    lead.data_sources.append("m7_activity_state.json")
        except Exception as exc:
            logger.warning("Error loading M7 activity state: %s", exc)

        # 8.8. Load all raw leads from input/ CSV files (Automatic discovery of new leads)
        self._load_input_csvs(leads_map)

        # 9. Derive sales stages, cities, timestamps, and detect data conflicts
        now_iso = datetime.now(timezone.utc).isoformat()
        for lead in leads_map.values():
            if not lead.last_updated_at:
                lead.last_updated_at = now_iso
            self._finalize_lead_stage_and_city(lead)

        return leads_map, raw_m6_state

    def _get_or_create_lead(self, leads_map: dict[str, LeadRecord], lead_id: str, business_name: str = "") -> LeadRecord:
        lid = _safe_str(lead_id)
        if not lid:
            # Generate deterministic fallback id from business name
            cleaned = re.sub(r"[^a-zA-Z0-9_]+", "_", business_name.strip().lower())
            lid = f"lead_{cleaned[:40]}" if cleaned else "lead_unknown"

        if lid not in leads_map:
            leads_map[lid] = LeadRecord(
                lead_id=lid,
                business_name=_safe_str(business_name, lid),
            )
        elif business_name and not leads_map[lid].business_name:
            leads_map[lid].business_name = business_name
        return leads_map[lid]

    def _load_m6_outreach_results_json(self, path: Path, leads_map: dict[str, LeadRecord]) -> None:
        try:
            with path.open(encoding="utf-8") as f:
                data = json.load(f)
                if not isinstance(data, list):
                    return
                for item in data:
                    lid = item.get("lead_id") or ""
                    bname = item.get("business_name") or ""
                    lead = self._get_or_create_lead(leads_map, lid, bname)

                    if item.get("action") and not lead.final_action:
                        lead.final_action = _safe_str(item.get("action"))
                    if item.get("priority") and not lead.outreach_priority:
                        lead.outreach_priority = _safe_str(item.get("priority"))
                    if item.get("potential") and (not lead.sales_potential or lead.sales_potential == "UNKNOWN"):
                        lead.sales_potential = _safe_str(item.get("potential"))
                    if item.get("recipient") and not lead.m6_recipient:
                        lead.m6_recipient = _safe_str(item.get("recipient"))
                    if item.get("send_status") and lead.m6_status in ("PENDING", "UNKNOWN", ""):
                        lead.m6_status = _safe_str(item.get("send_status"))
                    if item.get("error") and not lead.m6_error:
                        lead.m6_error = _safe_str(item.get("error"))
                    if item.get("opportunity") and not lead.detected_opportunity:
                        lead.detected_opportunity = _safe_str(item.get("opportunity"))
                    if item.get("message") and not lead.outreach_message:
                        lead.outreach_message = _safe_str(item.get("message"))
                    if item.get("location") and not lead.location:
                        lead.location = _safe_str(item.get("location"))
                    if item.get("business_type") and not lead.business_type:
                        lead.business_type = _safe_str(item.get("business_type"))
                    if item.get("service") and not lead.primary_service:
                        lead.primary_service = _safe_str(item.get("service"))
                    if item.get("review_flag") and not lead.review_flag:
                        lead.review_flag = bool(item.get("review_flag"))
                    if item.get("duplicate_reason") and not lead.duplicate_reason:
                        lead.duplicate_reason = _safe_str(item.get("duplicate_reason"))

                    lead.data_sources.append(path.name)
        except Exception as exc:
            logger.warning("Error loading m6 outreach results JSON %s: %s", path, exc)

    def _load_master_csv(self, path: Path, leads_map: dict[str, LeadRecord]) -> None:
        try:
            with path.open(encoding="utf-8", errors="replace") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    lid = row.get("lead_id") or ""
                    bname = row.get("business_name") or ""
                    lead = self._get_or_create_lead(leads_map, lid, bname)
                    lead.in_master = True
                    lead.source_file = path.name
                    lead.business_type = _safe_str(row.get("business_type"), lead.business_type)
                    lead.location = _safe_str(row.get("location"), lead.location)
                    lead.phone = _safe_str(row.get("phone"), lead.phone)
                    lead.mobile_phone = _safe_str(row.get("mobile_phone"), lead.mobile_phone)
                    lead.whatsapp = _safe_str(row.get("whatsapp"), lead.whatsapp)
                    lead.landline = _safe_str(row.get("landline"), lead.landline)
                    lead.email = _safe_str(row.get("email"), lead.email)
                    lead.website = _safe_str(row.get("website"), lead.website)
                    lead.instagram = _safe_str(row.get("instagram"), lead.instagram)
                    lead.facebook = _safe_str(row.get("facebook"), lead.facebook)
                    lead.tiktok = _safe_str(row.get("tiktok"), lead.tiktok)
                    lead.linkedin = _safe_str(row.get("linkedin"), lead.linkedin)
                    lead.youtube = _safe_str(row.get("youtube"), lead.youtube)

                    lead.research_status = _safe_str(row.get("research_status"), lead.research_status)
                    lead.digital_maturity = _safe_str(row.get("digital_maturity"), lead.digital_maturity)
                    lead.sales_potential = _safe_str(row.get("sales_potential"), lead.sales_potential)
                    lead.confidence = _safe_str(row.get("confidence"), lead.confidence)
                    lead.why_this_lead = _safe_str(row.get("why_this_lead"), lead.why_this_lead)
                    lead.detected_opportunity = _safe_str(row.get("detected_opportunity"), lead.detected_opportunity)
                    lead.primary_service = _safe_str(row.get("primary_service"), lead.primary_service)
                    lead.primary_service_reason = _safe_str(row.get("primary_service_reason"), lead.primary_service_reason)

                    sec_raw = row.get("secondary_services") or ""
                    if sec_raw:
                        lead.secondary_services = [s.strip() for s in sec_raw.split(",") if s.strip()]

                    lead.outreach_priority = _safe_str(row.get("outreach_priority"), lead.outreach_priority)
                    lead.outreach_channel = _safe_str(row.get("outreach_channel"), lead.outreach_channel)
                    lead.outreach_message = _safe_str(row.get("outreach_message"), lead.outreach_message)
                    lead.final_action = _safe_str(row.get("final_action"), lead.final_action)
                    lead.review_flag = row.get("review_flag", "").lower() in ("yes", "true", "1")
                    lead.review_reason = _safe_str(row.get("review_reason"), lead.review_reason)
                    lead.possible_duplicate = row.get("possible_duplicate", "").lower() in ("yes", "true", "1")
                    lead.duplicate_reason = _safe_str(row.get("duplicate_reason"), lead.duplicate_reason)
                    lead.last_updated_at = _safe_str(row.get("report_timestamp"), lead.last_updated_at)
                    lead.data_sources.append(path.name)
        except Exception as exc:
            logger.warning("Error loading master CSV %s: %s", path, exc)

    def _load_qualification_json(self, path: Path, leads_map: dict[str, LeadRecord]) -> None:
        try:
            with path.open(encoding="utf-8") as f:
                data = json.load(f)
                if not isinstance(data, list):
                    return
                for item in data:
                    lid = item.get("lead_id") or ""
                    bname = item.get("business_name") or ""
                    lead = self._get_or_create_lead(leads_map, lid, bname)
                    lead.business_category = _safe_str(item.get("category"), lead.business_category)
                    if not lead.business_type:
                        lead.business_type = lead.business_category
                    lead.location = _safe_str(item.get("location"), lead.location)
                    lead.sales_potential = _safe_str(item.get("sales_potential"), lead.sales_potential)
                    lead.confidence = _safe_str(item.get("confidence"), lead.confidence)
                    lead.why_this_lead = _safe_str(item.get("why_this_lead"), lead.why_this_lead)
                    lead.primary_service = _safe_str(item.get("primary_service"), lead.primary_service)
                    lead.primary_service_reason = _safe_str(item.get("primary_service_reason"), lead.primary_service_reason)
                    lead.detected_opportunity = _safe_str(item.get("detected_opportunity"), lead.detected_opportunity)
                    lead.outreach_channel = _safe_str(item.get("outreach_channel"), lead.outreach_channel)
                    lead.final_action = _safe_str(item.get("final_action"), lead.final_action)
                    lead.qualified_at = _safe_str(item.get("qualification_timestamp"), lead.qualified_at)
                    lead.data_sources.append("qualification_results.json")
        except Exception as exc:
            logger.warning("Error loading qualification JSON %s: %s", path, exc)

    def _load_research_json(self, path: Path, leads_map: dict[str, LeadRecord]) -> None:
        try:
            with path.open(encoding="utf-8") as f:
                data = json.load(f)
                if not isinstance(data, list):
                    return
                for item in data:
                    lid = item.get("lead_id") or ""
                    bname = item.get("business_name") or ""
                    lead = self._get_or_create_lead(leads_map, lid, bname)
                    lead.website_status = _safe_str(item.get("website_status"), lead.website_status)
                    lead.website_reachable = _safe_str(item.get("website_reachable"), lead.website_reachable)
                    lead.ecommerce_status = _safe_str(item.get("ecommerce_status"), lead.ecommerce_status)
                    lead.checkout_status = _safe_str(item.get("checkout_status"), lead.checkout_status)
                    lead.online_ordering = _safe_str(item.get("online_ordering"), lead.online_ordering)
                    lead.google_rating = _safe_str(item.get("google_rating"), lead.google_rating)
                    try:
                        lead.google_reviews = int(item.get("google_reviews") or 0)
                    except (ValueError, TypeError):
                        pass
                    lead.google_maps_url = _safe_str(item.get("google_maps_url"), lead.google_maps_url)
                    lead.research_summary = _safe_str(item.get("research_summary"), lead.research_summary)
                    lead.verified_facts = item.get("verified_facts") or lead.verified_facts
                    lead.observed_gaps = item.get("observed_digital_gaps") or lead.observed_gaps
                    lead.unknowns = item.get("unknowns") or lead.unknowns
                    lead.researched_at = _safe_str(item.get("research_timestamp"), lead.researched_at)
                    lead.data_sources.append("research_results.json")
        except Exception as exc:
            logger.warning("Error loading research JSON %s: %s", path, exc)

    def _load_outreach_json(self, path: Path, leads_map: dict[str, LeadRecord]) -> None:
        try:
            with path.open(encoding="utf-8") as f:
                data = json.load(f)
                if not isinstance(data, list):
                    return
                for item in data:
                    lid = item.get("lead_id") or ""
                    bname = item.get("business_name") or ""
                    lead = self._get_or_create_lead(leads_map, lid, bname)
                    lead.outreach_priority = _safe_str(item.get("outreach_priority"), lead.outreach_priority)
                    lead.outreach_subject = _safe_str(item.get("subject"), lead.outreach_subject)
                    lead.outreach_opening = _safe_str(item.get("opening"), lead.outreach_opening)
                    lead.outreach_message = _safe_str(item.get("message"), lead.outreach_message)
                    lead.outreach_cta = _safe_str(item.get("cta"), lead.outreach_cta)
                    lead.personalization_points = item.get("personalization_points") or lead.personalization_points
                    lead.message_notes = _safe_str(item.get("message_notes"), lead.message_notes)
                    lead.composed_at = _safe_str(item.get("outreach_timestamp"), lead.composed_at)
                    lead.data_sources.append("outreach_results.json")
        except Exception as exc:
            logger.warning("Error loading outreach JSON %s: %s", path, exc)

    def _mark_action_file(self, path: Path, leads_map: dict[str, LeadRecord], flag: str) -> None:
        try:
            with path.open(encoding="utf-8", errors="replace") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    bname = row.get("business_name") or ""
                    phone = row.get("phone") or ""
                    # Match by business name or phone
                    matched = False
                    for lead in leads_map.values():
                        if lead.business_name.lower() == bname.lower() or (phone and phone in (lead.phone, lead.whatsapp, lead.mobile_phone)):
                            setattr(lead, flag, True)
                            lead.data_sources.append(path.name)
                            matched = True
                            break
                    if not matched and bname:
                        lead = self._get_or_create_lead(leads_map, "", bname)
                        setattr(lead, flag, True)
                        lead.location = _safe_str(row.get("location"))
                        lead.phone = _safe_str(row.get("phone"))
                        lead.data_sources.append(path.name)
        except Exception as exc:
            logger.warning("Error marking action file %s: %s", path, exc)

    def _load_manual_instagram_csv(self, path: Path, leads_map: dict[str, LeadRecord]) -> None:
        try:
            with path.open(encoding="utf-8", errors="replace") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    bname = row.get("business_name") or ""
                    for lead in leads_map.values():
                        if lead.business_name.lower() == bname.lower():
                            lead.in_manual_instagram = True
                            lead.instagram = _safe_str(row.get("instagram"), lead.instagram)
                            lead.outreach_channel = "Instagram DM"
                            lead.data_sources.append(path.name)
                            break
        except Exception as exc:
            logger.warning("Error loading manual instagram CSV %s: %s", path, exc)

    def _load_mega_csv(self, path: Path, leads_map: dict[str, LeadRecord], default_priority: str) -> None:
        try:
            with path.open(encoding="utf-8", errors="replace") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    lid = row.get("lead_id") or ""
                    bname = row.get("business_name") or ""
                    lead = self._get_or_create_lead(leads_map, lid, bname)
                    lead.in_mega_cold_calling = True
                    if not lead.phone:
                        lead.phone = _safe_str(row.get("phone"))
                    if not lead.mobile_phone:
                        lead.mobile_phone = _safe_str(row.get("mobile_phone"))
                    if not lead.whatsapp:
                        lead.whatsapp = _safe_str(row.get("whatsapp"))
                    if not lead.location:
                        lead.location = _safe_str(row.get("location"))
                    if not lead.business_category:
                        lead.business_category = _safe_str(row.get("category"))
                    if not lead.business_type:
                        lead.business_type = lead.business_category
                    if not lead.outreach_priority:
                        lead.outreach_priority = _safe_str(row.get("sales_action"), default_priority)
                    if not lead.sales_potential or lead.sales_potential == "UNKNOWN":
                        lead.sales_potential = _safe_str(row.get("sales_potential"), lead.sales_potential)
                    if not lead.primary_service:
                        lead.primary_service = _safe_str(row.get("primary_service"), lead.primary_service)
                    if not lead.why_this_lead:
                        lead.why_this_lead = _safe_str(row.get("why_this_lead"), lead.why_this_lead)
                    if not lead.outreach_channel:
                        lead.outreach_channel = _safe_str(row.get("outreach_channel"), lead.outreach_channel)
                    if not lead.outreach_message:
                        lead.outreach_message = _safe_str(row.get("outreach_message"), lead.outreach_message)
                    if not lead.outreach_opening:
                        lead.outreach_opening = _safe_str(row.get("cold_call_pitch_hook"), lead.outreach_opening)
                    if not lead.website:
                        lead.website = _safe_str(row.get("website"), lead.website)
                    if not lead.google_maps_url:
                        lead.google_maps_url = _safe_str(row.get("google_maps_url"), lead.google_maps_url)

                    lead.batch_source = _safe_str(row.get("batch_source"), lead.batch_source)
                    raw_date = row.get("date_added") or row.get("added_timestamp") or ""
                    if raw_date and not lead.discovered_at:
                        clean_date = raw_date.replace(" UTC", "").strip()
                        if len(clean_date) == 16:
                            clean_date = clean_date.replace(" ", "T") + ":00+00:00"
                        lead.discovered_at = clean_date

                    lead.data_sources.append(path.name)
        except Exception as exc:
            logger.warning("Error loading mega CSV %s: %s", path, exc)

    def _load_batch_file(self, path: Path, leads_map: dict[str, LeadRecord]) -> None:
        try:
            # Parse batch date from filename, e.g. contact_first_wi_20260929_161608.csv
            date_match = re.search(r"(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})", path.name)
            batch_date_iso = ""
            if date_match:
                batch_date_iso = f"{date_match.group(1)}-{date_match.group(2)}-{date_match.group(3)}T{date_match.group(4)}:{date_match.group(5)}:{date_match.group(6)}+00:00"

            with path.open(encoding="utf-8", errors="replace") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    lid = row.get("lead_id") or ""
                    bname = row.get("business_name") or ""
                    phone = row.get("phone") or ""
                    if not bname and not lid:
                        continue

                    lead = self._get_or_create_lead(leads_map, lid, bname)
                    if not lead.discovered_at and batch_date_iso:
                        lead.discovered_at = batch_date_iso
                    lead.batch_source = _safe_str(row.get("batch_source"), path.name)

                    if "contact_first" in path.name:
                        lead.in_contact_first = True
                        if not lead.outreach_priority:
                            lead.outreach_priority = "CONTACT FIRST"
                    elif "contact_later" in path.name:
                        lead.in_contact_later = True
                        if not lead.outreach_priority:
                            lead.outreach_priority = "CONTACT LATER"

                    sales_act = _safe_str(row.get("sales_action") or row.get("outreach_priority"))
                    if sales_act:
                        if not lead.outreach_priority:
                            lead.outreach_priority = sales_act
                        if sales_act == "CONTACT FIRST":
                            lead.in_contact_first = True
                        elif sales_act == "CONTACT LATER":
                            lead.in_contact_later = True

                    if not lead.sales_potential or lead.sales_potential == "UNKNOWN":
                        lead.sales_potential = _safe_str(row.get("sales_potential"), lead.sales_potential)
                    if not lead.primary_service:
                        lead.primary_service = _safe_str(row.get("primary_service"), lead.primary_service)
                    if not lead.outreach_channel:
                        lead.outreach_channel = _safe_str(row.get("outreach_channel"), lead.outreach_channel)
                    if not lead.outreach_message:
                        lead.outreach_message = _safe_str(row.get("outreach_message"), lead.outreach_message)
                    if not lead.why_this_lead:
                        lead.why_this_lead = _safe_str(row.get("why_this_lead"), lead.why_this_lead)
                    if not lead.outreach_opening:
                        lead.outreach_opening = _safe_str(row.get("cold_call_pitch_hook"), lead.outreach_opening)
                    if not lead.phone:
                        lead.phone = _safe_str(phone)
                    if not lead.location:
                        lead.location = _safe_str(row.get("location"))
                    if not lead.website:
                        lead.website = _safe_str(row.get("website"), lead.website)

                    lead.data_sources.append(f"batch:{path.name}")
        except Exception as exc:
            logger.warning("Error loading batch file %s: %s", path, exc)

    def _load_input_csvs(self, leads_map: dict[str, LeadRecord]) -> None:
        """Scan input/*.csv and automatically register any raw ingested leads not yet processed."""
        if not self.input_dir.exists():
            return

        def _norm_phone(phone: str | None) -> str:
            if not phone:
                return ""
            digits = re.sub(r"\D", "", phone)
            if digits.startswith("92") and len(digits) >= 11:
                return digits[-10:]
            if digits.startswith("0") and len(digits) >= 10:
                return digits[-10:]
            return digits

        # Fast lookup maps
        phone_lookup: dict[str, LeadRecord] = {}
        name_lookup: dict[str, LeadRecord] = {}

        for lead in leads_map.values():
            for p_field in (lead.phone, lead.whatsapp, lead.mobile_phone):
                norm = _norm_phone(p_field)
                if norm:
                    phone_lookup[norm] = lead
            clean_n = re.sub(r"[^\w\s]", "", lead.business_name.lower()).strip()
            if clean_n:
                name_lookup[clean_n] = lead

        added = 0
        for p in sorted(self.input_dir.glob("*.csv")):
            if not p.is_file() or p.name.startswith("."):
                continue
            try:
                stat = p.stat()
                mtime_iso = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()
                with p.open(encoding="utf-8", errors="replace") as f:
                    reader = csv.DictReader(f)
                    for r in reader:
                        bname = _safe_str(r.get("business_name") or r.get("Business Name") or r.get("Name") or r.get("name"))
                        phone = _safe_str(r.get("phone") or r.get("Phone") or r.get("mobile_phone") or r.get("Mobile") or r.get("whatsapp") or r.get("WhatsApp"))
                        if not bname and not phone:
                            continue

                        matched_lead: LeadRecord | None = None
                        norm_p = _norm_phone(phone)
                        if norm_p and norm_p in phone_lookup:
                            matched_lead = phone_lookup[norm_p]
                        if not matched_lead and bname:
                            clean_n = re.sub(r"[^\w\s]", "", bname.lower()).strip()
                            if clean_n and clean_n in name_lookup:
                                matched_lead = name_lookup[clean_n]

                        src_tag = f"input:{p.name}"
                        if matched_lead:
                            if src_tag not in matched_lead.data_sources:
                                matched_lead.data_sources.append(src_tag)
                            if not matched_lead.phone and phone:
                                matched_lead.phone = phone
                            if not matched_lead.location:
                                matched_lead.location = _safe_str(r.get("address") or r.get("location") or r.get("Location"))
                            if not matched_lead.website:
                                matched_lead.website = _safe_str(r.get("website") or r.get("Website"))
                            if not matched_lead.instagram:
                                matched_lead.instagram = _safe_str(r.get("instagram") or r.get("Instagram"))
                            if not matched_lead.facebook:
                                matched_lead.facebook = _safe_str(r.get("facebook") or r.get("Facebook"))
                            if not matched_lead.business_category:
                                matched_lead.business_category = _safe_str(r.get("category") or r.get("Category"))
                            if not matched_lead.google_maps_url:
                                matched_lead.google_maps_url = _safe_str(r.get("google_maps_url"))
                            if not matched_lead.discovered_at:
                                matched_lead.discovered_at = mtime_iso
                        else:
                            cleaned = re.sub(r"[^a-zA-Z0-9_]+", "_", bname.lower()).strip("_")
                            lid = f"lead_{cleaned[:35]}" if cleaned else f"lead_in_{added+1}"
                            base_lid = lid
                            cnt = 1
                            while lid in leads_map:
                                lid = f"{base_lid}_{cnt}"
                                cnt += 1

                            new_lead = LeadRecord(
                                lead_id=lid,
                                business_name=bname or "Unknown Business",
                                phone=phone,
                                mobile_phone=_safe_str(r.get("mobile_phone") or r.get("Mobile")),
                                whatsapp=_safe_str(r.get("whatsapp") or r.get("WhatsApp")),
                                website=_safe_str(r.get("website") or r.get("Website")),
                                instagram=_safe_str(r.get("instagram") or r.get("Instagram")),
                                facebook=_safe_str(r.get("facebook") or r.get("Facebook")),
                                location=_safe_str(r.get("address") or r.get("location") or r.get("Location")),
                                business_category=_safe_str(r.get("category") or r.get("Category")),
                                business_type=_safe_str(r.get("category") or r.get("Category")),
                                google_rating=_safe_str(r.get("rating") or r.get("Rating")),
                                google_maps_url=_safe_str(r.get("google_maps_url")),
                                source_file=p.name,
                                sales_stage="NEW",
                                research_status="PENDING",
                                qualification_status="PENDING",
                                sales_potential="PENDING",
                                outreach_priority="PENDING",
                                m6_status="NOT_READY",
                                discovered_at=mtime_iso,
                            )
                            try:
                                new_lead.google_reviews = int(r.get("reviews") or r.get("Reviews") or 0)
                            except Exception:
                                pass
                            new_lead.data_sources.append(src_tag)
                            leads_map[lid] = new_lead
                            added += 1

                            if norm_p:
                                phone_lookup[norm_p] = new_lead
                            clean_n = re.sub(r"[^\w\s]", "", bname.lower()).strip()
                            if clean_n:
                                name_lookup[clean_n] = new_lead
            except Exception as exc:
                logger.warning("Error loading input leads from %s: %s", p, exc)

    def _finalize_lead_stage_and_city(self, lead: LeadRecord) -> None:
        """Extract Pakistani city cleanly, determine pipeline sales stage, and check conflicts."""
        # 1. City extraction
        loc = f"{lead.location} {lead.address}".lower()
        for city in ("Islamabad", "Rawalpindi", "Lahore", "Karachi", "Faisalabad", "Multan", "Peshawar", "Sialkot", "Gujranwala", "Hyderabad", "Quetta", "Gujrat", "Dubai", "London"):
            if city.lower() in loc:
                lead.city = city
                break
        if not lead.city and lead.location:
            # Check for JSON address string e.g. {"borough":"","city":"Lahore",...}
            city_m = re.search(r'"city":\s*"([^"]+)"', lead.location)
            if city_m and city_m.group(1).strip():
                lead.city = city_m.group(1).strip()
            else:
                parts = [p.strip() for p in lead.location.split(",") if p.strip() and not p.strip().startswith("{") and "borough" not in p]
                if parts:
                    lead.city = parts[0]
                else:
                    lead.city = "Lahore"

        # 2. Sales Stage derivation (Strict evidence based - no guessing)
        if lead.m6_status == "SENT":
            lead.sales_stage = "CONTACTED"
        elif lead.final_action == "ARCHIVE" or lead.outreach_priority == "ARCHIVE":
            lead.sales_stage = "ARCHIVED"
        elif lead.final_action == "SKIP" or lead.outreach_priority == "SKIP" or lead.sales_potential == "SKIP":
            lead.sales_stage = "SKIPPED"
        elif lead.in_manual_instagram:
            lead.sales_stage = "READY_TO_CONTACT"
        elif lead.outreach_priority == "CONTACT FIRST" or lead.final_action == "CONTACT":
            lead.sales_stage = "READY_TO_CONTACT"
        elif lead.sales_potential in ("HIGH", "MODERATE"):
            lead.sales_stage = "QUALIFIED"
        elif lead.research_status in ("RESEARCHED", "ADVANCED"):
            lead.sales_stage = "RESEARCHED"
        else:
            lead.sales_stage = "NEW"

        # 3. Discovery date resolution
        if not lead.discovered_at:
            lead.discovered_at = (
                lead.researched_at
                or lead.qualified_at
                or lead.composed_at
                or lead.m6_sent_at
                or lead.m6_last_attempt_at
                or ""
            )

        # 4. Last updated date resolution (most recent real event)
        all_timestamps = [
            ts for ts in (
                lead.m6_sent_at,
                lead.m6_last_attempt_at,
                lead.composed_at,
                lead.qualified_at,
                lead.researched_at,
                lead.discovered_at,
            ) if ts
        ]
        if all_timestamps:
            lead.last_updated_at = max(all_timestamps)
        elif not lead.last_updated_at:
            lead.last_updated_at = lead.discovered_at

        # 5. Qualification score derivation (0-100 integer)
        if lead.qualification_score is None:
            lead.qualification_score = self._derive_qualification_score(lead)

        # 6. Deduplicate data sources
        lead.data_sources = sorted(set(lead.data_sources))

    def _derive_qualification_score(self, lead: LeadRecord) -> int:
        """Derive standard qualification score (0-100) based on potential, priority, reviews, rating, and gaps."""
        pot = (lead.sales_potential or "").upper()
        pri = (lead.outreach_priority or "").upper()
        act = (lead.final_action or "").upper()

        if lead.is_archived:
            base = 15
        elif lead.is_skipped or pot == "SKIP" or pri == "SKIP" or act == "SKIP":
            base = 10
        elif pot == "HIGH" or pri == "CONTACT FIRST" or lead.in_contact_first:
            base = 82
        elif pot == "MODERATE" or pri == "CONTACT LATER" or lead.in_contact_later:
            base = 62
        elif pot == "LOW":
            base = 35
        elif lead.sales_stage in ("QUALIFIED", "READY_TO_CONTACT", "CONTACTED"):
            base = 65
        elif lead.sales_stage == "RESEARCHED":
            base = 50
        else:
            base = 40

        # Adjust based on reviews & rating if present
        bonus = 0
        try:
            if lead.google_reviews > 0:
                bonus += min(8, lead.google_reviews // 15)
            if lead.google_rating:
                rating_f = float(lead.google_rating)
                if rating_f >= 4.5:
                    bonus += 5
                elif rating_f >= 4.0:
                    bonus += 3
        except (ValueError, TypeError):
            pass

        # Gaps bonus: having clear identified pain points increases qualification score for agency outreach
        if lead.observed_gaps:
            bonus += min(5, len(lead.observed_gaps) * 2)

        # Confidence bonus
        if lead.confidence == "HIGH":
            bonus += 3
        elif lead.confidence == "LOW":
            bonus -= 5

        total = base + bonus
        if lead.is_archived or lead.is_skipped:
            return max(0, min(25, total))
        elif pot == "HIGH" or pri == "CONTACT FIRST" or lead.in_contact_first:
            return max(75, min(98, total))
        elif pot == "MODERATE" or pri == "CONTACT LATER" or lead.in_contact_later:
            return max(45, min(74, total))
        elif pot == "LOW":
            return max(25, min(44, total))
        else:
            return max(0, min(100, total))
