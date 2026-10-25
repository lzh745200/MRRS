#!/usr/bin/env pwsh
# ============================================================
# Windows installer one-shot build
#   frontend build -> sync resources/frontend -> PyInstaller -> NSIS
# ------------------------------------------------------------
# Why this wrapper exists (two real Windows pitfalls):
#   1) Default %TEMP% makes esbuild fail with "Access is denied"
#      (cannot delete its temp dir). We redirect TEMP/TMP to <repo>\.scratch\tmp.
#   2) `bash` is often taken over by WSL on Windows, so
#      scripts/build/sync-frontend-dist.sh cannot run; we use the
#      PowerShell equivalent below instead.
#
# ASCII-only on purpose: Windows PowerShell 5.1 decodes .ps1 as ANSI when
# there is no BOM, so non-ASCII text can break parsing after edits.
#
# Usage:
#   powershell -NoProfile -ExecutionPolicy Bypass -File scripts/build/build-win.ps1
#   powershell -File scripts/build/build-win.ps1 -SkipFrontend
#   powershell -File scripts/build/build-win.ps1 -IncludeMapTilesInBackend
#       # backend no longer bundles tiles by default; Electron ships them via
#       # extraResources + MAP_TILES_DIR. Use this only for standalone backend.
# ============================================================
[CmdletBinding()]
param(
    [switch]$SkipFrontend,
    [switch]$IncludeMapTilesInBackend
)

$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$tmp = Join-Path (Join-Path $root '.scratch') 'tmp'

function Fail([string]$msg) {
    Write-Host "[ERROR] $msg" -ForegroundColor Red
    exit 1
}

New-Item -ItemType Directory -Force -Path $tmp | Out-Null
$oldTemp = $env:TEMP
$oldTmp = $env:TMP
$oldInclude = $env:INCLUDE_MAP_TILES

try {
    $env:TEMP = $tmp
    $env:TMP = $tmp
    if ($IncludeMapTilesInBackend) {
        $env:INCLUDE_MAP_TILES = '1'
        Write-Host '[env] INCLUDE_MAP_TILES=1 (backend also bundles tiles)'
    } else {
        $env:INCLUDE_MAP_TILES = $null
        Write-Host '[env] INCLUDE_MAP_TILES unset (tiles only via extraResources)'
    }
    Write-Host "[env] TEMP/TMP -> $tmp"

    if (-not $SkipFrontend) {
        Write-Host ''
        Write-Host '=== [1/3] frontend build ==='
        Push-Location (Join-Path $root 'frontend')
        try {
            npm run build
            if ($LASTEXITCODE -ne 0) { Fail 'frontend build failed' }
        } finally { Pop-Location }

        Write-Host ''
        Write-Host '=== [2/3] sync frontend dist ==='
        & (Join-Path $PSScriptRoot 'sync-frontend.ps1')
        if ($LASTEXITCODE -ne 0) { Fail 'frontend sync failed' }
    } else {
        Write-Host '[1/3][2/3] skipped (-SkipFrontend)'
    }

    Write-Host ''
    Write-Host '=== [3/3] PyInstaller + electron-builder ==='
    Push-Location $root
    try {
        npm run build:win
        if ($LASTEXITCODE -ne 0) { Fail 'npm run build:win failed' }
    } finally { Pop-Location }

    # UTF-8 explicit read: PS 5.1 Get-Content defaults to ANSI and would choke
    # on the Chinese productName inside package.json.
    $pkgRaw = [System.IO.File]::ReadAllText(
        (Join-Path $root 'package.json'),
        [System.Text.Encoding]::UTF8
    )
    $pkg = $pkgRaw | ConvertFrom-Json
    $exeName = 'MRRS-Setup-' + $pkg.version + '-x64.exe'
    $exe = Join-Path (Join-Path (Join-Path $root 'dist') 'electron') $exeName
    if (-not (Test-Path $exe)) { Fail "installer not found: $exe" }
    $mb = [math]::Round((Get-Item $exe).Length / 1MB, 1)
    Write-Host ''
    Write-Host "[OK] installer: $exe ($mb MB)" -ForegroundColor Green
    exit 0
} finally {
    $env:TEMP = $oldTemp
    $env:TMP = $oldTmp
    $env:INCLUDE_MAP_TILES = $oldInclude
}
