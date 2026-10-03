# 组件规范 v2.0

> 标准件优先复用；新页面禁止手写页头/统计卡/空态的私有实现。

## 1. PageHeader（`components/common/PageHeader.vue`）

页面唯一页头实现（替代各页 30+ 种手写标题区）。

```vue
<PageHeader title="经费管理" subtitle="管理帮扶经费记录，跟踪资金流向">
  <el-button type="primary">新增经费</el-button>   <!-- 主操作唯一且右置 -->
</PageHeader>
```

- `title` 必填 / `subtitle` 一句话说明本页职责
- `showBack + backTo`：详情/编辑页返回态
- `#metrics` 插槽：标题下度量行
- 字号 20/semibold，副题 13/secondary —— 全 token 驱动

## 2. StatsCard（`components/common/StatsCard.vue`）

统计卡纯展示组件（**工作台 KPI 行**由页面级组件 `views/dashboard/KpiCards.vue` 组装使用）。

```vue
<StatsCard title="帮扶村" :value="stats.villages" :trend="trends.villages"
           subtitle="较上月" :icon="OfficeBuilding" type="primary" suffix="个" />
```

- 属性：`title`(必填) / `value`(必填) / `subtitle?` / `icon?` / `type?`(primary|success|warning|danger|info) / `trend?` / `prefix?` / `suffix?`
- 数值 24px semibold mono 千分位；空值统一走 `@/utils` 的 `format` 兜底
- 趋势语义：升=绿 `Top`、降=红 `Bottom`、0=持平；
  **负向指标**（异常数/超期数）需在页面侧自行决定颜色语义
- 图标底色由 `type` 决定

> ⚠️ **本文档曾经过期**：早期版本写的是 `components/business/KpiCard.vue`，该文件**不存在**
> （`components/business/` 实际只有 `EmptyState/`、`FundGuidePopover.vue`、`SystemStatus.vue`）。
> 工作台的 KPI 行实为 `views/dashboard/KpiCards.vue`，请以此为准。

## 3. Dialog 弹窗

- 宽度只用 `DIALOG_SM/MD/LG`（`config/dialog.ts`），禁魔法数：

```vue
<el-dialog v-model="visible" :width="DIALOG_MD" align-center destroy-on-close>
```

- 底部按钮右对齐：`[取消][主操作]`，主操作 loading 态必接
- 内嵌表格选择器用 LG 并注释业务豁免原因

## 4. Table 表格

- 全局组件尺寸 `large` 已在 `App.vue` 的 `el-config-provider` 固化，无需逐个声明；表头底色 bg-hover、文字 secondary
- **stripe 仅当可见列 ≥6** 时使用（81 处存量按此规则消化）
- 空态必须 `<EmptyState>`（business 组件），54 处 el-empty 渐进替换
- 操作列固定右侧，宽 ≤180；长表格横向滚动兜底 min-width

## 5. Form 表单

- label-width 两档：100（默认）/120（长标签）；对齐 `--form-label-width`
- 控件宽三档：full / 360 / 240；日期范围统一 380
- 分组用 section 卡片；底部操作条 sticky（T3 模板）

## 6. EmptyState 空态

- 列表无数据：`type="list" text="暂无xx记录"` + 去添加引导 action
- 分析图表空数据：显示空态而非全 0 图
- Dashboard ChartRow 文本 div 占位一律替换

## 7. 动效红线

- 只允许 hover/fade/slide 的 `transition-fast .15s` 过渡
- **禁入场动画**（低配机红线）；骨架屏仅 Dashboard 一处

## 8. 图标与日期

- 图标统一 `@element-plus/icons-vue`，16/18 两档，禁 emoji
- **日期时间只允许走 `@/utils` 的 `format`**（唯一实现，见 `src/utils/index.ts`）：
  `formatDateTime` / `formatDateTimeLocale` / `formatLocalDate` / `formatLocalDate2Digit` /
  `formatLocalDateTime2Digit` / `formatDate` / `formatDateTimeFull` / `formatCnDate` /
  `formatRelativeTime` / `formatShortDateTime` / `formatShortDateTimePadded` / `formatDuration`。
  2026-10-03 已把此前散落在 36 个文件里的 41 处本地实现全部收敛到这里；
  视图层**不要再新写** `formatDate` / `formatDateTime` 之类的本地函数
