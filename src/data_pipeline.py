"""
Data Pipeline Module for SmartMandi DSS.
Fetches live data from data.gov.in and Open-Meteo, engineers features, 
and prepares data for inference or database insertion.
"""

import pandas as pd
import numpy as np
import requests
import holidays
import time
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv

load_dotenv()

# You should move these to an environment variable (.env) later!
API_KEY = os.getenv("DATAGOV_API_KEY")
RESOURCE_ID = "35985678-0d79-46b4-9ed6-6f13308a1d24"

import time # Add this to your imports at the top if not already there

def fetch_live_mandi_data(days_back: int = 60) -> pd.DataFrame:
    """Fetches raw market data from the government API with retry logic."""
    base_url = f"https://api.data.gov.in/resource/{RESOURCE_ID}"
    params = {
        'api-key': API_KEY,
        'format': 'json',
        'limit': 2000,
        'filters[state]': 'Maharashtra',
        'filters[district]': 'Pune',
        'filters[commodity]': 'Onion'
    }
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            print(f"   [Attempt {attempt + 1}/{max_retries}] Connecting to data.gov.in...")
            response = requests.get(base_url, params=params, timeout=15)
            response.raise_for_status() # Raises an error for bad responses (like 502)
            data = response.json()
            break # If successful, break out of the retry loop
            
        except requests.exceptions.RequestException as e:
            print(f"   ⚠️ API connection failed: {e}")
            if attempt < max_retries - 1:
                print("   ⏳ Retrying in 5 seconds...")
                time.sleep(5)
            else:
                print("   ❌ Max retries reached. Government API is down.")
                return pd.DataFrame() # Return empty dataframe on total failure

    if 'records' not in data or len(data['records']) == 0:
        return pd.DataFrame()
        
    df = pd.DataFrame(data['records'])
    
    # Clean up column names based on your script
    col_mapping = {
        'Arrival_Date': 'arrival_date', 'Market': 'mandi_name',
        'District': 'district', 'State': 'state',
        'Variety': 'variety', 'Modal_Price': 'modal_price'
    }
    
    df = df.rename(columns=col_mapping)[list(col_mapping.values())]
    df['arrival_date'] = pd.to_datetime(df['arrival_date'], format='%d/%m/%Y', errors='coerce')
    df['modal_price'] = pd.to_numeric(df['modal_price'], errors='coerce')
    df['mandi_name'] = df['mandi_name'].str.title().str.strip()
    
    # Filter recent history
    start_date = pd.to_datetime(datetime.today().date() - timedelta(days=days_back))
    return df[df['arrival_date'] >= start_date].sort_values(by=['mandi_name', 'arrival_date'])


def fetch_live_weather(days_back: int = 60) -> pd.DataFrame:
    """Fetches daily average temp and rainfall for Pune using live forecast API."""
    import requests
    import pandas as pd
    
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": 18.5204,
        "longitude": 73.8567,
        "daily": ["temperature_2m_max", "temperature_2m_min", "precipitation_sum"],
        "timezone": "Asia/Kolkata",
        "past_days": days_back,
        "forecast_days": 1
    }
    
    response = requests.get(url, params=params)
    data = response.json()
    
    df = pd.DataFrame({
        'arrival_date': pd.to_datetime(data['daily']['time']),
        'temp_max': data['daily']['temperature_2m_max'],
        'temp_min': data['daily']['temperature_2m_min'],
        'rainfall': data['daily']['precipitation_sum']
    })
    
    # Calculate the mean temperature to match your model's exact expected features
    df['temp_mean'] = (df['temp_max'] + df['temp_min']) / 2.0
    
    return df[['arrival_date', 'temp_mean', 'rainfall']]


def generate_latest_features(mandi_df: pd.DataFrame, weather_df: pd.DataFrame) -> pd.DataFrame:
    """
    Merges market and weather data, engineers a UNIVERSAL set of lags/rolling means 
    for ALL horizons (1, 7, 15, 30), and returns the most recent row.
    """
    df = pd.merge(mandi_df, weather_df, on='arrival_date', how='left')
    df = df.sort_values(['mandi_name', 'arrival_date']).reset_index(drop=True)
    
    current_year = datetime.today().year
    india_holidays = holidays.India(years=[current_year, current_year - 1])
    
    latest_rows = []
    
    for mandi, group in df.groupby('mandi_name'):
        group = group.copy()
        
        group['is_real_trade'] = (group['modal_price'] > 0).astype(int)
        
        # -----------------------------------------------------
        # 1. UNIVERSAL PRICE LAGS (For 1, 7, 15, and 30 horizons)
        # -----------------------------------------------------
        group['price_lag_1'] = group['modal_price'].shift(1)
        group['price_lag_7'] = group['modal_price'].shift(7)
        group['price_lag_15'] = group['modal_price'].shift(15)
        group['price_lag_30'] = group['modal_price'].shift(30)
        
        # Expanding / Rolling Means
        group['price_expanding_mean'] = group['price_lag_1'].expanding().mean()
        group['price_roll_mean_7'] = group['price_lag_1'].rolling(window=7).mean()
        group['price_roll_std_7'] = group['price_lag_1'].rolling(window=7).std()
        group['price_roll_mean_30'] = group['price_lag_1'].rolling(window=30).mean()
        
        # -----------------------------------------------------
        # 2. UNIVERSAL WEATHER LAGS
        # -----------------------------------------------------
        group['temp_mean_lag1'] = group['temp_mean'].shift(1)
        group['temp_mean_lag30'] = group['temp_mean'].shift(30)
        
        group['rainfall_lag1'] = group['rainfall'].shift(1)
        group['rainfall_lag30'] = group['rainfall'].shift(30)
        
        group['rainfall_7d_sum'] = group['rainfall_lag1'].rolling(window=7).sum()
        group['rainfall_30d_sum'] = group['rainfall_lag1'].rolling(window=30).sum()
        group['temp_7d_avg'] = group['temp_mean_lag1'].rolling(window=7).mean()

        # -----------------------------------------------------
        # 3. DATE & TIME FEATURES
        # -----------------------------------------------------
        group['day_of_year'] = group['arrival_date'].dt.dayofyear
        group['day_of_week'] = group['arrival_date'].dt.dayofweek
        group['month'] = group['arrival_date'].dt.month
        group['is_weekend'] = group['day_of_week'].isin([5, 6]).astype(int)
        group['is_holiday'] = group['arrival_date'].dt.date.apply(lambda x: int(x in india_holidays))
        
        group['sin_365_1'] = np.sin(2 * np.pi * group['day_of_year'] / 365.25)
        group['cos_365_1'] = np.cos(2 * np.pi * group['day_of_year'] / 365.25)
        group['sin_365_2'] = np.sin(4 * np.pi * group['day_of_year'] / 365.25)
        group['cos_365_2'] = np.cos(4 * np.pi * group['day_of_year'] / 365.25)
        
        # We only want the VERY LAST ROW (today's known data) to feed into the models
        latest_row = group.iloc[-1:]
        latest_rows.append(latest_row)
        
    return pd.concat(latest_rows).reset_index(drop=True)