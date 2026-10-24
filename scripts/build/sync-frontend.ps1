#!/usr/bin/env pwsh
# ============================================================
# 前端构建产物同步：frontend/dist -> resources/frontend
# ------------------------------------------------------------
# 为什么有这份 PowerShell 版：
#   scripts/build/sync-frontend-dist.sh 依赖 bash；Windows 上 `bash` 常被 WSL 接管
#   （本机实测 WSL ext4.vhdx 报错不可用），导致同步脚本直接失败。
#   本脚本是等价实现：强制清空目标目录后整树复制，并做数量/入口校验。
#
# 用法：
#   powershell -NoProfile -ExecutionPolicy Bypass -File scripts/build/sync-frontend.ps1
#   powershell -File scripts/build/sync-frontend.ps1 -SkipClean
# ============================================================
[CmdletBinding()]
param(
    [switch]$SkipClean
)

$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$src = Join-Path (Join-Path $root 'frontend') 'dist'
$dst = Join-Path (Join-Path $root 'resources') 'frontend'

function Fail([string]$msg) {
    Write-Host "[错误] $msg" -ForegroundColor Red
    exit 1
}

Write-Host "[info] src=$src"
Write-Host "[info] dst=$dst"

if (-not (Test-Path (Join-Path $src 'index.html'))) {
    Fail "源目录不存在或缺少 index.html：$src。请先执行: cd frontend && npm run build"
}

$srcFiles = (Get-ChildItem $src -Recurse -File | Measure-Object).Count
Write-Host "[1/3] 源目录检查通过（$srcFiles 个文件）"

if (-not $SkipClean -and (Test-Path $dst)) {
    Write-Host "[2/3] 清空目标目录"
    try {
        Remove-Item -Recurse -Force $dst
    } catch {
        Fail "无法清理目标目录（可能被 python/uvicorn/electron/nginx 占用）：$dst；$($_.Exception.Message)"
    }
} else {
    Write-Host "[2/3] 跳过清理（-SkipClean）"
}
New-Item -ItemType Directory -Force -Path $dst | Out-Null

Write-Host "[3/3] 复制文件（robocopy /MIR）"
robocopy $src $dst /MIR /NFL /NDL /NJH /NJS /NP /R:2 /W:2 | Out-Null
$robocopyExit = $LASTEXITCODE
Write-Host "[info] robocopy exit=$robocopyExit"
# robocopy: 0-7 均为成功（0=无变化,1=已复制,2=多余文件已删,3=1+2 ...）；>=8 才是失败
if ($robocopyExit -ge 8) {
    Fail "robocopy 失败（exit=$robocopyExit）"
}

if (-not (Test-Path (Join-Path $dst 'index.html'))) {
    Fail "同步后缺少 index.html：$dst"
}

$dstFiles = (Get-ChildItem $dst -Recurse -File | Measure-Object).Count
if ($dstFiles -ne $srcFiles) {
    Fail "文件数不一致：源 $srcFiles / 目标 $dstFiles"
}

$srcBytes = (Get-ChildItem $src -Recurse -File | Measure-Object -Property Length -Sum).Sum
$dstBytes = (Get-ChildItem $dst -Recurse -File | Measure-Object -Property Length -Sum).Sum
if ($srcBytes -ne $dstBytes) {
    Fail "总字节数不一致：源 $srcBytes / 目标 $dstBytes"
}

Write-Host ("[OK] 同步完成：{0} 个文件 / {1:N1} MB -> {2}" -f $dstFiles, ($dstBytes / 1MB), $dst)
exit 0
