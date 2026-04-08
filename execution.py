"""
PROJECT ATLAS - Execution Engine
Order generation, routing, and portfolio management
"""

import logging
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple
from datetime import datetime, timedelta
import config

logger = logging.getLogger(__name__)
logger.setLevel(config.LOG_LEVEL)


class Order:
    """Represents a single order."""

    def __init__(
        self,
        ticker: str,
        quantity: int,
        order_type: str,  # 'BUY', 'SELL'
        price: float = None,
        order_time_type: str = 'LIMIT',  # 'LIMIT', 'MARKET', 'IOC'
        timeout_minutes: int = 5
    ):
        self.ticker = ticker
        self.quantity = quantity
        self.order_type = order_type
        self.price = price
        self.order_time_type = order_time_type
        self.timeout_minutes = timeout_minutes
        self.created_at = datetime.now()
        self.filled_at = None
        self.filled_quantity = 0
        self.filled_price = None
        self.status = 'PENDING'  # PENDING, FILLED, CANCELLED, EXPIRED

    def __repr__(self):
        return f"Order({self.order_type} {self.quantity} {self.ticker} @ ${self.price:.2f})"


class Portfolio:
    """Represents current portfolio state."""

    def __init__(self, initial_cash: float = 1_000_000):
        self.cash = initial_cash
        self.positions = {}  # ticker -> shares
        self.entry_prices = {}  # ticker -> entry price
        self.created_at = datetime.now()
        self.last_rebalance = datetime.now()

    def add_position(self, ticker: str, shares: int, entry_price: float):
        """Add or update position."""
        if ticker in self.positions:
            # Update entry price (average cost)
            old_shares = self.positions[ticker]
            old_price = self.entry_prices[ticker]
            new_shares = old_shares + shares
            if new_shares > 0:
                self.entry_prices[ticker] = (old_shares * old_price + shares * entry_price) / new_shares
        else:
            self.entry_prices[ticker] = entry_price

        self.positions[ticker] = self.positions.get(ticker, 0) + shares

    def remove_position(self, ticker: str, shares: int = None):
        """Remove or reduce position."""
        if ticker not in self.positions:
            return

        if shares is None:
            del self.positions[ticker]
            del self.entry_prices[ticker]
        else:
            self.positions[ticker] -= shares
            if self.positions[ticker] <= 0:
                del self.positions[ticker]
                del self.entry_prices[ticker]

    def get_position_value(self, ticker: str, current_price: float) -> float:
        """Get market value of position."""
        if ticker not in self.positions:
            return 0
        return self.positions[ticker] * current_price

    def get_total_value(self, current_prices: Dict[str, float]) -> float:
        """Get total portfolio value (cash + positions)."""
        total = self.cash
        for ticker, shares in self.positions.items():
            if ticker in current_prices:
                total += shares * current_prices[ticker]
        return total

    def get_position_sizes(self, current_prices: Dict[str, float]) -> Dict[str, float]:
        """Get each position as % of total portfolio value."""
        total_value = self.get_total_value(current_prices)
        sizes = {}

        for ticker, shares in self.positions.items():
            if ticker in current_prices:
                position_value = shares * current_prices[ticker]
                sizes[ticker] = position_value / total_value if total_value > 0 else 0

        return sizes

    def get_exposure(self) -> float:
        """Get gross exposure as % of portfolio."""
        return (self.get_total_value({}) - self.cash) / self.get_total_value({}) if self.get_total_value({}) > 0 else 0


class ExecutionEngine:
    """
    Executes trades and manages portfolio.
    MVP features:
    - Limit orders with timeout
    - TWAP for large trades
    - Slippage modeling
    """

    def __init__(self, initial_cash: float = 1_000_000):
        self.portfolio = Portfolio(initial_cash)
        self.orders = []
        self.trades_log = []
        self.current_prices = {}

    def update_prices(self, prices: Dict[str, float]):
        """Update current market prices."""
        self.current_prices = prices

    def generate_orders_from_signals(
        self,
        signals: pd.DataFrame,  # ticker, signal_strength
        current_prices: Dict[str, float],
        top_n: int = 30,
        target_position_size_pct: float = 0.03
    ) -> List[Order]:
        """
        Generate buy orders from model signals.

        Args:
            signals: DataFrame with ticker and predicted probability
            current_prices: Current market prices
            top_n: Take top N signals
            target_position_size_pct: Target size per position

        Returns:
            List of Order objects
        """
        orders = []

        # Get top signals
        signals_sorted = signals.nlargest(top_n, 'predicted_prob')

        for _, row in signals_sorted.iterrows():
            ticker = row['ticker']
            if ticker not in current_prices:
                continue

            price = current_prices[ticker]
            portfolio_value = self.portfolio.get_total_value(current_prices)

            # Calculate position size
            target_value = portfolio_value * target_position_size_pct
            shares = int(target_value / price)

            if shares > 0:
                # Create limit order at mid-price
                order = Order(
                    ticker=ticker,
                    quantity=shares,
                    order_type='BUY',
                    price=price,
                    order_time_type='LIMIT',
                    timeout_minutes=5
                )
                orders.append(order)

        logger.info(f"Generated {len(orders)} buy orders")
        return orders

    def generate_rebalance_orders(
        self,
        target_positions: Dict[str, float],  # ticker -> target size pct
        current_prices: Dict[str, float]
    ) -> List[Order]:
        """
        Generate orders to rebalance from current to target positions.

        Args:
            target_positions: Desired position sizes (as % of portfolio)
            current_prices: Current market prices

        Returns:
            List of Order objects (buys and sells)
        """
        orders = []
        current_positions = self.portfolio.get_position_sizes(current_prices)
        portfolio_value = self.portfolio.get_total_value(current_prices)

        # Determine sells first (free up cash)
        for ticker in set(list(current_positions.keys()) + list(target_positions.keys())):
            current_size = current_positions.get(ticker, 0)
            target_size = target_positions.get(ticker, 0)

            if target_size < current_size and ticker in self.portfolio.positions:
                # Need to sell
                shares_to_sell = self.portfolio.positions[ticker] - int((target_size * portfolio_value) / current_prices.get(ticker, 1))
                if shares_to_sell > 0:
                    price = current_prices.get(ticker, 0)
                    order = Order(
                        ticker=ticker,
                        quantity=shares_to_sell,
                        order_type='SELL',
                        price=price * 0.99,  # Sell slightly below market to ensure execution
                        order_time_type='LIMIT',
                    )
                    orders.append(order)

        # Then determine buys
        for ticker, target_size in target_positions.items():
            if target_size <= 0:
                continue

            current_size = current_positions.get(ticker, 0)

            if target_size > current_size and ticker in current_prices:
                # Need to buy
                target_value = target_size * portfolio_value
                current_value = current_size * portfolio_value
                value_to_buy = target_value - current_value

                if value_to_buy > 0:
                    price = current_prices[ticker]
                    shares = int(value_to_buy / price)

                    if shares > 0:
                        order = Order(
                            ticker=ticker,
                            quantity=shares,
                            order_type='BUY',
                            price=price,
                            order_time_type='LIMIT',
                        )
                        orders.append(order)

        logger.info(f"Generated {len(orders)} rebalance orders ({sum(1 for o in orders if o.order_type == 'BUY')} buys, {sum(1 for o in orders if o.order_type == 'SELL')} sells)")
        return orders

    def execute_order(self, order: Order, execution_slippage_pct: float = 0.001) -> bool:
        """
        Execute an order with realistic slippage.

        Args:
            order: Order to execute
            execution_slippage_pct: Slippage as % of execution price

        Returns:
            True if executed, False if failed
        """
        try:
            # Check if order has expired
            age_minutes = (datetime.now() - order.created_at).total_seconds() / 60
            if age_minutes > order.timeout_minutes:
                order.status = 'EXPIRED'
                logger.warning(f"Order expired: {order}")
                return False

            # Check cash availability for buys
            if order.order_type == 'BUY':
                cost = order.quantity * order.price * (1 + execution_slippage_pct)
                if cost > self.portfolio.cash:
                    logger.warning(f"Insufficient cash for {order}")
                    return False

            # Execute order
            if order.order_type == 'BUY':
                filled_price = order.price * (1 + execution_slippage_pct)
                cost = order.quantity * filled_price
                self.portfolio.cash -= cost
                self.portfolio.add_position(order.ticker, order.quantity, filled_price)

            elif order.order_type == 'SELL':
                filled_price = order.price * (1 - execution_slippage_pct)
                proceeds = order.quantity * filled_price
                self.portfolio.cash += proceeds
                self.portfolio.remove_position(order.ticker, order.quantity)

            # Update order status
            order.filled_at = datetime.now()
            order.filled_quantity = order.quantity
            order.filled_price = filled_price if order.order_type == 'BUY' else filled_price
            order.status = 'FILLED'

            # Log trade
            self.trades_log.append({
                'timestamp': order.filled_at,
                'ticker': order.ticker,
                'type': order.order_type,
                'quantity': order.quantity,
                'price': order.filled_price,
                'value': order.quantity * order.filled_price,
            })

            logger.info(f"Order executed: {order.order_type} {order.quantity} {order.ticker} @ ${order.filled_price:.2f}")
            return True

        except Exception as e:
            logger.error(f"Error executing order: {e}")
            return False

    def execute_orders(self, orders: List[Order]) -> List[bool]:
        """Execute multiple orders."""
        results = []
        for order in orders:
            results.append(self.execute_order(order))
        return results

    def get_portfolio_summary(self) -> Dict:
        """Get summary of current portfolio."""
        portfolio_value = self.portfolio.get_total_value(self.current_prices)
        positions = self.portfolio.get_position_sizes(self.current_prices)

        return {
            'timestamp': datetime.now(),
            'total_value': portfolio_value,
            'cash': self.portfolio.cash,
            'cash_pct': self.portfolio.cash / portfolio_value if portfolio_value > 0 else 1,
            'positions': positions,
            'num_positions': len(self.portfolio.positions),
            'gross_exposure': sum(positions.values()),
        }

    def get_daily_pnl(self, prices_start: Dict[str, float], prices_end: Dict[str, float]) -> Dict:
        """Calculate daily P&L."""
        pnl = 0
        pnl_by_position = {}

        for ticker, shares in self.portfolio.positions.items():
            if ticker in prices_start and ticker in prices_end:
                start_price = prices_start[ticker]
                end_price = prices_end[ticker]
                entry_price = self.portfolio.entry_prices[ticker]

                position_pnl = shares * (end_price - start_price)
                pnl += position_pnl
                pnl_by_position[ticker] = position_pnl

        return {
            'total_pnl': pnl,
            'pnl_by_position': pnl_by_position,
            'timestamp': datetime.now(),
        }


if __name__ == "__main__":
    logging.basicConfig(format=config.LOG_FORMAT)
    logger.info("Execution engine module loaded")
