#!/usr/bin/env python3
"""MalikAxiom Lead AI - entry point.

Milestones:
    1. Project structure, knowledge base, structure validation.
    2. Lead input + research engine (CSV -> structured JSON + CSV).
    3. AI lead qualification + service matching
       (research_results.json -> qualification_results.json/csv + report.md).
    4. Personalized outreach generator
       (qualification_results.json -> outreach_results.json/csv/md).
    5. Real lead pipeline + sales-ready report
       (Full pipeline: research → qualify → outreach → master sales report).

Explicitly NOT implemented (out of scope):
    Lead extraction / Google Maps scraping
    CRM, dashboard, automated sending
    WhatsApp API, email sending, Instagram automation

Standard library only. No external API calls required.
Messages generated for MANUAL REVIEW AND SENDING ONLY.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
VENDOR_DIR = PROJECT_ROOT / "vendor"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if VENDOR_DIR.exists() and str(VENDOR_DIR) not in sys.path:
    sys.path.append(str(VENDOR_DIR))

from research.researcher import run_research
from qualification.qualifier import run_qualification
from outreach.composer import run_outreach
from sales_report.output_writer import run_sales_report

PROJECT_NAME = "MalikAxiom Lead AI"
CURRENT_MILESTONE = "Milestone 7 - Sales Dashboard & Command Center (M1-M6 stable)"

KNOWLEDGE_DIR = PROJECT_ROOT / "knowledge"
INPUT_DIR = PROJECT_ROOT / "input"
OUTPUT_DIR = PROJECT_ROOT / "output"

KNOWLEDGE_FILES: tuple[str, ...] = (
    "company.md",
    "services.md",
    "business_digitalization.md",
    "ideal_clients.md",
    "qualification_rules.md",
    "outreach_rules.md",
)

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s [%(name)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("malik-lead-ai")


def check_structure() -> list[str]:
    issues: list[str] = []
    for directory in (KNOWLEDGE_DIR, INPUT_DIR, OUTPUT_DIR):
        if not directory.is_dir():
            issues.append(f"Missing directory: {directory}")
    for name in KNOWLEDGE_FILES:
        path = KNOWLEDGE_DIR / name
        if not path.is_file():
            issues.append(f"Missing knowledge file: {path}")
        elif not path.read_text(encoding="utf-8").strip():
            issues.append(f"Empty knowledge file: {path}")
    return issues


def list_knowledge() -> None:
    print("Knowledge base files:")
    for name in KNOWLEDGE_FILES:
        path = KNOWLEDGE_DIR / name
        if path.is_file():
            first_heading = next(
                (line.lstrip("# ").strip() for line in path.read_text(encoding="utf-8").splitlines() if line.startswith("#")),
                name,
            )
            print(f"  - {name:<28} {first_heading}")
        else:
            print(f"  - {name:<28} (MISSING)")


def show_knowledge(topic: str) -> int:
    filename = topic if topic.endswith(".md") else f"{topic}.md"
    if filename not in KNOWLEDGE_FILES:
        print(f"Unknown knowledge topic: {topic!r}", file=sys.stderr)
        print(f"Available topics: {', '.join(KNOWLEDGE_FILES)}", file=sys.stderr)
        return 1
    path = KNOWLEDGE_DIR / filename
    if not path.is_file():
        print(f"Knowledge file not found: {path}", file=sys.stderr)
        return 1
    print(path.read_text(encoding="utf-8"))
    return 0


def print_status() -> None:
    print(f"{PROJECT_NAME}")
    print(f"Current: {CURRENT_MILESTONE}")
    print()
    print("Project structure:")
    print(f"  {PROJECT_ROOT}")
    for directory in (KNOWLEDGE_DIR, INPUT_DIR, OUTPUT_DIR):
        print(f"  +-- {directory.name}/")
    print(f"  +-- main.py")
    print()
    print("Directories:")
    for directory in (KNOWLEDGE_DIR, INPUT_DIR, OUTPUT_DIR):
        state = "ok" if directory.is_dir() else "MISSING"
        print(f"  [{state}] {directory.name}/")
    print()
    list_knowledge()
    print()
    issues = check_structure()
    if issues:
        print("Structure check: FAILED")
        for issue in issues:
            print(f"  - {issue}")
    else:
        print("Structure check: OK - all knowledge files present.")
    print()
    print("Milestone 2 status:")
    print("  - input/ schema, sample_leads.csv, leads.csv: present")
    print("  - research/ module: present")
    print("  - Run: python3 main.py research input/leads.csv")
    print()
    print("Milestone 3 status:")
    print("  - qualification/ module: present")
    print("  - Run: python3 main.py qualify")
    print("  - Outputs: output/qualification_results.json")
    print("             output/qualification_results.csv")
    print("             output/qualified_leads_report.md")
    print()
    print("Milestone 4 status:")
    print("  - outreach/ module: present")
    print("  - Run: python3 main.py outreach")
    print("  - Run: python3 main.py outreach --mock   (pipeline test)")
    print("  - Outputs: output/outreach_results.json")
    print("             output/outreach_results.csv")
    print("             output/outreach_results.md")
    print()
    print("Milestone 5 status:")
    print("  - sales_report/ module: present")
    print("  - Run: python3 main.py sales-report")
    print("  - Run: python3 main.py pipeline input/leads.csv  (full pipeline)")
    print("  - Outputs: output/malikaxiom_sales_leads.csv")
    print("             output/contact_first.csv")
    print("             output/malikaxiom_sales_summary.md")
    print()
    print("Milestone 6 status (outreach execution engine):")
    print("  - m6/ module: present (validator, message_builder, send_tracker, channels)")
    print("  - Run: python3 main.py outreach-execute --dry-run     (inspect, sends nothing)")
    print("  - Run: python3 main.py outreach-execute               (send approved leads)")
    print("  - Run: python3 main.py outreach-execute --lead-id <id>")
    print("  - Outputs: output/m6_send_state.json      (duplicate-send protection)")
    print("             output/m6_outreach_results.json")
    print("             output/m6_outreach_results.csv")
    print("             output/m6_outreach.log")
    print()
    print("Out of scope (not implemented):")
    print("  - Lead extraction / Google Maps scraping")
    print("  - CRM, dashboard")
    print("  - Paid messaging APIs, Instagram/Facebook/email automation")
    print("  - Auto follow-ups, auto replies, bulk blasting")
    print("  M6 sends ONE initial WhatsApp message per approved lead; a human takes over.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="main.py",
        description=f"{PROJECT_NAME} - {CURRENT_MILESTONE}",
    )
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("status", help="Show project status and validate structure (default).")
    subparsers.add_parser("list", help="List the knowledge base files.")

    show_parser = subparsers.add_parser("show", help="Print a knowledge file.")
    show_parser.add_argument("topic", help=f"Knowledge topic name (one of: {', '.join(KNOWLEDGE_FILES)})")

    subparsers.add_parser("check", help="Validate the project structure; exit 1 on failure.")

    research_parser = subparsers.add_parser(
        "research",
        help="Research leads from a CSV file and write JSON + CSV output.",
    )
    research_parser.add_argument("input_csv", help="Path to the input CSV with raw leads.")
    research_parser.add_argument("-o", "--output", help="Output directory for research_results.json and research_results.csv (default: output/).")
    research_parser.add_argument("--timeout", type=float, default=12.0, help="Request timeout in seconds for website/social checks (default: 12).")
    research_parser.add_argument("-q", "--quiet", action="store_true", help="Suppress per-lead progress output.")

    qualify_parser = subparsers.add_parser(
        "qualify",
        help="Qualify researched leads and write JSON + CSV + Markdown report.",
    )
    qualify_parser.add_argument(
        "-i", "--input",
        default=None,
        help="Path to research_results.json (default: output/research_results.json).",
    )
    qualify_parser.add_argument(
        "-o", "--output",
        default=None,
        help="Output directory for qualification files (default: output/).",
    )
    qualify_parser.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="Suppress per-lead progress output.",
    )

    outreach_parser = subparsers.add_parser(
        "outreach",
        help="Generate personalized outreach messages from qualification results.",
    )
    outreach_parser.add_argument(
        "-i", "--input",
        default=None,
        help="Path to qualification_results.json (default: output/qualification_results.json).",
    )
    outreach_parser.add_argument(
        "-o", "--output",
        default=None,
        help="Output directory for outreach files (default: output/).",
    )
    outreach_parser.add_argument(
        "--mock",
        action="store_true",
        help="Pipeline test mode: generate labeled mock messages (no real composition).",
    )
    outreach_parser.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="Suppress per-lead progress output.",
    )

    sales_report_parser = subparsers.add_parser(
        "sales-report",
        help="Generate master sales leads CSV, contact_first.csv, and summary report.",
    )
    sales_report_parser.add_argument(
        "-o", "--output",
        default=None,
        help="Output directory (default: output/).",
    )
    sales_report_parser.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="Suppress progress output.",
    )

    pipeline_parser = subparsers.add_parser(
        "pipeline",
        help="Run the complete end-to-end pipeline: research -> qualify -> outreach -> sales-report.",
    )
    pipeline_parser.add_argument(
        "input_csv",
        help="Path to the input CSV with raw leads.",
    )
    pipeline_parser.add_argument(
        "-o", "--output",
        default=None,
        help="Output directory (default: output/).",
    )
    pipeline_parser.add_argument(
        "--timeout",
        type=float,
        default=12.0,
        help="Request timeout in seconds for website/social checks (default: 12).",
    )
    pipeline_parser.add_argument(
        "--mock",
        action="store_true",
        help="Pipeline test mode for outreach.",
    )
    pipeline_parser.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="Suppress per-lead progress output.",
    )

    # ------------------------------------------------------------------
    # Milestone 6 — outreach execution engine (additive; M1-M5 untouched)
    # ------------------------------------------------------------------
    execute_parser = subparsers.add_parser(
        "outreach-execute",
        help="M6: send ONE validated WhatsApp first-touch message per eligible M5 lead.",
    )
    execute_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show leads, recipients, services, messages and validation WITHOUT sending anything.",
    )
    execute_parser.add_argument(
        "--lead-id",
        action="append",
        default=[],
        metavar="LEAD_ID",
        help="Only process this M5 lead_id (repeatable). Example: --lead-id lead_017_arbrandzone",
    )
    execute_parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum messages this run (hard cap: 10).",
    )
    execute_parser.add_argument(
        "--source",
        default=None,
        help="M5 output file to read (default: output/malikaxiom_sales_leads.csv).",
    )
    execute_parser.add_argument(
        "-o", "--output",
        default=None,
        help="Output directory for M6 state/results/log (default: output/).",
    )
    execute_parser.add_argument(
        "--channel",
        choices=("playwright", "assist"),
        default="playwright",
        help="playwright = automated WhatsApp Web sending (default). assist = manual WhatsApp assist mode.",
    )
    execute_parser.add_argument(
        "--include-action",
        action="append",
        default=[],
        choices=("CONTACT_FIRST", "CONTACT_LATER", "INVESTIGATE", "ARCHIVE", "SKIP"),
        help="Explicitly allow an extra M5 action category (repeatable). Default: CONTACT_FIRST only.",
    )
    execute_parser.add_argument(
        "--include-pricing",
        dest="include_pricing",
        action="store_true",
        default=True,
        help="Add the short 'starting from PKR 10,000' line for local business leads (default: True).",
    )
    execute_parser.add_argument(
        "--no-pricing",
        dest="include_pricing",
        action="store_false",
        help="Disable the pricing mention in outreach messages.",
    )
    execute_parser.add_argument(
        "--template",
        choices=("demo", "standard"),
        default="demo",
        help="Message template: 'demo' (Personalized Boutique Storefront Demo in Roman Urdu, default) or 'standard' (M6 text template).",
    )
    execute_parser.add_argument(
        "--retry-failed",
        action="store_true",
        help="Allow one retry for leads whose previous attempt FAILED (never retried automatically).",
    )
    execute_parser.add_argument(
        "--force-resend",
        action="store_true",
        help="Ignore previous send state (use only with an explicit --lead-id).",
    )
    execute_parser.add_argument(
        "--confirm-manual-send",
        action="store_true",
        help="After opening the WhatsApp chat, ask whether you sent it and record SENT if yes.",
    )
    execute_parser.add_argument(
        "--mark-sent",
        action="store_true",
        help="Record SENT for already-opened lead(s) given via --lead-id (no chat is opened).",
    )
    execute_parser.add_argument(
        "--mark-no-whatsapp",
        dest="mark_no_whatsapp",
        action="store_true",
        help=(
            "Record lead(s) given via --lead-id as NO_WHATSAPP_NUMBER (the number has no "
            "WhatsApp account). Blocking: M6 never attempts that number again."
        ),
    )
    execute_parser.add_argument(
        "--reclassify-no-whatsapp",
        dest="reclassify_no_whatsapp",
        action="store_true",
        help=(
            "Scan the saved send state and move every lead whose recorded reason proves a "
            "number has no WhatsApp (e.g. Pakistani landline) to NO_WHATSAPP_NUMBER."
        ),
    )
    execute_parser.add_argument(
        "--show-state",
        action="store_true",
        help="Print the persistent M6 send state and exit.",
    )
    execute_parser.add_argument(
        "--open-browser",
        dest="open_browser",
        action="store_true",
        default=None,
        help="Open the WhatsApp chat in the browser (default in execute mode).",
    )
    execute_parser.add_argument(
        "--no-browser",
        dest="open_browser",
        action="store_false",
        help="Only generate the WhatsApp link; do not open a browser.",
    )
    execute_parser.add_argument(
        "--skip-review-flagged",
        action="store_true",
        help="Skip leads that M5's audit layer flagged for human review.",
    )
    execute_parser.add_argument(
        "--allow-channel-inference",
        action="store_true",
        help="Allow WhatsApp when M5's outreach_channel is unknown but a valid mobile exists.",
    )
    execute_parser.add_argument(
        "--min-interval",
        type=int,
        default=None,
        help=(
            "Minimum seconds between two sends (default: 180 = 3 minutes). "
            "Anti-restriction safety value — do not lower it."
        ),
    )
    execute_parser.add_argument(
        "--jitter",
        type=int,
        default=None,
        help=(
            "Random extra seconds added to each gap, so the cadence is not a "
            "fixed metronome (default: 120, giving a 3–5 minute gap)."
        ),
    )
    execute_parser.add_argument(
        "--log-file",
        default=None,
        help="M6 log file (default: output/m6_outreach.log).",
    )
    execute_parser.add_argument(
        "--yes",
        action="store_true",
        help="Confirm real sends without the interactive SEND prompt (needed in non-interactive shells).",
    )
    execute_parser.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="Suppress progress output.",
    )
    export_excel_parser = subparsers.add_parser(
        "export-excel",
        help="Export complete M1-M6 results and pipeline view to an Excel workbook.",
    )
    export_excel_parser.add_argument(
        "-o", "--output",
        default=None,
        help="Output directory for malikaxiom_lead_ai.xlsx (default: output/).",
    )
    export_excel_parser.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="Suppress detailed progress output.",
    )

    dashboard_parser = subparsers.add_parser(
        "dashboard",
        help="Launch the M7 Sales Dashboard & Command Center UI.",
    )
    dashboard_parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host address to bind the dashboard server (default: 127.0.0.1).",
    )
    dashboard_parser.add_argument(
        "-p", "--port",
        type=int,
        default=8080,
        help="Port to listen on (default: 8080).",
    )
    dashboard_parser.add_argument(
        "--open-browser",
        action="store_true",
        help="Automatically open web browser upon launch.",
    )
    normalize_parser = subparsers.add_parser(
        "normalize",
        help="Normalize raw scraper CSV into the standardized 22-column schema.",
    )
    normalize_parser.add_argument(
        "input_csv",
        help="Path to input raw scraper CSV file.",
    )
    normalize_parser.add_argument(
        "-o", "--output",
        default=None,
        help="Path to output standardized CSV (overwrites input if omitted).",
    )

    # ── HARVEST ─────────────────────────────────────────────────────────────
    harvest_parser = subparsers.add_parser(
        "harvest",
        help="Harvest Instagram startup leads by city & category (no login needed).",
    )
    harvest_parser.add_argument(
        "--city",
        default="Lahore",
        help="Target city (e.g. Lahore, Karachi, London, Dubai, New York).",
    )
    harvest_parser.add_argument(
        "--country",
        default="PK",
        help="ISO country code (PK, UK, AE, US, …). Affects phone extraction & address.",
    )
    harvest_parser.add_argument(
        "--category",
        default="pret clothing",
        help="Business niche (e.g. 'pret wear', 'jewelry', 'bakery', 'branding studio').",
    )
    harvest_parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Maximum number of leads to collect (default: 20).",
    )
    harvest_parser.add_argument(
        "-o", "--output",
        default=None,
        help="Output CSV path (default: input/harvested_leads.csv).",
    )
    harvest_parser.add_argument(
        "--auto-pipeline",
        action="store_true",
        help="Automatically chain into 'pipeline' after harvesting.",
    )

    return parser


def _run_outreach_execute(args: argparse.Namespace) -> int:
    """M6 CLI handler — planning/validation/dry-run/execution of outreach sends.

    Additive M6 entry point. It never alters M1–M5 behaviour: it only reads
    M5's final CSV output and writes new ``m6_*`` files.
    """
    from m6.config import (
        DEFAULT_SEND_LIMIT,
        MIN_SECONDS_BETWEEN_SENDS,
        SEND_INTERVAL_JITTER_SECONDS,
    )
    from m6.engine import (
        M6RunConfig,
        mark_lead_sent,
        mark_no_whatsapp,
        reclassify_no_whatsapp,
        run_outreach_command,
        show_state,
    )

    out_dir = Path(args.output) if args.output else OUTPUT_DIR
    if not out_dir.is_absolute():
        out_dir = PROJECT_ROOT / out_dir

    if args.quiet:
        logging.getLogger().setLevel(logging.WARNING)

    if args.show_state:
        return show_state(out_dir)

    if args.reclassify_no_whatsapp:
        return reclassify_no_whatsapp(output_dir=out_dir)

    if args.mark_no_whatsapp:
        if not args.lead_id:
            print("--mark-no-whatsapp requires at least one --lead-id.", file=sys.stderr)
            return 2
        exit_code = 0
        for lead_id in args.lead_id:
            exit_code |= mark_no_whatsapp(lead_id, output_dir=out_dir)
        return exit_code

    if args.mark_sent:
        if not args.lead_id:
            print("--mark-sent requires at least one --lead-id.", file=sys.stderr)
            return 2
        exit_code = 0
        for lead_id in args.lead_id:
            exit_code |= mark_lead_sent(lead_id, output_dir=out_dir)
        return exit_code

    if args.force_resend and not args.lead_id:
        print(
            "--force-resend is only allowed together with an explicit --lead-id.",
            file=sys.stderr,
        )
        return 2

    config = M6RunConfig(
        output_dir=out_dir,
        source=args.source,
        lead_ids=tuple(args.lead_id),
        dry_run=args.dry_run,
        include_actions=frozenset(args.include_action),
        limit=args.limit if args.limit is not None else DEFAULT_SEND_LIMIT,
        retry_failed=args.retry_failed,
        force_resend=args.force_resend,
        confirm_manual_send=args.confirm_manual_send,
        include_pricing=args.include_pricing,
        skip_review_flagged=args.skip_review_flagged,
        allow_channel_inference=args.allow_channel_inference,
        channel=args.channel,
        open_browser=(not args.dry_run) if args.open_browser is None else args.open_browser,
        yes=args.yes,
        log_file=Path(args.log_file) if args.log_file else None,
        min_interval_s=(
            args.min_interval if args.min_interval is not None else MIN_SECONDS_BETWEEN_SENDS
        ),
        jitter_s=(
            args.jitter if args.jitter is not None else SEND_INTERVAL_JITTER_SECONDS
        ),
        quiet=args.quiet,
        template=getattr(args, "template", "demo"),
    )

    print("=" * 60)
    print("MalikAxiom Lead AI — Milestone 6: Outreach Execution Engine")
    print(f"Mode: {'DRY RUN (nothing is sent)' if args.dry_run else 'EXECUTE'}")
    print("=" * 60)
    print()

    exit_code = run_outreach_command(config)
    print()
    if exit_code != 0:
        print("M6 finished with issues — review the output above and the log file.", file=sys.stderr)

    # Automatically refresh master Excel results workbook with latest state
    try:
        from exporter.excel_exporter import build_excel_workbook
        excel_path = build_excel_workbook(out_dir, out=lambda *_: None)
        print(f"Master Excel updated: {excel_path}")
    except Exception as exc:
        logger.debug("Automatic Excel export skipped: %s", exc)

    return exit_code


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "list":
        list_knowledge()
        return 0
    if args.command == "show":
        return show_knowledge(args.topic)
    if args.command == "check":
        issues = check_structure()
        if issues:
            print("Structure check: FAILED", file=sys.stderr)
            for issue in issues:
                print(f"  - {issue}", file=sys.stderr)
            return 1
        print("Structure check: OK - all knowledge files present.")
        return 0
    if args.command == "research":
        csv_path = Path(args.input_csv)
        if not csv_path.is_absolute():
            csv_path = PROJECT_ROOT / csv_path
        if not csv_path.is_file():
            print(f"Input CSV not found: {csv_path}", file=sys.stderr)
            return 1

        out_dir = Path(args.output) if args.output else OUTPUT_DIR
        if not out_dir.is_absolute():
            out_dir = PROJECT_ROOT / out_dir

        print(f"Researching leads from: {csv_path}")
        print(f"Output directory: {out_dir}")
        print()

        json_path, csv_out_path, total, fully, partial, unreachable, errors = run_research(
            csv_path=csv_path,
            output_dir=out_dir,
            timeout=args.timeout,
        )

        print()
        print("Research complete.")
        print(f"{total} leads processed.")
        print(f"{fully} fully researched.")
        print(f"{partial} partially researched.")
        if unreachable:
            print(f"{unreachable} website(s) unreachable (DNS/network — not system errors).")
        if errors:
            print(f"{errors} system error(s) — see logs for details.")
        else:
            print("0 system errors.")
        print()
        print(f"JSON output: {json_path}")
        print(f"CSV output: {csv_out_path}")
        return 0

    if args.command == "qualify":
        in_path = Path(args.input) if args.input else OUTPUT_DIR / "research_results.json"
        if not in_path.is_absolute():
            in_path = PROJECT_ROOT / in_path

        out_dir = Path(args.output) if args.output else OUTPUT_DIR
        if not out_dir.is_absolute():
            out_dir = PROJECT_ROOT / out_dir

        if not in_path.is_file():
            print(
                f"Research results not found: {in_path}",
                file=sys.stderr,
            )
            print(
                "Run 'python3 main.py research input/leads.csv' first.",
                file=sys.stderr,
            )
            return 1

        if args.quiet:
            logging.getLogger().setLevel(logging.WARNING)

        print(f"Qualifying leads from: {in_path}")
        print(f"Output directory: {out_dir}")
        print()

        try:
            json_path, csv_path, report_path, total, counts = run_qualification(
                input_json=in_path,
                output_dir=out_dir,
            )
        except FileNotFoundError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1

        print()
        print("Qualification complete.")
        print(f"  {total} leads processed.")
        print(f"  {counts.get('HIGH', 0)} HIGH potential.")
        print(f"  {counts.get('MODERATE', 0)} MODERATE potential.")
        print(f"  {counts.get('LOW', 0)} LOW potential.")
        print(f"  {counts.get('SKIP', 0)} SKIP.")
        print()
        print(f"JSON output:   {json_path}")
        print(f"CSV output:    {csv_path}")
        print(f"Report:        {report_path}")
        return 0

    if args.command == "outreach":
        in_path = Path(args.input) if args.input else OUTPUT_DIR / "qualification_results.json"
        if not in_path.is_absolute():
            in_path = PROJECT_ROOT / in_path

        out_dir = Path(args.output) if args.output else OUTPUT_DIR
        if not out_dir.is_absolute():
            out_dir = PROJECT_ROOT / out_dir

        if not in_path.is_file():
            print(
                f"Qualification results not found: {in_path}",
                file=sys.stderr,
            )
            print(
                "Run 'python3 main.py qualify' first.",
                file=sys.stderr,
            )
            return 1

        if args.quiet:
            logging.getLogger().setLevel(logging.WARNING)

        mode = " [MOCK MODE]" if args.mock else ""
        print(f"Generating outreach messages from: {in_path}{mode}")
        print(f"Output directory: {out_dir}")
        print()

        try:
            json_path, csv_path, report_path, total, counts = run_outreach(
                input_json=in_path,
                output_dir=out_dir,
                mock=args.mock,
            )
        except FileNotFoundError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1

        print()
        if args.mock:
            print("Mock outreach complete (pipeline test).")
        else:
            print("Outreach generation complete.")
        print(f"  {total} leads processed.")
        print(f"  {counts.get('CONTACT FIRST', 0)} CONTACT FIRST.")
        print(f"  {counts.get('CONTACT LATER', 0)} CONTACT LATER.")
        print(f"  {counts.get('SKIP', 0)} SKIP (no outreach).")
        print()
        print(f"JSON output:   {json_path}")
        print(f"CSV output:    {csv_path}")
        print(f"Report:        {report_path}")
        if not args.mock:
            print()
            print("Review outreach_results.md before sending any messages.")
        return 0

    if args.command == "sales-report":
        out_dir = Path(args.output) if args.output else OUTPUT_DIR
        if not out_dir.is_absolute():
            out_dir = PROJECT_ROOT / out_dir

        if args.quiet:
            logging.getLogger().setLevel(logging.WARNING)

        print(f"Generating sales report in: {out_dir}")
        print()

        try:
            master_csv, contact_first_csv, summary_md, xlsx_path, total, audit_counts = run_sales_report(
                output_dir=out_dir,
            )
        except FileNotFoundError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1

        print()
        print("Sales report complete.")
        print(f"  {total} leads processed.")
        print(f"  {audit_counts.get('review_flagged', 0)} review flags.")
        print(f"  {audit_counts.get('possible_duplicates', 0)} possible duplicates.")
        print()
        print(f"Master CSV:        {master_csv}")
        print(f"Contact First CSV: {contact_first_csv}")
        print(f"Summary Markdown:  {summary_md}")
        if xlsx_path:
            print(f"Master XLSX:       {xlsx_path}")
        return 0

    if args.command == "outreach-execute":
        return _run_outreach_execute(args)

    if args.command == "pipeline":
        csv_path = Path(args.input_csv)
        if not csv_path.is_absolute():
            csv_path = PROJECT_ROOT / csv_path
        if not csv_path.is_file():
            print(f"Input CSV not found: {csv_path}", file=sys.stderr)
            return 1

        out_dir = Path(args.output) if args.output else OUTPUT_DIR
        if not out_dir.is_absolute():
            out_dir = PROJECT_ROOT / out_dir

        if args.quiet:
            logging.getLogger().setLevel(logging.WARNING)

        print("==================================================")
        print("Starting MalikAxiom Lead AI Pipeline")
        print(f"Input CSV:  {csv_path}")
        print(f"Output Dir: {out_dir}")
        print("==================================================")
        print()

        print("[1/4] Step 1: Web Research...")
        run_research(csv_path=csv_path, output_dir=out_dir, timeout=args.timeout)
        print()

        print("[2/4] Step 2: Lead Qualification...")
        run_qualification(input_json=out_dir / "research_results.json", output_dir=out_dir)
        print()

        print("[3/4] Step 3: Outreach Generation...")
        run_outreach(input_json=out_dir / "qualification_results.json", output_dir=out_dir, mock=args.mock)
        print()

        print("[4/4] Step 4: Sales Report...")
        master_csv, contact_first_csv, summary_md, xlsx_path, total, audit_counts = run_sales_report(
            output_dir=out_dir,
        )
        print()

        # Automatically refresh master Excel results workbook
        try:
            from exporter.excel_exporter import build_excel_workbook
            excel_path = build_excel_workbook(out_dir, out=lambda *_: None)
        except Exception as exc:
            excel_path = None
            logger.debug("Automatic Excel export skipped: %s", exc)

        print("==================================================")
        print("Pipeline execution complete!")
        print(f"Total leads: {total}")
        print(f"Master CSV:        {master_csv}")
        print(f"Contact First CSV: {contact_first_csv}")
        print(f"Contact Later CSV: {out_dir / 'contact_later.csv'}")
        print(f"Manual Social DMs: {out_dir / 'manual_instagram_leads.csv'}")
        print(f"Mega Cold Calling: {out_dir / 'mega_cold_calling_leads.xlsx'}")
        print(f"Mega Contact 1st:  {out_dir / 'mega_contact_first.csv'}")
        print(f"Mega Contact Late: {out_dir / 'mega_contact_later.csv'}")
        print(f"Batch Archive Dir: {out_dir / 'batches'}")
        print(f"Summary Report:    {summary_md}")
        if excel_path:
            print(f"Master Workbook:   {excel_path}")
        print("==================================================")
        return 0

    if args.command == "export-excel":
        from exporter.excel_exporter import run_export_excel_command

        out_dir = Path(args.output) if args.output else OUTPUT_DIR
        if not out_dir.is_absolute():
            out_dir = PROJECT_ROOT / out_dir

        if args.quiet:
            logging.getLogger().setLevel(logging.WARNING)
            out_func = lambda *_: None
        else:
            out_func = print

        return run_export_excel_command(output_dir=out_dir, out=out_func)

    if args.command == "dashboard":
        from dashboard.server import run_dashboard_server

        run_dashboard_server(
            host=args.host,
            port=args.port,
            open_browser=args.open_browser,
            project_root=PROJECT_ROOT,
        )
        return 0

    if args.command == "normalize":
        from research.input_loader import normalize_csv

        in_path = Path(args.input_csv)
        if not in_path.is_absolute():
            in_path = PROJECT_ROOT / in_path
        if not in_path.is_file():
            print(f"Input CSV not found: {in_path}", file=sys.stderr)
            return 1

        out_path = Path(args.output) if args.output else None
        if out_path and not out_path.is_absolute():
            out_path = PROJECT_ROOT / out_path

        res_path = normalize_csv(in_path, out_path)
        print(f"Standardized CSV written to: {res_path}")
        return 0

    if args.command == "harvest":
        # ── Instagram Startup Harvester ───────────────────────────────────
        import sys as _sys
        _tools_dir = PROJECT_ROOT / "tools"
        if str(_tools_dir) not in _sys.path:
            _sys.path.insert(0, str(_tools_dir))

        try:
            from instagram_harvester import harvest_instagram_leads
        except ImportError as _e:
            print(f"❌ Could not import tools/instagram_harvester.py: {_e}", file=sys.stderr)
            return 1

        # Resolve output path
        out_csv = args.output
        if not out_csv:
            out_csv = str(PROJECT_ROOT / "input" / "harvested_leads.csv")
        else:
            p = Path(out_csv)
            if not p.is_absolute():
                out_csv = str(PROJECT_ROOT / p)

        # Determine country label for address column
        _country_map = {
            "PK": "Pakistan", "UK": "United Kingdom", "US": "United States",
            "AE": "UAE", "CA": "Canada", "AU": "Australia", "IN": "India",
            "SA": "Saudi Arabia", "DE": "Germany", "FR": "France",
        }
        country_label = _country_map.get(args.country.upper(), args.country.upper())

        print(f"\n🌍 Harvest Config → City: {args.city} | Country: {country_label} | Category: {args.category} | Limit: {args.limit}")

        count, saved_path = harvest_instagram_leads(
            city=args.city,
            category=args.category,
            limit=args.limit,
            output_file=out_csv,
            country_label=country_label,
            country_code=args.country.upper(),
        )

        if count == 0:
            print("⚠️  No leads harvested. Try a different city or category.")
            return 1

        rel_path = Path(saved_path).relative_to(PROJECT_ROOT) if Path(saved_path).is_relative_to(PROJECT_ROOT) else Path(saved_path)

        print(f"\n{'='*50}")
        print(f"✅  Harvested {count} Instagram leads  →  {rel_path}")
        print(f"{'='*50}")
        print(f"\n💡 Next steps:")
        print(f"   Run full pipeline  : python3 main.py pipeline {rel_path}")
        print(f"   Or harvest more    : python3 main.py harvest --city {args.city} --category \"{args.category}\" --limit 50")

        if args.auto_pipeline:
            print(f"\n🚀 --auto-pipeline flag detected → launching pipeline automatically...\n")
            import subprocess
            result = subprocess.run(
                [_sys.executable, str(PROJECT_ROOT / "main.py"), "pipeline", saved_path],
                cwd=str(PROJECT_ROOT),
            )
            return result.returncode

        return 0

    print_status()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
