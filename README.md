# MalikAxiom Lead AI

AI-powered B2B lead research and qualification system for **MalikAxiom Technology**.

## Project Purpose

MalikAxiom Lead AI will research businesses, assess their digital maturity, identify
factual digital gaps, match them against MalikAxiom's services, and recommend
personalized outreach - so the sales team can focus on leads with genuine opportunity.

The system is built on an evidence-based philosophy: it must distinguish between
**verified facts**, **reasonable opportunities**, and **unknown information**, and it must
never invent business challenges, revenue, technology stacks, customer volume, owner
identity, or business needs.

## Current Milestone

**Milestone 2 - Lead input + research engine.**

Completed in this milestone:

- [x] Input CSV loader with flexible column-name mapping
- [x] Website research module (HTTP checks, content signals, e-commerce detection)
- [x] Social research module (Instagram, Facebook, TikTok, LinkedIn reachability)
- [x] Google presence researcher (preserves Google Maps/Business data from input)
- [x] Research orchestrator with per-lead exception handling
- [x] JSON output (detailed structured research)
- [x] CSV output (spreadsheet-friendly)
- [x] Evidence classification (VERIFIED_FACT, REASONABLE_OBSERVATION, UNKNOWN)
- [x] Digital maturity classification (descriptive only, not a sales score)
- [x] Research summary generation
- [x] Per-lead error handling (one failure does not stop the batch)

Explicitly **not** built yet: AI API integration, sales potential scoring
(HIGH/MODERATE/LOW/SKIP), service recommendation, personalized outreach
generation, CRM, and dashboard. No third-party packages are installed.

## Folder Structure

```
MalikAxiom-Lead Ai/
├── README.md
└── malik-lead-ai/
    ├── knowledge/
    │   ├── company.md                 # Company overview, positioning, trust points, contacts
    │   ├── services.md                # Full service catalog (8 services)
    │   ├── business_digitalization.md # The 20,000 PKR package in detail
    │   ├── ideal_clients.md           # Target clients, digital maturity bands, profiles
    │   ├── qualification_rules.md     # Research philosophy, scoring, service matching
    │   └── outreach_rules.md          # Outreach pattern, rules, required outputs
    ├── input/
    │   ├── schema.md                  # Input CSV column documentation
    │   ├── sample_leads.csv           # 3 fictional test businesses
    │   └── leads.csv                  # Replace with real exported lead data
    ├── output/
    │   ├── .gitkeep
    │   ├── research_results.json      # Detailed structured research (generated)
    │   └── research_results.csv       # Spreadsheet-friendly output (generated)
    ├── research/
    │   ├── __init__.py
    │   ├── evidence.py                # Evidence class for structured findings
    │   ├── input_loader.py            # CSV loading with flexible column mapping
    │   ├── website_researcher.py      # HTTP-based website research
    │   ├── social_researcher.py       # Social URL validation
    │   ├── google_researcher.py       # Google Maps/Business data preservation
    │   └── researcher.py              # Orchestrates research, writes outputs
    └── main.py                        # Entry point
```

## Running

Requires Python 3.10+ - standard library only, no installation needed.

```bash
cd malik-lead-ai

# Show project status and validate structure
python3 main.py
python3 main.py status

# Validate structure only (exit code 1 on failure)
python3 main.py check

# List knowledge base files
python3 main.py list

# Print a knowledge file
python3 main.py show company
python3 main.py show qualification_rules

# Research leads from a CSV file
python3 main.py research input/leads.csv
python3 main.py research input/sample_leads.csv

# Research with custom output directory and timeout
python3 main.py research input/leads.csv -o /tmp/research_output --timeout 15
```

## Input CSV Format

See `input/schema.md` for full documentation.

The CSV must have one row per lead. Accepted column name variations:

| Concept | Accepted names |
|---------|---------------|
| Business name | business_name, business, name, company |
| Phone | phone, phone_number, contact, telephone |
| Website | website, site, url, website_url |
| Instagram | instagram, instagram_url, instagram_handle |
| Facebook | facebook, facebook_url |
| TikTok | tiktok, tiktok_url, tiktok_handle |
| LinkedIn | linkedin, linkedin_url |
| Address | address, location, city, town |
| Category | category, business_category, type |
| Rating | rating, google_rating, stars |
| Reviews | reviews, review_count, google_reviews |
| Google Maps URL | google_maps_url, maps_url, maps |

Missing columns are handled gracefully - they become "unknown" in the research.

## Output Format

### JSON (`output/research_results.json`)

Detailed structured research with:
- Full original source data preserved
- Website research (status, type, e-commerce signals, evidence)
- Social research (status, activity, evidence per platform)
- Google research (rating, reviews, website connection, evidence)
- Business understanding (type, presence model, target market)
- Digital maturity classification
- Evidence buckets (verified_facts, reasonable_observations, unknowns, gaps)
- Research summary and status

### CSV (`output/research_results.csv`)

Spreadsheet-friendly with 39 columns including:
- lead_id, business_name, category, location, phone
- website_status, website_type, ecommerce_status, checkout_status
- instagram_status, facebook_status, tiktok_status, linkedin_status
- google_rating, google_reviews, digital_maturity, business_type
- observed_digital_gaps, verified_facts, unknowns

- Use **"challenges"** - never "problems" - when describing customer needs.
python3 main.py outreach-execute

- Use **"challenges"** - never "problems" - when describing customer needs.
python3 main.py outreach-execute
