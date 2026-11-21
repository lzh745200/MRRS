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

function Get-FreeSpaceMB([string]$Path) {
  # NSIS extracts its payload into TEMP. A writable but almost-full TEMP still
  # fails with "Error creating mmap to file ...\nsc*.tmp" (NSIS needs several
  # times the installer size for its self-extracting buffers).
  try {
    if (-not $Path) { return -1 }
    $full = [IO.Path]::GetFullPath($Path)
    $root = [IO.Path]::GetPathRoot($full)
    if (-not $root) { return -1 }
    $drive = New-Object -TypeName System.IO.DriveInfo -ArgumentList $root
    return [math]::Floor($drive.AvailableFreeSpace / 1MB)
  } catch {
    # UNC / redirected / virtual paths may not expose DriveInfo; do not block
    # them just because free space is unknown.
    return -1
  }
}

function Test-TempCandidate([string]$Path, [long]$RequiredMB) {
  if (-not (Test-WritableDir $Path)) { return $false }
  $free = Get-FreeSpaceMB $Path
  if ($free -lt 0) { return $true }
  return ($free -ge $RequiredMB)
}

$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
if (-not $Installer) {
  # Release 用户通常把 Helper 与 Setup 放在同一个下载目录：同目录优先，
  # 且不再按 LastWriteTime 与仓库 dist 混排（否则仓库里较新的包会抢走选择）。
  $picked = Get-ChildItem -Path $PSScriptRoot -Filter 'MRRS-Setup-*-x64.exe' -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTime -Descending | Select-Object -First 1
  if (-not $picked) {
    $picked = Get-ChildItem -Path $PSScriptRoot -Filter 'MRRS-Setup-*.exe' -ErrorAction SilentlyContinue |
      Sort-Object LastWriteTime -Descending | Select-Object -First 1
  }
  if (-not $picked) {
    $repoRelease = Join-Path $root 'dist\release'
    $repoElectron = Join-Path $root 'dist\electron'
    $repoCandidates = @()
    if (Test-Path -LiteralPath $repoRelease) {
      $repoCandidates = Get-ChildItem -Path $repoRelease -Filter 'MRRS-Setup-*-x64.exe' -Recurse -ErrorAction SilentlyContinue
    }
    if (-not $repoCandidates -and (Test-Path -LiteralPath $repoElectron)) {
      $repoCandidates = Get-ChildItem -Path $repoElectron -Filter 'MRRS-Setup-*.exe' -ErrorAction SilentlyContinue
    }
    $picked = $repoCandidates | Sort-Object LastWriteTime -Descending | Select-Object -First 1
  }
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

# Reserve at least 2x the installer size plus 512MB: NSIS holds the compressed
# payload and its extracted files at the same time, and the install target may
# be on a different drive. For a ~366-382 MB installer this is about 1.2-1.3 GB.
$requiredMB = 2048
if ($Installer -and (Test-Path -LiteralPath $Installer -PathType Leaf)) {
  $installerMB = (Get-Item -LiteralPath $Installer).Length / 1MB
  $requiredMB = [long]([math]::Ceiling($installerMB) * 2 + 512)
}
Write-Step "Required free space: $requiredMB MB"

$currentOk = Test-WritableDir $env:TEMP
$currentFree = if ($currentOk) { Get-FreeSpaceMB $env:TEMP } else { -1 }
Write-Step "Current TEMP writable: $currentOk (free: $(if ($currentFree -ge 0) { "$currentFree MB" } else { 'unknown' }))"

$chosen = $null
if ($TempDir) {
  try { New-Item -ItemType Directory -Path $TempDir -Force | Out-Null } catch { }
  if (-not (Test-WritableDir $TempDir)) {
    throw "Explicit -TempDir is not writable: $TempDir"
  }
  $explicitFree = Get-FreeSpaceMB $TempDir
  if ($explicitFree -ge 0 -and $explicitFree -lt $requiredMB) {
    throw "Explicit -TempDir has insufficient free space: $TempDir (free=$explicitFree MB, required=$requiredMB MB)"
  }
  $chosen = $TempDir
} elseif ($currentOk -and ($currentFree -lt 0 -or $currentFree -ge $requiredMB)) {
  $chosen = $env:TEMP
} else {
  $fallbacks = @(
    (Join-Path $env:USERPROFILE 'AppData\Local\Temp'),
    (Join-Path $env:WINDIR 'Temp')
  )
  foreach ($dir in $fallbacks) {
    try { New-Item -ItemType Directory -Path $dir -Force | Out-Null } catch { }
    if (Test-TempCandidate $dir $requiredMB) { $chosen = $dir; break }
  }
}
if (-not $chosen) {
  throw "No TEMP directory has enough free space and is writable (required=$requiredMB MB). Free disk space or pass -TempDir to another volume."
}
$chosenFree = Get-FreeSpaceMB $chosen
Write-Step "Using temp directory: $chosen (free: $(if ($chosenFree -ge 0) { "$chosenFree MB" } else { 'unknown' }))"

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
