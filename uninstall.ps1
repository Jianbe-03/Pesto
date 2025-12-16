# Define installation directory
$InstallDir = "$HOME\.pesto"

Write-Host "Uninstalling Pesto..."

# 1. Remove wrappers + executable (best-effort)
$WrapperPS1 = "$InstallDir\pesto.ps1"
$WrapperBat = "$InstallDir\pesto.bat"
$ExePath = "$InstallDir\Pesto.exe"

if (Test-Path $WrapperPS1) {
    Write-Host "Removing PowerShell wrapper $WrapperPS1..."
    Remove-Item $WrapperPS1
}

if (Test-Path $WrapperBat) {
    Write-Host "Removing batch wrapper $WrapperBat..."
    Remove-Item $WrapperBat
}

if (Test-Path $ExePath) {
    Write-Host "Removing executable $ExePath..."
    Remove-Item $ExePath
}

# 2. Remove from PATH
$CurrentPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($CurrentPath -like "*$InstallDir*") {
    $NewPath = $CurrentPath -replace [regex]::Escape("$InstallDir;"), "" -replace [regex]::Escape(";$InstallDir"), ""
    [Environment]::SetEnvironmentVariable("Path", $NewPath, "User")
    Write-Host "Removed $InstallDir from user PATH."
} else {
    Write-Host "$InstallDir not found in user PATH."
}

Write-Host "Uninstallation complete!"
Write-Host "Note: If you installed the Roblox Plugin manually, please remove 'PestoPlugin.server.lua' from your Roblox Studio Plugins folder."
Write-Host "You may need to restart your terminal or PowerShell for PATH changes to take effect."

# 3. Remove installation directory
if (Test-Path $InstallDir) {
    Write-Host "Removing installation directory $InstallDir..."
    Remove-Item -Recurse -Force $InstallDir
} else {
    Write-Host "Installation directory $InstallDir not found."
}