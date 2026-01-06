# 🐧 Linux Setup Guide - Network Emulator

## Quick Start for Native Linux

This network emulator runs **natively** on Linux and provides the best performance compared to WSL2.

---

## Prerequisites

- **Linux Distribution**: Ubuntu 20.04+, Debian 11+, Fedora 35+, or similar
- **Kernel**: 5.4+ (check with `uname -r`)
- **Python**: 3.8 or higher
- **Root Access**: Required for network namespace operations

---

## Installation Steps

### 1. Install System Dependencies

#### Ubuntu/Debian:
```bash
sudo apt update
sudo apt install -y \
    python3 \
    python3-pip \
    python3-venv \
    iproute2 \
    iputils-ping \
    traceroute \
    tcpdump \
    iptables \
    net-tools \
    dnsmasq
```

#### Fedora/RHEL:
```bash
sudo dnf install -y \
    python3 \
    python3-pip \
    iproute \
    iputils \
    traceroute \
    tcpdump \
    iptables \
    net-tools \
    dnsmasq
```

### 2. Clone/Navigate to Project

```bash
cd /path/to/network-simulator
```

### 3. Create Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate
```

### 4. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 5. Verify Kernel Capabilities

```bash
# Check if network namespaces are supported
sudo ip netns add test-ns
sudo ip netns list
sudo ip netns delete test-ns

# Should show "test-ns" in the list
```

---

## Running the Emulator

### Start the Server

```bash
# Activate virtual environment
source venv/bin/activate

# Run as root (required for network namespaces)
sudo python3 src/main.py
```

### Access the Web Interface

Open your browser and navigate to:
```
http://localhost:8000
```

---

## Testing the Installation

### Quick Test

```bash
# In a new terminal, test the API
curl http://localhost:8000/api/status

# Should return:
# {"status":"running","devices":0,"links":0,...}
```

### Create a Simple Topology

```bash
# Create two hosts
curl -X POST http://localhost:8000/api/devices \
  -H "Content-Type: application/json" \
  -d '{"name":"host1","type":"host","ip_address":"10.0.1.10"}'

curl -X POST http://localhost:8000/api/devices \
  -H "Content-Type: application/json" \
  -d '{"name":"host2","type":"host","ip_address":"10.0.1.20"}'

# Create a link
curl -X POST http://localhost:8000/api/links \
  -H "Content-Type: application/json" \
  -d '{"device_a":"host1","device_b":"host2","latency_ms":10}'
```

### Test Terminal Access

1. Open the web interface at `http://localhost:8000`
2. Click on a host node
3. Click "Terminal" button
4. Run commands like:
   ```bash
   ping 10.0.1.20
   ifconfig
   route -n
   ```

---

## Architecture Overview

```
┌─────────────────────────────────────────┐
│         Browser (Web UI)                │
│  - Terminal (xterm.js)                  │
│  - Packet Visualization                 │
│  - Topology Editor                      │
└──────────────┬──────────────────────────┘
               │ WebSocket + REST API
┌──────────────▼──────────────────────────┐
│      FastAPI Backend (main.py)          │
│  - REST API Endpoints                   │
│  - WebSocket Handlers                   │
│  - Topology Manager                     │
└──────────────┬──────────────────────────┘
               │ System Calls
┌──────────────▼──────────────────────────┐
│         Linux Kernel                    │
│  - Network Namespaces (ip netns)        │
│  - Virtual Ethernet (veth)              │
│  - Traffic Control (tc)                 │
│  - Packet Filtering (iptables)          │
│  - Real TCP/IP Stack                    │
└─────────────────────────────────────────┘
```

---

## File Structure

```
network-simulator/
├── src/
│   ├── main.py                 # FastAPI server (NEW)
│   ├── namespace_manager.py    # Network namespace management
│   ├── link_manager.py         # veth pairs and bridges
│   ├── pty_manager.py          # Real terminal execution
│   ├── packet_observer.py      # Kernel packet capture
│   └── topology_manager.py     # High-level orchestration
├── static/
│   ├── index.html              # Web UI (UPDATED)
│   ├── packet-animation.js     # Packet visualization (UPDATED)
│   ├── terminal.js             # Terminal manager (NEW)
│   └── api-client.js           # API wrapper (NEW)
├── requirements.txt            # Python dependencies (NEW)
├── .gitignore                  # Git ignore file (NEW)
└── README.md                   # Main documentation
```

---

## Troubleshooting

### Permission Denied Errors

```bash
# Make sure you're running as root
sudo python3 src/main.py
```

### Port Already in Use

```bash
# Check what's using port 8000
sudo lsof -i :8000

# Kill the process or change port in main.py
```

### Network Namespace Errors

```bash
# Clean up any existing namespaces
sudo ip -all netns delete

# Restart the server
sudo python3 src/main.py
```

### Python Module Not Found

```bash
# Make sure virtual environment is activated
source venv/bin/activate

# Reinstall dependencies
pip install -r requirements.txt
```

---

## Performance Tips

### For Best Performance:

1. **Use Native Linux** (not WSL2 or VM)
2. **Disable Firewall** (if testing locally):
   ```bash
   sudo ufw disable  # Ubuntu
   sudo systemctl stop firewalld  # Fedora
   ```
3. **Increase File Descriptors**:
   ```bash
   ulimit -n 4096
   ```

---

## Security Considerations

⚠️ **WARNING**: This emulator requires root privileges and creates network namespaces.

### Running in Production:

1. **Isolate the Server**: Run on a dedicated machine or VM
2. **Firewall Rules**: Restrict access to port 8000
3. **Authentication**: Add authentication to the web interface
4. **Resource Limits**: Use cgroups to limit resource usage

---

## Next Steps

1. ✅ Install dependencies
2. ✅ Start the server
3. ✅ Open web interface
4. ✅ Create your first topology
5. ✅ Run ping/traceroute commands
6. ✅ Watch real-time packet animations

---

## Support

For issues or questions:
- Check the documentation in `docs/`
- Review `TESTING_INSTRUCTIONS.md`
- Check kernel capabilities with `test_core_components.sh`

---

**Enjoy building real networks!** 🚀
