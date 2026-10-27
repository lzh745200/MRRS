# Release Notes — v1.18.17（2026-10-27）

> 供 GitHub Release 正文使用；逐项变更见仓库根目录 `CHANGELOG.md` 的 `[1.18.17]` 段。
> 本版是**工程治理收口**：给三类"只涨不降"的技术债装上闸门，并当场修掉这个门禁**自身**
> 两个会让它失效的坑。

## 一、下载与校验

| 安装包 | 适用平台 |
|---|---|
| `MRRS-Setup-1.18.17-x64.exe` | Windows 10/11 x64（NSIS 安装包，含全部运行时） |
| `MRRS-Setup-1.18.17-arm64.deb` | 麒麟 V10 / 统信 ARM64（Electron） |
| `assistance-management-system_1.18.17_arm64.deb` | 麒麟 V10 / 统信 ARM64（standalone，无 Electron） |

同一 Release 附带：

- **`SHA256SUMS-*.txt`** —— 三个安装包的指纹（离线校验用）；
- **`latest.yml` / `MRRS-Setup-1.18.17-x64.exe.blockmap`** —— electron-builder 的 NSIS
  构建产物。**本系统不消费**（无 `electron-updater`、无自动更新逻辑，升级走覆盖安装），
  保留上传只为发布清单稳定。

> **体积与 SHA256 以 Release 资产页为准**：安装包由 GitHub Actions 现场构建，非逐字节可复现。

```powershell
Get-FileHash .\MRRS-Setup-1.18.17-x64.exe -Algorithm SHA256
```

> **未签名包提示**：证书尚未采购，首次运行会触发 SmartScreen（「更多信息」→「仍要运行」）。

## 二、本版做了什么

### 1. 技术债棘轮（新增阻断型门禁）

三个此前**无人看管**的指标：

| 指标 | 本版基线 | 此前状态 |
|---|---|---|
| mypy 错误数 | **1394** | CI 里是 `\|\| true`，永不阻断 |
| 前端 `as any` 处数 | **196** | 无任何上限 |
| 后端 `except Exception` 处数 | **802** | 无任何上限 |

一次性清零等于给全库补类型标注（150 个文件），不现实；但**"不允许继续恶化"**立刻可以做到。
所以做成棘轮：基线记录**数量 + 精确位置**，任一指标超过基线即 CI 失败，并**列出新增位置**
（不是只报"多了几条"，否则无法修）。`--update` 只应下调；上调需在 PR 说明理由。

### 2. 修掉这个门禁自身的两个失效点（重要）

**① 一提交就是红的**：基线写成 `1393`，实测稳定 **1394**（连跑三次 + `--no-incremental`
都是 1394）。核对后确认 1394 条与最近 3 个提交改动的 `app/` 文件**无任何交集** ——
属存量口径偏差，不是新缺陷。故按实测重生成基线，并把该结论写进 CHANGELOG，
避免后人误以为"悄悄放宽了标准"。

**② 测不到时会静默放行**：原实现在 mypy 无法解析汇总行时 `return 0` —— 一旦 mypy 改输出
格式或没装，第一条指标就**永久失效却仍显示绿色**，正是 `|| true` 换个马甲。现改为
**fail-closed**：抛 `MypyUnavailable` → `exit 2`（与"恶化"的 `exit 1` 区分），
并打印输出尾部与修复提示。该分支已单独注入假输出验证。

**③ 顺手堵住版本漂移**：CI 由 `pip install mypy` 改为 **`mypy==1.19.1`**（与
`requirements-dev.txt` 及基线测量口径一致）。棘轮把错误数当上限守着，不 pin 则上游发版
换个检查规则就能让全量计数整体漂移 —— 要么假红、要么假绿。

### 3. Python 3.13 兼容

`rapidocr-onnxruntime==1.4.4` 的元数据是 `requires_python < 3.13`（PyPI 官方 JSON 核实、
未 yanked）。原写法在 **Python 3.13** 下执行 `pip install -r requirements.txt` 会报
"No matching distribution found" 而**整个安装失败**（实测 3.13.14 复现）。

现加环境标记 `; python_version < "3.13"`：3.13 下自动跳过该行、其余依赖照装；
OCR 走既有降级路径（引擎不可用 → `available()=False` → 接口 503 提示手工录入），
不影响主流程。**CI 与打包基座仍是 3.11**，OCR 功能完整。

### 4. 门禁隔离（不再让门禁进程被清理动作带崩）

三层对齐门禁的参照库改落到仓库内 `.scratch/tmp/stack-align/`（`.gitignore` 兜底），
并让清理函数吞掉 `BaseException`：本机沙箱的 safe-delete shim 在单次删除量超过阈值时
会抛 `SystemExit` —— 那是 `BaseException`，`shutil.rmtree(ignore_errors=True)` 只吞
`OSError` 拦不住，会把门禁进程带崩、stdout 变空，负向用例因此误判成"门禁逻辑坏了"。

## 三、验证

- `python scripts/check_type_debt.py` → **1394 / 196 / 802 全部持平 ✓**（exit 0）；
- fail-closed 分支：注入 `returncode=2` 的假 mypy 输出 → 正确 `MypyUnavailable`；
- 三层对齐门禁：四轴（前端路径 / 模型↔库 / 前后端字段 / 请求体必填性）**无漂移**；
- 本次改动涉及的 58 个相关后端用例全过；
- `check_doc_numbers --full` 一致：后端 **14,870** 例 / 前端 **344** 文件 / 端点 **849**；
- 本地 20 项静态门禁全绿；CI 在 tag 提交上跑完整 12 段后端 + 覆盖率 100% + 前端 + E2E。

## 四、升级注意

- **功能行为与 v1.18.16 完全一致**（本版只动工程治理与依赖环境标记），
  已升级的单位不必为功能而升级；
- Python 3.13 的开发机现在可以正常 `pip install -r requirements.txt`，但**生产与打包仍用
  3.11**（OCR 依赖只在该版本可用）；
- 升级方式不变：下载对应平台安装包 → 覆盖安装（数据库与上传目录不受影响），
  详见 `docs/04-部署文档/OFFLINE_UPGRADE.md`。
