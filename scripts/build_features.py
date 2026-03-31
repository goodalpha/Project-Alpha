#!/usr/bin/env python
"""
CLI script to build feature matrix from raw data.

Loads downloaded prices, macro data, and fundamentals, then runs the
complete feature engineering pipeline.

Usage:
    python scripts/build_features.py [--config CONFIG]

Examples:
    python scripts/build_features.py
    python scripts/build_features.py --config config/custom.yaml
"""

import argparse
import sys
from pathlib import Path

import pandas as pd
import yaml
from loguru import logger

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.ingestion.prices import load_prices, compute_returns
from src.ingestion.macro import load_macro
from src.ingestion.fundamentals import load_fundamentals
from src.ingestion.universe import load_universe
from src.features.pipeline import build_feature_matrix
from src.targets.targets import compute_targets


def load_config(config_path: str) -> dict:
    """Load YAML configuration file."""
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
    logger.info(f"Loaded config from {config_path}")
    return config


def main():
    """Main CLI entrypoint."""
    parser = argparse.ArgumentParser(
        description="Build feature matrix for quantitative trading framework",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/build_features.py
  python scripts/build_features.py --config config/custom.yaml
        """,
    )

    parser.add_argument(
        "--config",
        type=str,
        default="config/defaults.yaml",
        help="Path to configuration file (default: config/defaults.yaml)",
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

        cache_dir = Path(config.get("data", {}).get("cache_dir", "data/raw"))
        processed_dir = Path(config.get("data", {}).get("processed_dir", "data/processed"))
        processed_dir.mkdir(parents=True, exist_ok=True)

        logger.info("=" * 80)
        logger.info("STEP 1: Loading Universe")
        logger.info("=" * 80)

        try:
            universe_file = cache_dir / "universe.parquet"
            if not universe_file.exists():
                logger.error(f"Universe file not found: {universe_file}")
                logger.error("Run 'python scripts/download_data.py' first")
                return 1

            universe_df = load_universe(universe_file)
            logger.info(f"Loaded universe: {len(universe_df)} tickers")

        except Exception as e:
            logger.error(f"Failed to load universe: {e}")
            return 1

        logger.info("=" * 80)
        logger.info("STEP 2: Loading Prices")
        logger.info("=" * 80)

        try:
            prices_df = load_prices(cache_dir / "prices")

            if prices_df.empty:
                logger.error("No price data found")
                return 1

            # Convert to wide format for feature engineering
            prices_wide = prices_df.reset_index()
            prices_wide = prices_wide.pivot_table(
                index="date",
                columns="ticker",
                values="close",
            )

            logger.info(f"Loaded prices: {prices_wide.shape[0]} dates × {prices_wide.shape[1]} tickers")
            logger.info(f"Date range: {prices_wide.index.min()} to {prices_wide.index.max()}")

            # Build prices_dict for feature pipeline
            prices_dict = {
                "close": prices_wide,
                "volume": prices_df.pivot_table(
                    index="date", columns="ticker", values="volume"
                ),
                "adj_close": prices_wide,  # Assume no adjustment for now
                "open": prices_wide,  # Placeholder
                "high": prices_wide,  # Placeholder
                "low": prices_wide,   # Placeholder
            }

        except Exception as e:
            logger.error(f"Failed to load prices: {e}")
            return 1

        logger.info("=" * 80)
        logger.info("STEP 3: Loading Macro Data")
        logger.info("=" * 80)

        try:
            macro_df = load_macro(cache_dir / "macro")

            if macro_df.empty:
                logger.warning("No macro data found, proceeding with empty macro data")
                macro_df = pd.DataFrame(index=prices_dict["close"].index)
            else:
                logger.info(f"Loaded macro data: {macro_df.shape[0]} dates × {macro_df.shape[1]} series")

        except Exception as e:
            logger.error(f"Failed to load macro data: {e}")
            macro_df = pd.DataFrame(index=prices_dict["close"].index)

        logger.info("=" * 80)
        logger.info("STEP 4: Loading Fundamentals")
        logger.info("=" * 80)

        try:
            fundamental_df = load_fundamentals(cache_dir / "fundamentals")

            if fundamental_df.empty:
                logger.warning("No fundamental data found")
                fundamental_df = pd.DataFrame()
            else:
                logger.info(f"Loaded fundamentals: {len(fundamental_df)} records")

        except Exception as e:
            logger.error(f"Failed to load fundamentals: {e}")
            fundamental_df = pd.DataFrame()

        logger.info("=" * 80)
        logger.info("STEP 5: Building Feature Matrix")
        logger.info("=" * 80)

        try:
            feature_matrix = build_feature_matrix(
                prices_dict=prices_dict,
                macro_df=macro_df,
                fundamental_panel=fundamental_df,
                universe_df=universe_df,
                config=config,
            )

            if feature_matrix.empty:
                logger.error("Feature matrix is empty")
                return 1

            logger.info(f"Built feature matrix: {feature_matrix.shape[0]} rows × {feature_matrix.shape[1]} columns")
            logger.info(f"Date range: {feature_matrix.index.get_level_values('date').min()} to "
                       f"{feature_matrix.index.get_level_values('date').max()}")

            # List feature columns
            feature_cols = [col for col in feature_matrix.columns if col not in ["date", "ticker", "sector"]]
            logger.info(f"Features ({len(feature_cols)}): {', '.join(feature_cols[:10])}...")

            # Save feature matrix
            features_file = processed_dir / "features.parquet"
            feature_matrix.to_parquet(features_file)
            logger.info(f"Saved features to {features_file}")

        except Exception as e:
            logger.error(f"Failed to build feature matrix: {e}")
            return 1

        logger.info("=" * 80)
        logger.info("STEP 6: Computing Targets")
        logger.info("=" * 80)

        try:
            targets_dict = compute_targets(prices_dict, config)

            if not targets_dict:
                logger.error("No targets computed")
                return 1

            logger.info(f"Computed {len(targets_dict)} target(s):")
            for target_name in targets_dict.keys():
                logger.info(f"  - {target_name}")

            # Save targets
            for target_name, target_df in targets_dict.items():
                target_file = processed_dir / f"target_{target_name}.parquet"
                target_df.to_parquet(target_file)

            logger.info(f"Saved targets to {processed_dir}")

        except Exception as e:
            logger.error(f"Failed to compute targets: {e}")
            return 1

        logger.info("=" * 80)
        logger.info("BUILD SUMMARY")
        logger.info("=" * 80)
        logger.info(f"Feature matrix: {feature_matrix.shape[0]} rows × {feature_matrix.shape[1]} columns")
        logger.info(f"Date range: {feature_matrix.index.get_level_values('date').min()} to "
                   f"{feature_matrix.index.get_level_values('date').max()}")
        logger.info(f"Number of tickers: {feature_matrix.index.get_level_values('ticker').nunique()}")
        logger.info(f"Output directory: {processed_dir.absolute()}")

        logger.info("=" * 80)
        logger.info("SUCCESS: Feature matrix built")
        logger.info("=" * 80)

        return 0

    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
