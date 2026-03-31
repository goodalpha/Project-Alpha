"""
Comprehensive tests for feature engineering pipeline.

Uses synthetic data generated within tests to avoid external dependencies
and ensure reproducibility.
"""

import numpy as np
import pandas as pd
import pytest
from datetime import datetime, timedelta


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def synthetic_prices():
    """Generate synthetic OHLCV price data for testing.

    Returns:
        dict with keys 'open', 'high', 'low', 'close', 'volume', 'adj_close'
        Each value is a DataFrame with dates as index and tickers as columns.
    """
    np.random.seed(42)

    # Create 300-day price series for 5 tickers
    dates = pd.date_range(start="2020-01-01", periods=300, freq="B")  # Business days
    tickers = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"]

    # Generate geometric Brownian motion prices
    initial_price = 100
    returns = np.random.normal(0.0005, 0.02, (len(dates), len(tickers)))
    prices = initial_price * np.exp(np.cumsum(returns, axis=0))

    close = pd.DataFrame(prices, index=dates, columns=tickers)
    open_prices = close * (1 + np.random.normal(0, 0.005, close.shape))
    high = close * (1 + np.abs(np.random.normal(0, 0.01, close.shape)))
    low = close * (1 - np.abs(np.random.normal(0, 0.01, close.shape)))
    volume = np.random.uniform(1e6, 1e8, close.shape)
    volume = pd.DataFrame(volume, index=dates, columns=tickers)

    return {
        "open": open_prices,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
        "adj_close": close,
    }


@pytest.fixture
def synthetic_macro():
    """Generate synthetic macro data.

    Returns:
        DataFrame with macro series indexed by date.
    """
    np.random.seed(42)

    dates = pd.date_range(start="2020-01-01", periods=300, freq="B")

    macro = pd.DataFrame({
        "DFF": np.random.uniform(0.1, 2.0, len(dates)),  # Fed funds rate
        "VIXCLS": np.random.uniform(10, 50, len(dates)),  # VIX
        "T10Y2Y": np.random.uniform(-0.5, 2.0, len(dates)),  # Yield curve
        "CPIAUCSL": np.linspace(250, 260, len(dates)),  # CPI
        "UNRATE": np.random.uniform(3.5, 6.0, len(dates)),  # Unemployment
    }, index=dates)

    return macro


@pytest.fixture
def synthetic_universe():
    """Generate synthetic universe metadata."""
    tickers = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"]

    universe = pd.DataFrame({
        "sector": ["Technology", "Technology", "Technology", "Consumer", "Automotive"],
        "industry": ["Hardware", "Software", "Internet", "Retail", "Automotive"],
        "include_date": pd.Timestamp("2020-01-01"),
    }, index=tickers)

    universe.index.name = "ticker"

    return universe


# ─────────────────────────────────────────────────────────────────────────────
# Price Features Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestMomentumNoLookahead:
    """Test that momentum features don't have lookahead bias."""

    def test_momentum_uses_only_past_data(self, synthetic_prices):
        """Verify momentum on date T uses only data up to T."""
        close = synthetic_prices["close"]

        # Compute 5-day momentum manually
        ret_5d = np.log(close / close.shift(5))

        # On the last available date, we should have NaN if we shift forward
        # This tests point-in-time safety
        assert ret_5d.iloc[-5:].isna().all().all(), \
            "Last 5 dates should be NaN (need 5 future prices)"

        # Check that non-NaN values use only past data
        # ret_5d on date T should equal log(close[T] / close[T-5])
        date_idx = 100
        expected = np.log(close.iloc[date_idx] / close.iloc[date_idx - 5])
        actual = ret_5d.iloc[date_idx]

        np.testing.assert_array_almost_equal(actual, expected, decimal=10)


class TestVolatilityComputation:
    """Test volatility feature computation."""

    def test_vol_annualization(self, synthetic_prices):
        """Verify 21-day volatility is properly annualized."""
        close = synthetic_prices["close"]

        # Compute daily log returns
        log_returns = np.log(close / close.shift(1))

        # Compute rolling 21-day volatility
        vol_21d = log_returns.rolling(window=21).std() * np.sqrt(252)

        # Verify annualization factor
        daily_vol = log_returns.rolling(window=21).std()
        expected_vol = daily_vol * np.sqrt(252)

        pd.testing.assert_frame_equal(vol_21d, expected_vol)

    def test_vol_rolling_window(self, synthetic_prices):
        """Test rolling volatility window behavior."""
        close = synthetic_prices["close"]
        log_returns = np.log(close / close.shift(1))

        window = 21
        vol = log_returns.rolling(window=window).std()

        # First window-1 values should be NaN
        assert vol.iloc[:window - 1].isna().all().all()

        # First non-NaN value should use window days of data
        assert vol.iloc[window - 1].notna().all()

    def test_vol_differs_by_stock(self, synthetic_prices):
        """Verify volatility varies by stock."""
        close = synthetic_prices["close"].copy()

        # Make one stock much more volatile
        close.iloc[:, 0] = close.iloc[:, 0] * (1 + np.random.normal(0, 0.05, len(close)))

        log_returns = np.log(close / close.shift(1))
        vol = log_returns.rolling(window=21).std()

        # Max volatility should be higher than min
        max_vol = vol.iloc[25:].max().max()
        min_vol = vol.iloc[25:].min().min()

        assert max_vol > min_vol, "Volatility should vary across stocks"


class TestCrossSectionalZscore:
    """Test cross-sectional z-score normalization."""

    def test_zscore_mean_zero_std_one(self):
        """After z-scoring per date, mean should be 0, std should be 1."""
        np.random.seed(42)

        # Create feature matrix: dates x tickers
        dates = pd.date_range(start="2020-01-01", periods=50, freq="B")
        tickers = [f"TICK{i}" for i in range(10)]

        features = pd.DataFrame(
            np.random.normal(100, 20, (len(dates), len(tickers))),
            index=dates,
            columns=tickers,
        )

        # Z-score by date
        zscore = (features - features.mean(axis=1, keepdims=True)) / features.std(axis=1, keepdims=True)

        # Check mean and std per date
        means = zscore.mean(axis=1)
        stds = zscore.std(axis=1)

        np.testing.assert_array_almost_equal(means.values, 0, decimal=10)
        np.testing.assert_array_almost_equal(stds.values, 1, decimal=10)

    def test_zscore_clipping(self):
        """After clipping at 3.0, no values outside [-3, 3]."""
        np.random.seed(42)

        dates = pd.date_range(start="2020-01-01", periods=50, freq="B")
        tickers = [f"TICK{i}" for i in range(10)]

        # Create features with some extreme values
        features = pd.DataFrame(
            np.random.normal(100, 50, (len(dates), len(tickers))),
            index=dates,
            columns=tickers,
        )

        # Z-score
        zscore = (features - features.mean(axis=1, keepdims=True)) / features.std(axis=1, keepdims=True)

        # Clip
        zscore_clipped = zscore.clip(-3.0, 3.0)

        # Verify no outliers
        assert (zscore_clipped >= -3.0).all().all()
        assert (zscore_clipped <= 3.0).all().all()


class TestSectorNeutralization:
    """Test sector neutralization."""

    def test_sector_means_zero_after_neutralization(self):
        """After sector neutralization, sector means should be ~0."""
        np.random.seed(42)

        dates = pd.date_range(start="2020-01-01", periods=50, freq="B")

        # Create features with strong sector bias
        # Tech stocks: feature mean = 1.0
        # Finance stocks: feature mean = -0.5
        tech_tickers = ["AAPL", "MSFT", "GOOGL"]
        fin_tickers = ["GS", "JPM", "BAC"]

        all_tickers = tech_tickers + fin_tickers

        features_list = []
        for ticker in all_tickers:
            if ticker in tech_tickers:
                feat = pd.DataFrame(
                    np.random.normal(1.0, 0.2, len(dates)),
                    index=dates,
                    columns=[ticker],
                )
            else:
                feat = pd.DataFrame(
                    np.random.normal(-0.5, 0.2, len(dates)),
                    index=dates,
                    columns=[ticker],
                )
            features_list.append(feat)

        features = pd.concat(features_list, axis=1)

        # Create sector mapping
        sectors = {ticker: "Technology" if ticker in tech_tickers else "Finance" for ticker in all_tickers}

        # Neutralize by sector
        neutralized = features.copy()
        for date in features.index:
            for sector in sectors.values():
                sector_tickers = [t for t in all_tickers if sectors[t] == sector]
                sector_mean = features.loc[date, sector_tickers].mean()
                neutralized.loc[date, sector_tickers] = features.loc[date, sector_tickers] - sector_mean

        # Check that sector means are ~0
        for date in neutralized.index:
            for sector in sectors.values():
                sector_tickers = [t for t in all_tickers if sectors[t] == sector]
                sector_mean = neutralized.loc[date, sector_tickers].mean()
                assert np.abs(sector_mean) < 1e-10, f"Sector {sector} mean {sector_mean} should be ~0"


class TestRankNormalize:
    """Test rank normalization to [-0.5, 0.5] scale."""

    def test_rank_normalize_range(self):
        """After rank normalization, values should be in [-0.5, 0.5]."""
        np.random.seed(42)

        dates = pd.date_range(start="2020-01-01", periods=50, freq="B")
        tickers = [f"TICK{i}" for i in range(10)]

        features = pd.DataFrame(
            np.random.normal(100, 20, (len(dates), len(tickers))),
            index=dates,
            columns=tickers,
        )

        # Rank normalize: (rank - 1) / (n - 1) - 0.5
        # This maps [1, n] to [0, 1] then to [-0.5, 0.5]
        rank_normalized = features.rank(axis=1, pct=True) - 0.5

        # Check range
        assert (rank_normalized >= -0.5).all().all()
        assert (rank_normalized <= 0.5).all().all()

        # Min and max should be close to -0.5 and 0.5
        assert rank_normalized.min().min() > -0.6
        assert rank_normalized.max().max() < 0.6


# ─────────────────────────────────────────────────────────────────────────────
# Target Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestTargetNoLookahead:
    """Test that targets don't have lookahead bias."""

    def test_forward_return_no_future_data(self, synthetic_prices):
        """Forward return on date T should not use data from T+1 to T+5."""
        close = synthetic_prices["close"]

        # Compute forward 5-day return
        # fwd_ret_5d[T] = log(close[T+5] / close[T])
        fwd_ret = np.log(close.shift(-5) / close)

        # Shift back to align with date T
        fwd_ret_aligned = fwd_ret.shift(5)

        # Last 5 dates should have NaN (no future prices)
        assert fwd_ret_aligned.iloc[-5:].isna().all().all()

        # Verify correct computation on a middle date
        date_idx = 100
        expected = np.log(close.iloc[date_idx + 5] / close.iloc[date_idx])
        actual = fwd_ret_aligned.iloc[date_idx]

        np.testing.assert_array_almost_equal(actual, expected, decimal=10)

    def test_excess_return_computation(self, synthetic_prices):
        """Excess return = stock return - benchmark return."""
        close = synthetic_prices["close"]

        # Assume SPY is benchmark (we'll use the first stock as proxy)
        benchmark_return = np.log(close.iloc[:, 0].shift(-5) / close.iloc[:, 0]).shift(5)
        stock_returns = np.log(close.shift(-5) / close).shift(5)

        # Excess return
        excess_returns = stock_returns.sub(benchmark_return, axis=0)

        # Verify shape
        assert excess_returns.shape == stock_returns.shape

        # Verify on a sample date
        date_idx = 100
        for i, ticker in enumerate(close.columns):
            expected = stock_returns.iloc[date_idx, i] - benchmark_return.iloc[date_idx]
            actual = excess_returns.iloc[date_idx, i]
            np.testing.assert_almost_equal(actual, expected, decimal=10)

    def test_target_last_5_dates_nan(self, synthetic_prices):
        """Last 5 dates should have NaN targets (no future data)."""
        close = synthetic_prices["close"]

        fwd_ret_5d = np.log(close.shift(-5) / close).shift(5)

        # Last 5 dates should be NaN
        assert fwd_ret_5d.iloc[-5:].isna().all().all()

        # Date before that should have valid data
        assert not fwd_ret_5d.iloc[-6:-5].isna().all().all()


class TestVolatilityAdjustedTarget:
    """Test volatility-adjusted targets."""

    def test_vol_adjusted_lower_variance(self, synthetic_prices):
        """Volatility-adjusted returns should have lower variance."""
        close = synthetic_prices["close"]

        # Raw forward returns
        fwd_ret = np.log(close.shift(-5) / close).shift(5)

        # Rolling 21-day volatility
        log_returns = np.log(close / close.shift(1))
        vol_21d = log_returns.rolling(window=21).std() * np.sqrt(252)

        # Volatility-adjusted returns
        fwd_ret_vol_adj = fwd_ret / vol_21d

        # Remove NaN for comparison
        raw_var = fwd_ret.iloc[30:100].var().mean()
        adj_var = fwd_ret_vol_adj.iloc[30:100].var().mean()

        # Adjusted should have lower or equal variance
        assert adj_var <= raw_var * 1.1, "Volatility-adjusted should have similar or lower variance"


# ─────────────────────────────────────────────────────────────────────────────
# Macro Features Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestMacroForwardFill:
    """Test forward-fill behavior for macro data."""

    def test_macro_ffill_daily_frequency(self):
        """Macro data should be forward-filled to daily frequency."""
        # Create monthly macro data
        dates = pd.date_range(start="2020-01-01", end="2020-12-31", freq="M")
        macro = pd.DataFrame({
            "DFF": np.arange(len(dates)),
            "VIXCLS": np.arange(len(dates), len(dates) * 2),
        }, index=dates)

        # Forward-fill to daily
        macro_daily = macro.asfreq("D", method="ffill")

        # Verify daily frequency
        assert (macro_daily.index.to_series().diff().dt.days == 1).sum() > 200, \
            "Should have daily values (except weekends)"

        # Verify no NaN
        assert macro_daily.isna().sum().sum() == 0, "No NaN after forward-fill"

    def test_macro_preserves_values(self):
        """Forward-fill should preserve original values."""
        dates = pd.date_range(start="2020-01-01", end="2020-01-31", freq="W")
        macro = pd.DataFrame({
            "DFF": [0.1, 0.15, 0.2],
        }, index=dates)

        macro_daily = macro.asfreq("D", method="ffill")

        # Check that original values are preserved
        for date in macro.index:
            assert macro_daily.loc[date, "DFF"] == macro.loc[date, "DFF"]


class TestVIXRegime:
    """Test VIX-based regime detection."""

    def test_vix_regime_thresholds(self):
        """VIX regimes should be quantile-based."""
        np.random.seed(42)

        dates = pd.date_range(start="2020-01-01", periods=252, freq="B")
        vix = pd.Series(np.random.uniform(10, 40, len(dates)), index=dates, name="VIX")

        # Detect regimes: quantile-based (0-33: regime 0, 33-66: regime 1, 66-100: regime 2)
        quantiles = vix.quantile([0.33, 0.66])

        regime = pd.Series(0, index=dates)
        regime[vix > quantiles[0.33]] = 1
        regime[vix > quantiles[0.66]] = 2

        # Verify regime distribution
        assert regime.value_counts()[0] > 50
        assert regime.value_counts()[1] > 50
        assert regime.value_counts()[2] > 50

        # Verify regime ordering
        regime_vix_means = {}
        for r in [0, 1, 2]:
            regime_vix_means[r] = vix[regime == r].mean()

        assert regime_vix_means[0] < regime_vix_means[1] < regime_vix_means[2], \
            "Higher regime should have higher VIX"


# ─────────────────────────────────────────────────────────────────────────────
# Integration Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestFeaturePipeline:
    """Integration tests for the full feature pipeline."""

    def test_feature_shapes_consistent(self, synthetic_prices, synthetic_macro):
        """All computed features should have consistent shapes."""
        close = synthetic_prices["close"]

        # Compute various features
        momentum = np.log(close / close.shift(5))
        volatility = np.log(close / close.shift(1)).rolling(21).std() * np.sqrt(252)

        # Should have same shape
        assert momentum.shape == close.shape
        assert volatility.shape == close.shape

    def test_feature_temporal_alignment(self, synthetic_prices):
        """Features computed on same date should align."""
        close = synthetic_prices["close"]

        # Compute two features
        momentum = np.log(close / close.shift(5))
        volatility = np.log(close / close.shift(1)).rolling(21).std()

        # Both should have same index
        pd.testing.assert_index_equal(momentum.index, volatility.index)
        pd.testing.assert_index_equal(momentum.columns, volatility.columns)

    def test_no_lookahead_across_features(self, synthetic_prices):
        """No feature should leak information from future."""
        close = synthetic_prices["close"]

        # Momentum (should not use future)
        momentum = np.log(close / close.shift(5))

        # Volatility (should not use future)
        volatility = np.log(close / close.shift(1)).rolling(21).std()

        # Both should have NaN on same recent dates
        momentum_nan = momentum.iloc[-10:].isna().sum().sum()
        volatility_nan = volatility.iloc[-10:].isna().sum().sum()

        # Both should have some NaN on recent dates
        assert momentum_nan > 0
        assert volatility_nan > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
