# v1.18.58 发布说明 — 安装 TEMP 兜底 / 长期会话 / 备份同盘自检

> 发布：2026-11-21 ｜ 版本：`1.18.58`

## 一、安装 TEMP 链路

- **Helper 同目录查找**：`MRRS-Installer-Helper.ps1` 优先在脚本所在目录查找 `MRRS-Setup-*.exe`，下载目录把 Helper 与安装包放一起即可运行；仓库开发态仍回退 `dist/release`、`dist/electron`。
- **新增 `Install-MRRS.cmd`**：双击启动器会创建可写 `%LOCALAPPDATA%\Temp\MRRS-Setup`，设置 `TEMP/TMP` 后启动同目录安装器；不再要求用户手写 PowerShell 命令。
- 保留 `-TempDir` 手动指定与 `-Persist` 持久化选项，适配企业镜像/策略禁用默认 Temp 的场景。
- Release 资产新增 `Install-MRRS.cmd`。

## 二、刷新令牌改为长期

- 统一为 **30 天**长期会话；ACCESS 仍为 8 小时。
- 消除三处漂移：`config.py`、`security.py`、`token_manager.py` 默认值一致；`.env.example` 同步为 30 天。
- 新增 `test_refresh_token_ttl.py` 锁定三处默认值与实际 JWT `exp`。
- 如需更短/更长，显式设置 `REFRESH_TOKEN_EXPIRE_DAYS`；Kylin 部署模板继续使用 30 天。

## 三、备份同盘自检

- 系统自检新增「备份位置」：备份目录与数据库在同一磁盘/卷时返回 **WARN**，并提示把备份目标改到独立磁盘、移动硬盘或网络盘。
- 无法判断时降级为 WARN，不阻断体检；独立卷为 OK。
- 前端 `SelfCheckCard` 动态渲染，无需新增页面；API 断言同步由 7 项更新为 8 项。

## 四、验证

- 后端定向：安装 TEMP 静态回归 2、刷新令牌 3、自检服务 24、自检 API 4。
- 前端定向（登录/错误/大屏）与完整门禁按 v1.18.58 重跑。
- Windows x64 + ARM64 双流水线构建、安装、版本接口与 Release 资产校验。

## 五、安装包

- `MRRS-Setup-1.18.58-x64.exe` + `.blockmap` + `latest.yml`
- `Install-MRRS.cmd`（TEMP 兜底双击启动）
- `MRRS-Installer-Helper.ps1` / `MRRS-Shortcut-Repair.ps1`
- `SHA256SUMS-windows-x64.txt`
- ARM64 Electron deb / standalone deb + 2 份 SHA256SUMS

## 六、边界

- `Install-MRRS.cmd` 处理的是 NSIS 启动前的 TEMP 问题；若系统策略完全禁止写入用户 Temp 与系统 Temp，仍需由管理员修复 TEMP/ACL。
- 本机自编译包未签名；正式交付请使用 GitHub Release 中 CI 签名包。
- ARM64 仍需麒麟 V10 真机复验。
