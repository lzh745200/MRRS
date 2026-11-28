# v1.18.67 发布说明

发布日期：2026-11-28

主题：系统角色收敛为四类、彻底下线自助注册、澄清 RBAC 与账号角色的边界。

## 本版重点

- **固定四类系统角色**：超级管理员（`super_admin`）、系统管理员（`admin`）、
  普通用户（`user`）、访客（`viewer`）。角色中文标签、描述、可选数据范围与下拉选项
  统一由后端 `core/constants.py` 派生，前端不再维护第二套文案。
- **自助注册彻底下线**：`POST /auth/register` 与 `SELF_REGISTER_MODE` 已删除，
  登录页公开配置不再返回 `self_register_enabled`。账号只能由管理员在「用户与角色」创建，
  或通过账号开通包离线导入。通行码保留，但只用于机器码绑定/激活与换机重置。
- **RBAC 仅服务权限包**：`rbac_roles` / `rbac_user_roles` 不再影响 `users.role`。
  权限包导入默认只恢复组织归属，不写账号级角色/数据范围/权限；确需恢复 v1 遗留权限时，
  管理员可显式传 `apply_legacy_privileges=true`。
- **角色与数据范围单一来源**：数据范围统一为 `all` / `org_children` / `org` / `self`，
  权限包中的 `own` 自动归一为 `self`。历史 `users.role` 值由 `role_normalize_001` 迁移清洗：
  `approval_leader` / `manager` → `admin`，`operator` → `user`，空值 → `user`。
- **前端对齐**：非超管不再看到超级管理员选项；未知角色显示「未知角色」且 fail-closed，
  不再被误判为管理员；RBAC 页签更名「权限包角色（RBAC）」并说明与系统角色的区别；
  删除无运行时守卫的“功能权限”表单。
- **账号开通包**：本版包含 v1.18.66 的默认启用、自动签发密钥、指纹确认信任修复；
  已安装 1.18.65 升级到本版后即可直接签发，无需配置 `ACCOUNT_PACKAGE_*` 环境变量。

## 数据与兼容

- 新增 Alembic 迁移 `role_normalize_001`（数据清洗，不改表结构）；迁移不可逆，
  未知角色值原样保留，不会静默提权。
- 权限包 v1.0 仍可导入；导入默认不写账号级权限，返回结果会带
  `legacy_privileges_skipped` 提示。需要旧行为时由管理员显式开启。
- 自助注册端点与公开配置字段被删除属于**有意的契约变更**：调用方应改用管理员创建或账号开通包；
  访问 `/api/v1/auth/register` 返回 404/405。
- RBAC 角色名/码不能再占用 `super_admin` / `admin` / `user` / `viewer`，已有同名角色不会被自动删除。

## 验证

- 后端合并回归（账号包、自检、权限包、RBAC、注册、角色迁移）**244** 例通过；
  `flake8 app/ --max-line-length=120 --max-complexity=16` 无输出；
  `check_stack_alignment.py`、`check_route_auth.py` 通过。
- 前端角色、权限面板、组织、通行码、用户管理相关 **663** 例（17 文件）通过；
  `vue-tsc --noEmit`、ESLint 通过。
- 文档数字门禁：API 端点 **864**、后端用例 **16,184**、前端测试文件 **351**。

## 已知边界

- 删除历史 RBAC 角色需要管理员手工操作；本版只保证系统角色名称/编码不被占用。
- 权限包导入的 `apply_legacy_privileges` 仅管理员可用；普通管理员默认走安全路径。
- 安装版为 PyInstaller onedir，代码不能热替换；本版需通过新安装包生效。

## 安装包

- Windows x64：`MRRS-Setup-1.18.67-x64.exe`（以 GitHub Release 资产为准）
- 麒麟 ARM64：`MRRS-Setup-1.18.67-arm64.deb`、`assistance-management-system_1.18.67_arm64.deb`

升级前请备份 `backend/data` 与上传目录。升级后原 `admin` / `user` / `viewer` 账号不变；
历史 `manager` / `approval_leader` 账号会在迁移后显示为系统管理员（权限语义不变）。
