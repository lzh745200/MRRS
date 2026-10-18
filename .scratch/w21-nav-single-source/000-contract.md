# W21 契约：单一菜单源（方案 C）— 后端菜单 schema v2 + 6 个系统管理聚合页

> 本文件是本批所有实施者的**唯一契约**。任何字段/路径/分组/聚合页映射以本文为准；
> 实施如需偏离，必须先通知 Lead 并同步更新本文。

## 1. 目标

1. **单一菜单源**：`backend/app/api/v1/menus.py` 的 `MENU_DEFINITIONS` 是唯一权威；
   前端侧栏、移动端底部导航、权限面板、权限包菜单树全部由后端下发数据驱动。
   **删除** `frontend/src/config/menu-config.ts`、`frontend/src/utils/systemMenu.ts`
   （及其专属测试），不再维护第二套菜单。
2. **导航重排**：后端按 7 个板块下发（工作台单独固定，不入 sections）：
   帮扶业务、乡村振兴、工作协同、分析汇报、数据管理、系统管理。
3. **系统管理聚合**：24+ 个系统页面收敛为 **6 个聚合入口**（Tabs 页内切换），
   原页面组件全部复用、旧路由全部保留（深链不失效），**菜单 key 一个不改**（权限包兼容），
   另新增 6 个 console key（见 §5）。
4. **导航体验**：菜单搜索（Ctrl+K）、最近访问、收藏（localStorage）。
5. 补入口：汇报大屏 `/bigscreen`、提醒中心 `/reminder`、帮助中心 `/help`、
   数据上报组、批量操作、综合数据录入、成效排名/评估、工作分析、舆情监测、驻村工作台。

## 2. 后端 `/menus/accessible` 响应 v2（单一源）

```json
{
  "success": true,
  "source": "user | pack | role",
  "data": {
    "version": 2,
    "sections": [
      {
        "key": "business", "label": "帮扶业务", "order": 10,
        "items": [
          { "key": "villages", "label": "帮扶村管理", "path": "/supported-villages",
            "icon": "Location", "order": 10, "kind": "page", "roles": null },
          { "key": "funds", "label": "经费管理", "icon": "Money", "order": 40,
            "kind": "group", "roles": ["admin","super_admin","user","viewer"],
            "children": [ { "key": "funds-admin", "label": "经费台账", "path": "/funds",
                            "icon": "Money", "order": 10, "kind": "page", "roles": [...] } ] },
          { "key": "system-console-org", "label": "组织与权限", "path": "/system/console/org",
            "icon": "OfficeBuilding", "order": 10, "kind": "console",
            "roles": ["admin","super_admin"],
            "tabs": [ { "key": "users-orgs", "label": "用户与组织", "path": "/system/users",
                        "icon": "User", "order": 10, "roles": ["admin","super_admin"] } ] }
        ]
      }
    ],
    "flat_keys": ["dashboard", "villages", "users-orgs", "..."]
  }
}
```

字段规则：
- `kind`: `page`（普通页面，必须有 path）| `group`（可折叠分组，必须有 children）| `console`（聚合页，必须有 path + tabs）。
- `path`: page/console 必填；group 不允许。
- `tabs[]`：仅 console；每项 `key/label/path/icon/order/roles`，path 为**旧页面路由**（聚合页内嵌组件，同时保留直达）。
- `roles`: `null` 表示所有角色；否则角色白名单（`normalize_role` 语义）。
- `order`: 同级升序，稳定排序。
- `flat_keys`: 过滤后可见的全部 key（含 group/console 本身 + children + tabs.key），供前端 `canAccessMenu` 与权限面板使用。
- `/menus/all`（管理员）返回**同样结构**（不做用户级过滤，含完整 roles），供权限面板/权限包菜单树。
- 前端 `menuStore` 仍可兼容旧结构（`data` 为数组时按旧树处理，单测覆盖降级分支），但生产只走 v2。

## 3. 过滤规则（`_get_user_accessible_menu_keys` 保持优先级不变）

优先级不变：superuser 全量 > user.allowed_menus > 启用中权限包 > 角色默认；之后并入 `_PUBLIC_ACCESS_KEYS`（政策法规/数据分析公开 key 保持不变）。

新增规则：
- `group` 可见 = 其任一 child 可见；children 裁掉不可见项；children 为空则不出现。
- `console` 可见 = `console.key ∈ allowed` **或** 任一 `tab.key ∈ allowed`；
  tabs 裁剪 = `tab.key ∈ allowed or console.key ∈ allowed`（即：勾了聚合页 key 视为其全部 Tab 可见；
  旧权限配置里只有 tab key 的用户也能看到该聚合页）。
- section 若过滤后 items 为空则不出现。
- `dashboard` 保留为普通 key（页面固定渲染，不在 sections 中）。
- 所有旧 key 保留在定义中（即使不直接出现在 sections 的 items 里，也通过 group children / console tabs 承载），保证权限包/历史 allowed_menus 不失效。

## 4. 板块与条目（最终清单，order 为建议值）

> 工作台（`dashboard`）由前端固定在侧栏顶部渲染，不在 sections。

### business 帮扶业务（order 10）
| key | label | path | kind |
|---|---|---|---|
| villages | 帮扶村管理 | /supported-villages | page |
| projects | 帮扶项目 | /projects | page |
| schools | 帮扶学校 | /schools | page |
| funds | 经费管理 | — | group |
| pairing | 结对帮扶 | /pairings | page |
| donation | 捐赠物资 | /donations | page |
| policies | 政策法规 | /policies | page |
| handover | 工作移交 | /handover | page |

funds group children（保持现有 10 个子项不删，避免功能入口丢失；本次不做经费页整合）：
`funds-admin`(/funds) `funds-user`(/funds/user) `funds-lifecycle`(/funds/lifecycle) `funds-settlement`(/funds/settlement)
`funds-budget`(/funds/budget) `funds-contract`(/funds/contract) `funds-transfer`(/funds/transfer)
`funds-anomaly`(/funds/anomaly) `funds-analysis`(/funds/analysis) `funds-report`(/funds/report)

### rural 乡村振兴（order 20）
| key | label | path | kind |
|---|---|---|---|
| rural-works | 工作首页 | /rural-works | page |
| rural-works-list | 工作列表 | /rural-works/list | page |
| checkin | 驻村工作台 | /rural-works/checkin | page |

### collab 工作协同（order 30）
| key | label | path | kind |
|---|---|---|---|
| todos | 待办事项 | /todos | page |
| approval | 审批管理 | — | group（children：approval `/approval`、approval-pending `/approval/pending`、approval-my `/approval/my`、approval-history `/approval/history`）|
| work-calendar | 工作日历 | /work-calendar | page |
| reminder | 提醒中心 | /reminder | page |
| messages | 消息中心 | /message | page |

### report 分析汇报（order 40）
| key | label | path | kind |
|---|---|---|---|
| bigscreen | 汇报大屏 | /bigscreen | page（新增 key） |
| analytics | 数据分析 | — | group（children：analytics-dashboard `/data-analysis/dashboard`、analytics-map `/data-analysis/map`、work-analysis `/data-analysis/reports`、effectiveness-rankings `/effectiveness/rankings`、effectiveness-evaluate `/effectiveness/evaluate`、sentiment `/sentiment`）|
| report-templates | 报表模板 | /report/templates | page |
| report-export | 报表导出 | /export/report | page |

### data 数据管理（order 50）
| key | label | path | kind |
|---|---|---|---|
| data-overview | 数据概览 | /data-management | page |
| data-sync-export | 数据导出 | /data-sync/export | page |
| data-sync-import | 数据导入 | /data-sync/import | page |
| data-package | 数据包与批量导入 | /data-package | page |
| data-verify | 数据校验 | /data-verify | page |
| validation-rules | 校验规则 | /data-verify/rules | page |
| comprehensive-entry | 综合数据录入 | /data-entry | page |
| batch-operations | 批量操作 | /batch | page |
| data-upload | 数据上报 | — | group（children：data-package-report `/data-package/report`、data-package-receive `/data-package/receive`、data-package-version `/data-package/version`） |

### system 系统管理（order 90，6 个 console）
全部 console 的 `path` = 聚合页路由；`tabs[].path` = 旧页面路由（组件映射见 §5）。

1. `system-console-org` 组织与权限 `/system/console/org`
   tabs：users-orgs `/system/users`、roles `/system/roles`、menus `/system/menus`、
   system-permission-packs `/system/permission-packs`、organizations `/organization`
   （roles/menus 路由若是 redirect，tabs.path 用最终可渲染路由；组件见 §5）
2. `system-console-security` 安全与审计 `/system/console/security`
   tabs：audit `/system/audit`、zero-trust `/system/zero-trust`、secrets `/system/secrets`、
   data-tier `/system/data-tier`、encryption `/system/encryption`、machine-code `/admin/machine-code/management`
3. `system-console-ops` 运维与监控 `/system/console/ops`
   tabs：system-overview `/system/overview`、health-check `/system/health-check`、
   monitor `/system/monitoring`、cache `/system/cache`、tasks `/system/tasks`、
   environment `/system/environment`、error-reports `/system/error-reports`
4. `system-console-storage` 备份与存储 `/system/console/storage`
   tabs：backup `/system/backup`、chunked-upload `/system/chunked-upload`、
   map-tiles `/system/map-tiles`、control-package `/system/control-package`、
   config-package `/system/config`
5. `system-console-settings` 系统设置 `/system/console/settings`
   tabs：i18n `/system/i18n`、email `/system/email`、update-logs `/system/update-logs`
6. `system-console-about` 关于与反馈 `/system/console/about`
   tabs：about `/system/about`、feedback `/system/feedback`、help `/help`、admin-dashboard `/admin/dashboard`

注意：`system-config` / `users-orgs` 等旧 key 与 menu key 的映射见 §5 组件表；聚合页 tab 的 key 必须使用**旧 key**（权限包兼容），console key 为新增。

## 5. 聚合页 Tab → 前端组件映射（SystemConsole.vue 内静态映射）

| tab.key | path | 组件 |
|---|---|---|
| users-orgs | /system/users | views/system/UserManagement.vue |
| roles | /system/roles | views/system/Role.vue（当前路由是 redirect；聚合页直接嵌组件） |
| menus | /system/menus | views/system/Menu.vue |
| system-permission-packs | /system/permission-packs | views/system/PermissionPacks.vue |
| organizations | /organization | views/organization/List.vue |
| audit | /system/audit | views/system/AuditManagement.vue |
| zero-trust | /system/zero-trust | views/system/ZeroTrust.vue |
| secrets | /system/secrets | views/system/SecretsManagement.vue |
| data-tier | /system/data-tier | views/system/DataTier.vue |
| encryption | /system/encryption | views/system/EncryptionSettings.vue |
| machine-code | /admin/machine-code/management | views/admin/MachineCodeManagement.vue |
| system-overview | /system/overview | views/system/SettingsOverview.vue |
| health-check | /system/health-check | views/system/HealthCheck.vue |
| monitor | /system/monitoring | views/system/MonitoringDashboard.vue |
| cache | /system/cache | views/system/CacheManagement.vue |
| tasks | /system/tasks | views/system/TaskManager.vue |
| environment | /system/environment | views/system/EnvCheck.vue |
| error-reports | /system/error-reports | views/system/ErrorReports.vue |
| backup | /system/backup | views/system/BackupManagement.vue |
| chunked-upload | /system/chunked-upload | views/system/ChunkedUploadManager.vue |
| map-tiles | /system/map-tiles | views/system/MapTileManager.vue |
| control-package | /system/control-package | views/system/ControlPackage.vue |
| config-package | /system/config | views/system/ConfigPackage.vue |
| i18n | /system/i18n | views/system/I18nManagement.vue |
| email | /system/email | views/system/EmailSettings.vue |
| update-logs | /system/update-logs | views/system/UpdateLogs.vue |
| about | /system/about | views/system/About.vue |
| feedback | /system/feedback | views/system/Feedback.vue |
| help | /help | views/help/HelpCenter.vue |
| admin-dashboard | /admin/dashboard | views/admin/AdminDashboard.vue |

聚合页路由：`/system/console/:group`（group ∈ org/security/ops/storage/settings/about），
当前 Tab 用 query `?tab=<tab.key>`；切换用 `router.replace`；无权限的 tab 不渲染。
聚合页测试中**必须 stub 上述子组件**（避免同一 .vue 被第二个测试文件真实执行，
违反仓库"单一执行者 + v8 fnMap 合并"规程）。

## 6. 前端契约

- `stores/menu.ts`：
  - 新类型 `MenuSection/MenuEntry/MenuTab`；state：`sections`、`flatEntries`（用于搜索/最近/收藏）、`allKeys`（含 tabs.key）。
  - `canAccessMenu(key)` 语义不变（含 tab key；superuser 旁路不变）。
  - `fetchMenus()` 解析 v2；`fetchAllMenus()` 新增（管理员 `/menus/all`，供权限面板/权限包）。
  - 删除对旧树的依赖；保留"旧数组结构降级"分支与单测。
- `layouts/DefaultLayoutSafe.vue`：
  - 侧栏完全数据驱动：`dashboard` 固定第一 → `v-for sections` → 分组标签 + items（page/group/console 三种渲染）。
  - 顶部（分组上方）显示"收藏"与"最近访问"（有数据时才显示）。
  - Ctrl+K 打开菜单搜索。
  - 删除全部手写菜单段（约 300+ 行）与 `resolveSystemMenuItems` 引用。
- `components/layout/MobileBottomNav.vue`：改数据驱动（工作台 + sections 前 3 个入口 + "更多"抽屉/菜单搜索）。
- 新增 `components/nav/MenuSearchDialog.vue`：搜索 label/key/path（大小写不敏感子串），上下键+回车跳转；空搜索显示收藏+最近。
- 新增 `composables/useRecentMenus.ts`、`composables/useMenuFavorites.ts`：localStorage 键 `nav:recent`/`nav:favorites`，上限 8，损坏数据回退空；单元测试覆盖。
- 权限面板：`components/permission/MenuVisibilityPanel.vue`、`views/system/PermissionPacks.vue`
  改为使用 `menuStore.fetchAllMenus()` 的 v2 sections 渲染三级树（板块→入口→Tab），
  勾选值仍是 key 列表（保存协议不变）。
- **删除**：`frontend/src/config/menu-config.ts`、`frontend/src/utils/systemMenu.ts`、
  `frontend/tests/unit/config/menu-config.test.ts`（或等价文件）、
  `frontend/tests/unit/utils/systemMenu.test.ts`；
  同步清理所有 import 与测试断言。
- 路由（Lead 统一改 `frontend/src/router/index.ts`）：新增 `/system/console/:group`；
  旧路由全部保留（不删组件、不改 redirect 行为）。
- 菜单对齐门禁 `scripts/check_menu_alignment.py` 重写（见 §7）。

## 7. 门禁脚本新规则（scripts/check_menu_alignment.py）

1. 提取后端 `MENU_DEFINITIONS` 的全部条目（含 children / tabs）与前端路由（path + meta.menuKey）。
2. 规则 A：后端每个带 path 的条目（含 tabs.path）必须命中前端已注册路由；否则 FAIL。
3. 规则 B：前端每个 `meta.menuKey` 必须存在于后端 key 集合（含 tabs.key）；否则 FAIL。
4. 规则 C：后端每个 key 必须"被前端消费"——满足任一：① 某路由 `meta.menuKey` 命中；② 是 group/console 且其子项命中；③ 是 console 的 tab 且对应 path 路由存在。否则 FAIL（防孤儿 key）。
5. 规则 D：同一条路径不得出现两个菜单入口（page/group children/tabs 全局唯一，`/system/help` 这类 redirect 除外）；否则 FAIL。
6. 规则 E：section key 唯一、section 内 order 单调（允许重复但 WARN）。
7. 退出码语义不变（0 通过 / 1 失败）；CI 调用方式不变。

## 8. 测试与覆盖率硬约束

- 后端：`menus.py` 改动后 `--cov=app.api.v1.menus --cov-branch` 语句/分支 100%；
  新增/更新 `backend/tests/unit/test_menus*.py`（sections 组装、过滤、console 可见性、tabs 裁剪、`/menus/all`、角色默认、权限包、公开 key、空数据、异常分支）。
- 前端：新增/修改文件在 `src/views/**/*.vue`、`src/components/**`、`src/composables/**`、`src/stores/**`、`src/layouts/**`
  12 组 glob 覆盖门禁内，四指标 100%。
- **单一执行者规程**：同一 `.vue` 全仓只能被一个测试文件执行（含 bare import）。
  - `SystemConsole.vue` 由 `tests/unit/views/system/SystemConsole.test.ts` 执行，**必须 stub 全部 Tab 子组件**；
  - `DefaultLayoutSafe.vue` 由现有 layout 唯一测试执行（T2 负责确认/合并）；
  - 新增 `MenuSearchDialog.vue` 专属测试（不得在其他测试 import）；
  - 不要在其他测试里 bare import 被聚合页内嵌的 .vue。
- 本次删除的测试文件要同步从任何 `vi.mock`/import 中清理。

## 9. 文件权属（并行写作用域，禁止越界）

| 责任方 | 允许修改的文件 |
|---|---|
| backend-menu | `backend/app/api/v1/menus.py`、`scripts/check_menu_alignment.py`、`backend/tests/unit/test_menus*.py`（+新增测试） |
| frontend-nav | `frontend/src/stores/menu.ts`、`frontend/src/layouts/DefaultLayoutSafe.vue`、`frontend/src/components/layout/MobileBottomNav.vue`、`frontend/src/components/nav/MenuSearchDialog.vue`、`frontend/src/composables/useRecentMenus.ts`、`frontend/src/composables/useMenuFavorites.ts`、`frontend/src/config/menu-config.ts`（删除）、`frontend/src/utils/systemMenu.ts`（删除）、上述文件对应测试 |
| frontend-console | `frontend/src/views/system/console/SystemConsole.vue`（+测试）、`frontend/src/components/permission/MenuVisibilityPanel.vue`、`frontend/src/views/system/PermissionPacks.vue`（+对应测试） |
| Lead | `frontend/src/router/index.ts`、`package.json`/版本、`CHANGELOG.md`、全部文档/PPT、最终集成与门禁 |
| docs-ppt | `docs/**`、`README.md`、`CLAUDE.md`、`.scratch/w21-nav-single-source/**`（不含 CHANGELOG 与版本文件） |

## 10. 版本

目标版本 **1.13.0**（导航架构重构，向后兼容）。`node scripts/sync-version.js --write v1.13.0`。
