# 硬编码颜色存量报告（P4 批次任务队列）

> 生成：`check_hardcoded_styles.py --update-baseline` ｜ 存量 **759 处 / 105 文件**（基线已冻结，只减不增）
> 消化方式：按映射表替换为 `var(--token)` → 跑 vitest+vue-tsc → `--update-baseline` 收紧基线。

## 颜色频次 Top15（映射表依据）

> Top15 字面量合计 371/759 处（约 49%），映射直换即可消化大半。

| 次数 | 字面量 | 建议映射 |
|---|---|---|
| 92 | `#1b4332` | var(--military-dark) / $military-dark（深军绿标题/背景） |
| 57 | `#fff` | var(--color-bg-card) |
| 34 | `#ffffff` | var(--color-bg-card) |
| 29 | `rgba(0, 0, 0, 0.06)` | border-light 或阴影 token 分解 |
| 27 | `#d4af37` | $badge-gold（金色徽章语义保留，可命名 token 化） |
| 21 | `#003366` | dashboard-theme 深蓝 → 建议新 token --color-navy |
| 20 | `#c0c4cc` | 人工审 |
| 14 | `rgba(255, 255, 255, 0.9)` | 人工审 |
| 13 | `#999` | 人工审 |
| 13 | `rgba(0, 0, 0, 0.08)` | 人工审 |
| 11 | `rgba(0, 0, 0, 0.1)` | 人工审 |
| 10 | `#94a3b8` | 人工审 |
| 10 | `rgba(64, 145, 108, 0.3)` | 人工审 |
| 10 | `#000` | 人工审 |
| 10 | `rgba(0, 0, 0, 0.3)` | 人工审 |

## 文件存量 Top20（批次顺序）

| 存量 | 文件 |
|---|---|
| 76 | `frontend/src/layouts/DefaultLayoutSafe.vue` |
| 45 | `frontend/src/views/auth/LoginEnhanced.vue` |
| 42 | `frontend/src/views/admin/AdminDashboard.vue` |
| 31 | `frontend/src/views/ruralWorks/Analysis.vue` |
| 28 | `frontend/src/components/business/SystemStatus.vue` |
| 27 | `frontend/src/views/projects/Import.vue` |
| 25 | `frontend/src/views/system/HealthCheck.vue` |
| 17 | `frontend/src/views/dashboard/InfoRow.vue` |
| 17 | `frontend/src/views/policies/List.vue` |
| 16 | `frontend/src/views/bigscreen/BigScreen.vue` |
| 15 | `frontend/src/views/funds/Report.vue` |
| 14 | `frontend/src/views/funds/Budget.vue` |
| 12 | `frontend/src/views/auth/GetMachineCode.vue` |
| 12 | `frontend/src/views/dashboard/components/QuickActions.vue` |
| 11 | `frontend/src/components/common/ResponsiveDataTable.vue` |
| 10 | `frontend/src/views/analytics/reports/WorkAnalysis.vue` |
| 10 | `frontend/src/views/policies/Category.vue` |
| 10 | `frontend/src/views/system/MonitoringDashboard.vue` |
| 10 | `frontend/src/views/system/SettingsOverview.vue` |
| 9 | `frontend/src/views/auth/ForgotPassword.vue` |

## 批次建议

- **B1（映射直换）**：上表 Top15 字面量机械替换，风险最低、覆盖最大
- **B2（文件攻坚）**：DefaultLayoutSafe/AdminDashboard/LoginEnhanced 三文件占 172 处，逐文件人工过
- **B3（长尾抽检）**：剩余按目录批量 + 20% 抽检截图对比