# -*- coding: utf-8 -*-
"""
data_fetcher.py
Fetches today's Maharashtra mandi price data from data.gov.in and returns
a DataFrame shaped for save_mandi_records_to_db():
    market, district, commodity, date, modal_price, min_price, max_price

Kept separate from data_pipeline.py (which owns inference feature engineering)
to avoid coupling the daily ingestion job to the prediction pipeline.
"""

import os
import time
import requests
import pandas as pd
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

API_KEY     = os.getenv("DATAGOV_API_KEY")
RESOURCE_ID = "35985678-0d79-46b4-9ed6-6f13308a1d24"

# Commodities we have models for — fetch only these to stay within API rate limits
COMMODITIES = ["Onion", "Potato", "Soyabean"]

_COL_MAP = {
    "Arrival_Date": "date",
    "Market":       "market",
    "District":     "district",
    "Commodity":    "commodity",
    "Modal_Price":  "modal_price",
    "Min_Price":    "min_price",
    "Max_Price":    "max_price",
}


def _fetch_one(commodity: str, days_back: int = 30,
               max_records: int = 5000) -> pd.DataFrame:
    """
    Fetches data.gov.in records for one commodity across all Maharashtra.

    days_back   — how far back to keep records after fetching.
    max_records — hard cap on total records fetched per commodity; prevents
                  runaway pagination for high-volume commodities like Potato.
    """
    base_url = f"https://api.data.gov.in/resource/{RESOURCE_ID}"
    all_records = []
    offset = 0
    limit  = 100

    while len(all_records) < max_records:
        params = {
            "api-key":            API_KEY,
            "format":             "json",
            "limit":              limit,
            "offset":             offset,
            "filters[state]":     "Maharashtra",
            "filters[commodity]": commodity,
        }
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
            )
        }

        try:
            resp = requests.get(base_url, params=params, headers=headers, timeout=60)
            if resp.status_code == 429:
                print(f"  Rate limit hit for {commodity}. Sleeping 10s...")
                time.sleep(10)
                continue
            resp.raise_for_status()
            records = resp.json().get("records", [])
            all_records.extend(records)
            if len(records) < limit:
                break
            offset += limit
            time.sleep(2)   # stay polite to the API
        except requests.exceptions.RequestException as exc:
            print(f"  API error for {commodity} at offset {offset}: {exc}")
            break   # return whatever was collected so far

    if not all_records:
        return pd.DataFrame()

    df = pd.DataFrame(all_records)
    valid = {k: v for k, v in _COL_MAP.items() if k in df.columns}
    df = df[list(valid.keys())].rename(columns=valid)

    df["date"]        = pd.to_datetime(df["date"], format="%d/%m/%Y", errors="coerce")
    df["modal_price"] = pd.to_numeric(df["modal_price"], errors="coerce")
    df["min_price"]   = pd.to_numeric(df["min_price"],   errors="coerce")
    df["max_price"]   = pd.to_numeric(df["max_price"],   errors="coerce")
    df["market"]      = df["market"].str.strip().str.title()

    # Keep only recent records
    cutoff = pd.Timestamp(datetime.today().date() - timedelta(days=days_back))
    df = df[df["date"] >= cutoff].dropna(subset=["date", "modal_price"])
    return df


def fetch_maharashtra_daily(days_back: int = 30) -> pd.DataFrame:
    """
    Fetches recent price data for all tracked commodities across Maharashtra.
    Defaults to 30 days back because data.gov.in Agmarknet exports are often
    7-14 days delayed; ON CONFLICT DO NOTHING in the DB upsert handles duplicates.
    Returns a DataFrame ready for save_mandi_records_to_db().
    """
    if not API_KEY:
        print("DATAGOV_API_KEY not set — skipping API fetch.")
        return pd.DataFrame()

    frames = []
    for commodity in COMMODITIES:
        print(f"  Fetching {commodity}...")
        df = _fetch_one(commodity, days_back=days_back)
        if not df.empty:
            frames.append(df)
            print(f"  {len(df)} records for {commodity}")

    if not frames:
        return pd.DataFrame()

    combined = pd.concat(frames, ignore_index=True)

    # Ensure all required columns are present
    for col in ("district", "commodity"):
        if col not in combined.columns:
            combined[col] = "Unknown"

    return combined[
        ["market", "district", "commodity", "date",
         "modal_price", "min_price", "max_price"]
    ]
