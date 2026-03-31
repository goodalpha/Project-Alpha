"""
Backtesting module for cross-sectional equity strategies.
"""

from .engine import BacktestEngine, run_backtest

__all__ = ["BacktestEngine", "run_backtest"]
