# -*- coding: utf-8 -*-
# 安装后助手：解除「下载标记」(MOTW) + 刷新 Windows 图标缓存。
#
# 为什么需要：
#  1) 现场常见做法是把安装包/整个安装目录从 GitHub、网盘、共享盘或 U 盘拷到目标机。
#     这类文件带 NTFS 备用数据流 Zone.Identifier（俗称"下载标记"/MOTW），
#     双击 exe 会先弹「打开文件 - 安全警告：无法验证发布者」，与签名是否有效无关。
#  2) Windows 的图标缓存（IconCache.db / thumbcache）是增量的：安装完成后立刻打开
#     资源管理器，新快捷方式常显示为白纸图标，按 F5 或重启才恢复。
#
# 本脚本幂等、永不失败（任何异常都吞掉并继续），由安装器的 customInstall 以
# -ExecutionPolicy Bypass 调用；企业组策略禁用脚本时安装器仍会继续（退出码被忽略）。
param(
  [Parameter(Mandatory = $false)][string]$InstallDir = "",
  [Parameter(Mandatory = $false)][switch]$SkipUnblock,
  [Parameter(Mandatory = $false)][switch]$SkipIconRefresh
)

$ErrorActionPreference = "SilentlyContinue"
$ProgressPreference = "SilentlyContinue"

function Write-Log([string]$msg) {
  $line = "[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $msg
  Write-Output $line
  if ($InstallDir -and (Test-Path -LiteralPath $InstallDir)) {
    # 安装目录可能因权限不可写：失败静默忽略，绝不阻断安装
    Add-Content -LiteralPath (Join-Path $InstallDir "install-post.log") -Value $line -Encoding UTF8
  }
}

Write-Log "post-install 开始，InstallDir=$InstallDir"

# ── 1. 解除下载标记 ───────────────────────────────────────────────────
if (-not $SkipUnblock -and $InstallDir -and (Test-Path -LiteralPath $InstallDir)) {
  $unblocked = 0
  try {
    $files = Get-ChildItem -LiteralPath $InstallDir -Recurse -File -Force -ErrorAction SilentlyContinue |
             Where-Object { $_.Extension -in @(".exe", ".dll", ".ico", ".lnk", ".ps1", ".bat", ".cmd") }
    foreach ($f in $files) {
      try {
        # 只有存在 Zone.Identifier 才动手，避免无谓的写操作
        $zone = Get-Item -LiteralPath $f.FullName -Stream Zone.Identifier -ErrorAction SilentlyContinue
        if ($null -ne $zone) {
          Unblock-File -LiteralPath $f.FullName -ErrorAction SilentlyContinue
          $unblocked++
        }
      } catch { }
    }
    Write-Log "解除下载标记：$unblocked 个文件（共扫描 $($files.Count) 个可执行类文件）"
  } catch {
    Write-Log "解除下载标记失败（忽略）：$($_.Exception.Message)"
  }
}

# ── 2. 刷新图标缓存 ───────────────────────────────────────────────────
if (-not $SkipIconRefresh) {
  try {
    # Win10/11 官方口径：ie4uinit -show 重建当前用户的图标缓存
    $ie4 = Join-Path $env:SystemRoot "System32\ie4uinit.exe"
    if (Test-Path -LiteralPath $ie4) {
      Start-Process -FilePath $ie4 -ArgumentList "-show" -WindowStyle Hidden -Wait -ErrorAction SilentlyContinue
      Write-Log "已执行 ie4uinit.exe -show"
    }
    # 再通知外壳「关联/图标已变更」，让资源管理器立即重读快捷方式图标
    if (-not ("Shell32Notify" -as [type])) {
      Add-Type -Namespace Win32 -Name Shell32Notify -MemberDefinition @'
[System.Runtime.InteropServices.DllImport("shell32.dll")]
public static extern void SHChangeNotify(int eventId, uint flags, System.IntPtr item1, System.IntPtr item2);
'@ -ErrorAction SilentlyContinue
    }
    [Win32.Shell32Notify]::SHChangeNotify(0x08000000, 0x0000, [IntPtr]::Zero, [IntPtr]::Zero)
    Write-Log "已通知外壳刷新图标（SHCNE_ASSOCCHANGED）"
  } catch {
    Write-Log "刷新图标缓存失败（忽略）：$($_.Exception.Message)"
  }
}

Write-Log "post-install 完成"
exit 0
