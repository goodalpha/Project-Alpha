"""Price data download and management."""

from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import yfinance as yf
import requests_cache
from loguru import logger

from .utils import safe_parquet_read, safe_parquet_write, retry, get_trading_calendar


# Configure requests caching for yfinance
requests_cache.install_cache(
    name="yfinance_cache",
    expire_after=86400,  # 1 day TTL
)


@retry(max_retries=3, backoff=2.0)
def download_prices(
    tickers: list[str],
    start: pd.Timestamp,
    end: pd.Timestamp,
    cache_dir: Path,
    batch_size: int = 50,
    adjusted: bool = True,
) -> pd.DataFrame:
    """
    Download OHLCV price data for tickers.

    Downloads from yfinance in batches with caching. Gracefully handles
    delisted tickers. Stores raw data as parquet files per batch.

    Args:
        tickers: List of ticker symbols
        start: Start date (inclusive)
        end: End date (inclusive)
        cache_dir: Directory for caching downloaded data
        batch_size: Number of tickers per batch (default: 50)
        adjusted: Whether to include adjusted close (default: True)

    Returns:
        DataFrame with MultiIndex (date, ticker) and columns:
        [open, high, low, close, adj_close, volume]

    Raises:
        Exception: If download fails after retries
    """
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)

    start = pd.Timestamp(start)
    end = pd.Timestamp(end)

    all_prices = []
    failed_tickers = []

    # Process tickers in batches
    for i in range(0, len(tickers), batch_size):
        batch = tickers[i : i + batch_size]
        logger.info(
            f"Downloading batch {i // batch_size + 1} "
            f"({len(batch)} tickers: {batch[0]}-{batch[-1]})"
        )

        try:
            # Download batch
            data = yf.download(
                " ".join(batch),
                start=start,
                end=end,
                progress=False,
                auto_adjust=False,  # Keep unadjusted close
            )

            if data.empty:
                logger.warning(f"No data retrieved for batch {batch}")
                continue

            # Ensure MultiIndex structure for single ticker case
            if len(batch) == 1:
                data.columns = pd.MultiIndex.from_product(
                    [data.columns, batch]
                )

            # Reshape from wide to long format
            price_data = _reshape_price_data(data, adjusted=adjusted)

            if not price_data.empty:
                all_prices.append(price_data)
                logger.info(f"Retrieved {len(price_data)} rows for batch {batch}")

        except Exception as e:
            logger.warning(f"Failed to download batch {batch}: {e}")
            failed_tickers.extend(batch)

    if failed_tickers:
        logger.warning(
            f"Failed to download {len(failed_tickers)} tickers: {failed_tickers}"
        )

    if not all_prices:
        logger.error("No price data retrieved")
        return pd.DataFrame()

    # Combine all batches
    prices_df = pd.concat(all_prices, ignore_index=False)
    prices_df = prices_df.sort_index()

    # Save to cache
    cache_path = cache_dir / f"prices_{start.date()}_{end.date()}.parquet"
    safe_parquet_write(prices_df, cache_path)

    logger.info(
        f"Downloaded {len(prices_df)} price records for "
        f"{len(prices_df.index.get_level_values('ticker').unique())} unique tickers"
    )

    return prices_df


def _reshape_price_data(
    data: pd.DataFrame,
    adjusted: bool = True,
) -> pd.DataFrame:
    """
    Reshape yfinance data from wide to long format.

    Args:
        data: Wide-format DataFrame with MultiIndex columns (price_type, ticker)
        adjusted: Whether to include adjusted close

    Returns:
        Long-format DataFrame with MultiIndex (date, ticker)
    """
    # Stack from wide to long
    stacked = data.stack().reset_index()
    stacked.columns = ["date", "ticker", "price_type", "value"]

    # Pivot to get prices as columns
    pivoted = stacked.pivot_table(
        index=["date", "ticker"],
        columns="price_type",
        values="value",
    )

    # Ensure standard column names (lowercase)
    pivoted.columns = [col.lower() for col in pivoted.columns]

    # Rename to standard names
    rename_map = {
        "open": "open",
        "high": "high",
        "low": "low",
        "close": "close",
        "adj close": "adj_close",
        "volume": "volume",
    }

    pivoted = pivoted.rename(columns=rename_map)

    # Select columns of interest
    cols_to_keep = ["open", "high", "low", "close", "volume"]
    if adjusted and "adj_close" in pivoted.columns:
        cols_to_keep.append("adj_close")

    result = pivoted[[col for col in cols_to_keep if col in pivoted.columns]]

    # Drop rows with all NaN
    result = result.dropna(how="all")

    return result


def load_prices(
    cache_dir: Path,
    tickers: Optional[list[str]] = None,
    start: Optional[pd.Timestamp] = None,
    end: Optional[pd.Timestamp] = None,
) -> pd.DataFrame:
    """
    Load price data from cache.

    Args:
        cache_dir: Directory containing cached price parquet files
        tickers: Optional list of tickers to load (all if None)
        start: Optional start date filter (inclusive)
        end: Optional end date filter (inclusive)

    Returns:
        DataFrame with MultiIndex (date, ticker) and price columns
    """
    cache_dir = Path(cache_dir)

    # Find all price parquet files
    price_files = list(cache_dir.glob("prices_*.parquet"))

    if not price_files:
        logger.warning(f"No price files found in {cache_dir}")
        return pd.DataFrame()

    # Load all price files
    all_prices = []
    for file in sorted(price_files):
        try:
            df = safe_parquet_read(file)
            all_prices.append(df)
        except Exception as e:
            logger.warning(f"Failed to load {file}: {e}")

    if not all_prices:
        return pd.DataFrame()

    prices_df = pd.concat(all_prices, ignore_index=False)
    prices_df = prices_df.sort_index()

    # Filter by tickers
    if tickers:
        prices_df = prices_df.xs(tickers, level="ticker", drop_level=False)

    # Filter by date range
    if start:
        prices_df = prices_df[prices_df.index.get_level_values("date") >= start]
    if end:
        prices_df = prices_df[prices_df.index.get_level_values("date") <= end]

    logger.info(
        f"Loaded {len(prices_df)} price records "
        f"({len(prices_df.index.get_level_values('ticker').unique())} tickers)"
    )

    return prices_df


def compute_returns(
    prices_df: pd.DataFrame,
    periods: list[int] = [1, 5, 20, 60],
) -> pd.DataFrame:
    """
    Compute forward and backward log returns.

    Args:
        prices_df: DataFrame with MultiIndex (date, ticker) and close price
        periods: List of periods for return calculation (default: [1, 5, 20, 60])

    Returns:
        DataFrame with columns like ret_1d, ret_5d, fwd_ret_1d, fwd_ret_5d, etc.
    """
    if prices_df.empty or "close" not in prices_df.columns:
        logger.warning("Empty prices dataframe or missing 'close' column")
        return pd.DataFrame()

    returns_df = pd.DataFrame(index=prices_df.index)

    for period in periods:
        # Backward return (previous returns)
        returns_df[f"ret_{period}d"] = prices_df.groupby(level="ticker")[
            "close"
        ].apply(lambda x: np.log(x / x.shift(period)))

        # Forward return (future returns)
        returns_df[f"fwd_ret_{period}d"] = prices_df.groupby(level="ticker")[
            "close"
        ].apply(lambda x: np.log(x.shift(-period) / x))

    logger.info(f"Computed returns for {len(returns_df)} observations")

    return returns_df


def detect_price_anomalies(prices_df: pd.DataFrame) -> pd.Series:
    """
    Detect extreme price movements that may indicate data errors.

    Flags single-day returns exceeding 50% as potential anomalies.

    Args:
        prices_df: DataFrame with MultiIndex (date, ticker) and close price

    Returns:
        Boolean Series (same index as prices_df) flagging anomalies
    """
    if prices_df.empty or "close" not in prices_df.columns:
        logger.warning("Empty prices dataframe or missing 'close' column")
        return pd.Series(dtype=bool)

    # Compute 1-day returns
    returns = prices_df.groupby(level="ticker")["close"].apply(
        lambda x: np.log(x / x.shift(1))
    )

    # Flag extreme returns
    anomalies = np.abs(returns) > 0.5

    num_anomalies = anomalies.sum()
    if num_anomalies > 0:
        logger.warning(f"Detected {num_anomalies} potential price anomalies (>50% 1-day return)")

    return anomalies
