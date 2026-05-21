"""
Creates all required tables in NeonDB.
Run once: python scripts/create_schema.py
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from src.db_utils import engine

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS latest_mandi_features (
    id SERIAL PRIMARY KEY,
    market VARCHAR(255),
    district VARCHAR(100),
    commodity VARCHAR(100),
    date DATE,
    modal_price FLOAT,
    min_price FLOAT,
    max_price FLOAT,
    lag_1 FLOAT,
    lag_7 FLOAT,
    lag_14 FLOAT,
    lag_30 FLOAT,
    rolling_mean_7 FLOAT,
    rolling_std_7 FLOAT,
    rolling_mean_30 FLOAT,
    temp_max FLOAT,
    temp_min FLOAT,
    temp_mean FLOAT,
    temp_lag1 FLOAT,
    temp_lag7 FLOAT,
    precipitation FLOAT,
    precip_lag1 FLOAT,
    precip_roll7 FLOAT,
    precip_roll30 FLOAT,
    evapotrans_lag1 FLOAT,
    day_of_week INT,
    month INT,
    week_of_year INT,
    sin_7 FLOAT,
    cos_7 FLOAT,
    sin_365 FLOAT,
    cos_365 FLOAT,
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_mandi_commodity_district
    ON latest_mandi_features(commodity, district);
CREATE INDEX IF NOT EXISTS idx_mandi_date
    ON latest_mandi_features(date);

CREATE TABLE IF NOT EXISTS mandi_prices (
    id SERIAL PRIMARY KEY,
    market VARCHAR(255),
    district VARCHAR(100),
    commodity VARCHAR(100),
    date DATE,
    modal_price FLOAT,
    min_price FLOAT,
    max_price FLOAT,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(market, commodity, date)
);

CREATE INDEX IF NOT EXISTS idx_mandi_prices_lookup
    ON mandi_prices(commodity, district, date);

CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255),
    password_hash VARCHAR(255),  -- NULL for Google OAuth users
    auth_provider VARCHAR(50) DEFAULT 'email',  -- 'email' or 'google'
    created_at TIMESTAMP DEFAULT NOW(),
    last_login TIMESTAMP
);
"""


def create_schema():
    with engine.connect() as conn:
        conn.execute(text(SCHEMA_SQL))
        conn.commit()
        print("Schema created successfully in NeonDB")


if __name__ == "__main__":
    create_schema()
