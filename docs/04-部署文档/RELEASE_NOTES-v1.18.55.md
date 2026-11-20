# v1.18.55 发布说明 — 安装器图标/临时目录修复与账号包限流收口

> 发布：2026-11-20 ｜ 版本：`1.18.55`

## 一、本版重点

1. **桌面/开始菜单图标修复**：安装钩子先展开 `$INSTDIR`，用绝对路径写 `IconLocation`；图标缺失回退 exe 内嵌图标；覆盖安装先删除旧 lnk，避免 `%SystemDrive%` 未展开导致的白纸图标。
2. **安装器临时目录错误**：NSIS 在 `InitPluginsDir` 阶段使用 `%TEMP%`，脚本内无法赋值。Release 附带 `MRRS-Installer-Helper.ps1`，探测并切换到可写 TEMP 后再启动安装器；另附 `MRRS-Shortcut-Repair.ps1` 修复已安装机器的图标/证书信任。
3. **账号包失败尝试限流**：`ACCOUNT_PACKAGE_MAX_ATTEMPTS` 生效；新增 `account_package_attempts` 台账（迁移 `account_package_attempts_001`），导出按签发人、导入按机器码计数；失败达阈值 429 `AP_ATTEMPTS_EXCEEDED`，重试过快 429 `AP_RATE_LIMITED`，成功清零；新增锁定/间隔配置。
4. **发布资产校验**：构建前后校验 latest.yml/blockmap/SHA256SUMS，发布后通过 GitHub API size/digest/正文校验；Windows Release 额外上传两个现场修复脚本。

## 二、安装器临时目录问题

如果双击安装器出现：

```
NSIS Error
Error writing temporary file. Make sure your temp folder is valid.
```

说明 NSIS 在解压自身插件到 `%TEMP%` 时失败，安装脚本尚未执行，**不是应用代码/后端启动错误**。处理：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\MRRS-Installer-Helper.ps1 -Installer .\MRRS-Setup-1.18.55-x64.exe
```

脚本会探测当前 `%TEMP%` 是否真实存在且可写，必要时切换到 `%LOCALAPPDATA%\Temp` 或 `%WINDIR%\Temp`，再启动安装器。详见 `docs/04-部署文档/01-Windows部署/安装器临时目录问题排查.md`。

## 三、验证

- 账号包后端 8 个测试文件 **68 passed**；新增限流台账/接口 14 例、迁移自证 3 例。
- 版本端点/VersionService/spec 打包回归 **48 例**、发布资产门禁 **40 例**通过。
- 干净 tag worktree 构建并安装：主程序版本 `1.18.55`；`/health` 迁移头 `at_head=true`；`/api/v1/system/version` 返回 `release_date=2026-11-20`、本版描述。
- `/health`、登录窗口、开始菜单/桌面快捷方式与卸载注册项均复验。

## 四、产物

- `MRRS-Setup-1.18.55-x64.exe` + `.blockmap` + `latest.yml`
- `MRRS-Setup-1.18.55-arm64.deb`
- `assistance-management-system_1.18.55_arm64.deb`
- `SHA256SUMS-windows-x64.txt` / `SHA256SUMS-electron-deb-arm64.txt` / `SHA256SUMS-standalone-deb-arm64.txt`
- `MRRS-Installer-Helper.ps1` / `MRRS-Shortcut-Repair.ps1`（Windows Release 附加）

## 五、已知边界

- 系统按设计无自动更新，升级为手动覆盖安装。
- 内网自签名证书需目标机预置 Root/TrustedPublisher 信任；静默安装不会弹证书导入询问。
- ARM64 需在麒麟 V10 ARM64 真机复验；本版完成构建、包结构、依赖与哈希验证。
- 若 `%TEMP%` 指向已拔出的外接盘/只读 ACL/已满磁盘，请先修复系统临时目录，再用 Helper 脚本启动。
