# build-scripts — 构建脚本与配置

> Windows 离线安装包统一使用 **electron-builder**（内置 NSIS target）打包，
> 不再使用手写 .nsi 脚本。历史 7 个 .nsi 文件与 3 个 .bat 脚本已废弃删除。

## Windows 离线安装包构建

### 架构方案

```
PyInstaller (assistance-backend.spec)
  └─ backend/dist/assistance-backend/  (onedir, ~85MB 主 exe + _internal 依赖目录, W6-T6)
electron-builder (package.json build 段)
  ├─ extraResources: assistance-backend.exe → resources/backend/
  ├─ extraResources: frontend/dist         → resources/frontend/
  ├─ extraResources: resources/vcredist    → resources/vcredist/
  ├─ NSIS target (内置) + electron-builder-nsis-hook.nsh 钩子
  └─ dist/electron/MRRS-Setup-<version>-x64.exe  (~234MB)
```

### 关键文件

| 文件 | 用途 |
|------|------|
| `electron-builder-nsis-hook.nsh` | electron-builder NSIS 钩子：VC++ SHA256 校验 + 静默安装 + 进程终止 + 卸载数据清理；同时是 URL/SHA256 钉扎常量的单一事实源 |

> ⚠️ 本目录**只有上述两个文件**。早期版本文档提到的 `build-config.json`、`build_deployment_packages.py`、
> `build_nuitka_arm64.py` 在本目录并不存在；ARM64 的构建入口已统一为 `docker/Dockerfile.*` + `make build-kylin-arm64`。

### 本地构建步骤

```bash
# 0. 拉取 VC++ Redistributable（二进制不入库，新 clone 必须先执行；
#    已存在且哈希匹配时自动跳过）
make fetch-vcredist

# 1. 前端构建并同步到 resources/frontend
cd frontend && npm run build
mkdir -p ../resources/frontend && cp -rf dist/* ../resources/frontend/

# 2. 后端打包（需对应架构的 Python 3.11）
cd ../backend && python -m PyInstaller assistance-backend.spec --clean --noconfirm

# 3. Electron 打包
cd ..
npx electron-builder --win --x64    # 64 位安装包（主力）
# npx electron-builder --win --ia32   # 32 位（已放弃：上游科学计算包不再提供 win32 cp311 wheels）
```

也可使用 Makefile 快捷命令：`make build-win-x64`

> **x86 说明**：x86/32-bit 构建已放弃（上游科学计算包 numpy/scipy/scikit-learn 不再提供 win32 cp311 wheels）。CI 仅构建 x64。

### 产物位置

- 安装包：`dist/electron/MRRS-Setup-<version>-x64.exe`（约 234MB；产物名由 `package.json` 的
  `build.artifactName` 决定，值为 `MRRS-Setup-${version}-${arch}.${ext}`）
- 后端 exe：`backend/dist/assistance-backend/assistance-backend.exe`（onedir 布局，W6-T6）
- 预置数据库：`resources/database/rural_revitalization.db`（打包进安装包，首次运行复制到用户目录）

### VC++ 运行库策略（双保险 + 供应链校验）

| 层级 | 机制 | 说明 |
|------|------|------|
| Layer 0 | 构建期下载校验 | `make fetch-vcredist`：官方 URL 下载 + SHA256 钉扎比对，不匹配即构建失败 |
| Layer 1 | PyInstaller 自动捆绑 | vcruntime140.dll / msvcp140.dll 打包进 backend.exe |
| Layer 2 | NSIS 钩子校验后静默安装 | 安装期三态：哈希匹配→静默安装；确证不匹配→弹窗中止；校验工具（PowerShell）不可用→跳过 redist 安装但不阻断（Layer 1 兜底） |

目标机器无需预装任何 VC++ 运行库。二进制不入库（`.gitignore: resources/vcredist/`），
URL/SHA256 常量唯一维护点：`electron-builder-nsis-hook.nsh` 文件头 `!define` 段。

### 数据目录（非安装目录）

```
%LOCALAPPDATA%\bumofu-assistance\
├── data\rural_revitalization.db   (SQLite 数据库)
├── logs\app.log
├── uploads\
└── ...
```

数据库放在 `%LOCALAPPDATA%` 而非安装目录，避免 Program Files 权限问题。
卸载时由 NSIS 钩子询问是否删除。

## CI/CD

GitHub Actions 工作流 `.github/workflows/build-windows.yml` 在 tag（`v*`）触发时构建
**Windows x64** 安装包并自动发布 GitHub Release；麒麟（国产 Linux）ARM64 的 `.deb` 包
由另一条工作流 `.github/workflows/build-arm64.yml` 构建并发布到**同一个** Release。
**32 位（x86）已放弃**（上游科学计算包不再提供 win32 cp311 wheels），CI 仅出 x64。

## electron-builder 打包方案说明

本项目采用 **electron-builder** 作为 Windows 离线安装包的打包方案，基于以下架构：

1. **PyInstaller** 将 FastAPI 后端打包为独立 exe（`assistance-backend.exe`），内含 Python 3.11 + 全部依赖
2. **electron-builder** 将 Electron 主进程、前端 dist、后端 exe 及 VC++ 运行库整合为单一 NSIS 安装包
3. **extraResources** 机制将后端 exe 和前端静态文件嵌入 Electron 应用资源目录
4. **NSIS 钩子**（`electron-builder-nsis-hook.nsh`）处理 VC++ 静默安装、进程终止和卸载数据清理

通过 `Makefile` 快捷命令 `make build-win-x64` 可一键完成前端构建 → PyInstaller 打包 → electron-builder 打包全流程。
