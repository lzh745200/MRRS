# CLAUDE.md - 帮扶管理信息系统

## 项目概述

帮扶管理信息系统 - 完全离线的单机版桌面应用，支持多机协同数据同步。
基于 Python FastAPI 后端 + Vue 3 TypeScript 前端 + Electron 桌面壳。

> **平台说明**: 以下命令示例以 Windows 为主（`.venv\\Scripts\\`）。Linux/macOS 用户请将路径替换为 `.venv/bin/`、将 `\\` 替换为 `/`。

> **Python 环境**: 推荐使用 Python 3.11 64-bit（`C:\\Users\\Administrator\\AppData\\Local\\Programs\\Python\\Python311\\python.exe`）。

## 项目结构

```
├── backend/app/              # 后端（FastAPI）
│   ├── api/v1/               # API 接口层（52 个路由模块文件 + 5 个子包；845 个端点）
│   │   ├── auth/             # 认证模块
│   │   ├── data/             # 数据分析
│   │   ├── import_export/    # 异步导入导出
│   │   ├── system/           # 系统管理
│   │   └── ...               # 地图、经费、项目、帮扶村、学校、政策、一户一档、影像库、消费帮扶等
│   ├── core/                 # 核心：config, security, database, cache, data_permission, transaction
│   ├── models/               # SQLAlchemy 数据模型（含 household/media/consumption 等 W22 新模型）
│   ├── schemas/              # Pydantic 数据校验
│   ├── services/             # 业务逻辑层（含 ocr_service / household_service / media_service 等）
│   ├── middleware/            # CSRF, 审计, 请求日志, 指标
│   └── utils/                # 工具类（含 win_proactor_fix 等平台修复）
├── backend/tests/            # 后端测试
│   ├── unit/                 # 单元测试
│   ├── integration/          # 集成测试
│   └── security/             # 安全测试
├── backend/alembic/versions/ # Alembic 数据库迁移（Schema 权威来源）
├── frontend/src/             # 前端（Vue 3 + TypeScript）
│   ├── views/                # 页面视图
│   │   ├── dashboard/        # 工作台（QuickActions, layout editor）
│   │   ├── system/           # 系统管理页面 + console/SystemConsole.vue（6 聚合页）
│   │   ├── analytics/        # 数据分析与帮扶村管理
│   │   ├── households/       # 一户一档（W22；v1.15.15 起无侧栏入口，从帮扶村年度数据页进入）
│   │   ├── media/            # 影像库（W22）
│   │   ├── consumption/      # 消费帮扶台账（W22）
│   │   └── ...
│   ├── components/           # 通用组件 + 业务组件（common/ 共享 PageHeader 等、nav/MenuSearchDialog、settings/AppearanceSettings）
│   ├── styles/               # 设计 Token + 全局模板（tokens.scss、components/{ui-v2,ui-refine,card,states,dialog,…}.scss）
│   ├── composables/          # 组合式函数（useUiPrefs 显示偏好 / useRecentMenus / useMenuFavorites）
│   ├── stores/               # Pinia 状态管理（menu.ts 消费后端 v2 菜单单一源）
│   ├── router/               # 路由配置与守卫
│   ├── api/                  # API 请求层
│   └── utils/                # 工具函数
├── electron/                 # Electron 桌面壳
├── scripts/                  # 运维脚本
├── build-scripts/            # 构建脚本（Windows .exe / Linux ARM64 .deb）
├── docker/                   # Docker 配置（含 E2E 测试环境）
├── docs/                     # 项目文档（01-快速开始 ~ 04-部署文档 + ER图）
└── resources/                # 图标、前端构建产物、瓦片地图
```

## 常用命令

### 开发环境启动

```bash
cd backend && python -m venv .venv && .venv\\Scripts\\activate && pip install -r requirements.txt && python start.py
cd frontend && npm install && npm run dev
```

> **Python 版本**：请用 **3.11**（与 CI / 打包基座一致）。`rapidocr-onnxruntime==1.4.4`
> 的元数据是 `requires_python<3.13`，3.13 下 `pip install -r requirements.txt` 会跳过该行
> （已加环境标记，不会整体失败），但 OCR 功能与 2 个真实引擎用例在本地就测不到。
>
> **Windows + WorkBuddy 沙箱注意**：若 venv 里的 `Scripts/python.exe` 报
> `failed to open '...pyvenv.cfg'`（exit 107），是 workspace 目录的
> `Everyone: Deny DeleteSubdirectoriesAndFiles` ACL 让 venvlauncher 读不到配置。
> 解法：把 venv 实体放在 workspace 外（如 `C:\mrrs-venv311`），再用
> `New-Item -ItemType Junction` 链接回 `backend/.venv` —— launcher 会解析到真实路径，
> 所有既有命令与文档路径不变。`backend/.venv313`（3.13）同理，仅用于 3.13 兼容性验证。

### 测试

```bash
cd backend && .venv/Scripts/python.exe -m pytest tests/ -q --cov=app   # 后端 15,198 用例（1 skipped；CI 12 段独立进程）+ 覆盖率门禁 100%
# ⚠️ 单进程跑全量会在约 88% 处进程级崩溃（SQLAlchemy engine.dispose 的 Windows
#    access violation，崩溃前无 FAILED）。本地等价 CI 请用分段执行器：
cd .. && backend/.venv/Scripts/python.exe scripts/run_backend_tests_segmented.py
cd frontend && npm test -- --run                                       # 前端 349 文件（用例数以输出为准）
# 文档数字漂移门禁（端点数 / 路由模块数 / 前端测试文件数 / 后端用例数）：
#   python scripts/check_doc_numbers.py [--full] [--update]
cd backend && .venv/Scripts/python.exe -m flake8 app/ --max-line-length=120 --max-complexity=16
cd frontend && npm run lint:check && npm run type-check

# 预防性棘轮门禁（P-1~P-3，CI static-analysis 作业同款；全部应 NEW=0）
cd backend && .venv/Scripts/python.exe scripts/check_os_exit.py
cd backend && .venv/Scripts/python.exe scripts/check_unbounded_read.py
cd backend && .venv/Scripts/python.exe scripts/check_upload_endpoints.py
cd backend && .venv/Scripts/python.exe scripts/check_subprocess_encoding.py
cd backend && .venv/Scripts/python.exe scripts/check_dir_replace.py
cd backend && .venv/Scripts/python.exe scripts/check_scheduler_registration.py
python scripts/check_hardcoded_styles.py          # 前端硬编码色值棘轮（只紧不松）
python scripts/check_changelog.py                 # 更新日志时效性（当前版本必须已记录）
npm run test:electron                             # Electron 外壳单测（10 例；CI 的 Linux+Windows 两侧都跑）

# lint-staged：仅检查 git 暂存文件（加速提交）
cd frontend && npx lint-staged

# Docker E2E 测试（Playwright 浏览器自动化 + Locust 性能测试）
docker compose -f docker-compose.yml -f docker/docker-compose.e2e.yml --profile e2e up
docker compose -f docker-compose.yml -f docker/docker-compose.e2e.yml --profile performance up
```

**已修复的测试问题**（2026-07-15）：
- ✅ 修复 20+ 个后端 API 文件中 `from app.core.transaction import safe_commit` 错误缩进导致的 `SyntaxError`/`IndentationError`（影响 11 个路由模块加载失败）
- ✅ 修复 `test_comprehensive_coverage.py` 中 3 个 `pytest.skip()` 调用 → 改为直接断言，消除所有跳过的测试
- ✅ 修复 `test_core_transaction.py` 中 `with_transaction` 装饰器 `_execute_in_transaction` 函数缺少 `return` 语句导致返回 `None`（4 个失败测试）
- ✅ 修复 `pyproject.toml` 与 `pytest.ini` 配置冲突警告（统一到 `pytest.ini`，移除 `[tool.pytest.ini_options]` 段）
- ✅ 修复 `test_comprehensive_coverage.py` 中 `SCHEMA_FILES` 列表引用不存在的 schema 模块（`rbac`/`approval`/`audit`/`effectiveness`）→ 更新为实际存在的模块
- ✅ 修复前端 `smoke.test.ts` 中 Vite 动态导入警告（添加 `.ts` 文件扩展名 + `@vite-ignore` 注释）

**历史上的已知预存测试错误已全部修复**（2026-08-14 复核，全部通过）：
- ✅ `test_import_export_history_service_full` + `test_token_blacklist_service_full`（原 16 errors）→ 已修复，86 项相关测试全部通过
- ✅ `test_chart.py` 导入错误（matplotlib 未安装）→ 已解决
- ✅ `test_batch_operations.py` "Unknown table: projects" → 已修复

### 构建

```bash
cd frontend && npm run build
bash scripts/build/sync-frontend-dist.sh          # 同步 + 完整性校验
python scripts/audit_static_assets.py --verbose   # 静态资源审计
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/build/build-installer-local.ps1   # Windows x64 安装包（NSIS，等价 make build-win-x64）
make build-kylin-arm64                            # 麒麟 ARM64 安装包（Docker buildx + QEMU，CI 同款）
```

## 访问地址与默认账号

- 前端: http://localhost:5173（开发）/ http://localhost:8000（生产）
- API 文档: http://localhost:8000/docs
- 默认账号: `admin` / `zgcZGC733035#`（出厂口令，见 `app/core/constants.py` 的
  `FACTORY_ADMIN_PASSWORD`；保密部署请用 `DEFAULT_ADMIN_PASSWORD` 环境变量覆盖）
  —— **首次登录强制修改密码**（服务端 `must_change_password` 拦截，直连 API 也被拦）
  历史文档写的 `admin123` 是过时文案，已纠正

## 关键设计约定

- 项目完全离线运行，安装包内置所有运行时
- Schema 权威来源: `backend/app/models/` 和 Alembic 迁移；`database/init.sql` 已删除
- `.env` 文件不纳入版本控制
- 版本号**唯一权威来源**是根 `package.json` 的 `version`（后端经同步写入
  `backend/app/core/config.py` → `Settings.PROJECT_VERSION`）；
  **22 处目标**（含 8 个 optional 项）由 `node scripts/sync-version.js --write` 单源同步，
  `--check` 为 CI 门禁。⚠️ 旧脚本 `scripts/sync_version.py` 只覆盖 6 类文件且**无校验能力**，
  仅被构建流水线按 tag 使用，不要把它当作唯一同步手段
- **发布流程**：本地门禁全绿 → 提交推送 → **确认 main 的 PR Checks 已绿** →
  `git tag v<版本> && git push origin v<版本>`
  → Actions 自动产出 **Windows x64 安装包** 与 **麒麟 ARM64 deb** 并发布 Release（两个安装包）。
  "确认已绿"用脚本，不靠眼睛：**`python scripts/check_main_ci.py`**（默认只查一次；
  `--wait-minutes 40` 可等）。它挡的是一类真实误判——2026-10-25 实测 main 上连续 5 次
  PR Checks **全部 cancelled**（并发组被后续推送打断），那段时间"推送成功"但**零完整验证**；
  `pr-checks.yml` 已改为 `cancel-in-progress` **只对 PR 生效**，main 改为排队。
  两个构建工作流的"发布前置门禁"（`scripts/check_release_gate.py`）会轮询该 commit 的
  PR Checks 结论，等待上限 **90 分钟**（2026-10-25 由 30 上调：本仓 PR Checks 实测
  17.4~30.2 分钟，原值 30 与最慢一次压线，正常"推 main 立刻打 tag"会超时变红）。
  该约束由 `electron/tests/ci-wiring.test.js` 守卫（等待预算 <60 分钟、或 main 恢复取消、
  或缺少 check_main_ci.py 接线，都会让测试失败）。
- **更新日志必须及时** (2026-10-25): `CHANGELOG.md` 是唯一账本 —— **每次改动在同一个提交里**
  更新当前版本段（`## [x.y.z] - <日期> — <一句话主题>`），写清「改了什么 / 为什么 / 怎么验证」，
  不要留到发版前补（v1.18.1 就漏记了 4 条最贵的踩坑：E2E 选择器失效、Release 正文 0 字符、
  Windows runner 上 shell 崩溃、哈希写死必过期）。门禁 `scripts/check_changelog.py`
  （CI `static-analysis`，单测 `backend/tests/unit/test_changelog_gate.py`）会校验：
  **当前 `package.json` 版本必须已记录** + 最近 3 版段格式规范（`x.y.z` / 日期非未来 /
  非空 / 严格降序）；早期历史遗留段（`未发布` / `1.2.0-build` / 重复段）**不追溯**。
- **依赖清单单一事实源** (2026-09-14, R15)：运行时依赖只登记在
  `backend/app/core/required_packages.py`（运行时必需 / 运行时可选 / 仅开发 三级），
  并在 `backend/requirements*.txt` 登记同一分发名。**禁止**在端点或启动钩子里自持清单
  （历史三处漂移：UI 那份列了应用不用的 `fpdf2` 与仅开发期的 `pytest` → 任何环境恒报缺失）。
  判定用 **import 名 + `importlib.util.find_spec`**（PyInstaller 冻结运行时同样可靠），
  不用 `importlib.metadata.distributions()` 枚举（冻结包里 `.dist-info` 不全 → 误报）。
- 数据库: `backend/data/rural_revitalization.db`
- 生产部署前清除测试数据: `DELETE FROM supported_villages; DELETE FROM schools;`
- **`SupportedVillage.is_revitalization_tier`** 是 Boolean（是否振兴梯队），原来的 `revitalization_tier` (String) 和 `tiered_development_level` (String) 已删除
- `TieredDevelopmentLevel` 查找表已删除
- **帮扶经费** 支持动态年度（用户可选择年份添加），不再固定 2021-2026
- **工作台自定义布局**: 支持预设布局 + 拖拽排序 + 可见性切换，状态持久化到 localStorage
- **QuickActions**: 4 组 26 个快捷入口（核心业务/数据同步/审批协作/系统管理）
- **导航与菜单单一源** (2026-10-18, v1.13.0): 后端 `app/api/v1/menus.py` 的 `MENU_SECTIONS` + `MENU_DEFINITIONS`
  （v2：`version/sections/flat_keys`；条目 `kind` = `page`/`group`/`console`）是**全站唯一菜单源**，
  侧栏、移动端底部导航、权限面板/权限包菜单树全部数据驱动；**前端菜单副本已删除**
  （`config/menu-config.ts`、`utils/systemMenu.ts` 及其测试），禁止再手写菜单段。
  导航固定 7 板块（工作台 + 帮扶业务/乡村振兴/工作协同/分析汇报/数据管理/系统管理）；
  系统管理收敛为 **6 个 console 聚合页**（组织与权限/安全与审计/运维与监控/备份与存储/系统设置/关于与反馈，
  路由 `/system/console/:group`、页内 `?tab=<tab key>` 切换、**旧路由全部保留**、菜单 key 一个不改），
  合计 **30 个功能 tab**。v1.15.18 起聚合页由横向 el-tabs 改为**左侧分组导航 + 右侧内容**
  （`SystemConsole.vue` 的 `TAB_LAYOUT`，**纯呈现层**：不改 key/path/权限粒度/深链；
  后端新增未登记 tab 自动落「其他」组，入口不丢；窄屏 ≤992px 转横向滚动）。
  导航增强：Ctrl+K 菜单搜索**已覆盖 console 的 30 个 tab**（`flatEntries` 带 `parentLabel`+`tabKey`，
  跳转 `/system/console/<group>?tab=<key>`）、最近访问/收藏（localStorage `nav:recent`/`nav:favorites`，
  上限 8，记录含可选 `tabKey`）。操作说明见 `docs/02-用户手册/系统管理操作说明.md`。
  过滤优先级不变（superuser 全量 > `allowed_menus` > 启用中权限包 > 角色默认）；
  console 可见 = `console.key` 或任一 `tab.key ∈ allowed`，勾聚合页 key 视为其全部 Tab 可见。
  门禁：`scripts/check_menu_alignment.py` 规则 A~E（路径可解析 / `meta.menuKey` 合法 / 无孤儿 key / 路径不重复 / 板块唯一）、
  `scripts/check_console_tab_mapping.py`（后端 console tab key ↔ 前端 `TAB_COMPONENTS` 双向一致，
  防"有菜单无组件"功能静默消失）、`src/utils/navLinks.ts` + `nav-links.test.ts`（导航 path 必须可解析）。
- **三层对齐门禁** (2026-10-24, R35): `scripts/check_stack_alignment.py` 比对
  **前端接口层 ↔ 后端路由/Pydantic ↔ 数据库 schema** 三层，防"单测绿、真机废"的契约漂移
  （v1.17.2 的 `/api/v1/system/self-check` 恒 404、`OrganizationCreate` 漏 `code` 字段即此类 ——
  单测用 MagicMock 传 `data` 不会暴露）。三条轴：
  - **A 路径**：`frontend/src/api/*.ts` 的调用路径必须命中后端真实路由
    （归一化：剥查询串 → `${x}`/`{x}` 统一为 `{}` → 去掉 `/api/v1`；注释里的示例路径不计）。
  - **B 模型↔库**：ORM 模型声明的表/列必须与数据库一致。基线固定为
    **"临时空库 + `alembic upgrade head`"**，**不读本机开发库** —— 否则本地脏数据会让门禁结果漂移，CI 也跑不了。
  - **C 字段**：前端 TS interface 与后端 Pydantic 字段必须一致。
    配对方式是**按 URL 解析到端点 + `response_model` 同名**（不是按类名）——
    仓库存在大量**同名不同契约**的类（前端 `types/organization.ts` 的 `DataPackageManifest` 与后端
    `schemas/data_package.py` 的同名类完全是两回事；`AggregateQuery`/`MonitorSnapshot`/`Fund` 同理），
    按类名配对会产生大量假阳性。字段名经 `CamelToSnakeMiddleware` 的规则归一为 snake_case 后比较。
  - 门禁自身：`--json` 输出纯 JSON（应用启动日志改道 stderr），单测
    `backend/tests/unit/test_stack_alignment_gate_r35.py`（含负向用例：注入坏路径必须被抓到并非 0 退出）。
  - **新增/修改端点或前端 api 函数后必须跑这个门禁**，否则 CI 的 `Stack alignment check` 会拦。

- **端点计数口径** (2026-10-28): `check_doc_numbers.py` 统计的是 **`/api` 前缀**端点（**845**）；
  另有 4 条非 `/api` 路由（`/health`、`/favicon.ico`、`/version.json`、SPA catch-all），
  全部 FastAPI 路由合计 **849**（由 `check_route_auth.py` 统计）。两个数字不是矛盾，是口径不同 ——
  讨论端点数量时请写明口径，避免像 v1.18.18 那样"校正 849 → 845"被误读为删了接口。
- **W22 功能迭代** (2026-10-18, v1.14.0):
  - **一户一档**：新表 `households` / `household_members` / `household_risk_records`；API `/households/*`；
    预警规则（连续未走访 >90 天且非一般户→medium；大病/住房不安全/突发困难→high，服务层实时计算不落库）；
    走访挂户回写 `last_visit_date`；`POST /households/rollup` 幂等回填 `VillagePopulation`；台账 xlsx/csv 导出。
  - **影像库**：新表 `photo_archives`；API `/media/photos/*`；EXIF 拍摄时间 + GPS（≤5km 就近匹配帮扶村）、
    `spot_key` 多期分组、Pillow 生成 PNG 对比图（左右/2xN + 日期标注，≤9 张）。
  - **消费帮扶**：新表 `consumption_records` + `/consumption/*`（替换已下线的舆情监测；与帮扶村年度板块
    `consumption_support` 区分）；菜单 key `sentiment` 保留为 legacy。
  - **经费凭证 OCR**：`services/ocr_service.py` + `POST /funds/ocr-voucher`；引擎 `rapidocr-onnxruntime==1.4.4`
    （离线/CPU，Windows 安装包内置；ARM64 构建过滤降级）；不可用时返回 503，前端提示手工录入不阻断业务。
  - **报表模板组合导出**：`POST /report-templates/{id}/export?format=xlsx|csv|docx|pdf&year` +
    `GET /report-templates/{id}/print-data?year`（单次上限 5000 行）。
  - **数据校验合并**：单页 `/data-verify`（Tabs：校验执行/规则管理/字段说明），独立「校验规则」菜单下线（key legacy）。
  - **7 板块折叠**：侧栏板块标题 18px 加粗、默认折叠，展开集合存 localStorage `nav:expanded-sections`。
  - **大屏退出**：`BigScreen.vue` 顶部「退出大屏」→ 退出全屏并回工作台；**数据上报链路**端到端校验修复（协议不变）。
  - **遗留表清理**：删除 `villages` / `villagers` / `industries` / `sentiment_news` 四表；`rural_works` / `rural_tasks` /
    `tea_plantations` / `cactus_fruit_plots` 的 `village_id` 迁移为 `supported_village_id`（FK→supported_villages）。
  - 新增依赖：`rapidocr-onnxruntime==1.4.4`（离线 OCR；PDF 仍用 reportlab 内置中文字体）。
- **UI v2.0 设计系统** (2026-10-19, v1.15.0):
  - **主题 5→3**：军绿（默认，无 `data-theme`）/ 深色大屏 `dark-bigscreen`（仅大屏页强制）/ 户外高对比 `outdoor`；
    旧值 `light`/`military`→`default`、`dark`→`dark-bigscreen`、`high-contrast`→`outdoor` 由 `normalizeTheme()` 迁移，
    非法值回落 default。入口：顶栏主题切换器 + 外观设置面板；`main.ts` 启动时 `applyThemeToDom(readStoredTheme())` 防闪烁。
  - **显示偏好 4 档**（localStorage **`ui:prefs`**，唯一读写入口 `composables/useUiPrefs.ts`）：
    `<html data-font-size="compact|standard|large">`（`--font-scale` 0.92/1/1.12）、
    `data-density="comfortable|compact"`（表格行高 44/34px）、`data-contrast="normal|high"`、
    `data-simplify="false|true"`（隐藏 `.stat-trend`/`.list-hint`/`.advanced-only`）；损坏 JSON/非法值回退默认、
    存储不可用静默内存态；面板 `components/settings/AppearanceSettings.vue`（头像下拉「外观设置」），即时生效并持久化。
  - **Token 升级**（`styles/tokens.scss`）：主色阶 50/100/500/600/700/900、`--color-card-border`、
    阴影 2 档（`--shadow-card`/`--shadow-pop`）、圆角 3 档（card 8/control 6/pill 999）、字号阶梯 `calc(* var(--font-scale))`、
    正文行高 1.6、数字 `tabular-nums`、侧栏 `--sidebar-bg` 深绿渐变 + 当前板块金色竖条（金色仅三用，面积 ≤5%）。
  - **全局模板样式/类**：`styles/components/ui-v2.scss`（表格浅主色表头+金色底线/去斑马纹/密度/焦点环）、
    `card.scss`（`.app-card`/`.app-stat-card`/`.stat-trend`/`.num-cell`）、`states.scss`（`.app-empty/.app-loading/.app-error`）、
    `dialog.scss`（三档宽度）、`theme-elevated.scss`（精美增强层）；通用组件 `components/common/` 6 个
    （AppPageHeader/AppStatCard/AppEmpty/AppLoading/AppError/AppTableToolbar + `index.ts`）。
  - **导航体验**：侧栏当前板块金色竖条、收起态 hover/键盘聚焦浮层 `.section-flyout`、面包屑「板块 › 页面」、
    Ctrl+K 命令面板/菜单搜索。
  - **页面**：工作台 KPI 统计卡 + 待办清单 + 图表层级；大屏三层结构（标题时间条/KPI 大数字/2–3 列图表）+
    `data-bigscreen-distance="3m|6m|10m"` 字号分档（默认 6m）+ 15s 自动轮播（可暂停/关闭、卸载清理定时器）；
    一户一档左主右辅 + 统计卡。
  - **质量门禁**：`tests/unit/ui/ui-tokens.test.ts`（Token/主题/偏好/全局类契约）、
    `tests/e2e/visual/visual-baseline.spec.ts`（10 个关键页面 DOM 结构基线，`UPDATE_VISUAL_BASELINE=1` 更新）；
    硬编码色棘轮 `check_hardcoded_styles.py` 基线 345 → 当前 **154**（40 个文件；**目标 ≤200 已达成**），改动文件零新增。
- **UI 精细化方案 C** (2026-10-20, v1.15.15):
  - **侧栏品牌区**：系统标识名 16→**20px / 800 单行**（logo 36px、侧栏头 64px），修正品牌名低于板块标题（18px）的层级倒挂；
    工作台提升为板块级入口（18px/700、Home 图标），与 7 板块标题同构。
  - **全站表格规范**：所有 el-table 启用 border（**117/117**，保留列宽拖拽）；序号列统一 **72px**（25/25）、
    选择列 **48px**（10/10）、操作列统一 fixed=right（67/67）；新增列表页必须按此三列宽度 + border 编写。
  - **筛选栏 4 档宽度**：input 220 / select 160 / date 240 / number 120，统一 16px 间距；已清理 **114 处**行内宽度，
    禁止在筛选栏写死行内宽度；搜索按钮带图标、重置按钮 100%。
  - **页面头部**：共享 `components/common/PageHeader.vue` 是 T1 列表页 / T2 详情页模板头部**唯一出口**
    （19 个列表页接入、全站 31 页），新页面必须复用，禁止手写标题区。
  - **全局精细化层**：`frontend/src/styles/components/ui-refine.scss`（筛选栏/表格规范 + 8px 栅格 +
    响应式断点 1200/992/768）；设计契约见 `docs/design/{tokens,pages,components}.md`。
  - 质量口径：硬编码色棘轮当前 **154**（基线 345，40 个文件，**目标 ≤200 已达成**），改动文件零新增。
    v1.15.19 起 `rgba(255,255,255,x)` / `rgba(0,0,0,x)` / 主色与金色的低透明度变体统一收敛为
    `tokens.scss` 的「透明度阶梯」Token（`--color-white-{alpha}` / `--color-black-{alpha}` /
    `--color-primary-a{N}` / `--color-gold-a{N}`），值与原字面量逐字节等价、视觉零变化。
- **一户一档入口收敛** (2026-10-20, v1.15.15):
  - 「一户一档」不再占侧栏一级菜单；入口 = **帮扶村管理 → 年度数据管理**页首张卡片
    （`/households?village_id=<村ID>`，列表按村预筛选）。
  - 后端菜单 key `households` 转 **legacy**（`menus.py`：无导航出口，仅权限包 / 历史 `allowed_menus` /
    深链守卫兼容）；前端路由 `meta.menuKey` 改为 `villages`（跟随帮扶村管理权限）；
    旧链接 `/households`、`/households/:id` 保留可直达。
  - 需要挂靠帮扶村权限的新页面按此模式复用 `meta.menuKey`，不要新增侧栏一级菜单。
- **组织编码 = 行政区划代码** (2026-10-22, v1.16.4；2026-10-27 v1.18.14 接入权威表):
  `organizations.code` 是跨机匹配的唯一依据，统一 **6 位行政区划代码**（GB/T 2260）：
  `XX0000` 省级 / `XXYY00` 市州级 / `XXYYZZ` 县市级（如 **522700 黔南州**、**522701 都匀市**）。
  判定口径只在 `services/organization_code_service.py` + `services/admin_division_service.py`，
  **禁止在其它模块重复实现**。
  - **权威表优先**：`backend/app/data/admin_divisions.json`（省级 34 全量；贵州 9 市州 + 88 县级
    全量，取自仓库内置 geojson adcode；`aliases` 存换码如 520222→520281）。表内覆盖的省份
    **存在性强制**（`522799` 这类空号直接拒绝）；表外省份退回末位规律并标记 unverified。
    数据文件缺失/损坏时**自动降级**为仅规律校验（不得因缺文件把合法编码判非法）。
  - 校验入口：`OrganizationCodeService.validate_admin_code(code, parent_code)`
    = 格式 → 别名归一 → 存在性 → **父子同属一个行政区划**（522701 只能挂在 522700 下）。
    落库路径（`POST /organizations`、`system/init`、`OrganizationService.create_organization`）
    都必须走它；`normalize_admin_code` 只做格式。
  - **首启单位不限于省级**（v1.18.14）：省 / 市州 / 县级都可作为根组织，下级从该层级逐级挂接。
  - 越权校验（`_assert_org_write_scope`）必须**早于**编码查重 —— 否则越权者可用 400/其它响应
    差异反推其它分支的组织编码。
  - 组织层级固定 **3 级**（`OrganizationLevel` 只有 level_1~3）；创建后 **编码不可修改**
    （需变更只能停用后新建）。自助注册默认关闭（`SELF_REGISTER_MODE=off`），
    注册流程 **不得自动创建组织**（组织树只由管理员或上级授权包建立）。
  - 回归：`backend/tests/unit/test_admin_divisions_r47.py`（表完整性 / 存在性 / 父子 / 降级 / 首启层级）。
- **遗留表清理契约** (2026-10-22, v1.16.2): 迁移清理"代码零引用"的历史表时**禁止直接 DROP 有数据的表** ——
  统一走 `r35_drop_legacy_tables_001` 的三分支策略：表不存在→跳过；**0 行→DROP**；**有数据→改名 `legacy_<表名>` 归档**
  （数据保留、退出活跃 schema、升级永不中断）。「允许消失」的表必须登记在
  `backend/scripts/gate_baselines/upgrade_legacy_tables.json`，升级演练据此接受
  「原表名消失（旧库 0 行）」或「改名归档且行数不变」；清单缺失时演练退回最严口径（任何表消失都算丢失）。
  迁移逻辑要抽成可单测的纯函数（如 `apply_cleanup(bind)`），三种分支必须有用例覆盖。
- **介质链路治理** (2026-10-23, v1.17.0): 离线 + 上下级 + 介质传输下，**每类导入都必须可追溯**。
  - 查重：`services/package_import_guard.py` 以**整包 SHA256**为指纹（数据包读文件、授权包/配置包读内容字节），
    命中 `audit_logs` 台账即 **409**，需显式 `force=true` 放行；**禁止各导入端点各写一套指纹/查重逻辑**。
  - 台账：导入写 `package_import`（类型/来源单位码/校验和/记录数），确认导入再写 `package_receipt`
    （接收单位码/来源单位码/冲突策略）—— 复用 `audit_logs`，**不新增业务表、不新增迁移**。
  - 单位码：`services/package_org_code.py` 比对包内 `org_code` 与本机目标单位码，
    不一致默认 409（`allow_org_mismatch=true` 放行），防"上级/邻县包导进本单位"后数据挂错组织树。
  - 前端统一用 `components/import/ImportPreviewDialog.vue`（包信息 + 差异 + 重复告警 + 冲突策略三选）；
    收到 409 时显示该弹窗，用户确认后带 `force=true` 重传。
- **系统自检** (2026-10-23, v1.17.0): `GET /api/v1/system/self-check`（仅管理员）+ `services/self_check_service.py`
  一次性体检 6 项 —— 单位码（缺失/格式/层级不符/重复）、组织层级（跨级挂接/根非省级）、
  待审核账号、账号锁定、PII 密钥指纹、介质导入近况。**只读**，不修数据；
  新增检查项必须带 `level`（ok/warn/error）与可读 `detail`，前端 `components/system/SelfCheckCard.vue` 直接渲染。
- **危险操作硬化** (2026-10-21, v1.15.18 批次 3): 四类不可逆/高影响操作必须二次确认且写审计 ——
  删除组织（`X-Confirm-Password` 请求头验密）、恢复备份（红色警告弹窗 + 加密包密码）、
  轮换密钥（令牌全失效提示）、**管理员重置他人密码（必须手工输入目标用户名）**。
  前端统一走 `composables/useDangerConfirm.ts`（`confirmDanger({ typedConfirmation })` 为高危录入确认；
  取消/关闭一律返回 `false`、绝不抛错）。新增危险操作必须复用该 composable，禁止各写一套。
  后端四端点已补 `AuditLogger.log`，动作名 `organization_delete` / `system_restore` /
  `secrets_rotate` / `admin_reset_password`（`details` 只放可 JSON 序列化字段：
  恢复结果里的 datetime 会让 JSON 列写入失败）。
- **软删除模式** (2026-07-05): 模型使用 `is_active` 列（Boolean, default=True）。`is_active=False`=已删除。列表端点默认过滤 `is_active=True`，`include_deleted=true` 显示全部（管理员）。`to_dict()` 暴露 `isDeleted`/`is_deleted`。已应用于 `SupportedVillage`、`School`、`Project`、`Fund`。
- **软删除权限收敛** (2026-07-20): `include_deleted` 参数通过 `enforce_admin_include_deleted` 依赖（`app/api/v1/deps.py`）统一收敛。非管理员传入 `include_deleted=true` 静默降级为 `False`（不抛 403）。4 个端点（supported-villages/schools/projects/funds）均使用 `Depends(enforce_admin_include_deleted)`。详情端点返回 `viewableBecause` 元数据（`build_viewable_because()` 函数）。`SoftDeleteMixin` 预留 `deleted_by` 审计字段。回归测试：`tests/unit/api/test_include_deleted_enforcement.py`（49 项）、E2E：`tests/unit/test_soft_delete_e2e.py`（2 项）。
- **统一列表响应** (2026-07-08): 所有列表端点已使用 `ok_list()` (envelope)。新增列表端点必须使用 `ok_list()` 而非裸 dict。前端 `_unwrapList()` 仍兼容两种格式以保证向后兼容。
- **密码策略** (2026-07-05): `PasswordPolicy` 类必须包含 `REQUIRE_SPECIAL=True` 属性（此前缺失导致 AttributeError）。`SPECIAL_WHITELIST` 与前端正则一致。
- **前端 API 调用规则** (2026-07-05): ① 所有 api 文件必须 `import { get, post, apiRequest } from '@/api/request'`（自动解包），禁止 `import request from './request'`（返回原始 AxiosResponse）。② `get()` 第二参数直接是 params：`get(url, { refresh:true })`，不是 `get(url, { params:{ refresh:true } })`。③ Blob 下载：API 函数内部链式 `.then(r=>triggerDownload(r.data,name))`，调用方只 `await`。
- **列表视图分页重置** (2026-07-05): 所有列表视图的 create/edit/delete/import 处理器必须在调用 `loadData`/`fetchData` 之前重置 `page.value=1`/`currentPage.value=1`/`pagination.page=1`。遗漏会导致用户在第2页+时看不到新建项。
- **安全路由导航** (2026-07-05): 使用 `pushSafe()` from `@/composables/useRouterSafe` 替代 `router.push()`，避免 `NavigationFailureType.aborted` 未捕获拒绝。`useRouterSafe()` 必须在 `<script setup>` 顶层调用。
- **ErrorBoundary 单一根元素** (2026-08-01): `ErrorBoundary.vue` 必须包裹单一根元素 `<div class="error-boundary-root">`（设 `display:contents`）后内部再用 `v-if`/`v-else` 切换。**禁止**在 `<transition>` 内直接使用多根元素的 `v-if`/`v-else`，否则 Vue patch 算法会异常调用 `setAttribute('0')` 导致页面白屏崩溃。
- **角色精简与归一化** (2026-08-01): 系统角色精简为 4 个：`super_admin`/`admin`/`user`/`viewer`。旧角色值通过 `normalize_role()`（`app/core/constants.py`）自动映射：`approval_leader`/`manager` → `admin`，`operator` → `user`。`data_permission.py` 已适配。前端角色选择器默认值必须为 `user`（非 `operator`）。
- **通行码验证三级回退** (2026-08-01): `machine_code_service.py` 的 `verify_pass_code()` 增加第三级回退逻辑：当机器码+通行码匹配失败时，仅凭通行码匹配 `status=pending` 的记录并自动更新 `machine_code` 绑定。解决 Windows 下 `wmic` 命令不稳定导致机器码变化的问题。
- **files API 响应格式统一** (2026-08-01): `files.py` 上传端点必须使用 `success_response()` 返回信封格式，禁止返回裸 dict。所有文件上传操作必须补充审计日志（`AuditLogger`）。
- **维护窗口** (2026-09-14, R7): 备份恢复入口必须包 `app/core/maintenance.maintenance_window()` —— 期间写请求 503（`maintenance_gate.py` 中间件）、读放行、等在途请求归零（≤10s）、`finally` 解除；`/health` 出 `maintenance` 字段。禁止在恢复路径上跳过该闸门。
- **上传与解压一律限长** (2026-09-13/14, R2): `UploadFile` 必须走 `read_upload_with_limit`/`save_upload_file`/带长度分块读；ZIP 先 `ensure_zip_within_limit` 再 `read_zip_member`（数据包、权限包、管控包、上报包、备份校验全覆盖）。
- **组织树元数据** (2026-09-14, R14): 新建/变更组织必须落 `path`（根 `/{id}/`、子 `{父 path}{id}/`）与 `level`；`OrganizationService.repair_organization_paths()` 在启动自检幂等回填历史 NULL 值。缺失会让组织级数据权限 fail-closed 成"成员一律无权限"（导出恒 403）。
- **优雅关闭** (2026-09-14, R12-5): 关机/重启一律 `signal.raise_signal(SIGINT)`，禁止 `os._exit`（`check_os_exit.py` 拦截）。

## Pre-commit Hooks（分阶段策略）

通过 `.pre-commit-config.yaml` 配置，分两个阶段执行：

| 阶段 | Hooks | 说明 |
|------|-------|------|
| **pre-commit** | ruff（Python 快速 lint+fix）、trailing-whitespace、YAML/JSON 检查、Dockerfile tail 检查 | 仅检查变更文件，毫秒级完成 |
| **pre-push** | flake8、bandit（安全扫描）、vue-tsc（前端类型检查） | 全量质量门禁，推送前执行 |

安装: `pip install pre-commit && pre-commit install`

前端 lint-staged 配合使用（`frontend/package.json` → `"lint-staged"` 配置）：
```bash
npx lint-staged   # 仅对 git 暂存的 *.vue/*.ts/*.tsx 文件执行 eslint --fix
```

## 事务管理（with_transaction 重构）

`backend/app/core/transaction.py` 提供完整的事务管理工具链，共 6 个便捷函数：

| 函数 | 类型 | 说明 |
|------|------|------|
| `transaction(db)` | 上下文管理器 | 基础事务，自动 commit/rollback |
| `transactional` | 装饰器 | 自动查找 db 参数或创建新会话 |
| `with_transaction(isolation_level, readonly)` | 高级装饰器 | 支持隔离级别（READ COMMITTED/REPEATABLE READ/SERIALIZABLE）和只读模式 |
| `nested_transaction(db)` | 上下文管理器 | 嵌套事务（savepoint） |
| `savepoint(db, name)` | 上下文管理器 | 命名保存点，可独立回滚 |
| `retry_on_deadlock(max_retries)` | 装饰器 | 死锁自动重试（默认3次） |

辅助工具: `BatchOperation` 类（`batch_insert` / `batch_update` / `batch_delete`），每批 1000 条。

## CI/CD

### PR Checks（`.github/workflows/pr-checks.yml`）

每次 PR 触发：后端测试、前端测试、flake8 检查、覆盖率报告上传到 Codecov。

### Nightly Full Test（`.github/workflows/nightly-full.yml`）

每天凌晨 2:00 UTC 自动运行，也可手动触发（`workflow_dispatch`）：
- 后端全量测试 + HTML/JSON 覆盖率报告 + JUnit XML 结果
- 前端全量测试 + 覆盖率
- Codecov 上传（backend-nightly / frontend-nightly flags）
- 质量报告汇总（Artifact）

### Codecov 集成

PR Checks 和 Nightly 工作流均上传覆盖率到 [Codecov](https://codecov.io/)：
- PR 中显示覆盖率变更 diff
- Nightly 用独立 flags 追踪趋势
- 使用 `codecov/codecov-action@v4`

## 技术栈升级记录

### Sass 1.101.0（modern-compiler API）

前端 `frontend/package.json` → `devDependencies.sass: "^1.101.0"`，使用 modern-compiler API（`vite.config.ts` 中配置 `css.preprocessorOptions.scss.api: 'modern-compiler'`），编译速度显著提升。

### 数据库迁移整合

`backend/alembic/versions/012_consolidate_baseline.py` 将早期分散的迁移脚本整合为单一基线迁移，减少 Alembic 迁移链长度，便于新环境初始化。

## 2026-08-30 体检批次（v1.11.x）持久性约定

- **PII 列已透明加密**（ADR-0005）：`households.helper_phone`、`household_members.id_card`、`village_committee_members.phone`、
  `users.phone`、`organizations/projects/rural_works/rural_tasks/schools.contact_phone` 共 9 列
  使用 `EncryptedText`（确定性 AES-SIV，密文带 `enc.v1:` 标记；v1.14.0 起原 `villagers.id_card/phone`
  随遗留表删除，由一户一档两列承接）。对这些列**禁止裸 SQL 写入**
  （绕过 TypeDecorator 会落明文/破坏等值查询）；等值查询直接 `WHERE col = :明文` 即可命中密文。
  多机离线同步部署必须配置相同 `ENCRYPTION_KEY`（密钥派生见 `app/core/pii_crypto.py`）。
- **数据权限 fail-closed**（ADR-0002）：`core/data_permission`（**唯一**数据范围模块）对缺过滤字段的模型降级"仅本人"
  或抛 `DataScopeFilterError`，绝不静默放行全量；无组织用户回退仅本人（绝不 is_admin）。
- **组织硬删除守卫**（ADR-0003）：`organization_service.delete_organization` 检查名下
  项目/用户（`OrganizationInUseError`）；`projects.organization_id` 外键为 SET NULL。
- **路径双源收口**：读写数据库用 `paths.get_database_path()`；上传目录消费方统一
  `paths.get_runtime_uploads_path()`（详见 AGENTS.md "Path Dual-Source Bug"）。
- **数据包类型**：`PackageType` 含 `update`（增量更新包）；增量端点
  `/data-packages/incremental/{detect-changes,export,import}` 已实现；
  版本管理路由为 `/data-package/version/:id?`（无 id 时页面内选择数据包）。

## 2026-09-10 权限体系收敛（去重 + 单一来源）

- **数据范围**：4 套并行实现合并为 `core/data_permission` 单一模块；删除
  `core/unified_data_scope.py`、`core/data_scope_adapter.py`、`services/village/data_permission.py`，
  约 12 处调用点改指统一入口。**语义**：`filter_by_data_scope`（内部列表/导出，~40 处调用）
  严格按角色——super_admin→全部、admin→本组织(OWN_DEPT)、其余→仅本人；部门级 admin 导出
  **不得跨组织**（军事审计红线 S2，`test_import_export_permission_security`）。
- **R28 收口（2026-10-14，R27-H8）**：`apply_scope_filter` 原先对**任何**管理员直接放行全量，
  与导出链路「admin 仅本组织」冲突（同一数据面两条口径：列表看全量、导出只看本组织）。
  现已统一为**默认严格**：部门级 admin（`role=admin` 且 `is_superuser=False`）收敛到
  「本组织及子树」；`super_admin`/`is_superuser`/`data_scope="all"` 仍为全局。只有组织树可见性
  模型（map / dashboard / 统计 / 组织树等，需 admin 全量才能渲染组织下拉与全局大屏）才显式
  传 `admin_full_access=True`。**新增调用点默认不得传该开关**。同时：`check_record_access`
  组织归属缺失（任一侧为 NULL）改为 fail-closed 拒绝；`orgs:list` 缓存只对真正全局用户启用
  （部门级 admin 的受限结果不得进全局缓存）。回归：`tests/unit/test_data_scope_strict_r28.py`、
  `test_data_permission_gaps_r28.py`。
- **is_admin**：`core/permission_utils.is_admin` 为全仓**唯一**管理员判定入口；语义为
  **仅 super_admin / admin / is_superuser**。历史"管理级业务角色" manager/approval_leader
  **不**归一化为系统管理员（不获得 include_deleted、跨组织等管理员专属能力）；其"管理操作"
  由 `deps.require_manager_role`（内部 `normalize_role`）放行。`deps.ADMIN_ROLES` 归并到
  `core/constants.ADMIN_ROLES` 单一常量源。
- **权限 API 收敛**：删除废弃的 `/api/v1/user-permissions/*`（`api/v1/user_permissions.py`
  + `services/user_permission_service.py` + 注册项）与两个前端零调用死端点
  `/rbac/frontend/route-permissions`、`/rbac/frontend/current-user-permissions`。`/rbac/*`
  为唯一 RBAC 入口。
- **菜单**：全站唯一菜单源为后端 `menus.py`（v1.13.0 起为 v2 `sections`+`flat_keys`，前端
  `menu-config.ts`/`systemMenu.ts` 已删除）；保留三级优先级（`allowed_menus` > 权限包 > 角色默认）；
  死菜单键 `user-permissions` 已删除。
- **前端**：删除死路由 `/system/user-permissions`、孤儿页 `OperationLogs.vue`；修正
  `Menu.vue` 读取不存在的 `meta.requiresAdmin`→改读 `meta.roles`；移除 `UserManagement.vue`
  中与权限抽屉 Tab「菜单可见性」重复的独立"菜单权限"对话框。

## 故障排查

### 启动崩溃 - WinError 1392（文件或目录损坏）

**症状**: 后端启动时 `OSError: [WinError 1392] 文件或目录损坏且无法读取`，堆栈在 `starlette/staticfiles.py`。

**修复**: 重命名损坏目录 → 重建 → 清理。
```bash
mv resources/frontend resources/frontend_corrupted
mv frontend/node_modules frontend/node_modules_corrupted
cd frontend && npm install && npm run build && cp -r dist ../resources/frontend
```
**根本修复**: 管理员权限运行 `chkdsk D: /F` 修复文件系统。

### 前端 404 - JS/CSS Not Found

**症状**: 文件存在但浏览器 404，部分文件正常加载。

**修复**: 彻底重建 + 同步脚本 + 清除浏览器缓存。
```bash
cd frontend && npm run build
bash scripts/build/sync-frontend-dist.sh    # 先清后拷 + 校验
python scripts/audit_static_assets.py --verbose
```

### WinError 10054 - 连接重置

已在 `backend/app/utils/win_proactor_fix.py` 通过三层纵深防御修复（monkey-patch ProactorEventLoop），`start.py` 和 `main.py` 自动加载。

> **v1.2.0 Logger 修复**: `win_proactor_fix.py` 中的 logger 从 `__name__` 方式获取，避免在模块导入早期阶段因日志系统未初始化而导致的 `KeyError` / `"No section: 'formatters'"` 错误。使用 `logging.getLogger(__name__)` 并确保 logger 实例在函数调用时才被引用。

### 登录超时（bcrypt 5.x 兼容性）

`backend/app/core/security.py` 已注入 `_bcrypt.__about__` 使 passlib 能加载 bcrypt C 扩展，`verify_password()` 耗时从 ~30s 降至 ~200ms。

### 页面白屏 - setAttribute('0') is not a valid attribute name

**症状**: 工作台首页等使用 `<transition>` 包裹 `ErrorBoundary` 的页面白屏，控制台报 `Failed to execute 'setAttribute' on 'Element': '0' is not a valid attribute name`。

**根因**: `ErrorBoundary.vue` 在 `<transition>` 组件内使用 `v-if`/`v-else` 双根元素切换，Vue 的 patch 算法在处理 transition 的 `patchProp` 时将数字索引 `0` 误作为属性名调用 `setAttribute`。

**修复**: 包裹单一根元素 `<div class="error-boundary-root">` 并设 `display:contents`，内部再用 `v-if`/`v-else` 切换。

### 注册时"通行码无效或已被使用"

**症状**: 新用户注册时明明通行码正确，但系统提示"通行码无效或已被使用"。

**根因**: Windows 环境下 `wmic` 命令生成的机器码可能因进程重启、系统更新或权限变化而不一致，导致机器码+通行码双重匹配失败。

**修复**: `machine_code_service.py` 新增第三级回退逻辑，仅凭通行码匹配 `status=pending` 的记录并自动更新 `machine_code` 绑定。

## Agent skills

### Issue tracker

本地 markdown 工单：`.scratch/<wave>/<NNN>-slug.md`，一票一文件。见 `docs/agents/issue-tracker.md`。

### Triage labels

默认五标签（needs-triage / needs-info / ready-for-agent / ready-for-human / wontfix）+ severity 前缀。见 `docs/agents/triage-labels.md`。

### Domain docs

single-context：根目录 `CONTEXT.md` + `docs/adr/`。见 `docs/agents/domain.md`。
