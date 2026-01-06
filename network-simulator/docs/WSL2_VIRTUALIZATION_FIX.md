# WSL2 Installation Fix - Virtualization Setup

## Problem

You're seeing this error:
```
WSL2 is not supported with your current machine configuration.
Please enable the "Virtual Machine Platform" optional component and ensure virtualization is enabled in the BIOS.
```

This means virtualization is either:
1. Not enabled in BIOS/UEFI
2. Not enabled in Windows features

## Solution - Step by Step

### Step 1: Enable Windows Features

**In PowerShell as Administrator**, run these commands:

```powershell
# Enable Virtual Machine Platform
dism.exe /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart

# Enable WSL
dism.exe /online /enable-feature /featurename:Microsoft-Windows-Subsystem-Linux /all /norestart

# Enable Hyper-V (if available)
dism.exe /online /enable-feature /featurename:Microsoft-Hyper-V-All /all /norestart
```

**Note**: The Hyper-V command might fail on Windows Home edition - that's okay, continue anyway.

### Step 2: Reboot

```powershell
Restart-Computer
```

**Important**: You MUST reboot after this step.

### Step 3: Enable Virtualization in BIOS/UEFI

After reboot, you need to enable virtualization in BIOS/UEFI.

#### How to Enter BIOS/UEFI:

**Method 1: From Windows**
1. Press `Windows + I` to open Settings
2. Go to **Update & Security** → **Recovery**
3. Under "Advanced startup", click **Restart now**
4. Choose **Troubleshoot** → **Advanced options** → **UEFI Firmware Settings**
5. Click **Restart**

**Method 2: During Boot**
- Restart your computer
- Press one of these keys repeatedly during boot:
  - **Dell**: F2 or F12
  - **HP**: F10 or Esc
  - **Lenovo**: F1 or F2
  - **ASUS**: F2 or Del
  - **Acer**: F2 or Del
  - **MSI**: Del

#### In BIOS/UEFI:

Look for one of these settings (location varies by manufacturer):

**Intel Processors**:
- Look for: **Intel Virtualization Technology** or **Intel VT-x** or **VMX**
- Set to: **Enabled**

**AMD Processors**:
- Look for: **AMD-V** or **SVM Mode**
- Set to: **Enabled**

**Common locations**:
- Advanced → CPU Configuration
- Advanced → System Configuration
- Security → Virtualization
- Configuration → Intel Virtual Technology

**Save and Exit** (usually F10)

### Step 4: Verify Virtualization is Enabled

After reboot, open **Task Manager** (Ctrl+Shift+Esc):
1. Go to **Performance** tab
2. Click **CPU**
3. Look for **Virtualization**: Should say **Enabled**

If it still says "Disabled", you need to go back to BIOS and enable it.

### Step 5: Install WSL2 Again

Once virtualization is enabled, run in PowerShell as Administrator:

```powershell
# Install WSL2
wsl --install

# Or if that fails, try:
wsl --install --no-distribution

# Then install Ubuntu separately:
wsl --install -d Ubuntu-22.04
```

### Step 6: Verify Installation

```powershell
wsl --status
wsl --list --verbose
```

You should see:
```
  NAME            STATE           VERSION
* Ubuntu-22.04    Running         2
```

---

## Alternative: If Virtualization Cannot Be Enabled

If your system doesn't support virtualization or you can't enable it in BIOS:

### Option 1: Use Docker Desktop (Requires Virtualization)
- Docker Desktop also requires virtualization
- Not a viable alternative if virtualization is unavailable

### Option 2: Use a Linux VM
- Install VirtualBox (doesn't require hardware virtualization)
- Create an Ubuntu 22.04 VM
- Run the emulator inside the VM
- **Downside**: Performance will be slower

### Option 3: Deploy to Cloud
- Use a cloud Linux instance (AWS EC2, Google Cloud, Azure)
- SSH into the instance
- Run the emulator there
- **Downside**: Requires cloud account and may incur costs

### Option 4: Use WSL1 (NOT RECOMMENDED)
- WSL1 doesn't support network namespaces
- The kernel-level emulator **will not work** on WSL1
- This is not a viable option for this project

---

## Troubleshooting

### "Hyper-V is not available on this system"

**Solution**: This is normal on Windows Home edition. Continue anyway - you don't need Hyper-V, just Virtual Machine Platform.

### "Virtualization is disabled in firmware"

**Solution**: You must enable it in BIOS/UEFI. Follow Step 3 above.

### "This operation requires elevation"

**Solution**: Run PowerShell as Administrator:
1. Right-click Start menu
2. Select "Windows PowerShell (Admin)" or "Terminal (Admin)"

### Virtualization option not in BIOS

**Possible reasons**:
1. **Older CPU**: Your CPU might not support virtualization
   - Check: Search online for "[Your CPU model] virtualization support"
2. **Locked BIOS**: Some OEM systems lock BIOS settings
   - Check: Contact manufacturer for BIOS update
3. **Already enabled**: It might already be on
   - Check: Task Manager → Performance → CPU → Virtualization

### How to check if your CPU supports virtualization

**Windows**:
```powershell
# Check CPU capabilities
systeminfo | findstr /C:"Hyper-V Requirements"
```

Look for:
- "VM Monitor Mode Extensions: Yes"
- "Virtualization Enabled In Firmware: Yes"

**Online**:
- Intel CPUs: Search "[CPU model] Intel VT-x"
- AMD CPUs: Search "[CPU model] AMD-V"

---

## Quick Fix Checklist

- [ ] Run `dism.exe` commands in PowerShell as Admin
- [ ] Reboot computer
- [ ] Enter BIOS/UEFI
- [ ] Enable Intel VT-x or AMD-V
- [ ] Save and exit BIOS
- [ ] Verify in Task Manager (Virtualization: Enabled)
- [ ] Run `wsl --install` again
- [ ] Verify with `wsl --list --verbose`

---

## Next Steps

### If Virtualization Works:

1. ✅ Complete WSL2 installation
2. ✅ Follow `TESTING_INSTRUCTIONS.md`
3. ✅ Run tests
4. ✅ Proceed with integration

### If Virtualization Doesn't Work:

**Contact me with**:
1. Your CPU model (e.g., "Intel Core i5-8250U")
2. Your Windows edition (Home/Pro/Enterprise)
3. Screenshot of Task Manager → Performance → CPU
4. What you see in BIOS (if you can access it)

I'll help you find an alternative solution.

---

## Summary

**The issue**: Virtualization is not enabled  
**The fix**: Enable in Windows features + Enable in BIOS  
**Time required**: 10-15 minutes  
**Difficulty**: Medium (requires BIOS access)

**Don't worry** - this is a common issue and easily fixable! 🚀

---

**Need help?** Let me know:
- What CPU you have
- What you see in Task Manager
- If you can access BIOS
- Any error messages you encounter
