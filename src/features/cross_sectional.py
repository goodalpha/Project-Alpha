"""
Cross-sectional feature transformations.

Applies z-score normalization, sector neutralization, and rank normalization
to features across the stock universe on each date.
"""

import numpy as np
import pandas as pd
from loguru import logger


def zscore_cross_sectional(
    df: pd.DataFrame, feature_cols: list, clip: float = 3.0
) -> pd.DataFrame:
    """
    Apply cross-sectional z-score normalization to features.

    For each date, computes z-score of each feature across stocks and clips outliers.

    Parameters
    ----------
    df : pd.DataFrame
        Feature DataFrame with columns: date, ticker, ...
    feature_cols : list
        List of feature column names to normalize
    clip : float
        Clipping threshold in standard deviations (default 3.0)

    Returns
    -------
    pd.DataFrame
        DataFrame with z-scored features added as new columns (original + "_zscore" suffix)
    """
    logger.debug(f"Applying z-score normalization to {len(feature_cols)} features")

    result = df.copy()

    for col in feature_cols:
        if col not in result.columns:
            logger.warning(f"Feature column '{col}' not found in DataFrame")
            continue

        # Compute z-score per date
        zscore_col = col + "_zscore"
        result[zscore_col] = result.groupby("date")[col].transform(
            lambda x: (x - x.mean()) / (x.std() + 1e-10)
        )

        # Clip outliers
        result[zscore_col] = result[zscore_col].clip(-clip, clip)

    return result


def sector_neutralize(
    df: pd.DataFrame, feature_cols: list, sector_col: str = "sector"
) -> pd.DataFrame:
    """
    Remove sector mean from features to create sector-neutral signals.

    For each date and sector, computes the mean of each feature and subtracts it
    from the original feature values within that sector.

    Parameters
    ----------
    df : pd.DataFrame
        Feature DataFrame with columns: date, ticker, sector, ...
    feature_cols : list
        List of feature column names to neutralize
    sector_col : str
        Name of sector column (default 'sector')

    Returns
    -------
    pd.DataFrame
        DataFrame with sector-neutralized features (original + "_sn" suffix)
    """
    logger.debug(
        f"Neutralizing {len(feature_cols)} features against {sector_col}"
    )

    result = df.copy()

    if sector_col not in result.columns:
        logger.warning(f"Sector column '{sector_col}' not found; skipping sector neutralization")
        return result

    for col in feature_cols:
        if col not in result.columns:
            logger.warning(f"Feature column '{col}' not found in DataFrame")
            continue

        # Compute sector mean per date
        sn_col = col + "_sn"
        sector_mean = result.groupby(["date", sector_col])[col].transform("mean")

        # Subtract sector mean
        result[sn_col] = result[col] - sector_mean

    return result


def rank_normalize(df: pd.DataFrame, feature_cols: list) -> pd.DataFrame:
    """
    Rank-normalize features to [-0.5, 0.5] range per date.

    For each date, ranks each feature across stocks and normalizes to [-0.5, 0.5].

    Parameters
    ----------
    df : pd.DataFrame
        Feature DataFrame with columns: date, ticker, ...
    feature_cols : list
        List of feature column names to rank-normalize

    Returns
    -------
    pd.DataFrame
        DataFrame with rank-normalized features (original + "_rank" suffix)
    """
    logger.debug(f"Rank-normalizing {len(feature_cols)} features")

    result = df.copy()

    for col in feature_cols:
        if col not in result.columns:
            logger.warning(f"Feature column '{col}' not found in DataFrame")
            continue

        # Rank per date (ascending order)
        rank_col = col + "_rank"
        result[rank_col] = result.groupby("date")[col].rank(
            method="average", na_option="keep"
        )

        # Normalize to [-0.5, 0.5]
        # rank ranges from 1 to N, normalize to [0, 1] then shift to [-0.5, 0.5]
        n_per_date = result.groupby("date")[col].transform("count")
        result[rank_col] = (result[rank_col] - 1) / (n_per_date - 1) - 0.5

    return result


def compute_cross_sectional_features(df: pd.DataFrame, config: dict) -> pd.DataFrame:
    """
    Apply complete cross-sectional feature transformation pipeline.

    Applies z-score normalization, optionally sector neutralization, and rank normalization
    to price and fundamental features.

    Parameters
    ----------
    df : pd.DataFrame
        Feature DataFrame with columns: date, ticker, ...
    config : dict
        Configuration dictionary with 'features' > 'cross_sectional' section:
        - zscore_clip: clipping threshold (default 3.0)
        - sector_neutralize: whether to apply sector neutralization (default False)

    Returns
    -------
    pd.DataFrame
        DataFrame with cross-sectional features added with "_xs" suffix
    """
    logger.info("Computing cross-sectional features...")

    result = df.copy()

    # Get cross-sectional config
    xs_config = config.get("features", {}).get("cross_sectional", {})
    zscore_clip = xs_config.get("zscore_clip", 3.0)
    do_sector_neutralize = xs_config.get("sector_neutralize", False)

    # Identify feature columns (exclude metadata)
    metadata_cols = {"date", "ticker", "sector"}
    feature_cols = [col for col in result.columns if col not in metadata_cols]

    if not feature_cols:
        logger.warning("No feature columns found for cross-sectional transformation")
        return result

    # Step 1: Z-score normalization
    result = zscore_cross_sectional(result, feature_cols, clip=zscore_clip)

    # Step 2: Optional sector neutralization
    if do_sector_neutralize and "sector" in result.columns:
        result = sector_neutralize(result, feature_cols, sector_col="sector")

    # Step 3: Rank normalization
    result = rank_normalize(result, feature_cols)

    logger.info(
        f"Cross-sectional features computed: {result.shape[0]} rows, "
        f"{len(feature_cols)} features × 3 transforms"
    )

    return result
