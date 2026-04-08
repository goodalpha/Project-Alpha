# ATLAS - Alpaca Paper Trading Setup Guide

## 🎯 Quick Start (5 minutes)

### 1. Create Free Alpaca Account
```bash
# Go to https://app.alpaca.markets
# Click "Sign Up"
# Verify your email
```

### 2. Generate API Keys
```bash
# After signup:
# 1. Login to https://app.alpaca.markets
# 2. Click your name (top right) → Settings
# 3. Go to "API Keys"
# 4. Click "Create New Key"
# 5. Copy both API Key ID and Secret Key
```

### 3. Set Environment Variables
```bash
# Option A: One-time (current session)
export APCA_API_KEY_ID='PKxxxxxxxxxxxxxx'
export APCA_API_SECRET_KEY='your_secret_key_here'

# Option B: Persistent (add to ~/.bashrc)
echo 'export APCA_API_KEY_ID="PKxxxxxxxxxxxxxx"' >> ~/.bashrc
echo 'export APCA_API_SECRET_KEY="your_secret_key"' >> ~/.bashrc
source ~/.bashrc
```

### 4. Install Alpaca Library
```bash
pip install alpaca-trade-api
```

### 5. Test Connection
```bash
python alpaca_integration.py
```

Expected output:
```
✅ CONNECTION SUCCESSFUL

Account Information:
  Portfolio Value: $100,000.00
  Cash: $100,000.00
  Buying Power: $400,000.00
  ...

✅ Ready for paper trading!
```

---

## 🚀 Using ATLAS with Alpaca

### Start Paper Trading
```bash
python main.py --live-paper
```

### Monitor in Real-Time
```bash
streamlit run dashboard.py
```

Visit: `http://localhost:8501`

---

## ⚠️ Important Notes

### Paper Trading (SAFE)
- 100% simulation, zero risk
- $100,000 starting cash (default)
- Resets daily at 4 PM ET
- Perfect for testing strategies

### Live Trading (REAL MONEY)
- Requires verified account
- Requires real capital
- Use small amounts to start ($1K-$10K)
- Implement kill switches & position limits

### Best Practices
1. **Always test on paper first** (minimum 1 month)
2. **Monitor daily P&L** for first 3 months
3. **Set position limits** (max 5% per trade)
4. **Use stop-losses** (mandatory in production)
5. **Check API status** before market open
6. **Keep API keys secret** (never commit to Git)

---

## 🔍 Troubleshooting

### ❌ 403 Forbidden
**Problem:** Invalid or missing credentials
```bash
# Check if variables are set
echo $APCA_API_KEY_ID
echo $APCA_API_SECRET_KEY

# Should output your keys (not empty)
```

### ❌ Connection Timeout
**Problem:** Alpaca API temporarily down
- Check: https://status.alpaca.markets
- Wait a few minutes and retry

### ❌ Insufficient Buying Power
**Problem:** Already have positions open
```bash
# Close all positions
python -c "from alpaca_integration import AlpacaConnector; \
ac = AlpacaConnector(); \
[ac.close_position(p['symbol']) for p in ac.get_positions()]"
```

### ❌ ImportError: No module named 'alpaca_trade_api'
**Problem:** Library not installed
```bash
pip install alpaca-trade-api --upgrade
```

---

## 📊 Example: Place a Test Order

```python
from alpaca_integration import AlpacaConnector

# Connect
connector = AlpacaConnector()

# Buy 10 shares of AAPL at market price
connector.place_order(
    symbol='AAPL',
    qty=10,
    side='buy',
    order_type='market'
)

# Or place a limit order
connector.place_order(
    symbol='GOOGL',
    qty=5,
    side='buy',
    order_type='limit',
    limit_price=100.50
)

# Check account
account = connector.get_account()
print(f"Portfolio Value: ${account['portfolio_value']:,.2f}")
```

---

## 📈 ATLAS Integration

Once connected, ATLAS will:

1. **Generate daily signals** based on the 10 MVP features
2. **Place orders** on top 30 predicted stocks
3. **Monitor positions** with 5-layer risk management
4. **Track P&L** with attribution analysis
5. **Alert on risk events** (drawdown, concentration, vol spike)

### Dashboard Features
- 📊 Real-time portfolio value
- 📈 P&L attribution by position
- ⚠️ Risk alerts & limit status
- 🎯 Model performance metrics
- 💹 Daily/monthly returns

---

## ✅ Verification Checklist

- [ ] Alpaca account created
- [ ] API keys generated
- [ ] Environment variables set
- [ ] `alpaca-trade-api` installed
- [ ] Connection test passed
- [ ] Dashboard accessible
- [ ] First test order placed
- [ ] Portfolio updated

---

**Once all steps complete, ATLAS is ready to trade! 🚀**

Next: Run `python main.py --live-paper` to start paper trading
