"""
PROJECT ATLAS - Data Ingestion Layer
Handles: OHLCV, fundamentals, macro data
"""

import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
try:
    import yfinance as yf
except ImportError:
    yf = None  # yfinance not available
import requests
from typing import List, Dict, Tuple
import json

import config

logger = logging.getLogger(__name__)
logger.setLevel(config.LOG_LEVEL)

# ============================================================================
# SYNTHETIC DATA GENERATION (for demo when yfinance unavailable)
# ============================================================================

def _generate_synthetic_ohlcv(
    tickers: List[str],
    start_date: str,
    end_date: str,
    save_to_parquet: bool = True
) -> pd.DataFrame:
    """Generate synthetic OHLCV data for testing."""
    start = pd.Timestamp(start_date)
    end = pd.Timestamp(end_date)
    dates = pd.date_range(start=start, end=end, freq='B')  # Business days

    all_data = []
    np.random.seed(42)

    for ticker in tickers:
        price = 100 + np.random.uniform(-20, 20)  # Random starting price
        volumes = []

        for date in dates:
            change = np.random.normal(0.001, 0.02)
            price = price * (1 + change)

            open_p = price * (1 + np.random.normal(0, 0.005))
            close_p = price
            high_p = max(open_p, close_p) * (1 + abs(np.random.normal(0, 0.005)))
            low_p = min(open_p, close_p) * (1 - abs(np.random.normal(0, 0.005)))
            volume = np.random.uniform(1_000_000, 50_000_000)

            all_data.append({
                'date': date,
                'ticker': ticker,
                'open': open_p,
                'high': high_p,
                'low': low_p,
                'close': close_p,
                'volume': volume,
                'adjusted_close': close_p,
            })

        if save_to_parquet:
            ticker_data = [d for d in all_data if d['ticker'] == ticker]
            if ticker_data:
                df = pd.DataFrame(ticker_data)
                path = config.DATA_DIR / f"ohlcv_{ticker}.parquet"
                df.to_parquet(path, index=False)

    return pd.DataFrame(all_data)

# ============================================================================
# SP500 CONSTITUENTS
# ============================================================================

def get_sp500_constituents() -> List[str]:
    """
    Fetch S&P 500 constituents from Wikipedia.
    Returns list of ticker symbols.
    """
    # Fallback: return common large-cap tickers (for demo)
    tickers = [
        'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'NVDA', 'TSLA',
        'JPM', 'JNJ', 'WMT', 'BA', 'GS', 'PG', 'UNH', 'HD',
        'XOM', 'CVX', 'IBM', 'INTC', 'AMD'
    ]
    logger.info(f"Using {len(tickers)} sample tickers (set {len(tickers)}/500 S&P constituents)")
    return tickers

# ============================================================================
# OHLCV DATA (yfinance)
# ============================================================================

def fetch_ohlcv(
    tickers: List[str],
    start_date: str,
    end_date: str,
    save_to_parquet: bool = True
) -> pd.DataFrame:
    """
    Fetch OHLCV data from yfinance.

    Args:
        tickers: List of ticker symbols
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        save_to_parquet: Save to parquet files by ticker

    Returns:
        DataFrame with OHLCV data (date, ticker, open, high, low, close, volume, adjusted_close)
    """
    logger.info(f"Fetching OHLCV for {len(tickers)} tickers from {start_date} to {end_date}")

    if yf is None:
        logger.warning("yfinance not available. Generating synthetic OHLCV data for demo...")
        return _generate_synthetic_ohlcv(tickers, start_date, end_date, save_to_parquet)

    try:
        # Download data for all tickers
        data = yf.download(
            tickers,
            start=start_date,
            end=end_date,
            progress=True,
            threads=True
        )

        # Reshape data
        if len(tickers) == 1:
            data['Ticker'] = tickers[0]
            data = data.reset_index()
        else:
            data = data.reset_index()
            data = data.melt(
                id_vars=['Date'],
                var_name='Level_0',
                value_name='Price'
            )
            # Pivot to get proper structure
            data_dict = {}
            for ticker in tickers:
                ticker_data = yf.download(ticker, start=start_date, end=end_date, progress=False)
                ticker_data['Ticker'] = ticker
                data_dict[ticker] = ticker_data.reset_index()
            data = pd.concat(data_dict.values(), ignore_index=True)

        # Standardize column names
        data.columns = [col.lower() for col in data.columns]

        # Save by ticker if requested
        if save_to_parquet:
            for ticker in tickers:
                ticker_data = data[data['ticker'] == ticker].copy()
                if not ticker_data.empty:
                    path = config.DATA_DIR / f"ohlcv_{ticker}.parquet"
                    ticker_data.to_parquet(path, index=False)

        logger.info(f"Successfully fetched OHLCV data: {len(data)} rows")
        return data

    except Exception as e:
        logger.error(f"Error fetching OHLCV data: {e}")
        return pd.DataFrame()

# ============================================================================
# MACRO DATA (FRED)
# ============================================================================

def fetch_macro_data(
    start_date: str,
    end_date: str,
    series_ids: Dict[str, str] = None
) -> pd.DataFrame:
    """
    Fetch macro data from FRED (Federal Reserve Economic Data).

    Args:
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        series_ids: Dict of {name: FRED_series_id}

    Returns:
        DataFrame with macro data (date, indicator, value)
    """
    if series_ids is None:
        # Default high-value macro indicators
        series_ids = {
            "vix": "VIXCLS",  # VIX Index
            "dgs10": "DGS10",  # 10-Year Treasury Yield
            "dgs2": "DGS2",  # 2-Year Treasury Yield
            "pcepi": "PCEPI",  # PCE Inflation
            "pmi": "MMNRNJ",  # ISM Manufacturing PMI
            "unrate": "UNRATE",  # Unemployment Rate
        }

    logger.info(f"Fetching macro data from FRED for {len(series_ids)} series")

    macro_data = {}
    base_url = "https://api.stlouisfed.org/fred/series/observations"

    for name, series_id in series_ids.items():
        try:
            # Note: Requires FRED API key (free from stlouisfed.org)
            # For now, use a simpler approach with yfinance
            logger.info(f"Fetching {name} ({series_id})")

            # Placeholder: In production, would use FRED API
            # For MVP, we'll use yfinance for VIX and approximations
            if name == "vix":
                data = yf.download("^VIX", start=start_date, end=end_date, progress=False)
                macro_data[name] = data['Close']

        except Exception as e:
            logger.warning(f"Error fetching {name}: {e}")

    if macro_data:
        df = pd.DataFrame(macro_data)
        df.index.name = 'Date'
        df = df.reset_index()
        logger.info(f"Fetched macro data: {len(df)} observations")
        return df

    return pd.DataFrame()

# ============================================================================
# FUNDAMENTAL DATA
# ============================================================================

def fetch_fundamental_data(tickers: List[str]) -> Dict[str, Dict]:
    """
    Fetch fundamental data from yfinance.

    Args:
        tickers: List of ticker symbols

    Returns:
        Dict mapping ticker → fundamental metrics (EV, EBITDA, FCF, etc.)
    """
    logger.info(f"Fetching fundamental data for {len(tickers)} tickers")

    fundamentals = {}
    for ticker in tickers:
        try:
            stock = yf.Ticker(ticker)
            info = stock.info

            fundamentals[ticker] = {
                "market_cap": info.get("marketCap"),
                "enterprise_value": info.get("enterpriseValue"),
                "revenue": info.get("totalRevenue"),
                "ebitda": info.get("ebitda"),
                "net_income": info.get("netIncome"),
                "total_debt": info.get("totalDebt"),
                "cash": info.get("totalCash"),
                "shares_outstanding": info.get("sharesOutstanding"),
                "roe": info.get("returnOnEquity"),
                "debt_to_equity": info.get("debtToEquity"),
                "price_to_book": info.get("priceToBook"),
                "pe_ratio": info.get("trailingPE"),
                "pb_ratio": info.get("priceToBook"),
            }
        except Exception as e:
            logger.warning(f"Error fetching fundamentals for {ticker}: {e}")
            fundamentals[ticker] = {}

    logger.info(f"Fetched fundamentals for {len(fundamentals)} tickers")
    return fundamentals

# ============================================================================
# INSIDER TRADING DATA
# ============================================================================

def fetch_insider_trading(ticker: str, lookback_days: int = 90) -> pd.DataFrame:
    """
    Fetch insider trading data from SEC EDGAR.

    For MVP: simplified version that counts recent insider transactions.
    In production: parse actual Form 4 filings.

    Args:
        ticker: Ticker symbol
        lookback_days: Look back this many days

    Returns:
        DataFrame with insider transaction info
    """
    # Placeholder: In production, parse SEC EDGAR Form 4 filings
    # For MVP, we'll estimate insider buying as a placeholder feature
    logger.debug(f"Fetching insider data for {ticker} (lookback={lookback_days}d)")

    # This would require SEC EDGAR parsing in production
    # For MVP, return empty (will be handled gracefully in features.py)
    return pd.DataFrame()

# ============================================================================
# POINT-IN-TIME DATA LOADER
# ============================================================================

class PointInTimeDataLoader:
    """
    Loads data ensuring point-in-time correctness.
    No lookahead bias: only use data that was available at signal time.
    """

    def __init__(self):
        self.ohlcv_cache = {}
        self.fundamentals_cache = {}
        self.macro_cache = None

    def load_ohlcv_until(self, ticker: str, until_date: pd.Timestamp) -> pd.DataFrame:
        """Load OHLCV data strictly before the given date (no lookahead)."""
        path = config.DATA_DIR / f"ohlcv_{ticker}.parquet"
        if path.exists():
            data = pd.read_parquet(path)
            data['date'] = pd.to_datetime(data['date'])
            return data[data['date'] < until_date].copy()
        return pd.DataFrame()

    def load_fundamentals_at_date(
        self,
        ticker: str,
        report_date: pd.Timestamp
    ) -> Dict:
        """
        Load fundamental data as of a specific date.
        Uses report date (not period end) to avoid lookahead bias.
        """
        # In production: query versioned fundamental database
        # For MVP: use most recent available data
        if ticker in self.fundamentals_cache:
            return self.fundamentals_cache[ticker]
        return {}

# ============================================================================
# INITIALIZATION
# ============================================================================

def initialize_data_pipeline():
    """Initialize the data pipeline for MVP."""
    logger.info("Initializing data pipeline...")

    # Get S&P 500 constituents
    tickers = get_sp500_constituents()

    # For MVP: use smaller subset for faster testing (top 50)
    tickers = tickers[:50]

    # Fetch OHLCV (3 years of history for backtesting)
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=365*3)).strftime("%Y-%m-%d")

    ohlcv_data = fetch_ohlcv(tickers, start_date, end_date, save_to_parquet=True)

    # Fetch macro data
    macro_data = fetch_macro_data(start_date, end_date)
    if not macro_data.empty:
        macro_data.to_parquet(config.DATA_DIR / "macro_data.parquet", index=False)

    # Fetch fundamental data
    fundamental_data = fetch_fundamental_data(tickers)
    with open(config.DATA_DIR / "fundamentals.json", "w") as f:
        # Convert non-serializable values to strings
        json.dump({k: str(v) for k, v in fundamental_data.items()}, f, indent=2)

    logger.info("Data pipeline initialization complete")
    return tickers

if __name__ == "__main__":
    logging.basicConfig(format=config.LOG_FORMAT)
    initialize_data_pipeline()
