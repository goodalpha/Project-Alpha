# 🍎 PROJECT ATLAS - Mac Setup Guide

## Quick Start (10 minutes)

```bash
# 1. Clone the repository to your Mac
git clone <repo-url> ~/Project-Alpha
cd ~/Project-Alpha

# 2. Install Python dependencies
pip install -r requirements.txt

# 3. Set up credentials
cp .env.template .env
nano .env  # Add your TradingView email and password

# 4. Install ChromeDriver (for TradingView scraping)
brew install chromedriver

# 5. Run the system!
python tradingview_strategy_optimizer.py
```

---

## Detailed Setup Instructions

### Step 1: Install Homebrew (if not already installed)

Homebrew is Mac's package manager - makes installing software easy.

```bash
# Check if Homebrew is installed
brew --version

# If not installed, run:
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

**Expected output:**
```
Homebrew 4.x.x
```

---

### Step 2: Install Python 3.9+

```bash
# Check current Python version
python3 --version

# If you have Python 3.9 or higher, skip this step
# Otherwise, install via Homebrew:
brew install python@3.11

# Verify installation
python3 --version
# Should show: Python 3.11.x
```

---

### Step 3: Clone Project & Install Dependencies

```bash
# Clone repository
git clone <repo-url> ~/Project-Alpha
cd ~/Project-Alpha

# Create virtual environment (optional but recommended)
python3 -m venv venv
source venv/bin/activate  # Activate virtual environment

# Install all dependencies
pip install -r requirements.txt

# Verify key packages installed
python3 -c "import pandas, numpy, xgboost, selenium; print('✅ All packages installed')"
```

**Expected output:**
```
✅ All packages installed
```

---

### Step 4: Install ChromeDriver

ChromeDriver is needed for TradingView web scraping.

#### Option A: Homebrew (Easiest)

```bash
# Install via Homebrew
brew install chromedriver

# Verify installation
chromedriver --version
# Should show: ChromeDriver xx.x.xxxx.xx
```

#### Option B: Manual Download

If Homebrew installation has issues:

```bash
# 1. Download ChromeDriver
# Go to: https://chromedriver.chromium.org/
# Select version matching your Chrome version

# Check your Chrome version:
# Click Chrome menu → About Google Chrome → Shows version

# 2. Extract the file
# Move chromedriver to system PATH
sudo mv ~/Downloads/chromedriver /usr/local/bin/

# 3. Make executable
sudo chmod +x /usr/local/bin/chromedriver

# 4. Verify
chromedriver --version
```

#### Option C: Using Apple Silicon (M1/M2/M3 Mac)

If you have an Apple Silicon Mac and ChromeDriver doesn't work:

```bash
# Check your Mac architecture
uname -m
# If shows "arm64" → you have Apple Silicon

# Install Chrome for Apple Silicon (if not already)
brew install --cask google-chrome

# Download ARM64 ChromeDriver
# From: https://chromedriver.chromium.org/
# Look for "arm64" version

# Install
sudo mv ~/Downloads/chromedriver /usr/local/bin/
sudo chmod +x /usr/local/bin/chromedriver

# Verify
chromedriver --version
```

---

### Step 5: Set Up Credentials

```bash
# Navigate to project directory
cd ~/Project-Alpha

# Copy template to actual .env
cp .env.template .env

# Open .env file in your preferred editor
nano .env
# or
code .env  # If you have VS Code
# or
open -a TextEdit .env  # TextEdit (simple)

# Edit the file with your credentials:
# TRADINGVIEW_EMAIL=puunvasa1996@gmail.com
# TRADINGVIEW_PASSWORD=Puunvasa11

# Save and close
```

**Your .env file should look like:**
```
TRADINGVIEW_EMAIL=puunvasa1996@gmail.com
TRADINGVIEW_PASSWORD=Puunvasa11
```

---

### Step 6: Verify Everything Works

```bash
# Test Python import
python3 << 'EOF'
import os
from dotenv import load_dotenv

load_dotenv()
email = os.getenv('TRADINGVIEW_EMAIL')
print(f"✅ Email loaded: {email}")
EOF

# Test ChromeDriver
chromedriver --version

# Test key packages
python3 -c "from selenium import webdriver; print('✅ Selenium works')"
```

**Expected output:**
```
✅ Email loaded: puunvasa1996@gmail.com
ChromeDriver xx.x.xxxx.xx
✅ Selenium works
```

---

## Running on Mac

### 1. Generate Trading Signals

```bash
cd ~/Project-Alpha
python3 tradingview_strategy_optimizer.py
```

**Output:**
```
======================================================================
                ATLAS - TradingView Strategy Optimizer                
======================================================================

Step 1: Running optimization sweep across confidence thresholds...
✅ Tested 2 strategies

Top 10 Signals:
 1. SAP    | Confidence: 0.591 | Expected Return: +0.42%
 ...
```

### 2. Run Live TradingView Scraper

```bash
# In terminal 1
cd ~/Project-Alpha
python3 tradingview_scraper.py

# Output will show:
# ✅ Chrome WebDriver initialized
# Logging in to TradingView...
# ✅ Successfully logged in
# ✅ Fetched 30 positions
```

### 3. View Dashboard (in another terminal)

```bash
# In terminal 2
cd ~/Project-Alpha
python3 -m streamlit run dashboard.py

# Opens browser at: http://localhost:8501
```

### 4. Train Model from Real Data

```bash
# In terminal 3 (after 8 hours of trading data)
cd ~/Project-Alpha
python3 tradingview_model_trainer.py
```

---

## Complete Workflow Example

### Morning Trading Setup

**Terminal 1: Start Scraper (monitors TradingView)**
```bash
cd ~/Project-Alpha
python3 tradingview_scraper.py &  # Runs in background
# Monitors every 5 minutes, saves data
```

**Terminal 2: Start Dashboard (watch in real-time)**
```bash
cd ~/Project-Alpha
python3 -m streamlit run dashboard.py
# Opens http://localhost:8501 in browser
```

**Terminal 3: Generate Signals (optional, anytime)**
```bash
cd ~/Project-Alpha
python3 tradingview_strategy_optimizer.py
# Shows recommended signals to execute
```

### Execute Signals on TradingView

1. Open www.tradingview.com in browser
2. For each signal from optimizer output:
   - Open stock chart (e.g., SAP)
   - Click "Paper Trading" button at top
   - Enter quantity (e.g., 16 shares)
   - Click "Buy"
3. Watch in ATLAS dashboard - positions appear automatically
4. Scraper tracks P&L in real-time

---

## Troubleshooting on Mac

### Issue: "command not found: python3"

```bash
# Check Python installation
which python3
# Should show: /usr/bin/python3 or /usr/local/bin/python3

# If not found, install via Homebrew
brew install python@3.11

# Then use:
python3.11 --version
```

### Issue: "chromedriver: command not found"

```bash
# Check if installed
which chromedriver
# Should show: /usr/local/bin/chromedriver

# If not found, install via Homebrew
brew install chromedriver

# Or manually:
# 1. Download from https://chromedriver.chromium.org/
# 2. Move to /usr/local/bin:
sudo mv ~/Downloads/chromedriver /usr/local/bin/
sudo chmod +x /usr/local/bin/chromedriver
```

### Issue: "ModuleNotFoundError: No module named 'selenium'"

```bash
# Reinstall dependencies
pip install -r requirements.txt

# Or install Selenium directly
pip install selenium

# Verify
python3 -c "import selenium; print(selenium.__version__)"
```

### Issue: "Permission denied" on .env file

```bash
# Fix permissions
chmod 600 ~/.env

# Or move to project directory
cd ~/Project-Alpha
chmod 600 .env
```

### Issue: "Permission denied: /usr/local/bin/chromedriver"

```bash
# Fix permissions
sudo chmod +x /usr/local/bin/chromedriver

# Verify
chromedriver --version
```

### Issue: Streamlit not starting

```bash
# Install Streamlit
pip install streamlit

# Run with explicit python
python3 -m streamlit run dashboard.py

# Or with full path
/usr/local/bin/python3 -m streamlit run dashboard.py
```

### Issue: "SSL: CERTIFICATE_VERIFY_FAILED" when installing packages

```bash
# Fix SSL certificates (one-time setup)
/Applications/Python\ 3.11/Install\ Certificates.command

# Then retry pip install
pip install -r requirements.txt
```

---

## Using Virtual Environment (Recommended)

Virtual environments isolate project dependencies - prevents conflicts.

```bash
# Create virtual environment
cd ~/Project-Alpha
python3 -m venv venv

# Activate it (do this every time you work on project)
source venv/bin/activate
# You'll see (venv) at start of terminal

# Install dependencies in virtual environment
pip install -r requirements.txt

# Run scripts (automatically uses venv Python)
python3 tradingview_strategy_optimizer.py

# Deactivate when done
deactivate
# (venv) disappears from terminal
```

**Pro tip:** Always activate the virtual environment before working:
```bash
cd ~/Project-Alpha
source venv/bin/activate
```

---

## Keyboard Shortcuts for Mac Terminal

```bash
# Stop running script
Ctrl + C

# Run in background
python3 script.py &

# List running processes
ps aux | grep python

# Kill process
kill -9 <PID>

# Open file with TextEdit
open -a TextEdit filename.txt

# Open directory in Finder
open .

# Create multiple terminal tabs
Cmd + T  # New tab in current terminal
Cmd + W  # Close tab
Cmd + }  # Switch to next tab
```

---

## Running Multiple Scripts Simultaneously

### Option A: Multiple Terminal Tabs

```bash
# Terminal - Tab 1: Scraper
cd ~/Project-Alpha && python3 tradingview_scraper.py

# Terminal - Tab 2: Dashboard (Cmd+T to open new tab)
cd ~/Project-Alpha && python3 -m streamlit run dashboard.py

# Terminal - Tab 3: Signal generator (Cmd+T again)
cd ~/Project-Alpha && python3 tradingview_strategy_optimizer.py
```

### Option B: Background Process

```bash
# Run scraper in background
cd ~/Project-Alpha
python3 tradingview_scraper.py &

# Get process ID
# Output: [1] 12345

# Run dashboard in foreground
python3 -m streamlit run dashboard.py

# Check background processes
jobs

# Bring background process to foreground
fg

# Stop background process
kill %1
```

---

## Daily Workflow on Mac

### Every Morning (9:30 AM ET)

```bash
# 1. Open Terminal
# 2. Start scraper in background
cd ~/Project-Alpha
source venv/bin/activate  # If using venv
python3 tradingview_scraper.py &

# 3. Start dashboard in another terminal tab (Cmd+T)
python3 -m streamlit run dashboard.py

# 4. Generate today's signals (optional)
python3 tradingview_strategy_optimizer.py
```

### Throughout the Day

- Monitor TradingView paper trading account
- Execute signals manually (click "Buy" on charts)
- Watch ATLAS dashboard update in real-time
- Monitor P&L as prices change

### End of Day (4 PM ET)

```bash
# Check final results
python3 tradingview_model_trainer.py

# View P&L and performance metrics in dashboard
# Already running at http://localhost:8501
```

### Stop for the Day

```bash
# Kill background scraper
kill %1

# Stop Streamlit dashboard
Ctrl + C  # In the Streamlit terminal

# Deactivate virtual environment
deactivate
```

---

## Updating/Reinstalling

### Update all dependencies

```bash
cd ~/Project-Alpha
source venv/bin/activate

pip install --upgrade -r requirements.txt
```

### Reset and clean install

```bash
cd ~/Project-Alpha

# Remove old virtual environment
rm -rf venv

# Create fresh environment
python3 -m venv venv
source venv/bin/activate

# Reinstall
pip install -r requirements.txt
```

---

## System Requirements

**Minimum:**
- macOS 10.14+ (Mojave or newer)
- Python 3.9+
- 4 GB RAM
- 500 MB disk space
- Chrome browser

**Recommended:**
- macOS 12+ (Monterey or newer)
- Python 3.11
- 8+ GB RAM
- 1 GB disk space
- Chrome browser (latest)

**Apple Silicon (M1/M2/M3):**
- All features work (use ARM64 ChromeDriver)
- May need to disable Rosetta emulation
- Use native Apple Silicon Python if possible

---

## Getting Help

If something doesn't work:

```bash
# Check Python version
python3 --version

# Check ChromeDriver version
chromedriver --version

# Check installed packages
pip list | grep -E "selenium|pandas|xgboost"

# Check running processes
ps aux | grep python

# Check logs
tail -50 logs/tradingview_scraper.log
```

Then refer to **Troubleshooting** section above.

---

## Next Steps

1. ✅ Follow this guide to set up Mac
2. ✅ Run `python3 tradingview_strategy_optimizer.py` to generate signals
3. ✅ Execute top signals manually on TradingView
4. ✅ Run `python3 -m streamlit run dashboard.py` to monitor
5. ✅ After 8 hours of trading, run `python3 tradingview_model_trainer.py`

**You're ready to trade!** 🍎📈
