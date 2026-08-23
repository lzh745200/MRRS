# CONTEXT.md — 帮扶管理信息系统（MRRS）

> 领域词汇与不变量。做非平凡改动前通读一遍；发现冲突事实须在同一次变更中更新本文件。

## 系统定位

完全**离线单机**的桌面应用：军队/地方联合帮扶乡村。FastAPI 后端 + Vue 3 前端 + Electron 壳 + SQLite。
多机之间通过"数据包"（导出 ZIP → 人工携带 → 导入）协同，无中心服务器。

## 核心领域概念

| 概念 | 说明 | 关键模块 |
|------|------|----------|
| 帮扶村 (SupportedVillage) | 受援行政村，含人口/收入/11 类年度帮扶数据子表 | `backend/app/models/supported_village.py` |
| 项目 (Project) | 帮扶项目，挂组织与村 | `models/project.py` |
| 经费 (Fund) | 资金记录，有状态机 pending→planned→...→audited | `models/fund.py`, `api/v1/funds.py:_transition_status` |
| 审批流 (ApprovalWorkflow) | 通用审批任务，节点可按角色或指定人 | `services/approval_workflow_service.py` |
| 组织 (Organization) | 树形结构，数据隔离的根，level_1~level_5 | `models/organization.py` |
| 机器码 (MachineCode) | 设备指纹，激活授权依据 | `services/machine_code_service.py` |
| 通行码 (PassCode) | HMAC 绑定机器码的激活凭证 | 同上 |
| 数据包 (DataPackage) | 跨机同步载体：全量/增量 ZIP，可加密(.rrs) | `services/data_package_service.py`, `data_sync_service.py` |
| 权限包 (PermissionPackage) | 离线分发的权限配置包 | `api/v1/permission_package.py` |

## 不变量（违反即缺陷）

1. **数据隔离**：一切业务查询必须经过组织范围过滤（`filter_by_data_scope` / `apply_scope_filter`）。语义：`user`=OWN，`admin`=OWN_DEPT，`super_admin`=ALL；角色先过 `normalize_role()`。
2. **fail-closed**：鉴权、加密、限流的任何前置条件缺失时拒绝操作，绝不放行。
3. **envelope 响应**：新端点一律 `success_response()` / `ok_list()`（`core/response.py`）。
4. **软删除**：核心业务模型用 `is_active` + `deleted_by`；审计类记录永不物理删除。
5. **审计留痕**：写操作调用 `write_work_log()`；审批/授权/密码类操作必须留痕。
6. **敏感数据**：身份证号等 PII 加密存储；日志与错误响应不得泄露内部细节。

## 已知架构决策（ADR）

见 `docs/adr/`。整改期间新增：
- ADR-0001 认证唯一出口（token_manager.validate_token）
- ADR-0002 数据隔离单一实现 fail-closed
- ADR-0003 组织删除守卫
- ADR-0004 通行码密钥 fail-closed
- ADR-0005 PII 加密落地方式
- ADR-0006 PyInstaller onedir
- ADR-0007 前端指令体系启用

## 整改工单

`.scratch/w1-security-redline/ … w6-release-eng/`，规则见 `docs/agents/issue-tracker.md`。
