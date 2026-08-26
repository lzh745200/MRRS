# ADR-0007: 前端权限指令与防泄密水印体系启用

- 状态：Accepted
- 日期：2026-08-26
- 关联工单：W3-T1 / W11-042

## 背景

`directives/permission.ts`（v-permission 四模式：角色数组/权限码/菜单 key/模块 view-edit）
与 `directives/watermark.ts`（v-watermark 防截图泄密水印）实现完成后长期未注册、
未被任何视图使用——按钮级权限与防泄密水印为死代码。军事场景下敏感数据
（经费/项目/帮扶村）存在截图外泄风险。

## 决策

**保留并启用**（非删除）：

1. `main.ts` 全局注册两个指令；
2. 系统管理页 admin 专属操作区接入 `v-permission="['admin','super_admin']"`
   （与既有 `v-if="isAdmin"` 形成双保险——指令在 updated 钩子还会响应角色切换）；
3. 敏感数据列表页（funds/projects/supported-villages）挂 `v-watermark`
   （默认取当前用户名+日期，可自定义文本）；
4. `useMenuPermission()` 从恒真桩改为委托 `menuStore.canAccessMenu`，
   与路由守卫、`v-permission="{ menu }"` 共用同一判定源。

## 后果

- 正面：按钮级权限有了统一出口；敏感列表带泄密追溯水印；权限判定单一来源。
- 负面/约束：
  - 测试环境不全局注册指令（jsdom + pinia 缺失会抛错），依赖 setup.ts 对
    "Failed to resolve directive" 告警的抑制——新视图测试如断言 admin 按钮可见性
    需 mock auth store 而非依赖指令执行。
  - 水印 canvas 在 jsdom 无真实实现，仅样式层验证。

## 验证

- `tests/unit/directives/*` 指令单测（注册/移除元素/updated 显隐）；
- `tests/unit/composables/useMenuPermission.test.ts` 三分支；
- 视图冒烟：admin/user 双角色渲染差异由各页既有测试覆盖。
