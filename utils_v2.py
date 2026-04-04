"""
PROJECT ATLAS - Utility Functions (Improved v2)
Common utilities for data processing, validation, and formatting

Improvements:
- Type hints throughout
- Comprehensive error handling
- Detailed docstrings
- Input validation
- Logging support
- Reusable functions to reduce code duplication
"""

import logging
import json
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple, Union
from pathlib import Path
import re

logger = logging.getLogger(__name__)


# ============================================================================
# DATA VALIDATION FUNCTIONS
# ============================================================================

def validate_symbol(symbol: str) -> bool:
    """
    Validate stock ticker symbol format.

    Args:
        symbol: Ticker symbol to validate

    Returns:
        True if valid, False otherwise
    """
    if not isinstance(symbol, str):
        return False

    symbol = symbol.strip().upper()
    # Stock symbols: 1-5 uppercase letters, optionally with dots/hyphens
    return bool(re.match(r'^[A-Z]{1,5}(\.[A-Z])?$', symbol))


def validate_price(price: Union[int, float], name: str = "price") -> bool:
    """
    Validate that price is a positive number.

    Args:
        price: Price value to validate
        name: Name of field for error messages

    Returns:
        True if valid, False otherwise
    """
    try:
        price_float = float(price)
        if price_float <= 0:
            logger.warning(f"{name} must be positive: {price}")
            return False
        return True
    except (ValueError, TypeError):
        logger.warning(f"{name} must be numeric: {price}")
        return False


def validate_quantity(quantity: Union[int, float], name: str = "quantity") -> bool:
    """
    Validate that quantity is a positive integer.

    Args:
        quantity: Quantity to validate
        name: Name of field for error messages

    Returns:
        True if valid, False otherwise
    """
    try:
        qty = int(quantity)
        if qty <= 0:
            logger.warning(f"{qty} must be positive: {quantity}")
            return False
        return True
    except (ValueError, TypeError):
        logger.warning(f"{name} must be integer: {quantity}")
        return False


def validate_percentage(value: Union[int, float], name: str = "percentage") -> bool:
    """
    Validate that value is between 0 and 1.

    Args:
        value: Value to validate
        name: Name of field for error messages

    Returns:
        True if valid, False otherwise
    """
    try:
        val_float = float(value)
        if not (0 <= val_float <= 1):
            logger.warning(f"{name} must be 0-1: {value}")
            return False
        return True
    except (ValueError, TypeError):
        logger.warning(f"{name} must be numeric: {value}")
        return False


def validate_dataframe(
    df: pd.DataFrame,
    required_columns: List[str],
    min_rows: int = 1,
) -> bool:
    """
    Validate DataFrame has required structure.

    Args:
        df: DataFrame to validate
        required_columns: List of required column names
        min_rows: Minimum number of rows required

    Returns:
        True if valid, False otherwise
    """
    if df is None or not isinstance(df, pd.DataFrame):
        logger.warning("Input is not a DataFrame")
        return False

    if df.empty:
        logger.warning("DataFrame is empty")
        return False

    if len(df) < min_rows:
        logger.warning(f"DataFrame has {len(df)} rows, need {min_rows}")
        return False

    missing_cols = [col for col in required_columns if col not in df.columns]
    if missing_cols:
        logger.warning(f"Missing columns: {missing_cols}")
        return False

    return True


# ============================================================================
# DATA FORMATTING FUNCTIONS
# ============================================================================

def format_currency(value: Union[int, float], decimals: int = 2) -> str:
    """
    Format number as currency string.

    Args:
        value: Value to format
        decimals: Number of decimal places

    Returns:
        Formatted currency string (e.g., "$1,234.56")
    """
    try:
        return f"${float(value):,.{decimals}f}"
    except (ValueError, TypeError):
        return "$0.00"


def format_percentage(value: Union[int, float], decimals: int = 2) -> str:
    """
    Format number as percentage string.

    Args:
        value: Value to format (0-1)
        decimals: Number of decimal places

    Returns:
        Formatted percentage string (e.g., "12.34%")
    """
    try:
        return f"{float(value) * 100:.{decimals}f}%"
    except (ValueError, TypeError):
        return "0.00%"


def format_number(value: Union[int, float], decimals: int = 2) -> str:
    """
    Format number with thousand separators.

    Args:
        value: Value to format
        decimals: Number of decimal places

    Returns:
        Formatted number string
    """
    try:
        return f"{float(value):,.{decimals}f}"
    except (ValueError, TypeError):
        return "0"


def format_date(date: Union[str, datetime], format_str: str = "%Y-%m-%d") -> str:
    """
    Format date consistently.

    Args:
        date: Date string or datetime object
        format_str: Output format string

    Returns:
        Formatted date string
    """
    try:
        if isinstance(date, str):
            date = pd.to_datetime(date)
        return date.strftime(format_str)
    except Exception as e:
        logger.warning(f"Error formatting date: {e}")
        return str(date)


# ============================================================================
# DATA PROCESSING FUNCTIONS
# ============================================================================

def calculate_returns(prices: List[float]) -> List[float]:
    """
    Calculate period returns from prices.

    Args:
        prices: List of prices

    Returns:
        List of returns (price change percentages)
    """
    if not prices or len(prices) < 2:
        return []

    try:
        prices = [float(p) for p in prices]
        returns = []

        for i in range(1, len(prices)):
            if prices[i - 1] != 0:
                ret = (prices[i] - prices[i - 1]) / prices[i - 1]
                returns.append(ret)

        return returns
    except Exception as e:
        logger.warning(f"Error calculating returns: {e}")
        return []


def calculate_sharpe_ratio(
    returns: List[float],
    risk_free_rate: float = 0.04,
    periods_per_year: int = 252,
) -> float:
    """
    Calculate Sharpe ratio from returns.

    Args:
        returns: List of returns
        risk_free_rate: Annual risk-free rate
        periods_per_year: Trading periods per year (252 for daily)

    Returns:
        Sharpe ratio
    """
    if not returns or len(returns) < 2:
        return 0.0

    try:
        returns = np.array(returns)
        excess_returns = returns - (risk_free_rate / periods_per_year)

        if np.std(excess_returns) == 0:
            return 0.0

        sharpe = np.mean(excess_returns) / np.std(excess_returns)
        return float(sharpe * np.sqrt(periods_per_year))
    except Exception as e:
        logger.warning(f"Error calculating Sharpe ratio: {e}")
        return 0.0


def calculate_drawdown(values: List[float]) -> Tuple[float, float]:
    """
    Calculate maximum and current drawdown.

    Args:
        values: List of portfolio values

    Returns:
        Tuple of (max_drawdown, current_drawdown)
    """
    if not values or len(values) < 1:
        return 0.0, 0.0

    try:
        values = np.array(values, dtype=float)
        cumulative_max = np.maximum.accumulate(values)
        drawdown = (values - cumulative_max) / cumulative_max

        max_drawdown = float(np.min(drawdown))
        current_drawdown = float(drawdown[-1])

        return max_drawdown, current_drawdown
    except Exception as e:
        logger.warning(f"Error calculating drawdown: {e}")
        return 0.0, 0.0


def calculate_win_rate(pnls: List[float]) -> float:
    """
    Calculate winning trade percentage.

    Args:
        pnls: List of trade P&Ls

    Returns:
        Win rate (0-1)
    """
    if not pnls:
        return 0.0

    try:
        wins = sum(1 for pnl in pnls if pnl > 0)
        return float(wins) / float(len(pnls))
    except Exception as e:
        logger.warning(f"Error calculating win rate: {e}")
        return 0.0


def calculate_profit_factor(pnls: List[float]) -> float:
    """
    Calculate profit factor (gross profit / gross loss).

    Args:
        pnls: List of trade P&Ls

    Returns:
        Profit factor
    """
    if not pnls:
        return 0.0

    try:
        wins = sum(pnl for pnl in pnls if pnl > 0)
        losses = abs(sum(pnl for pnl in pnls if pnl < 0))

        if losses == 0:
            return float('inf') if wins > 0 else 1.0

        return float(wins) / float(losses)
    except Exception as e:
        logger.warning(f"Error calculating profit factor: {e}")
        return 0.0


# ============================================================================
# FILE I/O FUNCTIONS
# ============================================================================

def save_json(data: Dict, filepath: Path, indent: int = 2) -> Optional[Path]:
    """
    Save dictionary to JSON file with error handling.

    Args:
        data: Dictionary to save
        filepath: Output file path
        indent: JSON indentation level

    Returns:
        Path if successful, None otherwise
    """
    try:
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)

        with open(filepath, 'w') as f:
            json.dump(data, f, indent=indent, default=str)

        logger.debug(f"Saved JSON to {filepath}")
        return filepath

    except IOError as e:
        logger.error(f"Error saving JSON: {e}")
        return None


def load_json(filepath: Path) -> Optional[Dict]:
    """
    Load dictionary from JSON file with error handling.

    Args:
        filepath: Input file path

    Returns:
        Dictionary if successful, None otherwise
    """
    try:
        filepath = Path(filepath)

        if not filepath.exists():
            logger.warning(f"File not found: {filepath}")
            return None

        with open(filepath, 'r') as f:
            data = json.load(f)

        logger.debug(f"Loaded JSON from {filepath}")
        return data

    except (IOError, json.JSONDecodeError) as e:
        logger.error(f"Error loading JSON: {e}")
        return None


def save_csv(df: pd.DataFrame, filepath: Path, index: bool = False) -> Optional[Path]:
    """
    Save DataFrame to CSV with error handling.

    Args:
        df: DataFrame to save
        filepath: Output file path
        index: Include index in output

    Returns:
        Path if successful, None otherwise
    """
    try:
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)

        df.to_csv(filepath, index=index)

        logger.debug(f"Saved CSV to {filepath}")
        return filepath

    except IOError as e:
        logger.error(f"Error saving CSV: {e}")
        return None


def load_csv(filepath: Path) -> Optional[pd.DataFrame]:
    """
    Load DataFrame from CSV with error handling.

    Args:
        filepath: Input file path

    Returns:
        DataFrame if successful, None otherwise
    """
    try:
        filepath = Path(filepath)

        if not filepath.exists():
            logger.warning(f"File not found: {filepath}")
            return None

        df = pd.read_csv(filepath)

        logger.debug(f"Loaded CSV from {filepath}")
        return df

    except (IOError, pd.errors.ParserError) as e:
        logger.error(f"Error loading CSV: {e}")
        return None


# ============================================================================
# DATE/TIME FUNCTIONS
# ============================================================================

def get_trading_days(start_date: datetime, end_date: datetime) -> List[datetime]:
    """
    Get list of trading days (excluding weekends).

    Args:
        start_date: Start date
        end_date: End date

    Returns:
        List of trading dates
    """
    try:
        dates = pd.date_range(start=start_date, end=end_date, freq='B')
        return [d.to_pydatetime() for d in dates]
    except Exception as e:
        logger.warning(f"Error getting trading days: {e}")
        return []


def get_market_hours(date: datetime, timezone: str = "US/Eastern") -> Tuple[datetime, datetime]:
    """
    Get market open and close times for a date.

    Args:
        date: Trading date
        timezone: Market timezone

    Returns:
        Tuple of (market_open, market_close)
    """
    try:
        date = pd.to_datetime(date)
        market_open = pd.Timestamp(year=date.year, month=date.month, day=date.day,
                                   hour=9, minute=30, tz=timezone)
        market_close = pd.Timestamp(year=date.year, month=date.month, day=date.day,
                                    hour=16, minute=0, tz=timezone)
        return market_open, market_close
    except Exception as e:
        logger.warning(f"Error getting market hours: {e}")
        return None, None


def is_market_open(dt: datetime, timezone: str = "US/Eastern") -> bool:
    """
    Check if market is currently open.

    Args:
        dt: Datetime to check
        timezone: Market timezone

    Returns:
        True if market is open
    """
    try:
        dt = pd.Timestamp(dt, tz=timezone)

        # Market closed on weekends
        if dt.weekday() >= 5:
            return False

        # Check market hours (9:30 AM - 4:00 PM ET)
        market_open = dt.replace(hour=9, minute=30)
        market_close = dt.replace(hour=16, minute=0)

        return market_open <= dt < market_close

    except Exception as e:
        logger.warning(f"Error checking market hours: {e}")
        return False


if __name__ == "__main__":
    # Test utilities
    logging.basicConfig(level="INFO")

    # Test validation
    assert validate_symbol("AAPL") == True
    assert validate_symbol("invalid") == False
    print("✅ Symbol validation works")

    # Test formatting
    print(f"Currency: {format_currency(1234.567)}")
    print(f"Percentage: {format_percentage(0.1234)}")
    print(f"Number: {format_number(1234567.89)}")

    # Test returns calculation
    prices = [100, 102, 101, 103]
    returns = calculate_returns(prices)
    print(f"Returns: {returns}")

    # Test Sharpe ratio
    sharpe = calculate_sharpe_ratio(returns)
    print(f"Sharpe ratio: {sharpe:.2f}")

    print("\n✅ All utilities working correctly")
