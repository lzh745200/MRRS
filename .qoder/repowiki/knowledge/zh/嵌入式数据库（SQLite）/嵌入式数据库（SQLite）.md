---
kind: external_dependency
name: 嵌入式数据库（SQLite）
slug: sqlite
category: external_dependency
category_hints:
    - sdk_real_api
    - client_constraint
scope:
    - '**'
source_files:
    - backend/.env.example
    - electron/main.js
    - backend/alembic.ini
---

### SQLite
- 角色：单机版唯一持久化存储，默认路径 `backend/data/rural_revitalization.db`；桌面端由 Electron 主进程在用户数据目录（Windows: `%APPDATA%\帮扶管理系统`，Linux: `$HOME/.bumofu/data`）下创建并复制内置初始库。
- 集成方式：后端通过 SQLAlchemy 2.0 + Alembic 管理 schema；Electron 启动时注入 `DATABASE_URL=sqlite:///...` 环境变量指向用户数据目录中的 DB 文件。
- 关键约束：当前工作目录决定读写哪个 DB 文件（项目根 vs 安装目录），迁移脚本中孤儿临时表曾阻断全部迁移；外键策略已从危险 `CASCADE` 改为 `SET NULL`，需确保 Alembic head 已运行。