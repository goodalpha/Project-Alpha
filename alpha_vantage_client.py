"""
PROJECT ATLAS - Alpha Vantage Integration
Real market data: daily OHLCV, technical indicators, fundamentals
"""

import os
import logging
import pandas as pd
import requests
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import time

logger = logging.getLogger(__name__)
logger.setLevel("INFO")

# Alpha Vantage API configuration
AV_API_KEY = os.getenv('ALPHA_VANTAGE_API_KEY')
AV_BASE_URL = "https://www.alphavantage.co/query"

# Rate limiting: 5 API calls per minute on free tier
# Use this to avoid hitting rate limits
RATE_LIMIT_DELAY = 0.25  # seconds between calls


class AlphaVantageClient:
    """
    Client for Alpha Vantage API.
    Fetches real market data: OHLCV, fundamentals, technical indicators.
    """

    def __init__(self, api_key: str = None):
        """
        Initialize Alpha Vantage client.

        Args:
            api_key: Alpha Vantage API key (or ALPHA_VANTAGE_API_KEY env var)
        """
        self.api_key = api_key or os.getenv('ALPHA_VANTAGE_API_KEY')

        if not self.api_key:
            raise ValueError(
                "Missing Alpha Vantage API key.\n"
                "Set via environment variable:\n"
                "  export ALPHA_VANTAGE_API_KEY='your_key_here'\n"
                "Get free key: https://www.alphavantage.co/api/"
            )

        logger.info("✅ Alpha Vantage client initialized")

    def _make_request(self, params: Dict) -> Dict:
        """Make API request with rate limiting."""
        params['apikey'] = self.api_key

        try:
            response = requests.get(AV_BASE_URL, params=params, timeout=10)
            response.raise_for_status()

            data = response.json()

            # Check for API errors
            if 'Error Message' in data:
                logger.error(f"API Error: {data['Error Message']}")
                return {}

            if 'Note' in data:
                logger.warning(f"API Note: {data['Note']} (rate limited)")
                return {}

            time.sleep(RATE_LIMIT_DELAY)  # Rate limiting
            return data

        except Exception as e:
            logger.error(f"Error making API request: {e}")
            return {}

    def get_daily_data(
        self,
        symbol: str,
        outputsize: str = 'full'  # 'compact' (100 days) or 'full' (20+ years)
    ) -> pd.DataFrame:
        """
        Fetch daily OHLCV data for a symbol.

        Args:
            symbol: Ticker symbol (e.g., 'AAPL')
            outputsize: 'compact' or 'full'

        Returns:
            DataFrame with columns: date, open, high, low, close, volume
        """
        logger.info(f"Fetching daily data for {symbol}...")

        params = {
            'function': 'TIME_SERIES_DAILY',
            'symbol': symbol,
            'outputsize': outputsize
        }

        data = self._make_request(params)

        if not data or 'Time Series (Daily)' not in data:
            logger.warning(f"No data returned for {symbol}")
            return pd.DataFrame()

        # Parse response
        time_series = data['Time Series (Daily)']
        records = []

        for date_str, daily_data in time_series.items():
            records.append({
                'date': pd.Timestamp(date_str),
                'open': float(daily_data['1. open']),
                'high': float(daily_data['2. high']),
                'low': float(daily_data['3. low']),
                'close': float(daily_data['4. close']),
                'volume': int(daily_data['5. volume']),
            })

        df = pd.DataFrame(records)
        df = df.sort_values('date').reset_index(drop=True)

        logger.info(f"✅ Fetched {len(df)} days of data for {symbol}")
        return df

    def get_intraday_data(
        self,
        symbol: str,
        interval: str = '60min'  # '1min', '5min', '15min', '30min', '60min'
    ) -> pd.DataFrame:
        """
        Fetch intraday OHLCV data.

        Args:
            symbol: Ticker symbol
            interval: Time interval

        Returns:
            DataFrame with intraday data
        """
        logger.info(f"Fetching {interval} intraday data for {symbol}...")

        params = {
            'function': 'TIME_SERIES_INTRADAY',
            'symbol': symbol,
            'interval': interval,
            'outputsize': 'full'
        }

        data = self._make_request(params)

        if not data:
            return pd.DataFrame()

        # Find the time series key (varies by interval)
        ts_key = None
        for key in data.keys():
            if 'Time Series' in key:
                ts_key = key
                break

        if not ts_key:
            logger.warning(f"No time series data for {symbol}")
            return pd.DataFrame()

        # Parse response
        time_series = data[ts_key]
        records = []

        for datetime_str, intraday_data in time_series.items():
            records.append({
                'datetime': pd.Timestamp(datetime_str),
                'open': float(intraday_data['1. open']),
                'high': float(intraday_data['2. high']),
                'low': float(intraday_data['3. low']),
                'close': float(intraday_data['4. close']),
                'volume': int(intraday_data['5. volume']),
            })

        df = pd.DataFrame(records)
        df = df.sort_values('datetime').reset_index(drop=True)

        logger.info(f"✅ Fetched {len(df)} data points for {symbol}")
        return df

    def get_global_quote(self, symbol: str) -> Dict:
        """
        Get latest quote for a symbol.

        Args:
            symbol: Ticker symbol

        Returns:
            Dict with latest price and metrics
        """
        params = {
            'function': 'GLOBAL_QUOTE',
            'symbol': symbol
        }

        data = self._make_request(params)

        if not data or 'Global Quote' not in data:
            return {}

        quote = data['Global Quote']

        return {
            'symbol': quote.get('01. symbol'),
            'price': float(quote.get('05. price', 0)),
            'volume': int(quote.get('06. volume', 0)),
            'timestamp': quote.get('07. latest trading day'),
            'change': float(quote.get('09. change', 0)),
            'change_pct': quote.get('10. change percent', '0%'),
        }

    def get_company_overview(self, symbol: str) -> Dict:
        """
        Get company overview (fundamentals).

        Args:
            symbol: Ticker symbol

        Returns:
            Dict with company info
        """
        logger.info(f"Fetching company overview for {symbol}...")

        params = {
            'function': 'OVERVIEW',
            'symbol': symbol
        }

        data = self._make_request(params)

        if not data:
            return {}

        return {
            'symbol': data.get('Symbol'),
            'name': data.get('Name'),
            'sector': data.get('Sector'),
            'industry': data.get('Industry'),
            'market_cap': int(float(data.get('MarketCapitalization', 0))),
            'pe_ratio': float(data.get('PERatio', 0)) if data.get('PERatio') != 'None' else None,
            'dividend_yield': float(data.get('DividendYield', 0)) if data.get('DividendYield') else 0,
            '52_week_high': float(data.get('52WeekHigh', 0)) if data.get('52WeekHigh') else 0,
            '52_week_low': float(data.get('52WeekLow', 0)) if data.get('52WeekLow') else 0,
            'profit_margin': float(data.get('ProfitMargin', 0)) if data.get('ProfitMargin') else 0,
        }

    def get_sma(
        self,
        symbol: str,
        interval: str = 'daily',
        time_period: int = 20,
        series_type: str = 'close'
    ) -> pd.DataFrame:
        """
        Get Simple Moving Average.

        Args:
            symbol: Ticker symbol
            interval: 'daily', 'weekly', 'monthly'
            time_period: Number of periods
            series_type: 'close', 'open', 'high', 'low'

        Returns:
            DataFrame with SMA values
        """
        params = {
            'function': 'SMA',
            'symbol': symbol,
            'interval': interval,
            'time_period': time_period,
            'series_type': series_type
        }

        data = self._make_request(params)

        if not data or 'Technical Analysis: SMA' not in data:
            return pd.DataFrame()

        ta_data = data['Technical Analysis: SMA']
        records = []

        for date_str, sma_data in ta_data.items():
            records.append({
                'date': pd.Timestamp(date_str),
                'sma': float(sma_data['SMA']),
            })

        df = pd.DataFrame(records)
        df = df.sort_values('date').reset_index(drop=True)

        logger.info(f"✅ Fetched {len(df)} SMA values for {symbol}")
        return df

    def get_rsi(
        self,
        symbol: str,
        interval: str = 'daily',
        time_period: int = 14,
        series_type: str = 'close'
    ) -> pd.DataFrame:
        """
        Get Relative Strength Index.

        Args:
            symbol: Ticker symbol
            interval: 'daily', 'weekly', 'monthly'
            time_period: Number of periods (typically 14)
            series_type: 'close', 'open', 'high', 'low'

        Returns:
            DataFrame with RSI values
        """
        params = {
            'function': 'RSI',
            'symbol': symbol,
            'interval': interval,
            'time_period': time_period,
            'series_type': series_type
        }

        data = self._make_request(params)

        if not data or 'Technical Analysis: RSI' not in data:
            return pd.DataFrame()

        ta_data = data['Technical Analysis: RSI']
        records = []

        for date_str, rsi_data in ta_data.items():
            records.append({
                'date': pd.Timestamp(date_str),
                'rsi': float(rsi_data['RSI']),
            })

        df = pd.DataFrame(records)
        df = df.sort_values('date').reset_index(drop=True)

        logger.info(f"✅ Fetched {len(df)} RSI values for {symbol}")
        return df


def test_connection(api_key: str = None):
    """Test Alpha Vantage connection."""
    try:
        client = AlphaVantageClient(api_key=api_key)

        print("\n" + "="*70)
        print("Alpha Vantage Connection Test".center(70))
        print("="*70 + "\n")

        # Test 1: Get quote
        print("🧪 Test 1: Fetching real-time quote for AAPL...")
        quote = client.get_global_quote('AAPL')
        if quote:
            print(f"  ✅ AAPL: ${quote['price']:.2f} ({quote['change_pct']})")
        else:
            print("  ⚠️  Quote not available (might be rate limited)")

        # Test 2: Get daily data
        print("\n🧪 Test 2: Fetching historical daily data for AAPL...")
        daily_data = client.get_daily_data('AAPL', outputsize='compact')
        if not daily_data.empty:
            print(f"  ✅ Fetched {len(daily_data)} days")
            print(f"     Latest: {daily_data.iloc[-1]['date'].date()} @ ${daily_data.iloc[-1]['close']:.2f}")
        else:
            print("  ⚠️  Data not available")

        # Test 3: Get company info
        print("\n🧪 Test 3: Fetching company overview...")
        company = client.get_company_overview('AAPL')
        if company:
            print(f"  ✅ {company.get('name', 'Apple')}")
            print(f"     Sector: {company.get('sector')}")
            print(f"     Market Cap: ${company.get('market_cap', 0):,.0f}")
        else:
            print("  ⚠️  Company info not available")

        print("\n" + "="*70)
        print("✅ Connection test complete!")
        print("="*70 + "\n")

        return True

    except Exception as e:
        print(f"\n❌ Connection failed: {e}\n")
        return False


if __name__ == "__main__":
    import sys

    api_key = None
    if len(sys.argv) > 1:
        api_key = sys.argv[1]

    test_connection(api_key=api_key)
