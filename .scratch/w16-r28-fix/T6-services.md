# T6 服务与数据层正确性（写入范围：backend/app/services/**、backend/app/models/**、backend/app/api/v1/auth/** 之外的服务层调用点、backend/tests/unit/**）
新增测试文件名统一 test_service_correctness_r28*.py。
不得触碰：backend/app/core/**（他人/Lead）、backend/app/api/**（他人，除你确需的最小改动并先报告）、frontend/**、electron/**。
**禁止新增 Alembic 迁移**（发布面，需 Lead 统一协调）；若某条必须加列/改列类型，先报告 Lead 并给方案。

## 待修条目（R27 报告 §2.2 服务与数据层）
- M21 rbac_service.py:318-343 vs :166-191 —— 权限真源分叉：admin 分支提前 return 跳过 restricted_perms，而 check_permission 会拒 → 返回集含会被拒的权限。删提前返回，两条路径共用收敛逻辑。
- M23 secrets_manager.py:21,112-163 —— 密钥版本仅存内存，rotate_key 生成的密钥**不持久化** → 重启后无法解密且版本列表清空。密钥版本落库/落受保护文件（注意：不得新增迁移 → 优先落受保护文件，或复用现有表/配置存储），启动时加载。这是**数据不可逆**级别，务必做真实持久化 + 重启后仍可解密的用例。
- M24 smart_conflict_resolver.py:380 —— KEEP_BOTH 用秒级时间戳后缀 → 同批同 code 撞唯一键。改 uuid/毫秒+序号。
- M25 smart_conflict_resolver.py:544-547 —— 外键重映射不完整（漏 funds.village_id/funds.school_id）→ 跨机导入经费挂到源机 id。补全映射。
- M26 permission_package_service.py:687-696 —— 导入新建组织不写 path → 组织级数据权限失效。建后调 recompute_subtree_paths 或按父链生成（复用 organization_service 既有实现）。
- M27 smart_conflict_resolver.py:194、permission_package_service.py:778/839/870、data_cleaning_service.py:40-54 —— 逐条查库 N+1；deduplicate O(n²) 且每对调 SequenceMatcher → 批量预取 + 先精确分组再模糊。
- M29 data_package_service.py:531-573 —— 覆盖导入会把记录未携带的可空字段写成 NULL（键并集补 None + stmt.excluded 全列更新）→ overwrite 只写本记录实际携带的键。
- M30 approval_workflow_service.py:464-541 —— 审批通过/驳回 check-then-act，无行锁/乐观锁 → 重放可双写审批记录、重复推进级别。加 VersionMixin 或 UPDATE ... WHERE status='pending' 校验 rowcount（SQLite 下用 rowcount 更稳）。
- M31 fund_service.py:177-181 —— 经费创建非原子（两次 safe_commit 补编号），第二次失败留下无 code 记录；年份用本地 date.today().year → 改 flush() + 单次 commit；年份取 utcnow()。
- M32 two_factor_service.py:166-196 —— 双因素启用 check-then-act，并发撞 unique(user_id) → IntegrityError 未捕获 → 500。捕获并回退为更新，或 upsert。
- 复核 M22 resource_limiter.py:171-184（限流永不生效）已由 c7e5501 修 —— 确认无残留。

## 低危（§3 服务层 6 条）
- models/rbac.py:204 AccessLog.user_id 为 String(36) 与全仓 Integer 不一致（R20 未修）→ **不要改列类型**（需迁移）；改为在模型上加注释说明 + 若读取处有 int/str 混用请统一为 str 比较并写用例锁定；方案与风险回报 Lead。
- models/todo.py:31 Todo.deadline 用 String(20) 存日期 → 同上，**不要改列类型**；若服务层有比较/排序逻辑，改为按 ISO 字符串比较并写用例。
- models/two_factor_auth.py:21 TwoFactorAuth.secret_key 未迁到 EncryptedText（R20 相关未修）→ 同上报方案，不直接改列（需迁移 + 存量数据加密回填）。
- system_config_service.py:230 set_initialized 三次提交非原子 → 改单次 commit。
- notification_preference_service.py:39 通知偏好 getter 隐式写库且并发撞唯一键 → getter 只读（缺则返回默认），写入走显式 setter/upsert。
- data_cleaning_service.py:140 地址标准化是空操作（replacements 键值全同）→ 实现真实标准化（省/市/县/乡镇/村 归一），或明确标注未实现并在调用点不谎报“已标准化”。

## 验收
每条：改前行为 + 改后断言；定向 pytest 全绿；改动文件 flake8 0；新增分支 100% 覆盖。
关键回归必须真实落库（SQLite 临时库）而非全 mock：M23（重启后可解密）、M25（外键重映射）、M26（path 生成）、M29（overwrite 不写 NULL）、M30（并发/重放不双写）。