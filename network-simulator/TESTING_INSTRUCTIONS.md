# 🧪 TESTING INSTRUCTIONS - Quick Start

## What You Need to Do

Follow these steps to test the core components before we proceed with integration.

---

## Step 1: Install WSL2 (5 minutes)

### In PowerShell (as Administrator):

```powershell
wsl --install
```

**Then reboot your computer.**

After reboot, verify:
```powershell
wsl --list --verbose
```

You should see Ubuntu with VERSION = 2

---

## Step 2: Launch WSL2 and Navigate (1 minute)

```powershell
# Launch WSL2
wsl
```

In the WSL2 terminal:
```bash
# Navigate to project
cd /mnt/c/Users/Admin/.gemini/antigravity/scratch/network-simulator

# Verify location
pwd
ls -la
```

---

## Step 3: Run Installation Script (10 minutes)

```bash
# Make executable
chmod +x install_wsl2.sh

# Run installer
./install_wsl2.sh
```

**Watch for green checkmarks (✓)**. All steps should pass.

---

## Step 4: Run Core Component Tests (2 minutes)

```bash
# Make executable
chmod +x test_core_components.sh

# Run tests
./test_core_components.sh
```

### Expected Result:

```
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
```

---

## Step 5: Report Results

### If All Tests Pass ✅

Reply with: **"All tests passed! Ready for integration."**

I will then create the FastAPI server (`src/main.py`) and proceed with backend integration.

### If Any Test Fails ❌

Reply with:
1. Which test failed
2. The error message
3. Screenshot of the output (if possible)

I will help you troubleshoot.

---

## Quick Troubleshooting

### "Permission denied" errors
```bash
# Re-run installation
./install_wsl2.sh
```

### "Command not found" errors
```bash
# Activate virtual environment
source ~/network-emulator/venv/bin/activate
```

### WSL2 not installed
```powershell
# In PowerShell as Administrator
wsl --install
# Then reboot
```

---

## What Happens Next

### After Successful Testing:

1. ✅ Core components verified working
2. 🚧 I create `src/main.py` (FastAPI server)
3. 🚧 I create WebSocket handlers
4. 🚧 I update frontend for xterm.js
5. 🚧 End-to-end testing
6. ✅ Complete system ready!

**Estimated time to completion**: 2-3 hours of development

---

## Files You'll Use

| File | Purpose |
|------|---------|
| `install_wsl2.sh` | Install dependencies and setup environment |
| `test_core_components.sh` | Test all core components |
| `docs/TESTING_GUIDE.md` | Detailed testing guide (if you need help) |

---

## Ready to Start?

1. Open PowerShell as Administrator
2. Run: `wsl --install`
3. Reboot
4. Follow steps above
5. Report results

**Let's test the core components!** 🚀

---

**Note**: The entire testing process should take about 15-20 minutes total.
