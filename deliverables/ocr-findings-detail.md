# OpenCodeReview 深度审查 — findings 明细

扫描文件数: 669 | findings 总数: 2020 | 消耗 token: 55,609,298

| 严重度 | 数量 |
|---|---|
| critical | 55 |
| high | 359 |
| medium | 1056 |
| low | 550 |

| 类别 | 数量 |
|---|---|
| bug | 1105 |
| maintainability | 514 |
| security | 218 |
| performance | 123 |
| documentation | 39 |
| style | 13 |
| other | 8 |

---

## CRITICAL (55)

### `backend/app/api/v1/ai_enhanced.py`

- **[bug] L98** Return-type annotation is used by FastAPI as the default `response_model`. `AnomalyDetectionService.detect_anomalies` returns `List[Dict[str, Any]]` (see backend/app/services/ai/anomaly_detection_service.py line 36), but this handler is annotated `-> Dict[str, Any]`. FastAPI will therefore validate the list against a `Dict[str, Any]` response model and raise `ResponseValidationError` (HTTP 500) whenever anomalies are returned. Change the annotation to `List[Dict[str, Any]]` to match the service contract.

### `backend/app/api/v1/approval.py`

- **[security] L1074** IDOR / broken access control: the scope is only narrowed when the client omits `submitter_id`. A non-admin can simply pass `?submitter_id=<other_user_id>` and read another user's approval history (records, opinions, entity data). Always override the filter for non-admins.

### `backend/app/api/v1/assessment.py`

- **[security] L51** Cross-user data leak via cache key. The response is computed from `scoped_filter(..., current_user)`, i.e. it is user/permission dependent, but the cache key only contains the year. A user with a narrow data scope will be served the cached payload built for a user with a wider scope (and vice versa), exposing villages they are not authorized to see. Include the caller's scope identity in the cache key (or per-user namespacing) so results can never be shared across scopes.

### `backend/app/api/v1/auth/user_management.py`

- **[security] L407** Privilege escalation via `assign_role`: `role_code` is taken raw from the query string with no validation against `ALL_ROLES` and no `normalize_role()` (unlike `update_user`). A plain `admin` caller can self-promote to `super_admin` (which sets `is_superuser=True` and grants the highest权限), and arbitrary/unknown role strings (e.g. "root") are persisted into `User.role`, whereas the same input through `update_user` would be normalized to `admin`/`user`. Validate the value and normalize it consistently.

### `backend/app/api/v1/control_package.py`

- **[security] L255** Import path never validates the organization it writes to. `generate_control_package` guards the target org with `_assert_org_reachable`, but here the org id is taken straight from the uploaded (untrusted) manifest: `is_admin` only proves the caller is a department-level `admin`, so a crafted/edited package can set `target_organization_id` to any other org and overwrite its module policies (cross-organization write). `organization_id` is also `nullable=False`, so a missing/None value raises IntegrityError that surfaces as a generic 500. Enforce the same reachability guard (and a positive-int check) here.

### `backend/app/api/v1/data/data/data_packages.py`

- **[security] L1348** Path traversal / temp-file collision: `file.filename` is attacker-controlled and joined directly into the temp path. A filename such as `../../../../etc/cron.d/x` escapes the temp directory and lets the uploader write an arbitrary file; the second-level `int(time.time())` uniqueness also allows two concurrent uploads in the same second to clobber each other's path. Sanitize the name (strip directories) and let `mkstemp` generate a unique path.

### `backend/app/api/v1/data/data/data_reports.py`

- **[security] L215** Missing authorization check (IDOR). Unlike cancel/resubmit/review, this endpoint never verifies that `current_user` belongs to `report.source_org_id`, and `DataReportService.submit_report` only validates the status transition (no org check). Any authenticated user who knows/guesses a `report_id` can submit another organization's report to its superior.

### `backend/app/api/v1/data/data/reports.py`

- **[security] L792** IDOR: `download_generated_report` looks up `ReportSubscription` by `report_id` alone, with no `user_id` scoping and no superuser bypass. Any authenticated user can pass another user's subscription id and download their report (JSON metadata, or an Excel file generated for that subscription's year). Scope the query the same way the other subscription endpoints do, e.g. filter by `ReportSubscription.user_id == current_user.id` unless `is_superuser(current_user)`.

### `backend/app/api/v1/funds.py`

- **[security] L279** 状态机绕过：`status` 是自由字符串，`create_fund` 直接把 `data` 交给 FundService，且 `FundUpdate.status`（第 ~200 行 `status: Optional[str] = None`）也会在 `update_fund` 的 `setattr` 循环里被无条件写入。客户端 `POST {"status":"approved"}` 或 `PUT {"status":"allocated"}` 即可越过 `_transition_status` 的状态校验、`require_funds_operator_role`、附件强制上传（contract/allocation_order）与里程碑检查，直接造出已批准/已拨付的经费。建议创建时把状态钉死为 pending，更新时禁止直接改 status（状态只能由 approve/allocate/... 端点驱动）。

### `backend/app/api/v1/import_export/export.py`

- **[security] L284** `export_comprehensive_report` is the only export endpoint without `require_admin`, so any authenticated user can reach it. Worse, only the village query is passed through `scoped_filter`; `db.query(User).count()` and the unscoped `School`/`Project`/`Fund` counts/count-sum (plus the raw Project/Fund sample queries below) aggregate across every organization. A department-scoped non-admin can therefore read global totals and cross-org records, violating the S2 data-isolation rule applied everywhere else in this file. Add the admin gate (or scope every aggregate with `scoped_filter`/`scoped_count`).

### `backend/app/api/v1/import_export/import_data.py`

- **[bug] L415** `DataValidatorService.validate_import_data` only accepts `(rows, validate_county)` — it has no `validate_tiered_level` parameter. This call therefore raises `TypeError: validate_import_data() got an unexpected keyword argument 'validate_tiered_level'`, so `POST /import/validate` returns HTTP 500 for the **default** `entity_type="supported_village"` (the only entity type that reaches this branch). Existing tests never exercise this path (they either bail out on the empty-filename check or mock `_resolve_validator`). Either drop the kwarg/query param or add support for it in the validator.

### `backend/app/api/v1/org_module_policy.py`

- **[security] L101** Horizontal privilege escalation: all four `/{org_id}` endpoints (`get_org_policies`, `set_org_policies`, `reset_org_policy`, `export_org_policies`) only check that the caller is an admin/superuser and never verify that `org_id` belongs to the caller's own organization subtree. Per the module docstring ("上级单位管理下级单位"), a department-level `admin` from any tenant can therefore read, overwrite, reset and export another tenant's module policies. The sibling module `app/api/v1/control_package.py` already solves exactly this with `_assert_org_reachable(db, current_user, org_id)` (also rejects non-existent orgs). Extract that helper into a shared module and call it in each endpoint here.

### `backend/app/api/v1/organization.py`

- **[bug] L675** `PUT /{org_id}` and `move_organization` only set `parent_id` (the former also fails to reject descendants/dangling ids) without recomputing `path`/`level` for the moved subtree. Because org data scope uses `path LIKE '<root.path>%'`, the subtree remains visible on the old branch and invisible on the new one, and cycles orphan the tree. Route reparenting through a shared helper that validates existence + cycle and rewrites `path`/`level` for the whole subtree.

### `backend/app/api/v1/performance.py`

- **[bug] L112** `redis_adapter.clear()` does not exist on the adapter. `backend/app/core/redis_adapter.py` only defines `flush()` (plus `get/set/delete/exists/get_stats/health_check`), so this call raises `AttributeError` at runtime and the endpoint always returns HTTP 500 instead of clearing the cache. Use `flush()`. Note that `flush()` returns `None`, so the current truthiness check would also treat success as failure — remove the failure branch (or have the adapter expose a `clear()` that returns a bool).

### `backend/app/api/v1/policy.py`

- **[security] L117** Path traversal / arbitrary file read. Client-supplied URLs are written verbatim into `policy.file_path`: - `first == "/uploads/../../etc/passwd"` → `rel = "../../etc/passwd"` is simply joined onto `UPLOAD_DIR` without normalization/containment check, escaping the upload directory (and `..` also survives when `os.sep != '/'`); - any non-`/uploads/` value (e.g. `"/etc/passwd"` or any absolute path) is stored as-is. Both values are later handed to `FileResponse(path=policy.file_path, ...)` in `/{policy_id}/preview` and `/{policy_id}/download`, so any authenticated user can read arbitrary server files. Validate containment against `UPLOAD_DIR` and reject values outside it.

### `backend/app/api/v1/project_milestones.py`

- **[security] L112** Missing data-scope/ownership check (IDOR) in `project_milestones.py`: `get_milestones`, `create_milestone`/`update_milestone`/`delete_milestone`, and the status-transition endpoints all query by raw `project_id` without validating access. Apply the same `scoped_filter`/`check_record_access` (or `projects.py::_get_project_or_404`) used by `get_change_logs`.

### `backend/app/api/v1/report_templates.py`

- **[bug] L676** Overwrite mode commits the scoped `DELETE` before any new row is written. If parsing/insertion fails afterwards, the caller gets a 500 while the previously existing data has already been permanently removed. The same pattern exists in `_import_school_data`, `_project_prepare_import` and `_rural_work_prepare_import`. Since the delete and the inserts share one session/transaction, the intermediate `safe_commit(db)` is what makes the deletion durable — use `db.flush()` here (or drop it entirely) and let the single `safe_commit()` at the end of the import atomically commit delete + inserts.

### `backend/app/api/v1/rural_tasks.py`

- **[security] L310** Self-approval / approval-workflow bypass. `_get_task_or_403` lets the non-admin *creator* of the task through, and this endpoint performs no role check, so the same user who called `/submit` can call `/approve` and approve (or reject) their own task. The approval step is therefore not an independent control for non-admins. Require an approver role (e.g. `is_admin(current_user)`) and/or explicitly reject when `task.submitted_by == current_user.id` (or when the approver is the creator).

### `backend/app/api/v1/sync.py`

- **[bug] L151** The published `success_rate` is miscalculated: `failure_count` compares against the wrong status literal (`"failure"` instead of `"failed"`) so it is always 0, and the denominator includes rows that are neither success nor failure (e.g. `pending`). Fix the status value and divide by the number of rows with a terminal status.

### `backend/app/api/v1/system/audit.py`

- **[security] L132** Invalid `before_date` degrades into an unfiltered bulk delete. When no `ids`/`actions`/`action` are supplied, the `elif not body.before_date: return` guard only short-circuits for a *missing* date; for a non-empty but unparseable date the code reaches this handler, swallows the `ValueError`, leaves the query with no WHERE clause at all, and then executes `query.delete(synchronize_session=False)` — wiping the entire audit_logs table. A malformed date must abort the request, not silently widen the deletion scope.

### `backend/app/api/v1/system/error_report.py`

- **[security] L200** 归属校验实际被完全绕过。`ErrorReport` 模型并没有 `user_id` 字段（只有 `reporter`），所以 `getattr(record, "user_id", None)` 恒为 `None`，`is_owner` 恒为 `True`；而两个创建端点也只写入 `reporter` 用户名、从不写入 `user_id`。结果是任何已登录用户都能修改任意错误报告（把 critical 报告标记为 resolved/ignored，掩盖故障）。应改为与真正被写入的字段 `reporter` 比较。

### `backend/app/api/v1/system/init.py`

- **[bug] L166** Fail-open on admin creation: when `User` creation fails (e.g. DB error, duplicate email/username constraint), the exception is only logged and a `warning` step is appended, then execution continues to `svc.set_initialized(org_id=1)`. The system is consequently marked as initialized while no superuser exists, so the account can never be created again through this endpoint (`/initialize` refuses to run once initialized) and the deployment is permanently locked out of administration. This step must be fatal — abort and prevent the initialization flag from being set.

### `backend/app/api/v1/system/monitor.py`

- **[bug] L179** KeyError risk: when a partition read fails, the fallback entry appended in the `except` branch has no `"percent"` key, yet the health assessment reads `disks[0]["percent"]` unconditionally. If the first partition fails (common on Windows CD-ROM/unmounted volumes, or stale network mounts), this raises `KeyError`, which is then swallowed by the outer `except Exception`, discarding the entire resource report and returning `status=error`. Use `.get()` and evaluate all disks, not just the first one.

### `backend/app/api/v1/validation.py`

- **[security] L88** 校验规则的增/改/删接口文档标注为「管理员」操作，但依赖只用了 `get_current_user`，任意登录用户都能创建、修改或删除直接影响业务数据校验行为的规则（可放开必填/数值/正则等约束）。代码库其他模块统一使用 `app.core.permission_utils.require_admin`。`update_rule`（约 L120）与 `delete_rule`（约 L148）存在同样问题，需一并补齐。

### `backend/app/core/permission_utils.py`

- **[security] L84** Fail-open in the direct-call branch: the mode is distinguished only by `isinstance(getattr(func, "role", None), str)`. Any other caller-supplied "user" (e.g. an object whose `role` is `None`/non-str, an enum role, or a payload/namespace carrying only `is_superuser`) is treated as the function to decorate, so the call returns a wrapper instead of raising 403 and the guarded code continues unchecked. `require_admin(None)` shows the same silent skip (it is indistinguishable from the `require_admin()` factory). All production call sites use the direct-call form (`require_admin(current_user)`), so the gate can be silently bypassed by bad/partial user data. Discriminate by user-like attributes (`hasattr(func, "role") or hasattr(func, "is_superuser")`) and make the "unauthenticated" case raise instead of returning a decorator (e.g. a sentinel default or a dedicated direct-call helper).

### `backend/app/core/transaction.py`

- **[bug] L162** `transactional` never commits on either path: the self-created-session branch relies on `get_db_context()`, which only resumes/closes the generator and `Session.close()` implicitly rolls back the still-open transaction, while the existing-session branch simply returns without calling `db.commit()` — so every write performed by `func` is silently discarded. All other helpers in this module commit before returning; these branches should too.

### `backend/app/models/fund_lifecycle.py`

- **[bug] L299** `contract_id` is declared `nullable=False` but its FK specifies `ondelete="SET NULL"`. When a `fund_contracts` row is deleted, the database will try to write NULL into a NOT NULL column and the delete will fail with an integrity error, so the intended SET NULL behavior can never work. Either make the column nullable, or use a referential action compatible with NOT NULL (`CASCADE` / `RESTRICT`).

### `backend/app/models/import_export_history.py`

- **[bug] L61** Contradictory column definition: `ondelete="SET NULL"` tells the DB to NULL out `user_id` when the referenced user row is deleted, but the column is declared `nullable=False`. Deleting a `User` will therefore fail with an integrity/FK error instead of preserving the audit row. Either make the column nullable (recommended for an audit trail that must survive user deletion) or change the FK action to something compatible (e.g. RESTRICT/NO ACTION). Note other audit models in this project use `nullable=True` with `SET NULL`, which is the consistent choice.

### `backend/app/models/message.py`

- **[bug] L49** `ondelete="SET NULL"` conflicts with `nullable=False`. When a user row is deleted, the database tries to set `messages.user_id` to NULL and the NOT NULL constraint raises an integrity error, so user deletion fails instead of preserving the message. Elsewhere in this codebase `SET NULL` FKs are declared `nullable=True` (e.g. `audit.py:67`, `approval.py:70`). Pick one: keep `SET NULL` and make the column nullable, or use `ondelete="CASCADE"` with `nullable=False`.

### `backend/app/models/package_version.py`

- **[bug] L39** `package_id` is non-nullable with DB-level `ondelete="CASCADE"`, but the `backref="versions"` relationship has no `cascade`/`passive_deletes` configured. The only ORM delete path is `db.delete(package)` in `DELETE /data-packages/{package_id}`, and SQLAlchemy's default behavior for a one-to-many without delete cascade is to load the children and set their FK to NULL before deleting the parent. Because `package_id` is NOT NULL, this raises an IntegrityError and the package delete fails (the DB-level ON DELETE CASCADE is never reached). Configure the relationship so the ORM either cascades the delete or lets the DB do it.

### `backend/app/services/aes_gcm_cipher.py`

- **[security] L24** Silent key substitution: when a caller passes a key that is not exactly 32 bytes (or an empty/whitespace-only key), the constructor quietly generates a random key instead of failing. Encrypt/decrypt then appear to succeed but produce ciphertext that can never be decrypted by the intended key, and the failure surfaces later as a misleading "密钥错误或数据被篡改". Invalid key material should be rejected loudly.

### `backend/app/services/analytics_service.py`

- **[bug] L106** Raw SQL uses plural table names (`village_populations`, `village_incomes`, `infrastructure_improvements`) that do not exist; the models declare singular `__tablename__` values. Every such query raises "relation does not exist" and is swallowed, returning empty results. Use the correct singular table names.

- **[bug] L188** This query cannot succeed: (1) it selects and groups by `vp.year` from `supported_villages`, but that table has no `year` column (only the aggregate `transition_fund_military_total`/`transition_fund_local_total` and the `transition_fund_items` JSON); (2) the subquery references the nonexistent `village_populations`. The broad `except` hides the error, so `get_funding_trends` always returns an empty trend list. The yearly funding must be derived from the per-year child tables (e.g. join `village_population`/`ForceInvestment` or parse `transition_fund_items`), not from `supported_villages` directly.

### `backend/app/services/approval_workflow_service.py`

- **[bug] L62** `self.db.rollback()` here rolls back the *whole* session, not just the handler's work. Every caller (`approve_task` lines ~497-505, `reject_task` lines ~517-525) adds the `ApprovalRecord` for the current action to the same uncommitted transaction *before* calling `apply_entity_change`. When the handler raises, that pending audit record is silently discarded while the task status is still committed as `*_apply_failed` — the approval/rejection leaves no trace in `approval_records`. Additionally the `task.completed_at` assigned just before the call is expired by the rollback and never re-assigned, so failed tasks end up with `completed_at = NULL`. Suggest either isolating the handler in a SAVEPOINT (`with self.db.begin_nested():` so only the handler's writes are undone), or re-creating the record / re-setting `completed_at` after a failed write-back.

### `backend/app/services/business_metrics_service.py`

- **[bug] L188** `DataReport.status == "completed"` never matches any row. `ReportStatus` (see `app/models/data_report.py`) only defines `draft/submitted/approved/rejected/cancelled` — there is no `completed` value, and nothing in the codebase ever writes `"completed"` to `DataReport.status` (the `"completed"` writes are on `DataSyncLog.status`). As a result `completed_reports` is always 0 and both `report_completion_rate` and `on_time_rate` are permanently reported as 0, silently masking the real reporting status. Use the actual completed status (e.g. `ReportStatus.APPROVED`) instead of the string literal.

### `backend/app/services/excel_importer_service.py`

- **[bug] L468** Full-mode data loss: the delete is only flushed, not committed, but the per-row inserts below catch exceptions individually (`result.failed_rows += 1`), so the batch is never rolled back. `import_data` subsequently calls `safe_commit(self.db)` even when `result.success is False`, permanently removing all pre-existing (in-scope) rows while keeping only the partial set of new rows. Either wrap the whole full-mode import in a savepoint/transaction and roll back on any failure (raise instead of swallowing), or require all rows to succeed before committing the delete.

### `backend/app/services/export_service.py`

- **[bug] L86** `export_organizations` 的表头使用中文键，但 `_create_workbook` 是用这些中文表头去 `row.get(h, "")` 取值，而唯一调用方 `backend/app/api/v1/organization.py`（`export_organizations`，约 434-459 行）传入的 `export_data` 是英文键：`name/code/type/level/contact_person/contact_phone/address/description/member_count/status/created_at`。键名完全不匹配，导出文件只有表头、11 列数据全部为空，且接口仍返回 200，属于静默数据丢失。建议改为像 `export_organization_pass_codes` 那样显式做字段映射（或让调用方按表头中文键构造数据）。

### `backend/app/services/import_export_history_service.py`

- **[bug] L44** `create_history` swallows every keyword it does not declare. `record_export` / `record_import` / `record_confirm` pass `file_name`, `file_size`, `record_count`, `data_types`, `user_agent` and `details_json`, but these names are not part of the signature, so they land in `**extra` and are never applied to the record — the audit metadata is silently lost even though the model defines all of these columns (`ImportExportHistory.file_name/file_size/record_count/data_types/user_agent/details_json`). Either declare them explicitly and forward them when constructing the record, or persist the remaining extras.

### `backend/app/services/machine_code_service.py`

- **[security] L35** Security: the secret falls back to a constant shipped inside the source/build, and `generate_org_pass_code` derives the code from nothing but the organization name (`"ORG:" + org_name`). Anyone with access to the application can therefore compute valid org pass codes offline and self-register into *any* organization (and machine pass codes for any machine code), defeating the whole authorization model; the docstring's audit fallback does not compensate. Also note `_PASS_CODE_SECRET_EXPLICIT` is no longer read anywhere in production code, so the previously documented fail-closed gate no longer exists — the regression tests that monkeypatch it are now vacuous. Recommend requiring `PASS_CODE_SECRET` at startup (fail fast) or deriving a per-installation secret from a persisted random key instead of a distributed constant.

### `backend/app/services/message_service.py`

- **[bug] L71** `MessageType.BACKUP` ("backup") is defined in the model and is actually used in production: `app/services/backup_scheduler.py::_send_backup_reminder` calls `MessageService(db).send_batch_messages(..., message_type="backup", ...)`. Because "backup" is missing from `valid_types`, every backup reminder raises `ValueError: 无效的消息类型: backup` at runtime. Add BACKUP to the whitelist (and to the initial dict in `get_unread_count_by_type` for consistency).

### `backend/app/services/policy_fts_service.py`

- **[bug] L65** The FTS query is built with a plain triple-quoted string, not an f-string, so the placeholders `{FTS_TABLE}` are never interpolated. The SQL sent to SQLite contains the literal text `{FTS_TABLE}` (e.g. `snippet({FTS_TABLE}, 1, ...)`, `FROM {FTS_TABLE} f`, `WHERE {FTS_TABLE} MATCH :query`), which is a syntax error (`unrecognized token: "{"`). The exception is swallowed by the `except Exception` below, so **full-text search never executes and every search silently degrades to the full-table LIKE fallback** (with a warning logged on every request). The existing tests cannot detect this because they only assert a non-empty result, which the LIKE path also satisfies.

### `backend/app/services/user_cascade_delete_service.py`

- **[bug] L122** `db.rollback()` inside the loop aborts the whole in-flight transaction, discarding every DELETE/UPDATE already executed for the earlier tables — yet `deleted_records`/`set_null_records` were already incremented for those rows and are never decremented. As a result the returned counts do not match the committed state, all prior cleanup is silently lost, and the loop then continues to `db.delete(user)`; with `PRAGMA foreign_keys=ON` (set in app/core/database.py) that delete can now raise an IntegrityError or leave dangling references, contradicting the 'preserve the reference' intent. The `except Exception` is also far broader than the 'column not yet migrated' case it is documented for, so locking/syntax/driver errors are swallowed and treated as benign. Use a savepoint for the audit UPDATE (or record the failure and abort the whole operation with a re-raise) instead of rolling back the shared transaction and continuing.

### `backend/app/services/user_service.py`

- **[security] L102** `update_user` 对调用方传入的任意键做 `setattr`，没有任何字段白名单，一次调用即可覆盖 `role`、`is_active`、`hashed_password`、`is_superuser` 等敏感属性，构成越权提升/凭据篡改通道（API 层对同样的直接 setattr 至少做了 PROTECTED_FIELDS 过滤，服务层却完全裸奔）。建议改为显式白名单，并在需要改角色时先做 `VALID_ROLES` 校验。

### `backend/app/services/validation_engine_service.py`

- **[bug] L112** `ValidationRule` has no `message` attribute — the column is `error_message` (see `app/models/validation_rule.py:44` and the sibling engine in `app/api/v1/validation.py:220` which uses `rule.error_message`). Accessing `rule.message` on a real ORM instance raises `AttributeError`, which is then swallowed by the broad `except` below, so `validate_with_db_rules` silently returns no errors and every payload is reported as valid in production (unit tests only pass because they mock the rule with a `message` attribute). Same problem at line 117.

- **[bug] L109** `ValidationRule.params` is a `Text` column holding a JSON string (see model comment `params = Column(Text, nullable=True) # JSON string`; the other engine does `json.loads(rule.params) if rule.params else {}`). Pushing the raw string into `_check_typed_rule` makes `params.get(...)` raise `AttributeError: 'str' object has no attribute 'get'`, which the broad `except` swallows — every range/regex/enum/length/positive/non_negative DB rule is silently skipped. Deserialize the JSON here (and guard against malformed JSON).

### `backend/app/services/village_cascade_delete_service.py`

- **[bug] L91** Early return leaves the pending dependent-table DELETEs in the session transaction without rolling back. `self.db.execute(...)` has already sent those DELETEs; if the session is later committed by the caller/session teardown (this method already delegates commit to `safe_commit`), the orphaned dependent rows of a non-existent village are permanently deleted even though `success` is False. Roll back before returning.

### `backend/app/utils/common.py`

- **[security] L282** Password hashing uses a single unsalted-iteration SHA-256 digest, which is extremely fast and therefore highly vulnerable to offline brute-force/dictionary attacks (plus CUDA/GPU cracking). Password hashes must be derived with a slow, vetted KDF such as bcrypt/scrypt/argon2, or at minimum PBKDF2 with a high iteration count.

### `backend/app/utils/upload_helper.py`

- **[security] L348** Path traversal: the default name is `f"{uuid}_{orig_name}"` where `orig_name` comes straight from the attacker-controlled multipart `filename`. Since the result still contains `/`/`\` and `..` segments, `os.path.join(upload_dir, unique_name)` escapes the upload directory (e.g. filename `x/../../../../etc/cron.d/evil`). The module docstring claims "禁止路径穿越", but only `sub_dir` is sanitized, not the filename. Strip any path components (and reject separators/traversal) before joining.

### `frontend/src/components/FilePreview.vue`

- **[security] L14** **Unsafe iframe rendering (XSS).** HTML content is rendered in an iframe via a `blob:` URL. Blob URLs inherit the app origin, and `type.includes('html')` also matches `application/xhtml+xml`; a malicious uploaded HTML file therefore executes scripts with full access to the app origin (parent DOM, `localStorage`/tokens). Add a `sandbox` attribute (without `allow-scripts`/`allow-same-origin`) for html/text, or keep HTML out of the inline allowlist and only preview PDF/text.

### `frontend/src/components/permission/MenuVisibilityPanel.vue`

- **[bug] L72** `default-checked-keys` is only a render-time default and cannot keep the tree in sync with `selectedMenuKeys`, which is mutated *after* mount by `loadUserMenuConfig` (async, awaited in `onMounted`), by the `currentMenuKeys` watcher and by `resetToDefault`. `menuTreeRef` is bound in the template but never used anywhere in the script (no `setCheckedKeys` call exists in this file), so the checkboxes the admin sees do not necessarily match the payload that `saveConfig` PUTs. In particular, after clicking “恢复角色默认” `selectedMenuKeys` becomes `null` → `|| []` → the tree is asked for an *empty* selection instead of the role-default keys, so the displayed state contradicts the meaning of `null`. Explicitly sync the tree state (and guard against feedback loops with the `@check` handler).

### `frontend/src/composables/useAutoLock.ts`

- **[bug] L34** `require('@/utils/authStorage')` cannot work in an ESM/Vite browser bundle (and the `@/` alias is not resolvable by CommonJS at runtime either). The call throws `ReferenceError: require is not defined`, so the whole default lock body is skipped: `clearSession()` / `markLockNow()` never run and auto-lock silently does nothing (the existing unit test even asserts this broken behaviour). Use a static ESM import instead.

### `frontend/src/composables/useRouterSafe.ts`

- **[security] L48** Open redirect / dangerous-scheme risk: `pathString` is derived from a caller-supplied value (plain string or `RouteLocationRaw`), which in practice can come from user-controlled sources such as the `?redirect=` query or a `backTo` prop. Assigning it directly to `window.location.href` performs an unvalidated navigation, so an absolute URL (`https://evil.com`) or a `data:`/`javascript:` payload would be honoured. Restrict the fallback to same-origin relative paths before navigating (the same guard is also needed at the two other `window.location.href` assignments in this function).

### `frontend/src/config/regionDictionary.ts`

- **[bug] L95** `detectRegionAttributes` hardcodes every region attribute to `false`, ignoring `city`/`county` entirely. This is not harmless: `ComprehensiveEntry.vue:945-950` calls it in `onRegionChange()` and writes the result straight back into `formData.basicInfo.isThreeRegionsThreeStates / isBorderArea / isEthnicArea / isRevolutionaryArea / isKeyCounty`, so any attribute the user set manually (or that was pre-filled from the backend when editing) is silently reset to `false` as soon as the province/city/county selectors change. Either implement the real classification logic or return `undefined`/only the `province` field so callers do not overwrite real data.

### `frontend/src/stores/auth.ts`

- **[security] L183** 2FA branch fall-through: the condition requires both `res.two_factor_required` **and** a truthy `res.temp_token`. If the backend flags 2FA but omits/returns an empty temp_token, control falls through to the normal-login branch and persists `res.data.access_token` as if 2FA verification had already succeeded — a potential auth-bypass. Branch on the flag alone and fail closed when the temp token is missing.

### `frontend/src/styles/components/prompt.scss`

- **[bug] L279** The keyframes hardcode `translate(-50%, -50%)`, but `.el-notification` and `.el-message-box` have no baseline transform (positioned by `right`/`top` or `.el-overlay` flex), so the animation shifts them by half their size; `.el-message` already uses `translateX(-50%)`. The comment claiming `main.ts` centers `.el-notification` is also incorrect. Split keyframes per component or fix the transform.

---

## HIGH (359)

### `backend/app/api/v1/ai_enhanced.py`

- **[performance] L104** These handlers are declared `async def` but perform no `await`; they call synchronous, CPU-bound code (Prophet fitting in `TrendPredictionService`, `IsolationForest`/`StandardScaler` in `AnomalyDetectionService`, which even runs Prophet through a `ThreadPoolExecutor` with a 10 s timeout while blocking). Executed directly on the event loop, a single request can stall all concurrent requests for seconds. Declare these handlers as plain `def` so FastAPI runs them in the threadpool (the same applies to `predict_trend` and the other AI handlers that call into these services).

### `backend/app/api/v1/approval.py`

- **[security] L996** Missing authorization on the diff endpoint: `get_task_diff` returns `change_data`/`original_data` for any `task_id`. Unlike the list endpoints, there is no check that the caller is the submitter, the approver, or an admin, so any authenticated user can read arbitrary approval payloads (including entity fields that may be sensitive). Add an ownership/role check before returning the diff.

### `backend/app/api/v1/auth/auth.py`

- **[bug] L911** 注册流程的事务边界不完整：`create_user` 内部已提交，之后才调用 `activate_machine_code` 认领通行码。当前代码只在“认领返回 False”这一条分支里显式删除用户；一旦 `activate_machine_code`（或随后的组织绑定 `safe_commit`）抛异常，就会落到这里的通用 `except`，只记日志并返回 400——用户已经被提交且没有机器码绑定，成为无法登录的孤儿账号（create_user 已提交，rollback 也不会撤销）。建议用一个 `created_user` 变量跟踪已创建的用户，在任何失败路径上删除该用户后再抛出；同时补上 `db.rollback()` 并保留原始异常。

- **[security] L370** 2FA 验证失败路径缺少暴力破解防护：验证码错误时只写审计日志并返回 401，既不递增 `failed_login_count`、不触发账户锁定（对比密码失败的 `_handle_failed_login`），也不吊销 temp_token。temp_token 有效期内（5 分钟）攻击者可在每 IP 5 次/分钟的限流下反复猜测 TOTP/备用码（多 IP 更宽松），且验证次数无上限。建议失败达到一定次数后调用 `get_lockout_service().record_failed(...)` 计入锁定阈值，并在失败次数超限（或验证码错误 N 次）时 `token_manager.revoke_token(verify_request.temp_token)` 强制重新走完整登录。

### `backend/app/api/v1/auth/two_factor.py`

- **[security] L46** The TOTP verification endpoint accepts an unlimited number of attempts with no rate limiting, lockout, or attempt counter, so an attacker holding a stolen access token can brute-force the 6-digit code (plus the ±1 window) online. The rest of the auth module already uses `check_rate_limit`/`get_client_ip` (see `app/api/v1/auth/auth.py`); apply the same pattern here (e.g. key on user id + client IP, limit ≈5/min) and consider locking the account/enroll flow after repeated failures.

- **[security] L70** Disabling 2FA only requires the active access token — no TOTP code, backup code, or password confirmation. A hijacked/CSRF-delivered request can therefore silently strip the second factor from the account, which defeats the purpose of enabling it. Require a fresh proof of the second factor (or password re-entry) before disabling.

### `backend/app/api/v1/auth/user_management.py`

- **[security] L235** `is_superuser(user_data)` is called on a Pydantic `UserCreate` model instead of a `User` object; `permission_utils.is_superuser` only reads `is_superuser` / `role`, so this is effectively `role == "super_admin"`. Combined with the `or user_data.role == UserRole.ADMIN` clause, every user created with the plain `admin` role is persisted with `is_superuser=True`, i.e. a normal admin can mint superusers — privileges far beyond the requested role (and beyond what `is_admin`/`is_superuser` semantics intend). `is_superuser` should be `True` only for the `super_admin` role, and the helper should be called with a real user object or replaced by an explicit role check.

- **[security] L288** Same privilege-widening bug as in `create_user`: passing the `UserUpdate` request model to `is_superuser()` makes it read `role` only, and `or user_data.role == UserRole.ADMIN` promotes any `admin` (or a legacy `manager`, since it isn't normalized here) to `is_superuser=True`. Only `super_admin` should set `is_superuser`.

### `backend/app/api/v1/auth/users.py`

- **[security] L698** Authorization check is inside the cached function body, so it is skipped on a cache hit. `cache_result` == `cached` (app/core/cache.py) and its wrapper returns `instance.get(ck)` before ever awaiting the wrapped coroutine — `require_admin(current_user)` only runs on a cache miss. Because the key is a constant ("role-options") and shared by all callers, the first authorized (admin) response is replayed to *any* authenticated user (e.g. role=viewer) for the next hour. The same defect applies to `get_data_scope_options` and `get_permission_options`. Fix by enforcing the check outside the cached function, e.g. move `require_admin` into a FastAPI dependency attached to the route (`dependencies=[Depends(...)]`) or a thin non-cached endpoint that calls the cached helper.

- **[security] L775** Missing target-privilege guard: `require_admin` only proves the caller is an `admin`/`super_admin` (permission_utils.is_admin), so an ordinary `admin` can reset the password of a `super_admin` account and then log in as it — a direct privilege escalation / account takeover. Add a guard before mutating the target, e.g. `if is_superuser(user) and not is_superuser(current_user): raise HTTPException(403, "无权重置超级管理员密码")`. (The same gap exists in `delete_user`, `update_user` and `update_user_permissions`.)

- **[security] L483** Privilege escalation: any admin can assign `super_admin` at creation time (VALID_ROLES accepts it), and `update_user_permissions` likewise lets any admin promote an arbitrary account — or themselves — to `super_admin`. Restrict privileged roles to superusers, e.g. reject when `role == "super_admin"` and `not is_superuser(current_user)` in `create_user`/`update_user`/`update_user_permissions`.

- **[security] L620** Only self-deletion is blocked; a normal `admin` can hard-delete a `super_admin` (or the last superuser) account. Add the same target-role guard as for password reset, and consider refusing to delete the last remaining superuser to avoid locking the system out.

### `backend/app/api/v1/batch_operations.py`

- **[security] L224** Authorization inconsistency: `batch_update`, `batch_delete` and `batch_export` all call `require_admin(current_user)`, but `/batch/validate` performs the same DB-backed existence checks (which can disclose which record IDs exist for the requested table) without any admin/role check. Any authenticated user can probe it. If admin-only is intended, add the same guard; if it must stay open to all users, document the intent explicitly.

### `backend/app/api/v1/control_package.py`

- **[security] L113** System-wide configuration is exported without any org scoping and without a superuser gate: any `admin` (department-level) can pull every `SystemConfig` value, which typically includes security-sensitive settings (lockout policy, SMTP/credentials, license keys). Either restrict the export to superusers or filter/allow-list the exported keys.

- **[security] L279** The import blindly applies every key/value pair from the uploaded package to the **global** `SystemConfig` table, with no allow-list and no superuser gate. Since this package is untrusted input (and the manifest tells the caller nothing about which configs are legitimate), a crafted package can rewrite security-relevant global settings unrelated to the target organization. Gate this block behind `is_superuser(current_user)` (returning 403 otherwise) and validate keys against an explicit allow-list before writing.

### `backend/app/api/v1/data/data/analytics.py`

- **[bug] L87** `date_range` and `filters` are accepted from the client but never forwarded to `AnalyticsService.get_dashboard_overview`, and the cache key `dashboard:{user_id}` does not include them either. A client requesting a filtered or date-scoped dashboard silently receives the unfiltered/global payload (and, on a cache hit, a payload cached for a completely different filter combination). Either forward these parameters into the service and incorporate them into the cache key, or remove them from the signature so the contract is not misleading.

### `backend/app/api/v1/data/data/dashboard.py`

- **[bug] L582** `get_recent_activities` returns `success_response(data=result)`, i.e. an envelope `{"code":..., "message":..., "success":..., "data": {"items": [...]}}` (see app/core/response.py:134). There is no top-level `items` key, so `.get("items", [])` always yields `[]` and `/summary` never returns any recent activity. Read the payload out of the `data` envelope instead.

- **[security] L695** The activity fetchers (`_fetch_project_activities` / `_fetch_fund_activities` / `_fetch_approval_activities` / `_fetch_custom_activities` / `_fetch_hidden_activities`) filter only on `is_active` and receive no `OrgScopeFilter`, and this cache key is global (not per user/org). As a result every caller sees other organizations' projects, funds, approvals and custom activities, and `DELETE /recent-activities/{id}` inserts a global row in `HiddenDashboardActivity`, letting any user hide other orgs' activities for everyone. Apply `data_scope` (as the stats queries do) and scope the cache key to the caller.

### `backend/app/api/v1/data/data/data_packages.py`

- **[security] L364** Missing authorization: `/preview` resolves the target org from the caller-supplied `data.org_id` via `get_org_with_fallback` but never calls `permission_service.can_access_organization`, unlike the `/export` endpoint right below. Any authenticated user can pass another organization's `org_id` and read its per-data-type record counts. Add the permission service dependency and the same 403 check used by `/export`.

- **[security] L1436** Missing authorization: `/decrypt-preview/{package_id}` performs no package lookup, no `can_access_organization` check and no `require_admin`, while the sibling `confirm_import` endpoint enforces both. Any authenticated user can decrypt and preview an arbitrary package (including other orgs') if they know/guess a package id. Fetch the package and enforce the same org check (and admin requirement where appropriate) before decrypting.

- **[security] L1473** Missing authorization: `/confirm-import/{package_id}` never loads the package nor checks `package.org_id` / `require_admin` before applying `confirm_import_with_conflict_resolution` (which overwrites/MERGES business data). Any authenticated user can apply an import to an arbitrary package. Add the package lookup, `require_admin` and `can_access_organization` checks as done in `confirm_import`.

- **[security] L863** Org-scope bypass: when `package.org_id` is falsy the permission check is skipped entirely, and the subsequent import then runs with `org_id or 0`, writing imported records under a bogus organization id 0. Reject packages without an org (or require an explicit authorized org id) instead of silently skipping the check.

### `backend/app/api/v1/data/data/data_quality.py`

- **[security] L49** The handler swallows every exception and returns `success_response` (HTTP 200) with the raw `str(e)` in the payload. This masks real failures from the caller/monitoring and leaks internal error/database details to any authenticated user (information disclosure). Return a proper error status (e.g. `raise HTTPException(status_code=500, detail="数据质量报告生成失败")`) and keep the full exception only in the log.

### `backend/app/api/v1/data/data/data_reports.py`

- **[bug] L69** `total` is set to the number of rows returned on the current page, not the total number of matching records. Clients paging through results will see a wrong total (e.g. page_size=20 shows total=20 even when 500 reports exist). Compute a real count with the same filters (e.g. add a `count_subordinate_reports`/`count_submitted_reports` helper on the service) before applying `offset`/`limit`.

- **[bug] L121** Same pagination defect as `list_data_reports`: `total=len(reports)` reports only the current page size, so the client can never know how many pending reports actually exist. Use a count query with the same `target_org_id` + `status` filters.

### `backend/app/api/v1/data/data/reports.py`

- **[security] L706** IDOR: the subscription branch of `generate_report` fetches the subscription by id without an ownership/admin check, so any authenticated user can read another user's subscription (`report_type`, `year`, `village_ids`) and have the report built from it. Add an owner/superuser filter (mirroring `generate_subscription_now`) before using `sub`.

### `backend/app/api/v1/data/data/statistics.py`

- **[security] L686** Data-isolation bypass: `_scoped()` (apply_scope_filter) is applied only to `total_villages` and the two fund totals, while the category sub-table aggregations (`cat_stats` loop), the consumption/employment aggregations and the `county_data` region distribution all run on raw `db.query(...)` with only an `is_active` filter. An org-scoped (OWN_DEPT / non-admin) user hitting `/statistics/analysis` therefore receives other organizations' category investment figures, county-level distributions and totals. Every aggregation that joins `SupportedVillage` here should be scoped consistently (`_scoped(db.query(...)...)`), as was done for the village/fund queries.

- **[bug] L77** Completeness can exceed 100%. `total_checks` is derived from `total_villages` (the count of **active** villages) but none of the numerator queries filter `SV.is_active` — the four field counts, the coordinate count, and the distinct `VP`/`VI` village counts all span the full table, including soft-deleted villages (and populations/income rows whose village was soft-deleted). `passed` can therefore exceed `total_checks`, and the returned percentage is only clamped later by `min(100, completeness)` in the health score, while `completeness` itself and `filing_rates`/`/analysis.overview.completeness` surface values > 100. Add `SV.is_active.is_(True)` to every sub-count (and a join on the active village for the population/income distinct counts), or clamp the result.

### `backend/app/api/v1/data_quality.py`

- **[bug] L109** For this `POST` endpoint, parameters annotated with a plain container type (`records: list`, `key_fields: list`) are bound by FastAPI as **query parameters**, not as a JSON body — only a Pydantic model or an explicit `Body(...)` produces a request body. The sibling endpoints use `ValidateDataRequest`/`CleanDataRequest`, and the API doc lists `/data-quality/deduplicate` as a POST, so clients sending a JSON payload will always get 422. Wrap the payload (ideally also `similarity_threshold`) in a Pydantic model, or declare the params with `Body(...)` (needs `from fastapi import Body`).

- **[bug] L177** `getattr(model, "is_active", True)` falls back to the Python bool `True` when the model has no `is_active` column, and `True == True` is then handed to `filter()`. `RuralWork` has no `is_active` column (see `app/models/rural_work.py`), so `entity_type="rural_work"` always reaches `db.query(RuralWork).filter(True)`, which SQLAlchemy 2.0 rejects as an invalid SQL expression (ArgumentError → 500); at best it is a silent no-op that skips soft-delete filtering. Build the condition explicitly per model instead of relying on a truthy default.

### `backend/app/api/v1/data_sync.py`

- **[bug] L111** The `HTTPException(400, "时间格式错误")` raised inside this `try` is caught by the generic `except Exception` and re-wrapped as a `BusinessError`, so a client input error is turned into a 5xx and the intended status code is lost. `export_encrypted_data` already does the right thing by re-raising `HTTPException` — apply the same here. Note the re-raise also drops the original traceback; add `from e`.

- **[bug] L189** Both the `HTTPException(400, "无效的数据包名称")`/`HTTPException(400, "无效的数据包路径")` raised above and the `NotFoundException` (404) raised for a missing package are swallowed here and converted into a generic `BusinessError`, so legitimate client/404 responses become 5xx. Re-raise `HTTPException` and `NotFoundException` before this handler (and keep the original cause with `from e`).

- **[bug] L219** Two problems here: (1) `_safe_filename` raises `HTTPException(400, "不支持的文件类型")` for files outside the extension whitelist, but that rejection is swallowed and re-wrapped as a `BusinessError`; (2) if `_save_upload_file` fails after the `open()` (e.g. the size/format check above fires, or a disk error mid-write), `file_path` is still `None`, so the `finally` block never removes the partially written file and it accumulates in `data_sync/uploads`. Handle `HTTPException` separately and track the destination path before writing so cleanup can always run.

- **[bug] L255** Same issue as `/import`: the `HTTPException(400)` raised by `_safe_filename` for disallowed extensions is caught by the generic handler and reported as a `BusinessError`, and a partially written upload file is leaked when the save fails (because `file_path` is only assigned after `_save_upload_file` returns).

- **[bug] L277** `conflict_id`, `resolution` and especially `merged_data` have no `Body()`/Pydantic model, so FastAPI binds them as *query parameters*. A `dict` cannot be reliably supplied through the query string, so resolving a conflict with merge data (the documented frontend contract, which sends a JSON body) will 422 or silently receive no `merged_data`. Introduce a request model and bind it to the body.

### `backend/app/api/v1/deps.py`

- **[security] L50** `require_funds_operator_role` uses a denylist (`role == "viewer"`), so it fails open: `normalize_role()` explicitly returns unknown/invalid role values unchanged (see `app.core.constants.normalize_role` docstring: "未知值原样返回（由调用方校验）"), and this caller never validates them. Any unexpected role (`"Guest"`, `"Auditor"`, a newly added or typo'd value, or a `None`/empty user whose role normalizes to `"user"`) passes the guard and is granted the full funds write flow (create/approve/pay/settle). Use an explicit allowlist so the guard fails closed.

### `backend/app/api/v1/feedback.py`

- **[bug] L138** This `write_work_log` call can never persist anything. `write_work_log` expects the operator via `user_id` (NOT NULL) / `username`, but here only `user_name` is passed — which is not a `WorkLog` column (`backend/app/models/work_log.py` has `user_id`, no `user_name`) and is therefore dropped by the `_WORKLOG_COLS` filter. Worse, because `user_id` is absent (`None`), `work_log_service.write_work_log` returns early with only a warning (`work_log_service.py:82-89`) — so the audit trail for feedback submission is silently never written, contradicting the repo rule that write operations must call `write_work_log()`. Pass the resolved user id + `username=` (and decide how anonymous submissions are represented, since `WorkLog.user_id` is NOT NULL).

### `backend/app/api/v1/fund_budgets.py`

- **[security] L188** `update_budget` (and `delete_budget`) fetch the record by id **without** applying the data scope, unlike `get_budgets`/`get_budget_alerts`/`get_budget_summary` which all call `apply_data_scope`. A department-level admin (`DataScope.OWN_DEPT`) can therefore update/delete budgets belonging to other organizations simply by guessing the id. The codebase already provides `check_record_access` for single-record checks (used the same way in `fund_lifecycle.py`).

- **[security] L387** `delete_transaction` loads the transaction by primary key with no data-scope check, so a manager can delete another organization's/user's expenditure record and roll back the linked budget/Fund balances. Add the same `check_record_access(tx, current_user)` guard (import it from `app.core.data_permission`) before mutating.

- **[bug] L476** Attachment metadata is persisted into the user-facing `remarks` field. Uploading an attachment silently overwrites whatever notes the user wrote in `remarks`, and conversely a later `PUT /fund-budgets/{id}` that sets plain-text `remarks` destroys the attachment list (the JSON parse then fails and `_get_attachments` returns `[]`). These are two unrelated data concerns sharing one column; store attachments in a dedicated column/table (or a separate JSON field) instead of clobbering `remarks`.

- **[bug] L354** Read-validate-write race / lost update: `executed_amount` is read, the 100% cap is checked, and then the value is *assigned* as `current + tx_amount` from a stale in-memory value. Two concurrent requests (or two workers) that both read the same starting value will each pass the cap check and the second commit overwrites the first increment, so `executed_amount` under-counts and the 100% cap can be bypassed. The same pattern applies to `fund.used_amount`/`remaining_amount` below. Use an atomic guarded UPDATE (`UPDATE fund_budget SET executed_amount = executed_amount + :amt WHERE id = :id AND executed_amount + :amt <= budget_amount` and verify `rowcount`) or reload the row with `with_for_update()` inside the transaction.

### `backend/app/api/v1/fund_lifecycle.py`

- **[security] L207** `advance_phase` only checks the role (`_require_manager`) but never loads the Project or calls `check_record_access`/`_get_project_or_403`. Any funds operator can advance the lifecycle phase of a project belonging to another organization (IDOR / broken object-level authorization). Additionally, `_init_phases(db, project_id)` is called without verifying that the project exists, so a bogus project_id hits the FK constraint and surfaces as a 500. Add the same project-level 404/403 guard used by the other endpoints.

- **[security] L250** `rollback_phase` has the same authorization gap as `advance_phase`: it only enforces the operator role and then reads/writes `ProjectFundPhase` rows by raw `project_id` for any organization, and it also mutates `Fund.lifecycle_phase` without a data-scope check on the funds. Add the project access guard.

- **[security] L396** `lock_budget` writes `BudgetBaseline` snapshots (and flips `budget_locked` on every fund) for an arbitrary `project_id` without any project-level 404/403 check — a funds operator from one organization can lock another organization's budgets. The same pattern exists in `detect_anomalies` (see the `"""触发智能异常检测"""` handler), which runs detection over a foreign project. Call `_get_project_or_403` before touching the data.

- **[bug] L794** `TransferVoucherUpdate` includes a free-form `status` and this loop blindly `setattr`s every supplied field, so a caller can PUT `{"status": "confirmed"}` and skip `/confirm` entirely. That leaves `confirmed_by`/`confirmed_at` unset while all budget accounting (`transfer_ledger`, the available-balance sum in `create_transfer_voucher`) treats the voucher as confirmed, and `delete`/`update` guards no longer apply. Only allow status transitions through the dedicated endpoints (or validate the value against `VoucherStatus` and fill the confirmation metadata when moving to `confirmed`).

- **[bug] L1255** `f.deviation_rate` is assigned for every fund but the handler never commits — it only calls `db.flush()` before returning. `get_db` (backend/app/core/database.py) yields the session without committing and just closes it, discarding the pending transaction, so the deviation rates are silently lost even though the response reports them as computed/recorded. Commit the updates (e.g. `safe_commit(db)`) before building the response.

### `backend/app/api/v1/funds.py`

- **[bug] L402** 软删记录仍可被访问/修改：这里只施加了数据权限过滤，没有排除 `is_active=False`。于是 `_get_fund_or_404` 的调用方（approve/reject/allocate/start-use/complete/audit 以及附件上传/删除、history 等）都能对已软删的经费继续做状态流转或挂附件，与 `list_funds` 默认隐藏软删记录的行为不一致；`get_fund` 详情同样会把软删记录返回给非管理员。建议默认排除软删，仅管理员通过 include_deleted 参数显式查看（`get_fund` 中的查询语句也需同样处理）。

### `backend/app/api/v1/import_export/async_export.py`

- **[performance] L132** `export_reports` (and `export_villages`, `get_export_status`, `download_export_file`, `get_export_tasks`) are declared `async def`, yet they execute fully synchronous, blocking work on the event loop: SQLAlchemy queries via `AsyncExportService` and CPU-bound Excel generation (`ExcelExportService`/openpyxl) for up to MAX_EXPORT_ROWS rows, plus a full-table `COUNT(*)` from `should_use_async`. While one request runs, every other request on the same worker is stalled. Prefer declaring these handlers as plain `def` (FastAPI runs sync endpoints in a thread pool) or offload the heavy calls with `starlette.concurrency.run_in_threadpool`.

### `backend/app/api/v1/import_export/chunked_upload.py`

- **[bug] L72** `InitUploadRequest.file_size` only has `gt=0`, but `ChunkedUploadService.create_session()` raises `ValueError` when `file_size > ChunkedUploadConfig.MAX_FILE_SIZE` (2GB). Since there is no `ValueError` exception handler registered anywhere in the app, a client sending e.g. `file_size = 10**12` gets an HTTP 500 instead of a 4xx validation error. Either constrain the field at the schema level or translate the service error into an `HTTPException`.

- **[bug] L114** `ChunkedUploadService.upload_chunk()` signals every client-side failure by raising `ValueError` (session expired, session already MERGED/MERGING, `chunk_index` out of range, chunk size mismatch, hash mismatch). None of these are caught here and no global `ValueError` handler exists, so all of them surface as HTTP 500. Wrap the call and map `ValueError` to 400 (or 409/404 depending on the case).

- **[bug] L161** Two problems in this block: (1) `ChunkedUploadService.merge_chunks()` raises `ValueError` for user-visible failures (incomplete upload / missing chunks / session gone / hash mismatch) and those are unhandled, so they become HTTP 500. (2) Because the service either raises or returns a non-empty path, `if not file_path:` is effectively unreachable and masks mismatch errors; it should be removed once `ValueError` is translated properly.

### `backend/app/api/v1/import_export/export.py`

- **[bug] L328** Soft-deleted rows leak into the comprehensive report: unlike the counts above and unlike every other endpoint in this file (all of which filter `is_active`), the sample `Project`/`Fund` queries here have neither an `is_active` filter nor a `scoped_filter`, and no deterministic ordering. Deleted projects/funds will appear in the exported workbook, contradicting the M1 filtering口径 used elsewhere. Apply the same filters to both queries (the `funds = db.query(Fund).limit(100).all()` line below has the identical problem).

### `backend/app/api/v1/import_export/import_data.py`

- **[bug] L252** Size-limit inconsistency that defeats the stated memory bound. The comment above `_IMPORT_MAX_FILE_SIZE` says the limit matches `DataValidatorService/EntityImportValidator.MAX_FILE_SIZE=10MB`, but this path uses `settings.MAX_FILE_SIZE` (currently 50MB). Consequences: (1) a 40MB upload is fully materialized in memory here (the OOM protection the comment claims is 5x looser than intended) before it is rejected; (2) `/validate` and `/preview` reject >10MB with HTTP 400 while `/entities` accepts the read and then returns HTTP 200 with `success=False` (the downstream `validate_file_size` rejects it), so the same file gets different status codes/behaviour per endpoint. Use the same module constant here.

### `backend/app/api/v1/map.py`

- **[bug] L414** Cache-hit path returns the raw `result` dict, while the cold path returns `success_response(data=result)`. Within the 10-minute TTL the same request alternates between two JSON shapes (with/without the `success`/`data` envelope), breaking clients that rely on the standard envelope. Wrap the cached value with `success_response` (or cache the already-wrapped response).

- **[bug] L439** Unlike `/markers` (which passes `v.id`/`v.village_name`), this call omits the record identity for villages, so `_get_coords` falls back to record_id=None / name="" and the MD5 seed becomes identical for every village in the same county that lacks stored coordinates. All such villages collapse onto exactly the same estimated point (and identical distances), making the distance ranking meaningless. Pass the village id and name for consistency.

- **[security] L410** The cached payload is built from `data_scope`-filtered rows but the cache key only contains `user_id`. A change in the user's org scope (or an org reassignment) keeps serving previously authorized rows for up to 10 minutes, leaking data outside the current permission set. Also, any user object lacking `id` falls back to 0, so unrelated users share the key `map_distances:0`. Include the resolved data scope (org ids / scope fingerprint) in the cache key.

### `backend/app/api/v1/messages.py`

- **[bug] L154** `end_date` parsed from a date-only string (e.g. `2026-09-17`) becomes midnight 00:00:00, while `MessageService.get_messages` filters `Message.created_at <= end_date`. Messages created later on the end day are therefore silently excluded, so a same-day filter drops nearly all of that day's messages. Normalize an end-of-day boundary (or have the caller pass `end_of_day=True`). Note also that an unparseable value returns `None` and the filter is silently ignored instead of surfacing a 422.

### `backend/app/api/v1/monitoring/data_tier.py`

- **[bug] L77** `before_days` and `batch_size` are taken as raw ints with no lower bound. A negative `before_days` places `before_date` in the future, which selects essentially every record and (for the cold tier) physically exports and DELETEs them; an unbounded `batch_size` can also blow up memory. Constrain them (e.g. with `Query(ge=..., le=...)`).

- **[bug] L216** `max_age_days` is unvalidated. A negative value makes `cutoff_date` a future timestamp in `cleanup_old_archives`, so every archive file (`mtime < cutoff_date`) is deleted — an irreversible data-loss path reachable by a single bad query string. Require a positive value.

- **[security] L206** `archive_file` is passed straight through to `restore_from_archive`, which resolves it as `Path(COLD_ARCHIVE_PATH) / archive_file`. Values such as `../../etc/passwd` (or an absolute path) escape the archive directory and allow arbitrary file reads (path traversal). Validate the input: allow only a bare file name and verify the resolved path stays inside `COLD_ARCHIVE_PATH`.

### `backend/app/api/v1/monitoring/metrics.py`

- **[security] L38** This endpoint has no authentication dependency, unlike `/business` and `/performance-dashboard` in the same router, so any anonymous caller can read internal business KPIs (fund approval success rate, pending approval count, total fund amount, error rates — see `business_metrics_service.get_all_metrics`). Unless the endpoint is deliberately restricted at the ingress layer, add the auth dependency or a scraper token check so business indicators are not publicly exposed.

### `backend/app/api/v1/monitoring/secrets.py`

- **[bug] L82** `keep_days` is taken straight from the client with no bounds check. In `SecretsManager.cleanup_expired_keys` the cutoff is computed as `time.time() - keep_days * 86400`, so a negative value (e.g. `?keep_days=-100000`) pushes the cutoff into the future and makes `revoked_at < cutoff_time and created_at < cutoff_time` true for every inactive version — permanently deleting all revoked keys regardless of the intended retention window. Add a lower bound (and a sane upper bound) via FastAPI validation.

### `backend/app/api/v1/monitoring_legacy.py`

- **[performance] L35** Blocking synchronous DB work inside an `async def` handler. `MonitoringService.get_api_performance_stats` runs SQLAlchemy sync queries (e.g. `db.query(APIMetric)...all()`) on the event-loop thread, which stalls all concurrent requests. The sibling `/resources` endpoint already offloads via `run_in_threadpool`; do the same here (and in the other two stats handlers below).

- **[performance] L55** Same issue as above: the synchronous `get_endpoint_stats` query is executed directly on the event loop, blocking other requests while the aggregate query runs.

- **[performance] L74** Same issue as above: the synchronous `get_error_stats` query is executed directly on the event loop, blocking other requests.

### `backend/app/api/v1/organization.py`

- **[security] L702** A plaintext password (confirmation/second-admin) is accepted as a query-string parameter, so it is written into access logs, browser history and `Referer` headers. Read it from a request body (Pydantic model) instead of `Query(...)`.

- **[bug] L520** Despite the name (and the `include_self` flag), this endpoint ignores `current_user` entirely and returns the whole organization table: `include_self=False` only filters out root orgs (`parent_id IS NOT NULL`) and `include_self=True` returns every org. Both the contract and the access scope are wrong — no caller ever receives “its subordinates”. Filter by the caller's own org (`Organization.path.like(f"{current_org.path}%")` plus an id exclusion when `include_self=False`).

### `backend/app/api/v1/policy.py`

- **[security] L587** Several `Policy` queries omit the soft-delete filter `Policy.is_active.is_(True)` (and, for search/export, the visibility rule used by the list endpoint). Deleted/draft policies therefore remain readable through detail, related-policies, favorites, export and global search. Add the `is_active` filter (and status/creation visibility where applicable) consistently.

### `backend/app/api/v1/projects.py`

- **[bug] L1699** 导入表头映射与系统自带模板不一致，导致模板列被静默丢弃，甚至整份模板导入 0 条。 `/import/template` 由 `ExcelTemplateService.generate_project_template()` → `EntityImportValidator.PROJECT_FIELDS` 生成表头，实际列名为：项目名称、项目编号、项目类型、项目状态、项目描述、预算金额、开始日期、结束日期、项目负责人、联系电话、负责单位、关联村庄、组织编码；且 `_write_data_table` 会给必填列加 `*` 前缀（如 `*项目名称`、`*项目类型`）。 本字典里既没有 `项目编号`/`项目负责人`/`关联村庄`/`组织编码`，又多了 `项目代码`/`负责人`/`所属村庄`/`项目目标`/`已投入金额`/`项目进度`/`紧急程度`/`经费来源`；`_detect_import_headers` 只做 `strip()`，不会去掉 `*`，因此 `*项目名称` 永远不会命中 `name`，`_process_import_rows` 中 `if not data.get("name"): continue` 会跳过每一行，最终返回“导入完成：成功 0 条”。同理 `example_hints`（XX村饮水安全工程/某某帮扶单位/张三）也与模板示例（村内道路硬化项目/某帮扶单位/张三）不匹配。 建议：在 `_detect_import_headers` 中对表头做规范化（去掉 `*`、空白）并按别名表匹配，或直接把本字典的键对齐模板标签（补充 项目编号/项目负责人/关联村庄/组织编码，并让 `_build_import_project` 真正消费 village/leader 列）。

### `backend/app/api/v1/recycle_bin.py`

- **[bug] L244** 批量恢复的状态标记重置没有把范围限定在「本次真正从回收站恢复」的记录上：`model.id.in_(ids)` 会把传入的所有 id 都查出来，其中**本来就活跃**、而 status 恰好是 `cancelled` 的（例如已被别的流程取消/停用但未软删）记录，会被静默改写为 `planned`，属于越界的数据篡改。此外该 update 与状态重置分两次 `safe_commit`，若第二次提交前进程中断，就会出现「已恢复但仍被 cancelled 标记过滤」的老问题。建议在 bulk update **之前**先取出确实处于回收站中的 id，只对这些 id 重置状态，并在同一事务内一次提交。

- **[bug] L270** 批量彻底删除缺少逐条错误隔离与失败上报：`svc.purge()` 内部会自行 commit，循环中只要有一条抛异常，前面已物理删除的数据就无法回滚，但后续的审计日志与即时备份都不会写入，客户端只会拿到 500，且被跳过的 id 仅表现为计数变小，管理员无法知道哪些没删成功。建议对单条 purge 加 try/except 收集 failed_ids，在 finally 中保证审计与备份执行，并在 total == 0 时不要触发一次昂贵的全量备份。

### `backend/app/api/v1/report_templates.py`

- **[security] L416** Missing authorization/validation on update. Every endpoint only depends on `get_current_user`, so any authenticated user can update (or delete) any template by id, even though the module contract says templates belong to their creator/assignee. Additionally, `update_template` applies `model_dump()` values blindly via `setattr` while `create_template` validates `type`/`module` against `VALID_TEMPLATE_TYPES`/`VALID_TEMPLATE_MODULES` — so a user can set an arbitrary `module`/`type` through the update path, leaving templates that later fail with 400 in upload/download. Add an ownership/role check and reuse the same whitelist validation here.

- **[security] L1276** The confirm-mode import path performs destructive writes (including `overwrite` deletions) for any template id without any ownership/role check — `get_current_user` alone is the only guard. A non-admin (or a user who is not the template owner/assignee) can trigger a bulk delete+import on another user's template. Before dispatching to the `_import_*` helpers, verify the caller is allowed to use this template (creator/assignee/admin) and, for `import_mode == "overwrite"`, require an elevated role.

- **[bug] L570** Data-start row collides with the required-field annotation row written by `download_template`. That endpoint writes `"(必填)"` into row 3 for every required column, while this parser treats row 3 as the first data row (`min_row=3`). Because row 3 is no longer all-`None`, the guard below does not skip it, so a round-tripped file produces a bogus first record filled with `"(必填)"` strings — and since those cells are non-empty, the required-value check passes and the bogus row is imported. Either move the annotation out of the data range (e.g. a legend row after the data / separate sheet) or start parsing at row 4.

### `backend/app/api/v1/rural_tasks.py`

- **[security] L235** Mass assignment / workflow bypass. `RuralTaskUpdate` exposes `status`, `result`, `progress`, `actual_cost`, `actual_start`, `actual_end`, so `model_dump(exclude_unset=True)` + `setattr` lets any owner write approval-controlled state directly (e.g. `{"status": "approved"}`) without going through `/submit` or `/approve`, and to mutate fields the dedicated endpoints are supposed to own. Whitelist the mutable fields instead of blind `setattr` (dropping non-column keys also prevents an unexpected AttributeError/500).

### `backend/app/api/v1/subordinate_reports.py`

- **[security] L41** These sensitive endpoints only require any authenticated user (`get_current_user`), while sibling/read or corresponding admin endpoints enforce `require_admin`. This allows non-admins to export bulk PII, redirect backups, disable/rewrite the backup schedule, or enumerate config packages. Add an explicit admin/role guard consistent with the rest of the module.

### `backend/app/api/v1/supported_village.py`

- **[security] L532** 列表缓存键只包含 `organization_id` + 查询参数，但返回结果实际由 `apply_scope_filter(query, current_user, ...)` 决定。该过滤器依赖用户的角色/data_scope（`data_scope="self"` → 仅本人、`OWN_DEPT` → 组织子树、admin/`all` → 不过滤，见 app/core/data_permission.py:447-513）。同一组织内权限不同的用户（例如「仅本人」用户与「本部门及下级」用户）会互相命中对方的结果缓存，导致跨用户数据范围泄露（越权读取他人创建/其他下级组织的帮扶村）。建议把数据范围本身纳入缓存键（如 `get_data_scope(current_user)` / `user.data_scope` / 用户 id），或对非 admin 用户直接跳过列表缓存。

### `backend/app/api/v1/system/__init__.py`

- **[bug] L38** The sub-router registration wraps both the import and `include_router(...)` in `except Exception` and only warns, so a genuine defect in an existing module (broken import, route conflict) leaves the application running with those endpoints silently missing, and the traceback is discarded. Narrow the try to the import, log with `exc_info`, and re-raise (fail-fast) instead of swallowing.

### `backend/app/api/v1/system/audit.py`

- **[bug] L46** These coercion helpers assume the value is a list. A string payload is iterated character by character (e.g. `"12"` becomes `[1, 2]`, `"login"` becomes `['l','o','g','i','n']`), silently targeting the wrong records, and a scalar raises `TypeError` (500). Normalize string/scalar inputs into a single-element list before iterating.

### `backend/app/api/v1/system/cache.py`

- **[bug] L33** Concurrency: `SimpleCache` guards `_store` with `self._lock` (it is documented as a thread-safe cache), but this handler reads `len(backend._store)` and iterates it without acquiring that lock. Sync endpoints using the `cached` decorator execute `get`/`set` in FastAPI's threadpool, so they can mutate `_store` while this async handler iterates it on the event loop, causing `RuntimeError: dictionary changed size during iteration` (swallowed into a generic 500) or torn statistics. Read a locked snapshot instead.

### `backend/app/api/v1/system/config_package.py`

- **[bug] L166** `str(value)` breaks round-trip fidelity for non-string values: a nested dict/list exported by `export_config()` becomes a Python repr such as `{'a': 1}` (single quotes, not valid JSON), and booleans become `"True"` instead of `"true"`. Consumers calling `svc.get_json()` on such a key will then fail to parse it. `SystemConfigService.set()` already normalizes bool → `"true"/"false"` and dict/list → `json.dumps(...)`, so the coercion here is both unnecessary and harmful.

### `backend/app/api/v1/system/init.py`

- **[bug] L116** Non-atomic check-then-act on the initialization guard: `/initialize` has no authentication dependency and `svc.is_initialized()` is a plain config read followed by many writes. Two concurrent first-boot requests can both observe `False`, then both run `initialize_defaults()`/`set()`/admin creation, producing duplicate/conflicting configuration and racing admin usernames. Guard the transition atomically (e.g. a DB-level unique/conditional update or an exclusive lock) before performing the writes.

- **[bug] L171** Hardcoded `org_id=1`: the docstring claims step 2 "创建根组织单位", but no organization record is created anywhere in this handler — only `organization_id` is written into system config pointing at an organization with id 1 that may not exist. This yields a dangling reference / wrong org binding (and any data-scope filtering based on the configured organization id will misbehave). Either actually create the root organization and use its id, or derive the org id from an existing record instead of assuming 1.

### `backend/app/api/v1/system/metrics.py`

- **[bug] L173** Inverted threshold evaluation: the `> 80` test is evaluated first, so any value above 95 still yields `"warning"` and the `"critical"` branch is unreachable dead code. Severe load is silently mis-labelled as a warning. Test the higher threshold first. The identical pattern is repeated for `memory.percent` and `disk.percent` below and must be fixed there too.

- **[bug] L297** Ordering ascending combined with `limit(500)` returns the 500 *earliest* rows in the window and discards the newest samples — the opposite of what a history/monitoring view needs. Order descending to keep the most recent records, then reverse in Python if the response must stay chronological.

### `backend/app/api/v1/system/system.py`

- **[bug] L245** Windows 重启存在端口占用竞态：`subprocess.Popen` 会立刻拉起新进程并开始绑定监听端口，而父进程此时仍持有该端口（要等到后面的 `_graceful_shutdown()` 走完 lifespan 才会释放）。uvicorn 在 Windows 上会设置 `SO_EXCLUSIVEADDRUSE`，子进程绑定必然失败并以 “address already in use” 退出，结果重启后服务直接不可用。建议由父进程先完成优雅关闭、再由一个独立/延迟的 helper（或让子进程带重试等待端口释放）拉起新进程。

### `backend/app/api/v1/system/system_config.py`

- **[performance] L47** All endpoints here are declared `async def` but perform blocking synchronous SQLAlchemy work (`SystemConfigService.get/set/delete`, `export_config`, `import_config`, `write_work_log`, and the underlying `safe_commit`). Under the FastAPI event loop these blocking calls stall every other concurrent request for the duration of the DB round-trip. Either declare the handlers as plain `def` (FastAPI then runs them in a threadpool) or offload the service calls via `run_in_threadpool`. This pattern applies to every endpoint in this module, not just this one.

- **[bug] L144** `SystemConfigService.import_config` only catches `json.JSONDecodeError`/`TypeError`. Passing valid JSON that is not an object (e.g. `[1,2]`, `"abc"`, `123`) makes `configs.items()` raise `AttributeError`, which is not caught and therefore surfaces as a 500 instead of the intended 400. The imported keys are also not whitelisted, so an admin-supplied payload can create/overwrite arbitrary config keys. Validate here that the parsed payload is a JSON object and restrict keys before delegating, or harden `import_config` to return `False` for non-mapping payloads and roll back on partial failure.

- **[security] L210** Configuration values (and descriptions) are accepted as URL query parameters. Config values can contain sensitive material (paths, tokens, identifiers) and query strings are routinely recorded in access logs, reverse-proxy logs, and browser history. Accept `value`/`description` in a JSON request body (e.g. a Pydantic model) instead of `Query(...)` so secrets are not persisted in URLs.

### `backend/app/api/v1/system/tasks.py`

- **[bug] L237** `_execute_task` runs on a Starlette threadpool worker (sync background task) and writes `status`/`progress`/`message` directly into the shared record without holding `_tasks_lock`. Two consequences: (1) readers (`list_tasks`, `get_task`, `get_task_stats`) can observe torn multi-field state; (2) a user cancel performed between the `_tasks.get()` here and the writes below is silently reverted — the record ends up COMPLETED even though `cancel_task` already returned "已取消" to the client. Re-read the record under the lock and bail out when it has already reached a terminal state.

### `backend/app/api/v1/system/update_logs.py`

- **[bug] L235** `record.version` is read after `db.delete(record)` + `safe_commit(db)`. With the default `expire_on_commit=True`, the committed (and now deleted) instance is expired, so this attribute access triggers a refresh that raises `ObjectDeletedError`, turning an already-successful delete into a 500. Capture the version before deleting.

- **[security] L278** The `except Exception as e` branch reports `"success": True` even when the version check failed, so callers cannot distinguish a successful check from a crash. It also embeds `str(e)` in the response, leaking internal exception details to the client. Return a failure indication and log the exception server-side instead.

### `backend/app/api/v1/system/zero_trust.py`

- **[bug] L318** Trust score is never derived from the reported `factors`: `total_score` starts at 100 and only ever decreases by the two hardcoded deductions (`-40` for unauthenticated, `-10` for non-HTTPS). The factor scores (25/15/10/10/5) are appended to `factors` but never summed, so the returned `score` (always 100, or 90 without HTTPS) contradicts the factor detail and the level is effectively hardcoded to `trusted`. Aggregate the factor scores instead so the score/level reconcilable with the returned `factors` (and remove the duplicated manual deductions).

- **[security] L450** Missing authorization on the audit-log read endpoints. `/events` (and `/events/stats` below) only require an authenticated user, so any logged-in user can enumerate every security event, including other users' `username`, `source` and `details`. Add a role/superuser check (e.g. `is_superuser`) or restrict results to the current user's own events.

### `backend/app/api/v1/system_health.py`

- **[bug] L94** `EXTRA_INDEXES` entries are `(table_name, index_name, columns)` (see `app/core/database_indexes.py`), so unpacking `idx_name` from the first element actually collects **table** names, then compares them against real index names read from `sqlite_master`. `missing` will therefore always contain the table names (e.g. `fund_budgets`), so the endpoint permanently reports "缺少预期索引: ..." even on a perfectly indexed DB — the check is effectively useless and misleading. Unpack the second element instead.

### `backend/app/api/v1/todos.py`

- **[bug] L227** `exclude_unset=True` only excludes fields the client omitted — it does **not** exclude fields explicitly sent as `null`. Since `TodoUpdate.title`, `completed` and `priority` are `Optional`, `{"title": null}` passes validation and `setattr(todo, "title", None)` writes `NULL` into a `nullable=False` column (`app/models/todo.py:30,33,34`). `safe_commit` re-raises the raw `IntegrityError`, which the generic `except Exception` below turns into an opaque 500 instead of a 4xx validation error. Reject explicit nulls for non-nullable fields before applying the update.

### `backend/app/api/v1/validation.py`

- **[bug] L215** `rule.params` 直接 `json.loads` 而未捕获异常。create/update 只在写入时做过 JSON 合法性校验，历史/手工导入/被直接改库的脏数据仍会命中，`json.JSONDecodeError` 会让整个 `/validate` 返回 500，使该模块所有数据都无法通过校验。建议加 try/except 并对非法参数给出明确处理（跳过并记录或返回 400）。

- **[bug] L241** 当 `rule_type` 没有对应处理器时直接返回 False（校验通过），规则会被静默跳过且不产生任何日志：新增枚举值 / 数据里出现未知类型都会导致「配置了规则却不生效」而无人察觉。建议明确抛错或记录告警。

- **[bug] L479** `limit` 在条件过滤之前生效，而条件是在 Python 侧逐行判断的，因此 `total`/`matched`/`unmatched` 以及 `results` 只反映「前 N 条记录」的匹配情况，并非全量数据的校验结果——用户会看到被截断后的统计（例如总数 200、匹配 3，实际全库可能匹配几百条），误导性强。建议先把条件下推到 SQL（可用 `model.__table__.columns` 白名单字段 + 运算符构造 filter），或在返回体中明确标注统计范围并支持分页/总数查询。

### `backend/app/api/v1/village_templates.py`

- **[performance] L131** `download_template` is declared `async` but performs fully synchronous, CPU-bound work (openpyxl import + workbook construction + `wb.save` for the village template and for `_generate_module_template`). Because there is no `await` anywhere in the body, this runs directly on the event loop and blocks every other request for the duration of the Excel generation. Either declare the handler as a plain `def` (FastAPI then runs it in the threadpool) or offload the generation via `run_in_threadpool`.

### `backend/app/api/v1/villages.py`

- **[performance] L30** 列表接口用 selectinload 预加载 4 个集合，唯一用途是在序列化时取 len() 计数。这会把每页每个村庄的全部 villagers/industries/tea_plantations/cactus_fruit_plots 行都读入内存，开销随关联行数而非 page_size 增长；其中 Villager.phone / id_card 是 EncryptedText，逐行加载还会触发逐行解密，属不必要的 PII 明文进入进程内存。建议改为聚合计数（相关子查询 func.count 或一次 GROUP BY 统计另一条查询），把 selectinload 留给详情接口。

### `backend/app/api/v1/work_logs.py`

- **[bug] L194** `content` 是 `Optional[str]`，客户端显式传 `content: null`（或 `title: null`，上面的兼容逻辑会把 None 赋给 content）时，`log_data.get("content", "")` 返回的是 `None` 而不是默认值 `""`，`.strip()` 直接抛 `AttributeError` → 接口返回 500，而不是预期的 422。建议先取到值再判空。

- **[security] L221** `category`（以及映射到它的 `log_type`）完全由客户端控制，服务端未做白名单校验。普通用户可以创建 `category="system_auto"` 的记录：列表/日历的可见性逻辑会把它暴露给所有用户，删除接口又固定拒绝删除 system_auto（403），从而产生全局可见且无法清理的记录；update 接口同样允许把自己的日志改成 `system_auto`。建议服务端校验/过滤保留分类（拒绝或忽略客户端传入的 `system_auto`）。

- **[bug] L274** 更新接口完全绕过了创建接口的校验与业务规则： 1) 未校验 `content`/`log_date` 非空 —— 客户端传 `content: null` 或 `log_date: null` 会直接 setattr 到 NOT NULL 列（模型定义 content/log_date 为 nullable=False），commit 时抛 IntegrityError → 500； 2) 未重做 checkin 去重 —— 客户端可以把自己的任意日志 `category` 改成 `"checkin"`（或重复修改同一条），绕过创建时的“同一天仅一条打卡”限制。 建议在 update 中复用与 create 相同的校验/归一化逻辑，并对 checkin 重新执行唯一性检查。

### `backend/app/core/async_utils.py`

- **[bug] L87** `concurrency` is not validated: a value of `0` makes `asyncio.Semaphore(0)` and the first coroutine blocks on `acquire()` forever (deadlock, the whole `gather_limited` call never returns); a negative value raises `ValueError` from the semaphore constructor. Since `concurrency` is caller-supplied, validate it explicitly before building the semaphore. Also consider `asyncio.gather(..., return_exceptions=True)` (or `TaskGroup`) so a single failure does not leave the remaining coroutines running unreferenced with their results discarded.

### `backend/app/core/audit_middleware.py`

- **[performance] L54** `dispatch` is `async`, but `_persist_api_access_log` performs a synchronous `SessionLocal()` + `safe_commit()` (blocking SQLite/file I/O) inline on the event loop. Every non-skipped request therefore stalls the loop for the whole DB write, adding latency under load and serializing concurrent requests. Offload the persistence (e.g. `run_in_threadpool` / `asyncio.to_thread`, or a background task with its own session) instead of awaiting it directly in the middleware.

### `backend/app/core/build_info.py`

- **[bug] L20** `_load()` returns the raw `json.loads()` result without checking its type. A syntactically valid but non-object build file (e.g. `["a"]`, `"1.2.3"`, `123`) is truthy, so the dev fallback below is skipped and the later `info.setdefault("version", ...)` raises `AttributeError: 'str'/'list' object has no attribute 'setdefault'`. A corrupt build artifact would then crash version lookup (and the unauthenticated health endpoints) instead of degrading gracefully. Guard for `dict`.

### `backend/app/core/config.py`

- **[bug] L372** `replace("data/", "")` removes **every** occurrence of `data/` anywhere in the URL, not just the leading directory component (e.g. `sqlite:///./data/mydata/app.db` becomes `myapp.db`), and the rebuilt path is anchored at the ad-hoc `data_dir` variable instead of the canonical `get_database_path()`. A user-supplied relative SQLite URL can therefore silently resolve to a different (empty) database file than the default. Note also that only the `sqlite:///./` prefix is handled, so `sqlite:///data/app.db` stays relative to cwd. Suggest extracting just the file name and resolving it against the same directory used by `_get_default_database_url()`.

### `backend/app/core/error_handler.py`

- **[bug] L24** Silent degradation of error classes to builtin `Exception` is a real correctness hazard: - `except ImportError` also swallows ImportErrors raised *inside* `app.core.exceptions` (e.g. a missing transitive dependency such as `sqlalchemy`/`app.core.errors`), masking the true root cause instead of surfacing it. - Once degraded, `NotFoundError` **is** `Exception`, so `except NotFoundError` catches everything, and `AppError`-based errors stop being handled by `register_exception_handlers` (see `app/core/exceptions.py`) — e.g. `raise NotFoundError("角色", role_id)` in `app/services/rbac_service.py` would return 500 instead of 404. - `BusinessLogicError` (used widely in `batch_service` / `data_sync_service`) would silently subclass `Exception` and lose the HTTP status mapping entirely. Fail fast instead of degrading, so an import problem is visible at startup.

### `backend/app/core/errors.py`

- **[bug] L77** Value collision: `_USER_NOT_FOUND_LEGACY = 4003` duplicates `FILE_UPLOAD_FAILED = 4003` declared earlier. In Python, a second member with an existing value does NOT create a new member — it becomes a silent alias of `FILE_UPLOAD_FAILED` (hidden from `ErrorCode` iteration, and `ErrorCode(4003)` resolves to `FILE_UPLOAD_FAILED`). This directly contradicts the adjacent comment "use unique values to avoid clashes": a legacy user-not-found code looked up here would be mis-routed to the file-upload error (and `get_error_message` would return "文件上传失败"). Note the member is currently referenced nowhere in the repo (only defined here), so it is also dead code. Use a distinct unused value (or drop it entirely if 4003 must remain the legacy wire value, in which case `FILE_UPLOAD_FAILED` needs renumbering).

### `backend/app/core/logging_config.py`

- **[bug] L155** `ColoredFormatter.format()` mutates the shared `LogRecord.levelname` in place. Handler order is console first, then the file handler, so the file handler (plain text *and* the JSON formatter, which writes `record.levelname`) receives a level string polluted with ANSI escapes — and each re-emission of the same record appends another escape pair. Format a copy of the record instead of mutating the original.

### `backend/app/core/migration_helper.py`

- **[bug] L120** `conn.execute(text(ddl))` raises `sqlalchemy.exc.OperationalError`/`DatabaseError` (e.g. "Cannot add a column with non-constant default", duplicate column, unsupported type), none of which is in the caught tuple `(ValueError, TypeError, AttributeError)`. A single bad `ALTER TABLE` therefore aborts the whole loop and can propagate out of the startup migration path, leaving the schema half-migrated. Catch `sqlalchemy.exc.SQLAlchemyError` (or `OperationalError`/`DatabaseError`) here, and note the outer handler at the table level has the same gap for `engine.connect()`/`conn.commit()`.

### `backend/app/core/money.py`

- **[bug] L30** The validator quantizes with `Decimal`/`ROUND_HALF_UP` and then immediately casts back to `float`, which reintroduces binary floating-point representation error (`float(Decimal("0.0001"))` is not exactly 0.0001). Since the declared type is plain `float`, no downstream consumer ever sees a `Decimal`, so the "Decimal 化" goal stated in the module docstring is not actually achieved: exact money arithmetic/comparisons (`==`, accumulation) remain unreliable. If exactness is required, keep `Decimal` end-to-end (and handle JSON serialization explicitly); otherwise the docstring/field promises should be narrowed to "bounds precision to 4 decimal places".

- **[bug] L26** `Decimal.quantize` raises `decimal.InvalidOperation` for `NaN`/`Infinity` inputs (`float('nan')` passes the `float` core validation) and also when the result exceeds the 28-digit default context precision (e.g. `Decimal('1e30').quantize(Decimal('0.0001'))`). `InvalidOperation` derives from `ArithmeticError`, not `ValueError`, so Pydantic v2 will not convert it into a `ValidationError` — it propagates and surfaces as a 500 instead of a clean 4xx validation error. Reject non-finite/overflowing values explicitly (e.g. `Field(allow_inf_nan=False)`) and/or convert the failure into a `ValueError`.

### `backend/app/core/permission_utils.py`

- **[security] L271** Fail-open org check: the mismatch check is skipped entirely when `user_org_id is None`, so a user not bound to any organization (or a token payload without org) can request any `organization_id` and reach another organization's data. The docstring promises "确保用户只能访问自己所属组织的数据". Deny when a requested org is supplied but the user has no known org.

### `backend/app/core/pii_crypto.py`

- **[bug] L85** 解密失败时把「带标记的密文」原样返回，调用方无法与「历史明文」区分：密钥轮换/丢失或数据损坏时，应用会把 `enc.v1:<base64>` 当作真实手机号/身份证展示甚至回写，问题被完全静默化。同时这里的 `except Exception` 覆盖面过宽，`base64.b64decode`、`AESSIV.decrypt` 之外的编程错误（如 `UnicodeDecodeError`、`AttributeError`）也会被当作“数据损坏”吞掉，掩盖真实 bug。建议：只捕获 `InvalidTag`/`ValueError` 等预期异常并抛出专用异常（或返回 `None`/sentinel）让调用方感知失败；如需兼容历史明文，至少应在模块内提供一个显式的 `is_encrypted` 校验入口，而不是在此静默降级。

- **[bug] L50** 此处的异常兜底假设 `get_or_create_secret` 会在无法落盘时抛异常，但 `runtime_secrets.get_or_create_secret`（backend/app/utils/runtime_secrets.py:127-134）在写文件失败时只打 warning 并返回进程内新生成的值。因此「无写入权限/磁盘满」时会走到 `return new_value`，本文件的 `RuntimeError` 分支不会触发，进程拿到的是一次性密钥：重启后密钥变化，历史密文全部无法解密，而 `decrypt_pii` 又会静默返回密文。建议：`_load_key` 中对运行时密钥做一次可持久化/可复现性校验（例如校验返回值确实来自文件），或至少在无法持久化时记录 ERROR 级日志提示密文将不可恢复。

### `backend/app/core/query_optimizer.py`

- **[bug] L115** The claim in this comment is false and makes the N+1 detector a silent no-op. `app/middleware/query_counter.py` maintains its own `contextvars`-based counter (`_query_counter_ctx` / `request.state.query_count`) and never touches this module's `_query_counter`; no SQLAlchemy `after_cursor_execute` listener increments it either, so `get_query_count()` always returns 0 and the `query_count > threshold` branch in `analyze_n_plus_one` can never trigger. `increment_query_count` also lives in the middleware module and takes a `Request`, so it cannot increment this thread-local. Either wire this counter to the actual query events (add an increment function and call it from the event listener / middleware) or drop the decorator, otherwise all N+1 reporting is silently dead.

### `backend/app/core/response.py`

- **[bug] L155** `resp.update(kwargs)` runs *after* the canonical envelope fields are set, so a caller that forwards arbitrary data (e.g. `success_response(data=d, **payload)` where `payload` contains `code`/`message`/`success`/`data`) silently clobbers them and breaks the response contract — the client may receive `success: False` on a 200 response or a non-`data` payload. Reserved keys should be excluded from `kwargs` (or the conflict rejected) instead of blindly merged.

- **[bug] L129** Same silent-clobber problem as `success_response`: `kwargs` is merged last, so `code`, `message`, `success`, `errors` or `detail` supplied via `**kwargs` overwrite the values just computed by `error_response` / `not_found_response` / `server_error_response`. Guard the reserved keys before merging.

### `backend/app/core/token_blacklist.py`

- **[other] L57** `remove()`, `clear()` and `load_from_db()` all mutate the shared `_blacklist` dict without holding `_BLACKLIST_LOCK`, while `_cleanup_expired()` iterates the same dict under the lock (triggered on every `is_blacklisted()` call). On a multi-threaded startup/request path this can raise `RuntimeError: dictionary changed size during iteration` and/or silently lose entries added by `add()`. Guard every mutating access with `_BLACKLIST_LOCK`.

- **[bug] L88** A DB row with `expires_at IS NULL` semantics (no natural expiry / permanent revocation) is converted to `expiry = now + 86400`, so the in-memory entry silently disappears after 24 hours. Until `load_from_db()` runs again (typically only at startup), the revoked token would be accepted again by `is_blacklisted()` — a security regression for permanent revocations. Either treat NULL as non-expiring in memory (e.g. `math.inf`) or make the fallback explicit and documented.

### `backend/app/core/token_manager.py`

- **[security] L108** `extra_claims` is merged **after** the reserved claims are set, so a caller can silently clobber `sub`/`jti`/`type`/`exp`. E.g. `extra_claims={"type": "refresh"}` defeats the token-type check in `validate_token`, and `extra_claims={"exp": ...}` extends the expiry beyond `access_ttl_minutes`. Reserved JWT claims must not be overridable.

- **[security] L162** The truthiness guard makes the type check optional: a token with **no** `type` claim is accepted for both `"access"` and `"refresh"`. Any token signed with the same secret but lacking `type` (e.g. legacy/other-service tokens) therefore passes as a refresh token and can be exchanged for a new pair. Require the claim to be present and equal.

### `backend/app/interfaces/schemas/responses.py`

- **[bug] L31** `BaseResponse` omits the `success` field present in `ResponseModel` and in the core envelope (`app/core/response.py` emits `success` in both `success_response` and `error_response`). This class is documented as the generic model for `response_model` declarations and is the one exposing the `success()`/`error()` factories, so any endpoint declaring it will serialize a body without `success`, and the frontend `res.success` check will read `undefined`. Align the field set with `ResponseModel` (the duplication then needs a single source of truth).

### `backend/app/main.py`

- **[bug] L659** 内层只捕获 `ValueError/TypeError/AttributeError`，但 `conn.execute(text(ddl))` 失败时实际抛出的是 SQLAlchemy 的 `OperationalError`（`SQLAlchemyError` 子类，例如 “Cannot add a column with non-constant default”、列已存在、类型冲突），**不属于这三个类型**；外层的 `except (ValueError, TypeError, KeyError)` 同样接不住，异常会一路冒泡出 `_init_database_tables()`，导致 lifespan 启动直接失败。这与该函数“单列失败只记 warning 并累加 total_failed”的设计意图相悖（失败路径不可达，计数与日志永远不生效）。建议改为捕获 `sqlalchemy.exc.SQLAlchemyError`（或至少 `Exception`）。

### `backend/app/middleware/body_size_limit.py`

- **[security] L89** The multipart pre-check silently swallows malformed `Content-Length` values (`except (ValueError, TypeError): pass`). A header such as `Content-Length: abc` / `1e9` / a non-decimal value makes `int()` raise, the `pass` drops the check, and the request is forwarded with **no size limit at all** and **no log line**, so a crafted header defeats the exact defence this method implements. Only real exception is the malformed-header case, which is fully attacker-controlled, so it should fail closed (reject with 400) or at least be logged. The same pattern is duplicated in the non-multipart branch below.

- **[security] L82** `is_multipart` is derived purely from the client-supplied `Content-Type` string via substring matching, so it is trivially spoofable: sending a large JSON body with `Content-Type: multipart/form-data` skips the 10 MB branch entirely (and even the 10 GB backup tier is reachable if the path matches), taking the 512 MB default instead. Since the header is untrusted, the multi-part tier should also be capped for endpoints that do not expect multipart (e.g. only honour the multipart tier for paths that actually accept uploads, or apply `min(multipart_limit, max_body_size)` for non-upload routes).

### `backend/app/middleware/cache_headers.py`

- **[bug] L28** Unconditional assignment clobbers any `Cache-Control` the route handler deliberately set, including stricter `no-store` directives. Concretely, `get_organization_tree` in `backend/app/api/v1/organization.py:309` calls `_set_no_cache_headers(response)` which sets `Cache-Control: no-cache, no-store, must-revalidate` (+ `Pragma`/`Expires`), yet this middleware matches `/api/v1/organizations/tree` and overwrites it with `public, max-age=300`, leaving inconsistent `Pragma: no-cache` / `Expires: 0` next to a 5-minute public cache. Only inject the value when the handler has not already decided (e.g. skip if `Cache-Control` is present), or re-apply the directive list consistently.

- **[bug] L24** The header is applied regardless of the response status code, so error responses (401/403/404/500) returned for a matching path are cached by the browser for the full TTL — e.g. a transient 500 or a 401 right after token expiry on `/api/v1/organizations/tree` gets pinned for 5 minutes (1 hour for `/assets/`, `immutable`). Restrict the rule to successful responses (e.g. only when `200 <= response.status_code < 300`, and never for `5xx`).

### `backend/app/middleware/camel_to_snake.py`

- **[bug] L99** Rebuilding the response as a bare `JSONResponse` drops the original response's headers and background task. Every header added by inner middleware/handlers (CORS, `Set-Cookie`, `X-Request-Id`, custom cache/security headers) plus `response.background` is discarded, silently breaking session/CSRF/correlation behaviour whenever the envelope patch fires. Copy the original headers (removing the now-stale `content-length`) and pass `background` through.

### `backend/app/middleware/metrics_middleware.py`

- **[bug] L173** Double counting when the downstream app raises after it has already sent `http.response.start`: the `except` block records a 500, then `finally` also records because `status_code > 0`, so `request_count`, `error_count` and the duration totals are inflated (and the duration is added twice). Add a guard flag so a request is recorded exactly once.

### `backend/app/middleware/request_logger.py`

- **[security] L32** Client IP is taken from `X-Forwarded-For`/`X-Real-IP` without verifying that the immediate peer is a trusted proxy. Any client can send these headers and forge the IP recorded in the logs (and in any downstream consumer that relies on these logs). The first XFF entry is the client-controlled one when nginx appends via `$proxy_add_x_forwarded_for`. Consider honoring these headers only when `scope["client"][0]` is in a configured trusted-proxy set, otherwise fall back to the socket peer address.

### `backend/app/middleware/slow_request_monitor.py`

- **[security] L104** Raw SQL parameters are persisted verbatim into the module-level ring buffer and emitted to the warning log. Parameter values routinely contain password hashes, tokens, e-mail addresses and other PII (e.g. `UPDATE users SET password=...`), so this leaks sensitive data into log aggregation systems and into memory readable by any code/monitoring endpoint that calls `get_slow_sql_records()`. Suggest logging only a redacted/summarised form (or gating raw params behind an explicit debug flag) and storing metadata such as parameter count/types in the ring buffer instead of the literal values.

### `backend/app/models/approval.py`

- **[bug] L153** `submitter_id` is declared `nullable=False` while its foreign key uses `ondelete="SET NULL"`. When a `users` row is deleted, the database will try to write NULL into this non-nullable column and the delete will fail with an integrity error. Either allow NULL (if approval traces should survive user deletion, mirroring `ApprovalRecord.approver_id`) or change the FK action to `RESTRICT`/`CASCADE` so the intent matches the nullability.

### `backend/app/models/audit.py`

- **[bug] L183** `DataExportLog.user_id` contradicts itself: the column is `nullable=False` while the FK is declared with `ondelete="SET NULL"`. When the referenced `users` row is deleted, the DB will try to set `user_id = NULL` and the NOT NULL constraint aborts the delete (or the parent delete fails entirely). Either make the column nullable (consistent with `AuditLog`/`SecurityEvent`/`APIAccessLog`) or drop the `SET NULL` action (use `CASCADE`/`RESTRICT`) to match the non-nullable contract.

### `backend/app/models/base.py`

- **[bug] L100** `before_update` 只在 ORM 逐个实例 flush 更新时触发，无法覆盖绕过 ORM 实例的写入路径，而增量包的过滤完全依赖该列（`data_package_service._export_data_type`: `model.sync_version > since_sync_version`）： 1) Query.update()/Core update()——本仓库大量使用，如 `policy.py:1016`、`message_service.py:314`、`project_milestones.py:463`——不会触发该事件，sync_version 保持不变，这些被修改的行会被增量导出静默漏掉（`scripts/update_tickets.py` 已记录裸 text() 导入同类问题）； 2) 任何裸 SQL / 其他进程写入同理。 另外这里是 Python 端读-改-写（`sv + 1`），并发事务对同一行更新时不是原子自增，两个事务可能都写入同一版本值。 建议：不把增量正确性押在 ORM 事件上——改为数据库层（触发器/`server_onupdate` 或 UPDATE 语句里带 `sync_version = sync_version + 1` 表达式），或在导出侧对同时提供 `since_time` 的场景做并集回退，并对批量更新统一封装递增逻辑。

### `backend/app/models/data_report.py`

- **[bug] L41** Contradictory FK definition: `package_id` is declared `nullable=False` while the FK specifies `ondelete="SET NULL"`. Deleting a `DataPackage` makes the DB try to NULL the column, which violates NOT NULL, so the delete fails with a constraint error (`NOT NULL constraint failed` / `FOREIGN KEY constraint failed` on SQLite) instead of the intended behavior. `DataReportCreate.package_id` is also a required field (`Field(...)`), so the reference is never legitimately absent. Align the model with the actual intent — e.g. `ondelete="CASCADE"` (or `RESTRICT` if reports must block package deletion) — and adjust the corresponding migration DDL.

- **[bug] L144** Naive/aware datetime comparison: `deadline` is read back from a `DateTime(timezone=True)` column, but on SQLite the value is returned as a naive datetime (the codebase already compensates for this elsewhere, e.g. `services/async_export_service.py` and `models/export_task.py`). Comparing a naive `self.deadline` with `datetime.now(timezone.utc)` raises `TypeError: can't compare offset-naive and offset-aware datetimes`, so `is_overdue` blows up for any persisted row that has a deadline. Normalize the stored value to UTC-aware before comparing.

### `backend/app/models/effectiveness.py`

- **[bug] L23** No uniqueness constraint on (village_id, year), but the domain treats an evaluation as one row per village per year. `EffectivenessService` (effectiveness_service.py:155-184) does a find-then-insert (`_find_evaluation` → else `db.add(...)`), so two concurrent requests for the same village/year can both miss the lookup and insert duplicates, corrupting the total_score/rank computation. Other sibling tables (annual_income, annual_industry, annual_population, annual_infrastructure) all enforce this with a `UniqueConstraint`. Add one here (and the `UniqueConstraint` import).

### `backend/app/models/export_task.py`

- **[bug] L39** Contradictory FK policy: the column is declared `nullable=False` while the foreign key uses `ondelete="SET NULL"`. If a referenced user is ever hard-deleted, the database will attempt to write NULL into a NOT NULL column, so the delete either fails with an integrity error or leaves the row orphaned. Either make the column nullable (`nullable=True`) so SET NULL can actually apply, or switch to `ondelete="CASCADE"`/`ondelete="RESTRICT"` to match the NOT NULL requirement.

### `backend/app/models/fund.py`

- **[bug] L215** On update, if `date` is cleared (set to None) and `application_date` is also empty, `parsed_date` is falsy and the whole assignment block is skipped — the previously computed `year` / `year_month` / `year_quarter` stay on the row. The record is then still counted by the dashboard aggregations in the *old* period (or in two periods at once), which is exactly what these redundant columns are supposed to power. Reset the derived fields when no usable date remains.

### `backend/app/models/fund_allocation_order.py`

- **[bug] L92** `order_id` is declared `nullable=False` while its foreign key uses `ondelete="SET NULL"`. Deleting the parent `fund_allocation_orders` row will make the DB attempt to set `allocation_order_items.order_id` to NULL, which violates the NOT NULL constraint and makes the DELETE (or the cascade) fail at runtime. Either keep the column nullable (as `FundBudgetItem.budget_id` does elsewhere in this project) or switch the FK to `ondelete="CASCADE"` so line items are removed with their order.

### `backend/app/models/fund_asset_verification.py`

- **[bug] L49** `Numeric(5, 2)` caps the stored percentage at 999.99. The value written by `verify_asset` is `abs(total_paid - asset_value) / total_paid * 100`, which grows without bound when `total_paid` is small and `asset_value` is large (e.g. total_paid=1, asset_value=100000 → 9,999,900%). On a real DB (PostgreSQL/MySQL) this raises a numeric-overflow error at COMMIT, so the verification record cannot be saved. Widen the column (and/or clamp the computed rate before persisting).

### `backend/app/models/fund_history.py`

- **[bug] L45** `DateTime(timezone=True)` columns are populated with a naive `datetime.utcnow()` value (same pattern on `changed_at` below). The naive value is sent to a `TIMESTAMP WITH TIME ZONE` column, so the DB/session time zone decides how it is interpreted — on a non-UTC session the recorded time is silently shifted, and the serialized `to_dict()` output is offset-naive while `FundOperationLog.created_at` (from `func.now()`) is offset-aware. `datetime.utcnow()` is also deprecated in Python 3.12+. Use a timezone-aware factory.

- **[bug] L49** The FK is declared `ondelete="CASCADE"`, but the relationship has no `cascade="all, delete-orphan"` / `passive_deletes=True`. `FundService.delete_fund()` performs an ORM `self.db.delete(fund)`, so SQLAlchemy will try to *nullify* `fund_id` on these history rows instead of letting the DB cascade — and since `fund_id` is `nullable=False`, the delete raises an IntegrityError (the DB-level cascade never gets a chance to run). Same issue on `field_changes` and `operation_logs` below.

### `backend/app/models/import_export_history.py`

- **[bug] L55** `ondelete="CASCADE"` on the organization FK silently deletes this table's rows whenever an organization is removed, which directly contradicts the documented purpose of the model ("audit trail ... for compliance"). An audit trail must be append-only and survive parent/tenant deletion. Use `SET NULL` (with `nullable=True`) or `RESTRICT` so history is retained; this also matches how other models in the project reference `organizations.id`.

### `backend/app/models/message_template.py`

- **[bug] L62** The render helpers only catch `KeyError`, but `str.format` raises other exceptions for malformed templates, and these templates are admin-editable (stored in the DB, per Requirement 7.1). A single unescaped brace (`"通知 {username"`) raises `ValueError`, positional placeholders such as `"{0}"` raise `IndexError`, and `"{user.name}"` raises `AttributeError` when `user` is not a matching type. Any of these will propagate and break notification rendering for every recipient. Broaden the handler to cover the exceptions `str.format` can actually raise (and log/report the failure instead of silently swallowing it).

### `backend/app/models/monitoring.py`

- **[bug] L74** AlertHistory has no `created_at` column, but the history endpoint (`app/api/v1/system/monitor.py` → `get_alert_history`) runs `query.order_by(AlertHistory.created_at.desc())` and reads `record.created_at.isoformat()`; the unit test even works around it with `patch.object(AlertHistory, "created_at", ..., create=True)`. Because the API wraps the whole block in `try/except`, the AttributeError is swallowed and the endpoint always returns an empty history list. Please make the model and the consumer agree — e.g. expose `created_at` (rename `triggered_at`, or add an alias/column) so the endpoint works.

### `backend/app/models/notification_preference.py`

- **[bug] L30** `user_id` is declared `nullable=False` while the foreign key uses `ondelete="SET NULL"`. These contradict each other: deleting a `users` row makes the DB try to set `notification_preferences.user_id` to NULL, which violates the NOT NULL constraint and aborts the user deletion (or the constraint). Use `ondelete="CASCADE"` (delete the preference row with the user) or make the column nullable if an orphaned row is actually intended.

### `backend/app/models/package_version.py`

- **[bug] L18** No uniqueness is enforced on `(package_id, version)`. The API (`data_packages.py` create-version endpoint) only does a check-then-insert (`db.query(...).first()` then `db.add`), which is a TOCTOU race: two concurrent requests can both pass the check and insert the same version, silently violating version semantics. Add a DB-level unique constraint (and an index on the FK column, which is not indexed automatically) so the invariant holds regardless of the caller.

### `backend/app/models/project.py`

- **[security] L203** `to_dict()` is the serializer exposed to the API layer, yet it returns decrypted PII/financial data in plaintext: `contact_phone` is transparently decrypted by `EncryptedText`, and the payer/payee bank account numbers, account names, handlers and contacts (see the `payer_*` / `payee_*` entries below) are output verbatim. Any caller that serializes a `Project` (list/detail endpoints, exports, logs) leaks this data to every viewer regardless of role. Consider masking these fields by default (e.g. `138****8000`, `****1234`) and only returning the full value through an explicitly authorized endpoint, or dropping them from the generic serializer and exposing them through a dedicated, permission-checked schema.

### `backend/app/models/rural_task.py`

- **[bug] L63** `rural_work_id` is declared `nullable=False` but its FK uses `ondelete="SET NULL"`. Deleting the referenced `rural_works` row makes the DB attempt to set this column to NULL, which violates the NOT NULL constraint and raises an integrity error — the delete rule and nullability contradict each other. Since a task cannot exist without its parent work, the rule should be `CASCADE` (consistent with the child-row convention used elsewhere, e.g. `rural_work.village_id` / `supported_village` children).

### `backend/app/models/school.py`

- **[bug] L128** `to_dict` calls `.value` unconditionally, but this column is declared with `validate_strings=False` precisely because legacy/manually-fixed rows can hold a raw string that is not a `SchoolType` member. In that case `self.type.value` raises `AttributeError` (and `self.support_status.value` likewise), which re-introduces the exact 500 the enum configuration was meant to prevent. Other call sites in `api/v1/school.py` (e.g. `school.type.value if isinstance(school.type, SchoolType) else school.type`) already guard with `isinstance`; apply the same guard here.

### `backend/app/models/sentiment.py`

- **[bug] L28** `collected_at` is never populated by any write path in the codebase (crawler_service.save_news only sets title/source/url/content/published_at/keywords), yet migration `006_add_effectiveness_sentiment_tables.py` creates this column as `NOT NULL` without a server default. On any database provisioned by that migration, every crawler insert will raise `IntegrityError` (NOT NULL violation); on databases bootstrapped via `create_all` from this metadata the column is nullable, so behaviour silently differs between deployments. Either populate `collected_at` at every insert site, or align the model and migration (e.g. `nullable=True` + `server_default=func.now()` / `default=datetime.utcnow`).

### `backend/app/models/system_config.py`

- **[security] L28** `__repr__` interpolates the raw `value`. `SystemConfig.value` stores sensitive material (e.g. `encryption_salt`, `encryption_verify_hash`, tokens), so any accidental print/logging/debugger rendering of this model leaks secrets into logs and tracebacks. Redact the value in the representation.

### `backend/app/models/two_factor_auth.py`

- **[security] L26** MutableList 只解决了「就地修改不产生 attribute 事件、UPDATE 静默丢失」的问题，它并**不**保证备用码的单次使用语义。`verify_login` 是典型的 check-then-act： ```python if token in two_factor.backup_codes: # 读 two_factor.backup_codes.remove(token) # 改 safe_commit(db) # 提交 ``` 两个并发登录请求（同一攻击者用同一个泄露的恢复码重放，或用户在多设备上同时提交）会各自读到包含该码的列表并各自提交，最终两次都验证成功——「每个恢复码只能使用一次」的承诺在并发下依然被破坏。模型层没有任何 DB 侧防护（无版本号/乐观锁、无唯一约束可依赖），建议在消费侧用行锁串行化，例如把查询改为 `db.query(TwoFactorAuth).filter(...).with_for_update().first()`（或给该表加 `version_id_col` 做乐观锁），并在提交后刷新校验，否则应把此处的注释从「已恢复单次使用保证」降级为「仅修复了变更追踪」。

### `backend/app/models/work_log.py`

- **[bug] L24** Contradictory FK action: `ondelete="SET NULL"` cannot be applied to a column declared `nullable=False`. When a referenced `users` row is deleted, the database will try to set `work_logs.user_id` to NULL and fail with a not-null violation (or abort the user delete), so the intended "keep the log when the user is removed" semantics never happens. Either make `user_id` nullable (and have the app tolerate a NULL author) or change the action to `RESTRICT`/`CASCADE` to match the NOT NULL contract.

### `backend/app/schemas/__init__.py`

- **[bug] L42** The fallback discovery scans every attribute of the submodule and re-exports any BaseModel subclass. Since none of the schema modules define `__all__` (checked: auth/fund/policy/project/school/user/village have no `__all__`), this branch always runs, and because each module does `from pydantic import BaseModel`, `BaseModel` itself matches `issubclass(attr, BaseModel)` and is written into `globals()` and appended to `__all__`. Models merely imported from sibling modules are also re-exported, so `from app.schemas import *` leaks `BaseModel` and imported symbols instead of only locally defined schemas. Restrict discovery to classes defined in the module and exclude `BaseModel`:

### `backend/app/schemas/permission_package.py`

- **[bug] L82** `mode` is an unconstrained `Optional[str]`. The consumer (`PermissionPackageService.confirm_import`) only treats the exact value `"merge"` as non-destructive: ```python merge_mode = (mode == "merge") or (mode is None and not overwrite_existing) ``` So any typo or unexpected casing (e.g. `"MERGE"`, `"Merge"`, `"mirror"`) silently falls through to the destructive mirror path that deletes the target machine's existing RBAC configuration. Constraining the field to a closed set makes the request self-validating instead of failing silently into data loss.

### `backend/app/schemas/rural_work.py`

- **[bug] L31** Timezone inconsistency in date parsing: formats that end with a literal `Z` are returned as tz-aware UTC datetimes, while all other formats (including `%Y-%m-%d`) return naive datetimes. The same field can therefore be aware or naive depending on the input format. The ORM columns `start_date`/`end_date` are declared as `DateTime(timezone=True)` (backend/app/models/rural_work.py:53-54) and later compared with `RuralWork.start_date >= dt` / `end_date <= dt` in the service, so a naive value is interpreted in the DB/session timezone and can yield wrong filtering results (or a `TypeError` when compared with an aware value in Python). Normalize every parsed value to a single convention, e.g. attach `timezone.utc` when `tzinfo` is missing.

### `backend/app/schemas/school.py`

- **[bug] L76** `SchoolResponse` is a read schema that is meant to be built from `School` ORM instances (it is nested in `SchoolListResponse`), but it does not declare `model_config = ConfigDict(from_attributes=True)`. Under Pydantic v2, validating a non-dict object (e.g. `SchoolResponse.model_validate(orm_obj)`) raises `ValidationError` without this config, so ORM->schema conversion will fail at runtime. This also breaks the convention used by the other response schemas in this project (e.g. `app/schemas/fund.py`, `organization.py`, `policy.py`, `village.py`, which all set `ConfigDict(from_attributes=True)`). Add the config and import `ConfigDict` from `pydantic`.

### `backend/app/services/ai/nlp_query_service.py`

- **[bug] L212** `data[0].get("total", 0)` / `.get("per_capita_income", 0)` returns `None` when the SQL aggregate is NULL (empty table or all-NULL), because the key is present with value `None`; formatting `{None:,.2f}` then raises TypeError. Guard against `None` (e.g. `or 0`) before formatting.

- **[bug] L23** The province regex capture and explanation are inconsistent: the capture group includes the suffix (`省` or `的`), so the SQL parameter binds the wrong value and the explanation appends `省` again, producing duplicated/mismatched text. Capture only the name and render it as-is.

- **[security] L184** Raw exception text (`str(e)`) is returned to API callers or persisted in error fields in several places (nlp_query_service, async_export_service, ai_service, compliance_engine). This leaks SQL/table/column/connection details. Log the full traceback server-side and return a generic sanitized message.

### `backend/app/services/ai/recommendation_service.py`

- **[bug] L56** `SupportedVillage.province`/`city` are nullable (`city = Column(String(50), nullable=True)`). When the source village has no region data, SQLAlchemy renders `column == None` as `IS NULL`, so unrelated villages whose province/city are also NULL are selected as "similar" and then drive the whole recommendation. Guard against a NULL region (or treat missing region as "no similar villages") before building the filter.

### `backend/app/services/ai/trend_prediction_service.py`

- **[bug] L67** The timeout guard does not actually work. `return` executes inside the `with ThreadPoolExecutor(...)` block, so the context manager's `__exit__` runs `shutdown(wait=True)` and the call still blocks until the hung Prophet task finishes (the worker thread is never cancelled either). The 10s `_PROPHET_TIMEOUT` therefore provides no real protection on the request path. Manage the executor explicitly and shut it down with `wait=False` (or run the work in a separate process that can actually be killed) so the caller can return the fallback promptly.

### `backend/app/services/alert_service.py`

- **[security] L58** `starttls()` is called without an SSL context, so `smtplib` falls back to its non-verifying default context (no certificate/hostname validation) and the SMTP login credentials can be sent to a MITM. In addition, `smtplib.SMTP` is constructed without a `timeout`, so a hung mail server will block indefinitely. Pass an explicit context and a timeout.

- **[bug] L42** The intended fallback to `smtp_user` never happens: `SMTP_FROM` is declared as `Optional[str] = None` in `app/core/config.py`, so the attribute always exists and `getattr(settings, "SMTP_FROM", smtp_user)` returns `None` when it is unset. `msg["From"]` is then assigned `None`, producing an invalid sender header and causing delivery to fail at runtime (the unit test mocks `smtplib`, so it does not catch this). Use `or` for the fallback and validate the sender together with the other required settings.

### `backend/app/services/analytics_service.py`

- **[bug] L105** `total_population` defaults to 0 (see `VillagePopulation.total_population`), so `resident_population * 100.0 / total_population` raises a division-by-zero error on PostgreSQL, which nulls/aborts the whole aggregate (and the exception is then swallowed). Guard the divisor with `NULLIF`.

### `backend/app/services/approval_workflow_service.py`

- **[bug] L626** The boolean result of `apply_entity_change` is ignored here. If the handler fails, the comment above claims the task/entity inconsistency is fixed, but in reality the task stays `pending` with no `*_apply_failed` marker, so `retry_apply_entity_change` can never detect and recover it. Also, the `apply_entity_change` failure path rolls back the `resubmit` record added a few lines above, so the resubmission is not recorded either. Check the return value and mark the task (`ApprovalStatus.PENDING.value + self.APPLY_FAILED_SUFFIX`) or re-raise on failure, consistently with `approve_task`/`reject_task`.

- **[security] L722** `batch_approve` always passes `standalone=True`, which skips the `task.current_approver_id` check performed by every other entry point. Any caller that can reach this method (no authorization is enforced here either) can approve tasks assigned to other users. Pass `standalone` through from the caller instead of hard-coding it, or validate `approver_id` against `current_approver_id`.

### `backend/app/services/async_export_service.py`

- **[security] L261** Data-permission/tenant isolation is missing or fails open in several places: async_export_service counts/details are unfiltered, analytics_service drill-down (`dimension` other than `province`) and `compare_villages` skip `scoped_filter`, and batch_service falls back to writing all rows when org context is absent. Apply `scoped_filter`/org checks and fail closed for non-superusers.

- **[bug] L382** 异常回写前缺少 `db.rollback()`：如果原异常来自失败的 DB 操作（例如查询语句报错、flush 失败），Session 会处于待回滚状态，此处重新 `db.query(...)` / `safe_commit(db)` 会直接抛 `PendingRollbackError`，被内层 except 吞掉，任务将永久停留在 `processing`（前端轮询永不结束）。建议在进入回写逻辑前先 `db.rollback()`（自身也需 try/except 兜底）。

### `backend/app/services/audit_enhancement_service.py`

- **[bug] L43** Operations perform two separate commits (audit_enhancement_service, audit_service.log_export, fund_service.create_fund_for_user), so a failure between them leaves inconsistent state (e.g. audit log with no changes, fund with empty code). Build the writes in one transaction and commit once.

### `backend/app/services/audit_event_handler.py`

- **[bug] L115** The audit INSERT runs on the same `connection`/transaction as the business change, and every failure (including a DB-level error such as a constraint/length violation on `work_logs`) is swallowed here. On PostgreSQL/SQLite that aborts the surrounding transaction, so the *business* write that triggered the listener will later fail at commit while the caller sees an unrelated error, and the audit record is silently lost (only a warning). Wrap the audit insert in a SAVEPOINT so a failed audit write rolls back only itself and cannot poison the caller's transaction, and log at `error` (or re-raise) instead of degrading to a warning.

### `backend/app/services/backup_service.py`

- **[bug] L801** The record query only matches keys starting with `backup_20`, but incremental backups are stored under their own prefix (`config_key = f"backup_incremental_{timestamp}"`). As a result `list_backups()`, `cleanup_old_backups()`, `cleanup_by_retention_days()` and `get_backup_statistics()` never see incremental backups: they are invisible in the UI, are never rotated/cleaned (they accumulate in the backup dir forever and inflate disk usage), and any that were listed would be counted as `full` because `BackupRecord.backup_type` defaults to `"full"`.

- **[bug] L1167** `last_manifest.json` (and the in-memory `self.last_backup_manifest`) is updated *before* `_save_incremental_backup_record()` commits the DB record. If that commit fails (e.g. `database is locked`, unique-key conflict — the same second-precision key issue), the outer `except` returns `status: error`, yet the manifest already claims these files are backed up. Every subsequent incremental run then computes `changed_files` as empty for them, so their content never enters a tracked backup again — a silent backup gap in the fail-loud/incremental design. Persist the manifest only after the record is successfully committed.

- **[bug] L592** `_create_snapshots()` swallows the `BackupIncompleteError` raised by `_create_consistency_snapshot()` and falls back to a raw `shutil.copy()` of the main DB file, which does not merge `-wal` content. This is exactly the fallback that `_create_consistency_snapshot`'s own docstring rejects as silently data-losing: the rollback snapshot can then be missing committed transactions, and `_rollback_to_snapshots()` will restore that stale database over the production one if the restore fails. For a rollback snapshot the failure should propagate (fail before mutating anything) rather than degrade to a WAL-blind copy.

- **[bug] L701** When the preceding `os.unlink(self.database_path)` failed (the code itself logs that the file may still be locked/occupied), this `shutil.copy` overwrites the production database in place. On Windows the copy of a file that is still held open raises `OSError`; since this runs inside the `except Exception as e:` block of `_restore_backup_impl`, the exception escapes `_rollback_to_snapshots()`, the `raise BackupRestoreError("恢复失败，已回滚到原始状态")` is skipped, and the caller sees a raw 500 with the original restore error masked. The rollback copy should be attempted with the retry helper (`_copy_database_with_retry`) / its own try-except and must never prevent the original error from being reported.

### `backend/app/services/business_metrics_service.py`

- **[bug] L179** `func.strftime` and `func.julianday` are SQLite-only; on PostgreSQL/MySQL these raise "function does not exist" and the metrics endpoints break. Use engine-agnostic expressions (extract/date_trunc/range filtering) or guard with `IS_SQLITE`.

### `backend/app/services/cache_service.py`

- **[bug] L103** `CacheManager.delete()` returns `None` (its backend `SimpleCache.delete`/`diskcache.delete` return no value), so `if result:` is always falsy. As a result `delete()` always reports `False` even when the entry WAS removed, `cache_stats["deletes"]` is never incremented, and `invalidate_related_cache()` always returns 0 (its `count` never grows). Callers that branch on the boolean are silently misled.

- **[bug] L390** `resource_id` is only read from `kwargs`; the positional-argument fallback is an empty `pass`. A typical call such as `update_user(user_id, data)` (or any method where the id is positional/`self`-adjacent) therefore invalidates nothing for that resource, leaving stale detail entries. Bind the arguments to the signature to resolve the value regardless of how it was passed.

- **[bug] L248** `json.dumps(arg, ...)` is applied to any non-primitive argument, so a non-JSON-serializable value (ORM model, `datetime`, `bytes`, `set`, or a `self`/`db` session captured by the decorator) raises `TypeError` and crashes the decorated function before it ever executes. Add a `default=` encoder (or hash `repr`/`pickle`-free fallback) so key generation can never fail.

### `backend/app/services/cascade_purge_service.py`

- **[bug] L112** The traversal is not the generic depth-first delete the docstring advertises: only two levels (children + their direct children) are removed. For a three-or-more level chain (e.g. `supported_villages → projects → funds → fund_transactions`), rows below the second level survive, so the parent deletes can trip FK constraints (and leave orphan rows when FKs are unenforced). The cross-branch ordering is also unsafe: if a grandchild row table is itself another direct child of the root, iterating the earlier branch can delete its parent rows before that branch has removed its own children. Use a real visited-set DFS (delete strictly bottom-up over the transitive closure), or rely on DB-level `ON DELETE CASCADE`.

### `backend/app/services/chunked_upload_service.py`

- **[bug] L431** The check-then-act sequence is not atomic: concurrent requests can both pass the guard and proceed to the same merge/claim, causing corrupted output or an unhandled `IntegrityError`/500. Add an atomic guard/DB uniqueness/`ON CONFLICT` handling and catch `IntegrityError`.

### `backend/app/services/data_cleaning_service.py`

- **[bug] L177** Two problems here: (1) values are not type-checked/normalized, so a column mixing numbers with non-numeric leftovers (e.g. an empty-string or text value that survived earlier steps) makes `sorted()` raise an uncaught `TypeError`, aborting the whole cleaning run; (2) for an even number of values this picks the upper-middle element (`values[len // 2]`) instead of averaging the two central values, producing a biased median (e.g. [1,2,3,4] -> 3 instead of 2.5). Coerce to numbers, skip non-numeric entries, and average the two middle values for even-length input.

- **[bug] L258** Assigning the standardized result unconditionally replaces a valid, non-empty original value with `None` whenever parsing fails (`standardize_phone`/`standardize_email`/`standardize_address` all return `None` for unparseable input). That is silent data loss rather than "standardization": e.g. an 8-digit landline is wiped out. Only overwrite when standardization succeeds (or keep the original and log the invalid value). Additionally, `field_config["field"]`/`["type"]` are indexed directly, so a malformed rule raises `KeyError` after earlier records have already been mutated — use `.get()` and validate the rule up front.

### `backend/app/services/data_package_service.py`

- **[bug] L582** DB errors inside per-record loops leave the session in a failed transaction state: `_bulk_upsert_records` calls `self.db.rollback()` which rolls back the whole session (including the caller's savepoint), and `_import_table_data` counts errors but never recovers, so subsequent statements raise `PendingRollbackError` while counters report success. Isolate each record with a SAVEPOINT (`with db.begin_nested():`).

### `backend/app/services/data_report_service.py`

- **[bug] L335** The response schema declares fewer fields than the service passes, and Pydantic's default `extra="ignore"` silently drops the extras (`draft/cancelled/overdue/approval_rate/by_source_org/by_month`, `not_reported_count/pending_review_count/overdue_count/report_rate`, etc.). Callers receive zeroed/missing statistics. Align the schemas with the payload or stop passing unsupported kwargs.

### `backend/app/services/data_sync_service.py`

- **[bug] L219** The failure status is set **after** `safe_commit(db)` has already persisted `status="completed"`, and there is no further commit before the `with self._get_db_context()` block exits — the exiting `db.close()` discards the pending `sync_log.status = "failed"` / `details["errors"]` changes. Result: a partially failed export is permanently recorded as `completed` in `sync_logs`, so UI/audit cannot see the failure. Commit again after mutating the log (the DB session is still open at this point).

### `backend/app/services/data_tier_service.py`

- **[bug] L177** The target tier is derived from the cutoff date (`before_date`) instead of from the records actually being archived, so records of wildly different ages all get routed to the same tier. Worse, with the default `before_date = now - HOT_THRESHOLD_DAYS` (365 days), `determine_tier()` evaluates `age_days == 365 <= HOT_THRESHOLD_DAYS` and returns `HOT`, which then falls into the `else` branch and sends these one-year-old records to **cold** storage rather than warm. Derive the tier from each record's own date (or compare `before_date` against the WARM/COLD thresholds directly) and explicitly skip HOT records instead of silently cold-archiving them.

- **[bug] L248** The archive write and the row deletion are not atomic. If the process dies (or `safe_commit` fails) between `f.write(json_data)` and this delete, the `.gz` is written but the rows stay in the DB — restoring that archive later duplicates every row. Symmetrically, if an exception occurs mid-`gzip` write, a truncated `.gz` is left on disk while the code returns "archive failed" without removing it. Write to a temporary file, flush/fsync, then `os.replace()` into the final path only after the content is complete, and ensure the DB delete is committed in the same unit of work that owns the archive. Note also that on this failure path `archive_records` logs and returns without calling `db.rollback()`, leaving the session dirty for the caller.

- **[bug] L202** This is effectively a no-op that reports success. `archived` is incremented for every scanned row even when the model has no `is_archived` attribute (nothing is modified at all in that case), and even when it is set, the record is not moved out of the hot DB and the archive query in `archive_records` does not filter on `is_archived` — so the same rows are re-scanned and re-counted as "archived" on every subsequent run. Either implement the real warm-tier migration (and exclude already-archived rows from the query) or return an explicit unsupported/failure result instead of a success count.

### `backend/app/services/data_validator_service.py`

- **[bug] L561** `validate_county` is a no-op that also produces duplicate errors. `FIELD_TYPES["county"] = "county"`, so `validate_row` → `_validate_field_format` already runs `_validate_county_field` for every row; this extra block appends a **second, identical** INVALID_COUNTY error for the same row/field (23 duplicate errors for a 23-row file), and `validate_county=False` does not actually disable county validation. Either remove this block (county is always validated) or honor the flag inside `validate_row`.

- **[security] L1029** Removing SQL keywords as bare substrings corrupts legitimate data: `OR` strips the middle of `FOR`→`F`, `ORDER`→`ER`, `AND` from `BAND`, `DELETE` from `DELETE`d pinyin/English names, etc. `re.sub(keyword, ...)` is also applied per keyword per row (no precompiled pattern). Blacklist substitution is not a real injection defense anyway — the correct fix is parameterized queries at the persistence layer, and here the sanitizer should be removed or limited to HTML/control-char stripping.

### `backend/app/services/database_health_service.py`

- **[bug] L310** The WAL bloat warning can never fire: `size_after` is sampled **after** `PRAGMA wal_checkpoint(TRUNCATE)`, which has already truncated the `-wal` file to ~0 bytes, so `size_after` is (almost) always far below the 50MB threshold. The meaningful growth indicator is `size_before` (captured before the checkpoint). Compare against `size_before` so the warning actually reports WAL bloat, and keep using `size_after` only for the debug log.

### `backend/app/services/db_maintenance.py`

- **[bug] L68** `stop_db_maintenance` leaves the stale `_maintenance_thread` handle, unlike `stop_wal_checkpoint_scheduler` (which explicitly documents and fixes this). After any stop, a subsequent `start_db_maintenance()` hits `if _maintenance_thread is not None: return` and silently no-ops, so periodic maintenance never restarts within the same process (TestClient/lifespan re-init, hot reload, etc.). Reset the global to `None`, matching the WAL scheduler.

### `backend/app/services/encrypted_package.py`

- **[bug] L94** The parser never checks the number of bytes actually read from a (possibly truncated / tampered) file: - `f.read(4)` for the length field returns <4 bytes at EOF, so `struct.unpack` raises `struct.error` instead of the documented `ValueError`. - `meta_len` is taken from the file with no upper bound; `f.read(meta_len)` can be asked to allocate up to ~4 GB for a crafted header, and a short read is silently accepted, shifting the parse of `encrypted_data`/`checksum`. Validate each read and bound `meta_len` against the remaining file size.

### `backend/app/services/entity_import_validator.py`

- **[bug] L203** The default `entity_type="supported_village"` has no entry in `ENTITY_CONFIGS` (which only defines the singular keys `project`/`fund`/`school`), so `self.config` silently becomes `{}`. In that state `get_column_mapping()` returns `{}`, `parse_excel_headers()` maps no columns, `get_required_fields()` returns `[]` and `validate_row()` performs no required/format/enum checks at all — every row is reported as valid. Callers (`_resolve_validator` in `import_data.py`, `excel_importer_service.py`) pass the raw `entity_type` through, so any unknown/plural/typo value (e.g. `projects`, `supported_villages`) silently disables validation instead of failing fast. Suggest raising a `ValueError` for unsupported types (or raising inside `__init__` when `entity_type` is not in `ENTITY_CONFIGS`) rather than falling back to an empty config.

### `backend/app/services/excel_importer_service.py`

- **[bug] L284** Dead statement: `self.validator.convert_row_types` (and the same line with `entity_validator` in the `else` branch) is missing the call parentheses and its return value is never used, so whatever batch type-conversion it was meant to perform never happens. If it is required before validation, assign/use the result (e.g. `rows = self.validator.convert_row_types(rows)`); otherwise delete the line.

- **[bug] L379** Unlike the `SQLAlchemyError` branch below, this generic handler rolls back the transaction (which discards the flushed `ImportHistory`) and returns without recreating it. The caller receives `result.import_history_id` pointing to a row that was never persisted and no failure is recorded. Persist an `ImportHistory` with `ImportStatus.FAILED` here as well, or move the history creation outside the rolled-back transaction.

### `backend/app/services/fund_anomaly_detector.py`

- **[bug] L62** The de-duplication key is only `project_id + fund_id + anomaly_type + resolved`, but all cross-record rules (duplicate voucher, contract split, single source, and large cash when `tx.fund_id` is None) emit `fund_id=None`. Because pending objects are auto-flushed before the next query, the second and every subsequent finding of the same type in the same project is treated as a duplicate and silently dropped — e.g. three distinct duplicate-voucher groups produce only one `FundAnomaly` row. Include a discriminating field (e.g. the description, or a stable detail key) in the existence check so distinct findings are all persisted.

### `backend/app/services/import_export_history_service.py`

- **[bug] L21** `self._is_async` is computed but never read anywhere in the file, so it is dead state. More importantly, the constructor advertises support for `AsyncSession`, yet the sync helpers below (`get_history_by_package`, `create_history`) use `self.db.query(...)` / `self.db.refresh(...)` / `safe_commit(self.db)`, none of which work on an `AsyncSession` (SQLAlchemy raises `AttributeError`/`MissingGreenlet`). Since the flag is already computed, either dispatch on it (or raise a clear error for unsupported combinations) so callers cannot silently take the wrong path.

### `backend/app/services/machine_code_permission_service.py`

- **[bug] L65** Semantics conflict between the read and write paths. `get_restricted_permissions` returns these rows as *restrictions* (rbac_service subtracts them from the user's effective permissions), but `grant_permission`/`revoke_permission` plus the `POST /{machine_code_id}/permissions` endpoint label the exact same rows as *granted* permissions (returning `granted_count` and "成功授予 N 个权限"). As written, an admin calling "grant" actually denies/removes that permission from the user. Confirm the intended meaning of `MachineCodePermission` rows and align naming/behavior (the model docstring describes them as 权限限制).

### `backend/app/services/machine_code_service.py`

- **[bug] L339** `hmac.compare_digest` raises `TypeError` when either argument is a non-ASCII `str`; user-supplied pass codes containing CJK/emoji cause an unhandled 500 instead of returning False/None. Encode both sides to UTF-8 bytes before comparing.

- **[bug] L1037** The reuse lookup filters on `status == "pending"` only. Once the record is activated/revoked, a new row with the same deterministic `pass_code` is inserted, violating the UNIQUE constraint and raising an unhandled `IntegrityError` (500). Match the record regardless of status (resetting status in the reuse branch) or catch/handle the constraint.

### `backend/app/services/message_service.py`

- **[bug] L36** Retention value contradicts the documented policy: this constant is 30, while the class docstring and `cleanup_old_messages` ("Requirements: 5.6 - 保留消息记录90天" / "days: 保留天数，默认90天") state 90 days. The scheduled cleanup therefore permanently deletes messages 60 days earlier than specified. Align the constant with the documented requirement (or fix the docstrings if 30 is intended).

### `backend/app/services/message_template_service.py`

- **[bug] L380** Error handling here only survives a single missing placeholder. `str.format` raises on the first missing key, so if the template has two or more unknown placeholders (e.g. the shipped APPROVAL_PENDING template with `{count}`/`{earliest_time}` if the caller omits one), the retry call inside the except block raises a second, uncaught `KeyError`. Malformed/user-typed braces (`{`, `}`) or positional placeholders (`{}`, `{0}`) also raise uncaught `ValueError`/`IndexError`, which will break notification rendering. Use a `defaultdict`/`format_map` with a safe mapping, or loop until no missing keys remain and also catch `ValueError`/`IndexError`, e.g. render via a custom `string.Formatter` that preserves unknown fields without raising.

- **[bug] L80** Modification history is only kept in an in-memory list on the service instance, and the service is created per-request via `get_template_service()`/`MessageTemplateService(db)` (see backend/app/api/v1/messages.py). As a result the history recorded by `_record_history` here is discarded as soon as the request ends, so Requirement 7.4 (记录修改历史) is not actually satisfied, and the list also grows unbounded for long-lived instances. Persist entries to a DB table (e.g. `message_template_histories`) or the existing audit log instead of instance state.

### `backend/app/services/monitoring_service.py`

- **[bug] L256** Check-then-act race: the "already triggered" lookup and the subsequent INSERT are not atomic. Two concurrent `check_alerts` runs (e.g. overlapping scheduler ticks or multiple workers) can both see no existing alert and each insert an AlertHistory row, producing duplicate alerts for the same rule. Add a DB-level guard (unique constraint on (rule_id, status='triggered') plus catching IntegrityError, or SELECT ... FOR UPDATE / an upsert) instead of relying on the pre-check.

### `backend/app/services/notification_preference_service.py`

- **[bug] L51** `get_preference` does a check-then-create without any locking or conflict handling. `NotificationPreference.user_id` has `unique=True`, so two concurrent first requests for the same user will both see no row and the second `safe_commit` raises `IntegrityError`, which propagates to the caller instead of returning a usable preference (and can leave the session rolled back). Handle the unique-violation by re-querying, or use a DB-side upsert.

### `backend/app/services/offline_map_service.py`

- **[bug] L83** `get_coverage()` is declared `async` but contains no `await`: the whole recursive `iterdir()`/`is_dir()`/`stat()` walk runs synchronously on the event loop (and `save_tile()` calls `mkdir()` synchronously too). On a cache with many tiles this stalls all other requests. Either make this a plain sync method called via `run_in_executor`/`anyio.to_thread`, or drive the traversal off the loop. Also note that if `__init__` swallowed the `mkdir` failure, `self.cache_dir.iterdir()` raises an uncaught `FileNotFoundError` (the local `try/except` only catches `ValueError`) — guard the traversal and treat an unreadable directory as empty coverage.

### `backend/app/services/organization_code_service.py`

- **[bug] L46** `validate_code` rejects the service's own output: `generate_code(..., prefix=...)` returns `PREFIX-XXXXXXXX` containing a hyphen, and `"PREFIX-XXXXXXXX".isalnum()` is `False`. Any caller that generates a prefixed code then validates it will treat a legitimate code as invalid. Make validation accept the separator(s) the generator can emit (and consider validating the format rather than only the character class).

### `backend/app/services/organization_permission_service.py`

- **[bug] L25** `PermissionDeniedError` inherits `BusinessError`, whose default `status_code` is 400, so every permission denial is surfaced as HTTP 400 by `register_exception_handlers` (it uses `exc.status_code`). A permission failure should be 403; clients/tests distinguishing "bad request" from "forbidden" will mis-handle it. Pass `status_code=403` explicitly.

### `backend/app/services/organization_service.py`

- **[bug] L466** `org.level` can be NULL for legacy rows, and the column is declared `String(50)` in the model while some code paths write integers and others write `"level_N"` strings (see `OrganizationCreate.level` / `_validate_org_enums`). `max(max_level, org.level)` therefore raises `TypeError` as soon as a row has a non-int level (e.g. `None` or `"level_1"`), taking down the whole statistics endpoint. Normalize the level to an int before aggregating.

- **[bug] L342** `org.path` is nullable (the model declares `path = Column(String(500), nullable=True)`, and this very file documents that orgs created through the API historically have NULL `path`/`level`). Calling `.strip("/")` on `None` raises `AttributeError`, so `get_ancestors` crashes for exactly the legacy rows that `repair_organization_paths()` / `get_subordinate_organizations()` are written to tolerate. `int(id_str)` can additionally raise `ValueError` on a malformed path. Guard the NULL/malformed case and return `[]` instead of throwing.

- **[bug] L375** Blind mass assignment over every set field of `OrganizationUpdate`: `parent_id` can be changed (and `level`/`path` overwritten) without calling `validate_parent_child_relationship` and without recomputing the node's and all descendants' `path`/`level`. That allows A→B→A cycles and leaves stale paths, which corrupts the `path`-prefix based organization data-permission matching used elsewhere. Whitelist the mutable scalar fields and handle a `parent_id` change explicitly (cycle check + subtree path/level recompute).

### `backend/app/services/package_record_validator.py`

- **[bug] L109** Explicit `None` for a NOT NULL column that has a default passes field validation. `is_active = Column(Boolean, default=True, nullable=False)` (project.py:144 / school.py:104 / supported_village.py:104, fund.py:146) is not in `_SYSTEM_COLUMNS`, and because it has a `default` it is excluded from `required`; the trim loop only handles strings, and the phone/date/enum/numeric loops all `continue` on `None`. So `{"is_active": null}` is accepted as "ok", and since the key is explicitly present in the INSERT, SQLAlchemy will NOT apply the column default — the DB raises a NOT NULL violation that aborts the whole bulk upsert (`_bulk_upsert_records` rolls back the batch). Recommend dropping explicit `None` values for non-nullable columns (or reporting them as rejected) instead of excluding only `default`-bearing columns from the check.

### `backend/app/services/password_encryption_service.py`

- **[bug] L136** `decrypt_data` uses `salt_hex` and `iterations` from stored (potentially attacker-influenced) metadata without validation: a malformed hex string raises an uncaught `ValueError` from `bytes.fromhex()`, `iterations <= 0` raises inside `pbkdf2_hmac()`, and a huge `iterations` value turns decryption into a CPU-denial-of-service (PBKDF2 cost scales linearly with iterations). These surface as unexpected 500s even though the documented contract is `Raises: InvalidPasswordError`. Validate/clamp both inputs and translate low-level failures (or reject out-of-range metadata) into the documented exception.

### `backend/app/services/permission_package_service.py`

- **[bug] L882** `is_superuser` is written into `data/user_legacy.json` during export, but the import never restores it here: mirror mode overwrites role/permissions/data_scope only. The documented contract ("完全还原权限分配") is therefore violated — a superuser exported from the source machine silently becomes a normal user on the target, and vice-versa (a target superuser keeps elevated rights after a mirror import that should have replaced them).

- **[bug] L680** `organizations_data` exports `parent_id`, but `_import_organizations` never assigns it on update or create, so the org hierarchy is silently flattened on the target machine (any scope inheritance derived from the tree is not reproduced). Note that the exported `parent_id` is the *source* machine's id and cannot be copied verbatim on a fresh DB where ids differ — the parent must be resolved by `code`/`name` in a second pass after all organizations have been upserted, then assigned.

- **[bug] L799** When neither the import-built map nor `role_name` resolves, this falls back to the raw old role id. `_import_user_roles` then inserts `UserRole(role_id=<stale id>)`, and because `rbac_user_roles.role_id` has an FK to `rbac_roles.id`, the violation only surfaces at `commit()`, rolling back the entire import and returning a generic failure instead of skipping the single row. Return `None` here so the caller counts it as `user_roles_skipped`.

### `backend/app/services/policy_fts_service.py`

- **[bug] L35** `ensure_fts_table` is invoked on the read path (`search_policies_fts` calls it before checking the query), and it performs DDL/backfill plus `safe_commit(db)`. On the caller's shared session this flushes and commits whatever unrelated pending work the request holds, and it also means a read-only search request can mutate the database. Prefer creating/backfilling the index only at startup or in a migration (or use a dedicated connection/transaction), and avoid committing the caller's session here. Note also that the existence probe in `ensure_fts_table` runs an extra `sqlite_master` query on every single search.

### `backend/app/services/policy_import_service.py`

- **[bug] L114** Per-row DB failures are not contained: `_process_policy_row` re-raises whatever `db.flush()` threw, but this handler only catches `ValueError/TypeError/KeyError`. SQLAlchemy errors (`IntegrityError`, `StatementError`, … — all `SQLAlchemyError` subclasses) therefore escape to the outer `except Exception`, which rolls the session back and returns a 500 for the whole file, discarding the rows already staged in earlier savepoints and breaking the documented partial-import/`errorRows` contract. Catch the DB exceptions here and downgrade them to a row error (the nested savepoint rollback already leaves the session usable).

### `backend/app/services/rbac_service.py`

- **[bug] L200** The resource-access fallback always checks the literal `"write"` level, regardless of which `permission` is being verified. Consequences: (a) a read-only resource grant can never satisfy a check, and (b) a `write` grant on the resource satisfies *unrelated* permission checks (delete/export/publish) for that resource. Derive the required access level from the requested permission (e.g. map `*:read` -> `read`, `*:delete` -> `delete`, otherwise `write`) instead of hardcoding `"write"`, or only apply this fallback when the permission actually maps to that resource.

### `backend/app/services/reminder_engine.py`

- **[bug] L28** The approval reminder scans can never deliver a message: `reminder_engine.scan_overtime_approvals()` / `scan_approaching_approvals()` build dicts with only `type/entity_id/title/elapsed_hours` and never set `user_id` (unlike the deadline/budget scans), and `reminder_orchestrator.run_reminder_scans` drops any reminder whose `user_id` is falsy (`messages.user_id` is NOT NULL). Every approval overtime/approaching reminder is silently discarded, so `run_reminder_scans` returns 0 for approval reminders forever. Resolve the recipient (cf. `reminder_service._resolve_reminder_recipient`: current approver → node approver → submitter) or stop scanning these two types.

- **[bug] L17** Naive local time vs UTC-stored timestamps. `created_at` is written as UTC (`TimestampMixin._utcnow` / `func.now()`), but `datetime.now()` returns local naive time. On a host whose TZ is not UTC the cutoff shifts by the local offset (e.g. UTC+8 flags tasks older than 40h as 48h-overtime), and `elapsed_hours` is inflated by the same offset. Use naive UTC consistently — note you cannot simply use an aware `now` here because SQLite returns `created_at` as a naive datetime and `aware - naive` raises TypeError.

### `backend/app/services/reminder_orchestrator.py`

- **[security] L98** `list_reminders` is not scoped to a recipient: it filters only on `message_type` and returns every user's `Message` rows (title/content of other people's approval tasks, projects and budgets). The only caller (`app/api/v1/reminders.py::list_reminders`) receives `current_user` via `Depends(get_current_user)` but never passes it down, so any authenticated user sees the whole instance's reminders. Accept a user identifier (e.g. `user_id: Optional[int] = None`) and add `.filter(Message.user_id == user_id)` when it is provided, and have the API pass `current_user.id`.

### `backend/app/services/reminder_service.py`

- **[bug] L75** `stop()` 在 join 超时（扫描正在跑 DB 查询）后直接 `return`，保留了 `_running = True`。该标记此后**永远不会被清除**：线程收尾退出后 `_running` 仍为 True，而 `start()` 的第一条判据就是 `if self._running ...`，于是同一实例再也无法重启（只打日志 "已在运行中" 就直接返回）。注释里说的"交由 start 判据兜底"并不成立——start 的判据把 `_running` 也算成运行中，兜底逻辑自相矛盾。建议 start() 以线程存活为准，并在进入时清理上次 join 超时遗留的标记。

- **[bug] L346** `stop()` 无论是否真正停掉线程都不返回状态，这里又无条件把全局单例置空。在 join 超时（旧扫描线程仍存活）的分支下，`_reminder_service` 被清空，随后调用 `start_approval_reminder()` 会新建实例并再起一个扫描线程，于是两个扫描循环并存——正是 R12-4 想避免的重复创建提醒/DB 连接翻倍。建议让 `stop()` 返回 bool（线程确已退出才为 True），仅在成功停止时才清空单例。

### `backend/app/services/report_export_service.py`

- **[bug] L131** Unit mismatch in the exported report: the money columns are stored in 万元 (see `models/fund.py` "金额(万元)" and `models/project.py` "预算金额(万元)"/"实际花费(万元)", matching the API labels), but the fund and project report headers label them as 元. Every figure in the formal Word/PDF document is off by a factor of 10,000 — either relabel the headers as 万元 or multiply the values by 10000 before formatting.

### `backend/app/services/report_service.py`

- **[bug] L331** Silent row truncation: the hard-coded `.limit(100)` caps the export while the Excel subtitle renders `共 {len(data_rows)} 条记录`, so the file both drops records and reports a wrong total. Remove the arbitrary cap (or make it a configurable/page-size parameter) and/or use the real count for the subtitle.

- **[bug] L328** `query_params` is accepted but never used, so the `year`, `village_ids` and `report_type` filters requested by the export endpoints (and by `export_comprehensive_report`) are silently ignored — the report always contains the first N villages regardless of the requested scope. Apply the filters to the query, or drop the unused parameter to avoid misleading callers.

### `backend/app/services/resource_limiter.py`

- **[bug] L82** Expired-timestamp pruning only runs inside `if key in self._rate_limits`. For any key that has no registered rate limit (i.e. any caller of `is_allowed()` before/without `set_quota`/`check_rate_limit`), `_request_counts[key]` is appended to on every call and never trimmed, so the list grows without bound and the limiter leaks memory for the lifetime of the process. Prune unconditionally (or drop the record entirely when the key has no limit). Related: `set_quota` replaces the `RateLimit` but never resets `_request_counts[key]`, so a key re-configured with a new window reuses stale timestamps from the previous configuration.

### `backend/app/services/restore_drill_service.py`

- **[bug] L185** `_latest_backup_file()` runs **outside** the try/except-finally that guards the rest of the drill, so an `OSError` (permission denied on `os.listdir`, or a backup file removed by the concurrent auto-backup/cleanup job between `listdir` and `os.path.getmtime`) propagates out of `run_restore_drill` and can break the daily scheduler job — exactly what the module docstring forbids ("失败不抛出到调度器"). Move the selection inside the guarded block (or catch `OSError` around it) so a failure is recorded as `fail` instead of escaping.

- **[bug] L155** `_verify_restored_db` only fails when `PRAGMA integrity_check` != 'ok'. An extracted file that is empty, zero-length or a valid-but-empty SQLite DB passes integrity_check, `tables_checked` stays `0`, and the caller then records `status="ok"` — a false "backup is restorable" verdict, which is the precise risk this drill exists to catch. Treat "no core table present" as a failure.

- **[bug] L89** `_update_status` stamps `checked_at` for **every** outcome, and `_persist_result` stores that value as `last_restore_drill_time`; `is_drill_due()` therefore returns False for the whole `interval_days` after a `fail` / `no_backup` / `skipped_encrypted` run. A corrupt or missing backup will not be re-verified (and a newly created backup will not be validated) for up to 30 days — masking the very risk the drill is meant to surface. Only advance the schedule when the drill actually proved restorability (or track the last successful drill time separately).

### `backend/app/services/retention_service.py`

- **[bug] L76** Backup is triggered only *after* all rows have already been physically deleted, which contradicts the module docstring promise ("清除前触发一次即时备份（防误删兜底）"). A snapshot taken after the purge no longer contains the deleted rows, so the documented safety net against accidental deletion does not actually exist; the failure path is also only logged as a warning. Either take the backup before the purge loop (so the data is still present in the snapshot), or correct the docstring/design intent so operators are not misled.

### `backend/app/services/rural_work_service.py`

- **[security] L406** Data-scope bypass: `by_type` is aggregated directly on `self.db` without `_apply_work_scope`, so a non-admin receives type counts computed over **all** departments' records while `total`/`planned`/... come from the scoped `base`. The same query should be built from `base` (also lets you collapse the 5 separate COUNT round-trips into one grouped aggregation).

### `backend/app/services/secrets_manager.py`

- **[bug] L43** Both fallbacks produce a value that is NOT a valid Fernet key: `secrets.token_urlsafe(32)` yields a 43-char unpadded base64url string, while `Fernet` requires a 32-byte *padded* urlsafe-base64 key (44 chars). Any downstream `Fernet(self.get_secret("default"))` will raise `binascii.Error`/`ValueError` at runtime, and because these exceptions are swallowed silently (no logging), the root cause (import failure, disk/permission error) is invisible. Narrow the exception handling and log it, and fall back to a well-formed key (or fail fast) instead of an incompatible one.

### `backend/app/services/sentiment/analysis_service.py`

- **[bug] L212** `re.findall(r"\b\w+\b", text)` cannot segment Chinese text: in Python's `re`, CJK characters are all `\w` and there is no word-nonword boundary inside a Chinese sentence, so an entire Chinese title is matched as a single token (e.g. "公司业绩增长显著" -> ["公司业绩增长显著"]). As a result `extract_keywords` returns whole titles/sentences instead of keywords, and the downstream `generate_hot_keywords` aggregation just counts whole titles, making both features effectively meaningless. Suggest splitting on non-CJK/non-alnum characters and using a proper Chinese tokenizer (jieba) or an n-gram fallback, e.g. match runs of alphanumerics plus CJK n-grams.

### `backend/app/services/sentiment/crawler_service.py`

- **[bug] L184** `save_news` hardcodes the sentiment fields and silently discards the values carried on the incoming `NewsItem` (`news.sentiment_score`, `news.sentiment_label`, `news.is_alert`). Any caller that has already scored/alerted the item (or that re-saves a fetched item) loses that information, and the persisted row is inconsistent with the object returned by `fetch_rss_feeds`. Propagate the items' values, falling back to the defaults only when they are unset.

### `backend/app/services/smart_conflict_resolver.py`

- **[bug] L242** Unsafe `updated_at` comparison in MERGE (same pattern in the AUTO/MERGE branch). `import_record["updated_at"]` can be a raw string, or a naive datetime parsed from an ISO string without offset, while the ORM column is `DateTime(timezone=True)` (aware). A str-vs-datetime or naive-vs-aware `>` raises `TypeError` that aborts the whole import. `_determine_auto_strategy` already normalizes with try/except — extract that normalization into a shared helper (e.g. `_to_datetime`) and use it here too, and only perform this timestamp decision when `key == "updated_at"` instead of on every field.

- **[bug] L210** The OVERWRITE/AUTO loops `setattr` every key of the import dict, excluding only id/created_at/created_by. Arbitrary/derived keys (e.g. flattened names, computed fields) become stray instance attributes, and legitimate columns such as `organization_id` or `updated_at` get clobbered — `updated_at` arriving as a string here will break the DateTime column. Filter against the model's mapped columns before assigning.

- **[bug] L227** The KEEP_BOTH copy keeps the imported foreign-key values (e.g. `village_id` / `project_id`) which belong to the *source* id space. Unlike `_import_new_records`, this path never calls `_update_foreign_keys` (id_mapping is not even available here), so the insert can raise an FK violation or link the new record to an unrelated existing village/project. Pass the id mapping into `resolve_conflicts_with_strategy` and remap FKs for the newly created row.

- **[security] L110** Business-key lookups omit any tenant scope. The models carry `organization_id` (see `Project.organization_id`), so an import for one organization can match another organization's row by `code`/`village_name` and OVERWRITE/MERGE will mutate (or KEEP_BOTH duplicate) foreign-tenant data. Add the tenant column to the query conditions, or verify ownership before mutating the matched record.

### `backend/app/services/supported_village_export_service.py`

- **[bug] L86** The docstring promises "其它/未传 → 不筛选", but any unrecognized `tiered_level` (e.g. a legacy/renamed tier string) evaluates `is_tier` to `False` and silently applies `is_revitalization_tier = False`, so the export returns the wrong (and possibly empty) result set instead of ignoring the parameter. Also, when `is_revitalization_tier` is passed explicitly together with `tiered_level`, the two filters are ANDed and can contradict each other. Handle the known values explicitly and skip filtering for anything else, or validate and reject unknown values.

### `backend/app/services/system_config_service.py`

- **[bug] L260** `import_config` is not robust: (1) `json.loads` may legitimately return a list/str/number, in which case `configs.items()` raises `AttributeError`, which is NOT in the `except` clause and therefore propagates to the caller; (2) each `self.set(...)` commits independently via `safe_commit`, so a failure on key N leaves keys 1..N-1 already persisted with no rollback (half-imported configuration); (3) arbitrary keys/values from the JSON are written without validation, so an imported payload can overwrite critical keys such as `initialized`/`organization_id`/`system_id`. Validate the parsed shape, apply all writes in a single transaction (commit once at the end), and reject keys outside the allowed set.

- **[bug] L231** `set_initialized` performs three independent commits. If a failure occurs after the first `set` (e.g. DB error on the second/third write), the system is left marked `initialized=true` while `organization_id`/`system_id` remain empty, producing an inconsistent state that later code trusts. These three writes should be a single atomic transaction (e.g. build/update all rows then one `safe_commit`, rolling back on error).

### `backend/app/services/task_queue.py`

- **[bug] L181** Self-healing condition is wrong after `stop()`. `stop()` sets `_running = False` and cancels all workers but never resets `self._queue` to `None`, so this branch is skipped and the task is put into a queue that no worker is consuming — it stays `PENDING` forever. Gate on the running flag instead (and restart if there are no live workers).

### `backend/app/services/two_factor_service.py`

- **[security] L45** Backup recovery codes are generated and persisted in plaintext (stored verbatim into `TwoFactorAuth.backup_codes` and returned to the client). Unlike the TOTP secret, which is encrypted via `encrypt_field`, these codes fully bypass the second factor, so any DB read/backup leak or an admin viewing the table yields immediately reusable MFA-bypass credentials. Store only a hash (e.g. `hashlib`/`passlib` one-way digest) of each code, return the plaintext list to the user exactly once at enrollment, and compare a hash of the submitted token during `verify_login`.

### `backend/app/services/update_log_service.py`

- **[bug] L402** `force=True` 先 `delete()` 并**单独提交**，随后才在另一个事务里重新插入数据。若插入阶段失败（`safe_commit` 会 rollback 并抛出），已提交的删除无法回滚，`system_update_logs` 会被永久清空，只能靠再次调用（且不能是 force 路径）修复。建议删除与插入放在同一个事务中（循环 `add` 之后只 commit 一次），或先构建好全部待插入记录再执行 delete+insert 并单次提交。

### `backend/app/services/user_service.py`

- **[bug] L104** 密码字段处理有误：User 模型的属性名是 `hashed_password`，并不存在 `password`。因此传 `{"password": "..."}` 时 `hasattr` 为 False，密码被静默忽略（用户以为改密成功）；传 `{"hashed_password": "明文"}` 时则会把明文原样落库，破坏哈希约定。建议显式处理改密分支：用 `get_password_hash` 生成哈希，并拒绝直接写入 `hashed_password`。

### `backend/app/services/validation_engine_service.py`

- **[security] L121** Fail-open error handling: the `try` wraps the DB query *and* the whole rule-execution loop, and on any failure it logs at `debug` and returns an empty list, i.e. "validation passed". A DB outage, a schema change or a mapping bug therefore turns into a security/quality hole (the API answers `valid: true` for invalid data). Same for the `if not self.db: return self.validate(data, {})` branch, which always yields `[]` — a missing session looks like a pass. On failure this should raise / return an explicit error (or at least log at `error`) instead of pretending validation succeeded.

### `backend/app/services/village_cascade_delete_service.py`

- **[bug] L80** Broad `except Exception` blocks swallow all failures in this service (DB locked, constraint violation, genuine SQL/schema errors) and execution continues to `safe_commit`, so the method can report `success: True` while dependent rows remain and reference counts are silently under-reported. Only tolerate a missing table/column; for any other error, log at least at warning/error level, roll back the whole cascade, and re-raise (or surface the failure in the result).

### `backend/app/services/work_log_service.py`

- **[security] L31** Whitelist bypass / mass assignment in WorkLog writes: `WorkLog(**data)` splats caller-supplied keys directly into the model (allowing protected columns such as `id`, `user_id`, `created_at`, `updated_at` to be overwritten, and unknown keys raise `TypeError`), and the update path uses `hasattr(log, key)` which accepts read-only hybrid properties and dunder attributes. Use the existing `_WORKLOG_COLS` whitelist in both the create and update paths.

### `backend/app/services/zero_trust/__init__.py`

- **[security] L77** Fail-open defaults in the zero-trust path for unknown/unregistered fingerprints: `assess_risk` returns `DeviceRiskLevel.LOW` (the least risky level) and `get_trust_score` returns `0.5`, so `is_trusted` returns `True` for never-before-seen devices. This contradicts `verify_device()`, which requires MFA for new devices. Default the unknown case to `MEDIUM`/deny, or require an existing device record before consulting the score.

### `backend/app/services/zero_trust/device_fingerprint.py`

- **[bug] L300** `block_device` sets the device record's `trust_score` to 0.0 but leaves the previously cached `TRUST_CACHE_PREFIX` entry (TTL 1h) untouched. `get_trust_score` reads that cache key first, so it keeps returning the pre-block score (e.g. 0.6) for up to an hour after the ban, defeating the block for any caller that trusts the score.

### `backend/app/services/zero_trust/dynamic_permission.py`

- **[security] L65** The anonymous branch returns early before the blocked-device check at the bottom of the method, so a device that has been explicitly blocklisted can still perform anonymous `read` operations. The device ban is silently ineffective for this path. Consider performing the `is_device_blocked` check (when a fingerprint is present) before this early return, or moving the block check to the top of `evaluate()`.

- **[security] L88** The high-risk/sensitive device-trust checks are entirely skipped when `device_fingerprint` is falsy, so if the middleware fails to supply a fingerprint, `delete`/`admin` are permitted with no device-trust gating at all. This fails open and defeats the zero-trust intent. For sensitive/high-risk actions, consider requiring a fingerprint (deny when absent) rather than treating its absence as trusted.

### `backend/app/services/zero_trust/middleware.py`

- **[bug] L58** The fingerprint generation and the cache lookups (`is_device_blocked` / `get_trust_score`) run unguarded on the global request path, while the module docstring promises "不阻断正常请求" and "不阻断正常请求：仅对已知封禁设备拦截，其余透传". Any error raised by `device_fingerprint_service` (e.g. a cache-backend deserialization error in `get_device`, or a non-float/coroutine value returned by `get_trust_score` making `trust_score < 0.3` raise `TypeError`) will propagate out of the middleware and turn an ordinary request into a 500 instead of a pass-through — a security middleware on the hot path must be fail-open. Wrap the whole fingerprint/block/score block in `try/except Exception`, log the failure, and fall through to `await self.app(scope, receive, send)`.

### `backend/app/startup/environment.py`

- **[security] L96** `_verify_file_integrity` does not actually verify anything: it computes the SHA256 of each file and only logs it at DEBUG level. There is no comparison against a baseline/expected hash or manifest, so file tampering or replacement can never be detected. The docstring's claim ("验证关键文件完整性，防止二进制被替换") is therefore misleading and gives a false sense of security. Either load a baseline hash list (e.g. from a signed/packaged manifest) and compare, logging a warning/error on mismatch, or drop the security claim from the docstring so callers don't rely on a check that is effectively a no-op.

### `backend/app/utils/api_error.py`

- **[bug] L120** `__exit__` forwards **every** exception to `handle_service_error`, including an `HTTPException` intentionally raised inside the `with` block (e.g. 404/400/403). Since `raise_api_error` always raises a new `HTTPException`, the block below is also unreachable and misleading: (a) an intentional `HTTPException` is converted into a generic 500 "<operation>失败", unlike `safe_api_call` which explicitly re-raises `HTTPException`; (b) `return True` can never execute because `handle_service_error` always raises, and if it ever did it would silently suppress the error and return success to the client. Re-raise `HTTPException` untouched and drop the unreachable `return True`.

### `backend/app/utils/audit_logger.py`

- **[bug] L109** `json.dumps` runs before the `try/except` that guards DB persistence, so any non-JSON-serializable value in `details` (e.g. a `datetime`/`Decimal`/ORM object passed via `log_data_change(old_data=...)`) raises `TypeError` and propagates into the caller's business flow — exactly what this module promises never to do. Pass `default=str` (and keep the fallback outside the dangerous path) so serialization can never break the main operation.

### `backend/app/utils/common.py`

- **[bug] L386** The email regex contains stray spaces inside the character classes (`[a - zA - Z0 - 9._%+-]`, `[a - zA - Z0 - 9.-]`, `[a - zA - Z]`). The spaces turn the intended ranges into a broken set that effectively excludes most letters/digits, so ordinary addresses such as `user@example.com` are rejected. Remove the spaces.

- **[bug] L392** Same stray-space problem here: `[3 - 9]` is parsed as the literal characters `3`, `-`, `9` plus space, not the range 3-9. Valid mobile numbers with a second digit of 4-8 (e.g. `13812345678`) are rejected. Use `[3-9]` without spaces.

### `backend/app/utils/drive_detect.py`

- **[bug] L49** Entries from `_list_linux_mounts()` only carry `path` and `type`, but `list_backup_dirs()` documents that every item has an `available` key. Any consumer doing `entry["available"]` on Linux/macOS will raise `KeyError`. Add the key here (the directory was already verified writable with `os.access`, so `True` is accurate).

### `backend/app/utils/encryption.py`

- **[bug] L53** 盐值加载失败时静默降级为**进程内随机盐值**，会把一个配置问题变成不可恢复的数据损坏：任何用密码派生密钥加密过的数据，在进程重启后都会因盐值改变而永远无法解密（且 `InvalidToken` 只在解密时才暴露）。同时该降级路径写入的类属性是不加锁的，多 worker/多线程首次并发调用时可能各自持有不同的盐值。建议显式失败（或至少以 error 级别告警并由调用方决定），而不是继续以随机盐运行。

### `backend/app/utils/helpers.py`

- **[bug] L92** `page_size` / `page` are not validated. With `page_size=0` the `total_pages` computation below raises `ZeroDivisionError`; with `page<1` (or a negative `page_size`) `start` becomes negative and Python slicing silently returns the wrong window instead of an empty/error result. Since both values typically come from request query params, this is reachable from untrusted input. Clamp/validate them before slicing (and guard the divisor).

- **[bug] L143** `except Exception` silently turns *any* malformed amount (e.g. `Decimal('nan')`/`'inf'` quantize raising `InvalidOperation`, unsupported types, overflow) into `Decimal("0")`. A bad input therefore looks like a legitimate zero amount, which can silently corrupt financial data. Narrow the caught exceptions to the ones `Decimal(...)`/`quantize()` actually raise (`InvalidOperation`, `TypeError`, `ValueError`) and at least log/raise so the caller can distinguish "0" from "invalid".

### `backend/app/utils/input_validator.py`

- **[security] L24** The SQL-injection deny-list is both over- and under-inclusive. `(union|select|insert|...)` with `\s` boundaries matches ordinary prose ("please select an option", "update your profile"), and `(--|#|/\*|\*/)` flags `#` in values such as "C#" or "ticket #42", so legitimate requests get rejected with a 400. Conversely, classic payloads such as `' OR '1'='1` (quotes without a second `or`), `1;DROP TABLE users`, or comments without surrounding whitespace slip through. Pattern matching on input can never make dynamic SQL safe — the actual protection must be parameterized queries/ORM bindings; this filter only adds false positives. If a deliberate deny-list is still wanted, anchor it to SQL tokens, drop the bare-word list, and bound the input length (validate_sql_safe currently has no length limit, so the `.*=.*` alternations can backtrack heavily on large inputs).

- **[security] L51** Only `<` and `>` are escaped, and the escaping happens after the pattern check, so HTML entities pass through untouched: `&lt;script&gt;alert(1)&lt;/script&gt;` or `&#60;script&#62;` match no XSS pattern and are returned verbatim — if the result is rendered into HTML the entity is decoded by the browser and the script executes. `&` must be escaped first (otherwise the escaping itself is not reversible/correct), and quotes should be escaped for attribute contexts. Prefer `html.escape(text, quote=True)` over ad-hoc `replace` chains, and consider that this escaping is not idempotent (applying the sanitizer twice double-escapes).

### `backend/app/utils/package_crypto.py`

- **[security] L85** The PBKDF2 iteration count is taken verbatim from the untrusted package header with no sanity/upper bound. A crafted (or corrupted) header such as `_MAGIC + b"\xff\xff\xff\xff" + 32*B` makes the decrypt path run ~4.29e9 PBKDF2 iterations, burning CPU for minutes/hours per request — an unauthenticated DoS amplified by the fact that this code can run before the password is ever validated. Additionally, `iterations == 0` reaches `hashlib.pbkdf2_hmac` and raises a bare `ValueError`. Validate the range before deriving the key, e.g.:

### `backend/app/utils/pagination.py`

- **[bug] L143** The cursor is derived by attribute access on the returned item, which only works when the statement returns ORM entities. For scalar selects (e.g. `select(Model.id)`) the items are plain values, so `getattr(value, col_key, None)` is always `None`; similarly a NULL last ordering value yields `None`. In both cases `has_more` can be `True` while `next_cursor` is `None`, leaving the caller with no way to fetch the next page (truncated results or an infinite fetch loop). Handle the scalar case explicitly — e.g. also try `getattr(last_item, col_key, last_item)` / use `result.mappings()` — and raise or at least log when `has_more` is true but no cursor could be produced.

### `backend/app/utils/runtime_secrets.py`

- **[bug] L58** On a JSON parse failure `loaded` silently stays `{}`, and the code then rewrites the whole file with only the newly generated SECRET_KEY/CSRF_SECRET_KEY. Any other secrets already persisted in that file (e.g. `ENCRYPTION_FERNET_KEY` written by `get_or_create_secret`) are permanently destroyed — subsequent calls regenerate them, making previously encrypted data undecryptable. Additionally, if the file contains valid JSON that is not an object (e.g. `[]` or `"abc"`), `loaded` is a non-dict and `loaded.get(...)` below raises `AttributeError`, crashing startup instead of falling back. Suggest validating the parsed structure and refusing to overwrite a file that could not be parsed.

- **[security] L65** The >=32-character strength check is applied only to the environment variables. Keys read back from `runtime_secrets.json` bypass it entirely, so a short/weak `SECRET_KEY` or `CSRF_SECRET_KEY` present in the file is accepted and injected into `os.environ` without any warning, defeating the stated validation goal.

### `backend/app/utils/upload_helper.py`

- **[security] L81** `_IMAGE_MAGIC` has no `"jpeg"` key, so when `enforce_image_magic=True` the magic sniffing is silently skipped for `.jpeg` files (the most common spelling of JPEG) — a rename from `.exe`/`.svg` to `.jpeg` still bypasses the check, defeating the stated "防改名绕过" protection for callers that rely on it. Add the `jpeg` alias (and consider `jpe`).

- **[bug] L167** In the concurrent-insert conflict branch the winning `FileBlob` is returned without incrementing `ref_count`, even though this request also keeps a reference to the same physical file (the caller then reuses `winner.path` and discards its own copy). The row therefore undercounts references, and a later `delete_attachment_file` will see `ref_count` hit 0 early and delete a file that is still referenced. Increment and persist the winner's count just like the hit path.

### `backend/app/utils/win_proactor_fix.py`

- **[bug] L113** `_silent_close` does not finish the teardown that the original `_call_connection_lost` skipped. When the original raises inside its `finally` (e.g. on `shutdown()`/`close()`), the remaining statements (`self._sock = None`, `self._protocol = None`, `self._loop = None`, `server._detach()`, `self._server = None`) never run, so the transport is left half-torn-down and keeps referencing a closed socket / a live protocol. Closing the socket alone is not enough — complete the cleanup here so the object reaches the same terminal state as the original method.

### `frontend/scripts/patch-vitest-coverage.cjs`

- **[bug] L94** 幂等短路只检测 SITE3（写侧）标记，无法判定读侧补丁（SITE2）是否已生效。若上一次运行是「先写后校验失败」退出的（文件已被写入一半：SITE3 生效、SITE2_ANCHOR 仍在），本次 `npm ci` 重跑会命中此分支直接报「已打最新补丁，跳过」并 0 退出，于是读侧内存镜像回退永远缺失，ENOENT 竞态原样复现——而 CI 显示补丁「成功」。建议同时要求 SITE2_PATCHED 存在才短路，否则继续走下面的修复分支。

### `frontend/src/api/approval.ts`

- **[bug] L371** `autoApproveAll` 与 `batchApprove` 调用的是同类批量接口，但这里既没有做信封解包，返回类型也与 `BatchApproveResult` 不一致：`failed` 声明为 `number[]`，而本文件上方定义的 `BatchApproveResult.failed` 是 `Array<{ id: number; reason: string }>`。若后端返回 `{success: true, data: {success:[...], failed:[...]}}`（正是 `batchApprove` 注释描述的场景），这里会原样把信封对象当成 `{success: number[]; failed: number[]}` 返回，消费方对其 `forEach`/`length` 判断会得到错误结果。建议复用同一套解包逻辑，并统一返回 `BatchApproveResult` 类型。

### `frontend/src/api/backup.ts`

- **[security] L51** `filename` is interpolated directly into the URL path without `encodeURIComponent`. A backup filename containing `/`, `?`, `#` or `../` will be interpreted as part of the route/query and can hit an unintended endpoint (path traversal / request manipulation). Encode the path segment before building the URL.

### `frontend/src/api/batchOperations.ts`

- **[bug] L38** `ids` is sent as an array inside `params`. The backend declares `ids: List[int] = Query(...)`, which FastAPI resolves via `getlist('ids')` and therefore expects the repeated-key form `ids=1&ids=2`. Axios' default params serializer emits bracket notation (`ids[]=1&ids[]=2`) for arrays, so `getlist('ids')` returns empty and the request fails validation (422) — the array is silently mis-serialized. A large selection additionally risks hitting URL-length limits, unlike the other functions here which pass ids in the POST body. Serialize explicitly (or move ids into the body once the backend supports it).

### `frontend/src/api/export.ts`

- **[bug] L46** `getExportHistory` is byte-for-byte identical to `getExportTasks` (lines 39-43): both hit `${ASYNC_EXPORT_BASE}/tasks` with the same params. This is almost certainly a copy-paste bug — either the history endpoint differs (e.g. a history/completed endpoint) or one of the two functions is redundant dead code and should be removed/re-exported as an alias.

### `frontend/src/api/helpers/blobDownload.ts`

- **[maintainability] L47** `parseFileName` 是 `@/api/request` 中已导入的 `parseContentDisposition` 的近乎逐行复制（正则、`''` 切分、decodeURIComponent 逻辑完全一致），只有返回值语义不同（null vs fallback）。同一份解析逻辑存在两份实现，后续修 bug（如 RFC 5987 引号/编码边界）时必须同步改两处，极易发散。建议直接复用已导入的实现，例如：`export const parseFileName = (cd?: string | null): string | null => parseContentDisposition(cd ? { 'content-disposition': cd } : undefined, '') || null`，或让 `getFileNameFromResponse`/`downloadBlobAsFile` 统一调用 `parseContentDisposition`。

- **[bug] L118** `result.data as Blob` 是无校验的不安全断言。当接口以 `responseType: 'blob'` 返回错误体（JSON/HTML 文本）、204 空响应或 axios 在某些环境下返回 string/ArrayBuffer 时，`blob` 并非 Blob：随后 `triggerDownload` 里的 `URL.createObjectURL(blob)` 会抛出难以定位的 TypeError，或更糟——把 JSON 错误内容当成文件静默保存成损坏文件。建议在下载前做实例校验（并可选校验 `content-type`）。

### `frontend/src/api/organization.ts`

- **[security] L9** Data is passed in the URL query string where it does not belong: `confirm_password` for the organization delete, and key/version identifiers (`version_id`, `key_type`) for the secrets endpoints. Query strings routinely end up in browser history, proxy/gateway access logs, server request logs and Referer headers, and this is also inconsistent with the rest of these modules. Send the values in the request body/header instead — this may require widening the shared `del`/`post` helpers to accept a config/body.

### `frontend/src/api/permissionPack.ts`

- **[bug] L47** Envelope precedence bug: the shared interceptor (request.ts) unwraps `{data: payload}` and additionally exposes array payloads as `items`. When the backend returns a paginated envelope like `{code, data: {items: [...], total}}`, `res.data` is the pagination **object** (truthy), so the `res.items` fallback is never reached and `Array.isArray(list)` then silently degrades to `[]` — the list is rendered empty with no error. Prefer `items` (the interceptor's canonical array slot) and/or verify each candidate is an array.

### `frontend/src/api/request.ts`

- **[bug] L199** **Bug: caller-provided `cancelToken` is silently overwritten for GET requests.** `createCancelableRequest()` / `requestWithTimeout()` attach `axios.CancelToken.source().token`, but this line replaces it unconditionally with the de-duplication token. As a result `cancel()` becomes a no-op for every GET: `requestWithTimeout` no longer aborts the timed-out HTTP call (the socket stays open until the 30s instance timeout) and the exported `createCancelableRequest().cancel` API is broken. Only install the dedup token when the caller has not supplied one (or link both tokens).

### `frontend/src/api/secrets.ts`

- **[security] L75** Path parameters are interpolated directly into the request URL without `encodeURIComponent` or validation (see the flagged lines in each of these files). IDs containing reserved characters (`/`, `?`, `#`, spaces) corrupt the route or can be used to manipulate the path (e.g. `../`), and an `undefined`/`NaN` id silently produces a request to `/.../undefined` instead of failing fast. Encode the path segment and add a cheap guard (`Number.isInteger(id)` / reject empty ids) before issuing the request in every wrapper that builds a path from an id; other modules in this layer (e.g. `api/dataTier.ts`) already encode path params.

### `frontend/src/components/FilePreview.vue`

- **[bug] L63** **Blob URL leaks from missing cleanup.** The watcher awaits `fetchBlob()` with no cancellation/token, so a late-resolving call after the dialog is closed or another preview is requested still runs `URL.createObjectURL(blob)` on a closed/other dialog and the URL is never revoked. Cleanup also depends solely on the dialog `@close`; if the component unmounts while a preview is open (route change, conditional rendering, `destroy-on-close`), `release()` never runs and the object URL leaks. Guard the async fetch with a request token and add `onBeforeUnmount(release)` (import `onBeforeUnmount` from `vue`).

- **[bug] L59** **Stale state not reset before a new load.** Only `loading`/`unsupported` are reset; a previously set `objectUrl`/`blobRef` is never cleared. If the new fetch fails (catch) or returns a zero-size blob (early `return`), the previous file's preview/download remains visible and is wrong. Release the old state before starting the load (e.g. call `release()` here).

### `frontend/src/components/MapPicker.vue`

- **[bug] L122** `onInputChange` forwards the raw field value to the parent without any validation. With `v-model.number` on `el-input`, clearing the field yields an empty string and non-numeric text can yield `NaN` (and on a component v-model the `.number` modifier is not guaranteed to be applied by ElInput at all), so `innerLng`/`innerLat` (declared as `number`) can actually hold a string/`NaN`. Downstream this produces corrupted coordinates and `innerLng.value.toFixed()`-style failures. Please coerce + validate (finite number, valid lng/lat ranges) and skip emitting invalid values.

- **[bug] L85** The `modelValue` watcher only reacts to truthy objects and never clears the internal state, while the `latitude`/`longitude` watchers only write non-null values. When the parent resets the model to `null`/`undefined` (e.g. form reset), `innerLng`/`innerLat` keep the stale coordinate and the next `change` re-emits it. Also, mutating `props.modelValue.lng` in place will not trigger this watcher. Handle the null/empty case and consider a deep watcher.

### `frontend/src/components/business/SystemStatus.vue`

- **[bug] L225** Timer lifecycle race: `onMounted` awaits `refresh()` (network calls) before creating the interval. If the component unmounts during that await, `onUnmounted` has already executed, so the later `setInterval` handle is never cleared and the timer keeps firing on a destroyed component (leak + updates to a stale component). Track an `isUnmounted` flag / cancel the pending work before starting the interval.

### `frontend/src/components/common/BaseChart.vue`

- **[bug] L53** `deep: true` + `notMerge = true` is a costly and state-destroying combination. Deep watching a large option object re-traverses the whole tree on every nested mutation, and `setOption(option, true)` replaces the entire chart config, resetting user-driven internal state (dataZoom position, legend toggles, selection, tooltip highlight). On any data refresh after the user zooms/pans, the view jumps back. Prefer merging (`setOption(newOption)`, optionally with `lazyUpdate: true`) so ECharts diffs the config; if replacing is intentional, watch the identity of `props.option` (no `deep`) instead to avoid the traversal cost.

- **[bug] L63** **Resize listener lifecycle is unsafe.** The listener is registered in a `nextTick` callback after `onMounted`; if the component unmounts before that tick, `onUnmounted` has already run and the listener is attached to a destroyed component, leaking and calling `resize()` on a stale instance. Registration is also decided once at mount from `props.autoResize` while removal is decided from the prop value at unmount, so toggling `autoResize` desyncs and leaks (or never attaches). Guard the callback with an `isUnmounted` flag and track attachment explicitly (remove unconditionally).

### `frontend/src/components/common/ChangeHistoryDialog.vue`

- **[bug] L45** `formatValue` is called during render and can throw: `JSON.stringify` raises `TypeError` on circular references (a plausible shape for values coming from a backend payload) and on `BigInt` values. A throw inside the template render aborts the whole dialog render instead of degrading to a placeholder. Wrap the serialization in try/catch and fall back to a safe string representation.

### `frontend/src/components/common/StatsCard.vue`

- **[bug] L37** `props.value` is only guarded for `string`; any other non-number runtime value falls through to `.toLocaleString()`. Callers merge API payloads of type `any` (e.g. `Analysis.vue`: `stats.value = { ...stats.value, ...data }` with `res: any`), so `null`/`undefined`/`NaN` can reach here and will either throw `TypeError` (`null.toLocaleString()`) or render `NaN` on the card. Additionally the default runtime locale is used, while callers format with an explicit locale (`toLocaleString('zh-CN')`), producing inconsistent separators between cards in the same view. Please guard with `Number.isFinite` and pin an explicit locale (ideally reuse the shared `format`/`Intl.NumberFormat` helper used by the views).

### `frontend/src/components/dataPackage/ExportDialog.vue`

- **[bug] L92** The download failure is swallowed silently while the user was already told `正在下载文件...`. If `downloadPackage` rejects (network error / 401 / expired blob URL), the user sees a success toast, the dialog closes, and no file appears — a real failure is masked. At minimum surface a warning so the user knows to download manually from the list, and log the error for diagnostics.

### `frontend/src/components/dataPackage/ImportDialog.vue`

- **[bug] L60** Dialog state is never reset. The dialog is not `destroy-on-close` and there is no watcher on `props.modelValue`, so `selectedFile`/`fileList` survive a cancel/close. Reopening the dialog shows the previously selected file with the 导入 button already enabled, which can trigger an unintended duplicate import. Note the sibling `ImportEncryptedDialog.vue` already handles this with a `watch(() => props.modelValue, ...)` reset — apply the same pattern here (remember to import `watch`).

### `frontend/src/components/dataPackage/ImportEncryptedDialog.vue`

- **[bug] L114** The dialog only performs step 1 of the encrypted-import flow. `POST /data-packages/upload-encrypted` just saves the file and creates a package record with status `pending` (backend: `_create_package_record(..., status=PackageStatus.pending)`); the actual decryption/import requires the follow-up calls `POST /data-packages/decrypt-preview/{package_id}` and `POST /data-packages/confirm-import/{package_id}`. As written, the user's password is never used by the backend for this endpoint and the data is never imported, yet the UI reports "导入成功" and closes. Please chain the remaining steps (using the returned `result.id`) or explicitly label this as an upload/staging step instead of a successful import.

### `frontend/src/components/funds/YearlyComparisonChart.vue`

- **[bug] L35** `department` is sent to `/funds/supported-village/statistics/yearly-comparison`, but the backend handler `fund_stats_yearly_comparison` only declares `year_start` / `year_end` (see backend/app/api/v1/funds.py:1059-1065); FastAPI silently ignores the unknown query param. The result: the chart renders unfiltered data while the parent believes it is filtered by department, and the `department` watcher below only triggers a redundant reload with identical results. Please align the contract (add `department` filtering server-side, filter client-side, or drop the prop/param) instead of sending a parameter that has no effect.

### `frontend/src/components/map/OfflineMap.vue`

- **[bug] L85** Race between async mount and unmount: the dynamic `import()` of the GeoJSON resolves after `onMounted` returns. If the component is unmounted while the import is pending, `initChart()` still runs afterwards and creates an ECharts instance plus a `window.resize` listener that `onUnmounted` has already had its chance to remove (the chart is then never disposed and `chart` is reassigned after being nulled). Add an `isUnmounted` guard that is set in `onUnmounted` and checked after the `await`, and bail out early in `initChart`.

### `frontend/src/components/permission/MenuVisibilityPanel.vue`

- **[bug] L128** `onMenuCheck` only reads `checked.checkedKeys` and discards `checked.halfCheckedKeys`. With `:check-strictly="false"`, a parent node whose children are only partially selected stays half-checked and is therefore never persisted; if the backend hides a parent menu whose key is absent, those children become unreachable in the navigation. Include the half-checked (ancestor) keys, and avoid assigning `undefined` when the event payload is malformed.

### `frontend/src/components/permission/PermissionAssignmentDrawer.vue`

- **[bug] L170** Stale-response race on user switch: `loadCurrentPermissions` / `loadMenuConfig` / `loadAllRoles` are fired without any cancellation or identity check, so a slow response for user A can land after the user has been switched to B and overwrite `currentPermissions` / `currentMenuKeys` with A's data. Worst case the operator then clicks 保存权限 and writes A's permission set onto B. Capture the requested user id and discard the response if `props.user` has changed (or abort the previous request via the cancel helper in `@/api/request`).

### `frontend/src/components/permission/RoleTagsPanel.vue`

- **[bug] L89** The `catch {}` swallows every failure (403/network/5xx) and resets `assignedRoles` to `[]`, so a failed fetch is indistinguishable from "user has no roles" — admins may then re-assign or double-revoke. Additionally `(res.data || res || [])` does not guarantee an array: `get()` already unwraps one level (see `apiRequest` doc in `@/api/request`), and if the payload is a non-array object (e.g. an error/empty envelope), `assignedRoles` becomes an object and `assignedRoles.value.map(...)` inside `availableRoles` throws an uncaught render error. Suggest validating the array explicitly and surfacing the error instead of silently clearing state.

- **[bug] L18** Every tag is closable with no confirmation at all, including `is_system` roles. A single mis-click immediately issues the revoke request and can strip the user's only/system role. At minimum add an `ElMessageBox.confirm` before revoking, and require an extra confirmation (or hide the close action) for `role.is_system` roles.

### `frontend/src/composables/useAutoLock.ts`

- **[bug] L38** The bare `catch {}` silently swallows every failure. Combined with the `require` failure above this makes a security-relevant failure (auto-lock not actually locking) completely invisible. At minimum log the error (e.g. `console.error('[useAutoLock] 锁屏失败', e)`) so the failure is detectable; a fully silent catch around session-clearing logic is unsafe.

### `frontend/src/composables/useBackupSchedule.ts`

- **[bug] L36** `parseCron` only understands plain numeric minute/hour plus `*` for dom/dow, so valid cron expressions containing steps/lists/ranges are silently mis-parsed. For `"*/5 2 * * *"` the minute field `*/5` is passed through `padStart` unchanged and the function returns `backupTime: '02:*/5'` (an invalid time the UI then displays/round-trips), and expressions such as `"0 2 * * 1,3,5"` collapse to a single `weekly` without preserving the selected weekdays. Suggest validating each field as a number before using it (falling back to the default when it is not) and explicitly handling unsupported forms instead of silently reporting `daily`.

- **[bug] L46** `backupTime` is destructured without any format/range validation, so values like `'25:99'`, `'abc:xyz'` or `'3:'` (empty minute, default `'0'` is not applied to `''`) are padded and sent to the backend as an invalid cron string. The backend stores it verbatim (`backup_schedule_cron`), so the scheduler would silently receive a broken expression. Validate/normalize `backupTime` (numeric and 0-23 / 0-59) and abort `saveSchedule` with a friendly message when it is invalid.

- **[bug] L49** Hardcoding weekday `1` / day-of-month `1` makes the friendly model lossy: a backend cron like `"0 2 * * 3"` (or `"0 2 15 * *"`) is loaded as `weekly`/`monthly`, but the very next save rewrites it to Monday/day-1, silently changing the user's schedule (data loss on round-trip). Either preserve the parsed dom/dow value in the config model or refuse to save when the loaded cron does not match the canonical form.

### `frontend/src/composables/useEventBus.ts`

- **[bug] L6** The handler registry is a module-level singleton that is never disposed. Every `on(...)` call adds to `eventHandlers`, and if a component forgets to call `off` (common when a component unmounts), its callback stays referenced forever, causing stale executions and unbounded Map growth. Consider exposing a `clear()`/dispose API and/or tying subscriptions to a component lifecycle so they can be released automatically.

- **[bug] L21** `forEach` has no error isolation: if one handler throws, iteration aborts and all remaining handlers for the event are silently skipped, and the error propagates to the emitter. Wrap each handler invocation in try/catch (and log/report) so a misbehaving subscriber cannot break the others.

### `frontend/src/composables/useKeyboardShortcuts.ts`

- **[bug] L83** 组合键归一化逻辑与 `formatShortcut` 重复实现，两处必须保持完全一致，否则注册表与真实事件会静默失配。当前已经存在实际缺口：`e.key` 在按住 Shift 时会返回符号而非数字键，例如注册 `{ key: '1', shift: true }`（`formatShortcut` → `Shift+1`）时，真实事件算出的是 `Shift+!`，快捷键永远不会触发（现有调用方的 `key: '?'` 恰好因 `?` 本身即大写符号而“侥幸”可用）。此外 `e.metaKey` 被并入 `Ctrl`，Shortcut 接口没有 meta 字段，macOS 下无法注册仅 Cmd 的快捷键。建议抽取唯一的构建函数供注册与匹配共用，并对 Shift+数字/符号键做归一化（或使用 `e.code`）。

### `frontend/src/composables/useRouterSafe.ts`

- **[bug] L46** For an *internal* path the router does not know, this performs a full-page reload (`window.location.href`) that re-boots the SPA and finally renders the catch-all NotFound view — i.e. a needless reload that discards all in-memory state (and repeats on every call). The native fallback should be reserved for genuinely external URLs; for internal unknown paths prefer `router.push({ name: 'NotFound' })` (or surfacing an error) so the SPA stays alive. Note `router` (the resolved path) is also lost, since only the raw `pathString` is used here.

- **[bug] L59** In vue-router 4 `router.push()` rejects with a `NavigationFailure` for *aborted* or *cancelled* navigations (e.g. a navigation guard returning `false`/throwing, or a newer navigation superseding this one). Reacting to those rejections with `window.location.href` bypasses the guard's decision and forces a hard reload for what is benign control flow. Only fall back to native navigation on real failures (e.g. dynamic-import/chunk load errors); navigation failures should just be logged/ignored. Also, the optional chaining `?.` is unnecessary because `push()` always returns a Promise, and the returned Promise is not awaited.

### `frontend/src/composables/useUploadHeaders.ts`

- **[bug] L14** `ensureCsrf` does not return the promise from `getCsrfToken()`, so every `await ensureCsrf()` call site is a no-op that resolves before the token is actually fetched (e.g. ContractManage.vue:391 and policies/Edit.vue:368 call it inside `before-upload` to guarantee the header exists). The upload request can then be issued with an empty `X-CSRF-Token`, producing a 403 without any feedback. Return/await the promise (and handle failure) so callers can actually rely on it.

### `frontend/src/composables/useVersionCheck.ts`

- **[bug] L54** `localStorage.setItem` runs *before* the reload. If the reload is blocked/cancelled, or the browser re-serves the previously cached bundle, the mismatch is permanently lost: the next run compares equal versions and never reloads, leaving the user stuck on stale code with no way to detect it. Persist the new version only after a successful reload (e.g. via a `sessionStorage` flag consumed on the next boot), or reload first and store afterwards.

- **[bug] L61** `window.location.reload()` does not bypass the HTTP cache, contrary to the comment above it: the HTML entry (and the cached JS bundle referencing this code) can be served from cache again, the same mismatch will be detected, and the page will reload again — an unbounded refresh loop. Use a cache-busting navigation (e.g. `window.location.replace(urlWithNewQuery)`) and/or set a short-lived guard flag in `sessionStorage` so at most one automatic reload happens per detected version.

### `frontend/src/config/regionDictionary.ts`

- **[maintainability] L92** `_city` and `_county` are accepted but never used, and the comment claims the function "兼容旧版三参数调用" while the legacy parameters are actually discarded. Callers (e.g. `onRegionChange`) pass city/county expecting them to influence the result, so this is a misleading/dead API surface. If the implementation is a TODO, remove the unused parameters (and adapt call sites) or document explicitly that they are not yet supported.

### `frontend/src/directives/permission.ts`

- **[bug] L40** `mounted` irreversibly detaches the element with `el.parentNode.removeChild(el)`, while `updated` only toggles `style.display`. Consequences: (1) once removed, the element can never be restored when roles/permissions change at runtime (e.g. after re-login or store refresh) — `updated` has no node to operate on; (2) manual DOM removal of a node managed by Vue can desync the virtual DOM and lead to patch errors on later re-renders. Use the same enforcement mechanism in both hooks (e.g. toggle `style.display` and, for a real access barrier, also rely on the backend/auth guards).

- **[bug] L135** Silent permission bypass: only the literal `'view'` / `'edit'` values are handled, and there is no `else`. Any other (malformed, misspelled, or untyped) `level` falls through both branches, leaving the element fully visible/clickable with no warning — a fail-open default for an authorization helper. Fail closed and log in DEV, e.g. `else { el.style.display = 'none'; if (import.meta.env.DEV) logger.warn(...) }`. Note also that the file-level doc promises "无权限则隐藏/禁用元素" for `edit`, but the implementation only hides; either implement the disable behaviour or fix the comment.

### `frontend/src/directives/watermark.ts`

- **[bug] L56** Missing `unmounted` hook: the injected `.watermark-layer` node is never removed when the host component/element is destroyed. Because the node is appended directly into a Vue-managed element (outside Vue's vnode tree), it can survive teardown / be re-created on remount, leaking DOM nodes and potentially breaking Vue's anchor-based patching. Add an `unmounted` (and ideally `beforeUnmount`) hook that removes the layer.

### `frontend/src/layouts/DefaultLayoutSafe.vue`

- **[bug] L501** Lifecycle hook registered inside the `onMounted` callback. Vue requires lifecycle registration APIs to be called synchronously during setup; inside a mounted callback there is no active instance, so `onBeforeUnmount` is not associated with the component (dev warning) and the 60s interval is never cleared — it keeps polling `getUnreadCount` after the layout is destroyed (e.g. test runs, route-driven layout swaps). Declare the timer at setup scope and register the cleanup at top level, consistent with the `onUnmounted` used for `narrowMq` below.

- **[bug] L546** Custom `onLock` overrides `useAutoLock`'s default implementation, which is the only place that calls `markLockNow()` (see `frontend/src/utils/lockDigest.ts`). Since no lock timestamp is ever written here, `consumeLockDigest()` in `loadUnreadCount` always returns false and the T037 "欢迎回来" unread summary never fires. Call `markLockNow()` before redirecting (import it alongside `consumeLockDigest`). Also note the comment above says this triggers on an unread *increment*, while `consumeLockDigest` merely checks `unread > 0` — reconcile the comment or the util so the intent is accurate.

- **[security] L94** The funds sub-menu is gated only by the parent-level OR check (`funds-admin || funds-user`), so a user holding just `funds-user` still sees admin-only children (预算管理/合同管理/异常监控/资金周期/决算结算/经费报表). More importantly, the corresponding routes (`/funds/budget`, `/funds/contract`, `/funds/anomaly`, `/funds/transfer`, `/funds/report`, …) carry no `meta.menuKey`, so `router/guards.ts` performs no menu-permission check for them and the navigation actually succeeds. Add per-child `v-if="menuStore.canAccessMenu(<key>)"` here and/or map each admin child route to its menu key so the route guard denies direct access.

### `frontend/src/main.ts`

- **[bug] L41** Unguarded `localStorage` read at module scope during bootstrap. In restricted-storage scenarios (Safari private mode, cookies/storage disabled, iframe with blocked storage) `localStorage.getItem()` throws a `SecurityError`, which propagates out of the entry module and prevents the whole app from mounting (blank page) — exactly the opposite of the FOUC-avoidance intent. Additionally the stored value is never validated against `THEME_OPTIONS`, so a legacy/tampered value (e.g. `"blue"`) silently sets an invalid `data-theme` and the page renders with no theme tokens. Wrap the read in try/catch and validate the value.

- **[bug] L44** One-shot credential migration is invoked without any error guard. `AuthStorage.migrateFromLocalStorage()` touches both `sessionStorage` and `localStorage`; if either access throws (restricted storage, quota errors while writing the migrated token/user JSON), the exception aborts the entire entry module and the user sees a blank page with no diagnostic. Failures here should degrade gracefully — the app can still run and ask the user to log in again.

### `frontend/src/router/guards.ts`

- **[security] L27** Lock-screen flag is only enforced on whitelist pages, so it can be bypassed by direct navigation. `AuthStorage.getToken()`/`getUser()` fall back to the persisted "remember me" credentials kept by `lockSession()` (see authStorage.ts:67-73 / 85-102), meaning after an auto/manual lock a user can simply enter `/dashboard` (address bar, bookmark, browser back) and the guard never evaluates `auto_lock_active` for non-whitelist paths → the protected page loads without re-entering the password. Enforce the lock flag for every route once a token exists, not only for `/login`-style routes.

### `frontend/src/stores/dataReport.ts`

- **[bug] L61** `previewReport` / `receiveReport` / `rejectReport` / `downloadReport` / `submitReport` have no `try/catch`: a failed request rejects out of the store action as an unhandled rejection and never populates `error`, unlike the two `fetch*` actions which do set it. This breaks the project's async error-handling standard and forces every caller to re-implement the same error UX. Please wrap these actions (or extract a shared helper) so failures set `error` with a user-friendly message (and reset `loading` when used).

### `frontend/src/stores/funds.ts`

- **[bug] L57** `total` is the server-side pagination total (`unwrapList(res).total`), not a flag. Blindly doing `total.value--` (a) can drive the value negative, (b) is wrong when the deleted id is not on the currently loaded page / is filtered out, and (c) leaves the page truncated without loading a replacement row, so the list and the count diverge from the server. Only decrement when the record was actually present, or simply refetch the list.

### `frontend/src/stores/organization.ts`

- **[bug] L70** `deleteOrganization` never passes `confirm_password`, but the backend `DELETE /organizations/{org_id}` requires a valid current-user password (`backend/app/api/v1/organization.py`: `confirm_password: str = Query("")` + `verify_password(...)` → 400 "二次确认失败：密码不正确" for an empty value). As written this action can never succeed; `views/organization/List.vue` works around it by calling the URL directly with `confirm_password`, and `api/organization.ts#deleteOrganization` already supports the parameter. Add the optional parameter and forward it (also replaces the hardcoded URL string).

### `frontend/src/stores/policy.ts`

- **[bug] L26** The blanket `catch { /* silent */ }` swallows every failure. The request layer deliberately does NOT show global toasts for non-401 errors — it attaches `error.userMessage` and relies on the caller (or the global `unhandledrejection` fallback) to surface it. By catching and discarding here, the rejection is considered handled, so neither the page nor the fallback ever shows anything: the user sees a permanently empty/stale list with no explanation. Log it and rethrow (or surface `err.userMessage`) so callers can react. The same pattern in `fetchPolicy` (line ~46) has the identical problem.

- **[bug] L46** `createPolicy`/`updatePolicy`/`deletePolicy` have no try/catch, so a network or server failure produces an unhandled promise rejection wherever the caller forgets to wrap the call, and no user-facing feedback is ever generated by the store. Mirror the read actions (or explicitly document that error handling is delegated) and surface `err.userMessage`.

### `frontend/src/stores/user.ts`

- **[bug] L62** `fetchUser(id)` assigns the fetched record to `currentUser` no matter which id is requested. When an admin views/edits another user, the session profile (`currentUser`) is silently replaced, which corrupts identity-dependent flows (`changePassword` uses `currentUser.value.id`, permission checks, avatar upload). Only update `currentUser` when the id matches the logged-in user — otherwise cache the record in the list/local state.

### `frontend/src/styles/accessibility.css`

- **[bug] L69** Wrong Element Plus token names: the library exposes `--el-text-color-primary` / `--el-text-color-regular` (the project itself consumes those, e.g. `styles/index.scss:146-149` and many components). `--el-color-text-*` does not exist, so these two high-contrast declarations are silently dropped and the black-text goal of this theme is never applied (text keeps being resolved from `--color-text-*`). Also note `--el-bg-color` only affects Element Plus, while the app's own surfaces use `--color-bg-*`, so the high-contrast theme is likely incomplete.

### `frontend/src/styles/components/form-page.scss`

- **[bug] L78** Using a background/surface token as a text color (`color: var(--color-bg-card)` or `$text-white: var(--color-bg-card)`) causes dark-on-dark, unreadable text in dark/military themes. Occurs in form-page.scss (c-9, header), list-page.scss (c-15 table header, c-20 pager label), index.scss (c-45 table header, which also has a self-referential fallback on border-bottom), and tokens-vars.scss (c-66 bridges `$text-white` to `--color-bg-card`). Use an inverse/foreground text token (e.g. `--color-text-inverse`) instead.

### `frontend/src/styles/components/prompt.scss`

- **[bug] L162** 这里的设计意图（通知标题/正文使用各语义色 dark 档以保证浅底高对比）实际不生效：上方第 68~106 行类型块中的 `.el-notification--success .el-notification__title`（及 `__content`/`__closeBtn`）选择器权重为 (0,2,0)，而本处 `.el-notification .el-notification__title` 权重同为 (0,2,0) 且文件位置更靠后，层叠后必然覆盖，`color: inherit` 永远拿不到语义色；同理 `.el-notification__content`/`__closeBtn` 也被覆盖。另外类型块中的 `.el-message--success .el-notification__title` 属于永不可能匹配的死规则。建议将类型色规则下沉到 `.el-notification` 块之后（或提高其选择器权重），并删除 `.el-message--* ` 与 `.el-notification__*` 的交叉组合。

### `frontend/src/styles/dashboard-theme.scss`

- **[bug] L604** Token roles are inverted in dark mode: border tokens (`--color-border-dark`, `--color-border-lighter`) are used as text colors (and `--color-text-primary` as a background), producing near-invisible text (e.g. near-white background with mid-grey text, or dark border color on dark card). Use semantic text tokens (`--color-text-primary`) for text and surface tokens for backgrounds.

### `frontend/src/styles/print.scss`

- **[bug] L83** Cells/headers set `background` (including the `#f0f0f0` header shading) and colors, but the file never enables print color adjustment. Most browsers default to `print-color-adjust: economy`, so header shading and card backgrounds are stripped while text colors are forced to black — the table ends up washed out and hard to read. Enable exact color rendering on the printed roots.

- **[bug] L58** `position: fixed` inside `@media print` is inconsistently supported: Chrome/Firefox may render the footer once at the bottom of the first page or repeat it on every page, and in both cases it overlays the page content because no compensating bottom space is reserved. Long reports will have their last table rows covered by the footer. Reserve space (e.g. `padding-bottom` on `body`) and keep the footer from overlapping content, or move the footer into the `@page` margin boxes.

### `frontend/src/styles/responsive.scss`

- **[bug] L43** The `max-width()` mixin mishandles boundary cases: a named `xs` breakpoint emits `max-width: -1px` (never matches, silently dropping styles), and raw pixel values are not decremented, so `max-width(768px)` and `min-width(768px)` both match at 768px. Normalize bounds and always subtract 1px from numeric max; guard against non-positive values.

### `frontend/src/styles/theme-elevated.scss`

- **[bug] L371** The reduced-motion override misses the selector that actually carries the route animation. `#main-content` (DefaultLayoutSafe.vue `<el-main id="main-content">`) has a single direct child — the ErrorBoundary root, which is deliberately excluded by `:not(.error-boundary-root)` in the animation rule — so the only animated elements are `#main-content > .error-boundary-root > *`. `#main-content > *` therefore matches nothing that is animated and `animation: none` here is a no-op: users with `prefers-reduced-motion: reduce` still get the 0.28s route fade on every navigation, contradicting the "全部关闭（无障碍合规）" claim. Add the error-boundary children selector (or drop the `:not()` in the rule above and animate the boundary root instead).

### `frontend/src/types/analytics.ts`

- **[bug] L26** Flag type inconsistency: `SupportedVillage` declares the region/key flags (isThreeRegions/isBorderArea/isEthnicArea/isRevolutionaryArea/isKeyCounty/isProvincialDemo/isHundredVillageDemo) as `boolean`, while `SupportedVillageCreate` (and therefore `SupportedVillageUpdate`) declares the exact same backend fields as `number | undefined`. The same field is now typed two incompatible ways, so a payload built from a `SupportedVillage` object cannot be fed back into an update call without casts, and it is easy to accidentally serialize `true/false` where the backend expects `0/1`. Pick one representation (or derive one from the other) and use it consistently across the entity and the create/update DTOs.

### `frontend/src/utils/approvalTimeline.ts`

- **[bug] L22** Sorting by `String(...).localeCompare` assumes a single, uniformly zero-padded timestamp format. Mixed inputs (ISO `2026-09-17T10:00:00Z` from `created_at` vs `2026-09-17 10:00:00` vs epoch strings such as `1758000000` vs ms `1758000000000`) will not be ordered chronologically, and records with an empty `time` silently sink to the end; `localeCompare` is also locale-dependent and much slower than a numeric comparison. Parse the values to a numeric timestamp (handling seconds/ms and invalid values) before comparing. Additionally, `history` and `statusLogs` may describe the same event (same operator/time/action) — concatenating them renders duplicate timeline nodes; consider de-duplicating on a composite key.

### `frontend/src/utils/authStorage.ts`

- **[bug] L68** `getToken()`, `getUser()` and `getRefreshToken()` each resolve their value from a *different* precedence chain, so the triple can be assembled from mixed sources. For example a user who opened a new session (sessionStorage token cleared, or `clearSession()` called for lock screen) but left `auth_persist_*` in localStorage will get a token from the persisted set combined with a session user, or a persisted user with a legacy local token. `getAuthData()`/`isAuthenticated()` therefore report a valid identity built from credentials that don't belong to the same login, and `clear()`/`clearSession()` can leave a token alive while its user is gone (or vice versa). Resolve the whole credential set from one coherent source (pick session first; only fall back to the persisted triple) instead of mixing per-field fallbacks.

### `frontend/src/utils/clipboard.ts`

- **[bug] L36** `document.execCommand('copy')` returns `false` when the copy actually fails, but its return value is discarded — the function then reports success and shows the `${label}已复制到剪贴板` toast even though nothing was copied. Additionally, `textArea.remove()` is not in a `finally` block, so if `focus()/select()/execCommand()` throws (or the success branch is taken in a way that skips it), the temporary `<textarea>` is left in the DOM. Suggestion: check the boolean result and throw/return false on failure, and remove the textarea in a `finally`.

### `frontend/src/utils/desensitize.ts`

- **[security] L36** The mask functions fail open: when the regex does not match (e.g. phone with `+86` or separators, ID ending in `X`, bank card with spaces/dashes), the original unmasked value is returned. Normalize the input, anchor the patterns, and fall back to a fixed mask instead of returning sensitive data.

- **[bug] L86** Bug: for an exactly 4-character id, `slice(0, 2)` and `slice(-2)` cover the whole string, producing `"12****34"` — every character of the credential is still visible, so no desensitization happens. Require a minimum length that guarantees hidden middle characters (or return a fixed mask).

### `frontend/src/utils/echarts-theme.ts`

- **[bug] L358** The dark variant only overrides `textStyle`/`title`/`categoryAxis`/`valueAxis`/`legend`/`tooltip`, but the shallow spread keeps the light-tuned values for every other key. Concretely, on a dark background you will get: - `logAxis.splitLine.lineStyle.color: '#f1f5f9'` and `timeAxis.axisLine.lineStyle.color: '#e2e8f0'` — near-white grid/axis lines that glare on dark; - `pie.itemStyle.borderColor: '#ffffff'` — bright white separators around slices; - `dataZoom.dataBackground` (`#cbd5e1` / `rgba(203,213,225,.15)`) and `toolbox.iconStyle.borderColor: '#94a3b8'` — light-theme chrome left untouched. Please explicitly override `logAxis`, `timeAxis`, `pie`, `dataZoom` (and `toolbox` if used) in the dark theme so the two variants stay consistent.

### `frontend/src/utils/echarts.ts`

- **[bug] L3** The chart/component registration list is incomplete for actual usage: `LinesChart` and `EffectScatterChart` (OfflineMap.vue) and `VisualMapComponent` and `MarkLineComponent` (OfflineMap.vue, gantt.ts) are not registered, so ECharts silently drops those series/features at runtime. Add them to both the imports and `echarts.use([...])`.

### `frontend/src/utils/errorHandler.ts`

- **[bug] L221** Several strategy fields are declared but never used: `showMessage` string form is ignored (only truthiness is checked), `severity` is ignored (notification type hardcoded to 'error', message uses warning), and `shouldRedirect`/`redirectPath` are never acted upon. Either implement these behaviors or remove the dead configuration.

### `frontend/src/utils/exportUtil.ts`

- **[security] L10** CSV formula injection: values beginning with `=`, `+`, `-`, `@` (and the tab/CR variants) are written verbatim. Because the exported field is still valid CSV, Excel/Sheets will evaluate attacker-controlled text as a formula (e.g. `=HYPERLINK(...)`, `=cmd|...`), which is a data-exfiltration / RCE vector. Neutralize leading formula characters by prefixing with a single quote.

### `frontend/src/utils/gantt.ts`

- **[bug] L15** Replacing every `-` with `/` corrupts ISO date-time strings that carry a time component or a numeric timezone offset: `'2026-09-17T10:00:00Z'` becomes `'2026/09/17T10:00:00Z'` (the `Z` is no longer honored, silently shifting the instant) and `'2026-09-17T10:00:00-05:00'` becomes `'2026/09/17T10:00:00/05:00'` which parses to `NaN`. These wrong/NaN values then flow into `hasRange` and the bar offsets/lengths. Only normalize strings that are strictly date-only (`YYYY-MM-DD`), which is the case the `/` substitution is meant to fix (Safari/iOS).

### `frontend/src/utils/index.ts`

- **[bug] L16** Several format helpers lack the defensive guards their siblings have: `formatDateTime` throws on null/undefined and returns the raw string for invalid dates, and `formatCurrency` throws on null/undefined and renders 'NaN' for non-finite numbers. Add consistent null/invalid handling to both.

### `frontend/src/utils/roleAccess.ts`

- **[bug] L58** Role normalization is applied inconsistently: `isAdminUser` compares the raw stored role, `hasAllowedRole` compares whitelist entries verbatim, `hasMinRole` uses an un-normalized `minRole` with an asymmetric fallback, and `getRoleFromLocalStorage` returns the raw role with a default that disagrees with `normalizeRole`. Normalize all roles/whitelists/minRole consistently and align defaults so permission decisions are uniform.

### `frontend/src/utils/treeNormalizer.ts`

- **[bug] L49** Prefixing numeric ids with `_` silently changes the node identity: for a backend id of `0` the normalized value becomes `_0`. Any consumer that sends the normalized `node.id` back to the API (detail / update / delete / permission assignment) will send a non-existent id. Consider keeping the original value (e.g. expose an additional `rawId` field) for API calls and only applying the `_` prefix at the DOM/id-rendering layer — or fix the conversion in the API mapping layer as the file header itself recommends.
