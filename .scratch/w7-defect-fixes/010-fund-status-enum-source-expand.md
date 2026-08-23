---
labels: [ready-for-agent, severity-medium]
blocks: ["w10-enhancements/029-enum-migration-batch2.md"]
blocked-by: ["w0-baseline/001-freeze-baseline.md"]
---

# 010: 状态枚举单一来源·expand（funds 先行）

**What to build:** config/enums.ts FUND_STATUS 补 planned/audited/rejected 四态齐全；funds 三视图（EnhancedList/UserFundList/Report）切换至 enums 单一映射，删除各自私有表。

**Acceptance criteria:**
- [ ] planned/audited/rejected 显示中文（vitest）
- [ ] 三视图状态列无英文裸露
- [ ] enums.ts 增补导出单测
