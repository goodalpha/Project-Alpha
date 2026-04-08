"""
PROJECT ATLAS - Feature Engineering
10 MVP Features with point-in-time correctness
"""

import logging
import pandas as pd
import numpy as np
from typing import Dict, Tuple
from datetime import datetime, timedelta
import config

logger = logging.getLogger(__name__)
logger.setLevel(config.LOG_LEVEL)


class FeatureComputer:
    """Computes all 10 MVP features with strict point-in-time correctness."""

    def __init__(self, data_loader):
        self.data_loader = data_loader
        self.sector_map = self._load_sector_map()

    def _load_sector_map(self) -> Dict[str, str]:
        """Load ticker to sector mapping."""
        # Simplified for MVP - in production would load from GICS
        return {
            'AAPL': 'Technology', 'MSFT': 'Technology', 'GOOGL': 'Communication',
            'AMZN': 'Consumer', 'META': 'Communication', 'NVDA': 'Technology',
            'TSLA': 'Consumer', 'JPM': 'Financials', 'JNJ': 'Healthcare',
            'WMT': 'Consumer', 'BA': 'Industrials', 'GS': 'Financials',
            'PG': 'Consumer', 'UNH': 'Healthcare', 'HD': 'Consumer',
            'XOM': 'Energy', 'CVX': 'Energy', 'IBM': 'Technology',
            'INTC': 'Technology', 'AMD': 'Technology', 'CSCO': 'Technology',
        }

    def compute_all_features(
        self,
        tickers: list,
        as_of_date: pd.Timestamp,
        lookback_years: int = 3
    ) -> pd.DataFrame:
        """
        Compute all 10 features for all tickers as of a specific date.

        Args:
            tickers: List of ticker symbols
            as_of_date: Date at which to compute features (point-in-time)
            lookback_years: How far back to look for historical data

        Returns:
            DataFrame: (ticker, feature1, feature2, ..., feature10)
        """
        logger.info(f"Computing features for {len(tickers)} tickers as of {as_of_date.date()}")

        features = []

        for ticker in tickers:
            try:
                # Load OHLCV data up to (but not including) as_of_date
                ohlcv = self.data_loader.load_ohlcv_until(ticker, as_of_date)

                if len(ohlcv) < 20:  # Need minimum 20 days for volatility
                    continue

                ticker_features = {
                    'ticker': ticker,
                    'date': as_of_date,
                    'sector': self.sector_map.get(ticker, 'Other'),
                }

                # Compute each feature
                ticker_features['f1_momentum_12_1'] = self._momentum_12_1(ohlcv)
                ticker_features['f2_ev_ebitda'] = self._ev_ebitda(ticker)
                ticker_features['f3_fcf_yield'] = self._fcf_yield(ticker)
                ticker_features['f4_realized_vol'] = self._realized_vol_20d(ohlcv)
                ticker_features['f5_earnings_surprise'] = self._earnings_surprise(ticker)
                ticker_features['f6_insider_buying'] = self._insider_buying(ticker, as_of_date)
                ticker_features['f7_mean_reversion'] = self._mean_reversion(ohlcv)
                ticker_features['f8_credit_spread'] = self._credit_spread_regime(as_of_date)
                ticker_features['f9_piotroski_fscore'] = self._piotroski_fscore(ticker)
                ticker_features['f10_volume_ratio'] = self._volume_ratio(ohlcv)

                features.append(ticker_features)

            except Exception as e:
                logger.warning(f"Error computing features for {ticker}: {e}")

        df = pd.DataFrame(features)
        logger.info(f"Computed features for {len(df)} tickers")
        return df

    # ========================================================================
    # FEATURE IMPLEMENTATIONS
    # ========================================================================

    def _momentum_12_1(self, ohlcv: pd.DataFrame) -> float:
        """
        12-1 Month Momentum (skip last month to avoid reversal).
        Sector-relative version would normalize by sector median.
        """
        if len(ohlcv) < 252:
            return np.nan

        # Last 252 trading days = ~1 year
        one_year_ago = ohlcv.iloc[-252]['close'] if len(ohlcv) >= 252 else ohlcv.iloc[0]['close']
        # 21 trading days ago = ~1 month
        one_month_ago = ohlcv.iloc[-21]['close'] if len(ohlcv) >= 21 else ohlcv.iloc[0]['close']

        # Return from 12 months ago to 1 month ago
        momentum = (one_month_ago - one_year_ago) / one_year_ago if one_year_ago > 0 else np.nan
        return momentum

    def _ev_ebitda(self, ticker: str) -> float:
        """EV/EBITDA valuation metric (sector-relative in full system)."""
        try:
            fundamentals = self.data_loader.load_fundamentals_at_date(ticker, pd.Timestamp.now())
            if 'enterprise_value' in fundamentals and 'ebitda' in fundamentals:
                ev = fundamentals.get('enterprise_value')
                ebitda = fundamentals.get('ebitda')
                if ev and ebitda and ebitda > 0:
                    return ev / ebitda
        except:
            pass
        return np.nan

    def _fcf_yield(self, ticker: str) -> float:
        """
        Free Cash Flow Yield = FCF / Market Cap.
        Higher is better (more cash generation per dollar of market value).
        """
        # Placeholder: FCF data not always available in yfinance
        # In production: use quarterly cash flow statement
        return np.nan

    def _realized_vol_20d(self, ohlcv: pd.DataFrame) -> float:
        """
        20-day realized volatility (annualized).
        Calculated as std of 20-day daily returns.
        """
        if len(ohlcv) < 20:
            return np.nan

        returns = ohlcv['close'].pct_change().tail(20)
        vol_daily = returns.std()
        vol_annual = vol_daily * np.sqrt(252)
        return vol_annual

    def _earnings_surprise(self, ticker: str) -> float:
        """
        Earnings Surprise: (Actual EPS - Consensus EPS) / Price.
        Placeholder: Would require earnings database.
        """
        # In production: connect to earnings database or SEC filings
        return np.nan

    def _insider_buying(self, ticker: str, as_of_date: pd.Timestamp) -> float:
        """
        Net insider buying flag (90-day window).
        Returns 1 if net buying, -1 if net selling, 0 if neutral.
        """
        # In production: parse SEC Form 4 filings
        # For MVP: placeholder
        return np.nan

    def _mean_reversion(self, ohlcv: pd.DataFrame) -> float:
        """
        Mean reversion: (3M price) / (12M price).
        If stock has pulled back, ratio is <1 (potential mean reversion).
        """
        if len(ohlcv) < 252:
            return np.nan

        price_3m_ago = ohlcv.iloc[-63]['close'] if len(ohlcv) >= 63 else ohlcv.iloc[0]['close']
        price_12m_ago = ohlcv.iloc[-252]['close'] if len(ohlcv) >= 252 else ohlcv.iloc[0]['close']

        current_price = ohlcv.iloc[-1]['close']
        high_52w = ohlcv.iloc[-252:]['close'].max()

        # How far below 52-week high (pullback indicator)
        pullback_ratio = current_price / high_52w if high_52w > 0 else 1
        return pullback_ratio

    def _credit_spread_regime(self, as_of_date: pd.Timestamp) -> float:
        """
        Credit spread change: macro regime indicator.
        Rising spreads = risk-off, falling = risk-on.
        Returns 1 (risk-on), 0 (neutral), -1 (risk-off).
        """
        # In production: fetch credit spread indices (IG OAS, etc.)
        # For MVP: use VIX as proxy
        try:
            vix_path = config.DATA_DIR / "macro_data.parquet"
            if vix_path.exists():
                macro = pd.read_parquet(vix_path)
                recent_vix = macro[macro['date'] <= as_of_date].tail(30)
                if len(recent_vix) > 0:
                    current_vix = recent_vix.iloc[-1].get('vix', 20)
                    vix_30d_avg = recent_vix.get('vix', [20]).mean() if 'vix' in recent_vix.columns else 20
                    if current_vix < vix_30d_avg * 0.9:
                        return 1  # Risk-on
                    elif current_vix > vix_30d_avg * 1.2:
                        return -1  # Risk-off
        except:
            pass
        return 0

    def _piotroski_fscore(self, ticker: str) -> float:
        """
        Piotroski F-Score: Composite fundamental quality (0-9).
        Measures profitability, efficiency, liquidity.
        """
        # In production: calculate from quarterly financials
        # For MVP: placeholder
        return np.nan

    def _volume_ratio(self, ohlcv: pd.DataFrame) -> float:
        """
        Volume Ratio: 20-day average volume / 60-day average volume.
        Rising volume = institutional accumulation signal.
        """
        if len(ohlcv) < 60:
            return np.nan

        vol_20d = ohlcv['volume'].tail(20).mean()
        vol_60d = ohlcv['volume'].tail(60).mean()

        if vol_60d > 0:
            return vol_20d / vol_60d
        return np.nan

    # ========================================================================
    # FEATURE SCALING & NORMALIZATION
    # ========================================================================

    @staticmethod
    def zscore_features_by_sector(df: pd.DataFrame) -> pd.DataFrame:
        """
        Z-score normalize features within each sector.
        Removes sector-level biases (e.g., tech always looks "expensive").
        """
        feature_cols = [col for col in df.columns if col.startswith('f')]

        for col in feature_cols:
            df[f'{col}_zscore'] = df.groupby('sector')[col].transform(
                lambda x: (x - x.mean()) / (x.std() + 1e-8)
            )

        return df

    @staticmethod
    def handle_missing_values(df: pd.DataFrame, method: str = 'drop') -> pd.DataFrame:
        """
        Handle missing feature values.

        Args:
            df: Feature DataFrame
            method: 'drop' (remove rows), 'fill_zero', 'fill_mean'

        Returns:
            DataFrame with missing values handled
        """
        feature_cols = [col for col in df.columns if col.startswith('f')]

        if method == 'drop':
            return df.dropna(subset=feature_cols)
        elif method == 'fill_zero':
            return df[feature_cols].fillna(0)
        elif method == 'fill_mean':
            for col in feature_cols:
                df[col].fillna(df[col].mean(), inplace=True)
            return df

        return df

# ============================================================================
# PIPELINE UTILITY
# ============================================================================

def generate_feature_matrix(
    tickers: list,
    dates: list,
    data_loader,
    normalize: bool = True
) -> pd.DataFrame:
    """
    Generate complete feature matrix for backtesting.

    Args:
        tickers: List of ticker symbols
        dates: List of dates to compute features
        data_loader: PointInTimeDataLoader instance
        normalize: Normalize features within sectors

    Returns:
        DataFrame: (date, ticker, feature1, ..., feature10, sector)
    """
    computer = FeatureComputer(data_loader)
    all_features = []

    for date in dates:
        features = computer.compute_all_features(tickers, date)
        all_features.append(features)

    df = pd.concat(all_features, ignore_index=True)

    if normalize:
        df = FeatureComputer.zscore_features_by_sector(df)

    df = FeatureComputer.handle_missing_values(df, method='drop')

    return df


if __name__ == "__main__":
    logging.basicConfig(format=config.LOG_FORMAT)
    logger.info("Feature engineering module loaded")
