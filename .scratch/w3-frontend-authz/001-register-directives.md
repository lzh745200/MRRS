---
labels: [ready-for-agent, severity-high]
blocks: []
blocked-by: []
---

# W3-T1 启用权限指令与水印体系（ADR-0007）

**来源**: 检测 P0-1（`directives/permission.ts`、`watermark.ts`、`composables/useMenuPermission.ts:2`）

## 问题
v-permission / v-watermark 从未注册也从未使用——按钮级权限与防泄密水印均为死代码。useMenuPermission 是恒真空壳。

## 决策（ADR-0007）
军事场景保留并启用：main.ts 注册两指令；系统管理页 admin 专属按钮接入 v-permission；敏感数据视图（funds/projects/villages 列表与详情）挂 v-watermark。

## 验收标准（TDD）
- [ ] 测试：指令注册后 user 角色渲染不含 admin 按钮；admin 可见
- [ ] 测试：watermark 指令在目标容器生成水印层且卸载时清理
- [ ] useMenuPermission 接入真实菜单权限或删除
- [ ] npm run test -- --run / lint / vue-tsc 全绿

## 涉及文件
- `frontend/src/main.ts`、`frontend/src/directives/*`、系统管理页与敏感列表页
- `docs/adr/0007-frontend-directives.md`
