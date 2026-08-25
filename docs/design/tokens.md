# 设计令牌规范 v2.0

> UI 精细化设计方案 v2.0 · 配套 `src/styles/tokens.scss`
> 规则：颜色/字号/间距/圆角/阴影**只准引用 token**。`<style>` 出现 hex 即被 `scripts/check_hardcoded_styles.py` 拦截。

## 1. 色彩

| 语义 | 变量 | 值 |
|---|---|---|
| 主色（军绿） | `--color-primary` | `#2d6a4f` + light-3~10 阶梯 |
| 页面底 | `--color-bg-page` | 浅灰 |
| 卡片底 | `--color-bg-card` | `#fff` |
| 悬浮底 | `--color-bg-hover` | `#f5f7fa` |
| 主文字 | `--color-text-primary` | 近黑 |
| 次要文字 | `--color-text-secondary` | `#909399` |
| 成功/警告/危险/信息 | `--color-{success,warning,danger,info}` | EP 语义色对齐 |

## 2. 字体阶梯（五档 + V2 补全）

| 变量 | 值 | 用途 |
|---|---|---|
| `--font-size-xs` | 12px | 辅助/标签 |
| `--font-size-sm` | 13px | 次要正文 |
| `--font-size-md` | 14px | 正文基准 |
| `--font-size-lg` | 16px | 卡片标题 |
| `--font-size-xl` | 18px | 区块标题 |
| `--font-size-xxl` | 20px | **页标题** |
| `--font-size-xxxl` | 24px | 数据大数 |

行高：`--line-height-tight: 1.3` / `--line-height-normal: 1.57`；字重：`--font-weight-semibold: 600`。
数字一律等宽字体 `--font-family-mono` + `tabular-nums`。

## 3. 弹窗三档（与 `src/config/dialog.ts` 一一对应）

| 变量 | 值 | 场景 |
|---|---|---|
| `--dialog-sm` | 480px | 表单 / 确认 |
| `--dialog-md` | 720px | 双列表单 / 详情查看 |
| `--dialog-lg` | 960px | 内嵌表格（批量导入预览等） |

## 4. 密度（compact formalize）

| 变量 | 值 | 说明 |
|---|---|---|
| `--table-row-height` | 36px | el size=small 行高锚定 |
| `--control-height` | 32px | 控件高度锚定 |
| `--form-label-width` | 100px | 第二档 120px 仅长标签表单 |

## 5. 圆角 / 阴影 / 动效

- 圆角三档：卡片 8 / 控件 6 / 标签 4
- 阴影两级：card `0 1px 3px rgba(45,106,79,.08)`、modal `0 8px 24px rgba(0,0,0,.12)`
- 动效仅 `transition-fast .15s`（hover/展开），**禁入场动画**

## 6. 迁移映射（codemod 高频 22 条）

```
#fff/#ffffff → var(--color-bg-card)
#909399     → var(--color-text-secondary)
#f5f7fa     → var(--color-bg-hover)
#67c23a     → var(--color-success)
#e6a23c     → var(--color-warning)
#f56c6c     → var(--color-danger)
#409eff     → var(--color-info)
#2d6a4f     → var(--color-primary)
...其余见 scripts/check_hardcoded_styles.py 内置映射表
```

## 7. 斑马纹规则

`stripe` 仅当**可见列 ≥ 6** 时启用（`--stripe-enabled-min-cols: 6`）——宽表增强横向阅读，窄表禁用避免视觉噪音。
