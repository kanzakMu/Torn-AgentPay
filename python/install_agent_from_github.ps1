param(
    [string]$RepoUrl = "",
    [string]$Branch = "main",
    [string]$InstallRoot = "",
    [string]$Target = "codex",
    [string]$Host = "",
    [string]$MerchantUrl = "",
    [switch]$SkipVerify
)

$ErrorActionPreference = "Stop"

if (-not $RepoUrl) {
    throw "RepoUrl is required. Example: -RepoUrl https://github.com/<owner>/<repo>.git"
}

if (-not $InstallRoot) {
    $InstallRoot = Join-Path $HOME "AimiPayAgent"
}

New-Item -ItemType Directory -Force -Path $InstallRoot | Out-Null

function Resolve-RepoName {
    param([string]$Url)
    $trimmed = $Url.TrimEnd("/")
    $name = [IO.Path]::GetFileName($trimmed)
    if ($name.EndsWith(".git")) {
        $name = $name.Substring(0, $name.Length - 4)
    }
    return $name
}

function Build-GithubArchiveUrl {
    param(
        [string]$Url,
        [string]$GitBranch
    )
    $trimmed = $Url.TrimEnd("/")
    if ($trimmed.EndsWith(".git")) {
        $trimmed = $trimmed.Substring(0, $trimmed.Length - 4)
    }
    return "$trimmed/archive/refs/heads/$GitBranch.zip"
}

$repoName = Resolve-RepoName -Url $RepoUrl
$targetDir = Join-Path $InstallRoot $repoName

if (-not (Test-Path $targetDir)) {
    if (Get-Command git -ErrorAction SilentlyContinue) {
        git clone --depth 1 --branch $Branch $RepoUrl $targetDir
        if ($LASTEXITCODE -ne 0) {
            throw "git clone failed."
        }
    }
    else {
        $zipUrl = Build-GithubArchiveUrl -Url $RepoUrl -GitBranch $Branch
        $tempZip = Join-Path ([IO.Path]::GetTempPath()) "$repoName-$Branch-agent.zip"
        $extractRoot = Join-Path ([IO.Path]::GetTempPath()) "$repoName-$Branch-agent-extract"
        if (Test-Path $tempZip) { Remove-Item $tempZip -Force }
        if (Test-Path $extractRoot) { Remove-Item $extractRoot -Recurse -Force }
        Invoke-WebRequest -Uri $zipUrl -OutFile $tempZip
        Expand-Archive -Path $tempZip -DestinationPath $extractRoot -Force
        $expandedFolder = Get-ChildItem $extractRoot | Select-Object -First 1
        if (-not $expandedFolder) {
            throw "Could not unpack the GitHub archive."
        }
        Move-Item $expandedFolder.FullName $targetDir
    }
}

$bootstrapScript = Join-Path $targetDir "python\bootstrap_easy_setup.ps1"
$installerScript = Join-Path $targetDir "python\install_agent_package.ps1"
$hostInstallerScript = Join-Path $targetDir "python\install_ai_host.ps1"

if (-not (Test-Path $bootstrapScript)) {
    throw "bootstrap_easy_setup.ps1 was not found after download."
}
if (-not (Test-Path $installerScript)) {
    throw "install_agent_package.ps1 was not found after download."
}

& $bootstrapScript
if ($LASTEXITCODE -ne 0) {
    throw "Agent bootstrap failed after download."
}

$effectiveHost = if ($Host) { $Host } else { $Target }
if (Test-Path $hostInstallerScript) {
    $installArgs = @("--repository-root", $targetDir, "--host", $effectiveHost, "--mode", "home-local")
} else {
    $installArgs = @("--repository-root", $targetDir, "--target", $Target, "--mode", "home-local")
}
if ($MerchantUrl) {
    $installArgs += @("--merchant-url", $MerchantUrl)
}
if ($SkipVerify) {
    $installArgs += "--skip-verify"
}

if (Test-Path $hostInstallerScript) {
    powershell -ExecutionPolicy Bypass -File $hostInstallerScript @installArgs
} else {
    powershell -ExecutionPolicy Bypass -File $installerScript @installArgs
}
if ($LASTEXITCODE -ne 0) {
    throw "Agent package installation failed after download."
}

Write-Host ""
Write-Host "AimiPay agent package downloaded to:"
Write-Host $targetDir
Write-Host "Installed target:"
Write-Host $effectiveHost
