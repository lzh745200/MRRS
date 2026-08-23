---
labels: [ready-for-agent, severity-medium]
blocks: []
blocked-by: ["w6-release-eng/009-build-windows-release-gate-w6.md"]
---

# W6-T7 Actions pin 到 commit SHA

**来源**: 检测 M3（checkout/setup-python/gh-release/codecov 等全部主版本 tag，两个 build workflow 有 contents:write）

## 验收标准
- [ ] 全部 workflows 的 uses 固定到具体 commit SHA（注释保留版本号）
- [ ] actionlint / workflow 语法校验通过
