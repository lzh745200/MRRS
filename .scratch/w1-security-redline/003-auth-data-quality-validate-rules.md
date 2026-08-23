---
labels: [ready-for-agent, severity-critical]
blocks: []
blocked-by: []
---

# T3 data_quality validate-rules 补认证与组织过滤

**来源**: 检测 S-3（`data_quality.py:125-148`）

## 问题
未认证 POST 可枚举全库村/经费/项目/学校记录（record_id+名称），无 organization_id 过滤。

## 验收标准（TDD）
- [ ] 测试：匿名 POST `/validate-rules` 返回 401
- [ ] 测试：user 角色仅收到本组织记录的校验结果（构造跨组织数据断言不可见）
- [ ] admin 行为不变（OWN_DEPT 语义，走 normalize_role）
- [ ] 全量回归通过

## 涉及文件
- `backend/app/api/v1/data_quality.py`
- `backend/tests/unit/api/test_data_quality_auth_scope.py`（新建）

## Resolution（2026-08-23）

**已修复，TDD 全绿（新增 5 测试 + 既有 6 回归）**

1. `/validate-rules` 补 `get_current_active_user` 认证（匿名 → 401）
2. 查询接入 `filter_by_data_scope()`：admin=OWN_DEPT 仅本组织、user=OWN、super_admin=ALL（语义锚点测试防回归）
3. 旧覆盖率测试文件补 super_admin 认证桩 + 修复"第一个 override 键取 db"的脆弱技巧

测试：`backend/tests/unit/api/test_data_quality_auth_scope.py`
