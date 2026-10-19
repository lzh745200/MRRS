# W23 契约：UI 精美·科学·一致性重构（v1.15.0）

> 用户要求："全部彻底执行，确保完全没有问题"。本文件为唯一实施契约。
> 总目标：**庄重可信 × 高效录入 × 低负担阅读**；硬编码色归零、主题 5→3、三档字号/密度/高对比/简化模式、
> 统一页面模板与三件套、侧栏折叠体验、命令面板、大屏三层结构、工作台统计卡、视觉回归门禁。

## 0. 设计决策（冻结，所有人以此为准）

### 0.1 主题（5 → 3 套）
| data-theme | 名称 | 用途 |
|---|---|---|
| `military`（默认，:root） | 军绿亮色 | 日常办公（默认） |
| `dark-bigscreen` | 深色大屏 | 会议室大屏专用（仅大屏页启用） |
| `outdoor` | 户外高对比 | 现场强光/低视力 |

删除 `light`、以及 tokens.scss 中其余 `[data-theme]` 块（保留上面 3 套）。
主题切换：管理员可设置全局默认；用户可切 3 套；大屏页强制 `dark-bigscreen`。

### 0.2 用户显示偏好（新增三档能力，存 localStorage `ui:prefs`）
| 属性 | 取值 | 默认 | 语义 |
|---|---|---|---|
| `data-font-size` | `compact` / `standard` / `large` | standard | 全站字号缩放：compact ×0.92、standard ×1、large ×1.12 |
| `data-density` | `comfortable` / `compact` | comfortable | 表格/列表行高与内边距：comfortable 40px 行高、compact 34px |
| `data-contrast` | `normal` / `high` | normal | 高对比：文字/边框加深、弱化色替换为实色 |
| `data-simplify` | `false` / `true` | false | 简化模式：隐藏次要信息（趋势箭头/辅助说明/非关键列），保留主操作 |

实现契约：`document.documentElement.dataset.*` 四属性；样式全部由 tokens.scss + 全局模板覆盖实现；
`ui:prefs` 读写工具 `frontend/src/composables/useUiPrefs.ts`（唯一读写入口，损坏 JSON 回退默认）。

### 0.3 视觉 Token（tokens.scss 升级值）
- 主色：`--color-primary: #2d6a4f`（保留）；新增 `--color-primary-50: #f2f8f4`、`--color-primary-100: #dfeee5`、
  `--color-primary-500: #2d6a4f`、`--color-primary-600: #235a42`、`--color-primary-700: #1b4332`、`--color-primary-900: #0f2e22`。
- 侧栏：深绿渐变 `linear-gradient(180deg, #123f2e 0%, #0f2e22 100%)`；当前项金色竖条 `--color-accent-gold` 3px。
- 金色仅三用：选中竖条 / 数据高亮数字 `.num-highlight` / 表头底线。面积 ≤5%。
- 背景：`--color-bg-page: #f5f7f5`（提亮）；`--color-bg-card: #ffffff`；卡片边框 `--color-card-border: #e5e9e6`。
- 卡片阴影统一 2 档：`--shadow-card: 0 1px 2px rgba(16, 40, 28, 0.04), 0 4px 12px rgba(16, 40, 28, 0.04)`；
  `--shadow-pop: 0 12px 32px rgba(16, 40, 28, 0.12)`。
- 圆角：`--radius-card: 8px`、`--radius-control: 6px`、`--radius-pill: 999px`。
- 间距节奏：页头 24 / 内容区 24 / 卡片内 20 / 表单行 12 / 表格行 40（compact 34）。
- 字号阶梯（calc 形式，受 `--font-scale` 缩放）：
  `--text-xs: calc(12px * var(--font-scale))`、`--text-sm: calc(13px * var(--font-scale))`、
  `--text-md: calc(14px * var(--font-scale))`（正文基准）、`--text-lg: calc(16px * var(--font-scale))`、
  `--text-xl: calc(18px * var(--font-scale))`、`--text-2xl: calc(20px * var(--font-scale))`、
  `--text-3xl: calc(24px * var(--font-scale))`、`--text-display: calc(32px * var(--font-scale))`；
  同时 `--el-font-size-base: var(--text-md)`。
- 行高：正文 1.6（`--leading-normal: 1.6`）、标题 1.25。
- 数字：全局 `table, .kpi-value, .stat-value { font-variant-numeric: tabular-nums }`。

### 0.4 全局模板样式（不碰 .vue，全部在 `frontend/src/styles/components/*.scss`）
- `list-page.scss`：页头与筛选区间距、表格视觉（表头 `--color-primary-50` 底 + 13px/600 + 金色底线）、
  hover 行 `--color-primary-50`、去斑马纹（`.el-table--striped` 行背景统一白）、分页右对齐、
  操作列次要按钮弱化为文字按钮（`.el-table .el-button.is-link` 已有，不新增结构）。
- `form-page.scss`：分组卡片 8px 圆角 + 20px 内边距 + 分组标题 16px/600；label 右对齐 13px；
  必填星号危险色；错误文案 `--text-xs` 危险色；只读态灰底。
- `table.scss`：行高变量 `--table-row-height`（comfortable 40 / compact 34）；
  `[data-density="compact"] .el-table td .cell, [data-density="compact"] .el-table th .cell { padding: 6px 8px; }`。
- `dialog.scss`（新增）：三档宽度 `--dialog-w-sm 480 / md 640 / lg 800`；统一 header 18px/600、footer 按钮顺序。
- `states.scss`（新增）：`.app-empty`/`.app-loading`/`.app-error` 三件套统一样式（图标/标题/说明/操作按钮）；
  全局类可直接用于新页面，旧页面不改。
- `card.scss`（新增或并入）：`.app-card` 统一卡片；`.app-stat-card` 统计卡（数字 28/700 tabular-nums、标签 13 次要色、趋势箭头 up/down 语义色）。
- `button.scss`（可并入 index.scss）：主按钮高 32（大 36）、圆角 6、阴影弱化；危险按钮描边为主；文字按钮 hover 用浅主色底。
- 大屏字号分层：`.bigscreen` 根下 `--bs-text-*` 三档（3m 标准、6m ×1.25、10m ×1.5）由 `data-bigscreen-distance` 控制；
  默认 6m。
- 高对比：`[data-contrast="high"]` 覆盖文字为主色深色、边框 `--color-border-dark`、卡片去阴影加强边框、
  表格 hover 用 `--color-primary-100`。
- 简化：`[data-simplify="true"] .stat-trend, [data-simplify="true"] .list-hint, [data-simplify="true"] .advanced-only { display: none !important; }`
  （新页面使用这些类名；不强制改旧页面）。

## 1. 工作包与文件权属（并行，禁止越界）

| 包 | 负责 | 允许修改文件 | 交付 |
|---|---|---|---|
| W1 | Lead | `frontend/src/styles/**`（tokens.scss、index.scss、theme-elevated.scss、components/*.scss 新增）、`frontend/src/composables/useUiPrefs.ts`、`frontend/src/components/settings/AppearanceSettings.vue`（新增，显示偏好面板）、`frontend/tests/unit/composables/useUiPrefs.test.ts`、`frontend/tests/unit/components/settings/AppearanceSettings.test.ts`、主题相关既有测试更新 | token 升级、主题 5→3、模板样式、模式属性、偏好面板、`main.ts` 样式导入更新 |
| W2 | frontend-screen | `frontend/src/views/households/**`、`frontend/tests/unit/views/households/**`、`frontend/tests/unit/api/households.test.ts`（如需） | 一户一档列表/详情接入 `.app-card`/`.app-stat-card`/三件套类/简化类；表格密度与操作列收敛；唯一执行者测试同步 100% |
| W3 | frontend-nav | `frontend/src/layouts/DefaultLayoutSafe.vue`、`frontend/src/components/nav/**`、`frontend/tests/unit/layouts/DefaultLayoutSafe.test.ts`、`frontend/tests/unit/components/nav/**`、`frontend/src/views/dashboard/Index.vue` 中**仅**侧栏/顶栏相关片段（如需）、`frontend/src/views/dashboard/components/HeaderActions.vue`（顶栏） | 侧栏：当前板块金色竖条 + 折叠态悬停浮层子菜单 + 面包屑（板块›页面）；顶栏：命令面板入口；测试同步 100% |
| W4 | frontend-console | `frontend/src/views/dashboard/**`（Index.vue + components，除 HeaderActions.vue）、`frontend/tests/unit/views/dashboard/**` | 工作台：KPI 统计卡（新 `.app-stat-card`）、待办清单、快捷入口视觉层级、空态/加载三件套；测试同步 100% |
| W5 | backend-menu | `frontend/src/views/bigscreen/**`、`frontend/tests/unit/views/bigscreen/**` | 大屏三层结构（标题时间条/KPI 大数字/2-3 列图表）、字号距离分档（`data-bigscreen-distance`）、自动轮播、退出保留；测试同步 100% |
| W6 | proposal-writer | `frontend/src/components/common/**`（AppPageHeader/AppStatCard/AppEmpty/AppLoading/AppError/AppTableToolbar + index.ts）、`frontend/tests/unit/components/common/**`、`frontend/tests/unit/ui/**`（视觉回归 vitest）、`frontend/tests/e2e/visual/**`（Playwright DOM 结构快照） | 通用组件（含测试 100%）+ 视觉回归基线（10 个关键页面：工作台/帮扶村/项目/经费/一户一档/影像库/消费帮扶/系统管理/数据校验/大屏） |
| W7 | docs-ppt | `CLAUDE.md`、`README.md`、`docs/**`（UI 规范/使用指南）、`docs/build_ppt.js`、`docs/帮扶管理信息系统介绍.pptx`、`项目文件结构说明.md`、`deliverables/README.md` | 文档/PPT 更新到 v1.15.0（新增 UI 能力章节与页面） |

**公共组件使用约定**：W6 的 common 组件由 W2/W4 按需接入（先等 W6 落地组件，再接入；或并行时 W2/W4 先用全局 class，后接入组件——**以全局 class 为准，组件为可选增强**）。

## 2. 硬约束

1. **单执行者**：每个 `.vue` 只能被其唯一测试文件真实执行；W2/W3/W4/W5 改动某 .vue 必须更新其唯一执行者测试，保持四指标 100%。
2. **禁止新增硬编码色**：只用 `var(--...)` token；`check_hardcoded_styles.py --files <改动>` 0 新增，且总基线只降不升。
3. 不改 `router/index.ts`、`menus.py`、backend、`.github/workflows`（Lead 除外）。
4. 不新增第三方依赖（不改 package.json/package-lock）。
5. 前端每个包交付前必须自测：目标测试四指标 100% + `vue-tsc --noEmit` + `eslint --max-warnings=0` + 硬编码色 0 新增。
6. 中途不跑全量、不 git（Lead 统一门禁）。
7. 主题切换/偏好面板：`AppearanceSettings.vue` 由 W1 建；W3 在顶栏用户下拉中挂入口（可调用 `useUiPrefs`）。

## 3. 验收标准

- `check_hardcoded_styles.py` 基线从 345 → **≤ 200**（本轮收敛目标；W1/各包改动文件 0 新增）
- 主题 `[data-theme]` 仅 3 套（military/dark-bigscreen/outdoor）
- 四档显示能力可切换且持久化（字号/密度/对比/简化）
- 三件套统一样式 + 通用组件（6 个）四指标 100%
- 侧栏：当前板块金色竖条 + 折叠态悬停浮层 + 面包屑
- 大屏：三层结构 + 距离字号档 + 自动轮播 + 退出
- 工作台：KPI 统计卡 + 待办清单 + 空态
- 视觉回归：10 个关键页面快照（DOM/关键 computed style）可在 CI 稳定运行
- 前端全量 12 组 glob 100%；E2E 全量 154+；vue-tsc/eslint/硬编码色/17 项门禁全绿
- 文档/PPT 更新；版本 1.15.0；构建 Windows+ARM64 成功

## 4. 实施顺序

1. W1 先落 tokens/主题/模板样式（其他人依赖 token 名）。
2. W6 common 组件 + 视觉回归（与 W2-W5 并行准备，接入延后）。
3. W2/W3/W4/W5 页面改造（各自唯一测试同步）。
4. Lead 集成：`useUiPrefs` 在 App/布局初始化（data-* 属性挂载）、顶栏入口、样式导入检查。
5. Lead 全量门禁 + 文档/PPT（W7）+ 构建 + 发布 v1.15.0。
