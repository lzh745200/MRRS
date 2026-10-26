# Release Notes — v1.18.9（2026-10-26）

> 供 GitHub Release 正文使用；逐项变更见根目录 `CHANGELOG.md` 的 `[1.18.9]` 段。
> 本版是**修复版**：解决"系统内的更新日志没有更新"——应用内更新日志长期停在 1.1.1，
> 并把这类"版本说明漂移"用门禁彻底堵死。

## 一、下载与校验

| 安装包 | 适用平台 |
|---|---|
| `MRRS-Setup-1.18.9-x64.exe` | Windows 10/11 x64（NSIS 安装包，含全部运行时） |
| `MRRS-Setup-1.18.9-arm64.deb` | 麒麟 V10 / 统信 ARM64（Electron） |
| `assistance-management-system_1.18.9_arm64.deb` | 麒麟 V10 / 统信 ARM64（standalone，无 Electron） |

同一 Release 附带 **`SHA256SUMS-*.txt`** 校验文件，以及 Windows 自动更新所需的 `latest.yml` / `.exe.blockmap`。

> **体积与 SHA256 以 Release 资产页为准**：安装包由 GitHub Actions 现场构建，
> PyInstaller / electron-builder 产物含时间戳与压缩差异，**不是逐字节可复现**，
> 正文写死哈希会在重跑构建后失效。请以资产页的 `SHA256SUMS-*.txt` 为准。

离线校验（Windows）：

```powershell
Get-FileHash .\MRRS-Setup-1.18.9-x64.exe -Algorithm SHA256
# 与 SHA256SUMS-windows-x64.txt 逐字符比对
```

离线校验（麒麟 / 统信）：

```bash
sha256sum -c SHA256SUMS-electron-deb-arm64.txt
sha256sum -c SHA256SUMS-standalone-deb-arm64.txt
```

所有行必须为 `OK`；出现 `FAILED` 表示文件损坏或被篡改，请勿安装。

> **未签名包提示**：证书尚未采购。首次运行会触发 SmartScreen（「更多信息」→「仍要运行」）；
> 涉密/企业环境请先报白名单或加 Defender 排除项，不要误判为卡死。

## 二、本版修了什么

### 1. 应用内「更新日志」长期不更新（用户可见）

- **现象**：点开系统里的更新日志，最新一条停在 **1.1.1**，此后 17 个小版本的说明全部缺失。
- **根因**：日志数据是 `update_log_service.py` 里一份 **240 行硬编码列表**，
  与 `CHANGELOG.md` 各写各的，而硬编码这份**没有任何门禁**。
- **修法**：删除硬编码，改由 `scripts/sync_update_log.py` 从 `CHANGELOG.md` 生成
  `backend/app/services/version_history_data.py`（1.0.0 起的全部历史版本）。
  升级后打开更新日志，可看到从 1.0.0 到 1.18.9 的完整演进。
- **附带修复**：同一天发布的多个版本（如 1.18.2–1.18.7 均为 10-25）原先时间戳相同，
  列表顺序随机（实测 1.18.2 会排在 1.18.3 前面）。现按版本序号加秒偏移 + `version DESC` 兜底，
  历史库里的老数据也能稳定倒序。

### 2. 发布说明一致性门禁（防复发）

新增 `scripts/check_update_log.py`，一次校验三处，已接入 PR Checks 的 static-analysis 与 `make test-local`：

1. 生成文件必须与 `CHANGELOG.md` 生成结果**逐字节一致**；
2. `backend/version.json` 的 `version` / `release_date` / `build` 必须等于 CHANGELOG 最新段；
3. `version.json` 的 `description` 必须等于 CHANGELOG 最新标题，`features` 不得为空。

> 只改 CHANGELOG 不重跑生成脚本、或只 bump 版本号不改说明，CI 都会直接失败。
> 这类漂移此前已复发 4 次（`version.json` 说明 3 次 + 应用内日志 1 次）。

## 三、升级说明

- **覆盖安装即可**，无需手工迁移数据；升级前系统仍会自动备份一次。
- 首次启动会按新数据初始化更新日志表；**已有记录不会被删除**，
  缺失的历史版本由 `sync_version_history` 补齐。
- 若你的库中更新日志已存在旧记录，列表会同时包含旧记录与新补的历史，
  顺序按版本号倒序，不影响业务数据。

## 四、验证结果

| 项目 | 结果 |
|---|---|
| 发布说明门禁 | `check_update_log.py` / `check_changelog.py` / `check_doc_numbers.py` / `sync-version.js --check` 全部 exit 0 |
| 单元测试 | 更新日志相关 29 例、版本相关 76 例全部通过 |
| 覆盖率 | `app/services/update_log_service.py` 行+分支 **100%**（92 语句 / 26 分支） |
| 端到端 | 全新库启动后 `GET /api/v1/system/update-logs` 返回全部历史版本，首条为当前版本、倒序严格按语义化版本排列 |
| 静态检查 | `flake8 app/`（max-complexity=16）与 `flake8 scripts/` 零违例 |

---

> 本版本为补丁版，无新增业务功能、无数据库结构变更（无新迁移），可安全回滚到 v1.18.8。
