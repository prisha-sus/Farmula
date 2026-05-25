# -*- coding: utf-8 -*-
"""
Smoke-tests the SHAP explanation pipeline for every commodity/horizon combo.
Run from project root: python scripts/test_shap.py
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.explainer import generate_explanation
from src.inference import load_models

commodities = [
    ("onion",    "nashik",   1),
    ("soyabean", "amravati", 1),
    ("potato",   "pune",     1),
]

all_passed = True

for commodity, district, horizon in commodities:
    print(f"\nTesting SHAP: {commodity} / {district} / {horizon}d")
    try:
        models = load_models(commodity, horizon)
        print(f"  Models loaded: {list(models.keys())}")
        explanation = generate_explanation(commodity, horizon)
        print(f"  SHAP explanation: {explanation[:80]}...")
        print(f"  PASS")
    except Exception as e:
        print(f"  FAIL: {e}")
        all_passed = False

print()
print("All tests passed." if all_passed else "Some tests FAILED — see above.")
