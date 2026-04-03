"""
PROJECT ATLAS - Model Training & Inference
XGBoost classifier for 1-month forward return prediction
"""

import logging
import pandas as pd
import numpy as np
from typing import Tuple, Dict
import pickle
from datetime import datetime
import xgboost as xgb
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import accuracy_score, precision_score, recall_score, roc_auc_score

import config

logger = logging.getLogger(__name__)
logger.setLevel(config.LOG_LEVEL)


class AtlasModel:
    """
    XGBoost model for MVP: 1-month forward return prediction.
    Target: Top quintile (1) vs rest (0) classification.
    """

    def __init__(self, model_id: str = None):
        self.model_id = model_id or f"atlas_model_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.model = None
        self.scaler = StandardScaler()
        self.feature_importance = None
        self.training_date = None
        self.training_metrics = {}

    def _prepare_data(
        self,
        df: pd.DataFrame,
        target_col: str = 'target'
    ) -> Tuple[pd.DataFrame, pd.Series]:
        """
        Prepare feature matrix and target.

        Args:
            df: DataFrame with features and target
            target_col: Name of target column

        Returns:
            Tuple of (X, y)
        """
        feature_cols = [col for col in df.columns if col.startswith('f')]

        X = df[feature_cols].copy()
        y = df[target_col].copy() if target_col in df.columns else None

        # Handle missing values
        X = X.fillna(X.mean())

        return X, y

    def create_target_variable(self, df: pd.DataFrame, lookback_days: int = 21) -> pd.DataFrame:
        """
        Create binary target: top quintile (1) vs rest (0).

        Args:
            df: DataFrame with OHLCV data
            lookback_days: Number of days to compute forward return

        Returns:
            DataFrame with 'target' column added
        """
        # Group by date and compute forward returns
        df = df.copy()
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values(['date', 'ticker']).reset_index(drop=True)

        # For each date, compute forward return
        df['forward_price'] = df.groupby('ticker')['close'].shift(-lookback_days)
        df['forward_return'] = (df['forward_price'] - df['close']) / df['close']

        # Create binary target: 1 if stock is in top quintile, 0 otherwise
        df['target'] = df.groupby('date')['forward_return'].transform(
            lambda x: (x >= x.quantile(0.80)).astype(int)
        )

        # Remove rows with NaN targets (last few rows of data)
        df = df.dropna(subset=['target'])

        logger.info(f"Created target variable: {df['target'].sum()} positive, {(~df['target'].astype(bool)).sum()} negative")

        return df

    def train(
        self,
        train_df: pd.DataFrame,
        val_df: pd.DataFrame = None,
        target_col: str = 'target'
    ) -> Dict:
        """
        Train XGBoost model on training data.

        Args:
            train_df: Training DataFrame with features and target
            val_df: Validation DataFrame for early stopping
            target_col: Name of target column

        Returns:
            Dict with training metrics
        """
        logger.info(f"Training model {self.model_id}...")

        # Prepare data
        X_train, y_train = self._prepare_data(train_df, target_col)

        if len(X_train) == 0 or len(y_train) == 0:
            logger.error("Empty training data")
            return {}

        # Scale features
        X_train_scaled = self.scaler.fit_transform(X_train)

        # Create XGBoost DMatrix
        dtrain = xgb.DMatrix(X_train_scaled, label=y_train)

        # Training parameters
        params = {
            'max_depth': config.XGBOOST_PARAMS['max_depth'],
            'eta': config.XGBOOST_PARAMS['learning_rate'],
            'objective': config.XGBOOST_PARAMS['objective'],
            'eval_metric': config.XGBOOST_PARAMS['eval_metric'],
            'subsample': config.XGBOOST_PARAMS['subsample'],
            'colsample_bytree': config.XGBOOST_PARAMS['colsample_bytree'],
            'random_state': config.XGBOOST_PARAMS['random_state'],
        }

        # Validation set for early stopping (optional)
        evals = []
        if val_df is not None:
            X_val, y_val = self._prepare_data(val_df, target_col)
            X_val_scaled = self.scaler.transform(X_val)
            dval = xgb.DMatrix(X_val_scaled, label=y_val)
            evals = [(dval, 'validation')]

        # Train
        self.model = xgb.train(
            params,
            dtrain,
            num_boost_round=config.XGBOOST_PARAMS['n_estimators'],
            evals=evals if evals else None,
            early_stopping_rounds=20 if evals else None,
            verbose_eval=False
        )

        # Compute training metrics
        y_pred_train = self.predict(train_df)
        y_pred_proba = self.predict_proba(train_df)

        self.training_metrics = {
            'accuracy': accuracy_score(y_train, y_pred_train),
            'precision': precision_score(y_train, y_pred_train, zero_division=0),
            'recall': recall_score(y_train, y_pred_train, zero_division=0),
            'auc_roc': roc_auc_score(y_train, y_pred_proba),
        }

        self.training_date = datetime.now()

        logger.info(f"Training complete. Metrics: {self.training_metrics}")
        return self.training_metrics

    def predict(self, df: pd.DataFrame) -> np.ndarray:
        """
        Predict class (0 or 1) for each row.

        Args:
            df: DataFrame with features

        Returns:
            Array of predictions (0 or 1)
        """
        X, _ = self._prepare_data(df)
        X_scaled = self.scaler.transform(X)
        dtest = xgb.DMatrix(X_scaled)
        proba = self.model.predict(dtest)
        return (proba > 0.5).astype(int)

    def predict_proba(self, df: pd.DataFrame) -> np.ndarray:
        """
        Predict probability of class 1.

        Args:
            df: DataFrame with features

        Returns:
            Array of probabilities
        """
        X, _ = self._prepare_data(df)
        X_scaled = self.scaler.transform(X)
        dtest = xgb.DMatrix(X_scaled)
        return self.model.predict(dtest)

    def get_feature_importance(self) -> Dict:
        """Get feature importance from trained model."""
        if self.model is None:
            return {}

        importance_dict = self.model.get_score(importance_type='weight')
        # Sort by importance
        return dict(sorted(importance_dict.items(), key=lambda x: x[1], reverse=True))

    def save(self, filepath: str = None):
        """Save model to disk."""
        if filepath is None:
            filepath = config.MODELS_DIR / f"{self.model_id}.pkl"

        with open(filepath, 'wb') as f:
            pickle.dump({
                'model': self.model,
                'scaler': self.scaler,
                'model_id': self.model_id,
                'training_date': self.training_date,
                'training_metrics': self.training_metrics,
            }, f)

        logger.info(f"Model saved to {filepath}")

    def load(self, filepath: str):
        """Load model from disk."""
        with open(filepath, 'rb') as f:
            data = pickle.load(f)

        self.model = data['model']
        self.scaler = data['scaler']
        self.model_id = data['model_id']
        self.training_date = data['training_date']
        self.training_metrics = data['training_metrics']

        logger.info(f"Model loaded from {filepath}")


# ============================================================================
# MODEL VALIDATION
# ============================================================================

class ModelValidator:
    """Validates model performance and detects drift."""

    @staticmethod
    def compute_information_coefficient(
        predictions: np.ndarray,
        actual_returns: np.ndarray
    ) -> float:
        """
        Compute Information Coefficient (IC).
        Rank correlation between predicted ranking and actual returns.
        """
        # Rank correlation between predictions and actual returns
        from scipy.stats import spearmanr
        ic, p_value = spearmanr(predictions, actual_returns)
        return ic

    @staticmethod
    def check_model_health(
        model: AtlasModel,
        val_df: pd.DataFrame,
        target_col: str = 'target'
    ) -> Dict:
        """
        Check model health: accuracy, calibration, information coefficient.

        Args:
            model: Trained AtlasModel instance
            val_df: Validation DataFrame
            target_col: Name of target column

        Returns:
            Dict with health metrics
        """
        y_val = val_df[target_col].values
        y_pred = model.predict(val_df)
        y_pred_proba = model.predict_proba(val_df)

        health_metrics = {
            'accuracy': accuracy_score(y_val, y_pred),
            'precision': precision_score(y_val, y_pred, zero_division=0),
            'recall': recall_score(y_val, y_pred, zero_division=0),
            'auc_roc': roc_auc_score(y_val, y_pred_proba),
        }

        # Check for minimum viable accuracy
        if health_metrics['accuracy'] < 0.52:
            logger.warning(f"Model accuracy below 52%: {health_metrics['accuracy']}")

        return health_metrics


if __name__ == "__main__":
    logging.basicConfig(format=config.LOG_FORMAT)
    logger.info("Model module loaded")
