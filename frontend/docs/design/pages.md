# 页面模板与改造矩阵 v2.0

> 130 个视图 → 5 类骨架模板；每页验收走 8 条通用 checklist。

## 五大页面骨架模板

| 模板 | 结构契约 | 代表页面 |
|---|---|---|
| **T1 列表页** | PageHeader(题+副题+唯一主钮) → 筛选工具条(inline) → 卡片包裹 Table → 分页右下 | funds/EnhancedList、schools/List、policies/List 等 77 张表页 |
| **T2 详情页** | 头卡(descriptions 关键字段+状态 tag+操作排) → Tabs 分区（每 Tab 内 2-3 卡片） | funds/Detail、projects/Detail、supported-villages/Detail |
| **T3 表单页** | section 分组卡 → label 100/120 → 控件宽 {full,360,240} → sticky 底部操作条 | 各 Edit.vue ×14 |
| **T4 仪表盘** | KpiRow(KpiCard×4) → ChartCard 双列栅格 → 快捷入口 | dashboard/index、analytics/* |
| **T5 弹窗流** | sm 表单/确认 · md 双列/详情 · lg 内嵌表格；底部 [取消][主钮] 右对齐 | 全部弹窗 |

## Top20 高频页精修清单（P3 批次）

1. dashboard/index — KpiRow 换 KpiCard、ChartRow 空态
2. funds/EnhancedList — PageHeader 化、stripe 规则、dialog 常量
3. funds/Detail — T2 头卡、steps 上移
4. projects/List、projects/Detail
5. analytics/supported-villages/List — 已挂水印，补 PageHeader
6. schools/List
7. system/UserManagement — admin 按钮区 v-permission 双保险
8. approval/PendingList、approval/History
9. policies/List
10. message/MessageCenter
11. dataPackage/List
12. organization/Detail
13. ruralWorks/Task
14. analytics/dashboard
15. auth/LoginEnhanced
16. admin/MachineCodeManagement

## 长尾批次（P4）

- `scripts/check_hardcoded_styles.py --update-baseline` 输出存量清单
- codemod 映射表自动替换高频字面量（#fff→bg-card、#909399→text-secondary、#f5f7fa→bg-hover、#67c23a→success 等）
- stripe 收敛、EmptyState 替换按目录批量推进，每批 vitest+vue-tsc 合入

## 响应式断点规则

- ≥1920：内容 max-width 1680 居中
- 1440–1919：标准布局（padding 24）
- 1366–1439：sidebar 自动折叠 + padding 16
- <1366：Electron 最小窗口 1280×720 锁定提示
- 缩放 125%/150%：全 px 无错位（禁 rem 混用）

## 每页 8 条通用验收 checklist

1. 栅格间距全部 4pt 倍数且引用 spacing token
2. 颜色零硬编码（守卫脚本通过）
3. 信息三级制：页标题 20 → 卡片标题 16 → 正文 14
4. 空/加载/错误三态齐备（EmptyState/v-loading/el-result）
5. 1366 与 1920 双档截图正常
6. 150% 缩放无错位
7. 交互反馈 ≤ .15s，无入场动画
8. 与同组已精修页并排无违和（圆角/阴影/密度一致）
