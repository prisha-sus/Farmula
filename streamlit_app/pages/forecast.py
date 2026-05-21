import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from src.live_prices import get_latest_prices, get_live_df
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


@st.cache_data(ttl=300)
def get_multi_horizon_forecasts(commodity_key: str) -> dict:
    try:
        df = pd.read_sql("SELECT * FROM latest_mandi_features", engine)
        if df.empty:
            return {}
        results = {}
        for horizon in [1, 7, 15, 30]:
            try:
                forecasts = generate_batch_forecasts(df, commodity=commodity_key, horizon=horizon)
                if forecasts:
                    p50_avg = sum(v["p50"] for v in forecasts.values()) / len(forecasts)
                    p10_min = min(v["p10"] for v in forecasts.values())
                    p90_max = max(v["p90"] for v in forecasts.values())
                    results[horizon] = {
                        "p50": round(p50_avg),
                        "p10": round(p10_min),
                        "p90": round(p90_max),
                    }
            except Exception:
                pass
        return results
    except Exception:
        return {}


@st.cache_data(ttl=3600)
def get_historical_df(commodity_key: str, days: int = 90) -> pd.DataFrame:
    df = get_live_df()
    if df.empty:
        return pd.DataFrame()
    mask = df["commodity"].str.lower().str.contains(commodity_key.lower(), na=False)
    df_c = df[mask].copy()
    if df_c.empty:
        return pd.DataFrame()
    cutoff = df_c["date"].max() - pd.Timedelta(days=days)
    df_c = df_c[df_c["date"] >= cutoff]
    return (
        df_c.groupby("date")["modal_price"]
        .mean()
        .reset_index()
        .sort_values("date")
    )


st.title("Price Forecast")
st.caption("Multi-horizon probabilistic price forecasts per commodity")

commodity = st.selectbox("Commodity", ["Onion", "Potato", "Soyabean"])
district, commodity_key = COMMODITY_DISTRICT[commodity]

with st.spinner("Loading forecasts..."):
    horizons = get_multi_horizon_forecasts(commodity_key)

df_live = get_latest_prices(district, commodity_key)
current_price = float(df_live["modal_price"].mean()) if not df_live.empty else None

st.markdown("---")
st.subheader("Forecast horizon cards")

h_cols = st.columns(4)
for col, horizon in zip(h_cols, [1, 7, 15, 30]):
    fc = horizons.get(horizon)
    if fc:
        delta_val = (fc["p50"] - current_price) if current_price is not None else None
        delta_str = (
            f"{'+' if delta_val >= 0 else ''}₹{delta_val:,.0f}" if delta_val is not None else None
        )
        col.metric(
            label=f"{horizon}-day forecast",
            value=f"₹{fc['p50']:,.0f}",
            delta=delta_str,
            help=f"p10: ₹{fc['p10']:,} — p90: ₹{fc['p90']:,}",
        )
    else:
        col.metric(f"{horizon}-day forecast", "—")

if current_price:
    st.caption(f"Delta vs current market average ₹{current_price:,.0f}/q")

st.markdown("---")
st.subheader(f"Historical prices — {commodity} (last 90 days)")

df_hist = get_historical_df(commodity_key)
if not df_hist.empty:
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df_hist["date"],
        y=df_hist["modal_price"],
        mode="lines+markers",
        line=dict(color=t["primary"], width=2),
        marker=dict(size=4),
        name="Modal Price",
        fill="tozeroy",
        fillcolor="rgba(34,197,94,0.1)",
    ))
    fig.update_layout(
        xaxis_title="Date",
        yaxis_title="Avg Modal Price (₹/qtl)",
        plot_bgcolor=t["plotly_bg"],
        paper_bgcolor=t["plotly_paper"],
        font=dict(color=t["text"]),
        margin=dict(l=0, r=0, t=20, b=0),
        height=360,
    )
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("No historical price data available.")
