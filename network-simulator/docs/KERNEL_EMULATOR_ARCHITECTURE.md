# Kernel-Level Network Emulator Architecture

## Executive Summary

This document describes the complete transformation from a **simulated network** to a **real-time, kernel-accurate network emulator** with live visualization.

**Status**: Architecture Design  
**Target Platform**: WSL2 (Windows Subsystem for Linux 2)  
**Kernel**: Linux 5.x+ with network namespace support  

---

## 1. ARCHITECTURAL PRINCIPLES

### 1.1 Core Constraint
**NO SIMULATION ALLOWED**. Every network behavior must originate from the Linux kernel TCP/IP stack.

### 1.2 Separation of Concerns
```
┌─────────────────────────────────────────────────────────┐
│                    FRONTEND (Browser)                    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │   Terminal   │  │ Visualization│  │   Topology   │  │
│  │   Display    │  │    Canvas    │  │   Editor     │  │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  │
└─────────┼──────────────────┼──────────────────┼─────────┘
          │                  │                  │
          │ WebSocket        │ WebSocket        │ HTTP/REST
          │                  │                  │
┌─────────▼──────────────────▼──────────────────▼─────────┐
│              BACKEND (Python FastAPI)                    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │ PTY Manager  │  │   Packet     │  │  Topology    │  │
│  │ (Real Shell) │  │  Observer    │  │  Manager     │  │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  │
└─────────┼──────────────────┼──────────────────┼─────────┘
          │                  │                  │
          │ exec()           │ eBPF/tcpdump     │ ip netns
          │                  │                  │
┌─────────▼──────────────────▼──────────────────▼─────────┐
│                    LINUX KERNEL                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │     PTY      │  │   Network    │  │   Network    │  │
│  │  Subsystem   │  │    Stack     │  │  Namespaces  │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
└──────────────────────────────────────────────────────────┘
```

### 1.3 Data Flow Rules
1. **Terminal Output**: PTY → Backend → WebSocket → Frontend (READ-ONLY)
2. **Packet Events**: Kernel → eBPF/tcpdump → Backend → WebSocket → Frontend (READ-ONLY)
3. **Network Behavior**: Kernel ONLY (no application-level routing logic)

---

## 2. NETWORK CORE IMPLEMENTATION

### 2.1 Network Namespace Architecture

Each simulated device is a **Linux network namespace**:

```bash
# Example: Creating a host
ip netns add host1
ip netns exec host1 ip link set lo up
ip netns exec host1 ip addr add 10.0.1.10/24 dev eth0
```

**Node Type Mapping**:
- **Host** → Network namespace with single veth interface
- **Router** → Network namespace with multiple veth interfaces + IP forwarding enabled
- **Switch** → Linux bridge (br0) connecting multiple veth pairs
- **DNS Server** → Network namespace running dnsmasq

### 2.2 Link Implementation

Links are **veth pairs** + **Linux bridges**:

```bash
# Create veth pair
ip link add veth-host1 type veth peer name veth-br0

# Attach to namespace
ip link set veth-host1 netns host1

# Attach to bridge (switch)
ip link set veth-br0 master br0

# Configure in namespace
ip netns exec host1 ip addr add 10.0.1.10/24 dev veth-host1
ip netns exec host1 ip link set veth-host1 up
```

**Latency Simulation** (using tc - Traffic Control):
```bash
# Add 10ms latency to link
ip netns exec host1 tc qdisc add dev veth-host1 root netem delay 10ms
```

### 2.3 Routing

**Automatic Routing** via kernel routing tables:

```bash
# Add default gateway
ip netns exec host1 ip route add default via 10.0.1.1

# Router forwarding
ip netns exec router1 sysctl -w net.ipv4.ip_forward=1
```

**NO Python-based routing logic**. All routing decisions made by kernel.

---

## 3. TERMINAL IMPLEMENTATION

### 3.1 PTY (Pseudo-Terminal) Architecture

```python
import pty
import os
import select

class NamespacePTY:
    def __init__(self, namespace: str):
        self.namespace = namespace
        self.master_fd, self.slave_fd = pty.openpty()
        
    def spawn_shell(self):
        """Spawn bash in network namespace"""
        pid = os.fork()
        if pid == 0:  # Child process
            # Enter network namespace
            os.system(f'ip netns exec {self.namespace} /bin/bash')
            os._exit(0)
        return pid
    
    def read_output(self) -> bytes:
        """Read raw bytes from PTY (non-blocking)"""
        if select.select([self.master_fd], [], [], 0)[0]:
            return os.read(self.master_fd, 4096)
        return b''
    
    def write_input(self, data: str):
        """Write to PTY (send command)"""
        os.write(self.master_fd, data.encode())
```

### 3.2 Command Execution Flow

```
User types: "ping 10.0.1.20"
    ↓
Frontend sends via WebSocket
    ↓
Backend writes to PTY: master_fd.write(b"ping 10.0.1.20\n")
    ↓
Linux kernel executes /bin/ping in namespace
    ↓
Real ICMP packets sent via kernel
    ↓
PTY captures stdout/stderr byte-by-byte
    ↓
Backend streams to frontend via WebSocket
    ↓
Frontend displays in terminal (with ANSI codes preserved)
```

**Critical**: NO command parsing, NO fake output generation. Only real Linux binaries.

---

## 4. PACKET OBSERVATION LAYER

### 4.1 Passive Packet Capture

**Method 1: tcpdump + libpcap**
```python
import subprocess
import json

class PacketObserver:
    def __init__(self, namespace: str, interface: str):
        self.namespace = namespace
        self.interface = interface
        
    def start_capture(self):
        """Start tcpdump in namespace"""
        cmd = [
            'ip', 'netns', 'exec', self.namespace,
            'tcpdump', '-i', self.interface,
            '-l',  # Line buffered
            '-n',  # No DNS resolution
            '-tt', # Unix timestamp
            '-e',  # Ethernet header
            'not', 'port', '22'  # Exclude SSH
        ]
        self.process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            bufsize=1
        )
    
    def read_packet(self) -> dict:
        """Parse tcpdump output into packet event"""
        line = self.process.stdout.readline().decode()
        # Parse: "1641234567.123456 IP 10.0.1.10 > 10.0.1.20: ICMP echo request"
        return {
            'timestamp': float(line.split()[0]),
            'protocol': 'ICMP',
            'src': '10.0.1.10',
            'dst': '10.0.1.20',
            'type': 'echo_request'
        }
```

**Method 2: eBPF (Advanced)**
```c
// eBPF program to capture packets
SEC("xdp")
int packet_capture(struct xdp_md *ctx) {
    // Extract packet metadata
    struct packet_event evt = {
        .timestamp = bpf_ktime_get_ns(),
        .src_ip = ...,
        .dst_ip = ...,
        .protocol = ...
    };
    
    // Send to userspace via perf buffer
    bpf_perf_event_output(ctx, &events, BPF_F_CURRENT_CPU, &evt, sizeof(evt));
    
    return XDP_PASS;  // NEVER DROP PACKETS
}
```

### 4.2 Packet Event Stream

**Packet events are READ-ONLY observations**:

```python
@dataclass
class PacketEvent:
    timestamp: float      # Kernel timestamp (nanoseconds)
    src_ip: str
    dst_ip: str
    src_mac: str
    dst_mac: str
    protocol: str         # ICMP, TCP, UDP, ARP
    packet_type: str      # echo_request, syn, ack, etc.
    ttl: int
    size: int
    interface: str        # Which interface captured this
    namespace: str        # Which namespace
```

**Event Types**:
- `icmp_echo_request`
- `icmp_echo_reply`
- `tcp_syn`
- `tcp_syn_ack`
- `tcp_ack`
- `arp_request`
- `arp_reply`
- `dns_query`
- `dns_response`

---

## 5. VISUALIZATION ENGINE

### 5.1 Observation-Based Animation

**CRITICAL RULE**: Visualization NEVER affects network behavior.

```javascript
class PacketAnimationEngine {
    constructor() {
        this.packetEvents = [];  // Kernel packet events
        this.animations = [];     // Visual animations
        this.animationClock = 0;  // Separate from real time
    }
    
    onPacketEvent(event) {
        // Convert kernel event to visual animation
        const animation = {
            id: event.id,
            startTime: event.timestamp,
            srcNode: this.findNode(event.src_ip),
            dstNode: this.findNode(event.dst_ip),
            protocol: event.protocol,
            type: event.packet_type,
            
            // Visual properties (NOT network properties)
            color: this.getProtocolColor(event.protocol),
            duration: this.calculateVisualDuration(event),
            path: this.calculateVisualPath(event.src_ip, event.dst_ip)
        };
        
        this.animations.push(animation);
    }
    
    calculateVisualDuration(event) {
        // Use ACTUAL latency from kernel timestamps
        // If reply exists, use (reply.timestamp - request.timestamp)
        // Otherwise, estimate from link latency
        return event.actual_rtt || this.estimateFromTopology(event);
    }
    
    render(currentTime) {
        // Render based on kernel timestamps, NOT simulation time
        for (const anim of this.animations) {
            const elapsed = currentTime - anim.startTime;
            const progress = elapsed / anim.duration;
            
            if (progress >= 0 && progress <= 1) {
                this.drawPacket(anim, progress);
            }
        }
    }
}
```

### 5.2 Time Synchronization

**Two clocks**:
1. **Kernel Time**: Real packet timestamps from kernel
2. **Animation Time**: Visual playback time (can be slowed/sped up)

```javascript
class TimeSynchronizer {
    constructor() {
        this.kernelTimeOffset = 0;
        this.playbackSpeed = 1.0;  // 1x, 2x, 0.5x, etc.
    }
    
    kernelToAnimationTime(kernelTimestamp) {
        // Convert kernel nanoseconds to animation milliseconds
        const kernelMs = kernelTimestamp / 1e6;
        const relativeTime = kernelMs - this.kernelTimeOffset;
        return relativeTime * this.playbackSpeed;
    }
}
```

### 5.3 Visual Mapping

**Network Properties → Visual Properties**:

| Network Property | Visual Representation |
|-----------------|----------------------|
| Latency | Animation duration |
| Packet Loss | Packet disappears mid-flight |
| TTL | Hop count visualization |
| Congestion | Queue buildup at router |
| Jitter | Variance in packet spacing |
| Bandwidth | Packet size/frequency |
| Protocol | Color (ICMP=blue, TCP=green, UDP=orange) |

---

## 6. FAILURE INJECTION

### 6.1 Kernel-Level Failures

**All failures implemented via kernel mechanisms**:

```bash
# Interface down
ip netns exec host1 ip link set eth0 down

# Packet loss (30%)
ip netns exec host1 tc qdisc add dev eth0 root netem loss 30%

# Latency increase
ip netns exec host1 tc qdisc change dev eth0 root netem delay 100ms

# Bandwidth limit
ip netns exec host1 tc qdisc add dev eth0 root tbf rate 1mbit burst 32kbit latency 400ms

# Block ICMP (using iptables)
ip netns exec host1 iptables -A OUTPUT -p icmp -j DROP

# Silent router (drop all forwarding)
ip netns exec router1 iptables -A FORWARD -j DROP
```

**NO application-level packet dropping**. Kernel handles all failures.

### 6.2 Failure API

```python
class FailureEngine:
    def enable_packet_loss(self, namespace: str, interface: str, percent: float):
        """Enable packet loss via tc netem"""
        subprocess.run([
            'ip', 'netns', 'exec', namespace,
            'tc', 'qdisc', 'add', 'dev', interface,
            'root', 'netem', 'loss', f'{percent}%'
        ])
    
    def block_icmp(self, namespace: str):
        """Block ICMP via iptables"""
        subprocess.run([
            'ip', 'netns', 'exec', namespace,
            'iptables', '-A', 'OUTPUT', '-p', 'icmp', '-j', 'DROP'
        ])
    
    def interface_down(self, namespace: str, interface: str):
        """Bring interface down"""
        subprocess.run([
            'ip', 'netns', 'exec', namespace,
            'ip', 'link', 'set', interface, 'down'
        ])
```

---

## 7. IMPLEMENTATION PHASES

### Phase 1: WSL2 Setup & Validation ✓
- Install WSL2 with Ubuntu
- Verify kernel capabilities (namespaces, veth, tc)
- Test basic namespace creation

### Phase 2: Network Core (Week 1)
- Implement namespace manager
- Create veth pair manager
- Build bridge/switch implementation
- Implement routing configuration

### Phase 3: PTY Terminal (Week 1)
- Build PTY manager
- Implement WebSocket streaming
- Handle ANSI escape codes
- Test with ping, traceroute, tcpdump

### Phase 4: Packet Observer (Week 2)
- Implement tcpdump-based capture
- Parse packet events
- Stream to frontend via WebSocket
- Test packet event accuracy

### Phase 5: Visualization (Week 2)
- Build observation-based animator
- Implement time synchronization
- Create protocol-specific visualizations
- Test with real packet captures

### Phase 6: Failure Injection (Week 3)
- Implement tc netem controls
- Add iptables rules
- Create failure API
- Test failure scenarios

### Phase 7: Integration & Testing (Week 3)
- End-to-end testing
- Performance optimization
- Documentation
- User acceptance testing

---

## 8. TECHNOLOGY STACK

### Backend
- **Language**: Python 3.10+
- **Framework**: FastAPI
- **PTY**: `pty` module (stdlib)
- **Network**: `subprocess` + `ip` command
- **Packet Capture**: `tcpdump` or `python-bcc` (eBPF)
- **WebSocket**: `websockets` library

### Frontend
- **Terminal**: xterm.js (real terminal emulator)
- **Visualization**: Canvas API + requestAnimationFrame
- **Topology**: Vis.js network graph
- **WebSocket**: Native WebSocket API

### Linux Requirements
- **Kernel**: 5.4+ (WSL2 provides 5.10+)
- **Capabilities**: CAP_NET_ADMIN, CAP_SYS_ADMIN
- **Tools**: `iproute2`, `tcpdump`, `iptables`, `dnsmasq`

---

## 9. VALIDATION CRITERIA

### 9.1 Terminal Authenticity
```bash
# Test: ping output must be IDENTICAL to real Linux
# Expected: Real RTT values, real TTL, real packet loss
ping -c 4 10.0.1.20

# Test: traceroute must show real hops
traceroute 10.0.1.30

# Test: tcpdump must show real packets
tcpdump -i eth0 -c 10
```

### 9.2 Network Behavior
- Packets MUST traverse actual kernel stack
- Routing MUST be done by kernel routing tables
- ARP MUST be handled by kernel ARP cache
- DNS MUST use real resolver (dnsmasq)

### 9.3 Visualization Accuracy
- Packet animations MUST match tcpdump timestamps
- No packet animation without corresponding kernel packet
- Latency visualization MUST reflect actual RTT
- Packet loss MUST be visible when kernel drops packets

---

## 10. SECURITY CONSIDERATIONS

### 10.1 Namespace Isolation
- Each namespace is isolated (cannot access other namespaces)
- No root access required in namespaces
- Iptables rules prevent cross-namespace attacks

### 10.2 Command Execution
- Commands run in isolated namespaces
- No access to host filesystem
- Resource limits via cgroups

### 10.3 WebSocket Security
- Authentication required
- Rate limiting on commands
- Input sanitization (prevent shell injection)

---

## 11. PERFORMANCE TARGETS

- **Packet Processing**: < 1ms latency from kernel to frontend
- **Terminal Responsiveness**: < 50ms for command echo
- **Visualization**: 60 FPS smooth animation
- **Scalability**: Support 50+ namespaces simultaneously
- **Memory**: < 100MB per namespace

---

## 12. TERMINOLOGY

**This system is**:
- ✅ Kernel-Level Network Emulator
- ✅ Real-Time Network Testbed
- ✅ Linux Network Namespace Visualizer

**This system is NOT**:
- ❌ Network Simulator
- ❌ Mock Network
- ❌ AI-Driven Network

---

**Version**: 1.0  
**Author**: Network Emulator Team  
**Date**: 2026-01-05  
**Status**: Architecture Complete, Implementation Pending
