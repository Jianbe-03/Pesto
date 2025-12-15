# Get the directory where this script is located
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

# Define installation directory
$InstallDir = "$HOME\.pesto"

Write-Host "Installing Pesto globally..."

# Create installation directory
if (!(Test-Path $InstallDir)) {
    New-Item -ItemType Directory -Path $InstallDir | Out-Null
}

# Copy files from the script's directory
Write-Host "Copying files from $ScriptDir..."
Copy-Item "$ScriptDir\Pesto.py" "$InstallDir\"
Copy-Item "$ScriptDir\Settings.yaml" "$InstallDir\"

# Create a virtual environment to avoid PEP 668 errors
Write-Host "Creating virtual environment..."
& python -m venv "$InstallDir\venv"

# Install dependencies into the virtual environment
Write-Host "Installing dependencies..."
& "$InstallDir\venv\Scripts\pip" install requests pyyaml watchdog

# Create wrapper PowerShell script using the venv python
$WrapperContent = @"
& "$InstallDir\venv\Scripts\python" "$InstallDir\Pesto.py" `$args
"@

$WrapperContent | Out-File -FilePath "$InstallDir\pesto.ps1" -Encoding UTF8

# Create a batch file wrapper for easier execution from Command Prompt
$BatchContent = @"
@echo off
"$InstallDir\venv\Scripts\python" "$InstallDir\Pesto.py" %*
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