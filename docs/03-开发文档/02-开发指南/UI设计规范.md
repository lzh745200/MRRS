# UI 设计规范（Token 驱动）

本文档定义本系统的 UI 视觉与交互规范，用于保证界面一致性、美观度与跨设备响应式体验。

## 1. 设计原则

- **一致性**：颜色、间距、字体、圆角、阴影统一使用 Token（禁止随意硬编码）。
- **可读性**：关键区域保持足够对比度；信息层级清晰。
- **可用性**：交互可预期，反馈及时；移动端可单手操作。
- **响应式**：以 768px 为关键断点，移动端侧边栏采用抽屉式 + 遮罩。

## 2. 设计 Token（来源）

统一 Token 文件：`frontend/src/styles/tokens.scss`

### 2.1 颜色

- **主色**：`--color-primary`（主题下可映射为军绿）
- **语义色**：`--color-success / --color-warning / --color-danger / --color-info`
- **文字色**：`--color-text-primary / --color-text-regular / --color-text-secondary`
- **背景/边框**：`--color-bg-page / --color-bg-card / --color-border*`

### 2.2 版式与动效

- **间距**：`--spacing-xs/sm/md/lg/xl...`
- **圆角**：`--radius-sm/md/lg...`
- **阴影**：`--shadow-sm/md/lg...`（卡片使用 `--shadow-card`）
- **过渡**：`--transition-fast/normal/...`

### 2.3 断点（建议）

- **移动端**：< 768px
- **平板**：768px–991px
- **桌面**：≥ 992px

> 断点 mixin 见：`frontend/src/styles/responsive.scss`

## 3. 主题规范

Token 内已定义：

- **暗色主题**：`[data-theme="dark"]`
- **军事主题**：`[data-theme="military"]`

### 3.1 主题切换约定

- 通过在 `html` 或 `body` 上挂 `data-theme="<name>"` 切换主题。
- 页面/组件禁止直接写 `#1b4332`、`#d4af37` 这类“主题色值”，应改用 Token（如 `var(--color-primary-dark-1)`、`var(--color-badge-gold)`）。

## 4. 布局与导航

### 4.1 默认布局

文件：`frontend/src/layouts/DefaultLayoutSafe.vue`

规范：

- 顶部栏高度：`--layout-header-height`
- 侧边栏宽度（桌面）：展开 240px / 收起 68px（与 UI设计方案 §4.1 一致）
- 移动端侧边栏：抽屉式（`mobile-open`）+ 遮罩（点击遮罩关闭）
- 侧边栏颜色：使用 Token（`var(--color-primary-dark-1)` 等）

### 4.2 导航结构（v1.13.0，后端单一菜单源）

- **数据来源**：后端 `app/api/v1/menus.py` 的 `MENU_DEFINITIONS` v2（`sections` + `flat_keys`），
  前端 `stores/menu.ts` 消费；**禁止在前端手写菜单段或维护菜单配置副本**（`config/menu-config.ts`、
  `utils/systemMenu.ts` 已删除）。
- **7 个板块**：工作台（固定首位，不入 sections）+ 帮扶业务 / 乡村振兴 / 工作协同 / 分析汇报 / 数据管理 / 系统管理。
- **三种条目的渲染**：`page`（普通菜单项）、`group`（可折叠分组）、`console`（系统管理聚合页入口）。
- **系统管理 6 聚合页**：组织与权限 / 安全与审计 / 运维与监控 / 备份与存储 / 系统设置 / 关于与反馈；
  页内 Tab 切换，Tab 来自后端 `tabs[]`，仅渲染有权限的 Tab，旧路由全部保留。
- **导航增强**：`Ctrl+K` 菜单搜索（label/key/path 过滤、键盘选择跳转、空态显示收藏+最近）、
  收藏与最近访问（localStorage `nav:favorites` / `nav:recent`，上限 8）、移动端底部导航（数据驱动）。
- **权限**：`canAccessMenu(key)` 含 console 的 `tabs[].key`；菜单可见性三级优先级不变
  （用户级 > 权限包 > 角色默认）。详见《前后端契约规范》§4。

本次已完成的改进点：

- **侧边栏支持移动端抽屉**（遮罩关闭、路由变化自动收起的逻辑由 `useResponsiveSidebar` 提供）
- **菜单颜色与布局色值收敛到 Token**，减少硬编码
- **侧栏/移动端/权限面板全部数据驱动**（v1.13.0 导航改造，前端菜单副本已删除）

## 5. 组件使用规范（Element Plus）

- **按钮**：重要操作用主按钮，其它用次按钮/文本按钮；避免同屏出现过多主按钮。
- **表单**：移动端尽量单列；输入控件宽度 100%。
- **表格**：移动端优先采用卡片化或横向滚动（`responsive.scss` 已提供基础工具类）。
- **反馈**：成功/失败/警告提示统一使用语义色；避免自定义“非语义”颜色提示。

## 6. 代码约束（强制）

- 新增样式优先放在 `styles/` 体系（Token/组件/布局），避免散落在各页面。
- 禁止在业务组件内引入大型 UI 依赖或全量图标注册（入口 `main.ts` 已按需注册图标）。
