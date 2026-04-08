"""
PROJECT ATLAS - Alpaca Paper Trading Integration
Handles authentication, account management, and order execution
"""

import os
import logging
from typing import Dict, List, Optional
from datetime import datetime
import json

logger = logging.getLogger(__name__)
logger.setLevel("INFO")

# Try to import alpaca, but handle gracefully if not installed
try:
    from alpaca_trade_api import REST
    ALPACA_AVAILABLE = True
except ImportError:
    ALPACA_AVAILABLE = False
    logger.warning("alpaca-trade-api not installed. Install with: pip install alpaca-trade-api")


class AlpacaConnector:
    """
    Connects to Alpaca paper trading API.
    Handles authentication, account info, orders, and positions.
    """

    def __init__(self, api_key: str = None, secret_key: str = None, base_url: str = None):
        """
        Initialize Alpaca connector.

        Args:
            api_key: Alpaca API key (or set APCA_API_KEY_ID env var)
            secret_key: Alpaca secret key (or set APCA_API_SECRET_KEY env var)
            base_url: Alpaca base URL (defaults to paper trading)
        """
        if not ALPACA_AVAILABLE:
            raise ImportError(
                "alpaca-trade-api not installed.\n"
                "Install with: pip install alpaca-trade-api\n"
                "Then set environment variables:\n"
                "  export APCA_API_KEY_ID='your_key'\n"
                "  export APCA_API_SECRET_KEY='your_secret'"
            )

        # Get credentials from arguments or environment
        self.api_key = api_key or os.getenv('APCA_API_KEY_ID')
        self.secret_key = secret_key or os.getenv('APCA_API_SECRET_KEY')
        self.base_url = base_url or 'https://paper-api.alpaca.markets'

        if not self.api_key or not self.secret_key:
            raise ValueError(
                "Missing Alpaca credentials. Set via:\n"
                "1. Environment variables:\n"
                "   export APCA_API_KEY_ID='your_key'\n"
                "   export APCA_API_SECRET_KEY='your_secret'\n"
                "2. Or pass to __init__:\n"
                "   connector = AlpacaConnector(api_key='...', secret_key='...')"
            )

        # Initialize REST client
        self.api = REST(
            key_id=self.api_key,
            secret_key=self.secret_key,
            base_url=self.base_url
        )

        logger.info(f"Connected to Alpaca: {self.base_url}")

    def get_account(self) -> Dict:
        """Get account information."""
        try:
            account = self.api.get_account()
            return {
                'cash': float(account.cash),
                'portfolio_value': float(account.portfolio_value),
                'buying_power': float(account.buying_power),
                'multiplier': float(account.multiplier),
                'equity': float(account.equity),
                'day_trading_buying_power': float(account.daytrading_buying_power),
            }
        except Exception as e:
            logger.error(f"Error fetching account: {e}")
            return {}

    def get_positions(self) -> List[Dict]:
        """Get all open positions."""
        try:
            positions = self.api.list_positions()
            return [
                {
                    'symbol': pos.symbol,
                    'qty': float(pos.qty),
                    'avg_fill_price': float(pos.avg_fill_price),
                    'market_value': float(pos.market_value),
                    'unrealized_pl': float(pos.unrealized_pl),
                    'unrealized_plpc': float(pos.unrealized_plpc),
                    'side': pos.side,
                }
                for pos in positions
            ]
        except Exception as e:
            logger.error(f"Error fetching positions: {e}")
            return []

    def place_order(
        self,
        symbol: str,
        qty: int,
        side: str,  # 'buy' or 'sell'
        order_type: str = 'market',  # 'market', 'limit'
        limit_price: float = None,
        time_in_force: str = 'day'
    ) -> Dict:
        """
        Place an order on Alpaca.

        Args:
            symbol: Ticker symbol (e.g., 'AAPL')
            qty: Number of shares
            side: 'buy' or 'sell'
            order_type: 'market' or 'limit'
            limit_price: Price for limit orders
            time_in_force: 'day', 'gtc' (good-til-cancelled), etc.

        Returns:
            Order details
        """
        try:
            if order_type == 'limit' and limit_price is None:
                raise ValueError("limit_price required for limit orders")

            order = self.api.submit_order(
                symbol=symbol,
                qty=qty,
                side=side,
                type=order_type,
                limit_price=limit_price,
                time_in_force=time_in_force
            )

            logger.info(f"Order placed: {side.upper()} {qty} {symbol} @ {limit_price or 'market'}")

            return {
                'id': order.id,
                'symbol': order.symbol,
                'qty': float(order.qty),
                'side': order.side,
                'type': order.order_type,
                'status': order.status,
                'filled_avg_price': float(order.filled_avg_price) if order.filled_avg_price else None,
                'filled_qty': float(order.filled_qty) if order.filled_qty else 0,
            }

        except Exception as e:
            logger.error(f"Error placing order: {e}")
            return {}

    def cancel_order(self, order_id: str) -> bool:
        """Cancel an open order."""
        try:
            self.api.cancel_order(order_id)
            logger.info(f"Order cancelled: {order_id}")
            return True
        except Exception as e:
            logger.error(f"Error cancelling order: {e}")
            return False

    def get_orders(self, status: str = 'open') -> List[Dict]:
        """
        Get orders.

        Args:
            status: 'open', 'closed', 'all'

        Returns:
            List of orders
        """
        try:
            orders = self.api.list_orders(status=status)
            return [
                {
                    'id': o.id,
                    'symbol': o.symbol,
                    'qty': float(o.qty),
                    'side': o.side,
                    'status': o.status,
                    'created_at': o.created_at.isoformat(),
                    'filled_qty': float(o.filled_qty) if o.filled_qty else 0,
                    'filled_avg_price': float(o.filled_avg_price) if o.filled_avg_price else None,
                }
                for o in orders
            ]
        except Exception as e:
            logger.error(f"Error fetching orders: {e}")
            return []

    def get_latest_quote(self, symbol: str) -> Dict:
        """Get latest quote for a symbol."""
        try:
            quote = self.api.get_latest_quote(symbol)
            if quote:
                return {
                    'bid': float(quote.bid_price),
                    'ask': float(quote.ask_price),
                    'mid': (float(quote.bid_price) + float(quote.ask_price)) / 2,
                }
            return {}
        except Exception as e:
            logger.error(f"Error fetching quote for {symbol}: {e}")
            return {}

    def close_position(self, symbol: str) -> Dict:
        """Close an entire position."""
        try:
            order = self.api.close_position(symbol)
            logger.info(f"Position closed: {symbol}")
            return {
                'id': order.id,
                'symbol': order.symbol,
                'status': order.status,
            }
        except Exception as e:
            logger.error(f"Error closing position: {e}")
            return {}


# ============================================================================
# SETUP INSTRUCTIONS & TESTING
# ============================================================================

def get_setup_instructions() -> str:
    """Return setup instructions for Alpaca."""
    return """
╔══════════════════════════════════════════════════════════════════════════╗
║           ATLAS - ALPACA PAPER TRADING SETUP                            ║
╚══════════════════════════════════════════════════════════════════════════╝

1. CREATE ALPACA ACCOUNT (FREE)
   ├─ Go to: https://app.alpaca.markets
   ├─ Sign up for free account
   └─ Create API keys in Settings → API Keys

2. GET YOUR API CREDENTIALS
   ├─ Login to https://app.alpaca.markets
   ├─ Go to Settings → API Keys
   ├─ Copy your API Key ID (looks like: PKXXX...)
   └─ Copy your Secret Key (shown only once!)

3. SET ENVIRONMENT VARIABLES
   Option A: One-time (current session only)
   $ export APCA_API_KEY_ID='your_api_key_here'
   $ export APCA_API_SECRET_KEY='your_secret_key_here'

   Option B: Persistent (.bashrc or .bash_profile)
   Add these lines to ~/.bashrc:
   export APCA_API_KEY_ID='your_api_key_here'
   export APCA_API_SECRET_KEY='your_secret_key_here'

   Then reload:
   $ source ~/.bashrc

4. INSTALL ALPACA LIBRARY
   $ pip install alpaca-trade-api

5. TEST CONNECTION
   $ python -c "from alpaca_integration import test_connection; test_connection()"

6. RUN ATLAS WITH LIVE TRADING
   $ python main.py --live

═══════════════════════════════════════════════════════════════════════════

IMPORTANT NOTES:
• Always test on PAPER TRADING first (default)
• Paper trading is 100% risk-free simulation
• Your real money is NOT at risk
• Paper trading account resets daily at market close
• Once validated, you can enable live trading (requires real capital)

TROUBLESHOOTING:
✗ 403 Forbidden → Missing/invalid API credentials
✗ Connection refused → Alpaca API down (check https://status.alpaca.markets)
✗ Insufficient buying power → You have open positions using margin

═══════════════════════════════════════════════════════════════════════════
"""


def test_connection():
    """Test Alpaca connection and print account status."""
    try:
        print(get_setup_instructions())

        connector = AlpacaConnector()

        print("\n✅ CONNECTION SUCCESSFUL\n")

        # Get account info
        account = connector.get_account()
        print("Account Information:")
        print(f"  Portfolio Value: ${account.get('portfolio_value', 0):,.2f}")
        print(f"  Cash: ${account.get('cash', 0):,.2f}")
        print(f"  Buying Power: ${account.get('buying_power', 0):,.2f}")
        print(f"  Day Trading Buying Power: ${account.get('day_trading_buying_power', 0):,.2f}")

        # Get positions
        positions = connector.get_positions()
        print(f"\nOpen Positions: {len(positions)}")
        for pos in positions:
            print(f"  {pos['symbol']}: {pos['qty']} shares @ ${pos['avg_fill_price']:.2f}")

        # Get orders
        orders = connector.get_orders(status='open')
        print(f"\nOpen Orders: {len(orders)}")
        for order in orders:
            print(f"  {order['symbol']}: {order['side'].upper()} {order['qty']} @ {order['status']}")

        print("\n✅ Ready for paper trading!")

    except Exception as e:
        print(f"\n❌ Connection Failed: {e}\n")
        print(get_setup_instructions())


if __name__ == "__main__":
    test_connection()
