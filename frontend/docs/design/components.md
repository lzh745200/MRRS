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

## 2. KpiCard（`components/business/KpiCard.vue`）

统计卡纯展示组件。

```vue
<KpiCard label="帮扶村" :value="stats.villages" :trend="trends.villages"
         trend-label="较上月" icon="OfficeBuilding" to="/villages" />
```

- 数值 24px semibold mono 千分位；null → `--`
- 趋势语义：升=绿 `Top`、降=红 `Bottom`、0=持平；
  **负向指标**（异常数/超期数）传 `invert-trend` 反转颜色
- `theme`: primary/success/warning/danger/info 图标底色变体
- `to` 可选点击跳转（走 pushSafe）

## 3. Dialog 弹窗

- 宽度只用 `DIALOG_SM/MD/LG`（`config/dialog.ts`），禁魔法数：

```vue
<el-dialog v-model="visible" :width="DIALOG_MD" align-center destroy-on-close>
```

- 底部按钮右对齐：`[取消][主操作]`，主操作 loading 态必接
- 内嵌表格选择器用 LG 并注释业务豁免原因

## 4. Table 表格

- 全局 small 已生效，无需逐个声明；表头底色 bg-hover、文字 secondary
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
- 日期时间只允许 `utils/datetime.ts` 具名格式（8 个），
  ESLint 视图层新增本地 formatDate 定义会被 review 打回
