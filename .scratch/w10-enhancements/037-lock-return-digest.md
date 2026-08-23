---
labels: [ready-for-agent, severity-low]
blocks: []
blocked-by: ["w10-enhancements/032-message-center-tabs-clearall.md"]
---

# 037: 锁屏归来消息摘要

**What to build:** 登录/解锁成功后对比上次活跃时间戳，若有未读增量弹 ElNotification 摘要（N 条新消息）点击直达消息中心；时间戳存 localStorage。

**Acceptance criteria:**
- [ ] 增量>0 弹一条摘要（vitest fake timers）
- [ ] 点击跳转 /message 并清时间戳
- [ ] 首次登录不误弹
