param(
    [switch]$SkipNpmInstall,
    [switch]$SkipPythonInstall,
    [string]$PythonExecutable = "",
    [string]$NetworkProfile = "local"
)

$merchantBootstrap = Join-Path $PSScriptRoot "bootstrap_merchant.ps1"
& $merchantBootstrap `
    -SkipNpmInstall:$SkipNpmInstall `
    -SkipPythonInstall:$SkipPythonInstall `
    -PythonExecutable $PythonExecutable `
    -NetworkProfile $NetworkProfile
exit $LASTEXITCODE
