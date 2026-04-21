param(
    [switch]$SkipNpmInstall,
    [switch]$SkipPythonInstall,
    [string]$PythonExecutable = "",
    [string]$NetworkProfile = "",
    [string]$MerchantUrl = "",
    [string]$MerchantUrls = "",
    [int]$BuyerOnboardingPort = 8011
)

$scriptPath = Join-Path $PSScriptRoot "bootstrap_local.ps1"

$argsList = @(
    "-ExecutionPolicy", "Bypass",
    "-File", $scriptPath,
    "-BuyerOnboardingPort", "$BuyerOnboardingPort"
)

if ($SkipNpmInstall) {
    $argsList += "-SkipNpmInstall"
}
if ($SkipPythonInstall) {
    $argsList += "-SkipPythonInstall"
}
if ($PythonExecutable) {
    $argsList += @("-PythonExecutable", $PythonExecutable)
}
if ($NetworkProfile) {
    $argsList += @("-NetworkProfile", $NetworkProfile)
}
if ($MerchantUrl) {
    $argsList += @("-MerchantUrl", $MerchantUrl)
}
if ($MerchantUrls) {
    $argsList += @("-MerchantUrls", $MerchantUrls)
}

& powershell @argsList

exit $LASTEXITCODE
