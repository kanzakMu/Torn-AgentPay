param(
    [int]$Port = 8011
)

$repoRoot = Split-Path -Parent $PSScriptRoot
$venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $venvPython)) {
    throw "Missing .venv. Run python/bootstrap_local.ps1 first."
}

$env:PYTHONPATH = "$repoRoot\python"
$env:AIMIPAY_REPOSITORY_ROOT = $repoRoot
$env:AIMIPAY_BUYER_ONBOARDING_PORT = "$Port"

& $venvPython -m uvicorn examples.buyer_onboarding_app:create_app --factory --host 127.0.0.1 --port $Port
