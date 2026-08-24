$ErrorActionPreference = "Stop"
Set-Location C:\actions-runner
if (-not (Test-Path .\app)) { New-Item -ItemType Directory app | Out-Null }
Expand-Archive -Path .\win64.zip -DestinationPath .\app -Force
Copy-Item .\.regtok .\app\.regtok -Force
Set-Location .\app
.\config.cmd --unattended --url "https://github.com/lzh745200/MRRS" `
  --token ((Get-Content .regtok -Raw).Trim()) `
  --name "mrrs-win-1" --labels "self-hosted,windows-2022,x64" `
  --work "_work" --replace --runasservice --windowslogonaccount "NT AUTHORITY\NETWORK SERVICE"
.\svc.cmd install
.\svc.cmd start
Start-Sleep -Seconds 10
Get-Service | Where-Object { $_.Name -like "actions.runner*" } | Format-Table Name, Status -AutoSize
