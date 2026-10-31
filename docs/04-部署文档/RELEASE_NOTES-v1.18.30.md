# Release Notes — v1.18.30（2026-10-31）

> 上一正式发布是 **v1.18.29**；本版覆盖其后的提交，主线是**安全契约对齐**
> （组织建根权限、任务列表归属、数据库异常只回类名、登录超管标记、组织下拉取值链路）。
> 逐项账本见仓库根目录 `CHANGELOG.md`。

## 一、下载与校验

| 安装包 | 适用平台 |
|---|---|
| `MRRS-Setup-1.18.30-x64.exe` | Windows 10/11 x64（NSIS 安装包，含全部运行时）|
| `MRRS-Setup-1.18.30-arm64.deb` | 麒麟 V10 / 统信 UOS ARM64（Electron）|
| `assistance-management-system_1.18.30_arm64.deb` | 麒麟 V10 / 统信 UOS ARM64（standalone，无 Electron）|

同一 Release 附带 `SHA256SUMS-*.txt` 与 `latest.yml` /
`MRRS-Setup-1.18.30-x64.exe.blockmap`（electron-builder 的 NSIS 产物，**本系统不消费**：
无自动更新逻辑，升级走覆盖安装）。

```powershell
Get-FileHash .\MRRS-Setup-1.18.30-x64.exe -Algorithm SHA256
```

> **未签名包提示**：证书尚未采购，首次运行会触发 SmartScreen（「更多信息」→「仍要运行」）。

## 二、本版修了什么


### Fixed（CI 两处测试未跟上安全守卫 —— 修复后 backend-test 应转绿）

`85637fc5`（系统管理域审计收口）加了两个守卫，配套测试未同步，导致 backend-test 段 2 例失败：

1. **`create_organization` 要求超管才能建根组织**（organization.py:793）——
   `test_cov_final_organization.py::test_is_active_defaulted_when_absent` 仍用
   `is_superuser=False` 的用户建根（520000），被 403 拦截。
   该用例意图是验证 `is_active` 默认值而非建根权限 → 用户改为超管，守卫另测。

2. **M6 任务列表按归属过滤**（tasks.py `_visible_tasks`）——
   `test_r12_low_risk_batch_20260913.py::test_list_endpoint_purges_expired` 传
   `current_user=None`（非管理员），`created_by="root"` 的 live 记录被滤掉 → total 0≠1。
   该用例意图是「列表端点触发过期清理」而非权限过滤 → 传管理员 user，过滤另测。

**验证**：flake8 0 · 两个文件 19 例全过 · organization/task 相关域 **417 passed**。

### Fixed（安装包可安装但无法启动）

**根因**：`backend/backend_linux_arm64_standalone.spec` 把标准库 `difflib`
列入 `excludes`，而 `app/services/data_cleaning_service.py` 顶层执行
`from difflib import SequenceMatcher`。v1.18.29 的 ARM64 Electron 包复用
standalone 后端产物，安装后后端启动即 `ModuleNotFoundError: No module named
'difflib'`，Electron 自动重启 3 次后退出。

**修复**：
- standalone spec 删除标准库排除项，`difflib` 显式加入 `hiddenimports`；
  统一 spec 同步显式声明，避免未来 excludes 漂移。
- 新增 `scripts/verify_frozen_modules.py`：直接读取 onedir 产物的
  CArchive/PYZ 模块表，校验 `difflib`、入口链与**全部 379 个 `app.*` 模块**。
- Windows、ARM64 Electron、standalone DEB、deb-complete 四条打包链路全部
  接入该门禁：模块漏收在构建期失败，不再等到装机后启动才暴露。
- `start.py` 增加 `BACKEND_IMPORT_CHECK=1` 手动自检入口（只 import，不监听端口）。

**验证**：本地重建 Windows 冻结产物，门禁输出 `difflib` 与 379 个 `app.*`
全部收录；数据质量路由 21 例通过；`vue-tsc`、前端构建、系统管理前端 759 例
与全量分片测试均通过。

### Fixed（构建与安装）

- ARM64 standalone spec 不再排除标准库 `difflib`，并显式加入隐藏导入
- 新增冻结产物模块门禁，校验 `difflib`、入口链与全部 379 个 `app.*` 模块
- Windows / ARM64 Electron / standalone DEB / deb-complete 四条出包链路全部接入门禁
- 后端启动增加 `BACKEND_IMPORT_CHECK` 自检入口，构建期即可验证产物可导入

## 三、验证

| 检查 | 结果 |
|---|---|
| main PR Checks（`e20b0631`）| **success**（9 个作业全部通过：backend-test / frontend-check / e2e-test / security / lint / static-analysis / stack-alignment / upgrade-rehearsal / windows-smoke）|
| 后端全量 | 15,101 用例，覆盖率 **100%**（CI 门禁）|
| 前端全量 | 349 文件 / 7,469 用例通过 |
| 迁移链 | 单 head，66 版本，无分叉 |
| 四层对齐 / 文档数字 / 更新日志 | 全部 ✓ |

## 四、已知限制

- 安装包未签名（证书未采购）。
- 完全离线运行，不联网检查更新。
- `schools.code` 列仍允许 NULL（API 层可选是既有兼容契约）；导入侧已改为「缺编码的行跳过并计入 errors」，不再静默写 None。
- 按钮级细粒度权限目前只覆盖 3/26 个快捷入口，其余依赖后端校验兜底。

> **升级提醒**：使用旧数据库的部署，升级后请执行一次 `alembic upgrade head`，
> 否则 PII 列宽（256）、索引去重、外键 ondelete 等历史修复不会在既有库上生效。

