"""
live_prices.py
Serves latest price data from local Agmarknet CSV exports.

Prisha's data_pipeline.py handles live Agmarknet API fetches for inference.
This module reads the static training CSVs so the Streamlit UI can show
current market prices and data-freshness indicators without hitting the API.
"""

import os
import pandas as pd

_DATA_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "data"))

# Maps commodity name (lowercase) -> CSV filename in data/
_CSV_MAP = {
    "onion":    "onion_nashik.csv",
    "potato":   "potato_pune.csv",
    "soyabean": "aamrawati_soyabean.csv",
}

_COL_RENAME = {
    "State":        "state",
    "District":     "district",
    "Market":       "market",
    "Commodity":    "commodity",
    "Variety":      "variety",
    "Grade":        "grade",
    "Arrival_Date": "date",
    "Min_Price":    "min_price",
    "Max_Price":    "max_price",
    "Modal_Price":  "modal_price",
}


def get_live_df() -> pd.DataFrame:
    """Loads all commodity CSVs and returns a combined, standardised DataFrame."""
    frames = []
    for _, filename in _CSV_MAP.items():
        path = os.path.join(_DATA_DIR, filename)
        if not os.path.exists(path):
            continue
        df = pd.read_csv(path)
        df = df.rename(columns={k: v for k, v in _COL_RENAME.items() if k in df.columns})
        df["date"] = pd.to_datetime(df["date"], dayfirst=True, errors="coerce")
        for col in ("modal_price", "min_price", "max_price"):
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        df = df.dropna(subset=["date", "modal_price"])
        frames.append(df)

    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def get_latest_prices(district: str, commodity: str) -> pd.DataFrame:
    """
    Returns the most recent modal price per market for a commodity/district.

    The district filter is lenient (prefix-match, 4 chars) to handle Agmarknet
    spelling variants such as 'Amarawati' vs 'Amravati'.

    Returns DataFrame with columns: market, modal_price, date
    """
    df = get_live_df()
    if df.empty:
        return pd.DataFrame()

    # Primary filter: commodity (each CSV covers one district, so this is sufficient)
    mask = df["commodity"].str.lower().str.contains(commodity.lower(), na=False)
    df_c = df[mask].copy()
    if df_c.empty:
        return pd.DataFrame()

    # Optional district refinement using first-4-chars prefix to tolerate spelling drift
    if district:
        prefix = district.lower().replace(" ", "")[:4]   # "amravati" -> "amra", "nashik" -> "nash"
        mask_d = (
            df_c["district"]
            .str.lower()
            .str.replace(" ", "", regex=False)
            .str.startswith(prefix)
        )
        if mask_d.any():
            df_c = df_c[mask_d]

    # Latest date only, then average across varieties for the same market
    latest_date = df_c["date"].max()
    df_latest = df_c[df_c["date"] == latest_date]
    result = (
        df_latest
        .groupby("market")["modal_price"]
        .mean()
        .reset_index()
        .assign(date=latest_date)
    )
    return result[result["modal_price"] > 0].reset_index(drop=True)


def get_data_freshness() -> dict:
    """Returns freshness info: latest date, days since update, record count."""
    df = get_live_df()
    if df.empty:
        return {"has_data": False}
    latest = df["date"].max()
    days_ago = (pd.Timestamp.today() - latest).days
    return {
        "has_data":     True,
        "latest_date":  latest.strftime("%d %b %Y"),
        "days_ago":     days_ago,
        "record_count": len(df),
    }
