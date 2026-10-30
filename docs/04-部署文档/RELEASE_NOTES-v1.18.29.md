# Release Notes — v1.18.29（2026-10-30）

> 上一正式发布是 **v1.18.28**。本版是**多会话全库收口后的统一交付版**，覆盖导出链路、
> 权限边界、系统初始化、备份/调度、错误语义、前端请求与桌面退出等修复。

## 一、下载与校验

| 安装包 | 适用平台 |
|---|---|
| `MRRS-Setup-1.18.29-x64.exe` | Windows 10/11 x64（NSIS 安装包，含全部运行时）|
| `MRRS-Setup-1.18.29-arm64.deb` | 麒麟 V10 / 统信 UOS ARM64（Electron）|
| `assistance-management-system_1.18.29_arm64.deb` | 麒麟 V10 / 统信 UOS ARM64（standalone，无 Electron）|

同一 Release 附带 `SHA256SUMS-*.txt`（三个安装包指纹）与 `latest.yml` /
`MRRS-Setup-1.18.29-x64.exe.blockmap`。本系统无自动更新逻辑，升级走覆盖安装。

```powershell
Get-FileHash .\MRRS-Setup-1.18.29-x64.exe -Algorithm SHA256
```

> **未签名包提示**：证书尚未采购，首次运行会触发 SmartScreen（「更多信息」→「仍要运行」）。

## 二、主要修复

### 1. 大数据导出不再阻塞全站
- 普通导出 / 加密导出 / Excel 导入整体移入线程池；
- ZIP 内 `data.json` 分块流式写入，去掉整包 JSON 字符串第二份内存；
- SQLAlchemy Session 与重活留在同一线程，不跨线程复用。

### 2. 权限边界与错误语义
- 自动审批/批量审批/全局审批视图收敛到超级管理员；
- 项目越权更新/删除返回 403，不再被包装成 500；
- 提醒扫描与统计审计查询失败返回 500，不再伪装成“新增 0 条 / 0 条操作”。

### 3. 初始化与备份安全
- 匿名首次初始化限制为本机 + 空库 + 可选引导令牌；
- 初始化重置密码改走请求体；
- 备份创建收口管理员；`target_dir` 白名单并禁止静态下载目录；
- 自动备份由后端 cron 唯一驱动并热重排。

### 4. 前端与桌面体验
- 网络重试只保留幂等 GET/HEAD，避免 POST 中断重发；
- Electron 退出等待后端优雅停止；
- 综合录入草稿按用户隔离；待办截止日按本地日历比较；
- 帮扶村附件预览/下载走带认证 Blob；地图单层包修复缩放与层级空洞。

## 三、验证

- 后端 CI 等价 12 段全量 + 覆盖率 100% 通过；
- 前端全量 3 分片 7,455 用例通过；`vue-tsc` 0、构建通过；
- 统一门禁 35/35 PASS；
- `node scripts/sync-version.js --check` 通过（1.18.29 同步）；
- `python scripts/sync_update_log.py --check` 通过（117 个版本段，最新 1.18.29）。

## 四、升级方式

1. 关闭正在运行的系统；
2. 运行 `MRRS-Setup-1.18.29-x64.exe` 覆盖安装到原目录；
3. 数据库位于 `%APPDATA%\Assistance-Management-Information-System\database\`，
   覆盖安装不会删除数据；升级前建议先做备份。
