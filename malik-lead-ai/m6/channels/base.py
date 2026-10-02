"""M6 — channel abstraction (base contract).

The M6 engine only knows this interface:

    channel.send(recipient, message, lead=...) -> SendResult

Everything browser- or provider-specific (wa.me deep links, WhatsApp Web
automation, or a future official WhatsApp Business API) lives in a concrete
subclass under ``m6/channels/``. Replacing a channel never touches M6 core
logic.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import M5Lead, SendResult


class ChannelError(RuntimeError):
    """Channel cannot be used at all (missing dependency, no session, ...)."""


class OutreachChannel(ABC):
    """Base class for every M6 send channel."""

    name: str = "base"
    #: True when the channel transmits without human interaction.
    automated: bool = False

    def ensure_ready(self) -> None:
        """Raise :class:`ChannelError` when the channel cannot run now."""

    @abstractmethod
    def send(self, recipient: str, message: str, *, lead: M5Lead | None = None) -> SendResult:
        """Send ONE message to ``recipient`` (E.164, e.g. '+923136162007')."""

    def preview_link(self, recipient: str, message: str) -> str:
        """Optional: the link this channel would open/send to."""
        return ""

    def describe(self) -> str:
        mode = "automated" if self.automated else "human-in-the-loop"
        return f"{self.name} ({mode})"


__all__ = ["OutreachChannel", "ChannelError"]
