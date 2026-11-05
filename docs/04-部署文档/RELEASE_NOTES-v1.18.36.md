# v1.18.36 发布说明 — 内网自签名代码签名（签名版安装包）

发布日期：2026-11-06

## 谁需要升级

- **内网离线部署的 Windows 工位**：本版安装包、主程序与卸载器均带内网自签名，便于统一
  信任、校验与升级核对；功能与 v1.18.35 完全一致，只新增签名与发布流水线加固。
- **希望「下载即装、离线运行」的机器**：安装包已内置 Electron、PyInstaller 打包的后端、
  前端静态资源、地图瓦片与 VC++ Redistributable，目标机无需另装 Python / Node / 数据库。
- **需要核对安装包真伪的运维人员**：可直接用仓库内
  `docs/04-部署文档/01-Windows部署/MRRS-Internal-CodeSigning.cer` 校验签名者指纹。

## 本版改动

### 1. 内网自签名代码签名

- 证书：`CN=MRRS Internal Code Signing, O=MRRS, C=CN`，自签名，有效期至 **2031-11-05**，
  指纹 `8203900B6DA54201A49BDAF923B2F20D76CA35A1`；公钥证书随仓库发布
  （`docs/04-部署文档/01-Windows部署/MRRS-Internal-CodeSigning.cer`），私钥只存在于
  GitHub Secrets（`CSC_LINK` / `CSC_KEY_PASSWORD`）。
- CI 对后端可执行文件、安装器与卸载器执行 `signtool sign /fd SHA256`（SHA-256 时间戳，
  失败时回退无时间戳签名）。
- 自签名证书不在公共 CA 链上，因此 CI 采用**签名者指纹口径**验签（不写运行器根存储，
  避免 Windows 交互确认导致非交互 runner 挂起）：`SELF_SIGNED_SIGNING=1` +
  `CODESIGN_THUMBPRINT=<指纹>`，状态允许 `Valid / UnknownError / NotTrusted`，但指纹必须匹配。
- `scripts/verify_installer_signature.ps1` 新增 `-AllowUntrustedRoot` 与
  `-ExpectedThumbprint`；构建末尾的安装包与全部 exe 验签均通过（`SIGNATURE_CHECK_PASS`）。

### 2. 安装包自包含与安装期校验

- 安装包内置 `resources/vcredist/vc_redist.x64.exe`，安装时先做 SHA256 校验，再静默安装
  （校验不匹配会中止安装；校验工具不可用时跳过 redist，由 PyInstaller 内置的 vcruntime DLL 兜底）。
- 后端为 PyInstaller onedir 打包，前端为构建产物 `frontend/dist`，地图瓦片随包分发；
  首次启动自动初始化 SQLite 数据库，无需外部服务。

## 安装与信任（重要）

自签名不是公共 CA 证书，**未信任根证书的机器上签名状态会显示为 UnknownError / NotTrusted**，
这是预期行为，不影响程序运行；按下列任一方式信任后可显示为 Valid：

1. **域环境（推荐）**：用 GPO 把 `MRRS-Internal-CodeSigning.cer` 下发到
   「受信任的根证书颁发机构」与「受信任的发布者」。
2. **单机（管理员 PowerShell）**：
   ```powershell
   certutil -addstore -f Root MRRS-Internal-CodeSigning.cer
   certutil -addstore -f TrustedPublisher MRRS-Internal-CodeSigning.cer
   ```
3. **核验签名**：
   ```powershell
   Get-AuthenticodeSignature .\MRRS-Setup-1.18.36-x64.exe |
     Select-Object Status, @{n='Signer';e={$_.SignerCertificate.Subject}},
                   @{n='Thumbprint';e={$_.SignerCertificate.Thumbprint}}
   ```
   期望签名者为 `CN=MRRS Internal Code Signing, O=MRRS, C=CN`，
   指纹为 `8203900B6DA54201A49BDAF923B2F20D76CA35A1`。

> 未信任证书时，Windows SmartScreen 仍可能提示「未知发布者」。这是自签名的正常表现；
> 完成上述信任后重新运行即可。

## 验证记录

| 项目 | 结果 |
|---|---|
| 后端全量（12 段独立进程） | **12/12 段 PASS，15,686 passed**；合并覆盖率 **100.00%**（0 miss / 0 partial） |
| 前端全量 vitest | **348 文件 / 7,508 用例全通过** |
| PR Checks | 9/9 jobs 全绿（backend-test / frontend-check / e2e-test / lint / static-analysis / windows-smoke / stack-alignment / upgrade-rehearsal / security） |
| 签名构建 | `Build Windows Installer (x64)` 全步骤通过；`Sign backend exe`、`Verify installer signature`、`Verify all exe signatures` 均 `SIGNATURE_CHECK_PASS` |
| 交叉验证 | 同一份签名管线已在 v1.18.35 的签名构建 run 42046510963 上实测通过（安装包签名者指纹与证书一致） |
| Electron 单测 | 23 passed |

## 升级步骤

1. 先备份：系统管理 → 备份与存储 → 创建备份（确认文件已加密并留存）。
2. 关闭应用（确认「帮扶管理系统」与 `assistance-backend` 进程已结束）。
3. 运行 `MRRS-Setup-1.18.36-x64.exe` 覆盖安装（默认路径不变则数据库 / 密钥沿用原目录）。
4. 启动后点检：登录 → 数据导入页下载模板并导入一条 → 「导出填报表格」导出后回导 →
   备份与存储页确认历史备份可见。
5. 核对安装包签名（见上）与 `SHA256SUMS-windows-x64.txt`。

## 已知限制

- 自签名证书需目标机信任（GPO 或 `certutil`），否则签名状态为 UnknownError / NotTrusted；
  域内批量部署建议统一用 GPO。
- Windows 安装包为 x64、perMachine 安装，需要管理员权限；ARM64 / 麒麟请使用同版本的
  self-contained deb 包。
- 组织级 `data_scope` 默认 `off`（仅影子观测）；`ORG_MODULE_POLICY_MODE` 默认 `shadow`。
- 授权包 `valid_until` 只提示不降级；空数据表（0 行）从「静默成功」改为 400 是有意的行为变更。
