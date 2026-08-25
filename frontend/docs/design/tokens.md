# 设计令牌规范 v2.0（Design Tokens）

> 唯一事实源：`frontend/src/styles/tokens.scss`（CSS 变量定义）+
> `frontend/src/styles/tokens-vars.scss`（SCSS 桥接注入）。
> 组件 `<style>` 中**只允许引用 token**，硬编码颜色由
> `scripts/check_hardcoded_styles.py` 在 pre-commit 拦截。

## 1. 颜色

| 语义 | 变量 | 值/用途 |
|---|---|---|
| 主色 | `--color-primary` | `#2d6a4f` 军绿，10 级 light 阶梯齐备 |
| 语义 | `--color-success / warning / danger / info` | 成功/警示/危险/信息 |
| 文字 | `--color-text-primary / regular / secondary / placeholder` | 四级文字 |
| 背景 | `--color-bg-page / bg-card / bg-hover` | 页面/卡片/悬浮 |
| 边框 | `--color-border / border-light` | 强/弱分隔 |

**规则**：
- 新代码禁止 hex/rgb 字面量；存量见 baseline（`scripts/hardcoded_styles_baseline.json`）只减不增。
- 图表配色统一走 `utils/chartColors.ts` + echarts-theme。

## 2. 字体阶梯

| 变量 | 值 | 用途 |
|---|---|---|
| `--font-size-xs` | 12px | 辅助说明、徽标 |
| `--font-size-sm` | 13px | 副标题、次要文字 |
| `--font-size-md` | 14px | 正文默认 |
| `--font-size-lg` | 16px | 卡片标题 |
| `--font-size-xl` | 18px | 区块标题 |
| `--font-size-xxl` | 20px | **页面标题**（PageHeader） |
| `--font-size-xxxl` | 24px | **KPI 大数**（KpiCard） |

行高：`tight 1.25 / snug 1.375 / normal 1.5 / relaxed 1.625`。
数字一律 `font-family: var(--font-family-mono)` + `tabular-nums`。

## 3. 间距（4pt 网格）

`xs 4 / sm 8 / md 12(实际16) / lg 16(实际24) / xl 24 / xxl 32`
—— 以 tokens.scss 实际值为准；页面留白只用这六档。

## 4. 圆角与阴影

- 圆角：卡片 `radius-lg(8)` / 控件 `radius-md(6)` / 标签 `radius-sm(4)`
- 阴影仅两级：`--shadow-card`（卡片）、`--shadow-dialog`（弹层）

## 5. 弹窗三档（v2.0 新增）

| 档位 | CSS 变量 | TS 常量 | 适用 |
|---|---|---|---|
| sm 480 | `--dialog-sm` | `DIALOG_SM` | 表单单列、二次确认 |
| md 720 | `--dialog-md` | `DIALOG_MD` | 双列表单、详情 |
| lg 960 | `--dialog-lg` | `DIALOG_LG` | 复杂表单+内嵌表格（需注释豁免） |

## 6. 密度（紧凑档 formalize）

| 变量 | 值 | 说明 |
|---|---|---|
| `--table-row-height` | 36px | 紧凑表格行高 |
| `--control-height` | 32px | 控件高度（= el size small） |
| `--form-label-width` | 100px | 标签宽第一档；长标签表单用 120 |

全局 `size="small"` 已在 App.vue `el-config-provider` 固化；
新代码不要再逐个写 `size="small"`（显式覆盖除外）。

## 7. 布局壳

`header 60px · sidebar 200↔64 · content-padding 24 · max-width 1400`
—— 见 tokens.scss 布局族；响应式断点见 responsive.scss。
