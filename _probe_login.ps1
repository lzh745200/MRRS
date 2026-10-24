
$base = "http://127.0.0.1:8010/api/v1"
$ErrorActionPreference = "Continue"
# raw login response (full)
$r = Invoke-WebRequest -Uri ($base + "/auth/login") -Method Post -Body (@{username="admin";password="Smoke#2026!Aa9"} | ConvertTo-Json) -ContentType "application/json" -UseBasicParsing -ErrorAction SilentlyContinue
echo ("LOGIN_STATUS=" + $r.StatusCode)
$r.Content
