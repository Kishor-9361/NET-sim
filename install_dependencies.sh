#!/bin/bash
# Install network tools for the simulator
# This script installs common network utilities required for the simulator's test cases.

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}Installing network tools...${NC}"

if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Please run as root (sudo)${NC}"
    exit 1
fi

apt-get update

# List of packages to install
PACKAGES="ifupdown dnsutils net-tools traceroute ethtool iputils-ping netcat-openbsd tcpdump nmap"

echo -e "${BLUE}Installing packages: ${PACKAGES}${NC}"
apt-get install -y $PACKAGES

echo -e "${GREEN}Installation complete!${NC}"
echo -e "${BLUE}Verifying installations:${NC}"

for cmd in ifup ifdown ifquery nslookup dig netstat traceroute ethtool ping nc tcpdump nmap; do
    if command -v $cmd >/dev/null; then
        echo -e "${GREEN}✓ $cmd found${NC}"
    else
        echo -e "${RED}✗ $cmd NOT found${NC}"
    fi
done

# Check nmap version/type
echo -e "${BLUE}Checking nmap type...${NC}"
if which nmap | grep -q snap; then
    echo -e "${RED}WARNING: nmap is installed via snap. It may not work inside namespaces.${NC}"
    echo -e "${RED}Recommendation: snap remove nmap && apt install nmap${NC}"
else
    echo -e "${GREEN}✓ nmap is standard binary (good for namespaces)${NC}"
fi
