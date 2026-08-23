---
labels: [ready-for-agent, severity-low]
blocks: []
blocked-by: []
---

# W5-T10 上帝组件拆分（第一批）+ 工具函数收敛

**来源**: 检测 P2-1/P2-5（10 个 >1100 行组件；38 个文件重复定义 formatDate；62 处 toLocale*String）

## 验收标准
- [ ] UserManagement.vue 拆为 UserTable/UserFormDrawer/PendingUsersDialog/MenuPermDialog（目标单文件 ≤500 行，行为不变）
- [ ] 新建 utils/datetime.ts（dayjs）+ utils/currency.ts，替换 38 处本地实现
- [ ] ruralWorks/Task.vue 与 funds/Detail.vue 拆分
- [ ] ESLint 禁止视图内新定义 formatXxx
- [ ] vitest / lint / vue-tsc 全绿

## 涉及文件
- `frontend/src/views/system/UserManagement.vue`、ruralWorks/Task.vue、funds/Detail.vue、38 个日期格式化文件
