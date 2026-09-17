---
labels: [done, severity-high]
blocks: []
blocked-by: []
---

# 013: 管理面板「用户管理」跳转 404 + 新增用户密码规则与后端策略不一致

**来源**: 用户报障（系统管理 → 管理面板 → 用户管理 卡片点击后进入「页面未找到」404 页）

## 缺陷 1（报障项）：管理面板快捷入口硬编码死链

**根因链**（三层，缺一不可）：

1. 后端 `app/api/v1/menus.py` 的 MENU_DEFINITIONS 中，`users-orgs` 下发
   `"path": "/system/users-orgs"`，而前端路由表**没有**该路径（真实路由是 `/system/users`）。
2. 该漂移只被 `utils/systemMenu.ts` 的 `PATH_OVERRIDES` 在前端兜住 —— 仅对
   「系统管理」动态子菜单生效。
3. `views/admin/AdminDashboard.vue`（管理面板）**绕过**该兜底，硬编码了
   `pushSafe('/system/users-orgs')` 与 `{ path: '/system/users-orgs' }` 两处
   （显然是从后端菜单定义抄的路径），点击即落入 `/:pathMatch(.*)*` 404 通配路由。

同一文件的 `{ path: '/data-management/overview' }`（数据总览）也是同类死链（真实为 `/data-management`）。

**修复**：
- `AdminDashboard.vue`：3 处路径改为真实路由（`/system/users` ×2、`/data-management`）。
- `menus.py`：6 处漂移 path 对齐真实路由（users-orgs / monitor / report-templates /
  data-package-list / data / data-quality），从源头消除漂移。
- `check_menu_alignment.py`：**补上文档字符串早已声明、代码却从未实现的规则 3**
  （后端 MENU_DEFINITIONS 的 path 必须能解析到前端已注册路由）—— 这正是漂移能长期
  存活的原因；对 `health`（与 health-check 同页的冗余项）、`task-package-admin`
  （前端无对应页面）两项显式豁免并注明理由。
- 新增 2 道守卫：`menuKeyAlignment.test.ts` 扫描 src 下**全部硬编码跳转字面量**是否
  可解析（含 alias/可选参数），并断言管理面板 6 个目标命中真实路由。

## 缺陷 2（排查中发现）：新增用户表单密码规则比后端宽松

- 前端 `UserManagement.vue` 规则为 `min: 6`，后端 `PasswordPolicy` 要求
  **≥12 位 + 大小写字母 + 数字 + 特殊字符**（`POST /users` 与 `POST /user-management`
  均强制）。用户填 6~11 位能通过前端校验，却被后端 400 拒绝 → 新增用户"失败"。
- **修复**：前端规则对齐后端（min 12 + 四类字符校验），并补 7 条单测覆盖全部分支。

## 验收证据

- `backend/tests/probe/probe_r15_user_management.py`（新增全链路探针）：
  **39 PASS / 0 FAIL** —— 覆盖两条并行用户接口族（页面用 `/users`、审批页用
  `/user-management`）的列表/新增/编辑/删除/重置密码/分配角色/角色列表，
  含 SQLite 直查落库断言、新密码真实登录、越权 403 与幂等 404 边界。
- 前端全量：**302 文件 / 6063 用例全绿**；后端全量：**10872 用例全绿**。
- `vue-tsc --noEmit` 通过；`eslint --max-warnings=0` 通过；
  `flake8 app/` 0 违例；6 项棘轮门禁 NEW=0；`check_menu_alignment.py` exit=0
  （后端 path 校验 61 项，此前为 0 项）。
- 改动文件覆盖率：`UserManagement.vue` **100%**（语句/分支/函数/行）。

## 附注（未改，供决策）

- 后端 `health`（系统健壮性）与 `health-check` 同页，属冗余菜单项，渲染层按 path 去重；
  当前指向不存在的 `/system/health`，已在门禁中显式豁免，待产品定性。
- `task-package-admin`（任务数据包管理）前端无对应页面（`views/dataPackage/` 无 admin 页），
  同样豁免待功能落地。
