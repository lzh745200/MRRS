---
labels: [in-review, severity-high]
blocks: []
blocked-by: [push-to-origin + 一次手动 workflow_dispatch dry-run（外发动作，需仓库负责人执行）]
---

# W6-T9 build-windows 发版门禁（W6 侧复核）

**来源**: 同 W4-T9，本票确保 tag→Release 链路最终状态：smoke-test 绿 → 构建 → 签名 → SHA256SUMS → Release

**本地复核（2026-08-30，已完成部分）**:
- tag→Release 链路结构复核（build-windows.yml 当前全貌）：
  smoke-test(job) → checkout → 前端构建 → sync → 版本同步 → PyInstaller →
  exe 校验 → Electron 依赖 → main.js 语法门禁(9.5) → **vcredist 拉取+SHA256
  钉扎(9.6, W6-T2)** → electron-builder(10) → **SHA256SUMS 生成(10.5, W6-T5)** →
  artifact 上传(11) → **Release 附 SHA256SUMS + 校验指引 body(12, W6-T5)**。
  两个 workflow YAML 解析通过。
- Release 说明模板：已含 `sha256sum -c` 校验和清单指引与签名占位说明
  （"代码签名（W6-T1）待证书采购到位后启用"）——本项验收达成。
- SHA256SUMS 生成步骤本地 dry-run 实测：中英文文件名 + UTF-8 无 BOM + LF
  行尾，`sha256sum -c` 全 OK（期间实测抓出 WriteAllLines CRLF 缺陷并修复，
  见 commit 65f3bbc7）。
- vcredist 拉取步骤本地 dry-run：跳过路径与真实下载路径均通过；NSIS 钩子
  makensis 编译通过。
- 完整 CI dry-run（fork/手动触发 build-windows.yml + build-arm64.yml）：
  需推送本分支后由仓库负责人手动触发（workflow_dispatch 不建 Release、
  仅产物 artifact，安全）；tag 触发会真实发 Release，验证通过后再做。

## 验收标准
- [ ] 与 W4-T9/W6-T1/W6-T5 联合验证一次完整 dry-run（fork/手动触发）
      —— 等待推送 + 手动触发；本地可验证分项已全部通过（见上）
- [x] Release 说明模板含校验和清单与签名验证说明
