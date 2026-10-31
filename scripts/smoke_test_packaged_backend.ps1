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
foreach ($d in @($dataDir, $logsDir, $uploadsDir, $cacheDir, $exportsDir)) {
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

Write-Host "[smoke] exe=$exe"
Write-Host "[smoke] port=$Port timeout=${TimeoutSeconds}s version=$(if ($Version) { $Version } else { '<any>' })"
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
