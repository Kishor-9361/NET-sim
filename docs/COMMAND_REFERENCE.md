# Network Simulator Command Reference

This document provides a comprehensive summary of the network commands available in the simulator environment.

## 1. Connectivity & Routing

### **ping**
Send ICMP ECHO_REQUEST to network hosts to check connectivity.
*   `ping <host>`: Ping a host (continuous).
*   `ping -c 4 <host>`: Send 4 packets and stop.
*   `ping -i 0.2 <host>`: Send packets every 0.2 seconds (fast).

### **traceroute**
Print the route packets trace to network host.
*   `traceroute <host>`: Trace path to host.
*   `traceroute -n <host>`: Do not resolve IP addresses to hostnames (faster).

### **ip**
Show / manipulate routing, networking, and interfaces.
*   `ip addr`: Show IP addresses.
*   `ip route`: Show routing table.
*   `ip link`: Show network interfaces.
*   `ip neigh`: Show ARP cache.
*   `ip link set eth0 up/down`: Enable/Disable an interface.
*   `ip addr add 192.168.1.5/24 dev eth0`: Add IP to interface.

### **ifconfig** (Legacy)
Interface configuration.
*   `ifconfig`: Show all interfaces.
*   `ifconfig eth0`: Show specifics for eth0.

### **ifup / ifdown**
High-level tool to configure interfaces based on `/etc/network/interfaces`.
*Note: In this simulator, interfaces are usually configured dynamically by the backend, so manual configuration in `/etc/network/interfaces` may be empty.*
*   `ifup eth0`: Bring interface up (according to config).
*   `ifdown eth0`: Bring interface down.
*   `ifquery --list`: List interfaces configured in `interfaces` file.

## 2. Network Analysis & Debugging

### **tcpdump**
Dump traffic on a network.
*   `tcpdump`: Capture packets on default interface.
*   `tcpdump -i eth0`: Capture on specific interface.
*   `tcpdump -n`: Don't resolve hostnames.
*   `tcpdump icmp`: Capture only ICMP (ping) traffic.
*   `tcpdump port 80`: Capture HTTP traffic.

### **netstat**
Print network connections, routing tables, interface statistics.
*   `netstat -tuln`: Show listening TCP/UDP ports.
*   `netstat -rn`: Show routing table (numeric).
*   `netstat -i`: Show interface statistics.

### **ethtool**
Query or control network driver and hardware settings.
*   `ethtool eth0`: Show speed, duplex, and link status.
*   `ethtool -S eth0`: Show detailed statistics.

### **nmap**
Network exploration tool and security / port scanner.
*   `nmap <host>`: Scan 1000 common ports on host.
*   `nmap -sn <network/24>`: Ping scan (discover hosts), don't scan ports.
*   `nmap -p 80 <host>`: Scan specific port.
*   `nmap -O <host>`: Attempt OS detection (requires root/sudo).

### **nc** (netcat)
Arbitrary TCP and UDP connections and listens.
*   **Client**: `nc <host> <port>` (Connect to a port).
*   **Server**: `nc -l -p <port>` (Listen on a port).
*   **Transfer**:
    *   Receiver: `nc -l -p 1234 > file.out`
    *   Sender: `nc <receiver_ip> 1234 < file.in`

## 3. DNS Tools

### **nslookup**
Query Internet name servers interactively.
*   `nslookup google.com`: Query default DNS.
*   `nslookup google.com <dns_server_ip>`: Query specific DNS server.

### **dig**
DNS lookup utility.
*   `dig google.com`: Standard query.
*   `dig @<dns_server_ip> google.com`: Query specific server.
*   `dig +short google.com`: Show only the IP.

## 4. Helper Commands

### **clear**
Clear the terminal screen.

### **history**
Show command history.

## 5. Tips
*   **Redirect output**: `command > file.txt` (Save output to file).
*   **Pipe**: `command1 | command2` (Use output of 1 as input of 2).
*   **Background**: `command &` (Run in background).
