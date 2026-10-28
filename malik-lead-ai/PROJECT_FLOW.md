# 🚀 MalikAxiom Lead AI — Complete System Architecture & Project Flow

> **Document Type:** Master System Specification & Technical Handover  
> **Target Audience:** AI Engineering Assistants, Lead AI Developers, System Architects  
> **Project:** MalikAxiom Lead AI (Automated Lead Intelligence, Qualification, Outreach & Sales Command Center)  
> **Company:** MalikAxiom Technology (Software Development, Business Digitalization & Growth Agency)  
> **Current Version:** Milestone 7 (M1 through M7 fully operational with 116+ automated tests)

---

## 1. Executive Summary & Core Identity

### 1.1 What is MalikAxiom Lead AI?
**MalikAxiom Lead AI** is an autonomous, filesystem-driven lead intelligence pipeline and sales operating system designed specifically for **MalikAxiom Technology**. It ingests raw business leads (from Google Maps, local directories, CSVs, or Google SERP Instagram harvesting), performs automated deep digital research, applies deterministic business qualification rules, composes hyper-personalized multi-channel sales hooks, maintains cumulative cold-calling archives, executes guarded WhatsApp outreach, and serves an interactive real-time Sales Command Center (Dashboard).

### 1.2 Target Market & Offering Matrix
* **Primary Target:** Pakistani & international SMEs, boutique fashion brands (pret wear, bridal), specialty clinics/doctors, salons, luxury jewelry designers, restaurants/cafes, and real estate agencies.
* **Core Value Propositions:**
  1. **Modern Websites & E-Commerce:** Starting anchor from **PKR 10,000** for basic storefronts, scaling to full Shopify/WooCommerce/custom web apps.
  2. **Short-Form Content & Reels:** Video reel production, Instagram aesthetic curation, and TikTok/Meta ad funnels.
  3. **Custom Software & Automation:** CRM, inventory systems, automated booking/ordering solutions, and WhatsApp AI bots.

### 1.3 Core Engineering Principles
1. **Zero-Database Architecture:** No PostgreSQL, MongoDB, or Redis required. All state, lead history, send records, and CRM notes are managed via atomic, filesystem-driven storage (`.json`, `.csv`, `.xlsx`, `.md`).
2. **Standard Library Priority:** Built almost entirely on Python's standard library (`urllib`, `http.server`, `threading`, `json`, `csv`, `re`), with optional vendorized helpers (`openpyxl`, `playwright`).
3. **Safety & Human-in-the-Loop:** Automated generation, but strictly guarded execution. Never spams; enforces dry-runs, confirmation prompts, duplicate protection, and phone normalization.
4. **Idempotence & Cumulative Memory:** Running the pipeline multiple times never loses previous call notes, call statuses, or historical outreach records.

---

## 2. High-Level End-to-End Pipeline Map

```
   ┌─────────────────────────────────────────────────────────────┐
   │                    INPUT & HARVESTING                       │
   │  Raw CSVs (Google Maps/Scrapers) OR Instagram SERP Engine  │
   │           python3 main.py harvest / input/leads.csv         │
   └──────────────────────────────┬──────────────────────────────┘
                                  │
                                  ▼
   ┌─────────────────────────────────────────────────────────────┐
   │             MILESTONE 2: WEB RESEARCH ENGINE                │
   │  - Multi-threaded DNS/HTTP/SSL probe                        │
   │  - Social profile discovery (IG, FB, LinkedIn, TikTok)      │
   │  - Digital maturity scoring & structured evidence           │
   │          Output: research_results.json / .csv               │
   └──────────────────────────────┬──────────────────────────────┘
                                  │
                                  ▼
   ┌─────────────────────────────────────────────────────────────┐
   │          MILESTONE 3: QUALIFICATION & SCORING               │
   │  - Need Score (0-30) + Fit Score (0-30)                     │
   │  - Budget Score (0-20) + Reachability Score (0-20)          │
   │  - Action Gates: CONTACT FIRST / CONTACT LATER / SKIP       │
   │  - Primary & Secondary Service Matching + Pitch Hooks       │
   │        Output: qualification_results.json / .csv / .md      │
   └──────────────────────────────┬──────────────────────────────┘
                                  │
                                  ▼
   ┌─────────────────────────────────────────────────────────────┐
   │          MILESTONE 4: OUTREACH MESSAGE GENERATION           │
   │  - Tailored WhatsApp message (with PKR 10k anchor)          │
   │  - Instagram DM & Cold Email copy generation                │
   │  - Specific evidence integration (no generic flattery)      │
   │           Output: outreach_results.json / .csv / .md        │
   └──────────────────────────────┬──────────────────────────────┘
                                  │
                                  ▼
   ┌─────────────────────────────────────────────────────────────┐
   │          MILESTONE 5: SALES REPORT & MEGA ARCHIVING         │
   │  - Data auditing (phone formats, missing field flags)       │
   │  - 32-column Master CSV + contact_first.csv / contact_later │
   │  - Mega Archive deduplication (preserves call notes/status) │
   │  - Output: mega_cold_calling_leads.xlsx & batches/          │
   │  - Excel Exporter: 9-tab malikaxiom_lead_ai.xlsx            │
   └──────────────────────────────┬──────────────────────────────┘
                                  │
                 ┌────────────────┴────────────────┐
                 ▼                                 ▼
   ┌───────────────────────────┐     ┌───────────────────────────┐
   │    MILESTONE 6: M6        │     │    MILESTONE 7: M7        │
   │  OUTREACH EXECUTION       │     │ SALES COMMAND CENTER      │
   │  - Guarded WhatsApp send  │     │  - Zero-DB Web Dashboard  │
   │  - wa.me Click-to-Chat /  │     │  - Real-time CRM Calling  │
   │    Playwright Automation  │     │  - Live Audio Notes & Log │
   │  - State & Dedupe Lock    │     │  - Dynamic Client Demos   │
   │  (m6_send_state.json)     │     │  (localhost:8080)         │
   └───────────────────────────┘     └───────────────────────────┘
```

---

## 3. Deep-Dive Milestone Breakdown

### 🎯 Milestone 1: Knowledge Base & Domain Truth (`knowledge/`)
The knowledge folder acts as the single source of truth for all downstream engines. No heuristics are hardcoded without referencing these rules.
* `company.md`: MalikAxiom's identity, positioning, team, and pricing tiers.
* `services.md`: Technical and marketing services breakdown (Web, E-commerce, Video Reels, Meta Ads, Custom Automation).
* `business_digitalization.md`: Framework for assessing digital maturity (No website -> Basic landing -> Functional store -> Automated powerhouse).
* `ideal_clients.md`: Ideal Customer Profile (ICP) definitions (Local retail, doctors, bespoke tailors, pret wear brands).
* `qualification_rules.md`: Explicit scoring algorithms, penalty criteria, and disqualification thresholds.
* `outreach_rules.md`: Messaging tone guidelines (friendly, professional, non-pushy, localized Urdu/English, clear call to action).

---

### 🌐 Milestone 2: Web Research Engine (`research/`)
* **Entry Point:** `research/researcher.py` (`run_research()`)
* **Sub-Modules:**
  * `input_loader.py`: Ingests messy raw CSVs, auto-detects column variants (`Company`, `Biz Name`, `Phone Number`, `Maps URL`), generates unique `lead_id` hash, cleans and standardizes schema.
  * `website_researcher.py`: Performs HTTP/HTTPS HEAD and GET requests. Checks for SSL validity, redirects, responsiveness, page load speed, and detects CMS signatures (Shopify, WordPress, Wix).
  * `social_researcher.py`: Detects and validates social presence across Instagram, Facebook, LinkedIn, TikTok, and YouTube.
  * `google_researcher.py`: Evaluates Google Maps presence, review count, rating stars, and missing data points.
  * `evidence.py`: Aggregates raw observations into structured evidence objects (`website_active`, `is_social_only`, `has_whatsapp`, `digital_gap_summary`).
* **Outputs Generated:**
  * `output/research_results.json`
  * `output/research_results.csv`

---

### ⚖️ Milestone 3: AI Qualification Engine (`qualification/`)
* **Entry Point:** `qualification/qualifier.py` (`run_qualification()`)
* **Logic & Scoring Architecture:**
  Each lead is evaluated across 4 scoring pillars (Total = 100 points):
  1. **Digital Need Score (0–30):** High points if the business has active social followings/sales but **no website**, broken mobile design, or no e-commerce checkout.
  2. **Business Fit Score (0–30):** High points for industries with high ROI on digitalization (Fashion, Pret wear, Healthcare, Luxury services).
  3. **Commercial Viability / Budget Score (0–20):** Evaluated based on Google review volume, physical location, brand maturity, and active marketing.
  4. **Reachability Score (0–20):** Direct WhatsApp number available (+20), mobile cell phone (+15), landline only (+5), no phone (0).
* **Decision Tiers:**
  * **`CONTACT FIRST` (Score ≥ 70):** Prime opportunities with verified contact numbers and clear digital gaps.
  * **`CONTACT LATER` (Score 45–69):** Moderate fit, secondary priority, or missing direct mobile phone.
  * **`SKIP / DISQUALIFIED` (Score < 45):** Closed businesses, corporate giants with existing in-house IT, or invalid contact leads.
* **Outputs Generated:**
  * `output/qualification_results.json`
  * `output/qualification_results.csv`
  * `output/qualified_leads_report.md`

---

### ✍️ Milestone 4: Personalized Outreach Generator (`outreach/`)
* **Entry Point:** `outreach/composer.py` (`run_outreach()`)
* **Composition Engine:**
  * Synthesizes M2 evidence and M3 qualification decisions into authentic, personalized outreach.
  * Avoids generic flattery ("I love your page!"). Instead, cites real observations (e.g., *"Noticed you take orders via Instagram DM without an automated catalog..."*).
  * Formulates tailored hooks across 3 channels:
    1. **WhatsApp (Primary):** Clean, concise, polite greeting in localized Urdu-English blend, anchoring the PKR 10,000 package or customized growth pitch.
    2. **Instagram DM:** Short conversational hook focused on visual aesthetic and bio link optimization.
    3. **Cold Email:** Professional proposal structure with clear portfolio references.
* **Outputs Generated:**
  * `output/outreach_results.json`
  * `output/outreach_results.csv`
  * `output/outreach_results.md`

---

### 📊 Milestone 5: Sales Pipeline, Auditor & Mega Archive (`sales_report/`)
* **Entry Point:** `sales_report/output_writer.py` (`run_sales_report()`)
* **Sub-Modules:**
  * `merger.py`: Performs an inner/left join across M2, M3, and M4 by `lead_id` to create a consolidated 32-column master data frame.
  * `auditor.py`: Runs quality audits: flags duplicate phone numbers, warns on landlines vs mobile numbers, flags missing decision fields.
  * `mega_archive.py`: **Crucial Cumulative Persistence Engine**.
    * Maintains `output/mega_contact_first.csv` and `output/mega_contact_later.csv`.
    * **Preserves Human Notes:** When re-running new batches, existing user edits in `call_status` (e.g. `INTERESTED`, `CALL_BACK`, `CLOSED`) and `call_notes` are retained based on phone/name deduplication.
    * Generates `output/mega_cold_calling_leads.xlsx` specifically designed for cold calling reps with formatted pitch hooks and note columns.
    * Saves immutable historical batch snapshots into `output/batches/batch_YYYYMMDD_HHMMSS/`.
* **Outputs Generated:**
  * `output/malikaxiom_sales_leads.csv` (Master 32-column audit file)
  * `output/contact_first.csv` (Immediate daily priority list)
  * `output/contact_later.csv` (Follow-up queue)
  * `output/manual_instagram_leads.csv` (Leads requiring Instagram DM outreach)
  * `output/malikaxiom_sales_summary.md` (Executive analytical summary)
  * `output/mega_cold_calling_leads.xlsx`

---

### 📲 Milestone 6: Safe Outreach Execution Engine (`m6/`)
* **Entry Point:** `m6/engine.py` (Invoked via `python3 main.py outreach-execute`)
* **Philosophy:** Execution with safety rails. Never spams, never mass-blasts, never re-qualifies.
* **Architecture:**
  * `eligibility.py`: Strict gatekeeper. Only leads with `CONTACT FIRST` status and valid mobile phones are eligible.
  * `phone.py`: Robust Pakistani phone sanitization (normalizes `0300...`, `92300...`, `+92-300...` into strict E.164 `+923001234567`).
  * `validator.py`: Pre-send sanity check (rejects placeholder text, verifies message length).
  * `send_tracker.py`: Persistent atomic state (`output/m6_send_state.json`). Prevents duplicate sends even across different sessions.
  * `channels/whatsapp.py`: Generates official encoded `https://wa.me/<phone>?text=<encoded_msg>` URLs for 1-click human execution.
  * `channels/whatsapp_playwright.py`: Optional headless/headful automated WhatsApp Web sender with human typing delays.
  * `channels/dry_run.py`: Zero-risk simulation channel for inspection and auditing.
* **Safety Controls:**
  * `dry-run` default mode
  * Explicit confirmation prompt requiring the user to type `SEND` before actual execution
  * Batch size capping (`--limit 5`)
  * Append-only audit logging in `output/m6_outreach.log`

---

### 💻 Milestone 7: Sales Command Center & Live Dashboard (`dashboard/`)
* **Entry Point:** `dashboard.py` or `python3 main.py dashboard` (Default port: `8080`)
* **Architecture:**
  * Built using Python's native `http.server.ThreadingHTTPServer` — requires **no external web framework** (no Flask/Django/FastAPI).
  * Modern, responsive glassmorphism web interface located in `dashboard/static/` (`index.html`, `app.js`).
* **Key Features:**
  1. **Live Lead CRM:** Instant search, sorting, filtering by category, city, score, and contact priority.
  2. **1-Click WhatsApp Launcher:** Direct wa.me launch with pre-filled personalized message.
  3. **Call Status & Notes Manager:** Updates `call_status` (`NEW`, `CONNECTED`, `PITCHED`, `CONVERTED`, `NOT_INTERESTED`) and writes notes directly back to the filesystem CSVs.
  4. **Voice Audio Notes:** Record and store micro-voice memos for cold calls.
  5. **Dynamic Demo Generator (`demo_generator.py`):** Automatically spins up personalized live client mockup URLs (`demo2/`) to show boutique clients during sales calls.
  6. **Real-time Pipeline Analytics (`analytics.py`):** Calculates conversion funnel, average score, service distribution, and call outcomes.

---

### 🌾 Auxiliary Engine: Instagram Bio Harvester (`tools/instagram_harvester.py`)
* **Purpose:** Harvests high-intent local D2C brands (Pret wear, bakeries, salons, jewelers) that operate entirely on Instagram without traditional websites.
* **Mechanism:**
  * Uses Google SERP queries with targeted footprint operators (e.g., `site:instagram.com "pret wear" "Lahore" "03"`).
  * Bypasses Instagram login blocks and anti-scraping walls by parsing public search result metadata.
  * Extracts business names, bio text, phone numbers, and handles.
  * Ingests directly into `input/harvested_leads.csv` with a single command or pipes straight into the full AI pipeline (`--auto-pipeline`).

---

### 📑 Auxiliary Exporter: Master Excel Workbook (`exporter/excel_exporter.py`)
* **Output:** `output/malikaxiom_lead_ai.xlsx`
* **Features:** Produces a 9-tab, beautifully styled executive workbook using custom color palettes, freeze panes, auto-fit columns, and formula summaries:
  1. `Summary`: Executive overview and pipeline KPI metrics.
  2. `Pipeline`: Consolidated master leads table.
  3. `M1_Raw_Leads`: Original input data.
  4. `M2_Research`: Digital footprint & research evidence.
  5. `M3_Qualification`: Scoring rationale & service matching.
  6. `M4_Outreach`: Message hooks and drafts.
  7. `M5_Decisions`: Final audit flags and priority lists.
  8. `M6_Outreach`: WhatsApp delivery history and status.
  9. `Files_Index`: File manifest and integrity timestamps.

---

## 4. Directory & File Inventory

```
malik-lead-ai/
├── main.py                          # Unified CLI entry point for all operations
├── dashboard.py                     # Standalone launcher for M7 Sales Command Center
├── commands.md                      # Operational cheatsheet for human operators
├── HARVEST_GUIDE.md                 # Documentation for Instagram SERP harvesting
│
├── knowledge/                       # Source of Truth rules & configuration
│   ├── company.md                   # MalikAxiom services, pricing & identity
│   ├── services.md                  # Service catalog details
│   ├── business_digitalization.md   # Digital maturity stages
│   ├── ideal_clients.md             # ICP definitions
│   ├── qualification_rules.md       # Scoring equations & criteria
│   └── outreach_rules.md            # Tone, copy & messaging guidelines
│
├── input/                           # Raw lead input directory
│   ├── leads.csv                    # Primary working input file
│   ├── sample_leads.csv             # Reference testing file
│   └── harvested_leads.csv          # Output from Instagram harvester
│
├── research/                        # Milestone 2: Web Research Engine
│   ├── researcher.py                # Pipeline research orchestrator
│   ├── input_loader.py              # CSV ingestion & schema normalization
│   ├── website_researcher.py        # HTTP, SSL, CMS & responsiveness probe
│   ├── social_researcher.py         # Social link detection & profile analysis
│   ├── google_researcher.py         # Google Maps & review scraper
│   └── evidence.py                  # Structured evidence builder
│
├── qualification/                   # Milestone 3: Lead Qualification Engine
│   ├── qualifier.py                 # Multi-pillar scoring & decision engine
│   ├── knowledge_loader.py          # Markdown rules parser
│   └── output_writer.py             # Formatter for qualification reports
│
├── outreach/                        # Milestone 4: Outreach Message Generator
│   ├── composer.py                  # Multi-channel copywriting engine
│   └── output_writer.py             # Formatter for outreach drafts
│
├── sales_report/                    # Milestone 5: Pipeline Merger, Auditor & Archive
│   ├── merger.py                    # Multi-stage data joiner
│   ├── auditor.py                   # Data quality & duplicate detector
│   ├── mega_archive.py              # Persistent multi-run history & calling sheet
│   └── output_writer.py             # Master CSV & summary report generator
│
├── m6/                              # Milestone 6: Guarded Outreach Execution
│   ├── engine.py                    # M6 operational orchestrator
│   ├── eligibility.py               # Gatekeeper for CONTACT FIRST leads
│   ├── source_loader.py             # M5 output data reader
│   ├── phone.py                     # E.164 phone sanitization for Pakistan
│   ├── message_builder.py           # First-touch message assembler
│   ├── validator.py                 # Pre-send integrity checker
│   ├── send_tracker.py              # Persistent duplicate-send protection state
│   ├── config.py                    # Operational limits & constants
│   ├── storage/state.py             # Atomic state file handler
│   └── channels/                    # Delivery channel adapters
│       ├── base.py                  # Channel interface
│       ├── whatsapp.py              # wa.me link preview builder
│       ├── whatsapp_playwright.py   # Automated browser dispatcher
│       └── dry_run.py               # No-op simulation channel
│
├── dashboard/                       # Milestone 7: M7 Sales Command Center
│   ├── server.py                    # Native Python HTTP server & REST API
│   ├── data_loader.py               # File-backed lead repository & query engine
│   ├── activity_manager.py          # Real-time event & action logger
│   ├── analytics.py                 # KPI & conversion rate calculator
│   ├── demo_generator.py            # Dynamic customized mockup generator
│   └── static/                      # Frontend UI assets
│       ├── index.html               # Single-page dashboard application
│       └── app.js                   # Client-side reactivity & API bindings
│
├── exporter/                        # Excel Multi-Sheet Reporting Engine
│   └── excel_exporter.py            # openpyxl workbook generator
│
├── tools/                           # Standalone Utility Scripts
│   ├── instagram_harvester.py       # Google SERP bio harvester
│   ├── generate_calling_sheet_pdf.py# Printable cold calling PDF generator
│   └── generate_playbook_pdf.py     # Sales playbook PDF generator
│
├── tests/                           # Complete Test Suite (116+ Unit & Integration Tests)
│   ├── test_m2_deep_research.py
│   ├── test_m3_qualification.py
│   ├── test_m6_engine.py
│   ├── test_m6_message.py
│   ├── test_m7_dashboard.py
│   └── test_excel_exporter.py
│
└── output/                          # Pipeline Artifacts (Created dynamically)
    ├── malikaxiom_sales_leads.csv   # Consolidated master lead repository
    ├── contact_first.csv            # Immediate outreach priority file
    ├── contact_later.csv            # Follow-up pipeline file
    ├── manual_instagram_leads.csv   # Instagram DM specific target file
    ├── mega_cold_calling_leads.xlsx # Calling workbook with notes & statuses
    ├── malikaxiom_lead_ai.xlsx      # 9-tab executive Excel workbook
    ├── m6_send_state.json           # Atomic outreach deduplication state
    ├── m6_outreach_results.csv      # Log of all outreach attempts
    ├── malikaxiom_sales_summary.md  # High-level analytical markdown report
    └── batches/                     # Timestamped batch historical snapshots
```

---

## 5. Standard CLI Command Reference

### 5.1 End-to-End Pipeline (Most Common)
```bash
# Run full analysis on a new CSV lead file:
python3 main.py pipeline input/leads.csv

# Run pipeline with a custom output directory:
python3 main.py pipeline input/my_leads.csv --output output/
```

### 5.2 Instagram SERP Harvester
```bash
# Harvest 30 Pret Wear businesses in Lahore:
python3 main.py harvest --city Lahore --category "pret wear" --limit 30

# Harvest 30 London Jewelry brands:
python3 main.py harvest --city London --country UK --category "jewelry brand" --limit 30

# Harvest and immediately trigger full analysis:
python3 main.py harvest --city Lahore --category "pret wear" --limit 30 --auto-pipeline
```

### 5.3 Step-by-Step Manual Execution
```bash
# Step 1: Deep Web & Social Research
python3 main.py research input/leads.csv

# Step 2: AI Qualification & Scoring
python3 main.py qualify

# Step 3: Personalized Outreach Generation
python3 main.py outreach

# Step 4: Master Sales Report & Mega Archiving
python3 main.py sales-report

# Step 5: Export Master Excel Workbook
python3 main.py export-excel
```

### 5.4 WhatsApp Outreach Execution (M6)
```bash
# Inspect eligible sends in Dry-Run mode (No actual messages sent):
python3 main.py outreach-execute --dry-run

# Execute real WhatsApp send (requires human confirmation prompt):
python3 main.py outreach-execute

# Send outreach to a specific lead ID only:
python3 main.py outreach-execute --lead-id lead_045_beymen___bespoke_tailoring_islamabad

# Retry previously failed sends:
python3 main.py outreach-execute --retry-failed
```

### 5.5 Sales Command Center (M7 Dashboard)
```bash
# Launch dashboard on http://127.0.0.1:8080:
python3 dashboard.py

# Launch on custom port and open browser automatically:
python3 dashboard.py --port 8080 --open-browser

# Alternatively via main.py:
python3 main.py dashboard
```

### 5.6 Testing & Health Verification
```bash
# Verify project structure and knowledge files:
python3 main.py check

# Run all 116+ automated unit & integration tests:
python3 -m unittest discover -s tests
```

---

## 6. Critical Technical Contracts & Data Schemas

### 6.1 Lead ID Generation Contract
Every lead receives a deterministic, collision-resistant identifier:
```python
clean_name = re.sub(r'[^a-z0-9]+', '_', business_name.lower()).strip('_')
lead_id = f"lead_{index:03d}_{clean_name[:40]}"
```

### 6.2 Phone Normalization Contract (Pakistan Market Focus)
* Raw: `0300 1234567` / `+92 (300) 123-4567` / `923001234567`
* Normalized: `+923001234567`
* Landlines (e.g. `042-35870000` / `051-...`) are flagged as `LANDLINE_NOT_WHATSAPP` and directed to Cold Calling rather than WhatsApp outreach.

### 6.3 State Storage & Atomic Writes
* `output/m6_send_state.json`:
  ```json
  {
    "lead_017_arbrandzone": {
      "status": "SENT",
      "recipient": "+923001234567",
      "sent_at": "2026-10-20T10:15:30Z",
      "channel": "whatsapp",
      "attempt_count": 1
    }
  }
  ```
  Writes are completed atomically via temporary file rename to prevent file corruption during sudden interruptions.

### 6.4 Human Feedback Loop in Mega Archive
`output/mega_cold_calling_leads.xlsx` and `output/mega_contact_first.csv` continuously maintain:
* `call_status`: `NEW` | `RINGING` | `CONNECTED` | `CALL_BACK` | `INTERESTED` | `MEETING_BOOKED` | `NOT_INTERESTED` | `WRONG_NUMBER`
* `call_notes`: Free-text field documenting objections, budget discussions, or appointment times.
* When a new batch of leads is merged, existing `call_status` and `call_notes` are preserved for any matching business name or phone number.

---

## 7. Summary for AI Assistants

When extending or maintaining this project:
1. **Do not introduce heavy databases (Postgres, Mongo, etc.)** without explicit user request. The system is intentionally architected to be 100% portable and filesystem-based.
2. **Never bypass safety checks in M6.** Outreach must remain audited, throttled, and duplicate-protected.
3. **Always run unit tests** (`python3 -m unittest discover -s tests`) after modifying any module in `research/`, `qualification/`, `outreach/`, `sales_report/`, `m6/`, or `dashboard/`.
4. **Follow the established style**: Python 3.10+ typing, `pathlib.Path`, clear docstrings, and atomic file handlers.
