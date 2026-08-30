# ADR-0003: 组织删除级联守卫

- 状态：Accepted（2026-08-30，W2-T2 实施）
- 关联工单：`.scratch/w2-data-integrity/002-org-delete-guard.md`

## 背景

组织→项目的外键为 `ondelete=CASCADE`，而项目→资金/合同/凭证同为级联。
任何对组织行的硬删除（服务层 `organization_service.delete_organization` 为
物理删除 API）都会沿级联链把项目、资金、合同、凭证一并物理删除，且删除前
不检查名下引用。数据完整性红线。

## 决策

1. **应用层引用守卫**：`delete_organization` 硬删除前检查名下
   项目/用户（`OrganizationInUseError`，错误信息含各类计数清单），
   与既有 `OrganizationHasSubordinatesError`（子组织守卫）并列。
2. **外键对齐**：`projects.organization_id` 的 `ondelete` 由 CASCADE 改为
   **SET NULL**（列可空，与其他实体指向组织的行为一致），迁移
   `org_guard_001` 以 SQLite batch + reflect + naming_convention 官方配方重建表。
   即便未来出现绕过应用层的硬删，DB 层也不会再级联抹掉项目链。
3. API 端点 `DELETE /organizations/{id}` 维持软删除（is_active=False）语义不变。

## 后果

- 硬删组织前必须先迁移/清理名下项目与用户（应用层 400/422 提示计数）。
- 组织被硬删后，遗留项目的 `organization_id` 为 NULL（历史数据保留，
  由数据范围过滤按"无组织"处理）。
