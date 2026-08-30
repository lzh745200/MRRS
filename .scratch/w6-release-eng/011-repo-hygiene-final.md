---
labels: [done, severity-low]
blocks: []
blocked-by: []
---

# W6-T11 仓库卫生收尾（commit_push_build.bat / secrets 明文回落）

**来源**: 检测 L1/L6（bat 执行 git add -A 有误提交风险；secrets.json safeStorage 不可用时明文回落——Linux 场景）

**完成（2026-08-30）**:
- commit_push_build.bat：已在 W6-T8 死配置清理中删除（全仓 find 无残留），
  本项自然关闭。
- secrets.json 明文回落（electron/main.js `_writeSecrets`）：safeStorage 不可用
  分支写入后 `fs.chmodSync(SECRETS_FILE, 0o600)`（Windows 忽略）+ 显式告警
  日志；风险说明写入 docs/04-部署文档/02-Linux部署/麒麟V10离线部署完整方案.md
  （Electron DEB 无 keyring 场景 → 建议 standalone DEB + 环境变量注入密钥）。

## 验收标准
- [x] commit_push_build.bat 改显式路径暂存或加二次确认（文件已随 W6-T8 删除，关闭）
- [x] Linux 无 keyring 场景：secrets.json 设置 0600 权限并在文档标注风险
