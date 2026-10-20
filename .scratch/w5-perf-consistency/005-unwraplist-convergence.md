---
labels: [done, severity-medium]
blocks: ["w5-perf-consistency/004-envelope-backend-convergence.md"]
blocked-by: []
---

# W5-T5 前端解包收敛 unwrapList<T> + 双请求模式清理

**来源**: 检测 P1-2/P1-3（6 处默认导出残留导入；funds.ts 解包后二次 .data；视图层手写 `?.data?.items ?? items` 散弹式复制）

## 验收标准
- [x] 全部手写解包替换为 utils/unwrapList 泛型版；ESLint no-restricted-syntax 禁止新增手写模式
- [x] api/funds.ts 等 6 处默认导出导入改具名包装器；消灭二次 .data（返回类型标注修正）
- [x] stores/user.ts 过时注释修正
- [x] vitest / lint / vue-tsc 全绿

## 涉及文件
- `frontend/src/api/funds.ts`、dataSync.ts、organizationPassCode.ts、report.ts、两个 Import.vue、相关视图与 store

## Resolution（W19 完成）

- **手写解包已清零**：`frontend/src/utils/unwrapList.ts` 是唯一事实源，全仓 `unwrapList` 引用
  **115 处**；`?.data?.items` / `.data.items` 仅在 util 内部（第 28-31 行，属规则豁免本体）与
  `api/request.ts` 的文档注释中出现。
- **禁止新增手写模式**：`frontend/.eslintrc.cjs` 增加 `no-restricted-syntax`
  （selector `MemberExpression[object.property.name='data'][property.name='items']`），
  并在 `overrides` 中对 `src/utils/unwrapList.ts` 整体关闭该规则（注释说明唯一豁免理由）。
- **api/funds.ts 收敛**：导入改为 `import { get, post, put, del, apiRequest } from '@/api/request'`
  + `import { unwrapList } from '@/utils/unwrapList'`，不再使用默认导出、无二次 `.data`。
- **stores/user.ts 注释修正**：明确「GET /users 返回裸格式 `{total,page,page_size,items}` 或
  envelope 两种形态」，列表分支统一走 `unwrapList(res).items`，无过时说明。
- **验证**：`npx eslint src/config/enums.ts src/views/ruralWorks/Task.vue --max-warnings=0` → exit 0；
  本轮前端全量 vitest / vue-tsc / lint:check 结果见 w13-052 存档。
