# 硬编码颜色存量报告（P4 批次任务队列）

> 生成：`check_hardcoded_styles.py --update-baseline` ｜ 存量 **1156 处 / 123 文件**（基线已冻结，只减不增）
> 消化方式：按映射表替换为 `var(--token)` → 跑 vitest+vue-tsc → `--update-baseline` 收紧基线。

## 颜色频次 Top15（映射表依据）

> Top15 字面量合计 656/1156 处（约 57%），映射直换即可消化大半。

| 次数 | 字面量 | 建议映射 |
|---|---|---|
| 136 | `#1b4332` | var(--military-dark) / $military-dark（深军绿标题/背景） |
| 75 | `#303133` | var(--color-text-primary)（EP 主文字） |
| 57 | `#fff` | var(--color-bg-card) |
| 51 | `#666` | var(--color-text-secondary) |
| 48 | `#606266` | var(--color-text-regular) |
| 41 | `#f5f7fa` | var(--color-bg-hover) |
| 35 | `#d4af37` | $badge-gold（金色徽章语义保留，可命名 token 化） |
| 34 | `#ffffff` | var(--color-bg-card) |
| 32 | `#e4e7ed` | var(--color-border-light) |
| 29 | `rgba(0, 0, 0, 0.06)` | border-light 或阴影 token 分解 |
| 26 | `#2d6a4f` | var(--color-primary) |
| 25 | `#40916c` | var(--color-primary-light-1) |
| 25 | `#f0f0f0` | var(--color-bg-hover) |
| 21 | `#ebeef5` | var(--color-border-light) |
| 21 | `#003366` | dashboard-theme 深蓝 → 建议新 token --color-navy |

## 文件存量 Top20（批次顺序）

| 存量 | 文件 |
|---|---|
| 77 | `frontend/src/layouts/DefaultLayoutSafe.vue` |
| 50 | `frontend/src/views/admin/AdminDashboard.vue` |
| 45 | `frontend/src/views/auth/LoginEnhanced.vue` |
| 36 | `frontend/src/views/ruralWorks/Analysis.vue` |
| 33 | `frontend/src/views/projects/Import.vue` |
| 33 | `frontend/src/views/system/HealthCheck.vue` |
| 29 | `frontend/src/components/business/SystemStatus.vue` |
| 29 | `frontend/src/views/auth/GetMachineCode.vue` |
| 25 | `frontend/src/views/policies/List.vue` |
| 21 | `frontend/src/views/dashboard/InfoRow.vue` |
| 21 | `frontend/src/views/system/SettingsOverview.vue` |
| 19 | `frontend/src/views/funds/Budget.vue` |
| 19 | `frontend/src/views/ruralWorks/Task.vue` |
| 19 | `frontend/src/views/system/MonitoringDashboard.vue` |
| 18 | `frontend/src/views/auth/ForgotPassword.vue` |
| 18 | `frontend/src/views/funds/Report.vue` |
| 18 | `frontend/src/views/schools/Detail.vue` |
| 17 | `frontend/src/views/auth/Profile.vue` |
| 17 | `frontend/src/views/help/HelpCenter.vue` |
| 16 | `frontend/src/views/bigscreen/BigScreen.vue` |

## 批次建议

- **B1（映射直换）**：上表 Top15 字面量机械替换，风险最低、覆盖最大
- **B2（文件攻坚）**：DefaultLayoutSafe/AdminDashboard/LoginEnhanced 三文件占 172 处，逐文件人工过
- **B3（长尾抽检）**：剩余按目录批量 + 20% 抽检截图对比