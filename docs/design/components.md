# 组件规范 v2.0

> UI 精细化设计方案 v2.0 · P2 骨架标准件契约。所有组件带 vitest 渲染测试。

## PageHeader（`components/common/PageHeader.vue`）

T1 列表页 / T2 详情页模板头部唯一出口，替代各页手写的 30+ 种标题区。

| Prop | 说明 |
|---|---|
| `title` | 页面主标题（20px/semibold） |
| `subtitle` | 一句话说明"这页管什么"（实用性原则必填） |
| `showBack` | 详情/编辑页显示返回钮（router.back + 菜单 fallback） |

Slots：`default/extra` 右侧操作区（**唯一主钮右置**）；`metrics` 标题下方统计条。

## ListToolbar（`components/common/ListToolbar.vue`）

T1 列表页工具栏：PageHeader 之下、Table 卡片之上。

- slot `filters`：筛选控件 inline 区
- slot `default/tools`：右侧工具组
- 规则：筛选项 >3 时折叠非核心项（`:filter-count` + `collapse-after=3`）

## KpiCard（`components/business/KpiCard.vue`）

T4 仪表盘 KPI 卡：数值 24px semibold mono、同比箭头语义色、图标 40px 容器 `primary-light-8` 底。

## EmptyState（`components/business/EmptyState/EmptyState.vue`）

全站唯一空态出口（54 文件渐进替换 el-empty 裸用）：

| Prop | 值 |
|---|---|
| `type` | `no-data`(默认) / `no-search` / `no-permission` / `error` |
| `text` | 覆盖默认文案 |
| `action` | 行动按钮文案 → `$emit('action')` |

## Dialog

```ts
import { DIALOG_SM, DIALOG_MD, DIALOG_LG } from '@/config/dialog'
```
- 宽度只准三常量；`align-center destroy-on-close` 默认
- 底部 `[取消][主钮]` 右对齐；复杂流用 steps

## Table

- 全局 `size=small`
- 表头底色 `bg-hover` 字色 secondary 不加粗
- **stripe 仅当可见列 ≥6**
- 空态必须 `<EmptyState>`
- 操作列固定右侧宽 ≤180
