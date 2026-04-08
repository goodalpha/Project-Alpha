"""
PROJECT ATLAS - System Orchestrator (v2)
Main entry point that coordinates all components

Improvements:
- Unified interface to all subsystems
- Health checks and diagnostics
- Graceful error handling and recovery
- Configuration validation
- Multiple execution modes
- Comprehensive logging
- Progress tracking
"""

import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict
import argparse

logger = logging.getLogger(__name__)
logger.setLevel("INFO")

try:
    import config_v2 as config
except ImportError:
    import config

from utils_v2 import format_currency, format_percentage, validate_configuration


class SystemHealthCheck:
    """Perform system health checks and diagnostics."""

    def __init__(self):
        self.checks: Dict[str, bool] = {}
        self.warnings: list = []
        self.errors: list = []

    def check_dependencies(self) -> bool:
        """Check all required dependencies are installed."""
        logger.info("Checking dependencies...")

        required = {
            'pandas': 'Data processing',
            'numpy': 'Numerical computing',
            'xgboost': 'ML model training',
            'selenium': 'Web scraping',
            'streamlit': 'Dashboard',
        }

        for package, purpose in required.items():
            try:
                __import__(package)
                self.checks[package] = True
                logger.debug(f"✅ {package}: {purpose}")
            except ImportError:
                self.checks[package] = False
                self.errors.append(f"Missing {package}: {purpose}")
                logger.error(f"❌ {package}: NOT INSTALLED")

        return all(self.checks.values())

    def check_directories(self) -> bool:
        """Check all required directories exist."""
        logger.info("Checking directories...")

        directories = {
            'data': config.DATA_DIR,
            'backtest': config.BACKTEST_DIR,
            'logs': config.LOGS_DIR,
            'models': config.MODELS_DIR,
        }

        for name, path in directories.items():
            try:
                path.mkdir(parents=True, exist_ok=True)
                self.checks[f'dir_{name}'] = True
                logger.debug(f"✅ {name}: {path}")
            except Exception as e:
                self.checks[f'dir_{name}'] = False
                self.errors.append(f"Cannot create {name}: {e}")
                logger.error(f"❌ {name}: {e}")

        return all(v for k, v in self.checks.items() if k.startswith('dir_'))

    def check_configuration(self) -> bool:
        """Check configuration is valid."""
        logger.info("Validating configuration...")

        if not validate_configuration():
            self.warnings.append("Configuration validation failed")
            return False

        self.checks['config'] = True
        logger.debug("✅ Configuration valid")
        return True

    def check_chromedriver(self) -> bool:
        """Check ChromeDriver is available."""
        logger.info("Checking ChromeDriver...")

        try:
            import shutil
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options

            # Try to find chromedriver
            chromedriver = shutil.which('chromedriver')
            if not chromedriver:
                self.warnings.append(
                    "ChromeDriver not found in PATH. "
                    "Install with: brew install chromedriver"
                )
                logger.warning("⚠️  ChromeDriver not in PATH")
                self.checks['chromedriver'] = False
                return False

            self.checks['chromedriver'] = True
            logger.debug("✅ ChromeDriver available")
            return True

        except Exception as e:
            self.warnings.append(f"ChromeDriver check failed: {e}")
            logger.warning(f"⚠️  ChromeDriver check: {e}")
            self.checks['chromedriver'] = False
            return False

    def run_all_checks(self) -> bool:
        """Run all health checks."""
        print("\n" + "="*70)
        print("ATLAS - System Health Check".center(70))
        print("="*70 + "\n")

        self.check_dependencies()
        self.check_directories()
        self.check_configuration()
        self.check_chromedriver()

        # Print results
        print("Check Results:")
        print("-" * 70)
        for check, passed in self.checks.items():
            status = "✅ PASS" if passed else "❌ FAIL"
            print(f"  {check:30s} {status}")

        if self.warnings:
            print("\nWarnings:")
            for warning in self.warnings:
                print(f"  ⚠️  {warning}")

        if self.errors:
            print("\nErrors:")
            for error in self.errors:
                print(f"  ❌ {error}")

        print()

        if self.errors:
            print("Status: ❌ HEALTH CHECK FAILED")
            return False
        elif self.warnings:
            print("Status: ⚠️  HEALTH CHECK PASSED (with warnings)")
            return True
        else:
            print("Status: ✅ HEALTH CHECK PASSED")
            return True


class AtlasSystemOrchestrator:
    """
    Main orchestrator for PROJECT ATLAS.
    Coordinates all subsystems and execution modes.
    """

    def __init__(self):
        self.config = config
        self.health_check = SystemHealthCheck()
        self.execution_mode = "manual"

    def validate_system(self) -> bool:
        """Validate system is ready to run."""
        logger.info("Validating system...")

        if not self.health_check.run_all_checks():
            return False

        return True

    def generate_signals(self) -> bool:
        """Generate trading signals for today."""
        print("\n" + "="*70)
        print("Generating Trading Signals".center(70))
        print("="*70 + "\n")

        try:
            from tradingview_backtest_signals_v2 import TradingViewHistoricalBacktest

            logger.info("Initializing signal generator...")

            backtest = TradingViewHistoricalBacktest(
                initial_capital=self.config.INITIAL_CAPITAL,
                position_size=self.config.POSITION_SIZE_PCT,
                slippage_pct=self.config.SLIPPAGE_PCT,
            )

            logger.info("Generating historical data...")
            historical = backtest.generate_historical_positions(
                num_days=30,
                num_stocks=30
            )

            logger.info("Generating signals...")
            signals = backtest.generate_trading_signals(
                historical,
                min_confidence=0.55
            )

            # Print top signals
            print(f"\nGenerated {len(signals)} signals:\n")
            print("Top 10 Signals for Today:")
            print("-" * 70)
            for i, sig in enumerate(signals[:10], 1):
                print(
                    f"{i:2d}. {sig['symbol']:6s} | "
                    f"Conf: {sig['confidence']:.3f} | "
                    f"Return: {sig['expected_return']:+.2f}% | "
                    f"Action: BUY"
                )

            print("\n✅ Signal generation complete")
            return True

        except Exception as e:
            logger.error(f"Signal generation failed: {e}", exc_info=True)
            print(f"❌ Signal generation failed: {e}")
            return False

    def run_backtest(self) -> bool:
        """Run historical backtest."""
        print("\n" + "="*70)
        print("Running Historical Backtest".center(70))
        print("="*70 + "\n")

        try:
            from tradingview_backtest_signals_v2 import TradingViewHistoricalBacktest

            logger.info("Initializing backtest...")

            backtest = TradingViewHistoricalBacktest(
                initial_capital=self.config.INITIAL_CAPITAL,
                position_size=self.config.POSITION_SIZE_PCT,
                slippage_pct=self.config.SLIPPAGE_PCT,
            )

            logger.info("Generating test data...")
            historical = backtest.generate_historical_positions(
                num_days=self.config.WALK_FORWARD_TEST_MONTHS * 21,  # ~21 days per month
                num_stocks=30
            )

            logger.info("Generating test signals...")
            signals = backtest.generate_trading_signals(historical, min_confidence=0.5)

            logger.info("Executing backtest...")
            results = backtest.backtest_execution(signals, historical)

            # Print results
            print("Backtest Results:")
            print("-" * 70)
            print(f"Initial Capital:        {format_currency(self.config.INITIAL_CAPITAL)}")
            print(f"Final Value:            {format_currency(results['final_value'])}")
            print(f"Total P&L:              {format_currency(results['total_pnl'])}")
            print(f"Total Return:           {format_percentage(results['total_return_pct']/100)}")
            print()
            print(f"Trades Executed:        {results['executed_signals']}")
            print(f"Winning Trades:         {results['winning_trades']}")
            print(f"Losing Trades:          {results['losing_trades']}")
            print(f"Win Rate:               {format_percentage(results['win_rate'])}")
            print()
            print(f"Avg Win:                {format_currency(results['avg_win'])}")
            print(f"Avg Loss:               {format_currency(results['avg_loss'])}")
            print(f"Profit Factor:          {results['profit_factor']:.2f}x")

            # Save results
            backtest.save_results(results, signals)

            print("\n✅ Backtest complete")
            return True

        except Exception as e:
            logger.error(f"Backtest failed: {e}", exc_info=True)
            print(f"❌ Backtest failed: {e}")
            return False

    def optimize_strategy(self) -> bool:
        """Run strategy optimization."""
        print("\n" + "="*70)
        print("Running Strategy Optimization".center(70))
        print("="*70 + "\n")

        try:
            from tradingview_strategy_optimizer_v2 import TradingViewStrategyOptimizer
            from tradingview_backtest_signals_v2 import TradingViewHistoricalBacktest

            logger.info("Generating historical data for optimization...")

            backtest = TradingViewHistoricalBacktest()
            historical = backtest.generate_historical_positions(
                num_days=60,
                num_stocks=30
            )

            logger.info("Running optimization sweep...")
            optimizer = TradingViewStrategyOptimizer()
            results = optimizer.run_optimization_sweep(historical)

            print("\nOptimization Results:")
            print("-" * 70)
            print("Threshold | Signals | Win Rate | Return")
            print("-" * 70)
            for result in results:
                print(
                    f"{result['confidence_threshold']:9.2f} | "
                    f"{result['signals_generated']:7d} | "
                    f"{result['win_rate']:8.1%} | "
                    f"{result['total_return_pct']:+8.2f}%"
                )

            print("\n✅ Strategy optimization complete")
            return True

        except Exception as e:
            logger.error(f"Strategy optimization failed: {e}", exc_info=True)
            print(f"❌ Optimization failed: {e}")
            return False

    def show_status(self) -> None:
        """Show system status."""
        print("\n" + "="*70)
        print("ATLAS - System Status".center(70))
        print("="*70 + "\n")

        print("Configuration:")
        print(f"  Capital:                {format_currency(self.config.INITIAL_CAPITAL)}")
        print(f"  Position Size:          {format_percentage(self.config.POSITION_SIZE_PCT)}")
        print(f"  Max Positions:          {self.config.MAX_POSITIONS}")
        print(f"  Max Daily Loss:         {format_percentage(self.config.MAX_DAILY_LOSS)}")
        print(f"  Max Drawdown:           {format_percentage(self.config.MAX_DRAWDOWN)}")
        print()

        print("Directories:")
        print(f"  Data:                   {self.config.DATA_DIR}")
        print(f"  Backtest:               {self.config.BACKTEST_DIR}")
        print(f"  Logs:                   {self.config.LOGS_DIR}")
        print(f"  Models:                 {self.config.MODELS_DIR}")
        print()

        print("Data Sources:")
        print(f"  Backtest Universe:      {len(self.config.BACKTEST_UNIVERSE)} stocks")
        print(f"  Feature Lookback:       {self.config.FEATURE_LOOKBACK_DAYS} days")
        print()

        print("✅ System ready")
        print()

    def show_help(self) -> None:
        """Show help message."""
        help_text = """
PROJECT ATLAS - Command Line Interface

Usage: python main_v2.py [COMMAND] [OPTIONS]

Commands:
  health              Run system health check
  status              Show system status
  signals             Generate trading signals for today
  backtest            Run historical backtest
  optimize            Run strategy optimization
  help                Show this help message

Examples:
  python main_v2.py health                # Check system is ready
  python main_v2.py signals               # Generate today's signals
  python main_v2.py backtest              # Run 6-month backtest
  python main_v2.py optimize              # Optimize strategy parameters

For more information, see:
  - CODE_IMPROVEMENTS_SUMMARY.md
  - TRADINGVIEW_BACKTEST_RESULTS.md
  - MAC_SETUP_GUIDE.md
  - SECURE_SETUP.md
"""
        print(help_text)


def main():
    """Main entry point."""
    # Setup logging
    logging.basicConfig(
        format=config.LOG_FORMAT,
        level=config.LOG_LEVEL,
        handlers=[
            logging.FileHandler(config.LOGS_DIR / "atlas_main.log"),
            logging.StreamHandler()
        ]
    )

    # Parse arguments
    parser = argparse.ArgumentParser(
        description="PROJECT ATLAS - Trading System Orchestrator",
        add_help=False
    )
    parser.add_argument(
        'command',
        nargs='?',
        default='help',
        help='Command to execute'
    )

    args = parser.parse_args()

    # Initialize orchestrator
    orchestrator = AtlasSystemOrchestrator()

    # Execute command
    if args.command == 'health':
        success = orchestrator.validate_system()
        sys.exit(0 if success else 1)

    elif args.command == 'status':
        orchestrator.show_status()
        sys.exit(0)

    elif args.command == 'signals':
        success = orchestrator.generate_signals()
        sys.exit(0 if success else 1)

    elif args.command == 'backtest':
        success = orchestrator.run_backtest()
        sys.exit(0 if success else 1)

    elif args.command == 'optimize':
        success = orchestrator.optimize_strategy()
        sys.exit(0 if success else 1)

    elif args.command in ('help', '-h', '--help'):
        orchestrator.show_help()
        sys.exit(0)

    else:
        print(f"Unknown command: {args.command}")
        orchestrator.show_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
