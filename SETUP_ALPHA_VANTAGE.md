# 📊 PROJECT ATLAS - Alpha Vantage Data Integration

## 🎉 You Have: API Key V28U6XTX4P9CU502

Your Alpha Vantage API key is ready! This gives you access to:
- ✅ Real-time stock quotes
- ✅ 20+ years of historical daily OHLCV data
- ✅ Company fundamentals (PE ratio, market cap, etc.)
- ✅ Technical indicators (RSI, SMA, MACD, etc.)
- ✅ Forex and crypto data

---

## 🚀 Setup (2 minutes)

### 1. Set Environment Variable
```bash
# Add to your shell profile (~/.bashrc or ~/.zshrc)
export ALPHA_VANTAGE_API_KEY='V28U6XTX4P9CU502'

# Or set temporarily in current session
export ALPHA_VANTAGE_API_KEY='V28U6XTX4P9CU502'
```

### 2. Test Connection
```bash
cd /home/user/Project-Alpha

# Test the Alpha Vantage integration
python alpha_vantage_client.py
```

Expected output:
```
✅ Alpha Vantage Connection Test

🧪 Test 1: Fetching real-time quote for AAPL...
  ✅ AAPL: $180.25 (+0.5%)

🧪 Test 2: Fetching historical daily data for AAPL...
  ✅ Fetched 100 days
     Latest: 2026-04-03 @ $180.25

🧪 Test 3: Fetching company overview...
  ✅ Apple Inc.
     Sector: Technology
     Market Cap: $2,750,000,000,000
```

### 3. Update ATLAS Data Pipeline
```bash
# The system will now use real data instead of synthetic
python main.py --real-data
```

---

## 📡 API Capabilities

### Daily OHLCV Data
```python
from alpha_vantage_client import AlpacaVantageClient

client = AlphaVantageClient(api_key='V28U6XTX4P9CU502')

# Get 20+ years of daily data
daily_data = client.get_daily_data('AAPL', outputsize='full')
print(daily_data.head())
# Output:
#         date   open    high     low   close    volume
# 0 2024-04-01 169.35 170.500 168.950 170.010  52345000
# 1 2024-04-02 170.15 171.200 169.800 170.890  48230000
```

### Real-Time Quotes
```python
quote = client.get_global_quote('AAPL')
print(f"AAPL: ${quote['price']:.2f} ({quote['change_pct']})")
# Output: AAPL: $180.25 (+0.5%)
```

### Company Fundamentals
```python
company = client.get_company_overview('AAPL')
print(f"{company['name']}: {company['sector']}")
print(f"Market Cap: ${company['market_cap']:,.0f}")
print(f"P/E Ratio: {company['pe_ratio']:.2f}")
# Output:
# Apple Inc.: Technology
# Market Cap: $2,750,000,000,000
# P/E Ratio: 28.45
```

### Technical Indicators
```python
# RSI (Relative Strength Index)
rsi = client.get_rsi('AAPL', time_period=14)
print(rsi.head())

# SMA (Simple Moving Average)
sma = client.get_sma('AAPL', time_period=20)
print(sma.head())
```

---

## ⚙️ Integration with ATLAS

### Option 1: Use Alpha Vantage for Historical Data
```python
from alpha_vantage_client import AlphaVantageClient
import pandas as pd

client = AlphaVantageClient(api_key='V28U6XTX4P9CU502')

# Fetch data for S&P 500 stocks
tickers = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META']
all_data = []

for ticker in tickers:
    data = client.get_daily_data(ticker, outputsize='compact')  # compact=100 days, full=20+ years
    data['ticker'] = ticker
    all_data.append(data)

# Combine and save
df = pd.concat(all_data, ignore_index=True)
df.to_parquet('data/real_market_data.parquet', index=False)
```

### Option 2: Use Real-Time Quotes for Current Signals
```python
from alpha_vantage_client import AlphaVantageClient

client = AlphaVantageClient(api_key='V28U6XTX4P9CU502')

# Get current price for position sizing
quote = client.get_global_quote('AAPL')
current_price = quote['price']

# Calculate position size
position_size = portfolio_value * 0.03 / current_price  # 3% per position
```

### Option 3: Use Fundamentals for Feature Engineering
```python
from alpha_vantage_client import AlphaVantageClient

client = AlphaVantageClient(api_key='V28U6XTX4P9CU502')

# Get company fundamentals for features
company = client.get_company_overview('AAPL')

features = {
    'pe_ratio': company['pe_ratio'],
    'dividend_yield': company['dividend_yield'],
    'market_cap': company['market_cap'],
    '52w_high': company['52_week_high'],
    '52w_low': company['52_week_low'],
}
```

---

## 📊 Free vs Premium Tiers

| Feature | Free | Premium |
|---------|------|---------|
| **API Calls/Minute** | 5 | Unlimited |
| **API Calls/Day** | 500 | Unlimited |
| **Data Delay** | Real-time | Real-time |
| **Historical Data** | 20+ years | 20+ years |
| **Indicators** | 50+ | 50+ |
| **Cost** | Free | $24.99/month |

**For MVP:** Free tier is sufficient
- 5 calls/min = ~7,200 calls/day
- ATLAS calls ~30 tickers/day = well within limit

---

## ⚠️ Rate Limiting Tips

### Strategy 1: Batch Fetching
```python
# Fetch all data needed for the day at once
# Save to cache/parquet for rest of day

daily_cache = {}
for ticker in tickers:
    daily_cache[ticker] = client.get_daily_data(ticker)

# Use cache throughout the day
price = daily_cache['AAPL'].iloc[-1]['close']
```

### Strategy 2: Caching
```python
# Cache historical data locally
# Only fetch new data (last 1-2 days)

# Check local cache first
try:
    cached_data = pd.read_parquet(f'cache/{ticker}_daily.parquet')
    # Update with new data
    new_data = client.get_daily_data(ticker, outputsize='compact')
except:
    # First time, fetch full history
    new_data = client.get_daily_data(ticker, outputsize='full')
```

### Strategy 3: Stagger Requests
```python
import time

tickers = ['AAPL', 'MSFT', 'GOOGL', ...]

for ticker in tickers:
    data = client.get_daily_data(ticker)
    time.sleep(0.25)  # 4 requests per second = 240/minute
```

---

## 🔄 Update ATLAS Configuration

### Edit `config.py`
```python
# Set to use Alpha Vantage
USE_REAL_DATA = True
ALPHA_VANTAGE_API_KEY = 'V28U6XTX4P9CU502'

# Or use environment variable
import os
ALPHA_VANTAGE_API_KEY = os.getenv('ALPHA_VANTAGE_API_KEY')
```

### Update Data Pipeline
```bash
# Use real data instead of synthetic
python main.py --real-data --save-cache

# This will:
# 1. Fetch real OHLCV from Alpha Vantage
# 2. Cache to parquet files
# 3. Use cache for subsequent runs
```

---

## 📈 Example: Fetch All S&P 500 Data

```bash
python -c "
from alpha_vantage_client import AlphaVantageClient
import pandas as pd
import time

client = AlphaVantageClient(api_key='V28U6XTX4P9CU502')

# Top 20 stocks to start
tickers = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'NVDA', 'TSLA',
           'JPM', 'JNJ', 'WMT', 'BA', 'GS', 'PG', 'UNH', 'HD',
           'XOM', 'CVX', 'IBM', 'INTC', 'AMD']

all_data = []
for i, ticker in enumerate(tickers):
    print(f'Fetching {ticker} ({i+1}/{len(tickers)})')
    data = client.get_daily_data(ticker, outputsize='compact')
    if not data.empty:
        data['ticker'] = ticker
        all_data.append(data)
    time.sleep(0.5)  # Rate limiting

# Save combined dataset
df = pd.concat(all_data, ignore_index=True)
df.to_parquet('data/real_market_data_20stocks.parquet')
print(f'✅ Saved {len(df)} rows')
"
```

---

## 🎯 Next Steps

1. **Set API key:**
   ```bash
   export ALPHA_VANTAGE_API_KEY='V28U6XTX4P9CU502'
   ```

2. **Test connection:**
   ```bash
   python alpha_vantage_client.py
   ```

3. **Fetch real data:**
   ```bash
   python main.py --real-data
   ```

4. **Train model with real data:**
   ```bash
   python main.py --real-data --train
   ```

5. **Start live trading:**
   ```bash
   python main.py --live-paper
   ```

---

## 📚 Resources

- **Alpha Vantage Documentation:** https://www.alphavantage.co/documentation/
- **API Reference:** https://www.alphavantage.co/api/
- **Supported Symbols:** https://www.alphavantage.co/query?apikey=demo&function=LISTING_STATUS
- **FAQ:** https://www.alphavantage.co/faq/

---

## 🎓 Upgrading to Premium (Optional)

For production with unlimited API calls:
1. Go to: https://www.alphavantage.co/
2. Click "Get Free API Key"
3. Upgrade to Premium ($24.99/month)
4. Update `ALPHA_VANTAGE_API_KEY` in config

**For MVP:** Free tier is perfect - no upgrade needed.

---

**Your API Key:** `V28U6XTX4P9CU502`

**Status:** ✅ Ready to use
**Data Access:** Real-time market data
**Historical Data:** 20+ years available
