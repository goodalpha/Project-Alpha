"""
PROJECT ATLAS - TradingView Strategy Optimizer
Improves signal generation and execution strategy using historical analysis
Includes position sizing optimization, confidence thresholds, and risk management
"""

import json
import logging
import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, List, Tuple
from pathlib import Path
import config

logger = logging.getLogger(__name__)
logger.setLevel("INFO")


class TradingViewStrategyOptimizer:
    """
    Optimizes ATLAS trading signals for TradingView paper trading.
    Tests different confidence thresholds, position sizing, and risk controls.
    """

    def __init__(self, initial_capital: float = 100_000):
        self.initial_capital = initial_capital
        self.optimization_results = []

    def generate_optimized_signals(
        self,
        historical_data: pd.DataFrame,
        confidence_threshold: float = 0.55,
        max_positions: int = 20,
        position_size: float = 0.05
    ) -> List[Dict]:
        """
        Generate optimized trading signals with confidence filtering.

        Args:
            historical_data: Historical position data
            confidence_threshold: Minimum confidence to execute trade
            max_positions: Maximum number of concurrent positions
            position_size: Allocation per position (5% default)

        Returns:
            List of optimized trading signals
        """
        symbols = historical_data['symbol'].unique()
        signals = []

        symbol_performance = historical_data.groupby('symbol').agg({
            'pnl_pct': ['mean', 'std', 'count'],
            'pnl': 'sum'
        })

        for symbol in symbols:
            mean_return = symbol_performance.loc[symbol, ('pnl_pct', 'mean')]
            std_return = symbol_performance.loc[symbol, ('pnl_pct', 'std')]
            win_rate = len(historical_data[(historical_data['symbol'] == symbol) &
                                          (historical_data['pnl_pct'] > 0)]) / \
                       len(historical_data[historical_data['symbol'] == symbol])

            # Calculate confidence: Sharpe ratio based confidence
            sharpe = mean_return / (std_return + 0.001) if std_return > 0 else 0
            base_confidence = 0.5 + (sharpe * 0.15)

            # Boost confidence for high win rate
            win_boost = (win_rate - 0.5) * 0.2 if win_rate > 0.5 else 0
            confidence = min(0.95, max(0.5, base_confidence + win_boost))

            # Filter by confidence threshold
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

        # Sort by confidence and limit positions
        signals.sort(key=lambda x: x['confidence'], reverse=True)
        return signals[:max_positions]

    def backtest_optimized_strategy(
        self,
        signals: List[Dict],
        historical_data: pd.DataFrame,
        slippage_pct: float = 0.02
    ) -> Dict:
        """
        Backtest optimized strategy against historical data.

        Args:
            signals: Optimized trading signals
            historical_data: Historical position data
            slippage_pct: Slippage percentage to apply

        Returns:
            Backtest results with performance metrics
        """
        executed_trades = 0
        winning_trades = 0
        total_pnl = 0
        trade_results = []

        latest_data = historical_data.groupby('symbol').tail(1)
        price_map = dict(zip(latest_data['symbol'], latest_data['current_price']))

        for signal in signals:
            symbol = signal['symbol']
            if symbol not in price_map:
                continue

            # Get historical P&L for this symbol
            symbol_history = historical_data[historical_data['symbol'] == symbol]
            avg_return_pct = symbol_history['pnl_pct'].mean()

            # Apply slippage
            slippage = np.random.uniform(-slippage_pct, slippage_pct) * 100
            actual_return_pct = avg_return_pct + slippage

            pnl = signal['position_value'] * (actual_return_pct / 100)
            total_pnl += pnl

            executed_trades += 1
            if pnl > 0:
                winning_trades += 1

            trade_results.append({
                'symbol': symbol,
                'confidence': signal['confidence'],
                'position_value': signal['position_value'],
                'expected_return': signal['expected_return'],
                'actual_return': round(actual_return_pct, 3),
                'pnl': round(pnl, 2),
                'profitable': pnl > 0,
            })

        # Calculate metrics
        win_rate = winning_trades / executed_trades if executed_trades > 0 else 0
        final_value = self.initial_capital + total_pnl

        return {
            'executed_trades': executed_trades,
            'winning_trades': winning_trades,
            'losing_trades': executed_trades - winning_trades,
            'win_rate': round(win_rate, 3),
            'total_pnl': round(total_pnl, 2),
            'final_value': round(final_value, 2),
            'total_return_pct': round((total_pnl / self.initial_capital) * 100, 2),
            'avg_trade_pnl': round(total_pnl / executed_trades, 2) if executed_trades > 0 else 0,
            'trade_details': trade_results,
        }

    def run_optimization_sweep(self, historical_data: pd.DataFrame) -> List[Dict]:
        """
        Run optimization sweep across different confidence thresholds.

        Args:
            historical_data: Historical position data

        Returns:
            List of optimization results
        """
        logger.info("Running optimization sweep...")

        thresholds = [0.50, 0.55, 0.60, 0.65, 0.70, 0.75]
        results = []

        for threshold in thresholds:
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
                logger.info(f"Threshold {threshold}: {len(signals)} signals, "
                          f"Win Rate: {backtest_result['win_rate']:.1%}, "
                          f"Return: {backtest_result['total_return_pct']:+.2f}%")

        return results

    def run_monte_carlo_simulation(
        self,
        signals: List[Dict],
        historical_data: pd.DataFrame,
        num_simulations: int = 1000
    ) -> Dict:
        """
        Run Monte Carlo simulation on strategy performance.

        Args:
            signals: Trading signals
            historical_data: Historical data
            num_simulations: Number of simulations to run

        Returns:
            Monte Carlo results with confidence intervals
        """
        logger.info(f"Running {num_simulations} Monte Carlo simulations...")

        sim_results = []

        for _ in range(num_simulations):
            # Randomly sample from historical returns
            sample_returns = []
            for signal in signals:
                symbol = signal['symbol']
                symbol_data = historical_data[historical_data['symbol'] == symbol]

                if len(symbol_data) > 0:
                    # Random sample with replacement
                    random_return = symbol_data['pnl_pct'].sample(1, replace=True).values[0]
                    sample_returns.append(random_return)

            # Calculate portfolio return
            if sample_returns:
                portfolio_return = np.mean(sample_returns)
                pnl = self.initial_capital * (portfolio_return / 100)
                final_value = self.initial_capital + pnl
                sim_results.append({
                    'final_value': final_value,
                    'pnl': pnl,
                    'return_pct': portfolio_return,
                })

        # Calculate statistics
        final_values = [r['final_value'] for r in sim_results]
        returns_pct = [r['return_pct'] for r in sim_results]

        return {
            'num_simulations': num_simulations,
            'mean_return': round(np.mean(returns_pct), 3),
            'std_return': round(np.std(returns_pct), 3),
            'min_return': round(np.min(returns_pct), 3),
            'max_return': round(np.max(returns_pct), 3),
            'percentile_5': round(np.percentile(returns_pct, 5), 3),
            'percentile_25': round(np.percentile(returns_pct, 25), 3),
            'percentile_50': round(np.percentile(returns_pct, 50), 3),
            'percentile_75': round(np.percentile(returns_pct, 75), 3),
            'percentile_95': round(np.percentile(returns_pct, 95), 3),
            'best_case': round(np.max(final_values), 2),
            'worst_case': round(np.min(final_values), 2),
            'mean_final_value': round(np.mean(final_values), 2),
        }

    def save_optimization_report(self, optimization_results: List[Dict],
                                 monte_carlo_results: Dict,
                                 best_signals: List[Dict]):
        """Save optimization report to file."""
        filename = f"tradingview_optimization_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        filepath = config.BACKTEST_DIR / filename

        report = {
            'timestamp': datetime.now().isoformat(),
            'optimization_sweep': optimization_results,
            'monte_carlo_analysis': monte_carlo_results,
            'recommended_signals': best_signals[:10],
            'summary': {
                'initial_capital': self.initial_capital,
                'best_return': max([r['total_return_pct'] for r in optimization_results]) if optimization_results else 0,
                'best_win_rate': max([r['win_rate'] for r in optimization_results]) if optimization_results else 0,
                'optimal_threshold': optimization_results[0]['confidence_threshold'] if optimization_results else 0.6,
            }
        }

        try:
            with open(filepath, 'w') as f:
                json.dump(report, f, indent=2, default=str)
            logger.info(f"✅ Report saved to {filepath}")
            return filepath
        except Exception as e:
            logger.error(f"Error saving report: {e}")
            return None


def run_full_optimization(historical_data: pd.DataFrame):
    """Run complete strategy optimization workflow."""
    print("\n" + "="*70)
    print("ATLAS - TradingView Strategy Optimizer".center(70))
    print("="*70 + "\n")

    optimizer = TradingViewStrategyOptimizer(initial_capital=100_000)

    # Step 1: Optimization sweep
    print("Step 1: Running optimization sweep across confidence thresholds...")
    optimization_results = optimizer.run_optimization_sweep(historical_data)
    print(f"✅ Tested {len(optimization_results)} strategies\n")

    # Step 2: Find best strategy
    print("Step 2: Finding optimal strategy...")
    best_result = max(optimization_results, key=lambda x: x['total_return_pct'])
    best_threshold = best_result['confidence_threshold']
    best_signals = optimizer.generate_optimized_signals(
        historical_data,
        confidence_threshold=best_threshold,
        max_positions=20,
        position_size=0.05
    )
    print(f"✅ Optimal threshold: {best_threshold}")
    print(f"   Expected return: {best_result['total_return_pct']:+.2f}%")
    print(f"   Win rate: {best_result['win_rate']:.1%}")
    print(f"   Trades: {best_result['executed_trades']}\n")

    # Step 3: Monte Carlo analysis
    print("Step 3: Running Monte Carlo analysis (1000 simulations)...")
    monte_carlo = optimizer.run_monte_carlo_simulation(best_signals, historical_data, num_simulations=1000)
    print(f"✅ Completed 1000 simulations\n")

    # Print results
    print("="*70)
    print("OPTIMIZATION RESULTS")
    print("="*70 + "\n")

    print("Confidence Threshold Sweep:")
    print("-" * 70)
    print("Threshold | Signals | Trades | Win Rate | Return    | P&L")
    print("-" * 70)
    for result in optimization_results:
        print(f"{result['confidence_threshold']:9.2f} | {result['signals_generated']:7d} | "
              f"{result['executed_trades']:6d} | {result['win_rate']:8.1%} | "
              f"{result['total_return_pct']:9.2f}% | ${result['total_pnl']:+8,.0f}")
    print()

    print("="*70)
    print("MONTE CARLO ANALYSIS (1000 Simulations)")
    print("="*70 + "\n")

    print(f"Mean Return:        {monte_carlo['mean_return']:+.2f}%")
    print(f"Std Deviation:      {monte_carlo['std_return']:.2f}%")
    print(f"Return Range:       {monte_carlo['min_return']:.2f}% to {monte_carlo['max_return']:+.2f}%\n")

    print("Percentile Returns:")
    print(f"  5th percentile:   {monte_carlo['percentile_5']:+.2f}%")
    print(f"  25th percentile:  {monte_carlo['percentile_25']:+.2f}%")
    print(f"  Median (50th):    {monte_carlo['percentile_50']:+.2f}%")
    print(f"  75th percentile:  {monte_carlo['percentile_75']:+.2f}%")
    print(f"  95th percentile:  {monte_carlo['percentile_95']:+.2f}%\n")

    print("Expected Portfolio Values:")
    print(f"  Worst case (5%):  ${monte_carlo['worst_case']:,.2f}")
    print(f"  Base case (50%):  ${monte_carlo['mean_final_value']:,.2f}")
    print(f"  Best case (95%):  ${monte_carlo['best_case']:,.2f}\n")

    # Top signals
    print("="*70)
    print("RECOMMENDED SIGNALS (Top 10)")
    print("="*70 + "\n")
    print("Rank | Symbol | Confidence | Expected Return | Position Value")
    print("-" * 70)
    for i, signal in enumerate(best_signals[:10], 1):
        print(f"{i:4d} | {signal['symbol']:6s} | {signal['confidence']:10.3f} | "
              f"{signal['expected_return']:15.2f}% | ${signal['position_value']:9,.0f}")
    print()

    # Save report
    print("Step 4: Saving optimization report...")
    filepath = optimizer.save_optimization_report(optimization_results, monte_carlo, best_signals)
    if filepath:
        print(f"✅ Report saved\n")

    print("="*70)
    print("✅ OPTIMIZATION COMPLETE")
    print("="*70)
    print("\nNext Steps:")
    print("1. Review optimization results above")
    print("2. Use recommended signals with confidence threshold: {:.2f}".format(best_threshold))
    print("3. Execute top 10 signals on TradingView")
    print("4. Run live scraper to track execution")
    print("5. Compare actual results vs Monte Carlo projections")


if __name__ == "__main__":
    # Import historical data from previous backtest
    from tradingview_backtest_signals import TradingViewHistoricalBacktest

    logging.basicConfig(
        format=config.LOG_FORMAT,
        level="INFO",
        handlers=[
            logging.FileHandler(config.LOGS_DIR / "tradingview_optimizer.log"),
            logging.StreamHandler()
        ]
    )

    # Generate or load historical data
    backtest = TradingViewHistoricalBacktest()
    historical_data = backtest.generate_historical_positions(num_days=60, num_stocks=30)

    # Run optimization
    run_full_optimization(historical_data)
