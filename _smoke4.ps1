
$ErrorActionPreference = "Continue"
$base = "http://127.0.0.1:8010/api/v1"
$script:pass = 0
$script:fail = 0
$script:session = $null
function Check($name, $cond, $extra) {
  if ($cond) { $script:pass++; echo ("  [PASS] " + $name + "   " + $extra) }
  else { $script:fail++; echo ("  [FAIL] " + $name + "   " + $extra) }
}
function NewSession() {
  return New-Object Microsoft.PowerShell.Commands.WebRequestSession
}
function Req($method, $url, $body, $token, $csrf, $sess) {
  $h = @{ "Content-Type" = "application/json" }
  if ($token) { $h["Authorization"] = "Bearer $token" }
  if ($csrf) { $h["X-CSRF-Token"] = $csrf }
  $p = @{ Uri = ($base + $url); Method = $method; Headers = $h; TimeoutSec = 60; UseBasicParsing = $true; ErrorAction = "Stop" }
  if ($sess) { $p["WebSession"] = $sess }
  if ($body -ne $null) { $p["Body"] = ($body | ConvertTo-Json -Depth 10) }
  try {
    $resp = Invoke-WebRequest @p
    return @{ code = [int]$resp.StatusCode; content = $resp.Content }
  } catch {
    $code = 0; $raw = ""
    if ($_.Exception.Response) {
      $code = [int]$_.Exception.Response.StatusCode
      try { $sr = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream()); $raw = $sr.ReadToEnd() } catch {}
    } else { $raw = $_.Exception.Message }
    return @{ code = $code; content = $raw }
  }
}
function J($r) { try { return ($r.content | ConvertFrom-Json) } catch { return $null } }

echo "########## T1 login + CSRF handshake ##########"
$script:session = NewSession
$r = Req "POST" "/auth/login" @{ username = "admin"; password = "zgcZGC733035#" } $null $null $script:session
$j = J $r
Check "login 200" ($r.code -eq 200) ("code=" + $r.code)
Check "must_change_password=true (top-level)" ($j.must_change_password -eq $true) ("val=" + $j.must_change_password)
$tok0 = $j.data.access_token
Check "access_token issued" ($tok0 -and $tok0.Length -gt 40) ("len=" + $(if($tok0){$tok0.Length}else{0}))

$r = Req "GET" "/auth/csrf-token" $null $tok0 $null $script:session
$j = J $r
$csrf = $j.data.csrf_token
Check "csrf-token 200" ($r.code -eq 200) ("code=" + $r.code)
Check "csrf token issued" ($csrf -and $csrf.Length -gt 20) ("len=" + $(if($csrf){$csrf.Length}else{0}))

echo "########## T2 must-change gate blocks business API ##########"
$r = Req "GET" "/system/self-check" $null $tok0 $null $script:session
Check "self-check blocked 403" ($r.code -eq 403) ("code=" + $r.code + " body=" + $r.content.Substring(0,[Math]::Min(120,$r.content.Length)))

echo "########## T3 change password (CSRF + own id) ##########"
$newPwd = "Smoke#2026!Aa9"
$r = Req "PUT" "/users/1/password" @{ old_password = "zgcZGC733035#"; new_password = $newPwd } $tok0 $csrf $script:session
Check "change-password 2xx" ($r.code -ge 200 -and $r.code -lt 300) ("code=" + $r.code + " body=" + $r.content.Substring(0,[Math]::Min(140,$r.content.Length)))

echo "########## T4 re-login with new password ##########"
$script:session = NewSession
$r = Req "POST" "/auth/login" @{ username = "admin"; password = $newPwd } $null $null $script:session
$j = J $r
Check "relogin 200" ($r.code -eq 200) ("code=" + $r.code + " body=" + $r.content.Substring(0,[Math]::Min(140,$r.content.Length)))
Check "must_change_password=false" ($j.must_change_password -ne $true) ("val=" + $j.must_change_password)
$tok = $j.data.access_token
$r = Req "GET" "/auth/csrf-token" $null $tok $null $script:session
$csrf = (J $r).data.csrf_token
Check "csrf2 issued" ($csrf -and $csrf.Length -gt 20) ("len=" + $(if($csrf){$csrf.Length}else{0}))

echo "########## T5 self-check after password change ##########"
$r = Req "GET" "/system/self-check" $null $tok $null $script:session
$j = J $r
Check "self-check 200" ($r.code -eq 200) ("code=" + $r.code + " body=" + $r.content.Substring(0,[Math]::Min(120,$r.content.Length)))
$d = $j.data
Check "check_count=6" ($d.summary.check_count -eq 6) ("count=" + $d.summary.check_count + " status=" + $d.status)
foreach ($c in $d.checks) { echo ("     - " + $c.name + " [" + $c.level + "]  " + $c.detail.Substring(0,[Math]::Min(52,$c.detail.Length))) }

echo "########## T6 public-config ##########"
$r = Req "GET" "/auth/public-config" $null $null $null $script:session
$j = J $r
Check "public-config 200" ($r.code -eq 200) ("code=" + $r.code)
Check "self_register_enabled=false" ($j.data.self_register_enabled -eq $false) ("val=" + $j.data.self_register_enabled)

echo "########## T7 organization tree ##########"
$r = Req "POST" "/organizations" @{ name = "SmokeProvince"; code = "520000"; org_type = "government" } $tok $csrf $script:session
$j = J $r
Check "create province 2xx" ($r.code -ge 200 -and $r.code -lt 300) ("code=" + $r.code + " body=" + $r.content.Substring(0,[Math]::Min(140,$r.content.Length)))
$provId = $j.data.id
if (-not $provId) { $provId = $j.id }
$r = Req "POST" "/organizations" @{ name = "SmokeCity"; code = "520100"; org_type = "government"; parent_id = $provId } $tok $csrf $script:session
$j = J $r
Check "create city 2xx" ($r.code -ge 200 -and $r.code -lt 300) ("code=" + $r.code + " body=" + $r.content.Substring(0,[Math]::Min(140,$r.content.Length)))
$cityId = $j.data.id
if (-not $cityId) { $cityId = $j.id }
$r = Req "POST" "/organizations" @{ name = "SmokeCounty"; code = "520102"; org_type = "government"; parent_id = $cityId } $tok $csrf $script:session
$j = J $r
Check "create county 2xx" ($r.code -ge 200 -and $r.code -lt 300) ("code=" + $r.code + " body=" + $r.content.Substring(0,[Math]::Min(140,$r.content.Length)))

echo "########## T8 negative: cross-level attach rejected ##########"
$r = Req "POST" "/organizations" @{ name = "SmokeSkip"; code = "520103"; org_type = "government"; parent_id = $provId } $tok $csrf $script:session
Check "skip-level 422" ($r.code -eq 422) ("code=" + $r.code + " body=" + $r.content.Substring(0,[Math]::Min(160,$r.content.Length)))

echo "########## T9 negative: duplicate code rejected ##########"
$r = Req "POST" "/organizations" @{ name = "SmokeDup"; code = "520100"; org_type = "government"; parent_id = $provId } $tok $csrf $script:session
Check "duplicate code 4xx" ($r.code -ge 400 -and $r.code -lt 500) ("code=" + $r.code)

echo "########## T10 self-check reflects org tree ##########"
$r = Req "GET" "/system/self-check" $null $tok $null $script:session
$d = (J $r).data
$oc = $d.checks | Where-Object { $_.name -like "*单位码*" } | Select-Object -First 1
Check "org-code item present" ($null -ne $oc) ("level=" + $oc.level + " detail=" + $oc.detail.Substring(0,[Math]::Min(70,$oc.detail.Length)))
$hc = $d.checks | Where-Object { $_.name -like "*层级*" } | Select-Object -First 1
Check "hierarchy item present" ($null -ne $hc) ("level=" + $hc.level)

echo "########## SUMMARY ##########"
echo ("  PASS=" + $script:pass + "  FAIL=" + $script:fail)
