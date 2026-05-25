# -*- coding: utf-8 -*-
"""
Bulk fetch ~2 years of historical Agmarknet data for all target
Maharashtra commodity-district pairs. Stores in mandi_prices table.

Run once. Idempotent — uses ON CONFLICT DO NOTHING for dedup.
"""
import os
import sys
import time
import requests
from pathlib import Path
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Make src importable
sys.path.append(str(Path(__file__).parent.parent / "src"))

from db_utils import save_mandi_records_to_db
from maharashtra_coverage import TARGET_DISTRICTS, TARGET_COMMODITIES
import pandas as pd

load_dotenv()
API_KEY = os.getenv("DATAGOV_API_KEY")
RESOURCE_ID = "9ef84268-d588-465a-a308-a864a43d0070"
BASE_URL = f"https://api.data.gov.in/resource/{RESOURCE_ID}"

# Exclude fruits to reduce runtime while keeping strong data volume
_EXCLUDED_COMMODITIES = {
    "Mango",
    "Banana",
    "Pomegranate",
    "Grapes",
}

# Column name map — handles both Title_Case (existing endpoint) and
# lowercase (historical endpoint) field names from data.gov.in
_COL_ALIASES = {
    # historical endpoint (lowercase)
    "arrival_date": "date",
    "market":       "market",
    "modal_price":  "modal_price",
    "min_price":    "min_price",
    "max_price":    "max_price",
    "district":     "district",
    "commodity":    "commodity",
    # daily endpoint (Title_Case) — fallback
    "Arrival_Date": "date",
    "Market":       "market",
    "Modal_Price":  "modal_price",
    "Min_Price":    "min_price",
    "Max_Price":    "max_price",
    "District":     "district",
    "Commodity":    "commodity",
}


def _date_ranges(days_back: int, chunk_days: int = 365) -> list[tuple[datetime, datetime]]:
    """Builds inclusive date ranges using chunk_days sized windows."""
    end = datetime.today().date()
    start = end - timedelta(days=days_back)

    ranges = []
    cursor = start
    while cursor <= end:
        range_start = cursor
        range_end = min(cursor + timedelta(days=chunk_days - 1), end)
        ranges.append((range_start, range_end))
        cursor = range_end + timedelta(days=1)

    return ranges


def fetch_pair(commodity: str, district: str, days_back: int = 730) -> pd.DataFrame:
    """
    Fetch up to days_back days of records for one commodity-district pair.
    Paginates until all records retrieved.
    """
    all_records = []
    limit = 1000  # max safe per request

    print(f"\n  Fetching {commodity} / {district} (last {days_back} days)...")

    for range_start, range_end in _date_ranges(days_back, chunk_days=365):
        offset = 0
        date_filter = f"{range_start:%Y-%m-%d}:{range_end:%Y-%m-%d}"
        print(f"    Date window: {date_filter}")

        while True:
            params = {
                "api-key": API_KEY,
                "format": "json",
                "limit": limit,
                "offset": offset,
                "filters[state]": "Maharashtra",
                "filters[district]": district,
                "filters[commodity]": commodity,
                "filters[arrival_date]": date_filter,
            }
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Farmula/1.0"
            }

            try:
                response = requests.get(BASE_URL, params=params, headers=headers, timeout=90)

                if response.status_code == 429:
                    print("    Rate limit hit, sleeping 30s...")
                    time.sleep(30)
                    continue

                response.raise_for_status()
                data = response.json()
                records = data.get("records", [])

                if not records:
                    break

                all_records.extend(records)
                print(f"    Fetched {len(records)} (total: {len(all_records)})")

                if len(records) < limit:
                    break

                offset += limit
                time.sleep(2)   # gentle rate limiting

            except requests.exceptions.RequestException as e:
                print(f"    ERROR for {commodity}/{district}: {e}")
                break

    if not all_records:
        return pd.DataFrame()

    df = pd.DataFrame(all_records)
    return _normalize(df)


def _normalize(df: pd.DataFrame) -> pd.DataFrame:
    """Map Agmarknet API field names to our schema, handling both casing variants."""
    if df.empty:
        return df

    # Build a rename map for whichever columns are present
    rename = {col: _COL_ALIASES[col] for col in df.columns if col in _COL_ALIASES}
    df = df.rename(columns=rename)

    # Drop rows where the essential fields couldn't be mapped
    required = {"date", "modal_price", "market", "district", "commodity"}
    if not required.issubset(df.columns):
        missing = required - set(df.columns)
        print(f"    Warning: missing columns after normalize: {missing}. Skipping.")
        return pd.DataFrame()

    df["date"] = pd.to_datetime(df["date"], format="%d/%m/%Y", errors="coerce")
    df = df.dropna(subset=["date", "modal_price"])

    for col in ["modal_price", "min_price", "max_price"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df["district"]  = df["district"].astype(str).str.strip().str.title()
    df["commodity"] = df["commodity"].astype(str).str.strip().str.title()
    df["market"]    = df["market"].astype(str).str.strip().str.title()

    keep = ["market", "district", "commodity", "date",
            "modal_price", "min_price", "max_price"]
    return df[[c for c in keep if c in df.columns]]


def main():
    if not API_KEY:
        print("ERROR: DATAGOV_API_KEY not set in .env")
        sys.exit(1)

    print("=" * 60)
    print("FARMULA BULK HISTORICAL DATA FETCH")
    print("=" * 60)
    commodities = [c for c in TARGET_COMMODITIES if c not in _EXCLUDED_COMMODITIES]
    print(f"Target: {len(TARGET_DISTRICTS)} districts × {len(commodities)} commodities")
    print(f"= up to {len(TARGET_DISTRICTS) * len(commodities)} pair-queries")
    print(f"Estimated time: 30–60 min (2s delay between requests)")
    if _EXCLUDED_COMMODITIES:
        excluded = ", ".join(sorted(_EXCLUDED_COMMODITIES))
        print(f"Excluded commodities: {excluded}")
    print()

    summary = []
    total_saved = 0

    for commodity in commodities:
        for district in TARGET_DISTRICTS:
            df = fetch_pair(commodity, district, days_back=730)

            if df.empty:
                summary.append({
                    "commodity": commodity,
                    "district": district,
                    "records_fetched": 0,
                    "records_saved": 0,
                    "status": "no_data",
                })
                continue

            try:
                saved = save_mandi_records_to_db(df)
                total_saved += saved
                summary.append({
                    "commodity": commodity,
                    "district": district,
                    "records_fetched": len(df),
                    "records_saved": saved,
                    "status": "ok",
                })
                print(f"    Saved {saved} new / {len(df)} fetched")
            except Exception as e:
                print(f"    DB save failed: {e}")
                summary.append({
                    "commodity": commodity,
                    "district": district,
                    "records_fetched": len(df),
                    "records_saved": 0,
                    "status": "db_error",
                    "error": str(e)[:200],
                })

    # Write summary
    summary_df = pd.DataFrame(summary)
    out_path = Path("data/historical_fetch_summary.csv")
    out_path.parent.mkdir(exist_ok=True)
    summary_df.to_csv(out_path, index=False)

    print("\n" + "=" * 60)
    print("FETCH COMPLETE")
    print("=" * 60)
    print(f"Total new records saved: {total_saved:,}")
    ok = summary_df[summary_df["status"] == "ok"]
    print(f"Pairs with data:  {len(ok)} / {len(summary_df)}")
    print(f"Summary written to: {out_path}")


if __name__ == "__main__":
    main()
