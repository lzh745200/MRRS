
$base = "http://127.0.0.1:8010/api/v1"
$ErrorActionPreference = "Continue"
try {
  $resp = Invoke-WebRequest -Uri ($base + "/auth/login") -Method Post -Body (@{username="admin";password="zgcZGC733035#"} | ConvertTo-Json) -ContentType "application/json" -UseBasicParsing
  echo ("LOGIN=" + $resp.StatusCode)
  $j = $resp.Content | ConvertFrom-Json
  echo ("TOP_KEYS=" + ($j.PSObject.Properties.Name -join ","))
  echo ("DATA_KEYS=" + ($j.data.PSObject.Properties.Name -join ","))
  echo ("must_change_password=" + $j.data.must_change_password)
  $tok = $j.data.access_token
  echo "--- CSRF ---"
  $csrf = Invoke-WebRequest -Uri ($base + "/auth/csrf-token") -Headers @{ Authorization = "Bearer $tok" } -UseBasicParsing
  echo ("CSRF=" + $csrf.StatusCode + " " + $csrf.Content.Substring(0,[Math]::Min(200,$csrf.Content.Length)))
  echo "--- write without CSRF ---"
  try {
    $w = Invoke-WebRequest -Uri ($base + "/organizations") -Method Post -Body (@{name="X";code="520000"} | ConvertTo-Json) -ContentType "application/json" -Headers @{ Authorization = "Bearer $tok" } -UseBasicParsing
    echo ("WRITE_NO_CSRF=" + $w.StatusCode)
  } catch {
    echo ("WRITE_NO_CSRF_ERR=" + [int]$_.Exception.Response.StatusCode)
    try { $sr = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream()); echo ("  detail=" + $sr.ReadToEnd()) } catch {}
  }
} catch {
  echo ("ERR=" + $_.Exception.Message)
}
