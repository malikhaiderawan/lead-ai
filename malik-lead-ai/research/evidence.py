"""Milestone 2 — Evidence class and status standards for structured research findings."""

from __future__ import annotations

from dataclasses import dataclass


class EvidenceClass:
    VERIFIED_FACT = "VERIFIED_FACT"
    REASONABLE_OBSERVATION = "REASONABLE_OBSERVATION"
    UNKNOWN = "UNKNOWN"


class ResourceStatus:
    """Standardized 5-state resource availability status."""
    FOUND = "FOUND"                  # Verified present / accessible
    NOT_FOUND = "NOT_FOUND"          # Verified non-existent (HTTP 404, empty handle)
    CHECK_FAILED = "CHECK_FAILED"    # Network, DNS, timeout, or connection error
    BLOCKED = "BLOCKED"              # HTTP 403, 429, cloudflare, login wall, anti-bot
    UNKNOWN = "UNKNOWN"              # Not provided in input and not discovered


@dataclass
class Evidence:
    """One research finding with an explicit evidence class and provenance."""

    class_: str
    statement: str
    detail: str = ""
    source_url: str = ""

    def to_dict(self) -> dict[str, str]:
        res = {
            "class": self.class_,
            "statement": self.statement,
            "detail": self.detail,
        }
        if self.source_url:
            res["source_url"] = self.source_url
        return res
