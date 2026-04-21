param(
    [switch]$SkipNpmInstall,
    [switch]$SkipPythonInstall,
    [string]$PythonExecutable = "",
    [string]$NetworkProfile = "local"
)

$repoRoot = Split-Path -Parent $PSScriptRoot
$venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
$requirementsPath = Join-Path $repoRoot "python\requirements.txt"
$merchantEnv = Join-Path $repoRoot "python\.env.merchant.local"

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

$env:PYTHONPATH = "$repoRoot\python"
& $venvPython -m ops_tools.merchant_setup --repository-root $repoRoot --env-file $merchantEnv --network-profile $NetworkProfile
if ($LASTEXITCODE -ne 0) {
    throw "Failed to prepare merchant install files."
}
& $venvPython -m ops_tools.merchant_doctor
if ($LASTEXITCODE -ne 0) {
    throw "Merchant doctor failed after bootstrap."
}

Write-Host ""
Write-Host "Merchant bootstrap complete."
Write-Host "Network profile:"
Write-Host $NetworkProfile
Write-Host "Merchant env saved to:"
Write-Host $merchantEnv
Write-Host "Next step:"
Write-Host "powershell -ExecutionPolicy Bypass -File python/run_merchant_stack.ps1"
