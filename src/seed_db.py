"""
Database Seeding Script for Farmula DSS.
Runs the data pipeline to fetch live API data, engineer features, 
and save the latest snapshot to PostgreSQL.
"""

from data_pipeline import fetch_live_mandi_data, fetch_live_weather, generate_latest_features
from db_utils import save_dataframe_to_db

def update_live_database():
    print("🚀 Starting Live Database Update...")
    
    # 1. Fetch live data (Last 60 days from today)
    print("\n📥 Fetching last 60 days of market data from data.gov.in...")
    mandi_df = fetch_live_mandi_data(days_back=60)
    if mandi_df.empty:
        print("❌ ERROR: No market data fetched. Check API key or connection.")
        return
        
    print(f"✅ Fetched {len(mandi_df)} market records.")
    
    print("\n📥 Fetching last 60 days of weather data from Open-Meteo...")
    weather_df = fetch_live_weather(days_back=60)
    print(f"✅ Fetched {len(weather_df)} weather records.")
    
    # 2. Engineer features
    print("\n⚙️ Engineering 30 universal features for inference...")
    latest_features_df = generate_latest_features(mandi_df, weather_df)
    
    # 3. Save to PostgreSQL
    print("\n💾 Saving latest feature snapshot to PostgreSQL...")
    # We use 'replace' because for inference, we only ever need the most recent row per mandi
    save_dataframe_to_db(latest_features_df, table_name="latest_mandi_features", if_exists="replace")
    
    print("\n🎉 Update Complete! The database is now ready for live predictions.")

if __name__ == "__main__":
    update_live_database()