# Release Notes — v1.18.27（2026-10-30）

> 上一正式发布是 **v1.18.26**；本版覆盖 v1.18.26 之后 main 上的提交，
> 以「**审计修复在真实库上真正落地**」为主线。逐项账本见仓库根目录 `CHANGELOG.md`。

## 一、下载与校验

| 安装包 | 适用平台 |
|---|---|
| `MRRS-Setup-1.18.27-x64.exe` | Windows 10/11 x64（NSIS 安装包，含全部运行时）|
| `MRRS-Setup-1.18.27-arm64.deb` | 麒麟 V10 / 统信 UOS ARM64（Electron）|
| `assistance-management-system_1.18.27_arm64.deb` | 麒麟 V10 / 统信 UOS ARM64（standalone，无 Electron）|

同一 Release 附带 `SHA256SUMS-*.txt`（三个安装包指纹）与 `latest.yml` /
`MRRS-Setup-1.18.27-x64.exe.blockmap`（electron-builder 的 NSIS 产物，**本系统不消费**：
无自动更新逻辑，升级走覆盖安装）。

```powershell
Get-FileHash .\MRRS-Setup-1.18.27-x64.exe -Algorithm SHA256
```

> **未签名包提示**：证书尚未采购，首次运行会触发 SmartScreen（「更多信息」→「仍要运行」）。

## 二、本版修了什么（4 项，都不是新功能）

### 1. 老库落后 4 个迁移 —— 审计修复在真实库上一条都没生效

`backend/data/rural_revitalization.db` 的 `alembic_version` 曾停在 `r43_prune_dead_columns_001`，
而 head 是 `fk_machine_codes_created_by_001`。升级前实测：**5 个 PII 列仍是 `VARCHAR(20)`**、
重复索引 7 组仍在、`machine_codes.created_by` 仍 `NO ACTION`。

根因：空库由 `001_baseline` 的 `create_all()` 直接按新模型建表，**空库永远是对的**；
老库必须手动 `alembic upgrade head`。升级后实测：PII 8 列全部 `VARCHAR(256)`、
冗余索引 8 个已删（重复组归零）、`created_by` 外键 `SET NULL` 已补、**数据零丢失**。

> ⚠️ **升级本版时请务必执行一次 `alembic upgrade head`**（安装包内的数据库同样适用）。

### 2. 外键迁移被整表 DDL 误判跳过

`fk_machine_codes_created_by_001.rewrite_fk_ddl` 用 `if "ON DELETE SET NULL" in ddl.upper()`
判断「已经改过」，但整张 `machine_codes` 的 DDL 里 `user_id` 那条外键**本来就带**该子句 ——
于是每次都误判跳过。改为只匹配 `created_by` **那一条**子句。

### 3. Nightly 覆盖率 99.97% < 100

缺口是 `app/utils/audit_logger.py` 第 51、54-56 行 —— `_json_safe_value` 的两个防御分支
（`value is None` 提前返回、序列化失败降级）。已补 3 例（用循环引用触发 `ValueError`）。

### 4. 学校 Excel 导入静默写入空编码

`schools.code` 是跨机数据包的匹配键，列 `UNIQUE` 但 SQLite 允许多个 NULL 并存 ——
原导入逻辑无编码时静默写 `None`，能积累任意多条「无编码」学校，导出/导入按 code 配对
全部落空且**没有任何提示**。改为**跳过并计入 errors**，用户可见。

## 三、验证

| 检查 | 结果 |
|---|---|
| main PR Checks（commit `7c0a9639`）| **success**，32m36s |
| 后端全量 | 14,994 用例通过，覆盖率 **100%**（CI 门禁）|
| 前端全量 | 348 文件 / 7,428 用例通过 |
| 后端 flake8（app 全量）| **0** |
| 迁移链 | 单 head，66 版本，无分叉 |
| 四层对齐 / 文档数字 / 更新日志 | 全部 ✓ |
| Windows x64 安装包 | 构建 **success** |
| ARM64 deb（Electron + standalone）| 构建 **success** |

## 四、已知限制（与 v1.18.26 相同，未变）

- 安装包未签名（证书未采购）。
- 完全离线运行，不联网检查更新。
- `schools.code` 列仍允许 NULL（API 层可选是既有兼容契约）；本版只修「导入静默写 None」，
  未收紧为 NOT NULL —— 若你的部署里存在空编码学校，请手工补齐后再导出数据包。
- 按钮级细粒度权限目前只覆盖 3/26 个快捷入口，其余依赖后端校验兜底。
