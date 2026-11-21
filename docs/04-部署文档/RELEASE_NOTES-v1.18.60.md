# v1.18.60 发布说明 — 全库审计收口

> 发布：2026-11-21 ｜ 版本：`1.18.60`

## 一、本版修复

### 安全与数据边界
- `/export/users` 补齐数据域过滤：部门级 admin 只能导出本组织账号，不能枚举全库用户。
- `/auth/refresh` 补初始凭据过期校验：开通包账号 `credential_expires_at` 到期后不能再靠 refresh 续命。
- 分片上传 merge 返回 `/uploads/files/...` 相对 URL，不再泄露服务器绝对路径。
- 数据同步 ZIP 导入补齐新增/更新/跳过统计，冲突跳过不再显示“0 条”。

### 时间与导出口径
- 消息日期筛选：本地日历先转 UTC 再比较，UTC+8 不再漏当天凌晨、串入次日。
- `/export/*`：aware UTC 时间统一转本地墙钟，与异步导出/报表脚注一致。
- 帮扶村年度筛选、看板年度趋势：按本地偏移平移年界，元旦 0–8 点记录不再归错年。
- 报表模板导出、填报导出：超过 5000 行返回 `X-Export-Truncated / Total / Returned / Limit`。

### 前端交互
- 非管理员编辑/删除学校、帮扶村：读取 `pending_approval`，提示“已提交审批”，不再假成功或乐观移除。
- 选择性导出：`since/modules/include_files` 作为 Query 参数发送，关闭加密后不再退化为全量导出。
- 里程碑完成日期使用本地日历，凌晨完成不再写成前一天。
- 合同/影像上传失败透出服务端原因（413/403/422 等）。
- 备份统计、数据管理本月统计失败明确提示，不再伪装成 0。
- 分片上传离开页面后停止后续分片、终检、合并与轮询。

## 二、安装与升级

1. 下载 `MRRS-Setup-1.18.60-x64.exe` 与 `Install-MRRS.cmd`、`MRRS-Installer-Helper.ps1` 到同一目录。
2. **优先双击 `Install-MRRS.cmd`**：它会选择可写且剩余空间≥约 1.3GB 的 TEMP，再启动安装器。
3. 直接双击安装包也可；若出现 `NSIS Error / Error creating mmap`，改用 `Install-MRRS.cmd`。
4. 升级前关闭正在运行的客户端；安装器会 `ExecWait taskkill /T` 终止旧进程并等待句柄释放。
5. 安装后启动，确认 `/health` 返回 `1.18.60`。

## 三、验证

- 后端 **16,054** 用例；前端 **351 文件 / 7,587 用例**；合计 **23,641**。
- 前端改动相关文件覆盖率 100%（BackupManagement、supported-villages、ChunkedUploadManager 按整组跑）。
- 新增回归：用户导出隔离、消息时区、refresh 过期、导出时间、模板/填报截断、导入计数、分片相对路径、卸载停止上传。
- 完整 PR Checks、Windows x64 + ARM64 构建按 v1.18.60 重跑。

## 四、发布资产

- `MRRS-Setup-1.18.60-x64.exe` + `.blockmap` + `latest.yml`
- `Install-MRRS.cmd`、`MRRS-Installer-Helper.ps1`、`MRRS-Shortcut-Repair.ps1`
- `SHA256SUMS-windows-x64.txt`
- ARM64 Electron deb / standalone deb + SHA256SUMS

## 五、仍属产品决策的事项

- `/uploads` 在服务端部署下是否改为签名 URL / nginx `auth_request`（本机桌面可维持现状）。
- 分片上传是否统一到 `/files/upload` 的白名单扩展名策略。
- “每 N 个月自动打包”按日历月还是满 N×30 天。
- 数据质量卡是否改后端全量聚合；当前仍按前 200 条抽样展示。

这些已在审计报告中单独列出，不在本版强行改变业务语义。
