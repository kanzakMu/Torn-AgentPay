param(
    [int]$MerchantPort = 8002
)

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$demoScript = Join-Path $scriptRoot "examples\run_local_demo.ps1"

& $demoScript -MerchantPort $MerchantPort
