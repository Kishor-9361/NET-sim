# Kernel-Level Network Emulator

## 🚀 What Is This?

A **real-time, kernel-accurate network emulator** with live visualization, running on WSL2 (Windows Subsystem for Linux 2).

**NOT a simulator** - This system uses the **actual Linux kernel** for all network behavior:
- ✅ Real network namespaces (isolated Linux environments)
- ✅ Real veth pairs and bridges (kernel virtual networking)
- ✅ Real PTY terminals (actual `/bin/ping`, `/bin/traceroute`)
- ✅ Real packet capture (tcpdump observing kernel packets)
- ✅ Real traffic control (kernel latency, bandwidth, packet loss)

---

## ⚠️ IMPORTANT: System Requirements

### Required
- **Windows 10** (Build 19041+) or **Windows 11**
- **WSL2** installed and configured
- **Ubuntu 22.04** in WSL2
- **Administrator access**
- **8GB RAM minimum** (16GB recommended)

### This Will NOT Work On
- ❌ Native Windows (requires Linux kernel)
- ❌ WSL1 (requires WSL2 for network namespaces)
- ❌ macOS (requires Linux kernel)
- ❌ Docker Desktop alone (WSL2 backend required)

---

## 📋 Quick Start

### Step 1: Install WSL2

```powershell
# In PowerShell as Administrator
wsl --install
```

**Reboot if prompted**, then verify:

```powershell
wsl --status
wsl --list --verbose
```

### Step 2: Run Installation Script

```bash
# In WSL2 Ubuntu terminal
cd /mnt/c/Users/Admin/.gemini/antigravity/scratch/network-simulator
chmod +x install_wsl2.sh
./install_wsl2.sh
```

This installs all dependencies and configures the environment.

### Step 3: Start the Emulator

```bash
cd ~/network-emulator
source venv/bin/activate
python3 src/main.py  # (to be created)
```

### Step 4: Access Web Interface

From Windows browser:
```
http://localhost:8000
```

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                  FRONTEND (Browser)                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │   Terminal   │  │ Visualization│  │   Topology   │  │
│  │  (xterm.js)  │  │   (Canvas)   │  │   Editor     │  │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  │
└─────────┼──────────────────┼──────────────────┼─────────┘
          │ WebSocket        │ WebSocket        │ HTTP/REST
          │                  │                  │
┌─────────▼──────────────────▼──────────────────▼─────────┐
│           BACKEND (Python FastAPI + WSL2)                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │ PTY Manager  │  │   Packet     │  │  Topology    │  │
│  │ (Real Shell) │  │  Observer    │  │  Manager     │  │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  │
└─────────┼──────────────────┼──────────────────┼─────────┘
          │                  │                  │
          │ pty.openpty()    │ tcpdump          │ ip netns
          │                  │                  │
┌─────────▼──────────────────▼──────────────────▼─────────┐
│                   LINUX KERNEL (WSL2)                    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │     PTY      │  │   Network    │  │   Network    │  │
│  │  Subsystem   │  │    Stack     │  │  Namespaces  │  │
│  │              │  │  (TCP/IP)    │  │  (veth/br)   │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
└──────────────────────────────────────────────────────────┘
```

---

## 🔧 Core Components

### 1. Namespace Manager (`src/namespace_manager.py`)
Creates and manages Linux network namespaces (isolated network environments).

**Each device = one namespace**

```python
from namespace_manager import NamespaceManager, DeviceType

manager = NamespaceManager()
host1 = manager.create_namespace("host1", DeviceType.HOST)
router1 = manager.create_namespace("router1", DeviceType.ROUTER)
```

### 2. Link Manager (`src/link_manager.py`)
Creates veth pairs (virtual ethernet) and bridges for network connectivity.

**Each link = veth pair or bridge connection**

```python
from link_manager import LinkManager

link_mgr = LinkManager()
link = link_mgr.create_p2p_link(
    namespace_a="host1",
    interface_a="eth0",
    namespace_b="router1",
    interface_b="eth0",
    latency_ms=10.0
)
```

### 3. PTY Manager (`src/pty_manager.py`)
Manages pseudo-terminals for real command execution.

**Real Linux commands, real output**

```python
from pty_manager import PTYManager

pty_mgr = PTYManager()
session = pty_mgr.create_session("session1", "host1")
pty_mgr.execute_command("session1", "ping 10.0.1.20")
```

### 4. Packet Observer (`src/packet_observer.py`)
Captures real packets from kernel using tcpdump.

**Passive observation, never affects packets**

```python
from packet_observer import PacketObserverManager

observer_mgr = PacketObserverManager()
observer_mgr.start_observer("host1", "eth0")
```

### 5. Topology Manager (`src/topology_manager.py`)
High-level orchestration of all components.

**Simplified API for network creation**

```python
from topology_manager import TopologyManager

topology = TopologyManager()
host1 = topology.add_device("host1", "host")
host2 = topology.add_device("host2", "host")
link = topology.add_link("host1", "host2", latency_ms=5.0)
```

---

## 📚 Documentation

### Essential Reading
1. **[Transformation Summary](docs/TRANSFORMATION_SUMMARY.md)** - Executive summary and status
2. **[Architecture](docs/KERNEL_EMULATOR_ARCHITECTURE.md)** - Complete technical design
3. **[WSL2 Setup Guide](docs/WSL2_SETUP_GUIDE.md)** - Detailed installation instructions
4. **[Transformation README](docs/TRANSFORMATION_README.md)** - Quick start guide

### Reference
- Linux Network Namespaces: https://man7.org/linux/man-pages/man8/ip-netns.8.html
- Traffic Control (tc): https://man7.org/linux/man-pages/man8/tc.8.html
- PTY: https://man7.org/linux/man-pages/man7/pty.7.html

---

## 🎯 Key Differences from Simulation

### Terminal Execution

**Before (Simulated)**:
```python
# Fake output generation
return "PING 10.0.1.20: 64 bytes from 10.0.1.20: time=10.5 ms"
```

**After (Real)**:
```python
# Execute actual /bin/ping in namespace
pty_manager.execute_command(session_id, f"ping {target}")
# Output comes from real Linux binary
```

### Packet Routing

**Before (Simulated)**:
```python
# Python logic determines routing
next_hop = find_next_hop(packet.dst_ip)
```

**After (Real)**:
```bash
# Kernel routing table handles everything
# No Python routing logic needed!
```

### Network Failures

**Before (Simulated)**:
```python
if failure_active:
    return  # Drop packet in Python
```

**After (Real)**:
```bash
# Use kernel mechanisms
sudo ip netns exec host1 tc qdisc add dev eth0 root netem loss 30%
```

---

## 🧪 Testing

### Verify Kernel Capabilities

```bash
# In WSL2
cd ~/network-emulator

# Test namespace creation
sudo ip netns add test-ns
sudo ip netns list
sudo ip netns delete test-ns

# Test veth pair
sudo ip link add veth0 type veth peer name veth1
ip link show type veth
sudo ip link delete veth0
```

### Test Components

```bash
# Test each component
python3 src/namespace_manager.py
python3 src/link_manager.py
python3 src/pty_manager.py
python3 src/packet_observer.py
python3 src/topology_manager.py
```

---

## 📊 Status

### ✅ Complete
- [x] Namespace Manager
- [x] Link Manager
- [x] PTY Manager
- [x] Packet Observer
- [x] Topology Manager
- [x] Architecture Documentation
- [x] Installation Scripts

### 🚧 In Progress
- [ ] FastAPI Server (`src/main.py`)
- [ ] WebSocket Handlers
- [ ] Frontend Integration
- [ ] End-to-End Testing

### 📅 Planned
- [ ] Advanced Protocols (BGP, OSPF)
- [ ] eBPF Packet Capture
- [ ] Multi-Host Emulation
- [ ] Cloud Integration

---

## 🐛 Troubleshooting

### "Permission denied" creating namespaces
```bash
# Ensure sudo is configured
sudo cat /etc/sudoers.d/netemu
```

### PTY not responding
```bash
# Check bash is running
sudo ip netns exec <namespace> ps aux | grep bash
```

### tcpdump not capturing
```bash
# Test manual capture
sudo ip netns exec <namespace> tcpdump -i <interface> -c 5
```

See **[WSL2 Setup Guide](docs/WSL2_SETUP_GUIDE.md)** for detailed troubleshooting.

---

## 🎓 Terminology

**This system is**:
- ✅ Kernel-Level Network Emulator
- ✅ Real-Time Network Testbed
- ✅ Linux Network Namespace Visualizer

**This system is NOT**:
- ❌ Network Simulator
- ❌ Mock Network
- ❌ AI-Driven Network

---

## 📝 License

Educational and research use.

---

## 🙏 Credits

Built with:
- **Linux Kernel** - Network namespaces, veth, tc
- **Python** - FastAPI, asyncio
- **tcpdump** - Packet capture
- **WSL2** - Windows Subsystem for Linux

---

**Version**: 2.0 (Kernel-Level Emulator)  
**Last Updated**: 2026-01-05  
**Status**: Core Complete, Integration Pending

**Next Steps**: See [Transformation Summary](docs/TRANSFORMATION_SUMMARY.md)
