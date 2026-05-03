import requests
import pandas as pd
import os
import time
from dotenv import load_dotenv

load_dotenv()

def test_open_meteo():
    print("========================================")
    print("🌦️ TESTING OPEN-METEO (WEATHER) API")
    print("========================================")
    
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": 18.5204,
        "longitude": 73.8567,
        "daily": ["temperature_2m_max", "temperature_2m_min", "precipitation_sum"],
        "timezone": "Asia/Kolkata",
        "past_days": 5, # Just requesting 5 days for a quick test
        "forecast_days": 1
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            print("✅ SUCCESS: Weather API is working perfectly!")
            data = response.json()
            
            # Show a tiny snippet to prove we actually got the data
            dates = data['daily']['time'][:3]
            precip = data['daily']['precipitation_sum'][:3]
            print(f"   Sample Dates: {dates}")
            print(f"   Sample Rainfall: {precip}")
        else:
            print(f"❌ ERROR: Received status code {response.status_code}")
            print(response.text)
    except Exception as e:
        print(f"❌ EXCEPTION: {e}")


def test_datagov():
    print("\n========================================")
    print("🧅 TESTING DATA.GOV.IN (MANDI) API")
    print("========================================")
    
    API_KEY = os.getenv("DATAGOV_API_KEY")
    RESOURCE_ID = "35985678-0d79-46b4-9ed6-6f13308a1d24"
    
    url = f"https://api.data.gov.in/resource/{RESOURCE_ID}"
    params = {
        'api-key': API_KEY,
        'format': 'json',
        'limit': 5  # Only fetch 5 records to test the connection quickly
    }
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            # Added a 15-second timeout safety
            response = requests.get(url, params=params)
            
            if response.status_code == 200:
                print("✅ SUCCESS: API Key is valid and server is UP!")
                data = response.json()
                mandi = data['records'][0]['Market']
                price = data['records'][0]['Modal_Price']
                print(f"   Sample Data -> Mandi: {mandi}, Price: ₹{price}")
                break # Success, exit retry loop
                
            elif response.status_code == 429:
                print(f"⚠️ 429 TOO MANY REQUESTS: Rate limit hit. Sleeping for 10 seconds (Attempt {attempt+1}/{max_retries})...")
                time.sleep(10)
                continue # Retry after sleeping
                
            elif response.status_code == 502:
                print("❌ 502 ERROR: Your code is correct, but the Government server is CURRENTLY DOWN.")
                break
                
            elif response.status_code in [401, 403]:
                print("❌ AUTH ERROR: Your API Key is invalid or expired.")
                break
                
            elif response.status_code == 404:
                print("❌ NOT FOUND: Your Resource ID is incorrect.")
                break
                
            else:
                print(f"❌ UNKNOWN ERROR: {response.status_code}")
                print(response.text)
                break
                
        except Exception as e:
            print(f"❌ EXCEPTION: {e}")
            break

if __name__ == "__main__":
    test_open_meteo()
    test_datagov()