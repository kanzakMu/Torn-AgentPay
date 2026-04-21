param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$InstallerArgs
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$VenvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$FallbackRuntime = "C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"

if (Test-Path $VenvPython) {
    $PythonExe = $VenvPython
} elseif (Test-Path $FallbackRuntime) {
    $PythonExe = $FallbackRuntime
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
    $PythonExe = "py"
    $InstallerArgs = @("-3", "-m", "ops_tools.install_agent_package") + $InstallerArgs
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $PythonExe = "python"
    $InstallerArgs = @("-m", "ops_tools.install_agent_package") + $InstallerArgs
} else {
    Write-Error "Python 3.11+ was not found. Install the official Python distribution or create .venv first."
}

if ($PythonExe -ne "py" -and $PythonExe -ne "python") {
    $InstallerArgs = @("-m", "ops_tools.install_agent_package") + $InstallerArgs
}

$PythonPath = @(
    (Join-Path $RepoRoot "python"),
    (Join-Path $RepoRoot "python\.vendor")
) -join [IO.Path]::PathSeparator

$PreviousPythonPath = $env:PYTHONPATH
$env:PYTHONPATH = $PythonPath

try {
    & $PythonExe @InstallerArgs
    exit $LASTEXITCODE
} finally {
    $env:PYTHONPATH = $PreviousPythonPath
}
