# v1.18.43 发布说明 — 系统管理优化批次

> 发布：2026-11-15 ｜ 提交：`41a5348a` ｜ 标签：`v1.18.43`
> 完整变更账本见根目录 `CHANGELOG.md`；本页面向部署与验收。

## 一、本版重点

1. **CI 后端 4 分片矩阵**：按实测耗时装箱拆分 12 段；同名 `backend-test` 聚合 job 统一 `coverage combine`、100% 与分支棘轮、Codecov；分片失败聚合 job 必失败。`BACKEND_TEST_SHARDS=0` 可回退旧的单作业串行路径。
2. **表单选项服务端下发**：`GET /users/form-options` 聚合角色、数据范围、权限项、组织树，支持 ETag/304；用户管理前端消费服务端选项，消除“能选但提交 403”。
3. **Electron 凭据托管**：主进程 `safeStorage` 认证仓 + preload 同步 IPC；持久 token/user/refresh 在 Electron 下不再落 localStorage。浏览器保留开发兼容路径，生产建议 Electron。
4. **任务可靠性**：系统任务页明确标注“演示任务”；新增 `POST /async-export/tasks/{task_id}/retry`，失败/过期导出可复制参数重试；中断导出在启动时置 failed，避免重放。
5. **授权策略门面**：新增 `authorize(actor, action, resource, scope)`，支持 `off/shadow/enforce`；`require_admin`/`require_superuser` 已接入，默认 `off`。
6. **可观测性**：慢 SQL 增加轮转 JSONL（默认 `logs/slow-sql.jsonl`）；路由增加 p50/p95/p99 与 5xx 计数，并入 `/system/metrics`。
7. **审计与数据包签名**：`audit_logs` 增加可选 `prev_hash/payload_hash` 与校验脚本 `scripts/verify_audit_chain.py`；`.rrs` 增加可选 detached Ed25519 签名（独立 `SYNC_PACKAGE_*` 配置，默认允许未签名并 warn）。

## 二、新增配置

```dotenv
# 授权策略门面：off（默认）/ shadow（只记录差异）/ enforce
AUTHORIZE_MODE=off

# 审计链：默认关闭；开启后 audit_logs 写 prev_hash/payload_hash
AUDIT_CHAIN_ENABLED=false

# 跨机 .rrs 来源签名（可选，独立于 GRANT_* / PACKAGE_*）
SYNC_PACKAGE_SIGNING_KEY=
SYNC_PACKAGE_PUBKEY=
SYNC_PACKAGE_ALLOW_UNSIGNED=true
```

> 以上默认值均为零行为变化；生产启用 `AUDIT_CHAIN_ENABLED` 前，请先确认审计删除/归档流程，避免物理删除造成链断裂。

## 三、验证结果

| 验证项 | 结果 |
|---|---|
| 后端全量 | 15,828 passed；覆盖率 100%（4 分片合并 + 分支棘轮） |
| 前端全量 | 348 文件 / 7,523 passed；覆盖率 100% |
| Electron | 23 passed |
| PR Checks | 14/14 作业 success |
| 迁移 | 单 head `audit_chain_001`；空库与旧库自证通过 |
| 安装包 | Windows x64 / ARM64 Electron / ARM64 standalone 三包构建成功 |

## 四、安装包

| 包 | 大小 | 说明 |
|---|---:|---|
| `MRRS-Setup-1.18.43-x64.exe` | 318,778,264 B | Windows 10/11 x64（CI Release 资产） |
| `MRRS-Setup-1.18.43-arm64.deb` | 295,752,546 B | 麒麟/国产 ARM64 Electron 桌面版 |
| `assistance-management-system_1.18.43_arm64.deb` | 105,242,532 B | 麒麟/国产 ARM64 standalone Web 版 |

> GitHub Release 资产由 CI 构建机产出；构建机未拷入离线瓦片，因此 x64 Release 包不含 70MB 地图瓦片。需要瓦片的交付可在构建机先执行 `python scripts/tiles/verify_tiles.py --require-min 1` 并拷入 `resources/map-tiles` 后本地构建。

## 五、升级步骤

1. 备份：系统管理 → 备份与存储 → 创建备份，记录备份密码。
2. 覆盖安装对应架构安装包：
   - Windows：运行 `MRRS-Setup-1.18.43-x64.exe`。
   - ARM64：`sudo dpkg -i MRRS-Setup-1.18.43-arm64.deb` 或 standalone 包。
3. 启动后确认：
   - 登录页/关于页显示 `1.18.43`；
   - `GET /health` 返回 `status=ok`、`migration.head=audit_chain_001`；
   - `GET /api/v1/system/version` 返回 `1.18.43`。
4. 如需启用审计链/数据包签名，先按第二节配置密钥与开关，再重启后端。

## 六、已知边界

- 审计链默认关闭；物理删除改逻辑封存仍待军审口径确认。
- 导出任务采用“持久化 ExportTask + 启动置 failed + 手动重试”，不自动续跑。
- ARM64 包仅完成构建验证，未在 ARM 真机安装。
