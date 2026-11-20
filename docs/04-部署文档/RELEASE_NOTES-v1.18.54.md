# v1.18.54 发布说明 — 版本元数据与发布链路修复

> 发布：2026-11-20 ｜ 版本：`1.18.54`
> 完整变更账本见根目录 `CHANGELOG.md`；本页面向部署与验收。

## 一、本版重点

1. **版本元数据随包分发**：三个 PyInstaller spec（Windows / ARM64 Electron / ARM64 standalone）均收集 `backend/version.json`；`VersionService` 缺文件时不再向安装目录写“当天日期 + 泛化描述”的伪版本。
2. **版本接口去硬编码**：`GET /api/v1/system/version` 的 `release_date` / `description` 改读版本文件；官方 v1.18.53 返回 `2026-04-25` 的问题在本版修复为 `2026-11-20`。
3. **构建来源门禁**：`npm run check:provenance` 检查脏工作区、tag/版本不一致、复用已发布版本；交付构建不得使用 `ALLOW_DIRTY_BUILD=1`。
4. **安装器残留清理**：NSIS `customInit` 安装前清理旧 `_internal/alembic/versions`，避免旧版本已移除的迁移继续被 Alembic 加载。
5. **发布资产校验**：构建后校验 `latest.yml`/`blockmap`/`SHA256SUMS`；Release 上传后通过 GitHub API 比对 size/digest 与 Release 正文，任一项不符发布作业变红。

## 二、验证

- 版本端点、VersionService、spec 打包回归 **48 例通过**；发布资产门禁 **38 例通过**。
- 干净 worktree 重新 PyInstaller 构建：`_internal/version.json` 存在且内容与版本一致；启动后 `/api/v1/system/version` 返回正确 `release_date` 与 `description`。
- ASGI/打包后端的 `/health`、`/api/v1/system/version` 与安装包启动链均已复验。
- 官方 v1.18.53 的 x64/ARM64 资产下载、SHA256/SHA512、Authenticode 签名、7z 载荷、无测试文件和 v52→v53 升级均已验证；本版沿用同一构建/发布链。

## 三、产物

- `MRRS-Setup-1.18.54-x64.exe` + `.blockmap` + `latest.yml`
- `MRRS-Setup-1.18.54-arm64.deb`
- `assistance-management-system_1.18.54_arm64.deb`
- `SHA256SUMS-windows-x64.txt` / `SHA256SUMS-electron-deb-arm64.txt` / `SHA256SUMS-standalone-deb-arm64.txt`

## 四、升级与回滚

1. 下载本版本安装包与对应 `SHA256SUMS-*.txt`，先校验 SHA256。
2. 关闭正在运行的系统，覆盖安装；用户数据目录（`%APPDATA%\Assistance-Management-Information-System` 或 Linux `~/.bumofu`）不会被安装器清理。
3. 启动后访问 `GET /health`，确认 `version=1.18.54` 且 `migration.at_head=true`。
4. 访问 `GET /api/v1/system/version`，确认 `release_date=2026-11-20`、`description=版本元数据与发布链路修复`。
5. 回滚：卸载本版前先备份用户数据；安装上一版覆盖安装，必要时从备份恢复数据库。降级前确认目标库迁移头可被上一版识别。

## 五、已知边界

- 系统按设计**不做自动更新**；`latest.yml` 仅作为发布元数据，升级为手动覆盖安装。
- 内网自签名证书在未预置信任的目标机上可能显示“未知发布者”；批量部署需通过 GPO 导入根证书。
- ARM64 需在麒麟 V10 ARM64 真机安装复验；本版完成构建、包结构和哈希验证。
