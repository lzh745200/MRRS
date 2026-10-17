---
labels: [ready-for-agent, severity-medium]
blocks: []
blocked-by: []
---

# 008 AI 结论可解释 + 业务数据体检（说真话）

**来源**: 2026-10-17 用户指令「按建议逐一执行」，建议八（最后一公里 3）。

**现状**: `ai.py` / `ai_enhanced.py` 提供预测/异常/推荐/问答，但结论无依据字段与
算式；「系统体检」只覆盖基础设施，业务数据质量靠独立页面。

**What to build**
- 可解释：AI 响应增加 `rationale`（依据字段、窗口、算式或规则说明）与
  `data_scope`（参与计算的数据量/范围），前端展示「为什么」。
- 业务体检：新增 `GET /system/business-health`（管理员）：村年度缺失清单、
  金额逻辑矛盾（used>amount、负数）、长期未动项目/经费、组织归属缺失等，
  逐项给入口与数量；不返回任何 PII。

**验收**
- [ ] 各 AI 端点 rationale 覆盖（不含模型幻觉式自由文本，均为结构化依据）
- [ ] 业务体检端点空库/满库均可用；扫描 SQL 不含原始 f-string 拼接
- [ ] 覆盖率与门禁全绿
