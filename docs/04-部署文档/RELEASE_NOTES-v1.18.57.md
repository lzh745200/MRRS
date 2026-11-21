# v1.18.57 发布说明 — 审计收口 + 首启/标识/大屏修复

> 发布：2026-11-21 ｜ 版本：`1.18.57`

## 一、审计收口（本版主线）

1. **账号初始凭据过期死锁（P0）**：改密成功清空 `credential_expires_at`；管理员重置同样清空，并仅对“确因过期被停用”的账号恢复启用，人工停用账号不会被误启用；登录提示改为可操作文案。
2. **汇报大屏筛选整表载入（P1）**：帮扶单位 facet 改为 4 条 `GROUP BY ... COUNT(*)`，新增 `perf_facet_indexes_001` 两个索引，避免省级数据每次打开筛选搬数万行。
3. **审计导出静默截断（P1）**：先 `count()` 取真实总数，CSV/Excel 带 `X-Export-Truncated/Total/Returned/Limit`，JSON 返回真实 total；不再把 5000 条上限伪装成“刚好导完”。
4. **系统自检新增“包签名校验”**：未配置 `PACKAGE_PUBKEY` / `GRANT_PUBKEY` / `ACCOUNT_PACKAGE_PUBKEY` 时明确告警。
5. **刷新令牌默认 30 天 → 7 天**；麒麟 root 运行 `--no-sandbox` 降级写入诊断日志。

## 二、同时包含的 1.18.56 修复

- `REAUTH_REQUIRED` 裸协议码不再直出：428 取消静默、重放失败中文提示、并发密码框合并。
- 统一错误码中文：`REAUTH_REQUIRED`、账号包 429/403 业务码及 `{detail:{code,message}}`。
- 安装后标识：快捷方式使用主程序内嵌图标（16~256 七档），窗口图标 `icon.png → app-circle.ico` 兜底，固定 Windows AppUserModelID。
- 首次启动引导：登录页首启横幅“机器码 → 权限包 → 管理员开通账号”，点击展开三步；登录后未完成引导仍展示一次。
- 汇报大屏深色化：深蓝渐变、玻璃 KPI/图表面板、暗色筛选条与设置抽屉、深色 ECharts 坐标/tooltip。
- 本地构建入口：`build`/`build:win` 纳入 `build:frontend`，避免打包旧前端产物。

## 三、验证

- 前端相关回归 **404 例**通过；登录页/错误消息/首启分支覆盖率 100%。
- 后端账号包 68 例、凭据过期 3 例、审计导出 3 例、自检 22 例、发布门禁 13 例通过。
- `npm run check:provenance`、CHANGELOG/更新日志/文档计数通过。
- Windows/ARM64 双流水线构建、安装、启动、版本接口与发布后资产校验。

## 四、安装包

- `MRRS-Setup-1.18.57-x64.exe` + `.blockmap` + `latest.yml`
- `MRRS-Setup-1.18.57-arm64.deb`
- `assistance-management-system_1.18.57_arm64.deb`
- 3 份 `SHA256SUMS-*.txt`
- `MRRS-Installer-Helper.ps1` / `MRRS-Shortcut-Repair.ps1`

## 五、已知边界

- 系统按设计无自动更新，升级为手动覆盖安装。
- 内网自签名证书需目标机预置信任；静默安装不弹证书导入询问。
- ARM64 需在麒麟 V10 ARM64 真机复验。
- 若 `%TEMP%` 指向已删除/只读/已满目录，NSIS 会在安装逻辑前失败，请用 `MRRS-Installer-Helper.ps1` 指定可写 TEMP 启动。
