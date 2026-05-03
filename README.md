# Farmula DSS

Farmula is an AI-powered Decision Support System that helps farmers and Farmer Producer Organizations (FPOs) make better pricing decisions for onions. It combines probabilistic forecasting, logistics-aware net-price ranking, and explainable AI.

---

## 🚀 What This Project Includes

- `api/` — FastAPI backend exposing recommendation endpoints
- `streamlit_app/` — Streamlit dashboard for interactive farmer-facing UI
- `src/` — Core application logic:
  - `db_utils.py` — PostgreSQL connection and DB utilities
  - `inference.py` — LightGBM model loading and forecast generation
  - `logistics.py` — Distance, transport cost, and net-price ranking
  - `explainer.py` — SHAP explanation generation
  - `data_pipeline.py` — Feature engineering for latest mandi data
- `models/` — Trained LightGBM onion quantile models
- `data/` — Sample/prepared datasets and feature snapshots

---

## 🧩 Requirements

- Python 3.11 or later
- PostgreSQL database
- Windows-compatible environment (this repo is structured for Windows paths)

---

## 📦 Setup

### 1. Create / activate the virtual environment

```powershell
python -m venv venv
.\venv\Scripts\activate
```
### 2. Install dependencies

```powershell
pip install -r requirements.txt
```
## 🔧 Database Configuration
The backend uses PostgreSQL via `db_utils.py`. It reads database connection details from `.env`.

Required `.env` variables
Create a `.env` file in the project root with:

```
DB_USER=postgres
DB_PASSWORD=your_password
DB_HOST=localhost
DB_PORT=5432
DB_NAME=farmula_db
```
Test the database connection

```
.\venv\Scripts\python.exe src\db_utils.py
```
This will run the built-in test_connection() and confirm whether PostgreSQL is reachable.

---
## 🧠 Loading Data
The project expects a table named latest_mandi_features in PostgreSQL. This is the latest feature snapshot used by inference.

If you need to refresh it, use:
```
.\venv\Scripts\python.exe src\seed_db.py
```
This script:
- fetches market data
- fetches weather data
- generates features
- writes the latest snapshot to PostgreSQL

---
## ▶️ Running the API
Start the FastAPI server from the project root:
```
.\venv\Scripts\python.exe -m uvicorn api.main:app --reload
```
Then open:
```
http://127.0.0.1:8000
```
### API Endpoints
- GET / — health check
- POST /get_recommendation — get recommended mandi, net price, distance, transport cost, and explanation
  
### Example request body
```
{
  "farmer_lat": 18.5204,
  "farmer_lon": 73.8567,
  "horizon": 7,
  "commodity": "onion"
}
```
---
## 🖥️ Running the Streamlit Dashboard
From the repo root:
```
.\venv\Scripts\python.exe -m streamlit run streamlit_app/app.py
```
This will launch the dashboard at:
```
http://localhost:8501
```
