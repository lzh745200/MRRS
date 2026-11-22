# v1.18.61 发布说明 — 权限治理地基 + 可靠性收口

> 发布：2026-11-22 ｜ 版本：`1.18.61`

## 一、本版内容

### 权限动作目录

- 目录只收录 **54 个可导航动作页**（48 个 `page` + 6 个 `console`），排除 15 个无 `path`
  的 legacy key，避免勾选界面出现“勾了也没有入口”的假页面。
- 6 个 `system-console-*` 页面重新纳入，并补齐 `page → module` 映射，系统管理写权限
  可以在页面级表达。
- 目录口径：**54 页面 / 32 模块级 / 212 动作码 / 17 条 legacy 别名 / 7 条单数别名**。
- `data:*` / `approve:*` 不再用 `*` 扫全目录：
  - `data:create` 不会获得 `roles` / `users-orgs` / `system` 写权限；
  - `approve:*` 只映射到 `approval`；
  - `data:export` 只给报表导出写权限；
  - `system/user/org/role:manage` 明确映射到模块级，`report:manage` 映射两个报表页。

### 有效权限解析器

新增 `effective_permission_service`：

- 复用 RBAC 权限、`allowed_permissions` 白名单与机器码扣减；
- 复用单位授权矩阵和菜单两条互斥分支；
- 支持 legacy 双读、单数前缀归一、矩阵 active 时按 `page_modules` 收窄写/删；
- 只读页（dashboard / bigscreen）不会被模块交集误删；
- 进程内按 `permissions_version + grant_version` 缓存；
- 7 例测试，模块行/分支覆盖 100%。

> **重要边界**：解析器尚未接入路由/中间件，本版不改变现有线上判权；动作级运行时守卫
> 与 `check_action_coverage.py` 仍属下一阶段，避免在军审口径下一次性替换数百个接口。

### 门禁与体验

- `check_permission_catalog.py` 扩到 **11 条断言**，已接入 `run_gates.py` 与 CI
  `stack-alignment`。
- `TaskManager` 自动刷新失败不再完全静默：只提示一次，保留手动刷新。
- `BackupManagement` 恢复备份后的 2 秒登录跳转定时器，在组件卸载/重复恢复时清除。

## 二、验证

- 后端 **16,085** 用例；前端 **351 文件 / 7,587 用例**。
- `permission_catalog` / `effective_permission_service` 行分支覆盖 **100%**。
- `check_permission_catalog`、`run_gates --only permission_catalog`、`check_changelog`、
  `check_doc_numbers --full`、`check_update_log`、`sync-version --check` 全通过。
- 完整 PR Checks、Windows x64 + ARM64 构建按 v1.18.61 重跑。

## 三、安装/升级

1. 下载 `MRRS-Setup-1.18.61-x64.exe` 与 `Install-MRRS.cmd`、`MRRS-Installer-Helper.ps1` 到同一目录。
2. Windows 优先双击 `Install-MRRS.cmd`：自动选择可写且空间充足的 TEMP 再启动安装器。
3. 直接双击安装包也可；若出现 `NSIS Error / Error creating mmap`，改用 `Install-MRRS.cmd`。
4. 升级前关闭客户端；安装器会先 `ExecWait taskkill /T` 结束旧进程。
5. 安装后启动，确认 `/health` 返回 `1.18.61`。

## 四、发布资产

- `MRRS-Setup-1.18.61-x64.exe` + `.blockmap` + `latest.yml`
- `Install-MRRS.cmd`、`MRRS-Installer-Helper.ps1`、`MRRS-Shortcut-Repair.ps1`
- `SHA256SUMS-windows-x64.txt`
- ARM64 Electron deb / standalone deb + SHA256SUMS

## 五、仍属下一阶段

- 动作级 `require_permission` 路由覆盖与 shadow/enforce 灰度；
- `check_action_coverage.py` 写路由覆盖棘轮；
- `/uploads` 签名 URL、分片上传扩展名白名单、自动打包“日历月 vs 30 天”、
  数据质量全量聚合等产品决策项。
