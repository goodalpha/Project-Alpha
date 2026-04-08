"""
PROJECT ATLAS - TradingView Paper Trading Scraper (Improved v2)
Automatically fetches positions, P&L, and portfolio metrics from TradingView

Improvements:
- Comprehensive error handling and retry logic
- Type hints throughout
- Better logging with context
- Input validation
- Automatic credential loading from .env
- Better exception handling
- Connection resilience
- Data validation before returning
"""

import os
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import re

logger = logging.getLogger(__name__)
logger.setLevel("INFO")

# Load credentials from .env
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    logger.warning("python-dotenv not installed. Install with: pip install python-dotenv")

# Try to import Selenium (for web scraping)
try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False
    logger.error("Selenium not installed. Install with: pip install selenium")

import config


class CredentialsError(Exception):
    """Raised when credentials are missing or invalid."""
    pass


class ScraperError(Exception):
    """Raised when scraper encounters an error."""
    pass


class TradingViewScraper:
    """
    Scrapes TradingView paper trading data using Selenium.
    Extracts positions, P&L, and account metrics with robust error handling.
    """

    # Configuration constants
    DEFAULT_TIMEOUT = 30
    RETRY_ATTEMPTS = 3
    RETRY_DELAY = 2
    MAX_POSITIONS = 1000
    MIN_POSITION_VALUE = 0

    LOGIN_URL = "https://www.tradingview.com/accounts/signin/"
    PAPER_TRADING_URL = "https://www.tradingview.com/accounts/paper-trading/"

    def __init__(
        self,
        email: Optional[str] = None,
        password: Optional[str] = None,
        headless: bool = True,
        timeout: int = DEFAULT_TIMEOUT,
        retry_attempts: int = RETRY_ATTEMPTS,
    ):
        """
        Initialize TradingView scraper with credentials and options.

        Args:
            email: TradingView email (or TRADINGVIEW_EMAIL env var)
            password: TradingView password (or TRADINGVIEW_PASSWORD env var)
            headless: Run browser in headless mode (no GUI)
            timeout: WebDriver wait timeout in seconds
            retry_attempts: Number of retry attempts for failed operations

        Raises:
            ImportError: If Selenium is not installed
            CredentialsError: If credentials are missing or invalid
        """
        if not SELENIUM_AVAILABLE:
            raise ImportError(
                "Selenium not installed.\n"
                "Install with: pip install selenium\n"
                "Download ChromeDriver: https://chromedriver.chromium.org/"
            )

        self.email = email or os.getenv('TRADINGVIEW_EMAIL', '').strip()
        self.password = password or os.getenv('TRADINGVIEW_PASSWORD', '').strip()
        self.headless = headless
        self.timeout = timeout
        self.retry_attempts = retry_attempts
        self.driver = None
        self.positions: Dict = {}
        self.account_value: float = 0.0
        self.cash: float = 0.0
        self.buying_power: float = 0.0
        self.last_update: Optional[datetime] = None

        # Validate credentials
        self._validate_credentials()

        logger.info(f"TradingView scraper initialized (headless={headless})")

    def _validate_credentials(self) -> None:
        """
        Validate that credentials are present and properly formatted.

        Raises:
            CredentialsError: If credentials are invalid or missing
        """
        if not self.email or not self.password:
            raise CredentialsError(
                "Missing TradingView credentials.\n"
                "Set via environment variables or .env file:\n"
                "  TRADINGVIEW_EMAIL=your_email@example.com\n"
                "  TRADINGVIEW_PASSWORD=your_password\n"
                "Or pass to constructor: TradingViewScraper(email='...', password='...')"
            )

        # Validate email format
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, self.email):
            raise CredentialsError(f"Invalid email format: {self.email}")

        # Validate password is not empty
        if len(self.password) < 1:
            raise CredentialsError("Password cannot be empty")

        logger.info(f"✅ Credentials validated for email: {self.email}")

    def _init_driver(self) -> None:
        """
        Initialize Chrome WebDriver with security and performance options.

        Raises:
            ScraperError: If WebDriver initialization fails
        """
        try:
            chrome_options = Options()

            # Performance options
            if self.headless:
                chrome_options.add_argument("--headless")

            # Security options
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--no-first-run")
            chrome_options.add_argument("--no-default-browser-check")

            # Anti-detection
            chrome_options.add_argument(
                "user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )

            # Disable notifications and popups
            prefs = {
                "profile.default_content_setting_values.notifications": 2,
                "profile.default_content_settings.popups": 0,
            }
            chrome_options.add_experimental_option("prefs", prefs)

            self.driver = webdriver.Chrome(options=chrome_options)
            self.driver.set_page_load_timeout(self.timeout)

            logger.info("✅ Chrome WebDriver initialized successfully")

        except WebDriverException as e:
            logger.error(f"WebDriver initialization failed: {e}")
            raise ScraperError(
                f"Failed to initialize WebDriver: {e}\n"
                f"Make sure ChromeDriver is installed and accessible:\n"
                f"  brew install chromedriver (macOS)\n"
                f"  https://chromedriver.chromium.org/"
            ) from e
        except Exception as e:
            logger.error(f"Unexpected error initializing WebDriver: {e}")
            raise ScraperError(f"Unexpected error: {e}") from e

    def login(self, timeout: Optional[int] = None) -> bool:
        """
        Login to TradingView with retry logic.

        Args:
            timeout: Max seconds to wait for login (overrides instance timeout)

        Returns:
            True if login successful, False otherwise
        """
        timeout = timeout or self.timeout

        for attempt in range(self.retry_attempts):
            try:
                logger.info(f"Login attempt {attempt + 1}/{self.retry_attempts}...")
                self._init_driver()

                logger.info(f"Navigating to {self.LOGIN_URL}...")
                self.driver.get(self.LOGIN_URL)

                # Wait for email field
                wait = WebDriverWait(self.driver, timeout)
                email_field = wait.until(
                    EC.presence_of_element_located((By.NAME, "email"))
                )

                # Enter credentials
                logger.debug("Entering email...")
                email_field.clear()
                email_field.send_keys(self.email)

                logger.debug("Entering password...")
                password_field = self.driver.find_element(By.NAME, "password")
                password_field.clear()
                password_field.send_keys(self.password)

                # Click login button
                logger.debug("Clicking login button...")
                login_button = self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
                login_button.click()

                # Wait for redirect
                logger.debug("Waiting for redirect...")
                time.sleep(3)

                # Check if logged in
                if "signin" not in self.driver.current_url.lower():
                    logger.info("✅ Successfully logged in to TradingView")
                    return True
                else:
                    logger.warning(f"Login redirect failed. Current URL: {self.driver.current_url}")

            except TimeoutException as e:
                logger.warning(f"Timeout during login attempt {attempt + 1}: {e}")
                if attempt < self.retry_attempts - 1:
                    time.sleep(self.RETRY_DELAY)
            except NoSuchElementException as e:
                logger.warning(f"Login form element not found: {e}")
                if attempt < self.retry_attempts - 1:
                    time.sleep(self.RETRY_DELAY)
            except Exception as e:
                logger.error(f"Login error on attempt {attempt + 1}: {e}")
                if attempt < self.retry_attempts - 1:
                    time.sleep(self.RETRY_DELAY)
            finally:
                if attempt == self.retry_attempts - 1 and self.driver:
                    self.close()

        logger.error("❌ Login failed after all retry attempts")
        return False

    def fetch_paper_trading_data(self) -> Dict:
        """
        Fetch paper trading positions and account metrics.

        Returns:
            Dict with account info and positions, empty dict if fetch fails
        """
        if not self.driver:
            logger.error("WebDriver not initialized. Call login() first.")
            return {}

        try:
            logger.info(f"Fetching paper trading data from {self.PAPER_TRADING_URL}...")
            self.driver.get(self.PAPER_TRADING_URL)
            time.sleep(2)  # Wait for page load

            # Extract account balance
            account_value = self._extract_account_balance()
            self.account_value = account_value

            # Extract positions
            positions = self._extract_positions()
            self.positions = {p['symbol']: p for p in positions}

            # Calculate portfolio metrics
            total_pnl = sum(p.get('pnl', 0) for p in positions)

            result = {
                'timestamp': datetime.now().isoformat(),
                'account_value': self.account_value,
                'positions': positions,
                'total_pnl': total_pnl,
                'position_count': len(positions),
            }

            self.last_update = datetime.now()
            logger.info(f"✅ Fetched {len(positions)} positions, P&L: ${total_pnl:+.2f}")
            return result

        except Exception as e:
            logger.error(f"Error fetching paper trading data: {e}")
            return {}

    def _extract_account_balance(self) -> float:
        """
        Extract account balance from page.

        Returns:
            Account balance as float, 0.0 if extraction fails
        """
        try:
            balance_element = self.driver.find_element(
                By.CSS_SELECTOR,
                "[data-test='account-balance']"
            )
            balance_text = balance_element.text.replace("$", "").replace(",", "")
            balance = float(balance_text)
            logger.debug(f"Account balance: ${balance:,.2f}")
            return balance
        except (NoSuchElementException, ValueError, AttributeError) as e:
            logger.warning(f"Could not extract account balance: {e}")
            return 0.0

    def _extract_positions(self) -> List[Dict]:
        """
        Extract position data from page with validation.

        Returns:
            List of validated position dictionaries
        """
        positions = []

        try:
            position_rows = self.driver.find_elements(
                By.CSS_SELECTOR,
                "tr[data-test='position-row']"
            )

            logger.debug(f"Found {len(position_rows)} position rows")

            for idx, row in enumerate(position_rows):
                try:
                    position = self._parse_position_row(row)
                    if position and self._validate_position(position):
                        positions.append(position)
                except Exception as e:
                    logger.warning(f"Error parsing position row {idx}: {e}")
                    continue

            logger.debug(f"Successfully extracted {len(positions)} valid positions")
            return positions

        except Exception as e:
            logger.warning(f"Error extracting positions: {e}")
            return []

    def _parse_position_row(self, row) -> Optional[Dict]:
        """
        Parse a single position row from HTML.

        Args:
            row: Selenium WebElement representing a position row

        Returns:
            Position dictionary or None if parsing fails
        """
        try:
            cells = row.find_elements(By.TAG_NAME, "td")

            if len(cells) < 6:
                logger.debug(f"Position row has only {len(cells)} cells, skipping")
                return None

            position = {
                'symbol': cells[0].text.strip().upper(),
                'quantity': int(float(cells[1].text.replace(",", ""))),
                'entry_price': float(cells[2].text.replace("$", "")),
                'current_price': float(cells[3].text.replace("$", "")),
                'pnl': float(cells[4].text.replace("$", "").replace(",", "")),
                'pnl_pct': float(cells[5].text.replace("%", "")),
            }

            return position

        except (ValueError, AttributeError, IndexError) as e:
            logger.debug(f"Error parsing position values: {e}")
            return None

    def _validate_position(self, position: Dict) -> bool:
        """
        Validate position data for correctness.

        Args:
            position: Position dictionary to validate

        Returns:
            True if position is valid, False otherwise
        """
        try:
            # Check required fields
            required_fields = ['symbol', 'quantity', 'entry_price', 'current_price', 'pnl', 'pnl_pct']
            if not all(field in position for field in required_fields):
                logger.warning(f"Position missing required fields: {position}")
                return False

            # Check value ranges
            if position['quantity'] <= 0:
                logger.warning(f"Invalid quantity for {position['symbol']}: {position['quantity']}")
                return False

            if position['entry_price'] <= 0 or position['current_price'] <= 0:
                logger.warning(f"Invalid prices for {position['symbol']}: {position}")
                return False

            # Check symbol format
            if not re.match(r'^[A-Z]{1,5}$', position['symbol']):
                logger.warning(f"Invalid symbol format: {position['symbol']}")
                return False

            # Check position size limits
            position_value = position['quantity'] * position['current_price']
            if position_value > 10_000_000:  # Sanity check: no position > $10M
                logger.warning(f"Position value too large: {position['symbol']} = ${position_value:,.0f}")
                return False

            return True

        except Exception as e:
            logger.warning(f"Error validating position: {e}")
            return False

    def get_real_time_prices(self, symbols: List[str]) -> Dict[str, float]:
        """
        Fetch real-time prices for symbols.

        Args:
            symbols: List of ticker symbols (validated)

        Returns:
            Dict mapping symbol → price
        """
        if not symbols:
            logger.warning("No symbols provided")
            return {}

        # Validate symbols
        symbols = [s.upper() for s in symbols if isinstance(s, str) and s.strip()]
        if not symbols:
            logger.warning("No valid symbols after validation")
            return {}

        prices = {}

        try:
            for symbol in symbols:
                try:
                    url = f"https://www.tradingview.com/symbols/{symbol}/"
                    self.driver.get(url)
                    time.sleep(1)

                    price_element = self.driver.find_element(
                        By.CSS_SELECTOR,
                        "[data-test='current-price']"
                    )
                    price = float(price_element.text.replace("$", "").replace(",", ""))
                    prices[symbol] = price
                    logger.debug(f"{symbol}: ${price:,.2f}")

                except (NoSuchElementException, ValueError) as e:
                    logger.warning(f"Could not fetch price for {symbol}: {e}")
                    continue

        except Exception as e:
            logger.error(f"Error fetching prices: {e}")

        return prices

    def save_to_file(self, data: Dict, filename: Optional[str] = None) -> Optional[Path]:
        """
        Save scraped data to JSON file with validation.

        Args:
            data: Data to save
            filename: Output filename (auto-generated if None)

        Returns:
            Path to saved file or None if save fails
        """
        if not data:
            logger.warning("No data to save")
            return None

        try:
            if filename is None:
                filename = f"tradingview_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

            filepath = config.BACKTEST_DIR / filename

            # Ensure directory exists
            filepath.parent.mkdir(parents=True, exist_ok=True)

            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2, default=str)

            logger.info(f"✅ Data saved to {filepath}")
            return filepath

        except IOError as e:
            logger.error(f"Error saving data to file: {e}")
            return None

    def close(self) -> None:
        """Close WebDriver connection."""
        try:
            if self.driver:
                self.driver.quit()
                logger.info("✅ WebDriver closed")
        except Exception as e:
            logger.warning(f"Error closing WebDriver: {e}")
        finally:
            self.driver = None


class TradingViewMonitor:
    """
    Monitors TradingView paper trading in real-time with robust error handling.
    Tracks positions, P&L, and updates ATLAS dashboard.
    """

    def __init__(
        self,
        scraper: TradingViewScraper,
        update_interval: int = 300,
    ):
        """
        Initialize monitor.

        Args:
            scraper: TradingViewScraper instance
            update_interval: Seconds between updates (default 5 min)

        Raises:
            ValueError: If scraper is invalid or interval is invalid
        """
        if not isinstance(scraper, TradingViewScraper):
            raise ValueError("scraper must be TradingViewScraper instance")

        if update_interval <= 0:
            raise ValueError("update_interval must be positive")

        self.scraper = scraper
        self.update_interval = update_interval
        self.data_history: List[Dict] = []
        self.is_running = False

        logger.info(
            f"TradingView monitor initialized "
            f"(interval={update_interval}s)"
        )

    def start_monitoring(self, duration_hours: int = 8) -> List[Dict]:
        """
        Start monitoring TradingView positions with error handling.

        Args:
            duration_hours: How long to monitor (for daily trading)

        Returns:
            List of historical data snapshots
        """
        if duration_hours <= 0:
            raise ValueError("duration_hours must be positive")

        logger.info(
            f"Starting TradingView monitoring for {duration_hours} hours "
            f"(updates every {self.update_interval}s)"
        )

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

                        # Save periodically (every hour)
                        if len(self.data_history) % max(1, int(3600 / self.update_interval)) == 0:
                            self.scraper.save_to_file(
                                {'history': self.data_history},
                                'tradingview_history.json'
                            )

                    # Wait before next update
                    time.sleep(self.update_interval)

                except KeyboardInterrupt:
                    logger.info("Monitoring stopped by user")
                    break
                except Exception as e:
                    logger.error(f"Monitor error: {e}")
                    time.sleep(30)  # Wait before retry

        except Exception as e:
            logger.error(f"Unexpected monitoring error: {e}")
        finally:
            self.is_running = False
            self.scraper.close()
            logger.info("Monitoring stopped")

        return self.data_history

    def stop_monitoring(self) -> None:
        """Stop monitoring gracefully."""
        self.is_running = False
        logger.info("Monitoring stop requested")

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


if __name__ == "__main__":
    import sys

    # Setup logging
    logging.basicConfig(
        format=config.LOG_FORMAT,
        level="INFO",
        handlers=[
            logging.FileHandler(config.LOGS_DIR / "tradingview_scraper_v2.log"),
            logging.StreamHandler()
        ]
    )

    try:
        # Load credentials
        email = os.getenv('TRADINGVIEW_EMAIL')
        password = os.getenv('TRADINGVIEW_PASSWORD')

        if email and password:
            logger.info("✅ Credentials found. Starting scraper...\n")

            # Initialize scraper
            scraper = TradingViewScraper(email, password, headless=True)

            # Login with error handling
            if scraper.login():
                # Start monitoring
                monitor = TradingViewMonitor(scraper, update_interval=300)
                history = monitor.start_monitoring(duration_hours=8)

                # Print final summary
                summary = monitor.get_summary()
                if summary:
                    logger.info("\n" + "="*70)
                    logger.info("TRADING SESSION SUMMARY")
                    logger.info("="*70)
                    logger.info(json.dumps(summary, indent=2, default=str))
            else:
                logger.error("❌ Login failed")
                sys.exit(1)
        else:
            logger.error("❌ Missing credentials. Set environment variables and try again.")
            sys.exit(1)

    except CredentialsError as e:
        logger.error(f"❌ Credential error: {e}")
        sys.exit(1)
    except ScraperError as e:
        logger.error(f"❌ Scraper error: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}", exc_info=True)
        sys.exit(1)
