---
labels: [ready-for-agent, severity-high]
blocks: ["w10-enhancements/031-gantt-lightweight.md"]
blocked-by: ["w8-dead-code/013-remove-project-mgmt-page.md"]
---

# 020: 里程碑子系统接线（最大断链）

**What to build:** 项目 Detail.vue 新增「里程碑」Tab：timeline 展示+增删改+完成标记；完成比例联动只读进度展示；调通既有 9 端点。

**Acceptance criteria:**
- [ ] 里程碑 CRUD 全链路 vitest（mock api 层）
- [ ] 完成标记触发进度联动展示
- [ ] upcoming/overdue 仪表盘端点冒烟 pytest 已存在则保持绿
- [ ] 空态 el-empty+去添加指引
