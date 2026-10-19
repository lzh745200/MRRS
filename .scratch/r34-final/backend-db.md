# R34 最终复检 · 后端 + 数据库切片报告（backend-probe）

- 基线：v1.15.12 / HEAD 2ad1f47；本切片**未 commit**，改动仅 8 个 app 文件（无共享文件/版本/CI 变更）
- 环境：Windows + backend\.venv\Python 3.11；探测库一律为 `backend/data/rural_revitalization.db` 的**副本**（.scratch/r34-final/dbtmp/），生产库只读打开
- 探测脚本：复用 `.scratch/w24-enterprise-probe/p1~p7`，新增 `p8_r33_grants.py`；DB 审计脚本在 `.scratch/r34-final/`

## 一、结论摘要

| 级别 | 事项 | 状态 |
|---|---|---|
| **P1（发布阻塞·升级路径）** | 旧库升级后 `effectiveness_evaluations.village_id` 外键仍指向已删除的 legacy 表 `villages` → 成效评估**写入直接 500**（OperationalError: no such table: main.villages）；`PRAGMA foreign_key_check` 恒报 1 条违规 | 证据已固定，**需新增 Alembic 迁移重建表**（alembic 不在本切片写入范围，未改） |
| **P1（升级 vs 全新库 schema 漂移）** | 升级库相对「模型元数据/全新安装库」缺 9 个模型声明 FK、缺 21 个模型声明索引、多 15 个脱离模型的索引、多 6 张无模型 legacy 表 | 证据已固定（含逐项清单），建议同一迁移批次收口 |
| **P2（工具陈旧）** | `backend/scripts/validate_indexes.py` 期望 24 个已被 `index_dedup_001` 迁移**故意删除**的旧索引（还检查已删表 `villages`/`approvals`）→ 恒报"验证失败"；`check_foreign_keys.py` 发现违规仍 exit 0（静默通过） | 报告（scripts/ 不在后端 app 写入范围） |
| **P2（发布卫生）** | 真实开发库 `backend/data/rural_revitalization.db` 含开发测试数据（6 村/6 项目/12 经费/138 work_logs/215 audit_logs）且 org 归属全 NULL；工作区 `backend/` 下 138 个测试残留目录 664.7MB | 均不在 git（gitignored），**不会随安装包发布**（Electron 无预置库分支、resources/database 不存在）；建议清理机器现场后再打包 |
| **已修（冗余清理）** | 删除 13 处零引用常量 + 1 条指向已删表的死索引配置 | 已完成，定向测试 322 passed，flake8 0 违规 |
| **复检通过** | 启动链路、p1~p7 全套探测、R33 签名/篡改/重放/降级/跨组织/事务/菜单/守卫/未映射路由 | 全部符合预期 |

---

## 二、R33 单位授权专项（新增 p8 探测，真实 TestClient + 真实临时 SQLite）

### 安全属性矩阵（全部符合设计）

| 场景 | 结果 |
|---|---|
| 签名包正常导入 | 200，版本 1→2，写审计 work_logs「导入单位授权包 vN」 |
| 篡改 grants/version 后签名失效 | 400「签名校验失败」，库内版本/矩阵不变 |
| 使用其他私钥签名 | 400 同上 |
| 同版本重放 | 400「拒绝降级导入：包版本 2 不大于本机当前版本 2」 |
| 低版本降级导入（v1 对 v2） | 400 同上 |
| 未签名包（allow_unsigned=false） | 400「授权包未签名…」；显式开启后 200（**部署警示：下级机开启 allow_unsigned=true 时，本地 admin 可自签任意矩阵自扩权** → 生产必须保持 false） |
| org_code 与本机不一致 / 本机无该单位 | 400 两条明确原因 |
| 非法级别 / 非法格式 / 缺字段 / version=bool / 非 JSON / 空文件 / >1MB | 全部 400，无 500 |
| 拒绝后事务一致性 | 版本、矩阵、签名、应用时间均保持上一成功状态 |
| 权限边界 | user 导入 403「仅管理员」；viewer 被 viewer 只读中间件 403；下级 admin 导出/设置父组织或兄弟组织 403（`assert_org_reachable`） |
| 菜单裁剪 | 矩阵 {villages:view, policies:edit} 生效时 `/menus/accessible` flat_keys 仅含 dashboard+villages+policies（含工作台兜底） |
| 写守卫 enforce | view 模块写→403「无该模块的录入权限」；edit 模块写→200；无授权单位回落 legacy→200；超管豁免→200；`/feedback` 豁免路径→200 |
| 写守卫 shadow | 越权写放行（仅记日志）→200；off 模式零行为变化 |
| 未映射写路由 | `unmapped_write_routes(app.routes)` = **0**（enforce 上线前置门禁达标） |
| 合并语义（直接服务单测） | 深者优先 ✓、父级继承 ✓、`inherit_from_parent=false` 断链 ✓、超管 inactive ✓、未知单位 inactive ✓、版本号变更后缓存失效 ✓ |
| 并发导入（v+1 与 v+2 同时） | 两个 200，最终版本 = v+2，无 500/无脏数据；**观察**：读-比较-写非原子（grant_package_service.py:186-200），极端交错下低版本可能后提交覆盖高版本，建议后续用 `UPDATE ... WHERE grant_version < :new` 或行级 CAS 加固（P2） |

### 迁移链 / 模型注册表

- `alembic heads` → **单 head `r33_org_grants_001`**；53 个 revision 全部 `down_revision` 可解析、无断链/无环。
- `r33` 降级（→ w22）后 `org_grants` 表与 organizations 5 列均被移除，再次 upgrade head 成功（双向可逆）。
- R33 表/列落地正确：`org_grants` 7 列 + `uq_org_grant` 唯一约束；organizations 新增 grant_version/grant_signature/grant_applied_at/grant_source/inherit_from_parent；permission_packs.grants。
- `app.models.__all__` 128/128 懒加载成功，0 个失效条目（无陈旧模型注册项）。

---

## 三、数据库专项审计（对 `backend/data/rural_revitalization.db` 的副本执行）

### 3.1 迁移演练（w22 → r33）

| 检查 | 结果 |
|---|---|
| `alembic upgrade head` | EXIT=0，单步 `w22_… → r33_org_grants_001` |
| 完整性 | `PRAGMA integrity_check` = ok（升级前后均 ok） |
| 数据保全 | users 2/2、supported_villages 6/6、projects 6/6、funds 12/12、approval_tasks 6/6、work_logs 138/138、audit_logs 215/215、households 0/0 |
| 表集合 | 134 → 135（仅新增 org_grants）；无表丢失；legacy 表 villages/villagers/industries/sentiment_news 均不存在 |
| SQLite 版本 | 3.53.1（支持 DROP COLUMN，降级可用） |
| 软删一致性 | 24 张含 is_active 表，20 条 inactive 全部带 deleted_at，0 条不一致 |
| 组织树元数据 | 0 组织（该库 organizations 为空），无 path/level 异常 |
| R33 数据 | org_grants 违法级别 0、重复 (org,module) 0 |

### 3.2 【P1·发布阻塞】effectiveness_evaluations 外键指向已删除的 `villages` 表

```
# 在迁移到 head 的副本上
pragma foreign_key_check -> [{table: effectiveness_evaluations, rowid: 1, parent: villages, fkid: 1}]
pragma foreign_key_list(effectiveness_evaluations) -> village_id -> villages (ON DELETE CASCADE)   # 应为 supported_villages
INSERT INTO effectiveness_evaluations ... -> OperationalError: no such table: main.villages  # 功能 100% 不可用
# 对照：全新 create_all 库
foreign_key_list -> village_id -> supported_villages (CASCADE)  ✓
```

- 根因：早期 `006_add_effectiveness_sentiment_tables` 建表时 FK→`villages`；v1.14 删除 `villages` 表的迁移未重建/迁移该 FK，SQLite 不会因父表删除而清理其他表 FK 定义。模型层早已改为 `supported_villages`，但 `create_all`/`_migrate_missing_columns` 都不改既有表 FK。
- 影响：**所有从 v1.13 及更早版本升级上来的用户库**，成效评估新增/更新（POST /api/v1/effectiveness/evaluate）会在 ORM/SQLite 层抛错 → 500；启动自检/`PRAGMA foreign_key_check` 也会一直报违规。全新安装不受影响（这解释了 CI 与全新库全绿）。
- 建议修复（需 Lead 批准新增迁移，本切片未改 alembic）：新增迁移 `r34_effectiveness_fk_rebuild_001`：① 备份/清洗孤儿行（`village_id` 在 supported_villages 中不存在且旧 villages 表已删 → 无可映射，删除或置为 quarantine 表）；② `batch_alter_table("effectiveness_evaluations")` 重建表并以 `supported_villages.id` FK 替换；③ 迁移后断言 `foreign_key_check` 为空；④ 补一条迁移测试（现有 tests 对迁移链有覆盖）。

### 3.3 【P1】升级库 vs 模型元数据 schema 漂移（21 索引 + 9 FK 缺失）

`create_all` 只在**建新表**时创建索引/FK，已存在的表不会补；因此从旧库升级后与"全新安装"存在结构差异：

- **缺失模型声明索引 21 个**（按表）：households 2、household_members 2、household_risk_records 3、consumption_records 2、photo_archives 2、policy_favorites 3、permission_packs 1、policies 1、rural_works 2、rural_tasks 1、tea_plantations 1、cactus_fruit_plots 1（完整名称见 `.scratch/r34-final/schema_drift.json`）。这些多为 W22/R33 新表在迁移中手写 DDL 时漏建 ORM `__table_args__` 声明的索引 → 升级库查询性能劣化、与全新库行为不一致。
- **缺失模型声明外键 9 个**：cactus_fruit_plots.village_id、tea_plantations.village_id、rural_works.organization_id、consumption_records.organization_id、households/household_members/household_risk_records/photo_archives.organization_id、users.permission_pack_id（列由 `ADD COLUMN` 补出，SQLite 无法补 FK）→ 升级库无参照完整性保护。
- **脱离模型的索引 15 个**（旧命名/旧列，如 ix_consumption_records_village_id、ix_audit_timestamp、ix_audit_user_action、ix_supported_villages_county 等）→ 只增写放大，建议随迁移清理。
- **无模型 legacy 表 8 张**（DB-only）：comments、messages_extended、sentiment_keywords、sentiment_reports、workflow_definitions、workflow_instances 在 `backend/app` **零引用**；policies_fts* 为 policy_fts_service 在用（保留）；alembic_version/sqlite_stat1 为系统表。建议在迁移中 `DROP TABLE IF EXISTS` 前 6 张（升级库瘦身；全新库本就没有）。
- 建议：新增一个"schema 对齐"迁移批次：补建上述模型索引与可补 FK（SQLite 需 batch rebuild 的表较敏感，可先只补索引 + 对关键 organization_id 列重建），并删除 6 张死表；或至少在启动 `create_indexes()` 扩展为"模型索引同步"（可复用 `Base.metadata` 与 Inspector，幂等 `CREATE INDEX IF NOT EXISTS`）。

### 3.4 【P2】两个官方 DB 脚本已陈旧/静默通过

- `scripts/validate_indexes.py`：期望 24 个 `idx_*` 索引，其中 `villages.*`、`approvals.*` 对应的表已删除，其余已被 `alembic index_dedup_001_drop_orphan_indexes` **故意删除**（因为当时建在 legacy `village_id` 列上）。在迁移到 head 的库上运行 → EXIT=1「验证失败，请执行数据库迁移」，属**误报**；建议删除或重写为"模型索引一致性"检查。
- `scripts/check_foreign_keys.py`：能打印 `effectiveness_evaluations → villages` 违规，但进程仍 exit 0（无失败退出码），CI/打包脚本无法据此失败；建议有违规时 exit 2。
- `scripts/` 不在本切片写入范围，未修改，交给 Lead/ops-probe 决策。

### 3.5 全新安装库基线（create_all + create_indexes）

- 122 张表、487 个索引；`effectiveness_evaluations` FK 正确指向 supported_villages；households 4 个索引齐全；
- `EXTRA_INDEXES` 20 条中 19 条有效、1 条指向已删除 `villages` 表（**本次已删除该死配置**，见四）。

---

## 四、冗余/死代码清理（本次已删除）

扫描方法：AST 全仓标识符引用计数（app/tests/scripts/alembic 全语料）+ 文本复核（`grep -w` 全仓命中数），只删除「零引用（含测试零引用）+ 非公开 API + 私有/模块常量」。

| 文件 | 删除内容 | 引用证据 |
|---|---|---|
| app/models/household.py | HOUSEHOLD_TYPES / RISK_TYPES / RISK_LEVELS / RISK_RECORD_STATUSES | 全仓各仅 1 处（定义行） |
| app/models/org_module_policy.py | VALID_VISIBILITIES / VALID_EDIT_MODES | 各仅 1 处 |
| app/services/batch_import_optimizer.py | PANDAS_READ_KWARGS | 仅 1 处（pandas 分支未使用该 dict） |
| app/services/business_health_service.py | ENTRY_VILLAGE_LIST | 仅 1 处（其余 ENTRY_* 在用） |
| app/services/excel_template_service.py | A4_PAGE_SETUP | 仅 1 处 |
| app/services/fund_anomaly_detector.py | DUPLICATE_AMOUNT_TOLERANCE / DUPLICATE_DATE_DAYS | 各仅 1 处 |
| app/services/supported_village_export_service.py | DATA_FONT | 仅 1 处 |
| app/core/database_indexes.py | EXTRA_INDEXES 中 `("villages","ix_villages_organization_id",…)` | 表已在 v1.14 删除，条目在全新库/升级库均只产生 skipped；全仓唯一引用即该定义 |

合计 **13 个零引用常量/字典 + 1 条死索引配置**。

### 报告但**未删除**（有测试依赖或涉及产品语义，按"不确定不删"处理）

1. **仅测试引用的私有 helper（9 个）**：`projects._get_fund_health_fields`、`system/env._get_installed_packages`、`query_optimizer._ensure_counter`、`batch_import_optimizer._read_excel_fallback`、`encryption_service._reset_cipher_cache`、`subscription_dispatch_service._period_starts_after`、`database._set_sqlite_pragma`/`_on_connection_close`（后两者为事件注册，属活代码误报）等 —— 生产无调用方、由专属测试直接调用维持覆盖率；删除需同时删测试，建议下轮统一处理。
2. **仅测试引用的常量/别名**：`core.constants.DEFAULT_PAGE_SIZE`、`database_indexes.INDEX_DEFINITIONS`（= EXTRA_INDEXES 兼容别名）、`COMPOSITE_INDEXES = []`、`org_grant.LEVEL_RANK`、`fund_service.FUND_TYPES`。
3. **`PermissionPack.grants_dict` + DB 列 `permission_packs.grants`**：生产代码零消费（仅 test_org_grant_model_r33 断言），R33 中"权限包可见性→可写性"尚未接线；删除属性需同步删 6 条测试，且 DB 列需迁移，建议作为 R33 后续功能或单独清理项。
4. **`scripts/validate_indexes.py` 整体与 `check_foreign_keys.py` 退出码**（见 3.4，scripts 不在写入范围）。
5. 注释掉的代码块：严格模式（`^s*#s*(def|class|return|await|raise|elif|else:)`）全仓 app 扫描 **0 处**；TODO/FIXME/HACK 真实标记 **0 处**（9 处均为 `XXXX` 占位文案误报）。

---

## 五、深度复检回归（复用 p1~p7，本轮全部通过）

| 探测 | 结果 |
|---|---|
| p1 启动链路 | 启动 4~5s；**831 路由 / 703 path**（R33 后 +3）；OpenAPI 834 操作；0 重复 path+method；/health 200 且无绝对路径泄漏；DB 122 表、alembic 达 head |
| p2 认证链路 | 出厂密码登录 200 + must_change=true；改密前业务 403/白名单 200；改密后旧 token 401、旧密码 401、refresh 轮换 200/重放 401、登出后 401 |
| p3a 静态鉴权 | 仅 11 条无鉴权写路由，全部为设计公开端点（login/register/refresh/logout/feedback/machine-code verify/init/shutdown） |
| p3b RBAC 写路由扫描 | viewer 非 401/403 响应 5 条（全部白名单自服务）、user 8 条（含公开发布），无越权通达 |
| p4 跨组织/软删/导出 | 详情节点赞 403、admin 子树可见、include_deleted 非管理员静默降级、重复删除 409、恢复 200、导出按数据域过滤；viewer 写 403 |
| p5 缓存隔离 | 帮扶村/学校列表按用户隔离（无跨角色泄漏）、orgs:list 不再被普通用户污染 |
| p6 异常/泄漏 | 全 GET 路由非法参数扫描 **0 个未捕获 500**、错误体无堆栈/SQL/路径（R33 新增路由同样覆盖） |
| p7a 业务链路 | 导出矩阵 xlsx/csv/pdf 全部 200 且 Content-Type 正确；数据包 preview/export/list 正常；备份 create→verify(hash/database_verified)→delete 全链路；us1 备份列表为空（权限口径）；audit_logs/login_attempts/work_logs 均落库 |
| p7b 一致性 | 学校编码重复 409、并发插编码 200/409 无 500、重复软删 409、rollup 幂等（created true→false、population 单行）、输入边界 422/404 无 500、并发更新 200/200 |

---

## 六、改动清单（未 commit，仅 backend/app 8 文件；无版本/CI/共享文件改动）

```
 M backend/app/models/household.py                    -4 死常量
 M backend/app/models/org_module_policy.py            -2 死常量
 M backend/app/services/batch_import_optimizer.py      -6 行死常量
 M backend/app/services/business_health_service.py     -1 死常量
 M backend/app/services/excel_template_service.py      -6 行死常量
 M backend/app/services/fund_anomaly_detector.py       -2 死常量
 M backend/app/services/supported_village_export_service.py -1 死常量
 M backend/app/core/database_indexes.py                -1 死索引配置条目
```
新增报告/脚本：`.scratch/r34-final/{backend-db.md,scan_dead_code.py,db_audit.py,db_fk_audit.py,schema_drift_audit.py,fresh_db_check.py,chain_check.py}`、`.scratch/w24-enterprise-probe/p8_r33_grants.py` + 结果 JSON。

### 验证命令与结果

```text
flake8（8 个改动文件 --max-line-length=120 --max-complexity=16）            -> 0 违规
pytest 受影响模块测试集（household/org_module_policy/batch_import/
  business_health/excel_template/fund_anomaly/village export 等 14 文件）   -> 293 passed
pytest tests/unit/test_database_indexes.py tests/unit/test_fixes.py          -> 29 passed
pytest tests/security tests/unit/middleware（viewer 只读回归）               -> 110 passed（前一轮，未受影响）
DB 审计脚本（副本）：db_audit / db_fk_audit / schema_drift_audit / chain_check / fresh_db_check -> 结果见第三节
alembic upgrade head（真实库副本 w22→r33）                                  -> EXIT=0；降级/再升级 EXIT=0
```

## 七、遗留风险与建议（按优先级）

1. **发布前必须决策**：是否补 `r34_effectiveness_fk_rebuild_001` + schema 对齐迁移（3.2/3.3）。若不补：全新安装可用；**v1.13 及更早升级用户的成效评估功能损坏**，且升级库缺索引/FK。建议至少在 Release Notes 声明"升级前备份"并由 Lead 批准迁移。
2. 生产 `GRANT_ALLOW_UNSIGNED` 必须保持 false（默认）；`GRANT_GUARD_MODE` 发布默认 off，若要启用 enforce 需先确认 `unmapped_write_routes=0`（已达标）并灰度 shadow。
3. `scripts/validate_indexes.py`/`check_foreign_keys.py` 陈旧，建议删除或重写（否则运维按脚本提示执行 `alembic upgrade head` 也不会消除误报）。
4. 真实开发库非发布产物：Electron 无预置库分支、`resources/database/` 不存在、Kylin postinst 的 `backend/database/...` 也不存在（该分支为死路径），全新安装由 backend 首启 create_all 建库 —— 无需清理该库；但**工作区** `backend/` 下 138 个测试残留目录（664.7MB）与 `backend/data` 下 20 个历史 *.db（73.7MB）建议打包前清理（均 gitignored，不随包分发）。
5. 并发导入授权的读-比较-写非原子（3.10），建议后续 CAS 加固（P2，本轮未改）。

---

# 附：R34 迁移实现（Lead 批准后落地，2026-10-19）

## 迁移文件

`backend/alembic/versions/r34_effectiveness_fk_rebuild_001.py`

- revision = `r34_effectiveness_fk_rebuild_001`，down_revision = `r33_org_grants_001` → **单 head**（`alembic heads` 输出仅此一个，revision_count 54、down_revision 全部可解析）。
- upgrade：① 孤儿评估行搬入审计表 `r34_orphan_effectiveness_evaluations`（列 NOT NULL 不能置 NULL；搬移保留可追溯性）→ ② `batch_alter_table(copy_from=显式表定义, recreate="always")` 重建 `effectiveness_evaluations`：village_id → `supported_villages.id (CASCADE)`、evaluated_by → `users.id (SET NULL)`、保留 `uq_effectiveness_village_year` 与 3 个模型索引 → ③ 保守补建 19 个模型声明但升级库缺失的索引（表/列/同名索引存在性逐项检查；仅 tea_plantations/cactus_fruit_plots 的 2 个因列为 W22 改名后的 supported_village_id 且两模型零业务引用而跳过）→ ④ 迁移内断言 `PRAGMA foreign_key_check` 为空，否则 raise（fail-loud）。
- downgrade：显式 `raise NotImplementedError`（父表 villages 已不存在，表重建不可无损回滚；升级前需备份）。实测 `alembic downgrade -1` EXIT=1 且版本保持 r34 head（无半迁移状态）。
- docstring 明确「本迁移不处理」：其余 9 个缺失 FK、6 张零引用 legacy 表、tea/cactus 列名漂移。

## 验证证据

### 1) 真实库副本 · 应用启动路径（生产同款 `_init_database_tables`）

```
baseline: alembic=w22_household_media_consumption_001, tables=134,
          users=2 / villages=6 / projects=6 / funds=12 / work_logs=138 / audit_logs=215
启动日志: Running upgrade w22 -> r33 -> r34；r34 完成（effectiveness 重建=True）；
          create_indexes: 19 成功, 0 跳过, 0 失败
after: alembic=r34_effectiveness_fk_rebuild_001, tables=135(+org_grants)
       foreign_key_violations = []            ← 原 1 条违规清零
       effectiveness FK: village_id -> supported_villages(CASCADE), evaluated_by -> users(SET NULL)
       19 个补建索引全部存在；effectiveness 3 索引 + 唯一索引齐全
       INSERT effectiveness_evaluations -> OK（不再 no such table: main.villages）
       关键表行数全部不变（users 2 / villages 6 / projects 6 / funds 12 / work_logs 138 / audit_logs 215）
check_foreign_keys.py: ✓ 无外键约束违规
```

### 2) 全新安装路径（空库 create_all + stamp head，不执行迁移）

```
alembic_version = r34_effectiveness_fk_rebuild_001（stamp，未重放迁移）
foreign_key_violations = []；effectiveness FK 正确；households 索引齐全；
INSERT effectiveness_evaluations -> OK；create_indexes 19 成功
```

### 3) 自动化测试（新增 10 条，全绿）

`backend/tests/unit/test_migration_r34_effectiveness_fk.py`：迁移链/SingleHead、旧结构+孤儿行升级后 FK 改写与数据保留、孤儿搬移（含审计表已存在的追加分支）、幂等重复 upgrade、已是新结构跳过重建、缺表安全、19 索引补建与「表缺/列缺」跳过、其他外键违规时 fail-loud raise、downgrade 显式 NotImplementedError。

```text
pytest tests/unit/test_migration_r34_effectiveness_fk.py                       -> 10 passed
pytest 迁移相关 6 文件（新增 + single_head/file_blob/migration_helper/
  main_migration_cov/main_migration_cov20/rural_work_village_migration）        -> 57 passed
flake8 迁移文件 + 新测试文件（-max-line-length=120 -max-complexity=16）         -> 0 违规
alembic heads                                                                    -> r34_effectiveness_fk_rebuild_001（单 head）
```

## 剩余 schema 漂移（本轮不做，后续专项清单，供 Lead 排期）

1. **9 个模型声明但升级库缺失的外键**：cactus_fruit_plots.village_id、tea_plantations.village_id、rural_works.organization_id、consumption_records.organization_id、households.organization_id、household_members.organization_id、household_risk_records.organization_id、photo_archives.organization_id、users.permission_pack_id（需逐表 batch 重建，风险高）。
2. **6 张零引用 legacy 表**：comments、messages_extended、sentiment_keywords、sentiment_reports、workflow_definitions、workflow_instances（app 内 0 引用；建议单独迁移 DROP）。
3. **tea_plantations / cactus_fruit_plots 列名漂移**：W22 迁移已改为 supported_village_id，模型仍声明 village_id；两模型当前零业务引用（可考虑连模型/表一并清理）。
4. **脱离模型的 15 个旧索引**（旧命名/旧列）仍在升级库中，可随下一次迁移清理。
5. `scripts/validate_indexes.py` 陈旧误报、`check_foreign_keys.py` 无失败退出码：scripts 不在后端写入范围，建议 ops-probe/后续批次处理。

