"""
Explainable AI (XAI) Module for Farmula DSS.
Uses SHAP to generate human-readable explanations for market price predictions.
"""

import shap
import numpy as np
import pandas as pd
import lightgbm as lgb
from typing import List

# A translation dictionary to convert raw feature names into farmer-friendly English
FEATURE_TRANSLATIONS = {
    'price_lag_1': 'yesterday\'s market price',
    'price_lag_7': 'the price trend from last week',
    'price_lag_30': 'the price trend from last month',
    'price_roll_mean_7': 'the average price over the last 7 days',
    'price_roll_mean_30': 'the average price over the last 30 days',
    'temp_mean_lag1': 'recent local temperatures',
    'temp_7d_avg': 'the average temperature this week',
    'rainfall_lag1': 'recent local rainfall',
    'rainfall_7d_sum': 'accumulated rainfall over the last week',
    'rainfall_30d_sum': 'accumulated rainfall over the last month',
    'day_of_week': 'historical day-of-week trading patterns',
    'month': 'seasonal monthly trends',
    'is_holiday': 'upcoming market holidays'
}

def generate_shap_explanation(model: lgb.Booster, features: pd.Series, feature_names: List[str], top_n: int = 3) -> str:
    """
    Analyzes a specific prediction using SHAP and returns a natural language explanation.
    
    Args:
        model: The trained LightGBM model (specifically the p50 gross price model).
        features: A Series containing the exact features fed into the model.
        feature_names: List of feature names corresponding to the features.
        top_n: Number of top driving factors to extract.
        
    Returns:
        A plain English string explaining the forecast.
    """
    # Check for required categorical columns
    required = ['mandi_name', 'district', 'state', 'variety']
    missing = [col for col in required if col not in features.index]
    if missing:
        raise ValueError(f"Missing required model feature columns for SHAP: {missing}")
    
    # Prepare the feature DataFrame
    feature_df = features[feature_names].to_frame().T
    
    # Fix model categorical features to avoid SHAP error
    if 'categorical_feature' in model.params:
        model.params['categorical_feature'] = []
    
    # 1. Initialize the SHAP TreeExplainer
    explainer = shap.TreeExplainer(model)
    
    # 2. Calculate SHAP values for this specific row
    shap_values = explainer.shap_values(feature_df)
    
    # For LightGBM regression, shap_values is typically a 2D array: [num_samples, num_features]
    # We take the first row since we only passed in one sample
    if isinstance(shap_values, list):
        # Handle older shap/lightgbm version list format
        row_shap_values = shap_values[0][0]
    else:
        row_shap_values = shap_values[0]
    
    # For shap.Explainer, shap_values is already the array
    row_shap_values = shap_values
        
    # 3. Create a list of (feature_name, shap_value) and sort by absolute magnitude
    feature_impacts = list(zip(feature_names, row_shap_values))
    feature_impacts.sort(key=lambda x: abs(x[1]), reverse=True)
    
    # 4. Extract the top N contributing features
    top_features = feature_impacts[:top_n]
    
    # 5. Build the Natural Language Explanation
    reasons = []
    for feat, impact in top_features:
        # Translate the feature name if it exists in our dictionary, otherwise use raw name
        friendly_name = FEATURE_TRANSLATIONS.get(feat, feat.replace('_', ' '))
        
        # Determine if this feature drove the price UP or DOWN
        direction = "pushing the price UP" if impact > 0 else "driving the price DOWN"
        
        reasons.append(f"• {friendly_name.capitalize()} is {direction}.")
        
    explanation = "Based on our AI analysis, the top factors influencing this forecast are:\n"
    explanation += "\n".join(reasons)
    
    return explanation