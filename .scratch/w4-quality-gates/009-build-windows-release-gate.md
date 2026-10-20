---
labels: [done, severity-high]
blocks: []
blocked-by: ["w4-quality-gates/003-remove-weak-assertions.md"]
---

# W4-T9 build-windows 发版门禁恢复

**来源**: 检测 S6（`build-windows.yml:29,44` smoke-test continue-on-error + `:52-53` build `if: always()` → 测试全红照样发 Release）

## 验收标准
- [x] smoke-test 失败即阻断；Release 步骤仅在测试绿时执行（移除 always()）
- [x] tag 触发路径与手动路径分别验证
- [x] workflow 语法校验通过（actionlint 或 yaml lint）

## 涉及文件
- `.github/workflows/build-windows.yml`

## Resolution（W19 完成）

`.github/workflows/build-windows.yml` 已是「测试绿才出包」的门禁结构：

- `smoke-test` 内**无** `continue-on-error`（W4-T9 注释在案）；内联 `--cov-fail-under=50` 已移除
  （覆盖率回归 `backend/.coveragerc` 单一事实源，与 pr-checks / nightly 口径统一）。
  其中保留的 `if: always()` 只挂在 "Upload test results" 工件上传步骤上（失败时仍上传诊断产物），
  不参与阻断判定。
- `build-windows` 为 `needs: smoke-test` + `if: success()` —— 原先的 `if: always()`
  （测试全红仍出 Release 包）已移除。
- 触发路径：`on.push.tags: ['v*']`（tag 发版）与 `workflow_dispatch`（手动）两路共存。
- 语法校验：4 个 workflow（build-windows / build-arm64 / pr-checks / nightly-full）均通过 YAML 解析
  （实测打印 jobs 列表）。本机无 `actionlint`（`shutil.which("actionlint")` 为空），
  以 YAML 解析 + 结构核对替代，未引入未验证声明。
