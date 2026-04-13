# VM-ERA Environment Setup Script for Windows
# ============================================
# Creates a virtual environment with GPU-specific dependencies for TensorFlow 2.10.1

param(
    [string]$VenvName = "venv_era",
    [switch]$SkipGPU
)

$PROJECT_ROOT = (Get-Item $PSScriptRoot).Parent.Parent.FullName
$VENV_PATH = Join-Path $PROJECT_ROOT $VenvName

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "VM-ERA Environment Setup" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Check Python version
Write-Host "[1/5] Checking Python version..." -ForegroundColor Yellow
$pythonVersion = python --version 2>&1
Write-Host "  Found: $pythonVersion"

# TensorFlow 2.10.1 requires Python 3.7-3.10
$versionMatch = $pythonVersion -match 'Python (\d+)\.(\d+)'
if ($versionMatch) {
    $major = [int]$matches[1]
    $minor = [int]$matches[2]

    if ($major -eq 3 -and $minor -ge 7 -and $minor -le 10) {
        Write-Host "  Python version is compatible with TensorFlow 2.10.1" -ForegroundColor Green
    } else {
        Write-Host "  WARNING: Python 3.7-3.10 recommended for TensorFlow 2.10.1" -ForegroundColor Red
        Write-Host "  Consider creating a virtual environment with compatible Python version"
    }
}

# Step 2: Create virtual environment
Write-Host ""
Write-Host "[2/5] Creating virtual environment at $VENV_PATH..." -ForegroundColor Yellow
if (Test-Path $VENV_PATH) {
    Write-Host "  Virtual environment already exists, skipping..." -ForegroundColor Yellow
} else {
    python -m venv $VENV_PATH
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  Virtual environment created successfully" -ForegroundColor Green
    } else {
        Write-Host "  ERROR: Failed to create virtual environment" -ForegroundColor Red
        exit 1
    }
}

# Step 3: Activate virtual environment
Write-Host ""
Write-Host "[3/5] Activating virtual environment..." -ForegroundColor Yellow
$ActivateScript = Join-Path $VENV_PATH "Scripts\Activate.ps1"
& $ActivateScript

if ($LASTEXITCODE -eq 0) {
    Write-Host "  Virtual environment activated" -ForegroundColor Green
} else {
    Write-Host "  ERROR: Failed to activate virtual environment" -ForegroundColor Red
    exit 1
}

# Step 4: Upgrade pip
Write-Host ""
Write-Host "[4/5] Upgrading pip..." -ForegroundColor Yellow
pip install --upgrade pip
Write-Host "  pip upgraded successfully" -ForegroundColor Green

# Step 5: Install dependencies
Write-Host ""
Write-Host "[5/5] Installing VM-ERA dependencies..." -ForegroundColor Yellow

# Install core requirements
Write-Host "  Installing core requirements..." -ForegroundColor Cyan
pip install -r (Join-Path $PROJECT_ROOT "requirements.txt")

if ($SkipGPU) {
    Write-Host "  Skipping GPU-specific TensorFlow installation" -ForegroundColor Yellow
} else {
    # Install TensorFlow 2.10.1 (last version with native Windows GPU support)
    Write-Host "  Installing TensorFlow 2.10.1 with GPU support..." -ForegroundColor Cyan
    pip install tensorflow==2.10.1

    # Install compatible protobuf version
    Write-Host "  Installing compatible protobuf version..." -ForegroundColor Cyan
    pip install "protobuf<3.20"
}

# Install VM-ERA specific packages
Write-Host "  Installing androguard for APK analysis..." -ForegroundColor Cyan
pip install androguard>=3.4.0a1

Write-Host "  Installing Pillow for image processing..." -ForegroundColor Cyan
pip install Pillow>=9.0.0

Write-Host "  Installing joblib for RF models..." -ForegroundColor Cyan
pip install joblib>=1.2.0

Write-Host "  Dependencies installed successfully" -ForegroundColor Green

# Verify installation
Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "Verifying Installation" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

Write-Host ""
Write-Host "Running GPU verification..." -ForegroundColor Yellow
python (Join-Path $PSScriptRoot "verify_gpu.py")

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "Setup Complete!" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "To activate the environment, run:" -ForegroundColor Yellow
Write-Host "  & `"$VENV_PATH\Scripts\Activate.ps1`"" -ForegroundColor White
Write-Host ""
Write-Host "To start the backend server:" -ForegroundColor Yellow
Write-Host "  python Chatbot_Interface/backend/app.py" -ForegroundColor White
Write-Host ""
Write-Host "To run tests:" -ForegroundColor Yellow
Write-Host "  pytest Chatbot_Interface/backend/test_apk_processor.py -v" -ForegroundColor White
Write-Host ""
