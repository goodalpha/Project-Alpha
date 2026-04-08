# 🎯 PROJECT ATLAS - TradingView Paper Trading (Direct)

## What You Get

Use **TradingView's built-in paper trading** with ATLAS:
- ✅ Execute trades directly on TradingView
- ✅ Use TradingView's charting for analysis
- ✅ ATLAS generates signals (ML model)
- ✅ Dashboard tracks P&L
- ✅ Zero risk - fully simulated

---

## 🚀 Quick Start (5 Minutes)

### Step 1: Enable TradingView Paper Trading

```
www.tradingview.com → Account Settings → Paper Trading
```

1. Click "Upgrade" or "Enable Paper Trading"
2. Set initial capital ($100,000 default)
3. Start trading

### Step 2: Generate ATLAS Signals

```bash
cd /home/user/Project-Alpha

# Start ATLAS signal generation
python main.py --generate-signals

# Output:
# [2026-04-03 16:00:00] Generated signals for 500 stocks
# [2026-04-03 16:00:15] Top 30 stocks for buying:
# 1. AAPL - Confidence: 0.78
# 2. MSFT - Confidence: 0.75
# 3. GOOGL - Confidence: 0.73
# ...
```

### Step 3: Execute on TradingView

For each signal:
1. Open TradingView chart (e.g., AAPL)
2. Click "Paper Trading" at top
3. Enter quantity (from ATLAS signal)
4. Click "Buy" or "Sell"
5. Track in Portfolio

### Step 4: Monitor in ATLAS Dashboard

```bash
streamlit run dashboard.py
```

View:
- ✅ Your TradingView positions
- ✅ P&L by position
- ✅ Risk metrics
- ✅ Model performance

---

## 📊 Position Sizing Guide

Since TradingView shows price dynamically:

```python
# Calculate shares from ATLAS signal

portfolio_value = 100_000  # Your TradingView paper trading capital
per_position_pct = 0.03  # 3% per position
position_value = portfolio_value * per_position_pct  # $3,000

# For each stock:
stock_price = 180.50  # Current price (from TradingView chart)
shares_to_buy = int(position_value / stock_price)  # Number of shares

print(f"Buy {shares_to_buy} shares at ${stock_price}")
# Output: Buy 16 shares at $180.50
```

Quick formula:
```
Shares = $3,000 / Stock_Price

Examples:
- AAPL @ $180: Buy 16 shares
- MSFT @ $420: Buy 7 shares  
- GOOGL @ $140: Buy 21 shares
```

---

## 🎯 Workflow: ATLAS Signals → TradingView Execution

### Typical Trading Day

**9:30 AM ET (Market Open)**
- Check ATLAS dashboard for today's signals
- Get latest signal report with top 30 stocks
- Start executing highest confidence signals

**10:00 AM - 12:00 PM**
- Continue executing remaining top signals
- Monitor entry prices vs ATLAS targets
- Verify position sizing

**4:00 PM (Market Close)**
- Review daily P&L on TradingView
- Log executions in ATLAS dashboard
- Check portfolio risk metrics

**Friday 4:00 PM (Weekly Rebalance)**
- Review this week's signal performance
- Generate next week's signals
- Prepare for Monday's execution

---

## 📈 Daily Signal Report Example

```
═══════════════════════════════════════════════════════════
ATLAS DAILY SIGNALS - 2026-04-03
═══════════════════════════════════════════════════════════

TOP 30 BUY SIGNALS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Rank  Symbol   Confidence   Target   Shares (@$100K)
────  ──────   ──────────   ──────   ──────────────
1.    AAPL     0.85         +12.5%   16 shares
2.    MSFT     0.82         +10.8%   7 shares
3.    GOOGL    0.79         +8.3%    21 shares
4.    AMZN     0.76         +7.2%    6 shares
5.    META     0.75         +6.8%    4 shares
...

EXECUTION GUIDE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Position sizing: $3,000 per position (3% of $100K)
Total positions: 30
Total capital deployed: $90,000
Cash reserve: $10,000

Execution:
1. Open TradingView chart (AAPL)
2. Click "Paper Trading" button
3. Set quantity (16 shares)
4. Click "Buy"
5. Repeat for all 30 signals

═══════════════════════════════════════════════════════════
```

---

## ✨ Your Trading Plan

### Today
- [ ] Enable TradingView paper trading account
- [ ] Verify $100K starting balance
- [ ] Get ATLAS signals
- [ ] Execute top 5 signals manually on TradingView

### This Week
- [ ] Execute all 30 recommended signals
- [ ] Track all trades in ATLAS dashboard
- [ ] Monitor daily P&L
- [ ] Verify position sizing

### Next Week (Friday Rebalance)
- [ ] Get new weekly signals
- [ ] Sell losing positions
- [ ] Execute new winning signals
- [ ] Review signal accuracy

### Month 1
- [ ] Complete full trading month
- [ ] Analyze ATLAS signal quality
- [ ] Check against backtest expectations
- [ ] Decide: continue as-is, improve, or scale

---

## 🎯 Commands

```bash
# Generate signals
python main.py --generate-signals

# View latest signals  
cat backtest/latest_signals.json

# Start dashboard to track trades
streamlit run dashboard.py

# Check model performance
python -c "from model import AtlasModel; m = AtlasModel(); print(m.training_metrics)"

# View backtest report
cat backtest/report_*.json | python -m json.tool
```

---

## 💡 TradingView Paper Trading Tips

✅ **Do:**
- Execute during market hours (9:30 AM - 4 PM ET)
- Use market orders (fastest execution)
- Track all trades in a spreadsheet
- Rebalance every Friday
- Monitor risk limits
- Review P&L daily

❌ **Don't:**
- Trade after market close
- Use only limit orders (might not fill)
- Forget position sizes
- Skip weekly rebalancing
- Ignore risk controls
- Let emotion override signals

---

## 🚀 Start Today!

**Total setup time: 5 minutes**

1. Enable TradingView paper trading
2. Get ATLAS signals
3. Execute on TradingView
4. Monitor in ATLAS dashboard

**Zero cost. Zero risk. Real learning.** ✅

---

Ready to start? Visit: **www.tradingview.com** 🎯
