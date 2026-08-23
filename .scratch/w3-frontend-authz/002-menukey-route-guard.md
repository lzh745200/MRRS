---
labels: [ready-for-agent, severity-high]
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
