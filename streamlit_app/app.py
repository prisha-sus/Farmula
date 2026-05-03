"""
Premium Frontend Streamlit Dashboard for Farmula DSS.
Features: Custom CSS, Geolocation, Live Weather, and Session State Management.
"""

import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
from streamlit_geolocation import streamlit_geolocation

# 1. Page Configuration
st.set_page_config(
    page_title="Farmula DSS | Smart Markets", 
    page_icon="🌾", 
    layout="wide", 
    initial_sidebar_state="collapsed"
)

# 2. Custom CSS Injection
st.markdown("""
    <style>
    [data-testid="collapsedControl"] {display: none;}
    #MainMenu {visibility: hidden;}
    
    .main-title {
        text-align: center;
        font-size: 3.5rem;
        font-weight: 800;
        background: -webkit-linear-gradient(45deg, #166534, #22c55e);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0rem;
    }
    .sub-title {
        text-align: center;
        color: #6b7280;
        font-size: 1.2rem;
        margin-bottom: 2rem;
    }
    
    [data-testid="stMetricValue"] {
        font-size: 2rem !important;
        color: #166534 !important;
        font-weight: bold;
    }
    [data-testid="stMetricLabel"] {
        font-size: 1rem !important;
        color: #4b5563 !important;
    }
    
    .stButton>button {
        background-color: #166534;
        color: white;
        border-radius: 8px;
        padding: 0.75rem 2rem;
        font-size: 1.2rem;
        font-weight: bold;
        transition: all 0.3s ease;
        border: none;
        width: 100%;
    }
    .stButton>button:hover {
        background-color: #15803d;
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(22, 101, 52, 0.3);
    }
    </style>
""", unsafe_allow_html=True)

# --- HELPER FUNCTIONS ---
@st.cache_data(ttl=3600) # Cache weather for 1 hour to save network calls
def get_live_weather(lat, lon):
    try:
        url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true"
        response = requests.get(url).json()
        return response.get('current_weather', None)
    except:
        return None

# --- HERO SECTION ---
st.markdown('<h1 class="main-title">Farmula DSS</h1>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">AI-Powered Geographic Arbitrage & Logistics for Indian Farmers</p>', unsafe_allow_html=True)

# --- INITIALIZE SESSION STATE ---
if 'farmer_lat' not in st.session_state:
    st.session_state.farmer_lat = 18.6500  # Default Pune
if 'farmer_lon' not in st.session_state:
    st.session_state.farmer_lon = 73.8000
if 'show_results' not in st.session_state:
    st.session_state.show_results = False

# --- COMMAND CENTER ---
st.markdown("### 🎛️ Market Parameters")
with st.container(border=True):
    col1, col2, col3 = st.columns([1, 1, 1.5])
    
    with col1:
        commodity = st.selectbox("🌾 Crop", ["Onion", "Potato"])
    with col2:
        horizon = st.selectbox("📅 Selling Horizon", [1, 7, 15, 30], format_func=lambda x: f"In {x} Day{'s' if x > 1 else ''}")
    with col3:
        st.markdown("**📍 Farm Location (GPS)**")
        # Geolocation button
        location = streamlit_geolocation()
        
        # Update session state if GPS is fetched successfully
        if location and location.get('latitude') is not None:
            st.session_state.farmer_lat = location['latitude']
            st.session_state.farmer_lon = location['longitude']
            st.success(f"GPS Locked: {round(st.session_state.farmer_lat, 4)}, {round(st.session_state.farmer_lon, 4)}")
        else:
            st.info(f"Using Default coordinates: {round(st.session_state.farmer_lat, 4)}, {round(st.session_state.farmer_lon, 4)}")

st.write("")

# --- ACTION TRIGGER ---
col_btn_left, col_btn_center, col_btn_right = st.columns([1, 2, 1])
with col_btn_center:
    # When clicked, update session state to show results
    if st.button("🚀 Optimize My Market Route"):
        st.session_state.show_results = True

st.divider()

# --- DYNAMIC UI TOGGLE (EMPTY STATE vs. DASHBOARD) ---

if not st.session_state.show_results:
    # --- EMPTY STATE (Before Button Click) ---
    st.markdown("### 🌍 Farm Overview")
    map_col, weather_col = st.columns([2, 1])
    
    with map_col:
        # Display an interactive map marker at the farmer's location
        df_map = pd.DataFrame({'lat': [st.session_state.farmer_lat], 'lon': [st.session_state.farmer_lon]})
        st.map(df_map, zoom=10, use_container_width=True)
        
    with weather_col:
        # Fetch and display live weather
        with st.container(border=True):
            st.markdown("#### ⛅ Current Weather")
            weather = get_live_weather(st.session_state.farmer_lat, st.session_state.farmer_lon)
            if weather:
                st.metric("Temperature", f"{weather['temperature']} °C")
                st.metric("Wind Speed", f"{weather['windspeed']} km/h")
                st.caption(f"Data sourced locally via Open-Meteo for coordinates.")
            else:
                st.warning("Weather data currently unavailable.")
                
    st.write("")
    st.markdown("#### ⚙️ How Farmula Works")
    st.info("""
    1. **Locate:** We pinpoint your farm using GPS.
    2. **Forecast:** Our LightGBM AI predicts prices for your crop across major mandis for your chosen timeline.
    3. **Deduct:** We calculate the exact logistics and transport costs from your farm to each market.
    4. **Optimize:** We reveal the market that yields the highest *actual profit* in your pocket.
    """)

else:
    # --- DASHBOARD RESULTS (After Button Click) ---
    
    # We add a "Reset" button to let them do another search
    if st.button("🔄 Start New Search"):
        st.session_state.show_results = False
        st.rerun()
        
    with st.spinner("Satellite routing, market forecasting, and AI analysis in progress..."):
        
        API_URL = "http://127.0.0.1:8000/get_recommendation"
        payload = {
            "farmer_lat": st.session_state.farmer_lat,
            "farmer_lon": st.session_state.farmer_lon,
            "horizon": horizon,
            "commodity": commodity.lower()
        }
        
        try:
            response = requests.post(API_URL, json=payload)
            
            if response.status_code == 200:
                data = response.json()
                
                # --- RESULTS: THE HEADLINE ---
                st.success(f"### 🏆 Optimal Destination: {data['recommended_mandi']} Mandi")
                
                # --- RESULTS: METRIC CARDS ---
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Highest Net Profit", f"₹ {data['net_price_p50']}/qtl", delta="Optimized", delta_color="normal")
                m2.metric("Gross Market Rate", f"₹ {data['gross_price_p50']}/qtl")
                m3.metric("Transport Cost", f"₹ {round(data['transport_cost'], 1)}/qtl")
                m4.metric("Distance Traveled", f"{round(data['distance_km'], 1)} km")
                
                st.write("") 
                
                # --- TABBED UTILITIES ---
                tab1, tab2, tab3 = st.tabs(["📊 Market Analytics", "🧠 AI Explanation (SHAP)", "📜 Recommendation History"])
                
                with tab1:
                    st.markdown("#### 📉 Price Risk Bounds (80% Confidence)")
                    st.info(f"The actual gross price at {data['recommended_mandi']} is highly likely to fall between **{data['confidence_interval']}**.")
                    
                    bounds = [float(x.replace('₹', '').strip()) for x in data['confidence_interval'].split('-')]
                    
                    fig = go.Figure()
                    fig.add_trace(go.Bar(
                        x=['Predicted Price Spread'],
                        y=[bounds[1] - bounds[0]],
                        base=[bounds[0]],
                        marker_color='#22c55e',
                        name='80% Confidence Interval',
                        text=f"Expected: ₹{data['gross_price_p50']}",
                        textposition='auto'
                    ))
                    fig.update_layout(
                        title=f"{commodity} Price Projection - {data['recommended_mandi']}",
                        yaxis_title="Price (₹ / qtl)",
                        plot_bgcolor='rgba(0,0,0,0)',
                        paper_bgcolor='rgba(0,0,0,0)',
                        showlegend=False
                    )
                    st.plotly_chart(fig, use_container_width=True)

                with tab2:
                    st.markdown("#### 🤖 Why did the AI choose this price?")
                    with st.container(border=True):
                        st.markdown(f"*{data['explanation']}*")
                        st.caption("Generated via SHAP (SHapley Additive exPlanations) on LightGBM tree architecture.")
                
                with tab3:
                    st.markdown("#### 🕒 Local Query History")
                    st.warning("History module is running in local memory only. Cloud database synchronization pending.")
                    history_data = pd.DataFrame({
                        "Date": pd.to_datetime("today").strftime("%Y-%m-%d"),
                        "Crop": [commodity],
                        "Target Mandi": [data['recommended_mandi']],
                        "Net Yield Est": [f"₹{data['net_price_p50']}"]
                    })
                    st.dataframe(history_data, use_container_width=True, hide_index=True)
                    
            else:
                st.error("⚠️ Backend Error: Ensure database is populated. (Waiting on Agmarknet API)")
                st.json(response.json())
                
        except requests.exceptions.ConnectionError:
            st.error("🚨 Connection Failed. Ensure FastAPI is running on port 8000 (`uvicorn api.main:app`).")