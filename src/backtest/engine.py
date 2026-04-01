"""
Vectorized backtesting engine for cross-sectional equity strategies.
Pure pandas/numpy implementation with no external backtesting libraries.
"""

import pandas as pd
import numpy as np
from loguru import logger
from typing import Dict, Optional, Tuple
from datetime import timedelta

from src.portfolio.constructor import PortfolioConstructor
from src.risk.controls import RiskControls


class BacktestEngine:
    """
    Vectorized backtesting engine for cross-sectional equity strategies.

    Workflow:
    1. For each rebalance date:
       - Get signal ranking
       - Select top top_pct (long book)
       - Compute vol-parity weights
       - Apply regime exposure multiplier
       - Apply position and sector limits
       - Apply transaction costs
    2. Compute daily portfolio returns between rebalance dates
    3. Track portfolio_returns, positions, turnover, cost_drag
    """

    def __init__(self, config: dict):
        """
        Initialize backtest engine.

        Parameters
        ----------
        config : dict
            Configuration dict with keys:
            - portfolio.top_pct: float, e.g. 0.2 for top 20%
            - portfolio.max_position_pct: float, e.g. 0.05
            - portfolio.max_sector_pct: float, e.g. 0.30
            - portfolio.target_vol: float, e.g. 0.15
            - portfolio.rebalance_freq: str, 'weekly' or 'daily'
            - transaction_costs.commission_per_share: float
            - transaction_costs.slippage_bps: int
            - transaction_costs.spread_bps: int
            - transaction_costs.market_impact_coeff: float
            - risk.vol_lookback: int, default 21
            - risk.regime_multipliers: dict {0: 1.0, 1: 0.75, 2: 0.50}
        """
        self.config = config
        self.portfolio_constructor = PortfolioConstructor(config)
        self.risk_manager = RiskControls(config)

        self.rebalance_freq = config.get("portfolio.rebalance_freq", "weekly")
        self.vol_lookback = config.get("risk.vol_lookback", 21)
        self.regime_multipliers = config.get("risk.regime_multipliers",
                                              {0: 1.0, 1: 0.75, 2: 0.50})

        logger.info(f"BacktestEngine initialized with config: {config}")

    def run(self,
            predictions: pd.DataFrame,
            prices: pd.DataFrame,
            universe: pd.DataFrame,
            regime_labels: Optional[pd.Series] = None) -> Dict:
        """
        Run backtest.

        Parameters
        ----------
        predictions : pd.DataFrame
            Columns: date, ticker, signal
        prices : pd.DataFrame
            Adjusted close prices, indexed by date, columns are tickers
        universe : pd.DataFrame
            Columns: date, ticker, sector
        regime_labels : pd.Series, optional
            Date-indexed regime labels (0, 1, 2), default None (constant regime=0)

        Returns
        -------
        dict
            Keys: portfolio_returns, positions, turnover, cost_drag,
                  total_cost, rebalance_dates
        """
        logger.info("Starting backtest run...")

        # Validate inputs
        if predictions.empty or prices.empty:
            logger.warning("Empty predictions or prices")
            return self._empty_result()

        # Set default regime if not provided
        if regime_labels is None:
            regime_labels = pd.Series(0, index=prices.index)

        # Get rebalance dates
        rebalance_dates = self._get_rebalance_dates(prices.index)
        logger.info(f"Total rebalance dates: {len(rebalance_dates)}")

        # Compute historical vols once
        log_returns = np.log(prices / prices.shift(1))
        vols = log_returns.rolling(window=self.vol_lookback).std() * np.sqrt(252)

        # Track results
        all_weights = {}
        all_turnover = []
        all_cost_drag = []
        all_portfolio_rets = {}

        prev_weights = pd.Series(dtype=float)

        # Main backtest loop
        for i, rebal_date in enumerate(rebalance_dates):
            if i == len(rebalance_dates) - 1:
                # Skip last date, need future returns
                break

            next_rebal_date = rebalance_dates[i + 1]

            try:
                # Get signals for rebalance date
                signals_subset = predictions[predictions['date'] == rebal_date]
                if signals_subset.empty:
                    logger.debug(f"No signals for {rebal_date}")
                    continue

                signals = pd.Series(
                    signals_subset['signal'].values,
                    index=signals_subset['ticker'].values
                )

                # Get universe and vols for this date
                universe_date = universe[universe['date'] == rebal_date]
                sector_map = pd.Series(
                    universe_date['sector'].values,
                    index=universe_date['ticker'].values
                )

                # Get vols for this date
                if rebal_date in vols.index:
                    vols_date = vols.loc[rebal_date]
                    vols_date = vols_date[~vols_date.isna()]
                else:
                    # Use most recent available vols
                    vols_date = vols[vols.index <= rebal_date].iloc[-1] if len(vols) > 0 else None
                    if vols_date is None or vols_date.isna().all():
                        logger.debug(f"No vols available for {rebal_date}")
                        continue
                    vols_date = vols_date[~vols_date.isna()]

                # Align signals, vols, sector_map
                common_tickers = signals.index.intersection(vols_date.index).intersection(sector_map.index)
                signals = signals[common_tickers]
                vols_date = vols_date[common_tickers]
                sector_map = sector_map[common_tickers]

                if signals.empty:
                    logger.debug(f"Empty intersection at {rebal_date}")
                    continue

                # Compute target weights
                target_weights = self.portfolio_constructor.build_portfolio(
                    signals, vols_date, sector_map
                )

                # Apply regime adjustment
                regime = regime_labels.get(rebal_date, 0) if isinstance(regime_labels, pd.Series) else 0
                regime = int(regime) if not np.isnan(regime) else 0
                regime_mult = self.regime_multipliers.get(regime, 1.0)
                target_weights = target_weights * regime_mult
                target_weights = target_weights / target_weights.sum() if target_weights.sum() > 0 else target_weights

                # Get prices for cost computation
                if rebal_date in prices.index:
                    prices_date = prices.loc[rebal_date]
                else:
                    prices_date = prices[prices.index <= rebal_date].iloc[-1] if len(prices) > 0 else None
                    if prices_date is None:
                        continue

                # Apply transaction costs
                cost = self._apply_transaction_costs(prev_weights, target_weights, prices_date)

                # Store results
                all_weights[rebal_date] = target_weights
                all_turnover.append(self._compute_turnover(prev_weights, target_weights))
                all_cost_drag.append(cost)

                # Compute portfolio returns for holding period
                if next_rebal_date in prices.index:
                    port_rets = self._compute_portfolio_returns(
                        target_weights, log_returns, rebal_date, next_rebal_date
                    )
                    all_portfolio_rets.update(port_rets)

                prev_weights = target_weights.copy()

            except Exception as e:
                logger.error(f"Error at rebalance date {rebal_date}: {e}")
                continue

        # Compile results
        if not all_portfolio_rets:
            logger.warning("No portfolio returns computed")
            return self._empty_result()

        portfolio_returns = pd.Series(all_portfolio_rets).sort_index()

        # Convert weights dict to DataFrame
        weights_df = pd.DataFrame(all_weights).T

        result = {
            'portfolio_returns': portfolio_returns,
            'positions': weights_df,
            'turnover': pd.Series(all_turnover, index=list(all_weights.keys())),
            'cost_drag': pd.Series(all_cost_drag, index=list(all_weights.keys())),
            'total_cost': sum(all_cost_drag),
            'rebalance_dates': rebalance_dates,
        }

        logger.info(
            f"Backtest completed: {len(portfolio_returns)} daily returns, "
            f"{len(all_weights)} rebalances, total cost: {result['total_cost']:.4f}"
        )

        return result

    def _get_rebalance_dates(self, date_index: pd.DatetimeIndex) -> list:
        """Get rebalance dates based on frequency."""
        if self.rebalance_freq == "weekly":
            # Group by year-week, take Friday (or last day of week)
            return [date for date in date_index
                    if date.weekday() == 4 or date == date_index[-1]]  # Friday
        else:
            return list(date_index)

    def _compute_weights(self, signals: pd.Series, vols: pd.Series,
                        sector_map: pd.Series, top_pct: float) -> pd.Series:
        """
        Compute vol-parity weights from signals.

        Parameters
        ----------
        signals : pd.Series
            Signal by ticker (higher is better)
        vols : pd.Series
            Volatility by ticker
        sector_map : pd.Series
            Sector by ticker
        top_pct : float
            Fraction of universe to include in long book

        Returns
        -------
        pd.Series
            Weight by ticker, indexed by ticker
        """
        return self.portfolio_constructor.build_portfolio(signals, vols, sector_map)

    def _apply_transaction_costs(self, old_weights: pd.Series, new_weights: pd.Series,
                                  prices: pd.Series) -> float:
        """
        Compute and apply transaction costs.

        Parameters
        ----------
        old_weights : pd.Series
            Previous portfolio weights
        new_weights : pd.Series
            Target portfolio weights
        prices : pd.Series
            Current prices by ticker

        Returns
        -------
        float
            Cost as fraction of portfolio value
        """
        # Align old and new weights
        all_tickers = old_weights.index.union(new_weights.index)
        old_w = old_weights.reindex(all_tickers, fill_value=0.0)
        new_w = new_weights.reindex(all_tickers, fill_value=0.0)

        # Turnover = sum(abs(new_w - old_w)) / 2
        turnover = np.abs(new_w - old_w).sum() / 2.0

        commission_per_share = self.config.get("transaction_costs.commission_per_share", 0.005)
        slippage_bps = self.config.get("transaction_costs.slippage_bps", 5)
        spread_bps = self.config.get("transaction_costs.spread_bps", 3)
        market_impact_coeff = self.config.get("transaction_costs.market_impact_coeff", 0.05)

        # Commission + slippage + spread
        simple_cost = (commission_per_share * 100) / 10000 + slippage_bps / 10000 + spread_bps / 10000

        # Market impact: coeff * sqrt(turnover)
        impact = market_impact_coeff * np.sqrt(max(turnover, 0.0)) / 10000

        total_cost = (simple_cost + impact) * turnover

        return total_cost

    def _compute_turnover(self, old_weights: pd.Series, new_weights: pd.Series) -> float:
        """
        Compute turnover between two weight vectors.

        Turnover = sum(abs(new_w - old_w)) / 2
        """
        if old_weights.empty and new_weights.empty:
            return 0.0

        all_tickers = old_weights.index.union(new_weights.index)
        old_w = old_weights.reindex(all_tickers, fill_value=0.0)
        new_w = new_weights.reindex(all_tickers, fill_value=0.0)

        return np.abs(new_w - old_w).sum() / 2.0

    def _compute_portfolio_returns(self, weights: pd.Series, log_returns: pd.DataFrame,
                                    start_date, end_date) -> Dict[str, float]:
        """
        Compute daily portfolio returns for holding period.

        Parameters
        ----------
        weights : pd.Series
            Portfolio weights by ticker
        log_returns : pd.DataFrame
            Daily log returns, indexed by date, columns are tickers
        start_date : Timestamp
            Start of holding period (exclusive)
        end_date : Timestamp
            End of holding period (inclusive)

        Returns
        -------
        dict
            Map of date to portfolio return
        """
        # Select holding period returns
        mask = (log_returns.index > start_date) & (log_returns.index <= end_date)
        period_returns = log_returns[mask]

        result = {}
        for date in period_returns.index:
            # Daily portfolio return
            daily_ret = (weights * period_returns.loc[date]).sum()
            result[date] = daily_ret

        return result

    def _empty_result(self) -> Dict:
        """Return empty result dict."""
        return {
            'portfolio_returns': pd.Series(dtype=float),
            'positions': pd.DataFrame(),
            'turnover': pd.Series(dtype=float),
            'cost_drag': pd.Series(dtype=float),
            'total_cost': 0.0,
            'rebalance_dates': [],
        }


def run_backtest(predictions: pd.DataFrame, prices_dict: Dict, universe: pd.DataFrame,
                  macro_df: pd.DataFrame, config: dict) -> Dict:
    """
    Convenience wrapper for backtesting.

    Parameters
    ----------
    predictions : pd.DataFrame
        Columns: date, ticker, signal
    prices_dict : dict
        Dict of ticker -> pd.Series (prices by date)
    universe : pd.DataFrame
        Columns: date, ticker, sector
    macro_df : pd.DataFrame
        Macro data for regime detection, indexed by date
    config : dict
        Configuration dict

    Returns
    -------
    dict
        Backtest results including benchmark comparison
    """
    logger.info("Running backtest with macro regime detection...")

    # Convert prices_dict to DataFrame
    prices = pd.DataFrame(prices_dict)
    prices.index.name = 'date'

    # Detect regime from macro_df
    regime_labels = None
    if not macro_df.empty and 'regime' in macro_df.columns:
        regime_labels = macro_df['regime']
        logger.info(f"Using macro regime from macro_df")

    # Run backtest
    engine = BacktestEngine(config)
    results = engine.run(predictions, prices, universe, regime_labels)

    # Add benchmark (SPY buy-and-hold)
    if 'SPY' in prices.columns:
        spy_returns = np.log(prices['SPY'] / prices['SPY'].shift(1))
        results['benchmark_returns'] = spy_returns[spy_returns.index.isin(results['portfolio_returns'].index)]

    return results
