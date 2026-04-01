"""Compute forward-looking return targets for cross-sectional equity ML models."""

import numpy as np
import pandas as pd
from pathlib import Path
from loguru import logger


def compute_targets(prices_dict: dict, config: dict) -> dict:
    """
    Compute forward-looking return targets for ML models.

    All targets are point-in-time safe: forward returns are shifted backward
    so they align with the feature date (model sees data up to t, predicts fwd return from t+1 onwards).

    Parameters
    ----------
    prices_dict : dict
        Dictionary with 'adj_close' key containing a pd.DataFrame of shape (dates, tickers)
        with adjusted close prices.
    config : dict
        Configuration dict with keys like config['data']['processed_dir'] for output path.

    Returns
    -------
    dict
        Dictionary of DataFrames keyed by target name:
        - 'fwd_ret_5d', 'fwd_ret_20d'
        - 'fwd_ret_5d_xs', 'fwd_ret_20d_xs'
        - 'fwd_ret_5d_positive'
        - 'fwd_ret_5d_rank'
        - 'vol_21d'
        - 'fwd_ret_5d_vol_adj'
        Each DataFrame is indexed by (date, ticker) and contains the target values.
    """
    logger.info("Computing forward-looking targets...")

    adj_close = prices_dict['adj_close'].copy()

    # Ensure dates are sorted
    adj_close = adj_close.sort_index()

    targets_dict = {}

    # === Compute forward log returns ===
    # shift(-5) moves future prices up; dividing gives future/current price ratio
    # Then shift(5) aligns them back to the feature date (point-in-time safe)
    fwd_ret_5d = np.log(adj_close.shift(-5) / adj_close).shift(5)
    fwd_ret_20d = np.log(adj_close.shift(-20) / adj_close).shift(20)

    logger.debug(f"fwd_ret_5d shape: {fwd_ret_5d.shape}, NaN count: {fwd_ret_5d.isna().sum().sum()}")
    logger.debug(f"fwd_ret_20d shape: {fwd_ret_20d.shape}, NaN count: {fwd_ret_20d.isna().sum().sum()}")

    # === Compute excess returns vs SPY or cross-sectional mean ===
    if 'SPY' in adj_close.columns:
        spy_fwd_ret_5d = fwd_ret_5d['SPY'].copy()
        spy_fwd_ret_20d = fwd_ret_20d['SPY'].copy()
        logger.info("SPY found in universe, using as benchmark for excess returns")
    else:
        logger.warning("SPY not in universe, using cross-sectional mean for excess returns")
        spy_fwd_ret_5d = fwd_ret_5d.mean(axis=1)
        spy_fwd_ret_20d = fwd_ret_20d.mean(axis=1)

    # Excess returns: subtract benchmark from each ticker
    fwd_ret_5d_xs = fwd_ret_5d.sub(spy_fwd_ret_5d, axis=0)
    fwd_ret_20d_xs = fwd_ret_20d.sub(spy_fwd_ret_20d, axis=0)

    logger.debug(f"fwd_ret_5d_xs shape: {fwd_ret_5d_xs.shape}")

    # === Binary classification target ===
    fwd_ret_5d_positive = (fwd_ret_5d_xs > 0).astype(int)

    # === Cross-sectional rank ===
    fwd_ret_5d_rank = fwd_ret_5d_xs.rank(axis=1, pct=True)

    # === Trailing 21-day annualized volatility ===
    log_rets = np.log(adj_close / adj_close.shift(1))
    vol_21d = log_rets.rolling(window=21).std() * np.sqrt(252)

    logger.debug(f"vol_21d shape: {vol_21d.shape}, NaN count: {vol_21d.isna().sum().sum()}")

    # === Vol-adjusted excess return ===
    fwd_ret_5d_vol_adj = fwd_ret_5d_xs / vol_21d.clip(lower=0.001)  # avoid division by zero

    # === Convert to long format for easier processing ===
    def melt_target(df, target_name):
        """Convert wide format (dates x tickers) to long format."""
        df = df.reset_index()
        df = df.melt(id_vars=['date'], var_name='ticker', value_name=target_name)
        df = df.set_index(['date', 'ticker'])
        return df

    targets_dict['fwd_ret_5d'] = melt_target(fwd_ret_5d, 'fwd_ret_5d')
    targets_dict['fwd_ret_20d'] = melt_target(fwd_ret_20d, 'fwd_ret_20d')
    targets_dict['fwd_ret_5d_xs'] = melt_target(fwd_ret_5d_xs, 'fwd_ret_5d_xs')
    targets_dict['fwd_ret_20d_xs'] = melt_target(fwd_ret_20d_xs, 'fwd_ret_20d_xs')
    targets_dict['fwd_ret_5d_positive'] = melt_target(fwd_ret_5d_positive, 'fwd_ret_5d_positive')
    targets_dict['fwd_ret_5d_rank'] = melt_target(fwd_ret_5d_rank, 'fwd_ret_5d_rank')
    targets_dict['vol_21d'] = melt_target(vol_21d, 'vol_21d')
    targets_dict['fwd_ret_5d_vol_adj'] = melt_target(fwd_ret_5d_vol_adj, 'fwd_ret_5d_vol_adj')

    # === Save combined targets to parquet ===
    processed_dir = Path(config['data']['processed_dir'])
    processed_dir.mkdir(parents=True, exist_ok=True)

    # Combine all targets into a single DataFrame
    combined = pd.concat(targets_dict.values(), axis=1)
    combined_path = processed_dir / 'targets.parquet'
    combined.to_parquet(combined_path)
    logger.info(f"Saved combined targets to {combined_path}")

    logger.info(f"Computed {len(targets_dict)} target metrics")

    return targets_dict


def load_targets(config: dict) -> dict:
    """
    Load pre-computed targets from parquet.

    Parameters
    ----------
    config : dict
        Configuration dict with config['data']['processed_dir'] path.

    Returns
    -------
    dict
        Dictionary of DataFrames keyed by target name (extracted from combined targets file).
    """
    processed_dir = Path(config['data']['processed_dir'])
    targets_path = processed_dir / 'targets.parquet'

    if not targets_path.exists():
        logger.error(f"Targets file not found at {targets_path}")
        raise FileNotFoundError(f"Targets file not found at {targets_path}")

    combined = pd.read_parquet(targets_path)
    logger.info(f"Loaded targets from {targets_path}")

    # Split combined DataFrame back into individual target DataFrames
    target_names = combined.columns.tolist()
    targets_dict = {col: combined[[col]] for col in target_names}

    logger.info(f"Loaded {len(targets_dict)} target metrics: {target_names}")

    return targets_dict


def align_features_targets(
    features: pd.DataFrame,
    targets: dict,
    target_name: str,
    embargo_days: int = 10
) -> tuple:
    """
    Merge features with chosen target and prepare for model training.

    Parameters
    ----------
    features : pd.DataFrame
        Features indexed by (date, ticker), columns are feature names.
    targets : dict
        Dictionary of target DataFrames keyed by target name.
    target_name : str
        Name of the target to use (key in targets dict).
    embargo_days : int, optional
        Number of days to embargo (for walk-forward validation split logic).
        Currently unused here—documented for reference. Used by walk-forward splitter.

    Returns
    -------
    tuple of (X, y)
        X : pd.DataFrame
            Feature matrix indexed by (date, ticker).
        y : pd.Series
            Target series indexed by (date, ticker).
    """
    logger.info(f"Aligning features with target '{target_name}'...")

    if target_name not in targets:
        raise ValueError(f"Target '{target_name}' not found in targets dict. Available: {list(targets.keys())}")

    target_df = targets[target_name]

    # Merge on common index (date, ticker)
    merged = features.join(target_df, how='inner')

    # Drop rows with NaN targets
    initial_rows = len(merged)
    merged = merged.dropna(subset=[target_name])
    dropped_rows = initial_rows - len(merged)

    logger.info(f"Dropped {dropped_rows} rows with NaN targets (from {initial_rows} to {len(merged)})")

    # Extract X and y
    X = merged.drop(columns=[target_name])
    y = merged[target_name].squeeze()

    logger.info(f"Aligned data: X shape {X.shape}, y shape {y.shape}")
    logger.debug(f"embargo_days={embargo_days} (used by walk-forward splitter, not here)")

    return X, y
