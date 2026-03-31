"""
Performance evaluation and reporting module.
"""

from .metrics import (
    compute_sharpe,
    compute_sortino,
    compute_max_drawdown,
    compute_calmar,
    compute_ic_series,
    compute_rank_ic_series,
    compute_turnover,
    compute_hit_rate,
    PerformanceReport,
)

__all__ = [
    "compute_sharpe",
    "compute_sortino",
    "compute_max_drawdown",
    "compute_calmar",
    "compute_ic_series",
    "compute_rank_ic_series",
    "compute_turnover",
    "compute_hit_rate",
    "PerformanceReport",
]
