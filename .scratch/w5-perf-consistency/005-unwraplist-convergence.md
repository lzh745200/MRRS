---
labels: [ready-for-agent, severity-medium]
blocks: ["w5-perf-consistency/004-envelope-backend-convergence.md"]
blocked-by: []
---

# W5-T5 前端解包收敛 unwrapList<T> + 双请求模式清理

**来源**: 检测 P1-2/P1-3（6 处默认导出残留导入；funds.ts 解包后二次 .data；视图层手写 `?.data?.items ?? items` 散弹式复制）

## 验收标准
- [ ] 全部手写解包替换为 utils/unwrapList 泛型版；ESLint no-restricted-syntax 禁止新增手写模式
- [ ] api/funds.ts 等 6 处默认导出导入改具名包装器；消灭二次 .data（返回类型标注修正）
- [ ] stores/user.ts 过时注释修正
- [ ] vitest / lint / vue-tsc 全绿

## 涉及文件
- `frontend/src/api/funds.ts`、dataSync.ts、organizationPassCode.ts、report.ts、两个 Import.vue、相关视图与 store
