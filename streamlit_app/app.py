"""
Frontend Streamlit Dashboard for Farmula DSS.
Interacts with the FastAPI backend to display logistics, forecasts, and XAI.
"""

import streamlit as st
import requests

# Set page configuration
st.set_page_config(page_title="Farmula DSS", page_icon="🧅", layout="wide")

# API Endpoint
API_URL = "http://127.0.0.1:8000/get_recommendation"

# --- UI Header ---
st.title("🌾 Farmula: AI Market Intelligence & Logistics DSS")
st.markdown("Optimized for **Onion** | Region: **Pune District, Maharashtra**")
st.divider()

# --- Sidebar Inputs ---
st.sidebar.header("📍 Farmer Details")
st.sidebar.markdown("Enter your farm's GPS coordinates:")

# Defaulting roughly to a farm outside Pune for testing
farmer_lat = st.sidebar.number_input("Latitude", value=18.6500, format="%.4f")
farmer_lon = st.sidebar.number_input("Longitude", value=73.8000, format="%.4f")

st.sidebar.header("📅 Forecast Horizon")
horizon = st.sidebar.selectbox(
    "When do you plan to sell?",
    options=[1, 7, 15, 30],
    format_func=lambda x: f"In {x} Day(s)"
)

if st.sidebar.button("🚀 Get Market Recommendation", type="primary", use_container_width=True):
    
    with st.spinner("Analyzing markets, calculating logistics, and generating AI insights..."):
        
        # Prepare the payload for the FastAPI backend
        payload = {
            "farmer_lat": farmer_lat,
            "farmer_lon": farmer_lon,
            "horizon": horizon
        }
        
        try:
            # Send request to FastAPI
            response = requests.post(API_URL, json=payload)
            
            if response.status_code == 200:
                data = response.json()
                
                # --- Success Display ---
                st.success(f"### 🏆 Top Recommended Market: {data['recommended_mandi']} Mandi")
                
                # Metrics Row
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Expected Net Price (After Freight)", f"₹ {data['net_price_p50']} / qtl")
                col2.metric("Gross Market Price", f"₹ {data['gross_price_p50']} / qtl")
                col3.metric("Distance to Market", f"{round(data['distance_km'], 1)} km")
                col4.metric("Est. Transport Cost", f"₹ {round(data['transport_cost'], 1)} / qtl")
                
                # Confidence Interval & Risk
                st.info(f"**📉 Risk Bounds (80% Confidence):** The actual gross price is highly likely to fall between **{data['confidence_interval']}**.")
                
                st.divider()
                
                # SHAP Explainability Section
                st.subheader("🧠 Why is the AI predicting this?")
                st.markdown(data['explanation'])
                
            elif response.status_code == 500:
                error_detail = response.json().get('detail', 'Unknown error')
                st.error("⚠️ The Backend reported an error. Have you hydrated the database yet?")
                st.code(error_detail)
            else:
                st.error(f"Failed to fetch recommendation. Status Code: {response.status_code}")
                
        except requests.exceptions.ConnectionError:
            st.error("🚨 Could not connect to the backend. Is FastAPI (uvicorn) running on port 8000?")