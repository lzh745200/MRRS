#!/usr/bin/env pwsh
# ============================================================
# Sync frontend build output: frontend/dist -> resources/frontend
# ------------------------------------------------------------
# Why this PowerShell version:
#   scripts/build/sync-frontend-dist.sh needs bash; on Windows `bash` is
#   often WSL, and WSL may be broken (ext4.vhdx error), so the sync fails.
#   This is the equivalent: wipe target, copy tree, verify counts.
#
# ASCII-only on purpose: Windows PowerShell 5.1 decodes .ps1 as ANSI when
# there is no BOM, so non-ASCII text can break parsing after edits.
#
# Usage:
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
    Write-Host "[ERROR] $msg" -ForegroundColor Red
    exit 1
}

Write-Host "[info] src=$src"
Write-Host "[info] dst=$dst"

if (-not (Test-Path (Join-Path $src 'index.html'))) {
    Fail "source missing index.html: $src. Run 'cd frontend && npm run build' first."
}

$srcFiles = (Get-ChildItem $src -Recurse -File | Measure-Object).Count
Write-Host "[1/3] source ok ($srcFiles files)"

if (-not $SkipClean -and (Test-Path $dst)) {
    Write-Host '[2/3] cleaning target'
    try {
        Remove-Item -Recurse -Force $dst
    } catch {
        Fail "cannot remove target (locked by python/uvicorn/electron/nginx?): $dst ; $($_.Exception.Message)"
    }
} else {
    Write-Host '[2/3] skip clean (-SkipClean)'
}
New-Item -ItemType Directory -Force -Path $dst | Out-Null

Write-Host '[3/3] copying (robocopy /MIR)'
robocopy $src $dst /MIR /NFL /NDL /NJH /NJS /NP /R:2 /W:2 | Out-Null
$robocopyExit = $LASTEXITCODE
Write-Host "[info] robocopy exit=$robocopyExit"
# robocopy: 0-7 are success (0=no change, 1=copied, 2=extra removed, 3=1+2 ...)
if ($robocopyExit -ge 8) {
    Fail "robocopy failed (exit=$robocopyExit)"
}

if (-not (Test-Path (Join-Path $dst 'index.html'))) {
    Fail "index.html missing after copy: $dst"
}

$dstFiles = (Get-ChildItem $dst -Recurse -File | Measure-Object).Count
if ($dstFiles -ne $srcFiles) {
    Fail "file count mismatch: src $srcFiles / dst $dstFiles"
}

$srcBytes = (Get-ChildItem $src -Recurse -File | Measure-Object -Property Length -Sum).Sum
$dstBytes = (Get-ChildItem $dst -Recurse -File | Measure-Object -Property Length -Sum).Sum
if ($srcBytes -ne $dstBytes) {
    Fail "byte count mismatch: src $srcBytes / dst $dstBytes"
}

Write-Host ("[OK] synced {0} files / {1:N1} MB -> {2}" -f $dstFiles, ($dstBytes / 1MB), $dst)
exit 0
