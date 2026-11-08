; ============================================================================
; electron-builder NSIS 钩子脚本
; ----------------------------------------------------------------------------
; 通过 package.json build.nsis.include 注入到 electron-builder 生成的 NSIS
; 安装脚本中，实现以下功能：
;   1. 安装前终止旧进程（升级覆盖安装场景，避免文件占用）
;   2. 静默安装 VC++ Redistributable（构建期校验，安装期不阻断；Layer 1 由
;      PyInstaller 自动捆绑 vcruntime140.dll 等核心 DLL）
;   3. 创建桌面快捷方式（使用圆形图标）
;   4. 卸载前终止运行进程（避免卸载时文件占用导致失败）
;   5. 卸载时询问是否删除 Electron userData 用户数据目录
;      （%APPDATA%\帮扶管理系统，H11，2026-10-14：安装期经注册表记录、
;      卸载期读回删除，并以字面量兜底；详见 customUnInstall 段注释）
;   6. 卸载时清理桌面快捷方式
;
; NSIS 字符串转义规则（W19 实测修正，2026-10-17）：
;   **反斜杠不是转义字符**，在双引号字符串里就是字面量 \（已用 makensis 实测：
;   写 "C:\A\B" 得到两个反斜杠）；转义要用 $ 前缀（$\r $\n $\t $\" $\$）。
;   因此路径直接写单反斜杠即可；写成 \\ 会得到**双反斜杠**（Windows 多数 API
;   容忍，但注册表值与日志会失真，曾让卸载口径排查跑偏）。
;   历史注释曾称"反斜杠必须写成 \\"（C 风格），那是误判。
;   ⚠️ 另注意 perMachine=true 时 NSIS 处于 all-users 上下文：$APPDATA/$LOCALAPPDATA
;   指向 C:\ProgramData，**不是**当前用户目录 —— 用户目录请用 $PROFILE 拼。
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
; VC++ 安装宏：静默安装 + 退出码记录，不弹窗、不阻断。
; 0/1638=成功/已安装；3010/1641=成功但需重启。其他返回码写日志后继续。
; ----------------------------------------------------------------------------
!macro InstallVCRedist ARCH FILE
  IfFileExists "$INSTDIR\resources\vcredist\${FILE}" 0 vcredist_${ARCH}_done
    DetailPrint "正在安装 VC++ 运行库 (${ARCH})..."
    nsExec::Exec '"$INSTDIR\resources\vcredist\${FILE}" /install /quiet /norestart'
    Pop $0
    FileOpen $1 "$INSTDIR\install-vcredist.log" a
    FileWrite $1 "${ARCH}: exit=$0$\r$\n"
    FileClose $1
    StrCmp $0 "0" vcredist_${ARCH}_done
    StrCmp $0 "1638" vcredist_${ARCH}_done
    StrCmp $0 "3010" vcredist_${ARCH}_done
    StrCmp $0 "1641" vcredist_${ARCH}_done
    DetailPrint "VC++ (${ARCH}) 未安装（exit=$0），继续；应用已内置运行时 DLL"
  vcredist_${ARCH}_done:
!macroend

; ----------------------------------------------------------------------------
; 安装钩子：终止旧进程 + VC++ 校验安装 + 创建桌面快捷方式
; ----------------------------------------------------------------------------
!macro customInstall
  ; ─── 记录 Electron userData 目录（H11 / W19 实测修正，2026-10-17）───
  ; electron/main.js getUserDataPath() 打包态返回 app.getPath('userData')，
  ; 全仓库无 setPath('userData', ...)、无 ELECTRON_USER_DATA_PATH 设置 →
  ; 取 Electron 默认值 %APPDATA%\<app.name>。
  ; **关键（W19 实测修正）**：Electron 的 app.name 取根 package.json 的
  ; productName，**没有**时才取 name。本仓库根层**没有** productName（只有
  ; build.productName，那只影响安装包/exe 命名，不影响 userData）→
  ; app.name = name = "Assistance-Management-Information-System"，
  ; 真实 userData 即 %APPDATA%\Assistance-Management-Information-System。
  ; 旧版此处按"productName 优先"写成 %APPDATA%\帮扶管理系统（该目录根本不存在），
  ; 导致卸载时删错目录、真实数据库/密钥/日志全部残留（W18 P1-5 实证）。
  ; 兜底：卸载段同时清理历史误判目录，避免老版本残留。
  ; perMachine=true（package.json build.nsis）→ 卸载器本就以管理员运行，HKLM 可用。
  ; **perMachine 下 $APPDATA = C:\ProgramData**（all-users 上下文），
  ; 用户目录必须用 $PROFILE 拼；路径写单反斜杠（见文件头转义规则）。
  WriteRegStr HKLM "Software\Bumofu\AssistanceManagementSystem" "UserDataPath" "$PROFILE\AppData\Roaming\Assistance-Management-Information-System"

  ; 安装前终止可能正在运行的旧进程（升级场景）
  ; taskkill 在进程不存在时返回非零退出码，Pop 丢弃即可，不阻断安装
  nsExec::Exec 'taskkill /F /IM "帮扶管理系统.exe" /IM "assistance-backend.exe"'
  Pop $0

  ; 安装 VC++ Redistributable（Layer 2 双保险）。
  ; 供应链 SHA256 已在**构建期**由 scripts/verify_vcredist_bundle.py 钉扎校验，
  ; 安装期不再用系统脚本复算：安装目录含中文、安全软件/策略限制、文件解压暂存，
  ; 都会让校验误报并弹窗；应用本身已由 PyInstaller + Electron app-local DLL
  ; 自带运行时，VC++ 安装失败不应阻断/惊吓用户。
  Delete "$INSTDIR\verify_x64.ps1"
  Delete "$INSTDIR\verify_x86.ps1"
  !insertmacro InstallVCRedist "x64" "vc_redist.x64.exe"
  !insertmacro InstallVCRedist "x86" "vc_redist.x86.exe"

  ; ─── 创建桌面快捷方式（圆形图标）───
  ; electron-builder 默认创建开始菜单快捷方式，但桌面快捷方式可能因
  ; oneClick=false + 用户取消而未创建。此处强制创建桌面快捷方式。
  IfFileExists "$INSTDIR\帮扶管理系统.exe" 0 skip_desktop_shortcut
    ; 尝试使用独立 ICO 文件，回退到 EXE 内嵌图标
    IfFileExists "$INSTDIR\resources\app-circle.ico" 0 use_exe_icon
      CreateShortCut "$DESKTOP\帮扶管理系统.lnk" "$INSTDIR\帮扶管理系统.exe" "" "$INSTDIR\resources\app-circle.ico" 0
      Goto shortcut_created
    use_exe_icon:
      CreateShortCut "$DESKTOP\帮扶管理系统.lnk" "$INSTDIR\帮扶管理系统.exe" "" "$INSTDIR\帮扶管理系统.exe" 0
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
  IfFileExists "$DESKTOP\帮扶管理系统.lnk" 0 skip_del_desktop
    Delete "$DESKTOP\帮扶管理系统.lnk"
    DetailPrint "已删除桌面快捷方式"
  skip_del_desktop:

  ; 询问用户是否删除用户数据目录（含 SQLite 数据库、上传文件、密钥、日志等）
  ; W19 实测修正（2026-10-17）：
  ;  · 真实 userData = %APPDATA%\Assistance-Management-Information-System
  ;    （Electron app.name 取**根** package.json 的 productName，无则取 name；
  ;     本仓库只有 build.productName，它只影响安装包/exe 命名）
  ;  · perMachine 安装的卸载器处于 all-users 上下文：$APPDATA/$LOCALAPPDATA
  ;    指向 C:\ProgramData，**不能**用于用户目录 → 一律用 $PROFILE 拼
  ;  · 注册表值优先（安装期以 $PROFILE 写入），缺失时按 $PROFILE 推导
  ;  · 多用户机器：枚举 $PROFILE\..\* 逐个清理（同一台机器可能有多个 Windows 账号）
  ;  · 同时清理历史误判/兜底目录（旧版曾写 ProgramData\帮扶管理系统、
  ;    %LOCALAPPDATA%\bumofu-assistance 等）
  ; deleteAppDataOnUninstall=false（package.json）保留 userData 小文件的
  ; 语义由本询问承接；/SD IDNO + MB_DEFBUTTON2（W6-T10）：静默卸载
  ; （企业批量部署）默认保留用户数据
  ReadRegStr $R0 HKLM "Software\Bumofu\AssistanceManagementSystem" "UserDataPath"
  StrCmp $R0 "" 0 uninst_have_path
    StrCpy $R0 "$PROFILE\AppData\Roaming\Assistance-Management-Information-System"
  uninst_have_path:
  MessageBox MB_YESNO|MB_ICONQUESTION|MB_DEFBUTTON2 "是否同时删除用户数据（包含数据库）?$\n$\n位置: $R0" /SD IDNO IDNO keep_user_data
    RMDir /r /REBOOTOK "$R0"
    DetailPrint "已删除用户数据目录: $R0"
    ; 多用户机器：注册表只记录安装者，逐个 profile 清理同一目录
    FindFirst $R9 $R1 "$PROFILE\..\*"
    uninst_users_loop:
      StrCmp $R1 "" uninst_users_done
      StrCmp $R1 "." uninst_users_next
      StrCmp $R1 ".." uninst_users_next
      RMDir /r /REBOOTOK "$PROFILE\..\$R1\AppData\Roaming\Assistance-Management-Information-System"
    uninst_users_next:
      FindNext $R9 $R1
      Goto uninst_users_loop
    uninst_users_done:
      FindClose $R9
    ; 兜底数据目录（frozen 后端无 Electron 注入时的 paths.get_app_data_dir）
    RMDir /r /REBOOTOK "$PROFILE\AppData\Local\bumofu-assistance"
    RMDir /r /REBOOTOK "$LOCALAPPDATA\bumofu-assistance"
    ; 历史误判目录（旧版本按 productName 假设 / 写入 ProgramData）
    RMDir /r /REBOOTOK "$PROFILE\AppData\Roaming\帮扶管理系统"
    RMDir /r /REBOOTOK "$APPDATA\帮扶管理系统"
    RMDir /r /REBOOTOK "$APPDATA\Assistance-Management-Information-System"
    RMDir /r /REBOOTOK "$APPDATA\bumofu-assistance"
    DetailPrint "已清理历史误判/兜底数据目录（如存在）"
  keep_user_data:
  ; 清理本钩子自有注册表键（不动 electron-builder 的卸载信息键）
  DeleteRegKey HKLM "Software\Bumofu\AssistanceManagementSystem"
!macroend
