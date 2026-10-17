# 数据完整性与不可逆风险 深度探测报告（W18）

> 探测器：probe-data（只读探测，未改任何产品代码）
> 基线：`d7246dc`（v1.12.18，工作区另有 w17 功能在途改动，与本报告无关）
> 方法：静态取证到 `文件:行号` + **最小可复现实证脚本**（`.scratch/w18-deep-probe/_probe_*.py`，均真实 SQLite/真实服务层，未跑全量测试）
> 去重口径：仅登记 R27（`docs/系统全面排查报告-2026-10-14.md`）/ R28（`docs/R28修复交付报告`、`docs/R28补充验证与补漏报告`）与 `.scratch/w2-data-integrity`、`.scratch/w12-system-compliance` 中**未登记或只登记表象未登记后果**的新维度；已修/已定性不修的条目不再重复。

---

## 0. 结论速览

| 级别 | 条数 | 条目 |
|---|---|---|
| **P0** | **3** | D1 数据包导入主键碰撞 → 跨机静默覆写/错挂（不可逆）· D2 全量覆盖导入物理删除回收站与级联子表（不可逆）· D3 权限包/数据包导入可写入他组织（越权写，安全红线） |
| **P1** | **5** | D4 导入"报告成功但数据没进去"（回执失真）· D5 增量包重复应用覆盖本机更新 · D6 回收站单条彻底删除无数据域 · D7 从更高版本备份恢复后生产环境永久无法启动 · D8 数据包内 PII 明文落盘 + 两套同步链 PII 处理相反导致跨机不可读 |
| **P2** | **6** | D9 村彻底删除预览/统计口径失真 · D10 村彻底删除与通用级联两套实现并存（新子表落两套之间）· D11 恢复半途失败会留下需人工介入的快照 + Windows 回滚必失败 · D12 恢复演练只看最新一个备份 · D13 增量备份产出的包**无法用于恢复** · D14 升级排练与真实启动的 schema 兜底路径不同（覆盖有缺口） |
| **P3** | **5** | 见 §4 |

### 最该先做的 3 条

1. **D1 导入主键碰撞**（`data_package_service.py:532-610`）：两台机器各自从 `id=1` 起步，A 机导出的包导入 B 机时，`confirmed_import(overwrite_existing=True)` 会用 `ON CONFLICT(id) DO UPDATE` **把 B 机同 id 的真实记录改写成 A 机数据**（`organization_id` 也一起被改写）。实证：B 机"B机的真实村" → 导入后变成"A机的另一个村"，全库只剩 1 行且归属翻到他组织。**没有任何冲突提示、没有备份、`deleted_at/created_at` 都被覆盖。** 注意**两条分支都错**：`overwrite_existing=False`（普通接收默认）走 `DO NOTHING` 静默丢导入记录，`=True`（增量应用硬编码）走 `DO UPDATE` 覆写本地记录（见 D1 正文实证）。
2. **D3 导入侧组织归属可被包内 manifest 改写**（`data_package_service.py:447-453`）：`confirm_import` 以 `manifest.org_code` 反查本地组织并**覆盖**调用者指定的目标 org，且不校验调用者是否有目标组织权限 → 部门级管理员把包导进本部门，实际数据写进别的部门。实证：adminB（org=B）导入后村的 `organization_id=A`。
3. **D2 全量覆盖导入删除范围远超用户认知**（`excel_importer_service.py:456-497`、`572-587`、`640-658`、`711-731`）：`_import_full_mode` 执行的是 **`query.delete()` 物理删除**（含回收站里的 `is_active=False` 行），且因 `projects.village_id / funds.project_id / funds.village_id` 全是 `ON DELETE CASCADE`，**只导入帮扶村也会把项目与经费一起物理删掉**。实证：`villages 1 / projects 1 / funds 1` → 全量导入 1 行村后 `projects 0 / funds 0`。

---

## 0b. 修复状态（2026-10-17 当日落地，Lead 实施）

| 条目 | 状态 | 修复位置 | 验证 |
|---|---|---|---|
| **D1 跨机主键碰撞** | ✅ **已修** | `data_package_service.py`：新增 `BUSINESS_KEYS`/`_business_key_of`/`_classify_import_records`；主键已占用时按业务键判定——相同则更新/跳过，不同则**换新 id 插入**、不覆写本机数据 | `test_data_package_pk_collision_w18.py`（8 条，真实双库场景）；实证：修复前全库只剩 1 行被覆写 → 修复后 2 行共存且本机 org 未变 |
| **D2 全量导入物理删除** | ✅ **已修** | `excel_importer_service.py`：四处 `query.delete()` 改为 `_soft_delete_scoped()`（软删 `is_active=False`），不再触发 `ON DELETE CASCADE` | `test_full_import_soft_delete_w18.py`（4 条）；实证：修复前只导村导致 projects/funds 归零 → 修复后子表完好 |
| **D3 包内组织改写 + KEEP_BOTH org=NULL** | ✅ **已修** | `data_package_service.py`：manifest.org_code 仅在**与调用者目标组织一致**时采纳，否则忽略并告警；`smart_conflict_resolver._keep_both` 插入前补回归属 | `test_import_org_scope_w18.py`（4 条）；实证：导入落库组织跟随调用者目标而非包内组织 |
| **D6 回收站单条越权物理删除** | ✅ **已修** | `recycle_bin.py`：新增模块级 `_require_reachable()`，接入 `/{rid}/purge/preview`、`/{rid}/restore`、`/{rid}/purge` | `test_recycle_scope_and_model_reg_w18.py`（4 条）；49 条回收站用例全绿 |
| **P3-1 `sentiment_news` 新装缺表** | ✅ **已修** | `models/__init__.py`：注册 `SentimentNews`；全仓扫描时**另发现** `MachineCodePermission` 同样漏注册，一并补上 | 扫描 0 遗漏；新装 `create_all` 实测 120 表含这两张；守卫测试断言全量模型均已登记 |
| D4/D5/D7/D8/D9–D14 | ⏳ 未修 | — | 本批优先处理不可逆/越权项；其余按优先级排列（见 §5 建议） |

> **D1 修复的取舍说明（如实记录）**：完整方案应按业务键做全局 `id_mapping` 重写外键，改动面涉及
> 导入链路全部子表；本轮采用**保守但正确**的方案——撞 id 且业务键不同即换新 id 插入。
> 副作用：跨机同步后同一业务记录可能在两库有不同 id（这正是"保留源 id"设计想要避免的，
> 但保留源 id 会覆写本地数据）。**外键重映射仍是待办**（D1 正文第 3 条修法），
> 建议作为独立批次：先接通 `smart_conflict_resolver._update_foreign_keys` 到 bulk 路径。

---

## 1. P0 条目

### D1 数据包导入按主键 `ON CONFLICT DO UPDATE`：跨机同 id 静默覆写，外键错挂

**位置**
- `backend/app/services/data_package_service.py:532-553`（`_build_upsert_statement`：:546 `on_conflict_do_update`，:550/:552 `on_conflict_do_nothing`）
- `backend/app/services/data_package_service.py:555-610`（`_bulk_upsert_records`：按列集合分组后逐组 upsert，:604 `imported += len(group_records)`）
- 触发入口：`backend/app/api/v1/data/data/data_packages.py:917-921`（`incremental/import` 的 `apply_changes=true` **硬编码 `overwrite_existing=True`**）
- 前端入口：`frontend/src/views/dataPackage/IncrementalUpdate.vue:313-318`（勾选"应用变更"即走该端点）

**现行行为**
```python
# data_package_service.py:533-546
stmt = sqlite_insert(model).values(clean_records)
if overwrite:
    carried = set(clean_records[0].keys())
    update_cols = {c.name: c for c in stmt.excluded if c.name != pk_name and c.name in carried}
    stmt = stmt.on_conflict_do_update(index_elements=[pk_name], set_=update_cols)
```
导入以**源机主键**作为冲突键：目标机只要存在相同 `id`，该行就被整体 UPDATE 成包内数据。

**实测（`.scratch/w18-deep-probe/_probe_pk_collision.py`）**
```
BEFORE local: 1 B机的真实村 org= 2 honors= B机自有数据
RESULT: True {'villages': 1} {'villages': 0}
AFTER row count: 1
   1 A机的另一个村 org= 1 honors= A机数据 created_at=2026-10-01 ...
```

**两条分支都错（关键）**：`overwrite_existing` 只决定走哪条错路——
- `overwrite_existing=True`（增量应用路径硬编码，`data_packages.py:920`）：本地同 id 行被**改写**（上面这组实证）；
- `overwrite_existing=False`（普通接收路径的默认值，`schemas/data_package.py:155`；前端 `ReceivePackage.vue:742` 就发这个）：走 `on_conflict_do_nothing`（`data_package_service.py:551-552`），**导入侧那条记录被静默丢弃**、本地行也不动，但计数仍按 `imported` 累加。实证 `_probe_item_village.py`：
```
overwrite=False result: True {'villages': 2} {'villages': 0}   ← 报导入 2 条
   1 本机村 org= 1          ← 本地 id=1 保留（正确）
   2 A机的新村 org= 1       ← 只写进 1 条
```
即：**默认路径丢导入数据、增量路径毁本地数据**，两条都没有任何冲突提示。

另一组（`_probe_wrong_link.py`）显示同型后果还包括**外键错挂**：
```
VILLAGE 1 A团的村 org= 1
PROJECT 1 B团的项目 village_id= 1     ← B 团原项目仍然指 1，但 1 号村已被换成 A 团的村
PROJECT 2 A团的项目 village_id= 1
```

**真实后果**
- 谁会踩：**任何两台各自录入过数据的机器**。SQLite 自增主键从 1 开始，两边前几条记录 id 必然相撞 —— 不是概率问题，是必现。
- 什么时候踩：用户把 A 机的增量/上报包带到 B 机，"预览"只显示 `added/modified` 计数（`data_packages.py:644-679` 只按 id 是否存在分 added/modified，**不区分"同 id 是不是同一条业务记录"**），管理员看到"修改 3 条"点确认。
- 可不可逆：**不可逆**。原行被 UPDATE 覆盖（`created_at`/`organization_id`/`deleted_at` 全被包内值替换），且**导入前不触发即时备份**（`data_packages.py` 全文件无 `trigger_immediate_backup`，只有回收站/村彻底删除/Excel 导入有）。事后无法区分"被覆盖的行原来是什么"。
- 连带：被覆盖行的 `organization_id` 变成源组织 → 该行从原组织的数据域里消失（等于"数据凭空少了"），并且在源组织的数据域里出现（跨组织串数据）。

**根因**
把"跨机数据同步"当成"同库备份还原"处理：以自增 `id` 作为身份，而这套系统没有全局唯一业务主键可做映射（`smart_conflict_resolver` 有 `id_mapping` 机制，但**只被 `confirm-import` 的 KEEP_BOTH 路径使用**，见 D3；`confirm_import` 的 upsert 路径完全不用映射）。

**修法（改动面）**
1. `_bulk_upsert_records` 里把"主键冲突"从 `DO UPDATE` 改为**按业务键判定**：
   - 先按业务键（`villages.village_name` + `organization_id`；`projects.code`；`funds.code`；`schools.code`）结算本地命中行；
   - 命中则按 `id_mapping` 建立 `源id → 本地id` 映射后更新；
   - 未命中则以**新 id 插入**（不要沿用源 id），并把映射表交给子表外键重写（`_update_foreign_keys` 已有该逻辑，可直接复用 `smart_conflict_resolver.py:564-591`）。
2. 保留"显式导入覆盖"能力时，必须在预览里按 `(类型, 源id, 源记录摘要, 本地记录摘要)` 列出**逐行差异**并要求二次确认（现状只有 4 个数字）。
3. 若短期不做映射，最低限度：`overwrite_existing=True` 分支在导入前触发一次 `trigger_immediate_backup(wait=True)`，失败则拒绝导入（与 `retention_service.py:72-87` 的既有 fail-closed 模式一致）。
4. 回归测试：`tests/unit/test_data_package_pk_collision.py` —— 构造"两边都从 1 开始"的两库，断言导入后本地原行**仍在**且 `organization_id/created_at` 未变。

**为何前几轮没发现**
R27/R28 的数据包相关条目只有 M29（`stmt.excluded` 把未携带列写 NULL，已修）和 M25（冲突解决器漏映射 `funds.village_id/school_id`，已修）—— 两者都在**"冲突解决器（confirm-import）"这条路径**上。`confirm_import` 的 bulk-upsert 路径被 R28 当成"已用 SAVEPOINT + 保留原始 ID 解决外键孤儿"的**修复成果**（`data_package_service.py:7` 模块注释"保留原始 ID…彻底解决外键孤儿问题"），审计时按"这是修好的"跳过。且该缺陷需要**两个都录过数据的库**才能显形，纯单元测试（单库）与既有用例（同库导入同库）都不会红。

---

### D2 全量覆盖导入：物理删除（含回收站）+ 级联抹掉子表

**位置**
- `backend/app/services/excel_importer_service.py:466-473`（帮扶村全量：`scoped_filter(...).delete(synchronize_session=False)`）
- `backend/app/services/excel_importer_service.py:583-587`（项目）、`:654-658`（经费）、`:725-731`（学校）同型
- 端点：`backend/app/api/v1/import_export/import_data.py:288-303`（`mode=full`）
- 下级外键：`projects.village_id` `ondelete="CASCADE"`（`models/project.py:80-85`）、`funds.project_id / funds.village_id` CASCADE（`models/fund.py:102-108`）

**现行行为**
```python
# excel_importer_service.py:466-473
if self.current_user:
    query = scoped_filter(self.db.query(SupportedVillage), SupportedVillage, self.current_user)
else:
    query = self.db.query(SupportedVillage)
query.delete(synchronize_session=False)     # ← 物理 DELETE，不过滤 is_active
```

**实测（`_probe_full_village_cascade.py`）**
```
BEFORE: villages 1 projects 1 funds 1 schools 1
BEFORE-said: 全量覆盖导入帮扶村
AFTER:  villages 1 projects 0 funds 0 schools 1
>>> 只导入帮扶村，却连带物理删除了项目/经费: True
```
`_probe_fullmode.py` 另测回收站：
```
before full import: [(1,'历史村0',False),(2,'历史村1',False),(3,'历史村2',False)]   ← 全部在回收站
after  full import: [(1,'新导入村',True)]
=> 回收站中的软删记录被物理删除: True
```
（附注：`ImportHistory.user_id` 在本脚本里必须置 NULL 才能插入，`import_histories.user_id` 对本环境是 NOT NULL —— 与本条无关，但说明**该表与 `users` 的 SET NULL×NOT NULL 矛盾在 w15 迁移后仍存在于 create_all 路径**，见 P3。）

**真实后果**
- 谁会踩：任何在导入页选择"全量覆盖"的用户。UI 文案是"删除现有所有记录后导入新数据"（`import_data.py:211`），但用户理解不到：(a) 回收站里的记录**也会被物理删除**（不可恢复）；(b) 删村会连带级联删项目/经费（外键 CASCADE）。
- 什么时候踩：一次常规的"我重新整理了一份村的 Excel，全量覆盖一下"。
- 可不可逆：**不可逆**。虽有 `trigger_immediate_backup(delay=1.0)`（`import_data.py:299-301`），但它是**导入之后**触发、后台线程、不等待结果 —— 快照里已经是删完的状态；且幂等锁被占用时直接 skip（`immediate_backup.py:33-35` 返回 False，调用方 `import_data.py:301` **不检查返回值**）。
- 数据域外幻觉：`scoped_filter` 对部门级 admin 收敛到本组织子树 —— 但组织树里**父组织导入会连带删下级组织的村**，且随后 CASCADE 掉这些村的全部项目/经费。

**根因**
两套"删除"语义混用：业务层约定是软删（`is_active=False` + 回收站 30 天，`retention_service.py`），批量导入的 full 模式却用 ORM 物理删除，且没加 `is_active == True` 过滤。同时把"清空主表"当成安全操作 —— 但 schema 里子表是 CASCADE，"清空主表"实际是"清空主表 + 全部子孙"。

**修法（改动面）**
1. 四处 `query.delete()` 改为软删：`.update({"is_active": False, "deleted_at": utcnow()}, synchronize_session=False)`（与 `projects.py:1119-1121` 的删除口径一致）；school/fund 同型。
2. 导入成功后**所有**被软删的行进入回收站（可恢复），而不是消失。
3. `import_data.py` 把 `trigger_immediate_backup` 改为 `wait=True` 且在**导入前**触发（fail-closed），并检查返回值；失败则拒绝执行 full 模式。
4. 前端"全量覆盖"文案补一句"已有记录将移入回收站（可在回收站恢复），关联的项目/经费不会被删除"。
5. 回归：`test_import_full_mode_soft_delete.py` —— 断言 full 导入后 `is_active=False` 行数 == 导入前行数、且 `projects/funds` 行数不变。

**为何前几轮没发现**
R27/R28 审视"删除路径"时聚焦在**用户点删除按钮**（`cascade_purge_service`、`recycle_bin`、`user_cascade_delete`、`village_cascade_delete`），R27-H1 修的是**彻底删除的 SQL 生成**，假设了"软删是所有删除的唯一入口"。批量导入的 full 模式从没人把它当"删除路径"审计（它被归类为"导入"）。而 `import_export/import_data.py` 的 R27 条目只有 M14（预览全表扫描）与错误文案，没有触及删除语义。

---

### D3 导入侧组织归属由包内 manifest 决定：越权写入他组织 + KEEP_BOTH 新行丢 `organization_id`

**位置**
- `backend/app/services/data_package_service.py:447-453`（`confirm_import` 用 `manifest["org_code"]` 反查本地组织并覆盖 `resolved_org_id`）
- `backend/app/services/data_package_service.py:782`（`SmartConflictResolver(self.db)` —— **不传 `organization_id`**）
- `backend/app/services/smart_conflict_resolver.py:87-96`（新行插入 `_import_new_records`，未设租户列）
- `backend/app/services/smart_conflict_resolver.py:31-38`（`_PROTECTED_COLUMNS` 含 `organization_id` → 导入记录自带的 org **被剥掉**）
- 路由鉴权：`backend/app/api/v1/data/data/data_packages.py:1527-1529`（`confirm-import` 只校验 **包记录** 的 `org_id` 权限）

**现行行为**
```python
# data_package_service.py:447-453
resolved_org_id = package.org_id
source_org_code = manifest_dict.get("org_code", "")
if source_org_code:
    local_org = self.db.query(Organization).filter(Organization.code == source_org_code).first()
    if local_org:
        resolved_org_id = local_org.id          # ← 覆盖调用者指定的目标组织，且此后再不校验权限
```
两条导入路径的租户处理**恰好相反**：
- `confirm_import`（bulk upsert）：用 `resolved_org_id` 强制写入每一条 → 归到包 manifest 说的那个组织；
- `confirm_import_with_conflict_resolution`（KEEP_BOTH 等）：`SmartConflictResolver(self.db)` 无租户上下文 → `_writable_items` 又把 `organization_id` 列入 `_PROTECTED_COLUMNS` 剥掉 → 新插入行 **`organization_id = NULL`**。

**实测**
1）越权写（`_probe_org_redirect.py`）：
```
target org A id: 1 | importer org B id: 2
路径一：先 import（包记录挂到 B），再 confirm
  package.org_id = 2 (B)
  confirm: True {'villages': 1}
  村: A部门的村 落库 organization_id = 1 -> A部门(越权)
```
2）KEEP_BOTH 新行丢组织（`_probe_confirm2.py`）：
```
result: {'success': True, 'message': '导入并解决冲突完成'}
AFTER 1 同名村 org= 2
AFTER 2 B独有村 org= 2
AFTER 3 同名村_imp_4d97e29c org= None     ← 新插入行无组织
```

**真实后果**
- 谁会踩：(a) 部门级 admin 把收到的包导进自己部门 → 数据落进原上报单位（对方组织），本部门看不到，且**没有任何提示**；若源组织在本地不存在（首次接收新单位），`local_org` 为 None 则退回 `package.org_id`（正常）。
- (b) 用"保留双方"策略导入的每一行**全部变成无组织数据**：`organization_id IS NULL` → 数据域 fail-closed（`ADR-0002`）→ 普通用户与部门级 admin 都看不到，只有 super_admin 可见；回收站保留期清理（`retention_service.py:57-65`，SQL 直接写表）也照样能删它。等于**数据在导入那一刻就"丢了"（只对超管可见）**。
- 可不可逆：越权写可逆（改回 org），但**用户不知道数据在别人那儿**；KEEP_BOTH 丢组织**不可逆**（`confirm-import` 路径没有 `id_mapping` 回写、没有审计字段记录原 org）。
- 合规：军审红线"跨组织数据串写"，且 `confirm-import` 是**三步链路里唯一没有 `require_admin` 的落库端点**（`data_packages.py:1511-1557` 全文无 `require_admin`，只有 `can_access_organization` 校验包记录）。普通用户拿到 `package_id`（自己组织的包）就能触发全量落库。

**根因**
"包记录的归属"与"包内数据的归属"被当成同一件事，而 manifest 里的 `org_code` 是**源机**的组织编码。设计上缺少"导入目标组织必须由调用者显式指定并校验可达性"的不变量；`SmartConflictResolver` 明明支持 `organization_id` 参数（`smart_conflict_resolver.py:139-147` 的 docstring 就写了"深审 #63 可选租户收敛"），生产调用点却没传。

**修法（改动面）**
1. `confirm_import` / `confirm_import_with_conflict_resolution`：删除 `manifest.org_code` 反查覆盖；目标组织一律取端点传入的 `org_id`，并在服务层**再校验一次** `can_access_organization`（端点层的校验点在三个入口都不同，服务层不应依赖）。
2. `SmartConflictResolver(self.db, organization_id=org_id)`（两处）；`_import_new_records` 显式 `new_data["organization_id"] = tenant`（`_writable_items` 剥掉后补回）。
3. `confirm-import` 端点补 `require_admin`（与其兄弟 `/{id}/confirm`（`data_packages.py:1067`）口径一致）。
4. 回归：`test_import_org_attribution.py` —— 断言导入后所有行 `organization_id == 调用者指定组织`；`assert `无 organization_id IS NULL 的新行`。

**为何前几轮没发现**
R28-T6 修的是 `permission_package_service` 的组织 `path/level`（M26）与 `smart_conflict_resolver` 的外键映射（M25）—— 都在"同一组织内"的假设下。R28 主报告 §4 明确把"admin 的 org-tree 全量口径"列为**已定设计**，审计时把"导入落哪个组织"归到该设计里，没有单独检查 `manifest.org_code` 这条**来自外部文件、不可信**的输入。KEEP_BOTH 丢 org 更是被 `_PROTECTED_COLUMNS` 的注释（"防止跨组织串改"）**反向掩盖**：剥离 org 的初衷是防覆盖，但没补写回。

---

## 2. P1 条目

### D4 导入回执失真："成功 1 条"但库里 0 条；`error_counts` 恒 0

**位置**
- `backend/app/services/data_package_service.py:592-610`（`imported += len(group_records)` 与"本组 savepoint 提交成功"混同；`on_conflict_do_nothing` 也计为 imported）
- `backend/app/services/data_package_service.py:551-552`（`overwrite=False` 走 `on_conflict_do_nothing` → 冲突行被**静默丢弃**却仍计数）
- `backend/app/services/data_package_service.py:484-486`（`error_counts[data_type] = len(errs)`，`errs` 只来自批量写入异常；**字段校验 rejected 被算进 `skipped_counts`**，见 `:485` `result["skipped"] = ... + len(rejected)`）
- `backend/app/services/data_package_service.py:494-497`（返回 `success=True`，与 `errors` 非空无关）

**实测（`_probe_count_lie.py`）**
```
local count: 3
REPORTED imported: {'villages': 3} skipped: {'villages': 0} success: True
ACTUAL local rows: 3        ← 3 条全被 on_conflict_do_nothing 丢弃，一行都没写
```
（另 `_probe_partial2.py`：`imported {'villages':1,'projects':0}`、`error_counts {'villages':0,'projects':0}`、另有 `error_msgs=['第1行校验未通过: 缺少必填字段: name']` —— **`error_counts` 是 0，只有 errors 列表里有内容**。）

**现行行为 / 真实后果**
- 前端 `ReceivePackage.vue:738-748` 只要 HTTP 200 就 `ElMessage.success('数据包导入成功')`，随后 `loadReports()`；列表里没有新数据，用户会以为"包是空的"或"系统吞数据"。
- 用户据此选择"换台机器再导一次" → 叠加 D1 的风险。
- `error_counts` 恒 0 使前端"失败 N 条"的提示永远不出现（`data_packages.py:1104` 把它写进操作历史，审计里也是 0）。
- 不可逆性：本身不丢数据，但**误导用户做后续不可逆操作**。

**修法**：`imported` 改为按 `INSERT ... ON CONFLICT DO NOTHING` 的实际 `rowcount` 累计（分批 execute 后累加 `result.rowcount`）；`skipped` 与 `rejected` 分开计；`success` 改为 `imported + skipped + rejected == total` 且 `rejected == 0`；前端按 `imported/skipped/rejected` 三态提示。

**为何漏掉**：R27-M29 只审 `overwrite=True` 的 `excluded` 语义，没看**计数来源**；单测 `test_data_package_service.py` 用的是"包内 id 与库内不冲突"的夹具，覆盖不到 DO NOTHING 分支的计数。

---

### D5 增量包可被重复应用：旧包覆盖本机新编辑（`overwrite_existing=True` 无视时间戳）

**位置**：`backend/app/api/v1/data/data/data_packages.py:917-921`（`confirm_import(overwrite_existing=True)`，无 `since/updated_at` 过滤）→ `data_package_service.py:533-546`
前端：`IncrementalUpdate.vue:313-318`（`apply_changes`）

**实测（`_probe_incr_reapply.py`）**
```
exported update package type: update status: PackageStatus.validated
local after edit: 版本2-本地新编辑
after apply_changes -> honors: 版本1
=> 本机新编辑被旧包覆盖: True
```

**后果**：用户按"增量"的语义理解（只补缺失/更新的部分），实际执行的是**无条件覆盖**。同一台机器上"导出 → 自己改 → 又点了应用"就丢编辑；两台机器互相传包时，谁的包后到谁赢，与 `updated_at` 无关。`_should_update_record`（`data_sync_service.py:997-1016`）那套时间戳比较只存在于 `.zip/.rrs` 那条链，**datapackage 这条链不用**。
**修法**：`confirm_import` 增加 `conflict_ts_guard=True` 参数（增量包默认开），在 `_build_upsert_statement` 的 `set_` 中加 `WHERE model.updated_at < excluded.updated_at`（SQLite upsert 支持 `where=`）；或直接复用 `_should_update_record` 做行级筛选。
**为何漏掉**：R28-T6 只修了"不要写 NULL 列"（M29），没审"要不要按版本覆盖"；`incremental/` 三个端点是 W18 之前新加的功能，R27/R28 的报告里**没有任何一条覆盖 `incremental/import` 的语义**。

---

### D6 回收站**单条**彻底删除缺数据域（批量删才有）—— 不可逆越权

**位置**
- `backend/app/api/v1/recycle_bin.py:152-163`（`/{rid}/purge`：`require_admin` → 密码校验 → `_get_or_404` → `CascadePurgeService.purge`）
- 对照 `backend/app/api/v1/recycle_bin.py:55-84`（`_reachable_ids`，**只有批量路径** `batch-purge` 用了它）
- 注册点：`funds.py:1495-1500`、`projects.py:2124-2126`、`school.py:1473-1478`
- 前端：`frontend/src/api/fundsRecycle.ts:5-7`、`projects.ts:38-41`、`schoolsRecycle.ts:5-7`

**实测（`_probe_purge_scope2.py`）**
```
mgr org: 2 role: admin is_superuser: False
target project id: 1 org: 1
PREVIEW (cross-org): 200 {"data":{"id":1,"name":"A组织的项目",...}}
PURGE (cross-org): 200 {"message":"已彻底删除并清理 1 条关联数据"}
project still exists after purge: False
```

**后果**：部门级 admin 只要知道 id（列表页会过滤看不到，但 id 可遍历 / 从审批单、日志、导出的旧 Excel 里得到），配合自己的登录密码就能**物理清除他组织的数据**。这是 R28-M3 **只修了一半**：批量路径已收敛（`recycle_bin.py:177-178, 192-194` 有注释），单条路径漏了。可不可逆：物理删除 + 无数据域 → 红线。
**修法**：`/purge` 与 `/purge/preview` 在 `_get_or_404` 之后加一步 `_reachable_ids(db, model, table, [rid], current_user)`，不在域内一律 404（与批量同语义）。
**为何漏掉**：R28-M3 的修复清单写的是"回收站批量操作按数据域收敛 ids（缺组织列时 fail-closed）"（`R28修复交付报告` T2 行），**只列了批量**；单条端点在同一个文件里但不在那条清单上。且 `require_admin` 让人误以为"管理员就能操作"是设计。

---

### D7 从"更高版本"的备份恢复后，生产环境**永久无法启动**（无降级路径）

**位置**
- `backend/app/services/backup_service.py:735-803`（`restore_backup` 只校验 `integrity_check`，**不校验 `alembic_version`**）
- `backend/app/main.py:592-608`（`_run_alembic_upgrade` 在 `ENVIRONMENT=production` 时 **raise**，启动中止）
- `backend/app/main.py:575-586`（只在"无 alembic_version 但有业务表"时 stamp；**已知 revision 但比代码 head 新**时不处理）

**实测（`_probe_newer_schema.py`）**
```
DB: alembic_version=newer_version_002, extra column brand_new_field
RESULT: migration raised CommandError Can't locate revision identified by 'newer_version_002'
```
（`_probe_future_restore.py` 同型：`STARTUP_ABORTED (production fail-loud)`。）

**真实后果**
- 谁会踩：多机环境里"新版本机器 → 旧版本机器"的**备份包搬运**（`BackupManagement.vue` 的上传恢复就是为此设计的，`backup.py:776-931`）。桌面端默认即为 production（`core/config.py:86` `ENVIRONMENT: str = "production"`，`backend/.env:21` 同为 production），因此这是**必现**路径：恢复后首次启动即中止，而恢复界面本身在应用内 → 用户无法自助回退。
- 可不可逆：数据没丢（库在磁盘上），但**应用无法启动**，而恢复界面本身也在应用里 → 用户只能手工改库或重装，等于不可自助恢复。而且此前的**唯一回滚快照已在恢复成功时被删除**（`backup_service.py:789` `_cleanup_snapshots`）—— 现场没有任何回退物。
- 另一半：恢复前的"当前库"快照是 `backup_snapshot_*.db` 写在 `%TEMP%`，恢复成功后立即删除；用户若在恢复后才发现版本不对，**没有"恢复前状态"可回去**（只有用户手动做的备份）。

**修法**
1. `restore_backup` 在替换文件**之前**解析包内库的 `alembic_version`，与 `ScriptDirectory.from_config(cfg).get_current_head()` 比较：包内 revision 不在当前脚本链上 → 400 拒绝并给出明确文案（"该备份来自更高版本，请先升级本机程序"）。
2. `_run_alembic_upgrade` 对 "Can't locate revision" 增加可识别分支：生产环境也允许启动到"只读/维护态"并在 `/health` 暴露 `migration.error_type`（已有该字段），给用户一个能进 UI 做恢复的入口。
3. 恢复成功后**保留**恢复前快照 N 天（改为 `backup_dir/pre_restore_snapshots/`，按保留期清理），而不是用完即删。
**为何漏掉**：R27/R28 的备份相关条目全部围绕"WAL 一致性 / 完整性校验 / 维护窗口 / 磁盘空间"（`w12-system-compliance/046`、R27-§4 的 M8 等），**从未把"schema 版本"当成恢复的前置条件**；`upgrade_rehearsal.py`（P0-8）测的是"旧库升新代码"，方向相反，不覆盖"新库跑旧代码"。

---

### D8 数据包内 PII 明文落盘；两套同步链对 PII 处理相反，跨机导入后字段不可读

**位置**
- 明文侧：`backend/app/services/data_package_service.py:217-228`（`_export_data_type` 逐列 `getattr` → TypeDecorator 解密后的**明文**直接进 JSON）；`:231-240`（写入 zip）
- 密文侧：`backend/app/services/data_sync_service.py:260-298`（`_export_table_data` 走 **raw `text()` SQL**，绕过 TypeDecorator → 拿到库里原样密文）
- 落盘位置：`DataPackageService.upload_dir = <app_data>/uploads/packages`（`data_package_service.py:81-84`），保留 7 天（`data_package_service.py:864-902` + `backup_scheduler.py:286-303`）

**实测**
1）明文（`_probe_pkg_pii_plain.py`）：
```
DB at rest: enc.v1:OeMMAk7981hnOJMZ9NW  encrypted: True
ZIP member contact_phone: 13800138000
>>> 数据包内为明文手机号: True
```
2）data_sync 侧是密文（`_probe_xm_export.py`）：`PKG_IS_CIPHERTEXT: True`
3）跨机（不同 `ENCRYPTION_KEY`）导入后（`_probe_xm_import.py`）：
```
IMPORT total/success: 1 1 errors: []
TGT ORM read: 'enc.v1:Tsta8J1Kon4Vop7hqs/YdDcpGiYu9tiMS8Ho'
PII_READABLE: False
日志: PII 字段解密失败（密钥不匹配或数据损坏）
```

**真实后果**
- (a) 明文落盘：`uploads/packages/*.zip` 就是**未加密的全量 PII 包**（`villagers.id_card/phone`、委员会电话、机构/项目/学校联系电话）。备份默认 `include_uploads=True`（`backup.py:62`）→ 明文 PII 进入备份 zip；`/files` 静态目录若同根则可能被下载（需按 `get_runtime_uploads_path` 确认，属待验证）；这些文件在磁盘上**存活 7 天**且无任何访问控制之外的加密。ADR-0005 声明"PII 列已透明加密"，用户/审计会认为"数据在磁盘上是加密的"，**数据包例外这件事没有任何文档或 UI 提示**。
- (b) 跨机不可读：`data_sync` 的 `.zip/.rrs` 导出把**密文**带过去，目标机 `EncryptedText.process_result_value` 解密失败 → `decrypt_pii` 记 error 后**原样返回密文**（`pii_crypto.py:79-88`）→ 该列在 UI 上显示 `enc.v1:...`；写入时因已带 `enc.v1:` 前缀也**不再加密**（`encrypt_pii` line 73-74 `is_encrypted` 短路）→ 永久损坏（只能靠原密钥机器重新导出）。
- 可不可逆：(b) 只要用户没意识到是"密钥不一致"，会在新机器上继续编辑并保存 → 覆盖成密文/垃圾，原明文在源机仍在，但目标机这条记录从此不可用。

**修法**
1. 数据包导出：对 `EncryptedText` 列**保持密文**（导出走 raw 列值或 `col.type.process_bind_param` 的密文），并要求跨机部署配置相同 `ENCRYPTION_KEY`（ADR-0005 已有约定）—— 与 `data_sync` 口径统一。
2. 无法统一密钥时，至少导出包增加明文开关与 UI 红字警示，且 zip 走 `permission_package` 式的密码加密。
3. `uploads/packages` 纳入"敏感目录"清单：备份时单独标记、`/files` 拒绝该前缀、诊断包明确提示。
4. 回归：`test_pii_package_roundtrip.py` —— 断言"导出包内不含明文手机号"+"同密钥跨机导入后可读"。

**为何漏掉**：R28/W5-T7 的 PII 审计只查了"**列**是否用 `EncryptedText`"（ADR-0005 的 9 列清单）和"禁止裸 SQL 写入"，没人检查**导出/同步这些"合规例外"通道是否把明文搬出去**。`data_sync_service` 的 raw SQL 在 W2-T7 被登记为"裸 SQL 未收敛"，但当时关注的是"绕过 `sync_version` 事件/审计"，**没注意到它顺带绕过了 PII 透明加密** —— 而这恰恰是两条链行为相反的原因。

---

## 3. P2 条目（精简）

### D9 帮扶村彻底删除的"预览/统计"与实际删除范围不一致
- `village_cascade_delete_service.py:34-63`（`DEPENDENT_TABLES` 手工清单）漏了 4 张有 FK 的子表：`village_attachments`、`effectiveness_evaluations`、`pairing_records`、`donation_items`（用元数据实测得出，见 `_probe_fk_graph.py` 输出 `FK tables NOT in service list`）。
- `check_village_references`（`:136-168`）用同一份清单 → **预览少报**；实测 `_probe_vp2.py`：`PREVIEW total_references: 0`，实际删掉了 `village_attachments` 行。
- 更严重的是 `pairing_records/donation_items` 是 `ON DELETE SET NULL`：村被物理删除后它们**存活但被置 NULL**（`_probe_dangling.py`：`pairing_records -> [(1, None)]`）—— 预览里完全没提"这些记录会被清空目的地"。结对台账/捐赠台账凭空少一条去向，用户无从追溯。
- 修法：`check_village_references` 改为从 `Base.metadata` 外键图自动派生（`CascadePurgeService._load_graph` 已有实现），并在预览里区分"将删除"与"将置空"两类。
- 为何漏掉：R27-H1 修的是 `CascadePurgeService`（元数据图，自动发现），但**村端点没走它**（`supported_village.py:1069` 仍调旧服务），修一处漏一处；R28 复核 H1 时只验证了 `_delete_chain` 的 SQL 形态。

### D10 两套级联删除实现并存（通用工厂 vs 村专用服务），新子表只落到其中一套
- `recycle_bin.py:87-195`（通用工厂，走 `CascadePurgeService` 元数据图）用于 projects/schools/funds；
- `supported_village.py:986-1007, 1046-1102` 仍用 `VillageCascadeDeleteService`（手工清单）。
- 后果：同一操作用户体验不同（村预览 0 条 vs 项目预览准确），且**新增子表必须同时改两处**（`donation_items/pairing_records` 就是只被通用图发现、被村服务漏掉）。
- 修法：村端点切到 `register_recycle_bin_routes`（`table_name="supported_villages"`），删除 `VillageCascadeDeleteService`；保留其 schema 容错可移植进 `CascadePurgeService`。
- 为何漏掉：R27-H1 明确写"由 `:170 purge` 调用"作为**唯一**入口，没人核对该文件之外还有第二个实现。

### D11 恢复半途失败：Windows 上回滚**必失败**，且残留快照必须在 TEMP 里等 GC
- `backup_service.py:695-723`（`_rollback_to_snapshots`：先 `os.unlink(当前库)`，Windows 上文件被占用 → `RuntimeError`）；`_restore_database_from_backup`（`:610-671`）已经 `engine.dispose()` 并释放会话，但**审计刷写线程/其它后台线程**仍持有 `SessionLocal` 连接（`core/audit_middleware.py:188-212` `_persist_batch` 用 `SessionLocal()` 写库），Windows 下即占住文件。
- 实测（`_probe_restore_atomic.py`）：
  ```
  before restore: ['原始村', '备份后新增村']
  restore raised: RuntimeError 回滚失败：数据库文件被占用，无法还原快照
  after failed restore: ['原始村']       ← 半恢复：备份内容已生效，恢复前数据已丢
  NEW snapshot db left in TEMP: ...\backup_snapshot_d58p110r.db  (2.5MB)
  ```
- 后果：**用户看到"恢复失败"，但数据库其实已经被替换成备份内容**（回滚失败），"备份后新增村"这条数据消失且无任何提示；唯一救命的快照在 `%TEMP%`，重启/清理 TEMP 即永久丢失。
- 修法：(a) 回滚不要依赖 `unlink+copy`，改为"把快照 copy 到一个新文件 → `os.replace` 原子换名"（`_write_backup_zip` 已有 `os.replace` 先例）；(b) 回滚失败时把快照**移动到** `backup_dir/pre_restore/`（而不是留 TEMP）并在 API 响应里返回路径；(c) 恢复前 `maintenance_window` 已等在途请求归零，但**后台线程不在此列** —— 需在 `enter` 时额外暂停/join 可枚举的后台写线程（`db_maintenance`、`audit flusher`、`immediate_backup`）。
- 为何漏掉：`w12-system-compliance/046` 与 R7 只验证了"成功路径"（清 WAL、integrity_check、维护窗口），**失败路径的回滚**只在 R6 注释里被讨论过（"快照必须保留"），但没有实测 Windows 占用场景；`_probe` 第一次跑就复现。

### D12 恢复演练只验最新一个备份，损坏的旧备份永远不会被发现
- `restore_drill_service.py:70-81`（`_latest_backup_file` 取 mtime 最大者）、`:160-223`（只跑一个）。
- 后果：`cleanup_by_retention_days` 保留 7 天（`backup_scheduler.py:81-89`），用户依赖"每天都有备份"；一旦最新备份恰好是不可用但 `integrity_check` 通过的（如 D7 的版本不符、或只备份了空库），演练仍报 ok，而**上一份真正可用的备份可能已过期**。"单机系统最高等级数据风险"（模块 docstring 自述）只覆盖了 1/N 的样本。
- 修法：演练改为"最近 N（如 3）个备份各验一次"或"轮转抽样"（记录上次验过哪个，下次换下一个）；至少对**最早的那份**也验一次，因为它是保留期边界上最后的机会。
- 为何漏掉：R27/R28 无该模块条目；模块是 2026-09-12 架构评估 C1 新增，尚未被后续审计覆盖。

### D13 增量备份产出的包**不能用于恢复**，却出现在"备份列表"里
- `backup_service.py:1074-1106`（`_write_incremental_backup_zip` 把`变更文件`按 `os.path.relpath(file_path)` 写进 zip，成员名是**绝对路径相对 CWD** 的形状，如 `backend/data/rural_revitalization.db`——不是 `data/rural_revitalization.db`）；`:1136-1215`；列表 `:805-855` 把它当普通备份列出；前端 `BackupManagement.vue:139-140` 标为"增量"。
- 恢复路径 `_restore_backup_impl` → `_restore_database_from_backup:612` 只认 `temp_dir/data/rural_revitalization.db` → 对增量包**恒返回 False** → `BackupRestoreError("数据库恢复失败…")`，此时 `_create_snapshots` 已经建了快照、但**没有任何数据被替换**（安全），代价是用户以为备份坏了。
- 另：`create_incremental_backup` **全仓无生产调用方**（只有测试），`INCREMENTAL_BACKUP_ENABLED` 环境变量默认 true 但无调度接线 —— 属"半成品功能"。
- 修法：要么补齐"增量→全量还原"链（需要 base 链元数据），要么从列表里隐藏/标注"不可用于恢复"并关闭该入口；最短路径是把 `create_incremental_backup` 标注为实验特性、从 `list_backups` 过滤。
- 为何漏掉：R27 只登记了 `_query_backup_records` 漏匹配 `backup_incremental_*`（已修，让它们出现在列表里）—— **把"可见"当成修好了**，反而让不可恢复的包更容易被用户选中。

### D14 升级排练与真实启动的 schema 兜底路径不同，排练绿 ≠ 现场绿
- `backend/scripts/upgrade_rehearsal.py:203-232`（用**旧代码 alembic** 建库 → 播种 → **当前代码 alembic** 升级）
- 真实启动 `backend/app/main.py:506-537`：`create_all()` → `_run_alembic_upgrade()` → `_migrate_missing_columns()`（第二道兜底）→ `create_indexes()`
- 后果：真实升级路径多一道 `create_all`（会**补建**缺失表）与 `_migrate_missing_columns`（会 ALTER 补列），排练脚本**不模拟这两步**。实测（`_probe_old_db_upgrade.py`）：手工造一个"老库"（少 `sentiment_news`，`alembic_version=user_session_001`），`alembic upgrade head` rc=0、版本到 `donation_item_001`，但 `sentiment_news` **仍然不存在** → 查询直接 `no such table`。排练脚本同样不会发现这一点（它检查的是"旧表不丢"和"行数不变"，**不检查"模型声明的表是否齐全"**）。
- 修法：排练脚本加一步"反射 `Base.metadata.tables`，断言当前代码声明的每张表在升级后都存在"；这比行数比对更能抓住"迁移链缺失某张表"。
- 为何漏掉：P0-8 是 2026-10-17 新增的门禁（`R28补充报告` §12.1），首次上线即绿，尚未被反向验证过。

---

## 4. P3 条目（清单式）

| # | 位置 | 问题 |
|---|---|---|
| P3-1 | `backend/app/models/__init__.py:13-83`（`_MODULE_MAP` 缺 `sentiment`）+ `backend/app/models/sentiment.py:20` | `SentimentNews` 未进 `_MODULE_MAP`，`main._init_database_tables`（`main.py:512-520`）遍历 `__all__` **不会导入它** → 全新安装的 `create_all` **不建 `sentiment_news`**；实证 `_probe_fresh_start.py`：`HAS_sentiment_news False` + `SENTIMENT QUERY FAILED: no such table`；舆情页（`api/v1/sentiment.py`）在新机器上恒 500。升级路径同样不补（见 D14）。修法：把`SentimentNews` 加入 `_MODULE_MAP`（或让 `_init_database_tables` 用 `pkgutil` 遍历全部模型模块，与 `001_baseline`/`013_bootstrap_baseline` 的既有做法一致）。 |
| P3-2 | `backend/app/services/backup_service.py:606-607` | `_create_snapshots` 的 `uploads_snapshot_<ts>` 目录：`_cleanup_snapshots`/`_rollback_to_snapshots` 只在**正常路径**清理；进程被杀/回滚失败时残留。工作区实测已残留 6 个（`backend/uploads_snapshot_20260830_*…20261017_*`，最早 8/30）。修法：启动时按前缀+保留期清理（与 `db_maintenance` 一起），或改用系统 tmp。 |
| P3-3 | `backend/app/services/immediate_backup.py:33-35, 79-84` | `trigger_immediate_backup` 幂等锁被占用时**返回 False 且静默**；`import_data.py:301`、`supported_village.py:820,1091`、`recycle_bin.py:251,328` **全部不检查返回值**。并发场景（两个管理员同时删/导）下"删后备份"可能根本未执行，而 UI 显示"已彻底删除"。修法：这些调用点改为 `wait=True` 并检查结果；或失败时写审计告警。 |
| P3-4 | `backend/app/api/v1/data/data/data_packages.py:1154-1193` | `delete_data_package` 先删文件再 `db.delete(package)`；删除失败时 `history/package_versions` 仍级联（`package_version.package_id` CASCADE），但 `data_reports.package_id/import_export_history.package_id` 是 SET NULL（`models/data_report.py:41`、`models/import_export_history.py:50`）→ 审计留痕保留（正确），**但文件已先 unlink**、`file_path` 指针在残留历史里指向不存在文件（同 R9 的"文件缺失"形态）。建议 `db.delete` 成功后再 unlink。 |
| P3-5 | `backend/app/services/data_sync_service.py:459-536`（`_import_table_data`）/ `:886-964` | 逐条 raw SQL 导入，**无 SAVEPOINT**：任一条约束失败后 SQLAlchemy session 进入 `PendingRollbackError`，后续所有记录全部失败，但 `result["failed"]` 只 +1、`success` 仍可能为 True（`data_sync.py:244` 直接返回 result）。W2-T7（``.scratch/w2-data-integrity/007-unify-import-pipeline.md`）登记为"ready-for-agent"**至今未修**；与 D4 同型，建议并入 D4 一并整改。 |

---

## 5. 建议的落地批次

**批次 1（P0，必须先做，互相独立可并行）**
1. **D1** —— 数据包导入主键碰撞。这是本批唯一"用户一次正常操作即造成不可逆数据错乱"的条目，建议先补**跨机双库回归用例**（两库各自 id=1 的两条不同记录），再改 upsert 为业务键 + id_mapping。改动面：`data_package_service.py` 的 `_bulk_upsert_records/_build_upsert_statement` + 复用一个 `_remap_ids` 工具（可从 `SmartConflictResolver._update_foreign_keys` 抽出共用）。
2. **D3** —— 导入组织归属。与 D1 同文件、同一函数链，**建议合并到同一 PR**（都涉及 `confirm_import` 与 `SmartConflictResolver` 的租户参数）。D3 顺带把 `confirm-import` 端点补 `require_admin`。
3. **D2** —— 全量导入软删化。改动集中在 `excel_importer_service` 四处 `delete()` + `import_data.py` 的备份时机。**不能与 D1/D3 合并**（不同模块），可并行。

**批次 2（P1，与本批 P0 不冲突）**
4. **D6** —— 回收站单条 purge 数据域（一处 helper 调用，最低风险，可与批次 1 并行）。
5. **D4 + P3-5** —— 导入回执与 raw SQL 导入收敛：建议合并（同一份"导入语义"整改），并一起把 W2-T7 的旧账清掉。
6. **D8** —— PII 两条链口径统一。**需要先定设计**：是"数据包也带密文 + 强制同密钥"（安全，但要求部署规范）还是"数据包明文 + 显式加密口令"（可用性好，需要 UI/审计配合）。建议先出 1 页 ADR，再改代码。
7. **D5** —— 增量包时间戳守卫（`where=` 一行改动 + 用例），可随 D1 一起做（同一个 upsert 语句）。
8. **D7** —— 恢复前置版本校验 + 保留 pre-restore 快照。与 D11 同属"恢复健壮性"，建议**合并为一个批次**：`restore_backup` 前后各加一道校验/留底。

**批次 3（P2/P3）**
9. **D9 + D10** —— 村彻底删除统一到 `CascadePurgeService` + 预览按元数据自动派生。**先定设计**：`SET NULL` 的行（`pairing_records/donation_items`）在预览里如何表达"会被清空去向"。
10. **D11 + D12 + D13** —— 备份/恢复健壮性三项，与批次 2 的 D7 同文件，建议同批。
11. **D14 + P3-1** —— `sentiment_news` 缺失与升级排练覆盖面：P3-1 是**真实功能故障**（新机器舆情页恒 500），建议从 P3 上调到 P1；修法一行（补 `_MODULE_MAP`），但需要配套"全新安装后模型声明表齐全"的门禁用例。
12. **P3-2 / P3-3 / P3-4** —— 清理与返回值检查，可批量处理。

**需要先定设计的（不宜直接改码）**
- D8（PII 跨机策略：同密钥 vs 明文加密包）；
- D9/D10（村删除时 `SET NULL` 子表的语义，以及"预览到底该显示什么"）；
- D7/D11（恢复失败后的产品语义：只回滚？还是允许"半恢复 + 人工介入"？需要明确 UI 文案与快照保留期）。

---

## 附：实证脚本清单（均可复跑）

| 脚本 | 验证条目 |
|---|---|
| `_probe_pk_collision.py` | D1 `overwrite=True` 同 id 覆写 |
| `_probe_item_village.py` | D1 `overwrite=False` `DO NOTHING` 静默丢弃 |
| `_probe_wrong_link.py` | D1 外键错挂 |
| `_probe_fullmode.py` / `_probe_full_village_cascade.py` | D2 物理删除回收站 + 级联删子表 |
| `_probe_org_redirect.py` / `_probe_confirm2.py` | D3 组织越权写 / KEEP_BOTH 丢 org |
| `_probe_count_lie.py` / `_probe_partial2.py` | D4 计数失真 |
| `_probe_incr_reapply.py` | D5 增量包覆盖新编辑 |
| `_probe_purge_scope2.py` | D6 单条 purge 越权 |
| `_probe_newer_schema.py` / `_probe_future_restore.py` | D7 高版本备份恢复 |
| `_probe_pkg_pii_plain.py` / `_probe_xm_export.py` / `_probe_xm_import.py` | D8 PII 明文与跨机不可读 |
| `_probe_fk_graph.py` / `_probe_vp2.py` / `_probe_dangling.py` | D9/D10 村级联清单漂移 |
| `_probe_restore_atomic.py` | D11 回滚失败与半恢复 |
| `_probe_fresh_start.py` / `_probe_old_db_upgrade.py` | P3-1 `sentiment_news` 缺失 |
| `_model_schema.json` / `_alembic_schema.json` / `_diff_schema.py` / `_diff_fk_idx.py` | 两条建库路径（`create_all` vs `alembic upgrade head`）等价性。结论：**共有表的列定义与 FK 零差异**；表集合差 8 张 —— `alembic_version` 外 7 张全为「迁移建过、模型已无」的历史遗留（`comments` / `messages_extended` / `sentiment_keywords` / `sentiment_reports` / `workflow_definitions` / `workflow_instances` / `sentiment_news`）。**`sentiment_news` 是方向相反的真实缺口**：迁移 006 建过它，但模型模块 `app/models/sentiment.py` 未注册进 `_MODULE_MAP` → `create_all` 路径不建表，且升级路径也不会补（见 P3-1/D14）。索引差 3 处（`audit_logs` 两个旧索引 + 两个唯一约束在 create_all 侧带 autoindex 名），无行为影响。 |