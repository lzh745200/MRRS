---
kind: build_system
name: 多架构构建流水线：Makefile + Docker Buildx + GitHub Actions 统一编排
category: build_system
scope:
    - '**'
source_files:
    - Makefile
    - backend/assistance-backend.spec
    - backend/pyproject.toml
    - backend/requirements.txt
    - frontend/package.json
    - package.json
    - docker/Dockerfile
    - docker/Dockerfile.deb-complete
    - docker/docker-compose.e2e.yml
    - .github/workflows/pr-checks.yml
    - .github/workflows/build-windows.yml
    - .github/workflows/build-arm64.yml
    - scripts/sync_version.py
    - scripts/generate_build_info.py
    - scripts/build/fetch_vcredist.ps1
---

## 1. 构建系统总览

本仓库采用**单体仓库（monorepo）**组织，以根级 `Makefile` 为统一入口，串联后端（FastAPI/Python）、前端（Vue3/Vite）、Electron 桌面壳、以及多种目标产物（Windows NSIS 安装包、Linux DEB、麒麟 V10 ARM64 单机版 DEB）。构建与发布由 **GitHub Actions** 在多个 runner 上并行执行，并通过 Docker Buildx 实现跨平台交叉编译。

核心工具链：
- Python 后端：PyInstaller `assistance-backend.spec`（onedir 布局，ADR-0006），依赖通过 `requirements.txt` 锁定版本。
- 前端：Vite + Vitest + ESLint + Vue-TSC，包管理使用 `frontend/package.json`。
- 桌面打包：electron-builder（NSIS for Windows，DEB for Linux），配置集中在根 `package.json` 的 `build` 段。
- 容器化：多阶段 Dockerfile（`docker/Dockerfile`、`Dockerfile.deb-complete`、`Dockerfile.kylin-*`、`Dockerfile.backend-arm64`）。
- CI：`.github/workflows/` 下四个工作流分别负责 PR 检查、Windows 安装程序构建、ARM64 DEB 构建、夜间全量构建。

## 2. 关键文件与职责

| 文件 | 职责 |
|---|---|
| `Makefile` | 本地开发/测试/构建的统一入口，定义 `test`、`coverage`、`deploy-check`、`build-win-*`、`build-deb*`、`build-kylin*` 等目标 |
| `backend/assistance-backend.spec` | PyInstaller onedir 打包规范，声明隐藏导入、数据文件、排除模块 |
| `backend/pyproject.toml` | pytest-cov 覆盖率配置（`fail_under = 100`，可被 `--cov-fail-under=98` 覆盖） |
| `backend/requirements.txt` | 后端依赖锁定清单（含 FastAPI、SQLAlchemy、Pydantic、pandas 等） |
| `frontend/package.json` | 前端脚本（`dev`/`build`/`test:coverage`/`lint`/`type-check`） |
| `package.json`（根） | Electron 应用元信息 + electron-builder 打包配置（win/mac/linux target、extraResources、NSIS hook） |
| `docker/Dockerfile` | 多阶段镜像：前端构建 → 后端 PyInstaller → 运行时（serve 静态资源 + 后端 exe） |
| `docker/Dockerfile.deb-complete` | 仅生成 DEB 的专用构建镜像（Node 18 Bookworm + dpkg-dev） |
| `docker/docker-compose.e2e.yml` | E2E 测试环境（Playwright + Locust），通过 `profiles: e2e/performance` 按需启用 |
| `.github/workflows/pr-checks.yml` | PR 门禁：pytest 98% 覆盖率、flake8/mypy/bandit、npm audit、SBOM、菜单对齐、软删除审计 |
| `.github/workflows/build-windows.yml` | 触发条件 `tags/v*`，构建 Windows x64 NSIS 安装包，可选代码签名（CSC_LINK/CSC_KEY_PASSWORD） |
| `.github/workflows/build-arm64.yml` | 触发条件 `tags/v*`，QEMU 模拟 ARM64 构建后端二进制 + Electron DEB + standalone 麒麟 DEB |
| `scripts/sync_version.py` | 同步版本号到 13 处位置（CI 中 tag 触发时调用） |
| `scripts/generate_build_info.py` | 生成构建元数据（commit、时间、tag） |
| `scripts/build/fetch_vcredist.ps1` | 下载并 SHA256 钉扎 VC++ Redistributable（不入库，新 clone 后自动补齐） |

## 3. 架构与约定

### 3.1 分层构建流程
1. **前端构建**：`cd frontend && npm run build` → 输出 `frontend/dist/`。
2. **后端打包**：`cd backend && python -m PyInstaller assistance-backend.spec --clean --noconfirm` → 输出 `backend/dist/assistance-backend/`（onedir 目录布局，含 `_internal/` 依赖目录）。
3. **桌面打包**：`npx electron-builder --win --x64`（或 `--linux deb --arm64`），将前端 dist 与后端 onedir 作为 `extraResources` 注入安装包。
4. **DEB 构建**：通过 `make docker-build-amd64|arm64` 调用 `docker/Dockerfile.deb-complete`，或使用 `make build-kylin-arm64` 调用 `Dockerfile.kylin-standalone`。

### 3.2 版本管理
- 版本号来源：根 `package.json.version`（当前 `1.11.3`），Makefile 通过 `node -p "require('./package.json').version"` 读取。
- Tag 触发发布：`v*` tag 推送时，CI 先执行 `python scripts/sync_version.py <tag>` 将版本号同步到 13 处位置，再构建产物。
- DEB 包名遵循 `assistance-management-system_<VERSION>_<ARCH>.deb` 命名规范。

### 3.3 质量门禁
- **覆盖率**：PR 合并要求后端 ≥98%（`--cov-fail-under=98`），本地 `coverage` 目标也强制该阈值；`pyproject.toml` 内配置为 100%，但可通过命令行覆盖。
- **Lint/类型**：flake8（max-line-length=120, max-complexity=16）、mypy（非阻断）、ESLint（`--max-warnings=0`）、Vue-TSC 类型检查。
- **安全扫描**：bandit（-ll 级别阻断）、pip-audit（仅报告不阻断）、npm audit（high+ 阻断）。
- **部署前检查**：`make deploy-check` 串行执行 pytest/flake8/bandit + 前端 lint/type-check/test，任一失败即中断。

### 3.4 多架构与交叉编译
- Windows：在 `windows-2022` runner 上用原生 Python x64 构建，同时支持 x64/x86 双架构（x86 需 32-bit Python 3.11，已弃用因上游科学计算包不再提供 win32 wheels）。
- Linux DEB：通过 `docker buildx --platform linux/arm64` 在 amd64 主机上交叉编译 ARM64 后端二进制，再用 electron-builder 打 DEB。
- 麒麟 V10 standalone：使用 `Dockerfile.kylin-standalone` 直接产出无 Electron 的纯 Web 架构 DEB，推荐用于麒麟真机部署。

### 3.5 产物完整性
- 每个 Release 自动生成 `SHA256SUMS-*.txt` 清单（Windows x64 / Electron DEB ARM64 / Standalone DEB ARM64 分文件命名，避免同 Release 覆盖）。
- Windows 安装包可选 Authenticode 代码签名（通过 `CSC_LINK`/`CSC_KEY_PASSWORD` secrets 控制，未配置则跳过并警告）。
- DEB 包内置 postinst 脚本修复 SUID 权限（`chrome-sandbox` 4755）和桌面数据库更新。

## 4. 约束与规则

- **禁止吞掉失败**：Makefile 注释明确要求“每条命令独立阻断，禁止 `|| true` 掩盖失败”，仅在清理步骤允许 `|| true`。
- **覆盖率门禁真实生效**：PR 检查中 `--cov-fail-under=98` 是真实阻断信号，不是 continue-on-error。
- **依赖固定**：所有生产依赖在 `requirements.txt` 中精确锁定版本（如 `fastapi==0.136.3`、`uvicorn[standard]==0.48.0`），构建工具单独放在 `requirements-build.txt`。
- **VC++ 运行库不入库**：`resources/vcredist/` 被 `.gitignore` 忽略，由 `fetch_vcredist.ps1` 从官方 URL 拉取并按 SHA256 校验。
- **E2E 测试必须走 Docker**：`make test-e2e` 仅提示使用 `make test-e2e-docker`，通过 `docker compose --profile e2e` 启动完整环境。
- **Electron 主进程语法检查**：CI 在每个构建 job 中对 `electron/*.js` 执行 `node --check`，防止乱码损坏进入安装包。
- **DEB 维护脚本 LF 验证**：standalone DEB 构建后解压并检查 `DEBIAN/` 目录下无 CRLF，否则报错。
- **onidir 布局守卫**：ARM64 构建步骤显式断言 `backend/dist/assistance-backend/assistance-backend` 和 `_internal/` 存在，结构不符立即失败。
- **覆盖率报告上传不阻断**：Codecov 上传步骤设置 `continue-on-error: true`，阻断由 pytest 的 `--cov-fail-under` 承担。