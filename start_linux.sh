#!/bin/bash
#
# Network Emulator Startup Script for Linux
# Run this script to start the network emulator server
#

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   Network Emulator - Linux Startup    ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════╝${NC}"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}✗ Error: This script must be run as root${NC}"
    echo -e "${YELLOW}  Please run: sudo $0${NC}"
    exit 1
fi

echo -e "${GREEN}✓${NC} Running as root"

# Check if Python 3 is installed
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}✗ Error: Python 3 is not installed${NC}"
    echo -e "${YELLOW}  Install with: sudo apt install python3${NC}"
    exit 1
fi

echo -e "${GREEN}✓${NC} Python 3 found: $(python3 --version)"

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}⚠${NC} Virtual environment not found"
    echo -e "${BLUE}  Creating virtual environment...${NC}"
    python3 -m venv venv
    echo -e "${GREEN}✓${NC} Virtual environment created"
fi

# Activate virtual environment
echo -e "${BLUE}  Activating virtual environment...${NC}"
source venv/bin/activate

# Check if dependencies are installed
if ! python3 -c "import fastapi" &> /dev/null; then
    echo -e "${YELLOW}⚠${NC} Dependencies not installed"
    echo -e "${BLUE}  Installing dependencies...${NC}"
    pip install -r requirements.txt
    echo -e "${GREEN}✓${NC} Dependencies installed"
else
    echo -e "${GREEN}✓${NC} Dependencies already installed"
fi

# Check kernel capabilities
echo -e "${BLUE}  Checking kernel capabilities...${NC}"

if ! ip netns list &> /dev/null; then
    echo -e "${RED}✗ Error: Network namespaces not supported${NC}"
    echo -e "${YELLOW}  Your kernel may not support network namespaces${NC}"
    exit 1
fi

echo -e "${GREEN}✓${NC} Network namespaces supported"

# Clean up any existing namespaces from previous runs
echo -e "${BLUE}  Cleaning up previous namespaces and interfaces...${NC}"
for ns in $(ip netns list | awk '{print $1}'); do
    ip netns delete "$ns" 2>/dev/null || true
done

# Clean up bridges starting with br-
for br in $(ip link show type bridge | awk -F': ' '{print $2}'); do
    if [[ $br == br-* ]]; then
        ip link delete "$br" type bridge 2>/dev/null || true
    fi
done

# Clean up any stray veth interfaces
for veth in $(ip link show | grep -o 'veth-[a-f0-9]*'); do
    ip link delete "$veth" 2>/dev/null || true
done

echo -e "${GREEN}✓${NC} Cleanup complete"

# Start the server
echo ""
echo -e "${GREEN}╔════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║   Starting Network Emulator Server    ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════╝${NC}"
echo ""
echo -e "${BLUE}  Server URL:${NC} http://localhost:8000"
echo -e "${BLUE}  Press Ctrl+C to stop${NC}"
echo ""

# Run the server
cd "$(dirname "$0")"
python3 src/main.py
