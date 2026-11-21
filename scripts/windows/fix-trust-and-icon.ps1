# -*- coding: utf-8 -*-
# 现场修复脚本（管理员 PowerShell 运行一次即可）：
#   ① 导入内网代码签名公钥证书 → 消除「未知发布者」
#   ② 解除安装目录的「下载标记」(MOTW) → 消除「打开文件 - 安全警告」
#   ③ 刷新图标缓存并重建快捷方式（图标源统一为 resources\app-circle.ico）→ 修复白纸图标
#
# 适用场景：已经装好 v1.18.36 ~ v1.18.43 的机器，不想重装升级。
# 用法：
#   powershell -ExecutionPolicy Bypass -File fix-trust-and-icon.ps1
#   powershell -ExecutionPolicy Bypass -File fix-trust-and-icon.ps1 -InstallDir "D:\Apps\MRRS" -WhatIfCertOnly
param(
  [string]$InstallDir = "C:\Program Files\Assistance-Management-Information-System",
  [string]$CertPath = "",
  [switch]$SkipCert,
  [switch]$SkipUnblock,
  [switch]$SkipShortcut
)

$ErrorActionPreference = "Stop"

function Info([string]$m) { Write-Host "[fix] $m" -ForegroundColor Cyan }
function Ok([string]$m)   { Write-Host "[ OK ] $m" -ForegroundColor Green }
function Warn([string]$m) { Write-Host "[WARN] $m" -ForegroundColor Yellow }

# ── 0. 前置检查 ───────────────────────────────────────────────────────
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
  [Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) { throw "请以管理员身份运行（右键 PowerShell → 以管理员身份运行）" }
if (-not (Test-Path -LiteralPath $InstallDir)) { throw "安装目录不存在：$InstallDir" }

$exe = Join-Path $InstallDir "帮扶管理系统.exe"
$ico = Join-Path $InstallDir "resources\app-circle.ico"
if (-not (Test-Path -LiteralPath $exe)) { throw "找不到主程序：$exe" }

# ── 1. 导入公钥证书（Root + TrustedPublisher） ────────────────────────
if (-not $SkipCert) {
  if (-not $CertPath) {
    $CertPath = Join-Path $InstallDir "resources\cert\MRRS-Internal-CodeSigning.cer"
  }
  if (Test-Path -LiteralPath $CertPath) {
    $cer = New-Object System.Security.Cryptography.X509Certificates.X509Certificate2 $CertPath
    Info ("证书：{0} / 指纹 {1}" -f $cer.Subject, $cer.Thumbprint)
    foreach ($storeName in @("Root", "TrustedPublisher")) {
      $store = New-Object System.Security.Cryptography.X509Certificates.X509Store($storeName, "LocalMachine")
      $store.Open("ReadWrite")
      try {
        if ($store.Certificates | Where-Object { $_.Thumbprint -eq $cer.Thumbprint }) {
          Ok "$storeName 已存在同一证书，跳过"
        } else {
          $store.Add($cer)
          Ok "已导入 $storeName"
        }
      } finally { $store.Close() }
    }
  } else {
    Warn "未找到证书文件：$CertPath（可用 -CertPath 指定）"
  }
}

# ── 2. 解除下载标记 ───────────────────────────────────────────────────
if (-not $SkipUnblock) {
  $n = 0
  Get-ChildItem -LiteralPath $InstallDir -Recurse -File -Force -ErrorAction SilentlyContinue |
    Where-Object { $_.Extension -in @(".exe", ".dll", ".ico", ".lnk") } |
    ForEach-Object {
      if (Get-Item -LiteralPath $_.FullName -Stream Zone.Identifier -ErrorAction SilentlyContinue) {
        Unblock-File -LiteralPath $_.FullName; $n++
      }
    }
  Ok "解除下载标记 $n 个文件"
}

# ── 3. 重建快捷方式（图标统一指向 ico） ───────────────────────────────
if (-not $SkipShortcut) {
  # 2026-11-21：优先使用主程序内嵌图标（构建期已校验 7 档），避免 ico 路径/缓存问题
  $iconLoc = "$exe,0"
  $targets = @(
    (Join-Path ([Environment]::GetFolderPath("CommonDesktopDirectory")) "帮扶管理系统.lnk"),
    (Join-Path ([Environment]::GetFolderPath("CommonPrograms")) "帮扶管理系统.lnk")
  )
  $shell = New-Object -ComObject WScript.Shell
  foreach ($lnkPath in $targets) {
    $lnk = $shell.CreateShortcut($lnkPath)
    $lnk.TargetPath = $exe
    $lnk.WorkingDirectory = $InstallDir
    $lnk.IconLocation = $iconLoc
    $lnk.Description = "帮扶管理系统 - 贵州省版 Standalone桌面应用"
    $lnk.Save()
    Ok "快捷方式已重建：$lnkPath（图标 $iconLoc）"
  }
  if (-not (Test-Path -LiteralPath $ico)) {
    Warn "安装目录缺少 app-circle.ico，快捷方式回退到 exe 内嵌图标；建议重装或从安装包补回该文件"
  }
}

# ── 4. 刷新图标缓存 ───────────────────────────────────────────────────
Start-Process -FilePath (Join-Path $env:SystemRoot "System32\ie4uinit.exe") -ArgumentList "-show" -WindowStyle Hidden -Wait -ErrorAction SilentlyContinue
if (-not ("Shell32Notify" -as [type])) {
  Add-Type -Namespace Win32 -Name Shell32Notify -MemberDefinition @'
[System.Runtime.InteropServices.DllImport("shell32.dll")]
public static extern void SHChangeNotify(int eventId, uint flags, System.IntPtr item1, System.IntPtr item2);
'@
}
[Win32.Shell32Notify]::SHChangeNotify(0x08000000, 0x0000, [IntPtr]::Zero, [IntPtr]::Zero)
Ok "图标缓存已刷新（若桌面仍显示旧图标，注销一次或按 F5）"

# ── 5. 结果核验 ───────────────────────────────────────────────────────
$sig = Get-AuthenticodeSignature -LiteralPath $exe
Info ("主程序签名状态：{0}（{1}）" -f $sig.Status, $sig.StatusMessage)
if ($sig.Status -eq "Valid") { Ok "发布者已验证，后续不再提示「未知发布者」" }
else {
  Warn "签名仍未受信：请确认第 1 步已成功导入 Root/TrustedPublisher；证书轮换后需导入新 .cer"
}
if ($sig.Status -eq "Valid") {
  Info "完成。双击桌面图标应可直接打开，且不再提示未知发布者。"
} else {
  Warn "证书未生效：双击仍可能提示「未知发布者」（图标与下载标记已修复）。"
}
