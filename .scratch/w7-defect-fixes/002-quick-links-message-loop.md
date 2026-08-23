---
labels: [done, severity-high]
blocks: ["w9-chain-completion/020-milestone-wiring.md"]
blocked-by: ["w0-baseline/001-freeze-baseline.md"]
---

# 002: 快捷入口与消息链接闭环

**What to build:** 工作台 QuickActions「资金周期」→/funds/lifecycle、「经费结算」→/funds/settlement；异常通知 link 由 /funds/anomalies 改 /funds/anomaly；审批推送写 link 字段使消息可点击直达对应实体详情。

**Acceptance criteria:**
- [ ] QuickActions 两个按钮路由正确且 vitest 断言
- [ ] backup_scheduler 异常通知 link 指向真实路由
- [ ] approval 提交/通过/驳回三类消息均带 link 字段（pytest）
- [ ] 消息中心点击审批通知可跳转目标页

## Resolution（v1.10.0）
快捷路由/消息link全链路修复并测试
