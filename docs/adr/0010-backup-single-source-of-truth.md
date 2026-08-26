# ADR-0010: 自动备份机制统一（唯一真相源）

- 状态: 已采纳（2026-08）
- 决策人: 后端/前端/桌面端协同
- 关联票据: T044（v1.10.0 polish）

## 背景

此前自动备份存在"四套并存"的真相源：

1. **后端 scheduler**（`backup_scheduler.auto_backup_job`）：每日 02:00 触发，但 `get_backup_schedule` 端点被硬编码为"已永久禁用"，且清理按 `max_backup_count`（份数）而非天数。
2. **REST 端点** `/system/backup/schedule`：返回写死的 `enabled: False`，`update` 端点"保留兼容"不落库。
3. **Electron 主进程**（`electron/main.js`）：自有 7 天清理逻辑，直接调用 DELETE 删除旧备份。
4. **`DEFAULT_CONFIGS`**（`system_config_service.DEFAULT_CONFIGS`）：`auto_backup` 默认 `"false"`，是 `get_config` 在无行时的真实默认值。

四套互相矛盾，管理员在 UI 改了策略也不生效，Electron 与后端的清理策略还可能打架。

## 决策

**后端 scheduler 为唯一真相源**，配置统一存放在 `SystemConfig`：

| 配置键 | 默认值 | 含义 |
|--------|--------|------|
| `auto_backup` | `"true"` | 是否启用（DEFAULT_CONFIGS 改为 true） |
| `backup_retention_days` | `"7"` | 保留天数（新增，过期自动清理） |
| `backup_schedule_cron` | `"0 2 * * *"` | 调度表达式（每日 02:00） |

落地要点：

- `GET /system/backup/schedule` 读取上述配置并返回 `enabled` / `keepCount` / `nextRun`；无配置时回退默认值（DEFAULT_CONFIGS）。
- `PUT /system/backup/schedule` 写入 `SystemConfig`（`set_config`），**热生效**——下次 scheduler 循环与后续 GET 立即反映，无需重启。
- `auto_backup_job`：默认开启；备份完成后调用 `BackupService.cleanup_by_retention_days(retention_days)` 按天数清理（取代旧的按份数 `cleanup_old_backups`）。
- **Electron 仅触发**：`performAutoBackup` 只 POST 创建备份，移除自有的 `cleanupOldBackups`（清理职责完全交给后端）。
- 前端 `BackupManagement.vue` 抽出 `useBackupSchedule` composable：保存后**回读** GET，保证与后端一致。

## 后果

- 管理员在 UI 配置的策略真实生效，单一可解释来源。
- Electron 不再维护备份策略，升级后端即可改策略。
- 默认开启自动备份（每日 02:00，保留 7 天），符合单机离线场景的数据安全预期；磁盘敏感场景可由管理员显式关闭。

## 验收（见 tests/unit/test_backup_schedule_unify.py + frontend useBackupSchedule.test.ts）

- 端点 GET 默认 `enabled=true` / `keepCount=7`。
- 端点 PUT 写入后 GET 回读一致（热生效）。
- `cleanup_by_retention_days` 按保留天数删除过期备份（fake clock 单测）。
- 前端 `saveSchedule` 发送 `keep_count` 并回读，`scheduleConfig` 与后端一致。
- Electron `cleanupOldBackups` 已删除，仅保留触发。
