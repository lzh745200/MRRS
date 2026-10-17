---
labels: [ready-for-agent, severity-medium]
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
- 前端：捐赠物资台账页（列表/新建/编辑/删除 + 附件上传）。

**验收**
- [x] 后端：模型 + 迁移（donation_item_001）+ 服务 + API（ok_list 信封、数据域）+ 测试
- [ ] 前端：捐赠物资台账页（列表/新建/编辑/删除 + 附件上传）—— **尚未建成**
- [ ] 与学校详情、项目详情互链（可选挂接展示）
- [x] 覆盖率与门禁全绿（后端）

> **状态（2026-10-17，W18 批次）**：后端已可用（`/api/v1/donation-items`），前端页面与
> `/donations` 路由尚未实现。原实现误在 `DefaultLayoutSafe.vue` 挂了侧边栏入口，
> 点击必然 404，且被 `menuKeyAlignment` 门禁判为"菜单项无对应路由"——已移除该入口。
> 待 UI 落地后：建 `views/donation/List.vue` + 路由 meta.menuKey='donation' +
> menu-config 加项 + 后端 `MENU_DEFINITIONS` 补回（menus.py 已留说明），再挂侧边栏入口。
