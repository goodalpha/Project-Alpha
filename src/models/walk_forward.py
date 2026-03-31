"""
Walk-forward cross-validation engine with embargo for backtesting.
"""

from typing import Iterator, Tuple
import numpy as np
import pandas as pd
from loguru import logger

from src.models.baseline import ElasticNetModel, compute_ic, compute_rank_ic, compute_icir
from src.models.ensemble import XGBoostModel, EnsembleModel


class WalkForwardSplitter:
    """Walk-forward time series split with embargo periods."""

    def __init__(self, config: dict):
        """
        Initialize WalkForwardSplitter.

        Parameters
        ----------
        config : dict
            Configuration dict. Expected keys:
            - 'validation':
              - 'train_years': int (default: 5)
              - 'val_months': int (default: 6)
              - 'test_months': int (default: 6)
              - 'embargo_days': int (default: 10)
              - 'min_train_samples': int (default: 252)
        """
        val_config = config.get("validation", {})
        self.train_years = val_config.get("train_years", 5)
        self.val_months = val_config.get("val_months", 6)
        self.test_months = val_config.get("test_months", 6)
        self.embargo_days = val_config.get("embargo_days", 10)
        self.min_train_samples = val_config.get("min_train_samples", 252)

        logger.info(
            f"WalkForwardSplitter config: train={self.train_years}yr, "
            f"val={self.val_months}mo, test={self.test_months}mo, embargo={self.embargo_days}d"
        )

    def split(
        self, dates: pd.DatetimeIndex
    ) -> Iterator[Tuple[np.ndarray, np.ndarray, np.ndarray]]:
        """
        Generate train/val/test indices with walk-forward and embargo.

        Parameters
        ----------
        dates : pd.DatetimeIndex
            Unique dates from the dataset, sorted.

        Yields
        ------
        Tuple[np.ndarray, np.ndarray, np.ndarray]
            (train_idx, val_idx, test_idx) for each fold.
        """
        if not isinstance(dates, pd.DatetimeIndex):
            dates = pd.to_datetime(dates)
        dates = dates.sort_values()

        # Get unique dates in the dataset
        unique_dates = np.array(dates.unique())
        unique_dates = np.sort(unique_dates)

        logger.info(f"Total unique dates: {len(unique_dates)}")
        logger.info(f"Date range: {unique_dates[0]} to {unique_dates[-1]}")

        fold_idx = 0
        train_start_idx = 0

        while True:
            # Define fold windows based on unique dates
            train_end_date = unique_dates[train_start_idx] + pd.DateOffset(years=self.train_years)
            embargo1_end_date = train_end_date + pd.DateOffset(days=self.embargo_days)
            val_end_date = embargo1_end_date + pd.DateOffset(months=self.val_months)
            embargo2_end_date = val_end_date + pd.DateOffset(days=self.embargo_days)
            test_end_date = embargo2_end_date + pd.DateOffset(months=self.test_months)

            # Find indices in unique dates
            train_indices = np.where(unique_dates <= train_end_date)[0]
            if len(train_indices) < self.min_train_samples:
                logger.warning(
                    f"Fold {fold_idx}: Train samples ({len(train_indices)}) < min_train_samples ({self.min_train_samples}). Skipping."
                )
                break

            # Validation: between embargo1_end_date and val_end_date
            val_indices = np.where(
                (unique_dates > embargo1_end_date) & (unique_dates <= val_end_date)
            )[0]

            # Test: between embargo2_end_date and test_end_date
            test_indices = np.where(
                (unique_dates > embargo2_end_date) & (unique_dates <= test_end_date)
            )[0]

            if len(val_indices) == 0 or len(test_indices) == 0:
                logger.warning(
                    f"Fold {fold_idx}: Insufficient val ({len(val_indices)}) or test ({len(test_indices)}) dates. Stopping."
                )
                break

            # Convert from unique_dates indices to original dates indices
            train_date_indices = np.where(np.isin(dates, unique_dates[train_indices]))[0]
            val_date_indices = np.where(np.isin(dates, unique_dates[val_indices]))[0]
            test_date_indices = np.where(np.isin(dates, unique_dates[test_indices]))[0]

            logger.info(
                f"Fold {fold_idx}: train={len(train_date_indices)}, "
                f"val={len(val_date_indices)}, test={len(test_date_indices)}"
            )

            yield train_date_indices, val_date_indices, test_date_indices

            # Move forward by test_months for next fold
            next_start_date = test_end_date
            next_start_idx = np.searchsorted(unique_dates, next_start_date, side='left')

            if next_start_idx >= len(unique_dates):
                logger.info("Reached end of data, stopping walk-forward")
                break

            train_start_idx = next_start_idx
            fold_idx += 1

    def n_splits(self, dates: pd.DatetimeIndex) -> int:
        """
        Get total number of splits.

        Parameters
        ----------
        dates : pd.DatetimeIndex
            Unique dates from the dataset, sorted.

        Returns
        -------
        int
            Number of folds.
        """
        count = 0
        for _ in self.split(dates):
            count += 1
        return count


class WalkForwardValidator:
    """Walk-forward cross-validation engine."""

    def __init__(self, config: dict):
        """
        Initialize WalkForwardValidator.

        Parameters
        ----------
        config : dict
            Configuration dict with 'validation' key containing WalkForwardSplitter config.
        """
        self.config = config
        self.splitter = WalkForwardSplitter(config)

    def run(
        self,
        features: pd.DataFrame,
        targets: pd.Series,
        model_class,
        model_config: dict,
    ) -> dict:
        """
        Run walk-forward validation.

        Parameters
        ----------
        features : pd.DataFrame
            Feature matrix with (date, ticker) MultiIndex or date index.
        targets : pd.Series
            Target values (realized returns) with same index as features.
        model_class : type
            Model class to instantiate (ElasticNetModel, XGBoostModel, etc.).
        model_config : dict
            Configuration dict for model initialization.

        Returns
        -------
        dict
            Results dict with:
            - 'fold_metrics': list of fold metrics
            - 'all_predictions': DataFrame with predictions and targets
            - 'feature_importance': DataFrame with feature importance per fold
            - 'summary': summary statistics dict
        """
        logger.info(f"Starting walk-forward validation with {model_class.__name__}")

        # Handle NaN features with warning
        nan_count = features.isna().sum().sum()
        if nan_count > 0:
            logger.warning(f"Found {nan_count} NaN values in features, filling with 0")
            features = features.fillna(0)

        # Extract unique dates
        if isinstance(features.index, pd.MultiIndex):
            if 'date' in features.index.names:
                date_level = features.index.names.index('date')
                unique_dates = features.index.get_level_values(date_level).unique().sort_values()
            else:
                unique_dates = features.index.get_level_values(0).unique().sort_values()
        else:
            unique_dates = features.index.unique().sort_values()

        fold_metrics = []
        all_predictions = []
        feature_importances = []

        for fold_idx, (train_idx, val_idx, test_idx) in enumerate(self.splitter.split(unique_dates)):
            logger.info(f"Processing fold {fold_idx}")

            # Get train/val/test data by indices
            X_train = features.iloc[train_idx]
            y_train = targets.iloc[train_idx]
            X_val = features.iloc[val_idx]
            y_val = targets.iloc[val_idx]
            X_test = features.iloc[test_idx]
            y_test = targets.iloc[test_idx]

            # Skip fold if insufficient data
            if len(X_train) < 10 or len(X_test) < 5:
                logger.warning(
                    f"Fold {fold_idx}: Insufficient data (train={len(X_train)}, test={len(X_test)}). Skipping."
                )
                continue

            # Instantiate and fit model
            try:
                model = model_class(model_config)

                # Some models support validation set, others don't
                if hasattr(model, 'fit'):
                    sig = model.fit.__code__.co_varnames
                    if 'X_val' in sig:
                        model.fit(X_train, y_train, X_val, y_val)
                    else:
                        model.fit(X_train, y_train)

                # Make predictions on test set
                y_pred = model.predict(X_test)

                # Compute metrics
                ic = compute_ic(y_pred, y_test)
                rank_ic = compute_rank_ic(y_pred, y_test)

                # Per-date IC for ICIR
                if isinstance(X_test.index, pd.MultiIndex):
                    if 'date' in X_test.index.names:
                        date_level = X_test.index.names.index('date')
                        dates_test = X_test.index.get_level_values(date_level)
                    else:
                        dates_test = X_test.index.get_level_values(0)
                else:
                    dates_test = X_test.index

                per_date_ic = []
                for date in dates_test.unique():
                    mask = dates_test == date
                    ic_date = compute_ic(y_pred[mask], y_test[mask])
                    if not np.isnan(ic_date):
                        per_date_ic.append(ic_date)

                if len(per_date_ic) > 0:
                    ic_series = pd.Series(per_date_ic)
                    icir = compute_icir(ic_series)
                else:
                    icir = np.nan

                # Store fold metrics
                train_date_start = X_train.index[0] if not isinstance(X_train.index, pd.MultiIndex) else X_train.index.get_level_values(0)[0]
                train_date_end = X_train.index[-1] if not isinstance(X_train.index, pd.MultiIndex) else X_train.index.get_level_values(0)[-1]
                test_date_start = X_test.index[0] if not isinstance(X_test.index, pd.MultiIndex) else X_test.index.get_level_values(0)[0]
                test_date_end = X_test.index[-1] if not isinstance(X_test.index, pd.MultiIndex) else X_test.index.get_level_values(0)[-1]

                fold_metrics.append({
                    'fold': fold_idx,
                    'train_dates': f"{train_date_start} to {train_date_end}",
                    'test_dates': f"{test_date_start} to {test_date_end}",
                    'ic': ic,
                    'rank_ic': rank_ic,
                    'icir': icir,
                    'n_test_samples': len(X_test),
                })

                # Store predictions
                for idx, pred in y_pred.items():
                    all_predictions.append({
                        'fold': fold_idx,
                        'index': idx,
                        'y_pred': pred,
                        'y_true': y_test[idx],
                    })

                # Store feature importance
                if hasattr(model, 'get_feature_importance'):
                    try:
                        importance = model.get_feature_importance()
                        for feature, imp in importance.items():
                            feature_importances.append({
                                'fold': fold_idx,
                                'feature': feature,
                                'importance': imp,
                            })
                    except Exception as e:
                        logger.warning(f"Could not extract feature importance in fold {fold_idx}: {e}")

            except Exception as e:
                logger.error(f"Error processing fold {fold_idx}: {e}")
                continue

        # Compile results
        predictions_df = pd.DataFrame(all_predictions) if all_predictions else pd.DataFrame()
        importance_df = pd.DataFrame(feature_importances) if feature_importances else pd.DataFrame()

        # Compute summary statistics
        if fold_metrics:
            fold_metrics_df = pd.DataFrame(fold_metrics)
            summary = {
                'mean_ic': fold_metrics_df['ic'].mean(),
                'std_ic': fold_metrics_df['ic'].std(),
                'icir': fold_metrics_df['icir'].mean(),
                'mean_rank_ic': fold_metrics_df['rank_ic'].mean(),
                'std_rank_ic': fold_metrics_df['rank_ic'].std(),
                'pct_positive_ic': (fold_metrics_df['ic'] > 0).sum() / len(fold_metrics_df),
                'n_folds': len(fold_metrics),
            }
        else:
            summary = {}

        logger.info(f"Walk-forward validation complete: {len(fold_metrics)} folds")

        return {
            'fold_metrics': fold_metrics,
            'all_predictions': predictions_df,
            'feature_importance': importance_df,
            'summary': summary,
        }


def run_walk_forward(
    features: pd.DataFrame,
    targets: dict,
    config: dict,
    mlflow_tracking: bool = False,
) -> dict:
    """
    Convenience function to run walk-forward validation for multiple models.

    Parameters
    ----------
    features : pd.DataFrame
        Feature matrix with (date, ticker) MultiIndex.
    targets : dict
        Dict of {target_name: pd.Series} for different targets.
    config : dict
        Configuration dict with 'models' and 'validation' keys.
    mlflow_tracking : bool, optional
        Whether to log results to MLflow (default: False).

    Returns
    -------
    dict
        Combined results dict with results for each model and target.
    """
    logger.info("Starting walk-forward run")

    results = {}

    # Get target (first one if multiple)
    target_name = list(targets.keys())[0]
    y = targets[target_name]

    logger.info(f"Using target: {target_name}")

    # Run ElasticNet
    if config.get("models", {}).get("elasticnet", {}).get("enabled", True):
        logger.info("Running ElasticNetModel")
        validator = WalkForwardValidator(config)
        elasticnet_config = config.get("models", {}).get("elasticnet", {})
        elasticnet_results = validator.run(features, y, ElasticNetModel, elasticnet_config)
        results['elasticnet'] = elasticnet_results

        if mlflow_tracking:
            try:
                import mlflow
                with mlflow.start_run(run_name="elasticnet_walk_forward"):
                    mlflow.log_params(elasticnet_config)
                    summary = elasticnet_results.get('summary', {})
                    for key, val in summary.items():
                        if isinstance(val, (int, float)):
                            mlflow.log_metric(key, val)
                logger.info("Logged ElasticNet results to MLflow")
            except ImportError:
                logger.warning("MLflow not available, skipping MLflow logging")

    # Run XGBoost
    if config.get("models", {}).get("xgboost", {}).get("enabled", True):
        logger.info("Running XGBoostModel")
        validator = WalkForwardValidator(config)
        xgboost_config = config.get("models", {}).get("xgboost", {})
        xgboost_results = validator.run(features, y, XGBoostModel, xgboost_config)
        results['xgboost'] = xgboost_results

        if mlflow_tracking:
            try:
                import mlflow
                with mlflow.start_run(run_name="xgboost_walk_forward"):
                    mlflow.log_params(xgboost_config.get("xgboost_params", {}))
                    summary = xgboost_results.get('summary', {})
                    for key, val in summary.items():
                        if isinstance(val, (int, float)):
                            mlflow.log_metric(key, val)
                logger.info("Logged XGBoost results to MLflow")
            except ImportError:
                logger.warning("MLflow not available, skipping MLflow logging")

    logger.info("Walk-forward run complete")
    return results
