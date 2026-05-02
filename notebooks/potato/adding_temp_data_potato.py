"""
Temperature Data Addition Pipeline for Potato - All Horizons (1d, 7d, 15d, 30d)
Adapted from the existing Onion Adding_Temp_Data notebooks.
Fetches weather data from Open-Meteo, engineers lagged features, merges with price data.
"""

import pandas as pd
import requests
import os
import sys

OUTPUT_DIR = '../../data/potato'


def fetch_weather_data():
    """Fetch historical weather data from Open-Meteo for Pune district."""
    print("Fetching weather data for Pune district from Open-Meteo...")
    
    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude": 18.5204,
        "longitude": 73.8567,
        "start_date": "2021-01-01",
        "end_date": "2026-04-20",
        "daily": ["temperature_2m_mean", "precipitation_sum"],
        "timezone": "Asia/Kolkata"
    }
    
    response = requests.get(url, params=params)
    
    if response.status_code != 200:
        print(f"ERROR: Weather API returned status {response.status_code}")
        print(response.text)
        sys.exit(1)
    
    weather_json = response.json()
    
    weather_df = pd.DataFrame({
        'arrival_date': pd.to_datetime(weather_json['daily']['time']),
        'temp_mean': weather_json['daily']['temperature_2m_mean'],
        'rainfall_daily': weather_json['daily']['precipitation_sum']
    })
    
    print(f"  Weather records fetched: {len(weather_df)}")
    print(f"  Date range: {weather_df['arrival_date'].min().date()} to {weather_df['arrival_date'].max().date()}")
    
    return weather_df


def engineer_weather_features(weather_df, lag_days):
    """Engineer lagged weather features for a specific horizon."""
    print(f"  Engineering weather features with lag={lag_days} days...")
    
    weather_df = weather_df.sort_values('arrival_date').copy()
    
    # Lag the raw weather by the horizon amount
    weather_df[f'temp_mean_lag{lag_days}'] = weather_df['temp_mean'].shift(lag_days)
    weather_df[f'rainfall_lag{lag_days}'] = weather_df['rainfall_daily'].shift(lag_days)
    
    # Rolling features (calculated from the lagged data)
    weather_df['rainfall_7d_sum'] = weather_df[f'rainfall_lag{lag_days}'].rolling(window=7).sum()
    weather_df['rainfall_30d_sum'] = weather_df[f'rainfall_lag{lag_days}'].rolling(window=30).sum()
    weather_df['temp_7d_avg'] = weather_df[f'temp_mean_lag{lag_days}'].rolling(window=7).mean()
    
    # Drop raw columns
    weather_df = weather_df.drop(columns=['temp_mean', 'rainfall_daily'])
    weather_df = weather_df.dropna()
    
    return weather_df


def merge_and_save(weather_df, horizon_name, lag_days):
    """Merge weather data with the prepared price dataset."""
    input_csv = os.path.join(OUTPUT_DIR, f'prepared_potato_pune_dynamic_master_{horizon_name}.csv')
    output_csv = os.path.join(OUTPUT_DIR, f'final_model_ready_pune_data_potato_{horizon_name}.csv')
    
    print(f"\n--- Processing {horizon_name} horizon (lag={lag_days}) ---")
    
    if not os.path.exists(input_csv):
        print(f"  ERROR: Input file not found: {input_csv}")
        print(f"  Please run data_cleaning_potato.py first!")
        return False
    
    print(f"  Loading: {input_csv}")
    master_df = pd.read_csv(input_csv)
    master_df['arrival_date'] = pd.to_datetime(master_df['arrival_date'])
    
    # Engineer weather features for this specific horizon
    weather_horizon = engineer_weather_features(weather_df.copy(), lag_days)
    
    # Merge
    final_df = pd.merge(master_df, weather_horizon, on='arrival_date', how='left')
    
    missing_weather = final_df['rainfall_7d_sum'].isna().sum()
    print(f"  Rows missing weather data after merge: {missing_weather}")
    
    # Forward fill any gaps
    weather_cols = [f'temp_mean_lag{lag_days}', f'rainfall_lag{lag_days}', 
                    'rainfall_7d_sum', 'rainfall_30d_sum', 'temp_7d_avg']
    final_df[weather_cols] = final_df[weather_cols].ffill()
    
    # Drop rows that still have NaN in weather columns (at the very start)
    final_df = final_df.dropna(subset=weather_cols)
    
    final_df.to_csv(output_csv, index=False)
    print(f"  [OK] Saved {len(final_df)} records to '{output_csv}'")
    print(f"  Weather features: {weather_cols}")
    
    return True


def main():
    # Fetch weather data once
    weather_df = fetch_weather_data()
    
    # Process each horizon
    horizons = {
        '1day': 1,
        '7day': 7,
        '15day': 15,
        '30day': 30,
    }
    
    success_count = 0
    for horizon_name, lag_days in horizons.items():
        if merge_and_save(weather_df, horizon_name, lag_days):
            success_count += 1
    
    print(f"\n{'='*60}")
    print(f"TEMPERATURE DATA ADDITION COMPLETE! ({success_count}/{len(horizons)} horizons)")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
