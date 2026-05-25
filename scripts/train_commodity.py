# -*- coding: utf-8 -*-
#!/usr/bin/env python3
"""
train_commodity.py
Train LightGBM quantile price-forecast models for a commodity.

Usage:
    python scripts/train_commodity.py --commodity onion    --file data/onion_nashik.csv    --district nashik
    python scripts/train_commodity.py --commodity soyabean --file data/aamrawati_soyabean.csv --district amravati

Produces 12 model files per commodity (4 horizons x 3 quantiles) in models/{commodity}/.
Filename convention matches inference.py exactly:
    1-day  -> lightgbm_{commodity}_1day_{q}_ver2.txt
    7-day  -> lightgbm_{commodity}_7day_{q}.txt
    15-day -> lightgbm_{commodity}_15day_{q}.txt
    30-day -> lightgbm_{commodity}_30day_{q}_smoothed.txt
"""

import os
import sys
import argparse
import warnings
import numpy as np
import pandas as pd
import lightgbm as lgb
import holidays
from sklearn.metrics import mean_absolute_error, mean_absolute_percentage_error

warnings.filterwarnings("ignore")

# Make src/ importable regardless of working directory
_SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)
sys.path.insert(0, os.path.join(_PROJECT_ROOT, "src"))

from weather_fetcher import fetch_weather_history, DISTRICT_COORDS  # noqa: E402

# ---------------------------------------------------------------------------
# Fallback coords when --district is not supplied (keyed by commodity name)
# ---------------------------------------------------------------------------
COMMODITY_LOCATIONS = {
    "onion":    {"lat": 20.0,    "lon": 73.8,    "label": "Nashik"},
    "soyabean": {"lat": 20.93,   "lon": 77.75,   "label": "Amravati"},
    "turmeric": {"lat": 16.85,   "lon": 74.56,   "label": "Sangli"},
    "potato":   {"lat": 18.5204, "lon": 73.8567, "label": "Pune"},
}

# ---------------------------------------------------------------------------
# Feature columns per horizon
#
# Existing features (Prisha's naming convention, preserved unchanged):
#   temp_mean_lag{1,7,15,30}  rainfall_lag{1,7,15,30}
#   rainfall_7d_sum  rainfall_30d_sum  temp_7d_avg
#
# New features added here (7 columns, appended at the end of every horizon):
#   temp_mean      – today's mean temp  (no lag)
#   temp_lag1      – temp_mean shifted 1 day
#   temp_lag7      – temp_mean shifted 7 days
#   precip_lag1    – raw daily precipitation shifted 1 day
#   precip_roll7   – 7-day rolling sum of raw precipitation
#   precip_roll30  – 30-day rolling sum of raw precipitation
#   evapotrans_lag1 – evapotranspiration shifted 1 day (new variable, not in Prisha's pipeline)
# ---------------------------------------------------------------------------
_NEW_WEATHER = [
    "temp_mean", "temp_lag1", "temp_lag7",
    "precip_lag1", "precip_roll7", "precip_roll30",
    "evapotrans_lag1",
]

_SHARED = [
    "mandi_name", "district", "state", "variety", "is_real_trade",
    "day_of_week", "month", "day_of_year", "is_weekend", "is_holiday",
    "price_roll_mean_7", "price_roll_std_7", "price_roll_mean_30", "price_expanding_mean",
    "sin_365_1", "cos_365_1", "sin_365_2", "cos_365_2",
    "rainfall_7d_sum", "rainfall_30d_sum", "temp_7d_avg",
]

HORIZON_FEATURES = {
    1:  _SHARED + ["price_lag_1", "price_lag_2", "price_lag_3", "price_lag_7",
                   "temp_mean_lag1",  "rainfall_lag1"] + _NEW_WEATHER,
    7:  _SHARED + ["price_lag_7", "price_lag_8", "price_lag_9", "price_lag_14", "price_lag_30",
                   "temp_mean_lag7",  "rainfall_lag7"] + _NEW_WEATHER,
    15: _SHARED + ["price_lag_15", "price_lag_16", "price_lag_17", "price_lag_30",
                   "temp_mean_lag15", "rainfall_lag15"] + _NEW_WEATHER,
    30: _SHARED + ["price_lag_30", "price_lag_31", "price_lag_32", "price_lag_45",
                   "temp_mean_lag30", "rainfall_lag30"] + _NEW_WEATHER,
}

# ---------------------------------------------------------------------------
# LightGBM training configs per horizon
# ---------------------------------------------------------------------------
_BASE_FAST = {
    "boosting_type": "gbdt", "learning_rate": 0.03,
    "feature_fraction": 0.8, "bagging_fraction": 0.8, "bagging_freq": 5,
    "verbose": -1, "random_state": 42,
}
_BASE_SLOW = {
    "boosting_type": "gbdt", "learning_rate": 0.01,
    "feature_fraction": 0.8, "bagging_fraction": 0.8, "bagging_freq": 5,
    "verbose": -1, "random_state": 42,
}

HORIZON_CONFIGS = {
    1: {
        "base": _BASE_FAST, "early_stopping": 50, "num_boost_round": 2000,
        "suffix": "_ver2.txt",
        "quantiles": {
            "p50": {"alpha": 0.50, "max_depth": 9,  "num_leaves": 45, "min_data_in_leaf": 20, "lambda_l1": 0.1, "lambda_l2": 0.1},
            "p10": {"alpha": 0.10, "max_depth": 5,  "num_leaves": 20, "min_data_in_leaf": 50, "lambda_l1": 1.5, "lambda_l2": 1.0},
            "p90": {"alpha": 0.90, "max_depth": 5,  "num_leaves": 20, "min_data_in_leaf": 50, "lambda_l1": 1.5, "lambda_l2": 1.0},
        },
    },
    7: {
        "base": _BASE_SLOW, "early_stopping": 100, "num_boost_round": 3000,
        "suffix": ".txt",
        "quantiles": {
            "p50": {"alpha": 0.50, "max_depth": 10, "num_leaves": 63, "min_data_in_leaf": 15, "lambda_l1": 0.1, "lambda_l2": 0.1},
            "p10": {"alpha": 0.05, "max_depth": 6,  "num_leaves": 31, "min_data_in_leaf": 30, "lambda_l1": 1.0, "lambda_l2": 1.0},
            "p90": {"alpha": 0.95, "max_depth": 6,  "num_leaves": 31, "min_data_in_leaf": 30, "lambda_l1": 1.0, "lambda_l2": 1.0},
        },
    },
    15: {
        "base": _BASE_SLOW, "early_stopping": 100, "num_boost_round": 3000,
        "suffix": ".txt",
        "quantiles": {
            "p50": {"alpha": 0.50, "max_depth": 10, "num_leaves": 63, "min_data_in_leaf": 15, "lambda_l1": 0.1, "lambda_l2": 0.1},
            "p10": {"alpha": 0.05, "max_depth": 6,  "num_leaves": 31, "min_data_in_leaf": 30, "lambda_l1": 1.0, "lambda_l2": 1.0},
            "p90": {"alpha": 0.95, "max_depth": 6,  "num_leaves": 31, "min_data_in_leaf": 30, "lambda_l1": 1.0, "lambda_l2": 1.0},
        },
    },
    30: {
        "base": _BASE_SLOW, "early_stopping": 100, "num_boost_round": 3000,
        "suffix": "_smoothed.txt",
        "quantiles": {
            "p50": {"alpha": 0.50, "max_depth": 10, "num_leaves": 63, "min_data_in_leaf": 15, "lambda_l1": 0.1, "lambda_l2": 0.1},
            "p10": {"alpha": 0.05, "max_depth": 6,  "num_leaves": 31, "min_data_in_leaf": 30, "lambda_l1": 1.0, "lambda_l2": 1.0},
            "p90": {"alpha": 0.95, "max_depth": 6,  "num_leaves": 31, "min_data_in_leaf": 30, "lambda_l1": 1.0, "lambda_l2": 1.0},
        },
    },
}


# ---------------------------------------------------------------------------
# Step 1 – Load & clean raw Agmarknet CSV
# ---------------------------------------------------------------------------
def load_and_clean(filepath: str) -> pd.DataFrame:
    df = pd.read_csv(filepath)

    col_map = {
        "Arrival_Date": "arrival_date",
        "District":     "district",
        "Market":       "mandi_name",
        "Commodity":    "commodity",
        "Variety":      "variety",
        "Grade":        "grade",
        "State":        "state",
        # Agmarknet exports use either spaces or underscores
        "Min Price":    "min_price",   "Min_Price":   "min_price",
        "Max Price":    "max_price",   "Max_Price":   "max_price",
        "Modal Price":  "modal_price", "Modal_Price": "modal_price",
    }
    df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})

    df["arrival_date"] = pd.to_datetime(df["arrival_date"], dayfirst=True, errors="coerce")
    for col in ("min_price", "max_price", "modal_price"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    for col in ("mandi_name", "variety", "district"):
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip().str.title()

    if "state" not in df.columns:
        df["state"] = "Maharashtra"

    df = df.dropna(subset=["arrival_date", "modal_price"])
    df = df[df["modal_price"] > 0].sort_values("arrival_date").reset_index(drop=True)

    print(f"  Rows loaded : {len(df):,}")
    print(f"  Date range  : {df['arrival_date'].min().date()} to {df['arrival_date'].max().date()}")
    print(f"  Markets     : {sorted(df['mandi_name'].unique().tolist())}")
    return df


# ---------------------------------------------------------------------------
# Step 2 – Feature engineering
#
# Prisha's existing weather features (kept unchanged, same names as
# data_pipeline.py so inference stays compatible):
#   temp_mean_lag{1,7,15,30}  rainfall_lag{1,7,15,30}
#   rainfall_7d_sum  rainfall_30d_sum  temp_7d_avg
#
# New features (appended after Prisha's, using different column names):
#   temp_mean, temp_lag1, temp_lag7, precip_lag1,
#   precip_roll7, precip_roll30, evapotrans_lag1
# ---------------------------------------------------------------------------
def engineer_features(df: pd.DataFrame, weather_df: pd.DataFrame) -> pd.DataFrame:
    years = range(df["arrival_date"].dt.year.min(),
                  df["arrival_date"].dt.year.max() + 2)
    india_hols = holidays.India(years=list(years))

    groups = []
    for _, grp in df.groupby("mandi_name"):
        g = grp.copy().sort_values("arrival_date").reset_index(drop=True)

        # -- Merge weather & fill gaps ----------------------------------------
        if not weather_df.empty:
            g = pd.merge(g, weather_df, on="arrival_date", how="left")
            for col in ("temp_max", "temp_min", "precipitation", "evapotranspiration"):
                g[col] = g[col].ffill().bfill().fillna(0.0)
            # Derive temp_mean from max/min (more accurate than mean API field)
            g["temp_mean"] = (g["temp_max"] + g["temp_min"]) / 2.0
            # Keep 'rainfall' as alias so Prisha's lag names stay consistent
            g["rainfall"]  = g["precipitation"]
        else:
            g["temp_mean"]        = 0.0
            g["rainfall"]         = 0.0
            g["precipitation"]    = 0.0
            g["evapotranspiration"] = 0.0

        g["is_real_trade"] = (g["modal_price"] > 0).astype(int)

        # -- Price lags --------------------------------------------------------
        for lag in (1, 2, 3, 7, 8, 9, 14, 15, 16, 17, 30, 31, 32, 45):
            g[f"price_lag_{lag}"] = g["modal_price"].shift(lag)

        g["price_expanding_mean"] = g["price_lag_1"].expanding().mean()
        g["price_roll_mean_7"]    = g["price_lag_1"].rolling(7).mean()
        g["price_roll_std_7"]     = g["price_lag_1"].rolling(7).std()
        g["price_roll_mean_30"]   = g["price_lag_1"].rolling(30).mean()

        # -- Prisha's weather lags (names preserved for inference compat) ------
        for lag in (1, 7, 15, 30):
            g[f"temp_mean_lag{lag}"] = g["temp_mean"].shift(lag)
            g[f"rainfall_lag{lag}"]  = g["rainfall"].shift(lag)

        g["rainfall_7d_sum"]  = g["rainfall_lag1"].rolling(7).sum()
        g["rainfall_30d_sum"] = g["rainfall_lag1"].rolling(30).sum()
        g["temp_7d_avg"]      = g["temp_mean_lag1"].rolling(7).mean()

        # -- New weather features (7 columns, different names) ----------------
        g["temp_lag1"]        = g["temp_mean"].shift(1)
        g["temp_lag7"]        = g["temp_mean"].shift(7)
        g["precip_lag1"]      = g["precipitation"].shift(1)
        g["precip_roll7"]     = g["precipitation"].rolling(7).sum()
        g["precip_roll30"]    = g["precipitation"].rolling(30).sum()
        g["evapotrans_lag1"]  = g["evapotranspiration"].shift(1)
        # temp_mean itself (no lag) is already set above and added to features

        # -- Date / calendar features ------------------------------------------
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

        groups.append(g)

    return pd.concat(groups).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Step 3 – Train one horizon (3 quantile models)
# ---------------------------------------------------------------------------
def train_horizon(df_feats: pd.DataFrame, commodity: str, horizon: int,
                  model_dir: str):
    cfg          = HORIZON_CONFIGS[horizon]
    feature_cols = HORIZON_FEATURES[horizon]

    horizon_groups = []
    for _, grp in df_feats.groupby("mandi_name"):
        g = grp.copy().sort_values("arrival_date").reset_index(drop=True)
        g["target_price"] = g["modal_price"].shift(-horizon)
        if horizon == 30:
            g["target_price"] = g["target_price"].rolling(
                window=7, center=True, min_periods=1
            ).mean()
        horizon_groups.append(g)
    df_h = pd.concat(horizon_groups).reset_index(drop=True)

    keep = feature_cols + ["target_price", "arrival_date"]
    df_h = df_h[[c for c in keep if c in df_h.columns]].dropna()
    df_h = df_h.sort_values("arrival_date").reset_index(drop=True)

    split_idx = int(len(df_h) * 0.85)
    train_df  = df_h.iloc[:split_idx].copy()
    val_df    = df_h.iloc[split_idx:].copy()
    print(f"    train={len(train_df):,}  val={len(val_df):,}")

    X_train = train_df[feature_cols].copy()
    y_train = train_df["target_price"]
    X_val   = val_df[feature_cols].copy()
    y_val   = val_df["target_price"]

    cat_cols = [c for c in ("mandi_name", "district", "state", "variety")
                if c in feature_cols]
    for col in cat_cols:
        X_train[col] = X_train[col].astype("category")
        X_val[col]   = pd.Categorical(
            X_val[col], categories=X_train[col].cat.categories
        )

    lgb_train_ds = lgb.Dataset(X_train, label=y_train, free_raw_data=False)
    lgb_val_ds   = lgb.Dataset(X_val,   label=y_val,
                               reference=lgb_train_ds, free_raw_data=False)

    p10_preds = p90_preds = None
    p50_metrics: dict = {}

    for q_name, q_cfg in cfg["quantiles"].items():
        params = {**cfg["base"], **q_cfg,
                  "objective": "quantile", "metric": "quantile"}
        callbacks = [
            lgb.early_stopping(
                stopping_rounds=cfg["early_stopping"],
                first_metric_only=False, verbose=False
            ),
            lgb.log_evaluation(period=500),
        ]
        model = lgb.train(
            params, lgb_train_ds,
            num_boost_round=cfg["num_boost_round"],
            valid_sets=[lgb_train_ds, lgb_val_ds],
            valid_names=["train", "val"],
            callbacks=callbacks,
        )

        filename  = f"lightgbm_{commodity}_{horizon}day_{q_name}{cfg['suffix']}"
        model.save_model(os.path.join(model_dir, filename))
        print(f"    Saved: {filename}")

        preds = model.predict(X_val)
        if q_name == "p50":
            p50_metrics = {
                "mae":  mean_absolute_error(y_val, preds),
                "mape": mean_absolute_percentage_error(y_val, preds) * 100,
            }
        elif q_name == "p10":
            p10_preds = preds
        elif q_name == "p90":
            p90_preds = preds

    return p50_metrics, y_val, p10_preds, p90_preds


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Train LightGBM quantile models for a commodity."
    )
    parser.add_argument("--commodity", required=True)
    parser.add_argument("--file",      required=True)
    parser.add_argument("--district",  default=None,
                        help="District name for weather coords (e.g. nashik, amravati, pune)")
    parser.add_argument("--lat",  type=float, default=None)
    parser.add_argument("--lon",  type=float, default=None)
    args = parser.parse_args()

    commodity    = args.commodity.strip().lower()
    model_dir    = os.path.join(_PROJECT_ROOT, "models", commodity)
    metrics_dir  = os.path.join(_PROJECT_ROOT, "metrics")
    metrics_path = os.path.join(metrics_dir, "model_metrics.csv")
    os.makedirs(model_dir,   exist_ok=True)
    os.makedirs(metrics_dir, exist_ok=True)

    print(f"\n{'='*65}")
    print(f"  Training models for: {commodity.upper()}")
    print(f"{'='*65}")

    # Snapshot old metrics for this commodity before overwriting
    old_mape: dict = {}
    if os.path.exists(metrics_path):
        old_df = pd.read_csv(metrics_path)
        for _, row in old_df[old_df["Commodity"] == commodity].iterrows():
            old_mape[row["Horizon"]] = row["MAPE"]

    # 1. Load raw CSV
    print("\n[Step 1] Loading & cleaning raw data")
    csv_path = (os.path.join(_PROJECT_ROOT, args.file)
                if not os.path.isabs(args.file) else args.file)
    df_raw = load_and_clean(csv_path)

    # 2. Resolve weather coordinates: --district > --lat/lon > commodity fallback
    print("\n[Step 2] Fetching historical weather")
    lat = lon = None
    if args.district:
        key = args.district.strip().lower()
        coords = DISTRICT_COORDS.get(key)
        if coords:
            lat, lon = coords["lat"], coords["lon"]
            print(f"  District '{key}' -> ({lat}, {lon})")
        else:
            print(f"  Warning: district '{key}' not in DISTRICT_COORDS. "
                  f"Known: {list(DISTRICT_COORDS.keys())}")
    if lat is None:
        lat = args.lat or COMMODITY_LOCATIONS.get(commodity, {}).get("lat")
        lon = args.lon or COMMODITY_LOCATIONS.get(commodity, {}).get("lon")

    weather_df = pd.DataFrame()
    if lat and lon:
        start = df_raw["arrival_date"].min().strftime("%Y-%m-%d")
        end   = df_raw["arrival_date"].max().strftime("%Y-%m-%d")
        print(f"  Fetching weather ({lat}, {lon})  {start} to {end} ...")
        raw_weather = fetch_weather_history(lat, lon, start, end)
        if not raw_weather.empty:
            # Rename 'date' -> 'arrival_date' for merge compatibility
            weather_df = raw_weather.rename(columns={"date": "arrival_date"})
            print(f"  Weather rows: {len(weather_df)}")
        else:
            print("  Weather fetch failed. Using zero placeholders.")
    else:
        print(f"  No coords for '{commodity}'. Pass --district or --lat/--lon.")

    # 3. Feature engineering
    print("\n[Step 3] Engineering features")
    df_feats = engineer_features(df_raw, weather_df)
    print(f"  Feature-engineered rows: {len(df_feats):,}")

    # 4. Train all 4 horizons
    all_metrics = []
    for h in (1, 7, 15, 30):
        print(f"\n[Horizon {h}d]")
        m, y_val, p10, p90 = train_horizon(df_feats, commodity, h, model_dir)
        coverage = ((y_val.values >= p10) & (y_val.values <= p90)).mean() * 100
        all_metrics.append({
            "Commodity": commodity,
            "Horizon":   f"{h}d",
            "Quantile":  "p50",
            "MAE":       round(m["mae"], 2),
            "MAPE":      f"{m['mape']:.2f}%",
            "Coverage":  f"{coverage:.1f}%",
        })
        print(f"  MAE={m['mae']:.2f}  MAPE={m['mape']:.2f}%  80%Coverage={coverage:.1f}%")

    # 5. Save / append metrics CSV
    new_df = pd.DataFrame(all_metrics)
    if os.path.exists(metrics_path):
        existing = pd.read_csv(metrics_path)
        existing = existing[existing["Commodity"] != commodity]
        new_df   = pd.concat([existing, new_df], ignore_index=True)
    new_df.to_csv(metrics_path, index=False)

    # 6. Before/after comparison (if old metrics exist for this commodity)
    if old_mape:
        print(f"\n{'='*65}")
        print(f"  BEFORE vs AFTER — {commodity.upper()} (p50 MAPE on val set)")
        print(f"{'='*65}")
        print(f"  {'Commodity':<12} {'Horizon':<9} {'Old MAPE':<12} {'New MAPE':<12} Change")
        print(f"  {'-'*60}")
        for r in all_metrics:
            h      = r["Horizon"]
            new_mp = float(r["MAPE"].rstrip("%"))
            old_mp_str = old_mape.get(h, "N/A")
            if old_mp_str != "N/A":
                old_mp = float(str(old_mp_str).rstrip("%"))
                delta  = new_mp - old_mp
                sign   = "+" if delta > 0 else ""
                change = f"{sign}{delta:.2f}pp"
            else:
                old_mp_str = "N/A"
                change     = "—"
            print(
                f"  {commodity:<12} {h:<9} {str(old_mp_str):<12} "
                f"{r['MAPE']:<12} {change}"
            )

    print(f"\n  Metrics saved : {metrics_path}")
    print(f"  Models saved  : {model_dir}")
    print(f"{'='*65}\n")


if __name__ == "__main__":
    main()
