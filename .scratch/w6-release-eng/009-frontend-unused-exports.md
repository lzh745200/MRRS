---
labels: [ready-for-agent, severity-low]
blocks: []
blocked-by: []
---

# W9-T1: 前端未使用导出清理(knip 扫描遗留项)

**来源**: 2026-08-29 死代码清理 Phase 6 knip 兜底扫描。
文件级/依赖级死代码已在同批清理中处理完毕(见 CHANGELOG 2026-08-29),
本工单处理**导出级**残留: 约 288 个 src/api/* 导出函数全仓(含测试)零引用。

## 背景
这些导出是对后端端点的类型化封装,后端端点存活,但前端从未调用。
删除它们不改变运行时行为,只缩小 API 面并降低维护成本。

## 执行要点
1. knip 完整清单见会话产物 `knip_exports.txt`(或重跑 `npx knip --no-progress`)。
2. 逐模块处理前先 `grep -rn "exportName" src tests` 复核(防 knip 漏判
   `import * as` / 动态访问)。
3. 优先级建议: analytics.ts(12+) > approval.ts(8+) > 其余。
4. 删除后跑 `npm run test -- --run` + `vue-tsc --noEmit` + `npm run build`。

## 注意(勿删, knip 误报)
- `src/styles/tokens-vars.scss` — vite.config additionalData 注入
- `@typescript-eslint/*`、`@vue/test-utils`、`lint-staged`、`eslint-config-prettier` —
  eslint/vitest 配置消费, knip 无配置时误报
- `stores/user.ts` — 生产存活(8 处引用)

## 验收标准
- [ ] 288 个未使用导出逐模块复核后删除或标注豁免理由
- [ ] 全量门禁绿(vitest/vue-tsc/eslint/build)
