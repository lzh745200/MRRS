# 帮扶管理信息系统

> 乡村振兴 — 完全离线的单机版桌面应用 | 多机协同数据同步 | v1.12.8

![Version](https://img.shields.io/badge/version-1.12.8-blue)
![License](https://img.shields.io/badge/license-MIT-lightgrey)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20ARM64-orange)
![Tests](https://img.shields.io/badge/tests-17%2C295%2B-brightgreen)
![Coverage](https://img.shields.io/badge/coverage-100%25-brightgreen)

## 项目状态

| 指标 | 结果 |
|------|------|
| 后端测试 | **11,244 passed**, 0 失败（含覆盖率 100% 门禁） |
| 前端测试 | **6,051 passed**（302 文件）, 0 失败 |
| 后端覆盖率 | **100%**（可覆盖集口径，门禁 `backend/.coveragerc` fail_under=100） |
| 前端覆盖率 | **100%**（门禁 `vitest.config.ts` 12 组 glob 阈值 ×100） |
| Flake8 | 0 错误, 0 警告 |
| ESLint | 0 错误, 0 警告 |
| Bandit (安全) | 0 高危 |
| vue-tsc | 0 错误 |
| TypeScript | strict: true（全选项启用） |
| Pre-commit | ruff（变更文件）+ flake8/bandit/vue-tsc（推送前） |
| CI/CD | PR Checks + Nightly Full Suite + Codecov |
| Sass | 1.101.0（modern-compiler API） |
| 角色体系 | 4 核心角色 (super_admin/admin/user/viewer) |

| 预防门禁 | 6 个棘轮扫描器（os._exit / 上传限长 / 无界读 / 子进程编码 / 目录替换 / 周期任务注册）接入 CI，NEW=0 |
| 真实 HTTP 探测 | 21 个探针脚本 0 失败（探针专用库，覆盖认证/帮扶村/学校/经费/项目/政策/组织/报表/备份/审批/数据包） |

> **上次全量验证**: 2026-09-14（v1.12.8）— 后端 11,244 用例 + 覆盖率 100%、前端 6,051 用例全部通过；
> flake8 0 / bandit 中高危 0 / vue-tsc 0 / eslint 0；GitHub Actions 双安装包构建全绿

## 快速开始

### 系统要求

| 项目 | 最低要求 | 推荐配置 |
|------|---------|---------|
| 操作系统 | Windows 10 / 麒麟 V10 ARM64 | Windows 10/11 64位 |
| 内存 | 4 GB | 8 GB |
| 硬盘 | 2 GB | 5 GB |

> **离线设计**：安装包内置所有运行时，无需安装 Python/Node.js。

### 一键启动

```bash
scripts\start-all.bat      # 启动所有服务
scripts\stop-all.bat       # 停止所有服务
```

### 开发环境

```bash
# 一键初始化开发环境
scripts\dev-setup.bat        # Windows
bash scripts/dev-setup.sh    # Linux

# 或手动
cd backend && python -m venv .venv && pip install -r requirements.txt && python start.py
cd frontend && npm install && npm run dev
```

### 访问地址与默认账号

| 服务 | 地址 |
|------|------|
| 前端（开发） | http://localhost:5173 |
| 前端（生产） | http://localhost:8000 |
| API 文档 | http://localhost:8000/docs |

默认账号: `admin` / `admin123`（首次登录后请修改密码）

## 技术栈

### 后端
- **框架**: FastAPI + SQLAlchemy 2.0 + Pydantic
- **数据库**: SQLite（`backend/data/rural_revitalization.db`）
- **认证**: JWT + bcrypt + 机器码绑定 + 通行码验证（三级回退）+ 2FA
- **缓存**: diskcache + 内存 LRU
- **任务**: threading.Timer 定时调度（备份计划/KPI预计算/异常检测, APScheduler 已移除）
- **角色体系**: 4 核心角色（super_admin/admin/user/viewer）+ `normalize_role()` 向后兼容
- **打包**: PyInstaller（x64 + ARM64）+ electron-builder（NSIS 安装包）

### 前端
- **框架**: Vue 3 + TypeScript + Vite
- **UI**: Element Plus + ECharts + Leaflet
- **状态**: Pinia + 响应式菜单权限
- **测试**: Vitest + Playwright
- **代码质量**: ESLint + Prettier + lint-staged

### 桌面
- **壳**: Electron 33 + electron-builder
- **安装**: NSIS (Windows) / dpkg-deb (Linux ARM64)

## 测试体系

| 测试类型 | 工具 | 数量 | 覆盖范围 |
|---------|------|------|---------|
| 后端单元测试 | pytest | 11,244（覆盖率 100%） | API/Service/Core/Model/Utils 全覆盖 |
| 后端集成测试 | pytest | 8 套 | Auth/Users/Policies/Search/Audit/API |
| 后端安全测试 | pytest | 3 套 | Data Isolation/Audit/Retry |
| 前端单元测试 | Vitest | 6,051（302 文件） | API/Store/Component/Composable/Utils |
| E2E 测试 | Playwright | 12 流程 | Login/Dashboard/Projects/Approval/Funds |
| 性能测试 | Locust | 配置可用 | 负载测试 |
| 属性测试 | fast-check | 多组 | 组件属性验证 |
| 无障碍测试 | Vitest | 多组 | ARIA/键盘/颜色对比度 |
| 安全扫描 | Bandit | 0 高危 | SQL注入/密码/加密 |
| 代码检查 | Flake8/ESLint | 0 错误 | Python + Vue/TS |

### 运行测试

```bash
# 后端
cd backend && pytest tests/ -q --tb=short

# 前端
cd frontend && npm test

# 全量（不含 E2E）—— 有 make 的环境用 make test；Windows 无 make 时逐条执行
cd backend && .venv/Scripts/python.exe -m pytest tests/ -q --cov=app
cd frontend && npm test -- --run

# E2E (Docker)
docker compose -f docker-compose.yml -f docker/docker-compose.e2e.yml --profile e2e up

# 覆盖率
cd backend && pytest --cov=app --cov-report=html
cd frontend && npm run test:coverage
```

## 开发工具链

```bash
# 代码格式化与检查
cd frontend && npm run lint            # ESLint 自动修复
cd frontend && npm run type-check      # TypeScript 类型检查
cd backend && flake8 app/ --max-line-length=120
cd backend && bandit -r app/

# Pre-commit hooks（推荐安装）
pip install pre-commit && pre-commit install
npx lint-staged                        # 仅检查暂存文件

# 构建（两种方式，产物一致）
# ① 推荐：推 tag 由 GitHub Actions 一次产出两个安装包并发布 Release
git tag v1.12.8 && git push origin v1.12.8     # → Windows x64 .exe + 麒麟 ARM64 .deb
# ② 本地（Windows 无 make 时）：fetch_vcredist → 前端构建 → 同步 → PyInstaller → electron-builder
powershell -ExecutionPolicy Bypass -File scripts/build/fetch_vcredist.ps1
cd frontend && npm run build && cd .. && cmd /c scripts\build\sync-frontend-dist.bat
cd backend && .venv/Scripts/python.exe -m PyInstaller assistance-backend.spec --clean --noconfirm && cd ..
npx electron-builder --win --x64     # 产物：dist/electron/MRRS-Setup-<版本>-x64.exe
```

## CI/CD 流水线

| 流水线 | 触发条件 | 内容 |
|--------|---------|------|
| **PR Checks**（7 作业） | Pull Request | 后端测试 + 覆盖率门禁（`.coveragerc` fail_under=100）+ 前端检查 + lint + security + **static-analysis（含 6 个预防棘轮门禁）** + E2E + **windows-smoke** |
| **Nightly Full** | 每日凌晨2:00 UTC | 全量测试 + 覆盖率报告 + Codecov + JUnit 报告 |
| **Build Windows x64** | **tag v\*** / 手动 | PyInstaller onedir + electron-builder NSIS → 安装包挂到 Release |
| **Build ARM64 deb** | **tag v\*** / 手动 | Docker Buildx QEMU + electron-builder DEB → 安装包挂到 Release |

## 项目结构

```
├── backend/app/              # 后端（FastAPI，339 个 py / 8.1 万行）
│   ├── api/v1/               # API 接口层（93 个模块 + 13 个子包）
│   ├── core/                 # 核心：config, security, database, transaction, cache, maintenance(维护闸门)
│   ├── models/               # SQLAlchemy 数据模型（59 个文件）
│   ├── services/             # 业务逻辑层（100 个服务 + 13 个子包）
│   ├── middleware/           # CSRF, 审计, 请求日志, 指标, maintenance_gate(写请求闸门)
│   └── startup/              # 启动钩子（种子/监控/恢复/环境自检 + 组织树自愈）
├── frontend/src/             # 前端（Vue 3 + TypeScript，292 个源文件）
│   ├── views/                # 页面视图（131 个 .vue）
│   ├── components/           # 通用 + 业务组件
│   ├── stores/               # Pinia 状态
│   ├── composables/          # 组合式函数
│   └── utils/                # 工具函数
├── electron/                 # Electron 桌面壳
├── docker/                   # 多架构 Dockerfile + E2E compose
├── deploy/                   # 麒麟 V10 systemd + DEBIAN 配置
├── k8s/                      # Kubernetes 部署清单
├── nginx/                    # Nginx 反向代理配置
├── scripts/                  # 管理/运维脚本
├── build-scripts/            # electron-builder NSIS 钩子 + 构建配置
├── docs/                     # 项目文档
├── .github/workflows/        # CI/CD（PR Checks + Nightly + Build）
└── resources/                # 图标、VC++ 运行库、预置数据库
```

## 许可证

MIT License - 详见 [LICENSE](LICENSE)

Copyright © 2025-2026 贵州省乡村振兴项目组

## 安装包获取

| 平台 | 安装包 | 获取方式 |
|------|--------|---------|
| Windows 10/11 x64 | `MRRS-Setup-<版本>-x64.exe`（约 228 MB，内置后端 exe + 前端产物 + VC++ 运行库） | GitHub → Releases（推 `v*` 标签由 Actions 自动构建并附带 SHA512） |
| 麒麟 V10 / 统信 UOS ARM64 | `*.deb`（自包含后端二进制） | 同上（`build-arm64.yml` 产出） |

> 本机 Windows 构建产物位于 `dist/electron/MRRS-Setup-<版本>-x64.exe`；
> 发布校验和随 GitHub Release 一起提供（旧版 `SHA256SUMS-*` 已随版本归档清理）。

## 近期修复记录

### 2026-09-14（v1.12.8）
- 🛡️ **R7 恢复维护窗口**：备份恢复期间新的写请求一律 503、读请求放行、等待在途请求归零后执行、`finally` 解除；`/health` 暴露 `maintenance` 状态。修复"恢复时恰有在途写 → Windows 覆盖失败 / POSIX 写进旧 inode 静默丢提交"
- 🛡️ **R14 组织树元数据**：新建组织不再缺 `path/level`（此前导致组织级数据权限 fail-closed，成员一律 403、管理员无法导出数据包）；历史数据由启动自检幂等回填
- 🧱 **R12 低危一致性 7 项**：慢请求计数器原子化、演练状态快照、提醒线程双启动窗口、`os._exit`→优雅关闭、内存任务表终态回收、后台任务调度契约
- 🔒 **R2 残余清零**：数据包/权限包 11 处 zip 打开点补解压后总量闸门与限长读；备份校验改流式；分片上传限长 + 合并摘要分块
- 🚦 **P-1~P-3 预防门禁**：6 个棘轮扫描器接入 CI（`os._exit` / 无界读 / 上传端点 / 子进程编码 / 目录替换 / 裸 Timer）
- 🎨 认证页与布局硬编码色值清零 + 补齐 3 个设计 token（样式棘轮新增归零）
- 📊 后端 11,244 用例 / 覆盖率 100%；前端 6,051 用例；21 个真实 HTTP 探针 0 失败

### 2026-09-13（v1.12.6 / v1.12.7）
- 🛡️ 遗留风险第一批：调度器 RecurringTimer 收敛 + 作业看门狗（自动备份不再静默停摆）、启动不再抢锁 VACUUM、备份语义 fail-loud
- 🛡️ 遗留风险第二批：上传体积三层上限（中间件/端点 18 处/压缩炸弹防护）、导出过期回收、导入失败记录 409 语义、Windows 冒烟作业入 CI
- 🔧 版本与依赖单源收敛（sync-version 13 处 + 删除 3 个无人引用的 requirements 变体）

### 2026-08-09
- ✨ 备份包上传恢复完整链路：`/system/backup/upload-restore` 支持加密备份（密码透传解密）、上传前内存预校验（加密标记/损坏ZIP/缺库文件，拒绝零残留）、恢复流程 WAL 安全（先释放连接池再覆盖）
- ✨ 备份管理页新增「导入备份包」入口（支持任意机器导出的备份包）
- 🐛 备份列表返回 `is_encrypted` 字段（修复加密备份恢复时密码框不出现）
- 🐛 备份上传改为分块流式落盘（8MB 分块 + 10GB 上限），消除大包 OOM 风险
- 🧹 删除死代码 `token_blacklist_service.py`；`fund_budgets`/`policy` 覆盖率补至 100%（总覆盖率 99.86%）
- 🐛 版本一致性测试纳入环境变量优先级（修复残留 `PROJECT_VERSION` 环境变量导致的测试失败）

### 2026-08-05
- 🔒 数据同步提权修复、备份下载权限收紧、审批自动通过越权修复、配置包导出安全加固
- ✨ 预算附件上报、合同附件上报、学校分析页接入真实数据、经费年度总览

### 2026-08-01
- 🐛 修复 Vue `setAttribute('0')` 页面白屏崩溃（ErrorBoundary 单一根元素修复）
- 🐛 修复注册时“通行码无效或已被使用”误报（机器码三级回退验证）
- 🐛 修复 files API 响应格式不统一（改用 `success_response()` 信封格式）
- ✨ 精简用户角色至 4 个核心角色 + `normalize_role()` 向后兼容

> 详见 [CHANGELOG.md](CHANGELOG.md)
