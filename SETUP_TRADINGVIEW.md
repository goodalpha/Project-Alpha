# 🎯 PROJECT ATLAS - TradingView Paper Trading Integration

## What You Can Do

### Option 1: TradingView Alerts → ATLAS Execution (Recommended)
- Create alerts/strategies in TradingView
- Send signals via webhook to ATLAS
- ATLAS executes trades on Alpaca (auto or manual)
- Dashboard tracks everything in real-time

### Option 2: Manual TradingView Paper Trading
- Use TradingView's built-in paper trading
- Execute trades manually on TradingView
- ATLAS monitors via API (coming soon)
- Track P&L in both systems

---

## 🚀 Setup Option 1: Alerts → ATLAS → Alpaca (RECOMMENDED)

### Step 1: Start Webhook Server
```bash
cd /home/user/Project-Alpha
python tradingview_webhook.py
```

Expected output:
```
✅ Webhook server started
Running on http://localhost:5000
Visit: http://localhost:5000/status
```

### Step 2: Create TradingView Alert

1. **Open TradingView** (www.tradingview.com)
2. **Create Alert:**
   - Right-click chart → "Add Alert"
   - Or use your existing strategy
3. **Configure Webhook:**
   - Alert Settings → Notification
   - Select "Webhook URL"
   - Enter: `http://localhost:5000/webhook`

4. **Alert Message (JSON):**
```json
{
  "symbol": "{{ticker}}",
  "action": "buy",
  "quantity": 10,
  "price": {{close}},
  "strategy": "ATLAS",
  "comment": "Signal at {{time}}"
}
```

5. **Create Alert** → Done!

### Step 3: Test Connection

```bash
# Test webhook
curl -X POST http://localhost:5000/test

# View signals
curl http://localhost:5000/signals

# Get stats
curl http://localhost:5000/stats
```

### Step 4: Enable Auto-Execution (Optional)

Edit `tradingview_webhook.py`:
```python
# Line: processor = SignalProcessor(...)
processor = SignalProcessor(auto_execute=True, paper=True)
```

Then set Alpaca credentials:
```bash
export APCA_API_KEY_ID='PKxxxxxxxxxxxxxx'
export APCA_API_SECRET_KEY='your_secret_key'
```

Now signals automatically execute on Alpaca!

---

## 🎯 Setup Option 2: TradingView Paper Trading (Manual)

### Step 1: Open TradingView Paper Trading
```
www.tradingview.com → Account → Paper Trading
```

### Step 2: Create Strategy/Indicator

Example Pine Script strategy:
```pinescript
//@version=5
strategy("ATLAS Signals", overlay=true)

// Buy signal
buySignal = ta.crossover(ta.sma(close, 10), ta.sma(close, 20))
// Sell signal  
sellSignal = ta.crossunder(ta.sma(close, 10), ta.sma(close, 20))

if buySignal
    strategy.entry("Buy", strategy.long)
if sellSignal
    strategy.close("Buy")

plot(ta.sma(close, 10), color=color.blue)
plot(ta.sma(close, 20), color=color.red)
```

### Step 3: Run on Paper Trading Account

1. Click "Strategy → Paper Trading"
2. Watch trades execute automatically
3. View P&L in TradingView

### Step 4: Monitor with ATLAS Dashboard

Start ATLAS to track your TradingView P&L:
```bash
streamlit run dashboard.py
```

---

## 📊 TradingView Alert Message Format

### Basic Buy/Sell
```json
{
  "symbol": "AAPL",
  "action": "buy",
  "quantity": 10,
  "price": 180.50,
  "strategy": "ATLAS",
  "comment": "Bullish signal"
}
```

### With Dynamic Values
```json
{
  "symbol": "{{ticker}}",
  "action": "buy",
  "quantity": 10,
  "price": {{close}},
  "strategy": "MyStrategy",
  "comment": "{{exchange}} {{time}}"
}
```

### Close Position
```json
{
  "symbol": "{{ticker}}",
  "action": "close",
  "quantity": 1,
  "strategy": "ATLAS",
  "comment": "Take profit"
}
```

### Available TradingView Variables
- `{{ticker}}` - Symbol (AAPL, MSFT, etc.)
- `{{exchange}}` - Exchange (NYSE, NASDAQ)
- `{{time}}` - Current time
- `{{close}}` - Close price
- `{{open}}` - Open price
- `{{high}}` - High price
- `{{low}}` - Low price
- `{{volume}}` - Volume
- `{{change}}` - Price change

---

## 🔗 API Endpoints

### Receive Signal
```
POST /webhook
Content-Type: application/json

{
  "symbol": "AAPL",
  "action": "buy",
  ...
}
```

### Get Signal History
```
GET /signals?limit=50
Response: { signals: [...], count: 50 }
```

### Get Statistics
```
GET /stats
Response: { total_signals: 100, by_action: {...} }
```

### Server Status
```
GET /status
Response: { status: 'online', signals_received: 100 }
```

### Test Webhook
```
POST /test
Response: { success: true, signal: {...} }
```

---

## 💡 Example Trading Strategies

### Strategy 1: Moving Average Crossover
```pinescript
//@version=5
strategy("MA Crossover", overlay=true)

sma10 = ta.sma(close, 10)
sma20 = ta.sma(close, 20)

buy = ta.crossover(sma10, sma20)
sell = ta.crossunder(sma10, sma20)

if buy
    strategy.entry("Buy", strategy.long)
if sell
    strategy.close("Buy")
```

### Strategy 2: RSI Oversold/Overbought
```pinescript
//@version=5
strategy("RSI Strategy", overlay=true)

rsi = ta.rsi(close, 14)

buy = rsi < 30
sell = rsi > 70

if buy
    strategy.entry("Buy", strategy.long)
if sell
    strategy.close("Buy")
```

### Strategy 3: Bollinger Bands
```pinescript
//@version=5
strategy("BB Strategy", overlay=true)

[middle, upper, lower] = ta.bb(close, 20, 2)

buy = close < lower
sell = close > upper

if buy
    strategy.entry("Buy", strategy.long)
if sell
    strategy.close("Buy")
```

---

## 🎮 Managing Signals

### View Signals in Real-Time
```bash
# Watch signals as they arrive
watch -n 1 'curl -s http://localhost:5000/signals | python -m json.tool'
```

### Check Statistics
```bash
curl http://localhost:5000/stats | python -m json.tool

# Output:
# {
#   "total_signals": 45,
#   "by_action": {
#     "buy": 25,
#     "sell": 18,
#     "close": 2
#   },
#   "by_symbol": {
#     "AAPL": 15,
#     "MSFT": 12,
#     "GOOGL": 18
#   },
#   "first_signal": "2026-04-03T10:30:00",
#   "last_signal": "2026-04-03T18:45:00"
# }
```

---

## ⚙️ Configuration

### Webhook Settings
```python
# tradingview_webhook.py

# Enable auto-execution
processor = SignalProcessor(auto_execute=True, paper=True)

# Use live trading (requires capital!)
processor = SignalProcessor(auto_execute=True, paper=False)

# Manual signal review
processor = SignalProcessor(auto_execute=False, paper=True)
```

### Security (Optional)
```bash
# Set webhook secret
export TRADINGVIEW_WEBHOOK_SECRET='your_secret_key'

# Then add to TradingView alert:
# Header: X-Webhook-Secret: your_secret_key
```

### Network Settings
```bash
# Run on specific host/port
export WEBHOOK_HOST='0.0.0.0'
export WEBHOOK_PORT='5000'

# Or in startup command:
python tradingview_webhook.py --host 0.0.0.0 --port 5000
```

---

## 🌐 Remote Deployment

### Using ngrok (for remote access)
```bash
# Terminal 1: Start webhook
python tradingview_webhook.py

# Terminal 2: Create tunnel
ngrok http 5000

# Copy HTTPS URL → Use in TradingView alert
# Example: https://abc123.ngrok.io/webhook
```

### Deploy to Cloud
```bash
# Example: Heroku
heroku create my-atlas-webhook
git push heroku main

# Get URL:
https://my-atlas-webhook.herokuapp.com/webhook
```

---

## 📊 Monitor in ATLAS Dashboard

```bash
# Start dashboard
streamlit run dashboard.py

# Visit: http://localhost:8501
# Check:
# - Portfolio value
# - Open positions
# - Recent trades
# - Risk metrics
# - P&L attribution
```

---

## 🎓 Best Practices

### 1. Start Small
- First alert: 1 share only
- Verify webhook works
- Then increase quantity

### 2. Use Limits
```json
{
  "symbol": "AAPL",
  "action": "buy",
  "quantity": 10,
  "max_position": 50,
  "stop_loss": -0.15
}
```

### 3. Log Everything
- Check `/signals` endpoint regularly
- Review statistics in `/stats`
- Monitor server status with `/status`

### 4. Test Alerts
```bash
# Send test alert
curl -X POST http://localhost:5000/test

# Should see it in:
curl http://localhost:5000/signals
```

### 5. Alert Message Best Practices
```json
{
  "symbol": "{{ticker}}",
  "action": "buy",
  "quantity": 10,
  "price": {{close}},
  "strategy": "MyStrategy",
  "comment": "Signal at {{time}}, Price: {{close}}, RSI: {{rsi}}"
}
```

---

## 🆘 Troubleshooting

### Webhook Not Receiving Signals
1. Check server is running: `curl http://localhost:5000/status`
2. Verify TradingView URL is correct (copy from `/status` output)
3. Check TradingView alert logs for errors
4. Test manually: `curl -X POST http://localhost:5000/test`

### Auto-Execution Not Working
1. Check Alpaca credentials: `echo $APCA_API_KEY_ID`
2. Verify credentials are set
3. Check logs: `tail -f logs/atlas_*.log`
4. Test Alpaca directly: `python alpaca_trader.py`

### Signals Not Executing on Alpaca
1. Check market hours (9:30 AM - 4 PM ET)
2. Verify position sizing (qty > 0)
3. Check buying power
4. Review `/signals` to see what was received

---

## 📞 Quick Commands

```bash
# Start webhook server
python tradingview_webhook.py

# Start ATLAS dashboard
streamlit run dashboard.py

# Test webhook
curl -X POST http://localhost:5000/test

# View signals
curl http://localhost:5000/signals | python -m json.tool

# Get stats
curl http://localhost:5000/stats | python -m json.tool

# Check status
curl http://localhost:5000/status | python -m json.tool

# Follow logs
tail -f logs/atlas_*.log
```

---

## ✨ Workflow Summary

1. **TradingView:** Create strategy/alert
2. **Webhook:** Send signal via JSON POST
3. **ATLAS:** Receive and process signal
4. **Alpaca:** Execute trade (auto or manual)
5. **Dashboard:** Monitor P&L in real-time

**Total latency:** <1 second from alert to execution ✅

---

**Ready to connect TradingView to ATLAS?**

Start the webhook server and you're 90% there!
