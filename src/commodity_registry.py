# -*- coding: utf-8 -*-
"""
Dynamic commodity-district registry.
Reads ui_mapping.json (from analysis) and training_results.json to build
what the app UI shows per district. has_forecast is district-aware:
a model trained on Nashik data does NOT count as a forecast for Pune.
"""
import json
from pathlib import Path
from functools import lru_cache

UI_MAPPING_PATH      = Path(__file__).parent.parent / "data" / "analysis" / "ui_mapping.json"
TRAINING_RESULTS_PATH = Path(__file__).parent.parent / "data" / "analysis" / "training_results.json"
MODELS_DIR           = Path(__file__).parent.parent / "models"
MIN_UI_RECORDS       = 100


@lru_cache(maxsize=1)
def _load_ui_mapping() -> dict:
    if not UI_MAPPING_PATH.exists():
        return {}
    return json.loads(UI_MAPPING_PATH.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _load_trained_pairs() -> set:
    """
    Returns set of (commodity_key, district_key) tuples that have trained models.
    Reads training_results.json which records the exact district each model was
    trained for. Falls back to legacy hardcoded pairs if the file is absent.
    """
    trained = set()

    # Primary source: training_results.json — district-aware
    if TRAINING_RESULTS_PATH.exists():
        results = json.loads(TRAINING_RESULTS_PATH.read_text(encoding="utf-8"))
        for r in results:
            if "metrics" in r and r["metrics"]:
                commodity_key = r["commodity"].lower().replace(" ", "_")
                district_key  = r["district"].lower()
                trained.add((commodity_key, district_key))

    # Original 3 pairs that pre-date bulk training (models exist on disk)
    LEGACY_PAIRS = [
        ("onion",    "nashik"),
        ("potato",   "pune"),
        ("soyabean", "amravati"),
    ]
    for pair in LEGACY_PAIRS:
        if (MODELS_DIR / pair[0]).exists():
            trained.add(pair)

    return trained


def get_trained_commodities() -> set:
    """Returns just the commodity keys — kept for backwards compatibility."""
    return {commodity for commodity, _ in _load_trained_pairs()}


def get_available_districts() -> list:
    """All districts that have at least some price data, sorted alphabetically."""
    mapping = _load_ui_mapping()
    return sorted(mapping.keys())


def get_commodities_for_district(district: str) -> list:
    """
    Returns commodities for a district, ranked by record count.
    has_forecast=True ONLY when a model was trained on this specific
    commodity+district pair — not just because any model for that commodity exists.
    """
    mapping       = _load_ui_mapping()
    trained_pairs = _load_trained_pairs()
    district_key  = district.lower()
    district_data = mapping.get(district, mapping.get(district.title(), []))

    result = []
    for item in district_data:
        if item["records"] < MIN_UI_RECORDS:
            continue
        commodity_key = item["commodity"].lower().replace(" ", "_")
        has_fc = (commodity_key, district_key) in trained_pairs
        result.append({
            "commodity":     item["commodity"],
            "commodity_key": commodity_key,
            "records":       item["records"],
            "has_forecast":  has_fc,
        })

    # AI-forecast pairs first, then by record count descending
    result.sort(key=lambda x: (not x["has_forecast"], -x["records"]))
    return result


def has_forecast(commodity: str, district: str) -> bool:
    """Check if a specific commodity-district pair has trained models."""
    trained_pairs = _load_trained_pairs()
    key           = commodity.lower().replace(" ", "_")
    district_key  = district.lower()
    return (key, district_key) in trained_pairs


def clear_cache():
    """Clear all caches — call after training new models without restarting."""
    _load_ui_mapping.cache_clear()
    _load_trained_pairs.cache_clear()
