#!/usr/bin/env python
"""
CLI script to download all raw data for the quantitative trading framework.

Orchestrates downloading prices, macro data, and fundamentals with
caching and error handling.

Usage:
    python scripts/download_data.py [--config CONFIG] [--start-date DATE] [--end-date DATE] \\
        [--universe {sp500,nasdaq100}] [--skip-fundamentals]

Examples:
    python scripts/download_data.py --start-date 2020-01-01 --end-date 2024-12-31
    python scripts/download_data.py --universe nasdaq100 --skip-fundamentals
"""

import argparse
import sys
from pathlib import Path
from datetime import datetime, timedelta

import pandas as pd
import yaml
from loguru import logger
from tqdm import tqdm

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.ingestion.prices import download_prices, load_prices
from src.ingestion.macro import download_macro, DEFAULT_MACRO_SERIES
from src.ingestion.fundamentals import download_fundamentals
from src.ingestion.universe import build_universe, load_universe


def load_config(config_path: str) -> dict:
    """Load YAML configuration file."""
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
    logger.info(f"Loaded config from {config_path}")
    return config


def parse_date(date_str: str) -> pd.Timestamp:
    """Parse date string to pandas Timestamp."""
    try:
        return pd.Timestamp(date_str)
    except Exception as e:
        logger.error(f"Failed to parse date '{date_str}': {e}")
        raise


def main():
    """Main CLI entrypoint."""
    parser = argparse.ArgumentParser(
        description="Download raw data for quantitative trading framework",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Download 5 years of data
  python scripts/download_data.py --start-date 2020-01-01

  # Download S&P 500 data without fundamentals
  python scripts/download_data.py --universe sp500 --skip-fundamentals

  # Use custom config
  python scripts/download_data.py --config config/custom.yaml
        """,
    )

    parser.add_argument(
        "--config",
        type=str,
        default="config/defaults.yaml",
        help="Path to configuration file (default: config/defaults.yaml)",
    )
    parser.add_argument(
        "--start-date",
        type=str,
        help="Start date (YYYY-MM-DD). Default: 5 years ago",
    )
    parser.add_argument(
        "--end-date",
        type=str,
        help="End date (YYYY-MM-DD). Default: today",
    )
    parser.add_argument(
        "--universe",
        type=str,
        choices=["sp500", "nasdaq100"],
        help="Universe source. Overrides config if provided.",
    )
    parser.add_argument(
        "--skip-fundamentals",
        action="store_true",
        help="Skip downloading fundamentals (slow, optional)",
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

        # Parse dates
        if args.end_date:
            end_date = parse_date(args.end_date)
        else:
            end_date = pd.Timestamp.today()

        if args.start_date:
            start_date = parse_date(args.start_date)
        else:
            start_date = end_date - timedelta(days=365 * 5)  # 5 years ago

        logger.info(f"Download period: {start_date.date()} to {end_date.date()}")

        # Override universe if provided
        if args.universe:
            config["universe"]["source"] = args.universe
            logger.info(f"Overriding universe source to: {args.universe}")

        # Create cache directory
        cache_dir = Path(config.get("data", {}).get("cache_dir", "data/raw"))
        cache_dir.mkdir(parents=True, exist_ok=True)

        logger.info("=" * 80)
        logger.info("STEP 1: Building Universe")
        logger.info("=" * 80)

        try:
            universe_df = build_universe(config)
            tickers = universe_df.index.tolist()
            logger.info(f"Built universe with {len(tickers)} tickers")
        except Exception as e:
            logger.error(f"Failed to build universe: {e}")
            return 1

        # Add SPY to tickers for benchmark
        if "SPY" not in tickers:
            tickers = tickers + ["SPY"]
            logger.info("Added SPY to universe for benchmark")

        logger.info("=" * 80)
        logger.info("STEP 2: Downloading Prices")
        logger.info("=" * 80)

        try:
            prices_df = download_prices(
                tickers=tickers,
                start=start_date,
                end=end_date,
                cache_dir=cache_dir / "prices",
            )

            if prices_df.empty:
                logger.error("No price data downloaded")
                return 1

            n_tickers = len(prices_df.index.get_level_values("ticker").unique())
            n_dates = len(prices_df.index.get_level_values("date").unique())
            logger.info(
                f"Downloaded prices: {n_tickers} tickers × {n_dates} dates "
                f"= {len(prices_df)} records"
            )
            logger.info(f"Date range: {prices_df.index.get_level_values('date').min()} "
                       f"to {prices_df.index.get_level_values('date').max()}")
            logger.info(f"File size: {prices_df.memory_usage(deep=True).sum() / 1e6:.1f} MB")

        except Exception as e:
            logger.error(f"Failed to download prices: {e}")
            return 1

        logger.info("=" * 80)
        logger.info("STEP 3: Downloading Macro Data")
        logger.info("=" * 80)

        try:
            # Get macro series from config
            macro_series = {}
            fred_config = config.get("features", {}).get("macro", {}).get("fred_series", [])
            if fred_config:
                # fred_config is list of dicts with 'id' and 'name'
                for item in fred_config:
                    macro_series[item["id"]] = item.get("name", item["id"])
            else:
                # Fall back to defaults
                macro_series = DEFAULT_MACRO_SERIES

            logger.info(f"Downloading {len(macro_series)} FRED series")
            macro_df = download_macro(
                series_ids=macro_series,
                start=start_date,
                end=end_date,
                cache_dir=cache_dir / "macro",
            )

            if macro_df.empty:
                logger.warning("No macro data downloaded")
            else:
                logger.info(
                    f"Downloaded macro data: {len(macro_df.columns)} series × {len(macro_df)} dates"
                )
                logger.info(f"Macro date range: {macro_df.index.min()} to {macro_df.index.max()}")
                logger.info(f"File size: {macro_df.memory_usage(deep=True).sum() / 1e6:.1f} MB")

        except Exception as e:
            logger.error(f"Failed to download macro data: {e}")
            return 1

        # Download fundamentals (optional)
        if not args.skip_fundamentals:
            logger.info("=" * 80)
            logger.info("STEP 4: Downloading Fundamentals (slow...)")
            logger.info("=" * 80)

            try:
                logger.warning("Fundamentals download is slow. Use --skip-fundamentals to skip.")
                fundamental_df = download_fundamentals(
                    tickers=tickers,
                    start=start_date,
                    end=end_date,
                    cache_dir=cache_dir / "fundamentals",
                )

                if fundamental_df.empty:
                    logger.warning("No fundamental data downloaded")
                else:
                    logger.info(f"Downloaded fundamentals: {len(fundamental_df)} records")
                    logger.info(f"File size: {fundamental_df.memory_usage(deep=True).sum() / 1e6:.1f} MB")

            except Exception as e:
                logger.error(f"Failed to download fundamentals: {e}")
                # Don't fail the entire pipeline
        else:
            logger.info("Skipping fundamentals download (--skip-fundamentals)")

        logger.info("=" * 80)
        logger.info("DOWNLOAD SUMMARY")
        logger.info("=" * 80)
        logger.info(f"Universe: {len(tickers)} tickers (including SPY)")
        logger.info(f"Date range: {start_date.date()} to {end_date.date()}")
        logger.info(f"Cache directory: {cache_dir.absolute()}")
        logger.info(f"Total cache size: {sum(f.stat().st_size for f in cache_dir.rglob('*') if f.is_file()) / 1e9:.2f} GB")

        logger.info("=" * 80)
        logger.info("SUCCESS: All data downloaded")
        logger.info("=" * 80)

        return 0

    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
