import streamlit as st
import pandas as pd
import requests
import plotly.graph_objects as go
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from src.live_prices import get_latest_prices, get_data_freshness
from src.db_utils import engine
from src.inference import generate_batch_forecasts
from streamlit_app.theme import get_theme, inject_theme_css

inject_theme_css()
t = get_theme()

COMMODITY_DISTRICT = {
    "Onion":    ("nashik",   "onion"),
    "Potato":   ("pune",     "potato"),
    "Soyabean": ("amravati", "soyabean"),
}

if "farmer_lat" not in st.session_state:
    st.session_state.farmer_lat = 18.65
if "farmer_lon" not in st.session_state:
    st.session_state.farmer_lon = 73.80

st.title("Dashboard")
st.caption("Live market overview across Maharashtra mandis")

freshness = get_data_freshness()
if freshness.get("has_data"):
    if freshness["days_ago"] == 0:
        st.caption(f"✅ Prices as of today · {freshness['record_count']:,} records")
    elif freshness["days_ago"] <= 3:
        st.caption(f"🕐 Last updated {freshness['latest_date']} · {freshness['days_ago']} days ago")
    else:
        st.warning(f"⚠️ Data last updated {freshness['latest_date']} ({freshness['days_ago']} days ago)")

st.markdown("---")


@st.cache_data(ttl=300)
def get_forecast_preview(commodity_key: str) -> dict | None:
    try:
        df = pd.read_sql("SELECT * FROM latest_mandi_features", engine)
        if df.empty:
            return None
        forecasts = generate_batch_forecasts(df, commodity=commodity_key, horizon=1)
        if not forecasts:
            return None
        p50_avg = sum(v["p50"] for v in forecasts.values()) / len(forecasts)
        p10_min = min(v["p10"] for v in forecasts.values())
        p90_max = max(v["p90"] for v in forecasts.values())
        return {"p10": round(p10_min), "p50": round(p50_avg), "p90": round(p90_max)}
    except Exception:
        return None


st.subheader("Predicted prices — tomorrow (1-day forecast)")

cols = st.columns(3)
for col, (commodity_label, (district, commodity_key)) in zip(cols, COMMODITY_DISTRICT.items()):
    with col:
        df_live = get_latest_prices(district, commodity_key)
        current_price = float(df_live["modal_price"].mean()) if not df_live.empty else None
        forecast = get_forecast_preview(commodity_key)

        if forecast:
            p50, p10, p90 = forecast["p50"], forecast["p10"], forecast["p90"]
            delta_str = ""
            if current_price:
                delta = p50 - current_price
                delta_str = f"₹{abs(delta):,.0f} {'↑' if delta >= 0 else '↓'} vs today"
            st.markdown(f"""
                <div class="price-card">
                    <div class="commodity">{commodity_label} · {district.title()}</div>
                    <div class="price">₹{p50:,.0f}</div>
                    <div class="label">p10: ₹{p10:,.0f} — p90: ₹{p90:,.0f}</div>
                    <div class="label">{delta_str}</div>
                </div>
            """, unsafe_allow_html=True)
        elif current_price:
            st.markdown(f"""
                <div class="price-card">
                    <div class="commodity">{commodity_label} · {district.title()}</div>
                    <div class="price">₹{current_price:,.0f}</div>
                    <div class="label">Current market price</div>
                    <div class="label">Forecast unavailable</div>
                </div>
            """, unsafe_allow_html=True)
        else:
            st.info(f"No data for {commodity_label}")

st.markdown("---")
st.subheader("Farm location")

map_col, weather_col = st.columns([2, 1])
farmer_lat = st.session_state.farmer_lat
farmer_lon = st.session_state.farmer_lon

with map_col:
    fig = go.Figure(go.Scattermapbox(
        lat=[farmer_lat],
        lon=[farmer_lon],
        mode="markers",
        marker=dict(size=14, color=t["primary"]),
        text=["Your farm location"],
    ))
    fig.update_layout(
        mapbox=dict(
            style=t["map_style"],
            center=dict(lat=farmer_lat, lon=farmer_lon),
            zoom=9,
        ),
        margin=dict(l=0, r=0, t=0, b=0),
        height=320,
        paper_bgcolor=t["plotly_paper"],
    )
    st.plotly_chart(fig, use_container_width=True)

with weather_col:
    with st.container(border=True):
        st.markdown("#### Current weather")
        try:
            url = (
                f"https://api.open-meteo.com/v1/forecast"
                f"?latitude={farmer_lat}&longitude={farmer_lon}&current_weather=true"
            )
            weather = requests.get(url, timeout=5).json().get("current_weather")
            if weather:
                st.metric("Temperature", f"{weather['temperature']} °C")
                st.metric("Wind speed", f"{weather['windspeed']} km/h")
            else:
                st.info("Weather unavailable")
        except Exception:
            st.info("Weather unavailable")

    st.markdown(" ")
    st.markdown("#### Quick navigate")
    if st.button("🚀 Optimize my route", use_container_width=True):
        st.switch_page("streamlit_app/pages/optimizer.py")
    if st.button("📈 View price forecasts", use_container_width=True):
        st.switch_page("streamlit_app/pages/forecast.py")
