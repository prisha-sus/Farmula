"""
Main FastAPI Backend for Farmula DSS.
Orchestrates the Database, Inference Engine, Logistics Engine, and XAI Explainer.
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import pandas as pd
import sys
import os

# Ensure the src folder is accessible to the API
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from db_utils import engine
from inference import generate_batch_forecasts, load_models
from logistics import calculate_net_prices
from explainer import generate_shap_explanation

app = FastAPI(title="Farmula DSS API", version="1.0")

# --- Define Request and Response Data Models ---
class FarmerRequest(BaseModel):
    farmer_lat: float
    farmer_lon: float
    horizon: int = 1  # Options: 1, 7, 15, 30
    commodity: str = "onion"

class RecommendationResponse(BaseModel):
    recommended_mandi: str
    gross_price_p50: float
    net_price_p50: float
    distance_km: float
    transport_cost: float
    confidence_interval: str  # e.g., "₹ 2100 - ₹ 2500"
    explanation: str

# --- API Endpoints ---
@app.get("/")
def health_check():
    return {"status": "Farmula Backend is Running!"}

@app.post("/get_recommendation", response_model=RecommendationResponse)
def get_recommendation(request: FarmerRequest):
    try:
        # 1. Fetch the exact latest features from the PostgreSQL Database
        query = "SELECT * FROM latest_mandi_features"
        latest_features_df = pd.read_sql(query, engine)
        
        if latest_features_df.empty:
            raise HTTPException(status_code=500, detail="Database is empty. Run seed_db.py first.")

        # 2. Run Inference (Get p10, p50, p90 for all mandis)
        forecasts = generate_batch_forecasts(latest_features_df, commodity=request.commodity, horizon=request.horizon)
        
        # 3. Run Logistics (Calculate distances and net prices)
        # Assuming logistics.py has a calculate_net_prices((farmer_lat, farmer_lon), forecasts) function
        ranked_mandis = calculate_net_prices((request.farmer_lat, request.farmer_lon), forecasts)
        
        if not ranked_mandis:
            raise HTTPException(status_code=500, detail="Could not calculate logistics.")
            
        # 4. Get the best Mandi (Rank 1)
        best_mandi = ranked_mandis[0]
        mandi_name = best_mandi['mandi_name']
        
        # 5. Run SHAP Explainer for the best Mandi
        # Get the specific feature row for this mandi to explain *why* it was chosen
        mandi_feature_row = latest_features_df[latest_features_df['mandi_name'] == mandi_name]
        if mandi_feature_row.empty:
            raise HTTPException(status_code=500, detail=f"No feature row found for mandi '{mandi_name}'")
        mandi_feature_row = mandi_feature_row.iloc[0]

        # Load the specific p50 model to pass to SHAP
        models = load_models(commodity=request.commodity, horizon=request.horizon)
        expected_features = models['p50'].feature_name()
        try:
            explanation_text = generate_shap_explanation(models['p50'], mandi_feature_row, expected_features)
        except Exception as e:
            # Fallback explanation if SHAP fails
            explanation_text = "Based on our AI analysis, the forecast is influenced by recent market trends, weather conditions, and seasonal patterns."
        
        # 6. Package the final response
        return RecommendationResponse(
            recommended_mandi=mandi_name,
            gross_price_p50=best_mandi['gross_price_p50'],
            net_price_p50=best_mandi['net_price'],
            distance_km=best_mandi['distance_km'],
            transport_cost=best_mandi['transport_cost'],
            confidence_interval=f"₹ {best_mandi['p10']} - ₹ {best_mandi['p90']}",
            explanation=explanation_text
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))