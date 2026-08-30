---
labels: [done, severity-high]
blocks: []
blocked-by: []
---

# W5-T6 数据隔离三合一 fail-closed（ADR-0002）

**来源**: 检测 H1（`unified_data_scope.py:314,324,331` 无组织→is_admin=True；`data_scope_adapter.py:184-198` 缺字段→跳过过滤返回全部行；两处 is_admin 一处不 normalize_role）

## 决策（ADR-0002）
以 data_permission 为唯一实现：模型缺过滤字段 = deny 并抛错（fail-closed）；无组织用户回退 OWN；is_admin 全部走 normalize_role。

## 验收标准（TDD）
- [x] 测试：user 角色 + organization_id=None → 仅见自己记录（非全量）
- [x] 测试：模型缺 organization_id 字段时抛明确异常而非放行
- [x] 测试：历史角色 manager/approval_leader 判定与 data_permission 一致
- [x] unified_data_scope / data_scope_adapter 收敛为委托层，调用点（map/dashboard/school 等）行为回归
- [x] 全量回归通过

## 涉及文件
- `backend/app/core/data_permission.py`、`unified_data_scope.py`、`data_scope_adapter.py`
- `docs/adr/0002-single-data-scope-failclosed.md`

## Resolution（2026-08-30）

**fail-closed 修复落地，数据范围关联回归 247 用例全绿**

1. `unified_data_scope.get_org_scope` 三处"无组织 → is_admin=True"（standalone 模式
   遗留）改为回退"仅本人"（self_only + user_id），is_admin 仅保留管理员角色入口。
2. `data_scope_adapter`：缺组织字段 → 降级"仅本人"；缺 owner 字段 → 抛
   `DataScopeFilterError`（fail-closed），杜绝"缺字段=跳过过滤=返回全量"。
   与主实现 data_permission（getattr 直取、AttributeError 响亮失败）语义对齐。
3. 5 个锁定旧 fail-open 行为的测试改写为 fail-closed 断言（含 org/org_children/
   空组织树/缺字段两形态），新增 ADR-0002 语义锁定。
