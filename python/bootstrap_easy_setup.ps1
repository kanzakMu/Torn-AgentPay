param(
    [switch]$SkipNpmInstall,
    [switch]$SkipPythonInstall,
    [string]$PythonExecutable = "",
    [switch]$Launch,
    [switch]$OpenBrowser,
    [int]$Port = 8010
)

$repoRoot = Split-Path -Parent $PSScriptRoot
$venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
$requirementsPath = Join-Path $repoRoot "python\requirements.txt"

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

Write-Host ""
Write-Host "AimiPay Easy Setup bootstrap complete."
Write-Host "Next step:"
Write-Host "powershell -ExecutionPolicy Bypass -File python/start_easy_setup.ps1"

if ($Launch) {
    Start-Process powershell -ArgumentList @(
        "-ExecutionPolicy", "Bypass",
        "-File", (Join-Path $repoRoot "python\start_easy_setup.ps1"),
        "-Port", "$Port"
    ) -WorkingDirectory $repoRoot | Out-Null
    Start-Sleep -Seconds 2
    $url = "http://127.0.0.1:$Port/aimipay/easy-setup"
    Write-Host "Easy Setup URL:"
    Write-Host $url
    if ($OpenBrowser) {
        Start-Process $url | Out-Null
    }
}
