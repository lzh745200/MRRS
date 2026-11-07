# v1.18.37 发布说明 — 安装器校验非阻断与打包冒烟隔离

发布日期：2026-11-07

## 谁需要升级

- **遇到过「升级安装到 4% 就中断」的 Windows 工位**：本版修复安装器对 VC++ Redistributable
  的硬失败处理——校验不一致时改为告警并跳过该可选组件，不再中止主程序安装。
- **需要离线验证安装包「装了能启动」的运维/交付人员**：打包后端冒烟脚本改为自隔离运行，
  在受限沙箱与 CI 中都能直接对安装包解包产物做启动验证。
- 功能与 v1.18.36 一致，本版是安装可靠性与验证工具链的补丁版本。

## 本版改动

### 1. 安装器 VC++ 校验非阻断

- 现场问题：升级安装进行到 4% 时，安装器因 `VC++ Redistributable` 的 SHA256 与内置值不符
  直接 `Abort`，用户无法完成升级。
- 修复：VC++ 运行库是可选「双保险」（应用已由 PyInstaller 捆绑 `VCRUNTIME140/MSVCP140`），
  校验不一致时**告警并跳过该组件安装**，主程序照常安装；实际哈希写入安装目录
  `verify_x64_hash.txt` / `verify_x86_hash.txt` 供排障。
- 同时修正 NSIS 钩子中的双反斜杠路径（NSIS 反斜杠不是转义符），并给校验脚本增加
  10×500ms 重试，避免升级时旧卸载器未退出导致的瞬时读文件竞态。
- 回归：`backend/tests/unit/test_installer_vcredist_nonfatal.py` 锁定「哈希失败不 Abort /
  单反斜杠 / 重试」三项契约。

### 2. 打包后端冒烟自隔离

- `scripts/smoke_test_packaged_backend.ps1` 默认把子进程的 `APPDATA`/`LOCALAPPDATA` 指向
  运行目录下的私有 profile，并从 `<resources>/frontend` 自动注入 `FRONTEND_DIST_PATH`。
- 好处：不污染本机用户配置；在受限沙箱中不会因 `%LOCALAPPDATA%` 不可写而卡在
  「初始化安全密钥…」；同时把 `GET /`（前端首页）纳入冒烟。
- 新增 `-FrontendDist` / `-MapTilesDir` / `-NoIsolateUserDirs` 参数，便于显式指定或沿用
  真实用户目录。

### 3. 文档与演示材料

- `docs/04-部署文档/06-打包态启动排障与离线包验证.md` §4.1 同步新参数与隔离说明。
- PPT 演示材料版本标识更新到 v1.18.37。

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
   Get-AuthenticodeSignature .\MRRS-Setup-1.18.37-x64.exe |
     Select-Object Status, @{n='Signer';e={$_.SignerCertificate.Subject}},
                   @{n='Thumbprint';e={$_.SignerCertificate.Thumbprint}}
   ```
   期望签名者为 `CN=MRRS Internal Code Signing, O=MRRS, C=CN`，
   指纹为 `8203900B6DA54201A49BDAF923B2F20D76CA35A1`。

> 安装为 perMachine（所有用户），需要管理员权限。未信任证书时 Windows 仍可能提示
> 「未知发布者」，完成信任后重新运行即可。

## 验证记录

| 项目 | 结果 |
|---|---|
| 后端全量（12 段独立进程） | **12/12 段 PASS，15,689 passed**；合并覆盖率 **100.00%**（0 miss / 0 partial） |
| 前端全量 vitest | **348 文件 / 7,515 用例全通过** |
| 静态与结构门禁 | 三层对齐、文档数字、CHANGELOG、路由鉴权、硬编码色、6 项棘轮、no-assert 全绿 |
| PR Checks | 9/9 jobs 全绿（backend-test / frontend-check / e2e-test / lint / static-analysis / windows-smoke / stack-alignment / upgrade-rehearsal / security） |
| 打包后端冒烟 | 从安装包解包产物启动：liveness / health / version.json 三端点 200，`[smoke] PASS` |
| Electron 单测 | 23 passed |

## 升级步骤

1. 下载 `MRRS-Setup-1.18.37-x64.exe`，用 `SHA256SUMS-windows-x64.txt` 核对 SHA256。
2. 关闭正在运行的系统，直接覆盖安装（数据目录 `%LOCALAPPDATA%\bumofu-assistance` 保留）。
3. 启动后确认 `/version.json` 为 `1.18.37`，既有数据与登录账号不受影响。

## 已知边界

- 安装包**不含离线地图瓦片**（仓库 `.gitignore` 排除瓦片，需构建机拷入 `resources/map-tiles`
  后再构建，或安装后经管理员接口 `POST /api/v1/map/tiles/import` 导入）。
- 自签名证书需目标机信任（见上）；不信任不影响功能，仅影响签名状态与 SmartScreen 提示。
- ARM64 纯 Web 版（`assistance-management-system_<版本>_arm64.deb`）仍为无外部依赖的自包含包。
