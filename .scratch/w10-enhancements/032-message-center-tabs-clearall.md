---
labels: [ready-for-agent, severity-medium]
blocks: ["w10-enhancements/037-lock-return-digest.md"]
blocked-by: ["w8-dead-code/016-message-module-slimming.md"]
---

# 032: 消息中心分类 Tab 与清空能力

**What to build:** 类型筛选升级 Tab（全部/审批/系统/待办/备份）；接通清空已读 DELETE /messages/read 与全部删除（带确认）；详情弹窗关联链接可达。

**Acceptance criteria:**
- [ ] Tab 切换过滤正确（vitest）
- [ ] 清空已读后 unread-count 归零联动
- [ ] 全部删除需二次确认且分页重置
