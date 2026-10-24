# Release Notes — v1.17.3（2026-10-24）

> 本文件供 GitHub Release 正文使用；对应同版本 CHANGELOG 条目见根目录 `CHANGELOG.md`
> 的 `[1.17.2]` 段。

## 一、下载与校验

| 安装包 | 适用平台 | 大小 | SHA256 |
|---|---|---|---|
| `MRRS-Setup-1.17.2-x64.exe` | Windows 10/11 x64 | 273.13 MB | `5ea1652906bc0a3c2de54e32ed91782e5bf5aab1bc0a693b5d486c4e316a223f` |
| `MRRS-Setup-1.17.2-arm64.deb` | 麒麟 V10 / 统信 ARM64（Electron） | 269.71 MB | `41267e24572876484188e8f63bb1a751dd30e09e1df4b9148823ce22c0500751` |
| `assistance-management-system_1.17.2_arm64.deb` | 麒麟 V10 / 统信 ARM64（standalone） | 101.16 MB | `6cefce397ae49bdd315d718a7eeb1482d361538e09b729881e84296d5b6f0748` |

离线校验（Windows）：

```powershell
Get-FileHash .\MRRS-Setup-1.17.2-x64.exe -Algorithm SHA256
```

## 二、⚠️ 升级前必读

### 1. 数据库迁移：**本版无 schema 变更**

v1.17.3 只修业务代码与测试，**Alembic head 保持 r41**（61 个版本、单 head）。
从 v1.17.0 / v1.17.1 升级无需额外迁移步骤；从 v1.16.x 升级仍走 r36~r41 的既有迁移。

- 升级前仍建议先备份（系统管理 → 备份与存储 → 备份），或离线复制
  `%APPDATA%\Assistance-Management-Information-System\data\rural_revitalization.db`

### 2. 本版修复两个「单测绿、真机废」的高危缺陷

- **创建组织在真实 HTTP 下必然失败**：`OrganizationCreate` 漏掉 `code` 字段，而端点创建路径
  直接读 `data.code`。单元测试用 MagicMock 传 `data` 不会暴露 → **新装机器无法创建任何组织**。
  已补 `code` 必填（6 位行政区划代码）；`OrganizationUpdate.code` 改为可选（编码只读语义）。
  **若你在 v1.17.0/v1.17.1 上遇到过"点新增组织报 422"，本版已修复。**
- **系统自检端点路径错位**：模块注册在 `/api/v1/self-check`（根级），前端调用
  `/api/v1/system/self-check` → 设置页自检卡片恒 404。已改为经 `system` 包聚合注册。

### 3. 死代码清理（不影响功能）

移除 6 个从未接入任何页面的通用组件（`AppEmpty` / `AppError` / `AppLoading` /
`AppPageHeader` / `AppStatCard` / `AppTableToolbar`）及其 barrel 与 7 个测试文件，
移除 3 个已被 `docs/build_ppt.js` 取代的一次性 PPT 版本脚本。
`ErrorBoundary` 经核实仍在 `DefaultLayoutSafe.vue` 通过全局名使用，**予以保留**。

## 三、验证

| 环节 | 结果 |
|---|---|
| 后端 12 段全量（14,404 用例） | PASS，行/分支覆盖率 100% |
| 前端全量（329 文件 / 6,995 用例，12 组 glob） | PASS，覆盖率 100% |
| flake8（含 `--max-complexity=16`）/ bandit | 0 |
| ESLint（`eslint src --max-warnings=0`）/ `vue-tsc --noEmit` | 0 |
| `npm audit --omit=dev` | 0 漏洞 |
| 升级演练 | r41 → r41，无 schema 变更 |
| 文档死链 / 文档数字 / 菜单对齐 / console tab 映射 | 0 / 一致 / A~E 通过 / 30-30 |
| Windows 构建产物校验 | backend exe、无测试文件、构建指纹、**自包含后端冒烟**、安装包无测试、SHA256 全部 PASS |
| ARM64 产物校验 | standalone-deb 与 Electron DEB 均含/不含 OCR 载荷契约校验通过，Depends 保持零外部依赖 |

## 四、已知限制

- 本版 ARM64 standalone 包**不内置离线 OCR 模型**（与 v1.15.x 起的既定行为一致），
  经费凭证 OCR 在麒麟机上返回 503、走手工录入；Electron 版 DEB 与 Windows 版内置 OCR。
- 自动更新（`latest.yml`）仅覆盖 Windows x64；ARM64 需手动安装 DEB。
