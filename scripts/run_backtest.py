#!/usr/bin/env python
"""
CLI script for backtesting cross-sectional strategies.

Runs the backtest engine on predictions, generates performance reports,
and saves tearsheets and metrics.

Usage:
    python scripts/run_backtest.py [--config CONFIG] [--predictions PATH] \\
        [--output-dir DIR]

Examples:
    python scripts/run_backtest.py
    python scripts/run_backtest.py --predictions data/processed/predictions.parquet
    python scripts/run_backtest.py --output-dir results/backtest_2024
"""

import argparse
import sys
from pathlib import Path
import json

import pandas as pd
import numpy as np
import yaml
from loguru import logger

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.backtest.engine import BacktestEngine
from src.ingestion.prices import load_prices
from src.ingestion.universe import load_universe
from src.ingestion.macro import load_macro
from src.regime.detector import detect_regime


def load_config(config_path: str) -> dict:
    """Load YAML configuration file."""
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
    logger.info(f"Loaded config from {config_path}")
    return config


def load_predictions(predictions_path: Path) -> pd.DataFrame:
    """Load predictions from parquet file."""
    df = pd.read_parquet(predictions_path)
    logger.info(f"Loaded predictions: {df.shape[0]} rows")
    logger.info(f"Date range: {df['date'].min()} to {df['date'].max()}")
    return df


def compute_performance_metrics(returns_series: pd.Series) -> dict:
    """Compute basic performance metrics from return series."""
    total_return = (1 + returns_series).prod() - 1
    annual_vol = returns_series.std() * np.sqrt(252)
    sharpe = returns_series.mean() / returns_series.std() * np.sqrt(252) if returns_series.std() > 0 else 0

    # Maximum drawdown
    cumulative = (1 + returns_series).cumprod()
    running_max = cumulative.expanding().max()
    drawdown = (cumulative - running_max) / running_max
    max_dd = drawdown.min()

    # Win rate
    win_rate = (returns_series > 0).sum() / len(returns_series)

    return {
        "total_return": total_return,
        "annual_vol": annual_vol,
        "sharpe_ratio": sharpe,
        "max_drawdown": max_dd,
        "win_rate": win_rate,
        "mean_return": returns_series.mean(),
        "std_return": returns_series.std(),
        "num_observations": len(returns_series),
    }


def main():
    """Main CLI entrypoint."""
    parser = argparse.ArgumentParser(
        description="Run backtest on strategy predictions",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/run_backtest.py
  python scripts/run_backtest.py --predictions custom_predictions.parquet
  python scripts/run_backtest.py --output-dir results/bt_v2
        """,
    )

    parser.add_argument(
        "--config",
        type=str,
        default="config/defaults.yaml",
        help="Path to configuration file (default: config/defaults.yaml)",
    )
    parser.add_argument(
        "--predictions",
        type=str,
        default=None,
        help="Path to predictions file (default: data/processed/predictions.parquet)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="results/backtest",
        help="Output directory for tearsheets and metrics (default: results/backtest)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    # Configure logging
    log_level = "DEBUG" if args.verbose else "INFO"
    logger.remove()
    logger.add(
        sys.stderr,
        level=log_level,
        format="<level>{level: <8}</level> | {name}:{function}:{line} - {message}",
    )

    try:
        # Load configuration
        config = load_config(args.config)

        # Determine paths
        processed_dir = Path(config.get("data", {}).get("processed_dir", "data/processed"))
        cache_dir = Path(config.get("data", {}).get("cache_dir", "data/raw"))
        output_dir = Path(args.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        if args.predictions:
            predictions_path = Path(args.predictions)
        else:
            predictions_path = processed_dir / "predictions.parquet"

        logger.info("=" * 80)
        logger.info("STEP 1: Loading Data")
        logger.info("=" * 80)

        try:
            # Load predictions
            if not predictions_path.exists():
                logger.error(f"Predictions file not found: {predictions_path}")
                logger.error("Run 'python scripts/train_models.py' first")
                return 1

            predictions_df = load_predictions(predictions_path)

            # Load prices
            prices_df = load_prices(cache_dir / "prices")
            if prices_df.empty:
                logger.error("No price data found")
                return 1

            # Convert to wide format
            prices_wide = prices_df.reset_index()
            prices_wide = prices_wide.pivot_table(
                index="date",
                columns="ticker",
                values="close",
            )
            logger.info(f"Loaded prices: {prices_wide.shape[0]} dates × {prices_wide.shape[1]} tickers")

            # Load universe
            universe_file = cache_dir / "universe.parquet"
            if universe_file.exists():
                universe_df = load_universe(universe_file)
                logger.info(f"Loaded universe: {len(universe_df)} tickers")
            else:
                logger.warning("Universe file not found, using price tickers")
                universe_df = pd.DataFrame(index=prices_wide.columns)

            # Load macro data
            macro_df = load_macro(cache_dir / "macro")
            if macro_df.empty:
                logger.warning("No macro data found")
            else:
                logger.info(f"Loaded macro data: {macro_df.shape}")

        except Exception as e:
            logger.error(f"Failed to load data: {e}")
            return 1

        logger.info("=" * 80)
        logger.info("STEP 2: Detecting Regime")
        logger.info("=" * 80)

        try:
            # Use VIX to detect regime (if available)
            if "VIX" in macro_df.columns or "VIXCLS" in macro_df.columns:
                vix_col = "VIX" if "VIX" in macro_df.columns else "VIXCLS"
                regime_labels = detect_regime(macro_df[[vix_col]], method="quantile", n_regimes=3)
                logger.info(f"Detected {regime_labels.nunique()} regimes")
            else:
                logger.info("VIX not available, using constant regime=0")
                regime_labels = pd.Series(0, index=prices_wide.index)

        except Exception as e:
            logger.warning(f"Failed to detect regime: {e}, using constant regime")
            regime_labels = pd.Series(0, index=prices_wide.index)

        logger.info("=" * 80)
        logger.info("STEP 3: Running Backtest")
        logger.info("=" * 80)

        try:
            engine = BacktestEngine(config)

            # Format predictions for backtest
            predictions_wide = predictions_df.pivot_table(
                index="date",
                columns="ticker",
                values="signal",
            )

            backtest_results = engine.run(
                predictions=predictions_df,
                prices=prices_wide,
                universe=universe_df,
                regime_labels=regime_labels,
            )

            logger.info("Backtest completed")

            if not backtest_results:
                logger.error("Backtest returned empty results")
                return 1

        except Exception as e:
            logger.error(f"Backtest failed: {e}")
            return 1

        logger.info("=" * 80)
        logger.info("STEP 4: Computing Performance Metrics")
        logger.info("=" * 80)

        try:
            # Extract portfolio returns
            portfolio_returns = backtest_results.get("portfolio_returns", pd.Series())

            if portfolio_returns.empty:
                logger.error("No portfolio returns in backtest results")
                return 1

            metrics = compute_performance_metrics(portfolio_returns)

            logger.info("\nPerformance Metrics:")
            logger.info(f"Total Return: {metrics['total_return']:.2%}")
            logger.info(f"Annual Volatility: {metrics['annual_vol']:.2%}")
            logger.info(f"Sharpe Ratio: {metrics['sharpe_ratio']:.4f}")
            logger.info(f"Max Drawdown: {metrics['max_drawdown']:.2%}")
            logger.info(f"Win Rate: {metrics['win_rate']:.2%}")
            logger.info(f"Observations: {metrics['num_observations']}")

        except Exception as e:
            logger.error(f"Failed to compute metrics: {e}")
            return 1

        logger.info("=" * 80)
        logger.info("STEP 5: Saving Results")
        logger.info("=" * 80)

        try:
            # Save metrics as JSON
            metrics_file = output_dir / "metrics.json"
            with open(metrics_file, "w") as f:
                # Convert numpy/pandas types to JSON-serializable
                json.dump(
                    {k: float(v) if isinstance(v, (np.number, np.floating)) else v
                     for k, v in metrics.items()},
                    f,
                    indent=2,
                )
            logger.info(f"Saved metrics to {metrics_file}")

            # Save portfolio returns
            returns_file = output_dir / "portfolio_returns.parquet"
            portfolio_returns.to_frame(name="return").to_parquet(returns_file)
            logger.info(f"Saved portfolio returns to {returns_file}")

            # Save positions if available
            if "positions" in backtest_results:
                positions_file = output_dir / "positions.parquet"
                backtest_results["positions"].to_parquet(positions_file)
                logger.info(f"Saved positions to {positions_file}")

            # Save turnover if available
            if "turnover" in backtest_results:
                turnover_file = output_dir / "turnover.parquet"
                backtest_results["turnover"].to_parquet(turnover_file)
                logger.info(f"Saved turnover to {turnover_file}")

            # Create simple tearsheet (text summary)
            tearsheet_file = output_dir / "tearsheet.txt"
            with open(tearsheet_file, "w") as f:
                f.write("=" * 80 + "\n")
                f.write("BACKTEST TEARSHEET\n")
                f.write("=" * 80 + "\n\n")

                f.write("Performance Metrics:\n")
                f.write("-" * 40 + "\n")
                for key, value in metrics.items():
                    if key in ["total_return", "annual_vol", "max_drawdown", "win_rate"]:
                        f.write(f"{key:.<30} {value:>10.2%}\n")
                    else:
                        f.write(f"{key:.<30} {value:>10.4f}\n")

                f.write("\n")
                f.write("Backtest Details:\n")
                f.write("-" * 40 + "\n")
                f.write(f"Date range: {predictions_df['date'].min()} to {predictions_df['date'].max()}\n")
                f.write(f"Predictions: {len(predictions_df)} records\n")
                f.write(f"Unique dates: {predictions_df['date'].nunique()}\n")
                f.write(f"Unique tickers: {predictions_df['ticker'].nunique()}\n")

                if "total_cost" in backtest_results:
                    f.write(f"Total transaction costs: {backtest_results['total_cost']:.4f}\n")

            logger.info(f"Saved tearsheet to {tearsheet_file}")

        except Exception as e:
            logger.error(f"Failed to save results: {e}")
            return 1

        logger.info("=" * 80)
        logger.info("BACKTEST SUMMARY")
        logger.info("=" * 80)
        logger.info(f"Total Return: {metrics['total_return']:.2%}")
        logger.info(f"Sharpe Ratio: {metrics['sharpe_ratio']:.4f}")
        logger.info(f"Max Drawdown: {metrics['max_drawdown']:.2%}")
        logger.info(f"Output directory: {output_dir.absolute()}")

        logger.info("=" * 80)
        logger.info("SUCCESS: Backtest completed")
        logger.info("=" * 80)

        return 0

    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
