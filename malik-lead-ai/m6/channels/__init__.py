"""M6 — send channels registry."""

from __future__ import annotations

from .base import ChannelError, OutreachChannel
from .dry_run import DryRunChannel
from .whatsapp import WhatsAppAssistChannel


def build_channel(name: str, *, open_browser: bool = True, profile_dir=None, **kwargs) -> OutreachChannel:
    """Instantiate a channel by internal name or CLI alias.

    ``assist`` / ``whatsapp`` / ``link`` → assist channel (wa.me deep link)
    ``playwright``                      → optional automated WhatsApp Web channel
    ``dry_run``                         → never sends anything
    """
    from ..config import CHANNEL_ALIASES, CHANNEL_WHATSAPP, CHANNEL_WHATSAPP_PLAYWRIGHT

    name = CHANNEL_ALIASES.get(name, name)

    if name == CHANNEL_WHATSAPP:
        return WhatsAppAssistChannel(open_browser=open_browser)
    if name == CHANNEL_WHATSAPP_PLAYWRIGHT:
        from .whatsapp_playwright import WhatsAppPlaywrightChannel

        return WhatsAppPlaywrightChannel(profile_dir=profile_dir, **kwargs)
    if name == "dry_run":
        return DryRunChannel()
    raise ChannelError(f"Unknown M6 channel: {name!r}")


__all__ = ["ChannelError", "OutreachChannel", "DryRunChannel", "WhatsAppAssistChannel", "build_channel"]
