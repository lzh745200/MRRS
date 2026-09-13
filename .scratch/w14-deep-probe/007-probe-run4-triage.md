---
labels: [done, severity-info]
blocks: []
blocked-by: []
---

# 真实 HTTP 探测 run-4 失败判定（2026-09-13）

| 项 | 值 |
|---|---|
| 被探测代码 | `972c534a`（R12 批量 + R7 维护窗口 + R2 残余无界读取清零 + P-1~P-3 门禁） |
| 服务实例 | `backend/.venv/Scripts/python.exe start.py`，`DATABASE_URL=backend/data/probe_r13d_*.db`（探针专用库，非生产库） |
| 探针脚本 | `.scratch/probe-r1/probe_*.py`（21 个，真实 HTTP） |
| 执行顺序 | 凭据分两族：`Admin@2026`（auth / approval_budgets / dashboard_* / packages_sync / policies / policy_upload / reports_stats / report_templates / system_backup_audit / users_orgs*）→ `probe_auth_flow`（首登改密，密码变为 `Probe#R1-2026x`）→ 其余 8 个 |
| 运行环境注意 | 登录限速 5 次/分钟（`auth.py:37`）+ 连续失败 5 次锁定 30 分钟（`lockout_service`）—— 探针必须按凭据分族、按 ≥20s 间隔执行，否则整轮被 429/423 淹没 |

## 结论

**本轮未发现新的产品缺陷。** 15 项 FAIL 全部可归为两类：

1. **探针脚本自身缺陷**（错误期望 / 错误路径 / 错误字段名 / 错误凭据族）；
2. **有意的契约行为**（资金状态机文档要求、数据域 fail-closed、扩展名白名单、系统动态不可改）。

下表逐条给出判定依据（含代码位置）。

| 探针 | FAIL 项 | 判定 | 依据 |
|---|---|---|---|
| probe_auth_flow | 新密码登录 429 | 探针缺陷（限速） | 登录限速 5 次/分钟 `auth.py:37`；该脚本自身连打 4 次登录 |
| probe_funds | approve/allocate/start-use/complete 400 | **有意契约** | `funds.py:862` 审批需附件、`:872` 拨付需「合同, 分配令」；`tests/probe/probe_r3_funds_state_yearly_rbac.py:94` 明确断言缺分配令被拒 |
| probe_funds_v2 / _flow | 同上 + 状态历史仅 1 条 | **有意契约**（级联） | 前序流转被文档要求拦下，状态历史自然只有 1 条 |
| probe_schools | DELETE 附件 405 | 探针缺陷（路径） | 后端与前端一致用扁平路径 `DELETE /schools/attachments/{id}`（`school.py:617`、`frontend/src/api/schools.ts:67`）；探针误用嵌套路径 |
| probe_approval_budgets | remind 400「未分配审批人」 | 探针缺陷（前置） | 探针自建流程未指定审批人，任务无审批人可提醒 |
| probe_approval_budgets | 重复 approve 403 | **有意契约** | 二次审批先过权限校验（`无权限审批此任务`），403 属合法拒绝；探针只接受 400/409 |
| probe_approval_budgets | 创建预算「失败」 | 探针缺陷（取值） | 实际 200 且返回扁平 `{"id":1,...}`；探针按 `data.id` 取值 |
| probe_dashboard_messages | POST recent-activities 422 | 探针缺陷（体） | `ActivityCreate` 要求 `action`/`target` 等字段 |
| probe_dashboard_messages | PUT 不存在动态 → 200 | **有意契约** | `dashboard.py:772-806`：非 `custom_` 前缀按系统动态处理，返回 200「无法更新系统自动生成的动态」；DELETE `:815-851` 同构（写隐藏表） |
| probe_dashboard_messages | DELETE /messages 422 | 探针缺陷（体） | 端点要求 `message_ids` |
| probe_packages_sync | export 403 | **有意契约（fail-closed）** | 管理员未挂组织时数据域拒绝跨组织导出（ADR-0002） |
| probe_packages_sync | import 400 扩展名 | 探针缺陷（已修） | export 返回的 `package_name` 不含扩展名（下载端点补 `.zip`/`.rrs`，`data_sync.py:176-186`），上传侧按白名单校验 `data_sync.py:46` |
| probe_policies | 上传 .txt 被拒 400 | **有意契约** | 政策导入仅接受 Excel（`upload_helper.py:338` 白名单） |
| probe_policies | 政策下载 404 | 级联 | 上传失败 → 无政策可下载 |
| probe_reports_stats | `/monitoring/*` 404 | 探针缺陷（已修） | 真实路由为 `/api/v1/system/monitor/*`（`monitor.py:23`，前端 `systemMonitor.ts`） |
| probe_report_templates | 创建模板「失败」 | 探针缺陷（取值） | 实际 200 且返回扁平 `{"id":1,...}` |
| probe_system_backup_audit | PUT schedule 422 | 探针缺陷（体） | `enabled` 为必填 |
| probe_system_backup_audit | DELETE 备份 404 / 预览 200 | 探针缺陷（前置） | 探针未先创建备份，目标文件名不存在，删除 404 与预览 200 均因此成立 |
| probe_users_orgs | 重置密码 422 / 头像 422 | 探针缺陷（体/字段名） | 重置密码需 `new_password`；头像端点字段名为 `avatar`（`users.py:839`），探针发的是 `file` |

## 已随本轮修复的探针脚本

- `probe_auth.py`：`must_change_password` 取信封顶层（原查内层恒 None）；`openapi.json` 按 DEBUG 口径（生产态 404 属设计）。
- `probe_reports_stats.py`：`/monitoring/*` → `/system/monitor/*`。
- `probe_packages_sync.py`：同步包回传文件名补 `.zip`。

## 待修的探针脚本（不阻断产品结论）

`probe_approval_budgets`、`probe_dashboard_messages`、`probe_funds*`（补文档/附件后重试）、
`probe_policies`（改用 .xlsx 样本）、`probe_report_templates`、`probe_schools`（扁平附件路径）、
`probe_system_backup_audit`（先建备份再删）、`probe_users_orgs`（字段名/必填项）。
建议下一轮按「凭据分族 + ≥20s 间隔 + 断言真实契约」三原则统一整改后再作为回归基线。

## Resolution

- 2026-09-13 完成 run-4 全量探测（21 个脚本）+ 逐条判定（上表）。
- **本轮发现并修复 1 个真实产品缺陷**：新建组织 path/level 缺失导致组织级数据权限
  恒拒（管理员无法导出数据包）——见 backend/app/api/v1/organization.py、
  backend/app/services/organization_service.py、backend/app/startup/monitors.py 与
  backend/tests/unit/test_org_tree_metadata_r14.py；真实 HTTP 复验由 403 → 200。
- 探针脚本纠偏：probe_auth.py（信封顶层 must_change_password / DEBUG 口径 openapi）、
  probe_reports_stats.py（/monitoring/* → /system/monitor/*）、
  probe_packages_sync.py（同步包回传补 .zip）。
- 其余 14 项判定为探针脚本自身缺陷（断言期望/路径/字段名/前置数据）或有意的契约行为，
  依据见上表；不构成产品缺陷，无需改码。
