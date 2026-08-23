---
labels: [ready-for-agent, severity-high]
blocks: ["w12-system-compliance/044-backup-unify-truth-source.md"]
blocked-by: ["w7-defect-fixes/010-fund-status-enum-source-expand.md"]
---

# 022: 预算预警接入与三级化

**What to build:** 后端阈值扩为 80/90/100 三级（100% 拦截交易写入 fail-closed）；Budget.vue 顶部预警条调 alerts 接口；废弃本地 70/90 配色档统一语义色。

**Acceptance criteria:**
- [ ] 三级阈值 pytest（80 提醒/90 警告/100 拒绝）
- [ ] 100% 后 createTransaction 返回 4xx 且不入库
- [ ] Budget 预警条三态样式 vitest
- [ ] ADR-0009 落稿
