# 帮扶管理信息系统

> 乡村振兴 — 完全离线的单机版桌面应用 | 多机协同数据同步 | v1.15.8

![Version](https://img.shields.io/badge/version-1.15.8-blue)
![License](https://img.shields.io/badge/license-MIT-lightgrey)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20ARM64-orange)
![Tests](https://img.shields.io/badge/tests-20%2C500%2B-brightgreen)
![Coverage](https://img.shields.io/badge/coverage-100%25-brightgreen)

## 项目状态

| 指标 | 结果 |
|------|------|
| 后端测试 | **13,710 passed**, 0 失败（含行+分支覆盖率 100% 门禁） |
| 前端测试 | **6,826 passed**（328 文件）, 0 失败 |
| 后端覆盖率 | **100%**（可覆盖集口径，门禁 `backend/.coveragerc` fail_under=100） |
| 分支覆盖 | **100%**（`.coveragerc` `branch=True` 严格门禁 + 棘轮基线 100.0） |
| 前端覆盖率 | **100%**（门禁 `vitest.config.ts` 12 组 glob 阈值 ×100） |
| Flake8 | 0 错误, 0 警告 |
| ESLint | 0 错误, 0 警告 |
| Bandit (安全) | 0 高危 |
| vue-tsc | 0 错误 |
| TypeScript | strict: true（全选项启用） |
| Pre-commit | ruff（变更文件）+ flake8/bandit/vue-tsc（推送前） |
| CI/CD | PR Checks + Nightly Full Suite + Codecov |
| Sass | 1.101.0（modern-compiler API） |
| 角色体系 | 4 核心角色 (super_admin/admin/user/viewer) |
| UI 设计系统 | **UI v2.0**：主题 3 套（军绿默认 / 深色大屏 / 户外高对比）+ 显示偏好 4 档（字号/密度/高对比/简化，localStorage `ui:prefs`）+ 统一 Token/组件类 |
| 前端质量门禁 | 视觉回归基线 10 个关键页面（`tests/e2e/visual`）+ Token 契约测试（`tests/unit/ui`）+ 硬编码色棘轮 345→305（57 个文件；目标 ≤200） |

| 预防门禁 | 6 个棘轮扫描器（os._exit / 上传限长 / 无界读 / 子进程编码 / 目录替换 / 周期任务注册）接入 CI，NEW=0 |
| 深审台账 | OCR 2026-09-17 全量审查的 358 条 critical/high 已逐条复核（LIVE 337 条），本轮处置与遗留见 `deliverables/ocr-findings-ledger-2026-09-30.md` |
| 真实 HTTP 探测 | 11 个探针脚本（`backend/tests/probe/`，覆盖认证/帮扶村/学校/经费/项目/政策/组织/报表/备份/审批/数据包），**与运行时刻/时区无关**（v1.12.11 起 `probe_r10` 的 `next_send_at` 断言按本地语义解析带偏移的 ISO） |

> **上次全量验证**: 2026-10-19（v1.15.0）— 后端 13,710 用例（1 skipped）+ 行/分支覆盖率 100.00%（44,423 stmts / 10,872 branches）；
> 前端 **328 文件 / 6,826 用例、12 组 glob 100%**；E2E 154+（含 10 页视觉回归基线）；
> flake8 0 / 6 项棘轮门禁 NEW=0（另加 2 道 W18 防腐门禁）/ vue-tsc 0 / eslint 0 / 硬编码色 305（基线 345，57 个文件）/ 版本单一来源一致 / Alembic 单 head（50 版本）

## 快速开始

### 系统要求

| 项目 | 最低要求 | 推荐配置 |
|------|---------|---------|
| 操作系统 | Windows 10 / 麒麟 V10 ARM64 | Windows 10/11 64位 |
| 内存 | 4 GB | 8 GB |
| 硬盘 | 2 GB | 5 GB |

> **离线设计**：安装包内置所有运行时，无需安装 Python/Node.js。

### 一键启动

```bash
scripts\start-all.bat      # 启动所有服务
scripts\stop-all.bat       # 停止所有服务
```

### 开发环境

```bash
# 一键初始化开发环境
scripts\dev-setup.bat        # Windows
bash scripts/dev-setup.sh    # Linux

# 或手动
cd backend && python -m venv .venv && pip install -r requirements.txt && python start.py
cd frontend && npm install && npm run dev
```

### 访问地址与默认账号

| 服务 | 地址 |
|------|------|
| 前端（开发） | http://localhost:5173 |
| 前端（生产） | http://localhost:8000 |
| API 文档 | http://localhost:8000/docs |

默认账号: `admin` / `zgcZGC733035#`（出厂口令；`DEFAULT_ADMIN_PASSWORD` 环境变量可覆盖，
保密部署务必覆盖）—— **首次登录强制修改密码**，改密前其它 API 一律 403

## 技术栈

### 后端
- **框架**: FastAPI + SQLAlchemy 2.0 + Pydantic
- **数据库**: SQLite（`backend/data/rural_revitalization.db`）
- **认证**: JWT + bcrypt + 机器码绑定 + 通行码验证（三级回退）+ 2FA
- **缓存**: diskcache + 内存 LRU
- **任务**: threading.Timer 定时调度（备份计划/KPI预计算/异常检测, APScheduler 已移除）
- **角色体系**: 4 核心角色（super_admin/admin/user/viewer）+ `normalize_role()` 向后兼容
- **离线 OCR**: `rapidocr-onnxruntime==1.4.4`（CPU/离线，识别经费凭证金额与日期；Windows 安装包内置模型，ARM64 构建过滤降级）
- **依赖自检**: 运行时依赖登记在 `backend/app/core/required_packages.py`（必需/可选/仅开发三级），
  启动自检与 `GET /api/v1/env/check` 按 **import 名** 校验；自包含安装包不误报、不给无效 pip 建议
- **打包**: PyInstaller（x64 + ARM64）+ electron-builder（NSIS 安装包）

### 前端
- **框架**: Vue 3 + TypeScript + Vite
- **UI**: Element Plus + ECharts + Leaflet；**UI v2.0 设计系统**（`tokens.scss`：主色阶/卡片边框/两级阴影/三档圆角/字号 calc 缩放/行高 1.6/tabular-nums）
- **主题与显示偏好**: 主题 3 套（军绿默认 / 深色大屏 `dark-bigscreen` / 户外高对比 `outdoor`）；显示偏好 4 档（字号 compact/standard/large、密度 comfortable/compact、高对比、简化模式；localStorage `ui:prefs` + `<html data-*>`），外观设置面板统一入口
- **导航**: 后端单一菜单源（`menus.py` v2 `sections`+`flat_keys`）数据驱动侧栏/移动端/权限面板；Ctrl+K 命令面板 + 收藏/最近访问；7 板块默认折叠、可展开（`nav:expanded-sections`）；侧栏当前板块金色竖条 + 收起态浮层 + 面包屑「板块 › 页面」
- **组件体系**: 全局类 `.app-card/.app-stat-card/.app-empty/.app-loading/.app-error/.app-table-toolbar` + `components/common/` 通用组件 6 个
- **状态**: Pinia
- **测试**: Vitest + Playwright；视觉回归基线（10 个关键页面 DOM 结构快照）+ Token 契约测试
- **代码质量**: ESLint + Prettier + lint-staged

### 桌面
- **壳**: Electron 33 + electron-builder
- **安装**: NSIS (Windows) / dpkg-deb (Linux ARM64)

## 测试体系

| 测试类型 | 工具 | 数量 | 覆盖范围 |
|---------|------|------|---------|
| 后端单元测试 | pytest | 13,710（行/分支覆盖率 100%） | API/Service/Core/Model/Utils 全覆盖 |
| 后端集成测试 | pytest | 8 套 | Auth/Users/Policies/Search/Audit/API |
| 后端安全测试 | pytest | 3 套 | Data Isolation/Audit/Retry |
| 前端单元测试 | Vitest | 6,826（328 文件） | API/Store/Component/Composable/Utils |
| E2E 测试 | Playwright | 154+ 流程（17 个 spec） | Login/Dashboard/Projects/Approval/Funds/导航正确性/响应时间 |
| 视觉回归 | Playwright | 10 个关键页面（DOM 结构快照，非像素） | 工作台/帮扶村/项目/经费/一户一档/影像库/消费帮扶/系统管理/数据校验/大屏 |
| UI Token 契约 | Vitest | `tests/unit/ui/ui-tokens.test.ts` | 主题 3 套/字号缩放/密度/高对比/简化/大屏字号档/全局类 |
| 性能测试 | Locust | 配置可用 | 负载测试 |
| 属性测试 | fast-check | 多组 | 组件属性验证 |
| 无障碍测试 | Vitest | 多组 | ARIA/键盘/颜色对比度 |
| 安全扫描 | Bandit | 0 高危 | SQL注入/密码/加密 |
| 代码检查 | Flake8/ESLint | 0 错误 | Python + Vue/TS |

### 运行测试

```bash
# 后端
cd backend && pytest tests/ -q --tb=short

# 前端
cd frontend && npm test

# 前端视觉回归基线（10 个关键页面 DOM 结构快照）
cd frontend && npx playwright test tests/e2e/visual --reporter=list

# UI Token 契约（主题 3 套 / 显示偏好 / 全局类）
cd frontend && npx vitest run tests/unit/ui/ui-tokens.test.ts

# 全量（不含 E2E）—— 有 make 的环境用 make test；Windows 无 make 时逐条执行
cd backend && .venv/Scripts/python.exe -m pytest tests/ -q --cov=app
cd frontend && npm test -- --run

# E2E (Docker)
docker compose -f docker-compose.yml -f docker/docker-compose.e2e.yml --profile e2e up

# 覆盖率
cd backend && pytest --cov=app --cov-report=html
cd frontend && npm run test:coverage
```

## 开发工具链

```bash
# 代码格式化与检查
cd frontend && npm run lint            # ESLint 自动修复
cd frontend && npm run type-check      # TypeScript 类型检查
cd backend && flake8 app/ --max-line-length=120
cd backend && bandit -r app/

# Pre-commit hooks（推荐安装）
pip install pre-commit && pre-commit install
npx lint-staged                        # 仅检查暂存文件

# 构建（两种方式，产物一致）
# ① 推荐：推 tag 由 GitHub Actions 一次产出两个安装包并发布 Release
#    发布前置条件：main 分支最近一次 PR Checks 必须为 success（tag 构建会自动校验）；
#    tag 构建只做发布专项门禁（Windows 敏感子集 + 前端类型/导航子集 + 自包含冒烟），
#    全量测试由 main 的 PR Checks 与 Nightly 承担，避免重复全量造成随机失败。
git tag v1.13.1 && git push origin v1.13.1     # → Windows x64 .exe + 麒麟 ARM64 .deb
# ② 本地（Windows 无 make 时）：fetch_vcredist → 前端构建 → 同步 → PyInstaller → electron-builder
powershell -ExecutionPolicy Bypass -File scripts/build/fetch_vcredist.ps1
cd frontend && npm run build && cd .. && cmd /c scripts\build\sync-frontend-dist.bat
cd backend && .venv/Scripts/python.exe -m PyInstaller assistance-backend.spec --clean --noconfirm && cd ..
npx electron-builder --win --x64     # 产物：dist/electron/MRRS-Setup-<版本>-x64.exe
```

## CI/CD 流水线

| 流水线 | 触发条件 | 内容 |
|--------|---------|------|
| **PR Checks**（8 作业） | Pull Request | 后端测试 + 覆盖率门禁（`.coveragerc` fail_under=100）+ **升级排练（最近发布标签的旧库 → 当前 head，数据/表/完整性校验）** + 前端检查 + lint + security + **static-analysis（6 个预防棘轮 + 原始 SQL 豁免 + 菜单/版本/迁移门禁）** + E2E + **windows-smoke** |
| **Nightly Full** | 每日凌晨2:00 UTC | 全量测试 + 覆盖率报告 + Codecov + JUnit 报告 |
| **Build Windows x64** | **tag v\*** / 手动 | 发布专项门禁（main PR Checks 绿 + Windows 敏感测试子集 + 前端类型/导航子集） → PyInstaller onedir + electron-builder NSIS → **安装包自包含冒烟**（解包后端 /health + 运行库/DLL 断言）→ Release |
| **Build ARM64 deb** | **tag v\*** / 手动 | Docker Buildx QEMU（复用同一构建缓存）→ standalone DEB + Electron DEB → Release |

## 项目结构

```
├── backend/app/              # 后端（FastAPI，340+ 个 py / 8 万+ 行）
│   ├── api/v1/               # API 接口层（91 个路由模块 + 13 个子包）
│   ├── core/                 # 核心：config, security, database, transaction, cache, maintenance(维护闸门)
│   ├── models/               # SQLAlchemy 数据模型（64 个文件，含 W22 新增 household/media/consumption）
│   ├── services/             # 业务逻辑层（100 个服务 + 13 个子包，含 ocr_service / household_service / media_service）
│   ├── middleware/           # CSRF, 审计, 请求日志, 指标, maintenance_gate(写请求闸门)
│   └── startup/              # 启动钩子（种子/监控/恢复/环境自检 + 组织树自愈）
├── frontend/src/             # 前端（Vue 3 + TypeScript，290+ 个源文件）
│   ├── views/                # 页面视图（含 system/console 6 聚合页、households 一户一档、media 影像库、consumption 消费帮扶）
│   ├── components/           # 通用 + 业务组件（common/ 6 个通用组件、nav/ 菜单搜索、settings/ 外观设置）
│   ├── composables/          # 组合式函数（useUiPrefs 显示偏好、useRecentMenus / useMenuFavorites）
│   ├── layouts/              # 主框架（数据驱动侧栏 + 当前板块金色竖条 + 收起浮层 + 面包屑）
│   ├── styles/               # 样式体系（tokens.scss 设计 Token；components/{card,states,dialog,ui-v2,…}.scss 全局模板）
│   ├── stores/               # Pinia 状态（menu.ts 消费后端 v2 菜单；config.ts 主题）
│   └── utils/                # 工具函数
├── electron/                 # Electron 桌面壳
├── docker/                   # 多架构 Dockerfile + E2E compose
├── deploy/                   # 麒麟 V10 systemd + DEBIAN 配置
├── k8s/                      # Kubernetes 部署清单
├── nginx/                    # Nginx 反向代理配置
├── scripts/                  # 管理/运维脚本
├── build-scripts/            # electron-builder NSIS 钩子 + 构建配置
├── docs/                     # 项目文档
├── .github/workflows/        # CI/CD（PR Checks + Nightly + Build）
└── resources/                # 图标、VC++ 运行库、预置数据库
```

## 许可证

MIT License - 详见 [LICENSE](LICENSE)

Copyright © 2025-2026 贵州省乡村振兴项目组

## 安装包获取

| 平台 | 安装包 | 获取方式 |
|------|--------|---------|
| Windows 10/11 x64 | `MRRS-Setup-<版本>-x64.exe`（约 204 MB，**自包含**） | GitHub → Releases（推 `v*` 标签由 Actions 自动构建并附带 SHA256） |
| 麒麟 V10 / 统信 UOS ARM64 | `*.deb`（自包含后端二进制） | 同上（`build-arm64.yml` 产出） |

> **安装包自包含清单（目标机器无需预装任何环境）**：Python 3.11 运行时与全部依赖（PyInstaller onedir，`_internal/` 内自带 `python311.dll` / `VCRUNTIME140(1).dll` / `MSVCP140.dll`）+ Electron 33 + Chromium + 前端产物 + Alembic 迁移与首启自建数据库 + reportlab 内置中文字体（PDF 不依赖系统字体）+ **rapidocr-onnxruntime 离线 OCR 模型（Windows 内置；ARM64 构建过滤降级为 503+手工录入）** + VC++ Redistributable（安装时校验 SHA256 后静默安装，作为系统级兜底）。
> **运行环境**：Windows 10/11 x64（Electron 33 不支持 Win7/8）；数据写入 `%APPDATA%\Assistance-Management-Information-System`（安装目录只读也可运行）；后端仅监听 `127.0.0.1`，端口被占用时自动切换。
> 本机 Windows 构建产物位于 `dist/electron/MRRS-Setup-<版本>-x64.exe`；发布校验和随 GitHub Release 一起提供。

## 近期修复记录

### 2026-10-19（v1.15.0）UI v2.0：主题 3 套 + 显示偏好 4 档 + 设计系统统一
- 🎨 **主题 5→3**：军绿（默认，无 `data-theme`）/ 深色大屏 `dark-bigscreen`（大屏专用）/ 户外高对比 `outdoor`；
  旧值 light/dark/military/high-contrast 由 `normalizeTheme()` 迁移，历史用户不失效
- 🔤 **显示偏好 4 档**：字号（紧凑/标准/大号，`--font-scale` 0.92/1/1.12）、密度（舒适/紧凑，表格行高 44/34px）、
  高对比、简化模式（隐藏趋势箭头/辅助说明/高级字段）；localStorage `ui:prefs` + `<html data-*>`，
  `composables/useUiPrefs.ts` 唯一入口，外观设置面板（头像下拉「外观设置」）即时生效并持久化
- 🧱 **Token 升级**：主色阶 50/100/500/600/700/900、卡片边框、两级阴影（`--shadow-card`/`--shadow-pop`）、
  三档圆角（8/6/999）、字号阶梯 calc 缩放、正文行高 1.6、数字 tabular-nums、侧栏深绿渐变 + 当前板块金色竖条
- 🧩 **全局组件类 + 通用组件**：`.app-card/.app-stat-card/.app-empty/.app-loading/.app-error/.app-table-toolbar`；
  `components/common/` 6 个通用组件（AppPageHeader/AppStatCard/AppEmpty/AppLoading/AppError/AppTableToolbar）
- 🧭 **导航体验**：侧栏当前板块金色竖条、收起态 hover/键盘聚焦浮层、面包屑「板块 › 页面」、Ctrl+K 命令面板
- 🖥️ **工作台/大屏**：工作台 KPI 统计卡 + 待办清单 + 图表层级；大屏三层结构 + 3m/6m/10m 距离字号分档 + 15s 自动轮播（可暂停/关闭）
- 🧪 **视觉回归门禁**：`tests/unit/ui/ui-tokens.test.ts`（Token/主题/偏好/类契约）+ `tests/e2e/visual`（10 页 DOM 结构基线）；
  硬编码色基线 345 → 305（57 个文件，目标 ≤200，改动文件零新增）
- 🐛 **本轮修复的真实问题**：多列表页 `page_size=500` 超后端上限 200 → 422（统一为 200）；工作台 KPI 取消请求被误判为错误（已降级）；
  Token 重复定义覆盖（已清理）；面包屑最长路径优先（`/rural-works/list` 不再错误命中父级目录）

### 2026-10-18（v1.14.0）功能大迭代：一户一档 / 影像库 / 消费帮扶 / OCR
- 🏠 **一户一档**：新增 `households` / `household_members` / `household_risk_records` 三表与 `/households/*` API；
  风险预警（连续未走访 >90 天且非一般户→中；大病/住房不安全/突发困难→高）、成员管理、走访挂户回写、
  一键汇总回填帮扶村年度人口（`VillagePopulation`，幂等）、台账 xlsx/csv 导出
- 📷 **影像库**：`photo_archives` 表 + `/media/photos/*`；EXIF 拍摄时间/GPS 自动解析、GPS ≤5km 就近匹配帮扶村、
  `spot_key` 多期分组、Pillow 生成 PNG 对比图（左右/2xN + 日期标注）
- 🛒 **消费帮扶台账**：`consumption_records` + `/consumption/*`（替换已下线的舆情监测；与帮扶村年度板块
  `consumption_support` 区分），品类/金额/采购方/供货方统计与导出
- 🧾 **经费凭证 OCR**：离线引擎 `rapidocr-onnxruntime==1.4.4` + `POST /funds/ocr-voucher`，识别金额/日期回填；
  引擎不可用时 503 降级为手工录入，不阻断业务
- 📊 **报表模板组合导出**：任意字段组合 → xlsx/csv/docx/pdf（单次上限 5000 行）+ 打印数据
- 🧹 **界面精简**：删除驻村工作台、舆情监测、国际化/邮件设置、独立校验规则页（并入数据校验三 Tab）；
  数据校验单页 `/data-verify`（校验执行/规则管理/字段说明）
- 🧭 **导航体验**：7 板块标题 18px 加粗 + 默认折叠（`nav:expanded-sections`）；汇报大屏新增「退出大屏」
- 🗃️ **遗留表清理**：删除 `villages` / `villagers` / `industries` / `sentiment_news`；`rural_works` / `rural_tasks` /
  茶园 / 刺梨园改挂 `supported_villages`；数据上报「生成→接收→可见」链路端到端修复（协议不变）

### 2026-10-18（v1.13.1）发布构建修复与自包含验证
- 🛠️ **Windows 发布构建恢复**：tag 构建不再重复跑全量测试（与 main 同代码却随机红），改为「main 最近 PR Checks 必须绿 + Windows 敏感后端子集 + 前端类型/导航子集 + 失败日志 artifact」，全量门禁仍由 main PR Checks 与 Nightly 承担
- 🛠️ **ARM64 构建修复**：`Dockerfile.kylin-standalone` 的 `backend-output` 阶段 COPY 源路径由 `assistance-backend` 修正为实际产物 `assistance-management-backend`（Electron ARM64 DEB 连续两版缺失的根因）
- ✅ **安装包自包含冒烟**：每次发布自动解包并启动打包后端，断言 `/health`、版本/指纹、数据库迁移 `at_head`，以及 Python/DLL/alembic/前端/VC++ 运行库齐全

### 2026-10-18（v1.13.0）导航架构重构（向后兼容）
- 🧭 **单一菜单源**：后端 `backend/app/api/v1/menus.py` 成为全站唯一菜单源（v2 `sections` + `flat_keys`；
  `kind` = page/group/console），侧栏、移动端底部导航、权限面板/权限包菜单树全部数据驱动；
  删除前端菜单副本 `frontend/src/config/menu-config.ts`、`frontend/src/utils/systemMenu.ts` 及其测试
- 🗂️ **导航重排为 7 板块**：工作台（固定首位）+ 帮扶业务 / 乡村振兴 / 工作协同 / 分析汇报 / 数据管理 / 系统管理
- 🧰 **系统管理 6 聚合页**：组织与权限 / 安全与审计 / 运维与监控 / 备份与存储 / 系统设置 / 关于与反馈，
  页内 Tab 切换；旧页面、旧路由、旧菜单 key 全部保留（深链不失效、权限包配置兼容）
- ⌨️ **导航增强**：Ctrl+K 菜单搜索、最近访问与收藏（localStorage `nav:recent` / `nav:favorites`，上限 8）
- ✅ **门禁**：`scripts/check_menu_alignment.py` 重写为规则 A~E（6 板块 / 99 key / 85 带 path 入口全对齐）；
  相关改动文件覆盖率 100%，`menus.py` 语句+分支 100%；发布门禁全量实测：后端 13,550 用例 / 语句 100.00%（43,293/43,293）+ 分支 100.00%（10,636/10,636），前端 6,707 用例（316 文件）/ 12 组 glob 四指标 100%

### 2026-09-14（v1.12.8）
- 🛡️ **R7 恢复维护窗口**：备份恢复期间新的写请求一律 503、读请求放行、等待在途请求归零后执行、`finally` 解除；`/health` 暴露 `maintenance` 状态。修复"恢复时恰有在途写 → Windows 覆盖失败 / POSIX 写进旧 inode 静默丢提交"
- 🛡️ **R14 组织树元数据**：新建组织不再缺 `path/level`（此前导致组织级数据权限 fail-closed，成员一律 403、管理员无法导出数据包）；历史数据由启动自检幂等回填
- 🧱 **R12 低危一致性 7 项**：慢请求计数器原子化、演练状态快照、提醒线程双启动窗口、`os._exit`→优雅关闭、内存任务表终态回收、后台任务调度契约
- 🔒 **R2 残余清零**：数据包/权限包 11 处 zip 打开点补解压后总量闸门与限长读；备份校验改流式；分片上传限长 + 合并摘要分块
- 🚦 **P-1~P-3 预防门禁**：6 个棘轮扫描器接入 CI（`os._exit` / 无界读 / 上传端点 / 子进程编码 / 目录替换 / 裸 Timer）
- 🎨 认证页与布局硬编码色值清零 + 补齐 3 个设计 token（样式棘轮新增归零）
- 📊 后端 11,244 用例 / 覆盖率 100%；前端 6,051 用例；10 个真实 HTTP 探针 0 失败（该版本当时的实测口径；当前口径见上方「质量指标」表）

### 2026-09-13（v1.12.6 / v1.12.7）
- 🛡️ 遗留风险第一批：调度器 RecurringTimer 收敛 + 作业看门狗（自动备份不再静默停摆）、启动不再抢锁 VACUUM、备份语义 fail-loud
- 🛡️ 遗留风险第二批：上传体积三层上限（中间件/端点 18 处/压缩炸弹防护）、导出过期回收、导入失败记录 409 语义、Windows 冒烟作业入 CI
- 🔧 版本与依赖单源收敛（sync-version 13 处 + 删除 3 个无人引用的 requirements 变体）

### 2026-08-09
- ✨ 备份包上传恢复完整链路：`/system/backup/upload-restore` 支持加密备份（密码透传解密）、上传前内存预校验（加密标记/损坏ZIP/缺库文件，拒绝零残留）、恢复流程 WAL 安全（先释放连接池再覆盖）
- ✨ 备份管理页新增「导入备份包」入口（支持任意机器导出的备份包）
- 🐛 备份列表返回 `is_encrypted` 字段（修复加密备份恢复时密码框不出现）
- 🐛 备份上传改为分块流式落盘（8MB 分块 + 10GB 上限），消除大包 OOM 风险
- 🧹 删除死代码 `token_blacklist_service.py`；`fund_budgets`/`policy` 覆盖率补至 100%（总覆盖率 99.86%）
- 🐛 版本一致性测试纳入环境变量优先级（修复残留 `PROJECT_VERSION` 环境变量导致的测试失败）

### 2026-08-05
- 🔒 数据同步提权修复、备份下载权限收紧、审批自动通过越权修复、配置包导出安全加固
- ✨ 预算附件上报、合同附件上报、学校分析页接入真实数据、经费年度总览

### 2026-08-01
- 🐛 修复 Vue `setAttribute('0')` 页面白屏崩溃（ErrorBoundary 单一根元素修复）
- 🐛 修复注册时“通行码无效或已被使用”误报（机器码三级回退验证）
- 🐛 修复 files API 响应格式不统一（改用 `success_response()` 信封格式）
- ✨ 精简用户角色至 4 个核心角色 + `normalize_role()` 向后兼容

> 详见 [CHANGELOG.md](CHANGELOG.md)
