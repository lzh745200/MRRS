---
labels: [done, severity-medium]
blocks: []
blocked-by: ["w0-baseline/001-freeze-baseline.md"]
---

# 026: 转账凭证附件上传按钮接线

**What to build:** TransferVoucher.vue 凭证行增加附件上传/查看入口，接 uploadVoucherAttachment 既有端点。

**Acceptance criteria:**
- [ ] 上传后列表可见并可下载（vitest）
- [ ] 非图片类型走下载提示分支

## Resolution（v1.10.0 续批3）
操作列内嵌 el-upload(http-request 接管)调 uploadVoucherAttachment；上传中按行 loading。TSC=0，TransferVoucher+api 套件 1015 绿
