# -*- coding: utf-8 -*-
"""
Analyzes all district CSV files in data/ folder.
Identifies trainable commodity-district pairs and produces
a ranked training plan for model development.
"""
import sys
import pandas as pd
import json
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent / "src"))
from maharashtra_coverage import (
    MIN_RECORDS_FOR_TRAINING,
    EXISTING_TRAINED_PAIRS,
    TARGET_COMMODITIES,
)

DATA_DIR = Path("data")
REPORT_DIR = Path("data/analysis")
REPORT_DIR.mkdir(exist_ok=True)

# These are the commodity names as they appear in Agmarknet exports
# Some have different spellings than our TARGET_COMMODITIES list
# We normalize common variations
COMMODITY_ALIASES = {
    "arhar (tur)": "tur",
    "tur": "tur",
    "arhar": "tur",
    "gram": "gram",
    "bengal gram(gram)(whole)": "gram",
    "coriander(leaves)": "coriander",
    "methi(leaves)": "methi",
    "sesamum(gingelly)oil seeds": "sesamum",
    "sesamum": "sesamum",
    "bhindi(ladies finger)": "bhindi",
    "chilly capsicum": "capsicum",
    "cucumbar(kheera)": "cucumber",
    "pomegranate": "pomegranate",
    "chikoos(sapota)": "chikoo",
}

# Map CSV filename stems to canonical district names
DISTRICT_NAME_MAP = {
    "amarawati": "Amravati",
    "amravati": "Amravati",
    "chattrapati sambhajinagar": "Aurangabad",
    "aurangabad": "Aurangabad",
}


def normalize_commodity(name: str) -> str:
    """Normalize commodity name to standard form."""
    cleaned = str(name).strip().lower()
    return COMMODITY_ALIASES.get(cleaned, cleaned.title())


def canonical_district(stem: str) -> str:
    """Return canonical district name from CSV filename stem."""
    return DISTRICT_NAME_MAP.get(stem.strip().lower(), stem.strip().title())


def load_csv(filepath: Path) -> pd.DataFrame:
    """Load a district CSV with robust column handling."""
    try:
        df = pd.read_csv(filepath, encoding="utf-8", low_memory=False)
    except UnicodeDecodeError:
        df = pd.read_csv(filepath, encoding="latin-1", low_memory=False)

    # Normalize column names — strip spaces, lowercase
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

    # Map to standard names
    col_map = {
        "arrival_date": "date",
        "commodity": "commodity",
        "commodity_code": "commodity_code",
        "district": "district",
        "grade": "grade",
        "market": "market",
        "max_price": "max_price",
        "min_price": "min_price",
        "modal_price": "modal_price",
        "modal_pri": "modal_price",
        "state": "state",
        "variety": "variety",
    }
    df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})

    # Parse date
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], dayfirst=True, errors="coerce")
        df = df.dropna(subset=["date"])

    # Parse prices
    for col in ["modal_price", "min_price", "max_price"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=["modal_price"])
    return df


def analyze_district_csv(filepath: Path) -> dict:
    """Analyze one district CSV and return pair-level stats."""
    district_name = canonical_district(filepath.stem)
    print(f"\nAnalyzing: {district_name} ({filepath.name})")

    df = load_csv(filepath)
    if df.empty:
        print(f"  EMPTY or unreadable")
        return {"district": district_name, "pairs": [], "total_records": 0}

    print(f"  Loaded {len(df):,} records | "
          f"{df['date'].min().date()} to {df['date'].max().date()}")

    # Normalize commodity names
    df["commodity_normalized"] = df["commodity"].apply(normalize_commodity)

    # Group by commodity
    pairs = []
    for commodity, group in df.groupby("commodity_normalized"):
        records = len(group)
        date_range_days = (group["date"].max() - group["date"].min()).days
        market_count = group["market"].nunique() if "market" in group.columns else 0
        avg_price = group["modal_price"].mean()
        price_std = group["modal_price"].std()

        pair_key = (commodity.lower(), district_name.lower())
        already_trained = pair_key in EXISTING_TRAINED_PAIRS

        trainable = (
            records >= MIN_RECORDS_FOR_TRAINING
            and date_range_days >= 180
        )

        pairs.append({
            "commodity": commodity,
            "district": district_name,
            "records": records,
            "date_range_days": date_range_days,
            "date_start": str(group["date"].min().date()),
            "date_end": str(group["date"].max().date()),
            "market_count": market_count,
            "avg_price": round(avg_price, 2),
            "price_std": round(price_std, 2) if pd.notna(price_std) else 0,
            "trainable": trainable,
            "already_trained": already_trained,
            "should_train": trainable and not already_trained,
            "raw_commodity_names": list(group["commodity"].unique()[:5]),
        })

    pairs.sort(key=lambda x: x["records"], reverse=True)

    trainable_count = sum(1 for p in pairs if p["trainable"])
    print(f"  {len(pairs)} commodities | {trainable_count} trainable")

    for p in pairs[:5]:
        flag = "TRAIN" if p["should_train"] else ("EXISTS" if p["already_trained"] else "skip")
        print(f"    {p['commodity']:<28} {p['records']:>6} records  [{flag}]")

    return {
        "district": district_name,
        "total_records": len(df),
        "total_commodities": len(pairs),
        "trainable_commodities": trainable_count,
        "pairs": pairs,
    }


def main():
    print("=" * 70)
    print("FARMULA -- DISTRICT CSV ANALYSIS")
    print("=" * 70)

    # Find all district CSVs (exclude non-district files)
    skip_files = {
        "historical_fetch_summary.csv",
        "pair_coverage_analysis.csv",
    }
    csv_files = sorted([
        f for f in DATA_DIR.glob("*.csv")
        if f.name not in skip_files
    ])

    print(f"\nFound {len(csv_files)} district CSV files:")
    for f in csv_files:
        print(f"  - {f.name}")

    all_results = []
    all_pairs = []

    for filepath in csv_files:
        result = analyze_district_csv(filepath)
        all_results.append(result)
        all_pairs.extend(result["pairs"])

    # Build master pairs DataFrame
    pairs_df = pd.DataFrame(all_pairs)
    pairs_df = pairs_df.sort_values(
        ["should_train", "records"], ascending=[False, False]
    )

    # Save full analysis
    pairs_df.to_csv(REPORT_DIR / "all_pairs_analysis.csv", index=False)

    # Save trainable pairs only
    trainable_df = pairs_df[pairs_df["should_train"]].copy()
    trainable_df.to_csv(REPORT_DIR / "trainable_pairs.csv", index=False)

    # District-level summary
    district_summary = pd.DataFrame([{
        "district": r["district"],
        "total_records": r["total_records"],
        "total_commodities": r["total_commodities"],
        "trainable_commodities": r["trainable_commodities"],
    } for r in all_results]).sort_values("total_records", ascending=False)
    district_summary.to_csv(REPORT_DIR / "district_summary.csv", index=False)

    # Training plan — top 20 trainable pairs
    training_plan = trainable_df.head(20)[[
        "commodity", "district", "records",
        "date_range_days", "market_count", "avg_price"
    ]]

    # Save training plan as JSON for the training script
    training_plan_list = trainable_df[[
        "commodity", "district", "records"
    ]].to_dict(orient="records")
    (REPORT_DIR / "training_plan.json").write_text(
        json.dumps(training_plan_list, indent=2)
    )

    # Print final summary
    print("\n" + "=" * 70)
    print("ANALYSIS SUMMARY")
    print("=" * 70)

    print("\nDistrict breakdown:")
    print(district_summary.to_string(index=False))

    print(f"\nTotal trainable pairs: {len(trainable_df)}")
    if not trainable_df.empty:
        print("\nTop 20 pairs to train:")
        print(training_plan.to_string(index=False))
    else:
        print("\nNo trainable pairs found (need >= 365 records and >= 180 day span).")
        print("All pairs with any data (top 30 by record count):")
        preview = pairs_df[["commodity", "district", "records",
                             "date_range_days"]].head(30)
        print(preview.to_string(index=False))

    # Print UI mapping
    print("\n" + "=" * 70)
    print("APP UI MAPPING -- District -> Available Commodities")
    print("=" * 70)
    ui_mapping = {}
    for _, row in pairs_df[pairs_df["records"] >= 50].iterrows():
        district = row["district"]
        if district not in ui_mapping:
            ui_mapping[district] = []
        ui_mapping[district].append({
            "commodity": row["commodity"],
            "records": int(row["records"]),
            "has_forecast": bool(row["already_trained"] or row["should_train"]),
        })

    for district, commodities in sorted(ui_mapping.items()):
        print(f"\n{district} ({len(commodities)} commodities):")
        for c in commodities[:8]:
            forecast_tag = "forecast" if c["has_forecast"] else "price only"
            print(f"  {c['commodity']:<30} {c['records']:>6} records  [{forecast_tag}]")

    (REPORT_DIR / "ui_mapping.json").write_text(
        json.dumps(ui_mapping, indent=2)
    )

    print(f"\n\nAll outputs saved to data/analysis/")
    print(f"  all_pairs_analysis.csv  -- every pair found")
    print(f"  trainable_pairs.csv     -- pairs with >={MIN_RECORDS_FOR_TRAINING} records")
    print(f"  district_summary.csv    -- per-district totals")
    print(f"  training_plan.json      -- ordered training queue")
    print(f"  ui_mapping.json         -- what the app UI will show")


if __name__ == "__main__":
    main()
