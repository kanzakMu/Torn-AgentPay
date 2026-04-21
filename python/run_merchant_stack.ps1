param(
    [int]$MerchantPort = 8000
)

$repoRoot = Split-Path -Parent $PSScriptRoot
$venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
$merchantEnv = Join-Path $repoRoot "python\.env.merchant.local"

if (-not (Test-Path $venvPython)) {
    throw "Missing .venv. Run python/bootstrap_merchant.ps1 first."
}

if (-not (Test-Path $merchantEnv)) {
    throw "Missing python/.env.merchant.local. Run python/bootstrap_merchant.ps1 first."
}

$env:PYTHONPATH = "$repoRoot\python"
$env:AIMIPAY_MERCHANT_PORT = "$MerchantPort"

Push-Location $repoRoot
try {
    & $venvPython -m uvicorn python.examples.merchant_app:app --host 127.0.0.1 --port $MerchantPort
}
finally {
    Pop-Location
}
