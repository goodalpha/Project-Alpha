#!/bin/bash

# PROJECT ATLAS - Alpaca Setup Script
# Sets environment variables and tests connection

set -e

echo ""
echo "╔══════════════════════════════════════════════════════════════════════════╗"
echo "║           PROJECT ATLAS - Alpaca Setup Script                           ║"
echo "╚══════════════════════════════════════════════════════════════════════════╝"
echo ""

# Check if credentials are provided
if [ $# -ne 2 ]; then
    echo "Usage: ./setup_alpaca.sh <API_KEY> <SECRET_KEY>"
    echo ""
    echo "Example:"
    echo "  ./setup_alpaca.sh PKxxxxxxxxxxxxxx your_secret_key_here"
    echo ""
    echo "Get your credentials from: https://app.alpaca.markets/settings/keys"
    echo ""
    exit 1
fi

API_KEY=$1
SECRET_KEY=$2

echo "📝 Setting environment variables..."
export APCA_API_KEY_ID="$API_KEY"
export APCA_API_SECRET_KEY="$SECRET_KEY"

echo "✅ Environment variables set:"
echo "   APCA_API_KEY_ID: ${APCA_API_KEY_ID:0:8}..."
echo "   APCA_API_SECRET_KEY: (hidden)"
echo ""

echo "🧪 Testing connection to Alpaca (PAPER TRADING)..."
python alpaca_trader.py

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Setup complete! You can now:"
    echo ""
    echo "1. Make credentials persistent:"
    echo "   echo 'export APCA_API_KEY_ID=\"$API_KEY\"' >> ~/.bashrc"
    echo "   echo 'export APCA_API_SECRET_KEY=\"$SECRET_KEY\"' >> ~/.bashrc"
    echo "   source ~/.bashrc"
    echo ""
    echo "2. Start paper trading:"
    echo "   python main.py --live-paper"
    echo ""
    echo "3. Monitor in dashboard:"
    echo "   streamlit run dashboard.py"
    echo ""
else
    echo ""
    echo "❌ Connection test failed. Check your credentials and try again."
    exit 1
fi
