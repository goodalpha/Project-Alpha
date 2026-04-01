"""
Macro regime feature engineering.

Computes macro regime indicators from FRED economic data and attaches them to
the stock-level feature matrix indexed by date.
"""

import numpy as np
import pandas as pd
from loguru import logger


def compute_macro_features(
    macro_df: pd.DataFrame, stock_dates: pd.DatetimeIndex, config: dict
) -> pd.DataFrame:
    """
    Compute macro regime features and prepare for merging onto stock panel.

    Transforms FRED macro data into regime indicators (yield curve, volatility,
    credit spreads, inflation, policy rates). Macro data is lower frequency than
    stock data, so forward-fill is applied to match stock trading dates.

    Parameters
    ----------
    macro_df : pd.DataFrame
        Macro data indexed by date, with columns named after FRED series
        (e.g., 'fed_funds_rate', 'yield_curve_10y2y', 'vix', etc.)
    stock_dates : pd.DatetimeIndex
        All unique trading dates in the stock universe (high frequency)
    config : dict
        Configuration dictionary with 'features' > 'macro' section:
        - fred_series: list of {id, name} dicts mapping FRED codes to column names

    Returns
    -------
    pd.DataFrame
        DataFrame indexed by date (matching stock_dates), with columns:
        - yield_curve_inverted: bool, True if 10Y-2Y spread < 0
        - vix_z21: VIX z-score over trailing 21 days
        - vix_regime: categorical (0=low <15, 1=normal 15-25, 2=high >25)
        - hy_spread_z63: HY spread z-score over trailing 63 days
        - cpi_mom: month-over-month CPI change
        - ff_rate_change: daily change in fed funds rate
        - macro_stress_score: composite stress indicator (0-10 scale)

    Notes
    -----
    - All features indexed by date for simple merge with stock panel
    - Missing macro data is forward-filled to stock trading dates
    - VIX z-score: (VIX - E[VIX]_21d) / std[VIX]_21d
    - Macro stress score: equal-weight of vix_z21, hy_spread_z63, -yield_curve_inverted*2
    """
    logger.info("Computing macro regime features...")

    if macro_df.empty:
        logger.warning("Macro DataFrame is empty; returning zeros")
        return pd.DataFrame(
            0.0,
            index=stock_dates,
            columns=[
                "yield_curve_inverted",
                "vix_z21",
                "vix_regime",
                "hy_spread_z63",
                "cpi_mom",
                "ff_rate_change",
                "macro_stress_score",
            ],
        )

    # Forward-fill macro data to match stock trading dates
    macro_df_reindexed = macro_df.reindex(
        pd.date_range(start=macro_df.index.min(), end=stock_dates.max(), freq="D"),
        method="ffill",
    )
    macro_df_reindexed = macro_df_reindexed.loc[stock_dates]

    result = pd.DataFrame(index=stock_dates)

    # ── Yield curve inversion ─────────────────────────────────────────────────
    if "yield_curve_10y2y" in macro_df_reindexed.columns:
        yield_curve = macro_df_reindexed["yield_curve_10y2y"]
        result["yield_curve_inverted"] = (yield_curve < 0).astype(int)
    else:
        logger.warning("yield_curve_10y2y not found; setting to 0")
        result["yield_curve_inverted"] = 0

    # ── VIX regime indicators ─────────────────────────────────────────────────
    if "vix" in macro_df_reindexed.columns:
        vix = macro_df_reindexed["vix"].fillna(method="ffill").fillna(15.0)

        # VIX z-score over 21 days
        vix_mean = vix.rolling(window=21).mean()
        vix_std = vix.rolling(window=21).std()
        result["vix_z21"] = (vix - vix_mean) / (vix_std + 1e-10)

        # VIX regime: 0=low (<15), 1=normal (15-25), 2=high (>25)
        result["vix_regime"] = pd.cut(
            vix, bins=[-np.inf, 15, 25, np.inf], labels=[0, 1, 2]
        ).astype(int)
    else:
        logger.warning("VIX not found; setting vix_z21 and vix_regime to 0")
        result["vix_z21"] = 0.0
        result["vix_regime"] = 1

    # ── High-yield spread regime ──────────────────────────────────────────────
    if "hy_spread" in macro_df_reindexed.columns:
        hy_spread = macro_df_reindexed["hy_spread"].fillna(method="ffill")

        # HY spread z-score over 63 days
        hy_mean = hy_spread.rolling(window=63).mean()
        hy_std = hy_spread.rolling(window=63).std()
        result["hy_spread_z63"] = (hy_spread - hy_mean) / (hy_std + 1e-10)
    else:
        logger.warning("hy_spread not found; setting hy_spread_z63 to 0")
        result["hy_spread_z63"] = 0.0

    # ── Inflation (CPI mom) ───────────────────────────────────────────────────
    if "cpi_yoy" in macro_df_reindexed.columns:
        cpi = macro_df_reindexed["cpi_yoy"]
        # Month-over-month change (approximate from YoY)
        result["cpi_mom"] = cpi.pct_change()
    else:
        logger.warning("cpi_yoy not found; setting cpi_mom to 0")
        result["cpi_mom"] = 0.0

    # ── Fed funds rate change ─────────────────────────────────────────────────
    if "fed_funds_rate" in macro_df_reindexed.columns:
        ff_rate = macro_df_reindexed["fed_funds_rate"]
        result["ff_rate_change"] = ff_rate.diff()
    else:
        logger.warning("fed_funds_rate not found; setting ff_rate_change to 0")
        result["ff_rate_change"] = 0.0

    # ── Macro stress score ────────────────────────────────────────────────────
    # Composite: equal-weight of (vix_z21, hy_spread_z63, -yield_curve_inverted*2)
    stress_components = pd.DataFrame(
        {
            "vix_stress": result["vix_z21"].fillna(0),
            "spread_stress": result["hy_spread_z63"].fillna(0),
            "curve_stress": -result["yield_curve_inverted"] * 2,
        }
    )

    # Normalize each component to [0, 1] using sigmoid-like transformation
    result["macro_stress_score"] = (
        stress_components.mean(axis=1) + 2
    ) / 4  # Rough scaling to [0, 1]
    result["macro_stress_score"] = result["macro_stress_score"].clip(0, 1) * 10

    logger.info(
        f"Macro features computed for {len(stock_dates)} trading dates: "
        f"{result.shape[1]} features"
    )

    return result
