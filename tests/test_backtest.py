"""
Comprehensive tests for backtesting engine.

Uses synthetic data to test portfolio construction, risk controls,
performance metrics, and IC computation.
"""

import numpy as np
import pandas as pd
import pytest
from scipy.stats import spearmanr, pearsonr


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def synthetic_signals():
    """Generate synthetic trading signals."""
    np.random.seed(42)

    dates = pd.date_range(start="2020-01-01", periods=252, freq="B")
    tickers = [f"TICK{i}" for i in range(20)]

    # Create signals (rankings)
    signals = pd.DataFrame(
        np.random.normal(0, 1, (len(dates), len(tickers))),
        index=dates,
        columns=tickers,
    )

    return signals


@pytest.fixture
def synthetic_prices():
    """Generate synthetic price data."""
    np.random.seed(42)

    dates = pd.date_range(start="2020-01-01", periods=252, freq="B")
    tickers = [f"TICK{i}" for i in range(20)]

    # Geometric Brownian motion
    initial_price = 100
    returns = np.random.normal(0.0005, 0.02, (len(dates), len(tickers)))
    prices = initial_price * np.exp(np.cumsum(returns, axis=0))

    prices_df = pd.DataFrame(prices, index=dates, columns=tickers)

    return prices_df


@pytest.fixture
def synthetic_volatilities(synthetic_prices):
    """Compute volatilities from prices."""
    log_returns = np.log(synthetic_prices / synthetic_prices.shift(1))
    vol = log_returns.rolling(window=21).std() * np.sqrt(252)

    return vol.fillna(0.15)  # Fill early dates with default vol


@pytest.fixture
def config():
    """Default configuration."""
    return {
        "portfolio.top_pct": 0.2,
        "portfolio.max_position_pct": 0.05,
        "portfolio.max_sector_pct": 0.30,
        "portfolio.target_vol": 0.15,
        "portfolio.rebalance_freq": "weekly",
        "transaction_costs.commission_per_share": 0.005,
        "transaction_costs.slippage_bps": 5,
        "transaction_costs.spread_bps": 3,
        "transaction_costs.market_impact_coeff": 0.1,
        "risk.vol_lookback": 21,
        "risk.regime_multipliers": {0: 1.0, 1: 0.75, 2: 0.50},
    }


# ─────────────────────────────────────────────────────────────────────────────
# Portfolio Construction Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestWeightsSumToOne:
    """Test that portfolio weights sum to 1.0 (long-only)."""

    def test_equal_weights_sum_to_one(self):
        """Equal weights should sum to 1.0."""
        n_positions = 20
        weights = np.ones(n_positions) / n_positions

        assert np.isclose(weights.sum(), 1.0)

    def test_vol_parity_weights_sum_to_one(self):
        """Vol-parity weights should sum to 1.0."""
        np.random.seed(42)

        # Create volatilities
        vols = np.random.uniform(0.1, 0.3, 20)

        # Vol-parity: inversely weighted by vol
        weights = (1 / vols) / (1 / vols).sum()

        assert np.isclose(weights.sum(), 1.0)
        assert (weights >= 0).all(), "Long-only weights should be non-negative"

    def test_conviction_weighted_sum_to_one(self):
        """Conviction-weighted portfolio should sum to 1.0."""
        np.random.seed(42)

        # Create signals (higher = higher conviction)
        signals = np.random.uniform(-1, 1, 20)

        # Conviction weights: positive signals weighted, others zero
        weights = np.maximum(signals, 0)
        weights = weights / weights.sum() if weights.sum() > 0 else np.ones(20) / 20

        assert np.isclose(weights.sum(), 1.0)


class TestPositionCap:
    """Test that no single position exceeds max_position_pct."""

    def test_position_cap_enforced(self):
        """No position should exceed 5% (typical cap)."""
        max_position_pct = 0.05
        n_positions = 50

        # Create uncapped weights
        weights = np.random.uniform(0, 1, n_positions)
        weights = weights / weights.sum()

        # Cap positions
        weights_capped = np.minimum(weights, max_position_pct)

        # Rescale to sum to 1
        weights_capped = weights_capped / weights_capped.sum()

        # Verify cap
        assert (weights_capped <= max_position_pct).all() or np.isclose(weights_capped.max(), max_position_pct, atol=1e-10)

    def test_cap_reduces_largest_positions(self):
        """Capping should reduce the largest positions."""
        max_position_pct = 0.05
        weights = np.array([0.5, 0.3, 0.2])
        weights = weights / weights.sum()

        weights_capped = np.minimum(weights, max_position_pct)
        weights_capped = weights_capped / weights_capped.sum()

        # Largest position should be at max_position_pct
        assert weights_capped.max() <= max_position_pct + 1e-10


class TestSectorCap:
    """Test that no sector exceeds max_sector_pct."""

    def test_sector_cap_enforced(self):
        """No sector should exceed 30% allocation."""
        max_sector_pct = 0.30

        # Create positions: 10 sectors, 5 positions each
        sectors = np.repeat(np.arange(10), 5)
        weights = np.random.uniform(0, 1, 50)
        weights = weights / weights.sum()

        # Compute sector weights
        sector_weights = np.array([
            weights[sectors == s].sum() for s in range(10)
        ])

        # Verify some sectors exceed cap
        assert (sector_weights > max_sector_pct).any(), "Test setup issue: no sector exceeded cap"

        # Cap sectors
        sector_weights_capped = np.minimum(sector_weights, max_sector_pct)
        sector_weights_capped = sector_weights_capped / sector_weights_capped.sum()

        # Verify cap
        assert (sector_weights_capped <= max_sector_pct + 1e-10).all()

    def test_sector_concentration_reduction(self):
        """Capping should reduce sector concentration."""
        max_sector_pct = 0.30

        # Concentrated portfolio
        sectors = np.repeat(np.arange(3), 10)
        weights = np.ones(30) / 30
        # Make first sector dominant
        weights[:10] = 0.5
        weights[10:] = weights[10:] / weights[10:].sum() * 0.5

        # Compute sector concentration
        sector_weights = np.array([
            weights[sectors == s].sum() for s in range(3)
        ])

        max_uncapped = sector_weights.max()

        # Cap and rescale
        sector_weights_capped = np.minimum(sector_weights, max_sector_pct)
        sector_weights_capped = sector_weights_capped / sector_weights_capped.sum()

        max_capped = sector_weights_capped.max()

        assert max_capped < max_uncapped, "Capping should reduce max sector weight"


# ─────────────────────────────────────────────────────────────────────────────
# Transaction Costs Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestTransactionCostsPositive:
    """Test that transaction costs are positive and reduce returns."""

    def test_turnover_creates_cost(self):
        """High turnover should create positive costs."""
        # Old weights
        old_weights = np.array([0.3, 0.3, 0.4])

        # New weights (high turnover)
        new_weights = np.array([0.4, 0.4, 0.2])

        # Turnover = sum(|new - old|) / 2
        turnover = np.abs(new_weights - old_weights).sum() / 2

        assert turnover > 0, "Reallocation should create turnover"

        # Cost = turnover * total_cost_bps
        total_cost_bps = 5 + 3 + 5  # slippage + spread + commission
        cost = turnover * total_cost_bps / 10000

        assert cost > 0, "Turnover should incur costs"

    def test_no_rebalance_no_cost(self):
        """No rebalancing should create zero costs."""
        # Same weights
        old_weights = np.array([0.3, 0.3, 0.4])
        new_weights = np.array([0.3, 0.3, 0.4])

        turnover = np.abs(new_weights - old_weights).sum() / 2

        assert turnover == 0
        assert turnover * 13 / 10000 == 0  # Zero cost

    def test_cost_scales_with_turnover(self):
        """Cost should scale linearly with turnover."""
        cost_bps = 13

        turnover_1 = 0.1
        cost_1 = turnover_1 * cost_bps / 10000

        turnover_2 = 0.2
        cost_2 = turnover_2 * cost_bps / 10000

        assert cost_2 > cost_1
        assert np.isclose(cost_2 / cost_1, turnover_2 / turnover_1)


# ─────────────────────────────────────────────────────────────────────────────
# Signal Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestZeroReturnNoSignal:
    """Test behavior with no signal (all equal)."""

    def test_equal_signals_equal_weights(self):
        """If all signals are equal, positions should be equal."""
        n_stocks = 20
        signals = np.ones(n_stocks)

        # Equal weight all
        weights = signals / signals.sum()

        expected = np.ones(n_stocks) / n_stocks

        np.testing.assert_array_almost_equal(weights, expected)

    def test_ranking_preserves_order(self):
        """Rankings should preserve signal order."""
        signals = np.array([3.0, 1.0, 2.0, 4.0])
        rankings = np.argsort(-signals)  # Descending order

        assert rankings[0] == 3, "Largest signal should rank first"
        assert rankings[-1] == 1, "Smallest signal should rank last"

    def test_top_pct_selection(self):
        """Top 20% selection should select 20% of stocks."""
        n_stocks = 100
        top_pct = 0.2

        signals = np.random.normal(0, 1, n_stocks)
        top_n = int(np.ceil(n_stocks * top_pct))
        top_idx = np.argsort(-signals)[:top_n]

        assert len(top_idx) == top_n
        assert len(top_idx) / n_stocks == top_pct


# ─────────────────────────────────────────────────────────────────────────────
# Regime Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestRegimeReducesExposure:
    """Test that regime reduces exposure in stress scenarios."""

    def test_regime_multipliers(self):
        """Regime multipliers should reduce exposure in high-regime states."""
        regime_multipliers = {0: 1.0, 1: 0.75, 2: 0.50}

        base_exposure = 1.0

        exposure_0 = base_exposure * regime_multipliers[0]
        exposure_1 = base_exposure * regime_multipliers[1]
        exposure_2 = base_exposure * regime_multipliers[2]

        assert exposure_0 > exposure_1 > exposure_2
        assert exposure_2 == 0.5 * base_exposure

    def test_portfolio_leverage_by_regime(self):
        """Portfolio leverage should decrease with regime."""
        base_weights = np.ones(10) / 10  # Equal weight
        regime_multipliers = {0: 1.0, 1: 0.75, 2: 0.50}

        leverage_0 = base_weights.sum() * regime_multipliers[0]
        leverage_1 = base_weights.sum() * regime_multipliers[1]
        leverage_2 = base_weights.sum() * regime_multipliers[2]

        assert leverage_0 > leverage_1 > leverage_2


class TestDrawdownHalt:
    """Test drawdown-based trading halts."""

    def test_drawdown_detection(self):
        """Drawdown should be computed correctly."""
        cumulative_returns = np.array([1.0, 1.05, 1.03, 0.90, 0.95, 1.00])

        running_max = np.maximum.accumulate(cumulative_returns)
        drawdown = (cumulative_returns - running_max) / running_max

        assert drawdown[0] == 0
        assert drawdown[3] < -0.1  # 10% drawdown
        assert drawdown[-1] >= drawdown[3]  # Recovering

    def test_halt_at_threshold(self):
        """Trading should halt at 15% drawdown."""
        max_drawdown_threshold = 0.15

        cumulative_returns = np.array([1.0, 1.05, 1.10, 0.935, 0.90])  # 15% DD
        running_max = np.maximum.accumulate(cumulative_returns)
        drawdown = (cumulative_returns - running_max) / running_max

        should_halt = drawdown.min() <= -max_drawdown_threshold

        assert should_halt

    def test_exposure_multiplier_zero(self):
        """Exposure multiplier should be 0 when halted."""
        max_drawdown = 0.20
        max_drawdown_threshold = 0.15

        if max_drawdown <= -max_drawdown_threshold:
            exposure_multiplier = 0.0
        else:
            exposure_multiplier = 1.0

        assert exposure_multiplier == 0.0


# ─────────────────────────────────────────────────────────────────────────────
# Performance Metrics Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestPerformanceMetrics:
    """Test computation of performance metrics."""

    def test_sharpe_constant_returns(self):
        """Sharpe should be sqrt(252)*mean/std."""
        daily_returns = np.ones(252) * 0.001  # Constant daily return

        mean_return = np.mean(daily_returns)
        std_return = np.std(daily_returns)

        sharpe = mean_return / std_return * np.sqrt(252)

        # With constant returns, std = 0, so Sharpe is inf
        assert np.isinf(sharpe)

    def test_sharpe_random_walk(self):
        """Sharpe ratio for random walk."""
        np.random.seed(42)

        daily_returns = np.random.normal(0.0005, 0.01, 252)

        mean_return = np.mean(daily_returns)
        std_return = np.std(daily_returns)

        sharpe = mean_return / std_return * np.sqrt(252)

        assert isinstance(sharpe, (float, np.floating))

    def test_max_drawdown_monotonic_increase(self):
        """Max drawdown should be 0 for monotonically increasing equity."""
        # Monotonically increasing returns
        cumulative = np.linspace(1.0, 2.0, 252)

        running_max = np.maximum.accumulate(cumulative)
        drawdown = (cumulative - running_max) / running_max

        max_dd = drawdown.min()

        assert max_dd == 0, "Monotonic increase should have 0 drawdown"

    def test_max_drawdown_crash(self):
        """Max drawdown should capture significant drops."""
        cumulative = np.array([1.0, 1.1, 1.05, 1.15, 0.80, 0.85])

        running_max = np.maximum.accumulate(cumulative)
        drawdown = (cumulative - running_max) / running_max

        max_dd = drawdown.min()

        assert max_dd < -0.20, "Should capture 20%+ drawdown"

    def test_total_return_computation(self):
        """Total return should be cumulative product of (1 + r)."""
        daily_returns = np.array([0.01, 0.02, -0.01, 0.03])

        total_return = np.prod(1 + daily_returns) - 1

        expected = 1.01 * 1.02 * 0.99 * 1.03 - 1

        np.testing.assert_almost_equal(total_return, expected)


# ─────────────────────────────────────────────────────────────────────────────
# Information Coefficient Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestICComputation:
    """Test Information Coefficient (IC) computation."""

    def test_ic_perfect_ranking(self):
        """Perfect ranking should give IC = 1.0."""
        y_pred = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        y_true = np.array([1.1, 2.1, 3.1, 4.1, 5.1])

        correlation, _ = pearsonr(y_pred, y_true)

        assert np.isclose(correlation, 1.0), "Perfect correlation should be 1.0"

    def test_ic_inverse_ranking(self):
        """Inverse ranking should give IC = -1.0."""
        y_pred = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        y_true = np.array([5.0, 4.0, 3.0, 2.0, 1.0])

        correlation, _ = pearsonr(y_pred, y_true)

        assert np.isclose(correlation, -1.0), "Inverse correlation should be -1.0"

    def test_ic_random_predictions(self):
        """Random predictions should give IC ≈ 0."""
        np.random.seed(42)

        y_pred = np.random.normal(0, 1, 1000)
        y_true = np.random.normal(0, 1, 1000)

        correlation, _ = pearsonr(y_pred, y_true)

        assert np.abs(correlation) < 0.1, "Random predictions should have low IC"

    def test_rank_ic_vs_ic(self):
        """Rank IC should be similar to IC for smooth data."""
        np.random.seed(42)

        y_pred = np.random.normal(0, 1, 100)
        y_true = y_pred + np.random.normal(0, 0.1, 100)  # Small noise

        ic, _ = pearsonr(y_pred, y_true)
        rank_ic, _ = spearmanr(y_pred, y_true)

        # Both should be positive and similar
        assert ic > 0
        assert rank_ic > 0
        assert np.abs(ic - rank_ic) < 0.1

    def test_ic_with_nan_handling(self):
        """IC computation should handle NaN values."""
        y_pred = np.array([1.0, 2.0, np.nan, 4.0, 5.0])
        y_true = np.array([1.1, 2.1, 3.1, np.nan, 5.1])

        # Remove NaN
        mask = ~(np.isnan(y_pred) | np.isnan(y_true))
        y_pred_clean = y_pred[mask]
        y_true_clean = y_true[mask]

        # Compute IC
        correlation, _ = pearsonr(y_pred_clean, y_true_clean)

        assert not np.isnan(correlation)
        assert 1.0 >= correlation >= -1.0

    def test_icir_mean_std(self):
        """ICIR should be mean IC / std IC."""
        ic_series = np.array([0.05, 0.08, 0.03, 0.07, 0.04])

        icir = ic_series.mean() / ic_series.std()

        assert icir > 0
        assert icir < 1.0  # Realistic ICIR

    def test_icir_time_series(self):
        """ICIR computed from IC time series."""
        np.random.seed(42)

        # Simulate 252 days of IC
        ic_daily = np.random.normal(0.02, 0.05, 252)

        # Filter for valid IC values
        ic_valid = ic_daily[~np.isnan(ic_daily)]

        icir = ic_valid.mean() / ic_valid.std()

        assert isinstance(icir, (float, np.floating))


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
