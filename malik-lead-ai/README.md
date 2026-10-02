# MalikAxiom Lead AI

An AI-powered lead qualification, personalized outreach generator, and sales-ready report pipeline for **MalikAxiom Technology** — a software development and business digitalization company serving SMEs, startups, and small businesses in Pakistan and internationally.

---

## What It Does

The system takes raw lead data (from Google Maps or any CSV source), researches each business's digital presence, qualifies the lead against MalikAxiom's service offerings, generates a personalized outreach message, and compiles a prioritized master sales report ready for manual review and outreach.

```
Raw leads (CSV)
    ↓  python3 main.py research input/leads.csv
Research results (JSON/CSV)
    ↓  python3 main.py qualify
Qualification results (JSON/CSV/MD)
    ↓  python3 main.py outreach
Outreach messages (JSON/CSV/MD)
    ↓  python3 main.py sales-report
Master Sales Report (CSV/MD)
    ↓  python3 main.py outreach-execute --dry-run   # M6: inspect
    ↓  python3 main.py outreach-execute             # M6: send ONE message per approved lead
Outreach execution state + results (M6)
```

Or run everything in a single command:
```bash
python3 main.py pipeline input/leads.csv
```

> **M1–M5 generate messages for human review. M6 (Milestone 6) is an additional
> execution layer: it sends ONE initial WhatsApp message per M5-approved
> (`CONTACT FIRST`) lead, tracks what was sent, and hands the conversation back
> to a human. It never re-qualifies a lead and never invents an opportunity.**


---

## Project Structure

```
malik-lead-ai/
├── main.py                     — CLI entry point (all subcommands)
├── knowledge/                  — Source of truth for all decisions
│   ├── company.md
│   ├── services.md
│   ├── business_digitalization.md
│   ├── ideal_clients.md
│   ├── qualification_rules.md
│   └── outreach_rules.md
├── input/
│   ├── leads.csv               — Your real lead data goes here
│   └── sample_leads.csv        — Sample data for testing
├── research/                   — Milestone 2: web research engine
│   ├── researcher.py
│   ├── website_researcher.py
│   ├── social_researcher.py
│   ├── google_researcher.py
│   ├── input_loader.py
│   └── evidence.py
├── qualification/              — Milestone 3: rules-based qualification engine
│   ├── qualifier.py
│   ├── knowledge_loader.py
│   └── output_writer.py
├── outreach/                   — Milestone 4: outreach message generator
│   ├── composer.py
│   └── output_writer.py
├── sales_report/               — Milestone 5: real lead pipeline + sales report
│   ├── merger.py               — joins M2+M3+M4 outputs by lead_id
│   ├── auditor.py              — audit flags, duplicate detection, quality checks
│   └── output_writer.py        — master CSV, contact_first.csv, summary MD
├── m6/                         — Milestone 6: outreach execution engine
│   ├── engine.py               — orchestrator (gate → build → validate → dedupe → send → log)
│   ├── eligibility.py          — M5 decision gate (CONTACT FIRST only by default)
│   ├── source_loader.py        — loads M5's master CSV / contact_first.csv
│   ├── phone.py                — safe Pakistani WhatsApp number normalisation
│   ├── social.py               — website/social URL classification (evidence reading)
│   ├── message_builder.py      — short evidence-based first-touch message
│   ├── validator.py            — NOT_READY checks before anything can be sent
│   ├── send_tracker.py         — persistent duplicate-send protection + history
│   ├── logging_setup.py        — append-only M6 log
│   ├── config.py               — fixed company/contact constants, limits, budgets
│   ├── channels/
│   │   ├── base.py             — channel contract: send(recipient, message)
│   │   ├── whatsapp.py         — default assist channel (wa.me click-to-chat)
│   │   ├── whatsapp_playwright.py — optional automated WhatsApp Web (not required)
│   │   └── dry_run.py          — dry-run channel (physically cannot send)
│   └── storage/state.py        — atomic JSON read/write
├── tests/                      — M6 test-suite (python3 -m unittest discover -s tests -t .)
└── output/                     — All generated results
    ├── research_results.json
    ├── research_results.csv
    ├── qualification_results.json
    ├── qualification_results.csv
    ├── qualified_leads_report.md
    ├── outreach_results.json
    ├── outreach_results.csv
    ├── outreach_results.md
    ├── malikaxiom_sales_leads.csv   ← Master CSV (all columns & quality flags)
    ├── contact_first.csv            ← Immediate working list (CONTACT FIRST only)
    ├── malikaxiom_sales_summary.md  ← Prioritized human-readable summary
    ├── m6_send_state.json           ← M6 duplicate-send protection state
    ├── m6_outreach_results.json     ← M6 attempt history (append-only)
    ├── m6_outreach_results.csv      ← M6 attempt history (spreadsheet view)
    └── m6_outreach.log              ← M6 run log (append-only)
```

---

## Milestones Summary

| # | Milestone | Status |
|---|---|---|
| 1 | Project structure, knowledge base | ✅ Done |
| 2 | Lead input + web research engine | ✅ Done |
| 3 | AI lead qualification + service matching | ✅ Done |
| 4 | Personalized outreach generator | ✅ Done |
| 5 | Real lead pipeline + sales-ready report | ✅ Done |
| 6 | Outreach execution engine (M6 — one validated WhatsApp message per approved lead) | ✅ Done |

---

## Quick Start (How to Run Real 50 Leads)

### Single Command Workflow (Recommended)

Place your CSV in `input/leads.csv` and run:

```bash
python3 main.py pipeline input/leads.csv
```

This automatically runs:
1. Web research
2. Qualification & service matching
3. Outreach message composition
4. Audit & master sales report generation

---

### Step-by-Step Workflow

```bash
# Step 1: Research leads from raw CSV
python3 main.py research input/leads.csv

# Step 2: Qualify researched leads
python3 main.py qualify

# Step 3: Generate personalized outreach messages
python3 main.py outreach

# Step 4: Generate master sales report & contact_first list
python3 main.py sales-report

# Step 5 (M6): Inspect what M6 would send — sends nothing, writes no state
python3 main.py outreach-execute --dry-run

# Step 6 (M6): Send ONE first-touch WhatsApp message per approved lead
python3 main.py outreach-execute --lead-id <lead_id_from_dry_run>
python3 main.py outreach-execute          # then small batches (capped, confirmed)
```

---

## All CLI Commands

```bash
# Show project status and structure
python3 main.py status

# Validate project structure (exits 1 on failure)
python3 main.py check

# List knowledge base files
python3 main.py list

# Show a knowledge file
python3 main.py show services

# Research leads from CSV
python3 main.py research input/leads.csv

# Qualify researched leads
python3 main.py qualify

# Generate outreach messages
python3 main.py outreach
python3 main.py outreach --mock        # pipeline test mode

# Generate sales master report
python3 main.py sales-report

# Run complete end-to-end pipeline
python3 main.py pipeline input/leads.csv

# M6: inspect outreach execution plan (no sends, no state written)
python3 main.py outreach-execute --dry-run

# M6: send the approved first-touch message (asks you to type SEND)
python3 main.py outreach-execute --lead-id lead_017_arbrandzone
python3 main.py outreach-execute --limit 5

# M6: state / recovery helpers
python3 main.py outreach-execute --show-state
python3 main.py outreach-execute --mark-sent --lead-id <lead_id>
python3 main.py outreach-execute --lead-id <lead_id> --retry-failed
python3 main.py outreach-execute --include-pricing --lead-id <lead_id>
```

---

## Output Files Reference

| File | Description | Use Case |
|---|---|---|
| `output/contact_first.csv` | 9 core columns (`business_name`, `location`, `phone`, `website`, `sales_potential`, `primary_service`, `why_this_lead`, `outreach_channel`, `outreach_message`) | Immediate daily outreach working list |
| `output/malikaxiom_sales_leads.csv` | Master CSV with 32 columns including review flags, duplicate indicators, contact quality checks, and evidence | Complete audit and CRM import file |
| `output/malikaxiom_sales_summary.md` | Prioritized markdown report grouped into CONTACT FIRST, CONTACT LATER, SKIP, with pipeline stats, review flags, and duplicate alerts | Human review before outreach |
| `output/m6_send_state.json` | Persistent M6 send state keyed by lead_id and normalized recipient (status history, attempt counts) | Duplicate-send protection across runs |
| `output/m6_outreach_results.json` / `.csv` | Append-only history of every M6 attempt (validation, duplicate check, send status, message, link) | Audit of what was sent to whom |
| `output/m6_outreach.log` | Append-only M6 run log | Troubleshooting and run history |

---

## Data Quality & Audit Layer (Milestone 5)

Milestone 5 adds an automated audit layer to flag suspicious leads or potential issues without altering qualification decisions:

1. **Duplicate Detection**: Flags leads sharing normalized business names, phone numbers, website domains, or Instagram handles (`possible_duplicate = true`). Leads are never deleted automatically.
2. **Suspicious HIGH Flags**: Flags HIGH leads that already have a reachable website + e-commerce present + mature social presence (`review_flag = true`).
3. **Suspicious LOW/SKIP Flags**: Flags LOW/SKIP leads that have 30+ Google reviews, active retail/product category, and clear digital gaps (`review_flag = true`).
4. **Message Validation**: Flags messages missing business names, containing prohibited revenue guarantee terms, or carrying `[MOCK]` tags in a real run.
5. **Contact Consistency**: Flags channel recommendations that lack corresponding contact evidence (e.g. WhatsApp recommended without a phone number).

---

## Outreach Rules & Evidence Discipline

- **No Revenue Guarantees**: Never promises guaranteed sales, profit, revenue, or ROI.
- **Evidence Respect**: `UNKNOWN` evidence is never converted to fact (e.g. "I couldn't verify an online store" instead of "You have no website").
- **Terminology**: Uses "challenges" instead of "problems" per `outreach_rules.md`.
- **Channel Specificity**: Tailors length and tone to WhatsApp (50-100w), Instagram DM (35-70w), Facebook, Email (with subject line), or Contact Form.
- **No False Claims**: Never claims store visits or fake urgency.

---

## Outreach Execution Engine (Milestone 6)

M6 consumes M5's decisions verbatim (`final_action`, `outreach_priority`,
`primary_service`, `detected_opportunity`, `outreach_channel`,
`outreach_message`) and executes exactly **one** evidence-based WhatsApp
first-touch per approved lead:

1. **Eligibility gate**: only `CONTACT FIRST` leads by default; other M5
   actions require an explicit `--include-action` flag. M6 never re-qualifies.
2. **Message build**: short (45–80 words) observation from M5's opportunity
   evidence + fixed MalikAxiom contact block. Optional `--include-pricing`
   ("starting from around PKR 10,000") only for local Business
   Digitalization leads.
3. **Validation** (`NOT_READY` blocks the send): placeholders / `None` /
   `N/A` in the message, missing or non-Pakistani mobile number, wrong
   contact details, banned claims (guaranteed sales, ROI, urgency), or an
   unapproved service in the opportunity line.
4. **Duplicate protection**: `output/m6_send_state.json` records every lead's
   status by lead_id *and* normalized recipient (+92…). `SENT` /
   `AWAITING_MANUAL_SEND` leads are always skipped; `FAILED` leads are only
   retried with `--retry-failed`, capped by `MAX_ATTEMPTS_PER_LEAD`. State is
   re-checked immediately before each send within a run.
5. **No-WhatsApp numbers are a recorded fact, not a retry**: a lead whose
   number cannot receive WhatsApp (Pakistani landline, no phone number at all,
   WhatsApp itself rejecting the number, or a human confirmation) is stored as
   `NO_WHATSAPP_NUMBER`. That status is **blocking** — every later run skips it
   with `SKIPPED_NO_WHATSAPP`, even with `--retry-failed`. Only an explicit
   `--force-resend` **plus** an explicit `--lead-id` can override it.
   - `python3 main.py outreach-execute --reclassify-no-whatsapp` — moves leads
     whose *already recorded* reason proves there is no WhatsApp (e.g.
     `pakistani_landline_not_whatsapp`) to `NO_WHATSAPP_NUMBER`. Nothing is
     guessed; malformed / foreign numbers stay `NOT_READY`.
   - `python3 main.py outreach-execute --mark-no-whatsapp --lead-id X [--lead-id Y]`
     — records a human-confirmed dead end (e.g. a number that repeatedly fails
     to load a WhatsApp chat).
6. **Human confirmation**: real sends require typing `SEND` (or `--yes` in
   scripts); per-run cap (`MAX_SENDS_PER_RUN`, hard cap 25) and
   `MIN_SECONDS_BETWEEN_SENDS` pacing apply.
7. **Channel**: default `assist` opens one pre-filled `wa.me` chat and you
   press Send (`--no-browser` only generates the link). Optional
   `--channel playwright` automates WhatsApp Web if you install Playwright —
   no stealth/anti-detection, no bulk blasting.

**Statuses**: `SENT`, `FAILED`, `NO_WHATSAPP_NUMBER`, `SKIPPED_NO_WHATSAPP`,
`SKIPPED_ALREADY_SENT`, `NOT_READY`, `NOT_ELIGIBLE`, `SKIPPED_LIMIT`,
`AWAITING_MANUAL_SEND`, `NOT SENT — DRY RUN`.

**No-WhatsApp statuses in one line**: `NO_WHATSAPP_NUMBER` = the number has no
WhatsApp account (never attempted again); `SKIPPED_NO_WHATSAPP` = this run saw
that recorded fact and skipped the lead. Both are reported in `--show-state`,
in `m6_outreach_results.csv`, and in the Excel workbook (`M6_Outreach` sheet
plus the `M6 NO WHATSAPP NUMBER` KPI in `Summary`).

**Always start with** `--dry-run`, then a single `--lead-id`, then a small
batch. Dry runs never send and never write state.

---

## What Is NOT Built

- Google Maps scraping or lead extraction (leads supplied externally)
- CRM or dashboard frontend
- Paid messaging APIs (WhatsApp Business API, Email API) and
  Instagram/Facebook automation
- Auto follow-ups, auto replies, bulk blasting
- Revenue or ROI tracking

M6 sends only ONE initial WhatsApp first-touch per approved lead with
duplicate-send protection; a human takes over the conversation.

---

*MalikAxiom Lead AI — built for MalikAxiom Technology*  
*https://malikaxiomtech.com/*
