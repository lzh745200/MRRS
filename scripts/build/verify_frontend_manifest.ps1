# ============================================================================
# verify_frontend_manifest.ps1 — 前端产物逐文件 SHA256 manifest 校验核心
# ----------------------------------------------------------------------------
# 对比源目录与目标目录的逐文件 SHA256（W6-T5）：
#   - 任何缺失/多出/哈希不一致 → 打印差异并 exit 1
#   - 一致 → 将 manifest（sha256sum -c 兼容格式）写入 -ManifestPath，
#     供 scripts/audit_static_assets.py --verify-manifest 复核
# 调用方：scripts/build/sync-frontend-dist.bat
# ============================================================================
param(
    [Parameter(Mandatory = $true)][string]$Src,
    [Parameter(Mandatory = $true)][string]$Dst,
    [Parameter(Mandatory = $true)][string]$ManifestPath
)
$ErrorActionPreference = 'Stop'

function Get-DirManifest([string]$root) {
    Get-ChildItem -LiteralPath $root -Recurse -File | Sort-Object FullName |
        ForEach-Object {
            '{0}  {1}' -f (Get-FileHash -Algorithm SHA256 -LiteralPath $_.FullName).Hash.ToLower(),
                $_.FullName.Substring($root.Length + 1).Replace('\', '/')
        }
}

$srcPath = (Resolve-Path -LiteralPath $Src).Path
$dstPath = (Resolve-Path -LiteralPath $Dst).Path
$mSrc = @(Get-DirManifest $srcPath)
$mDst = @(Get-DirManifest $dstPath)

$srcText = $mSrc -join "`n"
$dstText = $mDst -join "`n"
if ($srcText -cne $dstText) {
    Write-Host "[错误] SHA256 manifest 比对失败（< 源 / > 目标 或 => 两侧差异）"
    Compare-Object $mSrc $mDst | Select-Object -First 20 |
        ForEach-Object { Write-Host ("  {0} {1}" -f $_.SideIndicator, $_.InputObject) }
    exit 1
}

# UTF-8 无 BOM，保持 sha256sum -c 兼容
[IO.File]::WriteAllLines($ManifestPath, $mSrc, (New-Object Text.UTF8Encoding($false)))
Write-Host ("[OK] {0} 个文件逐文件 SHA256 一致" -f $mSrc.Count)
exit 0
