# Testing Guide - Core Components

## Prerequisites Check

Before testing, ensure you have:
- ✅ Windows 10 (Build 19041+) or Windows 11
- ✅ Administrator access

## Step 1: Install WSL2

### Option A: Quick Install (Recommended)

Open **PowerShell as Administrator** and run:

```powershell
wsl --install
```

**Important**: Reboot your computer after this step.

### Option B: Manual Install (if quick install fails)

1. Enable WSL feature:
```powershell
dism.exe /online /enable-feature /featurename:Microsoft-Windows-Subsystem-Linux /all /norestart
```

2. Enable Virtual Machine Platform:
```powershell
dism.exe /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart
```

3. Reboot your computer

4. Set WSL2 as default:
```powershell
wsl --set-default-version 2
```

5. Install Ubuntu:
```powershell
wsl --install -d Ubuntu-22.04
```

## Step 2: Verify WSL2 Installation

After reboot, open PowerShell and verify:

```powershell
wsl --status
wsl --list --verbose
```

Expected output should show:
```
  NAME            STATE           VERSION
* Ubuntu-22.04    Running         2
```

**VERSION must be 2** (not 1)!

## Step 3: Initial Ubuntu Setup

Launch WSL2 Ubuntu:

```powershell
wsl
```

You'll be prompted to create a username and password. Choose:
- Username: `netemu` (or your preference)
- Password: (choose a secure password)

## Step 4: Navigate to Project Directory

In WSL2 terminal:

```bash
# Navigate to the project (Windows path is mounted at /mnt/c/)
cd /mnt/c/Users/Admin/.gemini/antigravity/scratch/network-simulator

# Verify you're in the right place
ls -la
```

You should see:
- `src/` directory
- `docs/` directory
- `install_wsl2.sh`
- `test_core_components.sh`
- `README.md`

## Step 5: Run Installation Script

```bash
# Make script executable
chmod +x install_wsl2.sh

# Run installation
./install_wsl2.sh
```

This will:
- Update system packages
- Install network tools (iproute2, tcpdump, iptables, etc.)
- Install Python 3.10+
- Configure sudo permissions
- Create Python virtual environment
- Install Python dependencies
- Test kernel capabilities

**Expected duration**: 5-10 minutes

**Watch for**: All steps should show ✓ (green checkmarks)

## Step 6: Run Core Component Tests

After installation completes:

```bash
# Make test script executable
chmod +x test_core_components.sh

# Run tests
./test_core_components.sh
```

### Expected Test Output

```
==========================================
Kernel-Level Network Emulator
Core Components Test Suite
==========================================

✓ Running in WSL2

==========================================
Test 1: Kernel Capabilities
==========================================

Testing network namespace support... ✓ PASS
Testing veth pair support... ✓ PASS
Testing bridge support... ✓ PASS
Testing traffic control (tc)... ✓ PASS
Testing tcpdump... ✓ PASS

==========================================
Test 2: Python Environment
==========================================

Checking Python version... ✓ 3.10.x
✓ Virtual environment active

==========================================
Test 3: Namespace Manager
==========================================

Running namespace_manager.py...
INFO:__main__:Kernel network namespace support verified
INFO:__main__:Creating namespace: host1 (type: host)
INFO:__main__:Namespace created successfully: host1
INFO:__main__:Creating namespace: router1 (type: router)
INFO:__main__:Enabled IP forwarding for router1: router1
INFO:__main__:Namespace created successfully: router1
Created namespace: host1
Created router: router1 (IP forwarding: True)
All namespaces: ['host1', 'router1']
INFO:__main__:Cleaning up all namespaces...
INFO:__main__:Deleting namespace: host1
INFO:__main__:Namespace deleted successfully: host1
INFO:__main__:Deleting namespace: router1
INFO:__main__:Namespace deleted successfully: router1
INFO:__main__:Cleanup complete

✓ Namespace Manager: PASS

==========================================
Test 4: Link Manager
==========================================

Running link_manager.py...
INFO:__main__:Kernel link management support verified
INFO:__main__:Creating bridge: br0
INFO:__main__:Bridge created: br0
Created bridge: br0
INFO:__main__:Cleaning up all links and bridges...
INFO:__main__:Bringing bridge down: br0
INFO:__main__:Bridge deleted: br0
INFO:__main__:Cleanup complete

✓ Link Manager: PASS

==========================================
Test 5: PTY Manager
==========================================

Creating test namespace for PTY test...
Running pty_manager.py...
PTY Manager initialized successfully
✓ PTY Manager: PASS
✓ PTY Manager: PASS

==========================================
Test 6: Packet Observer
==========================================

Running packet_observer.py...
Packet Observer Manager initialized successfully
✓ Packet Observer: PASS
✓ Packet Observer: PASS

==========================================
Test 7: Topology Manager
==========================================

Running topology_manager.py...
INFO:__main__:Kernel network namespace support verified
INFO:__main__:Kernel link management support verified
INFO:__main__:Creating namespace: host1 (type: host)
INFO:__main__:Namespace created successfully: host1
INFO:__main__:Created PTY session for host1
INFO:__main__:Added device: host1 (type: host)
INFO:__main__:Creating namespace: host2 (type: host)
INFO:__main__:Namespace created successfully: host2
INFO:__main__:Created PTY session for host2
INFO:__main__:Added device: host2 (type: host)
INFO:__main__:Creating namespace: router1 (type: router)
INFO:__main__:Enabled IP forwarding for router1: router1
INFO:__main__:Namespace created successfully: router1
INFO:__main__:Created PTY session for router1
INFO:__main__:Added device: router1 (type: router)
INFO:__main__:Created network: net1 (10.0.1.0/24)
INFO:__main__:Creating veth pair: veth-xxxxxxxx <-> veth-xxxxxxxx
INFO:__main__:Attaching veth-xxxxxxxx to namespace host1
INFO:__main__:Attaching veth-xxxxxxxx to namespace router1
INFO:__main__:P2P link created: host1:eth0 <-> router1:eth0
INFO:__main__:Configuring interface eth0 in host1: 10.0.1.1/24
INFO:__main__:Interface configured: eth0 (10.0.1.1/24)
INFO:__main__:Configuring interface eth0 in router1: 10.0.1.2/24
INFO:__main__:Interface configured: eth0 (10.0.1.2/24)
INFO:__main__:Added link: host1:eth0 <-> router1:eth0
Topology: 3 devices, 2 links
INFO:__main__:Cleaning up topology...
INFO:__main__:Cleaning up all PTY sessions...
INFO:__main__:Cleaning up all links and bridges...
INFO:__main__:Cleaning up all namespaces...
INFO:__main__:Topology cleanup complete

✓ Topology Manager: PASS

==========================================
Test 8: Integration Test
==========================================

Creating a simple topology...
Initializing Topology Manager...
INFO:root:Kernel network namespace support verified
INFO:root:Kernel link management support verified

1. Creating two hosts...
INFO:root:Creating namespace: test-host1 (type: host)
INFO:root:Namespace created successfully: test-host1
INFO:root:Created PTY session for test-host1
INFO:root:Added device: test-host1 (type: host)
INFO:root:Creating namespace: test-host2 (type: host)
INFO:root:Namespace created successfully: test-host2
INFO:root:Created PTY session for test-host2
INFO:root:Added device: test-host2 (type: host)
   ✓ Hosts created

2. Creating link between hosts...
INFO:root:Created network: net1 (10.0.1.0/24)
INFO:root:Creating veth pair: veth-xxxxxxxx <-> veth-xxxxxxxx
INFO:root:Attaching veth-xxxxxxxx to namespace test-host1
INFO:root:Attaching veth-xxxxxxxx to namespace test-host2
INFO:root:P2P link created: test-host1:eth0 <-> test-host2:eth0
INFO:root:Configuring interface eth0 in test-host1: 10.0.1.1/24
INFO:root:Interface configured: eth0 (10.0.1.1/24)
INFO:root:Configuring interface eth0 in test-host2: 10.0.1.2/24
INFO:root:Interface configured: eth0 (10.0.1.2/24)
INFO:root:Added link: test-host1:eth0 <-> test-host2:eth0
   ✓ Link created: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx

3. Getting topology state...
   ✓ Devices: 2
   ✓ Links: 1

4. Getting device info...
   ✓ Host1 IP: {'eth0': '10.0.1.1'}

5. Cleanup...
INFO:root:Cleaning up topology...
INFO:root:Cleaning up all PTY sessions...
INFO:root:PTY session closed: pty-test-host1
INFO:root:PTY session closed: pty-test-host2
INFO:root:Cleaning up all links and bridges...
INFO:root:Cleaning up all namespaces...
INFO:root:Deleting namespace: test-host1
INFO:root:Namespace deleted successfully: test-host1
INFO:root:Deleting namespace: test-host2
INFO:root:Namespace deleted successfully: test-host2
INFO:root:Topology cleanup complete
   ✓ Cleanup complete

✓ Integration Test: PASS
✓ Integration Test: PASS

==========================================
All Tests Complete!
==========================================

✓ All core components are working correctly

Summary:
  ✓ Kernel capabilities verified
  ✓ Python environment ready
  ✓ Namespace Manager working
  ✓ Link Manager working
  ✓ PTY Manager working
  ✓ Packet Observer working
  ✓ Topology Manager working
  ✓ Integration test passed

Next steps:
  1. Review test output above
  2. Proceed with backend integration (src/main.py)
  3. See docs/IMPLEMENTATION_CHECKLIST.md for details
```

## Step 7: Manual Verification (Optional)

If you want to manually test kernel capabilities:

```bash
# Test namespace creation
sudo ip netns add manual-test
sudo ip netns list
sudo ip netns delete manual-test

# Test veth pair
sudo ip link add veth0 type veth peer name veth1
ip link show type veth
sudo ip link delete veth0

# Test bridge
sudo ip link add br0 type bridge
ip link show br0
sudo ip link delete br0

# Test traffic control
sudo tc qdisc add dev lo root netem delay 10ms
sudo tc qdisc show dev lo
sudo tc qdisc del dev lo root
```

## Troubleshooting

### Issue: "Permission denied" errors

**Solution**:
```bash
# Check sudoers configuration
sudo cat /etc/sudoers.d/netemu

# If file doesn't exist, re-run installation
./install_wsl2.sh
```

### Issue: "Cannot find device" errors

**Solution**:
```bash
# Verify namespace exists
sudo ip netns list

# Verify interface exists in namespace
sudo ip netns exec <namespace> ip link show
```

### Issue: Python import errors

**Solution**:
```bash
# Ensure virtual environment is activated
source ~/network-emulator/venv/bin/activate

# Verify Python path
python3 -c "import sys; print(sys.path)"
```

### Issue: Tests timeout

**Solution**:
- Increase timeout values in test script
- Check system resources (memory, CPU)
- Verify no other processes are using namespaces

## Success Criteria

All tests should show:
- ✅ Green checkmarks (✓ PASS)
- ✅ No red X marks (✗ FAIL)
- ✅ "All Tests Complete!" message
- ✅ Summary showing all components working

## Next Steps After Successful Testing

Once all tests pass:

1. ✅ **Review test output** - Ensure you understand what each component does
2. 🚧 **Proceed to backend integration** - Create `src/main.py` (FastAPI server)
3. 🚧 **Frontend integration** - Update web interface
4. 🚧 **End-to-end testing** - Test complete system

See `docs/IMPLEMENTATION_CHECKLIST.md` for detailed next steps.

---

## Quick Reference

### Start WSL2
```powershell
wsl
```

### Navigate to Project
```bash
cd /mnt/c/Users/Admin/.gemini/antigravity/scratch/network-simulator
```

### Activate Virtual Environment
```bash
source ~/network-emulator/venv/bin/activate
```

### Run Tests
```bash
./test_core_components.sh
```

### View Logs
```bash
tail -f ~/network-emulator/logs/emulator.log
```

---

**Good luck with testing!** 🚀
