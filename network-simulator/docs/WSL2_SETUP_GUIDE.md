# WSL2 Setup Guide for Kernel-Level Network Emulator

## Overview

This guide walks you through setting up WSL2 (Windows Subsystem for Linux 2) to run the kernel-level network emulator.

---

## Prerequisites

- **Windows 10** version 2004+ (Build 19041+) or **Windows 11**
- **Administrator access** to Windows
- **Virtualization enabled** in BIOS
- **At least 8GB RAM** (16GB recommended)
- **10GB free disk space**

---

## Step 1: Enable WSL2

### Option A: Automated Installation (Recommended)

Open **PowerShell as Administrator** and run:

```powershell
wsl --install
```

This will:
1. Enable WSL feature
2. Enable Virtual Machine Platform
3. Download and install Ubuntu (default distribution)
4. Set WSL2 as default version

**Reboot required after this step.**

### Option B: Manual Installation

If automated installation fails, follow these steps:

#### 1.1 Enable WSL Feature
```powershell
dism.exe /online /enable-feature /featurename:Microsoft-Windows-Subsystem-Linux /all /norestart
```

#### 1.2 Enable Virtual Machine Platform
```powershell
dism.exe /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart
```

#### 1.3 Reboot Windows
```powershell
Restart-Computer
```

#### 1.4 Set WSL2 as Default
```powershell
wsl --set-default-version 2
```

#### 1.5 Install Ubuntu
```powershell
wsl --install -d Ubuntu-22.04
```

---

## Step 2: Verify WSL2 Installation

After reboot, open PowerShell and check:

```powershell
# Check WSL version
wsl --status

# List installed distributions
wsl --list --verbose
```

**Expected output**:
```
  NAME            STATE           VERSION
* Ubuntu-22.04    Running         2
```

The `VERSION` column **must show 2** (not 1).

---

## Step 3: Initial Ubuntu Setup

### 3.1 Launch Ubuntu

```powershell
wsl
```

You'll be prompted to create a username and password. Choose:
- **Username**: `netemu` (or your preference)
- **Password**: (choose a secure password)

### 3.2 Update Ubuntu

```bash
sudo apt update
sudo apt upgrade -y
```

---

## Step 4: Install Required Tools

### 4.1 Install Network Tools

```bash
sudo apt install -y \
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
    wget
```

### 4.2 Install Python 3.10+

```bash
sudo apt install -y \
    python3 \
    python3-pip \
    python3-venv
```

### 4.3 Install Development Tools

```bash
sudo apt install -y \
    build-essential \
    git \
    vim
```

---

## Step 5: Verify Kernel Capabilities

### 5.1 Check Kernel Version

```bash
uname -r
```

**Expected**: `5.10.x` or higher

### 5.2 Verify Network Namespace Support

```bash
# Check if namespaces are supported
ls /proc/self/ns/

# Expected output should include:
# net, mnt, pid, uts, ipc, user
```

### 5.3 Test Namespace Creation

```bash
# Create test namespace (requires sudo)
sudo ip netns add test-ns

# List namespaces
sudo ip netns list

# Expected: test-ns

# Delete test namespace
sudo ip netns delete test-ns
```

### 5.4 Test veth Pair Creation

```bash
# Create veth pair
sudo ip link add veth0 type veth peer name veth1

# Verify
ip link show type veth

# Cleanup
sudo ip link delete veth0
```

### 5.5 Verify tc (Traffic Control)

```bash
# Check tc is available
which tc

# Expected: /usr/sbin/tc
```

---

## Step 6: Configure Permissions

### 6.1 Add User to sudoers (No Password for Network Commands)

Create sudoers file:

```bash
sudo visudo -f /etc/sudoers.d/netemu
```

Add these lines:
```
# Allow network commands without password
%sudo ALL=(ALL) NOPASSWD: /usr/sbin/ip
%sudo ALL=(ALL) NOPASSWD: /usr/sbin/tc
%sudo ALL=(ALL) NOPASSWD: /usr/sbin/iptables
%sudo ALL=(ALL) NOPASSWD: /usr/sbin/tcpdump
%sudo ALL=(ALL) NOPASSWD: /usr/sbin/brctl
```

Save and exit (Ctrl+X, Y, Enter).

### 6.2 Verify Passwordless Sudo

```bash
# Should NOT prompt for password
sudo ip netns list
```

---

## Step 7: Install Python Dependencies

### 7.1 Create Virtual Environment

```bash
cd ~
mkdir network-emulator
cd network-emulator
python3 -m venv venv
source venv/bin/activate
```

### 7.2 Install Python Packages

```bash
pip install --upgrade pip
pip install \
    fastapi \
    uvicorn[standard] \
    websockets \
    pydantic \
    python-multipart \
    aiofiles
```

---

## Step 8: Test Complete Setup

### 8.1 Run Comprehensive Test

Create test script:

```bash
cat > test_setup.sh << 'EOF'
#!/bin/bash

echo "=== WSL2 Network Emulator Setup Test ==="
echo ""

# Test 1: Kernel version
echo "1. Kernel Version:"
uname -r
echo ""

# Test 2: Network namespace
echo "2. Network Namespace Test:"
sudo ip netns add test-ns
sudo ip netns list | grep test-ns && echo "✓ Namespace creation: PASS" || echo "✗ Namespace creation: FAIL"
sudo ip netns delete test-ns
echo ""

# Test 3: veth pair
echo "3. veth Pair Test:"
sudo ip link add veth0 type veth peer name veth1
ip link show type veth | grep veth0 && echo "✓ veth creation: PASS" || echo "✗ veth creation: FAIL"
sudo ip link delete veth0
echo ""

# Test 4: Bridge
echo "4. Bridge Test:"
sudo ip link add br0 type bridge
ip link show br0 && echo "✓ Bridge creation: PASS" || echo "✗ Bridge creation: FAIL"
sudo ip link delete br0
echo ""

# Test 5: tc (Traffic Control)
echo "5. Traffic Control Test:"
which tc > /dev/null && echo "✓ tc available: PASS" || echo "✗ tc available: FAIL"
echo ""

# Test 6: iptables
echo "6. iptables Test:"
sudo iptables -L > /dev/null && echo "✓ iptables working: PASS" || echo "✗ iptables working: FAIL"
echo ""

# Test 7: tcpdump
echo "7. tcpdump Test:"
which tcpdump > /dev/null && echo "✓ tcpdump available: PASS" || echo "✗ tcpdump available: FAIL"
echo ""

# Test 8: Python
echo "8. Python Test:"
python3 --version
python3 -c "import fastapi; print('✓ FastAPI imported: PASS')" 2>/dev/null || echo "✗ FastAPI import: FAIL"
echo ""

echo "=== Setup Test Complete ==="
EOF

chmod +x test_setup.sh
./test_setup.sh
```

**All tests should show PASS**.

---

## Step 9: Access WSL2 from Windows

### 9.1 File System Access

From Windows Explorer, navigate to:
```
\\wsl$\Ubuntu-22.04\home\<username>\network-emulator
```

### 9.2 Network Access

WSL2 has its own IP address. To find it:

```bash
# In WSL2
ip addr show eth0 | grep inet
```

From Windows, you can access services at this IP (e.g., `http://172.x.x.x:8000`).

### 9.3 Port Forwarding (Optional)

To access WSL2 services via `localhost` from Windows:

```powershell
# In PowerShell (as Administrator)
netsh interface portproxy add v4tov4 listenport=8000 listenaddress=0.0.0.0 connectport=8000 connectaddress=<WSL2_IP>
```

---

## Step 10: Performance Optimization

### 10.1 Increase WSL2 Memory Limit

Create `.wslconfig` in Windows user directory:

```powershell
# In PowerShell
notepad $env:USERPROFILE\.wslconfig
```

Add:
```ini
[wsl2]
memory=8GB
processors=4
swap=2GB
```

Restart WSL2:
```powershell
wsl --shutdown
wsl
```

### 10.2 Enable systemd (Optional)

Edit `/etc/wsl.conf` in WSL2:

```bash
sudo nano /etc/wsl.conf
```

Add:
```ini
[boot]
systemd=true
```

Restart WSL2.

---

## Troubleshooting

### Issue: "WSL 2 requires an update to its kernel component"

**Solution**:
1. Download WSL2 kernel update: https://aka.ms/wsl2kernel
2. Install the update
3. Restart WSL2

### Issue: "The virtual machine could not be started"

**Solution**:
1. Enable virtualization in BIOS
2. Ensure Hyper-V is enabled:
   ```powershell
   Enable-WindowsOptionalFeature -Online -FeatureName Microsoft-Hyper-V -All
   ```

### Issue: "Operation not permitted" when creating namespaces

**Solution**:
- Ensure you're using `sudo`
- Verify WSL2 (not WSL1): `wsl --list --verbose`

### Issue: Slow network performance

**Solution**:
1. Update WSL2 kernel: `wsl --update`
2. Check Windows Firewall settings
3. Disable antivirus real-time scanning for WSL2 directories

---

## Next Steps

Once setup is complete:

1. ✅ Clone the network emulator repository
2. ✅ Run the installation script
3. ✅ Start the backend server
4. ✅ Access the web interface
5. ✅ Create your first network topology

See `INSTALLATION.md` for detailed instructions.

---

## Additional Resources

- **WSL2 Documentation**: https://docs.microsoft.com/en-us/windows/wsl/
- **Linux Network Namespaces**: https://man7.org/linux/man-pages/man8/ip-netns.8.html
- **Traffic Control (tc)**: https://man7.org/linux/man-pages/man8/tc.8.html
- **iptables**: https://linux.die.net/man/8/iptables

---

**Version**: 1.0  
**Last Updated**: 2026-01-05  
**Tested On**: Windows 11, WSL2 Ubuntu 22.04
