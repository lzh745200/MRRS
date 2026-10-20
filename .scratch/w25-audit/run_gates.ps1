# 运行所有门禁脚本并记录真实退出码 + 输出
$ErrorActionPreference = 'Continue'
$py = ".\backend\.venv313\Scripts\python.exe"
$out = ".scratch\w25-audit\gate-results.txt"
if (Test-Path $out) { Remove-Item $out -Force }

$targets = @(
  @{n='backend/scripts/check_os_exit.py';            wd='.'; cmd='backend/scripts/check_os_exit.py'},
  @{n='backend/scripts/check_subprocess_encoding.py';wd='.'; cmd='backend/scripts/check_subprocess_encoding.py'},
  @{n='backend/scripts/check_dir_replace.py';        wd='.'; cmd='backend/scripts/check_dir_replace.py'},
  @{n='backend/scripts/check_unbounded_read.py';     wd='.'; cmd='backend/scripts/check_unbounded_read.py'},
  @{n='backend/scripts/check_upload_endpoints.py';   wd='.'; cmd='backend/scripts/check_upload_endpoints.py'},
  @{n='backend/scripts/check_scheduler_registration.py'; wd='.'; cmd='backend/scripts/check_scheduler_registration.py'},
  @{n='backend/scripts/check_soft_delete_usage.py';  wd='.'; cmd='backend/scripts/check_soft_delete_usage.py'},
  @{n='backend/scripts/check_foreign_keys.py';       wd='.'; cmd='backend/scripts/check_foreign_keys.py'},
  @{n='backend/scripts/check_admin.py';              wd='.'; cmd='backend/scripts/check_admin.py'},
  @{n='backend/scripts/check_rural_works.py';        wd='.'; cmd='backend/scripts/check_rural_works.py'},
  @{n='backend/scripts/check_schools.py';            wd='.'; cmd='backend/scripts/check_schools.py'},
  @{n='scripts/check_unused_scope_params.py';       wd='.'; cmd='scripts/check_unused_scope_params.py'},
  @{n='scripts/check_userdata_path_consistency.py'; wd='.'; cmd='scripts/check_userdata_path_consistency.py'},
  @{n='scripts/check_raw_sql_fstrings.py';           wd='.'; cmd='scripts/check_raw_sql_fstrings.py'},
  @{n='scripts/check_menu_alignment.py';            wd='.'; cmd='scripts/check_menu_alignment.py'},
  @{n='scripts/check_migrations.py';                wd='.'; cmd='scripts/check_migrations.py'},
  @{n='scripts/check_pragma_reasons.py';            wd='.'; cmd='scripts/check_pragma_reasons.py --diff-base auto --allow-missing-base --max-bare 0'},
  @{n='scripts/check_hardcoded_styles.py';          wd='.'; cmd='scripts/check_hardcoded_styles.py'},
  @{n='scripts/check_tokens_sync.py';               wd='.'; cmd='scripts/check_tokens_sync.py'},
  @{n='scripts/check_css_vars.py';                  wd='.'; cmd='scripts/check_css_vars.py'},
  @{n='scripts/check_branch_coverage.py';           wd='.'; cmd='scripts/check_branch_coverage.py --help'},
  @{n='scripts/security_audit.py';                 wd='.'; cmd='scripts/security_audit.py'},
  @{n='scripts/archive/check_alembic.py';           wd='.'; cmd='scripts/archive/check_alembic.py'},
  @{n='scripts/archive/check_ci.py';                wd='.'; cmd='scripts/archive/check_ci.py'},
  @{n='scripts/archive/check_ci_status.py';         wd='.'; cmd='scripts/archive/check_ci_status.py'},
  @{n='scripts/archive/check_safe_commit_imports.py'; wd='.'; cmd='scripts/archive/check_safe_commit_imports.py'}
)

foreach ($t in $targets) {
  Add-Content -Path $out -Value ("=" * 70)
  Add-Content -Path $out -Value ("SCRIPT: " + $t.n)
  Add-Content -Path $out -Value ("CMD:   " + $t.cmd)
  $log = ".scratch\w25-audit\gatelogs\" + ($t.n -replace '[\\/]','_') + ".log"
  New-Item -ItemType Directory -Force -Path (Split-Path $log) | Out-Null
  $sw = [Diagnostics.Stopwatch]::StartNew()
  & $py $t.cmd *> $log 2>&1
  $code = $LASTEXITCODE
  $sw.Stop()
  Add-Content -Path $out -Value ("EXIT:  " + $code + "   elapsed=" + [math]::Round($sw.Elapsed.TotalSeconds,1) + "s")
  Add-Content -Path $out -Value ("LOG:   " + $log)
  Add-Content -Path $out -Value ""
}
Write-Output "DONE"
