## v1.18.51 — 旧版备份恢复兼容性修复

### 修复

- 修复无 `alembic_version` 旧备份被误判为“表已齐全”直接 stamp head，导致恢复后缺 `account_package_exports` / `credential_expires_at` 等结构。
- 无版本号且表较多的旧库改为 `create_all` 补表 + `ALTER` 补列 + stamp head，避免重放迁移撞已有索引；极小旧库仍从基线重放。
- 新增跨版本备份兼容回归：旧库文件名、旧 `backup_info.json`、无版本表、更高版本拒绝。

### 验证

- 真实 v1.18.47 备份 3 份（`audit_chain_001` / `machine_recovery_001`）全部迁移到 `account_credential_expiry_001`：用户保留、`integrity_check=ok`、新表新列齐全。
- 完整恢复流程（快照→覆盖→uploads→迁移）通过；无版本旧库补齐到 122 表。
- CI 14/14 通过。

### 产物

- `MRRS-Setup-1.18.51-x64.exe`
- `SHA256SUMS-windows-x64.txt`
- ARM64 DEB 与对应 SHA256SUMS

请下载安装包与 SHA256SUMS 到同一目录后执行：

```bash
sha256sum -c SHA256SUMS-*.txt
```

全部为 `OK` 再安装。
