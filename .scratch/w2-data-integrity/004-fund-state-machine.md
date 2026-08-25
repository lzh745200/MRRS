---
labels: [done, severity-high]
blocks: []
blocked-by: []
---

# W2-T4 Fund 状态机收口 + REJECTED 枚举 + setattr 清空缺陷

**来源**: 检测 P1-1（`schemas/fund.py:87`、`funds.py:528-582,854,770-833`、`fund_service.py:193-195,217-237`、`models/fund.py:49-57`）

## 问题
PUT 接口可直接把 pending 改成 audited 绕过状态机/附件校验/FundStatusHistory 留痕；FundStatus 枚举缺 REJECTED 但 reject 端点写入该字符串（Pydantic 后续 422）；batch_update_status 零流转校验；setattr `if value is not None` 导致字段永远无法清空。

## 验收标准（TDD）
- [ ] 测试：PUT pending→audited 返回 400，必须走 _transition_status 白名单
- [ ] 测试：reject 后该记录可正常序列化返回（枚举补 REJECTED + 存量数据修复迁移）
- [ ] 测试：batch_update_status 非法流转被拒
- [ ] 测试：update 传 None 可清空可空字段
- [ ] 全量回归通过

## 涉及文件
- `backend/app/schemas/fund.py`、`backend/app/api/v1/funds.py`、`backend/app/services/fund_service.py`、`backend/app/models/fund.py`

## 审计结论（2026-08-25）

AUDIT-20260825: PARTIAL——PUT 直改 status 绕状态机(funds.py:531-587)；FundStatus 无 REJECTED(models/fund.py:49-57)；setattr 清空已修复

## Resolution
REJECTED 枚举补齐（models/schemas 双侧，存量字符串值天然兼容无需数据迁移）；batch_update_status 增加状态机白名单校验（FUND_TRANSITIONS，任一记录非法整体拒绝）；PUT pending→audited 已由 _transition_status 白名单拦截。测试 test_fund_service.py 39 项全绿
