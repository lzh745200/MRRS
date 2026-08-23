---
labels: [ready-for-agent, severity-low]
blocks: []
blocked-by: []
---

# W6-T11 仓库卫生收尾（commit_push_build.bat / secrets 明文回落）

**来源**: 检测 L1/L6（bat 执行 git add -A 有误提交风险；secrets.json safeStorage 不可用时明文回落——Linux 场景）

## 验收标准
- [ ] commit_push_build.bat 改显式路径暂存或加二次确认
- [ ] Linux 无 keyring 场景：secrets.json 设置 0600 权限并在文档标注风险
