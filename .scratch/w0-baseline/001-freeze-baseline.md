---
labels: [ready-for-agent, severity-high]
blocks: []
blocked-by: []
---

# 001: W0 基线冻结：全量测试绿基线与环境预检

**What to build:** 改动前建立前后端全量测试基线；修复全部既有失败；记录耗时基准。

**Acceptance criteria:**
- [ ] 后端全量 pytest 通过（既有 15 个失败已归零：签名对齐×6、mock 自环×2、精度断言×3、loopback 桩×1、信封链×2 等）
- [ ] 前端 vitest 全量 6669 用例 PASS（基线已达成）
- [ ] 观察项记录：batch1/roundtrip 曾单次漂移，连续复测稳定，后续门禁盯梢
