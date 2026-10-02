"""M6 — Outreach Execution Engine (Milestone 6).

M6 is an *execution* layer, not a qualification engine. It:

    1. reads M5's final actionable output (``output/malikaxiom_sales_leads.csv``),
    2. keeps only leads whose M5 decision allows contact (``CONTACT FIRST``),
    3. validates contact + message data produced by M3/M4/M5,
    4. builds ONE short, evidence-based first-touch WhatsApp message,
    5. sends it through a replaceable channel abstraction,
    6. records the result permanently so a lead is never messaged twice.

Hard rules enforced in code:

* M6 never re-scores a lead and never invents an opportunity or service.
  The service/opportunity always comes from M5 (which comes from M3/M4).
* One lead = one initial message. No follow-ups, no multi-channel blasts.
* ``CONTACT LATER`` / ``INVESTIGATE`` / ``ARCHIVE`` / ``SKIP`` leads are
  never contacted unless the user explicitly opts in for that category.
* Dry-run touches nothing: no browser action, no state write.

Standard library only for the core engine.
"""

from __future__ import annotations

from .config import M6_VERSION

__all__ = ["M6_VERSION"]
