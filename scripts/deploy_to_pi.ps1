<#
.SYNOPSIS
    Deploy assistive-vision project from a Windows laptop to a Raspberry Pi over SSH/SCP.
.DESCRIPTION
    Works directly in Windows PowerShell without requiring WSL or Git Bash.
.EXAMPLE
    .\scripts\deploy_to_pi.ps1 -PiUser pi -PiHost 172.17.4.80 -ModelPath .\yolov8n.onnx
#>
param(
    [string]$PiUser = "pi",
    [Parameter(Mandatory=$false)][string]$PiHost,
    [string]$ModelPath = ".\yolov8n.onnx"
)

$ErrorActionPreference = "Stop"

Write-Host "`n=================================================================" -ForegroundColor Cyan
Write-Host "  🚀 ASSISTIVE VISION — POWERSHELL PI DEPLOYMENT" -ForegroundColor Cyan
Write-Host "=================================================================`n" -ForegroundColor Cyan

# 1. Prompt for PiHost if not provided
if (-not $PiHost) {
    $PiHost = Read-Host "Enter Raspberry Pi IP address (e.g. 172.17.4.80)"
    if (-not $PiHost) {
        Write-Error "Raspberry Pi IP address is required."
        exit 1
    }
}

# 2. Check for ssh and scp
foreach ($cmd in @("ssh", "scp")) {
    if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) {
        Write-Error "Command '$cmd' is not in PATH. Ensure OpenSSH Client is installed in Windows Optional Features."
        exit 1
    }
}

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDir = (Resolve-Path "$ScriptDir\..").Path

# Resolve model path
if (-not (Test-Path $ModelPath)) {
    if (Test-Path "$ProjectDir\$ModelPath") {
        $ModelPath = "$ProjectDir\$ModelPath"
    } else {
        Write-Error "Model file not found at: $ModelPath"
        exit 1
    }
}

$RemoteTarget = "${PiUser}@${PiHost}"
$RemoteDir = "/home/${PiUser}/assistive-vision"

Write-Host "📡 Target:   ${RemoteTarget}:${RemoteDir}" -ForegroundColor Yellow
Write-Host "📦 Model:    $ModelPath`n" -ForegroundColor Yellow

# Test SSH
Write-Host "🔍 Testing SSH connection..." -ForegroundColor Gray
$null = ssh $RemoteTarget "echo 'OK'"
if ($LASTEXITCODE -ne 0) {
    Write-Error "Could not connect to $RemoteTarget over SSH. Verify Pi is powered on and IP is correct."
    exit 1
}

# Create remote folder
ssh $RemoteTarget "mkdir -p '$RemoteDir'"

# Copy project files
Write-Host "📦 Copying files to Raspberry Pi..." -ForegroundColor Cyan
scp -r "$ProjectDir\src" "$ProjectDir\tools" "$ProjectDir\scripts" "$ProjectDir\pyproject.toml" "$ProjectDir\README.md" "$ProjectDir\QUICKSTART.md" "$ModelPath" "${RemoteTarget}:${RemoteDir}/"

if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to copy files via scp."
    exit 1
}

# Setup remote environment
Write-Host "⚙️ Configuring environment on Raspberry Pi..." -ForegroundColor Cyan
$setupCmd = "cd '$RemoteDir' && chmod +x scripts/*.sh tools/*.py 2>/dev/null; if [ ! -d .venv ]; then python3 -m venv --system-site-packages .venv 2>/dev/null || python3 -m venv .venv; fi; source .venv/bin/activate; pip install -e '.[pi]' -q 2>/dev/null || pip install -e '.[pi]'"
ssh $RemoteTarget $setupCmd

Write-Host "`n=================================================================" -ForegroundColor Green
Write-Host "  🎉 DEPLOYMENT COMPLETE!" -ForegroundColor Green
Write-Host "=================================================================" -ForegroundColor Green
Write-Host "Next steps:"
Write-Host "1. On this laptop, start the camera server:"
Write-Host "   python tools/laptop_camera_server.py --camera 0 --port 8765`n"
Write-Host "2. SSH into your Pi:"
Write-Host "   ssh $RemoteTarget`n"
Write-Host "3. Start the autonomous assistant on the Pi:"
Write-Host "   cd assistive-vision"
Write-Host "   source .venv/bin/activate"
Write-Host "   python tools/run_pi.py --auto`n"
