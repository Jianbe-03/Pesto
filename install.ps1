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

# Remove any previous install artifacts first
if (Test-Path "$InstallDir\Pesto-win") { Remove-Item -Recurse -Force "$InstallDir\Pesto-win" -ErrorAction SilentlyContinue }
if (Test-Path "$InstallDir\Pesto-win.exe") { Remove-Item -Force "$InstallDir\Pesto-win.exe" -ErrorAction SilentlyContinue }
if (Test-Path "$InstallDir\pesto.ps1") { Remove-Item -Force "$InstallDir\pesto.ps1" -ErrorAction SilentlyContinue }
if (Test-Path "$InstallDir\pesto.bat") { Remove-Item -Force "$InstallDir\pesto.bat" -ErrorAction SilentlyContinue }

# Copy files from the script's directory
Write-Host "Copying files from $ScriptDir..."
$ExeSource = "$ScriptDir\dist\Pesto-win"

if (Test-Path $ExeSource -PathType Container) {
    # Onedir build: copy the folder
    Copy-Item $ExeSource $InstallDir -Recurse -Force
    $ExeDest = "$InstallDir\Pesto-win\Pesto.exe"

    # Remove the embedded helpers folder (we install the correct helper manually)
    if (Test-Path "$InstallDir\Pesto-win\helpers") {
        Remove-Item -Recurse -Force "$InstallDir\Pesto-win\helpers"
    }

} elseif (Test-Path $ExeSource -PathType Leaf) {
    # Onefile build: copy the file
    $ExeDest = "$InstallDir\Pesto-win.exe"
    Copy-Item $ExeSource $ExeDest -Force
} else {
    throw "Pesto build not found at $ExeSource"
}

# Validate size (>1MB) and PE header (MZ)
$Len = (Get-Item $ExeDest).Length
if ($Len -lt 1000000) {
    if (Test-Path "$InstallDir\Pesto-win" -PathType Container) {
        Remove-Item -Recurse -Force "$InstallDir\Pesto-win" -ErrorAction SilentlyContinue
    } else {
        Remove-Item -Force $ExeDest -ErrorAction SilentlyContinue
    }
    throw "Installed executable is too small ($Len bytes). Expected a real PyInstaller binary (~8-12MB)."
}

$Header = Get-Content -Path $ExeDest -Encoding Byte -TotalCount 2
if ($Header.Count -lt 2 -or $Header[0] -ne 0x4D -or $Header[1] -ne 0x5A) {
    if (Test-Path "$InstallDir\Pesto-win" -PathType Container) {
        Remove-Item -Recurse -Force "$InstallDir\Pesto-win" -ErrorAction SilentlyContinue
    } else {
        Remove-Item -Force $ExeDest -ErrorAction SilentlyContinue
    }
    throw "Installed file does not look like a Windows executable (missing 'MZ' header)."
}

if (Test-Path "$InstallDir\Pesto-win" -PathType Container) {
    Copy-Item "$ScriptDir\Settings.yaml" "$InstallDir\Pesto-win\"
} else {
    Copy-Item "$ScriptDir\Settings.yaml" "$InstallDir\"
}

# Copy native helper binary (for high-performance operations)
Write-Host "Installing native helper..."
$HelperSource = "$ScriptDir\pesto-helper-windows-amd64.exe"
if (Test-Path $HelperSource) {
    if (Test-Path "$InstallDir\Pesto-win" -PathType Container) {
        Copy-Item $HelperSource "$InstallDir\Pesto-win\" -Force
    } else {
        Copy-Item $HelperSource "$InstallDir\" -Force
    }
    Write-Host "Installed native helper: pesto-helper-windows-amd64.exe"
} else {
    Write-Host "Warning: Native helper not found at $HelperSource"
    Write-Host "Pesto will use Python fallback (slower for large projects)"
}

# Create wrapper PowerShell script for the executable
$WrapperContent = @"
`$ExePath = "$ExeDest"
`$ExeDir = Split-Path -Parent `$ExePath
Push-Location `$ExeDir
try {
    & `$ExePath `$args
}
finally {
    Pop-Location
}
"@

$WrapperContent | Out-File -FilePath "$InstallDir\pesto.ps1" -Encoding UTF8

# Create a batch file wrapper for easier execution from Command Prompt
$BatchContent = @"
@echo off
cd /d "$(Split-Path -Parent $ExeDest)"
"$ExeDest" %*
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