# Project Cleanup Guide

## Files to KEEP (Essential for Kernel-Level Emulator)

### Root Directory
- ✅ `README.md` - Main project documentation
- ✅ `TESTING_INSTRUCTIONS.md` - Quick testing guide
- ✅ `TRANSFORMATION_COMPLETE.md` - Transformation summary
- ✅ `install_wsl2.sh` - WSL2 installation script
- ✅ `setup_wsl2_windows.ps1` - Windows setup script
- ✅ `test_core_components.sh` - Core component tests

### src/ - Core Components (KEEP ALL)
- ✅ `namespace_manager.py` - Network namespace management
- ✅ `link_manager.py` - veth pairs and bridges
- ✅ `pty_manager.py` - Real terminal execution
- ✅ `packet_observer.py` - Kernel packet capture
- ✅ `topology_manager.py` - High-level orchestration

### src/ - OLD Simulation Files (REMOVE)
- ❌ `api_server.py` - Old simulated API (will be replaced)
- ❌ `command_parser.py` - Old simulated commands (will be replaced)
- ❌ `simulation_engine.py` - Old simulation logic (not needed)
- ❌ `network_objects.py` - Old simulation objects (not needed)
- ❌ `protocol_engines.py` - Old simulation protocols (not needed)
- ❌ `topology_builder.py` - Old builder (replaced by topology_manager)
- ❌ `ip_manager.py` - Old IP manager (integrated into topology_manager)

### docs/ - Essential Documentation (KEEP)
- ✅ `KERNEL_EMULATOR_ARCHITECTURE.md` - Core architecture
- ✅ `WSL2_SETUP_GUIDE.md` - Installation guide
- ✅ `WSL2_VIRTUALIZATION_FIX.md` - Troubleshooting
- ✅ `TRANSFORMATION_README.md` - Quick start
- ✅ `TRANSFORMATION_SUMMARY.md` - Executive summary
- ✅ `IMPLEMENTATION_CHECKLIST.md` - Progress tracking
- ✅ `TESTING_GUIDE.md` - Testing instructions

### docs/ - Old Simulation Documentation (REMOVE)
- ❌ `ANIMATION_QUICK_START.md` - Old animation docs
- ❌ `SMOOTH_PING_VISUALIZATION.md` - Old visualization
- ❌ `ULTRA_SMOOTH_ANIMATION.md` - Old animation
- ❌ `IMPLEMENTATION_SUMMARY.md` - Old implementation notes
- ❌ `API_REFERENCE.md` - Old API docs (will be replaced)
- ❌ `FEATURES.md` - Old features list

### docs/ - Old UI Fix Documentation (REMOVE)
- ❌ `ALL_BUTTONS_FIXED.md` - Old UI fixes
- ❌ `BUTTON_FIX_SUMMARY.md` - Old button fixes
- ❌ `BUTTON_STATE_FIX.md` - Old button state
- ❌ `FINAL_BUTTON_FIX.md` - Old button fixes
- ❌ `UI_INSTANT_FEEDBACK.md` - Old UI feedback
- ❌ `CORRUPTION_OPTIONS.md` - Old corruption features
- ❌ `CORRUPTION_VERIFICATION.md` - Old verification
- ❌ `FAILURE_CONTROLS.md` - Old failure controls

### static/ - Frontend (KEEP for now, will be updated)
- ✅ `index.html` - Main web interface (needs update)
- ✅ `packet-animation.js` - Animation (needs update)

### tests/ - Old Tests (REMOVE ALL)
All test files in `tests/` directory are for the old simulation and should be removed.

---

## Cleanup Commands

Run these commands to remove old files:

### Windows PowerShell:
```powershell
cd C:\Users\Admin\.gemini\antigravity\scratch\network-simulator

# Remove old source files
Remove-Item src\api_server.py
Remove-Item src\command_parser.py
Remove-Item src\simulation_engine.py
Remove-Item src\network_objects.py
Remove-Item src\protocol_engines.py
Remove-Item src\topology_builder.py
Remove-Item src\ip_manager.py

# Remove old documentation
Remove-Item docs\ANIMATION_QUICK_START.md
Remove-Item docs\SMOOTH_PING_VISUALIZATION.md
Remove-Item docs\ULTRA_SMOOTH_ANIMATION.md
Remove-Item docs\IMPLEMENTATION_SUMMARY.md
Remove-Item docs\API_REFERENCE.md
Remove-Item docs\FEATURES.md
Remove-Item docs\ALL_BUTTONS_FIXED.md
Remove-Item docs\BUTTON_FIX_SUMMARY.md
Remove-Item docs\BUTTON_STATE_FIX.md
Remove-Item docs\FINAL_BUTTON_FIX.md
Remove-Item docs\UI_INSTANT_FEEDBACK.md
Remove-Item docs\CORRUPTION_OPTIONS.md
Remove-Item docs\CORRUPTION_VERIFICATION.md
Remove-Item docs\FAILURE_CONTROLS.md

# Remove old tests directory
Remove-Item -Recurse -Force tests
```

### Linux/WSL:
```bash
cd /mnt/c/Users/Admin/.gemini/antigravity/scratch/network-simulator

# Remove old source files
rm src/api_server.py
rm src/command_parser.py
rm src/simulation_engine.py
rm src/network_objects.py
rm src/protocol_engines.py
rm src/topology_builder.py
rm src/ip_manager.py

# Remove old documentation
rm docs/ANIMATION_QUICK_START.md
rm docs/SMOOTH_PING_VISUALIZATION.md
rm docs/ULTRA_SMOOTH_ANIMATION.md
rm docs/IMPLEMENTATION_SUMMARY.md
rm docs/API_REFERENCE.md
rm docs/FEATURES.md
rm docs/ALL_BUTTONS_FIXED.md
rm docs/BUTTON_FIX_SUMMARY.md
rm docs/BUTTON_STATE_FIX.md
rm docs/FINAL_BUTTON_FIX.md
rm docs/UI_INSTANT_FEEDBACK.md
rm docs/CORRUPTION_OPTIONS.md
rm docs/CORRUPTION_VERIFICATION.md
rm docs/FAILURE_CONTROLS.md

# Remove old tests directory
rm -rf tests
```

---

## Final Project Structure

After cleanup, your project will look like this:

```
network-simulator/
├── README.md                           # Main documentation
├── TESTING_INSTRUCTIONS.md             # Quick testing guide
├── TRANSFORMATION_COMPLETE.md          # Transformation summary
├── install_wsl2.sh                     # WSL2 installer
├── setup_wsl2_windows.ps1              # Windows setup
├── test_core_components.sh             # Component tests
│
├── src/                                # Core components (5 files)
│   ├── namespace_manager.py            # Network namespaces
│   ├── link_manager.py                 # veth pairs & bridges
│   ├── pty_manager.py                  # Real terminals
│   ├── packet_observer.py              # Packet capture
│   └── topology_manager.py             # Orchestration
│
├── docs/                               # Documentation (7 files)
│   ├── KERNEL_EMULATOR_ARCHITECTURE.md # Architecture
│   ├── WSL2_SETUP_GUIDE.md             # Setup guide
│   ├── WSL2_VIRTUALIZATION_FIX.md      # Troubleshooting
│   ├── TRANSFORMATION_README.md        # Quick start
│   ├── TRANSFORMATION_SUMMARY.md       # Summary
│   ├── IMPLEMENTATION_CHECKLIST.md     # Progress
│   └── TESTING_GUIDE.md                # Testing
│
└── static/                             # Frontend (2 files)
    ├── index.html                      # Web interface
    └── packet-animation.js             # Animation
```

**Total**: 
- 6 root files
- 5 core Python files
- 7 documentation files
- 2 frontend files
- **20 files total** (down from 50+)

---

## Why Remove These Files?

### Old Simulation Code
- `api_server.py`, `command_parser.py`, `simulation_engine.py`, etc.
- These implement the OLD simulated network
- They will be REPLACED with new kernel-level code
- Keeping them would be confusing

### Old Documentation
- Documentation about old features (buttons, UI, corruption, etc.)
- These features don't exist in kernel-level emulator
- Will be replaced with new documentation

### Old Tests
- Tests for simulated network
- Don't work with kernel-level emulator
- Will be replaced with new tests

---

## What Happens Next?

After cleanup:

1. ✅ Clean, minimal project structure
2. ✅ Only kernel-level emulator files
3. 🚧 Create new `src/main.py` (FastAPI server)
4. 🚧 Update frontend for kernel integration
5. 🚧 Create new tests for kernel emulator

---

## Ready to Clean Up?

Run the cleanup script below or manually delete the files listed above.
