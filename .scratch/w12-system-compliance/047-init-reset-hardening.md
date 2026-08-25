---
labels: [done, severity-high]
blocks: []
blocked-by: ["w0-baseline/001-freeze-baseline.md"]
---

# 047: 初始化/重置防护强化

**What to build:** /init/reset 增加 admin 密码校验（PasswordPolicy.verify）；/init/status|checklist 供前端潜在向导预留（本期不做向导页，YAGNI 记录于票）。

**Acceptance criteria:**
- [ ] 错密码 403（pytest）
- [ ] confirm=RESET+密码双因子才放行
- [ ] 审计留痕断言

## Resolution（v1.10.0 续批4）
reset 增加 admin_password Query 参数，verify_password fail-closed(403)；confirm 先行顺序不变；4用例(缺密码/错密码/正确通过/confirm先行)全绿。前端向导页按YAGNI未做(工单内已声明)
