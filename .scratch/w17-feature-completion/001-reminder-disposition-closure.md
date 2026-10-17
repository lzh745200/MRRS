---
labels: [done, severity-high]
blocks: []
blocked-by: []
---

# 001 提醒中心处置闭环（处理/忽略/延期/重新打开 + 统计 + 前往处理）

**来源**: 2026-10-17 用户指令「按建议逐一执行」，建议一（优先建议 1）。

**现状与顺带修复**: `GET /reminders` 仅列表；`api/v1/reminders.py` 调 `list_reminders(limit=100)`
**未传 user_id**，编排器 fail-closed 逻辑 → 现场恒返回空（本工单一并修复）。
页面仅「刷新 / 立即扫描」两个按钮。

**What to build**
- 新表 `reminder_dispositions`：每提醒一行（`state` open/handled/ignored、`note`、
  `snooze_until`、`acted_at`），迁移 `reminder_disp_001`（幂等建表）。
- 服务 `app/services/reminder_disposition_service.py`：本人校验（fail-closed 404）、
  upsert 处置、`write_work_log` 留痕。
- 端点：`POST /reminders/{id}/handle|ignore|snooze|reopen`（仅接收人本人）。
- `GET /reminders` 返回补 `state/note/snooze_until/entity_id/link`；`include_ignored`
  过滤；`stats`（pending/handled/ignored/snoozed）。
- 前端：`api/reminders.ts` 扩展；提醒中心逐条动作（处理 / 忽略理由 / 延期天数 /
  重新打开 / 前往处理）+ 状态标签 + 过滤页签。

**验收**
- [ ] `GET /reminders` 按 `current_user.id` 真实返回本人提醒（修复恒空缺陷）
- [ ] 处置幂等（重复处理不报错）、越权 404、参数非法 422、非法 id 404
- [ ] 后端新代码行+分支 100%；前端新分支 100%；flake8/vue-tsc/eslint 0
- [ ] 回归：`tests/unit/test_reminders.py`、`test_reminder_round2.py`、
  `test_coverage_gap_batch8.py`、前端 `ReminderCenter.test.ts` 全绿

## Resolution（2026-10-17，已完成）

**变更清单**
- 新表/模型 `ReminderDisposition`（`app/models/reminder_disposition.py`，注册进
  `models/__init__.py` 惰性表）；迁移 `reminder_disp_001_create_table.py`
  （`down_revision = user_session_001`，幂等建表；已验证"空库 create_all 路径"
  与"老库增量迁移路径"schema 等价：inline UNIQUE(message_id) + user_id/state 索引）。
- 新服务 `app/services/reminder_disposition_service.py`（本人 fail-closed 归属校验、
  upsert 处置、处置即已读、写 work_log 留痕且失败不阻断）+ 类型单一来源
  `app/services/reminder_types.py`。
- `reminder_orchestrator`：列表富化 `state/note/snooze_until/acted_at/link/entity_id`，
  未处理优先排序、`include_ignored` 过滤、`summarize_reminders()` 统计；
  `_parse_entity_id()` 解析去重键。
- API `app/api/v1/reminders.py`：**修复恒空缺陷**（`GET /reminders` 现在传
  `current_user.id`）；新增 `POST /{id}/handle|ignore|snooze|reopen`，
  404（越权/不存在）/400（非法天数）/500（泛化文案，不泄露异常原文）。
- 前端 `api/reminders.ts` 扩展 5 个函数 + 类型；`views/reminder/Index.vue`
  增加统计卡、过滤页签（待处理/已处理/已忽略/全部）、逐条动作（前往处理/处理/
  延期/忽略/重新打开）、状态角标与延期时间展示。

**验证证据**
- 后端新增 `tests/unit/test_reminder_disposition.py`（33 例）、
  `tests/unit/api/test_reminder_disposition_api.py`（15 例）；
  相关 6 个测试文件 124 passed；新增/改动模块行+分支 100%；
  flake8（--max-line-length=120 --max-complexity=16）= 0。
- 前端 `ReminderCenter.test.ts`（20 例）+ `api/reminders.test.ts`（10 例）
  30 passed；`src/views/reminder/Index.vue`、`src/api/reminders.ts`
  statements/branches/functions/lines 全 100%；eslint --max-warnings=0 干净；
  `vue-tsc --noEmit` 通过。
- 迁移：`alembic heads` 单 head（reminder_disp_001）；老库路径实测
  user_session_001 → head 升级成功且索引/列与模型 metadata 一致。

