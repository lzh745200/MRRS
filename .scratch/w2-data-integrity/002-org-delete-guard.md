---
labels: [done, severity-critical]
blocks: []
blocked-by: []
---

# W2-T2 组织删除级联守卫（ADR-0003）

**来源**: 检测 P0-3（`organization.py:47-52,87-92` + `organization_service.py:352-363`）

## 问题
删除组织 → 子组织 CASCADE 连带物理删除 → 其下 projects 物理删除 → funds/合同/凭证/决算 DB 级联硬删。删除前不检查名下项目/用户/机器码；Project 的 ondelete=CASCADE 与其他实体 SET NULL 不一致。

## 验收标准（TDD）
- [x] 测试：组织下存在项目时删除返回 400（错误信息含各类计数清单），复用 OrganizationHasSubordinatesError 模式
- [x] 测试：空组织（无项目/用户）删除成功且子组织一并处理
- [x] 迁移：Project.organization_id 改 SET NULL 对齐其他实体
- [x] 全量回归通过

## 涉及文件
- `backend/app/services/organization_service.py`
- `backend/app/models/project.py` + 新 alembic 迁移
- `docs/adr/0003-org-delete-guard.md`

## 审计结论（2026-08-25）

AUDIT-20260825: MISSING——delete_organization 仅查下级组织；Project.organization_id 仍 CASCADE(organization_service.py:333-363 / project.py:87-92)

## Resolution（2026-08-30，提交 34f7d7f8）

1. `organization_service.delete_organization` 硬删除前检查名下激活项目/用户
   （新 `OrganizationInUseError`，错误信息含计数清单），子组织守卫保持在前。
2. `Project.organization_id` 外键 CASCADE → SET NULL（模型 + 迁移 org_guard_001，
   SQLite 匿名外键采用影子表舞步重建），API 软删除语义不变。
3. 附带修复 fk_ondelete_001（W2-T5）全新库必败缺陷：SQLite 检查器不回传
   ondelete 导致幂等判断恒真 + 匿名外键按合成名 batch drop 必败——改为直读
   建表 DDL 判定 + 同款影子表舞步。
4. 验收测试 4/4（守卫计数/空组织可删/DB 层 SET NULL 实证/元数据防漂移）；
   完整 alembic 链从零升级到 head 验证通过（integrity_check ok）。
