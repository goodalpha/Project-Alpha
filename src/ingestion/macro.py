"""Macro data download and management."""

from pathlib import Path
from typing import Optional, Union

import numpy as np
import pandas as pd
from pandas_datareader import data as web
from loguru import logger

from .utils import safe_parquet_read, safe_parquet_write, retry, get_trading_calendar


# Common FRED series IDs for macro data
DEFAULT_MACRO_SERIES = {
    "DFF": "Federal Funds Effective Rate",
    "T10Y2Y": "10-Year minus 2-Year Treasury Spread",
    "VIXCLS": "VIX Closing Level",
    "CPIAUCSL": "CPI All Urban Consumers",
    "UNRATE": "Unemployment Rate",
    "DGS10": "10-Year Treasury Constant Maturity Rate",
    "DGS2": "2-Year Treasury Constant Maturity Rate",
    "BAMLH0A0HYM2": "High Yield OAS",
}


@retry(max_retries=3, backoff=2.0)
def download_macro(
    series_ids: dict[str, str],
    start: pd.Timestamp,
    end: pd.Timestamp,
    cache_dir: Path,
    api_key: Optional[str] = None,
) -> pd.DataFrame:
    """
    Download macroeconomic data from FRED.

    Downloads each series using pandas_datareader with 'fred' source,
    forward-fills to daily frequency, and computes derived features.

    Args:
        series_ids: Dict mapping FRED series IDs to descriptions
            (e.g., {"DFF": "Federal Funds Rate"})
        start: Start date (inclusive)
        end: End date (inclusive)
        cache_dir: Directory for caching downloaded data
        api_key: Optional FRED API key (uses environment variable if None)

    Returns:
        Wide DataFrame indexed by date with one column per series
        plus derived feature columns

    Raises:
        Exception: If download fails after retries
    """
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)

    start = pd.Timestamp(start)
    end = pd.Timestamp(end)

    macro_data = {}
    failed_series = []

    logger.info(f"Downloading {len(series_ids)} FRED series...")

    for series_id, description in series_ids.items():
        try:
            logger.info(f"Downloading {series_id}: {description}")

            df = web.DataReader(
                series_id,
                "fred",
                start=start,
                end=end,
                api_key=api_key,
            )

            # Forward-fill to daily frequency
            df = df.asfreq("D", method="ffill")
            macro_data[series_id] = df.squeeze()

        except Exception as e:
            logger.warning(f"Failed to download {series_id}: {e}")
            failed_series.append(series_id)

    if failed_series:
        logger.warning(f"Failed to download {len(failed_series)} series: {failed_series}")

    if not macro_data:
        logger.error("No macro data retrieved")
        return pd.DataFrame()

    # Combine into DataFrame
    macro_df = pd.concat(macro_data, axis=1)
    macro_df.index.name = "date"

    # Compute derived features
    macro_df = _compute_macro_features(macro_df)

    logger.info(f"Downloaded macro data with {len(macro_df)} daily observations")

    # Save to cache
    cache_path = cache_dir / f"macro_{start.date()}_{end.date()}.parquet"
    safe_parquet_write(macro_df, cache_path)

    return macro_df


def _compute_macro_features(macro_df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute derived macro features.

    Adds columns like yield_curve_slope, vix_regime, cpi momentum, etc.

    Args:
        macro_df: DataFrame with FRED series as columns

    Returns:
        DataFrame with additional derived feature columns
    """
    df = macro_df.copy()

    # Yield curve slope (10Y - 2Y Treasury)
    if "T10Y2Y" not in df.columns and "DGS10" in df.columns and "DGS2" in df.columns:
        df["yield_curve_slope"] = df["DGS10"] - df["DGS2"]
    elif "T10Y2Y" in df.columns:
        df["yield_curve_slope"] = df["T10Y2Y"]

    # VIX regime
    if "VIXCLS" in df.columns:
        vix_q25 = df["VIXCLS"].quantile(0.25)
        vix_q75 = df["VIXCLS"].quantile(0.75)
        df["vix_low_regime"] = df["VIXCLS"] <= vix_q25
        df["vix_high_regime"] = df["VIXCLS"] >= vix_q75

    # CPI momentum
    if "CPIAUCSL" in df.columns:
        df["cpi_mom"] = df["CPIAUCSL"].pct_change(periods=1)
        df["cpi_yoy"] = df["CPIAUCSL"].pct_change(periods=252)  # ~1 year of trading days

    logger.info(f"Computed derived macro features: {len(df.columns)} total columns")

    return df


def load_macro(cache_dir: Path) -> pd.DataFrame:
    """
    Load macro data from cache.

    Args:
        cache_dir: Directory containing cached macro parquet files

    Returns:
        Wide DataFrame indexed by date with macro series
    """
    cache_dir = Path(cache_dir)

    # Find all macro parquet files
    macro_files = list(cache_dir.glob("macro_*.parquet"))

    if not macro_files:
        logger.warning(f"No macro files found in {cache_dir}")
        return pd.DataFrame()

    # Load all macro files
    all_macro = []
    for file in sorted(macro_files):
        try:
            df = safe_parquet_read(file)
            all_macro.append(df)
        except Exception as e:
            logger.warning(f"Failed to load {file}: {e}")

    if not all_macro:
        return pd.DataFrame()

    macro_df = pd.concat(all_macro, ignore_index=False)
    macro_df = macro_df.sort_index()

    # Remove duplicates, keeping latest
    macro_df = macro_df[~macro_df.index.duplicated(keep="last")]

    logger.info(f"Loaded macro data with {len(macro_df)} observations")

    return macro_df


def compute_macro_features(macro_df: pd.DataFrame) -> pd.DataFrame:
    """
    Add advanced macro feature engineering.

    Computes z-scores, technical indicators, and regime flags from
    raw macro data.

    Args:
        macro_df: DataFrame with macro series as columns

    Returns:
        DataFrame with additional computed features
    """
    df = macro_df.copy()

    # Yield curve inversion
    if "yield_curve_slope" in df.columns:
        df["yield_curve_inverted"] = df["yield_curve_slope"] < 0

    # VIX z-score (21-day lookback)
    if "VIXCLS" in df.columns:
        vix_mean = df["VIXCLS"].rolling(window=21, min_periods=1).mean()
        vix_std = df["VIXCLS"].rolling(window=21, min_periods=1).std()
        df["vix_z21"] = (df["VIXCLS"] - vix_mean) / (vix_std + 1e-8)

    # High yield spread z-score (63-day lookback)
    if "BAMLH0A0HYM2" in df.columns:
        hy_mean = df["BAMLH0A0HYM2"].rolling(window=63, min_periods=1).mean()
        hy_std = df["BAMLH0A0HYM2"].rolling(window=63, min_periods=1).std()
        df["hy_spread_z63"] = (df["BAMLH0A0HYM2"] - hy_mean) / (hy_std + 1e-8)

    # Fed funds rate change (momentum)
    if "DFF" in df.columns:
        df["dff_change_1m"] = df["DFF"].diff(periods=21)  # ~1 month of trading days

    logger.info(f"Computed macro features: {len(df.columns)} total columns")

    return df
