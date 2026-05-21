import streamlit as st

THEMES = {
    "light": {
        "bg": "#ffffff",
        "surface": "#f8fafc",
        "primary": "#166534",
        "primary_light": "#22c55e",
        "text": "#111827",
        "text_muted": "#6b7280",
        "border": "#e5e7eb",
        "metric_color": "#166534",
        "plotly_bg": "rgba(255,255,255,0)",
        "plotly_paper": "rgba(255,255,255,0)",
        "map_style": "open-street-map",
    },
    "dark": {
        "bg": "#0f172a",
        "surface": "#1e293b",
        "primary": "#22c55e",
        "primary_light": "#4ade80",
        "text": "#f1f5f9",
        "text_muted": "#94a3b8",
        "border": "#334155",
        "metric_color": "#4ade80",
        "plotly_bg": "rgba(15,23,42,0)",
        "plotly_paper": "rgba(15,23,42,0)",
        "map_style": "carto-darkmatter",
    },
}


def init_theme():
    if "theme" not in st.session_state:
        st.session_state["theme"] = "light"


def toggle_theme():
    st.session_state["theme"] = "dark" if st.session_state["theme"] == "light" else "light"


def get_theme() -> dict:
    init_theme()
    return THEMES[st.session_state["theme"]]


def inject_theme_css():
    t = get_theme()
    st.markdown(f"""
        <style>
        .stApp {{ background-color: {t['bg']}; }}
        .stSidebar {{ background-color: {t['surface']}; border-right: 1px solid {t['border']}; }}

        [data-testid="stMetricValue"] {{
            font-size: 1.8rem !important;
            color: {t['metric_color']} !important;
            font-weight: 700 !important;
        }}
        [data-testid="stMetricLabel"] {{
            color: {t['text_muted']} !important;
        }}
        .stButton>button {{
            background-color: {t['primary']};
            color: white;
            border-radius: 8px;
            border: none;
            font-weight: 600;
            transition: all 0.2s ease;
        }}
        .stButton>button:hover {{
            background-color: {t['primary_light']};
            transform: translateY(-1px);
        }}
        h1, h2, h3 {{ color: {t['text']} !important; }}
        p, label {{ color: {t['text_muted']}; }}
        .price-card {{
            background: {t['surface']};
            border: 1px solid {t['border']};
            border-radius: 12px;
            padding: 1.2rem;
            text-align: center;
        }}
        .price-card .commodity {{
            font-size: 0.85rem;
            color: {t['text_muted']};
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}
        .price-card .price {{
            font-size: 2rem;
            font-weight: 700;
            color: {t['primary']};
        }}
        .price-card .label {{
            font-size: 0.8rem;
            color: {t['text_muted']};
        }}
        </style>
    """, unsafe_allow_html=True)
