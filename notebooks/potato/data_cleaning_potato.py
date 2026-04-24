"""
Data Cleaning Pipeline for Potato - All Horizons (1d, 7d, 15d, 30d)
Adapted from the existing Onion data cleaning notebooks.
Reads raw Agmarknet data, cleans, engineers features, creates targets for each horizon.
"""

import pandas as pd
import numpy as np
import holidays
import sys
import os

# =========================================================
# CONFIG
# =========================================================
RAW_DATA_PATH = '../../data/potato/potato_pune.csv.csv'
OUTPUT_DIR = '../../data/potato'

# Mandi name corrections (same geographic area as Onion)
MANDI_CORRECTIONS = {
    'Baramati': 'Baramati',
    'Indapur': 'Indapur',
    'Indapur Apmc': 'Indapur',
    'Junnar': 'Junnar',
    'Junnar Apmc': 'Junnar',
    'Junnar(Alephata)': 'Junnar(Alephata)',
    'Junnar(Alephata) Apmc': 'Junnar(Alephata)',
    'Junnar(Narayangaon)': 'Junnar(Narayangaon)',
    'Junnar(Narayangaon) Apmc': 'Junnar(Narayangaon)',
    'Junnar(Otur)': 'Junnar(Otur)',
    'Junnar(Otur) Apmc': 'Junnar(Otur)',
    'Khed(Chakan)': 'Khed(Chakan)',
    'Khed(Chakan) Apmc': 'Khed(Chakan)',
    'Manchar': 'Manchar',
    'Manchar Apmc': 'Manchar',
    'Nira': 'Nira',
    'Pune': 'Pune',
    'Pune Apmc': 'Pune',
    'Pune(Khadiki)': 'Pune(Khadiki)',
    'Pune(Khadiki) Apmc': 'Pune(Khadiki)',
    'Pune(Manjri)': 'Pune(Manjri)',
    'Pune(Manjri) Apmc': 'Pune(Manjri)',
    'Pune(Moshi)': 'Pune(Moshi)',
    'Pune(Moshi) Apmc': 'Pune(Moshi)',
    'Pune(Pimpri)': 'Pune(Pimpri)',
    'Pune(Pimpri) Apmc': 'Pune(Pimpri)',
    'Shirur': 'Shirur'
}


def load_and_clean_base(raw_path):
    """Load raw CSV, clean columns, filter for Potato, apply mandi corrections."""
    print(f"Loading raw data from: {raw_path}")
    df = pd.read_csv(raw_path)
    print(f"  Raw records: {len(df)}")
    
    # Rename columns to lowercase
    df.rename(columns={
        'State': 'state', 'District': 'district', 'Market': 'mandi_name',
        'Commodity': 'commodity', 'Variety': 'variety', 'Grade': 'grade',
        'Arrival_Date': 'arrival_date', 'Min_Price': 'min_price',
        'Max_Price': 'max_price', 'Modal_Price': 'modal_price',
        'Commodity_Code': 'commodity_code'
    }, inplace=True)
    
    # Clean string columns
    df['mandi_name'] = df['mandi_name'].str.strip().str.title()
    df['district'] = df['district'].str.strip().str.title()
    df['variety'] = df['variety'].str.strip().str.title()
    
    # Drop unnecessary columns
    df.drop(columns=['commodity_code', 'grade'], inplace=True, errors='ignore')
    
    # Filter for Potato
    df = df[df['commodity'].str.lower() == 'potato'].copy()
    print(f"  Potato records: {len(df)}")
    
    # Apply mandi corrections
    df['mandi_name'] = df['mandi_name'].replace(MANDI_CORRECTIONS)
    
    # Convert date - try multiple formats
    try:
        df['arrival_date'] = pd.to_datetime(df['arrival_date'], format='%d/%m/%Y')
    except ValueError:
        try:
            df['arrival_date'] = pd.to_datetime(df['arrival_date'], format='%d-%m-%Y')
        except ValueError:
            df['arrival_date'] = pd.to_datetime(df['arrival_date'], dayfirst=True)
    
    # Sort
    df = df.sort_values(by=['mandi_name', 'variety', 'arrival_date'])
    
    print(f"  Unique mandis: {df['mandi_name'].nunique()} -> {list(df['mandi_name'].unique())}")
    print(f"  Unique varieties: {list(df['variety'].unique())}")
    print(f"  Date range: {df['arrival_date'].min().date()} to {df['arrival_date'].max().date()}")
    
    return df


def filter_dense_groups(df, min_records=100, min_density=0.15):
    """
    Filter to keep only mandi/variety combos with enough data.
    Using relaxed thresholds for potato (less data than onion).
    """
    print(f"\nAnalyzing data density (min_records={min_records}, min_density={min_density})...")
    
    group_stats = df.groupby(['mandi_name', 'variety']).agg(
        start_date=('arrival_date', 'min'),
        end_date=('arrival_date', 'max'),
        record_count=('arrival_date', 'count')
    ).reset_index()
    
    group_stats['possible_days'] = (group_stats['end_date'] - group_stats['start_date']).dt.days + 1
    group_stats['density'] = group_stats['record_count'] / group_stats['possible_days']
    
    print("\n--- Mandi Diagnostics ---")
    print(group_stats[['mandi_name', 'variety', 'start_date', 'record_count', 'density']].to_string())
    
    valid_groups = group_stats[
        (group_stats['record_count'] >= min_records) & 
        (group_stats['density'] >= min_density)
    ]
    
    print(f"\nKeeping {len(valid_groups)} dense combinations out of {len(group_stats)}.")
    
    if len(valid_groups) == 0:
        print("WARNING: No groups meet the threshold! Relaxing to top 5 by record count...")
        valid_groups = group_stats.nlargest(5, 'record_count')
        print(f"Keeping top {len(valid_groups)} groups by record count.")
    
    # Filter the dataframe to only valid groups
    valid_keys = valid_groups[['mandi_name', 'variety']].apply(tuple, axis=1).tolist()
    df = df[df.apply(lambda row: (row['mandi_name'], row['variety']) in valid_keys, axis=1)]
    
    print(f"Records after filtering: {len(df)}")
    return df


def remove_outliers(df):
    """Remove price outliers using IQR method."""
    print("\nRemoving price outliers...")
    
    results = []
    for (mandi, variety), group in df.groupby(['mandi_name', 'variety']):
        col = 'modal_price'
        Q1 = group[col].quantile(0.25)
        Q3 = group[col].quantile(0.75)
        IQR = Q3 - Q1
        lower_bound = Q1 - 1.5 * IQR
        upper_bound = Q3 + 1.5 * IQR
        group = group.copy()
        group.loc[(group[col] < lower_bound) | (group[col] > upper_bound), col] = np.nan
        results.append(group)
    
    df = pd.concat(results, ignore_index=True)
    return df


def resolve_duplicates_and_reindex(df):
    """Resolve same-day duplicates and create continuous daily timeline."""
    print("Resolving same-day duplicates...")
    
    aggregation_dict = {
        'min_price': 'mean',
        'max_price': 'mean',
        'modal_price': 'mean'
    }
    if 'commodity' in df.columns:
        aggregation_dict['commodity'] = 'first'
    
    df = df.groupby(
        ['mandi_name', 'district', 'state', 'variety', 'arrival_date']
    ).agg(aggregation_dict).reset_index()
    
    print("Dynamically reindexing and flagging zero-arrival days...")
    df['is_real_trade'] = 1
    
    all_groups = []
    for (mandi, district, state, variety), group in df.groupby(['mandi_name', 'district', 'state', 'variety']):
        actual_start = group['arrival_date'].min()
        actual_end = group['arrival_date'].max()
        group = group.set_index('arrival_date')
        full_date_range = pd.date_range(start=actual_start, end=actual_end, freq='D')
        group = group.reindex(full_date_range)
        group.index.name = 'arrival_date'
        group['is_real_trade'] = group['is_real_trade'].fillna(0).astype(int)
        static_cols = ['mandi_name', 'district', 'state', 'variety']
        group[static_cols] = group[static_cols].ffill().bfill()
        price_cols = ['min_price', 'max_price', 'modal_price']
        group[price_cols] = group[price_cols].ffill()
        all_groups.append(group.reset_index())
    
    df_continuous = pd.concat(all_groups, ignore_index=True)
    
    print(f"  Continuous records: {len(df_continuous)}")
    return df_continuous


def add_calendar_features(df_continuous):
    """Add calendar and holiday features."""
    print("Generating calendar and holiday features...")
    ind_holidays = holidays.India(years=range(2021, 2027))
    
    df_continuous['day_of_week'] = df_continuous['arrival_date'].dt.dayofweek
    df_continuous['month'] = df_continuous['arrival_date'].dt.month
    df_continuous['day_of_year'] = df_continuous['arrival_date'].dt.dayofyear
    df_continuous['is_weekend'] = df_continuous['day_of_week'].isin([5, 6]).astype(int)
    df_continuous['is_holiday'] = df_continuous['arrival_date'].apply(lambda x: 1 if x in ind_holidays else 0)
    
    return df_continuous


def add_fourier_terms(df):
    """Add Fourier seasonality terms."""
    df['sin_365_1'] = np.sin(2 * np.pi * df['day_of_year'] / 365.25)
    df['cos_365_1'] = np.cos(2 * np.pi * df['day_of_year'] / 365.25)
    df['sin_365_2'] = np.sin(4 * np.pi * df['day_of_year'] / 365.25)
    df['cos_365_2'] = np.cos(4 * np.pi * df['day_of_year'] / 365.25)
    return df


def engineer_1day_features(df_continuous):
    """Engineer lag/rolling features for 1-day horizon."""
    print("\nCalculating 1-Day Horizon features...")
    mandi_group = df_continuous.groupby(['mandi_name', 'variety'])
    
    df_continuous['price_lag_1'] = mandi_group['modal_price'].shift(1)
    df_continuous['price_lag_2'] = mandi_group['modal_price'].shift(2)
    df_continuous['price_lag_3'] = mandi_group['modal_price'].shift(3)
    df_continuous['price_lag_7'] = mandi_group['modal_price'].shift(7)
    
    df_continuous['price_roll_mean_7'] = mandi_group['modal_price'].transform(lambda x: x.shift(1).rolling(window=7).mean())
    df_continuous['price_roll_std_7'] = mandi_group['modal_price'].transform(lambda x: x.shift(1).rolling(window=7).std())
    df_continuous['price_roll_mean_30'] = mandi_group['modal_price'].transform(lambda x: x.shift(1).rolling(window=30).mean())
    df_continuous['price_expanding_mean'] = mandi_group['modal_price'].transform(lambda x: x.shift(1).expanding().mean())
    
    df_continuous = add_fourier_terms(df_continuous)
    
    # Target: Tomorrow's price
    df_continuous['target_price'] = mandi_group['modal_price'].shift(-1)
    
    # Cleanup
    df_final = df_continuous.dropna(subset=['target_price', 'price_roll_mean_30', 'price_lag_7']).copy()
    return df_final


def engineer_7day_features(df_continuous):
    """Engineer lag/rolling features for 7-day horizon."""
    print("\nCalculating 7-Day Horizon features...")
    
    df_continuous['price_lag_7'] = df_continuous.groupby('mandi_name')['modal_price'].shift(7)
    df_continuous['price_lag_8'] = df_continuous.groupby('mandi_name')['modal_price'].shift(8)
    df_continuous['price_lag_9'] = df_continuous.groupby('mandi_name')['modal_price'].shift(9)
    df_continuous['price_lag_14'] = df_continuous.groupby('mandi_name')['modal_price'].shift(14)
    df_continuous['price_lag_30'] = df_continuous.groupby('mandi_name')['modal_price'].shift(30)
    
    df_continuous['price_roll_mean_7'] = df_continuous.groupby('mandi_name')['price_lag_7'].transform(lambda x: x.rolling(window=7, min_periods=1).mean())
    df_continuous['price_roll_std_7'] = df_continuous.groupby('mandi_name')['price_lag_7'].transform(lambda x: x.rolling(window=7, min_periods=1).std())
    df_continuous['price_roll_mean_30'] = df_continuous.groupby('mandi_name')['price_lag_7'].transform(lambda x: x.rolling(window=30, min_periods=1).mean())
    df_continuous['price_expanding_mean'] = df_continuous.groupby('mandi_name')['price_lag_7'].transform(lambda x: x.expanding().mean())
    
    df_final = df_continuous.dropna(subset=['modal_price', 'price_roll_mean_30', 'price_lag_30']).copy()
    df_final = add_fourier_terms(df_final)
    
    # Target: price 7 days out
    df_final['target_price'] = df_continuous.groupby('mandi_name')['modal_price'].shift(-7)
    df_final = df_final.dropna(subset=['target_price', 'price_roll_mean_30', 'price_lag_7']).copy()
    
    return df_final


def engineer_15day_features(df_continuous):
    """Engineer lag/rolling features for 15-day horizon."""
    print("\nCalculating 15-Day Horizon features...")
    
    df_continuous['price_lag_15'] = df_continuous.groupby('mandi_name')['modal_price'].shift(15)
    df_continuous['price_lag_16'] = df_continuous.groupby('mandi_name')['modal_price'].shift(16)
    df_continuous['price_lag_17'] = df_continuous.groupby('mandi_name')['modal_price'].shift(17)
    df_continuous['price_lag_30'] = df_continuous.groupby('mandi_name')['modal_price'].shift(30)
    
    df_continuous['price_roll_mean_7'] = df_continuous.groupby('mandi_name')['price_lag_15'].transform(lambda x: x.rolling(window=7, min_periods=1).mean())
    df_continuous['price_roll_std_7'] = df_continuous.groupby('mandi_name')['price_lag_15'].transform(lambda x: x.rolling(window=7, min_periods=1).std())
    df_continuous['price_roll_mean_30'] = df_continuous.groupby('mandi_name')['price_lag_15'].transform(lambda x: x.rolling(window=30, min_periods=1).mean())
    df_continuous['price_expanding_mean'] = df_continuous.groupby('mandi_name')['price_lag_15'].transform(lambda x: x.expanding().mean())
    
    df_final = df_continuous.dropna(subset=['modal_price', 'price_roll_mean_30', 'price_lag_30']).copy()
    df_final = add_fourier_terms(df_final)
    
    # Target: price 15 days out
    df_final['target_price'] = df_continuous.groupby('mandi_name')['modal_price'].shift(-15)
    df_final = df_final.dropna(subset=['target_price', 'price_roll_mean_30', 'price_lag_15']).copy()
    
    return df_final


def engineer_30day_features(df_continuous):
    """Engineer lag/rolling features for 30-day horizon."""
    print("\nCalculating 30-Day Horizon features...")
    
    df_continuous['price_lag_30'] = df_continuous.groupby('mandi_name')['modal_price'].shift(30)
    df_continuous['price_lag_31'] = df_continuous.groupby('mandi_name')['modal_price'].shift(31)
    df_continuous['price_lag_32'] = df_continuous.groupby('mandi_name')['modal_price'].shift(32)
    df_continuous['price_lag_45'] = df_continuous.groupby('mandi_name')['modal_price'].shift(45)
    
    df_continuous['price_roll_mean_7'] = df_continuous.groupby('mandi_name')['price_lag_30'].transform(lambda x: x.rolling(window=7, min_periods=1).mean())
    df_continuous['price_roll_std_7'] = df_continuous.groupby('mandi_name')['price_lag_30'].transform(lambda x: x.rolling(window=7, min_periods=1).std())
    df_continuous['price_roll_mean_30'] = df_continuous.groupby('mandi_name')['price_lag_30'].transform(lambda x: x.rolling(window=30, min_periods=1).mean())
    df_continuous['price_expanding_mean'] = df_continuous.groupby('mandi_name')['price_lag_30'].transform(lambda x: x.expanding().mean())
    
    df_final = df_continuous.dropna(subset=['modal_price', 'price_roll_mean_30', 'price_lag_30']).copy()
    df_final = add_fourier_terms(df_final)
    
    # Target: price 30 days out
    df_final['target_price'] = df_continuous.groupby('mandi_name')['modal_price'].shift(-30)
    df_final = df_final.dropna(subset=['target_price', 'price_roll_mean_30', 'price_lag_30']).copy()
    
    return df_final


def main():
    # =========================================================
    # STEP 1: Load and Clean Base Data
    # =========================================================
    df = load_and_clean_base(RAW_DATA_PATH)
    
    # =========================================================
    # STEP 2: Filter Dense Groups
    # =========================================================
    df = filter_dense_groups(df, min_records=100, min_density=0.15)
    
    # =========================================================
    # STEP 3: Remove Outliers
    # =========================================================
    df = remove_outliers(df)
    
    # =========================================================
    # STEP 4: Resolve Duplicates and Reindex
    # =========================================================
    df_continuous = resolve_duplicates_and_reindex(df)
    
    # =========================================================
    # STEP 5: Calendar Features
    # =========================================================
    df_continuous = add_calendar_features(df_continuous)
    
    # =========================================================
    # STEP 6: Engineer Features and Save for Each Horizon
    # =========================================================
    horizon_engineers = {
        '1day': engineer_1day_features,
        '7day': engineer_7day_features,
        '15day': engineer_15day_features,
        '30day': engineer_30day_features,
    }
    
    for horizon, engineer_fn in horizon_engineers.items():
        print(f"\n{'='*60}")
        print(f"Processing {horizon} horizon")
        print(f"{'='*60}")
        
        # Make a copy so each horizon starts from the same base
        df_copy = df_continuous.copy()
        df_final = engineer_fn(df_copy)
        
        csv_filename = os.path.join(OUTPUT_DIR, f'prepared_potato_pune_dynamic_master_{horizon}.csv')
        df_final.to_csv(csv_filename, index=False)
        print(f"[OK] Saved {len(df_final)} records to '{csv_filename}'")
    
    print(f"\n{'='*60}")
    print("DATA CLEANING COMPLETE FOR ALL HORIZONS!")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
