---
labels: [ready-for-agent, severity-low]
blocks: []
blocked-by: []
---

# W6-T10 OFFLINE_UPGRADE.md 升级与回滚文档

**来源**: 检测 L7（无自动更新为有意设计，但升级流程文档缺失）

## 验收标准
- [ ] 文档覆盖：升级前备份 → 校验签名/SHA256 → 安装 → alembic 迁移验证 → 数据兼容检查 → 回滚路径
- [ ] NSIS 卸载 MessageBox 加 `/SD IDNO` 静默默认
