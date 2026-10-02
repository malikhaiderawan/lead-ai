#!/usr/bin/env python3
"""MalikAxiom Lead AI — M7 Sales Command Center Launcher.

Zero-database, filesystem-driven sales dashboard and intelligence platform.
Usage:
    python3 dashboard.py
    python3 dashboard.py --port 8080 --open-browser
    python3 main.py dashboard
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
VENDOR_DIR = PROJECT_ROOT / "vendor"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if VENDOR_DIR.exists() and str(VENDOR_DIR) not in sys.path:
    sys.path.insert(0, str(VENDOR_DIR))

from dashboard.server import run_dashboard_server


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="dashboard.py",
        description="MalikAxiom Lead AI — M7 Sales Command Center",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host address to bind to (default: 127.0.0.1)",
    )
    parser.add_argument(
        "-p", "--port",
        type=int,
        default=8080,
        help="Port number to listen on (default: 8080)",
    )
    parser.add_argument(
        "--open-browser",
        action="store_true",
        help="Automatically open default browser to dashboard URL",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        run_dashboard_server(
            host=args.host,
            port=args.port,
            open_browser=args.open_browser,
            project_root=PROJECT_ROOT,
        )
        return 0
    except Exception as exc:
        print(f"Error launching dashboard server: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
