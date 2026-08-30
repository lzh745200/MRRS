; ============================================================================
; electron-builder NSIS 钩子脚本
; ----------------------------------------------------------------------------
; 通过 package.json build.nsis.include 注入到 electron-builder 生成的 NSIS
; 安装脚本中，实现以下功能：
;   1. 安装前终止旧进程（升级覆盖安装场景，避免文件占用）
;   2. 校验并静默安装 VC++ Redistributable（双保险 Layer 2；Layer 1 由
;      PyInstaller 自动捆绑 vcruntime140.dll 等核心 DLL）
;   3. 创建桌面快捷方式（使用圆形图标）
;   4. 卸载前终止运行进程（避免卸载时文件占用导致失败）
;   5. 卸载时询问是否删除 %LOCALAPPDATA%\bumofu-assistance\ 用户数据目录
;   6. 卸载时清理桌面快捷方式
;
; NSIS 字符串转义铁律（v1.11.0 安装失败复盘，2026-08-30）：
;   NSIS 对双引号字符串做 C 风格转义：\r \n \t \v \" \\ 等会被真实转换。
;   路径中的反斜杠必须写成 \\，否则 \resources → CR+esources、
;   \vcredist → VT+credist，静默损坏传给 PowerShell/exec 的路径
;   （初版即因此让 Get-FileHash 恒定报错，被误判为"哈希不匹配"中止安装）。
;   修改本文件时逐行检查所有 \ 的意图。
;
; 说明：
;   - $INSTDIR 由 electron-builder 设置为安装目录（Program Files\帮扶管理系统）
;   - $LOCALAPPDATA 为 NSIS 内置变量，等于 %LOCALAPPDATA%
;   - customInstall / customUnInstall 是 electron-builder 内置钩子宏
; ============================================================================

; ----------------------------------------------------------------------------
; VC++ Redistributable 供应链钉扎（单一事实源）
; ----------------------------------------------------------------------------
; 下方 URL/SHA256 同时被 scripts/build/fetch_vcredist.ps1 解析（构建期下载
; 校验）与本钩子使用（安装期校验），修改任一常量必须同步两处语义：
;   - 构建期：从 URL 下载后哈希不匹配 → 构建失败
;   - 安装期：内置二进制哈希不匹配 → 弹窗中止安装
; 微软会在 aka.ms 短链上原地更新二进制版本，届时构建期校验将失败——这是
; 有意的供应链防线；人工确认新版本无异常后更新此处的 SHA256 即可恢复。
!ifndef VCREDIST_X64_URL
!define VCREDIST_X64_URL "https://aka.ms/vs/17/release/vc_redist.x64.exe"
!endif
!ifndef VCREDIST_X64_SHA256
!define VCREDIST_X64_SHA256 "CC0FF0EB1DC3F5188AE6300FAEF32BF5BEEBA4BDD6E8E445A9184072096B713B"
!endif
!ifndef VCREDIST_X86_URL
!define VCREDIST_X86_URL "https://aka.ms/vs/17/release/vc_redist.x86.exe"
!endif
!ifndef VCREDIST_X86_SHA256
!define VCREDIST_X86_SHA256 "0C09F2611660441084CE0DF425C51C11E147E6447963C3690F97E0B25C55ED64"
!endif

; ----------------------------------------------------------------------------
; 安装钩子：终止旧进程 + VC++ 校验安装 + 创建桌面快捷方式
; ----------------------------------------------------------------------------
!macro customInstall
  ; 安装前终止可能正在运行的旧进程（升级场景）
  ; taskkill 在进程不存在时返回非零退出码，Pop 丢弃即可，不阻断安装
  nsExec::Exec 'taskkill /F /IM "帮扶管理系统.exe" /IM "assistance-backend.exe"'
  Pop $0

  ; 静默安装 VC++ Redistributable（双保险 Layer 2，先校验 SHA256）
  ; 根据实际存在的安装器文件判断架构（CI 仅放置匹配架构的 vc_redist）
  ;
  ; 安装期校验三态语义（v1.11.0 真机故障复盘，2026-08-30）：
  ;   exit 0 = 哈希匹配 → 静默安装
  ;   exit 1 = 哈希确证不匹配（PowerShell 正常运行且结果不同）→ 真实损坏/
  ;            篡改信号 → 弹窗中止安装
  ;   exit 3 / nsExec error = 校验基础设施不可用（无 PowerShell/被安全软件
  ;            或策略阻断/PS 过旧无 Get-FileHash）→ 不执行无法校验的二进制、
  ;            跳过 redist 安装但不阻断部署 —— 应用由 Layer 1（PyInstaller
  ;            捆绑 vcruntime DLL）覆盖，构建期拉取另有钉扎校验。
  IfFileExists "$INSTDIR\\resources\\vcredist\\vc_redist.x64.exe" 0 try_x86_redist
    DetailPrint "正在校验 VC++ Redistributable (x64) 完整性..."
    ; 校验脚本以文件形式写出后 -File 执行 —— 不用 -Command 行内脚本：
    ; 行内脚本要过 NSIS/命令行/PS 多层解析，极易损坏（v1.11.0 教训）
    FileOpen $1 "$INSTDIR\\verify_x64.ps1" w
    FileWrite $1 "$$ErrorActionPreference = 'Stop'$\n"
    FileWrite $1 "try {$\n"
    FileWrite $1 "  $$h = (Get-FileHash -ErrorAction Stop -Algorithm SHA256 -LiteralPath '$INSTDIR\\resources\\vcredist\\vc_redist.x64.exe').Hash$\n"
    FileWrite $1 "  if ($$h -ieq '${VCREDIST_X64_SHA256}') { exit 0 } else { exit 1 }$\n"
    FileWrite $1 "} catch {$\n"
    FileWrite $1 "  $$_ | Out-File -LiteralPath '$INSTDIR\\verify_x64_err.txt'$\n"
    FileWrite $1 "  exit 3$\n"
    FileWrite $1 "}$\n"
    FileClose $1
    nsExec::Exec 'powershell -NoProfile -ExecutionPolicy Bypass -File "$INSTDIR\\verify_x64.ps1"'
    Pop $0
    StrCmp $0 "0" vcredist_x64_ok
    StrCmp $0 "1" vcredist_hash_fail
    DetailPrint "警告：完整性校验工具不可用，跳过 VC++ (x64) 安装期校验及其安装（应用内置运行时 DLL 兜底）"
    Goto try_x86_redist
  vcredist_x64_ok:
    DetailPrint "正在安装 VC++ Redistributable (x64)..."
    nsExec::Exec '"$INSTDIR\\resources\\vcredist\\vc_redist.x64.exe" /install /quiet /norestart'
    Pop $0
    Goto vcredist_done
  try_x86_redist:
  IfFileExists "$INSTDIR\\resources\\vcredist\\vc_redist.x86.exe" 0 vcredist_done
    DetailPrint "正在校验 VC++ Redistributable (x86) 完整性..."
    FileOpen $1 "$INSTDIR\\verify_x86.ps1" w
    FileWrite $1 "$$ErrorActionPreference = 'Stop'$\n"
    FileWrite $1 "try {$\n"
    FileWrite $1 "  $$h = (Get-FileHash -ErrorAction Stop -Algorithm SHA256 -LiteralPath '$INSTDIR\\resources\\vcredist\\vc_redist.x86.exe').Hash$\n"
    FileWrite $1 "  if ($$h -ieq '${VCREDIST_X86_SHA256}') { exit 0 } else { exit 1 }$\n"
    FileWrite $1 "} catch {$\n"
    FileWrite $1 "  $$_ | Out-File -LiteralPath '$INSTDIR\\verify_x86_err.txt'$\n"
    FileWrite $1 "  exit 3$\n"
    FileWrite $1 "}$\n"
    FileClose $1
    nsExec::Exec 'powershell -NoProfile -ExecutionPolicy Bypass -File "$INSTDIR\\verify_x86.ps1"'
    Pop $0
    StrCmp $0 "0" vcredist_x86_ok
    StrCmp $0 "1" vcredist_hash_fail
    DetailPrint "警告：完整性校验工具不可用，跳过 VC++ (x86) 安装期校验及其安装（应用内置运行时 DLL 兜底）"
    Goto vcredist_done
  vcredist_x86_ok:
    DetailPrint "正在安装 VC++ Redistributable (x86)..."
    nsExec::Exec '"$INSTDIR\\resources\\vcredist\\vc_redist.x86.exe" /install /quiet /norestart'
    Pop $0
    Goto vcredist_done
  vcredist_hash_fail:
    MessageBox MB_ICONSTOP "VC++ Redistributable 完整性校验失败（SHA256 不匹配）。$\n$\n安装包可能已损坏或被篡改，安装已中止。请从官方渠道重新获取安装包。" /SD IDOK
    Abort
  vcredist_done:
  ; 清理一次性校验脚本（err 文件保留作诊断证据；减少 Program Files 下的 .ps1 暴露面）
  Delete "$INSTDIR\\verify_x64.ps1"
  Delete "$INSTDIR\\verify_x86.ps1"

  ; ─── 创建桌面快捷方式（圆形图标）───
  ; electron-builder 默认创建开始菜单快捷方式，但桌面快捷方式可能因
  ; oneClick=false + 用户取消而未创建。此处强制创建桌面快捷方式。
  IfFileExists "$INSTDIR\\帮扶管理系统.exe" 0 skip_desktop_shortcut
    ; 尝试使用独立 ICO 文件，回退到 EXE 内嵌图标
    IfFileExists "$INSTDIR\\resources\\app-circle.ico" 0 use_exe_icon
      CreateShortCut "$DESKTOP\\帮扶管理系统.lnk" "$INSTDIR\\帮扶管理系统.exe" "" "$INSTDIR\\resources\\app-circle.ico" 0
      Goto shortcut_created
    use_exe_icon:
      CreateShortCut "$DESKTOP\\帮扶管理系统.lnk" "$INSTDIR\\帮扶管理系统.exe" "" "$INSTDIR\\帮扶管理系统.exe" 0
    shortcut_created:
    DetailPrint "已创建桌面快捷方式（圆形图标）"
  skip_desktop_shortcut:
!macroend

; ----------------------------------------------------------------------------
; 卸载钩子：终止进程 + 删除桌面快捷方式 + 询问删除用户数据
; ----------------------------------------------------------------------------
!macro customUnInstall
  ; 卸载前终止运行进程，避免卸载时文件占用导致卸载失败
  nsExec::Exec 'taskkill /F /IM "帮扶管理系统.exe" /IM "assistance-backend.exe"'
  Pop $0

  ; 删除桌面快捷方式
  IfFileExists "$DESKTOP\\帮扶管理系统.lnk" 0 skip_del_desktop
    Delete "$DESKTOP\\帮扶管理系统.lnk"
    DetailPrint "已删除桌面快捷方式"
  skip_del_desktop:

  ; 询问用户是否删除用户数据目录（含 SQLite 数据库、上传文件、日志等）
  ; deleteAppDataOnUninstall=false（package.json）保留 userData 小文件，
  ; 此处单独询问大文件数据目录 %LOCALAPPDATA%\bumofu-assistance\
  ; /SD IDNO + MB_DEFBUTTON2（W6-T10）：静默卸载（企业批量部署）默认保留用户数据
  MessageBox MB_YESNO|MB_ICONQUESTION|MB_DEFBUTTON2 "是否同时删除用户数据（包含数据库）?$\n$\n位置: $LOCALAPPDATA\\bumofu-assistance\\" /SD IDNO IDNO keep_user_data
    RMDir /r /REBOOTOK "$LOCALAPPDATA\\bumofu-assistance"
    DetailPrint "已删除用户数据目录: $LOCALAPPDATA\\bumofu-assistance"
  keep_user_data:
!macroend
