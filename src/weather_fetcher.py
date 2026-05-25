# -*- coding: utf-8 -*-
"""
weather_fetcher.py
Thin wrapper around the Open-Meteo historical archive API.

Prisha's data_pipeline.py already handles live-forecast weather for Pune.
This module covers the historical fetch used by the training pipeline and
adds evapotranspiration, which is absent from the live pipeline.
"""

import requests
import pandas as pd

# ---------------------------------------------------------------------------
# District → (lat, lon) lookup used by the training script.
# Keys are lowercase district names matching what Agmarknet exports.
# ---------------------------------------------------------------------------
DISTRICT_COORDS = {
    "pune":     {"lat": 18.52, "lon": 73.85},
    "nashik":   {"lat": 19.99, "lon": 73.79},
    "amravati": {"lat": 20.93, "lon": 77.75},
}


def fetch_weather_history(
    lat: float,
    lon: float,
    start_date: str,
    end_date: str,
) -> pd.DataFrame:
    """
    Fetches daily weather from Open-Meteo historical API.
    No API key required.

    Returns DataFrame with columns:
        date, temp_max, temp_min, precipitation, evapotranspiration

    Returns an empty DataFrame on any network/parse error so callers can
    fall back gracefully.
    """
    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude":   lat,
        "longitude":  lon,
        "start_date": start_date,
        "end_date":   end_date,
        "daily": (
            "temperature_2m_max,"
            "temperature_2m_min,"
            "precipitation_sum,"
            "et0_fao_evapotranspiration"
        ),
        "timezone": "Asia/Kolkata",
    }

    try:
        response = requests.get(url, params=params, timeout=60)
        response.raise_for_status()
        daily = response.json()["daily"]

        df = pd.DataFrame({
            "date":              pd.to_datetime(daily["time"]),
            "temp_max":          daily["temperature_2m_max"],
            "temp_min":          daily["temperature_2m_min"],
            "precipitation":     daily["precipitation_sum"],
            "evapotranspiration": daily["et0_fao_evapotranspiration"],
        })

        # Coerce every numeric column — Open-Meteo occasionally returns nulls
        for col in ("temp_max", "temp_min", "precipitation", "evapotranspiration"):
            df[col] = pd.to_numeric(df[col], errors="coerce")

        return df

    except Exception as exc:
        print(f"  [weather_fetcher] fetch failed: {exc}")
        return pd.DataFrame()
