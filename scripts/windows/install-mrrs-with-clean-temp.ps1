<#
.SYNOPSIS
  Start the MRRS NSIS installer with a writable TEMP/TMP directory.

.DESCRIPTION
  NSIS runs InitPluginsDir and extracts plugins into %TEMP%. If %TEMP% points
  to a deleted external drive, a removed folder, or a non-writable policy
  folder, setup fails before any install logic with:
    Error writing temporary file. Make sure your temp folder is valid.

  $TEMP is read-only inside NSIS, so the installer itself cannot repair it.
  This wrapper probes the current TEMP, chooses a writable fallback, sets
  TEMP/TMP for the child process, then launches the installer.

.PARAMETER Installer
  Full path to MRRS-Setup-*.exe. If omitted, the newest installer under
  dist\release\*\ or dist\electron\ is used.

.PARAMETER NoLaunch
  Diagnose only; print the chosen temp directory and exit.

.PARAMETER TempDir
  Explicit writable temp directory. Useful when the default user Temp is
  blocked by policy/ACL in enterprise images.

.PARAMETER Persist
  Also write TEMP/TMP to the current user's environment. An already-running
  Explorer does not refresh its environment: sign out/restart or launch the
  installer from a new terminal afterwards.

.EXAMPLE
  powershell -NoProfile -ExecutionPolicy Bypass -File scripts\windows\install-mrrs-with-clean-temp.ps1 -NoLaunch

.EXAMPLE
  powershell -NoProfile -ExecutionPolicy Bypass -File scripts\windows\install-mrrs-with-clean-temp.ps1
#>
[CmdletBinding()]
param(
  [string]$Installer = "",
  [string]$TempDir = "",
  [switch]$NoLaunch,
  [switch]$Persist
)

$ErrorActionPreference = 'Stop'

function Write-Step([string]$Message) { Write-Host "[MRRS-TEMP] $Message" }

function Test-WritableDir([string]$Path) {
  try {
    if (-not (Test-Path -LiteralPath $Path -PathType Container)) { return $false }
    $probe = Join-Path $Path (".mrrs-write-probe-{0}.tmp" -f [guid]::NewGuid().ToString('N'))
    [IO.File]::WriteAllText($probe, 'ok')
    [IO.File]::Delete($probe)
    return $true
  } catch {
    return $false
  }
}

$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
if (-not $Installer) {
  $candidates = @()
  $candidates += Get-ChildItem -Path (Join-Path $root 'dist\release') -Filter 'MRRS-Setup-*-x64.exe' -Recurse -ErrorAction SilentlyContinue
  $candidates += Get-ChildItem -Path (Join-Path $root 'dist\electron') -Filter 'MRRS-Setup-*.exe' -ErrorAction SilentlyContinue
  $picked = $candidates | Sort-Object LastWriteTime -Descending | Select-Object -First 1
  if ($picked) { $Installer = $picked.FullName }
}
if (-not $NoLaunch) {
  if (-not $Installer -or -not (Test-Path -LiteralPath $Installer -PathType Leaf)) {
    throw "Installer not found. Pass -Installer with the full path to MRRS-Setup-*.exe."
  }
}

Write-Step "Current TEMP = $env:TEMP"
Write-Step "Current TMP  = $env:TMP"
Write-Step "Installer    = $(if ($Installer) { $Installer } else { '(diagnose only)' })"

$currentOk = Test-WritableDir $env:TEMP
Write-Step "Current TEMP writable: $currentOk"

$chosen = $null
if ($TempDir) {
  try { New-Item -ItemType Directory -Path $TempDir -Force | Out-Null } catch { }
  if (-not (Test-WritableDir $TempDir)) {
    throw "Explicit -TempDir is not writable: $TempDir"
  }
  $chosen = $TempDir
} elseif ($currentOk) {
  $chosen = $env:TEMP
} else {
  $fallbacks = @(
    (Join-Path $env:USERPROFILE 'AppData\Local\Temp'),
    (Join-Path $env:WINDIR 'Temp')
  )
  foreach ($dir in $fallbacks) {
    try { New-Item -ItemType Directory -Path $dir -Force | Out-Null } catch { }
    if (Test-WritableDir $dir) { $chosen = $dir; break }
  }
}
if (-not $chosen) {
  throw "Neither the current TEMP nor fallback Temp directories are writable. Check disk full/read-only, ACL deny, or security software blocking extraction."
}
Write-Step "Using temp directory: $chosen"

$env:TEMP = $chosen
$env:TMP = $chosen
if ($Persist) {
  [Environment]::SetEnvironmentVariable('TEMP', $chosen, 'User')
  [Environment]::SetEnvironmentVariable('TMP', $chosen, 'User')
  Write-Step "Persisted TEMP/TMP for the current user (sign out/restart or use a new terminal to apply)."
}

if ($NoLaunch) {
  Write-Step "Diagnose-only mode: installer not started."
  exit 0
}

Write-Step "Starting installer and waiting..."
$proc = Start-Process -FilePath $Installer -Wait -PassThru
Write-Step "Installer exit code: $($proc.ExitCode)"
exit $proc.ExitCode
