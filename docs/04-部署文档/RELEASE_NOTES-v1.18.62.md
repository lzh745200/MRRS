# v1.18.62 发布说明 — 权限解析 fail-closed 与大屏 Token 复核

> 发布：2026-11-22 ｜ 版本：`1.18.62`

## 一、本版内容

### 安全与正确性

- **矩阵已启用但授权为空时 fail-closed**：解析器原以“是否有模块授权”决定是否收窄，
  而“矩阵未启用”和“矩阵已启用但授权被清空”都表现为空授权。后者会跳过收窄、保留
  RBAC 全部动作，出现“菜单几乎为空、动作却全放行”的倒挂。现改按 `matrix.active`
  收窄：空授权只保留页面可见性允许的读，写/删/授权管理一律不放行。
- **缓存口径修正**：`users.permissions_version` 尚未落库（统一权限方案第 4 步），
  原缓存键恒为 0，角色、直授权、机器码变化都不会失效。现在只有用户对象确实暴露
  `permissions_version` 时才启用缓存；真实 `User` 暂不缓存。缓存命中不再先查单位矩阵，
  一次解析只读取一次矩阵。

### 大屏与门禁

- **BigScreen 字号 Token 串色**：`font-size` 误用颜色 Token `--bs-text-body`
  （`#cfe7ff`），变量解析成功但字号值非法、回退不生效。改用
  `--bs-title-size` / `--bs-kpi-size` / `--bs-label-size` / `--bs-chart-title-size`，
  删除页内失效的 `--bs-distance-scale`，并新增源码级回归断言。
- **package_contract 基线补齐**：`data_checksums`、`include_unassigned`、
  `unassigned_counts` 三个字段在 schema 已存在但 v1.18.60 基线漏登，曾使门禁变红；
  本版随变更记录，门禁恢复绿。
- `permission_catalog` 去除 `households` 在 `DATA_ALIAS_KEYS` 模块段的重复项，口径不变。

### 对 v1.18.61 说明的更正

v1.18.61 发布说明中的两处口径在本版更正：

1. 解析器测试为 **11 例**（v1.18.61 写 7 例；本版新增 4 例安全/缓存回归）。
2. 解析器**并非**已对真实用户启用“permissions_version + grant_version”缓存：
   该列属于方案第 4 步、尚未落库，本版仅在用户对象暴露该属性时启用缓存。

> 解析器仍未接入路由/中间件，不改变现有线上判权；动作级运行时守卫属下一阶段。

## 二、验证

- 后端 **16,089** 用例；前端 **351 文件 / 7,588 用例**。
- `permission_catalog` / `effective_permission_service` 行分支覆盖 **100%**。
- `check_permission_catalog`、`check_doc_numbers --full`、`check_changelog`、
  `check_update_log`、`sync-version --check`、`check_hardcoded_styles`、
  菜单/console 映射、`check_package_contract` 全通过。
- 完整 PR Checks、Windows x64 + ARM64 构建按 v1.18.62 重跑。

## 三、安装/升级

1. 下载 `MRRS-Setup-1.18.62-x64.exe` 与 `Install-MRRS.cmd`、`MRRS-Installer-Helper.ps1` 到同一目录。
2. Windows 优先双击 `Install-MRRS.cmd`：自动选择可写且空间充足的 TEMP 再启动安装器。
3. 直接双击安装包也可；若出现 `NSIS Error / Error creating mmap`，改用 `Install-MRRS.cmd`。
4. 升级前关闭客户端；安装器会先 `ExecWait taskkill /T` 结束旧进程。
5. 安装后启动，确认 `/health` 返回 `1.18.62`。

## 四、发布资产

- `MRRS-Setup-1.18.62-x64.exe` + `.blockmap` + `latest.yml`
- `Install-MRRS.cmd`、`MRRS-Installer-Helper.ps1`、`MRRS-Shortcut-Repair.ps1`
- `SHA256SUMS-windows-x64.txt`
- ARM64 Electron deb / standalone deb + SHA256SUMS

## 五、仍属下一阶段

- 动作级 `require_permission` 路由覆盖与 shadow/enforce 灰度；
- `check_action_coverage.py` 写路由覆盖棘轮；
- `users.permissions_version` 迁移与统一权限方案第 3/4 步接线。
