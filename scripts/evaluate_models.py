# -*- coding: utf-8 -*-
#!/usr/bin/env python3
"""
Model Evaluation Script for Farmula.
Generates actual vs predicted graphs and RMSE metrics for all trained models.
Outputs saved to evaluation/ folder — all files downloadable.
"""

import os
import sys

# Force UTF-8 output on Windows (avoids cp1252 encoding errors for ₹, box chars)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import warnings
import numpy as np
import pandas as pd
import lightgbm as lgb

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

from sklearn.metrics import mean_squared_error

warnings.filterwarnings("ignore")

_SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)
sys.path.insert(0, os.path.join(_PROJECT_ROOT, "src"))
sys.path.insert(0, _SCRIPT_DIR)

from weather_fetcher import fetch_weather_history, DISTRICT_COORDS
from train_commodity import load_and_clean, engineer_features, HORIZON_FEATURES

# ---------------------------------------------------------------------------
PAIRS = [
    ("potato",   "pune",     "data/potato_pune.csv"),
    ("onion",    "nashik",   "data/onion_nashik.csv"),
    ("soyabean", "amravati", "data/aamrawati_soyabean.csv"),
]

HORIZONS = [1, 7, 15, 30]

HORIZON_SUFFIX = {
    1:  "_ver2.txt",
    7:  ".txt",
    15: ".txt",
    30: "_smoothed.txt",
}

OUTPUT_DIR = os.path.join(_PROJECT_ROOT, "evaluation")
os.makedirs(OUTPUT_DIR, exist_ok=True)


def get_model_path(commodity: str, horizon: int, quantile: str) -> str:
    fname = f"lightgbm_{commodity}_{horizon}day_{quantile}{HORIZON_SUFFIX[horizon]}"
    return os.path.join(_PROJECT_ROOT, "models", commodity, fname)


def build_horizon_dataset(df_feats: pd.DataFrame, horizon: int):
    """
    Mirror train_horizon()'s dataset construction exactly.
    Returns (df_h_full, feature_cols) where df_h_full is the full chronologically
    sorted, NaN-dropped dataset with target_price and category-encoded columns.
    Category codes are fitted on the FULL dataset so train/test share the same encoding.
    """
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

    # Fit category encoding on the FULL dataset before any split so that
    # test-set codes are consistent with what training would have used.
    cat_cols = [c for c in ("mandi_name", "district", "state", "variety")
                if c in feature_cols and c in df_h.columns]
    for col in cat_cols:
        df_h[col] = df_h[col].astype("category")

    available_features = [c for c in feature_cols if c in df_h.columns]
    return df_h, available_features


def evaluate_pair(commodity: str, district: str, csv_file: str) -> list:
    print(f"\n{'='*65}")
    print(f"  Evaluating: {commodity.upper()} — {district.upper()}")
    print(f"{'='*65}")

    # 1. Load & clean
    csv_path = os.path.join(_PROJECT_ROOT, csv_file)
    df_raw = load_and_clean(csv_path)

    # 2. Fetch weather
    coords = DISTRICT_COORDS.get(district.lower(), {})
    lat, lon = coords.get("lat"), coords.get("lon")
    weather_df = pd.DataFrame()
    if lat and lon:
        start = df_raw["arrival_date"].min().strftime("%Y-%m-%d")
        end   = df_raw["arrival_date"].max().strftime("%Y-%m-%d")
        print(f"  Fetching weather ({lat}, {lon})  {start} to {end} ...")
        raw_weather = fetch_weather_history(lat, lon, start, end)
        if not raw_weather.empty:
            weather_df = raw_weather.rename(columns={"date": "arrival_date"})
            print(f"  Weather rows : {len(weather_df)}")
        else:
            print("  Weather fetch failed — using zero placeholders.")

    # 3. Feature engineering
    print("  Engineering features ...")
    df_feats = engineer_features(df_raw, weather_df)
    print(f"  Feature rows : {len(df_feats):,}")

    results      = []
    horizon_data = {}

    for horizon in HORIZONS:
        print(f"\n  [Horizon {horizon}d]")

        df_h, feature_cols = build_horizon_dataset(df_feats, horizon)

        # Chronological 80/20 split — test set is the last 20% of rows
        split_idx  = int(len(df_h) * 0.80)
        test_df    = df_h.iloc[split_idx:].copy()

        X_test     = test_df[feature_cols]
        y_actual   = test_df["target_price"].values
        test_dates = pd.to_datetime(test_df["arrival_date"].values)

        print(f"    total={len(df_h):,}  test={len(test_df):,}  "
              f"date range: {test_dates.min().date()} to {test_dates.max().date()}")

        # Load models
        model_p50 = lgb.Booster(model_file=get_model_path(commodity, horizon, "p50"))
        model_p10 = lgb.Booster(model_file=get_model_path(commodity, horizon, "p10"))
        model_p90 = lgb.Booster(model_file=get_model_path(commodity, horizon, "p90"))

        y_pred_p50 = model_p50.predict(X_test)
        y_pred_p10 = model_p10.predict(X_test)
        y_pred_p90 = model_p90.predict(X_test)

        # Metrics
        rmse     = np.sqrt(mean_squared_error(y_actual, y_pred_p50))
        mae      = np.mean(np.abs(y_actual - y_pred_p50))
        mape     = np.mean(np.abs((y_actual - y_pred_p50) / y_actual)) * 100
        coverage = np.mean((y_actual >= y_pred_p10) & (y_actual <= y_pred_p90)) * 100

        print(f"    RMSE=₹{rmse:.2f}  MAE=₹{mae:.2f}  MAPE={mape:.2f}%  "
              f"Coverage={coverage:.2f}%")

        results.append({
            "commodity":      commodity,
            "district":       district,
            "horizon":        f"{horizon}d",
            "RMSE":           round(rmse, 2),
            "MAE":            round(mae, 2),
            "MAPE":           round(mape, 2),
            "coverage_80pct": round(coverage, 1),
        })

        horizon_data[horizon] = {
            "dates":      test_dates,
            "y_actual":   y_actual,
            "y_pred_p50": y_pred_p50,
            "y_pred_p10": y_pred_p10,
            "y_pred_p90": y_pred_p90,
            "rmse":       rmse,
            "mape":       mape,
        }

    # 4. Generate 2×2 subplot figure
    fig, axes = plt.subplots(2, 2, figsize=(16, 10))
    fig.suptitle(
        f"{commodity.title()} — Actual vs Predicted Price ({district.title()})",
        fontsize=16, fontweight="bold",
    )

    SMOOTH = 7  # rolling-mean window (days) applied after daily-median aggregation

    for ax, horizon in zip(axes.flatten(), HORIZONS):
        d = horizon_data[horizon]

        # Collapse multi-mandi rows → one value per calendar date (median),
        # then smooth with a 7-day rolling mean so the lines are readable.
        raw = pd.DataFrame({
            "date": d["dates"],
            "actual": d["y_actual"],
            "p50":    d["y_pred_p50"],
            "p10":    d["y_pred_p10"],
            "p90":    d["y_pred_p90"],
        }).groupby("date").median().sort_index()

        dates    = raw.index
        actual   = raw["actual"].rolling(SMOOTH, center=True, min_periods=1).mean()
        pred_p50 = raw["p50"].rolling(SMOOTH, center=True, min_periods=1).mean()
        pred_p10 = raw["p10"].rolling(SMOOTH, center=True, min_periods=1).mean()
        pred_p90 = raw["p90"].rolling(SMOOTH, center=True, min_periods=1).mean()

        # Y-axis: 2nd–98th percentile of smoothed actuals + 25% margin,
        # so a single extreme quantile prediction never collapses the plot.
        p2, p98 = np.percentile(actual, [2, 98])
        margin   = (p98 - p2) * 0.25
        y_lo     = max(0, p2 - margin)
        y_hi     = p98 + margin

        ax.plot(dates, actual,
                label="Actual", color="#2196F3", linewidth=2)
        ax.plot(dates, pred_p50,
                label="Predicted (p50)", color="#FF9800", linewidth=2, linestyle="--")
        ax.fill_between(dates,
                        np.clip(pred_p10, y_lo, y_hi),
                        np.clip(pred_p90, y_lo, y_hi),
                        alpha=0.20, color="#FF9800", label="p10–p90 band")

        ax.set_ylim(y_lo, y_hi)
        ax.set_title(
            f"{horizon}-day horizon  |  RMSE: ₹{d['rmse']:.2f}  |  MAPE: {d['mape']:.2f}%",
            fontsize=10, fontweight="bold",
        )
        ax.set_xlabel("Date", fontsize=9)
        ax.set_ylabel("Price (₹/quintal)", fontsize=9)
        ax.legend(loc="upper left", fontsize=8, framealpha=0.7)
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha="right", fontsize=8)
        ax.tick_params(axis="y", labelsize=8)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.grid(True, alpha=0.25, linestyle="--")

    fig.text(0.5, 0.01,
             f"Lines show daily-median across mandis, smoothed with {SMOOTH}-day rolling mean  "
             f"|  RMSE/MAPE computed on raw per-mandi test data",
             ha="center", fontsize=7, color="grey")

    plt.tight_layout(rect=[0, 0.03, 1, 1])
    out_png = os.path.join(OUTPUT_DIR, f"{commodity}_actual_vs_predicted.png")
    plt.savefig(out_png, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"\n  Saved plot : {out_png}")

    return results


def build_summary_table(all_results: list) -> str:
    """Return the ╔...╗ bordered summary table as a string."""
    top = "╔══════════════════════════════════════════════════════════════╗"
    ttl = "║              FARMULA MODEL EVALUATION SUMMARY               ║"
    div = "╠══════════╦══════════╦═════════╦═══════════╦════════╦════════╣"
    hdr = "║ Commodity║ District ║ Horizon ║ RMSE (₹)  ║ MAE(₹) ║  MAPE  ║"
    bot = "╚══════════╩══════════╩═════════╩═══════════╩════════╩════════╝"

    # Column content widths (chars between ║ chars): 10, 10, 9, 11, 8, 8
    lines = [top, ttl, div, hdr, div]
    for r in all_results:
        h_str    = r["horizon"]
        rmse_str = f"{r['RMSE']:.2f}"
        mae_str  = f"{r['MAE']:.2f}"
        mape_str = f"{r['MAPE']:.2f}%"
        row = (
            f"║ {r['commodity']:<9}"   # 10 chars
            f"║ {r['district']:<9}"    # 10 chars
            f"║ {h_str:<8}"           # 9 chars
            f"║ {rmse_str:>9} "       # 11 chars
            f"║ {mae_str:>6} "        # 8 chars
            f"║ {mape_str:>7} ║"      # 8 chars
        )
        lines.append(row)
    lines.append(bot)
    return "\n".join(lines)


def save_metrics_table_png(metrics_df: pd.DataFrame) -> None:
    """Render rmse_metrics.csv as a styled table image."""
    columns = ["Commodity", "District", "Horizon", "RMSE (₹)", "MAE (₹)", "MAPE (%)"]
    rows = []
    for _, row in metrics_df.iterrows():
        rows.append([
            row["commodity"].title(),
            row["district"].title(),
            row["horizon"],
            f"{row['RMSE']:.2f}",
            f"{row['MAE']:.2f}",
            f"{row['MAPE']:.2f}%",
        ])

    fig, ax = plt.subplots(figsize=(12, 5))
    ax.axis("off")

    tbl = ax.table(
        cellText=rows,
        colLabels=columns,
        cellLoc="center",
        loc="center",
    )
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(11)
    tbl.scale(1.2, 1.8)

    # Header row styling
    for j in range(len(columns)):
        tbl[0, j].set_facecolor("#2d2d2d")
        tbl[0, j].set_text_props(color="white", fontweight="bold")

    # Alternating row shading
    for i in range(1, len(rows) + 1):
        color = "#f5f5f5" if i % 2 == 0 else "white"
        for j in range(len(columns)):
            tbl[i, j].set_facecolor(color)

    # Heavier bottom border after each commodity group (rows 4, 8)
    for i in [4, 8]:
        for j in range(len(columns)):
            tbl[i, j].visible_edges = "open"   # clear default
            cell = tbl[i, j]
            cell.set_edgecolor("#888888")

    plt.title(
        "Farmula DSS — Model Evaluation Metrics\n"
        "LightGBM Quantile Regression  ·  80/20 Chronological Split",
        fontsize=13, fontweight="bold", pad=20,
    )
    plt.tight_layout()
    out = os.path.join(OUTPUT_DIR, "rmse_metrics_table.png")
    plt.savefig(out, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close()
    print(f"Metrics table PNG  : {out}")


def main():
    all_results = []

    for commodity, district, csv_file in PAIRS:
        pair_results = evaluate_pair(commodity, district, csv_file)
        all_results.extend(pair_results)

    # Save rmse_metrics.csv
    metrics_df = pd.DataFrame(all_results)
    csv_out = os.path.join(OUTPUT_DIR, "rmse_metrics.csv")
    metrics_df.to_csv(csv_out, index=False)
    print(f"\nMetrics CSV saved  : {csv_out}")

    # Build and print summary table
    table = build_summary_table(all_results)
    print("\n" + table)

    # Save evaluation_summary.txt
    txt_out = os.path.join(OUTPUT_DIR, "evaluation_summary.txt")
    with open(txt_out, "w", encoding="utf-8") as fh:
        fh.write(table + "\n")
    print(f"Summary txt saved  : {txt_out}")

    # Save metrics table as PNG image
    save_metrics_table_png(metrics_df)

    # Print full CSV contents for copy-paste
    print("\n─── rmse_metrics.csv ─────────────────────────────────────────")
    print(metrics_df.to_string(index=False))
    print("──────────────────────────────────────────────────────────────")


if __name__ == "__main__":
    main()
