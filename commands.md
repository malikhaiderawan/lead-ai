# 🚀 MalikAxiom Lead AI — Complete Command Reference

This document contains all operational commands for the **MalikAxiom Lead AI** engine (Research, Qualification, Outreach Generation, WhatsApp Automation, and Excel Reporting).

---

## 📁 1. Pehle Workspace Directory Mein Aayein
Har command run karne se pehle `malik-lead-ai` folder mein enter hon:
```bash
cd "malik-lead-ai"
```

---

## ⚡ 2. Full Automated Pipeline (End-to-End Run)
Nayi CSV file se complete analysis, scoring, messages, aur Excel sheets aik hi command mein generate karne ke liye:

```bash
# Nayi CSV leads file process karein:
python3 main.py pipeline input/wi.csv

# Custom file name ke sath:
python3 main.py pipeline input/<your_file_name>.csv
```

---

## 📲 3. WhatsApp Outreach Execution (M6)

### 🔍 Preview / Testing (Dry Run — Kuch send nahi hota, links aur messages verify karein):
```bash
python3 main.py outreach-execute --dry-run
```

### 🚀 Real Outreach Send (WhatsApp Web open hoga aur messages send honge):
```bash
python3 main.py outreach-execute
```

### 🎯 Single Lead ID Send (Kisi specific lead ko bhejne ke liye):
```bash
python3 main.py outreach-execute --lead-id lead_045_beymen___bespoke_tailoring_islamabad
```

### 🔄 Failed Leads Ko Dobara Try Karna:
```bash
python3 main.py outreach-execute --retry-failed
```

### 💥 Force Resend (Already contacted lead ko dubara bhejne ke liye):
```bash
python3 main.py outreach-execute --lead-id <lead_id> --force-resend
```

### 🚫 Pricing Ke Baghair Message Bhejna (PKR 10,000 mention off karne ke liye):
```bash
python3 main.py outreach-execute --dry-run --no-pricing
```

---

## 🛠️ 4. Step-by-Step Execution (Manual Pipeline)

Agar pipeline ko step-by-step chalana ho:

### Step 1: Research (M2) — Websites & Social Links Check
```bash
python3 main.py research input/wi.csv
```

### Step 2: Qualification (M3) — Lead Scoring & Filtering
```bash
python3 main.py qualify
```

### Step 3: Outreach Messages Generate Karna (M4)
```bash
python3 main.py outreach
```

### Step 4: Sales Report & CSVs Generate Karna (M5)
```bash
python3 main.py sales-report
```

---

## 📊 5. Excel & Master Data Export

```bash
# Master Multi-Sheet Excel Workbook update karne ke liye:
python3 main.py export-excel
```

---

## 🖥️ 6. M7 Sales Dashboard & Command Center

```bash
# Dashboard start karne ke liye (Default: http://127.0.0.1:8080):
python3 main.py dashboard

# Custom Port ya Browser Auto-Open ke sath:
python3 main.py dashboard --port 8080 --open-browser
```

---

## 🔍 7. System Status & Verification

```bash
# System status aur knowledge structure check:
python3 main.py status

# Saare 116 Automated Unit Tests run karne ke liye:
python3 -m unittest discover -s tests


---

## 📂 7. Output Files Directory Guide

All generated files are saved inside the `output/` directory:

| File Name | Description |
| :--- | :--- |
| **`output/contact_first.csv`** | 🎯 Top Priority High-Conversion leads (Sab se pehle inko contact karein) |
| **`output/contact_later.csv`** | ⏳ Secondary / Follow-up leads |
| **`output/mega_cold_calling_leads.xlsx`** | 📞 Weekend Cold Calling Sheet with Call Notes, Call Status, & Pitch Hooks |
| **`output/malikaxiom_lead_ai.xlsx`** | 📈 Complete Multi-Sheet Master Excel Workbook |
| **`output/m6_outreach_results.csv`** | 📱 WhatsApp Outreach Send History & Status Tracker |
| **`output/m6_send_state.json`** | 🛡️ Duplicate-send protection database |
| **`output/malikaxiom_sales_summary.md`** | 📝 Complete analytics report & conversion metrics |

---

## 📩 8. Active WhatsApp Outreach Message Template

```text
Assalam o Alaikum 👋

I came across [Business Name] and had a look at your online presence.

We help businesses grow through tailored digital strategies — including modern websites, e-commerce solutions, video reel content creation, and targeted ads campaigns. Website solutions start from PKR 10,000.

I'd be happy to share a few growth ideas tailored for [Business Name].

Would you be open to a quick chat?

— Haider Nawaz
MalikAxiom Technology
🌐 malikaxiomtech.com
✉️ hello@malikaxiomtech.com
```

---

## ⚡ 9. Complete Daily Quick Reference Cheat Sheet

Ye daily use ke liye summary sheet hai:

### 📁 Step 0: Terminal Navigation
```bash
cd "malik-lead-ai"
```

### 🚀 Step 1: Run Full Pipeline (End-to-End)
```bash
# Nayi CSV leads file ko process karein (e.g. batch_08.csv):
python3 main.py pipeline input/batch_08.csv --timeout 8
```

### 🖥️ Step 2: Sales Command Center Dashboard Launch
```bash
# Dashboard chala kar browser me dekhein (Default: http://127.0.0.1:8080):
python3 main.py dashboard
```

### 📲 Step 3: WhatsApp Outreach Send Karna (M6)
```bash
# Test/Preview (Dry Run - messages aur links check karein):
python3 main.py outreach-execute --dry-run

# Actual Send (WhatsApp Web ke zariye send karein):
python3 main.py outreach-execute

# Specific Lead ID ko send karein:
python3 main.py outreach-execute --lead-id lead_002_ramsha_boutique___garments

# Failed leads ko dobara retry karein:
python3 main.py outreach-execute --retry-failed
```

### 📊 Step 4: Master Excel Workbook Refresh Karna
```bash
python3 main.py export-excel
```

### 🛠️ Step 5: Manual Step-by-Step Execution
```bash
# 1. Research (M2):
python3 main.py research input/batch_08.csv --timeout 8

# 2. Qualify & Score Leads (M3):
python3 main.py qualify

# 3. Outreach Messages Generate Karna (M4):
python3 main.py outreach

# 4. Sales Report, Contact First / Later CSVs (M5):
python3 main.py sales-report
```

### 🧪 Step 6: System & Unit Testing
```bash
# Core M2 & M3 tests verify karne ke liye:
python3 -m unittest tests.test_m2_deep_research tests.test_m3_qualification

# Saare automated unit tests run karne ke liye:
python3 -m unittest discover -s tests
```

