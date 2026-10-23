# UI 设计方案

> **版本**: v2.1 | **日期**: 2026-10-24（v1.0 基线 2026-08-04；2026-10-24 v1.17.1 导航改版 + v1.17.1 功能页面；**2026-10-24 v1.17.1 UI v2.0 重构**：主题 3 套、显示偏好 4 档、Token 升级、全局组件类/通用组件、侧栏金色竖条与折叠浮层、工作台 KPI、大屏三层结构与距离字号、视觉回归门禁；**2026-10-24 v1.17.1 界面精细化方案 C**：品牌区/工作台板块级/全站表格规范/筛选栏 4 档/PageHeader 统一/ui-refine 响应式层） | **范围**: frontend/（Vue 3 + Element Plus）
> 本文档是帮扶管理信息系统的 UI 设计总纲：设计定位、视觉基础、主题/显示偏好、组件/页面规范、状态与无障碍规范、实施路线图。
> 配套代码事实源：`frontend/src/styles/tokens.scss`（设计 Token 唯一数据源）、`styles/components/*.scss`（全局模板样式）。

---

## 目录

- [1. 设计定位与原则](#1-设计定位与原则)
- [2. 视觉基础](#2-视觉基础)
- [3. 主题策略](#3-主题策略)
- [4. 组件规范](#4-组件规范)
- [5. 页面规范](#5-页面规范)
- [6. 状态与反馈规范](#6-状态与反馈规范)
- [7. 无障碍规范](#7-无障碍规范)
- [8. 实施路线图](#8-实施路线图)
- [附录 A：样式文件地图](#附录-a样式文件地图)
- [附录 B：开发纪律](#附录-b开发纪律)

---

## 1. 设计定位与原则

### 1.1 产品定位

| 维度 | 描述 |
|------|------|
| 产品形态 | 完全离线的单机版桌面应用（Electron 壳 + Vue 前端 + FastAPI 本地后端），支持多机协同数据同步 |
| 目标用户 | 部队帮扶干部、乡村振兴驻村干部、机关业务管理员（4 类角色：super_admin / admin / user / viewer） |
| 使用场景 | 机关办公室日常录入（高频表单）、驻村现场移动环境（户外强光）、会议室汇报（大屏轮播） |
| 部署环境 | Windows 10/11 x64、麒麟 V10 ARM64（国产化）；内网离线环境 |

### 1.2 设计原则

| 原则 | 含义 | 落地点 |
|------|------|--------|
| **庄重可信** | 军风政务气质：军绿为主、金色仅三用（选中竖条 / 数据高亮 / 表头底线），金色面积 ≤5% | 色彩体系 §2.1；侧栏 §4.1；表格 §4.3 |
| **高效录入** | 表单是核心工作流（帮扶村 10 板块年度数据），减少视觉噪音、统一栅格 | 表单页规范 §5.2；form-page.scss |
| **低负担阅读** | 正文行高 1.6、字号阶梯可整体缩放、表格去斑马纹、简化模式隐藏次要信息 | 字号/密度/简化 §3.3；表格 §4.3 |
| **离线可用** | 无网络依赖：字体用系统字体栈、地图用离线瓦片、图标用 Element Plus 内置集 | tokens.scss 字体 Token；Leaflet 离线瓦片 |
| **失败可见** | 任何请求失败必须被用户看见并可重试，禁止静默 catch | 状态三件套 §6（`.app-error` 等全局类） |
| **人人可用** | 键盘可达、对比度达标、高对比/户外档、可整体放大字号 | 无障碍规范 §7；显示偏好 §3.3 |
| **单一数据源** | 颜色/字号/间距/阴影只用 Token 变量（`var(--xxx)`），禁止硬编码；全局样式集中在 `styles/components/*.scss` | tokens.scss；附录 A/B |

---

## 2. 视觉基础

### 2.0 UI v2.0 Token 升级总览（v1.15.0）

> 全部落地在 `frontend/src/styles/tokens.scss`；旧 Token 名保留兼容，新增/升级项如下。

| 类别 | v2.0 升级 |
|---|---|
| 主色阶 | 新增 `--color-primary-50/100/500/600/700/900`（`#f2f8f4` / `#dfeee5` / `#2d6a4f` / `#235a42` / `#1b4332` / `#0f2e22`），旧 `light-1~9` / `dark-1~2` 保留兼容 |
| 页面/卡片 | `--color-bg-page: #f5f7f5`（提亮）、`--color-bg-card: #ffffff`、`--color-card-border: #e5e9e6` |
| 阴影 2 档 | `--shadow-card`（轻卡片阴影）、`--shadow-pop`（弹层/浮层） |
| 圆角 3 档 | `--radius-card: 8px`、`--radius-control: 6px`、`--radius-pill: 999px` |
| 字号缩放 | 8 档字号全部 `calc(… * var(--font-scale))`，由显示偏好档位控制（compact ×0.92 / standard ×1 / large ×1.12；outdoor 主题 ×1.5）；`--text-*` 为兼容别名 |
| 行高 | 正文 `--line-height-normal: 1.6`，标题 1.25 |
| 数字 | `table / .kpi-value / .stat-value / .num-cell { font-variant-numeric: tabular-nums }` |
| 侧栏 | `--sidebar-bg` 深绿渐变（`#123f2e → #0f2e22`）+ 当前板块金色竖条 3px |
| 表格密度 | `--table-row-height`（舒适 44px / 紧凑 34px，见 §3.3） |
| 大屏 | `--bs-title-size / --bs-kpi-size / --bs-label-size / --bs-chart-title-size` 三档（3m/6m/10m，见 §5.5） |

### 2.1 色彩体系

**主色调：军绿色阶（12 档）** — 定义于 `tokens.scss :root`

| Token | 色值 | 用途 |
|-------|------|------|
| `--color-primary` | `#2d6a4f` | 主操作按钮、链接、激活态 |
| `--color-primary-light-1` ~ `light-9` | `#40916c` → `#f7fdf9` | 悬停、浅底、标签底、hover 背景 |
| `--color-primary-dark-1` / `dark-2` | `#1b4332` / `#081c15` | 卡片头、表格头、侧边栏深底 |

**点缀色：金色**

| Token | 色值 | 用途 |
|-------|------|------|
| `--color-accent-gold` | `#d4af37` | 表格头下边线、卡片头下边线、徽章、高亮强调 |
| `--color-accent-gold-light` | `#e8d48b` | 金色悬停态 |

> 金色只作"点睛"（边线、徽章、少量强调），禁止大面积铺金。

**语义色（四组，各含 light/lighter/lightest/dark 档）**

| 语义 | 基准 Token | 色值 | 使用场景 |
|------|-----------|------|---------|
| 成功 | `--color-success` | `#2ecc71` | 成功提示、已完成/已拨付等正向状态 |
| 警告 | `--color-warning` | `#f39c12` | 预警（预算预警、审批超时）、进行中状态 |
| 危险 | `--color-danger` | `#e63946` | 错误提示、删除操作、异常监控 |
| 信息 | `--color-info` | `#5a7d6a` | 中性提示、辅助信息 |

**文字色阶**

| Token | 色值 | 用途 |
|-------|------|------|
| `--color-text-primary` | `#1e293b` | 标题、正文主体 |
| `--color-text-regular` | `#475569` | 常规正文 |
| `--color-text-secondary` | `#64748b` | 次要说明、标签名 |
| `--color-text-placeholder` | `#94a3b8` | 占位符 |
| `--color-text-disabled` | `#c0c4cc` | 禁用态 |

**背景与边框**

| Token | 色值 | 用途 |
|-------|------|------|
| `--color-bg-page` | `#f0f4f0` | 页面底色（微绿灰） |
| `--color-bg-card` | `#ffffff` | 卡片、对话框 |
| `--color-bg-hover` / `--color-bg-active` | `#f0f4f0` / `#e8f8ec` | 悬停 / 激活 |
| `--color-border` → `--color-border-extra-light` | `#cbd5e1` → `#f8fafc` | 边框四档，由重到轻 |

### 2.1 界面精细化方案 C（v1.15.15）

> 目标：把 v1.15.0 建立的设计系统落到"每一页长得一样"的层面。实现契约见
> `docs/design/{tokens,pages,components}.md` 与 `frontend/src/styles/components/ui-refine.scss`。

| 维度 | 规范 | 落地 |
|---|---|---|
| **侧栏品牌区** | 系统标识名 20px / 800 单行（logo 36px、侧栏头 64px） | `layouts/` + 侧栏样式；工作台入口 18px/700 + Home 图标，与 7 板块标题同构 |
| **表格** | 全站 `el-table` 启用 border；序号列 72px（25/25）、选择列 48px（10/10）、操作列 `fixed=right`（67/67） | 列宽可拖拽；长表格横向滚动操作列常驻 |
| **筛选栏** | 4 档宽度：input 220 / select 160 / date 240 / number 120；统一 16px 间距；搜索按钮带图标 | 清理 114 处行内宽度；`ui-refine.scss` 统一约束 |
| **页面头部** | 共享 `components/common/PageHeader.vue`：标题 + 副标题 + 主操作；T1 列表/T2 详情两套模板 | 19 个列表页接入（全站 31 页），取代 30+ 种手写标题区 |
| **栅格与响应式** | 8px 栅格；断点 1200 / 992 / 768 | 筛选栏自动换行、页面栅格自适应 |
| **质量门禁** | 硬编码色棘轮 305/305 零新增；lint:check + vue-tsc 0 错误 | 改动文件零新增硬编码 |

### 2.2 硬编码色治理（基线棘轮，v1.15.0）

- 现状：`scripts/check_hardcoded_styles.py` 扫描 `.vue/.scss` 的硬编码色值；**基线 345 处 → 当前 154 处（57 个文件）**
  （v1.15.15 实测 305 处 / 57 个文件，`hardcoded_styles_baseline.json` 已更新），目标收敛到 **≤200 处**（后续计划）。
- 规则：新增/改动文件**不允许新增**硬编码色（只能用 `var(--token)`）；存量只降不升；
  基线更新必须由门禁脚本 `--update-baseline` 生成并在 CI 中只紧不松。
- 历史「语义蓝映射建议」表已完成治理，不再保留待决策项；新增语义色优先复用
  `--color-success/warning/danger/info`，图表系列色见 §4.6。

### 2.3 字体

- **字体族**：系统字体栈（`--font-family-base`），中文回退 Microsoft YaHei；等宽 `--font-family-mono`。离线环境不引入 Web Font。
- **字号 8 档（UI v2.0 全部 calc 化）**：xs 12 / sm 13 / md 14（基准）/ lg 16 / xl 18 / xxl 20 / xxxl 24 / display 32，
  均乘以 `var(--font-scale)`（默认 1）；显示偏好档位 ×0.92 / ×1 / ×1.12 见 §3.3。
- **字重**：正文 400，强调 500，标题 600，大标题 700。
- **行高**：正文 **1.6**（`--line-height-normal`），标题 1.25（`--line-height-tight`）。
- **数字**：表格/KPI/统计数字统一 `tabular-nums`，保证列对齐与读数稳定。

### 2.4 间距（4px 基准网格）

`--spacing-xs` 4 / `sm` 8 / `md` 16 / `lg` 24 / `xl` 32 / `xxl` 48 / `xxxl` 64。
**规则**：组件内部间距用 xs/sm；卡片内边距 md~lg；页面区块间距 lg~xl。禁止使用非 4 倍数像素。

### 2.5 圆角 / 阴影 / 层级

| 类别 | Token | 使用约定 |
|------|-------|---------|
| 圆角（v2.0） | `--radius-card` 8 / `--radius-control` 6 / `--radius-pill` 999；旧 `--radius-sm/md/lg/xl/xxl/round` 保留兼容 | 卡片/对话框 8；按钮/输入框 6；标签/胶囊 999 |
| 阴影（v2.0，2 档） | `--shadow-card`（近距轻阴影 + 大范围淡阴影）/ `--shadow-pop`（弹层/浮层/抽屉） | 白底卡片用 card；弹层/浮层/对话框/抽屉用 pop；**禁止自定义阴影值** |
| z-index | dropdown 1000 → loading 1090（10 档） | 侧栏收起态浮层用 3000（不遮挡 Element popper）；禁止随手写 999/9999 |

---

## 3. 主题与显示偏好（UI v2.0）

### 3.1 三套主题（5 → 3）

`tokens.scss` 只保留以下 3 套主题；旧的 light/dark/military/high-contrast 由 `normalizeTheme()` 迁移映射，历史用户不失效。

| 主题 | 选择器 | 定位 | 启用状态 |
|------|--------|------|---------|
| **军绿（默认）** | `:root`（**无 data-theme 属性**） | 日常办公默认主题，庄重政务风 | ✅ 默认渲染 |
| **深色大屏** | `[data-theme="dark-bigscreen"]` | 会议室大屏专用（深色底 + 大字号），仅大屏页强制启用 | ✅ 大屏页 |
| **户外高对比** | `[data-theme="outdoor"]` | 现场强光/低视力：高对比深蓝 + 亮黄，字号 ×1.5 | ✅ 可选 |

**旧值迁移映射**：`light` → `default`；`military` → `default`；`dark` → `dark-bigscreen`；`high-contrast` → `outdoor`；
非法值/空值一律回落 `default`（白名单校验，避免写坏 data-theme 导致全站 token 失效）。

### 3.2 切换机制

- **状态源**：`stores/config.ts` 的 `theme`（唯一数据源，`THEME_OPTIONS` 仅 3 项）。
- **DOM 接线**：`setTheme(t)` 同时写 localStorage 与 `document.documentElement.dataset.theme`；
  `'default'` 表示**移除** data-theme 属性（渲染 :root 军绿）。`applyThemeToDom()` 为共享工具函数。
- **启动应用**：`main.ts` 在 createApp 之前读取 localStorage 并应用到 DOM（防主题闪烁 FOUC）。
- **切换入口（双通道）**：
  - 顶栏主题切换器（全体用户，3 套）；
  - **外观设置面板**（`components/settings/AppearanceSettings.vue`）：头像下拉 →「外观设置」，
    含主题 + 字号/密度/高对比/简化 + 「恢复默认外观」。
- **大屏**：`/bigscreen` 强制 `dark-bigscreen`，离开大屏恢复用户主题。
- **无障碍**：`styles/accessibility.css` 保留焦点环、skip-link、`prefers-reduced-motion`；
  outdoor 主题通过 `--font-scale: 1.5` 放大字号（与字号档位不冲突，显示偏好档位在其上叠加语义）。

### 3.3 显示偏好四档（localStorage `ui:prefs`）

| 属性（`<html data-*>`） | 取值 | 默认 | 语义 |
|---|---|---|---|
| `data-font-size` | `compact` / `standard` / `large` | standard | 全站字号缩放：`--font-scale` = 0.92 / 1 / 1.12 |
| `data-density` | `comfortable` / `compact` | comfortable | 表格/列表行高与内边距：表格行高 44px / 34px，控件高度与单元格 padding 同步收紧 |
| `data-contrast` | `normal` / `high` | normal | 高对比：文字/边框加深、卡片去阴影、弱化色替换为实色 |
| `data-simplify` | `false` / `true` | false | 简化模式：隐藏 `.stat-trend` / `.list-hint` / `.advanced-only`，保留主操作 |

**实现契约**：

- `composables/useUiPrefs.ts` 为**唯一读写入口**：`normalizeUiPrefs` 白名单归一化、
  `readUiPrefs/writeUiPrefs`、`applyUiPrefsToDom`、`initUiPrefs`（`main.ts` 启动时调用一次）；
  `standard/comfortable/normal/false` 也会显式写入 data-* 属性（可断言、避免"删属性"歧义）。
- **容错**：损坏 JSON / 非法值逐字段回退默认；localStorage 不可用（隐私模式/配额）静默降级为内存态，绝不抛错。
- **样式落点**：`tokens.scss` 的 `[data-*]` 覆盖块 + `styles/components/ui-v2.scss` 密度覆盖；
  高对比下卡片边框改用 `--color-bord-dark` 语义并关闭卡片阴影。
- **入口**：头像下拉「外观设置」/ 系统设置；所有改动**即时生效**并持久化。

---

## 4. 组件规范

### 4.1 布局骨架

| 区域 | 规格 |
|------|------|
| 侧边栏 | 展开 240px / 收起 68px；`--sidebar-bg` 深绿渐变；当前板块金色竖条 3px；<768px 自动收起 |
| 顶栏 | 高 60px（`--layout-header-height`）；左：折叠按钮+面包屑（板块 › 页面）；右：菜单搜索（Ctrl+K）+主题切换器+用户下拉 |
| 内容区 | 最大宽 1400px（`--layout-content-max-width`），内边距 24px |
| 页脚 | 高 28px，版本号 |

**侧边栏导航结构（v1.14.0，完全数据驱动 + 板块折叠）**：

```
侧边栏
├── 工作台（固定第一，/dashboard）
├── 收藏（有数据时显示，最多 8 个）
├── 最近访问（有数据时显示，最多 8 个）
└── v-for sections（后端 /menus/accessible v2 下发，按 order 升序）
    ├── 板块标题（18px 加粗，默认折叠；点击展开/收起，状态存 nav:expanded-sections）
    ├── page 条目 → 普通菜单项
    ├── group 条目 → 可折叠子菜单（如 经费管理 / 审批管理 / 数据分析 / 数据上报）
    └── console 条目 → 聚合页入口（系统管理 6 个）
```

- 前端**不得再手写菜单段**；`dashboard` 固定渲染，其余全部来自后端 `MENU_DEFINITIONS` v2。
- **7 板块标题 18px 加粗、默认折叠**；展开集合存 localStorage `nav:expanded-sections`（默认空 = 全部折叠），
  折叠只影响板块级，group/console 子项按原逻辑渲染。
- **当前板块金色竖条（v1.15.0）**：当前页面所属板块标题左侧显示 3px 金色竖条（`--color-accent-gold`，
  高 22px、圆角 2px），标题文字同步金色；金色仅此三用之一（另两处：`.num-highlight`、表头底线）。
- **收起态悬停浮层（v1.15.0）**：侧栏收起（68px）时，hover / 键盘聚焦板块标题浮出 `.section-flyout`
  （fixed 定位、深绿底、金色标题、子项 hover 金色），点击子项直接跳转；离开/失焦关闭。
- **面包屑**：顶栏显示「板块 › 页面」（首页图标 + 板块名 + 当前页名），板块名由菜单 section 推导。
- **菜单搜索 / 命令面板**：顶栏搜索按钮或 `Ctrl+K` 打开 `MenuSearchDialog`（见 §4.7）。
- 移动端（<768px）：底部导航数据驱动（工作台 + sections 前 3 个入口 + "更多"），抽屉式侧栏保留。

### 4.2 卡片与对话框（UI v2.0 全局类）

- **通用卡片 `.app-card`**：白底 + `--color-card-border` 边框 + `--shadow-card` 轻阴影 + `--radius-card` 8px；
  变体 `.app-card--flat`（无阴影）/ `.app-card--compact`（紧凑内边距）；子类 `.app-card__header` / `.app-card__title`。
- **统计卡 `.app-stat-card`**：图标 + 标签 13px 次要色 + 数值 28px/700 `tabular-nums`；变体
  `--primary/success/warning/danger`；趋势 `.stat-trend`（`is-up` 成功色 / `is-down` 危险色，简化模式下隐藏）。
- **数据高亮 `.num-highlight`**：金色仅用于关键数字高亮（另一用途见侧栏竖条/表头底线）。
- **`.num-cell` / `.num-cell--muted`**：表格数字列等宽右对齐。
- **对话框**：三档宽度 `.dialog-sm/md/lg`（**480 / 720 / 960px**，窄屏 92vw）；圆角 `--radius-card`、
  阴影 `--shadow-pop`；header 18px/600 + 细分隔线；footer 右对齐。
- **品牌元素保留**：表单/详情卡片头仍为军绿深底 + 白字 + 金色下边线（form-page.scss），与 v2 轻卡片并存。

### 4.3 表格（UI v2.0）

- **表头**：`--color-primary-50` 浅主色底 + 13px/600 深色文字 + **金色下边线 2px**（`ui-v2.scss` 全局覆盖）。
- **去斑马纹**：`.el-table--striped` 行背景统一透明，以 hover 高亮替代（`--color-primary-50`）。
- **数字列**：`font-variant-numeric: tabular-nums`，金额/数量/排名等宽对齐。
- **行高**：`--table-row-height`（舒适 44px / 紧凑 34px，由 `data-density` 控制）；紧凑档单元格 padding 5px 8px。
- **操作列**：次要操作弱化为文字按钮（`.is-link`），表格行内按钮用小尺寸。
- **分页**：右对齐；空数据：`#empty` 插槽或 `.app-empty`。
- 移动端（<768px）：列表退化为卡片式（`.mobile-card`，index.scss 已提供）。

### 4.4 表单

- 容器：`.form-card`（白底、圆角 10px、最大宽 900px）。
- **栅格标准**：一律使用 `el-row`/`el-col`（`:xs="24" :sm="12"` 双列、单列 `:span="24"`），**禁止内联 style 做宽度/间距**；控件撑满由 form-page.scss 全局规则保证（`.form-card` 内 input-number/select/date-picker/cascader 默认 width:100%）。
- 标签：右对齐（`label-position="right"`，移动端自动转 top）；必填红星靠 Element 默认。
- 错误态：输入框红色描边 + 12px 错误文案（form-page.scss 已覆盖）。
- 提交区：`.form-actions` 右对齐，顶部浅分隔线。

### 4.5 按钮

- 主操作：`type="primary"`（军绿），一页最多 1 个；次操作 default；危险操作 `type="danger"` 且需二次确认（ElMessageBox.confirm）。
- 尺寸：默认 default（32px）；表格行内 small；户外模式随 Token 自动放大。

### 4.6 ECharts 色板

```
系列色推荐序列（军绿→金色渐进）：
#2d6a4f, #40916c, #52b788, #74c69d, #d4af37, #95d5b2, #1b4332
```

- 状态类图表优先用语义色（success/warning/danger）。
- 图表必须随容器 resize（useECharts composable 已处理）；组件卸载前 dispose。

### 4.7 导航、命令面板与菜单搜索（v1.15.0）

| 交互 | 规范 |
|------|------|
| **命令面板 / 菜单搜索** | 任意页面 `Ctrl+K` 或顶栏搜索按钮打开 `MenuSearchDialog`；搜索 `label` / `key` / `path`（大小写不敏感子串）；`↑`/`↓` 移动、`Enter` 跳转、`Esc` 关闭；空搜索显示"收藏 + 最近访问" |
| **最近访问** | localStorage `nav:recent`，最多 8 条，按访问时间倒序、按 key 去重；损坏数据回退空数组 |
| **收藏** | localStorage `nav:favorites`，最多 8 条；侧栏顶部"收藏"区与搜索弹窗共享同一份数据 |
| **菜单权限** | `canAccessMenu(key)` 语义不变，额外支持 console 的 `tabs[].key`；无权限的 Tab 不渲染 |
| **侧栏交互** | 当前板块金色竖条、收起态 hover/聚焦浮层、板块折叠（`nav:expanded-sections`）、面包屑「板块 › 页面」 |
| **可访问性** | 搜索弹窗支持键盘全流程操作；侧栏可点击项保持 `role`/焦点可见；菜单激活态用金色文字 + 金色竖条 |

> 实现位置：`frontend/src/components/nav/MenuSearchDialog.vue`、`composables/useRecentMenus.ts`、
> `composables/useMenuFavorites.ts`；数据源为 `stores/menu.ts`（后端单一菜单源 v2）；
> 外观相关入口在 `components/settings/AppearanceSettings.vue`（头像下拉「外观设置」）。

### 4.8 全局组件类与通用组件（v1.15.0）

**全局样式类**（`styles/components/card.scss` / `states.scss` / `dialog.scss` / `ui-v2.scss`，新页面直接套用）：

| 类 | 用途 |
|---|---|
| `.app-card` / `.app-card--flat` / `.app-card--compact` | 通用卡片（白底/8px/边框/轻阴影） |
| `.app-stat-card`（`__icon/__label/__value/__unit`） | 统计卡（数字 28/700 tabular-nums、趋势箭头） |
| `.stat-trend`（`is-up/is-down`） | 趋势箭头；简化模式隐藏 |
| `.num-highlight` / `.num-cell` | 金色数据高亮 / 等宽数字列 |
| `.app-empty` / `.app-loading` / `.app-error` | 状态三件套统一外观（图标/文案/操作） |
| `.app-table-toolbar` | 表格工具条（标题 + 右侧操作区） |
| `.list-hint` / `.advanced-only` | 辅助说明 / 高级字段；简化模式隐藏 |

**通用组件**（`frontend/src/components/common/`，Element Plus 之上的轻封装，按需接入）：

| 组件 | 关键 Props |
|---|---|
| `AppPageHeader` | `title`（必填）、`subtitle` |
| `AppStatCard` | `label`、`value`、`unit?`、`trend?: 'up'|'down'|null`、`tone?: primary/success/warning/danger` |
| `AppEmpty` | `text?`（默认"暂无数据"）、`description?` |
| `AppLoading` | `rows?`（骨架屏行数，默认 3） |
| `AppError` | `message?`（默认"加载失败，请稍后重试"）+ 重试事件 |
| `AppTableToolbar` | `title?` + 右侧操作插槽 |

> 约定：**全局 class 为准，组件为可选增强**；旧页面不强制改造，新页面优先使用上述类/组件。
> 视觉回归基线 `tests/unit/ui/ui-tokens.test.ts` 会校验上述类与 token 存在性。

---

## 5. 页面规范

### 5.1 列表页（list-page.scss）

结构：页头（标题+操作按钮）→ 筛选区（el-form inline，可折叠）→ 统计卡（可选，中性卡+语义色数值）→ 表格 → 分页。
要求：筛选与操作区 `flex-wrap`；操作列保留宽度避免挤压；批量工具栏用军绿系（禁用蓝色）。

### 5.2 表单页（form-page.scss）

结构：`.form-card` 分区块（el-divider 或区块标题分隔）→ 每区块 el-row/el-col 栅格 → 底部 `.form-actions`。
大表单（帮扶村 10 板块）按板块分步/分区，区块标题带序号；年度数据录入统一 `el-input-number :min="0"`。

### 5.3 详情页

`.detail-card` + `.detail-header`（标题+状态标签+操作）；信息展示用 `.info-grid`（auto-fit 250px 网格）或 el-descriptions。

### 5.4 工作台（dashboard，v1.15.0）

- **KPI 统计卡**：使用 `.app-stat-card`（数值 28/700 tabular-nums、标签 13 次要色、趋势箭头 `.stat-trend`）；
  KPI 区自动刷新（60s）+ 手动刷新按钮；可点卡必须 `role="button" tabindex="0"` + 键盘事件。
- **待办清单**：独立卡片区，按优先级/到期排序，可一键跳转；空态用 `.app-empty`，加载用 `.app-loading`。
- **图表层级**：主图表（趋势/结构）在前，辅助信息（说明/趋势箭头）用 `.list-hint`/`.stat-trend`（简化模式下隐藏）。
- 快捷操作与信息区保持可配置显隐（布局编辑器），禁止假数据可视化（如平线 sparkline 冒充趋势）。

### 5.5 大屏（bigscreen，v1.15.0 三层结构）

- **三层结构**：① 标题时间条（标题 + 当前时间 + 距离档位 + 轮播/暂停 + 退出大屏）；
  ② KPI 大数字区（`.kpi-value` 使用 `--bs-kpi-size`）；③ 2–3 列图表区。
- **距离字号分档**：`<html data-bigscreen-distance="3m|6m|10m">`（默认 **6m**），
  对应 `--bs-title-size` / `--bs-kpi-size` / `--bs-label-size` / `--bs-chart-title-size` 三档（3m 22/32/12/15、
  6m 28/40/14/18、10m 36/56/18/24）；仅影响大屏页，不影响其他页面。
- **自动轮播**：默认关闭；开启后每 **15s** 在「KPI 组 ↔ 图表组」数据视角间切换，当前视角高亮；
  支持「暂停/继续」「关闭轮播」，组件卸载/关闭时清理定时器（不残留）。
- **主题**：大屏强制 `dark-bigscreen`；**退出大屏**：先退出全屏再返回工作台（`pushSafe('/dashboard')`）。
- 汇报模式：KPI/经费趋势/成效排名/项目状态等卡片可显隐与排序；汇报脱敏开关保留。

### 5.6 系统管理聚合页（SystemConsole，v1.13.0）

- 路由 `/system/console/:group`（group ∈ `org` / `security` / `ops` / `storage` / `settings` / `about`），
  由 `views/system/console/SystemConsole.vue` 承载；标题/面包屑取后端 console 节点 `label`。
- 页内用 `el-tabs` 切换，Tab 来自后端 console 节点的 `tabs[]`（**仅渲染有权限的 Tab**）；
  当前 Tab 用 query `?tab=<tab.key>` 表达，切换用 `router.replace`（不产生历史堆栈）。
- **只有当前 Tab 的页面组件会被异步加载**；Tab 内容复用原页面组件（旧页面、旧路由全部保留，深链不失效）。
- 无权限 / 未知 group / 无可渲染 Tab：显示空态与"返回工作台"引导，不白屏。
- **v1.14.0**：系统管理 Tab 数量精简——「系统设置」聚合页仅保留「更新日志」（多语言/邮件设置下线）；
  「数据管理」独立「校验规则」入口并入「数据校验」页内 Tab。

### 5.7 一户一档（households，v1.14.0）

- 列表页：筛选区（帮扶村下拉 / 风险等级 / 户类型 / 关键词）+ 统计/预警入口 + 表格（户主、村、类型、风险等级、
  帮扶责任人、成员数、最近走访、预警标记）+ 新建/编辑抽屉 + 导出（xlsx/csv）+「一键汇总回填年度人口」按钮。
- 详情页：档案头（户主/村/类型/风险等级/帮扶责任人）+ 监测指标卡（年收入/务工人数/大病/住房安全）+
  成员表格（增删改）+ 风险记录时间线（登记/关闭）+ 预警提示 + 走访记录（挂户）。
- 风险等级用语义色标签（low=success / medium=warning / high=danger），禁止硬编码色值。
- **v1.15.15 入口迁移**：不再占用侧栏一级菜单，入口改为帮扶村「年度数据管理」页首张卡片
  （卡片内「进入一户一档」→ `/households?village_id=<村ID>`，列表挂载时按该村预筛选）；
  列表/详情页面与路由保持不变，菜单 key `households` 转 legacy 以兼容旧权限配置。

### 5.8 影像库（media，v1.14.0）

- 左侧筛选（村/学校/项目/标签/日期区间），右侧卡片网格（缩略图 + 拍摄时间 + 归档对象 + 标签）。
- 上传流程：先走通用文件上传，再登记归档；成功后显示 EXIF 解析结果（拍摄时间/GPS/来源 exif|manual）。
- 多选同拍摄点照片 →「生成对比图」弹窗展示后端合成 PNG（左右/2xN + 日期标注）并可下载。

### 5.9 消费帮扶台账（consumption，v1.14.0）

- 统计卡（年度总额/笔数/品类分布/村分布）+ 筛选（年度/品类/村/关键词）+ 表格 + 新建/编辑/删除 + 导出。
- 需在页面上明确区分「台账」与帮扶村年度数据第 8 板块「消费帮扶」的口径提示。

### 5.10 数据校验（合并页，v1.14.0）

- 单页三 Tab（`?tab=verify|rules|fields`）：① 校验执行（模块+条件→结果问题列表，可定位/导出）；
  ② 规则管理（原独立页逻辑内嵌）；③ 字段说明（只读字段中文映射表）。
- 旧 `/data-verify/rules` 重定向到 `?tab=rules`；独立「校验规则」菜单入口下线。

### 5.11 报表模板组合导出（reportTemplates，v1.14.0）

- 字段勾选组合（按模块 available-fields）→ 保存模板 → 选择导出格式（xlsx/csv/docx/pdf）→ 导出/预览打印。
- 打印用浏览器 `window.print` + 打印样式；单次导出上限 5000 行。

### 5.12 通用页面模板（v1.15.0）

新页面按以下骨架搭建（与全局类/通用组件对齐）：

```
AppPageHeader（标题/副标题）或 .page-header
└─ .app-card（筛选区）→ .filter-card + .app-table-toolbar
└─ .app-stat-card 统计行（可选）
└─ .app-card（表格区）→ 表格/列表 + 分页
   ├─ loading：.app-loading / el-skeleton
   ├─ empty：.app-empty（或 el-empty）
   └─ error：.app-error（重试按钮，禁止静默 catch）
```

- 间距节奏：页头/内容区 24；卡片内 20；表单行 12；表格行 44（紧凑 34）。
- 状态三件套必须齐备；错误态必须带重试；数字列等宽。
- 视觉回归基线覆盖 10 个关键页面（工作台/帮扶村/项目/经费/一户一档/影像库/消费帮扶/系统管理/数据校验/大屏）。

---

## 6. 状态与反馈规范

**三件套（每个异步视图必须齐备；UI v2.0 统一为全局类，旧页面不强制改造）**：

| 状态 | 规范 |
|------|------|
| loading | `.app-loading`（骨架屏/闪烁行，`rows` 可配）或 `el-skeleton`/`v-loading`（表格） |
| empty | `.app-empty`（图标 + 文案，默认"暂无数据"）或 `<el-empty description="暂无数据" />`；表格用 `#empty` 插槽 |
| error | `.app-error`（错误图标 + 说明 + **重试按钮**）+ `ElMessage.error`；**禁止静默 catch** |

**消息反馈**：ElMessage 全局默认 showClose + 5s（main.ts 已配置）；居中弹出（DOM 级 CSS 注入）。

**简化模式**：`[data-simplify="true"]` 隐藏 `.stat-trend`/`.list-hint`/`.advanced-only`，但 loading/empty/error 三件套**不隐藏**。

---

## 7. 无障碍规范（WCAG 2.1 AA）

| 条目 | 要求 |
|------|------|
| 键盘可达 | 可点击 div 必须 `role="button" tabindex="0"` + Enter/Space 键事件；优先使用原生 button/el-button |
| 假可点 | 无交互行为的卡片禁止 `cursor:pointer` 与 hover 浮起 |
| 对比度 | 正文 ≥ 4.5:1，大字号 ≥ 3:1；高对比档 `[data-contrast="high"]` 提供额外加深的文字/边框与去阴影 |
| 字号缩放 | 三档字号（×0.92 / ×1 / ×1.12）+ 户外主题 ×1.5，满足低视力与强光环境 |
| 简化模式 | `[data-simplify="true"]` 隐藏次要信息，降低认知负担（不隐藏三件套与主操作） |
| 焦点可见 | 全局 `:focus-visible` 2px 主色描边（ui-v2.scss）；禁止 `outline:none` 不补偿 |
| 跳转链接 | 布局提供 skip-link（DefaultLayoutSafe.vue 已实现） |
| 动效 | 尊重 `prefers-reduced-motion`（accessibility.css）；大屏轮播可暂停 |
| 表单 | label 与控件关联（el-form-item 自动）；错误提示紧邻控件 |

---

## 8. 实施路线图

### UI v2.0 已完成（2026-10-19，v1.15.0）

| # | 事项 | 内容 |
|---|------|------|
| 1 | 主题 5 → 3 | 军绿（默认 :root）/ 深色大屏 `dark-bigscreen` / 户外高对比 `outdoor`；旧值 `normalizeTheme` 迁移映射 |
| 2 | 显示偏好 4 档 | 字号 compact/standard/large、密度 comfortable/compact、高对比、简化模式；`ui:prefs` + `data-*` 属性；`useUiPrefs` 唯一入口 + 外观设置面板 |
| 3 | Token 升级 | 主色阶 50/100/500/600/700/900、卡片边框、阴影 2 档、圆角 3 档、字号 calc 化、行高 1.6、tabular-nums、侧栏渐变+金色竖条 |
| 4 | 全局模板样式 | `ui-v2.scss`（表格/卡片/按钮/输入/分页/焦点）、`card.scss`、`states.scss`、`dialog.scss`、`theme-elevated.scss` |
| 5 | 通用组件 | `components/common/` 6 个：AppPageHeader / AppStatCard / AppEmpty / AppLoading / AppError / AppTableToolbar |
| 6 | 导航体验 | 当前板块金色竖条、收起态 hover/聚焦浮层、面包屑「板块 › 页面」、Ctrl+K 命令面板 |
| 7 | 页面 | 工作台 KPI 统计卡 + 待办清单 + 图表层级；大屏三层结构 + 3m/6m/10m 字号分档 + 15s 自动轮播；一户一档左主右辅 + 统计卡 |
| 8 | 质量门禁 | `tests/unit/ui/ui-tokens.test.ts`（Token/主题/偏好/类契约）+ `tests/e2e/visual`（10 页 DOM 结构基线）；硬编码色基线 345 → 305（57 个文件；目标 ≤200） |

### 界面精细化方案 C 已完成（2026-10-20，v1.15.15）

| # | 事项 | 内容 |
|---|------|------|
| 1 | 侧栏品牌区 | 系统标识名 20px/800 单行（logo 36px、侧栏头 64px）；工作台提升为板块级入口（18px/700 + Home 图标） |
| 2 | 全站表格规范 | el-table border 117/117；序号列 72px（25/25）、选择列 48px（10/10）、操作列 fixed=right（67/67） |
| 3 | 筛选栏统一 | 4 档宽度（220/160/240/120）+ 16px 间距；清理 114 处行内宽度；搜索/重置按钮带图标 |
| 4 | 页面头部 | 共享 `PageHeader`：19 个列表页接入（全站 31 页） |
| 5 | 精细化样式层 | `ui-refine.scss`：筛选栏/表格规范 + 8px 栅格 + 响应式断点 1200/992/768 |
| 6 | 质量 | 硬编码色 305/305 零新增；lint:check / vue-tsc 0 错误；定向单测 45 files / 1325 tests 通过 |

### 二期（P1）

| # | 事项 | 前置 |
|---|------|------|
| 1 | 硬编码色基线继续收敛到 ≤200 处 | 逐页 Token 化（dashboard/analytics/系统页优先） |
| 2 | 旧页面接入 `.app-card`/`.app-stat-card`/三件套类与 common 组件 | 不改变业务交互，仅视觉收敛 |
| 3 | ECharts 色板随 `dark-bigscreen`/`outdoor` 注入 | 图表主题工具函数 |
| 4 | Playwright 像素截图基线接入 nightly | 稳定测试数据与固定视口 |

### 三期（P2，随迭代）

- 全站 a11y 推进（div@click 扫描逐批改 + axe 抽检）
- echarts vendor chunk 按路由异步加载（672KB 优化）
- 大屏多对象轮播/对比视图演进

---

## 附录 A：样式文件地图

| 文件 | 职责 | 引入方式 |
|------|------|---------|
| `styles/tokens.scss` | 设计 Token 唯一数据源（:root 军绿 + `dark-bigscreen` + `outdoor`；显示偏好 `[data-*]` 覆盖块） | index.scss @use |
| `styles/tokens-vars.scss` | 纯 SCSS 变量（**禁止实体 CSS 规则**） | vite additionalData 自动注入每个 SFC |
| `styles/index.scss` | 全局入口 + Element Plus `--el-*` 覆盖 + 弹层修复 | main.ts |
| `styles/components/list-page.scss` | 列表页规范 | main.ts |
| `styles/components/ui-refine.scss` | v1.15.15 精细化层：筛选栏 4 档 / 表格规范 / 8px 栅格 / 响应式断点 | main.ts |
| `styles/components/form-page.scss` | 表单/详情规范 | main.ts |
| `styles/components/card.scss` | `.app-card` / `.app-stat-card` / `.stat-trend` / `.num-*`（v2.0） | main.ts |
| `styles/components/states.scss` | `.app-empty` / `.app-loading` / `.app-error` 三件套（v2.0） | main.ts |
| `styles/components/dialog.scss` | 对话框三档宽度 + 圆角/阴影（v2.0） | main.ts |
| `styles/components/ui-v2.scss` | UI v2.0 全局统一层：表格/卡片/按钮/输入/分页/焦点（v2.0） | main.ts |
| `styles/components/table.scss` / `form.scss` / `layout.scss` / `prompt.scss` | 组件级规范 | index.scss @use |
| `styles/theme-elevated.scss` | 精美增强层：多层柔和阴影、hover/focus、胶囊化（v2.0 · U1） | main.ts |
| `styles/dashboard-theme.scss` | 工作台深度视觉主题 | main.ts |
| `styles/print.scss` | 打印样式（A4 适配） | main.ts |
| `styles/accessibility.css` | 无障碍增强（焦点环/skip-link/reduced-motion/high-contrast） | main.ts |
| `styles/responsive.scss` | 响应式断点 mixin | index.scss @use |

## 附录 B：开发纪律

1. **样式 Token 强制**：颜色只能用 `var(--xxx)` / `$xxx`，禁止硬编码十六进制值；新增/改动文件**零新增**硬编码色
   （`check_hardcoded_styles.py` 棘轮只降不升，基线 345 → 305（57 个文件），目标 ≤200）。
2. **优先复用全局类/组件**：新页面用 `.app-card` / `.app-stat-card` / `.app-empty|loading|error` / `.app-table-toolbar`
   与 `components/common/`，不要重复造卡片/三件套样式。
3. **显示偏好属性**：只通过 `composables/useUiPrefs.ts` 读写 `ui:prefs` 与 `<html data-*>`，禁止组件自行写 data 属性。
4. **tokens-vars.scss 只放变量**：禁止 `:root`、选择器等实体规则（该文件会被注入每个 SFC，写规则会导致样式重复打包）。
5. **错误状态必须显示**：请求失败禁止静默吞掉；错误态必须带重试。
6. **空数据用 `.app-empty`/el-empty**；表格用 `#empty` 插槽。
7. **可点卡片无障碍**：可点击 div 必须 `role="button" tabindex="0"` + 键盘事件；不可点的禁止 `cursor:pointer`。
8. **视觉回归**：改 UI 后跑 `vitest tests/unit/ui/ui-tokens.test.ts` + `npx playwright test tests/e2e/visual`；
   确属结构调整才用 `UPDATE_VISUAL_BASELINE=1` 更新基线。
9. **不动三处高风险全局覆盖区**：main.ts 运行时 CSS 注入、DefaultLayoutSafe `:deep` 层、index.scss Element Plus 覆盖区——改动需全量回归。
10. **每批次四道门禁**：eslint（--max-warnings=0）→ vue-tsc → 相关 vitest → vite build。
11. **ErrorBoundary 单一根**：`<transition>` 内子元素必须有且仅有一个根元素（白屏崩溃防护）。
