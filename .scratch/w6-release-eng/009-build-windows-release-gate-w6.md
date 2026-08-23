---
labels: [ready-for-agent, severity-high]
blocks: []
blocked-by: []
---

# W6-T9 build-windows 发版门禁（W6 侧复核）

**来源**: 同 W4-T9，本票确保 tag→Release 链路最终状态：smoke-test 绿 → 构建 → 签名 → SHA256SUMS → Release

## 验收标准
- [ ] 与 W4-T9/W6-T1/W6-T5 联合验证一次完整 dry-run（fork/手动触发）
- [ ] Release 说明模板含校验和清单与签名验证说明
