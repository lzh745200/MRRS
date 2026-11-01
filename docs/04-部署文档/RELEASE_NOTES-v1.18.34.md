# v1.18.34 发布说明 — 路线图长期项收口

发布日期：2026-11-01

## 谁需要升级

- **所有在用工位**：本版把 Electron 从已 EOL 的 33 升到 45（Chromium 安全补丁差距 12 个大版本），
  旧安装包的浏览器内核不再收到安全更新。
- **数据交换岗**：数据包导入改为「先演练、再确认」，导入前能看到新增/覆盖/拒绝的准确数量。
- **运维 / 系统管理员**：监控面板新增业务事件与慢请求 TOP，导入失败率可直接看到。

## 本版改动

### 1. Electron 33.3.1 → 45.2.1（安全寿命）

- 33 分支 2025-04-28 已 EOL，Chromium 130 与当前稳定版相差 12 个大版本；
  CVE-2025-6554（V8，CVSS 8.1，CISA KEV 在野利用）影响区间包含 130。
- 升级后验证：`node --check electron/main.js electron/preload.js`、`npm run test:electron`（23/23）、
  `electron-builder --dir --win --x64` 打包、冻结模块自检（`FROZEN_MODULE_CHECK_PASS`）、
  打包后端冷启动冒烟（liveness / health / version.json 全 200）。
- 真实 GUI 启动无法在非交互构建会话中验证（与 NSIS 卸载器同类限制），发布前以 CI 构建 +
  打包后端子进程冒烟为准；安装后请按「升级步骤」第 4 步做一次人工点检。

### 2. 两阶段导入：先演练、再确认

- 新增只读演练接口 `POST /api/v1/data-packages/{id}/dry-run`：返回每类「将新增 / 将覆盖 /
  将被拒」数量、拒绝明细与包信息，**不写库、不改包状态**；组织权限与确认导入同一口径。
- 前端「确认导入」前自动演练，弹窗摘要形如「本次将新增 6 条、覆盖 0 条、拒绝 4 条（合计 10 条）」；
  演练失败则不进入确认，零写入。
- 确认导入仍是 savepoint + 独占写锁的原子提交，中途失败整体回滚并把包标记为 failed。

### 3. 可观测性：业务事件与慢请求

- `GET /api/v1/system/metrics` 新增 `business`（数据包导入成功/失败、导出、备份创建/恢复、
  权限包导入计数）与 `observability`（慢请求摘要、慢请求 TOP5、数据包导入失败率）。
- 监控面板新增「业务事件（本次运行累计）」卡片与慢请求 TOP 列表；计数为进程内累计，
  **服务重启归零**（面板已注明，长期趋势请以日志/导出记录为准）。

### 4. 故障注入与并发用例

- 坏包演练必须抛 `BadZipFile`（端点转 400「数据包文件损坏」）。
- 确认导入中途异常：回滚、包标记 failed、失败计数 +1。
- `exclusive_write` 补互斥、超时、非 SQLite 放行三组用例，防止「没拿到锁却继续写」。

### 5. 依赖安全扫描

- 复核确认 PR Checks 的 `security` 作业已跑 `pip-audit -r backend/requirements.txt` 与
  `npm audit --omit=dev --audit-level=high`，本版不新增流水线步骤。

## 验证记录

| 项目 | 结果 |
|---|---|
| 后端全量（12 段独立进程） | **12/12 段 PASS，15,543 passed**；合并覆盖率 47,590 语句 / 11,956 分支 = **100.00%**（0 miss / 0 partial） |
| 前端全量 vitest | **348 文件 / 7,495 用例全通过** |
| 静态门禁（flake8 / type-debt / bare-returns / changelog / doc-numbers / 版本单源） | 全部通过：flake8 rc=0；mypy 77/77、`except Exception` 809/809（未恶化）；bare dict 241/244（NEW=0）；CHANGELOG 142 段；文档数字 846 端点 / 15,543 用例；`sync-version --check` ✅ |
| Electron 单测 | 23 passed |
| 打包冻结自检 | `FROZEN_MODULE_CHECK_PASS`（difflib + app.* 全收录） |
| 冷启动冒烟 | liveness / health / version.json 全 200 |
| main PR Checks | run 41329183881 **9/9 job 全绿** |
| CI 构建 | `Build Windows Installer (x64)` run 41332134601 **success**；`Build Self-Contained ARM64 Debian Package` run 41332134516 **success** |
| 发布资产 | Windows x64 `MRRS-Setup-1.18.34-x64.exe` 317,043,050 B / `f481dc87…3384ce`；ARM64 Electron deb 295,550,048 B / `9bdb2d08…57941d`；ARM64 standalone deb 105,107,032 B / `7a97577e…d8564e`；三份 `SHA256SUMS` 与 GitHub API digest 逐字一致 |

## 升级步骤

1. 先备份：系统管理 → 备份与存储 → 创建备份（确认文件已加密且下载/留存）。
2. 关闭应用（任务栏退出，确认进程结束）。
3. 运行新安装包覆盖安装（默认路径不变则数据/密钥沿用 `%LOCALAPPDATA%\bumofu-assistance\data`）。
4. 启动后点检：登录 → 工作台 → 数据管理 → 数据包列表点一次「演练」→ 打开监控面板看业务事件的
   计数是否随操作增加。

## 已知限制

- 安装包仍**未做代码签名**（无证书），Windows SmartScreen 首次运行会提示；如需签名，见
  `docs/04-部署文档/01-Windows部署/代码签名.md`。
- 组织模块策略默认 `shadow` 模式（只记日志与响应头 `X-Org-Module-Policy: would-block`，不拦截），
  确认无副作用后可用 `ORG_MODULE_POLICY_MODE=enforce` 切换到拦截。
- 权限包匿名导入仅限「库内还没有账号」的全新库，其余场景必须先登录管理员账号。
- 业务事件计数不持久化：重启归零，跨重启统计请用日志或导出记录。
- 本地 Windows 构建机的 NSIS 卸载器生成在非交互会话会挂死（环境限制），发布构建由 GitHub
  Actions 完成。
