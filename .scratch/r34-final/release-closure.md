# R34 发布闭环报告 — 文档 / PPT / Windows 构建链终审（ops-probe）

- 时间：2026-10-19｜基线：HEAD 2ad1f47（v1.15.12，origin 同步）
- 范围：docs 文档更新、介绍 PPT 更新、build-windows 构建链终审、GRANT_* 文档补充（Lead 追加的 P1-1/P1-2）
- 未执行：git 写操作、全量测试（Lead 统一跑）、PyInstaller/electron-builder 完整重跑

## 1. 文档更新

### 1.1 已修改
| 文件 | 变更 |
|---|---|
| README.md | 版本页脚保持 v1.15.12（Lead 已改）；后端测试 13,710→13,926（1 skipped，注明本机 12 段实测/CI 为准）、前端 6,826→6,865；badge tests 20,500+→20,700+；新增「部署安全必配项」（PASS_CODE_SECRET / viewer 只读 / GRANT_* / GRANT_GUARD_MODE）；新增近期修复记录 v1.15.8~v1.15.12 |
| CLAUDE.md | 后端用例 11244→13,900+（CI 12 段独立进程）；前端 302 文件/6051→328 文件/6,865；构建命令中已不存在的 build-scripts/*.bat|.sh 改为 `scripts/build/build-installer-local.ps1` 与 `make build-kylin-arm64` |
| .env.example | 新增 R33 授权包签名配置块（GRANT_GUARD_MODE=off / GRANT_SIGNING_KEY= / GRANT_PUBKEY= / GRANT_ALLOW_UNSIGNED=false）与生成密钥对命令；PASS_CODE_SECRET 注释保持 v1.15.7 口径 |
| docs/04-部署文档/README.md | 「部署前置检查（安全红线）」扩为 4 项：新增「3. R33 单位授权包签名（导入前必须先配置验签公钥）」「4. R33 写收窄 GRANT_GUARD_MODE 默认 off，先 shadow 再 enforce」 |
| docs/04-部署文档/02-Linux部署/国产电脑一键安装指南.md | 多机安全必配项增加 R33 授权包（下级先配 GRANT_PUBKEY）说明 |
| docs/帮扶管理信息系统介绍.pptx | 见 §2（已更新） |
| docs/04-部署文档/RELEASE_NOTES-v1.15.13.md（新增） | Release 正文草稿：升级前必读（GRANT 公钥/私钥、ALLOW_UNSIGNED 永远 false、PASS_CODE_SECRET、viewer 只读、GUARD_MODE 默认 off）、安装包清单、发布门禁说明、主要变更、已知事项 |
| docs/帮扶管理信息系统介绍-更新说明-v1.15.12.md（新增） | PPT 更新说明（与 .scratch/r34-final/ppt-update-notes.md 同源） |

### 1.2 核查后未改（避免大改）
- AGENTS.md / CONTEXT.md：grep `11244|13,710|6,826|20,500|build_windows_complete|build-linux-arm64|v1.15.0` 均 0 命中，无需修改。
- CHANGELOG.md：按硬约束由 Lead 统一维护。**建议 v1.15.13 条目要点**（可直接粘贴整理）：
  - 安全：viewer 严格只读（写接口服务端 403）；未配置 PASS_CODE_SECRET 时非回环自助注册 fail-closed；ARM64 工作流补发布门禁。
  - R33 单位授权：上级配置矩阵 + Ed25519 签名下发，下级验签导入；`GRANT_GUARD_MODE` 默认 off（shadow→enforce 可选）；导入前必须配置 `GRANT_PUBKEY`，`GRANT_ALLOW_UNSIGNED` 永远 false。
  - CI：后端测试 12 段独立进程（--cov-append 合并，覆盖率 100% 单一来源）；nightly 后端多段稳定化；Nightly 前端内存/重试加固。
  - 文档：部署安全必配项、Release Notes、介绍 PPT 更新。

## 2. PPT 更新（docs/帮扶管理信息系统介绍.pptx）

- 工具：`backend/.venv313/Scripts/python.exe` + python-pptx 1.0.2（项目既有 PPT 更新环境；`backend/.venv` 未安装 python-pptx）。
- 原始备份：`.scratch/r34-final/帮扶管理信息系统介绍-原始备份.pptx`；脚本：`.scratch/r34-final/update_ppt.py`；版本号二次调整脚本：`.scratch/r34-final/bump_ppt_version.py <x.y.z>`。
- 变更：全量 v1.15.0→v1.15.12；测试规模 13,926 / 6,865；slide 42 CI/CD 更新为 12 段后端 + 发布门禁 + 双平台产物；slide 43 增加 CI 安装包冒烟与构建指纹；slide 46 包体积按实际更新（~286MB / ~205MB / ~61MB）；slide 48 版本历程补 v1.15.8 安全收官与 v1.15.12 R33；slide 17/33 功能清单补 R33 单位授权。
- 验证：重新打开成功（50 页）；**shape 总数 841 与原始完全一致（0 结构丢失）**；溢出启发式扫描仅 1 处为原始既有（slide 08 Text 15），本次修改未新增溢出；12 个关键文本断言全部命中；文件 1.0MB→198KB 属 python-pptx 重新压缩 + 2 个未被引用 slideLayout/1 个 0 字节 media 占位被丢弃，内容无丢失。
- **版本注意**：PPT 当前按 v1.15.12 更新；若最终发布版本为 v1.15.13，运行 `backend\.venv313\Scripts\python.exe .scratch\r34-final\bump_ppt_version.py 1.15.13` 即可同步（只改文本版本号，不动版式）。

## 3. Windows 构建链终审（关键）

### 3.1 结论
**构建链本身与 v1.14.3 成功产出 Windows x64 安装包时一致，未发现代码/配置层阻断**；v1.15.0 之后未产出 Windows 安装包的原因是**发布门禁按设计拦截了红色 PR Checks**（以及 v1.15.6 一次 action SHA 基建故障），而不是 build-windows 构建失败。只要 tag 指向的提交 PR Checks 全绿，预计可恢复产出。

### 3.2 证据：v1.15.0 以来 Windows Release 缺失
- GitHub Releases（匿名 API）: v1.14.0 / v1.14.3 含 `MRRS-Setup-*-x64.exe`（约 285.9MB）；v1.15.0/1/2/5/6/7 的 Release **只有 4 个 ARM64 deb asset**，无 Windows exe。
- build-windows 历史 run 逐条定位（jobs API）：
  - v1.15.5（9de7aea）：smoke-test 853s 后失败于 **"Verify release gate is green"**，build-windows skipped → 门禁拦截（该 tag commit PR Checks 红）。
  - v1.15.6（0715086）：smoke-test **"Set up job" 3 秒失败** → 当时 workflow 的无效 action SHA 基建故障（已由 b786075 回滚修复）。
  - v1.15.7（b786075）：smoke-test 1576s 后失败于 **"Verify release gate is green"** → 门禁再次正确拦截。
  - v1.15.12（2ad1f47，当前）：三工作流 in_progress；PR Checks 已完成 `lint`/`static-analysis`/`frontend-check`/`windows-smoke` **failure**（均为工作区未提交修复项：flake8 F401 @grant_package_service.py、prettier @OrgGrant.vue、README 版本同步）；`backend-test` 仍在跑。→ 该 tag 的 smoke-test 门禁将再次拦截，属预期。

### 3.3 证据：构建步骤与配置一致性（无失效路径/硬编码）
- `git diff --stat v1.14.3..HEAD -- .github/workflows/build-windows.yml` = **仅 5 行**（timeout 30→90 + 注释），构建作业步骤与 v1.14.3 成功时一致。
- 关键路径存在性：`backend/requirements-build.txt`（pyinstaller==6.11.1）、`scripts/build/fetch_vcredist.ps1`、`build-scripts/electron-builder-nsis-hook.nsh`、`resources/icons/{app-circle.ico,app-circle-256.png}`、`scripts/verify_package_no_tests.py`、`scripts/generate_build_info.py`、`scripts/verify_build_info.py` 全部存在。
- electron-builder 配置：package.json build 段（NSIS/signing/extraResources/deb）自 v1.14.3 未变（diff 仅 version 与 build:backend 脚本）；electron-builder 24.13.3、electron 33.3.1 与 v1.14.3 相同。
- 前端依赖：vite 7.3.6 + @vitejs/plugin-vue 6.0.10，lock 一致；CI 用 `npm ci --legacy-peer-deps || npm install --legacy-peer-deps` 双保险。
- VC++ 运行库：**刚实测下载 aka.ms 官方 x64/x86 二进制并比对 SHA256，与 nsis hook `!define` 钉扎值完全一致**（x64 CC0FF0EB…、x86 0C09F261…）→ fetch 步骤不会因上游轮换失配。
- 版本单源：`node scripts/sync-version.js --check` 通过（22 目标全 ok）。
- 发布门禁超时：smoke-test job timeout 90 > gate 轮询上限 75 分钟（v1.15.5 修复），不会先被 job timeout 杀掉。

### 3.4 风险点（按现有证据排序）
1. **前置条件（高确定）**：tag 必须打在 PR Checks 全绿的提交上。当前 HEAD 的 PR Checks 因工作区未提交修复而红；需 Lead 提交+推送修复 → 等 PR Checks 全绿 → 再打新 tag（v1.15.13）。否则 release gate 会再次正确拦截。
2. **NSIS 卸载器提取步骤（本机环境风险，CI 历史上正常）**：electron-builder 构建 NSIS 时会执行刚生成的安装器以提取卸载器（NsisTarget.computeScriptAndSignUninstaller → execWine(installerPath)）。本机 v1.15.6/7/8 的本地构建日志均在 "building target=nsis" 后报 `Exit code: null. Command failed: MRRS-Setup-*.exe`（安装器进程被终止/拦截）；本机为管理员权限，倾向杀软/EDR 拦截。GitHub windows-2022 runner 无同类端点防护，且 v1.14.3 同配置 CI 成功产出 285.9MB exe → 判为**本机环境问题**，但仍是首个需要盯的步骤；失败时 workflow 已上传 packaged-backend-smoke-logs / release-smoke-logs artifact。
3. **构建时长（中低）**：v1.15.x 后端新增 OCR/onnxruntime 依赖（v1.14.3 已包含并成功）；build-windows timeout 90 分钟，未见历史超时证据；首次跑新 tag 建议观察 build job 前 20 分钟。
4. **Node20 deprecation（低）**：checkout/setup-python/upload-artifact/cache 等仍为 node20 版本（b786075 回滚了升级），仅 warning 不影响构建；如需清除告警可单独一次升级+首跑验证（映射与验证方法已在上轮报告 P1-1）。
5. **Windows x64 未签名（已知）**：CSC_LINK 未配置 → 构建跳过签名，SmartScreen 提示属预期，不影响安装。

### 3.5 tag 推送后预计成功的依据（一句话版）
同一 workflow（仅 timeout 改动）、同一 electron-builder/NSIS/VC++ 配置与钉扎、同一 runner 镜像曾在 v1.14.3 成功产出 x64 安装包；本次唯一新增前置是"gate 必须绿"，而 gate 红是当前 PR Checks 工作区修复未提交所致，提交推送后即满足。

## 4. 发布闭环检查清单（给 Lead）
1. 提交当前工作区修复（flake8 F401 grant_package_service.py、prettier OrgGrant.vue、README 版本同步）→ 推送 main。
2. 等 PR Checks（12 段后端）全绿；`node scripts/sync-version.js --check` 通过。
3. 版本号统一升至最终版本（若 v1.15.13：根 package.json 起 `node scripts/sync-version.js --write 1.15.13`，并运行 PPT bump 脚本）。
4. `git tag v1.15.13 && git push origin v1.15.13`。
5. 观察三个 workflow：PR Checks（该 tag commit 必须绿）→ build-windows smoke-test gate 通过 → build-windows 构建（关注 NSIS 阶段）；build-arm64 两个 gate 同样要求 PR Checks 绿。
6. Release 资产核对：`MRRS-Setup-1.15.13-x64.exe` + `MRRS-Setup-1.15.13-arm64.deb` + `assistance-management-system_1.15.13_arm64.deb` + 3 个 SHA256SUMS。
7. 抽一台干净 Windows 10/11 实机安装冒烟（首次启动建库 → 登录 → 强制改密）。

## 5. 验证命令与结果
| 检查 | 命令 | 结果 |
|---|---|---|
| 版本单源 | `node scripts/sync-version.js --check` | 通过（22 目标 ok） |
| PPT 完整性 | python-pptx 重新打开 + shape 计数 | 50 页 / 841 shapes（与原始一致） |
| PPT 文本 | 12 个关键断言（v1.15.12、13,926、6,865、R33、~286MB 等） | 全部命中 |
| PPT 溢出 | 启发式扫描（64 个文本段落，CJK 字宽估算） | 仅 slide 08 一处为原始既有，未新增 |
| VC++ 哈希 | 下载 aka.ms x64/x86 + Get-FileHash vs nsis hook 钉扎 | 两个均 MATCH |
| 构建链变更 | `git diff v1.14.3..HEAD -- build-windows.yml` | 5 行（timeout+注释） |
| 发布历史 | GitHub Releases API | v1.14.0/1.14.3 有 x64 exe；v1.15.0+ 无 |
| 失败定位 | Actions jobs API（逐 step conclusion/duration） | v1.15.5/7=gate 拦截；v1.15.6=Set up job 3s |
| 文档 | README/CLAUDE/docs 关键断言 grep | 已更新且 sync-version 通过 |

## 6. 遗留风险 / 未验证
- 全量测试未由我执行（Lead 统一跑）：本机 12 段实测有 4 个失败（seg10 `test_secrets_manager_complete` 的 cryptography 导入类、seg12 3 个配置/环境类），是否为并行测试污染待 CI 复核；README 已注明数字以 CI 为最终口径。
- Windows NSIS 构建无法在本机复现成功（本机反病毒环境），CI 首次跑需盯 build-windows 日志。
- PPT 版本当前 v1.15.12；若最终版本为 v1.15.13 需运行 bump 脚本（见 §2）。
- 本地 Release Notes 文件名按 v1.15.13 预置，最终版本变化时需同步改名与正文。