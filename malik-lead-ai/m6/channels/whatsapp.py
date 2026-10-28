"""M6 — WhatsApp channel (assist mode, standard library only).

How it works locally, with zero paid APIs and zero third-party packages:

1. M6 composes the message and builds a click-to-chat link:
   ``https://wa.me/923136162007?text=<url-encoded message>``
2. The channel opens that link in the user's own browser (WhatsApp Web /
   WhatsApp Desktop). The chat is opened with the message already typed.
3. The human presses Send once. M6 records ``AWAITING_MANUAL_SEND``.
4. The user (or the interactive prompt) confirms the send → M6 records ``SENT``
   with ``verification = manual_confirmation``.

One link, one chat, one lead at a time. No bulk blasting, no stealth, no
platform-restriction bypassing. This channel is intentionally conservative:
M6 cannot claim a message was sent when a human has not sent it.
"""

from __future__ import annotations

import logging
import urllib.parse
import webbrowser

from ..config import STATUS_AWAITING_MANUAL, STATUS_FAILED, STATUS_SENT
from ..models import M5Lead, SendResult
from .base import ChannelError, OutreachChannel

logger = logging.getLogger(__name__)


def build_wa_link(recipient_e164: str, message: str) -> str:
    """Build a wa.me click-to-chat link with the message pre-filled."""
    digits = "".join(ch for ch in recipient_e164 if ch.isdigit())
    if not digits:
        raise ChannelError(f"Cannot build a WhatsApp link for recipient {recipient_e164!r}")
    return f"https://wa.me/{digits}?text={urllib.parse.quote(message, safe='')}"


def build_web_wa_link(recipient_e164: str, message: str) -> str:
    """Build a direct web.whatsapp.com link with the message pre-filled."""
    digits = "".join(ch for ch in recipient_e164 if ch.isdigit())
    if not digits:
        raise ChannelError(f"Cannot build a WhatsApp link for recipient {recipient_e164!r}")
    return f"https://web.whatsapp.com/send?phone={digits}&text={urllib.parse.quote(message, safe='')}"


def _copy_to_clipboard(text: str) -> None:
    """Copy text directly to system clipboard on macOS for convenient Cmd+V pasting."""
    import platform
    import subprocess
    if platform.system() == "Darwin":
        try:
            subprocess.run(["pbcopy"], input=text.encode("utf-8"), check=False)
        except Exception:  # noqa: BLE001
            pass


def _open_desktop_browser(url: str) -> bool:
    """Open the URL in the user's active Google Chrome if available, else default browser."""
    import platform
    import subprocess
    from pathlib import Path

    if platform.system() == "Darwin":
        chrome_app = Path("/Applications/Google Chrome.app")
        if chrome_app.exists():
            try:
                res = subprocess.run(["open", "-a", "Google Chrome", url], capture_output=True, text=True)
                if res.returncode == 0:
                    return True
            except Exception:  # noqa: BLE001
                pass
    return webbrowser.open(url)


def confirmed_result(detail: str = "Confirmed by the user as sent manually.", link: str = "") -> SendResult:
    """Result to store after the human confirms the send."""
    from ..storage import utc_now_iso

    return SendResult(
        status=STATUS_SENT,
        detail=detail,
        sent_at=utc_now_iso(),
        verification="manual_confirmation",
        link=link,
    )


class WhatsAppAssistChannel(OutreachChannel):
    """Opens one pre-filled WhatsApp chat per lead; the human presses Send."""

    name = "whatsapp"
    automated = False

    def __init__(self, open_browser: bool = True, browser_open=None) -> None:
        self.open_browser = open_browser
        self._browser_open = browser_open or _open_desktop_browser

    def preview_link(self, recipient: str, message: str) -> str:
        return build_wa_link(recipient, message)

    def send(self, recipient: str, message: str, *, lead: M5Lead | None = None) -> SendResult:
        link = build_wa_link(recipient, message)
        web_link = build_web_wa_link(recipient, message)
        if not self.open_browser:
            return SendResult(
                status=STATUS_AWAITING_MANUAL,
                detail="Browser opening disabled (--no-browser). Link generated only.",
                verification="pending",
                link=link,
            )

        _copy_to_clipboard(message)

        try:
            opened = self._browser_open(web_link)
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to open WhatsApp link: %s", exc)
            return SendResult(
                status=STATUS_FAILED,
                detail=f"Could not open the browser: {exc}",
                verification="failed",
                link=link,
            )

        if opened is False:
            return SendResult(
                status=STATUS_FAILED,
                detail="The browser reported that it could not open the WhatsApp link.",
                verification="failed",
                link=link,
            )

        return SendResult(
            status=STATUS_AWAITING_MANUAL,
            detail="WhatsApp chat opened in Google Chrome with the message pre-filled — press Send once, then confirm.",
            verification="pending",
            link=web_link,
        )

    def describe(self) -> str:
        mode = "browser opened" if self.open_browser else "link only"
        return f"whatsapp (assist, {mode})"


__all__ = ["WhatsAppAssistChannel", "build_wa_link", "build_web_wa_link", "confirmed_result"]

