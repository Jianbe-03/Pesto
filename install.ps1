# Get the directory where this script is located
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

$ErrorActionPreference = 'Stop'

# Define installation directory
$InstallDir = "$HOME\.pesto"

Write-Host "Installing Pesto globally..."

# Create installation directory
if (!(Test-Path $InstallDir)) {
    New-Item -ItemType Directory -Path $InstallDir | Out-Null
}

# Copy files from the script's directory
Write-Host "Copying files from $ScriptDir..."
$ExeSource = "$ScriptDir\dist\Pesto-win.exe"
if (!(Test-Path $ExeSource)) {
    # Backward-compatible fallback
    $ExeSource = "$ScriptDir\dist\Pesto.exe"
}

if (!(Test-Path $ExeSource)) {
    throw "Pesto executable not found in $ScriptDir\dist (expected Pesto-win.exe or legacy Pesto.exe)"
}

$ExeDest = "$InstallDir\Pesto-win.exe"
Copy-Item $ExeSource $ExeDest -Force

# Validate size (>1MB) and PE header (MZ)
$Len = (Get-Item $ExeDest).Length
if ($Len -lt 1000000) {
    Remove-Item -Force $ExeDest -ErrorAction SilentlyContinue
    throw "Installed executable is too small ($Len bytes). Expected a real PyInstaller binary (~8-12MB)."
}

$Header = Get-Content -Path $ExeDest -Encoding Byte -TotalCount 2
if ($Header.Count -lt 2 -or $Header[0] -ne 0x4D -or $Header[1] -ne 0x5A) {
    Remove-Item -Force $ExeDest -ErrorAction SilentlyContinue
    throw "Installed file does not look like a Windows executable (missing 'MZ' header)."
}

Copy-Item "$ScriptDir\Settings.yaml" "$InstallDir\"

# Create wrapper PowerShell script for the executable
$WrapperContent = @"
& "$InstallDir\Pesto-win.exe" `$args
"@

$WrapperContent | Out-File -FilePath "$InstallDir\pesto.ps1" -Encoding UTF8

# Create a batch file wrapper for easier execution from Command Prompt
$BatchContent = @"
@echo off
"$InstallDir\Pesto-win.exe" %*
"@

$BatchContent | Out-File -FilePath "$InstallDir\pesto.bat" -Encoding ASCII

# Add to PATH if not already there
$CurrentPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($CurrentPath -notlike "*$InstallDir*") {
    $NewPath = $CurrentPath + ";$InstallDir"
    [Environment]::SetEnvironmentVariable("Path", $NewPath, "User")
    Write-Host "Added $InstallDir to user PATH."
} else {
    Write-Host "$InstallDir is already in your PATH."
}

# Add to current session PATH
if ($env:Path -notlike "*$InstallDir*") {
    $env:Path += ";$InstallDir"
}

Write-Host "Installation complete!"
Write-Host "You can now run 'pesto Server' in any directory to start syncing for that folder."