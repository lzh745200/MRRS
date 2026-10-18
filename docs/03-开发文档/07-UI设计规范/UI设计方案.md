# UI 设计方案

> **版本**: v1.0 | **日期**: 2026-08-04（2026-10-18 补充 v1.13.0 导航改版：7 板块 + 系统管理 6 聚合页 + 菜单搜索/最近/收藏） | **范围**: frontend/（Vue 3 + Element Plus）
> 本文档是帮扶管理信息系统的 UI 设计总纲：设计定位、视觉基础、主题策略、组件/页面规范、状态与无障碍规范、实施路线图。
> 配套代码事实源：`frontend/src/styles/tokens.scss`（设计 Token 唯一数据源）。

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
| **庄重可信** | 军风政务气质：军绿为主、金色点缀，克制使用高饱和色 | 色彩体系 §2.1；卡片/表格军绿头+金线 §4.2 |
| **高效录入** | 表单是核心工作流（帮扶村 10 板块年度数据），减少视觉噪音、统一栅格 | 表单页规范 §5.2；form-page.scss |
| **离线可用** | 无网络依赖：字体用系统字体栈、地图用离线瓦片、图标用 Element Plus 内置集 | tokens.scss 字体 Token；Leaflet 离线瓦片 |
| **失败可见** | 任何请求失败必须被用户看见并可重试，禁止静默 catch | 状态三件套 §6 |
| **人人可用** | 键盘可达、对比度达标、户外/长辈高对比模式 | 无障碍规范 §7；outdoor 主题 §3 |
| **单一数据源** | 颜色只用 Token 变量（`var(--xxx)`），禁止硬编码十六进制值 | tokens.scss；附录 B 纪律 |

---

## 2. 视觉基础

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

### 2.2 历史语义蓝映射建议表（23 处待决策项）

2026-07-18 美化时保留了 23 处"状态/分类语义蓝"（日志级别、图表系列色、地图 marker、数据冷热分层）。以下为推荐映射，**需产品确认后统一替换**：

| 场景 | 现状 | 推荐映射 | 理由 |
|------|------|---------|------|
| 日志级别 INFO | Element 蓝 | `--color-info`（军绿灰） | 中性信息归入语义 info |
| 日志级别 DEBUG | 浅蓝 | `--color-text-secondary` | 低优先级弱化 |
| 图表系列色（多系列） | ECharts 默认蓝系 | 军绿色板 §4.6 序列 | 与主题一致；系列区分靠色阶+金色 |
| 地图 marker（默认） | 蓝色 marker | `--color-primary` 绿 marker | 主色统一 |
| 数据冷热分层（冷数据） | 蓝底 | `--color-info-lightest` 底 + `--color-info` 字 | 冷=中性信息 |
| 链接文字 | Element 蓝 | `var(--el-color-primary)` | 已全局覆盖为军绿 |

### 2.3 字体

- **字体族**：系统字体栈（`--font-family-base`），中文回退 Microsoft YaHei；等宽 `--font-family-mono`。离线环境不引入 Web Font。
- **字号 8 档**：xs 12 / sm 13 / md 14（基准）/ lg 16 / xl 18 / xxl 20 / xxxl 24 / display 32。
- **字重**：正文 400，强调 500，标题 600，大标题 700。
- **行高**：正文 1.5，标题 1.25。

### 2.4 间距（4px 基准网格）

`--spacing-xs` 4 / `sm` 8 / `md` 16 / `lg` 24 / `xl` 32 / `xxl` 48 / `xxxl` 64。
**规则**：组件内部间距用 xs/sm；卡片内边距 md~lg；页面区块间距 lg~xl。禁止使用非 4 倍数像素。

### 2.5 圆角 / 阴影 / 层级

| 类别 | Token | 使用约定 |
|------|-------|---------|
| 圆角 | `--radius-sm` 2 / `md` 4 / `lg` 8 / `xl` 12 / `xxl` 16 / `round` | 按钮/输入框用 Element 默认 6px；卡片 lg；对话框 lg；标签 round |
| 阴影 | `--shadow-sm`~`--shadow-xxl` + 组件专用（card/dropdown/dialog/popover） | 白底卡片用轻阴影+边框；弹层用 dropdown/dialog 专用阴影；禁止自定义阴影值 |
| z-index | dropdown 1000 → loading 1090（10 档） | Element Plus popper 统一提升至 2000（已在 index.scss 处理）；禁止随手写 999/9999 |

---

## 3. 主题策略

### 3.1 五套主题定位

`tokens.scss` 已定义 5 套 `[data-theme]`（含 :root 默认），定位如下：

| 主题 | 选择器 | 定位 | 启用状态 |
|------|--------|------|---------|
| **军绿（默认）** | `:root`（无 data-theme） | 全局默认主题，庄重政务风 | ✅ 默认渲染，顶栏可切回 |
| **浅色** | `[data-theme="light"]` | Element Plus 原生蓝，兼容回退/对照用 | ✅ 顶栏可选 |
| **暗色** | `[data-theme="dark"]` | 夜间办公，低亮度环境 | 仅系统设置页（二期进顶栏，依赖硬编码 Token 化） |
| **军事风** | `[data-theme="military"]` | 深绿渐变+金色徽章，大屏/汇报场景 | 仅系统设置页（bigscreen 可局部应用） |
| **户外/长辈** | `[data-theme="outdoor"]` | 高对比深蓝+亮黄，字号×1.5，户外强光与老年用户 | ✅ 顶栏可选 |
| **高对比** | `[data-theme="high-contrast"]`（accessibility.css） | 黑白高对比无障碍模式 | ✅ 顶栏可选 |

### 3.2 切换机制

- **状态源**：`stores/config.ts` 的 `theme`（唯一数据源；`stores/app.ts` 不再持有 theme）。
- **DOM 接线**：`setTheme(t)` 同时写 localStorage 与 `document.documentElement.dataset.theme`；`'default'` 表示移除 data-theme 属性（渲染 :root 军绿）。`applyThemeToDom()` 为共享工具函数。
- **启动应用**：`main.ts` 在 createApp 之前读取 localStorage 并应用到 DOM，避免主题闪烁（FOUC）。
- **切换入口（双通道）**：
  - **顶栏切换器**（DefaultLayoutSafe header-right，全体用户）：仅开放已完成适配的 4 套 — 军绿（default）/ 明亮（light）/ 户外（outdoor）/ 高对比（high-contrast）。
  - **系统配置页**（系统管理 → 备份与存储 → **系统配置** `/system/config`，管理员）：开放全部 6 套（含深色 dark / 军旅 military，供调试与汇报场景）。
- **默认值**：`'default'`（军绿）。
- **开放节奏**：dark 与 military 待二期全站硬编码 Token 化后再进入顶栏切换器（military 的 `--color-bg-page` 为渐变值，用于 `background-color` 时失效，需先治理）。
- **无障碍接入**：`styles/accessibility.css` 已由 main.ts 全局引入 — high-contrast 主题补全、outdoor 触控增强、焦点环、prefers-reduced-motion；其中会改变全站既有布局的两条全局尺寸规则（el-icon 最小 24px / el-button--small 最小 32px）已移除。

### 3.3 主题适配验收标准

每开放一个新主题，必须逐页核查：

1. 文字对比度 ≥ 4.5:1（正文）/ 3:1（大字号）；
2. 无"白底白字/黑底黑字"穿帮（重点：硬编码色值页面）；
3. Element Plus 组件随 `--el-*` 变量联动（index.scss 已 var() 化）；
4. ECharts 图表色板可读（必要时按主题注入色板）。

---

## 4. 组件规范

### 4.1 布局骨架

| 区域 | 规格 |
|------|------|
| 侧边栏 | 展开 240px / 收起 68px；深军绿底；菜单激活文字金色 `#d4af37`；<768px 自动收起 |
| 顶栏 | 高 60px（`--layout-header-height`）；左：折叠按钮+面包屑；右：主题切换器+用户下拉 |
| 内容区 | 最大宽 1400px（`--layout-content-max-width`），内边距 24px |
| 页脚 | 高 28px，版本号 |

**侧边栏导航结构（v1.13.0，完全数据驱动）**：

```
侧边栏
├── 工作台（固定第一，/dashboard）
├── 收藏（有数据时显示，最多 8 个）
├── 最近访问（有数据时显示，最多 8 个）
└── v-for sections（后端 /menus/accessible v2 下发，按 order 升序）
    ├── 板块分组标题（帮扶业务 / 乡村振兴 / 工作协同 / 分析汇报 / 数据管理 / 系统管理）
    ├── page 条目 → 普通菜单项
    ├── group 条目 → 可折叠子菜单（如 经费管理 / 审批管理 / 数据分析 / 数据上报）
    └── console 条目 → 聚合页入口（系统管理 6 个）
```

- 前端**不得再手写菜单段**；`dashboard` 固定渲染，其余全部来自后端 `MENU_DEFINITIONS` v2。
- 移动端（<768px）：底部导航数据驱动（工作台 + sections 前 3 个入口 + "更多"），抽屉式侧栏保留。

### 4.2 卡片与对话框（军风标识）

- **卡片头**：军绿深底 `--color-primary-dark-1` + 白字 + 金色下边线 2px（form-page.scss 全局规范）。
- **对话框头**：同卡片头规范；对话框体白底，圆角 lg，`clip-path` 保圆角裁剪且不裁剪弹出层。
- **普通内容卡**：白底 + `--color-border-lighter` 边框 + 轻阴影，hover 阴影加深。

### 4.3 表格

- 表头：军绿深底 + 白字 + 金色下边线 2px；斑马纹用 `--color-bg-page`。
- 分页激活页码：军绿深底白字。
- 空数据：`#empty` 插槽统一 `<el-empty description="暂无数据" />`。
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

### 4.7 导航与菜单搜索（v1.13.0）

| 交互 | 规范 |
|------|------|
| **菜单搜索** | 任意页面 `Ctrl+K` 打开 `MenuSearchDialog`；搜索 `label` / `key` / `path`（大小写不敏感子串）；`↑`/`↓` 移动、`Enter` 跳转、`Esc` 关闭；空搜索显示"收藏 + 最近访问" |
| **最近访问** | localStorage `nav:recent`，最多 8 条，按访问时间倒序、按 key 去重；损坏数据回退空数组 |
| **收藏** | localStorage `nav:favorites`，最多 8 条；侧栏顶部"收藏"区与搜索弹窗共享同一份数据 |
| **菜单权限** | `canAccessMenu(key)` 语义不变，额外支持 console 的 `tabs[].key`；无权限的 Tab 不渲染 |
| **可访问性** | 搜索弹窗支持键盘全流程操作；侧栏可点击项保持 `role`/焦点可见；菜单激活态用金色文字 + 左缘主色条 |

> 实现位置：`frontend/src/components/nav/MenuSearchDialog.vue`、`composables/useRecentMenus.ts`、
> `composables/useMenuFavorites.ts`；数据源为 `stores/menu.ts`（后端单一菜单源 v2）。

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

### 5.4 工作台（dashboard）

KPI 卡（可点卡必须 `role="button" tabindex="0"` + 键盘事件）+ 图表区（el-skeleton 骨架屏加载）+ 快捷操作 + 全局搜索。禁止假数据可视化（如平线 sparkline 冒充趋势）。

### 5.5 大屏（bigscreen）

汇报模式：全屏自动轮播 KPI/经费趋势/成效排名/项目状态。视觉语言可局部启用 `[data-theme="military"]`（深绿渐变+金色徽章+发光效果，tokens.scss 已提供动画时长变量 `--animation-*`）。文字最小 24px，保证投影可读。

### 5.6 系统管理聚合页（SystemConsole，v1.13.0）

- 路由 `/system/console/:group`（group ∈ `org` / `security` / `ops` / `storage` / `settings` / `about`），
  由 `views/system/console/SystemConsole.vue` 承载；标题/面包屑取后端 console 节点 `label`。
- 页内用 `el-tabs` 切换，Tab 来自后端 console 节点的 `tabs[]`（**仅渲染有权限的 Tab**）；
  当前 Tab 用 query `?tab=<tab.key>` 表达，切换用 `router.replace`（不产生历史堆栈）。
- **只有当前 Tab 的页面组件会被异步加载**；Tab 内容复用原页面组件（旧页面、旧路由全部保留，深链不失效）。
- 无权限 / 未知 group / 无可渲染 Tab：显示空态与"返回工作台"引导，不白屏。

---

## 6. 状态与反馈规范

**三件套（每个异步视图必须齐备）**：

| 状态 | 规范 |
|------|------|
| loading | 骨架屏 `el-skeleton`（卡片/图表区）或 `v-loading`（表格） |
| empty | `<el-empty description="暂无数据" />`；表格用 `#empty` 插槽 |
| error | `ElMessage.error` 提示 + `el-result` 错误占位 + 重试按钮；**禁止静默 catch** |

**消息反馈**：ElMessage 全局默认 showClose + 5s（main.ts 已配置）；居中弹出（DOM 级 CSS 注入）。

---

## 7. 无障碍规范（WCAG 2.1 AA）

| 条目 | 要求 |
|------|------|
| 键盘可达 | 可点击 div 必须 `role="button" tabindex="0"` + Enter/Space 键事件；优先使用原生 button/el-button |
| 假可点 | 无交互行为的卡片禁止 `cursor:pointer` 与 hover 浮起 |
| 对比度 | 正文 ≥ 4.5:1，大字号 ≥ 3:1；outdoor 主题专项核查 |
| 焦点可见 | 保留 Element 默认 focus 环，禁止 `outline:none` 不补偿 |
| 跳转链接 | 布局提供 skip-link（DefaultLayoutSafe.vue 已实现） |
| 表单 | label 与控件关联（el-form-item 自动）；错误提示紧邻控件 |

---

## 8. 实施路线图

### 已完成（2026-07-18 美化基线）

- 阶段 0 样式体系卫生（tokens 单源、tokens-vars.scss 注入、孤儿 military-theme.scss 删除）
- 阶段 1 色彩统一（Element 蓝清理 29→6，保留 23 处语义蓝待决策）
- 阶段 2 状态三件套 + a11y（代表页）
- 阶段 3 响应式（侧边栏自动收起、flex-wrap、KPI 单列）

### 本轮（v1.0 方案落地）

| # | 事项 | 内容 |
|---|------|------|
| 1 | UI 设计方案文档 | 本文档 |
| 2 | 表单布局规范化 | SectionDataForm / YearlyDataForm / ComprehensiveEntry 内联 style 清理（171 处→0）+ form.scss 宽度/间距工具类（input-full-width / input-fixed-width / input-year-width / form-item-actions 等） |
| 3 | 主题切换接线 | config store 升级为唯一数据源（THEME_OPTIONS / applyThemeToDom / 默认 default 军绿）+ main.ts 启动应用（防 FOUC）+ 顶栏切换器（default/light/outdoor/high-contrast）+ ConfigPackage 增加军绿选项 + accessibility.css 接入（移除 2 条布局破坏性规则）+ 删除冗余 print.css |

### 二期（P1，需产品决策或前置条件）

| # | 事项 | 前置 |
|---|------|------|
| 1 | 仪表盘类硬编码 Token 化（~380 处：HomeSafe/dashboard、ruralWorks/Analysis、AdminDashboard、MonitoringDashboard、analytics/dashboard） | 先建 Playwright 视觉回归基线 |
| 2 | 23 处语义蓝按 §2.2 映射表替换 | 产品确认映射 |
| 3 | dark 主题开放 | 硬编码 Token 化完成 + 引入 EP dark css-vars |
| 4 | 派生中间档 Token 化（`--el-color-*-light-5/7/9` 12 处） | 无 |

### 三期（P2，随迭代）

- 全站 a11y 推进（div@click 扫描逐批改 + axe 抽检）
- echarts vendor chunk 按路由异步加载（672KB 优化）
- Playwright 截图基线接入 nightly-full
- military 主题大屏全面启用

---

## 附录 A：样式文件地图

| 文件 | 职责 | 引入方式 |
|------|------|---------|
| `styles/tokens.scss` | 设计 Token 唯一数据源（:root + 5 套 data-theme） | index.scss @use |
| `styles/tokens-vars.scss` | 纯 SCSS 变量（**禁止实体 CSS 规则**） | vite additionalData 自动注入每个 SFC |
| `styles/index.scss` | 全局入口 + Element Plus `--el-*` 覆盖 + 弹层修复 | main.ts |
| `styles/components/list-page.scss` | 列表页规范 | main.ts |
| `styles/components/form-page.scss` | 表单/详情/卡片/对话框规范 | main.ts |
| `styles/components/table.scss` / `form.scss` / `layout.scss` / `enhanced.scss` / `prompt.scss` | 组件级规范 | index.scss @use |
| `styles/dashboard-theme.scss` | 工作台深度视觉主题 | main.ts |
| `styles/print.scss` | 打印样式（A4 适配） | main.ts |
| `styles/accessibility.css` | 无障碍增强（焦点环/skip-link/reduced-motion/high-contrast 主题） | main.ts |
| `styles/responsive.scss` | 响应式断点 mixin | index.scss @use |

## 附录 B：开发纪律

1. **样式 Token 强制**：颜色只能用 `var(--xxx)` / `$xxx`，禁止硬编码十六进制值（`#409eff` 旧残留一律替换为 `var(--color-primary)` 系列）。
2. **tokens-vars.scss 只放变量**：禁止 `:root`、选择器等实体规则（该文件会被注入每个 SFC，写规则会导致样式重复打包）。
3. **错误状态必须显示**：请求失败禁止静默吞掉。
4. **空数据用 el-empty**；表格用 `#empty` 插槽。
5. **可点卡片无障碍**：可点击 div 必须 `role="button" tabindex="0"` + 键盘事件；不可点的禁止 `cursor:pointer`。
6. **不动三处高风险全局覆盖区**：main.ts 运行时 CSS 注入、DefaultLayoutSafe `:deep` 层、index.scss Element Plus 覆盖区——改动需全量回归。
7. **每批次四道门禁**：eslint（--max-warnings=0）→ vue-tsc → 相关 vitest → vite build。
8. **ErrorBoundary 单一根**：`<transition>` 内子元素必须有且仅有一个根元素（白屏崩溃防护）。
