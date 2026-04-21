param(
    [int]$MerchantPort = 8000
)

$repoRoot = Split-Path -Parent $PSScriptRoot
$venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
$envLocal = Join-Path $repoRoot "python\.env.local"

if (-not (Test-Path $venvPython)) {
    throw "Missing .venv. Run python/bootstrap_local.ps1 first."
}

if (-not (Test-Path $envLocal)) {
    throw "Missing python/.env.local. Run python/bootstrap_local.ps1 first."
}

$env:PYTHONPATH = "$repoRoot\python"
$env:AIMIPAY_MERCHANT_PORT = "$MerchantPort"
$env:NO_PROXY = "127.0.0.1,localhost"
$env:no_proxy = "127.0.0.1,localhost"

Push-Location $repoRoot
try {
    & $venvPython -m python.examples.local_end_to_end_demo
}
finally {
    Pop-Location
}
