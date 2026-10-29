# Release Notes — v1.18.26（2026-10-29）

> 上一正式发布是 **v1.18.25**；本版覆盖 v1.18.25 之后 main 上的 10 个提交，
> 以全库审计的认证/权限 Critical 修复为主。逐项账本见仓库根目录 `CHANGELOG.md`。

## 一、下载与校验

| 安装包 | 适用平台 |
|---|---|
| `MRRS-Setup-1.18.26-x64.exe` | Windows 10/11 x64（NSIS 安装包，含全部运行时） |
| `MRRS-Setup-1.18.26-arm64.deb` | 麒麟 V10 / 统信 UOS ARM64（Electron） |
| `assistance-management-system_1.18.26_arm64.deb` | 麒麟 V10 / 统信 UOS ARM64（standalone，无 Electron） |

同一 Release 附带 `SHA256SUMS-*.txt`（三个安装包指纹）与 `latest.yml` /
`MRRS-Setup-1.18.26-x64.exe.blockmap`（electron-builder 的 NSIS 产物，**本系统不消费**：
无自动更新逻辑，升级走覆盖安装）。

```powershell
Get-FileHash .\MRRS-Setup-1.18.26-x64.exe -Algorithm SHA256
```

> **未签名包提示**：证书尚未采购，首次运行会触发 SmartScreen（「更多信息」→「仍要运行」）。

## 二、认证与权限（4 个 Critical，审计八批 28 项）

- **refresh 完全绕过 `token_version` 吊销**：`validate_token` 只验签名/jti/type，不比对版本，
  而 access 链路有校验。登出或强退后，未随登出提交的 refresh（其他设备/被窃）仍能换发
  带新版本号的合法 access。现已补版本比对并在命中旧版本时吊销 refresh，
  负向回归 `test_refresh_rejects_stale_token_version`。
- **权限包可选认证绕过全部校验**：手写解码跳过黑名单 / `token_version` / `is_active` /
  首登改密四项，却被「重写全库 RBAC」的 `/permission-package/import`、`/confirm` 使用，
  已吊销令牌可远程改写整库权限。改为复用 `get_current_user` 完整链路。
- **权限/角色变更零审计**：`rbac.py` 8 个写路由 `AuditLogger` 出现 0 次。新增
  `_audit_permission_change()`，覆盖 assign/revoke role 与 grant/revoke/save permissions。
- **禁用账号未即时失效**：`is_active` 原先只在 `get_current_active_user` 校验，而绝大多数
  端点依赖 `get_current_user`。新增 `_reject_inactive_user()`，禁用后未过期 access 立即 403。

### 审计其余批次（数据面 / 契约 / 审计链）

- **未知 `DataScope` 列表过滤 fail-open**：`apply_scope_to_query` 兜底放行全量，与
  `check_record_access` 返回 `False` 的口径相反；改 `sa_false()` + warning，并加
  「两条路径必须同口径」回归。
- **`api_access_logs.user_id` 恒为 NULL**：中间件把 JWT `sub`（用户名）当 int 解析，
  访问日志无法按人归因；改为按用户名反查 `users.id`（有界缓存，异常不影响请求）。
- **全局搜索 LIKE 未转义（13 处）**：`q="%%"` 可枚举本域全表；新增 `_escape_like()`，
  全部 `ilike` 显式 `escape`。
- **`fund_lifecycle` 无项目归属记录跨组织可读写**：12 处守卫只在 `project_id` 有值时校验，
  空值时完全不校验；新增「创建人本人或管理员」兜底，其余 403，补 4 条负向用例。
- **`system/audit.py` 14 处内联角色比较漏掉 `is_superuser`**：超管标记但 role=user 的账号
  被误拒 403；统一改 `is_admin(current_user)`。
- **审计日志删除/备注自身不留审计**：三处破坏审计链的写操作补 `AuditLogger`
  （删除前快照关键字段、备注记录前后值），独立 Session 写入。
- **审计备注无入参模型**：`PATCH .../remark` 原 `body: dict` 无长度上限；新增
  `AuditRemarkUpdate(max_length=500)`，超长 422。
- **契约收敛**：改密响应改 `success_response()`；删除 `work_logs` 无效
  `response_model=dict`；审计详情裸 ORM 改为 11 字段白名单信封，避免全列外泄。
- **政策附件下载计数 best-effort**：计数失败不再让下载 500。
- **学校导入冗余临时文件**：删除从未读取的 15MB 级临时落盘；schema 与模型漂移改为 warning 可见。
- **`v-permission="[]"` fail-open**：无效用法分支只 warn 不隐藏；改为默认隐藏并补断言。

- **`/health/database-health` 泄露 DB 绝对路径**：库文件缺失时把部署路径写进匿名可访问的 message/issues；改为对外分类码 `DB_FILE_MISSING`，路径只进日志。
- **`UserCreate.phone_number/role_id` 是死字段**：users 表列名是 `phone`，注册链路传的电话被静默丢弃；schema 改名 `phone` 并补齐落库（兼容旧键名），`role_id` 删除并注明原因。

## 三、维护窗口与审计正确性

- **维护窗口豁免 `endswith` fail-open**：原实现 `("/system/backup/restore", "/shutdown")`
  的后缀匹配，会让任意以 `/shutdown` 结尾的**新写路由**自动继承豁免，静默绕过维护闸门。
  改为锚定正则，并补上此前漏登记的 `upload-restore`。
- **审计写入回滚业务事务**：`AuditLogService.log` 在调用方 Session 上 `add + commit`，
  失败时 `rollback()` 会把尚未提交的业务写入一并回滚，异常又被吞掉。改为独立
  `SessionLocal` 旁路审计，并补 `username`（原实现恒 NULL）；
  新增 `test_does_not_touch_caller_session`。
- **审计 `details` 含 `datetime` 整条丢失**：JSON 列无 `json_serializer`，驱动抛 TypeError
  被吞。新增 `_json_safe_value()` 入库前 round-trip。
- **恢复错误回传原文**：备份恢复把 `FileNotFoundError` / `ValueError` 原文（含本地绝对路径）
  返回前端；改为固定文案 + 日志留原文。
- **组织批量改删 fail-open**：操作者未绑定组织时过滤条件整体短路，可跨组织改删；
  改为三分支 fail-closed，并补 2 条负向用例。
- **`/system/env`** 收紧为管理员；**软删除记录**不再永久占用唯一编码，冲突提示给出
  可行动指引。

## 四、前端修复

- **学校分析页图表恒空**：请求 `page_size=1000` 越过后端 200 上限，每次进入都 422，
  被同一 `try` 吞掉只弹「加载学校分析数据失败」。改为按 200 分页拉全量 + 页数上限防御。
- **保存布局失败仍提示成功**：dashboard `saveLayout` watcher 缺 `try`；
  `SystemConsole` / `dataVerify` 的 `router.replace` 未 catch；`Role.vue` 删除失败吞掉
  后端原因 —— 均已修正。
- **3 处同名测试 F811 静默失效**：r16 双重失效、report_templates 覆盖版本缺 `finally`、
  recommendation 整类复制两遍 —— 已重命名并恢复有效断言。

## 五、质量与门禁

- 启用 SQLAlchemy mypy 插件，mypy **1310 → 880**（消除 420 个误报）；
  `rbac_service._log_access` 形参放宽为 `Optional[str]`。
- `as any` 保持 **0**；静默吞异常 **0**；统一门禁 **34/34 PASS**。
- 门禁基线按实测同步：`broad_except` 801→802、后端用例 **14,953**、locations 清单刷新。

## 六、验证（发布前本地实测）

- 统一门禁入口 `backend/.venv/Scripts/python.exe scripts/run_gates.py`：**34 道 PASS**；
- 后端全量：**14,953 用例**（分段/CI 口径以 `backend-test` 为准）；
- 前端：**347 个测试文件 / 7,420 用例**，生产构建成功；
- Electron：`npm run test:electron` **14/14**（含 AES-GCM 往返/篡改/短文件守护）；
- 安装冒烟：安装包 payload 解包后启动内置后端，`/health` 返回 1.18.26 /
  `migration.at_head=true` / WAL、时钟正常；**NSIS 静默安装未能在本执行环境落盘**（见第八节）。
- **ARM64 未在本机实测**：本机无 ARM64 硬件/容器；仅验证 CI 产物与 `SHA256SUMS-*.txt`。

## 七、升级注意

- 无数据迁移；升级方式不变：下载对应平台安装包 → 覆盖安装，数据库与上传目录不受影响，
  详见 `docs/04-部署文档/OFFLINE_UPGRADE.md`；
- 行为变化：禁用账号立即失效；权限包导入/确认要求完整认证；`/system/env` 仅管理员；
- 旧的 refresh token 在升级后会因版本校验失败被要求重新登录一次（符合吊销语义）。

## 八、本机构建与冒烟记录

- **源码冻结点**：`34bf9d9f`（含全库审计第 1~8 批；第 9 批 schema 在途改动已备份到
  `backup/parallel-batch9-2026-10-29`，不进入本版）。
- **Windows x64 安装包**：`dist/electron/MRRS-Setup-1.18.26-x64.exe`（223 MB，
  FileVersion/ProductVersion = 1.18.26）。
  SHA256：`dcbed210a0ad2b569c97757fb7932f8a6763eb286950022e9207a18f6546cbff`。
- **构建命令**：
  `cd frontend && npm run build` → `npm run build`（PyInstaller onedir + electron-builder）
  → 前端最终重建后 `./node_modules/.bin/electron-builder --win --x64` 重打包。
- **打包内容核对**：`resources/frontend/version.json` = 1.18.26（buildTime
  `2026-10-29T08:57:53Z`）；`app.asar` package version = 1.18.26；
  未打包 `tests/`、`conftest.py`、`pytest.ini`。
- **运行时冒烟**：安装包 payload 解包 3,093 项 → 启动
  `resources/backend/assistance-backend/assistance-backend.exe`（隔离 APPDATA、端口 18026）
  → `/health` 200：`version=1.18.26`、`git_hash=34bf9d9f`、
  `migration.at_head=true`、`journal_mode=wal`、`clock.status=ok`。
  证据：`deliverables/smoke-health-1.18.26.json`。
- **NSIS 安装器限制（未完成）**：本执行环境禁止跨目录写文件（工作区内/外均 0 files；
  7-Zip 解包到 `C:\` 直接 `Cannot create folder`），安装器静默执行返回 0/2 且未落盘；
  验证期间检测到旧 v1.18.17 安装已被升级逻辑移除（用户数据未删）。
  **发布前需在普通 Windows 桌面手工执行一次 `MRRS-Setup-1.18.26-x64.exe` 安装/卸载冒烟**；
  在该项完成前，本版状态为“有条件发布”。
