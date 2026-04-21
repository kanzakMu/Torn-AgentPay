param(
    [switch]$SkipNpmInstall,
    [switch]$SkipPythonInstall,
    [string]$PythonExecutable = "",
    [string]$NetworkProfile = "",
    [string]$MerchantUrl = "",
    [string]$MerchantUrls = "",
    [int]$BuyerOnboardingPort = 8011
)

$repoRoot = Split-Path -Parent $PSScriptRoot
$venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
$requirementsPath = Join-Path $repoRoot "python\requirements.txt"
$envTemplate = Join-Path $repoRoot "python\.env.local.example"
$envTarget = Join-Path $repoRoot "python\.env.local"
$walletFile = Join-Path $repoRoot "python\.wallets\buyer-wallet.json"
$buyerOnboardingPage = Join-Path $repoRoot "python\.agent\buyer-onboarding.html"
$buyerOnboardingUrl = "http://127.0.0.1:$BuyerOnboardingPort/aimipay/buyer/onboarding"

function Resolve-PythonBootstrapCommand {
    if ($PythonExecutable) {
        return @($PythonExecutable)
    }
    if (Get-Command py -ErrorAction SilentlyContinue) {
        return @("py", "-3")
    }
    if (Get-Command python -ErrorAction SilentlyContinue) {
        return @("python")
    }
    throw "Python 3.11+ is required. Install Python and retry."
}

function Ensure-VenvPythonReady {
    if (-not (Test-Path $venvPython)) {
        $pythonBootstrap = Resolve-PythonBootstrapCommand
        & $pythonBootstrap -m venv (Join-Path $repoRoot ".venv")
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to create virtual environment. Install the official Python 3.11+ distribution with venv/ensurepip support and retry."
        }
    }

    & $venvPython -c "import pip" *> $null
    if ($LASTEXITCODE -eq 0) {
        return
    }

    & $venvPython -m ensurepip --upgrade
    if ($LASTEXITCODE -eq 0) {
        & $venvPython -c "import pip" *> $null
        if ($LASTEXITCODE -eq 0) {
            return
        }
    }

    $pythonBootstrap = Resolve-PythonBootstrapCommand
    & $pythonBootstrap -m venv --clear (Join-Path $repoRoot ".venv")
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to repair .venv. Install the official Python 3.11+ distribution with venv/ensurepip support and retry."
    }

    & $venvPython -m ensurepip --upgrade
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to repair pip in .venv."
    }
}

function Ensure-BuyerOnboardingServer {
    try {
        Invoke-RestMethod -Uri "http://127.0.0.1:$BuyerOnboardingPort/aimipay/buyer/onboarding/data" -Method Get -TimeoutSec 2 | Out-Null
        return
    }
    catch {
    }

    $scriptPath = Join-Path $repoRoot "python\run_buyer_onboarding.ps1"
    Start-Process powershell -ArgumentList @(
        "-ExecutionPolicy", "Bypass",
        "-File", $scriptPath,
        "-Port", "$BuyerOnboardingPort"
    ) -WorkingDirectory $repoRoot | Out-Null
    Start-Sleep -Seconds 2
}

Ensure-VenvPythonReady

if (-not $SkipPythonInstall) {
    & $venvPython -m pip install --upgrade pip
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to upgrade pip in .venv."
    }
    & $venvPython -m pip install -r $requirementsPath
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to install Python requirements."
    }
}

if (-not $SkipNpmInstall) {
    if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
        throw "npm is required. Install Node.js 20+ and retry."
    }
    Push-Location $repoRoot
    try {
        npm install
        if ($LASTEXITCODE -ne 0) {
            throw "npm install failed."
        }
    }
    finally {
        Pop-Location
    }
}

if (-not (Test-Path $envTarget)) {
    Copy-Item $envTemplate $envTarget
}

$env:PYTHONPATH = "$repoRoot\python"
if ($MerchantUrls) {
    $merchantArgs = @()
    $merchantSummary = @()
    foreach ($item in $MerchantUrls.Split(",")) {
        $trimmed = $item.Trim()
        if ($trimmed) {
            $merchantArgs += @("--merchant-url", $trimmed)
            $merchantSummary += $trimmed
        }
    }
} elseif ($MerchantUrl) {
    $merchantArgs = @("--merchant-url", $MerchantUrl)
    $merchantSummary = @($MerchantUrl)
} else {
    $merchantArgs = @("--merchant-url", "http://127.0.0.1:8000")
    $merchantSummary = @("http://127.0.0.1:8000")
}

$buyerSetupArgs = @("-m", "ops_tools.buyer_setup", "--repository-root", $repoRoot, "--env-file", $envTarget) + $merchantArgs
if ($NetworkProfile) {
    $buyerSetupArgs += @("--network-profile", $NetworkProfile)
}

& $venvPython @buyerSetupArgs
if ($LASTEXITCODE -ne 0) {
    throw "Failed to prepare buyer install settings."
}
& $venvPython -m ops_tools.wallet_setup --repository-root $repoRoot --env-file $envTarget --wallet-file $walletFile
if ($LASTEXITCODE -ne 0) {
    throw "Failed to create or save the buyer wallet."
}
& $venvPython -m ops_tools.agent_onboarding --repository-root $repoRoot --env-file $envTarget --wallet-file $walletFile
if ($LASTEXITCODE -ne 0) {
    throw "Buyer onboarding failed after wallet setup."
}
& $venvPython -m ops_tools.install_doctor
if ($LASTEXITCODE -ne 0) {
    throw "Install doctor failed after bootstrap."
}
& $venvPython -m ops_tools.install_doctor --format html --output $buyerOnboardingPage
if ($LASTEXITCODE -ne 0) {
    throw "Failed to render buyer onboarding page."
}
Ensure-BuyerOnboardingServer

Write-Host ""
Write-Host "First-start wallet guidance:"
& $venvPython -m ops_tools.wallet_funding --repository-root $repoRoot
if ($LASTEXITCODE -ne 0) {
    throw "Wallet funding guidance failed."
}

Write-Host ""
Write-Host "Bootstrap complete."
if ($NetworkProfile) {
    Write-Host "Network profile:"
    Write-Host $NetworkProfile
}
Write-Host "Merchant URLs:"
Write-Host ($merchantSummary -join ", ")
Write-Host "Buyer wallet saved to:"
Write-Host $walletFile
Write-Host "Buyer onboarding page:"
Write-Host $buyerOnboardingPage
Write-Host "Buyer onboarding local URL:"
Write-Host $buyerOnboardingUrl
Write-Host "If you plan to use a live Tron environment, fund the generated buyer address before purchasing."
Write-Host "Next step:"
Write-Host "powershell -ExecutionPolicy Bypass -File python/run_buyer_onboarding.ps1"
Write-Host ""
Write-Host "If you also want a local merchant and a one-shot demo purchase, continue with:"
Write-Host "powershell -ExecutionPolicy Bypass -File python/bootstrap_merchant.ps1"
Write-Host "powershell -ExecutionPolicy Bypass -File python/run_local_stack.ps1"
