---
labels: [done, severity-medium]
blocks: ["w12-system-compliance/044-backup-unify-truth-source.md"]
blocked-by: ["w0-baseline/001-freeze-baseline.md"]
---

# 025: 经费编号 ZJ 自动生成

**What to build:** 创建经费 code 为空时后端自动生成 ZJ+YYYY+6 位流水（flush 后取 id 序，参照 ORG 模式）；唯一约束兜底并发。

**Acceptance criteria:**
- [ ] 编号格式 pytest（ZJ2026000001 形态）
- [ ] 并发创建唯一性（同毫秒随机后缀策略若需）
- [ ] 手输编号不被覆盖
- [ ] ADR-0011 落稿

## Resolution（v1.10.0 续批）
ZJ+年份+6位流水(flush后id序,手输不覆盖)+2测试
