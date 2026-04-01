# Quantitative Trading Framework - Cross-Sectional Equity Backtesting

A pure pandas/numpy quantitative trading framework for cross-sectional equity strategy backtesting.

## Files Created

### 1. Backtest Engine (`src/backtest/engine.py`)
**Purpose**: Vectorized backtesting engine with realistic transaction cost modeling

**Key Classes**:
- `BacktestEngine`: Main backtesting engine
  - `run(predictions, prices, universe, regime_labels)`: Execute full backtest
  - Returns: portfolio_returns, positions, turnover, cost_drag

**Key Functions**:
- `run_backtest()`: Convenience wrapper with macro regime detection

**Features**:
- Weekly rebalancing schedule
- Vol-parity weighting (1/vol normalization)
- Position caps (5% per stock)
- Sector exposure limits (30% per sector)
- Regime-aware multipliers (1.0, 0.75, 0.50)
- Transaction costs:
  - Commission: 0.5 bps per share
  - Slippage: 5 bps
  - Spread: 3 bps
  - Market impact: coefficient × sqrt(turnover)

### 2. Portfolio Constructor (`src/portfolio/constructor.py`)
**Purpose**: Multi-stage portfolio construction pipeline

**Key Classes**:
- `PortfolioConstructor`: Portfolio construction engine
  - `select_stocks()`: Select top N% by signal (supports long/long-short)
  - `compute_vol_parity_weights()`: Inverse volatility weighting
  - `apply_sector_caps()`: Enforce sector concentration limits
  - `scale_to_vol_target()`: Scale weights to 15% annual volatility target
  - `build_portfolio()`: Full pipeline (select → weight → cap → scale)

**Key Functions**:
- `compute_weights()`: Convenience wrapper

**Features**:
- Support for long-only and long-short strategies
- Inverse volatility weighting (robust to zero vol)
- Position-level caps
- Sector-level aggregation and caps
- Target portfolio volatility scaling (15% default)
- Max gross leverage capping (1.0 for long-only)

### 3. Risk Controls (`src/risk/controls.py`)
**Purpose**: Risk monitoring, drawdown tracking, and exposure controls

**Key Classes**:
- `RiskControls`: Risk management engine
  - `update(daily_return)`: Update equity and compute metrics
  - `check_halt()`: Check halt condition (>15% drawdown)
  - `get_exposure_multiplier()`: Return 0.0/0.5/1.0 based on drawdown
  - `earnings_blackout()`: Check stock-specific earnings windows
  - `filter_universe_for_blackout()`: Remove blackout stocks
  - `compute_portfolio_risk_metrics()`: Full risk analysis

**Key Functions**:
- `check_risk_limits()`: Quick constraint validation

**Features**:
- High water mark (HWM) tracking
- Drawdown from peak computation
- Trading halt triggers (>15% drawdown)
- Exposure reduction thresholds (>10% drawdown → 50% exposure)
- Earnings blackout periods (configurable days before)
- Portfolio-level risk metrics:
  - Volatility, Beta, VaR (95%), CVaR (95%), Max Drawdown
- Historical simulation VaR

### 4. Performance Evaluation (`src/evaluation/metrics.py`)
**Purpose**: Comprehensive performance metrics and tearsheet generation

**Key Functions**:
- `compute_sharpe()`: Annualized Sharpe ratio
- `compute_sortino()`: Sortino ratio (downside deviation)
- `compute_max_drawdown()`: Maximum drawdown
- `compute_calmar()`: Calmar ratio (return / |max_dd|)
- `compute_ic_series()`: Pearson IC per date
- `compute_rank_ic_series()`: Spearman rank IC per date
- `compute_turnover()`: Period-by-period turnover
- `compute_hit_rate()`: Directional prediction accuracy

**Key Classes**:
- `PerformanceReport`: Comprehensive analysis class
  - `summary()`: Dict of all key metrics
  - `plot_tearsheet()`: 4-panel visualization
  - `to_dict()` / `to_dataframe()`: Export functionality

**Metrics Computed**:
- Return metrics: annualized return, Sharpe, Sortino, Calmar, max drawdown
- Signal metrics: mean IC, ICIR, mean rank IC, hit rate
- Portfolio metrics: avg turnover, # positions, gross exposure
- Attribution: alpha, beta, information ratio (vs benchmark)

### 5. Module Exports

```python
# Backtest
from src.backtest import BacktestEngine, run_backtest

# Portfolio Construction
from src.portfolio import PortfolioConstructor, compute_weights

# Risk
from src.risk import RiskControls, check_risk_limits

# Evaluation
from src.evaluation import (
    compute_sharpe, compute_sortino, compute_max_drawdown, compute_calmar,
    compute_ic_series, compute_rank_ic_series, compute_turnover, compute_hit_rate,
    PerformanceReport
)
```

## Example Usage

```python
import pandas as pd
from src.backtest import run_backtest
from src.evaluation import PerformanceReport

# Prepare inputs
predictions = pd.DataFrame({  # date, ticker, signal
    'date': [...],
    'ticker': [...],
    'signal': [...]
})

prices_dict = {
    'AAPL': pd.Series([...], index=dates),
    'MSFT': pd.Series([...], index=dates),
    ...
}

universe = pd.DataFrame({  # date, ticker, sector
    'date': [...],
    'ticker': [...],
    'sector': [...]
})

macro_df = pd.DataFrame({  # macro indicators, indexed by date
    'regime': [...],  # 0, 1, 2
    ...
}, index=dates)

config = {
    'portfolio.top_pct': 0.2,  # Top 20%
    'portfolio.max_position_pct': 0.05,  # 5% per stock
    'portfolio.max_sector_pct': 0.30,  # 30% per sector
    'portfolio.target_vol': 0.15,  # 15% annual vol
    'portfolio.rebalance_freq': 'weekly',
    'transaction_costs.commission_per_share': 0.005,
    'transaction_costs.slippage_bps': 5,
    'transaction_costs.spread_bps': 3,
    'transaction_costs.market_impact_coeff': 0.05,
    'risk.vol_lookback': 21,
    'risk.max_drawdown_halt': 0.15,
    'risk.drawdown_reduction': 0.10,
    'risk.reduction_multiplier': 0.50,
}

# Run backtest
results = run_backtest(predictions, prices_dict, universe, macro_df, config)

# Analyze results
portfolio_returns = results['portfolio_returns']
benchmark_returns = results['benchmark_returns']
positions = results['positions']

# Create report
actuals = pd.DataFrame([...])  # Actual forward returns
report = PerformanceReport(
    portfolio_returns, benchmark_returns,
    predictions, actuals, positions, config
)

# View summary
summary = report.summary()
print(f"Sharpe: {summary['sharpe']:.2f}")
print(f"Max DD: {summary['max_drawdown']:.2f}")
print(f"Mean IC: {summary['mean_ic']:.4f}")

# Plot tearsheet
report.plot_tearsheet(save_path='tearsheet.png')
```

## Configuration Reference

### Portfolio Parameters
- `portfolio.top_pct` (float): Fraction of universe in long book (e.g., 0.2)
- `portfolio.bottom_pct` (float): Fraction in short book (long-short only)
- `portfolio.long_short` (bool): Enable long-short strategy
- `portfolio.max_position_pct` (float): Max weight per stock (e.g., 0.05)
- `portfolio.max_sector_pct` (float): Max weight per sector (e.g., 0.30)
- `portfolio.target_vol` (float): Target annual volatility (e.g., 0.15)
- `portfolio.max_gross_leverage` (float): Max gross exposure (e.g., 1.0)
- `portfolio.rebalance_freq` (str): 'weekly' or 'daily'

### Transaction Costs
- `transaction_costs.commission_per_share` (float): Commission per share
- `transaction_costs.slippage_bps` (int): Slippage in basis points
- `transaction_costs.spread_bps` (int): Bid-ask spread in basis points
- `transaction_costs.market_impact_coeff` (float): Market impact coefficient

### Risk Parameters
- `risk.vol_lookback` (int): Days for vol calculation (e.g., 21)
- `risk.max_drawdown_halt` (float): Halt threshold (e.g., 0.15)
- `risk.drawdown_reduction` (float): Reduction threshold (e.g., 0.10)
- `risk.reduction_multiplier` (float): Exposure multiplier when reduced (e.g., 0.50)
- `risk.earnings_blackout_days` (int): Days before earnings to avoid (e.g., 2)
- `risk.regime_multipliers` (dict): {regime_0: 1.0, regime_1: 0.75, regime_2: 0.50}

## Data Input Formats

### Predictions
```python
pd.DataFrame with columns:
- date: pd.Timestamp
- ticker: str
- signal: float (higher = more bullish)
```

### Prices
```python
Dict[ticker: pd.Series] where pd.Series is indexed by date
Alternative: pd.DataFrame indexed by date, columns are tickers
```

### Universe
```python
pd.DataFrame with columns:
- date: pd.Timestamp
- ticker: str
- sector: str
```

### Macro Data
```python
pd.DataFrame indexed by date with columns:
- regime: int (0, 1, 2, etc.)
- ... other macro indicators
```

## Edge Cases Handled

- Empty returns or signals: Returns graceful empty results
- Single-stock portfolios: Supported and handled
- Missing data (NaNs): Properly filtered at computation time
- Zero volatility: Fallback to median vol
- Covariance matrix singularity: Uses diagonal approximation
- Turnover edge cases: Handled with proper alignment and fillna
- Weekend/holiday gaps: Dates properly aligned

## Performance Characteristics

- **Backtesting Speed**: O(n_dates × n_stocks) via vectorized pandas ops
- **Memory Usage**: O(n_dates × n_stocks) for price data
- **Weekly Rebalancing**: Efficient sparse updates between rebalance dates
- **No External Libraries**: Pure pandas/numpy (scipy only for rank correlation)

## Logging

All modules use `loguru` for structured logging. Key events logged:
- Backtest initialization and completion
- Rebalance dates and position construction
- Risk violations and halts
- Sector cap applications
- Transaction cost calculations
- Metric computation warnings

## Output Structure

### Backtest Results
```python
{
    'portfolio_returns': pd.Series,      # Daily log returns
    'positions': pd.DataFrame,           # date x ticker weights
    'turnover': pd.Series,               # Date-indexed turnover
    'cost_drag': pd.Series,              # Date-indexed costs
    'total_cost': float,                 # Total cost fraction
    'rebalance_dates': list,             # Rebalance timestamps
    'benchmark_returns': pd.Series,      # (if SPY available)
}
```

### Performance Summary
```python
{
    'annualized_return': float,
    'sharpe': float,
    'sortino': float,
    'max_drawdown': float,
    'calmar': float,
    'mean_ic': float,
    'icir': float,
    'mean_rank_ic': float,
    'hit_rate': float,
    'avg_turnover': float,
    'avg_num_positions': float,
    'avg_gross_exposure': float,
    'alpha': float,
    'beta': float,
    'information_ratio': float,
}
```

## Notes

1. **Regime Detection**: Macro regime must be pre-computed and passed as regime_labels
2. **Rebalancing**: Fixed weekly (Friday) - modify `_get_rebalance_dates()` for other frequencies
3. **Costs**: Market impact uses square root of turnover (commonly used model)
4. **Vol Scaling**: Uses realized 21-day volatility by default
5. **Sector Limits**: Applied iteratively to handle multiple violators
6. **Position Limits**: Hard cap at max_position_pct before sector aggregation
7. **IC Computation**: Requires predictions and actuals aligned by date and ticker
8. **Benchmark**: Optional, defaults to SPY if available in prices_dict
