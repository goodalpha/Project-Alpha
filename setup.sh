#!/bin/bash
# PROJECT ATLAS - Setup Script
# Installation and configuration for macOS, Linux, and Windows (Git Bash)

set -e  # Exit on error

echo "=================================================="
echo "PROJECT ATLAS - Automated Setup"
echo "=================================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Detect OS
OS="$(uname -s)"
case "${OS}" in
    Darwin*) OS_TYPE="macOS" ;;
    Linux*) OS_TYPE="Linux" ;;
    MINGW*|MSYS*|CYGWIN*) OS_TYPE="Windows" ;;
    *) OS_TYPE="Unknown" ;;
esac

echo "Detected OS: $OS_TYPE"
echo ""

# Step 1: Check Python version
echo "Step 1: Checking Python..."
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python3 not found${NC}"
    echo "Install Python from https://www.python.org/"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
echo -e "${GREEN}✅ Python ${PYTHON_VERSION}${NC}"
echo ""

# Step 2: Create virtual environment
echo "Step 2: Setting up virtual environment..."
if [ -d "venv" ]; then
    echo "Virtual environment already exists"
else
    python3 -m venv venv
    echo -e "${GREEN}✅ Virtual environment created${NC}"
fi
echo ""

# Step 3: Activate virtual environment
echo "Step 3: Activating virtual environment..."
if [ "$OS_TYPE" = "Windows" ]; then
    source venv/Scripts/activate
else
    source venv/bin/activate
fi
echo -e "${GREEN}✅ Virtual environment activated${NC}"
echo ""

# Step 4: Upgrade pip
echo "Step 4: Upgrading pip..."
python3 -m pip install --upgrade pip setuptools wheel > /dev/null 2>&1
echo -e "${GREEN}✅ pip upgraded${NC}"
echo ""

# Step 5: Install dependencies
echo "Step 5: Installing dependencies..."
if [ -f "requirements_v2.txt" ]; then
    pip install -r requirements_v2.txt
else
    pip install -r requirements.txt
fi
echo -e "${GREEN}✅ Dependencies installed${NC}"
echo ""

# Step 6: Install ChromeDriver (macOS only)
if [ "$OS_TYPE" = "macOS" ]; then
    echo "Step 6: Installing ChromeDriver..."
    if ! command -v chromedriver &> /dev/null; then
        if command -v brew &> /dev/null; then
            brew install chromedriver
            echo -e "${GREEN}✅ ChromeDriver installed${NC}"
        else
            echo -e "${YELLOW}⚠️  Homebrew not found. Install ChromeDriver manually:${NC}"
            echo "   Visit: https://chromedriver.chromium.org/"
            echo "   Extract to: /usr/local/bin/"
        fi
    else
        echo -e "${GREEN}✅ ChromeDriver already installed${NC}"
    fi
    echo ""
fi

# Step 7: Setup credentials
echo "Step 7: Setting up credentials..."
if [ -f ".env" ]; then
    echo -e "${YELLOW}⚠️  .env file already exists${NC}"
else
    cp .env.template .env
    echo -e "${YELLOW}❓ Edit .env with your TradingView credentials:${NC}"
    echo "   nano .env"
    echo ""
fi
echo ""

# Step 8: Create directories
echo "Step 8: Creating directories..."
mkdir -p data backtest logs models .cache
echo -e "${GREEN}✅ Directories created${NC}"
echo ""

# Step 9: Run health check
echo "Step 9: Running health check..."
if python3 main_v2.py health > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Health check passed${NC}"
else
    echo -e "${YELLOW}⚠️  Health check completed with warnings${NC}"
    python3 main_v2.py health
fi
echo ""

# Final steps
echo "=================================================="
echo -e "${GREEN}✅ SETUP COMPLETE${NC}"
echo "=================================================="
echo ""
echo "Next steps:"
echo ""
echo "1. Edit credentials:"
echo "   nano .env"
echo ""
echo "2. Generate signals:"
echo "   python3 main_v2.py signals"
echo ""
echo "3. Run backtest:"
echo "   python3 main_v2.py backtest"
echo ""
echo "4. View dashboard:"
echo "   streamlit run dashboard.py"
echo ""
echo "For help:"
echo "   python3 main_v2.py help"
echo ""
echo "For detailed setup guide, see MAC_SETUP_GUIDE.md"
echo ""
