param(
    [string]$InstallRoot,
    [switch]$Json,
    [switch]$RunDoctor
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$InstallScript = Join-Path $PSScriptRoot "install_agent_package.ps1"
$VenvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$FallbackRuntime = "C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"

if (Test-Path $VenvPython) {
    $PythonExe = $VenvPython
} elseif (Test-Path $FallbackRuntime) {
    $PythonExe = $FallbackRuntime
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
    $PythonExe = "py"
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $PythonExe = "python"
} else {
    Write-Error "Python 3.11+ was not found. Install the official Python distribution or create .venv first."
}

$InstallArgs = @(
    "--repository-root", $RepoRoot,
    "--target", "all",
    "--mode", "home-local"
)
if ($InstallRoot) {
    $InstallArgs += @("--install-root", $InstallRoot)
}
if ($Json) {
    $InstallArgs += "--json"
}

powershell -ExecutionPolicy Bypass -File $InstallScript @InstallArgs
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

$VerifyArgs = @("-m", "ops_tools.verify_agent_installation", "--repository-root", $RepoRoot, "--mode", "home-local")
if ($InstallRoot) {
    $VerifyArgs += @("--install-root", $InstallRoot)
}
if ($Json) {
    $VerifyArgs += "--json"
}

$PythonPath = @(
    (Join-Path $RepoRoot "python"),
    (Join-Path $RepoRoot "python\.vendor")
) -join [IO.Path]::PathSeparator
$PreviousPythonPath = $env:PYTHONPATH
$env:PYTHONPATH = $PythonPath

try {
    if ($PythonExe -eq "py") {
        & $PythonExe -3 @VerifyArgs
    } else {
        & $PythonExe @VerifyArgs
    }
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }

    if ($RunDoctor) {
        $DoctorArgs = @("-m", "ops_tools.install_doctor", "--repository-root", $RepoRoot)
        if ($PythonExe -eq "py") {
            & $PythonExe -3 @DoctorArgs
        } else {
            & $PythonExe @DoctorArgs
        }
        exit $LASTEXITCODE
    }
} finally {
    $env:PYTHONPATH = $PreviousPythonPath
}
