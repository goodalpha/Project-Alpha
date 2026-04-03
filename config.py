"""
PROJECT ATLAS - Configuration & Constants
Minimum Viable Product (MVP) v1.0
"""

import os
from dataclasses import dataclass
from pathlib import Path

# ============================================================================
# PATHS
# ============================================================================
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
FEATURES_DIR = BASE_DIR / "features"
MODELS_DIR = BASE_DIR / "models"
BACKTEST_DIR = BASE_DIR / "backtest"
EXECUTION_DIR = BASE_DIR / "execution"
LOGS_DIR = BASE_DIR / "logs"

# Ensure directories exist
for directory in [DATA_DIR, FEATURES_DIR, MODELS_DIR, BACKTEST_DIR, EXECUTION_DIR, LOGS_DIR]:
    directory.mkdir(exist_ok=True)

# ============================================================================
# MVP SPECIFICATION
# ============================================================================

# Universe: S&P 500 constituents
UNIVERSE_SIZE = 500

# Model horizon: 1-month forward return
FORECAST_HORIZON_DAYS = 21
FORECAST_HORIZON_NAME = "1M"

# Backtesting parameters
BACKTEST_TRAIN_MONTHS = 36  # 3 years
BACKTEST_TEST_MONTHS = 6    # 6 months
BACKTEST_ROLL_MONTHS = 3    # Quarterly roll-forward

# Feature parameters
NUM_FEATURES = 10
SECTOR_RELATIVE_FEATURES = True

# Position management
MAX_POSITIONS = 30  # Top 30 stocks by predicted probability
MIN_POSITIONS = 20
MAX_POSITION_SIZE = 0.05  # 5% of NAV per position
MAX_SECTOR_EXPOSURE = 0.25  # 25% of NAV per sector
MIN_CASH_BUFFER = 0.05  # 5% minimum cash

# Risk management
MAX_SINGLE_LOSS = -0.15  # -15% trailing stop-loss per position
MAX_PORTFOLIO_LOSS = -0.10  # -10% from HWM triggers 50% cash
TARGET_PORTFOLIO_VOL = 0.12  # 12% annualized

# Execution parameters
REBALANCE_FREQUENCY_DAYS = 7  # Weekly rebalance (Friday close)
MIN_ADV = 5_000_000  # Minimum average daily volume
TRANSACTION_COST_BPS = 10  # 10 basis points round-trip
SLIPPAGE_PCT = 0.00075  # 0.075% slippage model

# Data sources
YFINANCE_DATA_REFRESH_HOURS = 4
DATA_STALENESS_WARNING_HOURS = 2
DATA_STALENESS_CRITICAL_HOURS = 48

# ============================================================================
# MVP FEATURE SET
# ============================================================================

FEATURES_CONFIG = {
    "momentum_12_1": {
        "name": "12-1 Month Momentum (Sector-Relative)",
        "type": "price",
        "lookback_days": 252,
        "sector_relative": True,
        "description": "Most robust cross-sectional predictor. Skip last month to avoid reversal."
    },
    "ev_ebitda": {
        "name": "EV/EBITDA (Sector-Relative)",
        "type": "valuation",
        "sector_relative": True,
        "description": "Value signal. Sector-relative removes structural sector differences."
    },
    "fcf_yield": {
        "name": "FCF Yield",
        "type": "quality",
        "description": "Quality of earnings signal. Cash beats accounting."
    },
    "realized_vol": {
        "name": "20-Day Realized Volatility (Rank)",
        "type": "volatility",
        "lookback_days": 20,
        "sector_relative": True,
        "description": "Low-vol anomaly. Low-vol stocks outperform risk-adjusted."
    },
    "earnings_surprise": {
        "name": "Earnings Surprise (Last Quarter)",
        "type": "earnings",
        "lookback_days": 90,
        "description": "Post-earnings drift persists for 60+ days."
    },
    "insider_buying": {
        "name": "Net Insider Buying (90 Days)",
        "type": "insider",
        "lookback_days": 90,
        "description": "Information asymmetry signal."
    },
    "mean_reversion": {
        "name": "3M vs 12M Price Ratio (Mean Reversion)",
        "type": "price",
        "lookback_days": 252,
        "sector_relative": True,
        "description": "Stocks that have pulled back from highs tend to revert."
    },
    "credit_spread_regime": {
        "name": "Credit Spread Change (30-Day)",
        "type": "macro",
        "lookback_days": 30,
        "description": "Macro risk appetite. Market-level, applies as regime modifier."
    },
    "piotroski_fscore": {
        "name": "Piotroski F-Score",
        "type": "fundamental",
        "description": "Composite fundamental quality. 0-9 score, well-validated."
    },
    "volume_ratio": {
        "name": "Volume Ratio (20D / 60D)",
        "type": "volume",
        "lookback_days": 60,
        "description": "Institutional accumulation signal. Rising relative volume = interest."
    },
}

# ============================================================================
# MODEL PARAMETERS
# ============================================================================

XGBOOST_PARAMS = {
    "max_depth": 5,
    "n_estimators": 200,
    "learning_rate": 0.05,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "objective": "binary:logistic",
    "eval_metric": "logloss",
    "random_state": 42,
    "n_jobs": -1,
    "tree_method": "hist",
}

# ============================================================================
# LOGGING
# ============================================================================

LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
