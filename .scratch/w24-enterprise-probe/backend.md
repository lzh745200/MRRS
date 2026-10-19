# W24 企业级深度探测 · 后端切片报告（backend-probe / task-1）

- 基线：v1.15.4，git main HEAD 5a182cd（工作区改动见文末清单，**未 commit**）
- 环境：Windows / Python 3.11（`backend\.venv\Scripts\python.exe`）/ 真实临时 SQLite（`tempfile.mkdtemp` + `BUMOFU_BACKEND_DIR_OVERRIDE`）
- 隔离声明：所有探测脚本的数据目录、日志、上传、备份均落在系统临时目录；**未触碰 `backend/data/rural_revitalization.db`**；全程未执行任何 git 写操作。
- 探测入口：`.scratch/w24-enterprise-probe/`（`_bootstrap.py` 隔离引导、`_seed.py` 四角色种子、p1~p7 探测脚本与 JSON 产物）。

## 一、结论摘要

| 级别 | 数量 | 状态 |
|---|---|---|
| P0 数据泄漏/权限绕过 | 2 | **本次已修 + 3 条回归用例** |
| P1 缓存污染/数据可见性/角色语义 | 2 已修 + 1 待产品决策 | 已修 2（含回归用例），另 1 报告 |
| P2 健壮性/一致性/可用性 | 5 | 2 已修（分页钳制），3 报告 |

启动链路 831 路由 / 700 path 静态注册、OpenAPI 830 操作生成、无重复 path+method、全量 GET 异常参数扫描 **0 个未捕获 500**、错误响应无堆栈/SQL/绝对路径泄漏。

---

## 二、P0（本次已修复，附回归测试）

### P0-1 帮扶村列表缓存键跨角色碰撞 → 普通用户/访客读到管理员整组织数据

- **现象**：同组织内 admin 先请求列表、user/viewer 随后请求，后者看到管理员的整组织记录（实测 user 看到 admin 创建的村），违反 `core.data_permission.apply_scope_filter` 对 user/viewer 的「仅本人」数据域；反向也错（admin 命中 user 的受限结果，列表缺数据）。
- **证据**：`.scratch/w24-enterprise-probe/p5_cache.py`（修复前）：
  - `village_admin_first: [普通用户村, 部门管理村]` → `village_user_after_admin_LEAK: [普通用户村, 部门管理村]`（应为仅 `普通用户村`）
  - `village_user_first: [普通用户村]` → `village_admin_after_user: [普通用户村]`（admin 结果被短路）
- **根因**：`backend/app/api/v1/supported_village.py` 列表缓存键 `villages:list:{organization_id}:...` 只含组织，不含数据权限主体；同一组织内 admin（本组织及子树）与 user/viewer（仅本人）共用键。
- **修复**：键改为 `villages:list:{current_user.id}:...`（对齐 `policy.py` 既有 `policies:list:{user_id}` 正确做法）。**文件:行** `backend/app/api/v1/supported_village.py:577`。
- **验证**：修复后同一脚本 `village_user_after_admin_LEAK: [普通用户村]`、admin 侧不再被短路；回归用例 `tests/unit/test_w24_probe_regressions.py::test_village_list_cache_key_isolated_between_admin_and_user` / `..._between_users_same_role`。

### P0-2 学校列表缓存键同款跨角色碰撞

- **现象/证据**：`backend/app/api/v1/school.py` 的 `schools:list:{organization_id}:...` 同款。`get_org_scope` 下部门级 admin 是 `is_admin=True`（全量），普通用户是「本组织及子树/仅本人」，同组织跨角色命中同一键（p5_cache.py `school_*` 组，键碰撞实测 admin 结果被 user 命中）。
- **修复**：键改为 `schools:list:{current_user.id}:...`。**文件:行** `backend/app/api/v1/school.py:754`。
- **验证**：回归用例 `test_school_list_cache_key_isolated_between_admin_and_user`。

---

## 三、P1（本次已修复 / 待决策）

### P1-1【已修】组织列表全局缓存「读门禁、写放行」→ 普通用户可污染超管的组织列表

- **现象**：普通用户 `GET /api/v1/organizations` 后，超管 5 分钟内看到**空组织列表**（实测 `orgs_sa_after_usr1_cache: []`，清缓存后恢复 2 条）。
- **根因**：`backend/app/api/v1/organization.py` 第 218 行读缓存已按 `_global_view` 门禁（注释明确"否则普通用户的受限结果会被写入全局缓存造成跨用户泄漏"），但第 263 行**写缓存未门禁**。
- **修复**：写条件追加 `_global_view`。**文件:行** `backend/app/api/v1/organization.py:267`。
- **验证**：修复后超管列表恢复 2 条组织；回归用例 `test_org_list_non_global_user_does_not_poison_shared_cache`（普通用户 get/set 均不触达共享缓存）与 `test_org_list_global_admin_can_read_and_write_shared_cache`。

### P1-2【已修】数据包列表对未绑定组织的超管恒空 → 刚导出的数据包不可见

- **现象**：默认安装的超管（出厂 admin `organization_id=None`）`POST /data-packages/export` 成功，但 `GET /data-packages` 恒返回 `total=0`（「数据包版本/增量更新」页看不到已导出包）。
- **证据**：`p7a_business.py` 修复前 `data_package_list: [200, {"total":0,"items":[]}]`，而 `data_package_export: [200, package_id=1 ...]`；修复后 `data_package_list: {"total":1,"items":[{"id":1,...}]}`。
- **根因**：导出链用 `get_org_with_fallback` 回退首个活跃组织，列表链直接 `return total=0` —— 同一 API 两条口径。
- **修复**：仅对 `is_superuser` 且无组织的用户做同口径回退（普通用户/部门 admin 不回退，杜绝跨组织可见面）。**文件:行** `backend/app/api/v1/data/data/data_packages.py:253-265`（import 见 29-34）。
- **验证**：回归用例 `test_data_package_list_orgless_superuser_falls_back_to_first_org`、`test_data_package_list_orgless_normal_user_stays_empty`；`tests/unit/test_data_packages_api.py` + `test_data_packages.py` 全绿。

### P1-3【报告·未改】viewer 角色在多个业务模块可执行写操作，与"只读"定位不一致

- **现象**：真实登录 viewer 后 `POST /api/v1/supported-villages` → 200 创建成功；`POST /api/v1/policies` → 200。帮助文案（`system/help.py`）与角色选项（`auth/users.py` 中 `viewer` 描述）均声明"只能查看，不能新增/编辑/删除"。
- **证据**：`p4_cross_org.py`：`viewer_create_village: [200, {"data":{"id":3...}}]`、`viewer_create_policy: [200]`；写路由全量扫描（383 条写路由 × viewer）仅 funds 系列显式 403（`deps.require_funds_operator_role`）。
- **根因**：viewer 只读没有全局收敛点，仅个别模块（funds/fund_lifecycle/offline_map）自行判权。
- **未修原因**：全局门禁会影响通知偏好/待办/个人资料等合理写操作，需产品给出白名单；直接改会破坏既有行为并波及大量测试。**建议**：在 `core/security.py` 增加 viewer 写操作白名单门禁（或按模块接入），由产品确认范围后实施。

---

## 四、P2（建议项）

### P2-1【已修】GET /users 分页无上限（SQLite `LIMIT -1` = 不限量）
- `backend/app/api/v1/auth/users.py:374-376` 用裸 int 计算 offset/limit；`page_size=-1` 一次拉全表、超大 page_size 无上限（DoS / 用户 PII 批量暴露面，管理员接口）。已改用仓库唯一钳制入口 `clamp_offset_limit`（与 feedback/rbac/data_sync 同口径）。回归：`test_users_list_clamps_negative_page_size` / `_oversized_page_size` / `_negative_page`。

### P2-2【已修】GET /machine-code/organization/list 分页无上限
- `backend/app/api/v1/machine_code.py:774` 同款（`skip/limit` 直传服务层），已钳制。回归：`test_machine_code_org_list_clamps_*`。

### P2-3【报告】软删除后唯一编码无法复用（School）
- `POST /schools` 用 `code` 唯一；删除是软删（`is_active=False`，DB 层 `code unique=True` 不含 is_active），删除后再用同一 code 创建 → 409「学校编码已存在」（`p7b_consistency.py`: `school_dup_after_soft_delete: [409]`）。原生 `pytest` 场景下不影响既有功能，但"删错重建"需先彻底删除回收站记录。建议：软删时释放/改写 code（如 `code = f"{code}#deleted#{id}"`）或唯一校验只查活跃记录 + 迁移唯一索引；属数据模型变更，未在本次最小修复内实施。

### P2-4【报告】两类列表的数据域口径不一致
- 帮扶村列表（`apply_scope_filter`）对 user/viewer = 严格「仅本人」（`created_by=me`）；学校列表（`get_org_scope` + `OrgScopeFilter`）对 user/viewer = 「本组织及子树」。同类业务数据同一角色可见范围不同，`p4_cross_org.py` 实测：user 在帮扶村列表只看到本人 1 条，但在学校列表看到本组织全部。建议统一到 `core/data_permission` 口径（本次未改，避免改变既有产品可见范围）。

### P2-5【报告】备份列表向任意已登录用户暴露绝对文件路径
- `GET /api/v1/system/backup` 设计为"任意已登录用户可读"（Electron 保留策略需要）；响应每项含 `file_path` 绝对路径（`p7a_business.py: backup_create` 可见）。单机离线场景风险低，建议对非管理员脱敏 `file_path`。

### P2-6【观察·非代码缺陷】`/health` 版本指纹来自 gitignore 的构建产物
- 工作区存在 `backend/app/core/_build_info.json`（未被 git 跟踪，内容 `version=1.15.1, git_hash=7f178ab`），`/health` 因此回报 1.15.1（当前源码版本 1.15.4）。属构建期生成物陈旧，非代码缺陷；发版前须由 `scripts/generate_build_info.py` 重新生成（该文件不在我的写入范围，未改动）。

### P2-7【观察】创建接口无幂等键；并发更新 last-write-wins
- 相同 payload 连续 POST 帮扶村 → 2 条记录（`repeat_create: [200,200, rows=2]`）；两个并发 PUT 同一记录均 200（无乐观锁）。符合当前 REST 设计，但客户端重试可能产生重复数据，建议前端提交防抖/后端幂等键（未改）。

---

## 五、探测覆盖与"未发现问题"的证据（避免误判为未测）

| 探测面 | 方法与证据 | 结果 |
|---|---|---|
| 真实启动链路 | `p1_startup.py`：TestClient 触发 lifespan（真实临时 SQLite） | 启动 4.1s；831 路由 / 700 path；**0 重复 path+method**；OpenAPI 200（830 操作）；`/health` 200；DB 122 表，alembic `w22_household_media_consumption_001` 达 head；默认 admin 种子成功 |
| 强制改密拦截 | `p2_auth.py`：出厂口令登录 → must_change=true；改密前业务端点 403、白名单端点 200 | 拦截正确；改密后旧 token 立即 401（token_version 递增）、旧密码 401、weak/错旧密码 400 envelope |
| 令牌生命周期 | 同上 | refresh 轮换 200、旧 refresh 重放 401、logout 后 token 401 |
| 静态鉴权面 | `p3a_static_auth.py`（分析全部 831 路由 dependant 树） | 仅 11 条无 get_current_user 写路由，全部为设计公开端点（login/register/refresh/logout/feedback/machine-code verify/reset/recover/system-init/shutdown）；另 45 条无鉴权读路由均为 health/静态模板/地图瓦片/i18n 等 |
| RBAC 写接口实测 | `p3b_rbac_sweep.py`：viewer/user 各扫 383 条写路由 | 除公开端点外**全部 401/403**，未发现鉴权绕过 |
| 跨组织隔离 | `p4_cross_org.py`：root/child 两组织 + 四角色 | 详情跨组织 403（`无权访问该帮扶村`）；admin 子树可见（设计）；include_deleted 非管理员静默降级；导出服务按 `apply_scope_filter` 过滤（跨组织 village_ids 导出 0 行） |
| 软删除 | 同上 | 默认过滤软删；admin `include_deleted=true` 可见；重复 DELETE 409；恢复 200；user/viewer 详情访问软删记录 403 |
| 异常/泄漏扫描 | `p6_errors.py`：全部 GET 路由 + 非法路径参数/超大 page_size | **0 个未捕获 500**；错误体无 Traceback / SQL / site-packages / 绝对路径 |
| 导出矩阵 | `p7a_business.py` | xlsx/csv/pdf 全部 200 且 Content-Type 正确：帮扶村 xlsx/csv、学校 xlsx、项目、一户一档、消费帮扶、政策 excel/pdf、组织、通行码、`/export/*` 系列；`/system/audit/logs/export` 默认 JSON（设计如此，format=excel/csv 可下载）；`/funds/export` 422 因该路径无端点（前端实际用 `/export/funds`，200，非缺陷） |
| 数据包 | `p7a` | preview/export 200（记录数 3+1），修复后 list 可见（P1-2） |
| 备份 | `p7a` | create 200（68KB zip）→ list 200 → verify 200（hash/`database_verified=true`）→ delete 200；恢复未执行真实覆盖（遵循任务要求，仅验证链路不触碰生产库） |
| 审计/日志落库 | `p7a` + SQL 直查 | `audit_logs` 登录/变更事件落库；`login_attempts` 5 条；`work_logs` 12 条（SQLAlchemy 事件审计覆盖 School 等模型）；`data_packages` 1 条 |
| 幂等 | `p7b_consistency.py` | 一户一档 rollup 两次均 200，`created:true→false`，`village_population` 仅 1 行（幂等成立） |
| 唯一约束/并发 | `p7b` | 学校编码重复 409；并发插同一编码 → 一个 200 一个 409（无 500）；并发更新同记录均 200（last-write-wins，见 P2-7） |
| 输入边界 | `p7b` | 超长村名 422、负数收入 422、非法日期 422、非法手机号 422、不存在的村 404、3000 字 keyword 200；无 500 |
| 事务一致性 | `p7b` 故障注入 | 审批任务创建失败被 `submit_entity_change_approval` 内部捕获（该函数自身吞异常返回 None），**不可达"半写+500"**；仅当强制 patch 该函数本体才会 500（非真实路径），故不列为缺陷 |

---

## 六、本次代码改动清单（未 commit；均在任务 write scope 内）

```
backend/app/api/v1/supported_village.py   P0-1 缓存键按用户隔离      (577)
backend/app/api/v1/school.py              P0-2 缓存键按用户隔离      (754)
backend/app/api/v1/organization.py        P1-1 写缓存 _global_view 门禁 (267)
backend/app/api/v1/auth/users.py          P2-1 分页钳制            (25, 374-376)
backend/app/api/v1/machine_code.py        P2-2 分页钳制            (774)
backend/app/api/v1/data/data/data_packages.py P1-2 未绑定组织超管列表回退 (29-34, 253-265)
backend/tests/unit/test_w24_probe_regressions.py  新增 12 条回归用例
```

### 定向验证（未跑全量；数据目录由 conftest/自建脚本隔离到系统临时目录）

```text
# 新增回归 + 相关既有用例
pytest tests/unit/test_w24_probe_regressions.py                              -> 12 passed
pytest tests/unit/test_supported_village_cov2.py test_school_cov.py \
       test_coverage_closing_r28.py test_branch_gaps_group_b.py \
       test_users_org_scope_r28.py test_v1129_gap_users_super_admin.py \
       test_coverage_gaps_final.py                                          -> 244 passed
pytest tests/unit/test_machine_code_api.py test_machine_code_cov.py \
       test_cov_final_machine_code.py test_machine_code_round2.py \
       test_organization_api.py test_cov_final_organization.py \
       test_organization_enum_validation_r24.py \
       tests/integration/test_users_integration.py                          -> 169 passed
pytest tests/unit/test_data_packages_api.py tests/unit/test_data_packages.py\
       tests/unit/test_w24_probe_regressions.py                             -> 104 passed
pytest tests/unit/test_feedback_api.py tests/unit/test_core_cache_cov.py \
       tests/unit/test_w24_probe_regressions.py                             -> 85 passed
# flake8（改动文件，--max-line-length=120 --max-complexity=16）        -> 0 违规
```

### 端到端复验（真实 TestClient + 真实临时 SQLite + 真实 JWT 登录）

- `p5_cache.py`：修复前 user 命中 admin 缓存看到整组织 2 条 / 修复后仅本人 1 条；修复前普通用户可把超管组织列表污染成空 / 修复后超管始终 2 条。
- `p7a_business.py`：修复前 data package list total=0 / 修复后 total=1（导出物可见）。

---

## 七、遗留风险与建议

1. **P1-3 viewer 只读语义**：需产品确认写操作白名单后统一收敛，否则"只读角色"在帮扶村/政策等模块可写数据。
2. **P2-3 软删唯一编码**：删除后不可复用编码，需数据模型/唯一索引方案评审。
3. **P2-4 数据域口径分叉**：建议后续把列表/详情/导出全部收敛到 `core.data_permission` 的严格口径（村庄/学校先统一）。
4. 备份列表 `file_path` 脱敏、创建接口幂等键属增强项。
5. 本次只做定向测试；全量 100% 覆盖率门禁由 Lead 在干净工作区统一跑（我未跑全量、未提交、未改门禁/阈值/既有测试）。
