# -*- coding: utf-8 -*-
"""
Defines coverage scope for Farmula — major Maharashtra agricultural districts
and commodities. Used by historical fetch + training pipeline.
"""

# Top 12 agricultural districts in Maharashtra by APMC activity
TARGET_DISTRICTS = [
    "Pune", "Nashik", "Nagpur", "Amravati", "Solapur", "Kolhapur",
    "Ahmednagar", "Aurangabad", "Satara", "Sangli", "Jalgaon", "Yavatmal"
]

# Top commodities traded across these districts (Agmarknet standard names)
TARGET_COMMODITIES = [
    "Onion", "Potato", "Tomato", "Soyabean", "Cotton", "Wheat",
    "Bajra", "Jowar", "Maize", "Tur", "Gram", "Mango",
    "Banana", "Pomegranate", "Grapes", "Sugarcane", "Cauliflower",
    "Cabbage", "Brinjal", "Coriander(Leaves)", "Methi(Leaves)"
]

# Minimum records required to consider a pair "trainable"
MIN_RECORDS_FOR_TRAINING = 365   # roughly 1 year of daily data

# Pairs we already have trained models for — do not retrain
EXISTING_TRAINED_PAIRS = [
    ("onion", "nashik"),
    ("potato", "pune"),
    ("soyabean", "amravati"),
]


def get_all_trained_pairs() -> list:
    """
    Dynamically discovers trained commodity folders from disk.
    Returns list of commodity folder names (lowercase, underscores) that
    have at least 12 model files. District is not encoded in the folder
    name — use ui_mapping.json to resolve commodity → districts.
    No hardcoding — reads model folder structure.
    """
    from pathlib import Path
    models_dir = Path("models")
    if not models_dir.exists():
        return []

    trained = []
    for commodity_dir in sorted(models_dir.iterdir()):
        if not commodity_dir.is_dir():
            continue
        model_files = list(commodity_dir.glob("*.txt"))
        if len(model_files) >= 12:
            trained.append(commodity_dir.name)
    return trained
