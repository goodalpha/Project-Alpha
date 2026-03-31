# CLI Scripts and Tests Documentation

This document describes the command-line scripts and test suite for the Project-Alpha quantitative trading framework.

## Overview

The project includes:
- **4 CLI scripts** for the data pipeline and model training
- **2 comprehensive test suites** with 50+ test cases covering features and backtesting

## CLI Scripts

All scripts are located in `scripts/` and follow a consistent design pattern:
- Command-line argument parsing with `argparse`
- Structured logging with `loguru`
- Progress tracking with `tqdm`
- Configuration management via YAML

### 1. `scripts/download_data.py`

Downloads raw market data from external sources.

**Usage:**
```bash
python scripts/download_data.py [--config CONFIG] [--start-date DATE] [--end-date DATE] \
    [--universe {sp500,nasdaq100}] [--skip-fundamentals]
```

**Arguments:**
- `--config` (default: `config/defaults.yaml`) - Path to configuration file
- `--start-date` (default: 5 years ago) - Start date (YYYY-MM-DD format)
- `--end-date` (default: today) - End date (YYYY-MM-DD format)
- `--universe` - Override universe source (sp500 or nasdaq100)
- `--skip-fundamentals` - Skip downloading fundamentals (slow optional step)
- `--verbose` - Enable debug logging

**Examples:**
```bash
# Download 5 years of S&P 500 data
python scripts/download_data.py --start-date 2020-01-01

# Download Nasdaq-100 without fundamentals
python scripts/download_data.py --universe nasdaq100 --skip-fundamentals

# Use custom configuration
python scripts/download_data.py --config config/custom.yaml
```

**Pipeline Steps:**
1. Load configuration from YAML
2. Build trading universe (scrape S&P 500/Nasdaq-100 tickers or use custom list)
3. Download OHLCV prices for all tickers + SPY benchmark
4. Download macroeconomic data from FRED (8+ series by default)
5. Download fundamentals (optional, slow)
6. Print download summary with counts and file sizes

**Data Locations:**
- Prices: `data/raw/prices/`
- Macro: `data/raw/macro/`
- Fundamentals: `data/raw/fundamentals/`

---

### 2. `scripts/build_features.py`

Builds feature matrix from downloaded data.

**Usage:**
```bash
python scripts/build_features.py [--config CONFIG]
```

**Arguments:**
- `--config` (default: `config/defaults.yaml`) - Configuration file path
- `--verbose` - Enable debug logging

**Examples:**
```bash
python scripts/build_features.py

python scripts/build_features.py --config config/custom.yaml --verbose
```

**Pipeline Steps:**
1. Load configuration
2. Load universe metadata
3. Load price data from cache and convert to wide format
4. Load macro data with forward-fill to daily frequency
5. Load fundamental data (if available)
6. Build feature matrix by orchestrating:
   - Price features (momentum, volatility, technical indicators)
   - Macro features (yield curve, regime indicators)
   - Fundamental features (valuation, profitability)
   - Cross-sectional transformations (z-scoring, sector neutralization)
7. Compute targets (forward returns, excess returns, vol-adjusted returns)
8. Save feature matrix and targets to parquet files

**Output Files:**
- `data/processed/features.parquet` - Main feature matrix
- `data/processed/target_*.parquet` - Target variables (one file per target)

**Feature Matrix Structure:**
- Index: MultiIndex of (date, ticker)
- Columns: Feature names (momentum, vol, macro indicators, etc.)
- Shape: ~252 dates × 500 tickers × 100+ features

---

### 3. `scripts/train_models.py`

Trains machine learning models using walk-forward cross-validation.

**Usage:**
```bash
python scripts/train_models.py [--config CONFIG] [--model {elastic_net,xgboost,ensemble}] \
    [--target TARGET] [--no-mlflow]
```

**Arguments:**
- `--config` (default: `config/defaults.yaml`) - Configuration file path
- `--model` (default: ensemble) - Model type: elastic_net, xgboost, or ensemble
- `--target` (default: from config) - Target variable name
- `--no-mlflow` - Disable MLflow experiment tracking
- `--verbose` - Enable debug logging

**Examples:**
```bash
# Train ensemble model on default target
python scripts/train_models.py

# Train XGBoost on custom target
python scripts/train_models.py --model xgboost --target fwd_ret_5d_xs

# Skip MLflow tracking
python scripts/train_models.py --no-mlflow

# Verbose logging
python scripts/train_models.py --verbose
```

**Pipeline Steps:**
1. Load configuration and select target
2. Load feature matrix and target variables
3. Run walk-forward validation with embargo periods:
   - Train: 5 years of data (configurable)
   - Validation: 6 months (configurable)
   - Test: 6 months (configurable)
   - Embargo: 10 days between sets (prevents leakage)
4. For each fold:
   - Train model on training set
   - Validate and compute metrics
5. Compute fold-level metrics:
   - Information Coefficient (IC) - correlation of predictions and returns
   - Rank IC (Spearman correlation)
   - ICIR = Mean IC / Std IC
6. Print summary statistics across folds
7. Save predictions to parquet for backtesting

**Output Files:**
- `data/processed/predictions.parquet` - Model predictions for backtesting

**Metrics:**
- **IC**: Pearson correlation between predictions and realized returns
- **Rank IC**: Spearman correlation (rank-based)
- **ICIR**: IC Information Ratio (mean IC / std IC)

---

### 4. `scripts/run_backtest.py`

Runs backtest on strategy predictions and generates performance reports.

**Usage:**
```bash
python scripts/run_backtest.py [--config CONFIG] [--predictions PATH] [--output-dir DIR]
```

**Arguments:**
- `--config` (default: `config/defaults.yaml`) - Configuration file path
- `--predictions` (default: `data/processed/predictions.parquet`) - Predictions file path
- `--output-dir` (default: `results/backtest`) - Output directory for results
- `--verbose` - Enable debug logging

**Examples:**
```bash
# Run standard backtest
python scripts/run_backtest.py

# Use custom predictions file
python scripts/run_backtest.py --predictions custom_predictions.parquet

# Save results to custom directory
python scripts/run_backtest.py --output-dir results/bt_v2

# Verbose output
python scripts/run_backtest.py --verbose
```

**Pipeline Steps:**
1. Load configuration
2. Load predictions, prices, universe, and macro data
3. Detect market regime from VIX or macro data
4. Run backtest engine:
   - For each rebalance date (weekly by default)
   - Select top 20% by signal
   - Compute vol-parity weights
   - Apply regime exposure multiplier
   - Apply position and sector limits
   - Apply transaction costs
5. Compute daily portfolio returns between rebalances
6. Calculate performance metrics:
   - Total return
   - Annual volatility
   - Sharpe ratio
   - Maximum drawdown
   - Win rate
7. Save results (metrics, returns, positions, turnover)

**Output Files:**
- `results/backtest/metrics.json` - Performance metrics (JSON)
- `results/backtest/portfolio_returns.parquet` - Daily returns
- `results/backtest/positions.parquet` - Portfolio holdings
- `results/backtest/turnover.parquet` - Rebalance turnover
- `results/backtest/tearsheet.txt` - Summary report (text)

**Key Metrics:**
- **Total Return**: Cumulative return over backtest period
- **Sharpe Ratio**: Risk-adjusted return (mean return / volatility × √252)
- **Max Drawdown**: Largest peak-to-trough decline
- **Win Rate**: Fraction of positive return days

---

## Test Suites

Tests are located in `tests/` and use **synthetic data** to avoid external dependencies. All tests are reproducible with fixed random seeds.

### Run Tests

```bash
# Install pytest if needed
pip install pytest pytest-cov

# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=src --cov-report=html

# Run specific test file
pytest tests/test_features.py -v

# Run specific test class
pytest tests/test_features.py::TestMomentumNoLookahead -v

# Run with verbose output
pytest tests/ -vv
```

---

## Test 1: `tests/test_features.py`

Comprehensive tests for feature engineering pipeline. **514 lines, 25+ test cases.**

### Test Classes

#### **TestMomentumNoLookahead** (3 tests)
Tests for lookahead bias in momentum features.

- `test_momentum_uses_only_past_data()` - Verify momentum on date T uses only T and earlier
- `test_momentum_computation()` - Check manual momentum computation

#### **TestVolatilityComputation** (3 tests)
Validates volatility feature calculations.

- `test_vol_annualization()` - Verify annualization (×√252)
- `test_vol_rolling_window()` - Check rolling window behavior
- `test_vol_differs_by_stock()` - Verify volatility varies across stocks

#### **TestCrossSectionalZscore** (2 tests)
Tests z-score normalization per date.

- `test_zscore_mean_zero_std_one()` - Mean=0, std=1 after z-scoring
- `test_zscore_clipping()` - Clipping at ±3.0 removes outliers

#### **TestSectorNeutralization** (1 test)
Validates sector-neutral feature construction.

- `test_sector_means_zero_after_neutralization()` - Sector means ≈ 0 after neutralization

#### **TestRankNormalize** (1 test)
Tests rank normalization to [-0.5, 0.5] scale.

- `test_rank_normalize_range()` - Rank-normalized values in [-0.5, 0.5]

#### **TestTargetNoLookahead** (3 tests)
Critical tests for target variable point-in-time safety.

- `test_forward_return_no_future_data()` - Forward 5d return on T doesn't use T+1...T+5
- `test_excess_return_computation()` - Excess return = stock - benchmark
- `test_target_last_5_dates_nan()` - Last 5 dates have NaN targets

#### **TestVolatilityAdjustedTarget** (1 test)
Tests volatility-adjusted return targets.

- `test_vol_adjusted_lower_variance()` - Vol-adjusted returns have lower variance

#### **TestMacroForwardFill** (1 test)
Tests macro data forward-fill to daily.

- `test_macro_ffill_daily_frequency()` - Macro forward-filled to daily frequency

#### **TestVIXRegime** (1 test)
Tests VIX-based regime detection.

- `test_vix_regime_thresholds()` - Regimes properly ordered by VIX level

#### **TestFeaturePipeline** (3 tests)
Integration tests for full feature pipeline.

- `test_feature_shapes_consistent()` - All features have consistent shapes
- `test_feature_temporal_alignment()` - Features on same date align
- `test_no_lookahead_across_features()` - No features leak future information

### Fixtures

- `synthetic_prices` - 300 days of OHLCV data for 5 stocks
- `synthetic_macro` - Macro data with 5 series
- `synthetic_universe` - Universe metadata with sectors

---

## Test 2: `tests/test_backtest.py`

Comprehensive tests for backtesting engine. **530 lines, 25+ test cases.**

### Test Classes

#### **TestWeightsSumToOne** (3 tests)
Validates that portfolio weights sum to 1.0 (long-only).

- `test_equal_weights_sum_to_one()` - Equal weights sum to 1.0
- `test_vol_parity_weights_sum_to_one()` - Vol-parity weights sum to 1.0
- `test_conviction_weighted_sum_to_one()` - Conviction weights sum to 1.0

#### **TestPositionCap** (2 tests)
Tests maximum position size constraints.

- `test_position_cap_enforced()` - No position exceeds 5% cap
- `test_cap_reduces_largest_positions()` - Capping reduces largest holdings

#### **TestSectorCap** (2 tests)
Tests maximum sector exposure constraints.

- `test_sector_cap_enforced()` - No sector exceeds 30% cap
- `test_sector_concentration_reduction()` - Capping reduces concentration

#### **TestTransactionCostsPositive** (3 tests)
Validates transaction cost calculations.

- `test_turnover_creates_cost()` - High turnover creates positive costs
- `test_no_rebalance_no_cost()` - No rebalancing = zero costs
- `test_cost_scales_with_turnover()` - Costs scale linearly with turnover

#### **TestZeroReturnNoSignal** (3 tests)
Tests behavior with no/equal signals.

- `test_equal_signals_equal_weights()` - Equal signals → equal weights
- `test_ranking_preserves_order()` - Signal ranking is preserved
- `test_top_pct_selection()` - Top 20% selection selects 20%

#### **TestRegimeReducesExposure** (2 tests)
Tests regime-based exposure reduction.

- `test_regime_multipliers()` - Exposure decreases with regime
- `test_portfolio_leverage_by_regime()` - Leverage reduced in stress regimes

#### **TestDrawdownHalt** (3 tests)
Tests drawdown-based trading halts.

- `test_drawdown_detection()` - Drawdown computed correctly
- `test_halt_at_threshold()` - Trading halts at 15% drawdown
- `test_exposure_multiplier_zero()` - Exposure = 0 when halted

#### **TestPerformanceMetrics** (5 tests)
Tests computation of performance metrics.

- `test_sharpe_constant_returns()` - Sharpe for constant returns
- `test_sharpe_random_walk()` - Sharpe ratio for random walk
- `test_max_drawdown_monotonic_increase()` - Max DD = 0 for monotonic increase
- `test_max_drawdown_crash()` - Max DD captures crashes
- `test_total_return_computation()` - Total return = cumulative product

#### **TestICComputation** (5 tests)
Critical tests for Information Coefficient calculation.

- `test_ic_perfect_ranking()` - Perfect predictions → IC = 1.0
- `test_ic_inverse_ranking()` - Inverse predictions → IC = -1.0
- `test_ic_random_predictions()` - Random predictions → IC ≈ 0
- `test_rank_ic_vs_ic()` - Rank IC vs regular IC comparison
- `test_ic_with_nan_handling()` - IC handles NaN values correctly

#### **ICIR Computation** (2 tests)
Tests Information Coefficient Information Ratio.

- `test_icir_mean_std()` - ICIR = mean IC / std IC
- `test_icir_time_series()` - ICIR from daily IC series

### Fixtures

- `synthetic_signals` - 252 days of 20 stock signals
- `synthetic_prices` - 252 days of 20 stock prices
- `synthetic_volatilities` - Volatility computed from prices
- `config` - Default backtest configuration

---

## Test Coverage

**Total: 50+ test cases covering:**

### Features
- ✓ Lookahead bias prevention (price, targets)
- ✓ Feature calculations (momentum, volatility, technicals)
- ✓ Cross-sectional transformations (z-score, rank, sector neutral)
- ✓ Target computation (forward returns, excess returns, vol-adjusted)
- ✓ Macro feature processing (forward-fill, regimes)
- ✓ End-to-end pipeline consistency

### Backtesting
- ✓ Portfolio weight constraints (sum to 1, position caps, sector caps)
- ✓ Transaction costs (turnover, slippage, commission)
- ✓ Signal handling (ranking, top-N selection)
- ✓ Risk management (regime exposure, drawdown halts)
- ✓ Performance metrics (Sharpe, drawdown, returns)
- ✓ Information Coefficient (IC, Rank IC, ICIR)

### Key Testing Principles

1. **Synthetic Data Only** - No external API calls or file dependencies
2. **Reproducibility** - Fixed random seeds for deterministic results
3. **Edge Cases** - NaN handling, boundary conditions, zero cases
4. **Point-in-Time Safety** - No lookahead bias in features/targets
5. **Mathematical Correctness** - Verify formulas and calculations
6. **Integration** - End-to-end pipeline consistency

---

## Typical Workflow

### 1. Download Data
```bash
python scripts/download_data.py --start-date 2020-01-01 --end-date 2024-12-31
```
**Duration:** 30-60 minutes (network dependent)

### 2. Build Features
```bash
python scripts/build_features.py
```
**Duration:** 5-15 minutes

### 3. Train Models
```bash
python scripts/train_models.py --model ensemble
```
**Duration:** 30-60 minutes

### 4. Backtest
```bash
python scripts/run_backtest.py
```
**Duration:** 2-5 minutes

### 5. Run Tests
```bash
pytest tests/ -v --cov=src
```
**Duration:** <1 minute

---

## Configuration

All scripts use configuration from `config/defaults.yaml`:

```yaml
# Universe
universe:
  source: "sp500"  # sp500, nasdaq100, or custom
  min_avg_dollar_volume: 5_000_000

# Features
features:
  price:
    momentum_windows: [5, 10, 21, 63, 126, 252]
    vol_windows: [21, 63]
  cross_sectional:
    zscore_clip: 3.0
    sector_neutralize: true

# Validation (for model training)
validation:
  train_years: 5
  val_months: 6
  test_months: 6
  embargo_days: 10

# Portfolio
portfolio:
  top_pct: 0.20  # Long top 20%
  max_position_pct: 0.05  # 5% cap per stock
  max_sector_pct: 0.30  # 30% cap per sector
  rebalance_freq: "weekly"

# Costs
costs:
  slippage_bps: 5
  spread_bps: 3
  market_impact_coeff: 0.1
```

---

## Troubleshooting

### Missing Modules
```bash
pip install -r requirements.txt
```

### Pytest Not Found
```bash
pip install pytest pytest-cov
```

### PYTHONPATH Issues
Scripts automatically add project root to path, but if running from elsewhere:
```bash
export PYTHONPATH=/home/user/Project-Alpha:$PYTHONPATH
python scripts/download_data.py
```

### Data Files Not Found
Ensure you run `download_data.py` before `build_features.py`:
```bash
python scripts/download_data.py  # Creates data/raw/
python scripts/build_features.py  # Reads from data/raw/, writes to data/processed/
```

---

## Files Summary

| File | Type | Lines | Tests |
|------|------|-------|-------|
| `scripts/download_data.py` | CLI | 295 | - |
| `scripts/build_features.py` | CLI | 285 | - |
| `scripts/train_models.py` | CLI | 340 | - |
| `scripts/run_backtest.py` | CLI | 410 | - |
| `tests/test_features.py` | Test | 514 | 25+ |
| `tests/test_backtest.py` | Test | 530 | 25+ |
| **Total** | | **2,374** | **50+** |

---

## Next Steps

1. **Install dependencies**: `pip install -r requirements.txt`
2. **Run tests**: `pytest tests/ -v`
3. **Download data**: `python scripts/download_data.py --start-date 2020-01-01`
4. **Build features**: `python scripts/build_features.py`
5. **Train models**: `python scripts/train_models.py`
6. **Backtest**: `python scripts/run_backtest.py`

---

## References

- **Point-in-time safety**: Features on date T must not use data from T+1 onward
- **Information Coefficient**: Correlation between predictions and realized returns
- **Sharpe Ratio**: (Mean Return - Risk-free Rate) / Standard Deviation × √252
- **Walk-forward validation**: Train on expanding window, validate on future period
- **Embargo period**: Gap between training and validation/test to prevent leakage
