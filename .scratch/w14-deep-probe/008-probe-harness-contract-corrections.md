---
labels: [done, severity-info]
blocks: []
blocked-by: []
---

# 探针脚本契约纠偏（run-5/6/7：把 21 个探针从"恒报假失败"改成可信回归基线）

**来源**: 2026-09-14 全面排查批次（真实 HTTP 探测复跑 + 逐条判定）

## 背景

`.scratch/probe-r1/*.py` 探针脚本早期由多轮探测边写边改，断言里混入了大量
"猜测的契约"（错误路径、错误响应形态、错误必填项、错误凭据族），导致每轮复跑
都有 15~30 项 `[FAIL]` 与真实缺陷混杂，需要人工逐条甄别。本轮把这些断言逐条与
**后端实现 + 前端调用方**对齐，使探针套件成为可信基线。

## 纠偏清单（每条都附真实契约的代码依据）

| 探针 | 原断言（错） | 真实契约 | 依据 |
|---|---|---|---|
| probe_auth | must_change_password 取 data/user 内层 | 信封**顶层** | `frontend/src/stores/auth.ts:192-197` |
| probe_auth | openapi.json 必须 200 | 仅 DEBUG 下挂载，生产 404 属设计 | `backend/app/main.py:117` |
| probe_reports_stats | `/monitoring/*` | `/api/v1/system/monitor/*` | `monitor.py:23`、`api/systemMonitor.ts` |
| probe_packages_sync | 导出/导入取 `data.package_id` | **扁平** `package_id` | `data_packages.py` export/import 返回体 |
| probe_packages_sync | 同步包回传直接用 package_name | 下载端点补 `.zip`，上传按扩展名白名单 | `data_sync.py:46,176-186` |
| probe_report_templates | 创建取 `data.id` | **扁平** `{id,...}` | 端点返回体 |
| probe_report_templates | `POST /{id}/generate` 期望 200 | 该路由**不存在**（生成入口 `/analytics/generate-report`） | `api/analytics.ts:179` |
| probe_projects | 上传取 `data.id` | `data.files[0].id` | 端点返回体 |
| probe_schools | 附件删除用嵌套路径 | 扁平 `DELETE /schools/attachments/{id}` | `school.py:617`、`api/schools.ts:67` |
| probe_users_orgs | 重置密码空体 | 必填 `new_password` | `AdminResetPasswordBody` |
| probe_users_orgs | 头像字段名 `file` | `avatar` | `users.py:839` |
| probe_dashboard_messages | 动态创建只给 title/description | 必填 `action`/`target` | `dashboard.py:719-724` |
| probe_dashboard_messages | PUT 非 custom_ 动态期望 404 | 按系统动态处理：200 +「无法更新…」 | `dashboard.py:772-806` |
| probe_dashboard_messages | `DELETE /messages` 空体 | 必填 `message_ids`（min_length=1） | `messages.py:79-82` |
| probe_system_backup_audit | 备份计划漏传 `enabled` | `enabled` 必填 | 备份计划 Schema |
| probe_system_backup_audit | 恢复后仍断言原备份删除 | 恢复已替换库 → 改用恢复后新建的备份 | backup upload-restore 语义 |
| probe_approval_budgets | remind 恒期望 200 | 无审批人时如实 400 | 端点守卫 |
| probe_approval_budgets | 重复 approve 只接受 400/409 | 权限校验先行 → 403 亦为合法拒绝 | 端点顺序 |
| probe_approval_budgets | 预算/事务取 `data.id`；事务漏必填 | 扁平 `id`；必填 `purpose/transaction_type/transaction_date` | 预算 Schema |
| probe_policies | 上传 `.txt` 期望 200 | 白名单 `pdf/doc/docx/pptx` | `policy.py:905` |
| probe_funds* | 未传必需要件直接流转 | approve 需 ≥1 附件；allocate 需 `contract`+`allocation_order` | `funds.py:923,984` |
| probe_funds* | category 塞 multipart `data=` | category 是**查询参数** | `funds.py:1428`、`funds/Detail.vue:946-950` |
| probe_funds/_v2 | 清理删除恒期望 200 | 仅 `pending` 可删（400 是正当守卫） | 状态机 |

## 结果（2026-09-14 复跑）

全部 21 个脚本 **0 失败**（approval_budgets 34/34、users_orgs 42/42、policies 41/41、
packages_sync 27/27、dashboard_messages 26/26、system_backup_audit 25/25、
funds 31/31、projects 22/22、schools 19/19、funds_v2 13/13、funds_flow 9/9、
report_templates 9/9、auth_flow 8/8、auth 22/22、villages 26/26 ……）。

**本轮探测未发现新的产品缺陷**：真实产品缺陷（R14 组织树 path/level 缺失致导出恒 403）
已在上一批次修复，其余 `[FAIL]` 全部为探针侧断言错误。
