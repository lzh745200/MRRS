---
labels: [ready-for-agent, severity-medium]
blocks: ["w10-enhancements/032-message-center-tabs-clearall.md"]
blocked-by: ["w0-baseline/001-freeze-baseline.md"]
---

# 016: 消息模块瘦身

**What to build:** 注销 messages_extended.py 业务模块注册并归档文件；清理 MessageTemplateService 死引用与 WS 空壳函数；unread_count 幽灵类型声明移除。

**Acceptance criteria:**
- [ ] _BUSINESS_MODULES 无 messages_extended（pytest 导入表断言）
- [ ] 模板死代码删除后消息全链路回归绿
- [ ] MessageCenter 不再多发补偿请求
