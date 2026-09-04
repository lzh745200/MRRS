---
kind: dependency_management
name: 多语言依赖管理：Python requirements 分层 + npm lockfile + Docker 镜像构建
category: dependency_management
scope:
    - '**'
source_files:
    - backend/requirements.txt
    - backend/requirements-dev.txt
    - backend/requirements-prod.txt
    - backend/requirements-docker.txt
    - backend/requirements-minimal.txt
    - backend/requirements-optional.txt
    - backend/pyproject.toml
    - frontend/package.json
    - frontend/package-lock.json
    - frontend/.npmrc
    - package.json
    - package-lock.json
    - docker/Dockerfile
---

## 1. 使用的系统/工具

本仓库采用**多语言、分层式依赖管理**策略，分别针对 Python 后端、Node.js 前端与 Electron 桌面壳进行独立声明与锁定：

- **Python（后端）**：使用 `pip` + 多个 `requirements*.txt` 文件进行依赖声明；通过 `pyproject.toml` 配置 coverage 等工具；通过 `alembic.ini` 管理数据库迁移。
- **Node.js（前端 + Electron）**：使用 `npm` + `package.json` + `package-lock.json` 锁定版本；Electron 打包由 `electron-builder` 完成。
- **容器化**：Docker 多阶段构建中显式安装依赖并固定 pip/npm 源，确保可重复构建。

## 2. 关键文件

- `backend/requirements.txt` — 生产运行时依赖（核心 Web、DB、验证、文件处理、数据处理、日志、工具库），所有版本均精确到次级版本（如 `fastapi==0.136.3`）。
- `backend/requirements-dev.txt` — 开发/测试/静态分析/打包工具（pytest、black、flake8、mypy、bandit、pyinstaller 等）。
- `backend/requirements-prod.txt` — 与 `requirements.txt` 内容一致，专门用于 PyInstaller 打包和 Docker 生产镜像。
- `backend/requirements-docker.txt` — 面向 Docker 运行时的精简依赖集（含 `slowapi`、`structlog`、`prophet`、`scrapy` 等）。
- `backend/requirements-minimal.txt` — 最小可运行依赖集，用于本地快速测试。
- `backend/requirements-optional.txt` — 可选依赖（预测统计：`prophet`、`cmdstanpy` 等），注释说明未安装时自动降级。
- `frontend/package.json` + `frontend/package-lock.json` — 前端 Vue3/Vite 依赖及完整锁文件。
- `package.json` + `package-lock.json` — Electron 主进程依赖（`electron`、`electron-builder`、`electron-log`）。
- `docker/Dockerfile` — 多阶段构建：Node 22 构建前端、Python 3.11 构建后端二进制、最终 runtime 镜像仅安装必要运行时依赖。
- `backend/pyproject.toml` — 覆盖率配置（`fail_under = 100`）。

## 3. 架构与约定

### 3.1 Python 依赖分层

| 文件 | 用途 | 特点 |
|---|---|---|
| `requirements.txt` | 生产运行时 | 全部精确版本，按功能分组注释 |
| `requirements-prod.txt` | 生产镜像/PyInstaller | 与 `requirements.txt` 保持一致 |
| `requirements-docker.txt` | Docker 运行镜像 | 包含更多运行时扩展（NLP、舆情、AI） |
| `requirements-minimal.txt` | 最小可运行集 | 仅保留核心 API + DB + 导出能力 |
| `requirements-dev.txt` | 开发环境 | 测试、lint、类型检查、安全扫描、打包工具 |
| `requirements-optional.txt` | 可选功能 | 需 C++ 编译器的预测模型依赖 |

### 3.2 版本锁定策略

- **Python**：几乎全部使用 `==` 精确锁定（如 `fastapi==0.136.3`、`SQLAlchemy==2.0.50`），少数使用 `>=`（如 `bcrypt>=4.2.0`、`cryptography>=41.0.0`）以兼容不同平台。
- **Node.js**：依赖使用 `^` 语义化版本范围（如 `vue: ^3.4.21`），通过 `package-lock.json` 锁定实际解析版本；根目录 `overrides.minimatch: ^9.0.0` 用于修复安全漏洞。
- **Docker**：构建阶段固定 Python/Node 基础镜像（`python:3.11-alpine`、`node:22-alpine`），并通过 `-i https://pypi.tuna.tsinghua.edu.cn/simple` 指定清华源加速下载。

### 3.3 平台条件依赖

通过 pip 条件表达式区分平台：
```text
python-magic-bin==0.4.14; sys_platform == 'win32'
python-magic==0.4.27; sys_platform != 'win32'
```
在 `requirements.txt`、`requirements-prod.txt`、`requirements-docker.txt` 中均有体现。

### 3.4 可选依赖与降级

`requirements-optional.txt` 中的 `prophet` 依赖 cmdstan C++ 编译器，在某些环境（ARM64、CI）安装困难。代码中通过 try/except 捕获导入失败并降级为离线模式，不影响核心功能。

### 3.5 私有/镜像源

- **npm**：`frontend/.npmrc` 存在但为空，实际通过 CI 或环境变量配置镜像；Docker 中通过 `npm config set registry https://registry.npmmirror.com` 设置淘宝镜像。
- **pip**：Docker 构建中使用 `https://pypi.tuna.tsinghua.edu.cn/simple` 清华源。
- 未发现 `GOPRIVATE`、`vendor/` 目录或 Go module 配置。

## 4. 约定与约束

- **生产依赖必须精确锁定**：`requirements.txt` 中绝大多数包使用 `==` 锁定，避免非确定性构建。
- **开发/生产依赖分离**：开发工具（pytest、black、mypy、bandit、pyinstaller）仅在 `requirements-dev.txt` 中声明，不混入生产依赖。
- **可选依赖必须可降级**：`requirements-optional.txt` 中的预测/统计功能在未安装时应自动降级，保证核心功能可用。
- **平台差异通过条件依赖处理**：Windows/Linux 专用依赖使用 `sys_platform` 条件表达式而非分支逻辑。
- **Docker 构建必须可重复**：基础镜像版本固定，pip/npm 源显式指定，禁止隐式网络依赖。
- **覆盖率门禁**：`pyproject.toml` 中 `fail_under = 100`，要求 100% 测试覆盖率（可通过 `pragma: no cover` 豁免真正不可执行行）。
- **安全加固**：Docker 镜像使用非 root 用户（`appuser`），并仅安装运行所需的最小系统库。

## 5. 注意事项

- `requirements-docker.txt` 与 `requirements.txt` 存在版本差异（如 `alembic==1.13.1` vs `1.16.4`、`cryptography==48.0.0` vs `>=41.0.0`），需在更新时保持同步。
- 前端 `package-lock.json` 中部分包从 `mirrors.cloud.tencent.com`（腾讯镜像）解析，表明 CI/开发环境可能配置了 npm 镜像。
- 未发现统一的依赖升级自动化脚本或 Dependabot/GitHub Actions 依赖更新流程，主要依赖人工维护 `requirements*.txt` 与 `package.json`。
