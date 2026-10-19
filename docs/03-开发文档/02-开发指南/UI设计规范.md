# UI 设计规范（Token 驱动 · UI v2.0）

> **版本**: v2.0（v1.15.0，2026-10-19）｜配套总纲：《[UI设计方案](../07-UI设计规范/UI设计方案.md)》
> 本文档定义本系统的 UI 视觉与交互规范，用于保证界面一致性、美观度与跨设备响应式体验。

## 1. 设计原则

- **一致性**：颜色、间距、字体、圆角、阴影统一使用 Token（禁止随意硬编码）；全局样式集中在 `styles/components/*.scss`。
- **庄重可信**：军绿为主，金色仅三用（当前板块竖条 / 数据高亮 / 表头底线），面积 ≤5%。
- **低负担阅读**：正文行高 1.6、字号可整体缩放、表格去斑马纹、简化模式隐藏次要信息。
- **可用性**：交互可预期、反馈及时、错误可见可重试；移动端可单手操作。
- **响应式**：以 768px 为关键断点，移动端侧边栏采用抽屉式 + 遮罩。

## 2. 设计 Token（来源）

统一 Token 文件：`frontend/src/styles/tokens.scss`（设计 Token 唯一数据源）。

### 2.1 颜色（v2.0 升级）

- **主色阶**：`--color-primary-50/100/500/600/700/900`（`#f2f8f4` / `#dfeee5` / `#2d6a4f` / `#235a42` / `#1b4332` / `#0f2e22`）；
  旧 `--color-primary-light-1~9` / `dark-1~2` 保留兼容。
- **金色三用**：`--color-accent-gold` 仅用于：当前板块竖条 / `.num-highlight` 数据高亮 / 表头底线。
- **语义色**：`--color-success / --color-warning / --color-danger / --color-info`。
- **文字色**：`--color-text-primary / regular / secondary / placeholder`。
- **背景/边框**：`--color-bg-page: #f5f7f5`、`--color-bg-card: #ffffff`、`--color-card-border: #e5e9e6`、`--color-border*`。
- **侧栏**：`--sidebar-bg` 深绿渐变（`#123f2e → #0f2e22`）。

### 2.2 版式 / 圆角 / 阴影 / 动效

- **字号阶梯**：`--text-xs/sm/md/lg/xl/2xl/3xl/display`（12/13/14/16/18/20/24/32px）
  **全部 `calc(… * var(--font-scale))` 化**，由显示偏好档位缩放（compact 0.92 / standard 1 / large 1.12）。
- **行高**：正文 `--line-height-normal: 1.6`；标题 `--line-height-tight: 1.25`。
- **数字**：`table / .kpi-value / .stat-value / .num-cell` 使用 `font-variant-numeric: tabular-nums`。
- **间距**：`--spacing-xs/sm/md/lg/xl/xxl/xxxl`（4/8/16/24/32/48/64px，4px 基准网格）。
- **圆角**：`--radius-card: 8px`（卡片/对话框）、`--radius-control: 6px`（按钮/输入）、`--radius-pill: 999px`。
- **阴影**：`--shadow-card`（白底卡片轻阴影+边框）、`--shadow-pop`（弹层/浮层/抽屉）；禁止自定义阴影值。
- **过渡**：`--transition-fast/normal` 等；尊重 `prefers-reduced-motion`。

### 2.3 断点

- **移动端**：< 768px；**平板**：768px–991px；**桌面**：≥ 992px。
- 断点 mixin 见：`frontend/src/styles/responsive.scss`。

## 3. 主题规范（5 → 3 套）

| 主题 | 选择器 | 用途 |
|---|---|---|
| **军绿（默认）** | `:root`（**无 data-theme 属性**） | 日常办公（默认） |
| **深色大屏** | `[data-theme="dark-bigscreen"]` | 会议室大屏专用（仅大屏页强制启用） |
| **户外高对比** | `[data-theme="outdoor"]` | 现场强光 / 低视力（高对比深蓝 + 亮黄，字号 ×1.5） |

- **旧值迁移**：`light`/`military` → `default`；`dark` → `dark-bigscreen`；`high-contrast` → `outdoor`；非法值回落 `default`。
- **切换约定**：只在 `stores/config.ts` 的 `theme` 状态与 `applyThemeToDom()` 中切换；
  `'default'` 表示移除 data-theme；页面/组件禁止直接写 `#1b4332`、`#d4af37` 这类主题色值。
- **入口**：顶栏主题切换器 + 外观设置面板（头像下拉「外观设置」）；大屏页强制深色大屏。

## 4. 显示偏好四档（v1.15.0）

存储：localStorage **`ui:prefs`**；DOM：`<html>` 上 4 个属性；唯一读写入口 `composables/useUiPrefs.ts`。

| 属性 | 取值 | 默认 | 语义 |
|---|---|---|---|
| `data-font-size` | `compact` / `standard` / `large` | standard | 全站字号缩放：`--font-scale` 0.92 / 1 / 1.12 |
| `data-density` | `comfortable` / `compact` | comfortable | 表格行高 44 / 34px，控件高度与内边距同步收紧 |
| `data-contrast` | `normal` / `high` | normal | 高对比：文字/边框加深、卡片去阴影、弱化色实色化 |
| `data-simplify` | `false` / `true` | false | 简化模式：隐藏 `.stat-trend` / `.list-hint` / `.advanced-only` |

- 损坏 JSON / 非法值逐字段回退默认，localStorage 不可用静默降级为内存态；
- 应用启动时 `main.ts` 调用 `initUiPrefs()` 恢复偏好（防闪烁）；
- 面板：`components/settings/AppearanceSettings.vue`（字号/密度/高对比/简化 + 主题 + 恢复默认），即时生效并持久化。

## 5. 布局与导航

### 5.1 默认布局

文件：`frontend/src/layouts/DefaultLayoutSafe.vue`

- 顶部栏高度：`--layout-header-height`；侧边栏宽度：展开 240px / 收起 68px。
- 侧边栏使用 `--sidebar-bg` 深绿渐变；当前板块标题左侧 3px 金色竖条。
- 移动端侧边栏：抽屉式（`mobile-open`）+ 遮罩（点击遮罩关闭）。
- 顶栏面包屑：**板块 › 页面**（首页图标 + 板块名 + 当前页名）。

### 5.2 导航结构（后端单一菜单源 + v2.0 交互）

- **数据来源**：后端 `app/api/v1/menus.py` 的 `MENU_DEFINITIONS` v2（`sections` + `flat_keys`），
  前端 `stores/menu.ts` 消费；**禁止前端手写菜单段或维护菜单配置副本**。
- **7 个板块**：工作台（固定首位）+ 帮扶业务 / 乡村振兴 / 工作协同 / 分析汇报 / 数据管理 / 系统管理。
- **板块折叠**：标题 18px 加粗、默认折叠；展开集合持久化到 `nav:expanded-sections`。
- **收起态悬停浮层**：侧栏收起时 hover/键盘聚焦板块标题浮出 `.section-flyout` 显示子项。
- **三种条目**：`page` / `group` / `console`（系统管理 6 聚合页，页内 Tab）。
- **导航增强**：`Ctrl+K` 命令面板/菜单搜索、收藏/最近访问（`nav:favorites`/`nav:recent`，上限 8）。

## 6. 全局组件类与通用组件

**全局类**（新页面直接套用，旧页面不强制）：`.app-card`（`--flat`/`--compact`）、`.app-stat-card`、
`.app-empty` / `.app-loading` / `.app-error`、`.app-table-toolbar`、`.num-highlight` / `.num-cell`、
`.stat-trend` / `.list-hint` / `.advanced-only`。

**通用组件**（`frontend/src/components/common/`，可选增强）：`AppPageHeader`、`AppStatCard`、`AppEmpty`、
`AppLoading`、`AppError`、`AppTableToolbar`（+ `index.ts` 统一导出）。

> 约定：全局 class 为准，组件为可选增强；新页面优先使用，避免重复造卡片/三件套样式。

## 7. 组件使用规范（Element Plus）

- **按钮**：主按钮每页最多 1 个；次操作 default；危险操作 `type="danger"` + 二次确认；圆角 6px。
- **表单**：移动端尽量单列；输入控件宽度 100%；label 右对齐 13px；必填星号危险色。
- **表格**：浅主色表头 + 金色底线、去斑马纹、hover 主色浅底、数字列等宽；移动端卡片化或横向滚动。
- **对话框**：三档宽度 `.dialog-sm/md/lg`（**480/720/960px**，窄屏 92vw）；header 18px/600。
- **反馈**：成功/失败/警告统一语义色；错误态必须带重试；禁止静默 catch。
- **状态三件套**：loading（`.app-loading`/骨架屏）、empty（`.app-empty`/el-empty）、error（`.app-error`+重试）。

## 8. 代码约束（强制）

1. 新增样式放在 `styles/` 体系（Token/组件/布局），禁止散落页面；优先复用全局类/通用组件。
2. 颜色只能用 `var(--xxx)`/`$xxx`：**改动文件零新增硬编码色**；`check_hardcoded_styles.py` 棘轮只降不升
   （基线 345 → 当前 305（57 个文件），目标 ≤200，后续计划）。
3. 显示偏好只经 `useUiPrefs` 读写 `ui:prefs` 与 `<html data-*>`，禁止组件自行写 data 属性。
4. `tokens-vars.scss` 只放变量（禁止 `:root`/选择器等实体规则）。
5. 视觉回归：改 UI 跑 `tests/unit/ui/ui-tokens.test.ts` + `npx playwright test tests/e2e/visual`；
   结构调整才用 `UPDATE_VISUAL_BASELINE=1` 更新基线。
6. 禁止在业务组件内引入大型 UI 依赖或全量图标注册（入口 `main.ts` 已按需注册图标）。
