# 006 R23：认证会话契约 + 帮扶村列表排序 两处根因修复

- 波次: w14-deep-probe
- 日期: 2026-09-10
- 版本: 1.12.1
- 状态: 已修复并验证

## 缘起
R22 全量套件收官时残留 **3 例失败**（`r22-fullsuite2.txt`：
`3 failed, 10728 passed in 696s`），均在 `get_current_user` 直调路径；同时产品侧
反馈「帮扶村新建成功后列表看不到新记录」。R23 对二者定位到根因并修复。

## 缺陷 1：认证出口「直接调用」路径崩溃（潜在生产 500）
- 现象：`tests/unit/test_two_factor_security_r19.py::...test_explicit_false_claim_is_allowed`
  等 3 例报 `AttributeError: 'Depends' object has no attribute 'query'`（`security.py:322`）。
- 根因：P1-2 将 `get_current_user` 由"自建 `SessionLocal()`"改为
  `db: Session = Depends(get_db)` 注入会话后，**直接调用**方不会触发依赖注入，
  `db` 保持为 `Depends(get_db)` 哨兵对象。
- 影响面（**测试之外的真实生产缺陷**）：
  `app/api/v1/system/backup.py::_jwt_user_from_request` 也是直调
  `get_current_user(HTTPAuthorizationCredentials(...))` → 走 Bearer JWT 的备份
  接口（非 Electron 内部密钥通道）会 500。此前未被测试捕获，因备份用例多走
  `dependency_overrides` 或内部密钥。
- 修复（`app/core/security.py`）：`_owns_session = not isinstance(db, Session)`；
  未注入则自建会话、`finally` 关闭；注入则复用且不关闭。
- 回归：`tests/unit/test_get_current_user_session_contract_r23.py`（3 例，
  含备份生产路径 `_jwt_user_from_request` 直调断言）。

## 缺陷 2：帮扶村新建成功却看不到新记录
- 现象：新建提交 → 前端提示成功并重置到第 1 页 → 列表无新行。
- 根因：`GET /supported-villages` 固定 `order_by(SupportedVillage.id)` **升序**，
  新记录 id 最大、落在最后一页；且端点**未声明** `sort_by`/`sort_order`，前端部门列
  `sortable="custom"` 下发的排序参数被 FastAPI 静默丢弃。
- 修复（`app/api/v1/supported_village.py`）：
  ① 新增 `sort_by`/`sort_order` 查询参数；② `_SORTABLE_COLUMNS` 白名单
  （camelCase prop 与 snake_case 列名都登记，杜绝 `getattr` 越界到非列属性）；
  ③ `_resolve_village_sort()` 默认 `id` 倒序（最新在前），非法列安全回退；
  ④ 缓存 key 纳入排序维度。与 `projects.py`（默认 `Project.id.desc()`）约定对齐。
- 回归：`tests/unit/test_supported_village_sort_r23.py`（4 例：默认最新在前 /
  显式部门升序降序 / camelCase prop 映射 / 非法列回退）。

## 验证
- 后端：`pytest tests/` 全量；
- 前端：`vue-tsc --noEmit` 0 错、`vitest run` 全绿、`eslint` 0 warning；
- `flake8 --max-line-length=120` 改动文件 0。

## 未处理（记录备查，不在本轮夹带）
- R22 审计扫描残余 34 条启发式告警（15 bare `db.commit()`、7 缺 `write_work_log`、
  12 `filter_by_data_scope` 提示）——多为 admin/system 端点或设计选择，
  按仓库既有「先判缺陷、观察项立此存照」文化，留待专门轮次逐条判定。
- `004-backlog-deferred-features.md` 五项计划内未完成功能维持 deferred。
