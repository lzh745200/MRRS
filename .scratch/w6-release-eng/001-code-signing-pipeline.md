---
labels: [done, severity-high]
blocks: []
blocked-by: []
---

# W6-T1 代码签名接入（外部依赖：证书采购）

**来源**: 检测 S1（无 CSC 配置、PyInstaller codesign_identity=None；军队场景无法过白名单）

## 前置（需用户提供）
- EV/OV 代码签名证书（建议硬件令牌）与 CSC_LINK / CSC_KEY_PASSWORD 密钥注入方式

**完成（2026-08-30，管线侧；证书采购仍为业务动作）**:
- build-windows.yml 第 8.5 步：配置 CSC_LINK/CSC_KEY_PASSWORD secrets 即自动
  signtool 签名后端 exe（SHA256 + RFC3161 时间戳）并 verify /pa /all；未配置
  则显式 WARNING 跳过（构建不失败）。第 10 步 electron-builder 以同一对密钥
  自动签安装包与卸载器。
- assistance-backend.spec codesign_identity 处已注释签名钩子位指向。
- 新增 docs/04-部署文档/01-Windows部署/代码签名.md：secrets 配置、dry-run 步骤、
  Get-AuthenticodeSignature / signtool verify 验证方法、与 SHA256SUMS 的关系。
- 剩余外部动作：证书采购 + secrets 注入（业务侧，见文档第二节）。

## 验收标准（管线侧先行完成）
- [x] build-windows.yml 支持可选签名：存在密钥则签 installer + uninstaller + backend.exe（signtool），不存在则显式 WARNING 跳过
- [x] assistance-backend.spec 签名钩子位预留
- [x] 文档记录签名验证方法
