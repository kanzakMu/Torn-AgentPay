param(
    [string]$OutputDir = ""
)

$ErrorActionPreference = "Stop"

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptRoot

$venvPython = Join-Path $repoRoot ".venv\\Scripts\\python.exe"
if (-not (Test-Path $venvPython)) {
    throw "Python virtual environment not found at $venvPython. Run python/bootstrap_buyer.ps1 or python/bootstrap_merchant.ps1 first."
}

$env:PYTHONPATH = Join-Path $repoRoot "python"

$args = @("-m", "ops_tools.build_release_artifacts")
if ($OutputDir) {
    $args += @("--output-dir", $OutputDir)
}
$args += "--json"

& $venvPython @args
exit $LASTEXITCODE
