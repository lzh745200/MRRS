# -*- coding: utf-8 -*-
# 安装后助手（Windows）：解除「下载标记」+ 版本化图标 + 重建快捷方式 + 刷新图标缓存。
#
# 为什么需要（2026-11-22 复盘）：
#  1) 现场常把安装包/安装目录从 GitHub、网盘、共享盘或 U 盘拷到目标机，文件带
#     Zone.Identifier（"下载标记"），双击会先弹「打开文件 - 安全警告」。
#  2) **图标白纸的真正成因**：Windows 图标缓存按"路径"记账。升级后 exe 图标已换新，
#     但 Explorer 仍复用旧的空白缓存条目；而提权安装进程里调 ie4uinit 常被拒
#     （0x80070522「客户端没有所需的特权」）或静默无效（实测 install-post.log）。
#     因此这里不再指望"刷新缓存"，而是把图标换成**带时间戳的新文件名**——
#     缓存键必然变化，Explorer 只能重新提取，不依赖任何缓存接口。
#  3) 同时逐项发 SHCNE_UPDATEITEM（ASSOCCHANGED 不会清单项缓存）。
#
# 本脚本幂等、永不失败（异常一律吞掉），由安装器 customInstall 以
# -ExecutionPolicy Bypass 调用；组策略禁用脚本时安装器继续（退出码被忽略）。
param(
  [Parameter(Mandatory = $false)][string]$InstallDir = "",
  [Parameter(Mandatory = $false)][switch]$SkipUnblock,
  [Parameter(Mandatory = $false)][switch]$SkipIconRefresh,
  [Parameter(Mandatory = $false)][switch]$SkipShortcutRebuild
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

# Shell 通知：路径版与空版各一个声明（UPDATEITEM 需要传 lnk 路径）
function Initialize-ShellNotify {
  if (-not ("Shell32Notify2" -as [type])) {
    Add-Type -Namespace Win32 -Name Shell32Notify2 -MemberDefinition @'
[System.Runtime.InteropServices.DllImport("shell32.dll")]
public static extern void AssocChanged(int eventId, uint flags, System.IntPtr item1, System.IntPtr item2);
[System.Runtime.InteropServices.DllImport("shell32.dll", CharSet = System.Runtime.InteropServices.CharSet.Unicode)]
public static extern void UpdateItem(int eventId, uint flags, string item1, System.IntPtr item2);
'@ -ErrorAction SilentlyContinue
  }
  return ("Shell32Notify2" -as [type]) -ne $null
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

# ── 2. 版本化图标 + 重建快捷方式（绕过"按路径缓存"的空白图标）──────────
$shortcutPaths = @()
if (-not $SkipShortcutRebuild -and $InstallDir -and (Test-Path -LiteralPath $InstallDir)) {
  try {
    $exe = Join-Path $InstallDir "帮扶管理系统.exe"
    $icoSrc = Join-Path $InstallDir "resources\app-circle.ico"
    if ((Test-Path -LiteralPath $exe) -and (Test-Path -LiteralPath $icoSrc)) {
      $resourcesDir = Join-Path $InstallDir "resources"
      $stamp = Get-Date -Format "yyyyMMddHHmmss"
      $icoDst = Join-Path $resourcesDir "icon-$stamp.ico"
      Copy-Item -LiteralPath $icoSrc -Destination $icoDst -Force

      $shell = New-Object -ComObject WScript.Shell
      $targets = @(
        (Join-Path ([Environment]::GetFolderPath("CommonDesktopDirectory")) "帮扶管理系统.lnk"),
        (Join-Path ([Environment]::GetFolderPath("CommonPrograms")) "帮扶管理系统.lnk")
      )
      foreach ($lnkPath in $targets) {
        $lnk = $shell.CreateShortcut($lnkPath)
        $lnk.TargetPath = $exe
        $lnk.WorkingDirectory = $InstallDir
        # 关键：图标指向带时间戳的新文件名，缓存键变化 → 必然重新提取
        $lnk.IconLocation = "$icoDst,0"
        $lnk.Description = "帮扶管理系统 - 贵州省版 Standalone桌面应用"
        $lnk.Save()
        $shortcutPaths += $lnkPath
      }
      [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($shell)
      Write-Log "已重建快捷方式（桌面 + 开始菜单），图标=$icoDst"

      # 旧版本图标延迟清理（保留本次的新文件）；失败不影响
      Get-ChildItem -LiteralPath $resourcesDir -Filter "icon-*.ico" -ErrorAction SilentlyContinue |
        Where-Object { $_.FullName -ne $icoDst } |
        Remove-Item -Force -ErrorAction SilentlyContinue
    } else {
      Write-Log "跳过快捷方式重建：缺少主程序或 app-circle.ico（保持安装器写入的 exe 内嵌图标）"
    }
  } catch {
    Write-Log "重建快捷方式失败（忽略，回退 exe 内嵌图标）：$($_.Exception.Message)"
  }
}

# ── 3. 刷新图标缓存 ───────────────────────────────────────────────────
if (-not $SkipIconRefresh) {
  try {
    $hasNotify = Initialize-ShellNotify
    if ($hasNotify -and $shortcutPaths.Count -gt 0) {
      # 逐项通知：ASSOCCHANGED 只清通用缓存，不会让 Explorer 丢掉单条目
      foreach ($p in $shortcutPaths) {
        [Win32.Shell32Notify2]::UpdateItem(0x00002000, 0x0005, $p, [IntPtr]::Zero)  # SHCNE_UPDATEITEM + SHCNF_PATHW
      }
      Write-Log "已对 $($shortcutPaths.Count) 个快捷方式发出 SHCNE_UPDATEITEM"
    }

    # Win10 1703+ 支持 -ClearIconCache；老系统会返回非 0，忽略即可
    $ie4 = Join-Path $env:SystemRoot "System32\ie4uinit.exe"
    if (Test-Path -LiteralPath $ie4) {
      Start-Process -FilePath $ie4 -ArgumentList "-ClearIconCache" -WindowStyle Hidden -Wait -ErrorAction SilentlyContinue
      Start-Process -FilePath $ie4 -ArgumentList "-show" -WindowStyle Hidden -Wait -ErrorAction SilentlyContinue
      Write-Log "已执行 ie4uinit.exe -ClearIconCache / -show（提权会话可能被拒，失败不影响上面的版本化图标方案）"
    }

    if ($hasNotify) {
      [Win32.Shell32Notify2]::AssocChanged(0x08000000, 0x0000, [IntPtr]::Zero, [IntPtr]::Zero)
      Write-Log "已通知外壳刷新图标（SHCNE_ASSOCCHANGED）"
    }
  } catch {
    Write-Log "刷新图标缓存失败（忽略）：$($_.Exception.Message)"
  }
}

Write-Log "post-install 完成"
exit 0
