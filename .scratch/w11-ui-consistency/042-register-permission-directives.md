---
labels: [ready-for-agent, severity-high]
blocks: ["w12-system-compliance/050-military-compliance-audit.md"]
blocked-by: ["w0-baseline/001-freeze-baseline.md"]
---

# 042: 启用权限指令与水印体系（ADR-0007）

**What to build:** 执行既有工单 w3/001：main.ts 注册 v-permission/v-watermark；系统管理 admin 专属按钮接入；敏感列表（funds/projects/villages）挂水印。

**Acceptance criteria:**
- [ ] user 角色不渲染 admin 按钮（vitest 指令测试既有）
- [ ] watermark 生成与卸载清理断言通过
- [ ] useMenuPermission 接真实菜单权限或删除
- [ ] vue-tsc/lint 绿
