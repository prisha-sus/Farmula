"""
Ingests bulk Agmarknet/data.gov.in CSV exports into mandi_prices.
Filters to Maharashtra + target districts/commodities and de-dups via DB upsert.

Usage:
  python scripts/ingest_bulk_csv.py --input-dir data/bulk_csv
"""
import argparse
import sys
import zipfile
from pathlib import Path

import pandas as pd

# Make src importable
sys.path.append(str(Path(__file__).parent.parent / "src"))

from db_utils import save_mandi_records_to_db
from maharashtra_coverage import TARGET_DISTRICTS, TARGET_COMMODITIES


_ALLOWED_DISTRICTS = {d.strip().title() for d in TARGET_DISTRICTS}
_ALLOWED_COMMODITIES = {c.strip().title() for c in TARGET_COMMODITIES}


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    # Normalize column names to lowercase with underscores
    df = df.rename(columns={c: c.strip().lower().replace(" ", "_") for c in df.columns})

    aliases = {
        "arrival_date": "date",
        "arrivaldate": "date",
        "date": "date",
        "market": "market",
        "market_name": "market",
        "mandi_name": "market",
        "district": "district",
        "commodity": "commodity",
        "modal_price": "modal_price",
        "modalprice": "modal_price",
        "min_price": "min_price",
        "minprice": "min_price",
        "max_price": "max_price",
        "maxprice": "max_price",
        "state": "state",
    }
    rename = {c: aliases[c] for c in df.columns if c in aliases}
    return df.rename(columns=rename)


def _normalize_chunk(df: pd.DataFrame, state_filter: str) -> pd.DataFrame:
    df = _normalize_columns(df)

    required = {"date", "market", "district", "commodity", "modal_price"}
    if not required.issubset(df.columns):
        return pd.DataFrame()

    if "state" in df.columns:
        df["state"] = df["state"].astype(str).str.strip().str.title()
        df = df[df["state"] == state_filter]

    df["district"] = df["district"].astype(str).str.strip().str.title()
    df["commodity"] = df["commodity"].astype(str).str.strip().str.title()
    df["market"] = df["market"].astype(str).str.strip().str.title()

    df = df[df["district"].isin(_ALLOWED_DISTRICTS)]
    df = df[df["commodity"].isin(_ALLOWED_COMMODITIES)]

    df["date"] = pd.to_datetime(df["date"], errors="coerce", dayfirst=True)
    df = df.dropna(subset=["date", "modal_price"])

    for col in ("modal_price", "min_price", "max_price"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    keep = ["market", "district", "commodity", "date", "modal_price", "min_price", "max_price"]
    return df[[c for c in keep if c in df.columns]]


def _iter_csv_sources(input_dir: Path) -> list[Path]:
    files = []
    for ext in ("*.csv", "*.CSV", "*.zip", "*.ZIP"):
        files.extend(input_dir.rglob(ext))
    return sorted(set(files))


def _read_csv_chunks(path: Path, chunksize: int = 50000):
    if path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path) as zf:
            for name in zf.namelist():
                if not name.lower().endswith(".csv"):
                    continue
                with zf.open(name) as f:
                    for chunk in pd.read_csv(f, chunksize=chunksize, dtype=str):
                        yield chunk
    else:
        for chunk in pd.read_csv(path, chunksize=chunksize, dtype=str):
            yield chunk


def main():
    parser = argparse.ArgumentParser(description="Bulk ingest Agmarknet CSV exports.")
    parser.add_argument("--input-dir", required=True, help="Folder with CSV/ZIP files")
    parser.add_argument("--state", default="Maharashtra", help="State name filter")
    parser.add_argument("--chunksize", type=int, default=50000, help="CSV read chunksize")
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    if not input_dir.exists():
        print(f"Input directory not found: {input_dir}")
        sys.exit(1)

    sources = _iter_csv_sources(input_dir)
    if not sources:
        print("No CSV/ZIP files found in input directory.")
        sys.exit(1)

    summary = []
    total_saved = 0

    for path in sources:
        rows_in = 0
        rows_kept = 0
        saved_total = 0

        for chunk in _read_csv_chunks(path, chunksize=args.chunksize):
            rows_in += len(chunk)
            cleaned = _normalize_chunk(chunk, args.state)
            if cleaned.empty:
                continue
            rows_kept += len(cleaned)
            saved = save_mandi_records_to_db(cleaned)
            saved_total += saved
            total_saved += saved

        summary.append({
            "file": str(path),
            "rows_read": rows_in,
            "rows_filtered": rows_kept,
            "rows_saved": saved_total,
        })
        print(f"Processed {path.name}: read={rows_in}, kept={rows_kept}, saved={saved_total}")

    summary_df = pd.DataFrame(summary)
    out_path = Path("data/bulk_ingest_summary.csv")
    out_path.parent.mkdir(exist_ok=True)
    summary_df.to_csv(out_path, index=False)

    print("\nBulk ingest complete")
    print(f"Total new rows saved: {total_saved}")
    print(f"Summary written to: {out_path}")


if __name__ == "__main__":
    main()
