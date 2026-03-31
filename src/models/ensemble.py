"""
XGBoost model and ensemble for cross-sectional return prediction.
"""

import numpy as np
import pandas as pd
import xgboost as xgb
from loguru import logger
from src.models.baseline import compute_rank_ic


class XGBoostModel:
    """XGBoost model for cross-sectional return prediction."""

    def __init__(self, config: dict):
        """
        Initialize XGBoostModel.

        Parameters
        ----------
        config : dict
            Configuration dict. Expected keys:
            - 'xgboost_params': dict with params like n_estimators, max_depth, learning_rate, etc.
            - 'early_stopping_rounds': int (default: 50)
        """
        self.config = config
        xgb_params = config.get("xgboost_params", {})

        # Set default XGBoost parameters
        self.n_estimators = xgb_params.get("n_estimators", 500)
        self.max_depth = xgb_params.get("max_depth", 4)
        self.learning_rate = xgb_params.get("learning_rate", 0.02)
        self.subsample = xgb_params.get("subsample", 0.8)
        self.colsample_bytree = xgb_params.get("colsample_bytree", 0.7)
        self.min_child_weight = xgb_params.get("min_child_weight", 50)
        self.early_stopping_rounds = config.get("early_stopping_rounds", 50)

        self.model = None

    def fit(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_val: pd.DataFrame = None,
        y_val: pd.Series = None,
    ) -> "XGBoostModel":
        """
        Fit the XGBoost model with optional early stopping on validation set.

        Parameters
        ----------
        X_train : pd.DataFrame
            Training feature matrix.
        y_train : pd.Series
            Training target values.
        X_val : pd.DataFrame, optional
            Validation feature matrix for early stopping.
        y_val : pd.Series, optional
            Validation target values for early stopping.

        Returns
        -------
        XGBoostModel
            Returns self for method chaining.
        """
        logger.info(f"Fitting XGBoostModel with {X_train.shape[0]} training samples")

        eval_set = None
        eval_metric = None

        if X_val is not None and y_val is not None:
            eval_set = [(X_val, y_val)]
            eval_metric = "rmse"
            logger.info(f"Using validation set of size {X_val.shape[0]} for early stopping")

        self.model = xgb.XGBRegressor(
            n_estimators=self.n_estimators,
            max_depth=self.max_depth,
            learning_rate=self.learning_rate,
            subsample=self.subsample,
            colsample_bytree=self.colsample_bytree,
            min_child_weight=self.min_child_weight,
            objective="reg:squarederror",
            random_state=42,
            verbosity=0,
        )

        if eval_set is not None:
            self.model.fit(
                X_train,
                y_train,
                eval_set=eval_set,
                eval_metric=eval_metric,
                early_stopping_rounds=self.early_stopping_rounds,
                verbose=False,
            )
            logger.info(f"XGBoost trained with {self.model.best_iteration} rounds (early stopped)")
        else:
            self.model.fit(X_train, y_train, verbose=False)
            logger.info(f"XGBoost trained with {self.n_estimators} estimators")

        return self

    def predict(self, X: pd.DataFrame) -> pd.Series:
        """
        Predict on new data.

        Parameters
        ----------
        X : pd.DataFrame
            Feature matrix.

        Returns
        -------
        pd.Series
            Predicted returns with same index as X.
        """
        if self.model is None:
            raise ValueError("Model must be fitted before prediction")

        predictions = self.model.predict(X)
        return pd.Series(predictions, index=X.index)

    def get_feature_importance(self) -> pd.Series:
        """
        Get feature importance from XGBoost.

        Returns
        -------
        pd.Series
            Feature importance indexed by feature names.
        """
        if self.model is None:
            raise ValueError("Model must be fitted before getting feature importance")

        feature_importance = self.model.feature_importances_
        feature_names = self.model.feature_names_in_
        return pd.Series(feature_importance, index=feature_names).sort_values(ascending=False)


class EnsembleModel:
    """Ensemble model combining multiple predictions with optional weights."""

    def __init__(self, models: list, weights: list = None):
        """
        Initialize EnsembleModel.

        Parameters
        ----------
        models : list
            List of fitted model objects with .predict() method.
        weights : list, optional
            Weights for each model. If None, uses equal weights.
        """
        self.models = models
        n_models = len(models)

        if weights is None:
            self.weights = [1.0 / n_models] * n_models
            logger.info(f"Using equal weights for {n_models} models")
        else:
            if len(weights) != n_models:
                raise ValueError(f"Number of weights ({len(weights)}) must match number of models ({n_models})")
            # Normalize weights to sum to 1
            total_weight = sum(weights)
            self.weights = [w / total_weight for w in weights]
            logger.info(f"Using provided weights: {self.weights}")

    def predict(self, X: pd.DataFrame) -> pd.Series:
        """
        Predict using weighted average of all models, then rank-normalize per date.

        Parameters
        ----------
        X : pd.DataFrame
            Feature matrix. Must have 'date' in index or as a column.

        Returns
        -------
        pd.Series
            Ensemble predictions rank-normalized by date, with same index as X.
        """
        # Get predictions from all models
        predictions_list = []
        for model in self.models:
            pred = model.predict(X)
            predictions_list.append(pred)

        # Compute weighted average
        predictions_array = np.array(predictions_list)
        weighted_predictions = np.average(predictions_array, axis=0, weights=self.weights)

        ensemble_pred = pd.Series(weighted_predictions, index=X.index)

        # Rank-normalize per date if 'date' is available
        if isinstance(X.index, pd.MultiIndex) and 'date' in X.index.names:
            # MultiIndex case: (date, ticker) or similar
            date_idx = X.index.names.index('date')
            ensemble_pred = ensemble_pred.groupby(level=date_idx, group_keys=False).apply(
                lambda x: x.rank(method='average') / len(x) - 0.5
            )
            logger.info("Applied per-date rank normalization (MultiIndex)")
        elif isinstance(X.index, pd.MultiIndex):
            # Try first level as date
            ensemble_pred = ensemble_pred.groupby(level=0, group_keys=False).apply(
                lambda x: x.rank(method='average') / len(x) - 0.5
            )
            logger.info("Applied per-date rank normalization (level 0)")
        elif 'date' in X.columns:
            # Date as column
            ensemble_pred = ensemble_pred.groupby(X['date'], group_keys=False).apply(
                lambda x: x.rank(method='average') / len(x) - 0.5
            )
            logger.info("Applied per-date rank normalization (column)")

        return ensemble_pred

    def get_ensemble_ic(self, X: pd.DataFrame, y: pd.Series) -> float:
        """
        Compute Rank Information Coefficient of ensemble predictions.

        Parameters
        ----------
        X : pd.DataFrame
            Feature matrix.
        y : pd.Series
            Realized returns.

        Returns
        -------
        float
            Rank IC (Spearman correlation) of ensemble predictions.
        """
        y_pred = self.predict(X)
        return compute_rank_ic(y_pred, y)
