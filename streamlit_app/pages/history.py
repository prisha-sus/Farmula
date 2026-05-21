import streamlit as st
import pandas as pd
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from src.db_utils import engine
from sqlalchemy import text
from streamlit_app.theme import inject_theme_css

inject_theme_css()

st.title("Query History")
st.caption("Your recent market optimization queries")


@st.cache_data(ttl=60)
def load_history() -> pd.DataFrame:
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT commodity, district, market, date, modal_price, min_price, max_price
                FROM mandi_prices
                ORDER BY date DESC
                LIMIT 50
            """))
            return pd.DataFrame(result.fetchall(), columns=result.keys())
    except Exception as e:
        st.error(f"Could not load history: {e}")
        return pd.DataFrame()


df = load_history()

if df.empty:
    st.info("No history yet. Run the market optimizer to see results here.")
else:
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")

    col1, col2, col3 = st.columns(3)
    col1.metric("Total records", f"{len(df):,}")
    if "modal_price" in df.columns:
        col2.metric("Avg modal price", f"₹{df['modal_price'].mean():,.0f}")
        col3.metric(
            "Price range",
            f"₹{df['modal_price'].min():,.0f} – ₹{df['modal_price'].max():,.0f}",
        )

    st.markdown("---")

    filter_col1, filter_col2 = st.columns(2)
    with filter_col1:
        commodities = ["All"] + sorted(df["commodity"].dropna().unique().tolist())
        selected_commodity = st.selectbox("Filter by commodity", commodities)
    with filter_col2:
        if "district" in df.columns:
            districts = ["All"] + sorted(df["district"].dropna().unique().tolist())
            selected_district = st.selectbox("Filter by district", districts)
        else:
            selected_district = "All"

    filtered = df.copy()
    if selected_commodity != "All":
        filtered = filtered[filtered["commodity"] == selected_commodity]
    if selected_district != "All" and "district" in filtered.columns:
        filtered = filtered[filtered["district"] == selected_district]

    st.dataframe(filtered, use_container_width=True, hide_index=True)
