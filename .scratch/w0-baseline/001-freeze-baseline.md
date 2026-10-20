---
labels: [done, severity-high]
blocks: []
blocked-by: []
---

# 001: W0 基线冻结：全量测试绿基线与环境预检

**What to build:** 改动前建立前后端全量测试基线；修复全部既有失败；记录耗时基准。

**Acceptance criteria:**
- [x] 后端全量 pytest 通过（既有 15 个失败已归零：签名对齐×6、mock 自环×2、精度断言×3、loopback 桩×1、信封链×2 等）
- [x] 前端 vitest 全量 6669 用例 PASS（基线已达成）
- [x] 观察项记录：batch1/roundtrip 曾单次漂移，连续复测稳定，后续门禁盯梢

## Resolution（W19 完成）

- **后端全量 pytest（含覆盖率门禁）全绿**：
  - 第 1 轮：================ 13929 passed, 1 skipped in 1135.15s
  - 第 2 轮：================ 13929 passed, 1 skipped in 894.17s
  - 覆盖率：**100.00%%**（44877 stmts / 11028 branches，`backend/.coveragerc` `fail_under=100` 达成）。
- **前端全量 vitest**：见 w13-052 Resolution（`vitest run --coverage` 全量通过、12 组 glob 阈值
  statements/branches/functions/lines 全部 100%）。
- **观察项**：历史 `batch1/roundtrip` 顺序漂移已由 w4-007（删除强制排序 + 随机序冒烟）与本轮
  两轮连续全绿锁定；后续门禁以「两轮连续全量 + 覆盖率 100%%」为准，单轮偶发漂移需复测确认。
