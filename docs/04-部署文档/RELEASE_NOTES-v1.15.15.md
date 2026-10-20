# Release Notes — v1.15.15（2026-10-20）

> 本文件供 GitHub Release 正文使用；对应同版本 CHANGELOG 条目见根目录 `CHANGELOG.md` 的
> `[1.15.15] - 2026-10-20` 段（及 v1.15.13 / v1.15.14 条目）。

## ⚠️ 升级前必读：会导致功能不可用的配置项

### 1. R33 单位授权包 —— 导入授权包前必须先配置验签公钥

R33 授权包用于「上级下发 → 下级导入」的单位模块授权矩阵，靠 Ed25519 签名防篡改。
**出厂配置下不配置密钥，授权包导入/下发都不可用**：

- **下级（接收方）**：必须配置 `GRANT_PUBKEY`（32 字节 hex Ed25519 **公钥**）。
  未配置时导入带签名授权包返回 400「本机未配置验签公钥，无法校验授权包来源」。
- **上级（下发方）**：配置 `GRANT_SIGNING_KEY`（32 字节 hex **私钥**）用于签发；
  ⚠️ 私钥必须保密，不得提交版本库、不得下发给下级。
- `GRANT_ALLOW_UNSIGNED` **永远保持 false**：开启即摧毁防篡改设计（仅离线演练可临时开启）。
- 生成密钥对（在 `backend` 目录执行）：

  ```bash
  # Windows
  .venv\Scripts\python.exe -c "from app.core.grant_signing import generate_keypair as g; k=g(); print('GRANT_SIGNING_KEY='+k[0]); print('GRANT_PUBKEY='+k[1])"
  # Linux / macOS
  .venv/bin/python -c "from app.core.grant_signing import generate_keypair as g; k=g(); print('GRANT_SIGNING_KEY='+k[0]); print('GRANT_PUBKEY='+k[1])"
  ```

- 配置位置：Linux 写入 `/opt/assistance-management-system/config/kylin.env`（systemd EnvironmentFile）；
  Windows 配置系统/用户环境变量；后端 `.env` 同样生效。
- 详细步骤见 `docs/04-部署文档/README.md` 的「部署前置检查 → 3. R33 单位授权包签名」。

### 2. 多机 / 局域网 / 非回环部署：PASS_CODE_SECRET 全实例一致

所有实例必须配置**同一随机** `PASS_CODE_SECRET`；未配置时来自非本机回环地址的自助注册/
通行码自验证会被 fail-closed 拒绝（403）。单机回环部署可留空。

### 3. viewer 角色为严格只读

`viewer` 的所有写操作（POST/PUT/PATCH/DELETE，含直连 API）由服务端返回 **403**；
需要录入/审批/导出的账号请使用 `user` 及以上角色。

### 4. R33 写收窄 `GRANT_GUARD_MODE` 默认 off（可选能力）

- `off`（默认）：仅菜单裁剪生效，接口层不做额外写拦截；
- `shadow`：只记日志不拦截（上线前收集"将被拦"清单）；
- `enforce`：越权写返回 403。
- **生产建议**：先 `shadow` 观察 1~2 周再 `enforce`，不要把默认值直接改为 enforce。

### 5. 数据库迁移

本版含 `effectiveness_evaluations` 外键重建迁移（v1.15.14）。安装包首启自动迁移到 head
（**54 个 Alembic 版本，单 head**）；**升级前请先备份**（系统管理 → 备份与存储 → 备份，
或离线复制 `%APPDATA%\Assistance-Management-Information-System\data\rural_revitalization.db`）。
迁移失败时启动自检直接 `SystemExit(1)` 保留现场，不会静默重建库。

## 本版主要变更（v1.15.13 ~ v1.15.15）

### UI 精细化方案 C（v1.15.15，R35）

- **侧栏品牌区**：系统标识名 16→**20px / 800 单行**（logo 36px、侧栏头 64px），修正品牌名低于板块标题
  （18px）的层级倒挂；**工作台提升为板块级入口**（18px/700、Home 图标），与七大板块标题同构。
- **全站表格规范**：所有 el-table 启用 border（**117/117**，恢复列宽拖拽）；序号列统一 **72px**（25/25）、
  选择列 **48px**（10/10）、操作列统一 `fixed=right`（67/67）。
- **筛选栏统一**：清理 **114 处**行内宽度，改为全局 4 档规范（input 220 / select 160 / date 240 /
  number 120）+ 统一 16px 间距；搜索按钮 28/28 带图标、筛选栏重置按钮 100% 带图标。
- **页面头部统一**：**19 个列表页**接入共享 `PageHeader`（全站 31 页），标题/副标题/主操作位置统一。
- **全局精细化层**：新增 `frontend/src/styles/components/ui-refine.scss`（筛选栏/表格规范 + 8px 栅格 +
  响应式断点 1200 / 992 / 768）。
- **体验修复**：帮扶村管理搜索重置行控件宽度不一致、帮扶学校/经费台账等表格列宽无法调整。

### 导航与入口收敛（v1.15.15）

- **「一户一档」入口迁移**：不再占侧栏一级菜单，入口改为 **帮扶村管理 → 年度数据管理**页首张卡片
  「一户一档」→ `/households?village_id=<村ID>`（列表按村预筛选）。
  后端菜单 key `households` 转 **legacy**（权限包 / 历史 `allowed_menus` / 深链守卫兼容），
  路由 `meta.menuKey` 改为 `villages`（跟随帮扶村管理权限）；旧链接 `/households` 仍可直达。
- **R33 单位授权导航入口（v1.15.13）**：系统管理 →「组织与权限」console 新增「单位授权配置」
  「导入授权包」两个 Tab（此前功能/接口齐全但菜单无入口，用户不可达）。

### 平台与 CI

- **v1.15.14**：PR Checks 全绿后成功构建 Windows x64 完全集成安装包；
  `effectiveness_evaluations` 外键重建迁移 + 冗余退码清理。
- **v1.15.13**：修复 v1.15.12 遗留 PR Checks 红项（flake8 F401 / prettier / README 版本号未同步），
  补齐 R33 UI 可达性，前端死代码清理，前端覆盖率合并稳定性修复。
- 后端测试 **12 段独立进程**执行（`--cov-append` 合并，覆盖率 100% 由 `.coveragerc`
  `fail_under` 单一来源判定）；前端 12 组 glob 覆盖率阈值 100%。

## 安装包（GitHub Release v1.15.15）

| 平台 | 产物 | 体积 | 说明 |
|---|---|---|---|
| Windows 10/11 x64 | `MRRS-Setup-1.15.15-x64.exe` | 286,035,588 B ≈ 272.8 MB | NSIS 安装包，内置 Python 运行时与 VC++ 运行库，目标机零依赖 |
| Windows（更新元数据） | `MRRS-Setup-1.15.15-x64.exe.blockmap`、`latest.yml` | — | 安装包差分/更新元数据 |
| 麒麟 V10 ARM64 | `MRRS-Setup-1.15.15-arm64.deb` | 205,545,106 B ≈ 196 MB | Electron 桌面版（buildx + QEMU 交叉构建） |
| 麒麟 V10 ARM64 | `assistance-management-system_1.15.15_arm64.deb` | 60,786,460 B ≈ 58 MB | standalone 纯 Web 版（systemd 托管，浏览器访问） |
| 全部 | `SHA256SUMS-windows-x64.txt`、`SHA256SUMS-electron-deb-arm64.txt`、`SHA256SUMS-standalone-deb-arm64.txt` | — | 分发前务必校验（`sha256sum -c`） |

## 发布门禁说明

- Tag 构建前强制校验 **tag commit 的 PR Checks 必须全绿**（Windows 与 ARM64 同口径）；
  门禁红时不会产出 Release，避免"构建成功即发布"绕过质量门禁。
- 本版发布验证：**PR Checks success**（后端 12 段独立进程 + 覆盖率 100%）、
  **Build Windows Installer success**、**Build ARM64 Deb success**。
- 后端测试 **12 段独立进程**（`--cov-append` 合并，覆盖率 100% 单一来源判定）；
  前端 12 组 glob 覆盖率阈值 100%。
- 安装包冒烟：解包直跑后端并断言 `/health`（版本/构建指纹/迁移 head）、包内禁含测试资产、
  构建指纹 `builder=ci`。

## 已知事项

- 代码签名待证书采购：当前安装包未签名，Windows 首次运行可能触发 SmartScreen 提示（不影响安装）。
- v1.15.0 ~ v1.15.7 的 Release 未产出 Windows x64 安装包：原因为发布门禁正确拦截了红色 PR Checks
  （v1.15.5/v1.15.7 门禁超时/未通过）与一次 action SHA 基建故障（v1.15.6 Set up job 3 秒失败）；
  构建链本身与 v1.14.3 成功产出 x64 安装包时一致。自 v1.15.14 起门禁全绿，双平台产出恢复。
