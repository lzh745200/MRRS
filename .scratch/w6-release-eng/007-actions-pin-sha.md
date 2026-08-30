---
labels: [done, severity-medium]
blocks: []
blocked-by: []
---

# W6-T7 Actions pin 到 commit SHA

**来源**: 检测 M3（checkout/setup-python/gh-release/codecov 等全部主版本 tag，两个 build workflow 有 contents:write）

**完成（2026-08-30）**: 全部 4 个 workflow 的 57 处 `uses:` 已固定到具体 commit SHA
（SHA 经 `git ls-remote` 从各上游仓库实时解析，均为 lightweight tag 即 commit；
行尾注释保留原版本号）。YAML 解析全通过，无残留 `@v` tag 引用。
覆盖：checkout / upload-artifact / download-artifact / setup-node / setup-python /
cache / codecov / action-gh-release / docker setup-qemu+buildx+build-push
（v3 与 v4.1.0 两个历史版本各自 pin）。

## 验收标准
- [x] 全部 workflows 的 uses 固定到具体 commit SHA（注释保留版本号）
- [x] actionlint / workflow 语法校验通过（YAML 解析 + 无残留 tag 引用核对）
