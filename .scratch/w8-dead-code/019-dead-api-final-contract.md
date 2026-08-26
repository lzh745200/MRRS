---
labels: [done, severity-low]
blocks: []
blocked-by: ["w9-chain-completion/021-reimbursement-ui.md", "w9-chain-completion/022-budget-alert-3level.md", "w9-chain-completion/023-policy-fts-wiring.md", "w9-chain-completion/026-voucher-attachment-upload.md"]
---

# 019: 死 API 收尾 contract

**What to build:** 删除最终仍无消费方的 api 层函数（fundFlow/getFundFlowTree/getBudgetSummary 等以当期 grep 为准）；保留未来一版内可能接线者加注释豁免清单。

**Acceptance criteria:**
- [ ] 删除清单逐项 grep 全仓零调用
- [ ] 前端构建+全量测试绿
- [ ] api 层无未使用导出（eslint 未用导出规则或脚本核验）

## Resolution（v1.10.0 续批9）
getBudgetSummary/fundFlow 等已随 W7-W10 各批删除；searchPolicies 保留(有契约测试 policyRuralWork.test)；uploadVoucherAttachment/listTransactions 已由 T026/T021 接线转活。残留豁免清单=零
