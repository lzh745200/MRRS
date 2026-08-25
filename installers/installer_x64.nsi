; 帮扶管理信息系统 — Windows 集成安装脚本 (x64 + x86)
!include "MUI2.nsh"
!include "x64.nsh"

!define PRODUCT_NAME "AssistanceSystem"
!define PRODUCT_DISPLAY "帮扶管理信息系统"
!define PRODUCT_VERSION "1.10.0"

SetCompressor /SOLID lzma
SetCompressorDictSize 64
RequestExecutionLevel admin
Name "${PRODUCT_DISPLAY} ${PRODUCT_VERSION}"
OutFile "..\dist\windows\${PRODUCT_DISPLAY}-${PRODUCT_VERSION}-Setup.exe"
InstallDir "$PROGRAMFILES64\${PRODUCT_DISPLAY}"

!define MUI_ABORTWARNING
!define MUI_ICON "..\resources\icons\app.ico"
!define MUI_UNICON "..\resources\icons\app.ico"

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "SimpChinese"

Function .onInit
  ; Auto-detect install dir for x86 systems
  ${IfNot} ${RunningX64}
    StrCpy $INSTDIR "$PROGRAMFILES\${PRODUCT_DISPLAY}"
  ${EndIf}
FunctionEnd

Section "Install"
  SetOutPath "$INSTDIR"

  ${If} ${RunningX64}
    DetailPrint "安装 64-bit 版本..."
    File /r "..\backend\dist\assistance-management-backend-x64.exe"
    Rename "$INSTDIR\assistance-management-backend-x64.exe" "$INSTDIR\assistance-management-backend.exe"
  ${Else}
    DetailPrint "安装 32-bit 版本..."
    File /r "..\backend\dist\assistance-management-backend-x86.exe"
    Rename "$INSTDIR\assistance-management-backend-x86.exe" "$INSTDIR\assistance-management-backend.exe"
  ${EndIf}

  File "..\dist\windows\package\launch.py"

  DetailPrint "安装前端界面..."
  SetOutPath "$INSTDIR\resources\frontend"
  File /r "..\resources\frontend\*.*"
  SetOutPath "$INSTDIR"

  CreateDirectory "$INSTDIR\data"
  CreateDirectory "$INSTDIR\logs"
  CreateDirectory "$INSTDIR\uploads"
  CreateDirectory "$INSTDIR\exports"
  CreateDirectory "$INSTDIR\backups"

  CreateShortCut "$DESKTOP\${PRODUCT_DISPLAY}.lnk" "$INSTDIR\assistance-management-backend.exe"
  CreateDirectory "$SMPROGRAMS\${PRODUCT_DISPLAY}"
  CreateShortCut "$SMPROGRAMS\${PRODUCT_DISPLAY}\${PRODUCT_DISPLAY}.lnk" "$INSTDIR\assistance-management-backend.exe"
  CreateShortCut "$SMPROGRAMS\${PRODUCT_DISPLAY}\卸载.lnk" "$INSTDIR\uninst.exe"

  WriteUninstaller "$INSTDIR\uninst.exe"
  WriteRegStr HKLM "Software\${PRODUCT_NAME}" "" "$INSTDIR"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}" "DisplayName" "${PRODUCT_DISPLAY}"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}" "UninstallString" "$INSTDIR\uninst.exe"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}" "DisplayVersion" "${PRODUCT_VERSION}"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}" "DisplayIcon" "$INSTDIR\assistance-management-backend.exe"
SectionEnd

Section "Uninstall"
  MessageBox MB_YESNO|MB_ICONQUESTION "是否保留数据库和上传文件？$\r$\n$\r$\n[是] 保留数据（重新安装后可继续使用）$\r$\n[否] 彻底删除" IDYES KeepData
  RMDir /r "$INSTDIR"
  Goto Done
  KeepData:
  RMDir /r "$INSTDIR\resources"
  RMDir /r "$INSTDIR\logs"
  Delete "$INSTDIR\*.exe"
  Delete "$INSTDIR\*.py"
  Done:
  Delete "$DESKTOP\${PRODUCT_DISPLAY}.lnk"
  RMDir /r "$SMPROGRAMS\${PRODUCT_DISPLAY}"
  DeleteRegKey HKLM "Software\${PRODUCT_NAME}"
  DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}"
SectionEnd
