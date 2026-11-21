# v1.18.59 发布说明 — NSIS 插件依赖 / TEMP 空间预检

> 发布：2026-11-21 ｜ 版本：`1.18.59`

## 一、修订背景

v1.18.58 现场仍有两类安装失败：

1. 旧版运行中直接覆盖安装，安装器可能**退出码 0，但安装目录只写了一半**（例如只有 `resources`，没有主程序）。
2. 磁盘尚有余量、TEMP 也“可写”时，NSIS 仍报：

```text
Error creating mmap to file ...\nsc*.tmp
Error writing temporary file. Make sure your temp folder is valid.
```

## 二、根因与修复

### 1. `customInit` 不应依赖 `nsExec` 插件

`nsExec::Exec` 是 NSIS 插件，首次调用要把插件解压到 `$PLUGINSDIR`；而 electron-builder 的 `customInit` 在 `InitPluginsDir` 之前执行。TEMP 异常或插件解包失败时，taskkill 实际上没有执行，旧主程序继续占用 `app.asar`，覆盖安装随之中断。

修复：

- `build-scripts/electron-builder-nsis-hook.nsh` 的 `customInit` / `customInstall` / `customUnInstall` 全部改为内置 `ExecWait`，直接调用 `$SYSDIR\taskkill.exe`；
- 使用 `/T` 同时结束后端子进程；
- 每次终止后 `Sleep 500~800ms`，等待文件句柄释放；
- 不再依赖 `nsExec` 插件，`customInit` 即使在插件目录初始化前也能可靠终止旧进程。

### 2. Helper 只检查“可写”不够，还要检查“够空间”

`MRRS-Installer-Helper.ps1` 原来只做写探针。可写但接近写满的 TEMP 仍无法提供 NSIS 解包缓冲。

修复：

- 新增 `Get-FreeSpaceMB` 与 `Test-TempCandidate`；
- 所需空间按安装包大小计算：**2 × 安装包 + 512MB**（当前约 1.2~1.3GB）；
- 当前 TEMP 空间不足时自动回退 `%USERPROFILE%\AppData\Local\Temp`、`%WINDIR%\Temp`；
- 显式 `-TempDir` 空间不足时直接报 `free=... / required=...`，不再把问题拖到 NSIS 阶段；
- `Install-MRRS.cmd` 在同目录存在 Helper 时优先委托 Helper，确保双击入口也执行空间预检。

## 三、验证

- 静态回归：`test_installer_temp_helper.py` **5 passed**，覆盖空间预检、cmd 委托、NSIS 无插件 taskkill。
- NSIS 重打：`electron-builder --win nsis --x64 --prepackaged` 成功，无脚本编译错误。
- 实际覆盖安装：旧版运行中执行新安装包，`UPGRADE_EXIT=0`；安装目录 **871 MB / 25 个根文件**；随后启动 `/health` 正常。
- 后端用例口径 **16,045**；完整 PR Checks、Windows x64 + ARM64 构建按 v1.18.59 重跑。

## 四、安装包

- `MRRS-Setup-1.18.59-x64.exe` + `.blockmap` + `latest.yml`
- `Install-MRRS.cmd`（双击启动，自动选择可写且空间充足的 TEMP）
- `MRRS-Installer-Helper.ps1` / `MRRS-Shortcut-Repair.ps1`
- `SHA256SUMS-windows-x64.txt`
- ARM64 Electron deb / standalone deb + SHA256SUMS

## 五、注意事项

- `Install-MRRS.cmd` / Helper 解决的是**安装器启动前**的 TEMP；若企业策略完全禁止用户 Temp 与系统 Temp，仍需管理员修复 TEMP/ACL。
- 直接双击 `MRRS-Setup-*.exe` 时，NSIS 无法在脚本内修改 `%TEMP%`；现场排障请优先使用 `Install-MRRS.cmd` 或 Helper。
- 本机自编译包未签名；正式交付使用 GitHub Release 中 CI 签名包。
- ARM64 仍需麒麟 V10 真机复验。
