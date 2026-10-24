#!/usr/bin/env pwsh
# ============================================================
# Windows 安装包一键构建（前端 -> 资源同步 -> PyInstaller -> NSIS）
# ------------------------------------------------------------
# 解决两个 Windows 实测坑：
#   1) 默认 %TEMP% 会让 esbuild 报 "Access is denied"（删临时文件失败）；
#      → 构建前把 TEMP/TMP 重定向到 <repo>\.scratch\tmp，结束后恢复。
#   2) `bash` 常被 WSL 接管而不可用，sync-frontend-dist.sh 失效；
#      → 改用 scripts/build/sync-frontend.ps1（robocopy 等价实现）。
#
# 用法：
#   powershell -NoProfile -ExecutionPolicy Bypass -File scripts/build/build-win.ps1
#   powershell -File scripts/build/build-win.ps1 -SkipFrontend
#   powershell -File scripts/build/build-win.ps1 -IncludeMapTilesInBackend
#       # 默认后端不再打包瓦片（由 Electron extraResources + MAP_TILES_DIR 提供）；
#       # 只有「不带 Electron 的 standalone 后端分发」才需要该开关。
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
    Write-Host "[错误] $msg" -ForegroundColor Red
    exit 1
}

New-Item -ItemType Directory -Force -Path $tmp | Out-Null
$oldTemp = $env:TEMP
$oldTmp = $env:TMP
$oldInclude = $env:INCLUDE_MAP_TILES

try {
    $env:TEMP = $tmp
    $env:TMP = $tmp
    if ($IncludeMapTilesInBackend) { $env:INCLUDE_MAP_TILES = '1' } else { $env:INCLUDE_MAP_TILES = $null }
    Write-Host "[env] TEMP/TMP -> $tmp"
    if ($env:INCLUDE_MAP_TILES) { Write-Host "[env] INCLUDE_MAP_TILES=1（后端也打包瓦片）" } else { Write-Host "[env] INCLUDE_MAP_TILES 未设置（瓦片仅走 extraResources）" }

    if (-not $SkipFrontend) {
        Write-Host ""
        Write-Host "=== [1/3] 前端构建 ==="
        Push-Location (Join-Path $root 'frontend')
        try {
            npm run build
            if ($LASTEXITCODE -ne 0) { Fail "前端构建失败" }
        } finally { Pop-Location }

        Write-Host ""
        Write-Host "=== [2/3] 同步前端产物 ==="
        & (Join-Path $PSScriptRoot 'sync-frontend.ps1')
        if ($LASTEXITCODE -ne 0) { Fail "前端产物同步失败" }
    } else {
        Write-Host "[1/3][2/3] 跳过前端构建与同步（-SkipFrontend）"
    }

    Write-Host ""
    Write-Host "=== [3/3] PyInstaller + electron-builder ==="
    Push-Location $root
    try {
        npm run build:win
        if ($LASTEXITCODE -ne 0) { Fail "npm run build:win 失败" }
    } finally { Pop-Location }

    $pkg = Get-Content (Join-Path $root 'package.json') -Raw | ConvertFrom-Json
    $exeName = "MRRS-Setup-$($pkg.version)-x64.exe"
    $exe = Join-Path (Join-Path (Join-Path $root 'dist') 'electron') $exeName
    if (-not (Test-Path $exe)) { Fail "未找到安装包：$exe" }
    $mb = [math]::Round((Get-Item $exe).Length / 1MB, 1)
    Write-Host ""
    Write-Host "[OK] 安装包：$exe（$mb MB）" -ForegroundColor Green
    exit 0
} finally {
    $env:TEMP = $oldTemp
    $env:TMP = $oldTmp
    $env:INCLUDE_MAP_TILES = $oldInclude
}
