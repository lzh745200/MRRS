---
labels: [done, severity-high]
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
**dry-run 完成（2026-08-30，以真实 tag 构建达成）**: v1.11.0 标签构建两轮
迭代后全绿（smoke-test → PyInstaller onedir → vcredist 拉取 → electron-builder
→ SHA256SUMS → Release 附件），Release 实物验证 `sha256sum -c` 通过。
过程中实测修复两个管线 bug：① fetch_vcredist 写临时文件前目标目录不存在
（CI 全新 checkout 被 gitignore）→ 建目录提前；② CSC secret 缺失时空串
CSC_LINK 被 electron-builder 24.x 当证书路径解析 → 改 GITHUB_ENV 按需导出。
另发现并处理：GitHub Release 资产名剥离非 ASCII 字符（中文名安装包上传后
变为 Setup.1.11.0.exe），导致校验清单与资产名不匹配——package.json 显式
`artifactName: "MRRS-Setup-${version}.${ext}"` 防复发，当前 Release 清单已
修正为实际资产名并实测哈希一致。

- [x] 与 W4-T9/W6-T1/W6-T5 联合验证一次完整 dry-run（fork/手动触发）
      —— 以 v1.11.0 真实 tag 构建达成，全绿
- [x] Release 说明模板含校验和清单与签名验证说明
