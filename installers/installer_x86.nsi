; 帮扶管理信息系统 — Windows x86 (32-bit) 安装脚本 (NSIS)
; 自带完整运行时：Python + VC++ Redist + 后端 + 前端 + 数据库

!include "MUI2.nsh"
!include "FileFunc.nsh"
!insertmacro GetParameters
!insertmacro GetOptions

!define PRODUCT_NAME "帮扶管理信息系统"
!define PRODUCT_NAME_EN "AssistanceManagementInformation"
!define PRODUCT_VERSION "1.10.0"
!define PRODUCT_PUBLISHER "Assistance Management Information"
!define PRODUCT_DIR_REGKEY "Software\${PRODUCT_NAME_EN}"
!define PRODUCT_UNINST_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME_EN}"

!define INSTALL_DIR "$PROGRAMFILES\${PRODUCT_NAME}"

SetCompressor /SOLID lzma
SetCompressorDictSize 64
RequestExecutionLevel admin
Name "${PRODUCT_NAME} ${PRODUCT_VERSION} (32-bit)"
OutFile "..\dist\windows\${PRODUCT_NAME}-${PRODUCT_VERSION}-x86-Setup.exe"
InstallDir "${INSTALL_DIR}"
BrandingText "${PRODUCT_NAME} (32-bit)"

!define MUI_ABORTWARNING
!define MUI_ICON "..\resources\icons\app.ico"
!define MUI_UNICON "..\resources\icons\app.ico"
!define MUI_WELCOMEPAGE_TITLE "${PRODUCT_NAME} 安装向导 (32-bit)"
!define MUI_WELCOMEPAGE_TEXT "本向导将引导您完成 ${PRODUCT_NAME} ${PRODUCT_VERSION} (32位版本) 的安装。$\r$\n$\r$\n系统自带全部运行时环境，无需单独安装 Python、Node.js 或其他依赖。$\r$\n$\r$\n请关闭所有其他应用程序后继续。"
!define MUI_FINISHPAGE_TITLE "安装完成"
!define MUI_FINISHPAGE_RUN "$INSTDIR\${PRODUCT_NAME_EN}.exe"
!define MUI_FINISHPAGE_RUN_TEXT "立即启动 ${PRODUCT_NAME}"
!define MUI_FINISHPAGE_SHOWREADME_FUNCTION CreateDesktopShortcut

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "..\LICENSE"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_UNPAGE_FINISH
!insertmacro MUI_LANGUAGE "SimpChinese"

Section "Install"
  SetOutPath "$INSTDIR"

  ; 1. VC++ Redistributable (x86)
  DetailPrint "正在安装 VC++ 运行时 (32-bit)..."
  IfFileExists "$INSTDIR\resources\vcredist\vc_redist.x86.exe" 0 SkipVC
  nsExec::ExecToLog '"$INSTDIR\resources\vcredist\vc_redist.x86.exe" /install /quiet /norestart'
  SkipVC:

  ; 2. 后端
  DetailPrint "正在安装后端服务..."
  File /r "..\backend\dist\assistance-management-backend-x86\*"
  File "..\backend\dist\assistance-management-backend-x86.exe"

  ; 3. 前端
  DetailPrint "正在安装前端界面..."
  SetOutPath "$INSTDIR\resources\frontend"
  File /r "..\resources\frontend\*"

  ; 4. 配置和脚本
  SetOutPath "$INSTDIR"
  File "..\launch.py"
  File "..\.env.example"
  File "..\build-scripts\build-config.json"

  ; 5. 数据目录
  CreateDirectory "$INSTDIR\data"
  CreateDirectory "$INSTDIR\logs"
  CreateDirectory "$INSTDIR\uploads"
  CreateDirectory "$INSTDIR\exports"
  CreateDirectory "$INSTDIR\backups"

  ; 6. 注册表
  WriteRegStr HKLM "${PRODUCT_DIR_REGKEY}" "" "$INSTDIR"
  WriteRegStr HKLM "${PRODUCT_UNINST_KEY}" "DisplayName" "${PRODUCT_NAME} (32-bit)"
  WriteRegStr HKLM "${PRODUCT_UNINST_KEY}" "UninstallString" "$INSTDIR\uninst.exe"
  WriteRegStr HKLM "${PRODUCT_UNINST_KEY}" "DisplayVersion" "${PRODUCT_VERSION}"
  WriteRegStr HKLM "${PRODUCT_UNINST_KEY}" "Publisher" "${PRODUCT_PUBLISHER}"
  WriteRegDWORD HKLM "${PRODUCT_UNINST_KEY}" "NoModify" 1
  WriteRegDWORD HKLM "${PRODUCT_UNINST_KEY}" "NoRepair" 1

  WriteUninstaller "$INSTDIR\uninst.exe"
  CreateDirectory "$SMPROGRAMS\${PRODUCT_NAME}"
  CreateShortCut "$SMPROGRAMS\${PRODUCT_NAME}\${PRODUCT_NAME} (32-bit).lnk" "$INSTDIR\${PRODUCT_NAME_EN}.exe"
  CreateShortCut "$SMPROGRAMS\${PRODUCT_NAME}\卸载.lnk" "$INSTDIR\uninst.exe"
SectionEnd

Function CreateDesktopShortcut
  CreateShortCut "$DESKTOP\${PRODUCT_NAME}.lnk" "$INSTDIR\${PRODUCT_NAME_EN}.exe"
FunctionEnd

Section "Uninstall"
  MessageBox MB_YESNO|MB_ICONQUESTION "是否保留数据库和上传文件？$\r$\n选择"是"保留，选择"否"彻底删除" IDYES KeepData
  RMDir /r "$INSTDIR\resources"
  RMDir /r "$INSTDIR\logs"
  Delete "$INSTDIR\*.exe"
  Delete "$INSTDIR\*.dll"
  Delete "$INSTDIR\*.pyd"
  Delete "$INSTDIR\*.py"
  Delete "$INSTDIR\*.json"
  Delete "$INSTDIR\*.bat"
  RMDir /r "$INSTDIR"
  KeepData:
  RMDir /r "$INSTDIR\resources"
  RMDir /r "$INSTDIR\logs"
  Delete "$INSTDIR\*.exe"
  Delete "$INSTDIR\*.dll"
  Delete "$INSTDIR\*.pyd"
  Delete "$INSTDIR\*.py"
  Delete "$INSTDIR\*.json"
  Delete "$INSTDIR\*.bat"
  Delete "$DESKTOP\${PRODUCT_NAME}.lnk"
  RMDir /r "$SMPROGRAMS\${PRODUCT_NAME}"
  DeleteRegKey HKLM "${PRODUCT_UNINST_KEY}"
  DeleteRegKey HKLM "${PRODUCT_DIR_REGKEY}"
SectionEnd
