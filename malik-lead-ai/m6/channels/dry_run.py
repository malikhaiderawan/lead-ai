"""M6 — dry-run channel.

Used by ``outreach-execute --dry-run``. It NEVER opens a browser, never
touches WhatsApp, and never records a send. It exists so the engine has a
real channel object to talk to while remaining physically unable to send.
"""

from __future__ import annotations

from ..models import M5Lead, SendResult
from .base import OutreachChannel


class DryRunChannel(OutreachChannel):
    name = "dry_run"
    automated = False

    def send(self, recipient: str, message: str, *, lead: M5Lead | None = None) -> SendResult:
        return SendResult(
            status="DRY_RUN",
            detail="Dry run — nothing was transmitted.",
            verification="none",
        )

    def describe(self) -> str:
        return "dry_run (no transmission)"


__all__ = ["DryRunChannel"]
