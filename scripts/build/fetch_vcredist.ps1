# ============================================================================
# fetch_vcredist.ps1 — VC++ Redistributable 拉取 + SHA256 钉扎校验
# ----------------------------------------------------------------------------
# 从微软官方固定 URL（aka.ms/vs/17）下载 vc_redist.{x64,x86}.exe 到
# resources/vcredist/，哈希必须与 build-scripts/electron-builder-nsis-hook.nsh
# 中 !define 钉扎的 SHA256 一致（单一事实源；NSIS 安装期校验用同一组常量）。
#
# 行为：
#   - 本地已存在且哈希匹配 → 跳过下载（离线构建友好）
#   - 本地存在但哈希不匹配 → 删除后重新下载校验
#   - 下载后哈希不匹配 → 删除临时文件并 exit 1
#   - 微软在短链上原地更新二进制导致失配属预期安全行为：人工确认新版本后
#     更新 .nsh 中的常量即可恢复
#
# 用途：CI（.github/workflows/build-windows.yml 第 9.6 步）
#      本地构建（Makefile: make fetch-vcredist，build-win-x64/x86/all 前置）
# ============================================================================
$ErrorActionPreference = 'Stop'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$RepoRoot = (Resolve-Path (Join-Path (Join-Path $PSScriptRoot '..') '..')).Path
$HookFile = Join-Path (Join-Path $RepoRoot 'build-scripts') 'electron-builder-nsis-hook.nsh'
$DestDir  = Join-Path (Join-Path $RepoRoot 'resources') 'vcredist'

if (-not (Test-Path -LiteralPath $HookFile)) {
    throw "钉扎常量源文件不存在: $HookFile"
}
$content = Get-Content -LiteralPath $HookFile -Raw

$targets = @(
    @{ Arch = 'x64'; File = 'vc_redist.x64.exe' },
    @{ Arch = 'x86'; File = 'vc_redist.x86.exe' }
)

foreach ($t in $targets) {
    $arch     = $t.Arch
    $file     = $t.File
    $urlMatch = [regex]::Match($content, ('(?i)!define\s+VCREDIST_{0}_URL\s+"([^"]+)"' -f $arch))
    $shaMatch = [regex]::Match($content, ('(?i)!define\s+VCREDIST_{0}_SHA256\s+"([^"]+)"' -f $arch))
    if (-not $urlMatch.Success -or -not $shaMatch.Success) {
        throw "无法从 $HookFile 解析 VCREDIST_${arch}_URL / VCREDIST_${arch}_SHA256"
    }
    $url      = $urlMatch.Groups[1].Value
    $expected = $shaMatch.Groups[1].Value
    $dest     = Join-Path $DestDir $file

    if ((Test-Path -LiteralPath $dest) -and
        ((Get-FileHash -Algorithm SHA256 -LiteralPath $dest).Hash -ieq $expected)) {
        Write-Host "[OK] $file 已存在且 SHA256 匹配，跳过下载"
        continue
    }
    if (Test-Path -LiteralPath $dest) {
        Write-Host "[..] $file 哈希不匹配，重新下载"
        Remove-Item -LiteralPath $dest -Force
    } else {
        Write-Host "[..] $file 缺失，开始下载: $url"
    }

    $tmp = "$dest.download"
    $maxAttempts = 3
    $downloaded = $false
    for ($attempt = 1; $attempt -le $maxAttempts; $attempt++) {
        try {
            if ($attempt -gt 1) {
                Write-Host "[..] $file 第 $attempt 次重试（前次网络失败）..."
                Start-Sleep -Seconds (10 * $attempt)
            }
            Invoke-WebRequest -Uri $url -OutFile $tmp -MaximumRedirection 10 `
                -UseBasicParsing -UserAgent "MRRS-build/1.0"
            $actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $tmp).Hash
            if ($actual -ine $expected) {
                Remove-Item -LiteralPath $tmp -Force
                throw ("{0} SHA256 不匹配：期望 {1}，实际 {2}。微软可能已更新短链指向的版本，" +
                       "请人工确认新版本后更新 {3} 中的钉扎常量") -f $file, $expected, $actual, $HookFile
            }
            New-Item -ItemType Directory -Force -Path $DestDir | Out-Null
            Move-Item -LiteralPath $tmp -Destination $dest -Force
            Write-Host "[OK] $file 下载完成并通过 SHA256 校验"
            $downloaded = $true
            break
        } catch {
            if (Test-Path -LiteralPath $tmp) { Remove-Item -LiteralPath $tmp -Force }
            $_ | Out-String | Write-Host -ForegroundColor Yellow
            if ($attempt -eq $maxAttempts) { throw }
            Write-Host "[..] 第 $attempt 次尝试失败，将重试"
        }
    }
    if (-not $downloaded) { throw "$file 下载失败（已重试 $maxAttempts 次）" }
}

Write-Host "VC++ Redistributable 就绪: $DestDir"
exit 0
