# Farmula: AI-Based Market Intelligence & Decision Support System

Farmula is an AI-powered Decision Support System (DSS) designed to help farmers and Farmer Producer Organizations (FPOs) in Maharashtra make data-driven crop marketing decisions. 

Currently optimized for Onion pricing across major Pune district mandis (Pune, Baramati, Shirur, Khed, Junnar), the system goes beyond standard price tickers by providing **distance-adjusted net-price comparisons**, probabilistic forecasting, and explainable AI insights.

## 🚀 Key Features

* **Probabilistic Price Forecasting:** Uses Quantile LightGBM models to predict prices across 4 horizons (1-day, 7-day, 15-day, and 30-day). Provides `p10`, `p50`, and `p90` bounds to capture market uncertainty.
* **Geospatial Logistics Engine:** Calculates the Haversine distance between the farmer and nearby mandis, automatically deducting transport costs to recommend the most profitable market.
* **Explainable AI (XAI):** Integrates SHAP (SHapley Additive exPlanations) to explain the driving factors behind the expected price in plain language.
* **Interactive Dashboard:** A Streamlit-based web application for easy farmer interaction.

## 📁 Project Structure

```text
farmula/
│
├── .venv/                                # Python virtual environment
├── Data/                                 # Datasets (Agmarknet prices, weather)
├── models/                               # Saved LightGBM models (.txt)
├── .gitignore                            # Git ignore file
├── app.py                                # Streamlit Web Dashboard application
├── Pune_mandi_ML_model_building.ipynb    # Model training and evaluation notebook
├── requirements.txt                      # Project dependencies
└── smartmandi_dss.ipynb                  # DSS logic testing and prototyping
```

## 🛠️ Technology Stack
* **Machine Learning:** Python, LightGBM, Scikit-Learn, Pandas, NumPy
* **Explainability:** SHAP
* **Frontend Dashboard:** Streamlit

## ⚙️ How to Run the Project Locally

### 1. Activate the Virtual Environment and Install Dependencies
Ensure you have activated the virtual environment and installed the required packages:

**For Windows:**
```bash
.venv\Scripts\activate
pip install -r requirements.txt
```

**For Mac/Linux:**
```bash
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Start the Frontend Dashboard
Run the Streamlit application directly from the root directory:

```bash
streamlit run app.py
```
*The web dashboard will automatically open in your default browser at `http://localhost:8501`.*

