<#
scripts/setup_environment.ps1
=============================
Mini-README: PowerShell automation for preparing a Python virtual environment and
installing Nichifier dependencies on Windows.
#>

$ErrorActionPreference = "Stop"

if (-Not (Test-Path .venv)) {
    py -3 -m venv .venv
}

. .venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .

Write-Host "Environment ready. Activate with '. .venv\\Scripts\\Activate.ps1' then run:" -ForegroundColor Green
Write-Host "python nichifier_platform_server.py --init-db" -ForegroundColor Green
Write-Host "python nichifier_platform_server.py --reload" -ForegroundColor Green
