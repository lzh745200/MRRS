---
labels: [ready-for-agent, severity-high]
blocks: []
blocked-by: ["w0-baseline/001-freeze-baseline.md"]
---

# 013: 删除 ProjectManagement 冗余页 + 主列表补列

**What to build:** 删除 ProjectManagement.vue 与 /projects/management 路由及其测试引用；List.vue 补所属村名/开始结束时间列（后端已返回）。

**Acceptance criteria:**
- [ ] 路由与文件移除、grep 无残留引用
- [ ] 主列表新列渲染（vitest 快照更新）
- [ ] 全量前端测试保持绿
