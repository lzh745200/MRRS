# W21-001 导航单一源 + 系统管理 6 聚合页：文档与 PPT 全量对齐

> Wave：`w21-nav-single-source`　｜　责任：docs-ppt（写作用域 `docs/**`、`README.md`、`CLAUDE.md`、
> `.scratch/w21-nav-single-source/`；经 Lead 授权追加 `项目文件结构说明.md`、`deliverables/README.md`）
> 契约：[000-contract.md](000-contract.md)（方案 C：后端单一菜单源 v2 + 7 板块 + 系统管理 6 聚合页 + 菜单搜索/最近/收藏）
> 版本：**v1.13.0**（2026-10-18）

## 背景

v1.13.0 导航架构重构（方案 C）：

- 后端 `backend/app/api/v1/menus.py` 成为**全站唯一菜单源**（v2：`MENU_SECTIONS` + `MENU_DEFINITIONS`，
  响应 `{version:2, sections, flat_keys}`；条目 `kind` = `page` / `group` / `console`）；
- 前端删除菜单副本 `frontend/src/config/menu-config.ts`、`frontend/src/utils/systemMenu.ts`，
  侧栏 / 移动端底部导航 / 权限面板 / 权限包菜单树全部数据驱动；
- 左侧导航重排为 **7 板块**（工作台固定 + 帮扶业务 / 乡村振兴 / 工作协同 / 分析汇报 / 数据管理 / 系统管理）；
- 系统管理 24+ 页面收敛为 **6 个聚合页**（组织与权限 / 安全与审计 / 运维与监控 / 备份与存储 / 系统设置 / 关于与反馈，
  页内 Tab 切换、旧路由全部保留、菜单 key 一个不改、权限包配置兼容）；
- 新增菜单搜索（Ctrl+K）、最近访问、收藏；补齐汇报大屏 / 提醒中心 / 帮助中心 / 数据上报组等入口。

旧文档中的「前后端两套菜单必须同步」「menu-config.ts 是菜单定义源」「系统管理各组」「组织管理独立入口」
等描述全部失效，需要按最终代码/契约清理并重写；介绍 PPT 的导航/系统管理/规模数字页同样过期。

## What（交付）

### 1. 文档更新（与最终代码对齐）

| 文件 | 改动要点 |
|---|---|
| `CLAUDE.md` | 项目结构树补 `views/system/console`、`components/nav`、`composables`、`stores/menu`；关键设计约定新增「导航与菜单单一源（v1.13.0）」；改写旧「菜单」条目 |
| `README.md` | 前端技术栈改「单一菜单源数据驱动导航」；项目结构补聚合页/导航组件；近期修复记录新增 v1.13.0 段 |
| `项目文件结构说明.md` | 删除 `menu-config.ts` / `systemMenu.ts` 旧说明；`menus.py` 标为唯一菜单源；加页面/加菜单流程改为只改后端；`system/` 补 6 聚合页；排障路径改「运维与监控」 |
| `deliverables/README.md` | PPT 描述改为 41 页 / v1.13.0 / docs 唯一副本（根副本已删） |
| `docs/INDEX.md`、`docs/README.md` | 版本行 v1.13.0；版本单一源口径修正；新增导航/菜单入口 |
| `docs/03-开发文档/前后端契约规范.md` | §4 整节重写：v2 schema（sections/flat_keys、kind 规则、tabs）、6 板块顺序、过滤规则、前端消费、门禁规则 A~E；§6 版本单源修正；§7 菜单门禁口径 |
| `docs/03-开发文档/03-API文档/API接口文档.md` | `menus.py` 段重写：`/menus/accessible` 与 `/menus/all` 的 v2 响应说明 + JSON 示例 + 字段规则 |
| `docs/03-开发文档/07-UI设计规范/UI设计方案.md` | 侧栏导航结构（数据驱动）、新增 §4.7 导航与菜单搜索、新增 §5.6 系统管理聚合页；主题入口改「系统配置页」 |
| `docs/03-开发文档/02-开发指南/UI设计规范.md` | §4 布局与导航：新增 §4.2 导航结构（7 板块/6 聚合页/搜索/收藏/权限） |
| `docs/03-开发文档/01-架构设计/系统架构说明.md` | 横切机制速查新增「菜单/导航：后端单一源」 |
| `docs/03-开发文档/01-架构设计/系统设计图集.md` | 前端组件树改为实际组件（数据驱动侧栏 / MenuSearchDialog / MobileBottomNav / SystemConsole）；§10 系统管理改 6 聚合页；附注补 v1.13.0 说明 |
| `docs/03-开发文档/00-需求规格说明书/01-需求规格说明书.md` | §4 加导航口径说明；FR 锚点列按新导航逐条更新（仅锚点，不改需求/验收） |
| `docs/03-开发文档/08-数据设计/02-数据字典.md` | `menu_keys` 说明改为对应后端 `MENU_DEFINITIONS` key（v1.13.0 单一源） |
| `docs/02-用户手册/使用指南.md` | 新增「🧭 导航与菜单」章节（7 板块/6 聚合页/Ctrl+K/收藏/最近/权限解释）；全部功能路径改为「板块 → 入口」；文末版本更新 |
| `docs/02-用户手册/README.md` | 删除失效链接（快速使用指南/单机版使用说明/03-技术文档/07-问题修复），补现有手册列表与导航口径 |
| `docs/02-用户手册/审批管理与数据分析操作说明.md` | 审批/分析/成效/备份入口路径更新；加导航口径说明 |
| `docs/02-用户手册/权限包管理与数据上报接收操作说明.md` | 权限包入口→组织与权限；可见菜单树改「板块→入口→Tab 三级树 + 聚合页 key 语义 + 旧 tab key 兼容」；数据上报组路径更新 |
| `docs/02-用户手册/备份管理操作说明.md`、`经费管理模块操作说明.md`、`经费管理操作流程详解.md`、`数据分析功能使用指南.md` | 备份/经费/大屏入口路径与菜单标签（经费台账/经费分析/资金报告/汇报大屏）更新 |
| `docs/04-部署文档/OFFLINE_UPGRADE.md`、`docs/03-开发文档/06-运维文档/技术栈说明.md` | 升级/回滚/更新日志/运行环境入口路径更新 |
| `docs/build_ppt.js` | 输出路径改 `path.join(__dirname, ...)`（`node docs/build_ppt.js` 直接更新 docs 份）；版本 v1.13.0；目录/章节页/功能地图/工作台/系统管理/权限模型/关键数字/测试体系/版本历程/结束页按新架构重写；测试数字口径更新 |
| `docs/帮扶管理信息系统介绍.pptx` | 由 build_ppt.js 重新生成（41 页） |

### 2. 删除 / 改写（过时说明）

- 删除根目录旧副本 `帮扶管理信息系统介绍.pptx`（docs 份为唯一对外 PPT）。
- 删除「前端 `menu-config.ts` 仅用于管理面板辅助展示」「已知废弃 key 白名单」等菜单双源旧描述；
  改写「加菜单要前后端两边都改」的旧流程。
- 删除 `docs/02-用户手册/README.md` 中 4 个不存在的失效链接。
- 改写「系统管理 → 备份管理/更新日志/健康检查/权限包/组织管理」「页头更多 → 成效大屏」等旧导航路径。
- 历史归档类文档不删不改：`CHANGELOG.md`（Lead 维护）、R28/W18/审查报告、`docs/architecture/**`（无相关）。

### 3. 明确不改（存量过期、非本批范围，已在汇报中列明）

- `docs/03-开发文档/01-架构设计/README.md`（整体停在 v1.0.3 / Electron 28 / 17 板块，存量过期）。
- `docs/03-开发文档/README.md`（目录条目与真实文件有出入，存量过期）。
- `docs/design/pages.md`（Sidebar 宽度等 UI 细节与 UI设计方案 不一致，非导航语义）。
- 契约规范 §7 的用例数（11678+/3239）与 API 文档「85 模块/765 端点」为存量口径，等 Lead 全量门禁后统一刷新。
- 需求规格说明书中部分历史接口路径（如 `/funds/apply`、`/data-packages`）非导航锚点，保留原状。

## 验收 checklist

- [x] 全仓 `grep`：文档中不再有「menu-config 是菜单定义源 / 前后端两套菜单必须同步 / 双轨」等过时描述
      （剩余命中均为「已删除」的说明性提及或与菜单无关的「双轨迁移/软删双轨/审计双轨」）。
- [x] 6 个曾被点名的文档逐个确认：系统设计图集 / UI设计规范 / 前后端契约规范 = 正确说明性提及；
      后端开发指南「双轨迁移」、数据库设计总览「软删除双轨」、系统完整需求规划「审计双轨」= 非菜单语义。
- [x] 7 板块顺序、6 聚合页与 Tab 清单、key/路径与最终 `menus.py` 逐条一致（以代码解析结果为准）。
- [x] `node docs/build_ppt.js` 成功；产物写入 `docs/帮扶管理信息系统介绍.pptx`（与 CWD 无关）。
- [x] PPT 用 python-pptx 验证：41 页、标题抽样正确、含 v1.13.0 / 99 key / 6 聚合页 / Ctrl+K、无 v1.12.18 残留。
- [x] `python scripts/ppt_overflow_check.py`：**0 处文字溢出**。
- [x] 根目录旧 PPT 副本已删除，docs 份为唯一副本。
- [x] 未修改代码/测试/`package.json`/`CHANGELOG.md`/版本文件；未执行 git 操作。

## Resolution 证据

### 菜单对齐门禁（最终代码，仓库根执行）

```text
[INFO] 后端单一菜单源: 6 个板块 / 99 个 key / 85 个带 path 入口；前端路由 157 条（含 alias）/ 70 个 meta.menuKey
[INFO] 历史兼容 key（section=None + legacy=True，无导航出口，规则 C 豁免 10 个）:
  - batch-import, data, data-analysis, data-logs, data-package-list, effectiveness,
    helpData, pass-code, system, system-config
[OK] 前后端菜单对齐检查通过（规则 A~E 全部满足）
```

### PPT 重新生成与验证

```text
$ node docs/build_ppt.js
DONE pages=38            # 内容页计数；实际 41 张（含封面/目录/结束页）
[自适应度量] 触发字号收缩 3 处：P06 数据来源 12→9pt、P32 数据来源 11→10pt、P32 测试纪律 12.5→11pt

$ backend/.venv313/Scripts/python.exe（python-pptx 1.0.2）
slides: 41
01 军民融合 · 乡村振兴帮扶数字化平台 | 帮扶管理信息系统
02 目录 | CONTENTS
06 01 系统概述 | 一眼看懂：系统规模
15 03 功能模块 | 功能地图：一个工作台 + 六大板块
16 03 功能模块 | 工作台：打开系统的第一屏
24 03 功能模块 | 系统管理：6 个聚合页 · 页内 Tab
26 04 安全体系 | 四角色权限模型：简单即安全
32 05 质量工程 | 测试体系：数字不会说谎
39 06 部署运行 | 版本历程：持续的密集演进
41 数据可信 · 流程可控 · 成效可查 | 谢谢观看
contains v1.13.0: True | contains V1.13.0: True
contains 99 个菜单 key: True | contains 6 个聚合页: True | contains Ctrl+K: True
legacy v1.12.18: False
文件：docs/帮扶管理信息系统介绍.pptx，859,751 bytes，2026-10-18 16:13
根目录副本存在：False

$ python scripts/ppt_overflow_check.py
文件: docs/帮扶管理信息系统介绍.pptx  共 41 页  (阈值 溢出比 >= 1.0)
>>> 合计溢出文本框: 0
```

### 数字口径（发布时全量实测，2026-10-18）

- 版本 **1.13.0**（根 `package.json` 为唯一源，由 Lead 的 `sync-version.js --write` 统一同步）。
- 菜单：**99 key / 6 板块 / 6 console / 85 个带 path 入口**（`menus.py` 解析实测，与门禁输出一致）。
- 后端全量：**13,550 passed / 1 skipped / 1 rerun**；语句覆盖率 **100.00%**（43,293/43,293），
  分支覆盖率 **100.00%**（10,636/10,636）。
- 前端全量：**316 个测试文件 / 6,707 用例全通过**；`src/**` 12 组 glob 四指标 100%。
- 静态门禁：flake8（app/，max-complexity=16）0、bandit `-ll` 0、`vue-tsc --noEmit` 0、
  `eslint src --max-warnings=0` 0；17 项静态门禁脚本（含菜单对齐规则 A~E、硬编码色、
  安全审计、Alembic 单 head、pragma 理由、版本一致性）全部 PASS。
- PPT：`docs/帮扶管理信息系统介绍.pptx` 41 页、0 文字溢出、含 v1.13.0/99 key/6 聚合页/Ctrl+K。

## 状态

**已完成（2026-10-18）**。等 Lead 全量门禁通过后统一提交；本工单不含 CHANGELOG/版本文件改动（由 Lead 负责）。

## 发布门禁复核（Lead，2026-10-18）

- 后端全量（隔离 `COVERAGE_FILE=.coverage-final`）：13,550 passed / 1 skipped / 1 rerun，
  语句 100.00%（43,293/43,293）、分支 100.00%（10,636/10,636）。
- 前端全量：316 文件 / 6,707 用例全通过，12 组 glob 四指标 100%（vitest exit 0）。
- `scripts/check_menu_alignment.py`：A=0/B=0/C=0/D=0/E=0，[OK] 6 板块 / 99 key / 85 path 全对齐。
- `node scripts/sync-version.js --check` 通过；17 项静态门禁全 PASS。

## 构建产物实测（Lead，2026-10-18 v1.13.0）

- 后端 PyInstaller（onedir）：`backend/dist/assistance-backend/assistance-backend.exe` 32.6MB；
  build info = `version=1.13.0 / git_hash=0523774 / builder=ci`；
  `verify_package_no_tests` 与 `verify_build_info` 均 OK。
- 前端构建：`frontend/dist` 653 个文件，`version.json` = 1.13.0。
- Windows 安装包：`dist/electron/MRRS-Setup-1.13.0-x64.exe`（204 MB）。
  SHA256：`e75f88d5b9fb510fc0ec408f9392f04aa7c68ecc9a31df2700cabbf01a09ae65`。
- 发布提交：`0523774`（origin/main）；tag `v1.13.0` 已推送（触发 Actions Windows x64 + ARM64 构建）。
