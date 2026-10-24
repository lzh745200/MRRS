
$ErrorActionPreference = "Continue"
$base = "http://127.0.0.1:8010/api/v1"
$script:pass = 0
$script:fail = 0
function Check($name, $cond, $extra) {
  if ($cond) { $script:pass++; echo ("  [PASS] " + $name + "   " + $extra) }
  else { $script:fail++; echo ("  [FAIL] " + $name + "   " + $extra) }
}
function Req($method, $url, $body, $token) {
  $h = @{ "Content-Type" = "application/json" }
  if ($token) { $h["Authorization"] = "Bearer $token" }
  $p = @{ Uri = ($base + $url); Method = $method; Headers = $h; TimeoutSec = 60; UseBasicParsing = $true; ErrorAction = "Stop" }
  if ($body -ne $null) { $p["Body"] = ($body | ConvertTo-Json -Depth 10) }
  try {
    $resp = Invoke-WebRequest @p
    $obj = $null; try { $obj = $resp.Content | ConvertFrom-Json } catch {}
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
  if ($null -eq $r.body) { return $null }
  $d = $r.body
  if ($d.data -and $d.data.data) { return $d.data.data }
  if ($d.data) { return $d.data }
  return $d
}

echo "########## T1 login (factory password) ##########"
$r = Req "POST" "/auth/login" @{ username = "admin"; password = "zgcZGC733035#" } $null
$d = Unwrap $r
Check "login 200" ($r.code -eq 200) ("code=" + $r.code + " raw=" + $r.raw.Substring(0,[Math]::Min(150,$r.raw.Length)))
Check "must_change_password=true" ($d.must_change_password -eq $true) ("val=" + $d.must_change_password)
$tok0 = $d.access_token
Check "token issued" ($tok0 -and $tok0.Length -gt 20) ("len=" + $(if($tok0){$tok0.Length}else{0}))

echo "########## T2 gated API blocked while must-change ##########"
$r = Req "GET" "/system/self-check" $null $tok0
Check "self-check 4xx while must-change" ($r.code -ge 400 -and $r.code -lt 500) ("code=" + $r.code + " raw=" + $r.raw.Substring(0,[Math]::Min(120,$r.raw.Length)))

echo "########## T3 change password (PUT /users/{id}/password) ##########"
$newPwd = "Smoke#2026!Aa9"
$r = Req "PUT" "/users/1/password" @{ old_password = "zgcZGC733035#"; new_password = $newPwd } $tok0
Check "change-password 2xx" ($r.code -ge 200 -and $r.code -lt 300) ("code=" + $r.code + " raw=" + $r.raw.Substring(0,[Math]::Min(160,$r.raw.Length)))

echo "########## T4 re-login ##########"
$r = Req "POST" "/auth/login" @{ username = "admin"; password = $newPwd } $null
$d = Unwrap $r
Check "relogin 200" ($r.code -eq 200) ("code=" + $r.code)
Check "must_change_password now false" ($d.must_change_password -ne $true) ("val=" + $d.must_change_password)
$tok = $d.access_token
Check "token2 issued" ($tok -and $tok.Length -gt 20) ("len=" + $(if($tok){$tok.Length}else{0}))

echo "########## T5 self-check 6 items ##########"
$r = Req "GET" "/system/self-check" $null $tok
$d = Unwrap $r
Check "self-check 200" ($r.code -eq 200) ("code=" + $r.code + " raw=" + $r.raw.Substring(0,[Math]::Min(120,$r.raw.Length)))
if ($r.code -eq 200) {
  Check "check_count=6" ($d.summary.check_count -eq 6) ("count=" + $d.summary.check_count + " status=" + $d.status)
  foreach ($c in $d.checks) { echo ("     - " + $c.name + " [" + $c.level + "]  " + $c.detail.Substring(0,[Math]::Min(56,$c.detail.Length))) }
}

echo "########## T6 public-config ##########"
$r = Req "GET" "/auth/public-config" $null $null
$d = Unwrap $r
Check "public-config 200" ($r.code -eq 200) ("code=" + $r.code)
Check "self_register_enabled=false" ($d.self_register_enabled -eq $false) ("val=" + $d.self_register_enabled)

echo "########## T7 org tree (province -> city -> county) ##########"
$r = Req "POST" "/organizations" @{ name = "SmokeProvince"; code = "520000"; org_type = "government" } $tok
$prov = Unwrap $r
Check "create province 2xx" ($r.code -ge 200 -and $r.code -lt 300) ("code=" + $r.code + " raw=" + $r.raw.Substring(0,[Math]::Min(140,$r.raw.Length)))
$provId = $prov.id
$r = Req "POST" "/organizations" @{ name = "SmokeCity"; code = "520100"; org_type = "government"; parent_id = $provId } $tok
$city = Unwrap $r
Check "create city 2xx" ($r.code -ge 200 -and $r.code -lt 300) ("code=" + $r.code + " raw=" + $r.raw.Substring(0,[Math]::Min(140,$r.raw.Length)))
$cityId = $city.id
$r = Req "POST" "/organizations" @{ name = "SmokeCounty"; code = "520102"; org_type = "government"; parent_id = $cityId } $tok
$county = Unwrap $r
Check "create county 2xx" ($r.code -ge 200 -and $r.code -lt 300) ("code=" + $r.code + " raw=" + $r.raw.Substring(0,[Math]::Min(140,$r.raw.Length)))
$countyId = $county.id

echo "########## T8 negative: cross-level attach must 422 ##########"
$r = Req "POST" "/organizations" @{ name = "SmokeSkipLevel"; code = "520103"; org_type = "government"; parent_id = $provId } $tok
Check "skip-level rejected (422)" ($r.code -eq 422) ("code=" + $r.code + " raw=" + $r.raw.Substring(0,[Math]::Min(140,$r.raw.Length)))

echo "########## T9 negative: duplicate org code must fail ##########"
$r = Req "POST" "/organizations" @{ name = "SmokeDup"; code = "520100"; org_type = "government"; parent_id = $provId } $tok
Check "duplicate code rejected (4xx)" ($r.code -ge 400 -and $r.code -lt 500) ("code=" + $r.code)

echo "########## T10 re-run self-check sees org data ##########"
$r = Req "GET" "/system/self-check" $null $tok
$d = Unwrap $r
$orgCheck = $d.checks | Where-Object { $_.name -like "*单位码*" } | Select-Object -First 1
Check "org-code check present" ($null -ne $orgCheck) ("level=" + $orgCheck.level + " detail=" + $orgCheck.detail)

echo "########## SUMMARY ##########"
echo ("  PASS=" + $script:pass + "  FAIL=" + $script:fail)
