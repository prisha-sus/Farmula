import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
from streamlit_geolocation import streamlit_geolocation
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from dotenv import load_dotenv
load_dotenv()

from src.msp_data import get_msp_status
from src.live_prices import get_latest_prices
from src.db_utils import engine
from sqlalchemy import text
from streamlit_app.theme import get_theme, inject_theme_css

inject_theme_css()
t = get_theme()

FASTAPI_URL = os.getenv("FASTAPI_URL", "http://127.0.0.1:8001")

COMMODITY_DISTRICT = {
    "Onion":    "nashik",
    "Potato":   "pune",
    "Soyabean": "amravati",
}

if "farmer_lat" not in st.session_state:
    st.session_state.farmer_lat = 18.65
if "farmer_lon" not in st.session_state:
    st.session_state.farmer_lon = 73.80
if "show_results" not in st.session_state:
    st.session_state.show_results = False


@st.cache_data(ttl=3600)
def cached_get_latest_prices(district: str, commodity: str):
    return get_latest_prices(district, commodity)


def show_best_market_preview(district: str, commodity: str):
    df = cached_get_latest_prices(district, commodity)
    if df.empty or len(df) < 2:
        return
    best = df.loc[df["modal_price"].idxmax()]
    district_avg = df["modal_price"].mean()
    advantage = best["modal_price"] - district_avg
    spread = best["modal_price"] - df.loc[df["modal_price"].idxmin(), "modal_price"]
    st.success(
        f"💡 **Best price today:** {best['market']} at ₹{best['modal_price']:,.0f}/q — "
        f"₹{advantage:,.0f} above district average · "
        f"₹{spread:,.0f} spread across {len(df)} mandis"
    )


st.title("Market Optimizer")
st.caption("Find the highest net-profit mandi for your crop and location")

with st.container(border=True):
    col1, col2, col3 = st.columns([1, 1, 1.5])
    with col1:
        commodity = st.selectbox("🌾 Crop", ["Onion", "Potato", "Soyabean"])
    with col2:
        horizon = st.selectbox(
            "📅 Selling Horizon",
            [1, 7, 15, 30],
            format_func=lambda x: f"In {x} Day{'s' if x > 1 else ''}",
        )
    with col3:
        st.markdown("**📍 Farm Location (GPS)**")
        location = streamlit_geolocation()
        if location and location.get("latitude") is not None:
            st.session_state.farmer_lat = location["latitude"]
            st.session_state.farmer_lon = location["longitude"]
            st.success(
                f"GPS Locked: {round(st.session_state.farmer_lat, 4)}, "
                f"{round(st.session_state.farmer_lon, 4)}"
            )
        else:
            st.info(
                f"Using coordinates: {round(st.session_state.farmer_lat, 4)}, "
                f"{round(st.session_state.farmer_lon, 4)}"
            )

st.write("")
_, col_center, _ = st.columns([1, 2, 1])
with col_center:
    if st.button("🚀 Optimize My Market Route", use_container_width=True):
        st.session_state.show_results = True

st.divider()

if not st.session_state.show_results:
    rec_district = COMMODITY_DISTRICT.get(commodity, "pune")
    show_best_market_preview(rec_district, commodity.lower())

else:
    if st.button("← Back to Dashboard"):
        st.session_state.show_results = False
        st.switch_page("streamlit_app/pages/dashboard.py")

    with st.spinner("Satellite routing, market forecasting, and AI analysis in progress..."):
        payload = {
            "farmer_lat": st.session_state.farmer_lat,
            "farmer_lon": st.session_state.farmer_lon,
            "horizon": horizon,
            "commodity": commodity.lower(),
        }
        try:
            response = requests.post(f"{FASTAPI_URL}/get_recommendation", json=payload, timeout=30)

            if response.status_code == 200:
                data = response.json()

                st.success(f"### 🏆 Optimal Destination: {data['recommended_mandi']} Mandi")

                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Highest Net Profit", f"₹ {data['net_price_p50']}/qtl", delta="Optimized", delta_color="normal")
                m2.metric("Gross Market Rate", f"₹ {data['gross_price_p50']}/qtl")
                m3.metric("Transport Cost", f"₹ {round(data['transport_cost'], 1)}/qtl")
                m4.metric("Distance Traveled", f"{round(data['distance_km'], 1)} km")

                modal_price = data["gross_price_p50"]
                msp_status = get_msp_status(commodity.lower(), modal_price)
                if msp_status["has_msp"]:
                    color = "🟢" if msp_status["status"] == "above" else "🔴"
                    st.info(
                        f"{color} **MSP comparison:** Current price ₹{modal_price:,.0f}/q · "
                        f"MSP ₹{msp_status['msp']:,}/q ({msp_status['season']}) · "
                        f"{msp_status['message']}"
                    )
                else:
                    st.caption(f"ℹ️ {msp_status['message']}")

                st.write("")
                tab1, tab2, tab3 = st.tabs(
                    ["📊 Market Analytics", "🧠 AI Explanation (SHAP)", "📜 Recommendation History"]
                )

                with tab1:
                    st.markdown("#### 📉 Price Risk Bounds (80% Confidence)")
                    st.info(
                        f"The actual gross price at {data['recommended_mandi']} is highly likely "
                        f"to fall between **{data['confidence_interval']}**."
                    )
                    bounds = [
                        float(x.replace("₹", "").strip())
                        for x in data["confidence_interval"].split("-")
                    ]
                    fig = go.Figure()
                    fig.add_trace(go.Bar(
                        x=["Predicted Price Spread"],
                        y=[bounds[1] - bounds[0]],
                        base=[bounds[0]],
                        marker_color=t["primary"],
                        name="80% Confidence Interval",
                        text=f"Expected: ₹{data['gross_price_p50']}",
                        textposition="auto",
                    ))
                    fig.update_layout(
                        title=f"{commodity} Price Projection — {data['recommended_mandi']}",
                        yaxis_title="Price (₹ / qtl)",
                        plot_bgcolor=t["plotly_bg"],
                        paper_bgcolor=t["plotly_paper"],
                        font=dict(color=t["text"]),
                        showlegend=False,
                    )
                    st.plotly_chart(fig, use_container_width=True)

                with tab2:
                    st.markdown("#### 🤖 Why did the AI choose this price?")
                    with st.container(border=True):
                        st.markdown(f"*{data['explanation']}*")
                        st.caption(
                            "Generated via SHAP (SHapley Additive exPlanations) "
                            "on LightGBM tree architecture."
                        )

                with tab3:
                    st.markdown("#### Recent Market Data")
                    try:
                        with engine.connect() as conn:
                            result = conn.execute(
                                text("""
                                    SELECT market, date, modal_price, min_price, max_price
                                    FROM mandi_prices
                                    WHERE commodity ILIKE :commodity
                                    ORDER BY date DESC
                                    LIMIT 20
                                """),
                                {"commodity": f"%{commodity.lower()}%"},
                            )
                            df_hist = pd.DataFrame(result.fetchall(), columns=result.keys())
                        if df_hist.empty:
                            st.info("No history found for this commodity.")
                        else:
                            df_hist["date"] = pd.to_datetime(df_hist["date"]).dt.strftime("%Y-%m-%d")
                            st.dataframe(df_hist, use_container_width=True, hide_index=True)
                    except Exception as e:
                        st.warning(f"Could not load history: {e}")

            else:
                st.error("⚠️ Backend Error: Ensure database is populated.")
                st.json(response.json())

        except requests.exceptions.ConnectionError:
            st.error(
                f"🚨 Connection Failed. Ensure the FastAPI backend is running at {FASTAPI_URL}."
            )
        except requests.exceptions.Timeout:
            st.error("🚨 Request timed out. The backend may be under load — try again.")
