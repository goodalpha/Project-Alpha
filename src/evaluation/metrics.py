"""
Performance metrics and reporting.
"""

import pandas as pd
import numpy as np
from loguru import logger
from scipy.stats import spearmanr, pearsonr
from typing import Dict, Optional, Tuple
import matplotlib.pyplot as plt


def compute_sharpe(returns: pd.Series, rf: float = 0.0, annualize: int = 252) -> float:
    """
    Compute Sharpe ratio.

    Parameters
    ----------
    returns : pd.Series
        Daily returns
    rf : float
        Risk-free rate (annualized), default 0.0
    annualize : int
        Annualization factor, default 252 (daily)

    Returns
    -------
    float
        Sharpe ratio
    """
    if returns.empty or len(returns) < 2:
        return np.nan

    excess_returns = returns - rf / annualize
    mean_excess = excess_returns.mean()
    std_excess = excess_returns.std()

    if std_excess == 0:
        return np.nan

    sharpe = (mean_excess / std_excess) * np.sqrt(annualize)

    return sharpe


def compute_sortino(returns: pd.Series, rf: float = 0.0, annualize: int = 252) -> float:
    """
    Compute Sortino ratio.

    Uses downside deviation (only negative returns).

    Parameters
    ----------
    returns : pd.Series
        Daily returns
    rf : float
        Risk-free rate (annualized), default 0.0
    annualize : int
        Annualization factor, default 252 (daily)

    Returns
    -------
    float
        Sortino ratio
    """
    if returns.empty or len(returns) < 2:
        return np.nan

    excess_returns = returns - rf / annualize
    downside = excess_returns[excess_returns < 0]

    if downside.empty:
        return np.nan

    downside_std = downside.std()

    if downside_std == 0:
        return np.nan

    sortino = (excess_returns.mean() / downside_std) * np.sqrt(annualize)

    return sortino


def compute_max_drawdown(returns: pd.Series) -> float:
    """
    Compute maximum drawdown.

    Parameters
    ----------
    returns : pd.Series
        Daily returns

    Returns
    -------
    float
        Maximum drawdown (negative value)
    """
    if returns.empty or len(returns) < 2:
        return np.nan

    cumulative = (1 + returns).cumprod()
    running_max = cumulative.expanding().max()
    drawdown = (cumulative - running_max) / running_max

    return drawdown.min()


def compute_calmar(returns: pd.Series) -> float:
    """
    Compute Calmar ratio.

    Calmar = annualized_return / abs(max_drawdown)

    Parameters
    ----------
    returns : pd.Series
        Daily returns

    Returns
    -------
    float
        Calmar ratio
    """
    if returns.empty or len(returns) < 2:
        return np.nan

    annualized_return = returns.mean() * 252
    max_dd = compute_max_drawdown(returns)

    if max_dd >= 0 or max_dd == np.nan:
        return np.nan

    calmar = annualized_return / abs(max_dd)

    return calmar


def compute_ic_series(predictions: pd.DataFrame, actuals: pd.DataFrame) -> pd.Series:
    """
    Compute Information Coefficient (Pearson correlation) per date.

    Parameters
    ----------
    predictions : pd.DataFrame
        Predicted returns, indexed by date, columns are tickers
    actuals : pd.DataFrame
        Actual returns, indexed by date, columns are tickers

    Returns
    -------
    pd.Series
        IC by date, indexed by date
    """
    ic_by_date = {}

    # Align
    common_dates = predictions.index.intersection(actuals.index)
    common_tickers = predictions.columns.intersection(actuals.columns)

    predictions = predictions.loc[common_dates, common_tickers]
    actuals = actuals.loc[common_dates, common_tickers]

    for date in common_dates:
        pred_date = predictions.loc[date].dropna()
        actual_date = actuals.loc[date].dropna()

        # Align by ticker
        common = pred_date.index.intersection(actual_date.index)

        if len(common) < 2:
            continue

        pred_date = pred_date[common]
        actual_date = actual_date[common]

        # Compute Pearson correlation
        try:
            corr, _ = pearsonr(pred_date.values, actual_date.values)
            ic_by_date[date] = corr
        except Exception as e:
            logger.debug(f"Error computing IC at {date}: {e}")
            continue

    return pd.Series(ic_by_date)


def compute_rank_ic_series(predictions: pd.DataFrame, actuals: pd.DataFrame) -> pd.Series:
    """
    Compute Rank Information Coefficient (Spearman correlation) per date.

    Parameters
    ----------
    predictions : pd.DataFrame
        Predicted returns, indexed by date, columns are tickers
    actuals : pd.DataFrame
        Actual returns, indexed by date, columns are tickers

    Returns
    -------
    pd.Series
        Rank IC by date, indexed by date
    """
    rank_ic_by_date = {}

    # Align
    common_dates = predictions.index.intersection(actuals.index)
    common_tickers = predictions.columns.intersection(actuals.columns)

    predictions = predictions.loc[common_dates, common_tickers]
    actuals = actuals.loc[common_dates, common_tickers]

    for date in common_dates:
        pred_date = predictions.loc[date].dropna()
        actual_date = actuals.loc[date].dropna()

        # Align by ticker
        common = pred_date.index.intersection(actual_date.index)

        if len(common) < 2:
            continue

        pred_date = pred_date[common]
        actual_date = actual_date[common]

        # Compute Spearman correlation
        try:
            corr, _ = spearmanr(pred_date.values, actual_date.values)
            rank_ic_by_date[date] = corr
        except Exception as e:
            logger.debug(f"Error computing rank IC at {date}: {e}")
            continue

    return pd.Series(rank_ic_by_date)


def compute_turnover(positions: pd.DataFrame) -> pd.Series:
    """
    Compute period-by-period turnover.

    Turnover = sum(abs(new_w - old_w)) / 2

    Parameters
    ----------
    positions : pd.DataFrame
        Portfolio weights, indexed by date, columns are tickers

    Returns
    -------
    pd.Series
        Turnover by date (starting from second date)
    """
    if positions.empty or len(positions) < 2:
        return pd.Series(dtype=float)

    # Forward fill NaNs within each row
    positions = positions.fillna(0)

    # Compute period changes
    weight_changes = positions.diff().fillna(0)

    # Turnover = sum(abs(change)) / 2
    turnover = weight_changes.abs().sum(axis=1) / 2.0

    return turnover[1:]  # Skip first NaN


def compute_hit_rate(predictions: pd.DataFrame, actuals: pd.DataFrame) -> float:
    """
    Compute hit rate (% of correct directional predictions).

    Parameters
    ----------
    predictions : pd.DataFrame
        Predicted returns, indexed by date, columns are tickers
    actuals : pd.DataFrame
        Actual returns, indexed by date, columns are tickers

    Returns
    -------
    float
        Hit rate (0-1)
    """
    # Align
    common_dates = predictions.index.intersection(actuals.index)
    common_tickers = predictions.columns.intersection(actuals.columns)

    predictions = predictions.loc[common_dates, common_tickers]
    actuals = actuals.loc[common_dates, common_tickers]

    if predictions.empty or actuals.empty:
        return np.nan

    # Compute directions
    pred_direction = np.sign(predictions.values)
    actual_direction = np.sign(actuals.values)

    # Count correct predictions
    correct = (pred_direction == actual_direction).sum()
    total = (~np.isnan(pred_direction) & ~np.isnan(actual_direction)).sum()

    if total == 0:
        return np.nan

    hit_rate = correct / total

    return hit_rate


class PerformanceReport:
    """
    Comprehensive performance report and analysis.
    """

    def __init__(self, portfolio_returns: pd.Series, benchmark_returns: pd.Series,
                 predictions: pd.DataFrame, actuals: pd.DataFrame,
                 positions: pd.DataFrame, config: dict):
        """
        Initialize performance report.

        Parameters
        ----------
        portfolio_returns : pd.Series
            Daily portfolio returns
        benchmark_returns : pd.Series
            Daily benchmark returns (e.g., SPY)
        predictions : pd.DataFrame
            Model predictions by date and ticker
        actuals : pd.DataFrame
            Actual returns by date and ticker
        positions : pd.DataFrame
            Portfolio positions (weights) by date and ticker
        config : dict
            Configuration dict
        """
        self.portfolio_returns = portfolio_returns.dropna()
        self.benchmark_returns = benchmark_returns[benchmark_returns.index.isin(
            self.portfolio_returns.index)].dropna()
        self.predictions = predictions
        self.actuals = actuals
        self.positions = positions
        self.config = config

        self._computed_metrics = None

        logger.info(
            f"PerformanceReport: {len(self.portfolio_returns)} portfolio returns, "
            f"{len(self.benchmark_returns)} benchmark returns"
        )

    def summary(self) -> Dict:
        """
        Compute comprehensive performance summary.

        Returns
        -------
        dict
            Keys: annualized_return, sharpe, sortino, max_drawdown, calmar,
                  mean_ic, icir, mean_rank_ic, hit_rate,
                  avg_turnover, avg_num_positions, avg_gross_exposure,
                  alpha, beta, information_ratio
        """
        if self._computed_metrics is not None:
            return self._computed_metrics

        result = {}

        # Return metrics
        if not self.portfolio_returns.empty:
            result['annualized_return'] = self.portfolio_returns.mean() * 252
            result['sharpe'] = compute_sharpe(self.portfolio_returns)
            result['sortino'] = compute_sortino(self.portfolio_returns)
            result['max_drawdown'] = compute_max_drawdown(self.portfolio_returns)
            result['calmar'] = compute_calmar(self.portfolio_returns)
        else:
            result['annualized_return'] = np.nan
            result['sharpe'] = np.nan
            result['sortino'] = np.nan
            result['max_drawdown'] = np.nan
            result['calmar'] = np.nan

        # IC metrics
        ic_series = compute_ic_series(self.predictions, self.actuals)
        if not ic_series.empty:
            result['mean_ic'] = ic_series.mean()
            result['icir'] = ic_series.mean() / ic_series.std() if ic_series.std() > 0 else np.nan
        else:
            result['mean_ic'] = np.nan
            result['icir'] = np.nan

        rank_ic_series = compute_rank_ic_series(self.predictions, self.actuals)
        if not rank_ic_series.empty:
            result['mean_rank_ic'] = rank_ic_series.mean()
        else:
            result['mean_rank_ic'] = np.nan

        result['hit_rate'] = compute_hit_rate(self.predictions, self.actuals)

        # Position metrics
        turnover_series = compute_turnover(self.positions)
        if not turnover_series.empty:
            result['avg_turnover'] = turnover_series.mean()
        else:
            result['avg_turnover'] = np.nan

        if not self.positions.empty:
            result['avg_num_positions'] = self.positions.notna().sum(axis=1).mean()
            result['avg_gross_exposure'] = self.positions.abs().sum(axis=1).mean()
        else:
            result['avg_num_positions'] = np.nan
            result['avg_gross_exposure'] = np.nan

        # Vs benchmark
        if not self.benchmark_returns.empty and not self.portfolio_returns.empty:
            # Align returns
            common_dates = self.portfolio_returns.index.intersection(
                self.benchmark_returns.index
            )
            port_ret = self.portfolio_returns[common_dates]
            bench_ret = self.benchmark_returns[common_dates]

            # Alpha and beta
            cov_mat = np.cov(port_ret.values, bench_ret.values)
            var_bench = np.var(bench_ret.values)

            if var_bench > 0:
                result['beta'] = cov_mat[0, 1] / var_bench
                result['alpha'] = port_ret.mean() - result['beta'] * bench_ret.mean()

                # Information ratio
                active_returns = port_ret - result['beta'] * bench_ret
                tracking_error = active_returns.std() * np.sqrt(252)

                if tracking_error > 0:
                    result['information_ratio'] = active_returns.mean() * 252 / tracking_error
                else:
                    result['information_ratio'] = np.nan
            else:
                result['beta'] = np.nan
                result['alpha'] = np.nan
                result['information_ratio'] = np.nan
        else:
            result['beta'] = np.nan
            result['alpha'] = np.nan
            result['information_ratio'] = np.nan

        self._computed_metrics = result
        return result

    def plot_tearsheet(self, save_path: Optional[str] = None) -> None:
        """
        Plot 4-panel performance tearsheet.

        Panels:
        1. Cumulative returns (portfolio vs benchmark)
        2. Rolling 63-day Sharpe ratio
        3. Rolling 21-day Information Coefficient
        4. Drawdown chart

        Parameters
        ----------
        save_path : str, optional
            Path to save figure
        """
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))
        fig.suptitle('Performance Tearsheet', fontsize=16)

        # Panel 1: Cumulative returns
        ax = axes[0, 0]
        if not self.portfolio_returns.empty:
            cum_port = (1 + self.portfolio_returns).cumprod()
            ax.plot(cum_port.index, cum_port.values, label='Portfolio', linewidth=2)

        if not self.benchmark_returns.empty:
            # Align benchmark to portfolio dates
            bench_aligned = self.benchmark_returns[self.benchmark_returns.index.isin(
                self.portfolio_returns.index
            )]
            cum_bench = (1 + bench_aligned).cumprod()
            ax.plot(cum_bench.index, cum_bench.values, label='Benchmark', linewidth=2, alpha=0.7)

        ax.set_title('Cumulative Returns')
        ax.set_ylabel('Cumulative Return')
        ax.legend()
        ax.grid(True, alpha=0.3)

        # Panel 2: Rolling Sharpe
        ax = axes[0, 1]
        if not self.portfolio_returns.empty and len(self.portfolio_returns) >= 63:
            rolling_sharpe = []
            rolling_dates = []

            for i in range(62, len(self.portfolio_returns)):
                window_ret = self.portfolio_returns.iloc[i-62:i+1]
                sharpe = compute_sharpe(window_ret)
                rolling_sharpe.append(sharpe)
                rolling_dates.append(self.portfolio_returns.index[i])

            ax.plot(rolling_dates, rolling_sharpe, linewidth=2)
            ax.set_title('Rolling 63-Day Sharpe Ratio')
            ax.set_ylabel('Sharpe Ratio')
            ax.axhline(y=0, color='red', linestyle='--', alpha=0.5)
            ax.grid(True, alpha=0.3)

        # Panel 3: Rolling Rank IC
        ax = axes[1, 0]
        rank_ic = compute_rank_ic_series(self.predictions, self.actuals)
        if not rank_ic.empty and len(rank_ic) >= 21:
            rolling_ic = rank_ic.rolling(window=21).mean()
            ax.plot(rolling_ic.index, rolling_ic.values, linewidth=2)
            ax.set_title('Rolling 21-Day Rank IC')
            ax.set_ylabel('Rank IC')
            ax.axhline(y=0, color='red', linestyle='--', alpha=0.5)
            ax.grid(True, alpha=0.3)

        # Panel 4: Drawdown
        ax = axes[1, 1]
        if not self.portfolio_returns.empty:
            cumulative = (1 + self.portfolio_returns).cumprod()
            running_max = cumulative.expanding().max()
            drawdown = (cumulative - running_max) / running_max

            ax.fill_between(drawdown.index, drawdown.values, 0, alpha=0.3)
            ax.plot(drawdown.index, drawdown.values, linewidth=2)
            ax.set_title('Portfolio Drawdown')
            ax.set_ylabel('Drawdown')
            ax.grid(True, alpha=0.3)

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches='tight')
            logger.info(f"Tearsheet saved to {save_path}")

        plt.show()

    def to_dict(self) -> Dict:
        """
        Convert report to dictionary.

        Returns
        -------
        dict
            Summary metrics dict
        """
        return self.summary()

    def to_dataframe(self) -> pd.DataFrame:
        """
        Convert report to DataFrame.

        Returns
        -------
        pd.DataFrame
            Single-row DataFrame with all metrics
        """
        summary = self.summary()
        return pd.DataFrame([summary])
