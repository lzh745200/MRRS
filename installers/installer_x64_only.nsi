; 帮扶管理信息系统 — Windows x64 (64-bit) 安装脚本 (NSIS)
; 独立 x64 安装包，包含完整运行时

!include "MUI2.nsh"
!include "x64.nsh"

!define PRODUCT_NAME "帮扶管理信息系统"
!define PRODUCT_NAME_EN "AssistanceManagementSystem"
!define PRODUCT_VERSION "1.10.0"
!define PRODUCT_PUBLISHER "专项乡村振兴"

SetCompressor /SOLID lzma
SetCompressorDictSize 64
RequestExecutionLevel admin
Name "${PRODUCT_NAME} ${PRODUCT_VERSION} (64-bit)"
OutFile "..\dist\windows\${PRODUCT_NAME}_${PRODUCT_VERSION}_win_x64.exe"
InstallDir "$PROGRAMFILES64\${PRODUCT_NAME}"

!define MUI_ABORTWARNING
!define MUI_ICON "..\resources\icons\app.ico"
!define MUI_UNICON "..\resources\icons\app.ico"
!define MUI_WELCOMEPAGE_TITLE "${PRODUCT_NAME} 安装向导 (64-bit)"
!define MUI_WELCOMEPAGE_TEXT "本向导将引导您完成 ${PRODUCT_NAME} ${PRODUCT_VERSION} (64位版本) 的安装。$\r$\n$\r$\n系统自带全部运行时环境，无需单独安装 Python、Node.js 或其他依赖。"

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

!insertmacro MUI_LANGUAGE "SimpChinese"

Section "Install"
  SetOutPath "$INSTDIR"

  DetailPrint "正在安装后端服务 (64-bit)..."
  File "..\backend\dist\assistance-management-backend-x64.exe"
  Rename "$INSTDIR\assistance-management-backend-x64.exe" "$INSTDIR\assistance-management-backend.exe"

  DetailPrint "正在安装前端界面..."
  SetOutPath "$INSTDIR\resources\frontend"
  File /r "..\resources\frontend\*.*"
  SetOutPath "$INSTDIR"

  File "..\dist\windows\package\launch.py"
  File "..\.env.example"
  File "..\build-scripts\build-config.json"

  CreateDirectory "$INSTDIR\data"
  CreateDirectory "$INSTDIR\logs"
  CreateDirectory "$INSTDIR\uploads"
  CreateDirectory "$INSTDIR\exports"
  CreateDirectory "$INSTDIR\backups"

  CreateShortCut "$DESKTOP\${PRODUCT_NAME}.lnk" "$INSTDIR\assistance-management-backend.exe"
  CreateDirectory "$SMPROGRAMS\${PRODUCT_NAME}"
  CreateShortCut "$SMPROGRAMS\${PRODUCT_NAME}\${PRODUCT_NAME}.lnk" "$INSTDIR\assistance-management-backend.exe"
  CreateShortCut "$SMPROGRAMS\${PRODUCT_NAME}\卸载.lnk" "$INSTDIR\uninst.exe"

  WriteUninstaller "$INSTDIR\uninst.exe"
  WriteRegStr HKLM "Software\${PRODUCT_NAME_EN}" "InstallDir" "$INSTDIR"
  WriteRegStr HKLM "Software\${PRODUCT_NAME_EN}" "Version" "${PRODUCT_VERSION}"
  WriteRegStr HKLM "Software\${PRODUCT_NAME_EN}" "Arch" "x64"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME_EN}" "DisplayName" "${PRODUCT_NAME} (64-bit)"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME_EN}" "UninstallString" "$INSTDIR\uninst.exe"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME_EN}" "DisplayVersion" "${PRODUCT_VERSION}"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME_EN}" "Publisher" "${PRODUCT_PUBLISHER}"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME_EN}" "DisplayIcon" "$INSTDIR\assistance-management-backend.exe"
  WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME_EN}" "NoModify" 1
  WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME_EN}" "NoRepair" 1
SectionEnd

Section "Uninstall"
  MessageBox MB_YESNO|MB_ICONQUESTION "是否保留数据库和上传文件？$\r$\n$\r$\n[是] 保留数据（重新安装后可继续使用）$\r$\n[否] 彻底删除所有文件" IDYES KeepData
  RMDir /r "$INSTDIR"
  Goto Done
  KeepData:
  RMDir /r "$INSTDIR\resources"
  RMDir /r "$INSTDIR\logs"
  Delete "$INSTDIR\*.exe"
  Delete "$INSTDIR\*.dll"
  Delete "$INSTDIR\*.py"
  Delete "$INSTDIR\*.json"
  Delete "$INSTDIR\*.txt"
  Done:
  Delete "$DESKTOP\${PRODUCT_NAME}.lnk"
  RMDir /r "$SMPROGRAMS\${PRODUCT_NAME}"
  DeleteRegKey HKLM "Software\${PRODUCT_NAME_EN}"
  DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME_EN}"
SectionEnd
