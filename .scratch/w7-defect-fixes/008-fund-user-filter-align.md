---
labels: [done, severity-high]
blocks: []
blocked-by: ["w0-baseline/001-freeze-baseline.md"]
---

# 008: 经费申请页过滤参数对齐

**What to build:** UserFundList fetchData 参数 search/type→keyword/fund_type 对齐后端 list_funds。

**Acceptance criteria:**
- [ ] 关键词与类型过滤真实生效（vitest 断言请求参数名）
- [ ] 状态筛选保持可用

## Resolution（v1.10.0）
keyword/fund_type对齐
