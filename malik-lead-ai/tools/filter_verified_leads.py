import csv, glob, os

# Load verified leads status
status_map = {}
with open("input/verification_report.csv", mode="r", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        handle = row["handle"].strip().lower()
        if handle:
            status_map[handle] = row["status"]

print(f"Loaded verification status for {len(status_map)} handles.")

# Now scan all city CSVs and produce a single clean master file: input/clean_no_website_watches.csv
city_files = glob.glob("input/*_watches.csv")
verified_leads = []
seen = set()

fieldnames = None

for cf in city_files:
    if "clean" in cf or "verification" in cf:
        continue
    with open(cf, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if not fieldnames:
            fieldnames = reader.fieldnames
        for row in reader:
            ig = row.get("instagram", "")
            # extract handle
            handle = ig.rstrip("/").split("/")[-1].lower() if ig else ""
            if not handle:
                continue
            if status_map.get(handle) == "NO_WEBSITE" and handle not in seen:
                seen.add(handle)
                verified_leads.append(row)

out_file = "input/clean_no_website_watches.csv"
with open(out_file, mode="w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(verified_leads)

print(f"✅ Generated {out_file} with {len(verified_leads)} 100% verified NO-WEBSITE watch leads!")
