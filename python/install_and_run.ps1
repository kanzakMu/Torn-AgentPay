param(
    [int]$MerchantPort = 8000,
    [string]$PythonExecutable = ""
)

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

& (Join-Path $scriptRoot "bootstrap_local.ps1") -PythonExecutable $PythonExecutable -NetworkProfile local
if ($LASTEXITCODE -ne 0) {
    throw "Bootstrap failed."
}

& (Join-Path $scriptRoot "run_local_stack.ps1") -MerchantPort $MerchantPort
