"""
Analyzes mandi_prices in NeonDB and identifies which commodity-district
pairs have enough data to train models on. Outputs ranked list.
"""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent / "src"))

from db_utils import engine
from maharashtra_coverage import (
    MIN_RECORDS_FOR_TRAINING,
    EXISTING_TRAINED_PAIRS,
    TARGET_DISTRICTS,
    TARGET_COMMODITIES,
)
from sqlalchemy import text
import pandas as pd


def main():
    print("Analyzing commodity-district pair coverage in NeonDB...")

    # Build deduplicated IN-lists containing both Title case and lowercase
    # so the query matches however data landed in the DB
    districts_set  = sorted(set(TARGET_DISTRICTS + [d.lower() for d in TARGET_DISTRICTS]))
    commodities_set = sorted(set(TARGET_COMMODITIES + [c.lower() for c in TARGET_COMMODITIES]))

    # SQLAlchemy text() doesn't support list binding for IN clauses cleanly,
    # so we build the tuple literals explicitly from our own safe constants.
    districts_sql   = str(tuple(districts_set))   if len(districts_set)  > 1 else f"('{districts_set[0]}')"
    commodities_sql  = str(tuple(commodities_set)) if len(commodities_set) > 1 else f"('{commodities_set[0]}')"

    query = f"""
    SELECT
        LOWER(commodity)                        AS commodity,
        LOWER(district)                         AS district,
        COUNT(*)                                AS record_count,
        MIN(date)                               AS earliest_date,
        MAX(date)                               AS latest_date,
        (MAX(date) - MIN(date))                 AS date_span_days,
        COUNT(DISTINCT market)                  AS market_count
    FROM mandi_prices
    WHERE district   IN {districts_sql}
      AND commodity  IN {commodities_sql}
    GROUP BY LOWER(commodity), LOWER(district)
    ORDER BY record_count DESC
    """

    with engine.connect() as conn:
        result = conn.execute(text(query))
        rows = result.fetchall()
        df = pd.DataFrame(rows, columns=list(result.keys()))

    if df.empty:
        print("\nNo data found. Run scripts/fetch_historical_data.py first.")
        return

    df["trainable"] = df["record_count"] >= MIN_RECORDS_FOR_TRAINING
    df["already_trained"] = df.apply(
        lambda r: (r["commodity"], r["district"]) in EXISTING_TRAINED_PAIRS,
        axis=1,
    )
    df["should_train"] = df["trainable"] & ~df["already_trained"]

    out_path = Path("data/pair_coverage_analysis.csv")
    out_path.parent.mkdir(exist_ok=True)
    df.to_csv(out_path, index=False)

    print(f"\n=== PAIR COVERAGE ANALYSIS ===\n")
    print(f"Total pairs with any data : {len(df)}")
    print(f"Already trained           : {df['already_trained'].sum()}")
    print(f"Trainable (>={MIN_RECORDS_FOR_TRAINING} records): {df['trainable'].sum()}")
    print(f"NEW pairs to train        : {df['should_train'].sum()}\n")

    if df["should_train"].any():
        print("=== TOP 20 NEW PAIRS TO TRAIN ===")
        top = df[df["should_train"]].head(20)
        print(
            top[["commodity", "district", "record_count",
                 "date_span_days", "market_count"]].to_string(index=False)
        )
    else:
        print("No new trainable pairs found yet.")
        print("All pairs with data (including sub-threshold):")
        print(df[["commodity", "district", "record_count"]].head(30).to_string(index=False))

    print(f"\nFull analysis saved to: {out_path}")


if __name__ == "__main__":
    main()
