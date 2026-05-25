# -*- coding: utf-8 -*-
"""
seed_from_csv.py
Populates latest_mandi_features from local Agmarknet CSV files + Open-Meteo weather.

Run whenever the database is empty or stale:
    python scripts/seed_from_csv.py

Produces exactly one row per mandi (the most recent date in each CSV),
with all 50 features that the trained models expect.
"""

import os
import sys
import numpy as np
import pandas as pd
import requests
import holidays

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.db_utils import engine, save_dataframe_to_db
from src.weather_fetcher import fetch_weather_history

# ---------------------------------------------------------------------------
# Config: which CSV to load and which coordinates to use for weather
# ---------------------------------------------------------------------------
COMMODITY_CONFIG = {
    "onion":    {"file": "data/onion_nashik.csv",        "lat": 19.99, "lon": 73.79},
    "potato":   {"file": "data/potato_pune.csv",         "lat": 18.52, "lon": 73.85},
    "soyabean": {"file": "data/aamrawati_soyabean.csv",  "lat": 20.93, "lon": 77.75},
}

_COL_MAP = {
    "Arrival_Date": "arrival_date",   "Market":       "mandi_name",
    "District":     "district",       "State":        "state",
    "Variety":      "variety",        "Commodity":    "commodity",
    "Grade":        "grade",
    "Min_Price":    "min_price",      "Min Price":    "min_price",
    "Max_Price":    "max_price",      "Max Price":    "max_price",
    "Modal_Price":  "modal_price",    "Modal Price":  "modal_price",
}


def _load_csv(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    df = df.rename(columns={k: v for k, v in _COL_MAP.items() if k in df.columns})
    df["arrival_date"] = pd.to_datetime(df["arrival_date"], dayfirst=True, errors="coerce")
    for col in ("min_price", "max_price", "modal_price"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    for col in ("mandi_name", "variety", "district"):
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip().str.title()
    if "state" not in df.columns:
        df["state"] = "Maharashtra"
    return (df.dropna(subset=["arrival_date", "modal_price"])
              .sort_values("arrival_date")
              .reset_index(drop=True))


def _engineer_and_take_latest(price_df: pd.DataFrame,
                               weather_df: pd.DataFrame) -> pd.DataFrame:
    """
    Mirrors train_commodity.engineer_features() exactly, then returns only
    the most recent row per mandi — what the inference engine needs.
    """
    years = range(price_df["arrival_date"].dt.year.min(),
                  price_df["arrival_date"].dt.year.max() + 2)
    india_hols = holidays.India(years=list(years))

    latest_rows = []

    for mandi, grp in price_df.groupby("mandi_name"):
        g = grp.copy().sort_values("arrival_date").reset_index(drop=True)

        # -- Merge weather --------------------------------------------------
        if not weather_df.empty:
            g = pd.merge(g, weather_df, on="arrival_date", how="left")
            for col in ("temp_max", "temp_min", "precipitation", "evapotranspiration"):
                g[col] = g[col].ffill().bfill().fillna(0.0)
            g["temp_mean"] = (g["temp_max"] + g["temp_min"]) / 2.0
            g["rainfall"]  = g["precipitation"]
        else:
            g["temp_mean"] = 0.0
            g["rainfall"]  = 0.0
            g["precipitation"]     = 0.0
            g["evapotranspiration"] = 0.0

        g["is_real_trade"] = (g["modal_price"] > 0).astype(int)

        # -- Price lags -------------------------------------------------------
        for lag in (1, 2, 3, 7, 8, 9, 14, 15, 16, 17, 30, 31, 32, 45):
            g[f"price_lag_{lag}"] = g["modal_price"].shift(lag)

        g["price_expanding_mean"] = g["price_lag_1"].expanding().mean()
        g["price_roll_mean_7"]    = g["price_lag_1"].rolling(7).mean()
        g["price_roll_std_7"]     = g["price_lag_1"].rolling(7).std()
        g["price_roll_mean_30"]   = g["price_lag_1"].rolling(30).mean()

        # -- Prisha's weather lags (inference pipeline expects these names) ---
        for lag in (1, 7, 15, 30):
            g[f"temp_mean_lag{lag}"] = g["temp_mean"].shift(lag)
            g[f"rainfall_lag{lag}"]  = g["rainfall"].shift(lag)

        g["rainfall_7d_sum"]  = g["rainfall_lag1"].rolling(7).sum()
        g["rainfall_30d_sum"] = g["rainfall_lag1"].rolling(30).sum()
        g["temp_7d_avg"]      = g["temp_mean_lag1"].rolling(7).mean()

        # -- New weather features (added in our training round) ---------------
        g["temp_lag1"]        = g["temp_mean"].shift(1)
        g["temp_lag7"]        = g["temp_mean"].shift(7)
        g["precip_lag1"]      = g["precipitation"].shift(1)
        g["precip_roll7"]     = g["precipitation"].rolling(7).sum()
        g["precip_roll30"]    = g["precipitation"].rolling(30).sum()
        g["evapotrans_lag1"]  = g["evapotranspiration"].shift(1)
        # temp_mean (no lag) is already set above

        # -- Date / calendar features ----------------------------------------
        g["day_of_year"] = g["arrival_date"].dt.dayofyear
        g["day_of_week"] = g["arrival_date"].dt.dayofweek
        g["month"]       = g["arrival_date"].dt.month
        g["is_weekend"]  = g["day_of_week"].isin([5, 6]).astype(int)
        g["is_holiday"]  = g["arrival_date"].dt.date.apply(
            lambda d: int(d in india_hols)
        )

        doy = g["day_of_year"]
        g["sin_365_1"] = np.sin(2 * np.pi * doy / 365.25)
        g["cos_365_1"] = np.cos(2 * np.pi * doy / 365.25)
        g["sin_365_2"] = np.sin(4 * np.pi * doy / 365.25)
        g["cos_365_2"] = np.cos(4 * np.pi * doy / 365.25)

        # Take the very last row — the most recent known data point per mandi
        latest_rows.append(g.iloc[[-1]])

    if not latest_rows:
        return pd.DataFrame()
    return pd.concat(latest_rows).reset_index(drop=True)


def main():
    all_frames = []

    for commodity, cfg in COMMODITY_CONFIG.items():
        print(f"\n[{commodity}]")
        csv_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            cfg["file"]
        )

        price_df = _load_csv(csv_path)
        print(f"  Price rows   : {len(price_df):,}")
        print(f"  Date range   : {price_df['arrival_date'].min().date()} "
              f"to {price_df['arrival_date'].max().date()}")

        start = price_df["arrival_date"].min().strftime("%Y-%m-%d")
        end   = price_df["arrival_date"].max().strftime("%Y-%m-%d")
        print(f"  Fetching weather ({cfg['lat']}, {cfg['lon']}) ...")
        weather_df = fetch_weather_history(cfg["lat"], cfg["lon"], start, end)
        if not weather_df.empty:
            weather_df = weather_df.rename(columns={"date": "arrival_date"})
            print(f"  Weather rows : {len(weather_df)}")
        else:
            print("  Weather fetch failed — using zeros")

        features_df = _engineer_and_take_latest(price_df, weather_df)
        features_df["commodity"] = commodity
        print(f"  Feature rows : {len(features_df)} (1 per mandi)")
        all_frames.append(features_df)

    combined = pd.concat(all_frames, ignore_index=True)
    print(f"\nTotal rows across all commodities: {len(combined)}")
    print(f"Columns ({len(combined.columns)}): {list(combined.columns)}")

    save_dataframe_to_db(combined, "latest_mandi_features", if_exists="replace")
    print("\nDone — latest_mandi_features seeded in NeonDB.")


if __name__ == "__main__":
    main()
