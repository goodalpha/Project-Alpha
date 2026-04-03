"""
PROJECT ATLAS - Alpaca Trading Integration (alpaca-py)
Modern SDK for paper trading and live trading
"""

import os
import logging
from typing import Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)
logger.setLevel("INFO")

try:
    from alpaca.trading.client import TradingClient
    from alpaca.trading.requests import MarketOrderRequest, LimitOrderRequest
    from alpaca.trading.enums import OrderSide, TimeInForce
    ALPACA_PY_AVAILABLE = True
except ImportError:
    ALPACA_PY_AVAILABLE = False
    logger.warning("alpaca-py not installed. Install with: pip install alpaca-py")


class AlpacaTrader:
    """
    Connects to Alpaca using the modern alpaca-py SDK.
    Handles paper trading and live trading with authentication.
    """

    def __init__(
        self,
        api_key: str = None,
        secret_key: str = None,
        paper: bool = True
    ):
        """
        Initialize Alpaca trader.

        Args:
            api_key: API key (or APCA_API_KEY_ID env var)
            secret_key: Secret key (or APCA_API_SECRET_KEY env var)
            paper: Use paper trading (True) or live trading (False)
        """
        if not ALPACA_PY_AVAILABLE:
            raise ImportError(
                "alpaca-py not installed.\n"
                "Install with: pip install alpaca-py\n"
                "Then set environment variables:\n"
                "  export APCA_API_KEY_ID='your_key'\n"
                "  export APCA_API_SECRET_KEY='your_secret'"
            )

        # Get credentials
        self.api_key = api_key or os.getenv('APCA_API_KEY_ID')
        self.secret_key = secret_key or os.getenv('APCA_API_SECRET_KEY')
        self.paper = paper

        if not self.api_key or not self.secret_key:
            raise ValueError(
                "Missing Alpaca credentials.\n"
                "Set environment variables:\n"
                "  export APCA_API_KEY_ID='your_key'\n"
                "  export APCA_API_SECRET_KEY='your_secret'"
            )

        # Initialize client
        self.client = TradingClient(
            api_key=self.api_key,
            secret_key=self.secret_key,
            paper=paper
        )

        mode = "PAPER TRADING" if paper else "LIVE TRADING"
        logger.info(f"✅ Connected to Alpaca: {mode}")

    def get_account(self) -> Dict:
        """Get account information."""
        try:
            account = self.client.get_account()
            return {
                'account_number': account.account_number,
                'buying_power': float(account.buying_power),
                'cash': float(account.cash),
                'portfolio_value': float(account.portfolio_value),
                'equity': float(account.equity),
                'regt_buying_power': float(account.regt_buying_power),
                'daytrade_buying_power': float(account.daytrade_buying_power),
                'status': account.status,
                'trading_suspended': account.trading_suspended,
            }
        except Exception as e:
            logger.error(f"Error fetching account: {e}")
            return {}

    def get_positions(self) -> List[Dict]:
        """Get all open positions."""
        try:
            positions = self.client.get_all_positions()
            return [
                {
                    'symbol': pos.symbol,
                    'quantity': float(pos.qty),
                    'avg_fill_price': float(pos.avg_fill_price),
                    'market_value': float(pos.market_value),
                    'unrealized_gain': float(pos.unrealized_gain),
                    'unrealized_gain_pct': float(pos.unrealized_gain_pct),
                    'side': pos.side.value if pos.side else None,
                }
                for pos in positions
            ]
        except Exception as e:
            logger.error(f"Error fetching positions: {e}")
            return []

    def place_market_order(
        self,
        symbol: str,
        qty: int,
        side: str,  # 'buy' or 'sell'
        time_in_force: str = 'day'
    ) -> Dict:
        """
        Place a market order.

        Args:
            symbol: Ticker symbol
            qty: Number of shares
            side: 'buy' or 'sell'
            time_in_force: 'day', 'gtc', 'opg', 'cls'

        Returns:
            Order details
        """
        try:
            order_side = OrderSide.BUY if side.lower() == 'buy' else OrderSide.SELL
            tif = TimeInForce(time_in_force.upper())

            request = MarketOrderRequest(
                symbol=symbol,
                qty=qty,
                side=order_side,
                time_in_force=tif
            )

            order = self.client.submit_order(request)

            logger.info(f"Market order: {side.upper()} {qty} {symbol}")

            return {
                'id': order.id,
                'symbol': order.symbol,
                'qty': float(order.qty),
                'side': order.side.value,
                'order_type': order.order_type.value,
                'status': order.status.value,
                'created_at': order.created_at.isoformat() if order.created_at else None,
                'filled_qty': float(order.filled_qty) if order.filled_qty else 0,
                'filled_avg_price': float(order.filled_avg_price) if order.filled_avg_price else None,
            }

        except Exception as e:
            logger.error(f"Error placing market order: {e}")
            return {}

    def place_limit_order(
        self,
        symbol: str,
        qty: int,
        side: str,
        limit_price: float,
        time_in_force: str = 'day'
    ) -> Dict:
        """
        Place a limit order.

        Args:
            symbol: Ticker symbol
            qty: Number of shares
            side: 'buy' or 'sell'
            limit_price: Limit price
            time_in_force: 'day', 'gtc', etc.

        Returns:
            Order details
        """
        try:
            order_side = OrderSide.BUY if side.lower() == 'buy' else OrderSide.SELL
            tif = TimeInForce(time_in_force.upper())

            request = LimitOrderRequest(
                symbol=symbol,
                qty=qty,
                side=order_side,
                limit_price=limit_price,
                time_in_force=tif
            )

            order = self.client.submit_order(request)

            logger.info(f"Limit order: {side.upper()} {qty} {symbol} @ ${limit_price}")

            return {
                'id': order.id,
                'symbol': order.symbol,
                'qty': float(order.qty),
                'side': order.side.value,
                'order_type': order.order_type.value,
                'limit_price': float(order.limit_price) if order.limit_price else None,
                'status': order.status.value,
                'created_at': order.created_at.isoformat() if order.created_at else None,
            }

        except Exception as e:
            logger.error(f"Error placing limit order: {e}")
            return {}

    def cancel_order(self, order_id: str) -> bool:
        """Cancel an order."""
        try:
            self.client.cancel_order_by_id(order_id)
            logger.info(f"Order cancelled: {order_id}")
            return True
        except Exception as e:
            logger.error(f"Error cancelling order: {e}")
            return False

    def get_orders(self, status: str = 'open', limit: int = 10) -> List[Dict]:
        """
        Get orders.

        Args:
            status: 'open', 'closed', 'all'
            limit: Maximum number of orders to return

        Returns:
            List of orders
        """
        try:
            orders = self.client.get_orders(
                status=status,
                limit=limit
            )

            return [
                {
                    'id': o.id,
                    'symbol': o.symbol,
                    'qty': float(o.qty) if o.qty else 0,
                    'side': o.side.value if o.side else None,
                    'order_type': o.order_type.value if o.order_type else None,
                    'status': o.status.value if o.status else None,
                    'limit_price': float(o.limit_price) if o.limit_price else None,
                    'created_at': o.created_at.isoformat() if o.created_at else None,
                    'filled_qty': float(o.filled_qty) if o.filled_qty else 0,
                    'filled_avg_price': float(o.filled_avg_price) if o.filled_avg_price else None,
                }
                for o in orders
            ]

        except Exception as e:
            logger.error(f"Error fetching orders: {e}")
            return []

    def get_order(self, order_id: str) -> Dict:
        """Get a specific order."""
        try:
            order = self.client.get_order_by_id(order_id)
            return {
                'id': order.id,
                'symbol': order.symbol,
                'status': order.status.value,
                'filled_qty': float(order.filled_qty) if order.filled_qty else 0,
                'filled_avg_price': float(order.filled_avg_price) if order.filled_avg_price else None,
            }
        except Exception as e:
            logger.error(f"Error fetching order: {e}")
            return {}

    def close_position(self, symbol: str) -> Dict:
        """Close a position by selling all shares."""
        try:
            # Get current position
            position = self.client.get_position(symbol)
            if not position or float(position.qty) == 0:
                logger.warning(f"No open position for {symbol}")
                return {}

            # Close by selling all
            qty = abs(int(float(position.qty)))
            order = self.place_market_order(
                symbol=symbol,
                qty=qty,
                side='sell' if float(position.qty) > 0 else 'buy'
            )

            logger.info(f"Position closed: {symbol}")
            return order

        except Exception as e:
            logger.error(f"Error closing position: {e}")
            return {}

    def get_clock(self) -> Dict:
        """Get market clock information."""
        try:
            clock = self.client.get_clock()
            return {
                'timestamp': clock.timestamp.isoformat() if clock.timestamp else None,
                'is_open': clock.is_open,
                'next_open': clock.next_open.isoformat() if clock.next_open else None,
                'next_close': clock.next_close.isoformat() if clock.next_close else None,
            }
        except Exception as e:
            logger.error(f"Error fetching market clock: {e}")
            return {}


def test_connection(paper: bool = True):
    """Test Alpaca connection."""
    try:
        print("\n" + "="*70)
        print("PROJECT ATLAS - Alpaca Connection Test".center(70))
        print("="*70 + "\n")

        trader = AlpacaTrader(paper=paper)

        print("✅ CONNECTION SUCCESSFUL\n")

        # Get account info
        account = trader.get_account()
        print("Account Information:")
        print(f"  Portfolio Value: ${account.get('portfolio_value', 0):,.2f}")
        print(f"  Cash: ${account.get('cash', 0):,.2f}")
        print(f"  Buying Power: ${account.get('buying_power', 0):,.2f}")
        print(f"  Status: {account.get('status', 'Unknown')}")
        print(f"  Trading Suspended: {account.get('trading_suspended', False)}")

        # Get market clock
        clock = trader.get_clock()
        print(f"\nMarket Status:")
        print(f"  Open: {clock.get('is_open', 'Unknown')}")
        print(f"  Next Open: {clock.get('next_open', 'Unknown')}")

        # Get positions
        positions = trader.get_positions()
        print(f"\nOpen Positions: {len(positions)}")
        for pos in positions[:5]:  # Show first 5
            print(f"  {pos['symbol']}: {pos['quantity']} shares @ ${pos['avg_fill_price']:.2f}")

        # Get orders
        orders = trader.get_orders(status='open', limit=5)
        print(f"\nOpen Orders: {len(orders)}")
        for order in orders[:5]:
            print(f"  {order['symbol']}: {order['side'].upper()} {order['qty']} @ {order['status']}")

        mode = "PAPER TRADING" if paper else "LIVE TRADING"
        print(f"\n✅ Ready for {mode}!")
        print("="*70 + "\n")

        return True

    except Exception as e:
        print(f"\n❌ Connection Failed: {e}\n")
        print("Setup Instructions:")
        print("1. Set environment variables:")
        print("   export APCA_API_KEY_ID='your_api_key'")
        print("   export APCA_API_SECRET_KEY='your_secret_key'")
        print("\n2. Get credentials from: https://app.alpaca.markets/settings/keys")
        print()
        return False


if __name__ == "__main__":
    import sys

    # Test paper trading by default
    paper = '--live' not in sys.argv

    test_connection(paper=paper)
