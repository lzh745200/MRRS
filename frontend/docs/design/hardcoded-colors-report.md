# 硬编码颜色存量报告（P4 批次任务队列）

> 生成：`check_hardcoded_styles.py --update-baseline` ｜ 存量 **660 处 / 103 文件**（基线已冻结，只减不增）
> 消化方式：按映射表替换为 `var(--token)` → 跑 vitest+vue-tsc → `--update-baseline` 收紧基线。

## 颜色频次 Top15（映射表依据）

> Top15 字面量合计 285/660 处（约 43%），映射直换即可消化大半。

| 次数 | 字面量 | 建议映射 |
|---|---|---|
| 92 | `#1b4332` | var(--military-dark) / $military-dark（深军绿标题/背景） |
| 29 | `rgba(0, 0, 0, 0.06)` | border-light 或阴影 token 分解 |
| 27 | `#d4af37` | $badge-gold（金色徽章语义保留，可命名 token 化） |
| 20 | `#c0c4cc` | 人工审 |
| 14 | `rgba(255, 255, 255, 0.9)` | 人工审 |
| 13 | `#999` | 人工审 |
| 13 | `rgba(0, 0, 0, 0.08)` | 人工审 |
| 11 | `rgba(0, 0, 0, 0.1)` | 人工审 |
| 10 | `#94a3b8` | 人工审 |
| 10 | `rgba(64, 145, 108, 0.3)` | 人工审 |
| 10 | `#000` | 人工审 |
| 10 | `#fff` | var(--color-bg-card) |
| 10 | `rgba(0, 0, 0, 0.3)` | 人工审 |
| 8 | `#64748b` | 人工审 |
| 8 | `#fafafa` | 人工审 |

## 文件存量 Top20（批次顺序）

| 存量 | 文件 |
|---|---|
| 68 | `frontend/src/layouts/DefaultLayoutSafe.vue` |
| 43 | `frontend/src/views/auth/LoginEnhanced.vue` |
| 42 | `frontend/src/views/admin/AdminDashboard.vue` |
| 28 | `frontend/src/components/business/SystemStatus.vue` |
| 21 | `frontend/src/views/system/HealthCheck.vue` |
| 19 | `frontend/src/views/ruralWorks/Analysis.vue` |
| 16 | `frontend/src/views/bigscreen/BigScreen.vue` |
| 16 | `frontend/src/views/policies/List.vue` |
| 15 | `frontend/src/views/dashboard/InfoRow.vue` |
| 15 | `frontend/src/views/projects/Import.vue` |
| 14 | `frontend/src/views/funds/Budget.vue` |
| 12 | `frontend/src/views/auth/GetMachineCode.vue` |
| 11 | `frontend/src/views/dashboard/components/QuickActions.vue` |
| 10 | `frontend/src/components/common/ResponsiveDataTable.vue` |
| 10 | `frontend/src/views/funds/Report.vue` |
| 10 | `frontend/src/views/system/MonitoringDashboard.vue` |
| 9 | `frontend/src/views/analytics/reports/WorkAnalysis.vue` |
| 9 | `frontend/src/views/auth/ForgotPassword.vue` |
| 9 | `frontend/src/views/funds/Detail.vue` |
| 9 | `frontend/src/views/schools/Detail.vue` |

## 批次建议

- **B1（映射直换）**：上表 Top15 字面量机械替换，风险最低、覆盖最大
- **B2（文件攻坚）**：DefaultLayoutSafe/AdminDashboard/LoginEnhanced 三文件占 172 处，逐文件人工过
- **B3（长尾抽检）**：剩余按目录批量 + 20% 抽检截图对比


## 已知视觉变化（2026-08-26 语义化批次，待设计评审确认）

> commit 9057b434 将灰阶/边框字面量按**语义阶梯**映射（非像素保持），
> 默认军绿主题下以下取值发生可见偏移（light 主题下值完全一致）：

- #999 / #909399 → ar(--color-text-secondary) = #64748b（更深、偏蓝）
- #c0c4cc → ar(--color-text-placeholder) = #94a3b8
- #dcdfe6 → ar(--color-border) = #cbd5e1；#fafafa → ar(--color-bg-hover) = #f0f4f0
- 认证四页（LoginEnhanced/Register/ForgotPassword/GetMachineCode）改走 token 后，
  light 主题下跟随主色变蓝，不再恒定军绿

若设计评审判定需回退像素保持，仅需将上述映射反向替换为字面量并收紧基线。
状态点灰色已采纳 review 建议改用 --color-text-disabled（两主题像素等同）。
