"""
Database Utility Module for Farmula DSS.
Handles connections to the local PostgreSQL database.
"""

import urllib.parse
from sqlalchemy import create_engine
import pandas as pd

# Database configuration
DB_USER = "postgres"

# We use quote_plus to safely encode any special characters (@, #, $, etc.) in your password
raw_password = "90$7&r3$p@ss"  # <-- Put your exact password here again
DB_PASSWORD = urllib.parse.quote_plus(raw_password)

DB_HOST = "localhost"
DB_PORT = "5432"
DB_NAME = "farmula_db"  # Updated to your new database name!

# Create the SQLAlchemy Engine safely
CONNECTION_STRING = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
engine = create_engine(CONNECTION_STRING)

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