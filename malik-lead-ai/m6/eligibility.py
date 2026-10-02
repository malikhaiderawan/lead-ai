"""M6 — eligibility gate.

M6 contacts what M5 decided is ready for contact.

Default: ``CONTACT FIRST`` and ``CONTACT LATER`` are eligible.
``ARCHIVE`` / ``SKIP`` / unknown actions are NOT eligible.
If an explicit action filter is passed via ``include_actions``, it is respected.
"""

from __future__ import annotations

from .models import M5Lead

# Canonical M6 action vocabulary.
ACTION_CONTACT_FIRST = "CONTACT_FIRST"
ACTION_CONTACT_LATER = "CONTACT_LATER"
ACTION_ARCHIVE = "ARCHIVE"
ACTION_SKIP = "SKIP"

DEFAULT_ELIGIBLE_ACTIONS: frozenset[str] = frozenset({ACTION_CONTACT_FIRST, ACTION_CONTACT_LATER})

_ALL_ACTIONS = (
    ACTION_CONTACT_FIRST,
    ACTION_CONTACT_LATER,
    ACTION_ARCHIVE,
    ACTION_SKIP,
)

# Accept every spelling that appears in M1–M5 data or in the task spec.
_ACTION_ALIASES: dict[str, str] = {
    "CONTACT": ACTION_CONTACT_FIRST,
    "CONTACT_FIRST": ACTION_CONTACT_FIRST,
    "CONTACT FIRST": ACTION_CONTACT_FIRST,
    "CONTACT-NOW": ACTION_CONTACT_FIRST,
    "INVESTIGATE": ACTION_CONTACT_LATER,
    "INVESTIGATE_FURTHER": ACTION_CONTACT_LATER,
    "INVESTIGATE FURTHER": ACTION_CONTACT_LATER,
    "CONTACT_LATER": ACTION_CONTACT_LATER,
    "CONTACT LATER": ACTION_CONTACT_LATER,
    "ARCHIVE": ACTION_ARCHIVE,
    "SKIP": ACTION_SKIP,
}

_PRIORITY_TO_ACTION: dict[str, str] = {
    "CONTACT FIRST": ACTION_CONTACT_FIRST,
    "CONTACT_LATER": ACTION_CONTACT_LATER,
    "CONTACT LATER": ACTION_CONTACT_LATER,
    "SKIP": ACTION_SKIP,
}


def normalize_action(value: str) -> str:
    """Canonicalise any action spelling; unknown values → ARCHIVE (never sent)."""
    text = (value or "").strip().upper().replace("-", "_")
    if text in _ACTION_ALIASES:
        return _ACTION_ALIASES[text]
    # tolerate double spaces / mixed separators
    compact = " ".join(text.replace("_", " ").split())
    return _ACTION_ALIASES.get(compact, ACTION_ARCHIVE)


def resolve_action(lead: M5Lead) -> str:
    """Canonical action for a lead, using M5's outreach_priority when present.

    M5's ``outreach_priority`` already merges M3's action with potential level
    (e.g. CONTACT + LOW potential → CONTACT LATER), so it wins. ``final_action``
    is used to tell ARCHIVE from SKIP.
    """
    priority = (lead.outreach_priority or "").strip().upper()
    if priority in _PRIORITY_TO_ACTION:
        mapped = _PRIORITY_TO_ACTION[priority]
        if mapped == ACTION_SKIP:
            # keep the archive/skip distinction from M3
            final = normalize_action(lead.final_action)
            return final if final in (ACTION_ARCHIVE, ACTION_SKIP) else ACTION_SKIP
        return mapped
    return normalize_action(lead.final_action)


def resolve_priority_label(lead: M5Lead) -> str:
    """Human-readable M5 decision label for logs/dry-run output."""
    priority = (lead.outreach_priority or "").strip()
    if priority:
        return priority
    action = normalize_action(lead.final_action)
    return {
        ACTION_CONTACT_FIRST: "CONTACT FIRST",
        ACTION_CONTACT_LATER: "CONTACT LATER",
        ACTION_ARCHIVE: "SKIP",
        ACTION_SKIP: "SKIP",
    }[action]


def check_eligibility(lead: M5Lead, include_actions: frozenset[str] | set[str] | None = None) -> tuple[bool, str]:
    """Return ``(eligible, reason)``.

    Default allowed: ``CONTACT_FIRST`` and ``CONTACT_LATER``.
    ``ARCHIVE`` / ``SKIP`` / unknown are NOT eligible.
    If ``include_actions`` is provided, it explicitly defines allowed actions.
    """
    action = resolve_action(lead)
    if include_actions:
        allowed = set()
        for raw in include_actions:
            mapped = _lookup_action(str(raw))
            if mapped:
                allowed.add(mapped)
    else:
        allowed = set(DEFAULT_ELIGIBLE_ACTIONS)

    if action in allowed:
        return True, f"m5_decision={resolve_priority_label(lead)}"

    return False, f"action_not_eligible:{action}"


def _lookup_action(value: str) -> str:
    """Alias lookup that returns '' for unknown input."""
    key = " ".join(str(value).strip().upper().replace("-", "_").replace("_", " ").split())
    return _ACTION_ALIASES.get(key, "")



__all__ = [
    "ACTION_CONTACT_FIRST",
    "ACTION_CONTACT_LATER",
    "ACTION_ARCHIVE",
    "ACTION_SKIP",
    "normalize_action",
    "resolve_action",
    "resolve_priority_label",
    "check_eligibility",
]
