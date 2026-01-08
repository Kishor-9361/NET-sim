# WSL2 Setup Script for Windows
# Run this in PowerShell as Administrator

Write-Host "=========================================="
Write-Host "WSL2 Setup - Enabling Required Features"
Write-Host "=========================================="
Write-Host ""

# Check if running as Administrator
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Write-Host "ERROR: This script must be run as Administrator" -ForegroundColor Red
    Write-Host ""
    Write-Host "To run as Administrator:" -ForegroundColor Yellow
    Write-Host "1. Right-click Start menu" -ForegroundColor Yellow
    Write-Host "2. Select 'Windows PowerShell (Admin)' or 'Terminal (Admin)'" -ForegroundColor Yellow
    Write-Host "3. Run this script again" -ForegroundColor Yellow
    Write-Host ""
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host "✓ Running as Administrator" -ForegroundColor Green
Write-Host ""

# Check Windows version
$osInfo = Get-WmiObject -Class Win32_OperatingSystem
$osVersion = [System.Environment]::OSVersion.Version

Write-Host "System Information:" -ForegroundColor Cyan
Write-Host "  OS: $($osInfo.Caption)"
Write-Host "  Version: $($osVersion.Major).$($osVersion.Minor).$($osVersion.Build)"
Write-Host ""

if ($osVersion.Build -lt 19041) {
    Write-Host "WARNING: Your Windows build ($($osVersion.Build)) is older than required (19041)" -ForegroundColor Yellow
    Write-Host "WSL2 requires Windows 10 build 19041 or later" -ForegroundColor Yellow
    Write-Host "Please update Windows before continuing" -ForegroundColor Yellow
    Write-Host ""
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host "✓ Windows version is compatible" -ForegroundColor Green
Write-Host ""

# Check CPU virtualization support
Write-Host "Checking CPU virtualization support..." -ForegroundColor Cyan

$hyperVRequirements = systeminfo | Select-String "Hyper-V Requirements"
Write-Host $hyperVRequirements
Write-Host ""

# Enable Virtual Machine Platform
Write-Host "Step 1: Enabling Virtual Machine Platform..." -ForegroundColor Cyan
try {
    dism.exe /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart
    Write-Host "✓ Virtual Machine Platform enabled" -ForegroundColor Green
} catch {
    Write-Host "✗ Failed to enable Virtual Machine Platform" -ForegroundColor Red
    Write-Host "Error: $_" -ForegroundColor Red
}
Write-Host ""

# Enable WSL
Write-Host "Step 2: Enabling Windows Subsystem for Linux..." -ForegroundColor Cyan
try {
    dism.exe /online /enable-feature /featurename:Microsoft-Windows-Subsystem-Linux /all /norestart
    Write-Host "✓ WSL enabled" -ForegroundColor Green
} catch {
    Write-Host "✗ Failed to enable WSL" -ForegroundColor Red
    Write-Host "Error: $_" -ForegroundColor Red
}
Write-Host ""

# Try to enable Hyper-V (will fail on Home edition, that's okay)
Write-Host "Step 3: Attempting to enable Hyper-V (may fail on Home edition)..." -ForegroundColor Cyan
try {
    dism.exe /online /enable-feature /featurename:Microsoft-Hyper-V-All /all /norestart
    Write-Host "✓ Hyper-V enabled" -ForegroundColor Green
} catch {
    Write-Host "⚠ Hyper-V not available (this is normal on Windows Home)" -ForegroundColor Yellow
}
Write-Host ""

Write-Host "=========================================="
Write-Host "Features Enabled Successfully!"
Write-Host "=========================================="
Write-Host ""

Write-Host "IMPORTANT NEXT STEPS:" -ForegroundColor Yellow
Write-Host ""
Write-Host "1. REBOOT YOUR COMPUTER" -ForegroundColor Yellow
Write-Host "   This is required for changes to take effect" -ForegroundColor Yellow
Write-Host ""
Write-Host "2. ENABLE VIRTUALIZATION IN BIOS" -ForegroundColor Yellow
Write-Host "   After reboot, check Task Manager:" -ForegroundColor Yellow
Write-Host "   - Press Ctrl+Shift+Esc" -ForegroundColor Yellow
Write-Host "   - Go to Performance tab → CPU" -ForegroundColor Yellow
Write-Host "   - Look for 'Virtualization: Enabled'" -ForegroundColor Yellow
Write-Host ""
Write-Host "   If it says 'Disabled':" -ForegroundColor Yellow
Write-Host "   - Restart computer" -ForegroundColor Yellow
Write-Host "   - Enter BIOS (press F2, F10, Del, or Esc during boot)" -ForegroundColor Yellow
Write-Host "   - Find 'Intel VT-x' or 'AMD-V' setting" -ForegroundColor Yellow
Write-Host "   - Set to 'Enabled'" -ForegroundColor Yellow
Write-Host "   - Save and exit (usually F10)" -ForegroundColor Yellow
Write-Host ""
Write-Host "3. INSTALL WSL2" -ForegroundColor Yellow
Write-Host "   After reboot and enabling virtualization:" -ForegroundColor Yellow
Write-Host "   - Open PowerShell as Administrator" -ForegroundColor Yellow
Write-Host "   - Run: wsl --install" -ForegroundColor Yellow
Write-Host ""
Write-Host "4. VERIFY INSTALLATION" -ForegroundColor Yellow
Write-Host "   After WSL2 installs:" -ForegroundColor Yellow
Write-Host "   - Run: wsl --list --verbose" -ForegroundColor Yellow
Write-Host "   - Verify VERSION shows '2' (not '1')" -ForegroundColor Yellow
Write-Host ""

Write-Host "For detailed instructions, see:" -ForegroundColor Cyan
Write-Host "  docs\WSL2_VIRTUALIZATION_FIX.md" -ForegroundColor Cyan
Write-Host ""

$rebootNow = Read-Host "Would you like to reboot now? (Y/N)"

if ($rebootNow -eq "Y" -or $rebootNow -eq "y") {
    Write-Host ""
    Write-Host "Rebooting in 10 seconds..." -ForegroundColor Yellow
    Write-Host "Press Ctrl+C to cancel" -ForegroundColor Yellow
    Start-Sleep -Seconds 10
    Restart-Computer
} else {
    Write-Host ""
    Write-Host "Please reboot manually when ready." -ForegroundColor Yellow
    Write-Host ""
    Read-Host "Press Enter to exit"
}
