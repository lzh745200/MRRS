---
labels: [done, severity-medium]
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
- [x] 各 AI 端点 rationale 覆盖（不含模型幻觉式自由文本，均为结构化依据）
- [x] 业务体检端点空库/满库均可用；扫描 SQL 不含原始 f-string 拼接
- [x] 覆盖率与门禁全绿

## Resolution（2026-10-17，W19 完成）

- **可解释**：`ai.py` 新增 `build_rationale` / `build_data_scope` / `year_window` 基础设施，
  10 个 AI 端点（/ai/* 5 个 + /ai-enhanced/* 5 个）统一返回结构化 `rationale`
  （version/method/basis_fields/window/formula/rules/assumptions）与 `data_scope`
  （dataset/scope/row_count/granularity/window/filters/counts）；数据不足如实置 None/0，不编造结论文本。
  前端 `views/ai/InteractiveResult.vue` 增加「为什么 · <本次分析>」面板（方法/依据字段/窗口/算式/规则/假设）。
- **业务体检**：`app/services/business_health_service.py` + `GET /api/v1/system/business-health`（管理员）：
  8 项（村年度缺失[收益/人口]、经费 used>amount、金额负数、长期未动项目/经费、村/项目/经费组织归属缺失），
  每项 count + 前端入口 + 截断明细；只出 id/状态/金额/时间，**无 PII**；空库/满库均 200；
  全部 ORM 表达式（无 `text(f"...")` 拼接）。
- 契约变更：/ai-enhanced 的 anomaly-detection 与 recommendations/projects 由裸 list/dict 改为结构化信封。

**验证**：后端相关 212 项测试全绿，5 个改动模块行+分支 100%；前端 92 项测试、两文件四指标 100%；
空库/满库、PII 不出现、管理员门禁均有断言；`security_audit.py --strict` 0 issues。
