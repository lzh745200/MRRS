@echo off
setlocal EnableExtensions
rem Double-click launcher for the MRRS NSIS installer.
rem NSIS reads %TEMP% before any script runs; a stale/read-only/removed temp
rem directory makes setup fail with "Error writing temporary file".
rem This launcher chooses a freshly-created writable temp and then starts setup.
set "MRRS_TEMP=%LOCALAPPDATA%\Temp\MRRS-Setup"
if not defined LOCALAPPDATA set "MRRS_TEMP=%USERPROFILE%\AppData\Local\Temp\MRRS-Setup"
if not exist "%MRRS_TEMP%" mkdir "%MRRS_TEMP%" >nul 2>&1
> "%MRRS_TEMP%\.mrrs-write-probe" echo ok 2>nul
if errorlevel 1 (
  set "MRRS_TEMP=%SystemRoot%\Temp\MRRS-Setup"
  if not exist "%MRRS_TEMP%" mkdir "%MRRS_TEMP%" >nul 2>&1
  > "%MRRS_TEMP%\.mrrs-write-probe" echo ok 2>nul
)
if errorlevel 1 (
  echo [MRRS] No writable temp directory found. Fix TEMP or use MRRS-Installer-Helper.ps1 -TempDir.
  pause
  exit /b 1
)
del /q "%MRRS_TEMP%\.mrrs-write-probe" >nul 2>&1
set "TEMP=%MRRS_TEMP%"
set "TMP=%MRRS_TEMP%"
set "SETUP="
for %%F in ("%~dp0MRRS-Setup-*-x64.exe") do if not defined SETUP set "SETUP=%%~fF"
if not defined SETUP for %%F in ("%~dp0MRRS-Setup-*.exe") do if not defined SETUP set "SETUP=%%~fF"
if not defined SETUP (
  echo [MRRS] MRRS-Setup-*.exe not found next to this launcher.
  pause
  exit /b 1
)
echo [MRRS] TEMP=%TEMP%
echo [MRRS] Starting %SETUP%
rem Prefer the PowerShell helper when present: it adds the free-space check
rem (the actual cause of NSIS "Error creating mmap ... nsc*.tmp" is often a
rem writable but nearly-full TEMP, not a missing one).
if exist "%~dp0MRRS-Installer-Helper.ps1" (
  powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0MRRS-Installer-Helper.ps1" -Installer "%SETUP%" -TempDir "%MRRS_TEMP%"
  exit /b %ERRORLEVEL%
)
start "" /wait "%SETUP%"
exit /b %ERRORLEVEL%
