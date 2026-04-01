"""Universe construction and management."""

from pathlib import Path
from typing import Optional

import pandas as pd
from loguru import logger

from .utils import safe_parquet_read, safe_parquet_write, retry


@retry(max_retries=3, backoff=2.0)
def get_sp500_tickers() -> list[str]:
    """
    Scrape S&P 500 tickers from Wikipedia.

    Fetches the list of S&P 500 companies from Wikipedia and returns
    a sorted list with dots replaced by dashes (e.g., BRK.B -> BRK-B).

    Returns:
        Sorted list of S&P 500 ticker symbols

    Raises:
        Exception: If scraping fails after retries
    """
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"

    try:
        tables = pd.read_html(url)
        # First table contains the list of companies
        df = tables[0]

        # Column name might be "Symbol" or "Ticker"
        ticker_col = next(
            col for col in df.columns
            if col.lower() in ["symbol", "ticker"]
        )

        tickers = df[ticker_col].astype(str).str.strip().tolist()
        # Replace dots with dashes
        tickers = [t.replace(".", "-") for t in tickers]
        tickers = sorted(set(tickers))

        logger.info(f"Retrieved {len(tickers)} S&P 500 tickers from Wikipedia")
        return tickers
    except Exception as e:
        logger.error(f"Failed to scrape S&P 500 tickers: {e}")
        raise


@retry(max_retries=3, backoff=2.0)
def get_nasdaq100_tickers() -> list[str]:
    """
    Scrape Nasdaq-100 tickers from Wikipedia.

    Fetches the list of Nasdaq-100 companies from Wikipedia and returns
    a sorted list with dots replaced by dashes.

    Returns:
        Sorted list of Nasdaq-100 ticker symbols

    Raises:
        Exception: If scraping fails after retries
    """
    url = "https://en.wikipedia.org/wiki/Nasdaq-100"

    try:
        tables = pd.read_html(url)
        # Find the table with ticker symbols (usually contains "Ticker")
        df = None
        for table in tables:
            if any(col.lower() in ["ticker", "symbol"] for col in table.columns):
                df = table
                break

        if df is None:
            raise ValueError("Could not find ticker table in Nasdaq-100 Wikipedia")

        ticker_col = next(
            col for col in df.columns
            if col.lower() in ["ticker", "symbol"]
        )

        tickers = df[ticker_col].astype(str).str.strip().tolist()
        # Replace dots with dashes
        tickers = [t.replace(".", "-") for t in tickers]
        tickers = sorted(set(tickers))

        logger.info(f"Retrieved {len(tickers)} Nasdaq-100 tickers from Wikipedia")
        return tickers
    except Exception as e:
        logger.error(f"Failed to scrape Nasdaq-100 tickers: {e}")
        raise


def filter_by_adv(
    tickers: list[str],
    prices_df: pd.DataFrame,
    min_adv: float = 5e6,
    window: int = 63,
) -> list[str]:
    """
    Filter tickers by minimum average daily volume.

    Computes rolling average dollar volume (close * volume) over specified
    window and filters to tickers meeting minimum ADV threshold.

    Args:
        tickers: List of ticker symbols to filter
        prices_df: DataFrame with MultiIndex (date, ticker) and volume column
        min_adv: Minimum average daily volume in dollars (default: 5M)
        window: Window size for rolling average in trading days (default: 63)

    Returns:
        Filtered list of tickers meeting ADV threshold
    """
    if prices_df.empty:
        logger.warning("Empty prices dataframe provided for ADV filtering")
        return tickers

    try:
        # Ensure we have the necessary columns
        if "close" not in prices_df.columns or "volume" not in prices_df.columns:
            logger.warning(
                "Missing 'close' or 'volume' column in prices dataframe. "
                "Returning all tickers."
            )
            return tickers

        # Compute dollar volume
        prices_df = prices_df.copy()
        prices_df["dollar_volume"] = prices_df["close"] * prices_df["volume"]

        # Filter to tickers of interest
        prices_subset = prices_df.xs(
            tickers, level="ticker", drop_level=False
        )

        # Compute rolling average ADV per ticker
        adv = (
            prices_subset.groupby(level="ticker")["dollar_volume"]
            .rolling(window=window, min_periods=1)
            .mean()
            .reset_index(level=0, drop=True)
            .groupby(level="ticker")
            .tail(1)  # Get most recent value
        )

        # Filter tickers meeting minimum ADV
        qualified = adv[adv >= min_adv].index.get_level_values("ticker").unique().tolist()
        qualified = sorted(set(qualified))

        filtered_out = len(tickers) - len(qualified)
        logger.info(
            f"ADV filter: {len(qualified)} of {len(tickers)} tickers qualified "
            f"(min_adv=${min_adv/1e6:.1f}M, window={window}d). "
            f"Filtered out {filtered_out} tickers."
        )

        return qualified
    except Exception as e:
        logger.error(f"Error filtering by ADV: {e}")
        return tickers


def build_universe(
    config: dict,
    output_path: Optional[Path] = None,
) -> pd.DataFrame:
    """
    Build trading universe.

    Constructs universe by default from S&P 500 or custom ticker list.
    Can optionally filter by ADV. Creates a DataFrame with ticker metadata.

    Args:
        config: Configuration dict with keys:
            - "universe": dict with:
              - "source": "sp500", "nasdaq100", or "custom" (default: "sp500")
              - "tickers": list of tickers if source is "custom"
              - "min_adv": minimum ADV in dollars (optional)
              - "prices_df": DataFrame for ADV filtering (if min_adv set)
        output_path: Optional path to save universe parquet file

    Returns:
        DataFrame with columns [ticker, sector, industry, include_date]
        indexed by ticker

    Raises:
        ValueError: If configuration is invalid
    """
    universe_config = config.get("universe", {})
    source = universe_config.get("source", "sp500").lower()

    # Get base ticker list
    if source == "sp500":
        tickers = get_sp500_tickers()
    elif source == "nasdaq100":
        tickers = get_nasdaq100_tickers()
    elif source == "custom":
        tickers = universe_config.get("tickers", [])
        if not tickers:
            raise ValueError("Custom universe source requires 'tickers' list")
        logger.info(f"Using custom universe with {len(tickers)} tickers")
    else:
        raise ValueError(f"Unknown universe source: {source}")

    # Apply ADV filter if configured
    if "min_adv" in universe_config and "prices_df" in universe_config:
        min_adv = universe_config["min_adv"]
        prices_df = universe_config["prices_df"]
        tickers = filter_by_adv(
            tickers,
            prices_df,
            min_adv=min_adv,
            window=universe_config.get("adv_window", 63),
        )

    # Build universe DataFrame
    universe_df = pd.DataFrame({
        "ticker": tickers,
        "sector": "Unknown",  # Placeholder - could be enriched from data source
        "industry": "Unknown",
        "include_date": pd.Timestamp.now(),
    })

    universe_df = universe_df.set_index("ticker").sort_index()

    logger.info(f"Built universe with {len(universe_df)} tickers")

    # Save if output path provided
    if output_path is not None:
        output_path = Path(output_path)
        safe_parquet_write(universe_df, output_path)

    return universe_df


def load_universe(path: Path) -> pd.DataFrame:
    """
    Load universe from parquet file.

    Args:
        path: Path to universe parquet file

    Returns:
        DataFrame with columns [sector, industry, include_date]
        indexed by ticker

    Raises:
        FileNotFoundError: If file not found
    """
    path = Path(path)
    df = safe_parquet_read(path)
    logger.info(f"Loaded universe with {len(df)} tickers")
    return df
