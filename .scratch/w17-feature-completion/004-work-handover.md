---
labels: [done, severity-high]
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
- [x] 移交在单事务内完成，失败全量回滚；跨组织目标拒绝（数据域 fail-closed）
- [x] 执行后原责任人工作台/待办清空、接任人可见
- [x] 审计留痕（移交人、接任人、逐项清单）
- [x] 覆盖率与门禁全绿

## Resolution（2026-10-17，W19 完成）

**后端**（2 个新模块 + 2 个测试文件）
- `app/services/handover_service.py`：清单统计（村 `created_by` / 项目 / 待办 / 审批中申请，统一走
  `filter_by_data_scope`）、接任人校验（不存在/停用 404、本人 422、跨组织或组织缺失 403、超管豁免）、
  单事务执行（归属改写 + 审批转交留痕 + 双方站内消息 + `write_work_log` 审计）、历史回放。
- `app/api/v1/handover.py`：`GET /handover/inventory`、`GET /handover/candidates`、
  `POST /handover/execute`（伪造/越权 ID → 403；批量行数不一致 → 409；失败全量回滚）、`GET /handover/history`。
- **历史由 WorkLog 承载**（log_type=handover，快照 JSON 存 attachments），不新增表/迁移。

**前端**
- `src/api/handover.ts` + `src/views/handover/Index.vue`（分组勾选 → 选接任人 → 确认执行 → 交接单弹窗
  与 PDF 导出；移交历史回放/导出/分页）；路由 `/handover`、menu-config、侧边栏、后端 `MENU_DEFINITIONS` 同步。

**验证**：新增后端 85 项测试全绿、service 283 stmts/108 branches 100%、API 28 stmts 100%；
前端 21 项测试、两文件四指标 100%；flake8 0；vue-tsc 0；eslint 0；硬编码样式棘轮 345/345 NEW=0。
