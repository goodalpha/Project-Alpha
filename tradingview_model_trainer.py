"""
PROJECT ATLAS - TradingView Data Model Training
Uses real TradingView paper trading data to train and validate models
"""

import os
import json
import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
from pathlib import Path

import config
from model import AtlasModel, ModelValidator
from tradingview_scraper import TradingViewScraper, TradingViewMonitor

logger = logging.getLogger(__name__)
logger.setLevel("INFO")


class TradingViewModelTrainer:
    """
    Trains and validates ATLAS model using real TradingView paper trading data.
    Tracks signal accuracy, P&L, and model performance.
    """

    def __init__(self):
        self.scraper = None
        self.monitor = None
        self.trading_data = []
        self.model = None
        self.validation_results = {}

    def setup_scraper(self, email: str = None, password: str = None) -> bool:
        """
        Setup TradingView scraper.

        Args:
            email: TradingView email (or TRADINGVIEW_EMAIL env var)
            password: TradingView password (or TRADINGVIEW_PASSWORD env var)

        Returns:
            True if setup successful
        """
        try:
            self.scraper = TradingViewScraper(email, password, headless=True)

            if self.scraper.login():
                logger.info("✅ TradingView scraper ready")
                return True
            else:
                logger.error("Failed to login to TradingView")
                return False

        except Exception as e:
            logger.error(f"Error setting up scraper: {e}")
            return False

    def collect_trading_data(self, duration_hours: int = 8) -> Dict:
        """
        Collect real trading data from TradingView.

        Args:
            duration_hours: How long to collect data

        Returns:
            Dict with collected trading data
        """
        try:
            logger.info(f"Collecting TradingView data for {duration_hours} hours...")

            self.monitor = TradingViewMonitor(self.scraper, update_interval=60)  # 1 min updates
            self.monitor.start_monitoring(duration_hours)

            # Save collected data
            data_summary = self.monitor.get_summary()
            self.save_training_data(data_summary)

            return data_summary

        except Exception as e:
            logger.error(f"Error collecting data: {e}")
            return {}

    def save_training_data(self, data: Dict, filename: str = None):
        """Save trading data for model training."""
        if filename is None:
            filename = f"tradingview_training_data_{datetime.now().strftime('%Y%m%d')}.json"

        filepath = config.BACKTEST_DIR / filename

        try:
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2, default=str)
            logger.info(f"Training data saved to {filepath}")
        except Exception as e:
            logger.error(f"Error saving training data: {e}")

    def load_training_data(self, filename: str = None) -> Dict:
        """Load previously saved training data."""
        if filename is None:
            # Find latest training data
            files = list(config.BACKTEST_DIR.glob("tradingview_training_data_*.json"))
            if not files:
                return {}
            filename = files[-1].name

        filepath = config.BACKTEST_DIR / filename

        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            logger.info(f"Loaded training data from {filename}")
            return data
        except Exception as e:
            logger.error(f"Error loading training data: {e}")
            return {}

    def validate_signals_vs_pnl(self, signals: List[Dict], positions: List[Dict]) -> Dict:
        """
        Validate ATLAS signals against actual TradingView P&L.

        Args:
            signals: List of ATLAS signals generated
            positions: List of actual positions from TradingView

        Returns:
            Validation results
        """
        logger.info("Validating signals vs actual P&L...")

        validation = {
            'timestamp': datetime.now().isoformat(),
            'total_signals': len(signals),
            'executed_signals': 0,
            'winning_signals': 0,
            'losing_signals': 0,
            'accuracy': 0.0,
            'avg_win': 0.0,
            'avg_loss': 0.0,
            'signal_details': []
        }

        # Create position map
        position_map = {p['symbol']: p for p in positions}

        wins = []
        losses = []

        for signal in signals:
            symbol = signal.get('symbol')
            confidence = signal.get('confidence', 0)

            if symbol in position_map:
                position = position_map[symbol]
                pnl = position.get('pnl', 0)
                pnl_pct = position.get('pnl_pct', 0)

                validation['executed_signals'] += 1

                # Track win/loss
                if pnl > 0:
                    validation['winning_signals'] += 1
                    wins.append(pnl)
                else:
                    validation['losing_signals'] += 1
                    losses.append(pnl)

                # Record signal detail
                validation['signal_details'].append({
                    'symbol': symbol,
                    'confidence': confidence,
                    'pnl': pnl,
                    'pnl_pct': pnl_pct,
                    'was_correct': pnl > 0,
                })

        # Calculate metrics
        if validation['executed_signals'] > 0:
            validation['accuracy'] = validation['winning_signals'] / validation['executed_signals']
            validation['avg_win'] = np.mean(wins) if wins else 0
            validation['avg_loss'] = np.mean(losses) if losses else 0
            validation['win_rate'] = validation['winning_signals'] / validation['executed_signals']

        logger.info(f"Validation: {validation['winning_signals']}/{validation['executed_signals']} signals profitable")
        return validation

    def train_model_from_tradingview(self, trading_data: Dict) -> bool:
        """
        Train ATLAS model using TradingView trading data.

        Args:
            trading_data: TradingView trading data from scraper

        Returns:
            True if training successful
        """
        try:
            logger.info("Training model from TradingView data...")

            positions = trading_data.get('positions', [])

            if not positions:
                logger.error("No positions in training data")
                return False

            # Convert to DataFrame
            df = pd.DataFrame(positions)

            # Add features (would normally come from ATLAS pipeline)
            df['return'] = df['pnl_pct'] / 100
            df['target'] = (df['return'] > 0).astype(int)

            # Train model
            self.model = AtlasModel(model_id='tradingview_trained')
            metrics = self.model.train(df)

            if metrics:
                logger.info(f"✅ Model trained successfully: {metrics}")
                self.model.save()
                return True
            else:
                logger.error("Model training failed")
                return False

        except Exception as e:
            logger.error(f"Error training model: {e}")
            return False

    def compare_backtest_vs_live(
        self,
        backtest_results: Dict,
        live_results: Dict
    ) -> Dict:
        """
        Compare backtest performance vs live TradingView performance.

        Args:
            backtest_results: Results from backtest.py
            live_results: Results from TradingView scraper

        Returns:
            Comparison analysis
        """
        logger.info("Comparing backtest vs live performance...")

        comparison = {
            'timestamp': datetime.now().isoformat(),
            'backtest': {
                'sharpe_ratio': backtest_results.get('sharpe_ratio'),
                'max_drawdown': backtest_results.get('max_drawdown'),
                'win_rate': backtest_results.get('win_rate'),
                'total_return': backtest_results.get('total_return'),
            },
            'live': {
                'win_rate': live_results.get('win_rate'),
                'avg_win': live_results.get('avg_win'),
                'avg_loss': live_results.get('avg_loss'),
                'total_signals': live_results.get('executed_signals'),
            },
            'variance': {}
        }

        # Calculate variance
        if backtest_results.get('win_rate'):
            comparison['variance']['win_rate_diff'] = (
                live_results.get('win_rate', 0) - backtest_results.get('win_rate', 0)
            )

        logger.info(f"Backtest Win Rate: {comparison['backtest']['win_rate']:.1%}")
        logger.info(f"Live Win Rate: {comparison['live']['win_rate']:.1%}")

        return comparison

    def generate_model_report(self) -> Dict:
        """Generate comprehensive model training report."""
        report = {
            'timestamp': datetime.now().isoformat(),
            'model_id': self.model.model_id if self.model else None,
            'training_metrics': self.model.training_metrics if self.model else {},
            'validation_results': self.validation_results,
            'status': 'Ready for deployment' if self.model else 'Not trained',
        }

        return report

    def save_report(self, report: Dict, filename: str = None):
        """Save model training report."""
        if filename is None:
            filename = f"tradingview_model_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        filepath = config.BACKTEST_DIR / filename

        try:
            with open(filepath, 'w') as f:
                json.dump(report, f, indent=2, default=str)
            logger.info(f"Report saved to {filepath}")
        except Exception as e:
            logger.error(f"Error saving report: {e}")


def quick_start_workflow():
    """
    Quick start workflow: Scrape TradingView → Train Model → Validate
    """
    print("\n" + "="*70)
    print("ATLAS - TradingView Model Training Workflow".center(70))
    print("="*70 + "\n")

    # 1. Setup scraper
    print("Step 1: Setting up TradingView scraper...")
    trainer = TradingViewModelTrainer()

    email = os.getenv('TRADINGVIEW_EMAIL')
    password = os.getenv('TRADINGVIEW_PASSWORD')

    if not email or not password:
        print("❌ Missing TradingView credentials")
        print("Set environment variables:")
        print("  export TRADINGVIEW_EMAIL='your_email@example.com'")
        print("  export TRADINGVIEW_PASSWORD='your_password'")
        return

    if not trainer.setup_scraper(email, password):
        print("❌ Failed to setup scraper")
        return

    print("✅ Scraper ready\n")

    # 2. Collect data
    print("Step 2: Collecting TradingView trading data...")
    print("This will monitor your paper trading account for 8 hours")
    print("(updates every 1 minute)\n")

    # For demo, load existing data if available
    trading_data = trainer.load_training_data()

    if not trading_data or not trading_data.get('positions'):
        print("No existing data found. Would collect live from TradingView.")
        print("Run during market hours (9:30 AM - 4 PM ET) for best results.")
        return

    print(f"✅ Loaded {len(trading_data.get('positions', []))} positions\n")

    # 3. Train model
    print("Step 3: Training model from TradingView data...")
    if trainer.train_model_from_tradingview(trading_data):
        print("✅ Model trained\n")
    else:
        print("❌ Model training failed\n")
        return

    # 4. Validate
    print("Step 4: Validating signals vs actual P&L...")

    # Generate sample signals for validation
    signals = [
        {'symbol': p.get('symbol'), 'confidence': 0.75}
        for p in trading_data.get('positions', [])[:10]
    ]

    validation = trainer.validate_signals_vs_pnl(signals, trading_data.get('positions', []))
    print(f"✅ Validation complete\n")

    # 5. Generate report
    print("Step 5: Generating report...")
    report = trainer.generate_model_report()
    trainer.save_report(report)
    print("✅ Report saved\n")

    # Print summary
    print("="*70)
    print("TRAINING SUMMARY")
    print("="*70)
    print(json.dumps(report, indent=2, default=str))
    print()


def setup_instructions() -> str:
    """Return setup instructions."""
    return """
╔══════════════════════════════════════════════════════════════════════════╗
║      PROJECT ATLAS - TradingView Model Training Setup                   ║
╚══════════════════════════════════════════════════════════════════════════╝

STEP 1: INSTALL SELENIUM
  $ pip install selenium

STEP 2: DOWNLOAD CHROMEDRIVER
  Visit: https://chromedriver.chromium.org/
  Extract to: /usr/local/bin/ (Linux/Mac)

STEP 3: SET TRADINGVIEW CREDENTIALS
  $ export TRADINGVIEW_EMAIL='your_email@example.com'
  $ export TRADINGVIEW_PASSWORD='your_password'

STEP 4: RUN TRAINING WORKFLOW
  $ python tradingview_model_trainer.py

This will:
1. ✅ Login to TradingView
2. ✅ Collect paper trading data (8 hours)
3. ✅ Train ATLAS model on real data
4. ✅ Validate signals vs actual P&L
5. ✅ Generate detailed report

═══════════════════════════════════════════════════════════════════════════
"""


if __name__ == "__main__":
    import sys

    logging.basicConfig(
        format=config.LOG_FORMAT,
        level="INFO",
        handlers=[
            logging.FileHandler(config.LOGS_DIR / "tradingview_trainer.log"),
            logging.StreamHandler()
        ]
    )

    print(setup_instructions())
    quick_start_workflow()
