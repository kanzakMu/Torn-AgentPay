param(
    [int]$Port = 8000
)

$merchantRunner = Join-Path $PSScriptRoot "run_merchant_stack.ps1"
& $merchantRunner -MerchantPort $Port
exit $LASTEXITCODE
