---
labels: [done, severity-low]
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

**完成（2026-08-30，逐项复核结论）**:

knip 288 项逐一复核（词边界全仓 grep，含 tests/electron），**工单前提纠正**：
原文"全仓(含测试)零引用"与事实不符——knip 默认未扫 tests，其中 265 项被各自的
单元测试（tests/unit/api/*.test.ts 等）导入并断言。

处置：
- **删除 2 项**（真零引用）：`userManagementApi` 分组对象（userManagement.ts）、
  `EXPORT_FIELDS` 常量（dataTypes.ts，35 行）+ 孤儿段注释。
- **豁免 265 项**（有引用）：被各自单元测试引用，生产代码零引用。删除需连同
  测试用例一并移除（死测试面专项，影响 ~40 个测试文件的用例结构，超出本票
  "删除导出"范围，另行立项）；按验收标准"删除**或**标注豁免理由"记录豁免。
- **豁免 21 项**（特殊形态且有真实引用）：6 个 `export default`（模块契约）、
  utils/index.ts 桶文件转出口（底层名字经直接路径使用）、echarts-theme 4 常量
  （被测试引用）、getErrorMessage/getFileNameFromResponse 等（视图/spec 引用）。
- **顺带修复存量红测试**：menuKeyAlignment 守卫（W3-T2）因 14d2b243 给
  /data-package/version 路由加可选 :id? 后精确路径匹配失效——守卫测试改为
  感知可选参数段（基础路径对齐），守卫意图不变。

门禁：vue-tsc ✓ / eslint src 零警告 ✓ / vite build ✓ / 全量 vitest
5690 通过 + 上述修复项单跑通过（此前 1 失败即 menuKeyAlignment 存量问题）。

## 验收标准
- [x] 288 个未使用导出逐模块复核后删除或标注豁免理由（2 删 + 286 豁免，理由分类记录）
- [x] 全量门禁绿(vitest/vue-tsc/eslint/build)
