# -*- coding: utf-8 -*-
"""
Trains LightGBM quantile models for the top commodity-district pairs
identified by the coverage analysis. Reads CSVs from data/, trains
12 models per pair (4 horizons × 3 quantiles), saves to models/ folder.

Skips pairs that already have trained models.
Reuses engineer_features() and train_horizon() from train_commodity.py
to guarantee model files are compatible with the existing inference pipeline.

Run: python scripts/bulk_train.py
"""
import sys
import json
import time
import traceback
from pathlib import Path

# Make scripts/ importable so we can import from train_commodity.py
sys.path.insert(0, str(Path(__file__).parent))
# Make src/ importable
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import numpy as np
import pandas as pd
from train_commodity import engineer_features, train_horizon
from maharashtra_coverage import EXISTING_TRAINED_PAIRS
from weather_fetcher import fetch_weather_history, DISTRICT_COORDS

# ── Configuration ─────────────────────────────────────────────────────────────
MIN_RECORDS  = 3000      # only train pairs with this many records in the CSV
HORIZONS     = [1, 7, 15, 30]
QUANTILES    = [0.1, 0.5, 0.9]
MAX_PAIRS    = 30        # safety cap — top N by record count

# Suffix convention matches train_commodity.py exactly
HORIZON_SUFFIX = {1: "_ver2", 7: "", 15: "", 30: "_smoothed"}

# ── District → CSV filename mapping ───────────────────────────────────────────
# The analyze script uses canonical names; the actual files on disk may differ.
CSV_FILENAME_MAP = {
    "amravati":   "Amarawati.csv",
    "aurangabad": "Chattrapati Sambhajinagar.csv",
}

# ── District → coordinates (for weather fetch) ────────────────────────────────
EXTRA_COORDS = {
    "nagpur":     {"lat": 21.15, "lon": 79.08},
    "jalgaon":    {"lat": 21.00, "lon": 75.56},
    "aurangabad": {"lat": 19.88, "lon": 75.32},
    "satara":     {"lat": 17.68, "lon": 74.00},
    "sangli":     {"lat": 16.86, "lon": 74.57},
    "kolhapur":   {"lat": 16.70, "lon": 74.24},
    "solapur":    {"lat": 17.68, "lon": 75.90},
    "yavatmal":   {"lat": 20.93, "lon": 77.75},
}
ALL_COORDS = {**DISTRICT_COORDS, **EXTRA_COORDS}

# ── Helpers ───────────────────────────────────────────────────────────────────

def models_exist(commodity_key: str) -> bool:
    """Return True if all 12 model files already exist for this commodity."""
    for h in HORIZONS:
        suffix = HORIZON_SUFFIX[h]
        for q in ["p10", "p50", "p90"]:
            fname = f"lightgbm_{commodity_key}_{h}day_{q}{suffix}.txt"
            if not (Path("models") / commodity_key / fname).exists():
                return False
    return True


def find_csv(district: str) -> Path | None:
    """Locate the district CSV file, accounting for filename variants."""
    key = district.lower()
    if key in CSV_FILENAME_MAP:
        p = Path("data") / CSV_FILENAME_MAP[key]
    else:
        p = Path("data") / f"{district.title()}.csv"
    return p if p.exists() else None


def load_commodity_from_district_csv(district: str, commodity: str) -> pd.DataFrame:
    """
    Load one commodity's rows from a district-level Agmarknet CSV.
    Normalises column names to match train_commodity.py's load_and_clean()
    so engineer_features() receives exactly the columns it expects.
    """
    csv_path = find_csv(district)
    if csv_path is None:
        raise FileNotFoundError(f"No CSV found for district: {district}")

    try:
        df = pd.read_csv(csv_path, encoding="utf-8", low_memory=False)
    except UnicodeDecodeError:
        df = pd.read_csv(csv_path, encoding="latin-1", low_memory=False)

    # Same column map as train_commodity.py → produces arrival_date, mandi_name, etc.
    col_map = {
        "Arrival_Date": "arrival_date",
        "District":     "district",
        "Market":       "mandi_name",
        "Commodity":    "commodity",
        "Variety":      "variety",
        "Grade":        "grade",
        "State":        "state",
        "Min Price":    "min_price",   "Min_Price":   "min_price",
        "Max Price":    "max_price",   "Max_Price":   "max_price",
        "Modal Price":  "modal_price", "Modal_Price": "modal_price",
    }
    df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})

    # Lowercase normalised column names (some exports use lowercase already)
    lower_map = {
        "arrival_date": "arrival_date",
        "district":     "district",
        "market":       "mandi_name",
        "commodity":    "commodity",
        "variety":      "variety",
        "grade":        "grade",
        "state":        "state",
        "min_price":    "min_price",
        "max_price":    "max_price",
        "modal_price":  "modal_price",
        "modal_pri":    "modal_price",
    }
    df = df.rename(columns={k: v for k, v in lower_map.items() if k in df.columns})

    if "arrival_date" not in df.columns:
        raise ValueError(f"Could not find date column in {csv_path.name}")

    df["arrival_date"] = pd.to_datetime(df["arrival_date"], dayfirst=True, errors="coerce")
    df = df.dropna(subset=["arrival_date"])

    for col in ("min_price", "max_price", "modal_price"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    for col in ("mandi_name", "variety", "district"):
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip().str.title()

    if "state" not in df.columns:
        df["state"] = "Maharashtra"

    df = df.dropna(subset=["modal_price"])
    df = df[df["modal_price"] > 0]

    # Filter to the requested commodity (case-insensitive)
    mask = df["commodity"].str.lower() == commodity.lower()
    df_commodity = df[mask].copy().sort_values("arrival_date").reset_index(drop=True)

    print(f"    CSV rows for {commodity}: {len(df_commodity):,} "
          f"({df_commodity['arrival_date'].min().date() if len(df_commodity) else 'N/A'} → "
          f"{df_commodity['arrival_date'].max().date() if len(df_commodity) else 'N/A'})")
    return df_commodity


def train_pair(commodity: str, district: str, df_commodity: pd.DataFrame) -> dict:
    """Train all 12 models for one commodity-district pair."""
    commodity_key = commodity.lower().replace(" ", "_")
    print(f"\n  Training {commodity} / {district} "
          f"({len(df_commodity):,} records) → models/{commodity_key}/")

    # Fetch weather (rename 'date' → 'arrival_date' for merge in engineer_features)
    coords = ALL_COORDS.get(district.lower())
    weather_df = pd.DataFrame()
    if coords:
        try:
            start = df_commodity["arrival_date"].min().strftime("%Y-%m-%d")
            end   = df_commodity["arrival_date"].max().strftime("%Y-%m-%d")
            raw_weather = fetch_weather_history(coords["lat"], coords["lon"], start, end)
            if not raw_weather.empty:
                weather_df = raw_weather.rename(columns={"date": "arrival_date"})
                print(f"    Weather: {len(weather_df)} days fetched")
        except Exception as e:
            print(f"    Weather fetch failed: {e} — training without weather")
    else:
        print(f"    No coords for {district} — training without weather")

    # Feature engineering (exact same function as train_commodity.py)
    df_feats = engineer_features(df_commodity, weather_df)
    print(f"    Feature rows: {len(df_feats):,}")

    model_dir = str(Path("models") / commodity_key)
    Path(model_dir).mkdir(parents=True, exist_ok=True)

    metrics = []
    for horizon in HORIZONS:
        print(f"\n    [Horizon {horizon}d]")
        try:
            m, y_val, p10, p90 = train_horizon(df_feats, commodity_key, horizon, model_dir)
            coverage = ((y_val.values >= p10) & (y_val.values <= p90)).mean() * 100
            metrics.append({
                "horizon": f"{horizon}d",
                "mae":      round(m["mae"], 2),
                "mape":     round(m["mape"], 2),
                "coverage": round(coverage, 1),
            })
            print(f"    [{horizon}d p50] MAE=₹{m['mae']:.0f}  "
                  f"MAPE={m['mape']:.1f}%  Coverage={coverage:.1f}%")
        except Exception as e:
            print(f"    [{horizon}d] ERROR: {e}")
            traceback.print_exc()

    return {"commodity": commodity, "commodity_key": commodity_key,
            "district": district, "metrics": metrics}


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 70)
    print("FARMULA BULK MODEL TRAINING")
    print("=" * 70)

    plan_path = Path("data/analysis/trainable_pairs.csv")
    if not plan_path.exists():
        print("ERROR: Run scripts/analyze_csv_datasets.py first")
        return

    plan_df = pd.read_csv(plan_path)
    plan_df = plan_df[plan_df["records"] >= MIN_RECORDS].copy()
    plan_df = plan_df.sort_values("records", ascending=False).head(MAX_PAIRS)

    print(f"\nTraining plan: {len(plan_df)} pairs "
          f"(>={MIN_RECORDS:,} records, top {MAX_PAIRS})")
    print(plan_df[["commodity", "district", "records"]].to_string(index=False))

    all_results = []
    skipped     = []
    start_time  = time.time()
    district_cache: dict[str, pd.DataFrame] = {}

    for _, row in plan_df.iterrows():
        commodity     = str(row["commodity"]).strip()
        district      = str(row["district"]).strip()
        commodity_key = commodity.lower().replace(" ", "_")

        # Skip if models already exist
        if models_exist(commodity_key):
            print(f"\n  SKIP {commodity}/{district} — models already exist")
            skipped.append(f"{commodity}/{district}")
            continue

        # Load district CSV (cached per district)
        dist_key = district.lower()
        try:
            df_commodity = load_commodity_from_district_csv(district, commodity)
        except FileNotFoundError as e:
            print(f"\n  SKIP {commodity}/{district} — {e}")
            continue

        if len(df_commodity) < MIN_RECORDS:
            print(f"\n  SKIP {commodity}/{district} — "
                  f"only {len(df_commodity)} rows after filtering")
            continue

        try:
            result = train_pair(commodity, district, df_commodity)
            all_results.append(result)
        except Exception as e:
            print(f"\n  ERROR training {commodity}/{district}:")
            traceback.print_exc()
            all_results.append({
                "commodity": commodity, "district": district, "error": str(e)
            })

    # ── Summary ───────────────────────────────────────────────────────────────
    elapsed = time.time() - start_time
    print("\n" + "=" * 70)
    print("TRAINING COMPLETE")
    print("=" * 70)
    trained = [r for r in all_results if "metrics" in r]
    errors  = [r for r in all_results if "error"   in r]
    print(f"Elapsed : {elapsed/60:.1f} min")
    print(f"Trained : {len(trained)}")
    print(f"Errors  : {len(errors)}")
    print(f"Skipped : {len(skipped)}")

    print("\n── Final metrics (p50 MAE) ──")
    print(f"{'Commodity':<22} {'District':<14} "
          f"{'1d':>7} {'7d':>7} {'15d':>7} {'30d':>7}")
    print("-" * 60)
    for r in trained:
        m = {m["horizon"]: m["mae"] for m in r["metrics"]}
        print(f"{r['commodity']:<22} {r['district']:<14} "
              f"{m.get('1d','--'):>7} {m.get('7d','--'):>7} "
              f"{m.get('15d','--'):>7} {m.get('30d','--'):>7}")

    results_path = Path("data/analysis/training_results.json")
    with open(results_path, "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"\nResults → {results_path}")

    model_files = list(Path("models").rglob("*.txt"))
    print(f"\nTotal model files on disk: {len(model_files)}")
    for d in sorted(set(f.parent.name for f in model_files)):
        count = sum(1 for f in model_files if f.parent.name == d)
        print(f"  models/{d}/  — {count} files")


if __name__ == "__main__":
    main()
