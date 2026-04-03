"""
PROJECT ATLAS - TradingView Webhook Integration
Receive trading signals from TradingView and execute via Alpaca
"""

import os
import json
import logging
from datetime import datetime
from typing import Dict, Optional
from flask import Flask, request, jsonify
import hashlib
import hmac

logger = logging.getLogger(__name__)
logger.setLevel("INFO")

# Initialize Flask app
app = Flask(__name__)

# TradingView webhook secret (set via environment variable for security)
TRADINGVIEW_SECRET = os.getenv('TRADINGVIEW_WEBHOOK_SECRET', 'your_secret_here')

# Optional: Alpaca integration for auto-execution
try:
    from alpaca_trader import AlpacaTrader
    ALPACA_AVAILABLE = True
except ImportError:
    ALPACA_AVAILABLE = False


class TradingViewSignal:
    """Represents a signal from TradingView."""

    def __init__(self, data: Dict):
        self.timestamp = datetime.now()
        self.symbol = data.get('symbol', '').upper()
        self.action = data.get('action', '').lower()  # 'buy', 'sell', 'close'
        self.quantity = float(data.get('quantity', 1))
        self.price = float(data.get('price', 0))
        self.strategy = data.get('strategy', 'ATLAS')
        self.comment = data.get('comment', '')
        self.raw_data = data

    def validate(self) -> tuple[bool, str]:
        """Validate signal data."""
        if not self.symbol:
            return False, "Missing symbol"
        if self.action not in ['buy', 'sell', 'close']:
            return False, f"Invalid action: {self.action}"
        if self.quantity <= 0:
            return False, "Invalid quantity"
        return True, "Valid"

    def __repr__(self):
        return f"TradingViewSignal({self.symbol} {self.action} {self.quantity} @ {self.timestamp})"

    def to_dict(self) -> Dict:
        return {
            'timestamp': self.timestamp.isoformat(),
            'symbol': self.symbol,
            'action': self.action,
            'quantity': self.quantity,
            'price': self.price,
            'strategy': self.strategy,
            'comment': self.comment,
        }


class SignalProcessor:
    """Process TradingView signals and execute trades."""

    def __init__(self, auto_execute: bool = False, paper: bool = True):
        """
        Initialize signal processor.

        Args:
            auto_execute: Auto-execute trades via Alpaca (requires credentials)
            paper: Use paper trading (True) or live (False)
        """
        self.auto_execute = auto_execute
        self.paper = paper
        self.signal_history = []

        if auto_execute and ALPACA_AVAILABLE:
            self.trader = AlpacaTrader(paper=paper)
            logger.info("✅ Alpaca auto-execution enabled")
        elif auto_execute:
            logger.warning("⚠️ Auto-execution requested but Alpaca not available")
            self.trader = None
        else:
            self.trader = None

    def process_signal(self, signal: TradingViewSignal) -> Dict:
        """
        Process a TradingView signal.

        Args:
            signal: TradingViewSignal object

        Returns:
            Processing result
        """
        # Validate signal
        is_valid, message = signal.validate()
        if not is_valid:
            logger.error(f"Invalid signal: {message}")
            return {
                'success': False,
                'error': message,
                'signal': signal.to_dict(),
            }

        logger.info(f"Processing signal: {signal}")

        # Log signal
        self.signal_history.append(signal)

        result = {
            'success': True,
            'signal': signal.to_dict(),
            'action': 'logged',
        }

        # Execute trade if enabled
        if self.auto_execute and self.trader:
            execution_result = self._execute_trade(signal)
            result['action'] = 'executed'
            result['execution'] = execution_result

        return result

    def _execute_trade(self, signal: TradingViewSignal) -> Dict:
        """Execute trade on Alpaca."""
        try:
            if signal.action == 'buy':
                order = self.trader.place_market_order(
                    symbol=signal.symbol,
                    qty=int(signal.quantity),
                    side='buy'
                )
            elif signal.action == 'sell':
                order = self.trader.place_market_order(
                    symbol=signal.symbol,
                    qty=int(signal.quantity),
                    side='sell'
                )
            elif signal.action == 'close':
                order = self.trader.close_position(signal.symbol)

            logger.info(f"✅ Trade executed: {order}")
            return {
                'success': True,
                'order_id': order.get('id'),
                'status': order.get('status'),
            }

        except Exception as e:
            logger.error(f"Trade execution failed: {e}")
            return {
                'success': False,
                'error': str(e),
            }

    def get_history(self, limit: int = 50) -> list:
        """Get recent signals."""
        return [s.to_dict() for s in self.signal_history[-limit:]]

    def get_stats(self) -> Dict:
        """Get signal statistics."""
        if not self.signal_history:
            return {
                'total_signals': 0,
                'by_action': {},
                'by_symbol': {},
            }

        actions = {}
        symbols = {}

        for signal in self.signal_history:
            actions[signal.action] = actions.get(signal.action, 0) + 1
            symbols[signal.symbol] = symbols.get(signal.symbol, 0) + 1

        return {
            'total_signals': len(self.signal_history),
            'by_action': actions,
            'by_symbol': symbols,
            'first_signal': self.signal_history[0].timestamp.isoformat(),
            'last_signal': self.signal_history[-1].timestamp.isoformat(),
        }


# Initialize signal processor (no auto-execution by default)
processor = SignalProcessor(auto_execute=False, paper=True)


# ============================================================================
# WEBHOOK ENDPOINTS
# ============================================================================

@app.route('/webhook', methods=['POST'])
def webhook():
    """
    Receive TradingView webhook signal.

    Expected JSON format:
    {
        "symbol": "AAPL",
        "action": "buy",  // or "sell", "close"
        "quantity": 10,
        "price": 180.50,
        "strategy": "ATLAS",
        "comment": "Earnings breakout"
    }

    Optional security: Add header validation
    """
    try:
        # Get JSON data
        data = request.get_json()

        if not data:
            return jsonify({'error': 'No JSON data'}), 400

        logger.info(f"Received signal: {data}")

        # Optional: Verify webhook secret (add header "X-Webhook-Secret")
        if TRADINGVIEW_SECRET != 'your_secret_here':
            secret = request.headers.get('X-Webhook-Secret')
            if secret != TRADINGVIEW_SECRET:
                logger.warning("Invalid webhook secret")
                return jsonify({'error': 'Invalid secret'}), 403

        # Parse signal
        signal = TradingViewSignal(data)

        # Process signal
        result = processor.process_signal(signal)

        return jsonify(result), 200 if result['success'] else 400

    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/status', methods=['GET'])
def status():
    """Get webhook server status."""
    return jsonify({
        'status': 'online',
        'timestamp': datetime.now().isoformat(),
        'auto_execute': processor.auto_execute,
        'paper_trading': processor.paper,
        'signals_received': len(processor.signal_history),
    })


@app.route('/signals', methods=['GET'])
def signals():
    """Get recent signals."""
    limit = request.args.get('limit', 50, type=int)
    return jsonify({
        'signals': processor.get_history(limit),
        'count': len(processor.signal_history),
    })


@app.route('/stats', methods=['GET'])
def stats():
    """Get signal statistics."""
    return jsonify(processor.get_stats())


@app.route('/test', methods=['POST'])
def test():
    """Test endpoint - send a test signal."""
    test_signal = {
        'symbol': 'TEST',
        'action': 'buy',
        'quantity': 1,
        'price': 100.00,
        'strategy': 'TEST',
        'comment': 'Test signal',
    }

    signal = TradingViewSignal(test_signal)
    result = processor.process_signal(signal)

    return jsonify(result)


# ============================================================================
# SETUP & INSTRUCTIONS
# ============================================================================

def get_setup_instructions(host: str = 'localhost', port: int = 5000) -> str:
    """Return TradingView setup instructions."""
    webhook_url = f"http://{host}:{port}/webhook"

    return f"""
╔══════════════════════════════════════════════════════════════════════════╗
║           PROJECT ATLAS - TradingView Webhook Setup                     ║
╚══════════════════════════════════════════════════════════════════════════╝

STEP 1: START THE WEBHOOK SERVER
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

$ python tradingview_webhook.py

Expected output:
  * Running on http://localhost:5000
  ✅ Webhook server started

STEP 2: GET YOUR WEBHOOK URL
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Local: {webhook_url}

For remote access (if server is on cloud):
$ ngrok http 5000
Then use: https://xxx.ngrok.io/webhook

STEP 3: CREATE TRADINGVIEW ALERT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. Open TradingView chart (e.g., AAPL)
2. Create a Strategy or Indicator alert
3. Go to Alert Settings
4. Select "Webhook URL"
5. Enter your webhook URL:
   {webhook_url}

6. In the alert message, use this JSON format:
   {{
     "symbol": "{{ticker}}",
     "action": "buy",
     "quantity": 10,
     "price": {{close}},
     "strategy": "MyStrategy",
     "comment": "Signal at {{time}}"
   }}

STEP 4: TEST THE WEBHOOK
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

$ curl -X POST http://localhost:5000/test

Expected response:
  {{
    "success": true,
    "signal": {{...}},
    "action": "logged"
  }}

STEP 5: VIEW SIGNALS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Check received signals:
$ curl http://localhost:5000/signals

Get statistics:
$ curl http://localhost:5000/stats

Get server status:
$ curl http://localhost:5000/status

═══════════════════════════════════════════════════════════════════════════

SIGNAL ACTIONS
  "buy"   - Buy signal (qty shares at market price)
  "sell"  - Sell signal (close position or sell qty shares)
  "close" - Close entire position

OPTIONAL: AUTO-EXECUTION (Requires Alpaca)
  Edit tradingview_webhook.py:
  processor = SignalProcessor(auto_execute=True, paper=True)

  Then set Alpaca credentials:
  export APCA_API_KEY_ID='...'
  export APCA_API_SECRET_KEY='...'

═══════════════════════════════════════════════════════════════════════════
"""


if __name__ == '__main__':
    import sys

    # Parse arguments
    host = os.getenv('WEBHOOK_HOST', 'localhost')
    port = int(os.getenv('WEBHOOK_PORT', '5000'))
    debug = '--debug' in sys.argv

    print(get_setup_instructions(host, port))

    # Start server
    logger.info(f"Starting webhook server on {host}:{port}")
    app.run(host=host, port=port, debug=debug)
