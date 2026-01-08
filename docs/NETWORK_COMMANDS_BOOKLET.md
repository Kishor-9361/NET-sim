# 📘 Network Simulator Command Booklet

Welcome to the Network Simulator Command Booklet. This guide provides a comprehensive reference for the network tools available in your terminal for debugging, analysis, and configuration.

---

## 🏗️ Interface Management

### **ip** (Modern Suite)
The `ip` command is the standard tool for all network configuration in modern Linux.

| Action | Command | Example |
| :--- | :--- | :--- |
| **Show Interfaces** | `ip link show` | `ip link show` |
| **Show IP Addresses** | `ip addr show` | `ip addr show eth0` |
| **Enable Interface** | `ip link set <dev> up` | `ip link set eth0 up` |
| **Disable Interface** | `ip link set <dev> down` | `ip link set eth0 down` |
| **Add IP Address** | `ip addr add <ip>/<mask> dev <dev>` | `ip addr add 192.168.1.5/24 dev eth0` |
| **Delete IP Address** | `ip addr del <ip>/<mask> dev <dev>` | `ip addr del 192.168.1.5/24 dev eth0` |

### **ifconfig** (Legacy)
Classic tool for interface configuration.
*   **Show all**: `ifconfig`
*   **Show properties**: `ifconfig eth0`
*   **Set IP**: `ifconfig eth0 192.168.1.5 netmask 255.255.255.0`

### **ifup / ifdown**
Controls interfaces based on `/etc/network/interfaces` definitions.
*   **Bring Up**: `ifup eth0`
*   **Bring Down**: `ifdown eth0`
*   **Query Config**: `ifquery --list`

---

## 📡 Connectivity & Routing

### **ping**
Checks reachability of a host via ICMP.
*   **Standard Ping**: `ping 8.8.8.8`
*   **Count Limit**: `ping -c 4 google.com` (Stops after 4 packets)
*   **Fast Ping**: `ping -i 0.2 10.0.0.1` (Sends packets every 0.2s)
*   **Specific Interface**: `ping -I eth0 10.0.0.1`

### **traceroute**
Shows the path packets take to reach a destination.
*   **Trace Path**: `traceroute google.com`
*   **No DNS Resolution**: `traceroute -n google.com` (Faster)
*   **Use ICMP instead of UDP**: `traceroute -I google.com`

### **netstat**
Network statistics and routing tables.
*   **Show Routing Table**: `netstat -rn`
*   **Show Listening Ports**: `netstat -tuln`
*   **Show Interface Stats**: `netstat -i`

### **Route Management** (via ip)
*   **Show Routes**: `ip route show`
*   **Add Default Gateway**: `ip route add default via <gateway_ip>`
*   **Add Static Route**: `ip route add 10.20.0.0/24 via 192.168.1.1`

---

## 🔍 Network Analysis & Security

### **tcpdump**
Powerful packet analyzer.
*   **Capture All**: `tcpdump`
*   **Capture Interface**: `tcpdump -i eth0`
*   **Capture ICMP only**: `tcpdump -i eth0 icmp`
*   **Capture Port 80**: `tcpdump -i eth0 port 80`
*   **Write to File**: `tcpdump -w capture.pcap` (View later with Wireshark)
*   **Read from File**: `tcpdump -r capture.pcap`

### **nmap**
Network exploration and security scanner.
*   **Ping Scan** (Host Discovery): `nmap -sn 192.168.1.0/24`
*   **Port Scan (Fast)**: `nmap -F 192.168.1.1`
*   **Specific Port**: `nmap -p 22,80 192.168.1.1`
*   **OS Detection**: `nmap -O 192.168.1.1` (Requires root)

### **nc** (Netcat)
The "Swiss Army knife" for TCP/UDP connections.
*   **Chat Mode (Server)**: `nc -l -p 5000`
*   **Chat Mode (Client)**: `nc <server_ip> 5000`
*   **Port Scan**: `nc -z -v 192.168.1.1 20-80`
*   **File Transfer**:
    *   Receiver: `nc -l -p 1234 > received_file`
    *   Sender: `nc <receiver_ip> 1234 < original_file`

---

## 🌐 DNS Tools

### **nslookup**
Interactive DNS query tool.
*   **Simple Query**: `nslookup google.com`
*   **Specific Server**: `nslookup google.com 1.1.1.1`
*   **Reverse Lookup**: `nslookup 8.8.8.8`

### **dig**
Detailed DNS lookup utility.
*   **Standard Query**: `dig google.com`
*   **Short Answer**: `dig +short google.com`
*   **Trace Path**: `dig +trace google.com`
*   **Specific Record Type**: `dig google.com MX`

---

## ⚙️ Hardware & System

### **ethtool**
Query/control network driver and hardware settings.
*   **Show Info**: `ethtool eth0` (Speed, Duplex, Link detected)
*   **Show Stats**: `ethtool -S eth0`

### **System Info**
*   **Hostname**: `hostname`
*   **Kernel Version**: `uname -r`
*   **Process List**: `ps aux`
*   **Socket Statistics**: `ss -tuln` (Modern alternative to netstat)

---

## 💡 Quick Tips

1.  **Sudo**: Most network commands require root privileges. The terminals in this simulator run as root by default for convenience.
2.  **Man Pages**: Use `man <command>` for detailed manual pages (e.g., `man ping`).
3.  **Help**: Use `<command> --help` for quick argument lists.
4.  **History**: Use `history` to see commands you've typed, and `!number` to re-run one.
