"""
Elastic Net baseline model for cross-sectional return prediction.
"""

import numpy as np
import pandas as pd
from scipy.stats import spearmanr, pearsonr
from sklearn.linear_model import ElasticNetCV
from sklearn.model_selection import TimeSeriesSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from loguru import logger


def compute_ic(y_pred: pd.Series, y_true: pd.Series) -> float:
    """
    Compute Information Coefficient (Pearson correlation) between predictions and realized returns.

    Parameters
    ----------
    y_pred : pd.Series
        Predicted returns.
    y_true : pd.Series
        Realized returns.

    Returns
    -------
    float
        Pearson correlation coefficient.
    """
    # Remove NaN values
    mask = ~(y_pred.isna() | y_true.isna())
    if mask.sum() < 2:
        logger.warning(f"Insufficient valid pairs for IC computation: {mask.sum()}")
        return np.nan

    correlation, _ = pearsonr(y_pred[mask], y_true[mask])
    return correlation


def compute_rank_ic(y_pred: pd.Series, y_true: pd.Series) -> float:
    """
    Compute Rank Information Coefficient (Spearman correlation) between predictions and realized returns.

    Parameters
    ----------
    y_pred : pd.Series
        Predicted returns.
    y_true : pd.Series
        Realized returns.

    Returns
    -------
    float
        Spearman rank correlation coefficient.
    """
    # Remove NaN values
    mask = ~(y_pred.isna() | y_true.isna())
    if mask.sum() < 2:
        logger.warning(f"Insufficient valid pairs for rank IC computation: {mask.sum()}")
        return np.nan

    correlation, _ = spearmanr(y_pred[mask], y_true[mask])
    return correlation


def compute_icir(ic_series: pd.Series) -> float:
    """
    Compute Information Coefficient Information Ratio (IC mean / IC std).

    Parameters
    ----------
    ic_series : pd.Series
        Time series of Information Coefficients.

    Returns
    -------
    float
        ICIR (mean IC / std IC).
    """
    ic_mean = ic_series.mean()
    ic_std = ic_series.std()

    if ic_std == 0 or np.isnan(ic_std):
        logger.warning("IC standard deviation is zero or NaN, returning NaN for ICIR")
        return np.nan

    return ic_mean / ic_std


class ElasticNetModel:
    """
    Elastic Net baseline model for cross-sectional return prediction.

    Uses ElasticNetCV with TimeSeriesSplit for hyperparameter tuning.
    """

    def __init__(self, config: dict):
        """
        Initialize ElasticNetModel.

        Parameters
        ----------
        config : dict
            Configuration dict. Expected keys:
            - 'l1_ratio': list of l1_ratio values [0.1, 0.5, 0.9]
            - 'alpha': list of alpha values [0.001, 0.01, 0.1]
            - 'cv_splits': number of CV splits for TimeSeriesSplit (default: 3)
        """
        self.config = config
        self.l1_ratio = config.get("l1_ratio", [0.1, 0.5, 0.9])
        self.alpha = config.get("alpha", [0.001, 0.01, 0.1])
        self.cv_splits = config.get("cv_splits", 3)
        self.model = None
        self.scaler = None
        self.best_l1_ratio = None
        self.best_alpha = None

    def fit(self, X: pd.DataFrame, y: pd.Series) -> "ElasticNetModel":
        """
        Fit the Elastic Net model with hyperparameter tuning using TimeSeriesSplit.

        Parameters
        ----------
        X : pd.DataFrame
            Feature matrix.
        y : pd.Series
            Target values (realized returns).

        Returns
        -------
        ElasticNetModel
            Returns self for method chaining.
        """
        logger.info(f"Fitting ElasticNetModel with {X.shape[0]} samples and {X.shape[1]} features")

        # Create pipeline with scaler
        pipeline = Pipeline(
            [
                ("scaler", StandardScaler()),
                (
                    "elasticnet",
                    ElasticNetCV(
                        l1_ratio=self.l1_ratio,
                        alphas=self.alpha,
                        cv=TimeSeriesSplit(n_splits=self.cv_splits),
                        max_iter=10000,
                        random_state=42,
                    ),
                ),
            ]
        )

        # Fit the pipeline
        pipeline.fit(X, y)

        self.model = pipeline
        self.scaler = pipeline.named_steps["scaler"]
        elastic_net = pipeline.named_steps["elasticnet"]
        self.best_l1_ratio = elastic_net.l1_ratio_
        self.best_alpha = elastic_net.alpha_

        logger.info(
            f"ElasticNet tuned: l1_ratio={self.best_l1_ratio:.4f}, alpha={self.best_alpha:.6f}"
        )
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
        Get feature importance as absolute coefficient values.

        Returns
        -------
        pd.Series
            Feature importance (absolute coefficients) indexed by feature names.
        """
        if self.model is None:
            raise ValueError("Model must be fitted before getting feature importance")

        elastic_net = self.model.named_steps["elasticnet"]
        coef = np.abs(elastic_net.coef_)

        # Get feature names from the pipeline
        feature_names = elastic_net.feature_names_in_
        return pd.Series(coef, index=feature_names).sort_values(ascending=False)

    def rank_ic(self, X: pd.DataFrame, y: pd.Series) -> float:
        """
        Compute Rank Information Coefficient on the given data.

        Parameters
        ----------
        X : pd.DataFrame
            Feature matrix.
        y : pd.Series
            Realized returns.

        Returns
        -------
        float
            Rank IC (Spearman correlation).
        """
        y_pred = self.predict(X)
        return compute_rank_ic(y_pred, y)
