---
labels: [ready-for-agent, severity-medium]
blocks: ["w11-ui-consistency/039-ep-gray-tokenize-batches.md"]
blocked-by: ["w0-baseline/001-freeze-baseline.md"]
---

# 038: Top10 硬编码文件 Token 化

**What to build:** AdminDashboard/ruralWorks Analysis/analytics Dashboard/DefaultLayoutSafe/projects Import/HealthCheck/SystemStatus/ReportExport/GetMachineCode/schools List 十文件 hex→SCSS 变量（$color-primary-dark/$color-gold 等 tokens-vars 注入体系）。

**Acceptance criteria:**
- [ ] 十文件 grep 目标色值归零
- [ ] 视觉回归：构建产物类名/规则数无明显异常
- [ ] vitest 全量绿
