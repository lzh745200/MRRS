# MRRS 后端审计报告（W25 · backend/app/）

- 审计范围：`backend/app/`（FastAPI 后端全量）
- 审计方式：实际读代码 + 静态扫描器 + 运行时复现（SQLite in-memory）
- 审计日期：2026-10-20
- 运行环境：`backend\.venv\Scripts\python.exe`（Python 3.11 / SQLAlchemy 2.x）
- 参照基线：`CLAUDE.md`、`CONTEXT.md`（不变量 1–7、指标字典）、`docs/adr/0002/0003/0005`

> 已排除的历史已修复项（不再重复报告）：i18n 清除、菜单单一源、households legacy key、
> `villages` 表删除、ErrorBoundary 单根元素、软删除 `include_deleted` 收敛、
> `admin_full_access` 开关收口（R27-H8）、`check_record_access` NULL fail-closed（M40）、
> 裸 SQL 拼接豁免登记（`check_raw_sql_fstrings.py` 全绿）、`os._exit`、上传限长门禁。

---

## 一、问题清单

| # | 严重度 | 位置(文件:行) | 问题 | 影响 | 修复建议 |
|---|--------|---------------|------|------|----------|
| 1 | **P0** | `backend/app/core/data_permission.py:399`（`get_org_scope`） | 部门级 `admin`（`role=admin` 且 `is_superuser=False`）被 `get_org_scope` 判定为 `is_admin=True` → `OrgScopeFilter(is_admin=True)`，`filter_by_org_ids()` **直接 return query 不加任何 WHERE**。与 `apply_scope_filter`（严格口径，默认收敛本组织及子树）形成**两条冲突口径**。 | 部署在**总部/分部级**的 `admin` 通过直接调用 API 即可读取**全部组织**的一户一档、影像库、消费帮扶、学校、地图、大屏、结对、捐赠、帮扶村列表与导出。违反 CONTEXT.md 不变量 1 与军审红线 S2。已运行时复现（见下）。 | `get_org_scope` 的 admin 分支改为复用 `apply_scope_filter` 的严格口径（部门级 admin → 本组织及子树），仅 `super_admin`/`is_superuser`/`data_scope=="all"` 才 `is_admin=True`；或让 `OrgScopeFilter` 增加 `org_ids` 约束而非 `is_admin` 短路。同步修正 `dashboard.py:184/450` 的 `has_full_access()` 分支语义。 |
| 2 | **P0** | `backend/app/api/v1/data/data/statistics.py:790-797`（`_get_analysis_data_impl`） | `active_projects` 统计 **完全未接数据域过滤**（`db.query(Project).filter(...)` 直查），而同函数内 `total_villages`/`mil_total`/`loc_total` 都走 `_scoped(...)`。 | 任意登录用户（`user`/`viewer`）调 `GET /api/v1/data/statistics/analysis` 即可获知**全库**在执行/已批准/活跃项目的数量——跨组织规模泄漏，且与同响应内其它已隔离指标口径矛盾。 | 给 `active_projects` 套 `_scoped(db.query(Project)..., SupportedVillage)`（该函数 `_scoped` 固定绑 `SupportedVillage` 模型，需改为接受 model 参数或直接用 `apply_scope_filter(q, current_user, Project, db=db)`）。 |
| 3 | **P1** | `backend/app/api/v1/consumption.py:190-212`、`backend/app/services/consumption_service.py:172-202` | 消费帮扶台账的**写路径**不接数据域：`get_consumption_or_404()` 用 `require_data_permission()`（仅比 `organization_id`/`created_by`），`ensure_village_accessible()` 同样；而 `require_data_permission` 对 `organization_id is None` 的记录 **只判 `created_by`**（`data_permission.py:249-254`）。 | ① 任何登录用户可 `POST /consumption` 在**任意帮扶村**建台账（`ensure_village_accessible` 对 `organization_id=None` 的村只判 `created_by`，而多数村 `created_by` 为管理员 → 普通用户 403，但 `organization_id` 为 NULL 的村仍可通过 `created_by` 命中绕过）；② `update`/`delete` 只按记录级 `created_by` 判，跨组织的他人记录（`organization_id` 有值且≠本人组织）靠 `require_data_permission` 拦截，但**本组织外的 NULL-organization 记录**只要 `created_by` 匹配即可读写。 | 消费帮扶写路径统一改走 `consumption_base_query(db, data_scope)` + `get_org_scope`（与列表/统计同口径），点查越权一律 404（不泄露存在性）。 |
| 4 | **P1** | `backend/app/api/v1/media.py:135-157` → `backend/app/services/media_service.py:325-341` | 影像库 `PUT/DELETE /media/photos/{id}` **没有 `data_scope` 依赖**，走 `get_photo()` → `require_data_permission()`。`require_data_permission` 对 `organization_id=None` 的归档只判 `created_by`；对 `organization_id` 有值的归档，判定是「同组织 OR 同创建人」，**部门级 admin 也被限制在本组织**，与列表端（`get_org_scope` 放行全量）口径相反。 | ① 同一用户在列表能看到 N 条记录，在详情/编辑却 404/403（口径分裂，用户可见的不一致）；② `organization_id` 为 NULL 的归档，任意用户只要 `created_by` 匹配即可改删。 | `update_photo`/`delete_photo` 改用 `_base_query(db, data_scope)` 取记录（与列表/对比图同源），越权收敛为 404。 |
| 5 | **P1** | `backend/app/api/v1/approval.py:275-340, 392-425, 428-495, 527-582, 591-615` | 审批模块**完全不做组织级数据隔离**：`ApprovalTask`/`ApprovalWorkflow` 模型**没有 `organization_id` 列**（`models/approval.py:137-198`），`submit_approval(entity_type, entity_id, ...)` 接受**任意 `entity_id`** 且不校验该实体是否属于提交人所在组织。 | ① 任一登录用户可 `POST /approval/submit` 对**其它组织的项目/经费/学校/帮扶村**伪造变更申请，诱导管理员审批并自动回写业务实体状态（`apply_entity_change` → `_apply_project_approval_result` 直接改 `Project.status`）；② `GET /approval/workflows/{id}` 泄露其它人创建的审批链定义；③ `submit_approval` 允许 `change_data` 携带任意字段。 | 给 `ApprovalTask` 增加 `organization_id`（与全库一致）并在 `submit_approval` 时按被审实体的 `organization_id` 落库；`submit` 端点先按数据域解析 `entity_type/entity_id` 指向的实体，越权 404。 |
| 6 | **P1** | `backend/app/api/v1/approval.py:428-462`（`approve_task`） | 审批通过端点调用 `service.approve_task(task_id, current_user.id, data.opinion)`，**未传 `standalone`**，而 `approval_workflow_service.py:470` 的判定是 `if not standalone and task.current_approver_id not in (None, approver_id): return None`——**当任务未分配审批人（`current_approver_id IS NULL`）时，任意登录用户都能审批通过**。`reject_task:550` 同一模式。 | 未分配审批人的任务（`role` 类型节点解析失败时即为此态，见 `approval_workflow_service.py:283-293`）可被**任何登录用户**通过/驳回，并触发业务实体状态回写（经费由 pending → approved，等于绕过经费审批链直接放款）。 | `approve_task`/`reject_task` 端点显式传 `standalone=is_admin(current_user)`，或在服务层把「未分配审批人」改为 fail-closed（仅 admin 可批）。 |
| 7 | **P1** | `backend/app/api/v1/import_export/import_data.py:176-303`（`_import_entities`） | Excel 导入**不校验调用者角色**（只有 `get_current_user`，无 `require_admin`），且 `mode="full"` 会走 `excel_importer_service.py:456-478` 的 `_soft_delete_scoped()`，该方法用 `scoped_filter(...)`（严格口径）**软删本组织全部帮扶村/项目/经费**，再由 `_import_projects`（`:629-631`）用 Excel 里的 `organization_code` 映射写入**任意组织**的 `organization_id`。 | 普通用户即可上传 Excel 触发「全量覆盖导入」：先把本组织数据批量软删（`is_active=False`），再把导入数据写进**其它组织**（`project_data["organization_id"] = org_map[org_code]` 无组织可达性校验）。同时 `_soft_delete_scoped` 用 `scoped_filter`（本组织子树）而 `_import_projects` 写入的组织是 Excel 决定的 → 删 A 组织写 B 组织。 | 导入端点加 `require_admin(current_user)`；`mode="full"` 额外要求 super_admin 或限定为自身组织；`_import_projects`/`_import_funds` 的 `organization_id` 必须经 `assert_org_reachable()` 校验。 |
| 8 | **P1** | `backend/app/api/v1/project_milestones.py:122-136, 328-352` | `GET /projects/{id}/milestones` 与 `GET /projects/{id}/change-logs` 使用 `response_model=List[...]` **直接返回裸 list**（非 envelope），违反 CONTEXT.md 不变量 3。且 `get_change_logs`（`:342-345`）自己实现了一遍 scope 判定（`scoped_filter` + `first()`），与 `_get_accessible_project_or_404`（`:105-116`）重复。 | 前端 `_unwrapList()` 兼容两种格式（CLAUDE.md 已记），但**新端点违反 envelope 契约**，且两处 scope 判定逻辑重复易漂移。 | 改为 `ok_list(items=..., total=...)`；`get_change_logs` 复用 `_get_accessible_project_or_404`。 |
| 9 | **P1** | `backend/app/api/v1/organization.py:903-933`（`get_ancestors`）、`:1101-1134` | `GET /organizations/{org_id}/ancestors` 直接 `return ancestors`（裸 list，非 envelope）；`POST /organizations/{id}/members` 与 `DELETE /organizations/{id}/members/{uid}` 返回裸 dict `{"code":200,"success":True,...}`，未走 `success_response()`。 | 违反 envelope 契约；`{"code": 200, "success": True}` 与 `success_response()` 的信封结构不同（前者无 `data` 顶层键），前端按 `success_response` 解析时 `data` 恒为 `undefined`。 | 统一改用 `ok_list()` / `success_response()`。 |
| 10 | **P1** | `backend/app/api/v1/approval.py`（19 处：`289, 319, 366, 386, 416, 453, 490, 519, 552, 577, 610, 665, 701, 724, 903, 923, 1036, 1090, 1124`） | 审批模块共 **19 处**返回裸 dict `{"code":200,"success":True,...}`，未使用 `success_response()`。`scan_bare_returns.py` 报 0 是因为它只匹配单行 `return {` 形式，跨行 `return {\n "code": 200,` 逃过了扫描 —— **门禁存在盲区**。 | 与 #8/#9 同类；审批模块 100% 未使用统一 envelope 工具，`ok_list` 只在 3 处用到。 | 补齐 `success_response()`；同时修复 `scan_bare_returns.py` 的多行匹配盲区（用 AST 判定而非正则）。 |
| 11 | **P1** | `backend/app/api/v1/auth/users.py:687-769`（`update_user`） | 更新用户时 `data_scope` 字段**未纳入提权约束**：`update_fields` 允许设置 `data_scope="all"`，而 `get_org_scope`（`data_permission.py:399`）和 `apply_scope_filter`（`:574-575`）都把 `data_scope=="all"` 当作**全局管理员**放行。 | 部门级 admin 可 `PUT /users/{id}` 把任意账号（含本组织普通用户）的 `data_scope` 改成 `"all"`，该账号随即获得**全库数据可见性**（资金/项目/帮扶村/一户一档全量）。这是从部门级 admin 到数据域全量的**直接提权路径**。 | `update_user` 对 `data_scope` 的修改加约束：仅 super_admin 可设 `"all"`；部门级 admin 只能在其组织子树内设 `"org"`/`"org_children"`/`"self"`。`create_user` 路径（`users.py:572`）同样需要收口。 |
| 12 | **P1** | `backend/app/api/v1/org_grants.py:203-210`、`backend/app/services/grant_package_service.py:192-200` | 两处授权矩阵写入使用**裸 `db.commit()`**（`security_audit.py` Scan 1 命中）：先 `delete()` 旧行再逐条 `add()` 新行，然后裸 commit。 | ① 绕过 `safe_commit` 的统一异常处理与 rollback 语义（commit 失败时无显式 rollback，session 状态污染后续请求）；② `delete` + 逐条 `add` 中间任一异常 → 授权矩阵部分写入。 | 改用 `safe_commit(db)`（`app/core/transaction.py`），或整段包 `with transaction(db):`。 |
| 13 | **P2** | `backend/app/api/v1/data/data/dashboard.py:450, 184` | `_query_fund_stats`（`:184`）与 `_compute_trends`（`:450`）用 `data_scope.has_full_access()` 分支决定是否跳过经费组织过滤。`has_full_access()` 直接返回 `self.is_admin`（`data_permission.py:282-284`），而 `get_org_scope` 对部门级 admin 返回 `is_admin=True` → **经费统计被无条件放行为全库**。 | 与 #1 同根因。即使 #1 修好，这里的 `has_full_access()` 语义仍需与 `apply_scope_filter` 统一（组织树可见性模型 vs 数据面严格模型）。 | 修 #1 后此处自动收敛；同时把 `has_full_access()` 的语义明确为「真正全局管理员」。 |
| 14 | **P2** | `backend/app/api/v1/data/data/statistics.py:187-198`（`get_summary`） | `get_summary` 返回**裸 dict**（`return result`），与同文件 `/dashboard`（`:1069`）等端点的 envelope 不一致；且 `users_count` 用 `apply_scope_filter(query, current_user, User)` —— `User` 模型**无 `created_by` 列**，普通用户走 OWN 分支会抛 `DataScopeFilterError`（`data_permission.py:648`）→ 500。 | ① 违反 envelope 契约；② 普通用户（`role=user`）调用 `GET /data/statistics/summary` 极可能 500（`User` 缺 owner 字段 → fail-closed 抛错）。同文件 `_get_overview_impl`（`:297-307`）已正确改用 `get_accessible_org_ids`，两处口径不同。 | 改用 `ok_list`/`success_response`；用户统计沿用 `_get_overview_impl` 的 `get_accessible_org_ids` 写法。 |
| 15 | **P2** | `backend/app/api/v1/projects.py:101-110`（`_apply_project_approval_result`） 及 `funds.py:201-222`、`school.py`、`supported_village.py:115`、`policy.py:47`、`rural_works.py:41` | 审批终态回写 handler 直接 `db.query(Project).filter(Project.id == task.entity_id).first()`，**不带任何组织校验**。 | 配合 #5（提交时不校验实体归属）构成完整越权链：跨组织用户提交审批 → 管理员/任意用户批准 → 业务实体状态被跨组织改写。 | 回写 handler 补数据域校验（按实体的 `organization_id` 判定），或由 #5 保证 `ApprovalTask.organization_id` 与实体一致后在回写处断言。 |
| 16 | **P2** | `backend/app/api/v1/system/backup.py:212-279`（`create_backup`）、`:338`（`list_backups`）、`:555`（`delete_backup`） | 这三个端点**没有 `get_current_user` 依赖**，用 `_authenticate_backup_request`（Electron 内部备份密钥）替代。在单机部署下 `X-Internal-Backup` 头是共享静态密钥。 | 备份内容含**全库数据 + 上传目录**（`include_uploads=True` 时含 PII 加密列的物理文件）。密钥泄露即等于全量数据导出。备份列表/删除同理。 | 备份/恢复类端点至少要求「管理员 JWT **或** 内部密钥」二选一，并在删除时留痕 `write_work_log`。 |
| 17 | **P2** | `backend/app/api/v1/validation.py:66-80`（`list_rules`）、`backend/app/api/v1/system/audit.py:377-418` | `list_rules` 返回**裸 list**（`response_model=List[ValidationRuleOut]`，`return rules`）；`system/audit.py` 的 `get_audit_logs`/`get_audit_log_detail` 返回裸 dict/list。 | 违反 envelope 契约（CONTEXT.md 不变量 3）。 | 改用 `ok_list()` / `success_response()`。 |
| 18 | **P2** | `backend/app/api/v1/fund_lifecycle.py:1966-1984`（`quota-adjust`）、`:1826-1925`（`allocation-orders`） | `quota-adjust`（`PUT /quota-adjust/{fund_id}`）写 `Fund` 配额字段，`:1839` 处有 `apply_data_scope`，但 `allocation-orders` 的 `POST /allocation-orders`（`:1850`）创建订单时**未落 `organization_id`**，导致新建记录 `organization_id=None` → 之后按组织过滤时**任何用户都看不到**（fail-closed 误伤），或被 `require_data_permission` 的 `created_by` 分支放行给单一用户。 | 新建记录缺少组织归属 → 列表里「凭空消失」，审计追不到归属组织。 | 创建时统一落 `organization_id = current_user.organization_id`（与 `households`/`media`/`consumption` 一致）。 |
| 19 | **P2** | `backend/app/api/v1/data/data/dashboard.py:462-490` | 人口/收入同比用 `max_pop_year`（**数据域内全局最大年份**）分别算当年与 `max_pop_year-1`，与指标字典「总人口 = 每村取各自最新年份」的**按村取最新年**口径不同（`:113-146` 的 `_query_village_stats` 才是字典口径）。 | 工作台「人口同比」与「总人口」两个数字在部分上报年度不齐时互相矛盾（这正是 W18 P0-1 修过的那类分裂，只是换到了趋势分支）。 | 趋势分支也按「每村各自最新年」取数，或在 CONTEXT.md 指标字典登记「人口同比」为独立口径并注明年份选取规则。 |
| 20 | **P2** | `backend/app/api/v1/consumption.py:98`、`backend/app/services/consumption_service.py:65-81` | `attach_village_names()` 查询帮扶村名称时**不带数据域过滤**（只按 `id.in_(village_ids)` + `is_active`）。 | 村名是辅助字段，泄漏面有限（ID 已由数据域过滤过的记录限定），但仍属「绕过统一入口」，且若未来记录中的 `supported_village_id` 可被越权写入即成泄漏通道。 | 复用 `data_scope.filter_by_org_ids` 或接受当前最小风险并加注释说明。 |
| 21 | **P2** | `backend/app/services/data_package_service.py:911` | `import_encrypted_package()` 中 `read_zip_member(zf, "manifest.json")` 用于**探测是否加密**，此处**未先调用 `ensure_zip_within_limit(zf)`**（同文件 `:412/495/539/1012` 与 `data_sync_service.py:439` 都调用了）。 | 恶意构造的 zip 炸弹（manifest.json 声明超大 `file_size`）在探测阶段就会 `zf.read()` 物化到内存，绕过 R2 第三层总量闸门。 | 在 `:910` 的 `with zipfile.ZipFile(...)` 内先 `ensure_zip_within_limit(zf)`，再 `read_zip_member`。 |
| 22 | **P2** | `backend/app/api/v1/approval.py:561-582`（`withdraw_task`）、`:591-615`（`resubmit_task`） | `withdraw_task`/`resubmit_task` 的成功路径**未调用 `write_work_log`**（`approval.py` 内只有 `:513` 一处 `write_work_log`，仅 `retry-apply` 用到）。审批状态机变更（通过/驳回/转交/撤回/重新提交/批量审批）**全部无审计留痕**。 | CONTEXT.md 不变量 5「审批/授权/密码类操作必须留痕」被违反。审批是本系统的核心合规链路，缺留痕意味着军事审计无法还原「谁在何时批了哪笔资金」。 | 在 `approve_task`/`reject_task`/`transfer_task`/`withdraw_task`/`resubmit_task`/`batch_approve` 6 处补 `write_work_log`（`ApprovalTask` 已在 `audit_event_handler.py:162` 注册了 SQLAlchemy 事件监听，但事件监听依赖 ContextVar，**ContextVar 为空时（后台任务/非 HTTP 上下文）只落应用日志不落 `work_logs` 表** —— 见 `audit_event_handler.py:97-105`）。 |
| 23 | **P2** | `backend/app/api/v1/work_logs.py:178-255`（`create_work_log`）、`:258-312`（`update_work_log`） | 手工写工作日志的 create/update **不调用 `write_work_log`**（写日志的日志）。 | 本身影响小（`work_logs` 表已有 `user_id` 归因），但违反「写操作必须留痕」的机械一致性。 | 接受现状或补记（低优先级）。 |
| 24 | **P2** | `backend/app/api/v1/approval.py:923, 1036, 1090, 1124` | 审批模块剩余 4 处裸 dict 返回（`/tasks/{id}/diff` 返回 `{"code":200,"success":True,"data":diff}`、`/tasks/{id}/remind`、`/history` 等），与 #10 同批未收敛。 | 同 #10。 | 同 #10。 |
| 25 | **P2** | `backend/app/services/audit_event_handler.py:97-105` | 集中式审计监听器在 **ContextVar 为空时（后台任务/定时任务/无 HTTP 上下文）只落应用日志，不写 `work_logs` 表**（`work_logs.user_id` 是 NOT NULL 外键，无法存 "system"）。 | 定时备份、自动任务等系统级写操作**在 `work_logs` 表中完全不可见**，只有日志文件里有。军事审计场景下这是审计链缺口。 | 增加 `work_logs` 的可空 `system_actor` 字段或独立的 `system_work_logs` 表，让系统级写操作也进库可查。 |

---

## 二、P0 / P1 关键代码说明

### #1（P0）`get_org_scope` 对部门级 admin 放行全量 —— 已运行时复现

`backend/app/core/data_permission.py:395-400`：

```python
role = getattr(current_user, "role", "user")
user_data_scope = getattr(current_user, "data_scope", "org") or "org"

# Admin roles or explicit "all" scope → full access
if role in ("admin", "super_admin") or is_superuser(current_user) or user_data_scope == "all":
    return OrgScopeFilter(is_admin=True)
```

`OrgScopeFilter.filter_by_org_ids`（`:286-311`）在 `is_admin` 为真时**直接返回原 query**：

```python
def filter_by_org_ids(self, query, *id_columns, created_by_column=None):
    if self.is_admin:
        return query          # ← 不加任何 WHERE
    ...
```

而同一模块的 `apply_scope_filter`（`:567-583`）走**严格口径**：

```python
if admin_full_access and is_admin(user):
    return query
...
scope = get_data_scope(user)
if scope == DataScope.ALL:      # 仅 super_admin / is_superuser
    return query
if scope == DataScope.OWN_DEPT:  # 部门级 admin → 本组织及子树
    org_ids = get_accessible_org_ids(user, db=db)
```

**运行时复现**（`.scratch/w25-audit/_verify_leak.py`，真实 SQLAlchemy + SQLite）：

```
[A] 部门级 admin(org=10) -> OrgScopeFilter(is_admin=True)  <-- 未加任何 org 过滤
[B] households filter_by_org_ids 可见行数 = 2
      -> id=1 name=A村张户 org_id=10
      -> id=2 name=B村李户 org_id=20      ← 其它组织的记录泄漏
```

影响面（走 `get_org_scope` 的全部端点）：

| 模块 | 端点 | 泄漏内容 |
|------|------|----------|
| 一户一档 | `GET /households`、`/households/alerts`、`/households/export`、`GET /households/{id}` | 户主姓名、帮扶责任人电话、身份证（成员）、风险预警 |
| 影像库 | `GET /media/photos`、`/photos/compare` | 帮扶现场影像（GPS、拍摄时间） |
| 消费帮扶 | `GET /consumption`、`/statistics`、`/export` | 成交金额、供货方、采购方 |
| 帮扶学校 | `GET /schools`、`/schools/statistics`、`/schools/export` | 学生数、联系方式 |
| 地图/大屏 | `GET /map/markers`、`/data/bigscreen/overview` | 全库地理与统计 |
| 结对/捐赠 | `GET /pairing`、`/donation` | 结对与捐赠台账 |

对照 `apply_scope_filter`（funds/projects/villages/search/assessment 走这条）在同一用户下**只返回本组织**，因此同一系统内**同一 admin 在两个页面看到的数据量不同**。

### #2（P0）`statistics._get_analysis_data_impl` 的 `active_projects` 无数据域

`backend/app/api/v1/data/data/statistics.py:786-797`：

```python
total_villages = _scoped(
    db.query(SupportedVillage).filter(SupportedVillage.is_active.is_(True)), SupportedVillage
).count()
active_projects = (                                  # ← 无 _scoped
    db.query(Project)
    .filter(
        Project.is_active == True,
        Project.status.in_(["in_progress", "approved", "active"]),
    )
    .count()
)
```

同函数内 `mil_total`/`loc_total`（`:800-815`）都套了 `_scoped`。对照 `get_summary`（`:187-192`）里同名指标**是**加了 `_scoped` 的 —— 同一指标两个端点两套实现（违反 CONTEXT.md「同一指标只能有一个口径」）。

### #5（P1）审批任务无组织归属 + 提交时不校验实体归属

`backend/app/models/approval.py:137-178`（`ApprovalTask`）字段里**没有 `organization_id`**：

```python
class ApprovalTask(Base):
    __tablename__ = "approval_tasks"
    id = Column(Integer, primary_key=True, index=True)
    workflow_id = ...
    entity_type = Column(String(50), nullable=False)
    entity_id = Column(Integer, nullable=False)
    submitter_id = ...
```

`backend/app/api/v1/approval.py:392-411`（提交端点）：

```python
@router.post("/submit", summary="提交审批")
def submit_approval(data: SubmitApprovalRequest, db=..., current_user=...):
    service = ApprovalWorkflowService(db)
    task = service.submit_approval(
        entity_type=data.entity_type,
        entity_id=data.entity_id,        # ← 任意 ID，未校验归属
        submitter_id=current_user.id,
        change_data=data.change_data,    # ← 任意变更载荷
        ...
    )
```

配合 `backend/app/api/v1/projects.py:101-110` 的回写 handler（无组织校验）即成完整越权链。

### #6（P1）未分配审批人的任务可被任意用户审批

`backend/app/services/approval_workflow_service.py:468-471`：

```python
# 未分配审批人（current_approver_id=None）的任务任何登录用户均可审批
if not standalone and task.current_approver_id not in (None, approver_id):
    return None
```

`backend/app/api/v1/approval.py:444-448`（端点未传 `standalone`）：

```python
service = ApprovalWorkflowService(db)
task = service.approve_task(task_id, current_user.id, data.opinion)  # standalone 缺省 False
```

`current_approver_id` 为 NULL 的路径真实存在：`approval_workflow_service.py:283-293` 的 `_resolve_role_approver_id` 解析失败时返回 `None`，且 `:256-261` 会打 warning 后保留未分配。

### #7（P1）Excel 导入无角色校验 + full 模式软删本组织再写他组织

`backend/app/api/v1/import_export/import_data.py:176-192`：

```python
@router.post("/villages", response_model=ImportResultResponse)
async def import_villages(
    file: UploadFile = File(...),
    mode: str = Query("incremental", ...),
    current_user: User = Depends(get_current_user),   # ← 无 require_admin
    db: Session = Depends(get_db),
):
```

`backend/app/services/excel_importer_service.py:456-478`（full 模式的软删）：

```python
def _soft_delete_scoped(self, model) -> int:
    query = scoped_filter(self.db.query(model), model, self.current_user) ...
    query = query.filter(model.is_active.is_(True))
    return query.update({model.is_active: False}, synchronize_session=False)
```

`backend/app/services/excel_importer_service.py:629-631`（写入他组织）：

```python
org_code = converted.get("organization_code")
if org_code and org_code in org_map:
    project_data["organization_id"] = org_map[org_code]   # ← Excel 决定组织，无可达性校验
```

### #11（P1）`data_scope="all"` 是未被守护的提权字段

`backend/app/core/data_permission.py:572-575`（`apply_scope_filter`）与 `:399`（`get_org_scope`）都把 `data_scope == "all"` 当作全局管理员。而 `backend/app/api/v1/auth/users.py:750-753`：

```python
# 验证数据范围有效性
if "data_scope" in update_fields and update_fields["data_scope"]:
    if update_fields["data_scope"] not in VALID_SCOPES:
        raise HTTPException(status_code=400, detail="无效的数据范围")
```

——**只校验取值合法性，不校验调用者是否有权授予「全库」范围**。部门级 admin 可把本组织任意账号（含自己以外的下属）改成 `all`。

---

## 三、已核查但无问题（避免重复排查）

| 排查点 | 结论 |
|--------|------|
| **既有静态门禁** | `check_unbounded_read.py`=0、`check_upload_endpoints.py`=0、`check_os_exit.py`=0、`scan_bare_returns.py`=0、`scan_list_returns.py`=0、`check_unused_scope_params.py`=0、`check_raw_sql_fstrings.py`=0（38 处拼接均登记豁免）、`report_unmapped_write_routes.py` 396/396 全覆盖、`security_audit.py` Scan 2/3/4/5 全 OK（仅 Scan 1 命中 2 处裸 commit → 已列为 #12） |
| **上传/解压限长** | 全部 `UploadFile` 端点（39 处）均走 `read_upload_with_limit` / `save_upload_file` / `_stream_package_to_disk`；ZIP 读取普遍先 `ensure_zip_within_limit` 再 `read_zip_member`（数据包/权限包/管控包/上报包/备份校验全覆盖）。**唯一例外**：`data_package_service.py:911` 加密探测 → 已列 #21 |
| **PII 加密（9 列）** | `households.helper_phone`、`household_members.id_card`、`village_committee_members.phone`、`users.phone`、`organizations/projects/rural_works/rural_tasks/schools.contact_phone` 全部为 `EncryptedText`；**未发现绕过 TypeDecorator 的明文写入**。`data_package_service._export_data_type`（`:262-319`）与 `data_sync_service._insert_record`（`:612-618`）走 raw SQL 但**只取/写密文**（W18-D8 有意设计，注释明确），导入侧经 TypeDecorator 透明解密。`startup/preflight.py:103-113` 的裸 SQL 是 `LIKE` 绕加密的必要例外且已注释说明 |
| **写操作审计留痕** | 168 处 `write_work_log` 调用点覆盖 funds/projects/villages/school/policy/organization/users/machine_code/encryption/menus/rbac/todos/messages/media/consumption/households/validation/report_templates/permission_packs/org_grants/batch/data_packages/system_config/diagnostics/rural_task/rural_work/pairing/donation/effectiveness/subordinate_registry/subordinate_reports/control_package/fund_lifecycle/fund_budgets。**缺口**：`approval.py` 仅 1 处（`retry-apply`）→ 已列 #22；`work_logs.py` 自身 → 已列 #23 |
| **事务与并发** | 审批状态机 `approve_task`/`reject_task` 已用**带条件原子 UPDATE 抢占**（`approval_workflow_service.py:502-512`、`:556-572`，rowcount!=1 即放弃），不是 check-then-act；`FileBlob.ref_count` 增减在 `upload_helper.py:175`/`:524`，命中唯一约束时回滚重查（`:184-188`）；`data_package_service` 批量导入用 `begin_nested()` SAVEPOINT 分组隔离（`:816`），失败只回滚本组；`data_sync_service._update_record`（`:634-635`）用 `table.c.sync_version + 1` 在 SQL 层原子自增。**未发现**计数器读-改-写丢失更新的新增实例 |
| **metrics 口径重复** | CONTEXT.md 指标字典 7 项逐条比对：帮扶村总数/总人口/总户数/人均纯收入/经费合计/报表村总数/金额单位 —— dashboard `_query_village_stats`（`:100-173`）与 statistics 已是「每村各自最新年」同口径。**发现两处新分裂**：① `statistics.py:790` `active_projects` 漏 scope（#2）；② `dashboard.py:462-490` 人口同比用「数据域内全局最大年份」而非「每村最新年」（#19） |
| **未授权端点** | 48 个无 `get_current_user` 依赖的端点逐个核过：登录/注册/刷新/CSRF/机器码激活与破窗恢复/地图瓦片/离线地图/下拉选项/下载导入模板/health/init/backup（`#16` 为唯一实质问题）。`permission_package.py:206-278` 与 `:280-309` 未登录调用时**强制 loopback 校验**（`_client_is_loopback`），非本机 403，设计合理 |
| **fail-closed 语义** | `apply_scope_to_query` 模型缺 owner 字段 → `sa_false()` 空集（`:163-171`）；`_apply_owner_filter` 缺 owner 字段 → 抛 `DataScopeFilterError`（`:646-651`）；`check_record_access` 组织缺失 → 拒绝（`:211-216`）；`get_data_scope` 无组织 admin → 降级 OWN（`:117-118`）；`require_data_permission` 的 `created_by is not None and ...` 写法正确（`:249-250`） |
| **`enforce_admin_include_deleted`** | 4 个端点（supported-villages/schools/projects/funds）正确使用；`households`/`consumption` 也已接（`households.py:64,130,178`、`consumption.py:78,105`），非管理员静默降级，符合 CLAUDE.md 约定 |
| **`check_record_access` / `require_data_permission` 的 NULL 组织** | `check_record_access` 已 fail-closed（已修复项，不重复报告）。但 `require_data_permission`（`data_permission.py:244-254`）**没有**同等保护：`organization_id` 为 None 时只判 `created_by` —— 这是 #3/#4 的成因 |
| **批次导入 dry_run** | `import_data.py:265-287` 用独立 Session + `dry_db.commit = lambda: None` 屏蔽提交，结束 rollback，dry-run 不会真的落库（历史缺陷已修） |
| **`admin_full_access` 开关** | 已按约定排除（`apply_scope_filter` 默认严格口径已收口）。但发现**全仓无任何调用点传 `admin_full_access=True`** —— 组织树可见性端点（地图/大屏）实际走的是 `get_org_scope`，与 CONTEXT.md 描述的「显式传 admin_full_access=True」实现路径不一致（相关影响并入 #1/#13） |
| **组织树元数据** | `Organization.path`/`level` 由 `OrganizationService.repair_organization_paths()` 启动自检回填，CLAUDE.md 记录的有效 |
| **`validation.py` 动态模型** | `_get_query_model()`（`:370-392`）对未知 module 返回 `None`，`query_check`（`:469-471`）与 `list_validation_fields`（`:447-449`）**都已早退 400**，不会把 `None` 传进 `apply_scope_filter` —— 无 500 风险（初稿误列，已复核排除） |
| **i18n / 菜单单一源 / villages 表 / ErrorBoundary** | 按要求排除，均已修复 |

---

## 四、总体健康度评分

### **62 / 100**

**评分理由**

**加分项（+）：**

- 静态门禁体系成熟：7 个棘轮脚本 + `report_unmapped_write_routes.py`（396 写端点 100% 映射）+ `security_audit.py` 5 项扫描，绝大部分历史缺陷已被自动化拦截。
- 数据域**核心原语**（`apply_scope_filter` / `filter_by_data_scope` / `check_record_access`）的 fail-closed 语义正确且有回归测试锁定（`test_data_scope_strict_r28.py` 234 行覆盖 4 类边界）。
- PII 加密落地扎实：9 列全部 TypeDecorator，无裸 SQL 明文写入绕道；数据包「密文出包」的设计有明确注释与 ADR 依据。
- 上传/解压三层限长（R2）覆盖 39 个上传端点全部到位。
- 审批状态机已用原子 UPDATE 抢占，不是 check-then-act。
- 指标字典治理机制（CONTEXT.md + 防腐门禁）已建立并对多数指标生效。

**扣分项（−）：**

- **P0 × 2**：#1 部门级 admin 跨组织全量可见（可直接调用 API 复现，影响一户一档/影像库/消费帮扶/学校/地图/大屏等 6 大模块，且与同系统其它端点口径直接矛盾）——这是**军事审计红线 S2 级别**的合规缺陷；#2 `active_projects` 无 scope 过滤，任意用户可获知全库项目规模。
- **P1 × 11**：审批链路整体缺组织隔离（#5）且「未分配审批人任务任何人可批」（#6），加上 Excel 导入无角色校验 + full 模式可软删本组织数据并写入他组织（#7），构成 3 条独立的可写入越权链；`data_scope="all"` 提权路径（#11）可把部门级 admin 升级为全库可见。
- **P1 × 4（一致性）**：审批模块 15 处裸 dict + 项目里程碑/组织/校验规则 3 处裸 list，envelope 契约在**新端点**上被系统性违反；且 `scan_bare_returns.py` 的正则只匹配单行 `return {`，对跨行 `return {\n "code": 200` 存在**盲区**（门禁本身漏报），这是门禁设计缺陷而非单纯代码缺陷。
- **P2 × 14**：文档/字典一致性、审计链路完整性（系统级写操作不入 `work_logs` 表）、加密包探测未过限长闸门等。

**结论**：后端**基础设施与门禁层面**已达较高成熟度（这是本次审计能快速定位问题的原因），但**「组织级数据隔离」这一条核心不变量在 `get_org_scope` 这条路径上从未真正收口** —— 一户一档/影像库/消费帮扶这三个 W22 新模块恰好全部走这条路径，说明 W22 新增时沿用了「admin 全量」的旧心智模型而非 R27-H8 收口后的严格口径。加上审批与导入两条写入链路缺组织校验，**这不是个别端点的疏漏，而是新模块普遍未继承 R28 收口结论**。

**建议修复顺序**：

1. #1（改 `get_org_scope` 口径）→ 一次修复覆盖 6 大模块的读侧泄漏；
2. #2 / #5 / #6 / #7 / #11（写侧越权链 + 提权路径）；
3. #3 / #4（把 media/consumption 写路径切到与读路径同源的数据域）；
4. #8 / #9 / #10 / #14 / #17（envelope 收敛）**并同步修 `scan_bare_returns.py` 的多行匹配盲区**，否则新增端点会继续漏出；
5. 其余 P2 按批次处理。
