"""
Probabilistic Model Training Pipeline for Potato - All Horizons (1d, 7d, 15d, 30d)
Adapted from the existing Onion model training notebooks.
Trains Quantile LightGBM models (p10, p50, p90) for each horizon.
"""

import pandas as pd
import numpy as np
import lightgbm as lgb
import os
import sys
import warnings
from sklearn.metrics import mean_absolute_error, mean_absolute_percentage_error, mean_squared_error

warnings.filterwarnings('ignore')

DATA_DIR = '../../data/potato'
MODELS_DIR = '../../models/potato'

# =========================================================
# HORIZON-SPECIFIC CONFIGURATIONS
# =========================================================
HORIZON_CONFIGS = {
    '1day': {
        'data_file': 'final_model_ready_pune_data_potato_1day.csv',
        'split_date': '2025-03-01',
        'drop_cols': ['arrival_date', 'target_price', 'commodity'],
        'base_params': {
            'boosting_type': 'gbdt',
            'learning_rate': 0.03,
            'feature_fraction': 0.8,
            'bagging_fraction': 0.8,
            'bagging_freq': 5,
            'verbose': -1,
            'random_state': 42
        },
        'quantile_configs': {
            'p50': {
                'alpha': 0.50, 'max_depth': 9, 'num_leaves': 45,
                'min_data_in_leaf': 20, 'lambda_l1': 0.1, 'lambda_l2': 0.1
            },
            'p10': {
                'alpha': 0.10, 'max_depth': 5, 'num_leaves': 20,
                'min_data_in_leaf': 50, 'lambda_l1': 1.5, 'lambda_l2': 1.0
            },
            'p90': {
                'alpha': 0.90, 'max_depth': 5, 'num_leaves': 20,
                'min_data_in_leaf': 50, 'lambda_l1': 1.5, 'lambda_l2': 1.0
            }
        },
        'num_boost_round': 2000,
        'early_stopping_rounds': 50,
    },
    '7day': {
        'data_file': 'final_model_ready_pune_data_potato_7day.csv',
        'split_date': '2024-11-01',
        'drop_cols': ['arrival_date', 'target_price', 'commodity', 'modal_price', 'min_price', 'max_price'],
        'base_params': {
            'boosting_type': 'gbdt',
            'learning_rate': 0.01,
            'feature_fraction': 0.8,
            'bagging_fraction': 0.8,
            'bagging_freq': 5,
            'verbose': -1,
            'random_state': 42
        },
        'quantile_configs': {
            'p50': {
                'alpha': 0.50, 'max_depth': 10, 'num_leaves': 63,
                'min_data_in_leaf': 15, 'lambda_l1': 0.1, 'lambda_l2': 0.1
            },
            'p10': {
                'alpha': 0.05, 'max_depth': 6, 'num_leaves': 31,
                'min_data_in_leaf': 30, 'lambda_l1': 1.0, 'lambda_l2': 1.0
            },
            'p90': {
                'alpha': 0.95, 'max_depth': 6, 'num_leaves': 31,
                'min_data_in_leaf': 30, 'lambda_l1': 1.0, 'lambda_l2': 1.0
            }
        },
        'num_boost_round': 3000,
        'early_stopping_rounds': 100,
    },
    '15day': {
        'data_file': 'final_model_ready_pune_data_potato_15day.csv',
        'split_date': '2024-11-01',
        'drop_cols': ['arrival_date', 'target_price', 'commodity', 'modal_price', 'min_price', 'max_price'],
        'base_params': {
            'boosting_type': 'gbdt',
            'learning_rate': 0.01,
            'feature_fraction': 0.8,
            'bagging_fraction': 0.8,
            'bagging_freq': 5,
            'verbose': -1,
            'random_state': 42
        },
        'quantile_configs': {
            'p50': {
                'alpha': 0.50, 'max_depth': 10, 'num_leaves': 63,
                'min_data_in_leaf': 15, 'lambda_l1': 0.1, 'lambda_l2': 0.1
            },
            'p10': {
                'alpha': 0.05, 'max_depth': 6, 'num_leaves': 31,
                'min_data_in_leaf': 30, 'lambda_l1': 1.0, 'lambda_l2': 1.0
            },
            'p90': {
                'alpha': 0.95, 'max_depth': 6, 'num_leaves': 31,
                'min_data_in_leaf': 30, 'lambda_l1': 1.0, 'lambda_l2': 1.0
            }
        },
        'num_boost_round': 3000,
        'early_stopping_rounds': 100,
    },
    '30day': {
        'data_file': 'final_model_ready_pune_data_potato_30day.csv',
        'split_date': '2024-11-01',
        'drop_cols': ['arrival_date', 'target_price', 'commodity', 'modal_price', 'min_price', 'max_price'],
        'base_params': {
            'boosting_type': 'gbdt',
            'learning_rate': 0.01,
            'feature_fraction': 0.8,
            'bagging_fraction': 0.8,
            'bagging_freq': 5,
            'verbose': -1,
            'random_state': 42
        },
        'quantile_configs': {
            'p50': {
                'alpha': 0.50, 'max_depth': 10, 'num_leaves': 63,
                'min_data_in_leaf': 15, 'lambda_l1': 0.1, 'lambda_l2': 0.1
            },
            'p10': {
                'alpha': 0.05, 'max_depth': 6, 'num_leaves': 31,
                'min_data_in_leaf': 30, 'lambda_l1': 1.0, 'lambda_l2': 1.0
            },
            'p90': {
                'alpha': 0.95, 'max_depth': 6, 'num_leaves': 31,
                'min_data_in_leaf': 30, 'lambda_l1': 1.0, 'lambda_l2': 1.0
            }
        },
        'num_boost_round': 3000,
        'early_stopping_rounds': 100,
    },
}


def train_horizon(horizon_name, config):
    """Train all 3 quantile models for a single horizon."""
    print(f"\n{'='*60}")
    print(f"TRAINING {horizon_name.upper()} HORIZON MODELS")
    print(f"{'='*60}")
    
    # 1. Load Data
    data_path = os.path.join(DATA_DIR, config['data_file'])
    if not os.path.exists(data_path):
        print(f"ERROR: Data file not found: {data_path}")
        print("Please run data_cleaning_potato.py and adding_temp_data_potato.py first!")
        return None
    
    print(f"Loading data from: {data_path}")
    df = pd.read_csv(data_path)
    df['arrival_date'] = pd.to_datetime(df['arrival_date'])
    df = df.sort_values(by='arrival_date').reset_index(drop=True)
    
    print(f"Dataset Shape: {df.shape}")
    print(f"Date Range: {df['arrival_date'].min().date()} to {df['arrival_date'].max().date()}")
    
    # 2. Encode Categoricals
    categorical_cols = ['mandi_name', 'district', 'state', 'variety']
    for col in categorical_cols:
        if col in df.columns:
            df[col] = df[col].astype('category')
    
    # 3. Chronological Split
    split_date = config['split_date']
    train_df = df[df['arrival_date'] < split_date].copy()
    test_df = df[df['arrival_date'] >= split_date].copy()
    
    if len(test_df) == 0:
        # If no test data with current split, use 80/20 split
        split_idx = int(len(df) * 0.8)
        train_df = df.iloc[:split_idx].copy()
        test_df = df.iloc[split_idx:].copy()
        print(f"  (Adjusted split to 80/20 due to date range)")
    
    print(f"Training: {len(train_df)} rows ({train_df['arrival_date'].min().date()} to {train_df['arrival_date'].max().date()})")
    print(f"Testing:  {len(test_df)} rows ({test_df['arrival_date'].min().date()} to {test_df['arrival_date'].max().date()})")
    
    # 4. Separate Features and Target
    drop_cols = config['drop_cols']
    
    X_train = train_df.drop(columns=drop_cols, errors='ignore')
    y_train = train_df['target_price']
    X_test = test_df.drop(columns=drop_cols, errors='ignore')
    y_test = test_df['target_price']
    
    print(f"Features ({X_train.shape[1]}): {list(X_train.columns)}")
    
    # 5. Create LightGBM Datasets
    cat_cols_present = [c for c in categorical_cols if c in X_train.columns]
    lgb_train = lgb.Dataset(X_train, label=y_train, categorical_feature=cat_cols_present, free_raw_data=False)
    lgb_eval = lgb.Dataset(X_test, label=y_test, categorical_feature=cat_cols_present, reference=lgb_train, free_raw_data=False)
    
    # 6. Train Models
    base_params = config['base_params']
    quantile_configs = config['quantile_configs']
    models = {}
    
    print(f"\nStarting Probabilistic Training ({horizon_name})...\n")
    
    for name, qconfig in quantile_configs.items():
        print(f"--- Training {name} Model (Alpha={qconfig['alpha']}) ---")
        
        params = {**base_params, **qconfig}
        params['objective'] = 'quantile'
        params['metric'] = 'quantile'
        
        callbacks = [
            lgb.early_stopping(stopping_rounds=config['early_stopping_rounds'], first_metric_only=False),
            lgb.log_evaluation(period=500)
        ]
        
        model = lgb.train(
            params,
            lgb_train,
            num_boost_round=config['num_boost_round'],
            valid_sets=[lgb_train, lgb_eval],
            valid_names=['train', 'eval'],
            callbacks=callbacks
        )
        
        models[name] = model
        
        model_path = os.path.join(MODELS_DIR, f"lightgbm_potato_{horizon_name}_{name}.txt")
        model.save_model(model_path)
        print(f"Saved: {model_path}\n")
    
    # 7. Evaluate
    print(f"\n--- {horizon_name.upper()} EVALUATION ---")
    results_df = test_df[['arrival_date', 'mandi_name', 'target_price']].copy()
    
    for name in quantile_configs.keys():
        results_df[f'{name}_pred'] = models[name].predict(X_test)
    
    # Standard Metrics (on p50)
    mae = mean_absolute_error(results_df['target_price'], results_df['p50_pred'])
    rmse = np.sqrt(mean_squared_error(results_df['target_price'], results_df['p50_pred']))
    mape = mean_absolute_percentage_error(results_df['target_price'], results_df['p50_pred'])
    
    # Probabilistic Coverage
    results_df['in_bound'] = (
        (results_df['target_price'] >= results_df['p10_pred']) & 
        (results_df['target_price'] <= results_df['p90_pred'])
    )
    coverage = results_df['in_bound'].mean() * 100
    
    print("=" * 50)
    print(f"FINAL {horizon_name.upper()} HORIZON METRICS")
    print("=" * 50)
    print(f"MAE:  Rs. {mae:.2f}")
    print(f"RMSE: Rs. {rmse:.2f}")
    print(f"MAPE: {mape*100:.2f}%")
    print(f"80% Prediction Interval Coverage: {coverage:.1f}%")
    
    if coverage < 70:
        print("WARNING: Model is overconfident (bands too narrow)")
    elif coverage > 90:
        print("WARNING: Model is underconfident (bands too wide)")
    else:
        print("[OK] Good calibration!")
    print("=" * 50)
    
    return {
        'horizon': horizon_name,
        'mae': mae,
        'rmse': rmse,
        'mape': mape * 100,
        'coverage': coverage,
        'train_size': len(train_df),
        'test_size': len(test_df)
    }


def main():
    os.makedirs(MODELS_DIR, exist_ok=True)
    
    all_results = []
    
    for horizon_name, config in HORIZON_CONFIGS.items():
        result = train_horizon(horizon_name, config)
        if result:
            all_results.append(result)
    
    # Final Summary
    print(f"\n{'='*70}")
    print("COMPLETE POTATO MODEL TRAINING SUMMARY")
    print(f"{'='*70}")
    print(f"{'Horizon':<10} {'MAE':>10} {'RMSE':>10} {'MAPE':>8} {'Coverage':>10} {'Train':>8} {'Test':>8}")
    print("-" * 70)
    for r in all_results:
        print(f"{r['horizon']:<10} Rs.{r['mae']:>8.2f} Rs.{r['rmse']:>8.2f} {r['mape']:>6.2f}% {r['coverage']:>8.1f}% {r['train_size']:>8} {r['test_size']:>8}")
    print(f"{'='*70}")
    
    print(f"\nModels saved to: {os.path.abspath(MODELS_DIR)}")


if __name__ == '__main__':
    main()
