# Quick Start Guide

## Installation

```bash
pip install -r requirements.txt
```

## Download Data

```bash
# Download 5 years of S&P 500 data (default)
python scripts/download_data.py --start-date 2020-01-01

# Or with Nasdaq-100 and skip fundamentals (faster)
python scripts/download_data.py --universe nasdaq100 --skip-fundamentals

# Custom date range
python scripts/download_data.py --start-date 2015-01-01 --end-date 2024-12-31
```

**Typical duration:** 30-60 minutes

**Outputs:**
- `data/raw/prices/` - OHLCV price data
- `data/raw/macro/` - Macroeconomic time series
- `data/raw/fundamentals/` - Company fundamentals (optional)

## Build Features

```bash
# Build feature matrix from downloaded data
python scripts/build_features.py

# With verbose output
python scripts/build_features.py --verbose
```

**Typical duration:** 5-15 minutes

**Outputs:**
- `data/processed/features.parquet` - Feature matrix
- `data/processed/target_*.parquet` - Target variables

## Train Models

```bash
# Train ensemble model (default)
python scripts/train_models.py

# Or train specific model
python scripts/train_models.py --model xgboost

# Train on specific target
python scripts/train_models.py --target fwd_ret_5d_xs

# Skip MLflow tracking
python scripts/train_models.py --no-mlflow
```

**Typical duration:** 30-60 minutes

**Outputs:**
- `data/processed/predictions.parquet` - Model predictions
- Console output: IC, Rank IC, ICIR metrics

## Run Backtest

```bash
# Run backtest on predictions
python scripts/run_backtest.py

# Use custom predictions file
python scripts/run_backtest.py --predictions custom_predictions.parquet

# Save to custom directory
python scripts/run_backtest.py --output-dir results/bt_v2
```

**Typical duration:** 2-5 minutes

**Outputs:**
- `results/backtest/metrics.json` - Performance metrics (JSON)
- `results/backtest/portfolio_returns.parquet` - Daily returns
- `results/backtest/positions.parquet` - Portfolio holdings
- `results/backtest/tearsheet.txt` - Summary report

## Run Tests

```bash
# Run all tests
pytest tests/ -v

# Run with coverage report
pytest tests/ --cov=src --cov-report=html

# Run specific test file
pytest tests/test_features.py -v

# Run specific test class
pytest tests/test_features.py::TestMomentumNoLookahead -v
```

**Typical duration:** <1 minute

## Full Workflow

```bash
# 1. Download (30-60 min)
python scripts/download_data.py --start-date 2020-01-01

# 2. Build Features (5-15 min)
python scripts/build_features.py

# 3. Train Models (30-60 min)
python scripts/train_models.py --model ensemble

# 4. Backtest (2-5 min)
python scripts/run_backtest.py

# 5. Test (< 1 min)
pytest tests/ -v

# Total: ~2-3 hours (first run)
```

## Configuration

All scripts use `config/defaults.yaml`. Key settings:

```yaml
universe:
  source: "sp500"  # sp500, nasdaq100, or custom

portfolio:
  top_pct: 0.20         # Long top 20%
  max_position_pct: 0.05  # 5% per stock
  max_sector_pct: 0.30    # 30% per sector

validation:
  train_years: 5      # Training period
  embargo_days: 10    # Leakage prevention
```

## Key Arguments

### download_data.py
- `--config` - Configuration file
- `--start-date` - Start date (YYYY-MM-DD)
- `--end-date` - End date (YYYY-MM-DD)
- `--universe` - sp500, nasdaq100
- `--skip-fundamentals` - Skip slow download

### build_features.py
- `--config` - Configuration file
- `--verbose` - Debug logging

### train_models.py
- `--config` - Configuration file
- `--model` - elastic_net, xgboost, ensemble
- `--target` - Target variable name
- `--no-mlflow` - Disable MLflow

### run_backtest.py
- `--config` - Configuration file
- `--predictions` - Predictions file path
- `--output-dir` - Output directory

All scripts support:
- `--verbose` - Enable debug logging
- `--help` - Show help message

## Documentation

- **SCRIPTS_TESTS_README.md** - Complete documentation
- **IMPLEMENTATION_SUMMARY.txt** - Technical details

## Troubleshooting

**Missing modules:**
```bash
pip install -r requirements.txt
```

**Pytest not found:**
```bash
pip install pytest pytest-cov
```

**Data files not found:**
Ensure scripts are run in order:
1. download_data.py (creates data/raw/)
2. build_features.py (reads data/raw/, writes data/processed/)
3. train_models.py (reads data/processed/)
4. run_backtest.py (reads data/processed/)

**PYTHONPATH issues:**
Scripts automatically add project root to path. If running from elsewhere:
```bash
export PYTHONPATH=/home/user/Project-Alpha:$PYTHONPATH
python scripts/download_data.py
```

## Output Files

```
data/
├── raw/
│   ├── prices/ - OHLCV data
│   ├── macro/ - Macro time series
│   └── fundamentals/ - Company fundamentals
├── processed/
│   ├── features.parquet - Feature matrix
│   ├── target_*.parquet - Targets
│   └── predictions.parquet - Model predictions

results/
└── backtest/
    ├── metrics.json - Performance metrics
    ├── portfolio_returns.parquet - Daily returns
    ├── positions.parquet - Holdings
    └── tearsheet.txt - Summary
```

## Key Metrics

### Model Performance
- **IC** - Information Coefficient (correlation with returns)
- **Rank IC** - Spearman correlation
- **ICIR** - IC Information Ratio (mean/std)

### Backtest Performance
- **Total Return** - Cumulative return
- **Sharpe Ratio** - Risk-adjusted return
- **Max Drawdown** - Largest peak-to-trough decline
- **Win Rate** - % of positive return days

## Example Output

```
Download Summary:
- Universe: 504 tickers (including SPY)
- Date range: 2020-01-01 to 2024-12-31
- Cache size: 2.5 GB

Feature Matrix:
- Shape: 1,250 dates × 504 tickers × 120+ features
- Coverage: 99% non-missing
- Date range: 2020-01-01 to 2024-12-31

Model Performance:
- Mean IC: 0.0523
- Mean Rank IC: 0.0487
- ICIR: 1.42

Backtest Results:
- Total Return: +45.2%
- Sharpe Ratio: 1.87
- Max Drawdown: -18.5%
- Win Rate: 51.2%
```

## Next Steps

1. Download historical data
2. Run tests to validate
3. Train and backtest models
4. Analyze results
5. Iterate on configurations

See **SCRIPTS_TESTS_README.md** for complete documentation.
