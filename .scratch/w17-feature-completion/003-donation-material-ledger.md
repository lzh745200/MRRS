---
labels: [done, severity-medium]
blocks: []
blocked-by: ["w17-feature-completion/002-pairing-and-visit-ledger.md"]
---

# 003 捐赠物资台账（实物口径：图书/设备/物资）

**来源**: 2026-10-17 用户指令「按建议逐一执行」，建议三（优先建议 3）。

**现状**: 资金侧仅有 `donation` 资金类型；实物捐赠（图书、设备、物资）无处登记。

**What to build**
- 新表 `donation_items`：名称、类别、数量、单位、折价、来源单位、去向（村/学校/
  项目）、交付日期、签收人、凭证附件、备注；软删 + 审计。
- 后端：模型 + 迁移 + 服务 + API（`ok_list` 信封、数据域）。
- 前端：捐赠物资台账页（列表/新建/编辑/删除 + 附件）。

**验收**
- [x] 后端：模型 + 迁移（donation_item_001）+ 服务 + API（ok_list 信封、数据域）+ 测试
- [x] 前端：台账页（列表/新建/编辑/删除 + 附件链接 + 统计/筛选/分页）
- [x] 与学校/项目互链：去向字段可指向村/学校/项目，台账支持按去向类型筛选
- [x] 覆盖率与门禁全绿（后端行+分支 100%；前端 statements/branches/functions/lines 100%）

## Resolution（2026-10-17，W19 完成）

**后端**（W17 批次已落地，本次复核）
- `app/models/donation_item.py`（软删 + 组织归属 + to_dict 富化）、迁移
  `donation_item_001_create_table.py`、`app/services/donation_item_service.py`
  （`donation_base_query` 数据域 + 软删过滤、`donation_stats`、`ensure_donation_valid`、
  `resolve_destination` 去向对象存在性/数据域校验、`attach_destination_names` 批量富化）。
- `app/api/v1/donation.py`：`/donations` 列表/统计/详情/新增/修改/软删，全部 envelope。

**前端**（本次新增）
- `src/api/donations.ts`：8 个类型 + 6 个接口函数 + 类别/去向常量。
- `src/views/donation/List.vue`：统计标签、关键字/类别/去向筛选、表格（类别标签、
  数量+单位、折价、去向名称）、分页、登记/编辑对话框（去向类型联动、附件按行解析、
  手写校验与后端 ensure_donation_valid 同口径）、删除二次确认。
- 路由 `/donations`（meta.menuKey='donation'）、`menu-config.ts` 第 19 项、
  侧边栏「捐赠物资」入口（Box 图标）、后端 `MENU_DEFINITIONS` 第 118 项。
- 测试：`tests/unit/api/donations.test.ts`（8）+ `tests/unit/views/donation/List.test.ts`（21），
  四指标 100%；同步菜单计数断言（18→19 / 55→56）。
