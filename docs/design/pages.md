# 页面模板规范 v2.0

> UI 精细化设计方案 v2.0 · 五大模板契约。P3 Top20 逐页按此验收。

## 应用壳

Header 60px（面包屑+搜索+通知+用户）｜Sidebar 200↔64（菜单分组标题 12px 大写间距，选中态左缘 3px 主色条）｜Content padding 20/24。

响应式：1366-1439 侧栏自动折叠+内容 padding 降 16；≥1920 内容 max-width 1680 居中；150% 缩放全 px 无错位。

## T1 列表页

```
PageHeader(题+副题+唯一主钮)
└─ ListToolbar(filters inline + tools 右置)
   └─ 卡片包裹 Table(size=small, stripe≥6列, EmptyState 空态)
      └─ 分页右下
```
适用：funds/EnhancedList、schools/List、policies/List 等 77 张表页。

## T2 详情页

```
头卡(el-descriptions 关键字段 + 状态 tag + 操作钮排)
└─ Tabs 分区（每 Tab 内 2-3 卡片）
```
适用：funds/Detail、projects/Detail、villages/Detail。

## T3 表单页

section 分组卡 → label 100/120 → 控件宽 `{full,360,240}` → sticky 底部操作条。
适用：各 Edit.vue ×14。

## T4 仪表盘

KpiRow(4 卡) → ChartCard 双列栅格 → 快捷入口。
适用：dashboard、analytics。

## T5 弹窗流

sm 表单/确认 · md 双列或详情 · lg 内嵌表格；底部 `[取消][主钮]` 右对齐。
适用：全部弹窗。

## 每页 8 条通用验收

1. 栅格对齐 4pt 倍数
2. 间距全 token
3. 层级三级清晰（20px 页题 / 16px 卡题 / 14px 正文）
4. 空/加载/错误三态齐
5. 1366 与 1920 双档截图正常
6. 150% 缩放无错位
7. 交互反馈 ≤.15s
8. 与本组已精修页并排无违和

## 图表主题

echarts 统一注册主题：序列色板取 primary 阶梯+语义色扩展 10 色，轴线 `border-light`，文字 12px secondary。chart.js 两处迁移后删除依赖。
