"""
run_daily.py
Daily data ingestion job for Farmula DSS.

Flags:
  --db-only     Fetch today's data from data.gov.in and save to NeonDB.
                Used by GitHub Actions.
  --fetch-only  Fetch today's data and save to a local CSV (no DB write).
                Used for local testing / offline runs.
  --all         Run both DB ingestion and CSV export.
"""

import os
import sys
import argparse

# Ensure project root is on the path regardless of where this is invoked from
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.data_fetcher import fetch_maharashtra_daily
from src.db_utils import save_mandi_records_to_db


# ---------------------------------------------------------------------------
# Core actions
# ---------------------------------------------------------------------------

def fetch_and_save_to_db() -> int:
    """Fetches today's data and saves to NeonDB. Used by GitHub Actions."""
    print("Fetching today's Maharashtra mandi data...")
    df = fetch_maharashtra_daily(days_back=2)
    if df.empty:
        print("No data returned from API today.")
        return 0
    count = save_mandi_records_to_db(df)
    print(f"Saved {count} new records to NeonDB")
    return count


def fetch_and_save_to_csv(output_path: str = "data/daily_fetch.csv") -> int:
    """Fetches today's data and saves to a local CSV file."""
    print("Fetching today's Maharashtra mandi data...")
    df = fetch_maharashtra_daily(days_back=2)
    if df.empty:
        print("No data returned from API today.")
        return 0
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    df.to_csv(output_path, index=False)
    print(f"Saved {len(df)} records to {output_path}")
    return len(df)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Farmula daily data ingestion job.")
    parser.add_argument("--db-only",    action="store_true",
                        help="Fetch live data and write to NeonDB (GitHub Actions mode)")
    parser.add_argument("--fetch-only", action="store_true",
                        help="Fetch live data and save to local CSV only")
    parser.add_argument("--all",        action="store_true",
                        help="Run both DB ingestion and local CSV export")
    args = parser.parse_args()

    if args.db_only:
        fetch_and_save_to_db()

    elif args.fetch_only:
        fetch_and_save_to_csv()

    elif args.all:
        fetch_and_save_to_db()
        fetch_and_save_to_csv()

    else:
        parser.print_help()
