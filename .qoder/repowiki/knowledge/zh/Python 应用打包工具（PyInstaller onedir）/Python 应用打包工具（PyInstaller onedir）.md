---
kind: external_dependency
name: Python 应用打包工具（PyInstaller onedir）
slug: pyinstaller
category: external_dependency
category_hints:
    - framework_behavior
scope:
    - '**'
source_files:
    - backend/assistance-backend.spec
    - .github/workflows/build-windows.yml
    - electron/main.js
---

### PyInstaller
- 用途：将 FastAPI 后端打包为独立可执行文件，采用 ADR-0006 规定的 `onedir` 布局（`assistance-backend.exe` + `_internal/` 依赖目录），供 Electron 主进程以子进程形式拉起。
- 构建流程：CI 在 `windows-2022` runner 上安装 Python 3.11 x64，先剥离 prophet/cmdstanpy 后 pip 安装核心依赖，再执行 `python -m PyInstaller assistance-backend.spec --clean --noconfirm`；Linux ARM64 通过 `Dockerfile.backend-arm64` + QEMU 交叉编译。