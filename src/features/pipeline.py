"""
Feature engineering pipeline orchestration.

Coordinates the end-to-end feature computation workflow: price features,
fundamental features, macro features, cross-sectional transformations,
and final output to parquet.
"""

import os
import pandas as pd
from loguru import logger

from src.features.price_features import compute_price_features
from src.features.fundamental_features import compute_fundamental_features
from src.features.macro_features import compute_macro_features
from src.features.cross_sectional import compute_cross_sectional_features


def build_feature_matrix(
    prices_dict: dict,
    macro_df: pd.DataFrame,
    fundamental_panel: pd.DataFrame,
    universe_df: pd.DataFrame,
    config: dict,
) -> pd.DataFrame:
    """
    Orchestrate full feature engineering pipeline.

    Computes price, fundamental, and macro features; applies cross-sectional
    transformations; and saves to parquet.

    Parameters
    ----------
    prices_dict : dict
        Dictionary with OHLCV data in wide format (dates x tickers):
        Keys: 'open', 'high', 'low', 'close', 'volume', 'adj_close'
    macro_df : pd.DataFrame
        Macro data indexed by date (output from src/ingestion/macro.py)
    fundamental_panel : pd.DataFrame
        Fundamental data: (ticker, date, metric, value) with reporting lag applied
    universe_df : pd.DataFrame
        Universe metadata with columns: ticker, date, sector
    config : dict
        Configuration dictionary

    Returns
    -------
    pd.DataFrame
        Complete feature matrix with columns:
        - date, ticker
        - price_features: momentum, reversal, volatility, volume, technical indicators
        - macro_features: yield_curve_inverted, vix_z21, vix_regime, etc.
        - fundamental_features: pe_ratio, pb_ratio, roe, etc.
        - cross_sectional_features: _zscore, _sn, _rank variants of price/fundamental
        - sector
        - staleness_flag

    Notes
    -----
    - Rows with all NaN primary features (warmup period) are dropped
    - Final DataFrame saved to config['data']['features_dir']/features.parquet
    - Missing data handled gracefully with NaN; warnings logged for large missingness
    """
    logger.info("Building feature matrix...")

    # Step 1: Compute price features
    logger.info("Step 1: Computing price features...")
    price_features = compute_price_features(prices_dict, config)

    if price_features.empty:
        logger.error("Price features computation failed; returning empty DataFrame")
        return pd.DataFrame()

    # Step 2: Compute macro features
    logger.info("Step 2: Computing macro features...")
    if not prices_dict["close"].empty:
        stock_dates = pd.to_datetime(prices_dict["close"].index)
        macro_features = compute_macro_features(macro_df, stock_dates, config)
        macro_features_long = macro_features.reset_index()
        macro_features_long.columns = ["date"] + list(macro_features.columns)
    else:
        logger.warning("No stock dates found; skipping macro features")
        macro_features_long = pd.DataFrame()

    # Step 3: Compute fundamental features
    logger.info("Step 3: Computing fundamental features...")
    fundamental_features = compute_fundamental_features(fundamental_panel, config)

    # Step 4: Merge all features on (date, ticker)
    logger.info("Step 4: Merging feature sets...")
    result = price_features.copy()

    if not macro_features_long.empty:
        result = result.merge(
            macro_features_long, on="date", how="left", suffixes=("", "_macro")
        )

    if not fundamental_features.empty:
        result = result.merge(
            fundamental_features, on=["date", "ticker"], how="left", suffixes=("", "_fund")
        )

    # Step 5: Add sector information
    logger.info("Step 5: Adding sector information...")
    if not universe_df.empty:
        sector_df = universe_df[["ticker", "date", "sector"]].drop_duplicates()
        result = result.merge(
            sector_df, on=["date", "ticker"], how="left", suffixes=("", "_univ")
        )

    # Step 6: Apply cross-sectional transformations
    logger.info("Step 6: Applying cross-sectional transformations...")
    result = compute_cross_sectional_features(result, config)

    # Step 7: Drop warmup period (rows where all primary features are NaN)
    logger.info("Step 7: Removing warmup period...")
    primary_feature_cols = [
        col
        for col in result.columns
        if col.startswith("ret_") or col.startswith("vol_")
    ]
    n_before = len(result)

    result = result.dropna(subset=primary_feature_cols, how="all")
    n_after = len(result)

    logger.info(
        f"Dropped {n_before - n_after} rows in warmup period; "
        f"{n_after} rows remaining"
    )

    # Step 8: Save to parquet
    logger.info("Step 8: Saving feature matrix...")
    features_dir = config.get("data", {}).get("features_dir", "data/features")
    os.makedirs(features_dir, exist_ok=True)

    output_path = os.path.join(features_dir, "features.parquet")
    result.to_parquet(output_path, engine="pyarrow", index=False)
    logger.info(f"Feature matrix saved to {output_path}")

    # Summary statistics
    logger.info(
        f"Final feature matrix: {result.shape[0]} rows, {result.shape[1]} columns"
    )
    logger.info(f"Date range: {result['date'].min()} to {result['date'].max()}")
    logger.info(f"Unique tickers: {result['ticker'].nunique()}")
    logger.info(f"Missing data by column:\n{result.isna().sum()}")

    return result


def load_feature_matrix(config: dict) -> pd.DataFrame:
    """
    Load pre-computed feature matrix from parquet.

    Parameters
    ----------
    config : dict
        Configuration dictionary with 'data' > 'features_dir' path

    Returns
    -------
    pd.DataFrame
        Feature matrix loaded from parquet

    Raises
    ------
    FileNotFoundError
        If features.parquet does not exist
    """
    features_dir = config.get("data", {}).get("features_dir", "data/features")
    feature_path = os.path.join(features_dir, "features.parquet")

    if not os.path.exists(feature_path):
        raise FileNotFoundError(f"Feature matrix not found at {feature_path}")

    logger.info(f"Loading feature matrix from {feature_path}...")
    result = pd.read_parquet(feature_path, engine="pyarrow")

    logger.info(
        f"Loaded {result.shape[0]} rows, {result.shape[1]} columns "
        f"({result['date'].min()} to {result['date'].max()})"
    )

    return result
