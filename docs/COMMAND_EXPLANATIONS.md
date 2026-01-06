# How Network Commands Work in the Kernel-Level Emulator

## Overview

In the kernel-level emulator, **ALL commands execute as real Linux binaries** in isolated network namespaces. There is **NO simulation** - every command interacts directly with the Linux kernel.

---

## Team Assignments

### Kishore's Commands
1. `ip` - Network interface and routing configuration
2. `ifconfig` - Legacy interface configuration
3. `ethtool` - Ethernet device settings

### Kumaravel's Commands
1. `nslookup` - DNS lookup utility
2. `tcpdump` - Packet capture and analysis
3. `nmap` - Network port scanner

### Lavanya's Commands
1. `netstat` - Network statistics and connections
2. `nc` (netcat) - Network connections and data transfer
3. `dig` - DNS query tool

### Parkavi's Commands
1. `ping` - ICMP echo request/reply testing
2. `traceroute` - Network path tracing
3. `ifup`, `ifdown`, `ifquery` - Interface management

---

## How Each Command Works

### 🔷 KISHORE - Network Configuration Commands

#### 1. `ip` - IP Route 2 Utility

**What it does**: Manages network interfaces, IP addresses, routing tables, and network namespaces.

**How it works in the emulator**:

```bash
# User runs in terminal
ip addr show

# What happens:
1. Command typed in browser terminal (xterm.js)
2. Sent via WebSocket to backend
3. Backend writes to PTY: os.write(pty_fd, b"ip addr show\n")
4. PTY executes in namespace: sudo ip netns exec host1 /bin/bash
5. Real /sbin/ip binary executes
6. Reads network interfaces from kernel
7. Kernel returns REAL interface data (eth0, lo, etc.)
8. Output sent back through PTY
9. Streamed to browser via WebSocket
10. Displayed in terminal with ANSI colors
```

**Example output** (REAL, not simulated):
```
1: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536 qdisc noqueue state UNKNOWN
    link/loopback 00:00:00:00:00:00 brd 00:00:00:00:00:00
    inet 127.0.0.1/8 scope host lo
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast state UP
    link/ether 02:42:ac:11:00:02 brd ff:ff:ff:ff:ff:ff
    inet 10.0.1.10/24 scope global eth0
```

**Key point**: This data comes from the **Linux kernel**, not Python code!

**Common `ip` commands**:
- `ip addr show` - Show IP addresses
- `ip route show` - Show routing table
- `ip link show` - Show network interfaces
- `ip neigh show` - Show ARP cache

---

#### 2. `ifconfig` - Interface Configuration

**What it does**: Legacy tool for configuring network interfaces (older than `ip`).

**How it works in the emulator**:

```bash
# User runs
ifconfig

# Execution flow:
1. Command sent to PTY in namespace
2. /sbin/ifconfig binary executes
3. Reads interface data from kernel via ioctl() system calls
4. Kernel returns actual interface states
5. Output formatted and returned
6. Displayed in terminal
```

**Example output** (REAL):
```
eth0: flags=4163<UP,BROADCAST,RUNNING,MULTICAST>  mtu 1500
        inet 10.0.1.10  netmask 255.255.255.0  broadcast 10.0.1.255
        ether 02:42:ac:11:00:02  txqueuelen 0  (Ethernet)
        RX packets 156  bytes 12345 (12.0 KiB)
        TX packets 89   bytes 6789 (6.6 KiB)
```

**Key point**: Packet counts, bytes transferred, and errors are **real kernel statistics**.

---

#### 3. `ethtool` - Ethernet Tool

**What it does**: Displays and changes ethernet device settings (speed, duplex, driver info).

**How it works in the emulator**:

```bash
# User runs
ethtool eth0

# Execution flow:
1. /sbin/ethtool executes in namespace
2. Queries kernel driver for interface eth0
3. Kernel returns driver information
4. Shows link speed, duplex mode, driver version
```

**Example output** (REAL):
```
Settings for eth0:
        Supported ports: [ TP ]
        Supported link modes:   10baseT/Half 10baseT/Full
                                100baseT/Half 100baseT/Full
                                1000baseT/Full
        Speed: 1000Mb/s
        Duplex: Full
        Link detected: yes
```

**Key point**: This shows **actual virtual ethernet (veth) device properties** from the kernel.

---

### 🔷 KUMARAVEL - Network Analysis Commands

#### 1. `nslookup` - DNS Lookup

**What it does**: Queries DNS servers to resolve domain names to IP addresses.

**How it works in the emulator**:

```bash
# User runs
nslookup google.com

# Execution flow:
1. /usr/bin/nslookup executes in namespace
2. Reads /etc/resolv.conf for DNS server
3. Sends REAL DNS query packet via kernel
4. Kernel routes packet through network
5. DNS server (if configured) responds
6. Response packet captured by packet observer
7. nslookup displays result
```

**Example output** (REAL):
```
Server:         8.8.8.8
Address:        8.8.8.8#53

Non-authoritative answer:
Name:   google.com
Address: 142.250.185.46
```

**Packet capture shows** (from tcpdump):
```
10:15:23.456789 IP 10.0.1.10.53124 > 8.8.8.8.53: 12345+ A? google.com. (28)
10:15:23.478901 IP 8.8.8.8.53 > 10.0.1.10.53124: 12345 1/0/0 A 142.250.185.46 (44)
```

**Key point**: Real DNS packets sent/received through kernel!

---

#### 2. `tcpdump` - Packet Capture

**What it does**: Captures and analyzes network packets in real-time.

**How it works in the emulator**:

```bash
# User runs
tcpdump -i eth0 -n

# Execution flow:
1. /usr/sbin/tcpdump executes in namespace
2. Opens raw socket to kernel
3. Kernel provides REAL packets from interface
4. tcpdump decodes and displays packets
5. Shows actual packet headers, timestamps, data
```

**Example output** (REAL):
```
10:15:23.456789 IP 10.0.1.10 > 10.0.1.20: ICMP echo request, id 1234, seq 1, length 64
10:15:23.457123 IP 10.0.1.20 > 10.0.1.10: ICMP echo reply, id 1234, seq 1, length 64
10:15:24.458901 IP 10.0.1.10.45678 > 10.0.1.20.80: Flags [S], seq 123456, win 64240
```

**Key point**: These are **actual packets** traversing the kernel network stack!

**Double observation**:
- User's tcpdump shows packets
- Our packet observer also captures same packets
- Both see identical data (proves authenticity)

---

#### 3. `nmap` - Network Port Scanner

**What it does**: Scans network hosts for open ports and services.

**How it works in the emulator**:

```bash
# User runs
nmap 10.0.1.20

# Execution flow:
1. /usr/bin/nmap executes in namespace
2. Sends REAL TCP SYN packets to target
3. Kernel handles TCP/IP stack
4. Target responds (or doesn't)
5. nmap analyzes responses
6. Reports open/closed/filtered ports
```

**Example output** (REAL):
```
Starting Nmap 7.80 ( https://nmap.org )
Nmap scan report for 10.0.1.20
Host is up (0.00023s latency).
Not shown: 998 closed ports
PORT   STATE SERVICE
22/tcp open  ssh
80/tcp open  http

Nmap done: 1 IP address (1 host up) scanned in 0.15 seconds
```

**Packet capture shows** (REAL TCP handshake):
```
10:15:25.123456 IP 10.0.1.10.54321 > 10.0.1.20.22: Flags [S], seq 789012
10:15:25.123789 IP 10.0.1.20.22 > 10.0.1.10.54321: Flags [S.], seq 345678, ack 789013
10:15:25.123890 IP 10.0.1.10.54321 > 10.0.1.20.22: Flags [R], seq 789013
```

**Key point**: Real TCP SYN scan performed by kernel!

---

### 🔷 LAVANYA - Network Statistics Commands

#### 1. `netstat` - Network Statistics

**What it does**: Displays network connections, routing tables, interface statistics.

**How it works in the emulator**:

```bash
# User runs
netstat -tuln

# Execution flow:
1. /bin/netstat executes in namespace
2. Reads /proc/net/tcp, /proc/net/udp from kernel
3. Kernel provides REAL connection data
4. netstat formats and displays
```

**Example output** (REAL):
```
Active Internet connections (only servers)
Proto Recv-Q Send-Q Local Address           Foreign Address         State
tcp        0      0 0.0.0.0:22              0.0.0.0:*               LISTEN
tcp        0      0 127.0.0.1:3306          0.0.0.0:*               LISTEN
udp        0      0 0.0.0.0:53              0.0.0.0:*
```

**Key point**: Shows **actual kernel TCP/UDP connection states**!

---

#### 2. `nc` (netcat) - Network Swiss Army Knife

**What it does**: Creates TCP/UDP connections, transfers data, port listening.

**How it works in the emulator**:

```bash
# User runs (server mode)
nc -l 8080

# Execution flow:
1. /bin/nc executes in namespace
2. Creates REAL socket via kernel
3. Binds to port 8080
4. Kernel listens for connections
5. When client connects, kernel establishes TCP connection
6. Data transferred through kernel
```

**Example usage**:
```bash
# On host1 (server)
nc -l 8080

# On host2 (client)
nc 10.0.1.10 8080
Hello from host2!

# Server receives:
Hello from host2!
```

**Packet capture shows** (REAL TCP data):
```
10:15:30.123456 IP 10.0.1.20.54321 > 10.0.1.10.8080: Flags [P.], seq 1:18, ack 1, length 17
    0x0000:  4500 0045 1234 4000 4006 abcd 0a00 010a  E..E.4@.@.......
    0x0010:  0a00 0114 d431 1f90 0000 0001 0000 0001  .....1..........
    0x0020:  5018 2000 1234 0000 4865 6c6c 6f20 6672  P....4..Hello.fr
    0x0030:  6f6d 2068 6f73 7432 210a                 om.host2!.
```

**Key point**: Real TCP connection with actual data transfer!

---

#### 3. `dig` - DNS Query Tool

**What it does**: Advanced DNS lookup tool (more detailed than nslookup).

**How it works in the emulator**:

```bash
# User runs
dig google.com

# Execution flow:
1. /usr/bin/dig executes in namespace
2. Sends REAL DNS query packet
3. Kernel routes to DNS server
4. DNS server responds
5. dig displays detailed response
```

**Example output** (REAL):
```
; <<>> DiG 9.16.1-Ubuntu <<>> google.com
;; global options: +cmd
;; Got answer:
;; ->>HEADER<<- opcode: QUERY, status: NOERROR, id: 12345
;; flags: qr rd ra; QUERY: 1, ANSWER: 1, AUTHORITY: 0, ADDITIONAL: 1

;; QUESTION SECTION:
;google.com.                    IN      A

;; ANSWER SECTION:
google.com.             300     IN      A       142.250.185.46

;; Query time: 23 msec
;; SERVER: 8.8.8.8#53(8.8.8.8)
;; WHEN: Sun Jan 05 19:15:35 IST 2026
;; MSG SIZE  rcvd: 55
```

**Key point**: Real DNS query with actual response time (23 msec from kernel)!

---

### 🔷 PARKAVI - Connectivity Testing Commands

#### 1. `ping` - ICMP Echo Request/Reply

**What it does**: Tests network connectivity using ICMP echo packets.

**How it works in the emulator**:

```bash
# User runs
ping -c 4 10.0.1.20

# Execution flow:
1. /bin/ping executes in namespace
2. Creates REAL ICMP socket via kernel
3. Kernel generates ICMP echo request packet
4. Packet routed through network stack
5. Crosses veth pair to target namespace
6. Target kernel responds with ICMP echo reply
7. Reply routed back through kernel
8. ping calculates RTT and displays
```

**Example output** (REAL):
```
PING 10.0.1.20 (10.0.1.20) 56(84) bytes of data.
64 bytes from 10.0.1.20: icmp_seq=1 ttl=64 time=0.123 ms
64 bytes from 10.0.1.20: icmp_seq=2 ttl=64 time=0.098 ms
64 bytes from 10.0.1.20: icmp_seq=3 ttl=64 time=0.105 ms
64 bytes from 10.0.1.20: icmp_seq=4 ttl=64 time=0.112 ms

--- 10.0.1.20 ping statistics ---
4 packets transmitted, 4 received, 0% packet loss, time 3067ms
rtt min/avg/max/mdev = 0.098/0.109/0.123/0.009 ms
```

**Packet capture shows** (REAL ICMP):
```
10:15:40.123456 IP 10.0.1.10 > 10.0.1.20: ICMP echo request, id 1234, seq 1, length 64
10:15:40.123579 IP 10.0.1.20 > 10.0.1.10: ICMP echo reply, id 1234, seq 1, length 64
```

**Key points**:
- RTT (0.123 ms) is **REAL** - measured by kernel
- TTL (64) is **REAL** - decremented by kernel at each hop
- Packet loss calculated from **actual** packet delivery
- Timing is **kernel-accurate**, not simulated

**Visualization**:
- Packet observer captures these REAL packets
- Frontend animates based on actual timestamps
- Animation speed matches real RTT

---

#### 2. `traceroute` - Network Path Tracing

**What it does**: Traces the route packets take through the network.

**How it works in the emulator**:

```bash
# User runs
traceroute 10.0.2.20

# Execution flow:
1. /usr/bin/traceroute executes in namespace
2. Sends packets with increasing TTL (1, 2, 3, ...)
3. Kernel sets TTL in IP header
4. First router decrements TTL to 0
5. Router sends ICMP "time exceeded" back
6. traceroute records hop
7. Increases TTL and repeats
8. Eventually reaches destination
```

**Example output** (REAL):
```
traceroute to 10.0.2.20 (10.0.2.20), 30 hops max, 60 byte packets
 1  10.0.1.1 (10.0.1.1)  0.234 ms  0.198 ms  0.187 ms
 2  10.0.2.1 (10.0.2.1)  0.456 ms  0.423 ms  0.412 ms
 3  10.0.2.20 (10.0.2.20)  0.678 ms  0.645 ms  0.634 ms
```

**Packet capture shows** (REAL TTL behavior):
```
# Hop 1 (TTL=1)
10:15:45.123456 IP (ttl 1) 10.0.1.10 > 10.0.2.20: ICMP echo request
10:15:45.123690 IP 10.0.1.1 > 10.0.1.10: ICMP time exceeded in-transit

# Hop 2 (TTL=2)
10:15:45.234567 IP (ttl 2) 10.0.1.10 > 10.0.2.20: ICMP echo request
10:15:45.234890 IP 10.0.2.1 > 10.0.1.10: ICMP time exceeded in-transit

# Hop 3 (TTL=3)
10:15:45.345678 IP (ttl 3) 10.0.1.10 > 10.0.2.20: ICMP echo request
10:15:45.346012 IP 10.0.2.20 > 10.0.1.10: ICMP echo reply
```

**Key points**:
- TTL is **actually decremented** by kernel at each router
- ICMP "time exceeded" messages are **real** kernel responses
- Hop times are **measured** by kernel, not calculated
- Route discovery is **authentic** network behavior

---

#### 3. `ifup`, `ifdown`, `ifquery` - Interface Management

**What they do**: Bring interfaces up/down and query interface configuration.

**How they work in the emulator**:

```bash
# User runs
ifdown eth0

# Execution flow:
1. /sbin/ifdown executes in namespace
2. Calls kernel to disable interface
3. Kernel marks interface as DOWN
4. No packets can be sent/received
5. Routing entries removed
```

**Example**:
```bash
# Check interface status
ip link show eth0
# Output: 2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> ...

# Bring interface down
ifdown eth0

# Check again
ip link show eth0
# Output: 2: eth0: <BROADCAST,MULTICAST> ...  (no UP flag)

# Try to ping (will fail)
ping 10.0.1.20
# Output: connect: Network is unreachable

# Bring interface back up
ifup eth0

# Ping works again
ping 10.0.1.20
# Output: 64 bytes from 10.0.1.20: icmp_seq=1 ttl=64 time=0.123 ms
```

**Key point**: Interface state is **controlled by kernel**, not Python!

---

## Summary: Simulation vs. Kernel Emulation

### ❌ OLD WAY (Simulation)

```python
def ping(target_ip):
    # Python generates fake output
    rtt = random.uniform(10, 20)  # Fake RTT
    return f"64 bytes from {target_ip}: time={rtt} ms"
```

**Problems**:
- RTT is random, not real
- No actual packets sent
- No kernel involvement
- Can't use real tcpdump
- Timing is fake

### ✅ NEW WAY (Kernel Emulation)

```python
def ping(session_id, target_ip):
    # Execute REAL ping command
    pty_manager.execute_command(session_id, f"ping {target_ip}")
    # Output comes from actual /bin/ping binary
    # RTT measured by kernel
    # Real ICMP packets sent
    # tcpdump can capture them
    # Timing is kernel-accurate
```

**Benefits**:
- RTT is real (measured by kernel)
- Actual ICMP packets sent
- Kernel handles everything
- tcpdump shows real packets
- Timing is authentic

---

## How to Verify Authenticity

### Test 1: Packet Capture Matches Command Output

```bash
# Terminal 1: Run tcpdump
tcpdump -i eth0 -n icmp

# Terminal 2: Run ping
ping -c 1 10.0.1.20

# tcpdump shows:
10:15:50.123456 IP 10.0.1.10 > 10.0.1.20: ICMP echo request, id 1234, seq 1
10:15:50.123579 IP 10.0.1.20 > 10.0.1.10: ICMP echo reply, id 1234, seq 1

# ping shows:
64 bytes from 10.0.1.20: icmp_seq=1 ttl=64 time=0.123 ms

# RTT matches: 0.123579 - 0.123456 = 0.000123 sec = 0.123 ms ✓
```

### Test 2: Kernel Statistics Are Real

```bash
# Check interface stats before
ifconfig eth0
# RX packets: 100

# Send 10 pings
ping -c 10 10.0.1.20

# Check interface stats after
ifconfig eth0
# RX packets: 120  (100 + 10 requests + 10 replies) ✓
```

### Test 3: Network Failures Are Authentic

```bash
# Bring interface down
ifdown eth0

# Try to ping
ping 10.0.1.20
# connect: Network is unreachable ✓ (real kernel error)

# Try to use any network command
curl http://10.0.1.20
# curl: (7) Couldn't connect to server ✓ (real failure)
```

---

## Conclusion

**Every command in this emulator is REAL**:
- Real Linux binaries (`/bin/ping`, `/sbin/ip`, etc.)
- Real kernel network stack
- Real packets (captured by tcpdump)
- Real timing (measured by kernel)
- Real errors (generated by kernel)
- Real statistics (from kernel counters)

**Nothing is simulated or faked!**

This is why it's called a **Kernel-Level Network Emulator**, not a simulator.

---

**Questions for each team member?** Ask me anything about how your assigned commands work! 🚀
