# EmbyD Windows Development Environment Setup
# Run this script to set up the development environment

param(
    [string]$PythonVersion = "3.10"
)

Write-Host "=== EmbyD Development Environment Setup ===" -ForegroundColor Cyan
Write-Host ""

# Check Python installation
try {
    $pythonPath = (Get-Command python).Source
    $pythonVersion = & python --version
    Write-Host "✓ Python found: $pythonVersion" -ForegroundColor Green
    Write-Host "  Path: $pythonPath"
} catch {
    Write-Host "✗ Python not found. Please install Python $PythonVersion+ from python.org" -ForegroundColor Red
    exit 1
}

# Create virtual environment
if (-not (Test-Path ".venv")) {
    Write-Host "Creating virtual environment..." -ForegroundColor Yellow
    & python -m venv .venv
    Write-Host "✓ Virtual environment created" -ForegroundColor Green
} else {
    Write-Host "✓ Virtual environment already exists" -ForegroundColor Green
}

# Activate virtual environment
& .\.venv\Scripts\Activate.ps1

# Upgrade pip
Write-Host "Upgrading pip..." -ForegroundColor Yellow
& python -m pip install --upgrade pip

# Install dependencies
Write-Host "Installing dependencies..." -ForegroundColor Yellow
& pip install -r requirements.txt

# Install dev dependencies
Write-Host "Installing dev dependencies..." -ForegroundColor Yellow
& pip install -e ".[dev]"

Write-Host ""
Write-Host "=== Setup Complete ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "To activate the virtual environment in the future, run:"
Write-Host "  .\.venv\Scripts\Activate.ps1"
Write-Host ""
Write-Host "To verify the installation, run:"
Write-Host "  python -m app.cli.main --help"