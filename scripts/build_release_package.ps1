param(
    [string]$OutputDirectory,
    [switch]$MetadataOnly
)

$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$version = (Get-Content -Raw -LiteralPath (Join-Path $root 'VERSION')).Trim()
if ($version -notmatch '^\d+\.\d+\.\d+$') { throw 'VERSION must be a semantic release number' }
$commit = (git -C $root rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0 -or $commit -notmatch '^[0-9a-f]{40}$') { throw 'Cannot resolve Git commit' }

if (-not $OutputDirectory) { $OutputDirectory = Join-Path $root "soar-sdlc-$version" }
$target = [System.IO.Path]::GetFullPath($OutputDirectory)
if (Test-Path -LiteralPath $target) { throw "Output directory already exists: $target" }
New-Item -ItemType Directory -Path $target | Out-Null

if (-not $MetadataOnly) {
    $archive = Join-Path $target 'source.tar'
    git -C $root archive --format=tar --output=$archive HEAD -- VERSION backend/app backend/alembic backend/alembic.ini backend/requirements.txt frontend/index.html frontend/package.json frontend/package-lock.json frontend/vite.config.js frontend/public frontend/src deployment
    if ($LASTEXITCODE -ne 0) { throw 'Git archive failed; commit the release source before packaging' }
    tar -xf $archive -C $target
    if ($LASTEXITCODE -ne 0) { throw 'Archive extraction failed' }
    Remove-Item -LiteralPath $archive
    $packagedVersion = (Get-Content -Raw -LiteralPath (Join-Path $target 'VERSION')).Trim()
    if ($packagedVersion -ne $version) { throw 'Working VERSION differs from committed release source' }
}

$deployment = Join-Path $target 'deployment'
New-Item -ItemType Directory -Path $deployment -Force | Out-Null
Set-Content -LiteralPath (Join-Path $deployment 'release.env') -Encoding ascii -Value @("APP_VERSION=$version", "GIT_COMMIT=$commit")

if (-not $MetadataOnly) {
    $package = "$target.tar.gz"
    tar -czf $package -C (Split-Path $target -Parent) (Split-Path $target -Leaf)
    if ($LASTEXITCODE -ne 0) { throw 'Release archive creation failed' }
    Write-Output $package
} else {
    Write-Output (Join-Path $deployment 'release.env')
}
