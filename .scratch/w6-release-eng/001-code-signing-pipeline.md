---
labels: [needs-info, severity-high]
blocks: []
blocked-by: []
---

# W6-T1 代码签名接入（外部依赖：证书采购）

**来源**: 检测 S1（无 CSC 配置、PyInstaller codesign_identity=None；军队场景无法过白名单）

## 前置（需用户提供）
- EV/OV 代码签名证书（建议硬件令牌）与 CSC_LINK / CSC_KEY_PASSWORD 密钥注入方式

## 验收标准（管线侧先行完成）
- [ ] build-windows.yml 支持可选签名：存在密钥则签 installer + uninstaller + backend.exe（signtool），不存在则显式 WARNING 跳过
- [ ] assistance-backend.spec 签名钩子位预留
- [ ] 文档记录签名验证方法
