# 🤖 PROJECT ATLAS - TradingView Automatic Scraper

## What It Does

The TradingView scraper **automatically**:
- ✅ Logs into your TradingView account
- ✅ Fetches paper trading positions in real-time
- ✅ Tracks P&L and account metrics
- ✅ Monitors positions continuously (every 5 minutes)
- ✅ Updates ATLAS dashboard automatically
- ✅ Uses real trading data to train/validate models

---

## 🚀 Quick Setup (10 Minutes)

### 1. Install Selenium & ChromeDriver

```bash
# Install Selenium
pip install selenium

# Download ChromeDriver
# Visit: https://chromedriver.chromium.org/
# Extract to: /usr/local/bin/chromedriver
# Make executable:
chmod +x /usr/local/bin/chromedriver

# Verify installation
chromedriver --version  # Should show version
```

### 2. Set TradingView Credentials

```bash
# Set environment variables
export TRADINGVIEW_EMAIL='your_email@example.com'
export TRADINGVIEW_PASSWORD='your_password'

# Or add to ~/.bashrc for permanent setup
echo 'export TRADINGVIEW_EMAIL="your_email@example.com"' >> ~/.bashrc
echo 'export TRADINGVIEW_PASSWORD="your_password"' >> ~/.bashrc
source ~/.bashrc
```

### 3. Run the Scraper

```bash
# Option A: Scrape and monitor
python tradingview_scraper.py

# Option B: Train model from TradingView data
python tradingview_model_trainer.py

# Option C: Run with dashboard
python tradingview_scraper.py & streamlit run dashboard.py
```

---

## 📊 How It Works

### Architecture

```
Your TradingView Account
        ↓ (Selenium WebDriver)
TradingView Website (HTML)
        ↓ (Web Scraping)
Extract Positions & P&L
        ↓ (JSON)
ATLAS System
        ↓
├─ Dashboard (Real-time updates)
├─ Model Training
├─ Risk Analysis
└─ Performance Reports
```

### Data Flow

```
9:30 AM: Start monitoring
        ↓
Every 5 minutes: Fetch positions from TradingView
        ↓
Extract: Symbol, quantity, entry price, current price, P&L
        ↓
Update ATLAS: Positions, P&L, account metrics
        ↓
4:00 PM: Save daily report
        ↓
Summary: Total P&L, win rate, positions tracked
```

---

## 🔧 Two Main Modules

### Module 1: `tradingview_scraper.py`

**Fetches real-time trading data:**

```bash
python tradingview_scraper.py
```

**What it does:**
1. Login to TradingView
2. Navigate to Paper Trading
3. Extract all open positions
4. Fetch real-time prices
5. Calculate P&L for each position
6. Update ATLAS dashboard
7. Save to JSON files
8. Continue monitoring every 5 minutes

**Data saved:**
```json
{
  "timestamp": "2026-04-03T10:30:00",
  "account_value": 102500.50,
  "positions": [
    {
      "symbol": "AAPL",
      "quantity": 16,
      "entry_price": 180.75,
      "current_price": 181.50,
      "pnl": 12.00,
      "pnl_pct": 0.41
    },
    ...
  ],
  "total_pnl": 2500.50,
  "position_count": 30
}
```

### Module 2: `tradingview_model_trainer.py`

**Trains models from TradingView data:**

```bash
python tradingview_model_trainer.py
```

**What it does:**
1. Collects real trading data from TradingView
2. Validates ATLAS signals vs actual P&L
3. Trains model on real trading outcomes
4. Compares backtest vs live performance
5. Generates detailed report

**Workflow:**
```
TradingView Data → Model Training → Validation → Report
```

---

## 📈 Real-Time Monitoring

### Option A: Headless (Background)

```bash
# Runs without opening browser
python tradingview_scraper.py &

# Check results
cat backtest/tradingview_history.json | python -m json.tool
```

### Option B: Visual (See Browser)

```bash
# Edit tradingview_scraper.py:
# scraper = TradingViewScraper(..., headless=False)

# Runs with visible browser window
python tradingview_scraper.py
```

### Option C: With Dashboard

```bash
# Terminal 1: Start scraper
python tradingview_scraper.py &

# Terminal 2: Start dashboard
streamlit run dashboard.py

# Visit: http://localhost:8501
```

---

## 🎯 Use Cases

### Use Case 1: Track Positions in Real-Time

```bash
# Continuously monitor your paper trading account
python tradingview_scraper.py

# Check every 5 minutes:
# - Open positions
# - Current P&L
# - Account value
```

**Output:**
```
10:30:00 | Positions: 30, Account: $102,500, P&L: +$2,500
10:35:00 | Positions: 30, Account: $102,450, P&L: +$2,450
10:40:00 | Positions: 28, Account: $102,600, P&L: +$2,600
```

### Use Case 2: Validate Model Signals

```bash
python tradingview_model_trainer.py

# Compares:
# ✅ ATLAS signals generated
# ✅ TradingView positions executed
# ✅ Actual P&L on each position
# → Model accuracy report
```

### Use Case 3: Train Model on Live Data

```bash
# Collect TradingView trading data (8 hours of trading)
python tradingview_model_trainer.py

# This will:
# 1. Monitor your paper trading
# 2. Collect real results
# 3. Train model from actual outcomes
# 4. Generate performance report
```

---

## 📊 Dashboard Integration

The scraper automatically updates the ATLAS dashboard with:

**Portfolio Section:**
- Total positions
- Account value
- Cash available
- Total P&L

**Positions Section:**
- All open positions
- Entry price vs current price
- Individual P&L
- P&L percentage

**Risk Section:**
- Position concentrations
- Sector exposure
- Largest losers/winners

---

## 🔐 Security Best Practices

### Never Hardcode Credentials

❌ **Don't do this:**
```python
email = "your_email@example.com"
password = "your_password"
```

✅ **Do this:**
```python
email = os.getenv('TRADINGVIEW_EMAIL')
password = os.getenv('TRADINGVIEW_PASSWORD')
```

### Store Credentials Safely

```bash
# Option 1: Environment variables (current session)
export TRADINGVIEW_EMAIL='your_email@example.com'

# Option 2: ~/.bashrc (persistent)
echo 'export TRADINGVIEW_EMAIL="your_email@example.com"' >> ~/.bashrc

# Option 3: .env file (git-ignored)
# Create .env file:
# TRADINGVIEW_EMAIL=your_email@example.com
# TRADINGVIEW_PASSWORD=your_password

# Load in Python:
from dotenv import load_dotenv
load_dotenv()
```

---

## 🚨 Troubleshooting

### ❌ "chromedriver not found"

```bash
# Make sure ChromeDriver is in PATH
which chromedriver  # Should show /usr/local/bin/chromedriver

# If not installed:
# 1. Download from: https://chromedriver.chromium.org/
# 2. Extract to: /usr/local/bin/
# 3. chmod +x /usr/local/bin/chromedriver
```

### ❌ Login Failed

```bash
# Check credentials
echo $TRADINGVIEW_EMAIL
echo $TRADINGVIEW_PASSWORD

# Should output your email and password (not empty)

# If empty, set them:
export TRADINGVIEW_EMAIL='your_email@example.com'
export TRADINGVIEW_PASSWORD='your_password'
```

### ❌ Can't Find Positions

```bash
# Check if paper trading is enabled
# Go to: www.tradingview.com/accounts/paper-trading/
# Verify you have positions in your account

# Try running with visible browser (headless=False)
# to see what the scraper sees
```

### ❌ Connection Timeout

```bash
# TradingView server might be slow
# Increase timeout in code:
# scraper = TradingViewScraper(..., timeout=60)

# Or retry after a few minutes
```

---

## 📋 Example Output

### Console Output

```
✅ Chrome WebDriver initialized
Logging in to TradingView...
✅ Successfully logged in to TradingView
✅ Fetched 30 positions
10:30:00 | Positions: 30, Account: $102,500, P&L: +$2,500 ✅
10:35:00 | Positions: 30, Account: $102,450, P&L: +$2,450 ✅
10:40:00 | Positions: 28, Account: $102,600, P&L: +$2,600 ✅
...
16:00:00 | Session ended. Final P&L: +$2,850 ✅
```

### JSON Data File

```json
{
  "timestamp": "2026-04-03T16:00:00",
  "account_value": 102850.00,
  "total_positions": 28,
  "total_pnl": 2850.00,
  "winning_positions": 21,
  "losing_positions": 7,
  "positions": [
    {
      "symbol": "AAPL",
      "quantity": 16,
      "entry_price": 180.75,
      "current_price": 181.50,
      "pnl": 12.00,
      "pnl_pct": 0.41
    }
  ]
}
```

---

## 🎓 Advanced Usage

### Custom Update Interval

```python
from tradingview_scraper import TradingViewMonitor

scraper = TradingViewScraper(email, password)
scraper.login()

# Update every 60 seconds instead of default 300
monitor = TradingViewMonitor(scraper, update_interval=60)
monitor.start_monitoring(duration_hours=8)
```

### Fetch Specific Stock Prices

```python
from tradingview_scraper import TradingViewScraper

scraper = TradingViewScraper(email, password)
scraper.login()

prices = scraper.get_real_time_prices(['AAPL', 'MSFT', 'GOOGL'])
print(prices)  # {'AAPL': 180.50, 'MSFT': 420.25, 'GOOGL': 140.10}
```

### Save Custom Data

```python
from tradingview_scraper import TradingViewScraper

scraper = TradingViewScraper(email, password)
data = scraper.fetch_paper_trading_data()

# Save with custom filename
scraper.save_to_file(data, filename='my_trading_session.json')
```

---

## 🚀 Full Workflow

### Daily Trading with Scraper

```bash
# Morning: Start scraper and dashboard
$ python tradingview_scraper.py &
$ streamlit run dashboard.py &

# Throughout the day:
# - ATLAS generates signals
# - You execute manually on TradingView
# - Scraper monitors everything
# - Dashboard updates in real-time

# Evening: Check final results
$ cat backtest/tradingview_history.json | python -m json.tool
```

### Weekly Model Training

```bash
# End of week: Train model from real data
$ python tradingview_model_trainer.py

# This will:
# 1. Collect all week's trading data
# 2. Validate signals vs actual P&L
# 3. Train model on real outcomes
# 4. Generate performance report
# 5. Compare to backtest predictions

# Review report
$ cat backtest/tradingview_model_report_*.json
```

---

## 📞 Commands Reference

```bash
# Scrape TradingView (real-time monitoring)
python tradingview_scraper.py

# Train model from TradingView data
python tradingview_model_trainer.py

# With dashboard
python tradingview_scraper.py & streamlit run dashboard.py

# Headless (background)
python tradingview_scraper.py > /dev/null 2>&1 &

# Check saved data
cat backtest/tradingview_history.json | python -m json.tool

# Follow live updates
tail -f logs/tradingview_scraper.log
```

---

## ✨ Benefits

✅ **Automatic:** No manual entry needed
✅ **Real-time:** Updates every 5 minutes
✅ **Accurate:** Pulls directly from TradingView
✅ **Integrated:** Works with ATLAS dashboard
✅ **Training:** Use real data to improve models
✅ **Validation:** Verify signals work in practice

---

**Start monitoring your paper trading NOW!** 🚀
