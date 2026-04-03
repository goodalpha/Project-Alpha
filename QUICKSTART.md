# 🚀 PROJECT ATLAS - Quick Start Guide

## ⚡ 5-Minute Setup

### 1️⃣ Create Free Alpaca Account (2 min)
```bash
# Go to: https://app.alpaca.markets
# Click "Sign Up"
# Verify email
# Done!
```

### 2️⃣ Get API Credentials (2 min)
```bash
# After signup, login and go to:
# Settings → API Keys → Create New Key

# You'll get:
# - API Key ID (looks like: PKxxxxxxxxxxxxxx)
# - Secret Key (shown only once - save it!)
```

### 3️⃣ Configure ATLAS (1 min)

**Option A: Quick Test**
```bash
cd /home/user/Project-Alpha

# Run setup script with your credentials
./setup_alpaca.sh PKxxxxxxxxxxxxxx your_secret_key_here
```

**Option B: Manual Setup**
```bash
export APCA_API_KEY_ID='PKxxxxxxxxxxxxxx'
export APCA_API_SECRET_KEY='your_secret_key_here'

# Test connection
python alpaca_trader.py
```

Expected output:
```
✅ CONNECTION SUCCESSFUL

Account Information:
  Portfolio Value: $100,000.00
  Cash: $100,000.00
  Buying Power: $400,000.00
```

---

## 🎯 Start Paper Trading

### Run the System
```bash
python main.py --live-paper
```

This will:
- ✅ Generate daily stock signals (10 MVP features)
- ✅ Place buy orders for top 30 stocks
- ✅ Monitor positions with risk controls
- ✅ Track P&L and performance

### Monitor in Real-Time
```bash
streamlit run dashboard.py
```

Visit: **http://localhost:8501**

Features:
- 📊 Portfolio value, cash, exposure
- 📈 Daily P&L and attribution
- ⚠️ Risk alerts and limit status
- 🎯 Model performance metrics
- 💹 Order execution status

---

## 📋 What Gets Executed

| Component | Frequency | Action |
|-----------|-----------|--------|
| **Data Fetch** | Daily (4 PM ET) | Downloads market data |
| **Features** | Daily | Computes 10 ML features |
| **Predictions** | Daily | Generates stock signals |
| **Orders** | Daily (Friday) | Buys top 30 stocks |
| **Monitoring** | Real-time | Tracks positions & risk |
| **Reporting** | Daily | P&L attribution |

---

## 🔍 Monitor Your Trading

### Dashboard
- Visit **http://localhost:8501**
- View portfolio in real-time
- Check risk alerts & limits
- See P&L by position

### Logs
```bash
# View current logs
tail -f logs/atlas_*.log

# See latest report
cat backtest/report_*.json | python -m json.tool
```

### Check Positions
```bash
python -c "
from alpaca_trader import AlpacaTrader
trader = AlpacaTrader(paper=True)
positions = trader.get_positions()
for p in positions:
    print(f\"{p['symbol']}: {p['quantity']} @ \${p['avg_fill_price']:.2f}\")
"
```

---

## ⚖️ Risk Management Active

The system protects your capital with 5-layer controls:

| Layer | Limit | Trigger |
|-------|-------|---------|
| **L1: Position** | -15% | Stop-loss per stock |
| **L2: Sector** | 25% | Max sector exposure |
| **L3: Portfolio** | -10% | Drawdown circuit breaker |
| **L4: Volatility** | 12% | Vol target scaling |
| **L5: Crisis** | VIX >35 | Panic mode → 50% cash |

---

## ⚠️ Important Notes

### Paper Trading (Safe)
- ✅ 100% simulation - no real money
- ✅ $100,000 starting capital
- ✅ Resets daily at 4 PM ET
- ✅ Perfect for testing

### Before Going Live
- **Test for 1+ months** on paper
- **Check execution quality** - compare paper vs backtest
- **Validate model consistency** - stable performance
- **Monitor drawdowns** - max loss behavior
- **Only then** scale to real capital ($5K-$25K minimum)

---

## 🆘 Troubleshooting

### ❌ 403 Forbidden
```bash
# Check credentials are set
echo $APCA_API_KEY_ID
echo $APCA_API_SECRET_KEY

# If empty, set them:
export APCA_API_KEY_ID='your_key'
export APCA_API_SECRET_KEY='your_secret'
```

### ❌ Connection Timeout
- Check: https://status.alpaca.markets
- Retry in a few minutes

### ❌ ImportError: No module named 'alpaca'
```bash
pip install alpaca-py --upgrade
```

### ❌ No available orders
- Wait for market hours (9:30 AM - 4 PM ET)
- Check if market is closed

---

## 📊 Expected Performance

Based on 3-year backtests:

| Metric | Target | Note |
|--------|--------|------|
| **Sharpe Ratio** | 0.5-1.5 | Risk-adjusted returns |
| **Max Drawdown** | 10-20% | Worst peak-to-trough |
| **Win Rate** | 52-55% | Monthly positive |
| **Return** | 8-15% | Annual average |

**Note:** Paper trading may differ from backtest due to:
- Real slippage vs model assumptions
- Market regimes changes
- Model drift over time

---

## 🎓 Next Steps

### Immediate (Today)
1. ✅ Set up Alpaca credentials
2. ✅ Test connection
3. ✅ Start paper trading
4. ✅ Monitor dashboard

### Week 1
- [ ] Check daily P&L
- [ ] Verify order execution
- [ ] Review risk alerts
- [ ] Validate signals

### Month 1
- [ ] Compare paper vs backtest
- [ ] Monitor model drift
- [ ] Check execution consistency
- [ ] Plan next steps

### Month 2-3
- [ ] Analyze performance attribution
- [ ] Validate risk controls
- [ ] Test edge cases
- [ ] Plan real money deployment

---

## 📞 Commands Reference

```bash
# Test connection
python alpaca_trader.py

# Start paper trading
python main.py --live-paper

# Launch dashboard
streamlit run dashboard.py

# Check positions
python -c "from alpaca_trader import AlpacaTrader; \
ac = AlpacaTrader(paper=True); \
print('Positions:', len(ac.get_positions()))"

# Get account info
python -c "from alpaca_trader import AlpacaTrader; \
ac = AlpacaTrader(paper=True); \
print(ac.get_account())"

# View latest report
cat backtest/report_*.json | python -m json.tool | head -50

# Follow logs
tail -f logs/atlas_*.log | grep -E "(✅|❌|⚠️)"
```

---

## 🎯 You're Ready!

Everything is set up and ready to trade. Just:

1. **Get credentials** from https://app.alpaca.markets/settings/keys
2. **Run setup script**: `./setup_alpaca.sh PKxxxx your_secret`
3. **Start trading**: `python main.py --live-paper`
4. **Monitor**: Visit http://localhost:8501

**Paper trading is 100% risk-free. Start today!** 🚀

---

*For detailed information, see:*
- `README.md` - Full project documentation
- `SETUP_ALPACA.md` - Detailed Alpaca setup
- `alpaca_trader.py` - API reference
