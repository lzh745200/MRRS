# 离线升级与回滚指南

> 适用范围：Windows 10/11（Electron 安装包）与麒麟 V10（DEB 包）。
> 本系统为**离线单机部署**，无自动更新（有意设计）——升级 = 下载新版安装包，
> 在目标机覆盖安装。本文档给出完整的安全升级流程与回滚路径。

## 一、升级前：备份（必做）

升级会**覆盖程序目录，但不动用户数据目录**（见下表）。尽管如此，升级前必须
备份一次数据库——新版首次启动会自动执行 Alembic 数据库迁移，该操作不可自动回退。

| 平台 | 程序目录（升级覆盖） | 用户数据目录（升级保留） |
|------|---------------------|--------------------------|
| Windows | `C:\Program Files\帮扶管理系统\` | `%LOCALAPPDATA%\bumofu-assistance\` |
| 麒麟（Electron DEB） | `/opt/assistance-management-system/` | `~/.config/bumofu-assistance/`（配置）+ `~/.bumofu/data/`（数据库） |
| 麒麟（standalone DEB） | `/opt/assistance-management-system/` | 部署目录下 `data/`（由 systemd 服务配置决定） |

备份方式（三选一，推荐①）：

1. **应用内备份**（推荐）：管理员登录 → 系统管理 → 数据备份 → 立即备份。
   产物为 `.zip` 包（含数据库），记下其存放路径。
2. **手动复制**：直接复制上表用户数据目录中的 `rural_revitalization.db`
   （先退出应用，确保数据库已落盘）。
3. **整机快照**（军队场景如有）：虚拟机/还原卡快照。

## 二、升级包获取与校验

1. 从 GitHub Releases（或内部下发渠道）获取新版安装包与配套
   `SHA256SUMS-*.txt`：
   - Windows x64：`MRRS-Setup-<版本>.exe`（如 `MRRS-Setup-1.11.4.exe`）+
     `SHA256SUMS-windows-x64.txt`
   - 麒麟 ARM64：Electron 版 `MRRS-Setup-<版本>.deb`、standalone 版
     `assistance-management-system_<版本>_arm64.deb` +
     `SHA256SUMS-electron-deb-arm64.txt` /
     `SHA256SUMS-standalone-deb-arm64.txt`

   > 文件名由 `package.json` 的 `build.artifactName`（`MRRS-Setup-${version}.${ext}`）
   > 决定，不是产品显示名「帮扶管理系统」。
2. 放入同一目录后校验完整性（**任何 FAILED 都必须停止升级**）：

   ```bash
   sha256sum -c SHA256SUMS-windows-x64.txt
   # 所有行必须为 OK
   ```

   Windows 上可在 Git Bash 中执行；或用 PowerShell：
   `Get-FileHash -Algorithm SHA256 .\安装包.exe` 后人工比对清单值。
3. **签名校验**（待代码签名证书采购到位后启用，见
   [代码签名](01-Windows部署/代码签名.md)）：右键安装包 → 属性 → 数字签名，
   或 PowerShell `Get-AuthenticodeSignature .\安装包.exe`。

## 三、执行升级

### Windows

1. 退出运行中的应用（托盘图标 → 退出；升级程序也会自动结束旧进程）。
2. 双击新版 `Setup.exe` → 安装程序默认安装到原目录（覆盖安装）。
   用户数据与数据库**自动保留**。
3. 安装完成后启动应用。**首次启动时后端自动执行 Alembic 数据库迁移**
   （`upgrade head`，日志见 `%LOCALAPPDATA%\bumofu-assistance\logs\app.log`），
   等待时间可能略长于平时（首次启动需解压/迁移），属正常现象。
4. 验证：登录后查看 **系统管理 → 更新日志**（版本号应为新版）；
   抽查核心列表页与一次导出操作。

### 麒麟 V10

```bash
# Electron DEB / standalone DEB 均为覆盖安装（数据目录自动保留）
sudo dpkg -i <新版>.deb

# 重启服务（standalone）
sudo systemctl restart assistance-system
```

## 四、数据兼容说明

- 新版 → 旧库：首次启动自动迁移（Alembic），正常情况无需人工干预。
- **迁移失败的后果按环境分流**（`app/main.py` 的 `_run_alembic_upgrade`）：
  - **生产环境（安装包默认，`ENVIRONMENT=production`）：迁移失败会中止启动**
    （fail-loud），日志先记 `ERROR` 完整异常栈、再记 `CRITICAL`
    `生产环境迁移失败——中止启动…`。这是有意设计：避免带着漂移的 schema 长期运行
    造成不可见的数据风险。**代价是升级现场可能表现为"应用起不来"**，此时必须
    取 `%LOCALAPPDATA%\bumofu-assistance\logs\app.log` 排查，不要反复重装。
  - **开发/测试环境**：保持启动韧性，记 `ERROR` 后降级为"自动补列"兜底并附
    `WARNING`，应用仍可用但 schema 可能落后 head。
- **快速判据（无需翻日志）**：后端起来后访问 `/health`，看 `migration` 子对象——
  `at_head: true` 表示已达目标版本；`false` 表示未达，`head` 是目标 revision、
  `error_type` 是失败异常类名（该端点无需认证，故只出类名不出异常原文，
  完整细节在 app.log）。
- **旧版 → 新库（降级）**：Alembic 迁移是**前向**的，旧版程序遇到新版库结构
  可能不兼容 —— 因此回滚必须连同数据库一起回退（见下节）。

## 五、回滚路径

1. **仅程序回退**（未启动过新版、数据库未迁移）：直接安装旧版安装包覆盖即可。
2. **程序 + 数据回退**（新版已运行过、迁移已执行）：
   1. 卸载或直接覆盖安装**旧版**安装包；
   2. 恢复升级前备份：
      - 应用内备份包：管理员 → 系统管理 → 数据备份 → 恢复（选择 `.zip`，
        加密包需输入备份密码）；
      - 手动备份：退出应用，用备份的 `rural_revitalization.db` 覆盖用户数据
        目录中的同名文件；
   3. 启动旧版应用，验证数据完整。
3. 回滚后如需再次升级，重新走本文档全流程即可。

## 六、升级检查清单（速查）

- [ ] 退出应用
- [ ] 备份数据库（应用内备份或复制 .db）
- [ ] `sha256sum -c` 校验安装包 = OK
- [ ] （证书到位后）数字签名校验通过
- [ ] 覆盖安装
- [ ] 首次启动等待迁移完成，查看 app.log 无 `Alembic upgrade 失败`
- [ ] 登录 → 更新日志版本核对 → 核心功能抽查
- [ ] 旧安装包与备份留存至新版稳定运行至少一周
