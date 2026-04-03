# Project ATLAS — Autonomous Trading & Learning Alpha System

**An institutional-grade trading system blueprint with a 30-day MVP implementation.**

## Overview

Project ATLAS is a complete blueprint for building an automated trading system from first principles. It combines:

- **Quantitative Research** (10 battle-tested factors)
- **Machine Learning** (XGBoost for daily rebalancing)
- **Risk Management** (5-layer protection architecture)
- **Execution** (transaction cost modeling)
- **Backtesting** (walk-forward validation with point-in-time correctness)

## Project Structure

```
Project-Alpha/
├── config.py                 # Configuration & constants
├── data_ingestion.py         # Data fetching (yfinance, FRED, SEC)
├── features.py               # 10 MVP features with z-scoring
├── model.py                  # XGBoost classifier
├── backtest.py               # Walk-forward backtesting engine
├── risk.py                   # 5-layer risk management
├── execution.py              # Order generation & execution
├── main.py                   # Orchestration & 30-day plan
├── requirements.txt          # Python dependencies
├── data/                     # OHLCV, macro, fundamental data
├── features/                 # Computed features
├── models/                   # Trained XGBoost models
├── backtest/                 # Backtest results
└── logs/                     # System logs
```

## 30-Day MVP Build Plan

### **Days 1–3: Foundation**
- [x] Set up project structure with proper directories
- [x] Build data ingestion for S&P 500 (yfinance, FRED)
- [x] Implement point-in-time join utility

### **Days 4–7: Features**
- [x] Implement 10 MVP features (momentum, valuation, quality, macro)
- [x] Z-score normalization within sectors
- [x] Feature validation and EDA

### **Days 8–14: Model & Backtest**
- [x] Train XGBoost classifier on 3-year data
- [x] Target: top quintile vs rest (binary classification)
- [x] Walk-forward backtesting engine
- [x] Include realistic transaction costs (10 bps)

### **Days 15–20: Stress Testing**
- [x] Parameter sensitivity analysis
- [x] Feature ablation tests
- [x] Double slippage assumptions
- [x] Year-by-year breakdown

### **Days 21–25: Production Pipeline**
- [x] Convert notebooks to production Python scripts
- [x] Daily pipeline: fetch → features → predict → signal
- [x] Alpaca paper trading integration (ready)

### **Days 26–30: Risk & Monitoring**
- [x] Implement risk controls (position, sector, portfolio limits)
- [x] Data staleness detection
- [x] Alert system (email/Telegram ready)
- [x] Documentation & runbook

## Installation & Setup

### 1. Clone Repository
```bash
cd /home/user/Project-Alpha
```

### 2. Create Virtual Environment
```bash
python3.11 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure & Run
```bash
python main.py
```

This will:
1. Download 3 years of S&P 500 price data
2. Compute 10 features per stock
3. Train XGBoost model
4. Run walk-forward backtest
5. Validate risk controls
6. Generate report

## 10 MVP Features

| # | Feature | Type | Why It Works |
|---|---------|------|-------------|
| 1 | 12-1 Momentum (sector-relative) | Price | Most robust cross-sectional predictor |
| 2 | EV/EBITDA (sector-relative) | Valuation | Value signal, removes sector bias |
| 3 | FCF Yield | Quality | Cash beats accounting |
| 4 | 20-Day Realized Volatility | Volatility | Low-vol anomaly (outperformance) |
| 5 | Earnings Surprise | Earnings | Post-earnings drift (60+ days) |
| 6 | Insider Cluster Buying | Insider | Information asymmetry (3-6mo) |
| 7 | Mean Reversion (3M vs 12M) | Price | Pullbacks revert upward |
| 8 | Credit Spread Change | Macro | Bond market leads equity market |
| 9 | Piotroski F-Score | Fundamental | Composite quality (0-9) |
| 10 | Volume Ratio (20D / 60D) | Volume | Rising volume = accumulation |

## Model Architecture

### Target
**Binary classification:** Top quintile (1) vs rest (0) for 1-month forward returns

### Algorithm
**XGBoost** with hyperparameters:
- `max_depth: 5`
- `n_estimators: 200`
- `learning_rate: 0.05`
- `subsample: 0.8`
- `colsample_bytree: 0.8`

### Validation
- **Walk-forward:** 3-year train → 6-month test → quarterly roll
- **Cross-validation:** Purged k-fold for time-series
- **Metrics:** Accuracy >52%, Information Coefficient >0.03

## Risk Management (5-Layer)

| Layer | Control | Trigger | Action |
|-------|---------|---------|--------|
| **L1** | Position stop-loss | -15% from entry | Auto-exit, 5-day cooldown |
| **L2** | Sector concentration | >25% NAV | Trim proportionally |
| **L3** | Portfolio drawdown | -10% from HWM | Reduce exposure to 50% |
| **L4** | Volatility scaling | >1.5× target vol | Scale positions down |
| **L5** | Crisis detection | VIX >35 + spreads | Go 50% cash, daily review |

## Execution Strategy

### Order Types
- **Default:** Limit orders at mid-price with 5-min timeout
- **Large orders:** TWAP over 30-60 minutes
- **Exits:** IOC limit at bid-2 ticks

### Costs
- Commission: $0.005/share (IBKR)
- Slippage model: 0.05% + (trade_size / ADV) × 0.10%

### Broker
- **Paper trading:** Alpaca (free)
- **Live trading:** Interactive Brokers (lowest commissions)

## Performance Expectations (MVP)

Based on research & empirical validation:

| Metric | Target | Minimum | Excellent |
|--------|--------|---------|-----------|
| Sharpe Ratio | 0.5-1.0 | 0.5 | >1.5 |
| Max Drawdown | <20% | <25% | <10% |
| Win Rate | 52-55% | 52%+ | >60% |
| Monthly Consistency | 55%+ | 52%+ | >62% |

**Caveat:** Backtests show optimistic results. Expect 30-50% gap between paper and live performance.

## Next Steps (Phase 2: Paper Trading)

1. **Connect Alpaca API**
   ```python
   from alpaca_trade_api import REST
   api = REST('PK_XXXXX', 'SK_XXXXX', base_url='https://paper-api.alpaca.markets')
   ```

2. **Build Dashboard**
   ```bash
   streamlit run dashboard.py
   ```

3. **Run 3-Month Paper Trading**
   - Track execution quality vs backtest
   - Monitor model drift
   - Validate risk system

4. **Deploy to Real Capital** (if validated)
   - Start with $25K-$100K
   - Use 50% of model signals initially
   - Full risk management active

## Key Design Decisions

### Why XGBoost?
Transformers on tabular financial data routinely underperform gradient-boosted trees (Grinsztajn et al. 2022). GBMs are the workhorse for this problem.

### Why Long-Only (Phase 1)?
Shorting introduces borrow costs (2-4% annually), squeeze risk, and regulatory complexity. Build long alpha first; add shorts only when proven.

### Why No Leverage?
Maximum gross exposure = 100% NAV. Leverage amplifies both gains and ruin probability. Risk first.

### Why Weekly Rebalancing?
Daily rebalancing incurs 3-5× transaction costs for marginal improvement. Our signals (earnings revisions, insider buys) don't change daily.

## Critical Warnings

⚠️ **Backtests Are Optimistic**
- Assume perfect execution
- Underestimate real-world slippage
- Overestimate available returns

⚠️ **Model Drift Is Real**
- Markets change; models must adapt
- Information Coefficient decays over time
- Retrain on 3-month or drift detection

⚠️ **Operator Overconfidence**
- After 6 months of gains, temptation to loosen risk limits is enormous
- This is how LTCM died
- Make risk limits immutable constants, not config variables

## References

### Academic Papers
- Grinsztajn et al. (2022): "Revisiting Deep Learning Models for Tabular Data"
- De Prado (2018): "Advances in Financial Machine Learning"
- Fama & French (1993): "Common Risk Factors in the Returns of Stocks and Bonds"

### Practitioner Resources
- "Quantitative Momentum" - Wesley Gray & Jack Vogel
- "What Works on Wall Street" - James O'Shaughnessy
- "A Man for All Markets" - Edward Thorp

## Support & Documentation

For detailed rationale behind each design decision, refer to the ATLAS blueprint (HTML document in artifacts).

---

**Project ATLAS v1.0 | Autonomous Trading & Learning Alpha System | April 2026**