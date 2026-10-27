# Release Notes — v1.18.15（2026-10-27）

> 供 GitHub Release 正文使用；逐项变更见仓库根目录 `CHANGELOG.md` 的 `[1.18.15]` 段。
> 本版是 **v1.18.14 之后的收口轮**：修掉一处「只报失败条数、不报原因」的导入可观测性缺陷，
> 并把文档与三份 PPT 里滞后的实测数字、版本标记全部追平到真值。

## 一、下载与校验

| 安装包 | 适用平台 |
|---|---|
| `MRRS-Setup-1.18.15-x64.exe` | Windows 10/11 x64（NSIS 安装包，含全部运行时） |
| `MRRS-Setup-1.18.15-arm64.deb` | 麒麟 V10 / 统信 ARM64（Electron） |
| `assistance-management-system_1.18.15_arm64.deb` | 麒麟 V10 / 统信 ARM64（standalone，无 Electron） |

同一 Release 附带 **`SHA256SUMS-*.txt`**，以及 Windows 自动更新所需的 `latest.yml` / `.exe.blockmap`。

> **体积与 SHA256 以 Release 资产页为准**：安装包由 GitHub Actions 现场构建，不是逐字节可复现。

离线校验（Windows）：

```powershell
Get-FileHash .\MRRS-Setup-1.18.15-x64.exe -Algorithm SHA256
```

离线校验（麒麟 / 统信）：

```bash
sha256sum -c SHA256SUMS-electron-deb-arm64.txt
sha256sum -c SHA256SUMS-standalone-deb-arm64.txt
```

> **未签名包提示**：证书尚未采购，首次运行会触发 SmartScreen（「更多信息」→「仍要运行」）。

## 二、本版修了什么

### 帮扶村「分段数据」导入：失败时终于能看到原因

导入结束后，系统一直只回一个汇总：`{"imported": 5, "failed": 3}`。
用户知道有 3 行没进去，但**不知道是哪 3 行、为什么**，只能整份重来。

三个失败分支此前都是静默计数：

| 分支 | 触发场景 | 此前表现 | 现在 |
|---|---|---|---|
| 表头未识别 | 模板列名被改 / 贴错工作表 | 整表按失败计数，无任何提示 | 告警「前 N 行均未命中 ≥2 个字段标签，请核对模板列名」 |
| 行内无可写字段 | 数值列填了文字、日期格式不对 | `failed += 1` | 告警含 **Excel 行号** + 字段模型 + 年份 |
| 写库异常 | 约束冲突 / 数据库异常 | `failed += 1` | 告警含行号 + **完整异常栈**（`exc_info`） |

现场操作：导入失败后，把应用日志里的 `分段导入第 N 行…` 交给运维即可定位，
不必再靠猜。

> **对现有用户无影响**：接口返回结构未变（仍是 `{imported, failed}`），
> 前端与既有脚本无需调整。

### 文档与 PPT 的实测数字追平

三份 PPT（系统介绍 56 页 / 零基础版 44 页 / 操作培训 60 页）此前停留在 v1.18.8 的旧实测值，
与 README 自相矛盾：

| 指标 | 旧值（PPT） | 真值 |
|---|---|---|
| 后端用例 | 14,722 / 14,726 | **14,870** |
| 前端用例 | 7,356 | **7,374** |
| 合计 | 22,078 | **22,244** |
| 前端测试文件 | 347 | **344**（`tests/**/*.test.ts(x)` 口径） |

同时修正文档入口页：`docs/README.md`、`docs/INDEX.md`、`docs/04-部署文档/README.md`、
`docs/01-快速开始/README.md` 此前仍指向 `RELEASE_NOTES-v1.18.1`（13 个版本前）。

### 仓库卫生

- 清理 **1,405 个测试残留目录（6.6 GB）** 与顶层 28 个 pip 空临时目录；
- `.gitignore` 补齐 `backend/verify_*/`（280 个）、`backend/wf_*/`、`backend/_scratch_lazy/` ——
  此前只忽略 `bumofu_pytest_appdata_*/`，另两类每次全量测试后都会让 `git status` 变脏。

## 三、升级前必读

1. **本版无数据库迁移**，可直接覆盖安装，无需备份恢复（仍建议按惯例先做一次完整备份）。
2. 升级后「关于」页应显示 `1.18.15`；若仍显示旧版本，请确认安装包名称与本文一致。
3. 多机部署请确保所有节点的 `PASS_CODE_SECRET` 一致，否则跨机通行码校验会失败。

## 四、本版验证口径

| 项 | 结果 |
|---|---|
| 后端测试 | 14,870 例全绿；行+分支覆盖率 **100%**（CI 12 段独立进程，`.coveragerc` `fail_under=100`） |
| 前端测试 | 7,374 例 / 347 文件全绿；12 组 glob 覆盖率阈值全 100% |
| 静态门禁 | flake8（复杂度 16）0 错误 / bandit 无 Medium+ / ESLint `--max-warnings=0` 0 警告 / `vue-tsc` 无错误 |
| 四层栈对齐 | 零漂移（前端路径 / 模型↔库 / 前后端字段 / 请求体必填性） |
| 前后端 API 路径 | 后端 853 条路由 vs 前端 352 个去重调用，**0 不一致** |
| 依赖漏洞 | `npm audit --omit=dev` → 0 vulnerabilities |
| 文档数字 | `check_doc_numbers --full` ✓ / `check_update_log` ✓（103 个版本） |
