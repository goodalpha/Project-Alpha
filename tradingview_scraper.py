"""
PROJECT ATLAS - TradingView Paper Trading Scraper
Automatically fetches positions, P&L, and portfolio metrics from TradingView
"""

import os
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import pandas as pd
from pathlib import Path

logger = logging.getLogger(__name__)
logger.setLevel("INFO")

# Try to import Selenium (for web scraping)
try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.chrome.options import Options
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False
    logger.warning("Selenium not installed. Install with: pip install selenium")

import config


class TradingViewScraper:
    """
    Scrapes TradingView paper trading data using Selenium.
    Extracts positions, P&L, and account metrics.
    """

    def __init__(self, email: str = None, password: str = None, headless: bool = True):
        """
        Initialize TradingView scraper.

        Args:
            email: TradingView email (or TRADINGVIEW_EMAIL env var)
            password: TradingView password (or TRADINGVIEW_PASSWORD env var)
            headless: Run browser in headless mode (no GUI)
        """
        if not SELENIUM_AVAILABLE:
            raise ImportError(
                "Selenium not installed.\n"
                "Install with: pip install selenium\n"
                "Download ChromeDriver: https://chromedriver.chromium.org/"
            )

        self.email = email or os.getenv('TRADINGVIEW_EMAIL')
        self.password = password or os.getenv('TRADINGVIEW_PASSWORD')
        self.headless = headless
        self.driver = None
        self.positions = {}
        self.account_value = 0
        self.cash = 0
        self.buying_power = 0
        self.last_update = None

        if not self.email or not self.password:
            logger.warning(
                "Missing TradingView credentials.\n"
                "Set via environment variables:\n"
                "  export TRADINGVIEW_EMAIL='your_email@example.com'\n"
                "  export TRADINGVIEW_PASSWORD='your_password'"
            )

    def _init_driver(self):
        """Initialize Chrome WebDriver."""
        try:
            chrome_options = Options()
            if self.headless:
                chrome_options.add_argument("--headless")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")

            self.driver = webdriver.Chrome(options=chrome_options)
            logger.info("✅ Chrome WebDriver initialized")

        except Exception as e:
            logger.error(f"Error initializing WebDriver: {e}")
            logger.info("Make sure ChromeDriver is installed: https://chromedriver.chromium.org/")
            raise

    def login(self, timeout: int = 30) -> bool:
        """
        Login to TradingView.

        Args:
            timeout: Max seconds to wait for login

        Returns:
            True if login successful
        """
        try:
            self._init_driver()

            logger.info("Logging in to TradingView...")
            self.driver.get("https://www.tradingview.com/accounts/signin/")

            # Wait for email field
            wait = WebDriverWait(self.driver, timeout)
            email_field = wait.until(
                EC.presence_of_element_located((By.NAME, "email"))
            )

            # Enter credentials
            email_field.send_keys(self.email)
            password_field = self.driver.find_element(By.NAME, "password")
            password_field.send_keys(self.password)

            # Click login
            login_button = self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
            login_button.click()

            # Wait for redirect
            time.sleep(3)

            # Check if logged in
            if "signin" not in self.driver.current_url:
                logger.info("✅ Successfully logged in to TradingView")
                return True
            else:
                logger.error("Login failed - redirect didn't occur")
                return False

        except Exception as e:
            logger.error(f"Login error: {e}")
            return False

    def fetch_paper_trading_data(self) -> Dict:
        """
        Fetch paper trading positions and account metrics.

        Returns:
            Dict with account info and positions
        """
        try:
            # Navigate to paper trading
            self.driver.get("https://www.tradingview.com/accounts/paper-trading/")

            time.sleep(2)  # Wait for page load

            # Extract account balance
            try:
                balance_element = self.driver.find_element(
                    By.CSS_SELECTOR,
                    "[data-test='account-balance']"
                )
                self.account_value = float(balance_element.text.replace("$", "").replace(",", ""))
            except:
                logger.warning("Could not find account balance")

            # Extract positions
            positions = []
            try:
                position_rows = self.driver.find_elements(
                    By.CSS_SELECTOR,
                    "tr[data-test='position-row']"
                )

                for row in position_rows:
                    try:
                        cells = row.find_elements(By.TAG_NAME, "td")
                        if len(cells) >= 5:
                            position = {
                                'symbol': cells[0].text.strip().upper(),
                                'quantity': int(float(cells[1].text.replace(",", ""))),
                                'entry_price': float(cells[2].text.replace("$", "")),
                                'current_price': float(cells[3].text.replace("$", "")),
                                'pnl': float(cells[4].text.replace("$", "").replace(",", "")),
                                'pnl_pct': float(cells[5].text.replace("%", "")),
                            }
                            positions.append(position)
                    except Exception as e:
                        logger.warning(f"Error parsing position: {e}")

                self.positions = {p['symbol']: p for p in positions}
                logger.info(f"✅ Fetched {len(positions)} positions")

            except Exception as e:
                logger.warning(f"Error fetching positions: {e}")

            # Calculate portfolio metrics
            result = {
                'timestamp': datetime.now().isoformat(),
                'account_value': self.account_value,
                'positions': positions,
                'total_pnl': sum(p.get('pnl', 0) for p in positions),
                'position_count': len(positions),
            }

            self.last_update = datetime.now()
            return result

        except Exception as e:
            logger.error(f"Error fetching paper trading data: {e}")
            return {}

    def get_real_time_prices(self, symbols: List[str]) -> Dict[str, float]:
        """
        Fetch real-time prices for symbols.

        Args:
            symbols: List of ticker symbols

        Returns:
            Dict mapping symbol → price
        """
        prices = {}

        try:
            for symbol in symbols:
                self.driver.get(f"https://www.tradingview.com/symbols/{symbol}/")
                time.sleep(1)

                try:
                    price_element = self.driver.find_element(
                        By.CSS_SELECTOR,
                        "[data-test='current-price']"
                    )
                    price = float(price_element.text.replace("$", "").replace(",", ""))
                    prices[symbol] = price
                except:
                    logger.warning(f"Could not fetch price for {symbol}")

        except Exception as e:
            logger.error(f"Error fetching prices: {e}")

        return prices

    def save_to_file(self, data: Dict, filename: str = None):
        """Save scraped data to JSON file."""
        if filename is None:
            filename = f"tradingview_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        filepath = config.BACKTEST_DIR / filename

        try:
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2, default=str)
            logger.info(f"Data saved to {filepath}")
        except Exception as e:
            logger.error(f"Error saving data: {e}")

    def close(self):
        """Close WebDriver."""
        if self.driver:
            self.driver.quit()
            logger.info("WebDriver closed")


class TradingViewMonitor:
    """
    Monitors TradingView paper trading in real-time.
    Tracks positions, P&L, and updates ATLAS dashboard.
    """

    def __init__(self, scraper: TradingViewScraper, update_interval: int = 300):
        """
        Initialize monitor.

        Args:
            scraper: TradingViewScraper instance
            update_interval: Seconds between updates (default 5 min)
        """
        self.scraper = scraper
        self.update_interval = update_interval
        self.data_history = []
        self.is_running = False

    def start_monitoring(self, duration_hours: int = 8):
        """
        Start monitoring TradingView positions.

        Args:
            duration_hours: How long to monitor (for daily trading)
        """
        logger.info(f"Starting TradingView monitor (updates every {self.update_interval}s)")

        self.is_running = True
        start_time = time.time()
        max_duration = duration_hours * 3600

        try:
            while self.is_running and (time.time() - start_time) < max_duration:
                try:
                    # Fetch data
                    data = self.scraper.fetch_paper_trading_data()

                    if data:
                        self.data_history.append(data)

                        # Log summary
                        logger.info(
                            f"Positions: {data['position_count']}, "
                            f"Account: ${data['account_value']:,.2f}, "
                            f"P&L: ${data['total_pnl']:+,.2f}"
                        )

                        # Save periodically
                        if len(self.data_history) % 12 == 0:  # Every hour
                            self.scraper.save_to_file(
                                {'history': self.data_history},
                                'tradingview_history.json'
                            )

                    # Wait before next update
                    time.sleep(self.update_interval)

                except Exception as e:
                    logger.error(f"Monitor error: {e}")
                    time.sleep(30)  # Wait before retry

        except KeyboardInterrupt:
            logger.info("Monitoring stopped by user")
        finally:
            self.is_running = False
            self.scraper.close()

    def stop_monitoring(self):
        """Stop monitoring."""
        self.is_running = False

    def get_current_positions(self) -> List[Dict]:
        """Get current positions from latest data."""
        if self.data_history:
            return self.data_history[-1].get('positions', [])
        return []

    def get_summary(self) -> Dict:
        """Get summary of current trading session."""
        if not self.data_history:
            return {}

        latest = self.data_history[-1]
        positions = latest.get('positions', [])

        winners = [p for p in positions if p.get('pnl', 0) > 0]
        losers = [p for p in positions if p.get('pnl', 0) < 0]

        return {
            'timestamp': latest['timestamp'],
            'account_value': latest['account_value'],
            'total_positions': len(positions),
            'winning_positions': len(winners),
            'losing_positions': len(losers),
            'total_pnl': latest['total_pnl'],
            'positions': positions,
            'data_points': len(self.data_history),
        }


def setup_instructions() -> str:
    """Return setup instructions for TradingView scraper."""
    return """
╔══════════════════════════════════════════════════════════════════════════╗
║           PROJECT ATLAS - TradingView Scraper Setup                     ║
╚══════════════════════════════════════════════════════════════════════════╝

STEP 1: INSTALL DEPENDENCIES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

$ pip install selenium

STEP 2: DOWNLOAD CHROMEDRIVER
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. Go to: https://chromedriver.chromium.org/
2. Download version matching your Chrome version
3. Extract to: /usr/local/bin/ (Linux/Mac) or Program Files (Windows)
4. Make executable: chmod +x /usr/local/bin/chromedriver

Check version:
$ chrome --version
$ chromedriver --version  # Should match

STEP 3: SET CREDENTIALS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

$ export TRADINGVIEW_EMAIL='your_email@example.com'
$ export TRADINGVIEW_PASSWORD='your_password'

Or add to ~/.bashrc:
export TRADINGVIEW_EMAIL='your_email@example.com'
export TRADINGVIEW_PASSWORD='your_password'

STEP 4: RUN SCRAPER
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

$ python tradingview_scraper.py

STEP 5: VIEW RESULTS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Open ATLAS dashboard:
$ streamlit run dashboard.py

Or check saved data:
$ cat backtest/tradingview_data_*.json | python -m json.tool

═══════════════════════════════════════════════════════════════════════════

FEATURES:
✅ Automatic login to TradingView
✅ Fetch paper trading positions in real-time
✅ Track P&L and account value
✅ Monitor continuously (every 5 minutes)
✅ Save data to JSON files
✅ Integrate with ATLAS dashboard

═══════════════════════════════════════════════════════════════════════════
"""


if __name__ == "__main__":
    import sys

    # Setup logging
    logging.basicConfig(
        format=config.LOG_FORMAT,
        level="INFO",
        handlers=[
            logging.FileHandler(config.LOGS_DIR / "tradingview_scraper.log"),
            logging.StreamHandler()
        ]
    )

    # Print setup instructions
    print(setup_instructions())

    # Run scraper if credentials are available
    email = os.getenv('TRADINGVIEW_EMAIL')
    password = os.getenv('TRADINGVIEW_PASSWORD')

    if email and password:
        print("\n✅ Credentials found. Starting scraper...\n")

        try:
            # Initialize scraper
            scraper = TradingViewScraper(email, password, headless=True)

            # Login
            if scraper.login():
                # Start monitoring
                monitor = TradingViewMonitor(scraper, update_interval=300)  # 5 min updates
                monitor.start_monitoring(duration_hours=8)  # Monitor during market hours

                # Print final summary
                summary = monitor.get_summary()
                print("\n" + "="*70)
                print("TRADING SESSION SUMMARY")
                print("="*70)
                print(json.dumps(summary, indent=2, default=str))
            else:
                print("❌ Login failed")

        except Exception as e:
            print(f"❌ Error: {e}")
    else:
        print("\n❌ Missing credentials. Set environment variables and try again.")
