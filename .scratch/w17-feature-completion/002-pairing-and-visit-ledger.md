---
labels: [done, severity-high]
blocks: []
blocked-by: []
---

# 002 结对帮扶与走访台账（谁帮谁、帮了什么，可溯明细）

**来源**: 2026-10-17 用户指令「按建议逐一执行」，建议二（优先建议 2）。

**现状**: 全库只有年度板块的两个计数字段（`pairedBranches`、`donatedSchools`），
无「帮扶主体 ↔ 对象」关系实体，无走访/慰问记录。

**What to build**
- 新表：帮扶结对（主体：单位/支部/干部个人；对象：村/学校/学生；起止、状态）
  + 走访记录（时间、人员、事项、照片附件、可选关联项目/经费/物资）。
- 后端：模型 + 迁移 + 服务 + API（envelope、数据域、软删、审计留痕）。
- 前端：结对台账列表/详情 + 走访记录录入（挂村详情、学校详情入口）。

**验收**
- [x] 结对/走访 CRUD 全链路（含数据域隔离与越权 404）
- [x] 村/校详情可按对象聚合展示结对与走访
- [x] 覆盖率与门禁全绿；迁移单 head

## Resolution

**后端**（3 个新文件 + 2 处注册）
- `app/models/pairing.py`：`PairingRecord`（主体 unit/branch/person；对象 village/school/student；
  标题/内容/起止/状态 + `organization_id` + 软删）+ `VisitRecord`（FK CASCADE，
  `organization_id` 随结对继承，防止跨组织写入孤儿走访）。
- `app/services/pairing_service.py`：CRUD + 统计 + 本人/组织域校验（fail-closed 404），
  写操作全部 `write_work_log` 留痕。
- `app/api/v1/pairing.py`：prefix `/pairings`；列表/详情/新增/修改/删除 + `/stats` +
  `/{id}/visits` 子资源（列表为空则回退按 `pairing_id` 查询）；全部 envelope；
  列表支持 `keyword/subject_type/partner_type/partner_id/status`；
  `partner_id` 按对象类型落到 `village_id`/`school_id`。
- `alembic/versions/pairing_001_create_tables.py`（down_revision=reminder_disp_001）：
  新建库走 metadata `create_all`，老库走本迁移；两路径实测 schema 完全一致且幂等（inspector 守卫）。
- 注册：`app/api/v1/__init__.py`（`_BUSINESS_MODULES`，785 路由 / 47 业务模块）、
  `app/models/__init__.py`（`_MODULE_MAP`）、`menus.py`（`pairing` 顶级菜单，order 117）。

**前端**（1 个新 API 模块 + 1 个新视图 + 2 处入口）
- `src/api/pairings.ts`：10 个函数 + 完整类型。
- `src/views/pairing/List.vue`：筛选（关键字/主体/对象/状态）、统计标签、表格、分页、
  新建/编辑对话框、走访抽屉（内联登记/编辑/删除、`EmptyState`）。
  **按对象聚合**：`partner_type` + `partner_id` 组合筛选，命中对象显示「对象：XXX」标签 +
  「清除对象筛选」；对象类型切换自动清空对象 id（避免类型与 id 错配）。
- **深链契约**：`/pairings?partner_type=village|school&partner_id=N`（村/学校详情入口跳转用），
  页面挂载时预填筛选；非法值（未知类型 / 非数字 id / id≤0）静默忽略 → 退化为全量列表，不阻塞页面。
- 入口：`views/schools/Detail.vue`（`partner_type=school`）、
  `views/analytics/supported-villages/Detail.vue`（`partner_type=village`）各加「结对帮扶台账」按钮
  （`pushSafe` 跳深链）；路由 `/pairings`（`meta.menuKey='pairing'`）、`menu-config.ts`（order 18）。

**测试与门禁**
- 后端 `tests/unit/test_pairing_service.py` + `tests/unit/api/test_pairing_api.py`：85 passed，
  3 个新文件行 + 分支 100%。
- 前端 `tests/unit/views/pairing/List.test.ts`（16）+ `tests/unit/api/pairings.test.ts`（11）：
  27 passed；`views/pairing/List.vue` 与 `api/pairings.ts` 四指标 100%
  （含 v-model 编译处理器、深链预填/非法值/清除对象筛选全分支）。
- 学校详情新增入口断言：`tests/unit/views/schools/Detail.test.ts` 点击「结对帮扶台账」→
  `pushSafe('/pairings?partner_type=school&partner_id=3')`；该文件 30 passed 且仍 100%。
- 门禁：`flake8` 0、`scripts/security_audit.py` 0 问题、`check_migrations.py` OK（49 版本 / 单 head `pairing_001`）、
  `check_menu_alignment.py` OK、ESLint 0 errors/0 warnings、`vue-tsc --noEmit` 0；
  `menu-config.test.ts` 计数断言更新（18 顶级 / 55 键）后全绿。

**备注**
- 走访记录的照片附件字段（`attachments` JSON）已落库，附件上传 UI 留待 007（一村一档）统一接入，
  避免两处各写一套上传。
