---
kind: external_dependency
name: 桌面壳与安装包打包（Electron + electron-builder）
slug: electron-electron-builder
category: external_dependency
category_hints:
    - framework_behavior
    - migration_status
scope:
    - '**'
source_files:
    - electron/main.js
    - package.json
    - .github/workflows/build-windows.yml
    - .github/workflows/build-arm64.yml
---

### Electron + electron-builder
- 角色：桌面应用壳（`electron/main.js`），负责启动 PyInstaller 打包的后端进程、加载前端页面、托盘/快捷键/自动备份/崩溃恢复等系统级能力。
- 打包产物：Windows 使用 NSIS 生成 `.exe` 安装包（`deleteAppDataOnUninstall=false`，升级覆盖安装保留 Roaming 下的 userData 数据）；Linux 使用 dpkg-deb 生成 ARM64 DEB，安装到 `/opt/帮扶管理系统` 或 `/opt/assistance-management-system`。
- 行为约定：首次启动探测 8000 端口，占用则顺延备用端口；后端异常退出最多自动重启 3 次；通过 `X-Internal-Backup` / `X-Internal-Shutdown` 内部密钥调用后端管理接口；Linux 下 postinst 会修复 PyInstaller onedir 二进制权限与 Chromium SUID sandbox 位。