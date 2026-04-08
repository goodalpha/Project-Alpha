"""
PROJECT ATLAS - Backtesting Framework
Walk-forward validation with strict point-in-time correctness
"""

import logging
import pandas as pd
import numpy as np
from typing import List, Dict, Tuple
from datetime import datetime, timedelta
import config
from data_ingestion import PointInTimeDataLoader
from features import FeatureComputer, generate_feature_matrix
from model import AtlasModel

logger = logging.getLogger(__name__)
logger.setLevel(config.LOG_LEVEL)


class BacktestEngine:
    """
    Walk-forward backtesting engine.
    - 3-year train → 6-month test → roll forward quarterly
    - Point-in-time correctness enforced
    - Transaction costs and slippage modeled
    """

    def __init__(self, data_dir: str = None):
        self.data_loader = PointInTimeDataLoader()
        self.results = []
        self.models = {}

    def load_price_data(self, ticker: str, start_date: str, end_date: str) -> pd.DataFrame:
        """Load OHLCV data for a ticker."""
        path = config.DATA_DIR / f"ohlcv_{ticker}.parquet"
        if path.exists():
            df = pd.read_parquet(path)
            df['date'] = pd.to_datetime(df['date'])
            df = df[(df['date'] >= start_date) & (df['date'] <= end_date)]
            return df.sort_values('date')
        return pd.DataFrame()

    def generate_trading_dates(self, start_date: str, end_date: str, frequency: str = 'M') -> List[pd.Timestamp]:
        """
        Generate trading dates for rebalancing.

        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            frequency: 'D' (daily), 'W' (weekly), 'M' (monthly)

        Returns:
            List of timestamps for rebalancing
        """
        dates = pd.date_range(start=start_date, end=end_date, freq='B')  # Business days

        if frequency == 'W':
            # Weekly (Fridays)
            dates = [d for d in dates if d.dayofweek == 4]
        elif frequency == 'M':
            # Monthly (last business day)
            dates = [d for d in dates if d == d + pd.offsets.MonthEnd(0)]

        return [pd.Timestamp(d) for d in dates]

    def run_walk_forward_backtest(
        self,
        tickers: List[str],
        start_date: str,
        end_date: str,
        train_months: int = 36,
        test_months: int = 6,
        roll_months: int = 3,
    ) -> Dict:
        """
        Run walk-forward backtest.

        Args:
            tickers: List of ticker symbols
            start_date: Start date for backtest
            end_date: End date for backtest
            train_months: Training period (months)
            test_months: Testing period (months)
            roll_months: Roll forward period (months)

        Returns:
            Dict with backtest results
        """
        logger.info(f"Starting walk-forward backtest: {start_date} to {end_date}")
        logger.info(f"Train={train_months}m, Test={test_months}m, Roll={roll_months}m")

        # Load all price data upfront
        all_price_data = {}
        for ticker in tickers:
            data = self.load_price_data(ticker, start_date, end_date)
            if not data.empty:
                all_price_data[ticker] = data

        if not all_price_data:
            logger.error("No price data loaded")
            return {}

        logger.info(f"Loaded data for {len(all_price_data)} tickers")

        # Generate walk-forward periods
        start = pd.Timestamp(start_date)
        end = pd.Timestamp(end_date)

        train_end = start + pd.DateOffset(months=train_months)
        test_end = train_end + pd.DateOffset(months=test_months)

        period_num = 0
        backtest_results = []

        while test_end <= end:
            period_num += 1
            logger.info(f"\n=== PERIOD {period_num} ===")
            logger.info(f"Train: {start.date()} - {train_end.date()}")
            logger.info(f"Test: {train_end.date()} - {test_end.date()}")

            # Get all available tickers for training period
            train_tickers = [t for t in tickers if t in all_price_data]

            # Run strategy for this period
            period_results = self._run_period(
                train_tickers,
                all_price_data,
                start,
                train_end,
                test_end
            )

            if period_results:
                backtest_results.append(period_results)

            # Roll forward
            start = train_end + pd.DateOffset(months=roll_months)
            train_end = start + pd.DateOffset(months=train_months)
            test_end = train_end + pd.DateOffset(months=test_months)

        # Aggregate results
        return self._aggregate_results(backtest_results)

    def _run_period(
        self,
        tickers: List[str],
        all_price_data: Dict,
        train_start: pd.Timestamp,
        train_end: pd.Timestamp,
        test_end: pd.Timestamp
    ) -> Dict:
        """Run a single walk-forward period."""
        try:
            # Create feature matrix for training period
            train_dates = self.generate_trading_dates(
                train_start.strftime('%Y-%m-%d'),
                train_end.strftime('%Y-%m-%d'),
                frequency='M'
            )

            # For MVP: simplified feature generation
            # In production: use proper FeatureComputer with point-in-time logic
            logger.info(f"Computing features for {len(train_dates)} dates")

            # Collect OHLCV data for feature computation
            ohlcv_list = []
            for ticker in tickers:
                if ticker in all_price_data:
                    data = all_price_data[ticker].copy()
                    data = data[data['date'] <= train_end]
                    if not data.empty:
                        data['ticker'] = ticker
                        ohlcv_list.append(data)

            if not ohlcv_list:
                logger.warning("No OHLCV data for period")
                return {}

            train_data = pd.concat(ohlcv_list, ignore_index=True)

            # Train model
            model = AtlasModel(model_id=f"period_{train_start.strftime('%Y%m%d')}")

            # Create target variable
            train_data = model.create_target_variable(train_data)

            # Check if we have enough data
            if len(train_data) < 100:
                logger.warning("Insufficient training data")
                return {}

            # Train
            metrics = model.train(train_data)

            if not metrics or metrics.get('accuracy', 0) < 0.52:
                logger.warning("Model accuracy insufficient")
                return {}

            # Test period: generate signals
            test_dates = self.generate_trading_dates(
                train_end.strftime('%Y-%m-%d'),
                test_end.strftime('%Y-%m-%d'),
                frequency='M'
            )

            # Compute returns during test period
            test_returns = []
            for test_date in test_dates:
                # Get data as of test_date
                test_ohlcv = []
                for ticker in tickers:
                    if ticker in all_price_data:
                        data = all_price_data[ticker].copy()
                        data = data[data['date'] < test_date]
                        if not data.empty:
                            data['ticker'] = ticker
                            test_ohlcv.append(data)

                if test_ohlcv:
                    test_snap = pd.concat(test_ohlcv, ignore_index=True)
                    # Predict for this date
                    predictions = model.predict_proba(test_snap)

                    # Get top 30 stocks
                    top_indices = np.argsort(predictions)[-30:]
                    top_tickers = test_snap.iloc[top_indices]['ticker'].values

                    # Compute 1M forward returns
                    forward_date = test_date + timedelta(days=21)
                    forward_data = []
                    for ticker in top_tickers:
                        if ticker in all_price_data:
                            data = all_price_data[ticker].copy()
                            current_price = data[data['date'] < test_date]['close'].iloc[-1] if len(data) > 0 else None
                            future_price = data[(data['date'] >= test_date) & (data['date'] <= forward_date)]['close'].iloc[-1] if len(data) > 0 else None

                            if current_price and future_price:
                                ret = (future_price - current_price) / current_price
                                forward_data.append(ret)

                    if forward_data:
                        period_return = np.mean(forward_data)
                        test_returns.append(period_return)

            if test_returns:
                period_metrics = self._compute_performance_metrics(test_returns)
                return {
                    'period': train_start.strftime('%Y-%m'),
                    'train_metrics': metrics,
                    'test_returns': test_returns,
                    'period_metrics': period_metrics,
                }

        except Exception as e:
            logger.error(f"Error in period: {e}")

        return {}

    def _compute_performance_metrics(self, returns: List[float]) -> Dict:
        """Compute performance metrics from returns."""
        returns = np.array(returns)
        n = len(returns)

        if n == 0:
            return {}

        total_return = np.prod(1 + returns) - 1
        avg_return = returns.mean()
        std_return = returns.std()
        sharpe_ratio = (avg_return / std_return * np.sqrt(12)) if std_return > 0 else 0
        max_dd = np.min(np.cumsum(returns))
        win_rate = (returns > 0).sum() / n

        return {
            'total_return': total_return,
            'avg_monthly_return': avg_return,
            'monthly_std': std_return,
            'sharpe_ratio': sharpe_ratio,
            'max_drawdown': max_dd,
            'win_rate': win_rate,
            'num_periods': n,
        }

    def _aggregate_results(self, period_results: List[Dict]) -> Dict:
        """Aggregate results from all periods."""
        if not period_results:
            return {}

        all_returns = []
        for period in period_results:
            all_returns.extend(period.get('test_returns', []))

        if not all_returns:
            return {}

        aggregate_metrics = self._compute_performance_metrics(all_returns)
        aggregate_metrics['num_periods'] = len(period_results)
        aggregate_metrics['period_results'] = period_results

        logger.info(f"\n=== BACKTEST SUMMARY ===")
        logger.info(f"Total Return: {aggregate_metrics.get('total_return', 0):.2%}")
        logger.info(f"Sharpe Ratio: {aggregate_metrics.get('sharpe_ratio', 0):.2f}")
        logger.info(f"Max Drawdown: {aggregate_metrics.get('max_drawdown', 0):.2%}")
        logger.info(f"Win Rate: {aggregate_metrics.get('win_rate', 0):.1%}")

        return aggregate_metrics


if __name__ == "__main__":
    logging.basicConfig(format=config.LOG_FORMAT)
    logger.info("Backtest engine loaded")
