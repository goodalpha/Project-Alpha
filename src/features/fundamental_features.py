"""
Fundamental feature engineering from SEC EDGAR data.

Computes valuation ratios, profitability metrics, and financial health indicators
with point-in-time safety (reporting lag already applied).
"""

import numpy as np
import pandas as pd
from loguru import logger


def compute_fundamental_features(fundamental_panel: pd.DataFrame, config: dict) -> pd.DataFrame:
    """
    Compute fundamental valuation and financial health features.

    Transforms SEC EDGAR panel data (with reporting lag already applied) into
    cross-sectional features. Handles missing data with forward-fill up to
    staleness threshold, then NaN.

    Parameters
    ----------
    fundamental_panel : pd.DataFrame
        Panel data with columns: ticker, date, metric, value
        Assumes reporting_lag_days has already been applied to dates.
    config : dict
        Configuration dictionary with 'features' > 'fundamental' section:
        - reporting_lag_days: assumed delay (for documentation, already applied)
        - staleness_threshold_days: max days to forward-fill before marking stale (default 400)

    Returns
    -------
    pd.DataFrame
        Long-format DataFrame with columns:
        - date, ticker
        - Fundamental features: pe_ratio, pb_ratio, ps_ratio, roe, asset_turnover,
          debt_to_equity, current_ratio, gross_margin, fcf_yield
        - staleness_flag: bool, True if data is > staleness_threshold_days old

    Notes
    -----
    - pe_ratio computed as price / (eps_basic * 4) to annualize quarterly EPS
    - Missing price data causes pe_ratio to be NaN (merged later if available)
    - Forward-fill applied within staleness_threshold_days, then NaN
    - earnings_revision placeholder returns NaN (analyst consensus not in free data)
    """
    logger.info("Computing fundamental features...")

    fund_config = config.get("features", {}).get("fundamental", {})
    staleness_threshold = fund_config.get("staleness_threshold_days", 400)

    if fundamental_panel.empty:
        logger.warning("Fundamental panel is empty; returning empty DataFrame")
        return pd.DataFrame()

    # Pivot panel to wide format: (date x ticker) x metric
    if "metric" in fundamental_panel.columns and "value" in fundamental_panel.columns:
        pivot = fundamental_panel.pivot_table(
            index=["date", "ticker"],
            columns="metric",
            values="value",
            aggfunc="first",
        )
        pivot = pivot.reset_index()
    else:
        # Already in wide format
        pivot = fundamental_panel.copy()

    # Initialize result
    result = pivot[["date", "ticker"]].copy()

    # Helper function to safely get column
    def get_col(name):
        return pivot.get(name, pd.Series(np.nan, index=pivot.index))

    # ── Valuation ratios ──────────────────────────────────────────────────────

    # P/E ratio: price / (quarterly_eps * 4)
    price = get_col("price")
    eps_basic = get_col("eps_basic")
    if not price.isna().all() and not eps_basic.isna().all():
        result["pe_ratio"] = price / (eps_basic * 4 + 1e-10)
    else:
        logger.warning("Price or EPS data missing; pe_ratio will be NaN")
        result["pe_ratio"] = np.nan

    # P/B ratio: market_cap / book_value
    market_cap = get_col("market_cap")
    book_value = get_col("book_value")
    if not market_cap.isna().all() and not book_value.isna().all():
        result["pb_ratio"] = market_cap / (book_value + 1e-10)
    else:
        result["pb_ratio"] = np.nan

    # P/S ratio: market_cap / revenue_ttm
    revenue_ttm = get_col("revenue_ttm")
    if not market_cap.isna().all() and not revenue_ttm.isna().all():
        result["ps_ratio"] = market_cap / (revenue_ttm + 1e-10)
    else:
        result["ps_ratio"] = np.nan

    # ── Profitability metrics ─────────────────────────────────────────────────

    # ROE: net_income_ttm / book_value
    net_income_ttm = get_col("net_income_ttm")
    if not net_income_ttm.isna().all() and not book_value.isna().all():
        result["roe"] = net_income_ttm / (book_value + 1e-10)
    else:
        result["roe"] = np.nan

    # Asset turnover: revenue_ttm / total_assets
    total_assets = get_col("total_assets")
    if not revenue_ttm.isna().all() and not total_assets.isna().all():
        result["asset_turnover"] = revenue_ttm / (total_assets + 1e-10)
    else:
        result["asset_turnover"] = np.nan

    # ── Leverage metrics ──────────────────────────────────────────────────────

    # Debt-to-equity: total_debt / book_value
    total_debt = get_col("total_debt")
    if not total_debt.isna().all() and not book_value.isna().all():
        result["debt_to_equity"] = total_debt / (book_value + 1e-10)
    else:
        result["debt_to_equity"] = np.nan

    # ── Liquidity metrics ─────────────────────────────────────────────────────

    # Current ratio: current_assets / current_liabilities
    current_assets = get_col("current_assets")
    current_liabilities = get_col("current_liabilities")
    if not current_assets.isna().all() and not current_liabilities.isna().all():
        result["current_ratio"] = current_assets / (current_liabilities + 1e-10)
    else:
        result["current_ratio"] = np.nan

    # ── Efficiency metrics ────────────────────────────────────────────────────

    # Gross margin: gross_profit / revenue
    gross_profit = get_col("gross_profit")
    if not gross_profit.isna().all() and not revenue_ttm.isna().all():
        result["gross_margin"] = gross_profit / (revenue_ttm + 1e-10)
    else:
        result["gross_margin"] = np.nan

    # ── Cash flow metrics ─────────────────────────────────────────────────────

    # FCF yield: (operating_cashflow - capex) / market_cap
    operating_cashflow = get_col("operating_cashflow")
    capex = get_col("capex")
    if (
        not operating_cashflow.isna().all()
        and not capex.isna().all()
        and not market_cap.isna().all()
    ):
        fcf = operating_cashflow - capex
        result["fcf_yield"] = fcf / (market_cap + 1e-10)
    else:
        result["fcf_yield"] = np.nan

    # ── Earnings revision (placeholder) ────────────────────────────────────────
    # Note: Free data sources (Yahoo Finance, SEC Edgar) do not provide analyst
    # estimates or revisions. This would require paid data (FactSet, Bloomberg, etc.)
    result["earnings_revision"] = np.nan
    logger.info("earnings_revision set to NaN (analyst data not available in free sources)")

    # ── Forward-fill within staleness threshold ───────────────────────────────
    logger.info(f"Forward-filling fundamental data within {staleness_threshold} days...")

    feature_cols = [
        "pe_ratio",
        "pb_ratio",
        "ps_ratio",
        "roe",
        "asset_turnover",
        "debt_to_equity",
        "current_ratio",
        "gross_margin",
        "fcf_yield",
        "earnings_revision",
    ]

    # Sort by ticker and date to ensure proper forward-fill
    result = result.sort_values(["ticker", "date"]).reset_index(drop=True)

    for col in feature_cols:
        if col not in result.columns:
            continue

        # Track days since last non-NaN value per ticker
        result["_days_since_update"] = result.groupby("ticker")[col].apply(
            lambda x: x.notna()[::-1].cumsum()[::-1].where(x.isna(), 0)
        )

        # Forward-fill within staleness threshold
        result[col] = result.groupby("ticker")[col].fillna(method="ffill", limit=staleness_threshold)

    # Add staleness flag: True if data is stale (all NaN after forward-fill)
    result["staleness_flag"] = result[feature_cols].isna().all(axis=1)

    # Clean up temporary column
    result = result.drop(columns=["_days_since_update"], errors="ignore")

    logger.info(
        f"Fundamental features computed: {result.shape[0]} rows, "
        f"{len(feature_cols)} features"
    )

    return result
