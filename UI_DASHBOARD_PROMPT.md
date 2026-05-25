# Farmula React Dashboard Prompt

Build a production-ready React and Tailwind CSS dashboard for Farmula DSS, replacing the current Streamlit UI while preserving every workflow and data connection.

Requirements:

- Keep all Python model, inference, logistics, SHAP, MSP, live-price, and database logic unchanged.
- Use FastAPI as the only bridge between the frontend and Python helpers.
- Wire these flows completely: email login, email signup, Google OAuth token verification, sign out, data freshness, GPS/default coordinates, weather lookup, latest mandi prices, best live mandi preview, recommendation request, MSP comparison, analytics chart, AI explanation, and local recommendation history.
- Render every current Streamlit section in a polished dashboard: authenticated shell, user panel, market parameters, farm map, live weather, best-price preview, decision flow, optimal mandi result, net/gross/transport/distance metrics, confidence interval analytics, SHAP explanation, and query history.
- Rename action buttons to clearer dashboard labels such as "Find Best Mandi", "Use Current Location", "Clear Result", and "Sign Out".
- Use responsive layout, accessible form controls, loading states, empty states, and backend error messages.
- Do not use mock data for wired backend features. If a backend call fails, show a clear UI error without hiding the failure.
- Keep the visual style professional for farmer/FPO market operations: practical, readable, data-first, mobile-friendly, and suitable for a demo tomorrow.
