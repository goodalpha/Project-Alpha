"""Regime detection using macro indicators and rule-based/ML classification."""

import numpy as np
import pandas as pd
from typing import Optional
from loguru import logger
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches


class RegimeDetector:
    """
    Market regime detector using macro indicators and hybrid rule-based/ML approach.

    Supports both rule-based stress scoring and data-driven KMeans clustering.
    """

    def __init__(self, config: dict):
        """
        Initialize RegimeDetector.

        Parameters
        ----------
        config : dict
            Configuration dictionary (for future extensibility; currently minimal usage).
        """
        self.config = config
        self.scaler = StandardScaler()
        self.kmeans = None
        self.rolling_stats = {}
        self.is_fitted = False
        logger.info("RegimeDetector initialized")

    def fit(self, macro_df: pd.DataFrame) -> 'RegimeDetector':
        """
        Fit regime detection parameters on macro data.

        Computes rolling statistics and fits KMeans on normalized macro indicators.

        Parameters
        ----------
        macro_df : pd.DataFrame
            DataFrame indexed by date with columns:
            - vix: volatility index
            - yield_curve_10y2y: 10Y-2Y yield spread
            - hy_spread: high-yield credit spread
            - fed_funds_rate: fed funds rate
            - cpi_yoy: year-over-year CPI
            (Not all columns required; adjust as needed)

        Returns
        -------
        RegimeDetector
            Returns self for chaining.
        """
        logger.info(f"Fitting RegimeDetector on {len(macro_df)} observations...")

        macro_df = macro_df.sort_index()

        # Compute rolling statistics (63-day window for calibration)
        window = 63

        self.rolling_stats = {}

        # Extract required columns (fallback to NaN if missing)
        vix = macro_df['vix'] if 'vix' in macro_df.columns else pd.Series(np.nan, index=macro_df.index)
        hy_spread = macro_df['hy_spread'] if 'hy_spread' in macro_df.columns else pd.Series(np.nan, index=macro_df.index)
        yield_curve_10y2y = macro_df['yield_curve_10y2y'] if 'yield_curve_10y2y' in macro_df.columns else pd.Series(np.nan, index=macro_df.index)

        # Rolling mean and std
        self.rolling_stats['vix_mean'] = vix.rolling(window=window).mean()
        self.rolling_stats['vix_std'] = vix.rolling(window=window).std()

        self.rolling_stats['hy_spread_mean'] = hy_spread.rolling(window=window).mean()
        self.rolling_stats['hy_spread_std'] = hy_spread.rolling(window=window).std()

        self.rolling_stats['yield_curve_mean'] = yield_curve_10y2y.rolling(window=window).mean()
        self.rolling_stats['yield_curve_std'] = yield_curve_10y2y.rolling(window=window).std()

        logger.debug(f"Computed rolling statistics with window={window}")

        # === Fit KMeans on normalized features ===
        # Prepare data for KMeans: normalize and drop NaN
        vix_z63 = (vix - self.rolling_stats['vix_mean']) / (self.rolling_stats['vix_std'] + 1e-6)
        hy_spread_z63 = (hy_spread - self.rolling_stats['hy_spread_mean']) / (self.rolling_stats['hy_spread_std'] + 1e-6)
        yield_curve_z63 = (yield_curve_10y2y - self.rolling_stats['yield_curve_mean']) / (self.rolling_stats['yield_curve_std'] + 1e-6)

        kmeans_data = pd.concat([vix_z63, hy_spread_z63, yield_curve_z63], axis=1).dropna()

        if len(kmeans_data) < 3:
            logger.warning(f"Insufficient data for KMeans ({len(kmeans_data)} rows). Skipping KMeans fit.")
            self.kmeans = None
        else:
            self.kmeans = KMeans(n_clusters=3, random_state=42, n_init=10)
            self.kmeans.fit(kmeans_data.values)
            logger.info(f"Fitted KMeans with 3 clusters on {len(kmeans_data)} observations")

        self.is_fitted = True
        logger.info("RegimeDetector fitting complete")

        return self

    def predict(self, macro_df: pd.DataFrame) -> pd.Series:
        """
        Predict regime using rule-based stress scoring.

        Returns regime labels: 0 (bull/low stress), 1 (neutral), 2 (bear/high stress).

        Parameters
        ----------
        macro_df : pd.DataFrame
            Macro data indexed by date.

        Returns
        -------
        pd.Series
            Regime labels indexed by date.
        """
        if not self.is_fitted:
            logger.error("RegimeDetector must be fitted before prediction")
            raise ValueError("RegimeDetector not fitted. Call fit() first.")

        macro_df = macro_df.sort_index()

        # Extract features
        vix = macro_df['vix'] if 'vix' in macro_df.columns else pd.Series(np.nan, index=macro_df.index)
        hy_spread = macro_df['hy_spread'] if 'hy_spread' in macro_df.columns else pd.Series(np.nan, index=macro_df.index)
        yield_curve_10y2y = macro_df['yield_curve_10y2y'] if 'yield_curve_10y2y' in macro_df.columns else pd.Series(np.nan, index=macro_df.index)

        # Normalize using stored rolling stats (align indices)
        vix_mean = self.rolling_stats['vix_mean'].reindex(macro_df.index)
        vix_std = self.rolling_stats['vix_std'].reindex(macro_df.index)
        hy_spread_mean = self.rolling_stats['hy_spread_mean'].reindex(macro_df.index)
        hy_spread_std = self.rolling_stats['hy_spread_std'].reindex(macro_df.index)
        yield_curve_mean = self.rolling_stats['yield_curve_mean'].reindex(macro_df.index)
        yield_curve_std = self.rolling_stats['yield_curve_std'].reindex(macro_df.index)

        vix_z63 = (vix - vix_mean) / (vix_std + 1e-6)
        hy_spread_z63 = (hy_spread - hy_spread_mean) / (hy_spread_std + 1e-6)
        yield_curve_z63 = (yield_curve_10y2y - yield_curve_mean) / (yield_curve_std + 1e-6)

        # Compute stress score: 0.4 * vix_z + 0.4 * hy_spread_z + 0.2 * (-yield_curve_z)
        stress_score = 0.4 * vix_z63 + 0.4 * hy_spread_z63 - 0.2 * yield_curve_z63

        # Classify based on thresholds
        regime = pd.Series(1, index=macro_df.index, dtype=int)  # default neutral
        regime[stress_score < -0.5] = 0  # bull
        regime[stress_score > 0.5] = 2   # bear

        logger.debug(f"Rule-based regime prediction: {regime.value_counts().to_dict()}")

        return regime

    def predict_kmeans(self, macro_df: pd.DataFrame) -> pd.Series:
        """
        Predict regime using KMeans clustering.

        Cluster labels are relabeled so that the cluster with highest mean VIX = regime 2.

        Parameters
        ----------
        macro_df : pd.DataFrame
            Macro data indexed by date.

        Returns
        -------
        pd.Series
            KMeans regime labels (0, 1, 2) indexed by date.
        """
        if not self.is_fitted or self.kmeans is None:
            logger.error("RegimeDetector must be fitted with valid KMeans before KMeans prediction")
            raise ValueError("RegimeDetector not fitted or KMeans not available. Call fit() first.")

        macro_df = macro_df.sort_index()

        # Extract and normalize features
        vix = macro_df['vix'] if 'vix' in macro_df.columns else pd.Series(np.nan, index=macro_df.index)
        hy_spread = macro_df['hy_spread'] if 'hy_spread' in macro_df.columns else pd.Series(np.nan, index=macro_df.index)
        yield_curve_10y2y = macro_df['yield_curve_10y2y'] if 'yield_curve_10y2y' in macro_df.columns else pd.Series(np.nan, index=macro_df.index)

        vix_mean = self.rolling_stats['vix_mean'].reindex(macro_df.index)
        vix_std = self.rolling_stats['vix_std'].reindex(macro_df.index)
        hy_spread_mean = self.rolling_stats['hy_spread_mean'].reindex(macro_df.index)
        hy_spread_std = self.rolling_stats['hy_spread_std'].reindex(macro_df.index)
        yield_curve_mean = self.rolling_stats['yield_curve_mean'].reindex(macro_df.index)
        yield_curve_std = self.rolling_stats['yield_curve_std'].reindex(macro_df.index)

        vix_z63 = (vix - vix_mean) / (vix_std + 1e-6)
        hy_spread_z63 = (hy_spread - hy_spread_mean) / (hy_spread_std + 1e-6)
        yield_curve_z63 = (yield_curve_10y2y - yield_curve_mean) / (yield_curve_std + 1e-6)

        kmeans_data = pd.concat([vix_z63, hy_spread_z63, yield_curve_z63], axis=1)

        # Predict with KMeans
        labels_raw = self.kmeans.predict(kmeans_data.values)
        labels = pd.Series(labels_raw, index=macro_df.index)

        # Relabel so highest VIX cluster = regime 2
        cluster_vix_means = {}
        for cluster_id in range(3):
            cluster_mask = labels == cluster_id
            cluster_vix_means[cluster_id] = vix[cluster_mask].mean()

        # Create mapping from raw cluster IDs to relabeled regimes
        sorted_clusters = sorted(cluster_vix_means.items(), key=lambda x: x[1])
        relabel_map = {sorted_clusters[i][0]: i for i in range(3)}

        labels = labels.map(relabel_map)

        logger.debug(f"KMeans regime prediction: {labels.value_counts().to_dict()}")

        return labels

    def get_current_regime(self, macro_df: pd.DataFrame, use_kmeans: bool = False) -> int:
        """
        Get regime label for the most recent date.

        Parameters
        ----------
        macro_df : pd.DataFrame
            Macro data indexed by date.
        use_kmeans : bool, optional
            If True, use KMeans prediction; else use rule-based prediction.

        Returns
        -------
        int
            Regime label (0, 1, or 2) for the most recent date.
        """
        if use_kmeans:
            regimes = self.predict_kmeans(macro_df)
        else:
            regimes = self.predict(macro_df)

        current_regime = regimes.iloc[-1]
        logger.info(f"Current regime (most recent date): {current_regime}")

        return int(current_regime)

    def regime_exposure_multiplier(self, regime: int) -> float:
        """
        Return portfolio exposure multiplier based on regime.

        Parameters
        ----------
        regime : int
            Regime label (0, 1, or 2).

        Returns
        -------
        float
            Exposure multiplier: 1.0 for bull, 0.75 for neutral, 0.50 for bear.
        """
        de_risk_pct = self.config.get('risk', {}).get('regime_de_risk_pct', 0.50)

        if regime == 0:
            multiplier = 1.0
            label = "bull/low_stress"
        elif regime == 1:
            multiplier = 0.75
            label = "neutral"
        elif regime == 2:
            multiplier = 1.0 - de_risk_pct
            label = "bear/high_stress"
        else:
            logger.warning(f"Unknown regime {regime}, defaulting to neutral (0.75)")
            multiplier = 0.75
            label = "unknown"

        logger.debug(f"Regime {regime} ({label}) -> exposure multiplier {multiplier:.2%}")

        return multiplier

    def plot_regime(self, macro_df: pd.DataFrame, save_path: Optional[str] = None) -> None:
        """
        Plot stress score over time with colored background by regime.

        Parameters
        ----------
        macro_df : pd.DataFrame
            Macro data indexed by date.
        save_path : str, optional
            If provided, save plot to this path. Otherwise display.
        """
        macro_df = macro_df.sort_index()

        # Compute stress score
        vix = macro_df['vix'] if 'vix' in macro_df.columns else pd.Series(np.nan, index=macro_df.index)
        hy_spread = macro_df['hy_spread'] if 'hy_spread' in macro_df.columns else pd.Series(np.nan, index=macro_df.index)
        yield_curve_10y2y = macro_df['yield_curve_10y2y'] if 'yield_curve_10y2y' in macro_df.columns else pd.Series(np.nan, index=macro_df.index)

        vix_mean = self.rolling_stats['vix_mean'].reindex(macro_df.index)
        vix_std = self.rolling_stats['vix_std'].reindex(macro_df.index)
        hy_spread_mean = self.rolling_stats['hy_spread_mean'].reindex(macro_df.index)
        hy_spread_std = self.rolling_stats['hy_spread_std'].reindex(macro_df.index)
        yield_curve_mean = self.rolling_stats['yield_curve_mean'].reindex(macro_df.index)
        yield_curve_std = self.rolling_stats['yield_curve_std'].reindex(macro_df.index)

        vix_z63 = (vix - vix_mean) / (vix_std + 1e-6)
        hy_spread_z63 = (hy_spread - hy_spread_mean) / (hy_spread_std + 1e-6)
        yield_curve_z63 = (yield_curve_10y2y - yield_curve_mean) / (yield_curve_std + 1e-6)

        stress_score = 0.4 * vix_z63 + 0.4 * hy_spread_z63 - 0.2 * yield_curve_z63

        # Get regimes
        regimes = self.predict(macro_df)

        # Create plot
        fig, ax = plt.subplots(figsize=(14, 6))

        # Plot stress score
        ax.plot(macro_df.index, stress_score, color='black', linewidth=1.5, label='Stress Score')
        ax.axhline(y=-0.5, color='gray', linestyle='--', linewidth=1, alpha=0.5)
        ax.axhline(y=0.5, color='gray', linestyle='--', linewidth=1, alpha=0.5)
        ax.axhline(y=0, color='gray', linestyle='-', linewidth=0.5, alpha=0.5)

        # Color background by regime
        colors = {0: 'green', 1: 'yellow', 2: 'red'}
        regime_labels = {0: 'Bull', 1: 'Neutral', 2: 'Bear'}

        for regime_id in [0, 1, 2]:
            regime_dates = regimes[regimes == regime_id].index
            if len(regime_dates) > 0:
                for i in range(len(regime_dates) - 1):
                    ax.axvspan(regime_dates[i], regime_dates[i+1], alpha=0.1, color=colors[regime_id])

        # Legend
        legend_patches = [
            mpatches.Patch(facecolor=colors[0], alpha=0.3, label=regime_labels[0]),
            mpatches.Patch(facecolor=colors[1], alpha=0.3, label=regime_labels[1]),
            mpatches.Patch(facecolor=colors[2], alpha=0.3, label=regime_labels[2]),
        ]
        ax.legend(handles=legend_patches, loc='upper left', fontsize=10)

        ax.set_xlabel('Date', fontsize=11)
        ax.set_ylabel('Stress Score (zscore)', fontsize=11)
        ax.set_title('Market Regime Detection: Stress Score over Time', fontsize=12, fontweight='bold')
        ax.grid(True, alpha=0.2)

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches='tight')
            logger.info(f"Saved regime plot to {save_path}")
        else:
            plt.show()

        plt.close()


def detect_regime(macro_df: pd.DataFrame, config: dict) -> pd.Series:
    """
    Convenience function to detect market regime.

    Fits and predicts regime in one call.

    Parameters
    ----------
    macro_df : pd.DataFrame
        Macro data indexed by date.
    config : dict
        Configuration dictionary.

    Returns
    -------
    pd.Series
        Regime labels indexed by date.
    """
    logger.info("Running convenience detect_regime function...")
    detector = RegimeDetector(config)
    detector.fit(macro_df)
    regimes = detector.predict(macro_df)
    logger.info("Regime detection complete")
    return regimes
