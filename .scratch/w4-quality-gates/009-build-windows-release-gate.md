---
labels: [ready-for-agent, severity-high]
blocks: []
blocked-by: ["w4-quality-gates/003-remove-weak-assertions.md"]
---

# W4-T9 build-windows 发版门禁恢复

**来源**: 检测 S6（`build-windows.yml:29,44` smoke-test continue-on-error + `:52-53` build `if: always()` → 测试全红照样发 Release）

## 验收标准
- [ ] smoke-test 失败即阻断；Release 步骤仅在测试绿时执行（移除 always()）
- [ ] tag 触发路径与手动路径分别验证
- [ ] workflow 语法校验通过（actionlint 或 yaml lint）

## 涉及文件
- `.github/workflows/build-windows.yml`
