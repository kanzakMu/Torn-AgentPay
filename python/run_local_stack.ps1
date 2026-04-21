param(
    [int]$MerchantPort = 8000,
    [int]$BuyerOnboardingPort = 8011,
    [switch]$BootstrapMerchantIfNeeded = $true
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
$buyerEnv = Join-Path $repoRoot "python\.env.local"
$merchantEnv = Join-Path $repoRoot "python\.env.merchant.local"
$merchantScript = Join-Path $repoRoot "python\run_merchant_stack.ps1"
$buyerOnboardingScript = Join-Path $repoRoot "python\run_buyer_onboarding.ps1"
$merchantDashboardUrl = "http://127.0.0.1:$MerchantPort/aimipay/install"
$buyerOnboardingUrl = "http://127.0.0.1:$BuyerOnboardingPort/aimipay/buyer/onboarding"

function Test-Endpoint {
    param([string]$Url)
    try {
        $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 2
        return $response.StatusCode -eq 200
    }
    catch {
        return $false
    }
}

function Wait-Endpoint {
    param(
        [string]$Url,
        [string]$Label,
        [int]$TimeoutSeconds = 20
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-Endpoint -Url $Url) {
            return
        }
        Start-Sleep -Milliseconds 500
    }
    throw "$Label did not become healthy in time: $Url"
}

function Start-BackgroundPowerShell {
    param(
        [string]$ScriptPath,
        [string[]]$Arguments
    )

    $argumentList = @(
        "-ExecutionPolicy", "Bypass",
        "-File", $ScriptPath
    ) + $Arguments

    Start-Process powershell -ArgumentList $argumentList -WorkingDirectory $repoRoot | Out-Null
}

if (-not (Test-Path $venvPython)) {
    throw "Missing .venv. Run python/bootstrap_local.ps1 first."
}

if (-not (Test-Path $buyerEnv)) {
    throw "Missing python/.env.local. Run python/bootstrap_local.ps1 first."
}

if ((-not (Test-Path $merchantEnv)) -and $BootstrapMerchantIfNeeded) {
    powershell -ExecutionPolicy Bypass -File (Join-Path $repoRoot "python\bootstrap_merchant.ps1") -SkipNpmInstall -SkipPythonInstall -NetworkProfile local
    if ($LASTEXITCODE -ne 0) {
        throw "Merchant bootstrap failed while preparing the local stack."
    }
}

if (-not (Test-Path $merchantEnv)) {
    throw "Missing python/.env.merchant.local. Run python/bootstrap_merchant.ps1 first."
}

$env:PYTHONPATH = "$repoRoot\python"
$env:NO_PROXY = "127.0.0.1,localhost"
$env:no_proxy = "127.0.0.1,localhost"

if (-not (Test-Endpoint -Url $merchantDashboardUrl)) {
    Start-BackgroundPowerShell -ScriptPath $merchantScript -Arguments @("-MerchantPort", "$MerchantPort")
}
Wait-Endpoint -Url $merchantDashboardUrl -Label "merchant dashboard"

if (-not (Test-Endpoint -Url $buyerOnboardingUrl)) {
    Start-BackgroundPowerShell -ScriptPath $buyerOnboardingScript -Arguments @("-Port", "$BuyerOnboardingPort")
}
Wait-Endpoint -Url $buyerOnboardingUrl -Label "buyer onboarding"

Write-Host ""
Write-Host "AimiPay local stack is running."
Write-Host "Merchant dashboard:"
Write-Host $merchantDashboardUrl
Write-Host "Buyer onboarding:"
Write-Host $buyerOnboardingUrl
Write-Host "One-shot local payment demo:"
Write-Host "powershell -ExecutionPolicy Bypass -File python/run_local_demo.ps1"
