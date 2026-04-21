$ErrorActionPreference = "Stop"

if (-not $env:AIMIPAY_REPOSITORY_ROOT) {
  $env:AIMIPAY_REPOSITORY_ROOT = "e:/trade/aimicropay-tron"
}

if (-not $env:AIMIPAY_FULL_HOST) {
  $env:AIMIPAY_FULL_HOST = "http://127.0.0.1:9090"
}

if (-not $env:AIMIPAY_MERCHANT_PORT) {
  $env:AIMIPAY_MERCHANT_PORT = "8000"
}

if (-not $env:AIMIPAY_SETTLEMENT_BACKEND) {
  $env:AIMIPAY_SETTLEMENT_BACKEND = "local_smoke"
}

$env:PYTHONPATH = "$env:AIMIPAY_REPOSITORY_ROOT;$env:AIMIPAY_REPOSITORY_ROOT/python"
$env:NO_PROXY = "127.0.0.1,localhost"
$env:no_proxy = "127.0.0.1,localhost"
Push-Location $env:AIMIPAY_REPOSITORY_ROOT
try {
  python -m python.examples.local_end_to_end_demo
}
finally {
  Pop-Location
}
