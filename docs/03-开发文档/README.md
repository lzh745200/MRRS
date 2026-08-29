# 开发文档

> 帮扶管理信息系统 — 开发文档总览

本目录包含系统的全部开发相关文档，按模块组织，覆盖架构设计、开发指南、API 规范和安全策略。

---

## 目录结构

| 目录/文件 | 说明 |
|-----------|------|
| `01-架构设计/` | 系统架构设计文档 |
| `02-开发指南/` | 开发环境搭建与编码规范 |
| `03-API文档/` | API 接口文档与版本控制 |
| `前端开发指南.md` | 前端（Vue 3 + TypeScript + Vite）开发指南 |
| `后端开发指南.md` | 后端（FastAPI + SQLAlchemy）开发指南 |
| `UI设计规范.md` | UI/UX 设计规范与组件库使用 |
| `API接口文档.md` | REST API 接口详细说明 |
| `API版本控制策略.md` | API 版本管理与向后兼容策略 |
| `安全开发规范.md` | 安全编码规范与常见漏洞防护 |

---

## 01-架构设计

系统整体架构采用前后端分离模式：

- **前端**：Vue 3 + TypeScript + Vite + Pinia + Element Plus
- **后端**：FastAPI + SQLAlchemy + Alembic + Pydantic
- **桌面端**：Electron 壳 + PyInstaller 打包后端
- **数据库**：SQLite(离线单机,唯一数据库;跨机数据经加密数据包交换)
- **缓存**：diskcache + 内存 LRU 双层缓存

详细设计见 `01-架构设计/` 目录下的架构图、类图和时序图。

---

## 02-开发指南

### 环境要求

- Python 3.11+
- Node.js 18+
- Git
- （可选）Docker & Docker Compose

### 快速开始

```bash
# 一键初始化开发环境
# Windows
scripts\dev-setup.bat

# Linux/macOS
bash scripts/dev-setup.sh
```

### 项目结构约定

- 后端路由模块自动注册：`backend/app/api/v1/__init__.py` 扫描所有路由文件
- 数据模型懒加载：`backend/app/models/__init__.py` 使用 `__getattr__` 延迟导入
- Service 序列化约定：`_to_dict`/`to_dict` 必须包含前端表格 `prop` 绑定的所有字段

详细规范见 `02-开发指南/` 和 `前端开发指南.md`、`后端开发指南.md`。

---

## 03-API 文档

### Swagger 文档

启动后端后访问：

```
http://localhost:8000/docs
http://localhost:8000/redoc
```

### API 版本控制

当前 API 版本：`v1`

版本控制策略详见 `API版本控制策略.md`，核心原则：

- URL 路径版本化：`/api/v1/...`
- 破坏性变更需发布新版本路径
- 旧版本至少维护 2 个大版本周期
- 废弃接口通过响应头 `Deprecation` 和 `Sunset` 通知

---

## 安全相关文档

安全开发规范涵盖以下方面：

| 安全域 | 说明 |
|--------|------|
| **认证安全** | JWT 签发/验证、bcrypt 密码哈希、Token 黑名单、2FA |
| **CSRF 防护** | Double Submit Cookie + HMAC-SHA256 |
| **数据加密** | AES-GCM、SM2/SM4 国密算法、字段级加密 |
| **审计日志** | 操作审计、登录尝试记录、API 访问日志 |
| **输入校验** | Pydantic Schema 校验、SQL 注入防护、XSS 过滤 |
| **文件上传** | 类型白名单、大小限制、病毒扫描接口 |
| **数据权限** | 按组织/角色过滤 SQL 查询（DataPermission） |

详见 `安全开发规范.md`。

---

## 相关文档

- [项目文件结构说明](../../项目文件结构说明.md)
- [部署文档](../04-部署文档/)
- [用户手册](../../USER_MANUAL.md)
- [贡献指南](../../CONTRIBUTING.md)
- [CHANGELOG](../../CHANGELOG.md)
