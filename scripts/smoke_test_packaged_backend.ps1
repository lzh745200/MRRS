<#
.SYNOPSIS
    Smoke-test a packaged (PyInstaller-frozen) backend exactly as the desktop app starts it.

.DESCRIPTION
    The frozen backend does NOT read .env from the repo and does NOT inherit the
    Electron-generated secrets when started by hand. Starting it without the full
    environment set produces misleading failures (missing DATABASE_URL, missing
    encryption key, migrations skipped). This script starts the frozen exe against
    an isolated data directory and asserts the three endpoints a healthy install
    must serve:

        /api/v1/health/liveness   -> 200 {"status":"alive"}
        /api/v1/health            -> 200 {"status":"healthy", ...}
        /version.json             -> 200 {"version":"<Version>", ...}

    It never touches the installed application: its own port, its own data/log/
    upload/cache/export directories, and it always kills the process afterwards.

.PARAMETER BackendDir
    Directory that contains assistance-backend.exe. Accepts either the inner layout
    (resources/backend/assistance-backend) or resources/backend; the script walks
    one level down automatically when the exe is not at the top.

.PARAMETER Port
    Port for the isolated instance. Default 18124 (uncommon, avoids the app's 8000).

.PARAMETER Version
    Expected version from /version.json. Empty string skips the assertion.

.PARAMETER TimeoutSeconds
    How long to wait for liveness. Cold start on a slow disk can take ~20s.

.PARAMETER Keep
    Keep the run directory (stdout.log / stderr.log / data / logs) for investigation.

.PARAMETER FrontendDist
    Frontend build directory containing index.html. Default: auto-detect
    ``<resources>/frontend`` next to the backend, then ``frontend/dist`` in the repo.
    Passed to the backend as ``FRONTEND_DIST_PATH`` so ``GET /`` works in unpacked runs.

.PARAMETER MapTilesDir
    Optional offline map-tiles directory, passed as ``MAP_TILES_DIR``. Auto-detected
    from ``<resources>/map-tiles`` when present.

.PARAMETER NoIsolateUserDirs
    By default the child process gets private ``APPDATA``/``LOCALAPPDATA`` under the
    run directory. This makes the smoke test hermetic and avoids startup hangs when
    a sandbox blocks writes to the real user profile. Pass this switch to inherit
    the current user profile instead.

.EXAMPLE
    powershell -NoProfile -ExecutionPolicy Bypass -File scripts/smoke_test_packaged_backend.ps1 `
        -BackendDir 'dist\electron\win-unpacked\resources\backend\assistance-backend' -Version 1.18.31

.NOTES
    Exit code 0 = PASS, 1 = FAIL. See docs/04-部署文档/06-打包态启动排障与离线包验证.md
#>
[CmdletBinding()]
param(
    [string]$BackendDir = 'dist\electron\win-unpacked\resources\backend\assistance-backend',
    [int]$Port = 18124,
    [string]$Version = '',
    [int]$TimeoutSeconds = 120,
    [string]$FrontendDist = '',
    [string]$MapTilesDir = '',
    [switch]$NoIsolateUserDirs,
    [switch]$Keep
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot

function Resolve-BackendExe {
    param([string]$dir)
    $candidates = @(
        (Join-Path $dir 'assistance-backend.exe'),
        (Join-Path $dir 'assistance-backend\assistance-backend.exe')
    )
    foreach ($c in $candidates) {
        if (Test-Path -LiteralPath $c) { return (Resolve-Path -LiteralPath $c).Path }
    }
    throw "assistance-backend.exe not found under '$dir' (looked in the directory and one level down)."
}

$backendDirAbs = if ([System.IO.Path]::IsPathRooted($BackendDir)) { $BackendDir } else { Join-Path $repoRoot $BackendDir }
if (-not (Test-Path -LiteralPath $backendDirAbs)) {
    Write-Host "[smoke] FAIL backend directory not found: $backendDirAbs" -ForegroundColor Red
    exit 1
}
$exe = Resolve-BackendExe -dir $backendDirAbs
$workingDir = Split-Path -Parent $exe
# <resources>\backend\assistance-backend\assistance-backend.exe -> <resources>
$resourcesDir = Split-Path -Parent (Split-Path -Parent $workingDir)

function Resolve-FrontendDist {
    param([string]$explicit, [string]$resources, [string]$repo)
    $candidates = @()
    if ($explicit) { $candidates += $explicit }
    $candidates += (Join-Path $resources 'frontend')
    $candidates += (Join-Path $repo 'frontend\dist')
    $candidates += (Join-Path $repo 'resources\frontend')
    foreach ($c in $candidates) {
        if ($c -and (Test-Path -LiteralPath (Join-Path $c 'index.html'))) {
            return (Resolve-Path -LiteralPath $c).Path
        }
    }
    return ''
}

function Resolve-MapTilesDir {
    param([string]$explicit, [string]$resources)
    if ($explicit) {
        if (Test-Path -LiteralPath $explicit) { return (Resolve-Path -LiteralPath $explicit).Path }
        Write-Host "[smoke] WARN -MapTilesDir not found: $explicit" -ForegroundColor Yellow
        return ''
    }
    $candidate = Join-Path $resources 'map-tiles'
    if (Test-Path -LiteralPath $candidate) { return (Resolve-Path -LiteralPath $candidate).Path }
    return ''
}

$frontendDirAbs = Resolve-FrontendDist -explicit $FrontendDist -resources $resourcesDir -repo $repoRoot
$mapTilesDirAbs = Resolve-MapTilesDir -explicit $MapTilesDir -resources $resourcesDir

# A leftover instance on the same port would make the poll below hit the wrong
# process and report a false PASS. Fail fast instead of guessing.
$stale = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if ($stale) {
    Write-Host "[smoke] FAIL port $Port is already in use (pid $($stale.OwningProcess)); pass -Port or stop that process" -ForegroundColor Red
    exit 1
}

$runDir = Join-Path $repoRoot '.scratch\smoke-unpacked'
if (Test-Path -LiteralPath $runDir) { Remove-Item -LiteralPath $runDir -Recurse -Force }
$dataDir = Join-Path $runDir 'data'
$logsDir = Join-Path $runDir 'logs'
$uploadsDir = Join-Path $runDir 'uploads'
$cacheDir = Join-Path $runDir 'cache'
$exportsDir = Join-Path $runDir 'exports'
$profileDir = Join-Path $runDir 'profile'
$appDataRoaming = Join-Path $profileDir 'AppData\Roaming'
$appDataLocal = Join-Path $profileDir 'AppData\Local'
foreach ($d in @($dataDir, $logsDir, $uploadsDir, $cacheDir, $exportsDir, $appDataRoaming, $appDataLocal)) {
    New-Item -ItemType Directory -Force -Path $d | Out-Null
}
$outLog = Join-Path $runDir 'stdout.log'
$errLog = Join-Path $runDir 'stderr.log'
$dbPath = Join-Path $dataDir 'smoke.db'

$rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
$keyBytes = New-Object byte[] 32
$rng.GetBytes($keyBytes)
$rng.Dispose()
$encryptionKey = [Convert]::ToBase64String($keyBytes)

# Same contract the Electron main process uses when spawning the backend
# (electron/main.js -> buildBackendEnv): explicit paths, then the secrets.
$env:DATABASE_URL = "sqlite:///$($dbPath -replace '\\', '/')"
$env:HOST = '127.0.0.1'
$env:PORT = "$Port"
$env:LOG_FILE = Join-Path $logsDir 'app.log'
$env:UPLOAD_DIR = $uploadsDir
$env:CACHE_DIR = $cacheDir
$env:EXPORT_DIR = $exportsDir
$env:ENVIRONMENT = 'production'
$env:PROJECT_VERSION = $Version
$env:ENCRYPTION_KEY = $encryptionKey
$env:INTERNAL_BACKUP_KEY = 'smoke-backup-key-0123456789abcdef'
$env:INTERNAL_SHUTDOWN_KEY = 'smoke-shutdown-key-0123456789abcdef'
$env:ENABLE_AUTO_MIGRATION = 'false'
if (-not $NoIsolateUserDirs) {
    # Hermetic run: never touch the real user profile. Besides keeping the host
    # clean, this avoids startup hangs on machines where a sandbox blocks writes
    # to %LOCALAPPDATA% (frozen backend resolves its data dir from there).
    $env:APPDATA = $appDataRoaming
    $env:LOCALAPPDATA = $appDataLocal
}
if ($frontendDirAbs) {
    $env:FRONTEND_DIST_PATH = $frontendDirAbs
} else {
    Write-Host '[smoke] WARN frontend dist not found; GET / will 404 (pass -FrontendDist)' -ForegroundColor Yellow
}
if ($mapTilesDirAbs) {
    $env:MAP_TILES_DIR = $mapTilesDirAbs
}

Write-Host "[smoke] exe=$exe"
Write-Host "[smoke] frontend=$(if ($frontendDirAbs) { $frontendDirAbs } else { '<none>' })"
Write-Host "[smoke] map-tiles=$(if ($mapTilesDirAbs) { $mapTilesDirAbs } else { '<none>' })"
Write-Host "[smoke] port=$Port timeout=${TimeoutSeconds}s version=$(if ($Version) { $Version } else { '<any>' })"
# Windows PowerShell 5.1 Start-Process 在环境同时存在 HTTPS_PROXY/https_proxy
# 这类仅大小写不同的键时会抛“字典中的关键字已添加”。启动前去掉大写重复项，
# 代理仍保留小写键（或由系统默认代理接管）。
[Environment]::SetEnvironmentVariable('HTTP_PROXY', $null, 'Process')
[Environment]::SetEnvironmentVariable('HTTPS_PROXY', $null, 'Process')
[Environment]::SetEnvironmentVariable('ALL_PROXY', $null, 'Process')
[Environment]::SetEnvironmentVariable('NO_PROXY', $null, 'Process')
[Environment]::SetEnvironmentVariable('http_proxy', $null, 'Process')
[Environment]::SetEnvironmentVariable('https_proxy', $null, 'Process')
[Environment]::SetEnvironmentVariable('all_proxy', $null, 'Process')
[Environment]::SetEnvironmentVariable('no_proxy', $null, 'Process')
$proc = Start-Process -FilePath $exe -WorkingDirectory $workingDir -PassThru `
    -RedirectStandardOutput $outLog -RedirectStandardError $errLog
Write-Host "[smoke] pid=$($proc.Id)"

$sw = [System.Diagnostics.Stopwatch]::StartNew()
$livenessOk = $false
$livenessBody = ''
while ($sw.Elapsed.TotalSeconds -lt $TimeoutSeconds) {
    Start-Sleep -Milliseconds 1500
    if ($proc.HasExited) {
        Write-Host "[smoke] FAIL process exited early, code=$($proc.ExitCode)" -ForegroundColor Red
        break
    }
    try {
        $r = Invoke-WebRequest -Uri "http://127.0.0.1:$Port/api/v1/health/liveness" -TimeoutSec 3 -UseBasicParsing
        if ($r.StatusCode -eq 200) {
            $livenessOk = $true
            $livenessBody = $r.Content
            break
        }
    } catch { }
}

$healthOk = $false
$versionOk = $false
$versionBody = ''
if ($livenessOk) {
    Write-Host "[smoke] liveness OK in $([int]$sw.Elapsed.TotalSeconds)s: $livenessBody" -ForegroundColor Green
    try {
        $h = Invoke-WebRequest -Uri "http://127.0.0.1:$Port/api/v1/health" -TimeoutSec 10 -UseBasicParsing
        if ($h.StatusCode -eq 200) {
            $healthOk = $true
            Write-Host "[smoke] health OK: $($h.Content)"
        }
    } catch { Write-Host "[smoke] health request failed: $($_.Exception.Message)" }
    try {
        $v = Invoke-WebRequest -Uri "http://127.0.0.1:$Port/version.json" -TimeoutSec 5 -UseBasicParsing
        $versionBody = $v.Content
        $versionOk = $true
        Write-Host "[smoke] version.json: $versionBody"
        if ($Version -and ($versionBody -notmatch [regex]::Escape($Version))) {
            Write-Host "[smoke] FAIL version mismatch: expected '$Version'" -ForegroundColor Red
            $versionOk = $false
        }
    } catch { Write-Host "[smoke] version.json failed: $($_.Exception.Message)" }
} else {
    Write-Host "[smoke] FAIL liveness not ready within ${TimeoutSeconds}s" -ForegroundColor Red
}

if (-not $proc.HasExited) { Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue }
Start-Sleep -Milliseconds 800

Write-Host '--- stderr tail (startup diagnostics) ---'
if (Test-Path -LiteralPath $errLog) { Get-Content -LiteralPath $errLog -Tail 15 -Encoding UTF8 }
Write-Host '--- app.log tail ---'
$appLog = Join-Path $logsDir 'app.log'
if (Test-Path -LiteralPath $appLog) { Get-Content -LiteralPath $appLog -Tail 20 -Encoding UTF8 }

$pass = $livenessOk -and $healthOk -and $versionOk
if ($pass) {
    Write-Host '[smoke] PASS (liveness + health + version.json)' -ForegroundColor Green
} else {
    Write-Host '[smoke] FAIL' -ForegroundColor Red
    Write-Host "[smoke] logs kept at $runDir"
    exit 1
}
if (-not $Keep) { Remove-Item -LiteralPath $runDir -Recurse -Force -ErrorAction SilentlyContinue }
exit 0
