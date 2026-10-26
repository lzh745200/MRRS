# Release Notes — v1.18.8（2026-10-26）

> 供 GitHub Release 正文使用；逐项变更见根目录 `CHANGELOG.md` 的 `[1.18.8]` 段。
> 本版是**交付前最后一次全面体检 + 项目整理**，无新增业务功能；重点是把仓库清干净、把一道
> 「看起来永远绿、其实没验证」的覆盖率门禁修成真的。

## 一、下载与校验

| 安装包 | 适用平台 |
|---|---|
| `MRRS-Setup-1.18.8-x64.exe` | Windows 10/11 x64（NSIS 安装包，含全部运行时） |
| `MRRS-Setup-1.18.8-arm64.deb` | 麒麟 V10 / 统信 ARM64（Electron） |
| `assistance-management-system_1.18.8_arm64.deb` | 麒麟 V10 / 统信 ARM64（standalone，无 Electron） |

同一 Release 附带 **`SHA256SUMS-*.txt`** 校验文件，以及 Windows 自动更新所需的 `latest.yml` / `.exe.blockmap`。

> **体积与 SHA256 以 Release 资产页为准**：安装包由 GitHub Actions 现场构建，
> PyInstaller / electron-builder 产物含时间戳与压缩差异，**不是逐字节可复现**，
> 正文写死哈希会在重跑构建后失效。请以资产页的 `SHA256SUMS-*.txt` 为准。

离线校验（Windows）：

```powershell
Get-FileHash .\MRRS-Setup-1.18.8-x64.exe -Algorithm SHA256
# 与 SHA256SUMS-windows-x64.txt 逐字符比对
```

离线校验（麒麟 / 统信）：

```bash
sha256sum -c SHA256SUMS-electron-deb-arm64.txt
sha256sum -c SHA256SUMS-standalone-deb-arm64.txt
```

所有行必须为 `OK`；出现 `FAILED` 表示文件损坏或被篡改，请勿安装。

> **未签名包提示**：证书尚未采购。首次运行会触发 SmartScreen（「更多信息」→「仍要运行」）；
> **Defender 实时保护下，316.7 MB 的未签名安装包在本机实测 20 分钟以上未启动**
> —— 涉密/企业环境请**先报白名单或加 Defender 排除项**，不要误判为卡死。

## 二、本版重点

### 1. 项目整理：被跟踪文件 4,407 → 2,527（−1,880）

三项删除都有证据，且全部能从 git 历史恢复：

- `.scratch/tiles-import-test/`（**1,423 个**）：瓦片导入测试的中间产物。在 py/ts/vue/js/md/yml/
  json/ps1/sh 全量检索中**零引用**（含文档与 CI），删除不影响任何测试或构建。
- `.qoder/`（**456 个**，含 1.8 MB `repowiki-metadata.json`）：AI 工具生成的仓库知识库缓存。
  本仓《项目文件结构说明.md》本就把它标注为「机器本地元数据，不参与交付 ❌」——
  文档说不该入库，实际却跟踪了 456 个文件，本次纠正。
- `.scratch/r34-final/…介绍-原始备份.pptx`（**1.0 MB**）：与 `docs/` 正式版重复且零引用。

补 `.gitignore`：`.scratch/tmp/`、`.qoder/`、`.reasonix/`、`.zcode/`、`deliverables/releases/`、
`*.exe|*.msi|*.dmg`。**未动**：`deliverables/`（README/AGENTS/CHANGELOG 引用其中报告）、
`deploy/`、`nginx/`、`tests/`（E2E 与性能入口）。

### 2. 修掉一个「假绿」门禁：分段覆盖率合并从来就没成功过

`scripts/run_backend_tests_segmented.py` 的覆盖率门禁有三处缺陷叠加：

| 缺陷 | 表现 | 根因 |
|---|---|---|
| 合并永远失败 | 每次全量跑完打印一行 `覆盖率 combine 失败: `（**消息为空**），却仍报 100% | `coverage combine` 的位置参数是**路径**，代码传的是数据文件基名 `.covseg.<stamp>.<N>` |
| 分片扫不到 | 即使不传参也合并不了 | 各段分片名与 coverage 的 `<data_file>.*` glob 不匹配 |
| 提示读不到 | 只剩空消息，无法排障 | coverage 把 `No data to combine` 写在 **stdout**，代码只打印 stderr |
| 单段误判 | `--segment 11` 会报 `TOTAL … 28.40%` 并置退出码 1，像真实缺口 | 单段运行的数据天然不完整，却照样跑阈值判定 |

修法：分片改名为 `<data_file>.segN`（与 glob 对齐）、`combine` 改为**无参**调用（自行发现分片）、
失败时打印 stdout+stderr、**子集运行不再判定阈值**并明确提示「比值无意义」。
全量运行现在真的合并成功：**45,936 语句 / 11,452 分支，Miss 0 / BrPart 0，100.00%**。

### 3. 全面体检（逐项，零缺陷）

| 检查项 | 结果 |
|---|---|
| 静态门禁 20 道（错误文案泄漏 / 更新日志 / 迁移健康 / 菜单对齐 / console tab / 安全审计 / 硬编码色 / 三层对齐 / 版本单一来源 / 文档数字 / 6 个棘轮 / 零断言 / 软删除 / 裸返回 / electron 单测） | **20/20 通过** |
| 后端分段 | **12/12 PASS**，14,722 用例，0 失败 0 跳过 |
| 后端覆盖率 | **100.00%** |
| 前端 | **347 文件 / 7,356 用例全过**，四项覆盖率 **100%** |
| flake8 | `app/`（复杂度 16）**0**；`scripts/`（复杂度 40，CI 同口径）**0** |
| PII / 硬编码密钥 | **0 高危 / 0 中危** |
| 文档死链 | 146 个 md / 133 条相对链接 → **0** |
| TODO / FIXME 遗留 | **0** |
| 运行时依赖清单 ↔ `requirements.txt` | **完全一致** |
| Alembic | 单 head `r43_prune_dead_columns_001` |

### 4. 文档与 PPT

- `backend/version.json`：版本 1.18.8 / 2026-10-26，描述与 features 重写为本版结论。
- 系统介绍 PPT：版本页脚与「数据来源」日期同步至 **v1.18.8 / 2026-10-26**，保持 56 页与既有版式
  （原位改文本，不动版式；改后溢出检查与改动前**完全一致**，确认未引入新问题）。
- `README` / `CHANGELOG` / `项目文件结构说明` 与本版实测数字对齐，并记录本次清理的依据。

## 三、升级说明

- **数据库**：本版无 schema 变更（head 仍为 `r43`），直接覆盖安装即可；升级前建议照常备份。
- **配置**：无新增环境变量。
- **回滚**：安装包可覆盖安装旧版本；数据兼容（本版未动表结构）。
