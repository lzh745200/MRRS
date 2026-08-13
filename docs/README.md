# 文档中心

帮扶管理信息系统 v1.8.1 项目文档。

## 快速入口

- **[启动指南](01-快速开始/启动指南.md)** — 如何启动系统
- **[使用指南](02-用户手册/使用指南.md)** — 日常操作说明
- **[经费管理操作说明](02-用户手册/经费管理模块操作说明.md)** — 经费模块详细操作
- **[架构设计](03-开发文档/01-架构设计/)** — 系统架构与代码结构
- **[开发指南](03-开发文档/02-开发指南/)** — 前后端开发规范
- **[部署文档](04-部署文档/)** — Windows/Linux/Docker 部署
- **[ER 图](ER-DIAGRAM.md)** — 数据库关系图
- **[系统设计（打包方案）](system_design.md)** — Windows 离线安装包打包方案 + 类图 + 时序图
- **[项目文件结构说明](../项目文件结构说明.md)** — 仓库目录结构与关键文件速查（仓库根目录）

## 文档约定

- 所有文档以项目根目录 `README.md` 为准
- 版本号统一使用 `backend/app/core/config.py` 中的 `PROJECT_VERSION`
- Schema 以 `backend/app/models/` 和 Alembic 迁移为准
- 构建配置以 `package.json` build 段 + `backend/assistance-backend.spec` 为准
- 审计日志必须同时写入文件日志和数据库（audit_logs + login_attempts 表）
- 备份恢复统一走 `/api/v1/system/backup/upload-restore`（支持加密备份，见 AGENTS.md）
