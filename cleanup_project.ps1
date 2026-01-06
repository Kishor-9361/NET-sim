# Automated Project Cleanup Script
# Removes old simulation backend files
# KEEPS existing UI for reuse with kernel-level emulator

Write-Host "=========================================="
Write-Host "Project Cleanup - Removing Old Backend"
Write-Host "=========================================="
Write-Host ""

$projectRoot = "C:\Users\Admin\.gemini\antigravity\scratch\network-simulator"
Set-Location $projectRoot

Write-Host "Current directory: $projectRoot" -ForegroundColor Cyan
Write-Host ""

Write-Host "NOTE: Keeping existing UI (static/) for reuse" -ForegroundColor Cyan
Write-Host "      UI will be updated to work with kernel emulator" -ForegroundColor Cyan
Write-Host ""

# Files to remove (BACKEND ONLY)
$filesToRemove = @(
    # Old backend simulation files
    "src\api_server.py",
    "src\command_parser.py",
    "src\simulation_engine.py",
    "src\network_objects.py",
    "src\protocol_engines.py",
    "src\topology_builder.py",
    "src\ip_manager.py",
    
    # Old documentation (not UI-related)
    "docs\ANIMATION_QUICK_START.md",
    "docs\SMOOTH_PING_VISUALIZATION.md",
    "docs\ULTRA_SMOOTH_ANIMATION.md",
    "docs\IMPLEMENTATION_SUMMARY.md",
    "docs\API_REFERENCE.md",
    "docs\FEATURES.md",
    "docs\ALL_BUTTONS_FIXED.md",
    "docs\BUTTON_FIX_SUMMARY.md",
    "docs\BUTTON_STATE_FIX.md",
    "docs\FINAL_BUTTON_FIX.md",
    "docs\UI_INSTANT_FEEDBACK.md",
    "docs\CORRUPTION_OPTIONS.md",
    "docs\CORRUPTION_VERIFICATION.md",
    "docs\FAILURE_CONTROLS.md"
)

# Files to KEEP (UI and core components)
$filesToKeep = @(
    "static\index.html",
    "static\packet-animation.js",
    "src\namespace_manager.py",
    "src\link_manager.py",
    "src\pty_manager.py",
    "src\packet_observer.py",
    "src\topology_manager.py"
)

Write-Host "Files that will be KEPT:" -ForegroundColor Green
foreach ($file in $filesToKeep) {
    if (Test-Path $file) {
        Write-Host "  ✓ $file" -ForegroundColor Green
    }
}
Write-Host ""

$removedCount = 0
$notFoundCount = 0

Write-Host "Removing old simulation backend files..." -ForegroundColor Yellow
Write-Host ""

foreach ($file in $filesToRemove) {
    if (Test-Path $file) {
        try {
            Remove-Item $file -Force
            Write-Host "  ✓ Removed: $file" -ForegroundColor Green
            $removedCount++
        }
        catch {
            Write-Host "  ✗ Failed to remove: $file" -ForegroundColor Red
            Write-Host "    Error: $_" -ForegroundColor Red
        }
    }
    else {
        Write-Host "  ⊘ Not found: $file" -ForegroundColor Gray
        $notFoundCount++
    }
}

Write-Host ""
Write-Host "Removing old tests directory..." -ForegroundColor Yellow

if (Test-Path "tests") {
    try {
        Remove-Item -Path "tests" -Recurse -Force
        Write-Host "  ✓ Removed: tests/ directory" -ForegroundColor Green
        $removedCount++
    }
    catch {
        Write-Host "  ✗ Failed to remove tests directory" -ForegroundColor Red
        Write-Host "    Error: $_" -ForegroundColor Red
    }
}
else {
    Write-Host "  ⊘ Not found: tests/ directory" -ForegroundColor Gray
}

Write-Host ""
Write-Host "=========================================="
Write-Host "Cleanup Complete!"
Write-Host "=========================================="
Write-Host ""
Write-Host "Summary:" -ForegroundColor Cyan
Write-Host "  Files removed: $removedCount" -ForegroundColor Green
Write-Host "  Files not found: $notFoundCount" -ForegroundColor Gray
Write-Host ""

# Show remaining files
Write-Host "Remaining project structure:" -ForegroundColor Cyan
Write-Host ""

Write-Host "Root files:" -ForegroundColor Yellow
Get-ChildItem -Path . -File | ForEach-Object {
    Write-Host "  ✓ $($_.Name)" -ForegroundColor Green
}

Write-Host ""
Write-Host "src/ (Core Components):" -ForegroundColor Yellow
if (Test-Path "src") {
    Get-ChildItem -Path "src" -File | ForEach-Object {
        Write-Host "  ✓ $($_.Name)" -ForegroundColor Green
    }
}

Write-Host ""
Write-Host "docs/ (Documentation):" -ForegroundColor Yellow
if (Test-Path "docs") {
    Get-ChildItem -Path "docs" -File | ForEach-Object {
        Write-Host "  ✓ $($_.Name)" -ForegroundColor Green
    }
}

Write-Host ""
Write-Host "static/ (UI - KEPT for reuse):" -ForegroundColor Yellow
if (Test-Path "static") {
    Get-ChildItem -Path "static" -File | ForEach-Object {
        Write-Host "  ✓ $($_.Name) [WILL BE UPDATED]" -ForegroundColor Green
    }
}

Write-Host ""
Write-Host "=========================================="
Write-Host "Project is now clean and ready!"
Write-Host "=========================================="
Write-Host ""
Write-Host "What's next:" -ForegroundColor Cyan
Write-Host "  1. Enable virtualization in BIOS" -ForegroundColor Yellow
Write-Host "  2. Run: wsl --install" -ForegroundColor Yellow
Write-Host "  3. Test core components" -ForegroundColor Yellow
Write-Host "  4. Create new backend (src/main.py)" -ForegroundColor Yellow
Write-Host "  5. Update UI to work with kernel emulator" -ForegroundColor Yellow
Write-Host ""
Write-Host "UI will be updated to:" -ForegroundColor Cyan
Write-Host "  - Use xterm.js for real terminal" -ForegroundColor Yellow
Write-Host "  - Connect to kernel packet events" -ForegroundColor Yellow
Write-Host "  - Keep existing visual design" -ForegroundColor Yellow
Write-Host ""

Read-Host "Press Enter to exit"
