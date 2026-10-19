# Release Notes — v1.15.13（待发；最终版本号以 tag 为准，如版本变化请同步文件名与正文）

> 本文件供 GitHub Release 正文使用；对应同版本 CHANGELOG 条目由 Lead 统一维护。

## ⚠️ 升级前必读：会导致功能不可用的配置项

### 1. R33 单位授权包 —— 导入授权包前必须先配置验签公钥

R33 授权包用于「上级下发 → 下级导入」的单位模块授权矩阵，靠 Ed25519 签名防篡改。
**出厂配置下不配置密钥，授权包导入/下发都不可用**：

- **下级（接收方）**：必须配置 `GRANT_PUBKEY`（32 字节 hex Ed25519 **公钥**）。
  未配置时导入带签名授权包返回 400「本机未配置验签公钥，无法校验授权包来源」。
- **上级（下发方）**：配置 `GRANT_SIGNING_KEY`（32 字节 hex **私钥**）用于签发；
  ⚠️ 私钥必须保密，不得提交版本库、不得下发给下级。
- `GRANT_ALLOW_UNSIGNED` **永远保持 false**：开启即摧毁防篡改设计（仅离线演练可临时开启）。
- 生成密钥对（在 `backend` 目录执行）：

  ```bash
  # Windows
  .venv\Scripts\python.exe -c "from app.core.grant_signing import generate_keypair as g; k=g(); print('GRANT_SIGNING_KEY='+k[0]); print('GRANT_PUBKEY='+k[1])"
  # Linux / macOS
  .venv/bin/python -c "from app.core.grant_signing import generate_keypair as g; k=g(); print('GRANT_SIGNING_KEY='+k[0]); print('GRANT_PUBKEY='+k[1])"
  ```

- 配置位置：Linux 写入 `/opt/assistance-management-system/config/kylin.env`（systemd EnvironmentFile）；
  Windows 配置系统/用户环境变量；后端 `.env` 同样生效。
- 详细步骤见 `docs/04-部署文档/README.md` 的「部署前置检查 → 3. R33 单位授权包签名」。

### 2. 多机 / 局域网 / 非回环部署：PASS_CODE_SECRET 全实例一致

所有实例必须配置**同一随机** `PASS_CODE_SECRET`；未配置时来自非本机回环地址的自助注册/
通行码自验证会被 fail-closed 拒绝（403）。单机回环部署可留空。

### 3. viewer 角色为严格只读

`viewer` 的所有写操作（POST/PUT/PATCH/DELETE，含直连 API）由服务端返回 **403**；
需要录入/审批/导出的账号请使用 `user` 及以上角色。

### 4. R33 写收窄 `GRANT_GUARD_MODE` 默认 off（可选能力）

- `off`（默认）：仅菜单裁剪生效，接口层不做额外写拦截；
- `shadow`：只记日志不拦截（上线前收集"将被拦"清单）；
- `enforce`：越权写返回 403。
- **生产建议**：先 `shadow` 观察 1~2 周再 `enforce`，不要把默认值直接改为 enforce。

## 安装包

| 平台 | 产物 | 说明 |
|---|---|---|
| Windows 10/11 x64 | `MRRS-Setup-<version>-x64.exe` | NSIS 安装包，内置 Python 运行时与 VC++ 运行库，目标机零依赖 |
| 麒麟 V10 ARM64 | `MRRS-Setup-<version>-arm64.deb` | Electron 桌面版（buildx + QEMU 交叉构建） |
| 麒麟 V10 ARM64 | `assistance-management-system_<version>_arm64.deb` | standalone 纯 Web 版（systemd 托管，浏览器访问） |
| 全部 | `SHA256SUMS-*.txt` | 分发前务必校验（`sha256sum -c`） |

## 发布门禁说明

- Tag 构建前强制校验 **tag commit 的 PR Checks 必须全绿**（Windows 与 ARM64 同口径）；
  门禁红时不会产出 Release，避免"构建成功即发布"绕过质量门禁。
- 后端测试为 **12 段独立进程**执行（`--cov-append` 合并，覆盖率 100% 由 `.coveragerc` fail_under 单一来源判定）；
  前端 12 组 glob 覆盖率阈值 100%。
- 安装包冒烟：解包直跑后端并断言 `/health`（版本/构建指纹/迁移 head）、包内禁含测试资产、构建指纹 `builder=ci`。

## 主要变更（v1.15.8 ~ v1.15.13）

- **安全**：viewer 严格只读（服务端 403）；非回环自助注册 fail-closed；ARM64 工作流补发布门禁。
- **R33 单位授权**：上级配置单位模块授权矩阵并 Ed25519 签名下发，下级验签导入；写收窄默认 off。
- **CI 稳定性**：后端测试改 12 段独立进程（消除"约 24 分钟进程消失"型失败）；nightly 后端同步多段执行。
- **文档/演示**：部署安全必配项（PASS_CODE_SECRET / viewer / GRANT_*）；介绍 PPT 更新至 v1.15.12。

## 已知事项

- 代码签名待证书采购：当前安装包未签名，Windows 首次运行可能触发 SmartScreen 提示（不影响安装）。
- v1.15.0 ~ v1.15.7 的 Release 未产出 Windows x64 安装包：原因为发布门禁正确拦截了红色 PR Checks
  （v1.15.5/v1.15.7 门禁超时/未通过）与一次 action SHA 基建故障（v1.15.6 Set up job 3 秒失败）；
  构建链本身与 v1.14.3 成功产出 x64 安装包时一致。门禁全绿后恢复双平台产出。
