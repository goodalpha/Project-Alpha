"""
PROJECT ATLAS - Configuration (Improved v2)
Centralized configuration with validation and sensible defaults

Improvements:
- Comprehensive documentation for all settings
- Type hints for all configuration values
- Validation of critical settings
- Grouped logical organization
- Environment variable support
- Fallback defaults for robustness
- Better comments and explanations
"""

import os
from pathlib import Path
from typing import Optional
import logging

# ============================================================================
# PATHS & DIRECTORIES
# ============================================================================

# Project root directory
PROJECT_ROOT = Path(__file__).parent.absolute()

# Data directory for storing OHLCV and other data
DATA_DIR = PROJECT_ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)

# Backtesting and results
BACKTEST_DIR = PROJECT_ROOT / "backtest"
BACKTEST_DIR.mkdir(exist_ok=True)

# Logs directory
LOGS_DIR = PROJECT_ROOT / "logs"
LOGS_DIR.mkdir(exist_ok=True)

# Models directory
MODELS_DIR = PROJECT_ROOT / "models"
MODELS_DIR.mkdir(exist_ok=True)

# Cache directory for intermediate data
CACHE_DIR = PROJECT_ROOT / ".cache"
CACHE_DIR.mkdir(exist_ok=True)

# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================

# Log level: DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

# Log format with timestamp, logger name, level, and message
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# Log file rotation (in bytes)
LOG_ROTATION_SIZE = 10_000_000  # 10 MB

# ============================================================================
# TRADING CONFIGURATION
# ============================================================================

# Paper trading capital
INITIAL_CAPITAL = float(os.getenv("INITIAL_CAPITAL", 100_000))

# Position sizing
POSITION_SIZE_PCT = float(os.getenv("POSITION_SIZE_PCT", 0.03))  # 3% per position
MAX_POSITIONS = int(os.getenv("MAX_POSITIONS", 20))
MIN_POSITION_VALUE = float(os.getenv("MIN_POSITION_VALUE", 100))

# Slippage and transaction costs (simulated)
SLIPPAGE_PCT = float(os.getenv("SLIPPAGE_PCT", 0.02))  # 2%
COMMISSION_PCT = float(os.getenv("COMMISSION_PCT", 0.001))  # 0.1%

# Rebalancing frequency
REBALANCE_FREQUENCY = os.getenv("REBALANCE_FREQUENCY", "monthly")  # daily, weekly, monthly

# ============================================================================
# MODEL CONFIGURATION
# ============================================================================

# XGBoost hyperparameters
XGBOOST_PARAMS = {
    "n_estimators": int(os.getenv("XGBOOST_N_ESTIMATORS", 100)),
    "max_depth": int(os.getenv("XGBOOST_MAX_DEPTH", 5)),
    "learning_rate": float(os.getenv("XGBOOST_LEARNING_RATE", 0.1)),
    "subsample": float(os.getenv("XGBOOST_SUBSAMPLE", 0.8)),
    "colsample_bytree": float(os.getenv("XGBOOST_COLSAMPLE_BYTREE", 0.8)),
    "objective": "binary:logistic",
    "eval_metric": "logloss",
}

# Model training parameters
TRAIN_TEST_SPLIT = float(os.getenv("TRAIN_TEST_SPLIT", 0.8))
VALIDATION_SPLIT = float(os.getenv("VALIDATION_SPLIT", 0.1))
RANDOM_STATE = int(os.getenv("RANDOM_STATE", 42))
EARLY_STOPPING_ROUNDS = int(os.getenv("EARLY_STOPPING_ROUNDS", 10))

# Feature engineering
FEATURE_LOOKBACK_DAYS = int(os.getenv("FEATURE_LOOKBACK_DAYS", 252))  # 1 year
FEATURE_LIST = [
    "momentum_20",      # 20-day momentum
    "momentum_60",      # 60-day momentum
    "volatility_20",    # 20-day volatility
    "volatility_60",    # 60-day volatility
    "rsi_14",          # 14-day RSI
    "macd",            # MACD signal
    "bb_position",     # Bollinger Band position
    "pe_ratio",        # Price-to-Earnings ratio
    "pb_ratio",        # Price-to-Book ratio
    "dividend_yield",  # Dividend yield
]

# ============================================================================
# BACKTESTING CONFIGURATION
# ============================================================================

# Walk-forward testing parameters
WALK_FORWARD_TRAIN_MONTHS = int(os.getenv("WF_TRAIN_MONTHS", 36))  # 3 years
WALK_FORWARD_TEST_MONTHS = int(os.getenv("WF_TEST_MONTHS", 6))     # 6 months
WALK_FORWARD_ROLL_MONTHS = int(os.getenv("WF_ROLL_MONTHS", 3))     # Roll quarterly

# Backtesting universe
BACKTEST_UNIVERSE = [
    # Large cap tech
    "AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA",
    # Financial services
    "JPM", "BAC", "WFC", "GS", "MS", "BLK",
    # Healthcare
    "JNJ", "UNH", "PFE", "ABBV", "CVS",
    # Consumer
    "WMT", "KO", "PG", "MCD", "SBUX",
    # Energy
    "XOM", "CVX", "COP",
    # Industrial
    "BA", "CAT", "LMT",
    # Semiconductors
    "INTC", "AMD", "QCOM", "AVGO",
    # Other
    "CISCO", "ORCL", "IBM", "ADBE", "NFLX",
]

# Minimum volume for backtesting (daily average)
MIN_BACKTEST_VOLUME = int(os.getenv("MIN_BACKTEST_VOLUME", 1_000_000))

# ============================================================================
# RISK MANAGEMENT CONFIGURATION
# ============================================================================

# Position risk limits
MAX_POSITION_SIZE = float(os.getenv("MAX_POSITION_SIZE", 0.10))  # 10% max per position
MAX_SECTOR_WEIGHT = float(os.getenv("MAX_SECTOR_WEIGHT", 0.30))  # 30% per sector

# Portfolio risk limits
MAX_PORTFOLIO_LEVERAGE = float(os.getenv("MAX_PORTFOLIO_LEVERAGE", 1.5))
MAX_DAILY_LOSS = float(os.getenv("MAX_DAILY_LOSS", 0.02))  # 2% daily loss limit
MAX_DRAWDOWN = float(os.getenv("MAX_DRAWDOWN", 0.10))  # 10% max drawdown

# Stop loss and take profit
DEFAULT_STOP_LOSS = float(os.getenv("DEFAULT_STOP_LOSS", 0.05))  # 5% stop loss
DEFAULT_TAKE_PROFIT = float(os.getenv("DEFAULT_TAKE_PROFIT", 0.10))  # 10% take profit

# Volatility scaling
USE_VOLATILITY_SCALING = os.getenv("USE_VOLATILITY_SCALING", "true").lower() == "true"
VOLATILITY_TARGET = float(os.getenv("VOLATILITY_TARGET", 0.15))  # 15% annual vol

# Crisis mode triggers
CRISIS_MODE_VIX = float(os.getenv("CRISIS_MODE_VIX", 30))  # VIX > 30
CRISIS_MODE_DRAWDOWN = float(os.getenv("CRISIS_MODE_DRAWDOWN", 0.05))  # 5% DD
CRISIS_MODE_POSITION_SCALE = float(os.getenv("CRISIS_MODE_POSITION_SCALE", 0.5))  # 50% size

# ============================================================================
# DATA SOURCES CONFIGURATION
# ============================================================================

# Alpha Vantage API
ALPHA_VANTAGE_API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY", "")
ALPHA_VANTAGE_BASE_URL = "https://www.alphavantage.co/query"
ALPHA_VANTAGE_TIMEOUT = int(os.getenv("ALPHA_VANTAGE_TIMEOUT", 30))

# yfinance configuration
YFINANCE_TIMEOUT = int(os.getenv("YFINANCE_TIMEOUT", 30))
YFINANCE_THREADS = int(os.getenv("YFINANCE_THREADS", 4))
YFINANCE_RETRY_COUNT = int(os.getenv("YFINANCE_RETRY_COUNT", 3))

# TradingView configuration
TRADINGVIEW_LOGIN_TIMEOUT = int(os.getenv("TRADINGVIEW_LOGIN_TIMEOUT", 30))
TRADINGVIEW_SCRAPE_TIMEOUT = int(os.getenv("TRADINGVIEW_SCRAPE_TIMEOUT", 60))
TRADINGVIEW_UPDATE_INTERVAL = int(os.getenv("TRADINGVIEW_UPDATE_INTERVAL", 300))  # 5 minutes
TRADINGVIEW_CHROMEDRIVER_PATH = os.getenv("TRADINGVIEW_CHROMEDRIVER_PATH", "/usr/local/bin/chromedriver")

# ============================================================================
# BROKER CONFIGURATION
# ============================================================================

# Alpaca (paper trading)
APCA_API_BASE_URL = os.getenv("APCA_API_BASE_URL", "https://paper-api.alpaca.markets")
APCA_API_KEY_ID = os.getenv("APCA_API_KEY_ID", "")
APCA_API_SECRET_KEY = os.getenv("APCA_API_SECRET_KEY", "")
ALPACA_PAPER_TRADING = True

# ============================================================================
# FEATURE ENGINEERING CONFIGURATION
# ============================================================================

# Feature scaling
FEATURE_SCALE_METHOD = os.getenv("FEATURE_SCALE_METHOD", "zscore")  # zscore, minmax, robust
FEATURE_FILL_METHOD = os.getenv("FEATURE_FILL_METHOD", "forward")   # forward, backward, linear

# Feature selection
FEATURE_CORRELATION_THRESHOLD = float(os.getenv("FEATURE_CORR_THRESHOLD", 0.95))
FEATURE_IMPORTANCE_THRESHOLD = float(os.getenv("FEATURE_IMPORTANCE_THRESHOLD", 0.01))

# Technical indicators
RSI_PERIOD = int(os.getenv("RSI_PERIOD", 14))
MACD_FAST = int(os.getenv("MACD_FAST", 12))
MACD_SLOW = int(os.getenv("MACD_SLOW", 26))
MACD_SIGNAL = int(os.getenv("MACD_SIGNAL", 9))
BB_PERIOD = int(os.getenv("BB_PERIOD", 20))
BB_STD = float(os.getenv("BB_STD", 2.0))

# ============================================================================
# PERFORMANCE & METRICS CONFIGURATION
# ============================================================================

# Benchmark configuration
BENCHMARK_SYMBOL = os.getenv("BENCHMARK_SYMBOL", "SPY")
BENCHMARK_RISK_FREE_RATE = float(os.getenv("RISK_FREE_RATE", 0.04))  # 4%

# Performance metrics
METRICS_LOOKBACK_PERIODS = [1, 3, 6, 12]  # months
STATISTICS_ANNUAL_PERIODS = 252  # trading days per year
STATISTICS_ANNUAL_PERIODS_MONTHS = 12

# ============================================================================
# NOTIFICATION & ALERT CONFIGURATION
# ============================================================================

# Email notifications
ENABLE_EMAIL_ALERTS = os.getenv("ENABLE_EMAIL_ALERTS", "false").lower() == "true"
EMAIL_SMTP_SERVER = os.getenv("EMAIL_SMTP_SERVER", "")
EMAIL_SMTP_PORT = int(os.getenv("EMAIL_SMTP_PORT", 587))
EMAIL_FROM_ADDRESS = os.getenv("EMAIL_FROM_ADDRESS", "")
EMAIL_TO_ADDRESS = os.getenv("EMAIL_TO_ADDRESS", "")

# Slack notifications
ENABLE_SLACK_ALERTS = os.getenv("ENABLE_SLACK_ALERTS", "false").lower() == "true"
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")

# ============================================================================
# DASHBOARD CONFIGURATION
# ============================================================================

# Streamlit dashboard settings
DASHBOARD_REFRESH_INTERVAL = int(os.getenv("DASHBOARD_REFRESH_INTERVAL", 30))  # seconds
DASHBOARD_TIMEZONE = os.getenv("DASHBOARD_TIMEZONE", "America/New_York")
DASHBOARD_THEME = os.getenv("DASHBOARD_THEME", "light")

# Chart configuration
CHART_CANDLESTICK_PERIOD = os.getenv("CHART_CANDLESTICK_PERIOD", "daily")
CHART_SHOW_VOLUME = os.getenv("CHART_SHOW_VOLUME", "true").lower() == "true"
CHART_SHOW_INDICATORS = os.getenv("CHART_SHOW_INDICATORS", "true").lower() == "true"

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def validate_configuration() -> bool:
    """
    Validate critical configuration settings.

    Returns:
        True if all validations pass, False otherwise
    """
    issues = []

    # Validate capital
    if INITIAL_CAPITAL <= 0:
        issues.append(f"INITIAL_CAPITAL must be positive: {INITIAL_CAPITAL}")

    # Validate position size
    if not (0 < POSITION_SIZE_PCT <= 1):
        issues.append(f"POSITION_SIZE_PCT must be 0-1: {POSITION_SIZE_PCT}")

    # Validate max positions
    if MAX_POSITIONS <= 0:
        issues.append(f"MAX_POSITIONS must be positive: {MAX_POSITIONS}")

    # Validate risk limits
    if not (0 < MAX_DAILY_LOSS < 1):
        issues.append(f"MAX_DAILY_LOSS must be 0-1: {MAX_DAILY_LOSS}")

    if not (0 < MAX_DRAWDOWN < 1):
        issues.append(f"MAX_DRAWDOWN must be 0-1: {MAX_DRAWDOWN}")

    # Log validation results
    if issues:
        logger = logging.getLogger(__name__)
        for issue in issues:
            logger.error(f"Configuration error: {issue}")
        return False

    return True


def get_config_summary() -> str:
    """
    Get a summary of current configuration.

    Returns:
        Formatted string with configuration details
    """
    summary = f"""
PROJECT ATLAS - Configuration Summary
=====================================
Capital:                ${INITIAL_CAPITAL:,.0f}
Position Size:          {POSITION_SIZE_PCT:.1%}
Max Positions:          {MAX_POSITIONS}
Max Daily Loss:         {MAX_DAILY_LOSS:.1%}
Max Drawdown:           {MAX_DRAWDOWN:.1%}
Slippage:               {SLIPPAGE_PCT:.1%}
Commission:             {COMMISSION_PCT:.1%}
Log Level:              {LOG_LEVEL}
Rebalance Frequency:    {REBALANCE_FREQUENCY}
"""
    return summary


if __name__ == "__main__":
    # Print configuration summary
    print(get_config_summary())

    # Validate configuration
    if validate_configuration():
        print("✅ Configuration validation passed")
    else:
        print("❌ Configuration validation failed")
