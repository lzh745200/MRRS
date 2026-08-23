---
labels: [ready-for-agent, severity-low]
blocks: ["w8-dead-code/016-message-module-slimming.md"]
blocked-by: ["w0-baseline/001-freeze-baseline.md"]
---

# 018: 微冗余清扫包

**What to build:** 学校旧奖学金导入端点标记 deprecated 注释转发；getPolicyTypes/getLevelOptions 去重；YearlyIndex 过渡页移除（列表直达年度总览）；UserPermissions.vue 下线重定向；fetchRoles 空函数、ChartRow summary=true 幽灵参数清理。

**Acceptance criteria:**
- [ ] 各清理点 grep 零残留
- [ ] 相关页面功能回归绿
- [ ] 政策/学校 API 行为不变（既有测试通过）
