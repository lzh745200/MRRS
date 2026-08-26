---
labels: [done, severity-high]
blocks: ["w3-frontend-authz/001-register-directives.md"]
blocked-by: []
---

# W3-T2 路由 menuKey 守卫生效

**来源**: 检测 P0-2（`router/guards.ts:65-77` + `router/index.ts` 90+ 路由无一声明 meta.menuKey）

## 问题
菜单级权限检查永不触发——直接输 URL 绕过"菜单可见性配置"。UserManagement 的 /menus/user-menus 配置只影响侧边栏渲染。

## 验收标准（TDD）
- [ ] 盘点菜单 store 的全部 menuKey，为对应路由补 meta.menuKey（与侧边栏键一致）
- [ ] 测试：user 角色直接导航到未授权 menuKey 路由被重定向/403
- [ ] admin/super_admin 全部可访问
- [ ] vitest 全绿

## 涉及文件
- `frontend/src/router/index.ts`、`frontend/src/stores/menu.ts`（键清单单一来源）

## Resolution
- router/index.ts: 为全部 50 个菜单叶子 key 对应路由补 meta.menuKey（与 menu-config.ts 键一致，
  含 3 个无 meta 的重定向路由 /system/user-permissions、/organizations/pass-code、/data-verify、/report-export 手工补 meta）
- router/guards.ts: 将 beforeEach 回调导出为 routeGuard（便于单测），菜单权限检查逻辑不变
- 测试: menuKeyAlignment.test.ts（菜单键↔路由 menuKey 双向对齐）+ guards.test.ts（user 无权限→/403、
  有权限放行、admin 全放行、未登录跳登录）共 6 用例通过
- vue-tsc 干净；menu-config.test.ts 16 用例无回归
- 注: /data-package 菜单配置存在 batch-import 与 data-package-list 同 path 的历史冲突，
  路由 menuKey 取 data-package-list（主列表入口），为 menu-config 既有问题，非本工单引入
