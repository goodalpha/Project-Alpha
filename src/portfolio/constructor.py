"""
Portfolio construction module.
Handles stock selection, weighting, and constraints.
"""

import pandas as pd
import numpy as np
from loguru import logger
from typing import Optional


class PortfolioConstructor:
    """
    Portfolio construction pipeline.

    Workflow:
    1. select_stocks: Choose top top_pct by signal
    2. compute_vol_parity_weights: Weight by inverse vol
    3. apply_sector_caps: Enforce sector concentration limits
    4. scale_to_vol_target: Scale to target portfolio volatility
    """

    def __init__(self, config: dict):
        """
        Initialize portfolio constructor.

        Parameters
        ----------
        config : dict
            Configuration dict with keys:
            - portfolio.top_pct: float, e.g. 0.2
            - portfolio.bottom_pct: float, e.g. 0.2 (for long-short)
            - portfolio.long_short: bool, default False
            - portfolio.max_position_pct: float, e.g. 0.05
            - portfolio.max_sector_pct: float, e.g. 0.30
            - portfolio.target_vol: float, e.g. 0.15
            - portfolio.max_gross_leverage: float, e.g. 1.0
        """
        self.config = config
        self.top_pct = config.get("portfolio.top_pct", 0.2)
        self.bottom_pct = config.get("portfolio.bottom_pct", 0.2)
        self.long_short = config.get("portfolio.long_short", False)
        self.max_position_pct = config.get("portfolio.max_position_pct", 0.05)
        self.max_sector_pct = config.get("portfolio.max_sector_pct", 0.30)
        self.target_vol = config.get("portfolio.target_vol", 0.15)
        self.max_gross_leverage = config.get("portfolio.max_gross_leverage", 1.0)

        logger.info(
            f"PortfolioConstructor initialized: top_pct={self.top_pct}, "
            f"long_short={self.long_short}, target_vol={self.target_vol}"
        )

    def select_stocks(self, signals: pd.Series, universe_tickers: Optional[list] = None) -> pd.Series:
        """
        Select top stocks by signal.

        Parameters
        ----------
        signals : pd.Series
            Signal by ticker (higher is better)
        universe_tickers : list, optional
            Restrict to these tickers, default None (use all)

        Returns
        -------
        pd.Series
            Selected signals, indexed by ticker
        """
        # Filter universe if provided
        if universe_tickers is not None:
            signals = signals[signals.index.isin(universe_tickers)]

        if signals.empty:
            logger.warning("Empty signals after universe filter")
            return pd.Series(dtype=float)

        # Remove NaNs
        signals = signals.dropna()

        if signals.empty:
            logger.warning("No non-NaN signals")
            return pd.Series(dtype=float)

        n_stocks = len(signals)
        n_long = max(1, int(np.ceil(n_stocks * self.top_pct)))

        # Select top long
        long_stocks = signals.nlargest(n_long)

        if not self.long_short:
            return long_stocks

        # Select bottom short
        n_short = max(1, int(np.ceil(n_stocks * self.bottom_pct)))
        short_stocks = signals.nsmallest(n_short)

        # Combine: long +1, short -1
        combined = pd.concat([
            pd.Series(1.0, index=long_stocks.index),
            pd.Series(-1.0, index=short_stocks.index)
        ])

        return combined

    def compute_vol_parity_weights(self, selected: pd.Series, vols: pd.Series) -> pd.Series:
        """
        Compute vol-parity weights.

        Weight ∝ 1/vol, normalized to sum to 1 (long-only) or sum to 0 (long-short).
        Clip individual weights at max_position_pct.

        Parameters
        ----------
        selected : pd.Series
            Selected signal values (or direction for long-short)
        vols : pd.Series
            Realized volatility by ticker

        Returns
        -------
        pd.Series
            Weights by ticker, indexed by ticker
        """
        # Align selected and vols
        common_idx = selected.index.intersection(vols.index)
        selected = selected[common_idx]
        vols = vols[common_idx]

        if selected.empty or vols.empty:
            logger.warning("Empty selected or vols in vol_parity")
            return pd.Series(dtype=float)

        # Handle zero vols
        vols = vols.replace(0, vols.median() if vols.median() > 0 else 0.01)

        # Inverse vol weights
        inv_vols = 1.0 / vols
        inv_vols = inv_vols / inv_vols.sum()

        # Apply direction (sign of selected)
        direction = np.sign(selected)
        direction = direction.replace(0, 1)  # Default to long if direction is 0

        weights = direction * inv_vols

        # Clip at max position
        weights = weights.clip(-self.max_position_pct, self.max_position_pct)

        # Renormalize
        weight_sum = weights.sum()
        if weight_sum != 0:
            weights = weights / weight_sum

        return weights

    def apply_sector_caps(self, weights: pd.Series, sector_map: pd.Series) -> pd.Series:
        """
        Apply sector concentration limits.

        If any sector > max_sector_pct, scale down proportionally and renormalize.

        Parameters
        ----------
        weights : pd.Series
            Weights by ticker
        sector_map : pd.Series
            Sector by ticker

        Returns
        -------
        pd.Series
            Capped weights, indexed by ticker
        """
        if weights.empty or sector_map.empty:
            return weights.copy()

        # Align
        common_idx = weights.index.intersection(sector_map.index)
        weights = weights[common_idx].copy()
        sector_map = sector_map[common_idx]

        if weights.empty:
            return weights

        # Compute sector exposures
        sector_exposures = {}
        for ticker, weight in weights.items():
            if pd.isna(sector_map[ticker]):
                sector = "UNKNOWN"
            else:
                sector = sector_map[ticker]
            sector_exposures[sector] = sector_exposures.get(sector, 0.0) + abs(weight)

        # Check for violations and scale
        violations = {s: exp for s, exp in sector_exposures.items()
                     if exp > self.max_sector_pct}

        if not violations:
            return weights

        logger.debug(f"Sector cap violations: {violations}")

        # Iteratively scale down violating sectors
        for _ in range(10):  # Max iterations
            violations = {s: exp for s, exp in sector_exposures.items()
                         if exp > self.max_sector_pct}

            if not violations:
                break

            # Scale factor for each sector
            scale_factors = {}
            for sector in violations:
                scale_factors[sector] = self.max_sector_pct / sector_exposures[sector]

            # Apply scaling
            new_weights = weights.copy()
            for ticker, weight in weights.items():
                sector = sector_map[ticker]
                if pd.isna(sector):
                    sector = "UNKNOWN"
                if sector in scale_factors:
                    new_weights[ticker] = weight * scale_factors[sector]

            # Renormalize
            weight_sum = new_weights.sum()
            if abs(weight_sum) > 1e-6:
                new_weights = new_weights / weight_sum

            weights = new_weights

            # Recompute sector exposures
            sector_exposures = {}
            for ticker, weight in weights.items():
                if pd.isna(sector_map[ticker]):
                    sector = "UNKNOWN"
                else:
                    sector = sector_map[ticker]
                sector_exposures[sector] = sector_exposures.get(sector, 0.0) + abs(weight)

        return weights

    def scale_to_vol_target(self, weights: pd.Series, vols: pd.Series,
                            cov_matrix: Optional[pd.DataFrame] = None) -> pd.Series:
        """
        Scale weights to target portfolio volatility.

        Portfolio vol = sqrt(w' Σ w) where Σ is covariance matrix.
        If no cov_matrix, use diagonal (assume zero correlation).

        Parameters
        ----------
        weights : pd.Series
            Weights by ticker
        vols : pd.Series
            Realized volatility by ticker
        cov_matrix : pd.DataFrame, optional
            Covariance matrix, default None (use diagonal)

        Returns
        -------
        pd.Series
            Scaled weights, indexed by ticker
        """
        if weights.empty:
            return weights

        # Align weights and vols
        common_idx = weights.index.intersection(vols.index)
        weights = weights[common_idx].copy()
        vols = vols[common_idx]

        if weights.empty:
            return weights

        # Compute current portfolio vol
        if cov_matrix is not None:
            cov_matrix = cov_matrix.loc[common_idx, common_idx]
            try:
                port_var = (weights.values @ cov_matrix.values @ weights.values)
                port_vol = np.sqrt(port_var) if port_var > 0 else 0.01
            except Exception as e:
                logger.debug(f"Error computing portfolio vol from cov matrix: {e}")
                port_vol = 0.01
        else:
            # Diagonal covariance (independent)
            port_var = (weights * vols) ** 2
            port_vol = np.sqrt(port_var.sum())

        if port_vol < 1e-6:
            logger.debug("Portfolio vol near zero, no scaling applied")
            return weights

        # Target scalar
        target_scalar = self.target_vol / port_vol

        # Clip scalar at max leverage
        target_scalar = min(target_scalar, self.max_gross_leverage)

        scaled_weights = weights * target_scalar

        return scaled_weights

    def build_portfolio(self, signals: pd.Series, vols: pd.Series,
                       sector_map: pd.Series) -> pd.Series:
        """
        Full portfolio construction pipeline.

        select_stocks → compute_vol_parity_weights → apply_sector_caps → scale_to_vol_target

        Parameters
        ----------
        signals : pd.Series
            Signal by ticker
        vols : pd.Series
            Volatility by ticker
        sector_map : pd.Series
            Sector by ticker

        Returns
        -------
        pd.Series
            Final weights by ticker
        """
        # 1. Select stocks
        selected = self.select_stocks(signals)
        if selected.empty:
            logger.warning("No stocks selected")
            return pd.Series(dtype=float)

        # 2. Vol parity weights
        weights = self.compute_vol_parity_weights(selected, vols)
        if weights.empty:
            logger.warning("Empty weights from vol parity")
            return pd.Series(dtype=float)

        # 3. Sector caps
        weights = self.apply_sector_caps(weights, sector_map)

        # 4. Vol target scaling
        weights = self.scale_to_vol_target(weights, vols)

        return weights


def compute_weights(signals: pd.Series, vols: pd.Series, sector_map: pd.Series,
                   config: dict) -> pd.Series:
    """
    Convenience function to compute weights.

    Parameters
    ----------
    signals : pd.Series
        Signal by ticker
    vols : pd.Series
        Volatility by ticker
    sector_map : pd.Series
        Sector by ticker
    config : dict
        Configuration dict

    Returns
    -------
    pd.Series
        Weights by ticker
    """
    constructor = PortfolioConstructor(config)
    return constructor.build_portfolio(signals, vols, sector_map)
