<#
.SYNOPSIS
    校验 Windows 安装包 / 后端 exe 的 Authenticode 签名状态。

.DESCRIPTION
    W6-T1 签名管线的「构建后校验」环节（短期项 8，2026-11-01）。
    证书未到位时可以正常跑（只报告 NotSigned），证书到位后配合
    -RequireSignature 作为发版硬门禁：任何未签名/签名无效的产物都会失败。

    判定口径：
    - Valid             → 通过（打印签名主体与时间戳）
    - NotSigned         → 未配置证书：默认只 WARNING；带 -RequireSignature 则失败
    - UnknownError/HashMismatch/NotTrusted 等 → 一律失败（签名存在但无效）

.PARAMETER Path
    待校验的 .exe 文件或目录（目录会递归找 *.exe，含安装包与后端主程序）。

.PARAMETER RequireSignature
    要求每个 exe 都必须有有效签名（证书到位后的发版门禁）。

.EXAMPLE
    powershell -NoProfile -ExecutionPolicy Bypass -File scripts/verify_installer_signature.ps1 -Path dist/electron

.EXAMPLE
    powershell -NoProfile -ExecutionPolicy Bypass -File scripts/verify_installer_signature.ps1 -Path dist/electron -RequireSignature
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Path,

    [switch]$RequireSignature
)

$ErrorActionPreference = 'Stop'

function Resolve-Targets {
    param([string]$InputPath)
    if (-not (Test-Path -LiteralPath $InputPath)) {
        throw "路径不存在：$InputPath"
    }
    $item = Get-Item -LiteralPath $InputPath
    if ($item.PSIsContainer) {
        return @(Get-ChildItem -LiteralPath $InputPath -Recurse -Filter '*.exe' -File | Sort-Object FullName)
    }
    return @($item)
}

$targets = Resolve-Targets -InputPath $Path
if ($targets.Count -eq 0) {
    Write-Host '[WARN] 未找到任何 .exe 产物（目录为空？尚未构建？）' -ForegroundColor Yellow
    if ($RequireSignature) { exit 1 }
    exit 0
}

$failures = @()
$unsigned = @()

foreach ($file in $targets) {
    $sig = Get-AuthenticodeSignature -LiteralPath $file.FullName
    $status = [string]$sig.Status
    $rel = $file.FullName
    if ($status -eq 'Valid') {
        $subject = ''
        if ($null -ne $sig.SignerCertificate) { $subject = $sig.SignerCertificate.Subject }
        Write-Host ("[OK]   {0}`n       签名主体：{1}" -f $rel, $subject) -ForegroundColor Green
        continue
    }
    if ($status -eq 'NotSigned') {
        Write-Host ("[WARN] {0}`n       未签名（证书未配置时属预期）" -f $rel) -ForegroundColor Yellow
        $unsigned += $rel
        continue
    }
    Write-Host ("[FAIL] {0}`n       签名状态：{1} {2}" -f $rel, $status, $sig.StatusMessage) -ForegroundColor Red
    $failures += $rel
}

Write-Host ''
Write-Host ("汇总：{0} 个 exe，有效签名 {1}，未签名 {2}，无效 {3}" -f `
    $targets.Count, ($targets.Count - $unsigned.Count - $failures.Count), $unsigned.Count, $failures.Count)

if ($failures.Count -gt 0) {
    Write-Host '[FAIL] 存在签名无效的产物（伪造/被篡改/证书链不受信），禁止发布。' -ForegroundColor Red
    exit 1
}

if ($RequireSignature -and $unsigned.Count -gt 0) {
    Write-Host '[FAIL] -RequireSignature 已开启，但仍有未签名产物。' -ForegroundColor Red
    exit 1
}

if ($unsigned.Count -gt 0) {
    Write-Host '[WARN] 存在未签名产物：军队白名单/政企分发场景需配置 CSC_LINK 后重新构建。' -ForegroundColor Yellow
}

Write-Host 'SIGNATURE_CHECK_PASS'
exit 0
