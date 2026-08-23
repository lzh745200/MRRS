---
labels: [ready-for-agent, severity-high]
blocks: ["w13-docs-release/051-docs-update-adrs.md"]
blocked-by: ["w11-ui-consistency/042-register-permission-directives.md", "w12-system-compliance/044-backup-unify-truth-source.md", "w12-system-compliance/047-init-reset-hardening.md"]
---

# 050: 军规合规终检（发布门禁）

**What to build:** PII 三通道扫描（API 响应/Excel 导出/日志）→ 缺口补脱敏或加密；EncryptionService 接线核查（银行卡等）；desensitize.ts 覆盖清单对照安全五项 checklist 逐条签字归档 Resolution。

**Acceptance criteria:**
- [ ] 扫描脚本输出零高危（脚本入库 scripts/security/pii_scan.py）
- [ ] checklist 五项在 Resolution 逐条勾稽
- [ ] 发现缺口当场修复或开新票不得带病发布
