"""
Risk controls and drawdown monitoring.
"""

import pandas as pd
import numpy as np
from loguru import logger
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple


class RiskControls:
    """
    Risk monitoring and controls.

    Tracks high water mark (HWM), drawdown from peak, and applies
    exposure reduction/halting rules.
    """

    def __init__(self, config: dict):
        """
        Initialize risk controls.

        Parameters
        ----------
        config : dict
            Configuration dict with keys:
            - risk.max_drawdown_halt: float, e.g. 0.15 (15%)
            - risk.drawdown_reduction: float, e.g. 0.10 (10%)
            - risk.reduction_multiplier: float, e.g. 0.50
            - risk.earnings_blackout_days: int, e.g. 2
        """
        self.config = config
        self.hwm = 1.0  # High water mark (normalized)
        self.current_equity = 1.0
        self.trading_halted = False

        self.max_drawdown_halt = config.get("risk.max_drawdown_halt", 0.15)
        self.drawdown_reduction_threshold = config.get("risk.drawdown_reduction", 0.10)
        self.reduction_multiplier = config.get("risk.reduction_multiplier", 0.50)
        self.earnings_blackout_days = config.get("risk.earnings_blackout_days", 2)

        logger.info(
            f"RiskControls initialized: max_dd_halt={self.max_drawdown_halt}, "
            f"dd_reduction={self.drawdown_reduction_threshold}"
        )

    def update(self, daily_return: float) -> Dict:
        """
        Update equity and compute risk metrics.

        Parameters
        ----------
        daily_return : float
            Daily return (e.g. 0.01 for 1%)

        Returns
        -------
        dict
            Keys: drawdown, hwm, halt, reduce_exposure_pct
        """
        # Update equity
        self.current_equity = self.current_equity * (1.0 + daily_return)

        # Update HWM
        if self.current_equity > self.hwm:
            self.hwm = self.current_equity

        # Compute drawdown
        drawdown = (self.current_equity - self.hwm) / self.hwm if self.hwm > 0 else 0.0

        # Check halt condition
        halt = self.check_halt()

        # Compute exposure reduction
        exposure_mult = self.get_exposure_multiplier()

        result = {
            'drawdown': drawdown,
            'hwm': self.hwm,
            'halt': halt,
            'exposure_multiplier': exposure_mult,
        }

        logger.debug(
            f"Risk update: equity={self.current_equity:.4f}, dd={drawdown:.4f}, "
            f"halt={halt}, exp_mult={exposure_mult:.2f}"
        )

        return result

    def check_halt(self) -> bool:
        """
        Check if trading should be halted.

        Returns True if drawdown > max_drawdown_halt.
        """
        if self.hwm <= 0:
            return False

        drawdown = (self.current_equity - self.hwm) / self.hwm
        halt = drawdown <= -self.max_drawdown_halt  # Negative drawdown

        if halt and not self.trading_halted:
            logger.warning(
                f"Trading HALTED: drawdown {drawdown:.4f} exceeds {-self.max_drawdown_halt}"
            )
            self.trading_halted = True

        return halt

    def get_exposure_multiplier(self) -> float:
        """
        Get portfolio exposure multiplier based on drawdown.

        Returns:
        - 0.0 if trading halted
        - reduction_multiplier if drawdown > drawdown_reduction_threshold
        - 1.0 otherwise
        """
        if self.trading_halted:
            return 0.0

        if self.hwm <= 0:
            return 1.0

        drawdown = (self.current_equity - self.hwm) / self.hwm

        if drawdown <= -self.drawdown_reduction_threshold:
            return self.reduction_multiplier
        else:
            return 1.0

    def earnings_blackout(self, ticker: str, earnings_dates: Dict[str, List],
                         current_date) -> bool:
        """
        Check if ticker is in earnings blackout window.

        Parameters
        ----------
        ticker : str
            Ticker symbol
        earnings_dates : dict
            Map of ticker -> list of earnings dates
        current_date : datetime-like
            Current date

        Returns
        -------
        bool
            True if within blackout window
        """
        if ticker not in earnings_dates:
            return False

        earnings_list = earnings_dates[ticker]
        if not earnings_list:
            return False

        # Convert current_date to Timestamp if needed
        if not isinstance(current_date, pd.Timestamp):
            current_date = pd.Timestamp(current_date)

        # Check if within blackout_days before any earnings
        for earnings_date in earnings_list:
            earnings_date = pd.Timestamp(earnings_date)
            days_to_earnings = (earnings_date - current_date).days

            if 0 <= days_to_earnings <= self.earnings_blackout_days:
                return True

        return False

    def filter_universe_for_blackout(self, universe: List[str], earnings_dates: Dict,
                                     current_date) -> List[str]:
        """
        Filter universe to remove stocks in earnings blackout.

        Parameters
        ----------
        universe : list
            List of tickers
        earnings_dates : dict
            Map of ticker -> list of earnings dates
        current_date : datetime-like
            Current date

        Returns
        -------
        list
            Filtered universe
        """
        filtered = [ticker for ticker in universe
                   if not self.earnings_blackout(ticker, earnings_dates, current_date)]

        if len(filtered) < len(universe):
            logger.debug(f"Filtered {len(universe) - len(filtered)} stocks for earnings blackout")

        return filtered

    def compute_portfolio_risk_metrics(self, weights: pd.Series, returns: pd.DataFrame,
                                      lookback: int = 252) -> Dict:
        """
        Compute portfolio risk metrics.

        Parameters
        ----------
        weights : pd.Series
            Portfolio weights by ticker
        returns : pd.DataFrame
            Daily returns, indexed by date, columns are tickers
        lookback : int
            Lookback window in days, default 252 (1 year)

        Returns
        -------
        dict
            Keys: portfolio_vol, portfolio_beta, var_95, cvar_95, max_drawdown
        """
        if weights.empty or returns.empty:
            return {
                'portfolio_vol': 0.0,
                'portfolio_beta': 0.0,
                'var_95': 0.0,
                'cvar_95': 0.0,
                'max_drawdown': 0.0,
            }

        # Align weights and returns
        common_tickers = weights.index.intersection(returns.columns)
        weights = weights[common_tickers]
        returns = returns[common_tickers]

        if weights.empty or returns.empty:
            logger.warning("Empty weights or returns in risk metrics")
            return {
                'portfolio_vol': 0.0,
                'portfolio_beta': 0.0,
                'var_95': 0.0,
                'cvar_95': 0.0,
                'max_drawdown': 0.0,
            }

        # Use recent returns
        returns = returns.iloc[-lookback:] if len(returns) > lookback else returns

        # Compute portfolio returns
        port_returns = (weights * returns).sum(axis=1)

        # Compute portfolio vol (annualized)
        portfolio_vol = port_returns.std() * np.sqrt(252)

        # Compute portfolio beta (vs SPY if available)
        portfolio_beta = 1.0  # Default
        if 'SPY' in returns.columns:
            spy_returns = returns['SPY']
            cov_port_spy = port_returns.cov(spy_returns)
            var_spy = spy_returns.var()
            if var_spy > 0:
                portfolio_beta = cov_port_spy / var_spy

        # Compute VaR (95%) and CVaR
        sorted_returns = np.sort(port_returns.values)
        var_95 = np.percentile(sorted_returns, 5)  # 5th percentile for negative tail
        cvar_95 = sorted_returns[sorted_returns <= var_95].mean()

        # Compute max drawdown
        cumulative = (1 + port_returns).cumprod()
        running_max = cumulative.expanding().max()
        drawdown_series = (cumulative - running_max) / running_max
        max_drawdown = drawdown_series.min()

        result = {
            'portfolio_vol': portfolio_vol,
            'portfolio_beta': portfolio_beta,
            'var_95': var_95,
            'cvar_95': cvar_95,
            'max_drawdown': max_drawdown,
        }

        return result


def check_risk_limits(weights: pd.Series, config: dict) -> Dict:
    """
    Quick sanity check on portfolio weights.

    Parameters
    ----------
    weights : pd.Series
        Weights by ticker
    config : dict
        Configuration dict

    Returns
    -------
    dict
        Keys: passed (bool), violations (list of str)
    """
    violations = []

    max_position_pct = config.get("portfolio.max_position_pct", 0.05)
    max_gross_leverage = config.get("portfolio.max_gross_leverage", 1.0)

    # Check position limits
    bad_positions = weights[abs(weights) > max_position_pct]
    if not bad_positions.empty:
        violations.append(
            f"Position limit violation: {len(bad_positions)} positions > {max_position_pct}"
        )

    # Check gross leverage
    gross_exposure = weights.abs().sum()
    if gross_exposure > max_gross_leverage * 1.01:  # Allow 1% slack
        violations.append(
            f"Gross leverage {gross_exposure:.4f} exceeds {max_gross_leverage}"
        )

    result = {
        'passed': len(violations) == 0,
        'violations': violations,
    }

    if not result['passed']:
        logger.warning(f"Risk limit violations: {violations}")

    return result
