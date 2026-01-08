# Kernel-Level Network Emulator

A **real-time, kernel-accurate network emulator** with live visualization, running on Linux.

**NOT a simulator** - This system uses the **actual Linux kernel** for all network behavior.

---

## 🚀 Quick Start

### Prerequisites
- **Linux** (Ubuntu/Debian recommended)
- **Root access** (sudo)
- **Python 3.8+**

### Installation

```bash
# 1. Clone/navigate to project directory
cd /path/to/network-simulator

# 2. Install dependencies (First time only)
sudo ./install_dependencies.sh

# 3. Start the emulator
sudo ./start_linux.sh
```

### Access
Open browser to: **http://localhost:8000**

---

## 📚 Documentation

Detailed documentation is available in the `docs/` directory:

- [**Command Booklet**](docs/NETWORK_COMMANDS_BOOKLET.md): A comprehensive guide to available network commands (ip, ping, nmap, etc.) and their usage.

---

## 📋 Features

### Core Capabilities
- ✅ **Real Linux Kernel Networking** - Uses actual network namespaces, veth pairs, and bridges
- ✅ **Real Terminal Access** - PTY-based terminals with real bash shells
- ✅ **Real Packet Capture** - tcpdump observing actual kernel packets
- ✅ **Traffic Control** - tc netem for latency, bandwidth, packet loss
- ✅ **Live Visualization** - Real-time network graph with packet animation
- ✅ **Failure Injection** - Interface down, ICMP blocking, silent router mode

### User Interface
- 🎨 Professional dark theme with glassmorphism
- 📊 Interactive network topology editor
- 💻 Full-featured terminal emulator (xterm.js)
- 🔍 Real-time packet monitoring
- ⚙️ Comprehensive property panels
- 🎯 Visual link creation with preview

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                  FRONTEND (Browser)                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │   Terminal   │  │ Visualization│  │   Topology   │  │
│  │  (xterm.js)  │  │ (vis-network)│  │   Editor     │  │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  │
└─────────┼──────────────────┼──────────────────┼─────────┘
          │ WebSocket        │ WebSocket        │ REST API
┌─────────▼──────────────────▼──────────────────▼─────────┐
│           BACKEND (Python FastAPI)                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │ PTY Manager  │  │   Packet     │  │  Topology    │  │
│  │ (Real Bash)  │  │  Observer    │  │  Manager     │  │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  │
└─────────┼──────────────────┼──────────────────┼─────────┘
          │ setns()          │ tcpdump          │ ip netns
┌─────────▼──────────────────▼──────────────────▼─────────┐
│                   LINUX KERNEL                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │  Namespaces  │  │  Networking  │  │    Traffic   │  │
│  │   (netns)    │  │ (veth/bridge)│  │  Control(tc) │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
└─────────────────────────────────────────────────────────┘
```

---

## 🎯 Usage Guide

### Creating a Network

1. **Add Devices**
   - Click device icons in left palette (Host, Router, Switch, DNS)
   - Enter device name when prompted

2. **Create Links**
   - Click "Link" tool in toolbar
   - Click source node (gets green border)
   - Hover over target (see preview line)
   - Click target node to create link
   - IPs are automatically assigned!

3. **Configure Devices**
   - Click any node to view properties
   - Edit hostname, gateway, interfaces
   - Use "Corruption" tab for failure injection
   - Use "Inspect" tab to view ARP, routes, sockets

4. **Open Terminal**
   - Click node → Click "Terminal" button
   - Real bash shell in that device's namespace
   - Run any Linux command: `ping`, `traceroute`, `ip`, etc.

### Supported Commands

All commands execute **real binaries** with **kernel-accurate behavior**:

- `ping` - ICMP echo requests
- `traceroute` - Multi-hop route tracing
- `ip addr` / `ip route` / `ip link` - Network configuration
- `ip neigh` - ARP cache
- `ss` / `netstat` - Socket statistics
- `tcpdump` - Packet capture
- `curl` / `nc` - HTTP/TCP/UDP
- Any other Linux networking command!

---

## 🔧 Configuration

### Link Properties
- **Latency**: Delay in milliseconds (via tc netem)
- **Bandwidth**: Limit in Mbps (via tc tbf)
- **Packet Loss**: Percentage (via tc netem)

### Failure Injection
- **Interface Down**: Disable network interface
- **Block ICMP**: Drop ICMP packets (iptables)
- **Silent Router**: Prevent ICMP error messages
- **Packet Loss**: Inject random packet drops

---

## 📊 Monitoring

### Real-Time Packet Monitoring
- **Monitor Tab**: Hop-by-hop packet events
- **Visual Animation**: Packets moving along links
- **Color Coding**: ICMP (green), TCP (blue), UDP (orange)

### Inspection Tools
- **ARP Cache**: View neighbor MAC addresses
- **Routing Table**: View kernel routes
- **Socket Statistics**: Active connections
- **Interface Status**: UP/DOWN state

---

## 🛠️ Technical Details

### Core Components

**Backend (Python)**
- `src/main.py` - FastAPI server
- `src/namespace_manager.py` - Network namespaces
- `src/link_manager.py` - veth/bridge/tc
- `src/pty_manager.py` - PTY terminals
- `src/packet_observer.py` - tcpdump capture
- `src/topology_manager.py` - Orchestration

**Frontend (JavaScript)**
- `static/index.html` - Complete UI
- `static/terminal.js` - Terminal manager

### Dependencies

**Python**
```
fastapi
uvicorn[standard]
websockets
pydantic
```

**System Tools**
```
iproute2 (ip command)
tcpdump
iptables
bridge-utils
nmap
net-tools
dnsutils
```

---

## 📝 Recent Changes

### 2026-01-07 - Optimization & Robustness
- 🔧 **Terminal Upgrade**: Switched to robust JSON protocol for terminal resizing and input.
- 🛠️ **Toolchain**: Added automated dependency installation (`install_dependencies.sh`).
- 📚 **Documentation**: Added comprehensive networking command booklet.
- 🧪 **Testing**: Added rigorous connectivity test suite.
- 🧹 **Cleanup**: Removed unused setup scripts.

### 2026-01-06 - UI Improvements
- ✅ Fixed IP display (now below node names)
- ✅ Implemented all control buttons (Save, Block ICMP, Silent Mode)
- ✅ Added backend API endpoints for failure injection

---

## 🎯 Use Cases

- **Education**: Teaching network protocols and routing
- **Research**: Testing network algorithms
- **Development**: Network application testing
- **Security**: Attack/defense simulation
- **Performance**: Bottleneck analysis
- **Debugging**: Network troubleshooting

---

## 🏆 Project Status

**Status**: ✅ Production-Ready
**Compliance**: ✅ 100% Kernel-Accurate
**Features**: ✅ All Core Features Implemented
**Documentation**: ✅ Complete
**Testing**: ✅ Verified

---

## 📞 Quick Reference

### Start Server
```bash
sudo ./start_linux.sh
```

### Stop Server
```bash
# Ctrl+C in terminal
# Or:
sudo pkill -f "python3 src/main.py"
```

### Check Status
```bash
curl http://localhost:8000/api/status
```

---

## 🎉 Enjoy Your Network Emulator!

This is a **real kernel-level network emulator** - not a simulation.
Every packet is real. Every route is real. Every command is real.

**Happy networking!** 🚀

---

*Last Updated: 2026-01-07*
*Version: 1.1*
*License: Educational/Research Use*
