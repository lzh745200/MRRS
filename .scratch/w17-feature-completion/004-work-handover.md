---
labels: [ready-for-agent, severity-high]
blocks: []
blocked-by: ["w17-feature-completion/001-reminder-disposition-closure.md"]
---

# 004 工作移交（人员轮换：我负责的村/项目/待办/提醒责任人一键交接）

**来源**: 2026-10-17 用户指令「按建议逐一执行」，建议四（优先建议 4）。

**现状**: 全仓无移交/接任功能；审批转交仅覆盖审批任务；用户删除是级联清理而非交接。

**What to build**
- 服务 `handover_service`：统计「我负责/我发起」的资产清单（村 `created_by`/
  负责人字段、项目、待办、审批中申请、提醒接收人如可改）。
- API：`GET /handover/inventory`（预览清单）、`POST /handover/execute`
  （目标用户、范围勾选、备注）→ 事务内批量改归属 + 双方站内消息 + 审计留痕；
  `GET /handover/history`。
- 前端：个人中心/系统管理入口「工作移交」页：清单勾选 → 选择接任人 → 确认执行；
  交接单导出（Excel/PDF 至少其一）。

**验收**
- [ ] 移交在单事务内完成，失败全量回滚；跨组织目标拒绝（数据域 fail-closed）
- [ ] 执行后原责任人工作台/待办清空、接任人可见
- [ ] 审计留痕（移交人、接任人、逐项清单）
- [ ] 覆盖率与门禁全绿
