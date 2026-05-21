"""
Authentication for Farmula.

Three views managed via st.session_state["auth_view"]:
  "login"         — email/password sign-in + Google OAuth button
  "signup"        — create a new email/password account
  "authenticated" — set automatically when session_state["connected"] is True

Google OAuth flow runs through FastAPI:
  /auth/login  →  Google consent  →  /auth/callback  →  Streamlit /?auth_token=
"""

import streamlit as st
import requests
import os
from dotenv import load_dotenv

load_dotenv()

FASTAPI_URL = os.getenv("FASTAPI_URL", "http://localhost:8000")


def check_auth_token_in_url():
    """Handles Google OAuth redirect — verifies token and sets session state."""
    token = st.query_params.get("auth_token")
    if token and not st.session_state.get("connected"):
        try:
            response = requests.get(
                f"{FASTAPI_URL}/auth/verify",
                params={"token": token},
                timeout=10
            )
            data = response.json()
            if data.get("valid"):
                st.session_state["connected"]  = True
                st.session_state["user_info"]  = data["user"]
                st.query_params.clear()
                st.rerun()
        except Exception as e:
            st.error(f"Authentication failed: {e}")


def show_login_page() -> bool:
    check_auth_token_in_url()
    if st.session_state.get("connected"):
        return True

    if "auth_view" not in st.session_state:
        st.session_state["auth_view"] = "login"

    # Centered card — logo + title
    _, col, _ = st.columns([1, 1.2, 1])
    with col:
        st.markdown("## 🌾 Farmula")
        st.markdown("##### Agricultural Price Intelligence")
        st.markdown("---")

    if st.session_state["auth_view"] == "login":
        _show_login_form()
    else:
        _show_signup_form()

    return False


def _show_login_form():
    _, col, _ = st.columns([1, 1.2, 1])
    with col:
        st.markdown("### Sign in")

        email    = st.text_input("Email",    placeholder="you@example.com", key="login_email")
        password = st.text_input("Password", type="password", placeholder="Password", key="login_password")

        if st.button("Sign in", use_container_width=True, type="primary"):
            if not email or not password:
                st.error("Please enter email and password")
            else:
                try:
                    from src.db_utils import verify_user
                    user = verify_user(email, password)
                    if user:
                        st.session_state["connected"]  = True
                        st.session_state["user_info"]  = user
                        st.rerun()
                    else:
                        st.error("Invalid email or password")
                except Exception as e:
                    st.error(f"Login failed: {e}")

        st.markdown(" ")

        col1, col2 = st.columns([2, 1])
        with col1:
            st.caption("Don't have an account?")
        with col2:
            if st.button("Create one", use_container_width=True):
                st.session_state["auth_view"] = "signup"
                st.rerun()

        st.markdown("""
            <div style='display:flex;align-items:center;gap:8px;margin:16px 0'>
                <hr style='flex:1;border:none;border-top:1px solid #333'>
                <span style='color:#888;font-size:13px'>or</span>
                <hr style='flex:1;border:none;border-top:1px solid #333'>
            </div>
        """, unsafe_allow_html=True)

        google_url = f"{FASTAPI_URL}/auth/login"
        st.markdown(f"""
            <a href="{google_url}" target="_self" style="text-decoration:none">
                <div style="
                    display:flex;align-items:center;justify-content:center;gap:10px;
                    padding:10px 16px;border-radius:6px;
                    border:1px solid #444;background:#1a1a1a;
                    cursor:pointer;font-size:15px;color:#eee;
                ">
                    <img src="https://www.google.com/favicon.ico" width="18"/>
                    Continue with Google
                </div>
            </a>
        """, unsafe_allow_html=True)

        st.markdown(" ")
        st.caption("Your data is secure. We only access your name and email.")


def _show_signup_form():
    _, col, _ = st.columns([1, 1.2, 1])
    with col:
        st.markdown("### Create account")

        name     = st.text_input("Full name",         placeholder="Your name",          key="signup_name")
        email    = st.text_input("Email",             placeholder="you@example.com",     key="signup_email")
        password = st.text_input("Password",          type="password",
                                 placeholder="Min. 8 characters",                        key="signup_password")
        confirm  = st.text_input("Confirm password",  type="password",
                                 placeholder="Repeat password",                          key="signup_confirm")

        if st.button("Create account", use_container_width=True, type="primary"):
            if not all([name, email, password, confirm]):
                st.error("Please fill in all fields")
            elif len(password) < 8:
                st.error("Password must be at least 8 characters")
            elif password != confirm:
                st.error("Passwords do not match")
            else:
                try:
                    from src.db_utils import create_user
                    user = create_user(email, name, password)
                    st.session_state["connected"]  = True
                    st.session_state["user_info"]  = user
                    st.success("Account created!")
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))
                except Exception as e:
                    st.error(f"Signup failed: {e}")

        st.markdown(" ")
        col1, col2 = st.columns([2, 1])
        with col1:
            st.caption("Already have an account?")
        with col2:
            if st.button("Sign in", use_container_width=True):
                st.session_state["auth_view"] = "login"
                st.rerun()

        st.markdown("""
            <div style='display:flex;align-items:center;gap:8px;margin:16px 0'>
                <hr style='flex:1;border:none;border-top:1px solid #333'>
                <span style='color:#888;font-size:13px'>or</span>
                <hr style='flex:1;border:none;border-top:1px solid #333'>
            </div>
        """, unsafe_allow_html=True)

        google_url = f"{FASTAPI_URL}/auth/login"
        st.markdown(f"""
            <a href="{google_url}" target="_self" style="text-decoration:none">
                <div style="
                    display:flex;align-items:center;justify-content:center;gap:10px;
                    padding:10px 16px;border-radius:6px;
                    border:1px solid #444;background:#1a1a1a;
                    cursor:pointer;font-size:15px;color:#eee;
                ">
                    <img src="https://www.google.com/favicon.ico" width="18"/>
                    Continue with Google
                </div>
            </a>
        """, unsafe_allow_html=True)


def show_logout_button():
    """Sidebar user info + sign-out. Must be called after st.set_page_config()."""
    if st.session_state.get("connected"):
        with st.sidebar:
            st.markdown("---")
            user_info = st.session_state.get("user_info", {})
            picture   = user_info.get("picture", "")
            if picture:
                st.image(picture, width=36)
            st.caption(f"**{user_info.get('name', 'User')}**")
            st.caption(user_info.get("email", ""))
            if st.button("Sign out", use_container_width=True):
                st.session_state["connected"]  = False
                st.session_state["user_info"]  = {}
                st.session_state["auth_view"]  = "login"
                st.rerun()


def is_authenticated() -> bool:
    """Safe to call before st.set_page_config — only reads session state."""
    return st.session_state.get("connected", False)
