---
labels: [ready-for-agent, severity-critical]
blocks: []
blocked-by: []
---

# W2-T2 组织删除级联守卫（ADR-0003）

**来源**: 检测 P0-3（`organization.py:47-52,87-92` + `organization_service.py:352-363`）

## 问题
删除组织 → 子组织 CASCADE 连带物理删除 → 其下 projects 物理删除 → funds/合同/凭证/决算 DB 级联硬删。删除前不检查名下项目/用户/机器码；Project 的 ondelete=CASCADE 与其他实体 SET NULL 不一致。

## 验收标准（TDD）
- [ ] 测试：组织下存在项目时删除返回 400（错误信息含各类计数清单），复用 OrganizationHasSubordinatesError 模式
- [ ] 测试：空组织（无项目/用户）删除成功且子组织一并处理
- [ ] 迁移：Project.organization_id 改 SET NULL 对齐其他实体
- [ ] 全量回归通过

## 涉及文件
- `backend/app/services/organization_service.py`
- `backend/app/models/project.py` + 新 alembic 迁移
- `docs/adr/0003-org-delete-guard.md`
