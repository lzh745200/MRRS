
$ErrorActionPreference = "Continue"
$base = "http://127.0.0.1:8010/api/v1"
$script:pass = 0
$script:fail = 0
function Check($name, $cond, $extra) {
  if ($cond) { $script:pass++; echo ("  [PASS] " + $name + " " + $extra) }
  else { $script:fail++; echo ("  [FAIL] " + $name + " " + $extra) }
}
function Req($method, $url, $body, $token) {
  $h = @{ "Content-Type" = "application/json" }
  if ($token) { $h["Authorization"] = "Bearer $token" }
  $p = @{
    Uri = ($base + $url); Method = $method; Headers = $h;
    TimeoutSec = 40; UseBasicParsing = $true; ErrorAction = "Stop"
  }
  if ($body -ne $null) { $p["Body"] = ($body | ConvertTo-Json -Depth 10) }
  try {
    $resp = Invoke-WebRequest @p
    $obj = $null
    try { $obj = $resp.Content | ConvertFrom-Json } catch {}
    return @{ code = [int]$resp.StatusCode; body = $obj; raw = $resp.Content }
  } catch {
    $code = 0; $raw = ""
    if ($_.Exception.Response) {
      $code = [int]$_.Exception.Response.StatusCode
      try { $sr = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream()); $raw = $sr.ReadToEnd() } catch {}
    } else { $raw = $_.Exception.Message }
    return @{ code = $code; body = $null; raw = $raw }
  }
}
function Unwrap($r) {
  if ($r.body -and $r.body.data -and $r.body.data.data) { return $r.body.data.data }
  if ($r.body -and $r.body.data) { return $r.body.data }
  return $r.body
}

echo "===== T1 login (factory password) ====="
$r = Req "POST" "/auth/login" @{ username = "admin"; password = "zgcZGC733035#" } $null
$d = Unwrap $r
Check "login 200" ($r.code -eq 200) ("code=" + $r.code)
Check "must_change_password=true" ($d.must_change_password -eq $true) ("val=" + $d.must_change_password)
$tok0 = $d.access_token

echo "===== T2 gated API blocked before password change ====="
$r = Req "GET" "/system/self-check" $null $tok0
Check "self-check blocked (4xx)" ($r.code -ge 400 -and $r.code -lt 500) ("code=" + $r.code + " raw=" + $r.raw.Substring(0,[Math]::Min(120,$r.raw.Length)))

echo "===== T3 change password ====="
$newPwd = "Smoke#2026!Aa"
$r = Req "POST" "/auth/change-password" @{ old_password = "zgcZGC733035#"; new_password = $newPwd } $tok0
Check "change-password 2xx" ($r.code -ge 200 -and $r.code -lt 300) ("code=" + $r.code + " raw=" + $r.raw.Substring(0,[Math]::Min(160,$r.raw.Length)))

echo "===== T4 re-login with new password ====="
$r = Req "POST" "/auth/login" @{ username = "admin"; password = $newPwd } $null
$d = Unwrap $r
Check "relogin 200" ($r.code -eq 200) ("code=" + $r.code)
Check "must_change_password=false" ($d.must_change_password -ne $true) ("val=" + $d.must_change_password)
$tok = $d.access_token
Check "token present" ($tok -and $tok.Length -gt 20) ("len=" + $(if($tok){$tok.Length}else{0}))

echo "===== T5 self-check (6 items) ====="
$r = Req "GET" "/system/self-check" $null $tok
$d = Unwrap $r
Check "self-check 200" ($r.code -eq 200) ("code=" + $r.code)
Check "6 checks" ($d.summary.check_count -eq 6) ("count=" + $d.summary.check_count + " status=" + $d.status)
foreach ($c in $d.checks) { echo ("    - " + $c.name + " [" + $c.level + "] " + $c.detail.Substring(0,[Math]::Min(60,$c.detail.Length))) }

echo "===== T6 public-config (self register off) ====="
$r = Req "GET" "/auth/public-config" $null $null
$d = Unwrap $r
Check "public-config 200" ($r.code -eq 200) ("code=" + $r.code)
Check "self_register_enabled=false" ($d.self_register_enabled -eq $false) ("val=" + $d.self_register_enabled)

echo "===== SUMMARY ====="
echo ("  PASS=" + $script:pass + " FAIL=" + $script:fail)
