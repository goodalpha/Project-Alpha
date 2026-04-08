"""
PROJECT ATLAS - TradingView Model Trainer (Improved v2)
Train model on real TradingView trading data with validation and risk controls

Improvements:
- Comprehensive error handling and data validation
- Type hints throughout
- Better logging with detailed context
- Input validation for all parameters
- Realistic performance metrics (IC, Sharpe, max drawdown)
- Model persistence and versioning
- Data quality checks before training
- Better separation of concerns
"""

import json
import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import pickle

logger = logging.getLogger(__name__)
logger.setLevel("INFO")

import config
from model import AtlasModel


class DataValidationError(Exception):
    """Raised when data validation fails."""
    pass


class TrainingError(Exception):
    """Raised when model training fails."""
    pass


class TradingViewModelTrainer:
    """
    Train ATLAS model on real TradingView trading data.
    Validates signals against actual P&L, trains improved models.
    """

    # Configuration constants
    MIN_SAMPLES_REQUIRED = 10
    MIN_SIGNAL_CONFIDENCE = 0.5
    MAX_LOOKBACK_DAYS = 90
    MIN_POSITION_SIZE = 100
    MAX_POSITION_SIZE = 100_000_000

    def __init__(self, model: Optional[AtlasModel] = None):
        """
        Initialize model trainer.

        Args:
            model: AtlasModel instance (creates new if None)

        Raises:
            ValueError: If model type is invalid
        """
        self.model = model or AtlasModel(model_id=f"trained_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        self.training_data: List[Dict] = []
        self.validation_results: Dict = {}
        self.model_metrics: Dict = {}

        logger.info(f"Model trainer initialized (model_id={self.model.model_id})")

    def load_trading_data(self, filepath: Path) -> List[Dict]:
        """
        Load trading data from file with validation.

        Args:
            filepath: Path to JSON or CSV trading data file

        Returns:
            List of validated trade records

        Raises:
            DataValidationError: If data is invalid or missing
            FileNotFoundError: If file not found
        """
        if not filepath.exists():
            raise FileNotFoundError(f"Data file not found: {filepath}")

        try:
            logger.info(f"Loading trading data from {filepath}...")

            # Load based on file type
            if filepath.suffix == '.json':
                with open(filepath, 'r') as f:
                    data = json.load(f)
                records = data if isinstance(data, list) else data.get('trades', [])
            elif filepath.suffix == '.csv':
                df = pd.read_csv(filepath)
                records = df.to_dict('records')
            else:
                raise ValueError(f"Unsupported file type: {filepath.suffix}")

            if not records:
                raise DataValidationError("No records found in data file")

            # Validate records
            validated = []
            for i, record in enumerate(records):
                try:
                    validated_record = self._validate_trade_record(record)
                    validated.append(validated_record)
                except DataValidationError as e:
                    logger.warning(f"Skipping record {i}: {e}")
                    continue

            if not validated:
                raise DataValidationError("No valid records after validation")

            self.training_data = validated
            logger.info(f"✅ Loaded {len(validated)} validated trade records")
            return validated

        except json.JSONDecodeError as e:
            raise DataValidationError(f"Invalid JSON format: {e}") from e
        except pd.errors.ParserError as e:
            raise DataValidationError(f"Invalid CSV format: {e}") from e
        except Exception as e:
            logger.error(f"Error loading data: {e}")
            raise

    def _validate_trade_record(self, record: Dict) -> Dict:
        """
        Validate individual trade record.

        Args:
            record: Trade record to validate

        Returns:
            Validated record with normalized fields

        Raises:
            DataValidationError: If record is invalid
        """
        required_fields = ['symbol', 'entry_price', 'exit_price', 'quantity', 'pnl']

        # Check required fields
        missing = [f for f in required_fields if f not in record]
        if missing:
            raise DataValidationError(f"Missing required fields: {missing}")

        symbol = str(record.get('symbol', '')).upper().strip()
        if not symbol or not 1 <= len(symbol) <= 5:
            raise DataValidationError(f"Invalid symbol: {symbol}")

        try:
            entry_price = float(record['entry_price'])
            exit_price = float(record['exit_price'])
            quantity = int(float(record['quantity']))
            pnl = float(record['pnl'])

            if entry_price <= 0 or exit_price <= 0:
                raise ValueError("Prices must be positive")

            if quantity <= 0:
                raise ValueError("Quantity must be positive")

            # Check position size limits
            position_value = quantity * entry_price
            if not (self.MIN_POSITION_SIZE <= position_value <= self.MAX_POSITION_SIZE):
                raise ValueError(f"Position size out of range: ${position_value:,.0f}")

            # Validate P&L calculation
            expected_pnl = quantity * (exit_price - entry_price)
            pnl_diff = abs(pnl - expected_pnl)
            if pnl_diff > 1:  # Allow $1 rounding difference
                logger.warning(
                    f"P&L mismatch for {symbol}: "
                    f"calculated=${expected_pnl:,.2f}, provided=${pnl:,.2f}"
                )

        except (ValueError, TypeError) as e:
            raise DataValidationError(f"Invalid numeric values: {e}") from e

        return {
            'symbol': symbol,
            'entry_price': float(entry_price),
            'exit_price': float(exit_price),
            'quantity': int(quantity),
            'pnl': float(pnl),
            'entry_date': record.get('entry_date', datetime.now().isoformat()),
            'exit_date': record.get('exit_date', datetime.now().isoformat()),
            'signal_confidence': float(record.get('signal_confidence', 0.5)),
            'notes': str(record.get('notes', '')),
        }

    def validate_signals(self, signals: List[Dict]) -> Dict:
        """
        Validate signal accuracy against actual P&L.

        Args:
            signals: List of trading signals with confidence scores

        Returns:
            Dict with signal validation metrics
        """
        if not signals or not self.training_data:
            logger.warning("No signals or training data for validation")
            return {}

        logger.info(f"Validating {len(signals)} signals against trading data...")

        validation = {
            'total_signals': len(signals),
            'matched_signals': 0,
            'signal_accuracy': 0.0,
            'winning_signals': 0,
            'losing_signals': 0,
            'win_rate': 0.0,
            'avg_pnl': 0.0,
            'sharpe_ratio': 0.0,
            'information_coefficient': 0.0,
            'max_drawdown': 0.0,
            'by_symbol': {},
        }

        # Create symbol → trade map
        symbol_trades = {}
        for trade in self.training_data:
            symbol = trade['symbol']
            if symbol not in symbol_trades:
                symbol_trades[symbol] = []
            symbol_trades[symbol].append(trade)

        # Match signals to trades
        matched_pnls = []
        matched_confidences = []

        for signal in signals:
            symbol = signal.get('symbol', '').upper()
            if symbol not in symbol_trades:
                continue

            # Get most recent trade for this symbol
            trade = max(symbol_trades[symbol], key=lambda x: x['entry_date'])
            validation['matched_signals'] += 1

            is_winner = trade['pnl'] > 0
            if is_winner:
                validation['winning_signals'] += 1
            else:
                validation['losing_signals'] += 1

            matched_pnls.append(trade['pnl'])
            matched_confidences.append(signal.get('confidence', 0.5))

            # Symbol-level stats
            if symbol not in validation['by_symbol']:
                validation['by_symbol'][symbol] = {
                    'trades': 0,
                    'wins': 0,
                    'pnl': 0.0,
                    'avg_confidence': 0.0,
                }

            validation['by_symbol'][symbol]['trades'] += 1
            validation['by_symbol'][symbol]['wins'] += int(is_winner)
            validation['by_symbol'][symbol]['pnl'] += trade['pnl']
            validation['by_symbol'][symbol]['avg_confidence'] += signal.get('confidence', 0.5)

        # Calculate metrics
        if matched_pnls:
            validation['win_rate'] = validation['winning_signals'] / len(matched_pnls)
            validation['avg_pnl'] = np.mean(matched_pnls)

            # Sharpe ratio (assuming annual risk-free rate = 0)
            returns = np.array(matched_pnls) / 100  # Convert to percentages
            if len(returns) > 1 and np.std(returns) > 0:
                validation['sharpe_ratio'] = np.mean(returns) / np.std(returns) * np.sqrt(252)

            # Information coefficient (correlation between confidence and P&L)
            if len(matched_confidences) > 1:
                correlation = np.corrcoef(matched_confidences, matched_pnls)[0, 1]
                validation['information_coefficient'] = float(correlation) if not np.isnan(correlation) else 0.0

            # Max drawdown
            cumulative_pnl = np.cumsum(matched_pnls)
            running_max = np.maximum.accumulate(cumulative_pnl)
            drawdown = (cumulative_pnl - running_max) / running_max
            validation['max_drawdown'] = float(np.min(drawdown)) if len(drawdown) > 0 else 0.0

        # Calculate symbol averages
        for symbol_data in validation['by_symbol'].values():
            if symbol_data['trades'] > 0:
                symbol_data['win_rate'] = symbol_data['wins'] / symbol_data['trades']
                symbol_data['avg_confidence'] /= symbol_data['trades']

        self.validation_results = validation
        logger.info(
            f"✅ Signal validation complete: "
            f"{validation['matched_signals']} matched, "
            f"Win rate: {validation['win_rate']:.1%}, "
            f"Sharpe: {validation['sharpe_ratio']:.2f}"
        )
        return validation

    def train_model(self, test_size: float = 0.2) -> Dict:
        """
        Train model on validated trading data.

        Args:
            test_size: Proportion of data to use for testing

        Returns:
            Dict with training metrics and performance stats

        Raises:
            TrainingError: If training fails
            DataValidationError: If insufficient data
        """
        if len(self.training_data) < self.MIN_SAMPLES_REQUIRED:
            raise DataValidationError(
                f"Insufficient training data: "
                f"{len(self.training_data)} < {self.MIN_SAMPLES_REQUIRED}"
            )

        try:
            logger.info(f"Training model on {len(self.training_data)} records...")

            # Convert to DataFrame for feature engineering
            df = pd.DataFrame(self.training_data)

            # Create features
            df['price_change'] = (df['exit_price'] - df['entry_price']) / df['entry_price']
            df['return_pct'] = (df['pnl'] / (df['quantity'] * df['entry_price'])) * 100
            df['position_size'] = df['quantity'] * df['entry_price']
            df['target'] = (df['pnl'] > 0).astype(int)

            # Split data
            split_idx = int(len(df) * (1 - test_size))
            train_df = df.iloc[:split_idx]
            test_df = df.iloc[split_idx:]

            if len(train_df) < self.MIN_SAMPLES_REQUIRED:
                raise DataValidationError(
                    f"Training set too small after split: {len(train_df)}"
                )

            logger.info(
                f"Training set: {len(train_df)} records, "
                f"Test set: {len(test_df)} records"
            )

            # Train model
            metrics = self.model.train(train_df)

            if not metrics:
                raise TrainingError("Model training returned no metrics")

            # Evaluate on test set
            test_metrics = self._evaluate_model(self.model, test_df)

            # Store metrics
            self.model_metrics = {
                'timestamp': datetime.now().isoformat(),
                'training_records': len(train_df),
                'test_records': len(test_df),
                'training_metrics': metrics,
                'test_metrics': test_metrics,
                'validation_results': self.validation_results,
            }

            # Save model
            self.model.save()

            logger.info(
                f"✅ Model training complete: "
                f"Train Acc={metrics.get('accuracy', 0):.1%}, "
                f"Test Acc={test_metrics.get('accuracy', 0):.1%}"
            )

            return self.model_metrics

        except Exception as e:
            logger.error(f"Model training failed: {e}")
            raise TrainingError(f"Training failed: {e}") from e

    def _evaluate_model(self, model: AtlasModel, test_df: pd.DataFrame) -> Dict:
        """
        Evaluate model on test data.

        Args:
            model: Trained AtlasModel
            test_df: Test DataFrame

        Returns:
            Dict with evaluation metrics
        """
        try:
            if test_df.empty or model.model is None:
                return {}

            # Get predictions
            feature_cols = [col for col in test_df.columns if col.startswith('f')]
            if not feature_cols:
                logger.warning("No feature columns found for evaluation")
                return {}

            X_test = test_df[feature_cols].fillna(test_df[feature_cols].mean())
            y_test = test_df.get('target', pd.Series([0] * len(test_df)))

            predictions = model.model.predict(X_test)
            probabilities = model.model.predict_proba(X_test)

            # Calculate metrics
            from sklearn.metrics import accuracy_score, precision_score, recall_score, roc_auc_score

            metrics = {
                'accuracy': float(accuracy_score(y_test, predictions)),
                'precision': float(precision_score(y_test, predictions, zero_division=0)),
                'recall': float(recall_score(y_test, predictions, zero_division=0)),
            }

            # ROC AUC if binary classification
            if len(np.unique(y_test)) > 1 and probabilities.shape[1] > 1:
                metrics['roc_auc'] = float(roc_auc_score(y_test, probabilities[:, 1]))

            return metrics

        except Exception as e:
            logger.warning(f"Error evaluating model: {e}")
            return {}

    def compare_models(self, baseline_model: Optional[AtlasModel] = None) -> Dict:
        """
        Compare current model against baseline.

        Args:
            baseline_model: Baseline AtlasModel to compare against

        Returns:
            Dict with comparison metrics and improvements
        """
        if not self.model_metrics:
            logger.warning("No metrics available for comparison")
            return {}

        comparison = {
            'timestamp': datetime.now().isoformat(),
            'current_model': self.model.model_id,
            'current_metrics': self.model_metrics,
        }

        if baseline_model and baseline_model.training_metrics:
            comparison['baseline_metrics'] = baseline_model.training_metrics
            comparison['improvement'] = self._calculate_improvement(
                self.model_metrics,
                baseline_model.training_metrics
            )

        return comparison

    def _calculate_improvement(self, current: Dict, baseline: Dict) -> Dict:
        """
        Calculate metric improvements.

        Args:
            current: Current metrics
            baseline: Baseline metrics

        Returns:
            Dict with improvement percentages
        """
        improvement = {}

        current_acc = current.get('training_metrics', {}).get('accuracy', 0)
        baseline_acc = baseline.get('accuracy', 0)

        if baseline_acc > 0:
            improvement['accuracy'] = (current_acc - baseline_acc) / baseline_acc * 100

        return improvement

    def save_metrics(self, filepath: Optional[Path] = None) -> Optional[Path]:
        """
        Save training metrics to file.

        Args:
            filepath: Output filepath (auto-generated if None)

        Returns:
            Path to saved file or None if save fails
        """
        if not self.model_metrics:
            logger.warning("No metrics to save")
            return None

        try:
            if filepath is None:
                filepath = config.BACKTEST_DIR / f"model_metrics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

            filepath.parent.mkdir(parents=True, exist_ok=True)

            with open(filepath, 'w') as f:
                json.dump(self.model_metrics, f, indent=2, default=str)

            logger.info(f"✅ Metrics saved to {filepath}")
            return filepath

        except IOError as e:
            logger.error(f"Error saving metrics: {e}")
            return None


def run_training_workflow(data_file: Optional[Path] = None):
    """
    Run complete model training workflow.

    Args:
        data_file: Path to training data file
    """
    print("\n" + "="*70)
    print("ATLAS - Model Training Workflow".center(70))
    print("="*70 + "\n")

    try:
        # Initialize trainer
        trainer = TradingViewModelTrainer()

        # Load data
        if data_file is None:
            # Look for most recent trading data
            data_files = list(config.BACKTEST_DIR.glob("tradingview_data_*.json"))
            if not data_files:
                logger.error("No training data found. Execute trades first.")
                return

            data_file = max(data_files, key=lambda p: p.stat().st_mtime)

        logger.info(f"Using data file: {data_file}")

        # Load and validate data
        trades = trainer.load_trading_data(data_file)

        if len(trades) < trainer.MIN_SAMPLES_REQUIRED:
            logger.error(
                f"Insufficient trades ({len(trades)}) for training. "
                f"Execute more trades and try again."
            )
            return

        # Train model
        metrics = trainer.train_model()

        # Print results
        print("\n" + "="*70)
        print("TRAINING RESULTS")
        print("="*70 + "\n")

        train_metrics = metrics.get('training_metrics', {})
        test_metrics = metrics.get('test_metrics', {})

        print(f"Training Set:  {metrics['training_records']} records")
        print(f"Test Set:      {metrics['test_records']} records")
        print(f"Model ID:      {trainer.model.model_id}\n")

        print("Training Metrics:")
        for key, value in train_metrics.items():
            print(f"  {key}: {value}")

        print("\nTest Metrics:")
        for key, value in test_metrics.items():
            print(f"  {key}: {value}")

        # Save metrics
        trainer.save_metrics()

        print("\n" + "="*70)
        print("✅ MODEL TRAINING COMPLETE")
        print("="*70)

    except Exception as e:
        logger.error(f"Training workflow failed: {e}", exc_info=True)


if __name__ == "__main__":
    import sys

    logging.basicConfig(
        format=config.LOG_FORMAT,
        level="INFO",
        handlers=[
            logging.FileHandler(config.LOGS_DIR / "tradingview_model_trainer_v2.log"),
            logging.StreamHandler()
        ]
    )

    run_training_workflow()
