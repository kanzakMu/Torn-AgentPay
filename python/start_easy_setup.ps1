param(
    [int]$Port = 8010
)

$repoRoot = Split-Path -Parent $PSScriptRoot
$venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $venvPython)) {
    throw "Missing .venv. Run python/bootstrap_buyer.ps1 or python/bootstrap_merchant.ps1 first."
}

$env:PYTHONPATH = "$repoRoot\python"
$env:AIMIPAY_REPOSITORY_ROOT = $repoRoot

& $venvPython -m uvicorn examples.easy_setup_app:create_app --factory --host 127.0.0.1 --port $Port
