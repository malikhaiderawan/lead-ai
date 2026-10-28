"""M7 — Sales Activity & Call CRM Manager.

Persists call statuses, categories, notes, and activity history for every lead
in `output/m7_activity_state.json`. Zero database dependency.
Authoritative M6 state and M1-M6 pipeline data are strictly preserved.
"""

from __future__ import annotations

import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_STATE_FILE = PROJECT_ROOT / "output" / "m7_activity_state.json"


class M7ActivityManager:
    """Thread-safe persistent manager for M7 Sales Activity and Call CRM."""

    def __init__(self, state_file: Path | str = DEFAULT_STATE_FILE) -> None:
        self.state_file = Path(state_file)
        self._lock = threading.Lock()
        self._cache: dict[str, dict[str, Any]] | None = None
        self._last_mtime: float = 0.0

    def _ensure_dir(self) -> None:
        self.state_file.parent.mkdir(parents=True, exist_ok=True)

    def _load_state_unlocked(self) -> dict[str, dict[str, Any]]:
        """Load state from disk with mtime check."""
        if not self.state_file.is_file():
            self._cache = {}
            return self._cache

        try:
            mtime = self.state_file.stat().st_mtime
            if self._cache is not None and mtime <= self._last_mtime:
                return self._cache

            with self.state_file.open("r", encoding="utf-8") as f:
                data = json.load(f)
                self._cache = data.get("activities", {})
                self._last_mtime = mtime
                return self._cache
        except Exception as exc:
            logger.warning("Error reading %s: %s", self.state_file, exc)
            if self._cache is None:
                self._cache = {}
            return self._cache

    def _save_state_unlocked(self) -> None:
        """Persist state to disk atomically."""
        self._ensure_dir()
        temp_file = self.state_file.with_suffix(".tmp")
        payload = {
            "version": "1.0.0",
            "system": "MalikAxiom Lead AI M7 Call CRM",
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "activities": self._cache or {},
        }
        with temp_file.open("w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        temp_file.replace(self.state_file)
        self._last_mtime = self.state_file.stat().st_mtime

    def get_lead_activity(self, lead_id: str) -> dict[str, Any]:
        """Return the activity entry for a lead (or empty default)."""
        if not lead_id:
            return {}
        with self._lock:
            activities = self._load_state_unlocked()
            entry = activities.get(lead_id)
            if entry:
                return dict(entry)
            return {
                "lead_id": lead_id,
                "call_status": "PENDING",
                "category": "",
                "last_called_at": "",
                "latest_note": "",
                "history": [],
            }

    def get_all_activities(self) -> dict[str, dict[str, Any]]:
        """Return mapping of all recorded lead activities."""
        with self._lock:
            return {k: dict(v) for k, v in self._load_state_unlocked().items()}

    def record_activity(
        self,
        lead_id: str,
        *,
        business_name: str = "",
        call_status: str | None = None,
        category: str | None = None,
        m6_status: str | None = None,
        note: str = "",
        contact: str = "",
        outcome: str = "",
        interest: str = "",
        next_action: str = "",
        action_type: str = "CALL",
        timestamp: str | None = None,
    ) -> dict[str, Any]:
        """Record a call, status override, or activity event with historical persistence."""
        if not lead_id:
            raise ValueError("lead_id is required to record activity")

        now_iso = timestamp or datetime.now(timezone.utc).isoformat()

        # Normalize call statuses
        norm_call_status = None
        if call_status is not None:
            clean_cs = call_status.strip().upper()
            if clean_cs in ("CONNECTED", "CONNECT", "CALL_CONNECTED", "DONE_CONNECTED"):
                norm_call_status = "CONNECTED"
            elif clean_cs in ("NOT_CONNECTED", "NOT CONNECTED", "MISSED", "FAILED", "CALL_NOT_CONNECTED"):
                norm_call_status = "NOT_CONNECTED"
            elif clean_cs in ("PENDING", "NOT_CALLED", "NOT CALLED"):
                norm_call_status = "PENDING"
            else:
                norm_call_status = clean_cs

        # Normalize categories
        norm_category = None
        if category is not None:
            clean_cat = category.strip().upper()
            if "INTEREST" in clean_cat:
                norm_category = "INTERESTED"
            elif "SEND" in clean_cat or "DEMO" in clean_cat:
                norm_category = "SEND"
            elif "NO" in clean_cat and "ANSWER" in clean_cat:
                norm_category = "NO_ANSWER"
            elif not clean_cat:
                norm_category = ""
            else:
                norm_category = clean_cat

        # Normalize M6 statuses
        norm_m6_status = None
        if m6_status is not None:
            clean_m6 = m6_status.strip().upper()
            if clean_m6 in ("SENT", "SEND", "DONE", "COMPLETED"):
                norm_m6_status = "SENT"
            elif clean_m6 in ("PENDING", "QUEUE", "QUEUED"):
                norm_m6_status = "PENDING"
            elif clean_m6 in ("AWAITING_MANUAL_SEND", "MANUAL", "MANUAL_SEND"):
                norm_m6_status = "AWAITING_MANUAL_SEND"
            elif clean_m6 in ("FAILED", "FAIL", "ERROR"):
                norm_m6_status = "FAILED"
            elif clean_m6 in ("NOT_READY", "NOT READY", "UNREADY"):
                norm_m6_status = "NOT_READY"
            elif clean_m6 in ("NO_WHATSAPP_NUMBER", "NO_WA", "NO_WHATSAPP"):
                norm_m6_status = "NO_WHATSAPP_NUMBER"
            elif clean_m6 in ("ARCHIVE", "ARCHIVED"):
                norm_m6_status = "ARCHIVE"
            elif clean_m6 in ("SKIP", "SKIPPED"):
                norm_m6_status = "SKIP"
            elif not clean_m6:
                norm_m6_status = ""
            else:
                norm_m6_status = clean_m6

        with self._lock:
            activities = self._load_state_unlocked()
            entry = activities.get(lead_id, {
                "lead_id": lead_id,
                "business_name": business_name,
                "call_status": "PENDING",
                "category": "",
                "m6_status": "",
                "last_called_at": "",
                "latest_note": "",
                "history": [],
            })

            if business_name:
                entry["business_name"] = business_name

            # Update call status if provided
            if norm_call_status is not None:
                entry["call_status"] = norm_call_status
                if norm_call_status in ("CONNECTED", "NOT_CONNECTED"):
                    entry["last_called_at"] = now_iso

            # Update category if provided
            if norm_category is not None:
                entry["category"] = norm_category

            # Update M6 status if provided
            if norm_m6_status is not None:
                entry["m6_status"] = norm_m6_status

            # Update note if provided
            clean_note = (note or "").strip()
            if clean_note:
                entry["latest_note"] = clean_note

            if contact:
                entry["contact"] = contact
            if outcome:
                entry["outcome"] = outcome
            if interest:
                entry["interest"] = interest
            if next_action:
                entry["next_action"] = next_action

            # Action type inference
            inferred_action = action_type.upper()
            if action_type == "CALL" and norm_m6_status is not None and norm_call_status is None and norm_category is None:
                inferred_action = "M6_STATUS_UPDATE"

            # Append to history
            history_item: dict[str, Any] = {
                "id": f"act_{int(datetime.now(timezone.utc).timestamp() * 1000)}",
                "timestamp": now_iso,
                "action_type": inferred_action,
                "call_status": entry.get("call_status", "PENDING"),
                "category": entry.get("category", ""),
                "m6_status": entry.get("m6_status", ""),
                "note": clean_note,
                "contact": contact,
                "outcome": outcome,
                "interest": interest,
                "next_action": next_action,
            }
            if "history" not in entry:
                entry["history"] = []
            entry["history"].append(history_item)
            entry["updated_at"] = now_iso

            activities[lead_id] = entry
            self._save_state_unlocked()

            # Safely sync to m6_send_state.json if m6_status was modified
            if norm_m6_status is not None:
                self._sync_m6_send_state_file(lead_id, norm_m6_status, clean_note, now_iso)

            return dict(entry)

    def _sync_m6_send_state_file(self, lead_id: str, status: str, note: str, now_iso: str) -> None:
        """Propagate M6 status to output/m6_send_state.json so other tools and CLI see it."""
        m6_file = PROJECT_ROOT / "output" / "m6_send_state.json"
        if not m6_file.is_file():
            return
        try:
            with m6_file.open("r", encoding="utf-8") as f:
                data = json.load(f)
            leads = data.setdefault("leads", {})
            if lead_id in leads:
                entry = leads[lead_id]
                entry["status"] = status
                if status == "SENT":
                    entry["sent_at"] = entry.get("sent_at") or now_iso
                    entry["attempts"] = max(1, entry.get("attempts", 0))
                entry["last_attempt_at"] = now_iso
                if note:
                    entry["note"] = note
                entry.setdefault("history", []).append({
                    "lead_id": lead_id,
                    "send_status": status,
                    "timestamp": now_iso,
                    "note": note or f"Manually set to {status} via M7 Command Center.",
                })
            else:
                leads[lead_id] = {
                    "lead_id": lead_id,
                    "first_seen_at": now_iso,
                    "recipient": "",
                    "attempts": 1 if status == "SENT" else 0,
                    "status": status,
                    "sent_at": now_iso if status == "SENT" else "",
                    "last_attempt_at": now_iso,
                    "note": note or f"Manually set to {status} via M7 Command Center.",
                    "history": [{
                        "lead_id": lead_id,
                        "send_status": status,
                        "timestamp": now_iso,
                        "note": note or f"Created via M7 Dashboard with status {status}.",
                    }],
                }
            data["updated_at"] = now_iso
            temp_file = m6_file.with_suffix(".tmp")
            with temp_file.open("w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            temp_file.replace(m6_file)
        except Exception as exc:
            logger.warning("Could not sync M6 status for %s to m6_send_state.json: %s", lead_id, exc)

    def calculate_crm_metrics(
        self,
        total_leads_count: int,
        leads_map: dict[str, Any] | None = None,
        target_date_str: str | None = None,
    ) -> dict[str, Any]:
        """Compute live today and total metrics from persisted activity state.

        - Total Leads: Count all leads in the dataset.
        - Pending Calls: Count only eligible CONTACT FIRST leads with NO recorded call attempt.
        - Total Calls Made: Count unique leads with at least one recorded call attempt.
        - Total Connected: Count unique leads with recorded CONNECTED call outcome.
        - Total Not Connected: Count unique leads with recorded NOT_CONNECTED call outcome.
        - Total Interested: Count unique leads explicitly marked INTERESTED.
        - Total Send/Demo: Count unique leads explicitly marked SEND or confirmed sent.
        - Total No Answer: Count unique leads explicitly marked NO_ANSWER.
        - CONTACT LATER / SKIP / ARCHIVE: Excluded from Pending Calls.
        """
        today_date = target_date_str or datetime.now(timezone.utc).strftime("%Y-%m-%d")

        with self._lock:
            activities = self._load_state_unlocked()

        def _is_eligible_contact_first(lead: Any) -> bool:
            """Check if a lead is eligible for immediate CONTACT FIRST cold calling."""
            is_arch = getattr(lead, "is_archived", False)
            is_skip = getattr(lead, "is_skipped", False)
            is_dup = getattr(lead, "possible_duplicate", False)
            if is_arch or is_skip or is_dup:
                return False
            if getattr(lead, "final_action", "") in ("ARCHIVE", "SKIP"):
                return False
            if getattr(lead, "outreach_priority", "") in ("ARCHIVE", "SKIP"):
                return False
            if getattr(lead, "sales_potential", "") == "SKIP":
                return False
            if not getattr(lead, "phone", ""):
                return False
            prio = getattr(lead, "outreach_priority", "")
            in_cf = getattr(lead, "in_contact_first", False)
            if prio == "CONTACT FIRST":
                return True
            if in_cf and prio != "CONTACT LATER":
                return True
            return False

        def _is_contact_later(lead: Any) -> bool:
            """Check if a lead is currently categorized as CONTACT LATER."""
            is_arch = getattr(lead, "is_archived", False)
            is_skip = getattr(lead, "is_skipped", False)
            if is_arch or is_skip:
                return False
            prio = getattr(lead, "outreach_priority", "")
            in_cl = getattr(lead, "in_contact_later", False)
            return (prio == "CONTACT LATER" or in_cl) and prio != "CONTACT FIRST"

        # Unique lead-level sets to prevent double-counting
        calls_made_leads: set[str] = set()
        connected_leads: set[str] = set()
        not_connected_leads: set[str] = set()
        interested_leads: set[str] = set()
        send_leads: set[str] = set()
        no_answer_leads: set[str] = set()

        today_calls_leads: set[str] = set()
        today_connected_leads: set[str] = set()
        today_not_connected_leads: set[str] = set()
        today_interested_leads: set[str] = set()
        today_send_leads: set[str] = set()
        today_no_answer_leads: set[str] = set()

        # Recent activities feed
        recent_feed: list[dict[str, Any]] = []

        all_lead_ids: set[str] = set()
        if leads_map:
            all_lead_ids.update(leads_map.keys())
        if activities:
            all_lead_ids.update(activities.keys())

        for lid in all_lead_ids:
            act = activities.get(lid)
            lead_obj = leads_map.get(lid) if leads_map else None

            # Current call status
            if act and act.get("call_status"):
                cs = act["call_status"]
            elif lead_obj and getattr(lead_obj, "call_status", None):
                cs = lead_obj.call_status
            else:
                cs = "PENDING"

            # Current category
            if act and "category" in act and act.get("category") is not None:
                cat = act["category"]
            elif lead_obj and getattr(lead_obj, "category", None) is not None:
                cat = lead_obj.category
            else:
                cat = ""

            # Last called at timestamp
            last_called = ""
            if act and act.get("last_called_at"):
                last_called = act["last_called_at"]
            elif lead_obj and getattr(lead_obj, "last_called_at", None):
                last_called = lead_obj.last_called_at

            # M6 WhatsApp status
            m6_stat = ""
            if act and act.get("m6_status"):
                m6_stat = act["m6_status"]
            elif lead_obj and getattr(lead_obj, "m6_status", None):
                m6_stat = lead_obj.m6_status

            # History list
            history: list[dict[str, Any]] = []
            if act and act.get("history"):
                history = act["history"]
            elif lead_obj and getattr(lead_obj, "activity_history", None):
                history = lead_obj.activity_history

            bname = (getattr(lead_obj, "business_name", None) if lead_obj else None) or (act.get("business_name") if act else None) or lid

            # Check if this lead has had at least one recorded call attempt
            has_call_attempt = (
                cs in ("CONNECTED", "NOT_CONNECTED")
                or bool(last_called)
                or any(
                    h.get("action_type") == "CALL" or h.get("call_status") in ("CONNECTED", "NOT_CONNECTED")
                    for h in history
                )
            )

            if has_call_attempt:
                calls_made_leads.add(lid)

            # Tally lifetime outcome categories (lead-level)
            if cs == "CONNECTED":
                connected_leads.add(lid)
            elif cs == "NOT_CONNECTED":
                not_connected_leads.add(lid)

            if cat == "INTERESTED":
                interested_leads.add(lid)
            elif cat == "SEND" or m6_stat == "SENT":
                send_leads.add(lid)
            elif cat == "NO_ANSWER":
                no_answer_leads.add(lid)

            # Today's activity tally
            called_today = (
                bool(last_called and last_called[:10] == today_date)
                or any(
                    h.get("timestamp", "")[:10] == today_date
                    and (h.get("action_type") == "CALL" or h.get("call_status") in ("CONNECTED", "NOT_CONNECTED"))
                    for h in history
                )
            )

            if called_today:
                today_calls_leads.add(lid)

                # Determine effective today outcome from today's events or current status
                today_events = [h for h in history if h.get("timestamp", "")[:10] == today_date]
                if today_events:
                    call_events = [h for h in today_events if h.get("call_status") in ("CONNECTED", "NOT_CONNECTED")]
                    eff_today_cs = call_events[-1].get("call_status") if call_events else cs
                    cat_events = [h for h in today_events if h.get("category")]
                    eff_today_cat = cat_events[-1].get("category") if cat_events else cat
                else:
                    eff_today_cs = cs
                    eff_today_cat = cat

                if eff_today_cs == "CONNECTED":
                    today_connected_leads.add(lid)
                elif eff_today_cs == "NOT_CONNECTED":
                    today_not_connected_leads.add(lid)

                if eff_today_cat == "INTERESTED":
                    today_interested_leads.add(lid)
                elif eff_today_cat == "SEND" or (m6_stat == "SENT" and bool(last_called and last_called[:10] == today_date)):
                    today_send_leads.add(lid)
                elif eff_today_cat == "NO_ANSWER":
                    today_no_answer_leads.add(lid)

            # History inspection for today's chronological activity log
            for h in history:
                ts = h.get("timestamp", "")
                if ts and ts[:10] == today_date:
                    recent_feed.append({
                        "lead_id": lid,
                        "business_name": bname,
                        "timestamp": ts,
                        "time_display": ts[11:16] if len(ts) >= 16 else "",
                        "call_status": h.get("call_status", ""),
                        "category": h.get("category", ""),
                        "action": h.get("action_type", "ACTIVITY"),
                        "note": h.get("note", ""),
                    })

        # Sort recent feed chronological descending
        recent_feed.sort(key=lambda x: x["timestamp"], reverse=True)

        # Pending calls calculation:
        # Strictly count eligible CONTACT FIRST leads with NO recorded call attempt
        if leads_map is not None:
            eligible_cf_leads = {lid for lid, l in leads_map.items() if _is_eligible_contact_first(l)}
            contact_later_leads = {lid for lid, l in leads_map.items() if _is_contact_later(l)}
            pending_calls = len(eligible_cf_leads - calls_made_leads)
            cf_count = len(eligible_cf_leads)
            cl_count = len(contact_later_leads)
        else:
            pending_calls = max(0, total_leads_count - len(calls_made_leads))
            cf_count = total_leads_count
            cl_count = 0

        return {
            "today": {
                "date": today_date,
                "calls_made": len(today_calls_leads),
                "connected": len(today_connected_leads),
                "not_connected": len(today_not_connected_leads),
                "interested": len(today_interested_leads),
                "send": len(today_send_leads),
                "no_answer": len(today_no_answer_leads),
            },
            "total": {
                "total_leads": total_leads_count,
                "calls_made": len(calls_made_leads),
                "connected": len(connected_leads),
                "not_connected": len(not_connected_leads),
                "interested": len(interested_leads),
                "send": len(send_leads),
                "no_answer": len(no_answer_leads),
                "pending_calls": pending_calls,
                "contact_first": cf_count,
                "contact_later": cl_count,
            },
            "recent_feed": recent_feed[:50],
        }


# Global singleton instance
activity_manager = M7ActivityManager()
