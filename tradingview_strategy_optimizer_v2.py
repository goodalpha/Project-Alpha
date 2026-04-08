"""
PROJECT ATLAS - TradingView Strategy Optimizer (Improved v2)
Improves signal generation and execution strategy using historical analysis

Improvements:
- Better type hints
- Comprehensive error handling
- Input validation
- Detailed logging
- Monte Carlo analysis
- Performance optimization
"""

import json
import logging
import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)
logger.setLevel("INFO")

import config_v2 as config
from utils_v2 import format_percentage, format_currency


class OptimizationError(Exception):
    """Raised when optimization fails."""
    pass


class TradingViewStrategyOptimizer:
    """
    Optimizes ATLAS trading signals for TradingView paper trading.
    Tests different confidence thresholds and position sizing.
    """

    def __init__(self, initial_capital: float = 100_000):
        """
        Initialize optimizer.

        Args:
            initial_capital: Starting portfolio value

        Raises:
            ValueError: If capital is invalid
        """
        if initial_capital <= 0:
            raise ValueError(f"Capital must be positive: {initial_capital}")

        self.initial_capital = float(initial_capital)
        self.optimization_results: List[Dict] = []

    def generate_optimized_signals(
        self,
        historical_data: pd.DataFrame,
        confidence_threshold: float = 0.55,
        max_positions: int = 20,
        position_size: float = 0.05,
    ) -> List[Dict]:
        """
        Generate optimized trading signals with filtering.

        Args:
            historical_data: Historical position data
            confidence_threshold: Minimum confidence to execute
            max_positions: Maximum concurrent positions
            position_size: Allocation per position

        Returns:
            List of optimized signals
        """
        if historical_data.empty:
            logger.warning("No historical data provided")
            return []

        logger.info(
            f"Generating optimized signals "
            f"(threshold={confidence_threshold:.2f}, max_pos={max_positions})"
        )

        signals = []

        try:
            symbol_performance = historical_data.groupby('symbol').agg({
                'pnl_pct': ['mean', 'std', 'count'],
                'pnl': 'sum'
            })

            for symbol in symbol_performance.index:
                mean_return = symbol_performance.loc[symbol, ('pnl_pct', 'mean')]
                std_return = symbol_performance.loc[symbol, ('pnl_pct', 'std')]
                count = symbol_performance.loc[symbol, ('pnl_pct', 'count')]

                if count < 2:
                    continue

                # Calculate Sharpe-based confidence
                sharpe = mean_return / (std_return + 0.001) if std_return > 0 else 0
                win_rate = len(
                    historical_data[(historical_data['symbol'] == symbol) &
                                   (historical_data['pnl_pct'] > 0)]
                ) / count

                base_confidence = 0.5 + (sharpe * 0.15)
                win_boost = (win_rate - 0.5) * 0.2 if win_rate > 0.5 else 0
                confidence = min(0.95, max(0.5, base_confidence + win_boost))

                if confidence >= confidence_threshold:
                    signals.append({
                        'symbol': symbol,
                        'confidence': round(confidence, 3),
                        'expected_return': round(mean_return, 3),
                        'volatility': round(std_return, 3),
                        'win_rate': round(win_rate, 3),
                        'position_size': position_size,
                        'position_value': self.initial_capital * position_size,
                    })

            signals.sort(key=lambda x: x['confidence'], reverse=True)
            logger.info(f"Generated {len(signals)} optimized signals")
            return signals[:max_positions]

        except Exception as e:
            logger.error(f"Error generating optimized signals: {e}")
            raise OptimizationError(f"Signal generation failed: {e}") from e

    def backtest_optimized_strategy(
        self,
        signals: List[Dict],
        historical_data: pd.DataFrame,
    ) -> Dict:
        """
        Backtest optimized strategy.

        Args:
            signals: Optimized signals
            historical_data: Historical data

        Returns:
            Backtest results
        """
        logger.info(f"Backtesting {len(signals)} signals...")

        executed = 0
        winners = 0
        total_pnl = 0
        trades = []

        try:
            latest = historical_data.groupby('symbol').tail(1)
            price_map = dict(zip(latest['symbol'], latest['current_price']))

            for signal in signals:
                symbol = signal['symbol']
                if symbol not in price_map:
                    continue

                symbol_history = historical_data[historical_data['symbol'] == symbol]
                avg_return_pct = symbol_history['pnl_pct'].mean()

                # Add realistic slippage
                slippage = np.random.uniform(-0.02, 0.02) * 100
                actual_return = avg_return_pct + slippage

                pnl = signal['position_value'] * (actual_return / 100)
                total_pnl += pnl
                executed += 1

                if pnl > 0:
                    winners += 1

                trades.append({
                    'symbol': symbol,
                    'confidence': signal['confidence'],
                    'pnl': round(pnl, 2),
                    'return': round(actual_return, 2),
                })

            win_rate = winners / executed if executed > 0 else 0
            final_value = self.initial_capital + total_pnl

            result = {
                'executed_trades': executed,
                'winning_trades': winners,
                'losing_trades': executed - winners,
                'win_rate': round(win_rate, 3),
                'total_pnl': round(total_pnl, 2),
                'final_value': round(final_value, 2),
                'total_return_pct': round((total_pnl / self.initial_capital) * 100, 2),
                'avg_trade_pnl': round(total_pnl / executed, 2) if executed > 0 else 0,
            }

            logger.info(
                f"Backtest: {executed} trades, "
                f"Win rate: {win_rate:.1%}, "
                f"Return: {result['total_return_pct']:+.2f}%"
            )

            return result

        except Exception as e:
            logger.error(f"Error backtesting strategy: {e}")
            raise OptimizationError(f"Backtest failed: {e}") from e

    def run_optimization_sweep(
        self,
        historical_data: pd.DataFrame,
        thresholds: Optional[List[float]] = None,
    ) -> List[Dict]:
        """
        Run optimization sweep across thresholds.

        Args:
            historical_data: Historical data
            thresholds: Confidence thresholds to test (default 0.50-0.75)

        Returns:
            List of optimization results
        """
        if thresholds is None:
            thresholds = [0.50, 0.55, 0.60, 0.65, 0.70, 0.75]

        logger.info(f"Running optimization sweep with {len(thresholds)} thresholds...")

        results = []

        for threshold in thresholds:
            try:
                signals = self.generate_optimized_signals(
                    historical_data,
                    confidence_threshold=threshold,
                    max_positions=20,
                    position_size=0.05
                )

                if signals:
                    backtest_result = self.backtest_optimized_strategy(signals, historical_data)
                    result = {
                        'confidence_threshold': threshold,
                        'signals_generated': len(signals),
                        **backtest_result
                    }
                    results.append(result)

            except OptimizationError as e:
                logger.warning(f"Optimization failed for threshold {threshold}: {e}")
                continue

        self.optimization_results = results
        logger.info(f"Optimization sweep complete: {len(results)} results")
        return results

    def run_monte_carlo_simulation(
        self,
        signals: List[Dict],
        historical_data: pd.DataFrame,
        num_simulations: int = 1000,
    ) -> Dict:
        """
        Run Monte Carlo simulation on strategy.

        Args:
            signals: Trading signals
            historical_data: Historical data
            num_simulations: Number of simulations

        Returns:
            Monte Carlo results with confidence intervals
        """
        logger.info(f"Running {num_simulations} Monte Carlo simulations...")

        sim_results = []

        try:
            for _ in range(num_simulations):
                sample_returns = []

                for signal in signals:
                    symbol = signal['symbol']
                    symbol_data = historical_data[historical_data['symbol'] == symbol]

                    if len(symbol_data) > 0:
                        random_return = symbol_data['pnl_pct'].sample(1, replace=True).values[0]
                        sample_returns.append(random_return)

                if sample_returns:
                    portfolio_return = np.mean(sample_returns)
                    pnl = self.initial_capital * (portfolio_return / 100)
                    sim_results.append({
                        'final_value': self.initial_capital + pnl,
                        'return_pct': portfolio_return,
                    })

            if not sim_results:
                logger.warning("No simulation results generated")
                return {}

            final_values = [r['final_value'] for r in sim_results]
            returns_pct = [r['return_pct'] for r in sim_results]

            result = {
                'num_simulations': num_simulations,
                'mean_return': round(np.mean(returns_pct), 3),
                'std_return': round(np.std(returns_pct), 3),
                'min_return': round(np.min(returns_pct), 3),
                'max_return': round(np.max(returns_pct), 3),
                'percentile_5': round(np.percentile(returns_pct, 5), 3),
                'percentile_50': round(np.percentile(returns_pct, 50), 3),
                'percentile_95': round(np.percentile(returns_pct, 95), 3),
                'best_case': round(np.max(final_values), 2),
                'worst_case': round(np.min(final_values), 2),
                'mean_final_value': round(np.mean(final_values), 2),
            }

            logger.info(
                f"Monte Carlo: "
                f"Mean={result['mean_return']:.2f}%, "
                f"Std={result['std_return']:.2f}%"
            )

            return result

        except Exception as e:
            logger.error(f"Monte Carlo simulation failed: {e}")
            raise OptimizationError(f"Monte Carlo failed: {e}") from e

    def save_optimization_report(
        self,
        optimization_results: List[Dict],
        monte_carlo_results: Dict,
        best_signals: List[Dict],
        filename: Optional[str] = None,
    ) -> Optional[Path]:
        """
        Save optimization report to file.

        Args:
            optimization_results: Optimization sweep results
            monte_carlo_results: Monte Carlo analysis results
            best_signals: Best signals
            filename: Output filename

        Returns:
            Path if saved, None otherwise
        """
        try:
            if filename is None:
                filename = f"optimizer_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

            filepath = config.BACKTEST_DIR / filename
            filepath.parent.mkdir(parents=True, exist_ok=True)

            report = {
                'timestamp': datetime.now().isoformat(),
                'optimization_sweep': optimization_results,
                'monte_carlo': monte_carlo_results,
                'top_signals': best_signals[:10],
            }

            with open(filepath, 'w') as f:
                json.dump(report, f, indent=2, default=str)

            logger.info(f"Report saved to {filepath}")
            return filepath

        except IOError as e:
            logger.error(f"Error saving report: {e}")
            return None


if __name__ == "__main__":
    import logging

    logging.basicConfig(
        level="INFO",
        format=config.LOG_FORMAT,
    )

    print("TradingView Strategy Optimizer v2 - Ready to use")
