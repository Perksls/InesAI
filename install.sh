#!/bin/bash
# InesAI — One-shot installer
# Run from the project root: bash install.sh

set -e

YELLOW='\033[1;33m'
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${YELLOW}"
echo "  ___                 _    ___ "
echo " |_ _|_ __   ___  ___| |  / _ \\"
echo "  | || '_ \\ / _ \\/ __| | | (_) |"
echo "  | || | | |  __/\\__ \\ |  \\__, |"
echo " |___|_| |_|\\___||___/_|    /_/ "
echo -e "${NC}"
echo "Lightweight multi-provider AI chat"
echo "------------------------------------"
echo ""

# Check Python
if ! command -v python3 &>/dev/null; then
    echo -e "${RED}Error: python3 not found. Install it first.${NC}"
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo -e "✓ Python $PYTHON_VERSION found"

# Create venv
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi
source venv/bin/activate
echo -e "✓ Virtual environment ready"

# Install dependencies
echo "Installing dependencies..."
pip install -q --upgrade pip
pip install -q -r requirements.txt
echo -e "✓ Dependencies installed"

# Config
if [ ! -f "config.json" ]; then
    cp config.example.json config.json
    echo -e "${YELLOW}⚠  config.json created from template."
    echo -e "   Edit it and add at least one API key before starting.${NC}"
else
    echo -e "✓ config.json already exists"
fi

# Secret key
if [ ! -f ".env" ]; then
    SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")
    echo "INESBOT_SECRET=$SECRET" > .env
    chmod 600 .env
    echo -e "✓ Secret key generated (.env)"
else
    echo -e "✓ .env already exists"
fi

# Make scripts executable
chmod +x start.sh stop.sh restart.sh 2>/dev/null || true

# Create user
echo ""
echo -e "${YELLOW}Creating first user...${NC}"
python3 manage_users.py setup

echo ""
echo -e "${GREEN}✓ Installation complete!${NC}"
echo ""
echo "Next steps:"
echo "  1. Edit config.json and add your API keys"
echo "  2. Run: ./start.sh"
echo "  3. Open: http://$(hostname -I | awk '{print $1}'):8001"
echo ""
echo "For production (nginx + systemd):"
echo "  ./install-nginx.sh"
echo "  ./install-systemd.sh"
echo ""
