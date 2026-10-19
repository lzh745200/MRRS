# build-installer-local.ps1 — Windows x64 离线安装包本地构建链（等价 make build-win-x64）
#
# 为什么需要它：Windows 默认不带 make，且 CI 走 tag 触发；本脚本把官方构建链固化成一条命令，
# 避免每次手工敲 5 步（顺序错一步就会打出缺资源/缺后端的包）。
#
# 用法： powershell -NoProfile -ExecutionPolicy Bypass -File scripts/build/build-installer-local.ps1
# 产物： dist/electron/MRRS-Setup-<版本>-x64.exe （+ latest.yml / *.blockmap）
#
# 步骤： ① fetch_vcredist → ② 前端构建 → ③ 同步到 resources/frontend（先清后拷）
#        → ④ PyInstaller onedir 打包后端 → ⑤ electron-builder NSIS 出安装包
#
# 正式发布仍推荐推 tag：git tag v<版本> && git push origin v<版本> → Actions 产出两个平台安装包。
# Windows x64 offline installer build chain (ASCII only; mirrors Makefile build-win-x64)
$ErrorActionPreference = 'Continue'
# W24：不再硬编码构建机绝对路径 —— 由脚本位置推导仓库根，任意 checkout 目录可复现
$Root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $Root
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'

Write-Host "=== STEP 1/5: fetch vcredist ==="
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\build\fetch_vcredist.ps1
if ($LASTEXITCODE -ne 0) { Write-Host "[BUILD-FAIL] fetch_vcredist exit=$LASTEXITCODE"; exit 1 }

Write-Host "=== STEP 2/5: frontend build ==="
Push-Location frontend
npm run build
$code = $LASTEXITCODE
Pop-Location
if ($code -ne 0) { Write-Host "[BUILD-FAIL] frontend build exit=$code"; exit 1 }

Write-Host "=== STEP 3/5: sync frontend -> resources/frontend ==="
cmd /c scripts\build\sync-frontend-dist.bat
if ($LASTEXITCODE -ne 0) { Write-Host "[BUILD-FAIL] sync-frontend-dist exit=$LASTEXITCODE"; exit 1 }

Write-Host "=== STEP 4/5: pyinstaller backend (onedir) ==="
# W24：显式解析项目 Python（PATH 里的裸 python 可能指向已删除/32 位安装）
$PythonExe = Join-Path $Root 'backend\.venv\Scripts\python.exe'
if (-not (Test-Path $PythonExe)) {
  Write-Host "[BUILD-FAIL] 缺少 $PythonExe"
  Write-Host "请安装 64-bit Python 3.11 后重建 venv（scripts\dev-setup.bat 或 py -3.11 -m venv backend\.venv）"
  exit 1
}
Push-Location backend
& $PythonExe -m PyInstaller assistance-backend.spec --clean --noconfirm
$code = $LASTEXITCODE
Pop-Location
if ($code -ne 0) { Write-Host "[BUILD-FAIL] pyinstaller exit=$code"; exit 1 }
if (-not (Test-Path 'backend\dist\assistance-backend\assistance-backend.exe')) {
  Write-Host "[BUILD-FAIL] backend exe missing"; exit 1
}
Write-Host "[OK] backend/dist/assistance-backend/assistance-backend.exe"

Write-Host "=== STEP 5/5: electron-builder --win --x64 ==="
npx electron-builder --win --x64
if ($LASTEXITCODE -ne 0) { Write-Host "[BUILD-FAIL] electron-builder exit=$LASTEXITCODE"; exit 1 }

Write-Host "=== BUILD OK ==="
Get-ChildItem dist\electron\*.exe -ErrorAction SilentlyContinue | ForEach-Object {
  "{0}  {1:N1} MB  {2}" -f $_.Name, ($_.Length / 1MB), $_.LastWriteTime
}
exit 0