# 🌾 MalikAxiom Lead AI — Instagram Harvester Guide (v2.0)

Is document mein **Instagram Startup & D2C Bio Harvester** ki mukammal tafseel, setup, command examples, aur pipeline integration ka tariqa darj hai.

---

## 📌 Harvester Kya Hai?
Bohat saari D2C brands, boutiques, designers, bakeries, aur startups ki website nahi hoti — wo **100% Instagram** par business karte hain (DM to order, WhatsApp orders).

Hamara Harvester:
1. **Google Search API (Serper.dev)** aur **Brave Search API** ke zariye public indexed Instagram bios aur posts ko search karta hai.
2. Bio aur caption se **Phone Numbers / WhatsApp**, **Brand Name**, **Instagram Handle**, aur **City/Country** auto-extract karta hai.
3. Data ko **Standard 22-Column CSV Schema** (`input/schema.md`) mein save karta hai.
4. Bina kisi manual data entry ke direct **M2 ➔ M3 ➔ M4 ➔ M6** pipeline mein feed ho jata hai.

---

## 🔑 1. Environment Variable Setup (API Key)

Harvester **Google Search API (via Serper.dev)** use karta hai jo ke 2,500 Google searches free deta hai.

Aapki key aapke `~/.zshrc` mein pehle se add kar di gayi hai:
```bash
# Agar kisi nayi machine par chalana ho:
export SERPER_API_KEY="af3b851937396b936aa328e72fc1b3735ed9a126"

# Permanent save karne ke liye:
echo 'export SERPER_API_KEY="af3b851937396b936aa328e72fc1b3735ed9a126"' >> ~/.zshrc
source ~/.zshrc
```

*(Note: Agar aap Brave Search API use karna chahein to `BRAVE_API_KEY` bhi support karta hai).*

---

## ⚡ 2. Basic Command Structure

Harvester ko aap direct `main.py` ke zariye run karte hain:

```bash
cd "malik-lead-ai"
python3 main.py harvest --city <CITY> --country <COUNTRY_CODE> --category <NICHE> --limit <COUNT>
```

### CLI Parameters:
| Argument | Description | Default | Example |
| :--- | :--- | :--- | :--- |
| `--city` | Target city | `Lahore` | `--city London`, `--city Dubai`, `--city Karachi` |
| `--country` | ISO 2-letter Country code | `PK` | `PK`, `UK`, `AE`, `US`, `CA`, `SA` |
| `--category` | Business niche ya product | `pret clothing` | `"jewelry brand"`, `"bakery"`, `"perfume"` |
| `--limit` | Maximum leads to collect | `20` | `--limit 30`, `--limit 50`, `--limit 100` |
| `-o`, `--output` | Output CSV path | `input/harvested_leads.csv` | `-o input/dubai_luxury.csv` |
| `--auto-pipeline` | Harvest ke foran baad full pipeline chalao | `False` | Flag (sirf `--auto-pipeline` likhein) |

---

## 🎯 3. Ready-to-Use Command Examples

### A. Local Pakistan Harvests:

```bash
# 1. Lahore Pret Wear (30 leads):
python3 main.py harvest --city Lahore --category "pret wear" --limit 30

# 2. Karachi Home Bakeries (25 leads):
python3 main.py harvest --city Karachi --category "bakery cakes" --limit 25 -o input/karachi_bakeries.csv

# 3. Islamabad Boutiques & Jewelry (40 leads):
python3 main.py harvest --city Islamabad --category "jewelry designer" --limit 40 -o input/isb_jewelry.csv
```

### B. International Cities Harvests:

```bash
# 1. London (UK) Jewelry Brands (30 leads):
python3 main.py harvest --city London --country UK --category "jewelry brand" --limit 30 -o input/london_jewelry.csv

# 2. Dubai (UAE) Luxury Clothing (50 leads):
python3 main.py harvest --city Dubai --country AE --category "luxury clothing" --limit 50 -o input/dubai_luxury.csv

# 3. New York (US) Fashion Boutiques (30 leads):
python3 main.py harvest --city "New York" --country US --category "fashion boutique" --limit 30 -o input/ny_fashion.csv
```

---

## 🚀 4. End-to-End Automated Pipeline (`--auto-pipeline`)

Agar aap chahte hain ke pehle leads harvest hon, aur foran research (M2), scoring (M3), outreach copy (M4), aur WhatsApp execution (M6) complete ho jaye:

```bash
python3 main.py harvest --city Lahore --category "pret wear" --limit 20 --auto-pipeline
```

Ya manual 2-step tariqa:
```bash
# Step 1: Harvest leads
python3 main.py harvest --city Lahore --category "pret wear" --limit 30 -o input/my_batch.csv

# Step 2: Run MalikAxiom Lead AI Pipeline
python3 main.py pipeline input/my_batch.csv

# Step 3: WhatsApp Outreach Preview (Dry Run)
python3 main.py outreach-execute --dry-run
```

---

## 📁 5. Directory Ingestion Format (`b2b-linkdien`)

Agar aapko yahi leads Track B (Directory / No-website companies) ke liye `b2b-linkdien` mein chahiye:

```bash
cd "/Users/malikhaidernawaz/Documents/b2b-linkdien"

# Harvest directly into directory CSV:
python3 harvest_instagram.py --country PK --city Lahore --category "pret clothing" --limit 30

# Ingest into b2b-linkdien:
python -m malikaxiom_leads discover --source directory --country PK --listings data/instagram_directory_leads.csv
```

---

## 📊 6. Standard 22-Column Schema Match

Harvested CSV bilkul standard format mein save hoti hai:

```csv
business_name,phone,website_phones,email,website,facebook,instagram,linkedin,twitter,whatsapp,youtube,tiktok,address,category,rating,reviews,hours,latitude,longitude,place_id,cid,google_maps_url
```

* `business_name`: Extracted brand title
* `phone`: Cleaned phone number (+92 / +44 / +971 format)
* `whatsapp`: Same as verified mobile phone
* `instagram`: Direct profile link (`https://instagram.com/username/`)
* `category`: Specified niche
* `address`: Specified city + country (e.g. `Lahore, Pakistan`, `Dubai, UAE`)

---

## 🛠️ 7. Troubleshooting & FAQ

* **Q: Phone number kahan se nikalta hai?**  
  Google SERP ke indexed bio snippets se jahan brands *"DM for inquiries"*, *"WhatsApp 03xx-xxxxxxx"*, *"wa.me/923xx"* likhti hain.
* **Q: Har roz kitni searches kar sakte hain?**  
  Serper.dev free tier 2,500 queries deta hai. Rozana 50-100 searches aaram se ho sakti hain.
* **Q: Duplicate leads ka kya hota hai?**  
  Code mein automatic `seen_handles` set laga hai — ek run mein koi bhi duplicate profile dobara CSV mein add nahi hoti.
