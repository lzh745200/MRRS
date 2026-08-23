---
labels: [ready-for-agent, severity-medium]
blocks: []
blocked-by: ["w0-baseline/001-freeze-baseline.md"]
---

# 026: 转账凭证附件上传按钮接线

**What to build:** TransferVoucher.vue 凭证行增加附件上传/查看入口，接 uploadVoucherAttachment 既有端点。

**Acceptance criteria:**
- [ ] 上传后列表可见并可下载（vitest）
- [ ] 非图片类型走下载提示分支
