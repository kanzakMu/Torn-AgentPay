param(
    [string]$RepoUrl = "",
    [string]$Branch = "main",
    [string]$InstallRoot = "",
    [switch]$Launch = $true,
    [switch]$OpenBrowser = $true,
    [int]$Port = 8010
)

$ErrorActionPreference = "Stop"

if (-not $RepoUrl) {
    throw "RepoUrl is required. Example: -RepoUrl https://github.com/<owner>/<repo>.git"
}

if (-not $InstallRoot) {
    $InstallRoot = Join-Path $HOME "AimiPay"
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
        $tempZip = Join-Path ([IO.Path]::GetTempPath()) "$repoName-$Branch.zip"
        $extractRoot = Join-Path ([IO.Path]::GetTempPath()) "$repoName-$Branch-extract"
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
if (-not (Test-Path $bootstrapScript)) {
    throw "bootstrap_easy_setup.ps1 was not found after download."
}

& $bootstrapScript -Launch:$Launch -OpenBrowser:$OpenBrowser -Port $Port
if ($LASTEXITCODE -ne 0) {
    throw "Easy setup bootstrap failed after download."
}

Write-Host ""
Write-Host "AimiPay downloaded to:"
Write-Host $targetDir
Write-Host "Easy Setup URL:"
Write-Host "http://127.0.0.1:$Port/aimipay/easy-setup"
