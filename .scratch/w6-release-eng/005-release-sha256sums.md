---
labels: [ready-for-agent, severity-high]
blocks: []
blocked-by: []
---

# W6-T5 Release 产物完整性链（SHA256SUMS）

**来源**: 检测建议6（军队分发最低要求；sync 脚本仅 du 字节数比对且 >5% 只警告不退出）

## 验收标准
- [ ] 两个 build workflow 在 Release 前生成 SHA256SUMS.txt 一并上传
- [ ] sync-frontend-dist.sh 改为 SHA256 manifest 校验，偏差即退出非零
- [ ] audit_static_assets.py 补哈希校验能力
