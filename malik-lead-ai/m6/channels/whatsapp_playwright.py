"""M6 — automated WhatsApp Web channel (Playwright).

This is the DEFAULT channel for ``outreach-execute`` (``--channel playwright``).
It sends exactly one approved M6 message per lead through WhatsApp Web with
NO manual ``input()`` confirmation anywhere in the flow.

How it works:
    1. One-time profile bootstrap: the user's own Chrome WhatsApp Web session
       (``~/.config/google-chrome`` → ``Profile 1``) is copied into
       ``~/.malikaxiom/whatsapp-profile`` (``Local State`` + profile dir,
       ``Singleton*`` lock files stripped). Later runs reuse that copy, which
       keeps its own up-to-date session. Re-sync by deleting the directory.
    2. Launches headed Chrome (``channel="chrome"``) with a persistent context
       on that profile. Headless Chromium cannot load the logged-in session.
    3. Opens ``https://web.whatsapp.com/send?phone=<digits>&text=<message>``
       so WhatsApp itself prefills the EXACT approved message.
    4. Verifies the compose box contains exactly the approved message
       (whitespace-normalised compare). On mismatch it clears any stale draft,
       reloads to re-apply the URL prefill, and as a last resort inserts the
       text directly — if none of that matches, it FAILS **without sending**.
    5. Clicks the Send button (focused-Enter fallback) and verifies a new
       message row appeared in the chat containing the sent text.
    6. Returns ``FAILED`` whenever login/verification does not succeed, so the
       engine records the attempt honestly and never claims a phantom send.
       When WhatsApp itself reports that the number has no account, it returns
       ``NO_WHATSAPP_NUMBER`` instead — a dead-end fact M6 never retries.

Deliberately NOT implemented: stealth/anti-detection, captcha or restriction
bypasses, bulk blasting, automatic follow-ups or auto-replies. The user is
responsible for complying with WhatsApp's terms of service.
"""

from __future__ import annotations

import logging
import os
import shutil
import sys
import time
import urllib.parse
from pathlib import Path

from ..config import (
    NO_WHATSAPP_DETAIL,
    NO_WHATSAPP_MARKERS,
    STATUS_FAILED,
    STATUS_NO_WHATSAPP,
    STATUS_SENT,
)
from ..models import M5Lead, SendResult
from ..storage import utc_now_iso
from .base import ChannelError, OutreachChannel
from .whatsapp import build_wa_link

logger = logging.getLogger(__name__)

DEFAULT_PROFILE_DIR = Path.home() / ".malikaxiom" / "whatsapp-profile"

#: Chrome profile directories, in preference order (source AND destination name).
PROFILE_NAMES: tuple[str, ...] = ("Profile 5", "Profile 6", "Default", "Profile 1")

_COMPOSE_BOX = (
    'footer div[contenteditable="true"], '
    '#main footer [contenteditable="true"], '
    'div[contenteditable="true"][data-tab="10"], '
    'div[contenteditable="true"][aria-label*="Type a message"]'
)
_SEND_BUTTONS: tuple[str, ...] = (
    '#main footer button[aria-label*="Send"]',
    'footer button[aria-label*="Send"]',
    'button[aria-label*="Send"]',
    'button:has(span[data-icon="send"])',
    'span[data-icon="send"]',
)
_QR_CONTAINER = "div[data-ref]"
_MESSAGE_ROWS = '#main div[role="row"]'


def no_whatsapp_marker(text: str | None) -> str:
    """Return WhatsApp's wording proving ``text`` has no WhatsApp account.

    Case-insensitive, so it survives WhatsApp's own capitalisation changes.
    """
    lowered = (text or "").lower()
    for marker in NO_WHATSAPP_MARKERS:
        if marker in lowered:
            return marker
    return ""


def is_no_whatsapp_reason(reason: str | None) -> bool:
    """True when a failure reason means 'this number has no WhatsApp account'."""
    text = (reason or "").strip().lower()
    if not text:
        return False
    return text.startswith(NO_WHATSAPP_DETAIL.lower()) or bool(no_whatsapp_marker(text))

_INSERT_TEXT_JS = """(args) => {
    const [selector, text] = args;
    const el = document.querySelector(selector);
    if (el) {
        el.focus();
        document.execCommand('insertText', false, text);
        return true;
    }
    return false;
}"""


def _norm(text: str | None) -> str:
    """Whitespace-normalised comparison form (emoji/UTF-8 preserved)."""
    return " ".join((text or "").split())


#: Codepoints WhatsApp Web renders as ``<img>`` inside sent bubbles (so
#: ``inner_text()`` omits them): pictographs + the emoji modifiers that often
#: accompany them (ZWJ, variation selectors, keycap).
_EMOJI_RANGES: tuple[tuple[int, int], ...] = (
    (0x1F000, 0x1FFFF),  # emoticons, transport & map, supplemental symbols
    (0x2600, 0x27BF),    # misc symbols + dingbats (✉ ✅ ⭐ …)
    (0x2B00, 0x2BFF),    # misc symbols and arrows
)
_EMOJI_SINGLE: frozenset[int] = frozenset({0x200D, 0xFE0E, 0xFE0F, 0x20E3})


def _strip_emoji(text: str | None) -> str:
    """Drop characters that sent-bubble DOM stores as ``<img>`` instead of text."""
    return "".join(
        ch for ch in (text or "")
        if ord(ch) not in _EMOJI_SINGLE
        and not any(lo <= ord(ch) <= hi for lo, hi in _EMOJI_RANGES)
    )


def _comparable(text: str | None) -> str:
    """Whitespace-, replacement-char-, and emoji-normalised form for bubble text comparison."""
    cleaned = _strip_emoji(text).replace("\ufffd", "")
    return _norm(cleaned)


def _row_matches(message: str, row_text: str) -> bool:
    """True when a chat row contains the approved message.

    Tries the exact (whitespace-normalised) comparison first, then falls back
    to an emoji-insensitive comparison — WhatsApp converts emoji in sent
    bubbles to ``<img alt="👋">`` which ``inner_text()`` does not return, while
    the approved message still contains the literal emoji character.
    """
    needle = _norm(message)[:80]
    if needle and needle in _norm(row_text):
        return True
    loose = _comparable(message)[:80]
    return bool(loose) and loose in _comparable(row_text)


def chrome_user_data_dirs() -> list[Path]:
    """Candidate Chrome user-data directories for this platform."""
    candidates: list[Path] = []
    if sys.platform == "darwin":
        candidates.append(Path.home() / "Library" / "Application Support" / "Google" / "Chrome")
    elif os.name == "nt":
        local = os.environ.get("LOCALAPPDATA")
        if local:
            candidates.append(Path(local) / "Google" / "Chrome" / "User Data")
    else:
        candidates.append(Path.home() / ".config" / "google-chrome")
    return [path for path in candidates if path.is_dir()]


class WhatsAppPlaywrightChannel(OutreachChannel):
    """Automated WhatsApp Web sender built on Playwright (lazy import)."""

    name = "whatsapp_playwright"
    automated = True

    def __init__(
        self,
        profile_dir: Path | str | None = None,
        *,
        headless: bool = False,
        login_timeout_s: int = 120,
        verify_timeout_s: int = 30,
        prefill_timeout_s: int = 12,
        min_interval_s: int = 0,
    ) -> None:
        self.profile_dir = Path(profile_dir) if profile_dir else DEFAULT_PROFILE_DIR
        self.headless = headless
        self.login_timeout_s = login_timeout_s
        self.verify_timeout_s = verify_timeout_s
        self.prefill_timeout_s = prefill_timeout_s
        self.min_interval_s = min_interval_s
        self._last_send_ts = 0.0
        self._profile_name = PROFILE_NAMES[0]

    # -- setup --------------------------------------------------------------
    def ensure_ready(self) -> None:
        vendor_dir = Path(__file__).resolve().parent.parent.parent / "vendor"
        if vendor_dir.exists() and str(vendor_dir) not in sys.path:
            sys.path.append(str(vendor_dir))
        try:
            import playwright.sync_api  # noqa: F401
        except Exception as exc:  # noqa: BLE001
            raise ChannelError(
                "Playwright is not installed. Install it with:\n"
                "  pip install playwright\n"
                "  python -m playwright install chromium\n"
                "or use the assist channel (--channel assist)."
            ) from exc

    def preview_link(self, recipient: str, message: str) -> str:
        return build_wa_link(recipient, message)

    def describe(self) -> str:
        return f"whatsapp_playwright (automated, profile={self.profile_dir})"

    # -- send ---------------------------------------------------------------
    def send(self, recipient: str, message: str, *, lead: M5Lead | None = None) -> SendResult:
        self.ensure_ready()
        self._respect_pacing()
        if self.headless:
            logger.warning(
                "whatsapp_playwright: headless mode cannot load the logged-in WhatsApp "
                "session — expect a FAILED result; run headed."
            )

        from playwright.sync_api import sync_playwright

        digits = "".join(ch for ch in recipient if ch.isdigit())
        encoded_msg = urllib.parse.quote(message, safe="")
        link = f"https://web.whatsapp.com/send?phone={digits}&text={encoded_msg}"

        self._ensure_profile()

        with sync_playwright() as pw:
            try:
                context = pw.chromium.launch_persistent_context(
                    user_data_dir=str(self.profile_dir),
                    headless=self.headless,
                    channel="chrome",
                    args=[
                        "--no-default-browser-check",
                        "--no-first-run",
                        f"--profile-directory={self._profile_name}",
                    ],
                )
            except Exception as exc:  # noqa: BLE001
                raise ChannelError(
                    f"Could not launch Chrome with the WhatsApp profile at "
                    f"{self.profile_dir}: {exc}"
                ) from exc

            try:
                page = context.pages[0] if context.pages else context.new_page()
                page.goto(link, wait_until="domcontentloaded", timeout=60_000)

                ready, reason = self._wait_until_ready(page)
                if not ready:
                    return self._failure_result(page, reason, link)

                staged, stage_reason = self._stage_message(page, link, message)
                if not staged:
                    return self._failure_result(page, stage_reason, link)

                before = self._matching_rows(page, message)
                self._click_send(page)

                if self._verify_sent(page, message, before=before):
                    return SendResult(
                        status=STATUS_SENT,
                        sent_at=utc_now_iso(),
                        verification="browser_verification",
                        detail="Message verified in the WhatsApp Web chat.",
                        link=link,
                    )
                return SendResult(
                    status=STATUS_FAILED,
                    detail=(
                        "Message could not be verified in the chat — treat as NOT sent "
                        "and check manually."
                    ),
                    verification="failed",
                    link=link,
                )
            finally:
                try:
                    context.close()
                except Exception:  # noqa: BLE001
                    logger.debug("Failed to close the Playwright context cleanly", exc_info=True)

    # -- profile bootstrap --------------------------------------------------
    def _ensure_profile(self) -> None:
        """Copy the user's Chrome WhatsApp session once; strip stale locks always."""
        self.profile_dir.mkdir(parents=True, exist_ok=True)

        source_root: Path | None = None
        for root in chrome_user_data_dirs():
            if any((root / name).is_dir() for name in PROFILE_NAMES):
                source_root = root
                break

        # Reuse an existing destination profile (it maintains its own session).
        existing = next(
            (name for name in PROFILE_NAMES if (self.profile_dir / name).is_dir()), None
        )
        if existing is None:
            if source_root is None:
                raise ChannelError(
                    f"No Chrome profile found to bootstrap a WhatsApp Web session into "
                    f"{self.profile_dir}. Log in to WhatsApp Web once in Google Chrome, "
                    "then re-run (or use --channel assist)."
                )
            source_name = next(
                (name for name in PROFILE_NAMES if (source_root / name).is_dir()), None
            )
            if source_name is None:
                raise ChannelError(
                    f"No Chrome profile directory ({', '.join(PROFILE_NAMES)}) in {source_root}."
                )
            logger.info(
                "Syncing Chrome %r session into %s (one-time)…", source_name, self.profile_dir
            )
            local_state = source_root / "Local State"
            if local_state.exists():
                shutil.copy2(local_state, self.profile_dir / "Local State")
            shutil.copytree(
                source_root / source_name,
                self.profile_dir / source_name,
                ignore=shutil.ignore_patterns("Singleton*", "*.lock", "LOCK", "*.tmp"),
                dirs_exist_ok=True,
            )
            self._profile_name = source_name
        else:
            self._profile_name = existing
            if not (self.profile_dir / "Local State").exists() and source_root is not None:
                local_state = source_root / "Local State"
                if local_state.exists():
                    shutil.copy2(local_state, self.profile_dir / "Local State")

        # Strip lock files a previous run may have left behind.
        for base in (self.profile_dir, self.profile_dir / self._profile_name):
            if not base.is_dir():
                continue
            for lock in base.glob("Singleton*"):
                try:
                    lock.unlink()
                except OSError:  # noqa: BLE001
                    logger.debug("Could not remove stale lock %s", lock, exc_info=True)

    # -- browser flow internals ---------------------------------------------
    def _no_whatsapp_marker_on_page(self, page) -> str:
        """Detect WhatsApp's own 'this number has no account' wording."""
        try:
            if page.locator(f"text={NO_WHATSAPP_MARKERS[0]}").count() > 0:
                return NO_WHATSAPP_MARKERS[0]
        except Exception:  # noqa: BLE001
            logger.debug("No-WhatsApp selector probe failed", exc_info=True)
        try:
            return no_whatsapp_marker(page.inner_text("body"))
        except Exception:  # noqa: BLE001
            logger.debug("No-WhatsApp body probe failed", exc_info=True)
        return ""

    def _failure_result(self, page, reason: str, link: str) -> SendResult:
        """A failed attempt — reported as a dead-end number when WhatsApp says so."""
        if is_no_whatsapp_reason(reason) or self._no_whatsapp_marker_on_page(page):
            logger.warning(
                "WhatsApp reports no account for this number — recording "
                "NO_WHATSAPP_NUMBER (never retried automatically).",
            )
            return SendResult(
                status=STATUS_NO_WHATSAPP,
                detail=f"{NO_WHATSAPP_DETAIL} — {reason}",
                verification="no_whatsapp",
                link=link,
            )
        return SendResult(
            status=STATUS_FAILED,
            detail=f"{reason} — nothing was sent.",
            verification="failed",
            link=link,
        )

    def _wait_until_ready(self, page) -> tuple[bool, str]:
        """Wait until a chat with a compose box is open (or report why not)."""
        deadline = time.time() + self.login_timeout_s
        qr_seen = False
        probe = 0
        while time.time() < deadline:
            try:
                if page.locator(_COMPOSE_BOX).count() > 0:
                    return True, ""
                if not qr_seen and page.locator(_QR_CONTAINER).count() > 0:
                    qr_seen = True
                    logger.warning(
                        "WhatsApp Web shows a QR code — scan it once in the browser; "
                        "the login is remembered in %s.", self.profile_dir,
                    )
                probe += 1
                if probe % 5 == 1:  # cheap enough to run every ~5s
                    marker = self._no_whatsapp_marker_on_page(page)
                    if marker:
                        return False, f"{NO_WHATSAPP_DETAIL} (WhatsApp said: {marker!r})"
            except Exception:  # noqa: BLE001
                logger.debug("Readiness probe failed", exc_info=True)
            time.sleep(1)
        if qr_seen:
            return False, (
                f"WhatsApp Web login required (QR not scanned within {self.login_timeout_s}s)"
            )
        return False, (
            f"No chat/compose box appeared within {self.login_timeout_s}s "
            "(WhatsApp Web did not load)"
        )

    def _find_compose(self, page):
        """Return the compose-box locator, preferring the one inside the chat footer."""
        try:
            locator = page.locator(_COMPOSE_BOX)
            count = locator.count()
        except Exception:  # noqa: BLE001
            return None
        for index in range(count):
            candidate = locator.nth(index)
            try:
                if candidate.evaluate("el => !!el.closest('footer')"):
                    return candidate
            except Exception:  # noqa: BLE001
                continue
        return locator.first if count else None

    def _await_text(self, box, message: str, timeout_s: int) -> bool:
        """True once the compose box contains exactly ``message`` (normalised)."""
        target = _norm(message)
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            try:
                if _norm(box.inner_text()) == target:
                    return True
            except Exception:  # noqa: BLE001
                pass
            time.sleep(0.5)
        return False

    def _stage_message(self, page, link: str, message: str) -> tuple[bool, str]:
        """Make the compose box hold exactly the approved message, or fail safely."""
        box = self._find_compose(page)
        if box is None:
            return False, "Could not find the WhatsApp message box"

        # Fast path: URL prefill (WhatsApp's own mechanism, exact bytes).
        if self._await_text(box, message, self.prefill_timeout_s):
            if "\ufffd" not in (box.inner_text() or ""):
                return True, ""
            logger.warning("URL prefill contained replacement character; re-inserting clean text.")

        # Clear any corrupted or stale draft and insert text directly if replacement characters appear
        if "\ufffd" in (box.inner_text() or ""):
            try:
                box.click(timeout=5_000)
                page.keyboard.press("Meta+a")
                page.keyboard.press("Control+a")
                page.keyboard.press("Backspace")
                page.evaluate(_INSERT_TEXT_JS, [_COMPOSE_BOX, message])
                if "\ufffd" not in (box.inner_text() or ""):
                    return True, ""
            except Exception:  # noqa: BLE001
                logger.debug("Clean text re-insertion failed", exc_info=True)

        # Clear any stale draft and reload so the URL prefill re-applies.
        try:
            box.click(timeout=5_000)
            page.keyboard.press("Control+a")
            page.keyboard.press("Backspace")
        except Exception:  # noqa: BLE001
            logger.debug("Could not clear the compose box", exc_info=True)
        try:
            page.goto(link, wait_until="domcontentloaded", timeout=60_000)
        except Exception:  # noqa: BLE001
            return False, "Reload to re-apply the message prefill failed"
        ready, reason = self._wait_until_ready(page)
        if not ready:
            return False, reason
        box = self._find_compose(page)
        if box is None:
            return False, "Could not find the WhatsApp message box after reload"
        if self._await_text(box, message, self.prefill_timeout_s):
            return True, ""

        # Last resort: insert the text directly into the (now empty) box.
        try:
            box.click(timeout=5_000)
            page.evaluate(_INSERT_TEXT_JS, [_COMPOSE_BOX, message])
        except Exception:  # noqa: BLE001
            logger.debug("Direct text insertion failed", exc_info=True)
        if self._await_text(box, message, 5):
            return True, ""

        return False, (
            "The message box does not contain exactly the approved message "
            "(prefill/insert verification failed)"
        )

    def _click_send(self, page) -> None:
        # Try scoped selectors first so a stray "Send" button elsewhere in the
        # DOM can never be clicked before the chat's own send button.
        for selector in _SEND_BUTTONS:
            try:
                button = page.locator(selector)
                if button.count() == 0:
                    continue
                button.first.click(timeout=5_000)
                return
            except Exception:  # noqa: BLE001
                logger.debug("Send button %r click failed", selector, exc_info=True)
        # Fallback: Enter, but only while the compose box actually has focus.
        try:
            focused = page.evaluate(
                "() => { const el = document.activeElement;"
                " return !!(el && el.closest && el.closest('[contenteditable=\"true\"]')); }"
            )
            if not focused:
                box = self._find_compose(page)
                if box is None:
                    return
                box.click(timeout=5_000)
            page.keyboard.press("Enter")
        except Exception:  # noqa: BLE001
            logger.debug("Enter-to-send failed", exc_info=True)

    def _matching_rows(self, page, message: str) -> int:
        """Count chat rows (outside the compose footer) containing the message text.

        Uses :func:`_row_matches` so emoji rendered as ``<img>`` inside sent
        bubbles (which ``inner_text()`` omits) cannot cause a false negative.
        """
        if not _norm(message):
            return 0
        try:
            rows = page.locator(_MESSAGE_ROWS)
            count = rows.count()
        except Exception:  # noqa: BLE001
            return 0
        hits = 0
        for index in range(count):
            row = rows.nth(index)
            try:
                if row.evaluate("el => !!el.closest('footer')"):
                    continue
                if _row_matches(message, row.inner_text()):
                    hits += 1
            except Exception:  # noqa: BLE001
                continue
        return hits

    def _verify_sent(self, page, message: str, *, before: int) -> bool:
        """True once a NEW chat row containing the message appears."""
        deadline = time.time() + self.verify_timeout_s
        while time.time() < deadline:
            if self._matching_rows(page, message) > before:
                return True
            time.sleep(1)
        return False

    def _respect_pacing(self) -> None:
        if self.min_interval_s <= 0:
            return
        elapsed = time.time() - self._last_send_ts
        if self._last_send_ts and elapsed < self.min_interval_s:
            time.sleep(self.min_interval_s - elapsed)
        self._last_send_ts = time.time()


__all__ = ["WhatsAppPlaywrightChannel", "DEFAULT_PROFILE_DIR"]




