---
kind: frontend_style
name: 前端样式体系：Element Plus + CSS 变量设计令牌与多主题增强层
category: frontend_style
scope:
    - '**'
source_files:
    - frontend/src/styles/tokens.scss
    - frontend/src/styles/index.scss
    - frontend/src/styles/dashboard-theme.scss
    - frontend/src/styles/theme-elevated.scss
    - frontend/src/styles/responsive.scss
    - frontend/src/styles/accessibility.css
    - frontend/src/styles/print.scss
    - frontend/src/styles/components/layout.scss
    - frontend/src/styles/components/table.scss
    - frontend/src/styles/components/form.scss
    - frontend/src/styles/components/prompt.scss
    - frontend/src/styles/components/list-page.scss
    - frontend/src/styles/components/form-page.scss
    - frontend/src/main.ts
    - frontend/package.json
---

## 1. 采用的系统/方法

- **UI 组件库**：基于 Element Plus（`element-plus@^2.6.1`），通过 `unplugin-vue-components` 按需自动导入组件，并在 `main.ts` 中显式引入命令式 API（ElMessage/MessageBox/Notification）的样式文件，避免按需注入遗漏。
- **样式预处理**：使用 SCSS（`sass@^1.101.0`），采用 `@use` 替代已弃用的 `@import`，以模块化的方式组织样式。
- **构建工具**：Vite 作为构建器，配合 `vite-plugin-compression` 进行产物压缩。
- **设计令牌系统**：在 `src/styles/tokens.scss` 中定义完整的 CSS 自定义属性（CSS Variables）令牌集，包括颜色、间距、圆角、阴影、字体、断点、z-index、布局尺寸、组件尺寸、弹窗尺寸、密度等，并通过 `[data-theme]` 选择器实现多主题切换。
- **响应式策略**：基于 SCSS mixin 的断点系统（`responsive.scss`），定义 xs/sm/md/lg/xl/xxl 六个断点，提供 `min-width`/`max-width`/`between`/`mobile-only`/`tablet-up` 等 mixin，以及响应式栅格和工具类。

## 2. 关键文件与包

- **令牌与主题**：
  - `frontend/src/styles/tokens.scss` — 核心设计令牌，定义 `:root` 默认绿色系主题及 `[data-theme="light"|"dark"|"military"|"outdoor"]` 多主题覆盖
  - `frontend/src/styles/dashboard-theme.scss` — Dashboard 专属视觉主题层，作用域限定 `.dashboard-modern`
  - `frontend/src/styles/theme-elevated.scss` — 全站精美增强层（UI v2.0 U1），在品牌基调之上叠加柔和阴影、hover 微交互、focus 光环
  - `frontend/src/styles/tokens-vars.scss` — 与 tokens.scss 同步校验（由 `scripts/check_tokens_sync.py` 保障）
- **全局入口**：
  - `frontend/src/main.ts` — 按序引入所有样式层，并应用本地存储的主题
  - `frontend/src/styles/index.scss` — 聚合入口，覆盖 Element Plus CSS 变量映射到项目 token，统一组件尺寸密度
- **组件级样式**：`frontend/src/styles/components/` 下的 `layout.scss`、`table.scss`、`form.scss`、`prompt.scss`、`list-page.scss`、`form-page.scss`
- **辅助样式**：`accessibility.css`（WCAG 2.1 AA）、`print.scss`（A4 打印）、`responsive.scss`（响应式 mixin 与栅格）
- **依赖包**：`element-plus`、`@element-plus/icons-vue`、`sass`、`vite`、`unplugin-auto-import`、`unplugin-vue-components`

## 3. 架构与约定

### 令牌分层
- 所有颜色、间距、圆角、阴影、字体、断点、z-index、布局、组件尺寸均以 CSS 自定义属性形式声明在 `tokens.scss` 的 `:root` 下，作为单一数据源。
- 通过 `[data-theme]` 属性选择器覆盖同一组 token 名称实现主题切换，支持 light/dark/military/outdoor 四种主题。
- 为兼容历史代码，同时提供 SCSS 变量 `$color-*`/$spacing-*`/$radius-*` 等映射到对应 CSS 变量。

### Element Plus 集成
- 在 `index.scss` 中将 Element Plus 的 `--el-color-*`、`--el-text-color-*`、`--el-border-color-*`、`--el-bg-color-*` 等 CSS 变量映射到项目 token，保证组件与主题一致。
- 通过 `--el-component-size` 系列变量统一控件密度，锚定 `--control-height` 等 token 值。
- 对 `el-select`、`el-dialog`、`el-card`、`el-table`、`el-pagination` 等常用组件进行精细化覆盖，解决弹出层裁剪、下拉框宽度、对话框滚动等已知问题。

### 样式加载顺序（强制约定）
`main.ts` 中样式引入顺序严格规定：`index.scss` → `dashboard-theme.scss` → `components/list-page.scss` → `components/form-page.scss` → `theme-elevated.scss` → `print.scss` → `accessibility.css`。该顺序确保品牌基线（深军绿表头+金线）不被后续增强层推翻。

### 作用域隔离
- Dashboard 主题通过 `.dashboard-modern` 作用域限定，不影响全局。
- 各组件样式文件职责单一：`layout.scss` 处理布局、`table.scss` 处理表格、`form.scss` 处理表单、`prompt.scss` 处理消息/确认框等。

### 无障碍与可访问性
- `accessibility.css` 提供 WCAG 2.1 AA 增强：焦点指示器、skip-link、屏幕阅读器隐藏类、减少动画偏好、高对比度主题、户外大字体模式。
- 通过 `prefers-reduced-motion` 媒体查询禁用动画。

### 打印适配
- `print.scss` 提供 A4 纸张打印样式，隐藏侧边栏/头部/底部等非打印内容，优化表格分页与图表显示。

## 4. 约定与约束

- **禁止硬编码颜色**：所有颜色必须引用 `--color-*` token，新增 token 需同步到 `tokens-vars.scss` 并由 `check_tokens_sync.py` 校验（见 `tokens.scss` 末尾注释 T043）。
- **主题切换通过 data 属性**：运行时通过设置 `document.documentElement.dataset.theme` 切换主题，首屏 FOUC 通过 `applyThemeToDom` 在挂载前应用。
- **Element Plus 样式覆盖规范**：仅通过 CSS 变量和全局覆盖文件修改，不在组件 `<style>` 中直接写死颜色值。
- **响应式断点统一**：所有媒体查询必须使用 `responsive.scss` 中定义的断点 mixin，禁止散落的硬编码像素值。
- **弹窗高度规范**：`el-dialog` 使用 flex 列布局 + `max-height: calc(100vh - 48px)`，footer 常驻可见，超长内容在 body 内滚动。
- **动效安全**：路由入场动画仅使用 opacity（禁用 transform 位移以避免固定定位元素被裁切），并通过 `prefers-reduced-motion` 关闭。
- **滚动条统一**：最终由 `theme-elevated.scss` 收敛为 6px 细条，覆盖 index.scss 的 8px 与 dashboard 的 6px。
- **Electron 兼容性**：对话框使用 `clip-path: inset(0 round ...)` 替代 `overflow:hidden` 以保持圆角且不裁剪 teleported popper。