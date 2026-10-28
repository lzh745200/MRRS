# 帮扶管理信息系统

> 乡村振兴 — 完全离线的单机版桌面应用 | 多机协同数据同步 | v1.18.23

![Version](https://img.shields.io/badge/version-1.18.23-blue)
![License](https://img.shields.io/badge/license-MIT-lightgrey)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20ARM64-orange)
![Tests](https://img.shields.io/badge/tests-22%2C280-brightgreen)
![Coverage](https://img.shields.io/badge/coverage-100%25-brightgreen)

## 本版亮点（v1.18.23）

- **门禁统一入口 `scripts/run_gates.py`**：29 道门禁的「在哪跑 / 带什么参数 / 编码怎么设」
  固化成注册表，本地一条命令与 CI 同款；收口实测 **34 道 PASS / 0 FAIL / 0 SKIP**。
  背景很实在：一天内三次"门禁自己跑不起来"（cwd 错、缺 `--json`、GBK 控制台崩），
  差点被误判成代码红
- **新增三道门禁**：`no-print`（桌面端没有控制台，`print` 输出用户和排障都看不到）、
  `dist_size`（前端产物体积棘轮，当前 9.2 MB / 674 文件 / 114 个 .br）、
  `bench`（关键路径性能基线，5,000 行 xlsx 解析 0.32s / CSV 导出 0.005s / 模板生成 0.05s；只报警不阻断）
- **修掉一处真实回归**：`milestoneProgress` 在响应体为 `null`/`undefined` 时抛
  `TypeError`（"as any 清零"把守卫改成了只容忍"信封里缺 items 键"）—— 改为显式
  `| null | undefined` + 可选链，**不**回退到宽松断言
- **端点计数口径写明**：`check_doc_numbers` 统计 `/api` 前缀端点 **845**；全部 FastAPI 路由
  合计 **849**（含 `/health`、`/favicon.ico`、`/version.json`、SPA catch-all）。两个数字是口径差异，
  不是删了接口
- **分段测试执行器加单实例锁**：根治"并发跑全量 → `.coverage` 被重置 → 覆盖率假红"
- **技术债继续单向下压**：mypy **1394 → 1385**；`as any` **196 → 172**

## 历史亮点（v1.18.18）

- **修掉 6 个系统接口全部不可达**：`system.py` 与聚合器重复加了 `/system` 前缀，实际注册成 `/api/v1/system/system/info` —— 正确路径**全部 404**（含关机/重启），因无人调用一直没被发现；顺带清掉 `config_package` 重复注册多出的 4 条错误路径，路由总数 853 → 849
- **新增路由认证覆盖门禁**：`api_v1_router` 无全局认证依赖，少写一行 `Depends` 就是越权入口；门禁用运行时依赖树递归判定，58 个无认证路由逐个核查并登记理由（**无真实漏洞**）
- **修掉一处用户可见的乱码报错**：加密包版本不匹配时原先把 bytes 直接拼进消息，
  用户看到 `b'9.9'`；非法版本字节更会变成**不可见控制符**（冒号后一片空白）。
  现统一渲染为 `不支持的版本: 9.9（本机支持 1.0）`，非法字节转义为 `\xNN`
- **修掉"把内建函数当类型注解"**：`Optional[any]` / `value: any` 里的 `any` 是内建函数，
  注解零约束却静默生效 —— 改为 `Optional[Any]` / `Any`
- **技术债棘轮首次下调**：mypy 1394 → **1391**，`as any` 196 / `except Exception` 802 持平
- **核查留痕**：逐条核对 mypy 高风险类别与 129 处宽泛 `except`，把"疑似但实为误报"
  的结论写进 CHANGELOG，避免下次重复排查

## 历史亮点（v1.18.17）

- **技术债棘轮上线**：mypy 错误数 / 前端 `as any` / 后端 `except Exception` 三类此前
  无人看管的指标装上了闸门 —— 基线存**数量 + 精确位置**，超限直接列出新增项；
  `--update` 只许下调，上调需 PR 说明理由
- **修掉新门禁自身两个会失效的点**：① 基线 1393 与实测 1394 不一致（一提交就红，
  核实为存量口径偏差后按实测重建）；② mypy 解析失败时原会**静默按 0 放行** ——
  改为 fail-closed（exit 2），不再是 `|| true` 换马甲
- **CI 固定 `mypy==1.19.1`**：棘轮把计数当上限守着，不 pin 则上游换规则就能让全量计数漂移
- **Python 3.13 兼容**：`rapidocr-onnxruntime` 加 `python_version < "3.13"` 标记，
  3.13 下不再让整个 `pip install -r requirements.txt` 失败（OCR 走既有 503 降级）
- **门禁隔离**：三层对齐的参照库落仓库内临时目录，清理失败不再带崩门禁进程

## 历史亮点（v1.18.16）

- **修掉发布流水线的竞态缺陷**：Windows 作业的 electron-builder 在有 `GH_TOKEN` 时
  会按 `onTagOrDraft` 自行发布；若 ARM64 作业先把 Release 发成正式版，它判定
  「existing type not compatible」→ **exe/blockmap/latest.yml 全部跳过**，
  v1.18.15 因此只剩 6 个资产（v1.18.14 是 8 个）。现改 `--publish never`，
  上传统一由 softprops 负责，并把两个元数据文件显式列入清单
- **新增构建期守卫**：NSIS 构建缺 `latest.yml` / `.exe.blockmap` 直接失败并打印 dist 清单，
  不让「Release 少文件」留到发版后才发现
- **依赖版本 pin**：`bcrypt==5.0.0` / `cryptography==50.0.2` / `setuptools==84.2.1` /
  `wheel==0.48.0` —— 此前本地 bcrypt 4.0.1、CI 实装 5.0.0，本地与 CI 测的不是同一套依赖
- **纠正一处文档误述**：`latest.yml` 不是「Windows 自动更新所需」——本系统没有
  `electron-updater` 也没有更新检查代码（离线部署，升级 = 覆盖安装）
- **docs/INDEX 补齐 12 篇漏收录文档**（7 篇 ADR + 4 篇 Agent 约定 + 通知 UI 规范）

## 历史亮点（v1.18.15）

- **帮扶村「分段数据」导入失败时能看到原因了**：此前导入结束只报「成功 5 条、失败 3 条」，
  既不知道是哪一行、也不知道为什么，只能整份重来。现在三个失败分支
  （表头未识别 / 行内有内容但全部列转换失败 / 写库异常）都会记下
  **Excel 行号 + 字段模型 + 年份 + 异常栈**，现场把日志发给运维即可定位
- **表头识别失败不再静默白导**：模板列名被改或贴错工作表时，整表按失败计数并明确告警
- **文档与三份 PPT 的实测数字全部追平真值**：后端 14,870 / 前端 7,374 / 合计 22,244，
  此前 PPT 停留在 v1.18.8 的旧值（14,722 / 7,356），与 README 自相矛盾
- **仓库卫生**：清理 1,405 个测试残留目录（6.6 GB）；`.gitignore` 补齐
  `backend/verify_*/` 等三类每次跑测试都会新生的目录

## 历史亮点（v1.18.14）

- **组织编码接入权威行政区划表**：新增 `backend/app/data/admin_divisions.json`（省级 34 全量、
  贵州 9 市州 + 88 县级全量，取自仓库内置 geojson adcode，另存区划调整换码），
  落库前统一校验 **存在性 + 层级 + 父子同区划 + 别名归一**
- **修掉 4 个真实缺陷**（均由「黔南州代码 522700」这条反馈顺线查出）：
  ① 初始化建根组织时编码被**随机替换**成 `ORG-XXXXXXXX`（实测传 522700 落库 ORG-848B7F7C）；
  ② 初始化**强制省级编码**，黔南州（市州级）首启必被拒；③ 不校验代码**是否真实存在**
  （522799 能入库）；④ 不校验**父子同区划**（都匀市 522701 能挂到贵阳市 520100 下，
  组织树与数据权限会把黔南的县市算进贵阳子树）
- **越权探测顺带修复**：`POST /organizations` 改为**越权 403 先行**，越权者无法再用
  400/其它响应差异反推其它分支的组织编码（编码是跨机匹配标识，可枚举即信息泄漏）
- **缺表自动降级**：权威表文件缺失/损坏时回落「末位规律」并告警，绝不因缺文件把合法编码判非法
- **历史亮点（v1.18.1 起）**：

- **登录页务实化改造**：修掉「注册账户」死链（默认不开放自助注册却无条件显示，现已按 `public-config` 显隐、
  取不到即隐藏）；被锁定/限流时显示**倒计时并禁用按钮**；失败即清空密码并聚焦；CapsLock 提示；
  2FA 满 6 位自动提交；背景 12 张 3.51MB 轮播 → 1 张静态图（**净减 3.16MB**）
- **顺手修掉的真 bug**：`authStore.login` 读 `data.message` 而 FastAPI 返回 `detail` →
  后端中文错误文案全部丢失（用户看到 `Request failed with status code 423`），已按
  `detail → message → err.message` 取值并透出 `httpStatus`
- **R35 三层对齐门禁**：一次比对 **前端 API 路径 ↔ 后端路由**、**ORM 模型 ↔ 数据库 schema**、
  **前端 TS interface ↔ 后端 Pydantic 字段**，专治"单测全绿、真机全废"；上线即抓到两处契约漂移
  （行业模型列名与 `r42` 迁移不一致、数据上报 schema 字段名与 service 返回不一致）并已修复
- **100% 覆盖率门禁真绿复验**：发现 `backend/.coveragerc` 被误删导致 `fail_under=100` 静默失效
  （12/12 段"通过"实为 99%），恢复后补齐 7 处缺口，现为 **46,243 语句 / 11,560 分支，Miss 0 / BrPart 0**
- **离线可靠性**：备份携带 PII 密钥指纹（跨机恢复 409 + 显式放行 + 审计）、备份启动补跑、
  `OFFLINE_MODE` 统一开关、`/health` 暴露时钟漂移与 WAL 状态
- **介质链路治理**（v1.17.0 起）：四类包统一**整包查重（SHA256）+ 导入台账 + 回执**、
  **来源单位码核对**防包导错组织树、`GET /api/v1/system/self-check` 一次体检 6 项

## 项目状态

| 指标 | 结果 |
|------|------|
| 后端测试 | **14,870 用例**, 0 skipped（CI 12 段独立进程为最终口径；含行+分支覆盖率 100% 门禁） |
| 前端测试 | **7,374 passed**（347 个 `.test.ts`），0 失败 |
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
| UI 设计系统 | **UI v2.0**：主题 3 套（军绿默认 / 深色大屏 / 户外高对比）+ 显示偏好 4 档（字号/密度/高对比/简化，localStorage `ui:prefs`）+ 三档场景预设（标准/紧凑/演示，首次启动按视口自适应）+ 统一 Token/组件类 |
| 前端质量门禁 | 视觉回归基线 10 个关键页面（`tests/e2e/visual`）+ Token 契约测试（`tests/unit/ui`）+ 硬编码色棘轮 **146**（40 个文件；基线 345 → 146，只紧不松） |

| 预防门禁 | 6 个棘轮扫描器（os._exit / 上传限长 / 无界读 / 子进程编码 / 目录替换 / 周期任务注册）接入 CI，NEW=0 |
| 深审台账 | OCR 2026-09-17 全量审查的 358 条 critical/high 已逐条复核（LIVE 337 条），本轮处置与遗留见 `deliverables/ocr-findings-ledger-2026-09-30.md` |
| 真实 HTTP 探测 | 11 个探针脚本（`backend/tests/probe/`，覆盖认证/帮扶村/学校/经费/项目/政策/组织/报表/备份/审批/数据包），**与运行时刻/时区无关**（v1.12.11 起 `probe_r10` 的 `next_send_at` 断言按本地语义解析带偏移的 ISO） |

> **上次全量验证**: 2026-10-28（v1.18.23）— 后端 14,896 用例（0 skipped）+ 行/分支覆盖率 **100.00%**
> （CI 后端测试为 **12 段独立进程**分段执行，各段写独立分片 `.coverage.gate.<stamp>.segN`，
> 全部段跑完后 `coverage combine` 合并、统一 report，由 `.coveragerc` fail_under=100 单一来源判定；
> 46,243 语句 / 11,560 分支，Miss 0 / BrPart 0）；
> 前端 **347 个 `.test.ts` / 7,384 用例、12 组 glob 100%**；E2E 199（含 44 页视觉回归基线）；
> flake8 app+scripts 0 / vue-tsc 0 / eslint 0 / 硬编码色 146（棘轮 146/146）/ 版本单一来源一致 /
> Alembic 单 head（63 版本，r43）/ 门禁脚本全绿（含三层对齐、零断言棘轮、同步覆盖率、菜单对齐、单 head 迁移）

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

### 部署安全必配项（发布版）

> 完整口径见 [部署文档总览](docs/04-部署文档/README.md) 的「部署前置检查（安全红线）」。

- **多机 / 局域网 / 非回环部署**：所有实例必须配置**同一**随机 `PASS_CODE_SECRET`（否则非本机自助注册 fail-closed 403）。
- **viewer 为严格只读**：写操作（含直连 API）服务端一律 403；需要录入/审批请用 `user` 及以上角色。
- **R33 单位授权包**：上级配置 `GRANT_SIGNING_KEY`（Ed25519 私钥，保密勿入库）签发授权包；下级配置 `GRANT_PUBKEY` 验签——**导入授权包前必须先配置验签公钥**，否则导入被拒绝（400）。`GRANT_ALLOW_UNSIGNED` 永远保持 false。
- **R33 写收窄** `GRANT_GUARD_MODE` 默认 `off`（仅菜单裁剪生效）；可选 `shadow`（只记日志）→ `enforce`（越权写 403），生产建议先 shadow 观察再 enforce。

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
- **离线 OCR**: `rapidocr-onnxruntime==1.4.4`（CPU/离线，识别经费凭证金额与日期；**Windows 与 ARM64 安装包均内置模型**。ARM64 侧改用 `opencv-python-headless` + 构建期冒烟，避免为 OCR 引入图形栈依赖；ARM64 安装包体积因此增加约 65–80 MB，前提是目标机 glibc ≥ 2.28）
- **依赖自检**: 运行时依赖登记在 `backend/app/core/required_packages.py`（必需/可选/仅开发三级），
  启动自检与 `GET /api/v1/env/check` 按 **import 名** 校验；自包含安装包不误报、不给无效 pip 建议
- **打包**: PyInstaller（x64 + ARM64）+ electron-builder（NSIS 安装包）

### 前端
- **框架**: Vue 3 + TypeScript + Vite
- **UI**: Element Plus + ECharts + Leaflet；**UI v2.0 设计系统**（`tokens.scss`：主色阶/卡片边框/两级阴影/三档圆角/字号 calc 缩放/行高 1.6/tabular-nums）
- **主题与显示偏好**: 主题 3 套（军绿默认 / 深色大屏 `dark-bigscreen` / 户外高对比 `outdoor`）；显示偏好 4 档（字号 compact/standard/large、密度 comfortable/compact、高对比、简化模式；localStorage `ui:prefs` + `<html data-*>`），外观设置面板统一入口
- **导航**: 后端单一菜单源（`menus.py` v2 `sections`+`flat_keys`，6 板块 / 104 key / 84 带 path 入口 / 16 legacy）数据驱动侧栏/移动端/权限面板；Ctrl+K 命令面板 + 收藏/最近访问；7 板块默认折叠、可展开（`nav:expanded-sections`）；侧栏当前板块金色竖条 + 收起态浮层 + 面包屑「板块 › 页面」；v1.15.15 起「一户一档」入口并入帮扶村「年度数据管理」页（`households` key 转 legacy，路由 `meta.menuKey` 跟随 `villages`）
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
| 后端测试（全量） | pytest | 14,870（0 skipped；行/分支覆盖率 100%） | API/Service/Core/Model/Utils 全覆盖 |
| 后端集成测试 | pytest | 8 套 | Auth/Users/Policies/Search/Audit/API |
| 后端安全测试 | pytest | 3 套 | Data Isolation/Audit/Retry |
| 前端单元测试 | Vitest | 7,020（339 文件） | API/Store/Component/Composable/Utils |
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
├── backend/app/              # 后端（FastAPI，376 个 py / 12 万+ 行）
│   ├── api/v1/               # API 接口层（52 个路由模块文件 + 5 子包；845 个端点）
│   ├── core/                 # 核心：config, security, database, transaction, cache, maintenance(维护闸门)
│   ├── models/               # SQLAlchemy 数据模型（64 个文件 / 124 张表，含 W22 新增 household/media/consumption）
│   ├── services/             # 业务逻辑层（107 个服务文件 / 5 个子包，含 ocr_service / household_service / media_service）
│   ├── middleware/           # CSRF, 审计, 请求日志, 指标, maintenance_gate(写请求闸门)
│   └── startup/              # 启动钩子（种子/监控/恢复/环境自检 + 组织树自愈）
├── frontend/src/             # 前端（Vue 3 + TypeScript，330+ 个源文件：144 个页面 .vue / 32 个组件 .vue / 60 个 API 模块）
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
| Windows 10/11 x64 | `MRRS-Setup-<版本>-x64.exe`（**自包含**，约 270 MB） | GitHub → Releases（推 `v*` 标签由 Actions 自动构建；体积与 SHA256 以 Release 资产的 `SHA256SUMS-windows-x64.txt` 为准） |
| 麒麟 V10 / 统信 UOS ARM64 | Electron 版 `MRRS-Setup-<版本>-arm64.deb`（约 267 MB）+ Web 版 `assistance-management-system_<版本>_arm64.deb`（约 98 MB） | 同上（`build-arm64.yml` 产出；校验见对应的 `SHA256SUMS-*.txt`） |

> **安装包自包含清单（目标机器无需预装任何环境）**：Python 3.11 运行时与全部依赖（PyInstaller onedir，`_internal/` 内自带 `python311.dll` / `VCRUNTIME140(1).dll` / `MSVCP140.dll`）+ Electron 33 + Chromium + 前端产物 + Alembic 迁移与首启自建数据库 + reportlab 内置中文字体（PDF 不依赖系统字体）+ **rapidocr-onnxruntime 离线 OCR 模型（Windows 与 ARM64 安装包均内置；模型随包约 15 MB，ARM64 侧要求目标机 glibc ≥ 2.28）** + VC++ Redistributable（安装时校验 SHA256 后静默安装，作为系统级兜底）。
> **运行环境**：Windows 10/11 x64（Electron 33 不支持 Win7/8）；数据写入 `%APPDATA%\Assistance-Management-Information-System`（安装目录只读也可运行）；后端仅监听 `127.0.0.1`，端口被占用时自动切换。
> 本机 Windows 构建产物位于 `dist/electron/MRRS-Setup-<版本>-x64.exe`；发布校验和随 GitHub Release 一起提供。

> **安装包目前未做代码签名**（证书未采购；签名管线已就绪，见
> [代码签名接入指南](docs/04-部署文档/01-Windows部署/代码签名.md)）。首次运行会遇到：
>
> - **SmartScreen**：提示「Windows 已保护你的电脑」→ 点「更多信息」→「仍要运行」；
> - **Defender 扫描**：首次双击后可能静默扫描数分钟（包体约 270~320 MB），期间安装程序无响应属正常，
>   请勿重复双击。**2026-10-25 实测（Windows 11 + Defender 实时保护）**：未签名的
>   `MRRS-Setup-1.18.5-x64.exe`（316.7 MB）静默安装（`/S`）在本机 **20 分钟以上仍未启动**
>   （`Start-Process` 挂起、目标目录始终未创建、`MsMpEng` 持续占用 CPU），
>   因此「等一会儿就好」并不总成立。涉密/企业环境请**先报白名单**，或由管理员为安装包目录
>   添加 Defender 排除项后再安装；也可先 `Get-FileHash` 核对 SHA256 再分发
>   （与 `SHA256SUMS-windows-x64.txt` 一致）。

## 近期修复记录

### 2026-10-24（v1.18.1）登录门面重构 + 三层对齐门禁 + 门禁真绿复验

- 🐞 **登录页「注册账户」是死链**：`SELF_REGISTER_MODE` 默认 `off`（不开放自助注册），但前端**无条件显示**注册入口，
  而后端早已提供 `GET /api/v1/auth/public-config`、前端一次都没调用。现按配置显隐，**取不到配置即隐藏**（fail-closed）。
- 🐞 **后端中文错误文案全部丢失**：`authStore.login` 读 `err.response.data.message`，而 FastAPI 返回 `{detail}` ——
  用户被锁定时看到的是 `Request failed with status code 423`，而不是「账户已锁定，请30分钟后再试」。
  改为 `detail → message → err.message`，并透出可选 `httpStatus`。
- ✨ **锁定/限流可见化**：`public-config` 新增 `lockout_minutes` / `max_failed_attempts`，
  登录页显示「请稍候 30 分 00 秒」倒计时并禁用按钮；403 未授权本机额外给「去获取机器码」直达。
- ✨ **登录页其余打磨**：失败即清空密码并聚焦、CapsLock 提示、2FA 满 6 位自动提交、「首次使用？」三步引导；
  背景 12 张 3.51MB 轮播 → 1 张静态图（**净减 3.16MB**）。
- 🔒 **R35 三层对齐门禁**（`scripts/check_stack_alignment.py`）：前端 API 路径 ↔ 后端路由、ORM 模型 ↔ 数据库 schema、
  前后端字段三轴一次比对。上线即抓到两处真漂移：行业模型列名与 `r42` 迁移不一致、
  `DataReportStatistics` 前端缺 `pending`，均已修复。
- 🔒 **100% 覆盖率门禁曾静默失效**：`backend/.coveragerc` 被误删 → `fail_under=100` 不再生效，
  分段执行器报的 12/12「全绿」实际只有 99%。恢复配置并补齐 7 处缺口后为
  **45,782 语句 / 11,376 分支，Miss 0 / BrPart 0**。
- 🐞 **备份上传恢复的临时包泄漏**：密钥指纹不一致（409）时未清理已落盘的临时包，
  每次跨机误导入都会留下一个可能上 GB 的残包；现按「存在则删、失败只记日志」处理且保持 409 语义。

### 2026-10-24（v1.17.3）端到端排查修复 + 死代码清理

- 🐞 **组织创建在真实 HTTP 下必然失败（严重）**：`OrganizationCreate` 漏掉 `code` 字段，而端点创建路径
  直接读 `data.code` —— 单测用 MagicMock 传 `data` 不会暴露，**新装机器因此无法创建任何组织**。
  已补 `code` 必填（6 位），`OrganizationUpdate.code` 改为可选（编码只读语义）。
- 🧭 **系统自检端点路径错位**：模块注册在 `/api/v1/self-check`（根级），前端与文档调用
  `/api/v1/system/self-check` → 设置页自检卡片恒 404。改为经 `system` 包聚合注册并移除根级重复注册。
- 🧪 **防回归**：新增 `test_p3_org_create_http_contract.py`（8 例，只走 TestClient 锁定 422 契约）；
  自检路径契约用例断言前后端一致；补齐 `test_v1129_r2_system_api.py` 漏传的 `organization_code`。
- 🧹 **死代码清理**：移除 6 个从未接入任何页面的通用组件（AppEmpty / AppError / AppLoading /
  AppPageHeader / AppStatCard / AppTableToolbar）及其 barrel 与 7 个测试文件，移除 3 个已被
  `build_ppt.js` 取代的一次性 PPT 脚本；`ErrorBoundary` 经核实仍在 `DefaultLayoutSafe` 通过全局名使用，予以保留。
- 🔍 **全仓审计结论**：后端 379 个模块零死代码；前端 412 条 API 路径 vs 后端 720 条路由**零错位**；
  127 份文档 132 条相对链接**死链 0**；`npm audit --omit=dev` **0 漏洞**；PPT 53 页 **0 溢出**。

### 2026-10-21（v1.16.0）系统管理梳理 + 危险操作硬化 + 离线瓦片地图 + PII 密钥迁移

- 🧭 **系统管理左侧分组导航**：6 个聚合页由横向 tab 平铺改为「左分组 + 右内容」，**30 个 tab** 按语义归组；
  分组是**纯呈现层**（`TAB_LAYOUT`），不改后端菜单 key / tab path / 权限粒度 / `?tab=` 深链，
  未登记的新 tab 自动落「其他」组，窄屏 ≤992px 转横向滚动。
- 🔒 **危险操作硬化**：新增 `useDangerConfirm`（普通确认 / 高危录入两档）；管理员**重置他人密码必须手工输入目标用户名**；
  删除组织、恢复备份、轮换密钥、管理员重置密码四类动作补**强制审计**，可在「安全与审计」按操作类型检索。
- 🗺️ **离线瓦片地图**：前端引入 Leaflet 栅格瓦片，瓦片包由构建机预置并复制进安装包；
  新增切片/校验/清单工具链与 `npm run tiles:verify`，Windows 构建增加瓦片预置校验步骤。
- 🔑 **PII 密钥跨机迁移**：新增 `/system/pii-key` 查看指纹 / 导出 / 导入（仅管理员），
  解决多机离线同步时各机 `ENCRYPTION_KEY` 不一致导致 PII 密文永不可解的问题；**只记指纹不记密钥本体**。
- 💾 **备份权限**：普通用户可创建备份，但下载 / 恢复 / 上传恢复 / 删除仍限管理员；
  `viewer` 与未分配角色账号 fail-closed。
- 🧰 **门禁增强**：新增 console tab key ↔ 前端 `TAB_COMPONENTS` 双向一致检查、文档数字漂移检查、
  安全审计覆盖棘轮（动态发现全部写路由模块）。
- ⚠️ **本版移出 R35 删表迁移**：升级演练复现出「表非空即 raise」会让老用户升级中断、装完起不来，
  schema 维持 r34 head，后续改为归档式清理再单独发布。

### 2026-10-20（v1.15.13 ~ v1.15.15）R35 UI 精细化方案 C + 一户一档入口收敛 + 发布闭环

- 🎨 **侧栏品牌区（v1.15.15）**：系统标识名 16→**20px / 800 单行**（logo 36px、侧栏头 64px），修正品牌名低于板块标题（18px）的层级倒挂；工作台提升为板块级入口（18px/700、Home 图标）。
- 📊 **全站表格规范（v1.15.15）**：所有 el-table 启用 border（**117/117**）恢复列宽拖拽；序号列统一 **72px**（25/25）、选择列 **48px**（10/10）、操作列统一 fixed=right（67/67）。
- 🧰 **筛选栏与页头统一（v1.15.15）**：清理 **114 处**行内宽度，改为全局 4 档规范（input 220 / select 160 / date 240 / number 120）+ 统一 16px 间距；**19 个列表页**接入共享 PageHeader（全站 31 页）。
- 📐 **全局精细化层（v1.15.15）**：新增 `frontend/src/styles/components/ui-refine.scss`（筛选栏/表格规范 / 8px 栅格 / 响应式断点 1200·992·768）。
- 🏠 **一户一档入口收敛（v1.15.15）**：「一户一档」不再占侧栏一级菜单，入口迁入 **帮扶村管理 → 年度数据管理**页首张卡片（`/households?village_id=<村ID>`，列表按村预筛选）；后端菜单 key `households` 转 **legacy**（权限包/历史 `allowed_menus`/深链兼容），路由 `meta.menuKey` 改为 `villages`（跟随帮扶村管理权限）；旧链接 `/households` 仍可直达。
- ✅ **发布闭环**：v1.15.14 在 CI 全绿后成功构建 Windows x64 安装包；v1.15.15 双平台发布（PR Checks success / Build Windows Installer success / Build ARM64 Deb success），产出 Windows x64 NSIS（272.8 MB）与 ARM64 Electron DEB（196 MB）+ Web DEB（58 MB），附 `SHA256SUMS-*` 与 `latest.yml`。
- 🧹 **v1.15.14**：`effectiveness_evaluations` 外键重建迁移 + 冗余退码清理；**v1.15.13**：R33 单位授权导航入口补齐（系统管理 → 组织与权限）、PR Checks 红项修复、文档/PPT 更新。

### 2026-10-19（v1.15.8 ~ v1.15.12）安全收官 + R33 单位授权 + CI 稳定化

- **viewer 严格只读**：写操作（含直连 API）服务端一律 403；未配置 `PASS_CODE_SECRET` 时非回环自助注册 fail-closed。
- **R33 单位授权**：上级配置单位模块授权矩阵并按 Ed25519 签发授权包，下级验签导入；写收窄 `GRANT_GUARD_MODE` 默认 off（可选 shadow→enforce）。**导入授权包前必须配置 `GRANT_PUBKEY`**，`GRANT_ALLOW_UNSIGNED` 永远 false。
- **发布门禁**：ARM64 工作流补 release gate（与 Windows 同口径：tag commit 的 PR Checks 必须全绿才发布）。
- **CI 稳定性**：后端测试改 **12 段独立进程**（`--cov-append` 合并 + 覆盖率 100% 单一来源），消除“约 24 分钟进程消失”型失败；nightly 后端同步 6 段。
- 测试规模：后端 13,926 用例（1 skipped）、前端 6,865 用例（328 文件）。

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
- ✅ **门禁**：`scripts/check_menu_alignment.py` 重写为规则 A~E（当前口径 6 板块 / 104 key / 84 带 path 入口 / 16 legacy 全对齐）；
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
