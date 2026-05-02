"""
Database Utility Module for Farmula DSS.
Handles connections to the local PostgreSQL database.
"""

import urllib.parse
from sqlalchemy import create_engine
import pandas as pd
import os
from dotenv import load_dotenv

# Load the variables from the .env file into the system
load_dotenv()

# Fetch variables securely
DB_USER = os.getenv("DB_USER")
raw_password = os.getenv("DB_PASSWORD")
DB_PASSWORD = urllib.parse.quote_plus(raw_password)
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")

# Construct the URL
DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# Create the SQLAlchemy Engine
engine = create_engine(DATABASE_URL)

def test_connection():
    """Tests if Python can successfully talk to PostgreSQL."""
    try:
        with engine.connect() as connection:
            print(f"✅ SUCCESS: Successfully connected to PostgreSQL database '{DB_NAME}'!")
    except Exception as e:
        print("❌ ERROR: Could not connect to the database.")
        print(f"Details: {e}")

def save_dataframe_to_db(df: pd.DataFrame, table_name: str, if_exists: str = 'replace'):
    """
    Saves a Pandas DataFrame directly to a PostgreSQL table.
    'if_exists' can be 'replace' (overwrite table) or 'append' (add new rows).
    """
    try:
        df.to_sql(table_name, engine, if_exists=if_exists, index=False)
        print(f"✅ Data successfully saved to table: '{table_name}'")
    except Exception as e:
        print(f"❌ Failed to save data to table '{table_name}'. Error: {e}")

# Run the test if this file is executed directly
if __name__ == "__main__":
    test_connection()