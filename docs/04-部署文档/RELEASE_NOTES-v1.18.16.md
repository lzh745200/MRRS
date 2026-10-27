# Release Notes — v1.18.16（2026-10-27）

> 供 GitHub Release 正文使用；逐项变更见仓库根目录 `CHANGELOG.md` 的 `[1.18.16]` 段。
> 本版是**发布流水线的收口**：上一版 Release 少了两个产物文件，追出根因并加了守卫；
> 同时把「构建不可复现」的依赖漂移钉住。

## 一、下载与校验

| 安装包 | 适用平台 |
|---|---|
| `MRRS-Setup-1.18.16-x64.exe` | Windows 10/11 x64（NSIS 安装包，含全部运行时） |
| `MRRS-Setup-1.18.16-arm64.deb` | 麒麟 V10 / 统信 ARM64（Electron） |
| `assistance-management-system_1.18.16_arm64.deb` | 麒麟 V10 / 统信 ARM64（standalone，无 Electron） |

同一 Release 附带：

- **`SHA256SUMS-*.txt`** —— 三个安装包的指纹（离线校验用，见下）；
- **`latest.yml` / `MRRS-Setup-1.18.16-x64.exe.blockmap`** —— electron-builder 的 NSIS
  构建产物。**本系统不消费它们**：没有 `electron-updater` 依赖、也没有任何自动更新逻辑，
  升级一律走「下载新安装包覆盖安装」（见 `OFFLINE_UPGRADE.md`）。保留上传只为发布物清单
  稳定，将来若启用自动更新可直接使用。

> **体积与 SHA256 以 Release 资产页为准**：安装包由 GitHub Actions 现场构建，不是逐字节可复现。

离线校验（Windows）：

```powershell
Get-FileHash .\MRRS-Setup-1.18.16-x64.exe -Algorithm SHA256
```

离线校验（麒麟 / 统信）：

```bash
sha256sum -c SHA256SUMS-electron-deb-arm64.txt
sha256sum -c SHA256SUMS-standalone-deb-arm64.txt
```

> **未签名包提示**：证书尚未采购，首次运行会触发 SmartScreen（「更多信息」→「仍要运行」）。

## 二、本版修了什么

### 1. Release 资产丢失（latest.yml / .exe.blockmap）

**现象**：v1.18.15 的 Release 只有 6 个资产，而 v1.18.14 有 8 个 —— 同一套流水线，
产出清单却不同，其中少的正是两个产物的元数据文件。

**根因**（构建日志原文）：

```
• publishing      publisher=Github (owner: lzh745200, project: MRRS, version: 1.18.15)
• GitHub release not created  reason=existing type not compatible with publishing type
    tag=v1.18.15 existingType=release publishingType=draft
• skipped publishing  file=latest.yml  reason=existing type not compatible ...
• skipped publishing  file=MRRS-Setup-1.18.15-x64.exe.blockmap  reason=...
```

Windows 作业的 electron-builder 在有 `GH_TOKEN` 时，默认 publish 策略是 `onTagOrDraft`
——它要在 tag 构建里**自己**建一个 **draft** Release 上传产物。可是本仓的 Release 由三个
作业的 `softprops/action-gh-release` 发布：若 ARM64 作业先把 Release 发成**正式版**，
electron-builder 就判定类型不兼容，把 exe / blockmap / latest.yml **三个文件全部跳过**；
随后只有 softprops 步骤把 exe 传上去，两个元数据文件永久丢失。

**修复**：

- Windows 侧改 `npx electron-builder --win --x64 --publish never`
  （与 `build-arm64.yml` 第 209 行同口径）——**单一发布路径**：electron-builder 只构建，
  上传一律由 softprops 负责；
- 制品上传与 Release 文件清单都显式补上 `dist/electron/latest.yml` 与
  `dist/electron/*.blockmap`（v1.18.14 的 8 件口径）；
- **新增构建期守卫** `Verify updater metadata produced`：NSIS 构建只要正常出包，
  必然同时产出 `latest.yml` 与 `MRRS-Setup-<版本>-x64.exe.blockmap`；缺一即构建失败，
  并打印 `dist/electron` 清单 —— 不让「Release 少文件」留到发版后才发现。

### 2. 依赖版本漂移（构建可复现）

`backend/requirements.txt` 里四个包此前用 `>=`：

| 包 | 原约束 | 实际状况 | 现在 |
|---|---|---|---|
| `setuptools` | `>=83.0.0` | 漂移 | `==84.2.1` |
| `wheel` | `>=0.45.0` | 漂移 | `==0.48.0` |
| `bcrypt` | `>=4.2.0` | **本地 4.0.1（连约束都不满足）/ CI 5.0.0** | `==5.0.0` |
| `cryptography` | `>=41.0.0` | 漂移 | `==50.0.2` |

后果是**本地测的与 CI 测的不是同一套依赖**，安装包里的运行时也无法复现。现全部 pin 到
CI 已全绿验证的确切版本（取自 CI 实装记录）。bcrypt 5.0 移除了 `__about__`，
`app/core/security.py` 的兼容 shim 与 passlib 1.7.4 的回退路径已由 CI 覆盖；
哈希格式仍是 `$2b$`，**与 4.x 生成的历史密码完全互通，升级不影响存量用户**。

### 3. 文档更正与补全

- 纠正「`latest.yml` 是 Windows 自动更新所需」的不准确表述（见上文第一节）；
- `docs/INDEX.md` 补齐 12 篇此前只有目录级入口的文档：7 篇 ADR、4 篇 Agent 约定、
  1 篇通知与提醒 UI 规范 —— 现在 `docs/` 下 18 篇文档都有显式链接，死链 0。

## 三、验证

- `.github/workflows/build-windows.yml`：YAML 可解析，27 个步骤（含新守卫）；
- `npm run test:electron`：**11 例全过**（含 ci-wiring：发布门禁等待预算 <60 分钟、
  main 不再 cancel-in-progress、check_main_ci.py 接线）；
- 本地 20 项静态门禁全绿；`check_doc_numbers --full` 一致（后端 14,870 例 / 前端 344 文件）；
- 本 tag 构建即验证：Release 应为 **8 个资产**（3 安装包 + 3 SHA256SUMS + latest.yml + blockmap），
  且 `SHA256SUMS-*.txt` 与资产 digest 逐项一致。

## 四、升级注意

- 功能行为与 v1.18.15 **完全一致**（本版只动发布流水线、依赖版本与文档），
  已在 v1.18.15 上升级的单位**不必**为功能而升级；
- 若你正在等安装包用于离线分发，请以本版为准：它的依赖版本与流水线产物都是可复现的；
- 升级方式不变：下载对应平台安装包 → 覆盖安装（数据库与上传目录不受影响），
  详见 `docs/04-部署文档/OFFLINE_UPGRADE.md`。
