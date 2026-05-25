# -*- coding: utf-8 -*-
"""
Main FastAPI Backend for Farmula DSS.
Orchestrates the Database, Inference Engine, Logistics Engine, and XAI Explainer.
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, JSONResponse
from pydantic import BaseModel
from authlib.integrations.starlette_client import OAuth
from starlette.middleware.sessions import SessionMiddleware
from itsdangerous import URLSafeTimedSerializer
import pandas as pd
import httpx
import sys
import os
from typing import Optional
from dotenv import load_dotenv
from sqlalchemy import text

load_dotenv()

# Ensure the src folder is first on the path regardless of launch directory
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from db_utils import engine, upsert_google_user, verify_user, create_user
from inference import generate_batch_forecasts, load_models
from logistics import calculate_net_prices
from explainer import generate_shap_explanation
from live_prices import get_latest_prices
from msp_data import get_msp_status
from sms_service import send_sms, build_message
from commodity_registry import (
    get_available_districts,
    get_commodities_for_district,
    has_forecast as commodity_has_forecast,
)

app = FastAPI(title="Farmula DSS API", version="1.0")

cors_origins = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8501,http://127.0.0.1:8501",
    ).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SESSION_SECRET_KEY", "farmula-secret-key-change-in-prod")
)

# ---------------------------------------------------------------------------
# Google OAuth via Authlib
# ---------------------------------------------------------------------------
oauth = OAuth()
oauth.register(
    name="google",
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"}
)

# Signs tokens sent back to Streamlit so the frontend can verify them
serializer = URLSafeTimedSerializer(
    os.getenv("SESSION_SECRET_KEY", "farmula-secret-key-change-in-prod")
)

# ---------------------------------------------------------------------------
# Define Request and Response Data Models
# ---------------------------------------------------------------------------
class FarmerRequest(BaseModel):
    farmer_lat: float
    farmer_lon: float
    horizon: int = 1   # Options: 1, 7, 15, 30
    commodity: str = "onion"

class RecommendationResponse(BaseModel):
    recommended_mandi: str
    gross_price_p50: float
    net_price_p50: float
    distance_km: float
    transport_cost: float
    confidence_interval: str   # e.g., "₹ 2100 - ₹ 2500"
    explanation: str


class LoginRequest(BaseModel):
    email: str
    password: str


class SignupRequest(BaseModel):
    name: str
    email: str
    password: str


class WeatherRequest(BaseModel):
    farmer_lat: float
    farmer_lon: float


class SMSTestRequest(BaseModel):
    phone_number: str
    language: str = "en"
    user_email: Optional[str] = None


class AlertSubscriptionRequest(BaseModel):
    user_email: str
    phone_number: str
    commodity: str
    district: str
    language: str = "en"
    alert_type: str
    threshold_price: Optional[float] = None


class HarvestRecommendationRequest(BaseModel):
    commodity: str
    district: str
    horizon: int = 7
    phone_number: Optional[str] = None
    language: str = "en"
    user_email: Optional[str] = None


class TraderCompareRequest(BaseModel):
    commodity: str
    district: str
    trader_offer: float

# ---------------------------------------------------------------------------
# Core endpoints
# ---------------------------------------------------------------------------
@app.get("/")
def health_check():
    return {"status": "Farmula Backend is Running!"}


@app.post("/auth/email/login")
def email_login(request: LoginRequest):
    """Email/password login for the React dashboard."""
    if not request.email or not request.password:
        raise HTTPException(status_code=400, detail="Email and password are required")

    try:
        user = verify_user(request.email, request.password)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Login failed: {str(e)}")

    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    return {"user": user}


@app.post("/auth/email/signup")
def email_signup(request: SignupRequest):
    """Email/password signup for the React dashboard."""
    if not request.name or not request.email or not request.password:
        raise HTTPException(status_code=400, detail="Name, email, and password are required")
    if len(request.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    try:
        user = create_user(request.email, request.name, request.password)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Signup failed: {str(e)}")

    return {"user": user}


@app.get("/auth/login")
async def login(request: Request):
    """Redirects the user to Google's OAuth consent screen."""
    redirect_uri = os.getenv("OAUTH_REDIRECT_URI", "http://localhost:8000/auth/callback")
    return await oauth.google.authorize_redirect(request, redirect_uri)


@app.get("/auth/callback")
async def auth_callback(request: Request):
    """
    Handles the Google OAuth callback.
    Exchanges the auth code for user info, signs a short-lived token,
    and redirects back to Streamlit with the token as a query param.
    """
    try:
        token = await oauth.google.authorize_access_token(request)
        user_info = token.get("userinfo")
        if not user_info:
            raise HTTPException(status_code=400, detail="Could not fetch user info")

        # Persist / update the user in the unified users table
        upsert_google_user(
            email=user_info["email"],
            name=user_info.get("name", ""),
            picture=user_info.get("picture", "")
        )

        # Sign a payload containing user identity — Streamlit verifies this
        signed_token = serializer.dumps({
            "email":   user_info["email"],
            "name":    user_info.get("name", ""),
            "picture": user_info.get("picture", "")
        })

        frontend_url = os.getenv("FRONTEND_URL", os.getenv("STREAMLIT_URL", "http://localhost:5173"))
        return RedirectResponse(f"{frontend_url}/?auth_token={signed_token}")

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"OAuth failed: {str(e)}")


@app.get("/auth/verify")
async def verify_token(token: str):
    """
    Verifies a signed auth token. Called by Streamlit after receiving the
    redirect to confirm the token is genuine and unexpired (8-hour TTL).
    """
    try:
        user_data = serializer.loads(token, max_age=28800)   # 8 hours
        return JSONResponse({"valid": True, "user": user_data})
    except Exception:
        return JSONResponse({"valid": False, "user": None})


@app.get("/market/freshness")
def market_freshness():
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT MAX(date) as latest_date, COUNT(*) as record_count,
                       COUNT(DISTINCT LOWER(district)) as district_count,
                       COUNT(DISTINCT LOWER(commodity)) as commodity_count
                FROM mandi_prices
            """)).fetchone()
            if not result or not result.latest_date:
                return {"has_data": False}
            from datetime import date
            latest    = result.latest_date
            days_ago  = (date.today() - latest).days
            districts = get_available_districts()
            return {
                "has_data":        True,
                "latest_date":     str(latest),
                "days_ago":        days_ago,
                "record_count":    int(result.record_count),
                "district_count":  len(districts),
                "commodity_count": int(result.commodity_count),
            }
    except Exception:
        return {"has_data": False}


@app.get("/market/districts")
def list_districts():
    """Returns all districts with available price data."""
    districts = get_available_districts()
    return {"districts": districts, "count": len(districts)}


@app.get("/market/commodities")
def list_commodities(district: str):
    """
    Returns commodities available for a district,
    ranked by data volume, with forecast availability flag.
    """
    commodities = get_commodities_for_district(district)
    return {
        "district":      district,
        "commodities":   commodities,
        "total":         len(commodities),
        "with_forecast": sum(1 for c in commodities if c["has_forecast"]),
    }


@app.get("/market/forecast-availability")
def forecast_availability(commodity: str, district: str):
    """Check if a specific commodity-district pair has trained models."""
    available = commodity_has_forecast(commodity, district)
    return {
        "commodity":   commodity,
        "district":    district,
        "has_forecast": available,
        "message": None if available else (
            "Live prices available. AI forecast not yet trained for this pair."
        ),
    }


@app.get("/market/latest-prices")
def latest_prices(district: str, commodity: str):
    df = get_latest_prices(district, commodity)
    if df.empty:
        return {"prices": []}

    result = df.copy()
    result["date"] = result["date"].astype(str)
    return {"prices": result.to_dict(orient="records")}


@app.get("/market/best-price")
def best_market_price(district: str, commodity: str):
    df = get_latest_prices(district, commodity)
    if df.empty or len(df) < 2:
        return {"available": False, "message": "Not enough live price data available"}

    best = df.loc[df["modal_price"].idxmax()]
    worst = df.loc[df["modal_price"].idxmin()]
    district_avg = float(df["modal_price"].mean())

    return {
        "available": True,
        "best_market": best["market"],
        "best_price": float(best["modal_price"]),
        "worst_market": worst["market"],
        "worst_price": float(worst["modal_price"]),
        "district_average": district_avg,
        "advantage": float(best["modal_price"] - district_avg),
        "spread": float(best["modal_price"] - worst["modal_price"]),
        "market_count": int(len(df)),
        "date": str(best["date"]),
    }


@app.get("/msp/status")
def msp_status(commodity: str, current_price: float):
    return get_msp_status(commodity, current_price)


@app.post("/weather/current")
async def current_weather(request: WeatherRequest):
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                "https://api.open-meteo.com/v1/forecast",
                params={
                    "latitude": request.farmer_lat,
                    "longitude": request.farmer_lon,
                    "current_weather": "true",
                },
            )
            response.raise_for_status()
            return {"weather": response.json().get("current_weather")}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Weather data unavailable: {str(e)}")


@app.post("/get_recommendation", response_model=RecommendationResponse)
def get_recommendation(request: FarmerRequest):
    try:
        # 1. Fetch the exact latest features from the PostgreSQL Database
        query = "SELECT * FROM latest_mandi_features"
        latest_features_df = pd.read_sql(query, engine)

        if latest_features_df.empty:
            raise HTTPException(
                status_code=500,
                detail="Database is empty. Run seed_db.py first."
            )

        # 2. Run Inference (Get p10, p50, p90 for all mandis)
        # commodity is already the commodity_key (lowercase, underscores) from the frontend
        commodity_key = request.commodity.lower().replace(" ", "_")
        forecasts = generate_batch_forecasts(
            latest_features_df,
            commodity=commodity_key,
            horizon=request.horizon
        )

        # 3. Run Logistics (Calculate distances and net prices)
        ranked_mandis = calculate_net_prices(
            (request.farmer_lat, request.farmer_lon), forecasts
        )

        if not ranked_mandis:
            raise HTTPException(status_code=500, detail="Could not calculate logistics.")

        # 4. Get the best Mandi (Rank 1)
        best_mandi = ranked_mandis[0]
        mandi_name = best_mandi['mandi_name']

        # 5. Run SHAP Explainer for the best Mandi
        mandi_feature_row = latest_features_df[
            latest_features_df['mandi_name'] == mandi_name
        ]
        if mandi_feature_row.empty:
            raise HTTPException(
                status_code=500,
                detail=f"No feature row found for mandi '{mandi_name}'"
            )
        mandi_feature_row = mandi_feature_row.iloc[0]

        models = load_models(commodity=commodity_key, horizon=request.horizon)
        expected_features = models['p50'].feature_name()
        try:
            explanation_text = generate_shap_explanation(
                models['p50'], mandi_feature_row, expected_features
            )
        except Exception:
            explanation_text = (
                "Based on our AI analysis, the forecast is influenced by recent "
                "market trends, weather conditions, and seasonal patterns."
            )

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


@app.post("/sms/test")
def test_sms(request: SMSTestRequest):
    """Send a test SMS to verify the integration works."""
    test_messages = {
        "en": "Farmula test message: Your SMS alerts are now active. You will receive price updates in English.",
        "hi": "फार्मूला परीक्षण संदेश: आपके SMS अलर्ट अब सक्रिय हैं. आपको हिंदी में मूल्य अपडेट प्राप्त होंगे.",
        "mr": "फार्मुला चाचणी संदेश: तुमचे SMS अलर्ट आता सक्रिय आहेत. तुम्हाला मराठीत किंमत अपडेट मिळतील.",
    }
    lang = (request.language or "en").lower()
    message = test_messages.get(lang, test_messages["en"])
    result = send_sms(request.phone_number, message, lang, request.user_email)

    if result["success"]:
        return {"success": True, "message": "Test SMS sent successfully"}
    raise HTTPException(status_code=400, detail=result["error"])


@app.post("/alerts/subscribe")
def subscribe_alert(request: AlertSubscriptionRequest):
    """Create or update an SMS alert subscription."""
    valid_alert_types = {"daily_price", "price_threshold", "harvest_recommendation"}
    if request.alert_type not in valid_alert_types:
        raise HTTPException(status_code=400, detail="Invalid alert_type")

    try:
        with engine.connect() as conn:
            conn.execute(
                text(
                    """
                INSERT INTO user_alert_preferences
                    (user_email, phone_number, commodity, district, language, alert_type, threshold_price, is_active)
                VALUES (:email, :phone, :commodity, :district, :lang, :type, :threshold, TRUE)
                ON CONFLICT (user_email, commodity, district, alert_type)
                DO UPDATE SET
                    phone_number = EXCLUDED.phone_number,
                    language = EXCLUDED.language,
                    threshold_price = EXCLUDED.threshold_price,
                    is_active = TRUE
            """
                ),
                {
                    "email": request.user_email,
                    "phone": request.phone_number,
                    "commodity": request.commodity.lower(),
                    "district": request.district.lower(),
                    "lang": (request.language or "en").lower(),
                    "type": request.alert_type,
                    "threshold": request.threshold_price,
                },
            )
            conn.commit()
        return {"success": True, "message": "Alert subscription saved"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/alerts/list")
def list_user_alerts(user_email: str):
    """List all active alerts for a user."""
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text(
                    """
                SELECT id, commodity, district, alert_type, threshold_price, language, is_active, created_at
                FROM user_alert_preferences
                WHERE user_email = :email
                ORDER BY created_at DESC
            """
                ),
                {"email": user_email},
            ).fetchall()

            alerts = [
                {
                    "id": row.id,
                    "commodity": row.commodity,
                    "district": row.district,
                    "alert_type": row.alert_type,
                    "threshold_price": row.threshold_price,
                    "language": row.language,
                    "is_active": row.is_active,
                    "created_at": str(row.created_at),
                }
                for row in result
            ]
            return {"alerts": alerts}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/alerts/{alert_id}")
def delete_alert(alert_id: int):
    """Delete an alert subscription."""
    try:
        with engine.connect() as conn:
            conn.execute(text("DELETE FROM user_alert_preferences WHERE id = :id"), {"id": alert_id})
            conn.commit()
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/harvest/recommendation")
def harvest_recommendation(request: HarvestRecommendationRequest):
    """
    Returns SELL NOW vs HOLD recommendation based on price forecast.
    Optionally sends SMS in user's language.
    """
    try:
        commodity = request.commodity.lower()
        district = request.district.lower()
        language = (request.language or "en").lower()

        with engine.connect() as conn:
            result = conn.execute(
                text(
                    """
                SELECT AVG(modal_price) as today_price,
                       (SELECT market FROM mandi_prices
                        WHERE LOWER(commodity) = LOWER(:commodity)
                          AND LOWER(district) = LOWER(:district)
                        ORDER BY date DESC, modal_price DESC LIMIT 1) as best_market
                FROM mandi_prices
                WHERE LOWER(commodity) = LOWER(:commodity)
                  AND LOWER(district) = LOWER(:district)
                  AND date >= CURRENT_DATE - INTERVAL '3 days'
            """
                ),
                {"commodity": request.commodity, "district": request.district},
            ).fetchone()

        if not result or not result.today_price:
            raise HTTPException(status_code=404, detail="No recent price data for this commodity-district")

        today_price = float(result.today_price)
        best_market = result.best_market or request.district.title()

        latest_features_df = pd.read_sql("SELECT * FROM latest_mandi_features", engine)
        if latest_features_df.empty:
            raise HTTPException(status_code=500, detail="Forecast features unavailable")

        if "commodity" in latest_features_df.columns:
            non_null = latest_features_df["commodity"].dropna()
            if not non_null.empty:
                latest_features_df = latest_features_df[
                    latest_features_df["commodity"].astype(str).str.lower() == commodity
                ]
        if "district" in latest_features_df.columns:
            district_filtered = latest_features_df[
                latest_features_df["district"].astype(str).str.lower() == district
            ]
            if not district_filtered.empty:
                latest_features_df = district_filtered

        if latest_features_df.empty:
            raise HTTPException(status_code=500, detail="No matching forecast features for this commodity-district")

        forecasts = generate_batch_forecasts(
            latest_features_df,
            commodity=commodity,
            horizon=request.horizon,
        )

        if not forecasts:
            raise HTTPException(status_code=500, detail="Could not generate forecast")

        if isinstance(forecasts, dict):
            p50_values = [row.get("p50") for row in forecasts.values() if row and row.get("p50") is not None]
        else:
            p50_values = [row.get("p50") for row in forecasts if row and row.get("p50") is not None]

        if not p50_values:
            raise HTTPException(status_code=500, detail="Forecast did not include p50 values")

        future_p50 = sum(p50_values) / len(p50_values)
        change_pct = ((future_p50 - today_price) / today_price) * 100

        if change_pct < -3:
            recommendation = "sell_now"
            message_key = "harvest_sell_now"
        elif change_pct > 3:
            recommendation = "hold"
            message_key = "harvest_hold"
        else:
            recommendation = "neutral"
            message_key = "harvest_hold" if change_pct >= 0 else "harvest_sell_now"

        message = build_message(
            message_key,
            language,
            commodity=commodity,
            today=int(today_price),
            future=int(future_p50),
            horizon=request.horizon,
            change=abs(round(change_pct, 1)),
        )

        sms_result = None
        if request.phone_number:
            sms_result = send_sms(request.phone_number, message, language, request.user_email)

        return {
            "recommendation": recommendation,
            "today_price": round(today_price, 2),
            "future_price_p50": round(future_p50, 2),
            "change_pct": round(change_pct, 2),
            "horizon": request.horizon,
            "best_market": best_market,
            "message": message,
            "sms_sent": sms_result["success"] if sms_result else False,
            "sms_error": sms_result.get("error") if sms_result and not sms_result["success"] else None,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/trader/compare")
def trader_compare(request: TraderCompareRequest):
    """
    Compare a trader's offer against actual mandi rates.
    Returns difference + recommendation.
    """
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text(
                    """
                SELECT AVG(modal_price) as avg_mandi_price,
                       MAX(modal_price) as max_mandi_price,
                       MIN(modal_price) as min_mandi_price,
                       COUNT(*) as mandi_count
                FROM mandi_prices
                WHERE LOWER(commodity) = LOWER(:commodity)
                  AND LOWER(district) = LOWER(:district)
                  AND date >= CURRENT_DATE - INTERVAL '3 days'
            """
                ),
                {"commodity": request.commodity, "district": request.district},
            ).fetchone()

        if not result or not result.avg_mandi_price:
            raise HTTPException(status_code=404, detail="No recent mandi data for comparison")

        avg_mandi = float(result.avg_mandi_price)
        max_mandi = float(result.max_mandi_price)
        min_mandi = float(result.min_mandi_price)
        difference = avg_mandi - request.trader_offer
        difference_pct = (difference / avg_mandi) * 100 if avg_mandi > 0 else 0

        if difference > 0:
            verdict = "trader_lower"
            recommendation_key = "Trader is offering less. You could earn more at the mandi."
        elif difference < -50:
            verdict = "trader_higher"
            recommendation_key = "Trader offer is higher than mandi average. Verify the offer is genuine."
        else:
            verdict = "fair"
            recommendation_key = "Trader offer is fair compared to mandi rates."

        return {
            "trader_offer": request.trader_offer,
            "mandi_average": round(avg_mandi, 2),
            "mandi_max": round(max_mandi, 2),
            "mandi_min": round(min_mandi, 2),
            "difference": round(difference, 2),
            "difference_pct": round(difference_pct, 2),
            "verdict": verdict,
            "recommendation": recommendation_key,
            "mandi_count": int(result.mandi_count),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
