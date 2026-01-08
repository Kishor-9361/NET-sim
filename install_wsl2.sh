#!/bin/bash

# Automated WSL2 Installation Script for Network Emulator
# Run this script in WSL2 Ubuntu

set -e  # Exit on error

echo "=========================================="
echo "Network Emulator - WSL2 Setup Script"
echo "=========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if running in WSL2
if ! grep -qi microsoft /proc/version; then
    echo -e "${RED}Error: This script must be run in WSL2${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Running in WSL2${NC}"
echo ""

# Update system
echo "Step 1: Updating system packages..."
sudo apt update -qq
sudo apt upgrade -y -qq
echo -e "${GREEN}✓ System updated${NC}"
echo ""

# Install network tools
echo "Step 2: Installing network tools..."
sudo apt install -y -qq \
    iproute2 \
    iputils-ping \
    traceroute \
    tcpdump \
    iptables \
    bridge-utils \
    dnsmasq \
    net-tools \
    ethtool \
    netcat \
    curl \
    wget \
    nmap \
    iperf3 \
    mtr \
    socat
echo -e "${GREEN}✓ Network tools installed${NC}"
echo ""

# Install Python
echo "Step 3: Installing Python 3.10+..."
sudo apt install -y -qq \
    python3 \
    python3-pip \
    python3-venv \
    python3-dev
echo -e "${GREEN}✓ Python installed${NC}"
python3 --version
echo ""

# Install development tools
echo "Step 4: Installing development tools..."
sudo apt install -y -qq \
    build-essential \
    git \
    vim \
    htop \
    jq
echo -e "${GREEN}✓ Development tools installed${NC}"
echo ""

# Configure sudoers for network commands
echo "Step 5: Configuring passwordless sudo for network commands..."
SUDOERS_FILE="/etc/sudoers.d/netemu"
if [ ! -f "$SUDOERS_FILE" ]; then
    sudo tee "$SUDOERS_FILE" > /dev/null << EOF
# Network Emulator - Passwordless sudo for network commands
%sudo ALL=(ALL) NOPASSWD: /usr/sbin/ip
%sudo ALL=(ALL) NOPASSWD: /usr/sbin/tc
%sudo ALL=(ALL) NOPASSWD: /usr/sbin/iptables
%sudo ALL=(ALL) NOPASSWD: /usr/sbin/tcpdump
%sudo ALL=(ALL) NOPASSWD: /usr/sbin/brctl
%sudo ALL=(ALL) NOPASSWD: /usr/bin/dnsmasq
EOF
    sudo chmod 0440 "$SUDOERS_FILE"
    echo -e "${GREEN}✓ Sudoers configured${NC}"
else
    echo -e "${YELLOW}⚠ Sudoers file already exists${NC}"
fi
echo ""

# Create project directory
echo "Step 6: Creating project directory..."
PROJECT_DIR="$HOME/network-emulator"
if [ ! -d "$PROJECT_DIR" ]; then
    mkdir -p "$PROJECT_DIR"
    echo -e "${GREEN}✓ Project directory created: $PROJECT_DIR${NC}"
else
    echo -e "${YELLOW}⚠ Project directory already exists${NC}"
fi
cd "$PROJECT_DIR"
echo ""

# Create Python virtual environment
echo "Step 7: Creating Python virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo -e "${GREEN}✓ Virtual environment created${NC}"
else
    echo -e "${YELLOW}⚠ Virtual environment already exists${NC}"
fi

# Activate virtual environment
source venv/bin/activate
echo -e "${GREEN}✓ Virtual environment activated${NC}"
echo ""

# Install Python dependencies
echo "Step 8: Installing Python dependencies..."
pip install --upgrade pip -q
pip install -q \
    fastapi \
    uvicorn[standard] \
    websockets \
    pydantic \
    python-multipart \
    aiofiles \
    psutil \
    python-iptables
echo -e "${GREEN}✓ Python dependencies installed${NC}"
echo ""

# Test kernel capabilities
echo "Step 9: Testing kernel capabilities..."

# Test namespace creation
echo -n "  Testing network namespaces... "
if sudo ip netns add test-ns 2>/dev/null; then
    sudo ip netns delete test-ns
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${RED}✗${NC}"
    echo -e "${RED}Error: Cannot create network namespaces${NC}"
    exit 1
fi

# Test veth pair creation
echo -n "  Testing veth pairs... "
if sudo ip link add veth0 type veth peer name veth1 2>/dev/null; then
    sudo ip link delete veth0
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${RED}✗${NC}"
    echo -e "${RED}Error: Cannot create veth pairs${NC}"
    exit 1
fi

# Test bridge creation
echo -n "  Testing bridges... "
if sudo ip link add br0 type bridge 2>/dev/null; then
    sudo ip link delete br0
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${RED}✗${NC}"
    echo -e "${RED}Error: Cannot create bridges${NC}"
    exit 1
fi

# Test tc (traffic control)
echo -n "  Testing traffic control (tc)... "
if which tc > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${RED}✗${NC}"
    echo -e "${RED}Error: tc not available${NC}"
    exit 1
fi

# Test iptables
echo -n "  Testing iptables... "
if sudo iptables -L > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${RED}✗${NC}"
    echo -e "${RED}Error: iptables not working${NC}"
    exit 1
fi

# Test tcpdump
echo -n "  Testing tcpdump... "
if which tcpdump > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${RED}✗${NC}"
    echo -e "${RED}Error: tcpdump not available${NC}"
    exit 1
fi

echo ""

# Create directory structure
echo "Step 10: Creating directory structure..."
mkdir -p src
mkdir -p static
mkdir -p tests
mkdir -p docs
mkdir -p logs
echo -e "${GREEN}✓ Directory structure created${NC}"
echo ""

# Create systemd service (optional)
echo "Step 11: Creating systemd service..."
SERVICE_FILE="$HOME/.config/systemd/user/network-emulator.service"
mkdir -p "$HOME/.config/systemd/user"
cat > "$SERVICE_FILE" << EOF
[Unit]
Description=Network Emulator Backend
After=network.target

[Service]
Type=simple
WorkingDirectory=$PROJECT_DIR
ExecStart=$PROJECT_DIR/venv/bin/python src/main.py
Restart=on-failure
RestartSec=5s

[Install]
WantedBy=default.target
EOF
echo -e "${GREEN}✓ Systemd service created${NC}"
echo ""

# Create helper scripts
echo "Step 12: Creating helper scripts..."

# Start script
cat > start.sh << 'EOF'
#!/bin/bash
cd "$(dirname "$0")"
source venv/bin/activate
python3 src/main.py
EOF
chmod +x start.sh

# Stop script
cat > stop.sh << 'EOF'
#!/bin/bash
pkill -f "python3 src/main.py"
EOF
chmod +x stop.sh

# Cleanup script
cat > cleanup.sh << 'EOF'
#!/bin/bash
echo "Cleaning up network namespaces..."
for ns in $(sudo ip netns list | awk '{print $1}'); do
    echo "  Deleting namespace: $ns"
    sudo ip netns delete "$ns"
done
echo "Done."
EOF
chmod +x cleanup.sh

echo -e "${GREEN}✓ Helper scripts created${NC}"
echo ""

# Print summary
echo "=========================================="
echo -e "${GREEN}Installation Complete!${NC}"
echo "=========================================="
echo ""
echo "Project directory: $PROJECT_DIR"
echo ""
echo "Next steps:"
echo "  1. Copy the source code to: $PROJECT_DIR/src/"
echo "  2. Copy the static files to: $PROJECT_DIR/static/"
echo "  3. Run: ./start.sh"
echo ""
echo "Useful commands:"
echo "  Start server:    ./start.sh"
echo "  Stop server:     ./stop.sh"
echo "  Cleanup:         ./cleanup.sh"
echo "  View logs:       tail -f logs/emulator.log"
echo ""
echo "Access the web interface at:"
echo "  http://localhost:8000"
echo ""
echo -e "${YELLOW}Note: You may need to configure port forwarding from Windows${NC}"
echo "      to access the web interface from Windows browser."
echo ""
