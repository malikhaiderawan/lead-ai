"""M7 Analytics & KPI Aggregation Engine.

Calculates real-time sales KPIs, chronological activity feeds, pipeline stages,
and chart datasets strictly from verified pipeline data.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from typing import Any

from .data_loader import DiscoveredFile, LeadRecord


def _get_utc_today_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _get_utc_yesterday_str() -> str:
    return (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")


def _lead_matches_date_range(lead: LeadRecord, filter_type: str, custom_start: str = "", custom_end: str = "") -> bool:
    """Filter lead based on timestamp or discovery date."""
    if filter_type == "ALL_TIME" or not filter_type:
        return True

    today_str = _get_utc_today_str()
    yesterday_str = _get_utc_yesterday_str()

    # Determine best date for this lead
    lead_date = ""
    for ts in (lead.m6_sent_at, lead.last_contacted_at, lead.discovered_at, lead.qualified_at, lead.researched_at, lead.last_updated_at):
        if ts and len(ts) >= 10:
            lead_date = ts[:10]
            break

    if not lead_date:
        return filter_type in ("ALL_TIME", "UNKNOWN")

    if filter_type == "TODAY":
        return lead_date == today_str
    elif filter_type == "YESTERDAY":
        return lead_date == yesterday_str
    elif filter_type == "LAST_7_DAYS":
        seven_days_ago = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")
        return lead_date >= seven_days_ago
    elif filter_type == "LAST_30_DAYS":
        thirty_days_ago = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%d")
        return lead_date >= thirty_days_ago
    elif filter_type == "CUSTOM":
        if custom_start and lead_date < custom_start:
            return False
        if custom_end and lead_date > custom_end:
            return False
        return True
    return True


class DashboardAnalytics:
    """Calculates all metrics, KPIs, activity logs, and pipeline summaries."""

    @staticmethod
    def _lead_matches_date_range(lead: LeadRecord, filter_type: str, custom_start: str = "", custom_end: str = "") -> bool:
        return _lead_matches_date_range(lead, filter_type, custom_start, custom_end)

    @staticmethod
    def calculate_overview(
        leads_map: dict[str, LeadRecord],
        files: list[DiscoveredFile],
        date_filter: str = "ALL_TIME",
        custom_start: str = "",
        custom_end: str = "",
    ) -> dict[str, Any]:
        """Compute the full analytics overview and KPI dictionary."""
        all_leads = list(leads_map.values())
        filtered_leads = [
            l for l in all_leads
            if _lead_matches_date_range(l, date_filter, custom_start, custom_end)
        ]

        today_str = _get_utc_today_str()
        yesterday_str = _get_utc_yesterday_str()

        today_leads = [
            l for l in all_leads
            if _lead_matches_date_range(l, "TODAY")
        ]
        yesterday_leads = [
            l for l in all_leads
            if _lead_matches_date_range(l, "YESTERDAY")
        ]

        # Active vs Inactive counts (Deduplicated)
        archived_leads = sum(1 for l in filtered_leads if l.is_archived)
        skipped_leads = sum(1 for l in filtered_leads if l.is_skipped)
        active_leads = sum(1 for l in filtered_leads if l.is_active)

        lifetime_archived = sum(1 for l in all_leads if l.is_archived)
        lifetime_skipped = sum(1 for l in all_leads if l.is_skipped)
        lifetime_active = sum(1 for l in all_leads if l.is_active)

        # Potential counts (Strictly Active pipeline)
        high_potential = sum(1 for l in filtered_leads if l.sales_potential == "HIGH" and l.is_active)
        mod_potential = sum(1 for l in filtered_leads if l.sales_potential == "MODERATE" and l.is_active)
        low_potential = sum(1 for l in filtered_leads if l.sales_potential == "LOW" and l.is_active)
        skip_potential = sum(1 for l in filtered_leads if l.is_skipped or l.sales_potential == "SKIP")

        # Action priorities (Strictly Active pipeline - Canonical single source of truth)
        contact_first = sum(1 for l in filtered_leads if l.outreach_priority == "CONTACT FIRST" and l.is_active)
        contact_later = sum(1 for l in filtered_leads if l.outreach_priority == "CONTACT LATER" and l.is_active)

        # WhatsApp M6 Statuses (Strict ground truth)
        wa_sent = sum(1 for l in filtered_leads if l.m6_status == "SENT")
        wa_failed = sum(1 for l in filtered_leads if l.m6_status == "FAILED")
        wa_no_num = sum(1 for l in filtered_leads if l.m6_status == "NO_WHATSAPP_NUMBER")
        wa_not_ready = sum(1 for l in filtered_leads if l.m6_status == "NOT_READY")
        wa_pending = sum(
            1 for l in filtered_leads
            if (l.outreach_channel in ("WhatsApp", "") or l.phone)
            and l.m6_status in ("PENDING", "")
            and l.outreach_priority == "CONTACT FIRST"
            and l.is_active
        )

        # Instagram & Cold Calling
        ig_pending = sum(1 for l in filtered_leads if (l.in_manual_instagram or l.outreach_channel == "Instagram DM") and l.is_active)
        calls_pending = sum(
            1 for l in filtered_leads
            if l.is_active
            and bool(l.phone)
            and not l.is_archived
            and not l.is_skipped
            and l.m6_status not in ("SENT", "FAILED", "NOT_READY", "NO_WHATSAPP_NUMBER", "SKIPPED_LIMIT", "SKIPPED_ALREADY_SENT", "SKIPPED_NO_WHATSAPP")
            and (l.outreach_priority in ("CONTACT FIRST", "CONTACT LATER") or l.in_contact_first or l.in_contact_later)
            and l.outreach_priority not in ("ARCHIVE", "SKIP")
            and l.final_action not in ("ARCHIVE", "SKIP")
            and l.sales_potential != "SKIP"
        )

        # Sales Outcomes (Real data)
        replies = sum(1 for l in filtered_leads if l.reply_status == "REPLIED")
        interested = sum(1 for l in filtered_leads if l.interested_status == "INTERESTED")
        won = sum(1 for l in filtered_leads if l.sales_stage == "WON")
        lost = sum(1 for l in filtered_leads if l.sales_stage == "LOST")
        revenue = sum(l.revenue for l in filtered_leads)

        # Follow-ups due
        follow_ups_due = sum(1 for l in filtered_leads if l.follow_up_at and l.follow_up_at[:10] <= today_str)

        # Top attention items count
        attention_items = DashboardAnalytics.get_needs_attention(leads_map)
        needs_attention_count = len(attention_items)

        # Activity feed
        recent_activity = DashboardAnalytics.get_today_activity(leads_map, files)

        # Charts aggregation
        leads_by_day = DashboardAnalytics._aggregate_by_day(all_leads)
        channel_dist = dict(Counter(l.outreach_channel or "WhatsApp" for l in filtered_leads))
        potential_dist = {
            "HIGH": high_potential,
            "MODERATE": mod_potential,
            "LOW": low_potential,
            "SKIP": skip_potential,
        }
        service_dist = dict(Counter(l.primary_service or "Business Digitalization" for l in filtered_leads if l.primary_service))
        city_dist = dict(Counter(l.city or "Unknown" for l in filtered_leads if l.city))
        pipeline_stages = dict(Counter(l.sales_stage for l in filtered_leads))

        # Milestone counts
        milestones = {
            "M1_INGESTION": len(all_leads),
            "M2_RESEARCH": sum(1 for l in all_leads if l.researched_at or l.website or l.instagram or l.gaps),
            "M3_QUALIFICATION": sum(1 for l in all_leads if l.is_active and (l.qualification_score is not None or l.sales_potential in ("HIGH", "MODERATE", "LOW"))),
            "M4_OUTREACH_READY": sum(1 for l in all_leads if l.is_active and bool(l.outreach_message)),
            "M5_MASTER_READY": sum(1 for l in all_leads if l.is_active and (l.in_master or l.in_contact_first or l.in_contact_later)),
            "M6_WHATSAPP_SENT": wa_sent,
        }

        # Unified uppercase channel counts
        channels = {
            "WHATSAPP": sum(1 for l in filtered_leads if l.outreach_channel.lower() == "whatsapp" or l.phone),
            "INSTAGRAM": sum(1 for l in filtered_leads if l.in_manual_instagram or l.outreach_channel.lower() in ("instagram", "instagram dm")),
            "COLD_CALLING": calls_pending,
            "EMAIL": sum(1 for l in filtered_leads if l.outreach_channel.lower() == "email" or l.email),
        }

        return {
            "total_leads_all_time": len(all_leads),
            "sources_discovered_count": len(files),
            "kpis": {
                "TOTAL_LEADS": len(filtered_leads),
                "total_leads": len(filtered_leads),
                "TOTAL_LIFETIME_LEADS": len(all_leads),
                "total_lifetime_leads": len(all_leads),
                "ACTIVE_LEADS": active_leads,
                "active_leads": active_leads,
                "ARCHIVED_LEADS": archived_leads,
                "archived_leads": archived_leads,
                "SKIPPED_LEADS": skipped_leads,
                "skipped_leads": skipped_leads,
                "lifetime_active_leads": lifetime_active,
                "lifetime_archived_leads": lifetime_archived,
                "lifetime_skipped_leads": lifetime_skipped,
                "TODAY_LEADS": len(today_leads),
                "today_leads": len(today_leads),
                "yesterday_leads": len(yesterday_leads),
                "CONTACT_FIRST": contact_first,
                "contact_first": contact_first,
                "CONTACT_LATER": contact_later,
                "contact_later": contact_later,
                "HIGH_POTENTIAL": high_potential,
                "high_potential": high_potential,
                "MODERATE_POTENTIAL": mod_potential,
                "moderate_potential": mod_potential,
                "LOW_POTENTIAL": low_potential,
                "low_potential": low_potential,
                "SKIP_POTENTIAL": skip_potential,
                "skip_potential": skip_potential,
                "WHATSAPP_SENT": wa_sent,
                "whatsapp_sent": wa_sent,
                "WHATSAPP_FAILED": wa_failed,
                "whatsapp_failed": wa_failed,
                "WHATSAPP_PENDING": wa_pending,
                "whatsapp_pending": wa_pending,
                "whatsapp_not_ready": wa_not_ready + wa_no_num,
                "INSTAGRAM_DM_LEADS": ig_pending,
                "instagram_pending": ig_pending,
                "COLD_CALLS_PENDING": calls_pending,
                "cold_calls_pending": calls_pending,
                "REPLIES": replies,
                "replies": replies,
                "INTERESTED": interested,
                "interested": interested,
                "FOLLOW_UPS_DUE": follow_ups_due,
                "follow_ups_due": follow_ups_due,
                "WON_CLIENTS": won,
                "won": won,
                "lost": lost,
                "REVENUE_GENERATED": revenue,
                "revenue": revenue,
                "needs_attention_count": needs_attention_count,
            },
            "today": {
                "total_discovered_today": len(today_leads),
                "whatsapp_sent_today": sum(1 for l in today_leads if l.m6_status == "SENT"),
            },
            "whatsapp_summary": {
                "TOTAL_WHATSAPP_ELIGIBLE": sum(1 for l in filtered_leads if l.phone or l.m6_recipient),
                "SENT": wa_sent,
                "FAILED": wa_failed,
                "PENDING": wa_pending,
                "NO_WHATSAPP_NUMBER": wa_no_num,
                "NOT_READY": wa_not_ready,
            },
            "milestones": milestones,
            "channels": channels,
            "geography": dict(sorted(city_dist.items(), key=lambda x: x[1], reverse=True)[:10]),
            "sales_potential_breakdown": potential_dist,
            "attention_items": attention_items,
            "recent_activity": recent_activity,
            "charts": {
                "leads_by_day": leads_by_day,
                "channel_distribution": channel_dist,
                "potential_distribution": potential_dist,
                "service_distribution": service_dist,
                "city_distribution": dict(sorted(city_dist.items(), key=lambda x: x[1], reverse=True)[:8]),
                "pipeline_stages": pipeline_stages,
            },
            "date_filter": {
                "selected": date_filter,
                "today": today_str,
                "yesterday": yesterday_str,
                "custom_start": custom_start,
                "custom_end": custom_end,
            },
            "file_counts": {
                "total_files": len(files),
                "m1_files": sum(1 for f in files if f.milestone == "M1"),
                "m2_files": sum(1 for f in files if f.milestone == "M2"),
                "m3_files": sum(1 for f in files if f.milestone == "M3"),
                "m4_files": sum(1 for f in files if f.milestone == "M4"),
                "m5_files": sum(1 for f in files if f.milestone == "M5"),
                "m6_files": sum(1 for f in files if f.milestone == "M6"),
                "batch_files": sum(1 for f in files if f.milestone == "Batch"),
            },
        }

    @staticmethod
    def _aggregate_by_day(leads: list[LeadRecord]) -> dict[str, int]:
        """Aggregate lead discovery/activity counts by date string (YYYY-MM-DD)."""
        counts: dict[str, int] = defaultdict(int)
        for l in leads:
            date_key = ""
            for ts in (l.discovered_at, l.researched_at, l.qualified_at, l.last_updated_at):
                if ts and len(ts) >= 10:
                    date_key = ts[:10]
                    break
            if date_key:
                counts[date_key] += 1
            else:
                counts["Undated"] += 1
        return dict(sorted(counts.items()))

    @staticmethod
    def get_today_activity(leads_map: dict[str, LeadRecord], files: list[DiscoveredFile]) -> list[dict[str, Any]]:
        """Build chronological real-time event feed for today."""
        today_str = _get_utc_today_str()
        events: list[dict[str, Any]] = []

        # 1. File modified/generated events today
        for f in files:
            if f.modified_time and f.modified_time[:10] == today_str:
                events.append({
                    "timestamp": f.modified_time,
                    "time_display": f.modified_time[11:19] if len(f.modified_time) >= 19 else "",
                    "type": "FILE_GENERATED",
                    "milestone": f.milestone,
                    "title": f"Pipeline File: {f.filename}",
                    "description": f"{f.scenario} ({f.record_count} records, {f.size_bytes / 1024:.1f} KB)",
                    "lead_id": "",
                    "icon": "file",
                })

        # 2. Lead research & qualification events today
        for lead in leads_map.values():
            if lead.m6_sent_at and lead.m6_sent_at[:10] == today_str:
                events.append({
                    "timestamp": lead.m6_sent_at,
                    "time_display": lead.m6_sent_at[11:19] if len(lead.m6_sent_at) >= 19 else "",
                    "type": "WHATSAPP_SENT",
                    "milestone": "M6",
                    "title": f"WhatsApp Message Sent → {lead.business_name}",
                    "description": f"Delivered via automated engine to {lead.m6_recipient}",
                    "lead_id": lead.lead_id,
                    "icon": "send",
                })

            if lead.m6_history:
                for h in lead.m6_history:
                    hts = h.get("timestamp") or ""
                    if hts and hts[:10] == today_str:
                        status = h.get("send_status") or "ATTEMPT"
                        err = h.get("error") or ""
                        events.append({
                            "timestamp": hts,
                            "time_display": hts[11:19] if len(hts) >= 19 else "",
                            "type": f"M6_{status}",
                            "milestone": "M6",
                            "title": f"M6 Execution: {lead.business_name} ({status})",
                            "description": err or f"Attempt #{h.get('attempt', 1)} status: {status}",
                            "lead_id": lead.lead_id,
                            "icon": "alert" if "FAIL" in status or "ERROR" in status else "check",
                        })

            if lead.qualified_at and lead.qualified_at[:10] == today_str:
                events.append({
                    "timestamp": lead.qualified_at,
                    "time_display": lead.qualified_at[11:19] if len(lead.qualified_at) >= 19 else "",
                    "type": "LEAD_QUALIFIED",
                    "milestone": "M3",
                    "title": f"Lead Qualified: {lead.business_name}",
                    "description": f"Potential: {lead.sales_potential} | Action: {lead.final_action or lead.outreach_priority}",
                    "lead_id": lead.lead_id,
                    "icon": "target",
                })

        # Sort reverse chronologically
        events.sort(key=lambda e: e.get("timestamp", ""), reverse=True)
        return events[:150]

    @staticmethod
    def get_needs_attention(leads_map: dict[str, LeadRecord]) -> list[dict[str, Any]]:
        """Identify high-priority action items requiring immediate human attention."""
        attention_items: list[dict[str, Any]] = []

        for lead in leads_map.values():
            # 1. Failed WhatsApp sends
            if lead.m6_status == "FAILED":
                attention_items.append({
                    "priority": "HIGH",
                    "urgency_rank": 1,
                    "type": "FAILED_SEND",
                    "title": f"WhatsApp Send Failed — {lead.business_name}",
                    "lead_id": lead.lead_id,
                    "business_name": lead.business_name,
                    "phone": lead.phone or lead.m6_recipient,
                    "reason": lead.m6_error or "Send attempt failed",
                    "suggested_action": "Verify number format or send manually",
                })

            # 2. Instagram Manual DMs pending
            elif lead.in_manual_instagram or (lead.outreach_channel == "Instagram DM" and lead.m6_status != "SENT"):
                attention_items.append({
                    "priority": "MEDIUM",
                    "urgency_rank": 2,
                    "type": "PENDING_INSTAGRAM",
                    "title": f"Instagram DM Ready — {lead.business_name}",
                    "lead_id": lead.lead_id,
                    "business_name": lead.business_name,
                    "instagram": lead.instagram,
                    "reason": "Active Instagram brand without direct phone number",
                    "suggested_action": "Copy generated DM pitch and send on Instagram",
                })

            # 3. High Potential Leads never contacted
            elif lead.sales_potential == "HIGH" and lead.outreach_priority == "CONTACT FIRST" and lead.m6_status not in ("SENT", "AWAITING_MANUAL_SEND"):
                attention_items.append({
                    "priority": "MEDIUM",
                    "urgency_rank": 3,
                    "type": "UNCONTACTED_HIGH_POTENTIAL",
                    "title": f"Uncontacted High Potential — {lead.business_name}",
                    "lead_id": lead.lead_id,
                    "business_name": lead.business_name,
                    "phone": lead.phone,
                    "reason": f"Fit for {lead.primary_service or 'Digitalization'} (PKR 10k–50k opportunity)",
                    "suggested_action": "Execute WhatsApp outreach or initiate Cold Call",
                })

            # 4. Review Flags
            elif lead.review_flag:
                attention_items.append({
                    "priority": "LOW",
                    "urgency_rank": 4,
                    "type": "REVIEW_FLAG",
                    "title": f"Audit Review Flag — {lead.business_name}",
                    "lead_id": lead.lead_id,
                    "business_name": lead.business_name,
                    "phone": lead.phone,
                    "reason": lead.review_reason or "Flagged during M5 quality audit",
                    "suggested_action": "Review lead details before initiating outreach",
                })

        attention_items.sort(key=lambda x: x["urgency_rank"])
        return attention_items
