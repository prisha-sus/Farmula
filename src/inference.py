# -*- coding: utf-8 -*-
"""
Inference Module for SmartMandi DSS.
Handles loading LightGBM models into memory and generating batch forecasts.
"""

import os
import pandas as pd
import lightgbm as lgb
from typing import Dict

# Global cache to store models in memory and prevent reloading on every request
_MODEL_CACHE: Dict[int, Dict[str, lgb.Booster]] = {}

WEATHER_LAG_COLS = [
    'temp_lag1', 'temp_lag7', 'precip_lag1',
    'precip_roll7', 'precip_roll30', 'evapotrans_lag1',
    'temp_mean', 'temp_max', 'temp_min',
    'precipitation', 'evapotranspiration'
]

def load_models(commodity: str, horizon: int):
    """
    Loads the correct LightGBM models based on the exact commodity folder and horizon.
    Assumes naming convention: lightgbm_{commodity}_{horizon}day_{quantile}{suffix}
    """
    # 1. Match the specific suffix based on the horizon
    if horizon == 1:
        suffix = "_ver2.txt"
    elif horizon == 30:
        suffix = "_smoothed.txt"
    else:
        suffix = ".txt"  # For 7 and 15 days

    models = {}
    quantiles = ['p10', 'p50', 'p90']
    
    # Format the commodity name to be safe (lowercase, no extra spaces)
    safe_commodity = commodity.strip().lower()
    
    # 2. Build the filename and load the model
    for q in quantiles:
        # Dynamically inject the commodity name into the filename
        filename = f"lightgbm_{safe_commodity}_{horizon}day_{q}{suffix}"
        
        # Point to the specific commodity subfolder (e.g., models/onion/...)
        filepath = os.path.join(os.path.dirname(__file__), '..', 'models', safe_commodity, filename)
        
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"❌ Cannot find model file: {filepath}")
            
        models[q] = lgb.Booster(model_file=filepath)
        
    return models


def generate_batch_forecasts(
    latest_features_df: pd.DataFrame, 
    commodity: str,
    horizon: int, 
    model_dir: str = "models"
) -> Dict[str, Dict[str, float]]:
    """
    Runs inference for all mandis in the provided dataframe.
    
    Args:
        latest_features_df (pd.DataFrame): DataFrame containing the latest lagged 
                                           and weather features for all mandis.
        horizon (int): The forecast horizon.
        model_dir (str): Directory containing the models.
        
    Returns:
        Dictionary mapping mandi names to their forecasts.
        Example: {'Pune': {'p10': 2100.5, 'p50': 2500.0, 'p90': 2950.0}}
    """
    # 1. Load the requested horizon models
    models = load_models(commodity, horizon)
    
    # 2. Ensure 'mandi_name' exists to map results back to the correct market
    if 'mandi_name' not in latest_features_df.columns:
        raise ValueError("Input dataframe must contain a 'mandi_name' column.")
        
    # 3. Prevent data leakage: Drop strictly forbidden columns if they accidentally slipped in
    # But keep any columns required by the loaded model.
    expected_features = models['p50'].feature_name()
    drop_cols = ['arrival_date', 'target_price', 'modal_price', 'min_price', 'max_price']
    drop_candidates = [col for col in drop_cols if col in latest_features_df.columns and col not in expected_features]
    features_only_df = latest_features_df.drop(columns=drop_candidates)

    # Fill any missing weather lag columns with 0.0 so inference never crashes
    # when the DB table was built without weather features.
    for col in WEATHER_LAG_COLS:
        if col not in features_only_df.columns:
            features_only_df[col] = 0.0

    # 4. Convert categoricals explicitly before inference (required by LightGBM)
    categorical_cols = ['mandi_name', 'district', 'state', 'variety']
    for col in categorical_cols:
        if col in features_only_df.columns:
            features_only_df[col] = features_only_df[col].astype('category')

    features_only_df = features_only_df[expected_features]
            
    # 5. Generate Predictions
    p10_preds = models['p10'].predict(features_only_df)
    p50_preds = models['p50'].predict(features_only_df)
    p90_preds = models['p90'].predict(features_only_df)
    
    # 6. Package results into a clean dictionary
    results = {}
    for idx, mandi in enumerate(latest_features_df['mandi_name']):
        results[mandi] = {
            'p10': round(float(p10_preds[idx]), 2),
            'p50': round(float(p50_preds[idx]), 2),  # Expected Gross Price
            'p90': round(float(p90_preds[idx]), 2)
        }
        
    return results