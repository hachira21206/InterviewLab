$ErrorActionPreference = "Stop"

# Define paths using $PSScriptRoot
$ProjectRoot = $PSScriptRoot
$BackendDir = Join-Path $ProjectRoot "backend"
$VenvDir = Join-Path $BackendDir ".venv"
$CacheDir = Join-Path $ProjectRoot ".cache\pip"

# Create .cache/pip if not exists
if (-not (Test-Path $CacheDir)) {
    New-Item -ItemType Directory -Path $CacheDir | Out-Null
}

# Create virtual environment if not exists
if (-not (Test-Path $VenvDir)) {
    Write-Host "Creating virtual environment at $VenvDir"
    python -m venv $VenvDir
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to create virtual environment."
        exit $LASTEXITCODE
    }
} else {
    Write-Host "Virtual environment already exists at $VenvDir. Using it."
}

# Configure pip cache inside venv
$PipIniPath = Join-Path $VenvDir "pip.ini"
$CacheDirEscaped = $CacheDir -replace '\\', '\\'
"[global]`ncache-dir = $CacheDirEscaped" | Out-File -Encoding ascii $PipIniPath
Write-Host "Configured pip cache at $PipIniPath"

# Install dependencies
Write-Host "Installing dependencies..."
$PythonExe = Join-Path $VenvDir "Scripts\python.exe"
& $PythonExe -m pip install -r (Join-Path $BackendDir "requirements-dev.txt")
if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to install dependencies."
    exit $LASTEXITCODE
}

Write-Host "Bootstrap completed successfully."
