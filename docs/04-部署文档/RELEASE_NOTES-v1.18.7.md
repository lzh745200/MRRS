# Release Notes — v1.18.7（2026-10-25）

> 供 GitHub Release 正文使用；逐项变更见根目录 `CHANGELOG.md` 的 `[1.18.2]`–`[1.18.7]` 段。

## 一、下载与校验

| 安装包 | 适用平台 |
|---|---|
| `MRRS-Setup-1.18.7-x64.exe` | Windows 10/11 x64（NSIS 安装包，含全部运行时） |
| `MRRS-Setup-1.18.7-arm64.deb` | 麒麟 V10 / 统信 ARM64（Electron） |
| `assistance-management-system_1.18.7_arm64.deb` | 麒麟 V10 / 统信 ARM64（standalone，无 Electron） |

同一 Release 附带 **`SHA256SUMS-*.txt`** 校验文件，以及 Windows 自动更新所需的
`latest.yml` / `.exe.blockmap`。

> **体积与 SHA256 以 Release 资产页为准**：安装包由 GitHub Actions 现场构建，
> PyInstaller / electron-builder 产物含时间戳与压缩差异，**不是逐字节可复现**；
> 正文写死哈希会在重跑构建后失效。请以资产页的 `SHA256SUMS-*.txt` 为准。

离线校验（Windows）：

```powershell
Get-FileHash .\MRRS-Setup-1.18.7-x64.exe -Algorithm SHA256
# 与 SHA256SUMS-windows-x64.txt 逐字符比对
```

离线校验（麒麟/统信）：

```bash
sha256sum -c SHA256SUMS-electron-deb-arm64.txt
sha256sum -c SHA256SUMS-standalone-deb-arm64.txt
```

所有行必须为 `OK`；出现 `FAILED` 表示文件损坏或被篡改，请勿安装。

## 二、本版重点

### 1. 录入效率包收口（③）

- **批量粘贴弹窗 `BulkPasteDialog`**：从 Excel 复制多行 → 粘贴 → 预览 → 逐行校验 → 确认，
  四步可视化，校验不通过的行直接标红，不进入提交。
- **批量新增执行器 `useBulkCreate`**：串行提交、逐条失败明细、摘要话术；
  消费帮扶台账已接入（逐行校验 + 串行新增 + **失败行号原样回传**，不整批回滚）。
- **草稿自动保存扩到 4 个页面**：学校编辑、组织编辑等页面接入 `useFormDraft` +
  未保存离开拦截；切页/刷新不丢输入。

### 2. 工作协同：顶栏数据同步胶囊（④）

顶栏新增数据同步状态胶囊 + 台账抽屉，只读 `/data-sync/logs`，**不新增接口**；
异常状态一眼可见，点击可下钻到台账。

### 3. 经费凭证 OCR 字段级建议（⑤）

转账凭证新建对话框接入 OCR 字段级建议：识别金额/日期给出建议值，由人工确认后填入
（后端能力早已存在，此前前端零调用）。

### 4. 性能基座（⑥）

- **`VirtualList` 虚拟滚动基座**：窗口算术抽成纯函数（22 例测试，双文件 100% 覆盖），
  为长列表做准备；本轮不强行改造既有页面。
- **`usePageSize` 每页条数偏好**：偏好记忆 + 归一化，项目列表接入。

### 5. 视觉回归扩到 44 页（⑨）

DOM 结构快照基线从 10 页扩到 **44 页**（30 个 console tab + 4 个核心表单），
不比对像素，CI 稳定运行。

### 6. 质量与发布工程

- **PR/Nightly 覆盖率一致性门禁**：防止两套口径长期漂移。
- **Nightly 补跑 `tests` 根目录**：`permission_packs` 覆盖率 38% → 100%。
- **E2E 新增村庄表单断言**：顶栏同步抽屉的隐藏元素污染 `.first()`，改用 `:visible`。
- **`release_tag` 工具加固**：输出改 UTF-8；工作区脏时提供 `--allow-dirty` 逃生口
  （tag 仍只指向已推送 commit）；`ci_green` 兼容 stdout/stderr 为 `None`；
  裸 pragma 补理由（F2 棘轮 1 → 0）。

### 7. 文档与 PPT 收口

- `README` / `backend/version.json` 版本与测试数字统一；
- 新增本发布说明；系统介绍 PPT 升级为 **v1.18.7 / 56 页**：
  新增「v1.18.2 → v1.18.7：五版收口要点」页，版本历程补到 v1.18.7，全篇数字同步。

## 三、升级说明

- **数据库**：无新增迁移（延续 `r43_prune_dead_columns_001`）。
  当前为 **63 个迁移版本、单 head `r43`**。
- **配置**：无新增必填项；`MAX_PAGE_SIZE` 上限为 200（超限请求返回 422）。
- **兼容性**：登录错误语义（401/403/423/429）未变；旧管理员恢复端点返回 410，
  请改用备份恢复通道；旧前端不受 `public-config` 新增字段影响。
- **数据目录**：与 1.18.0 一致（Windows `%APPDATA%\MRRS`、麒麟 `~/.local/share/mrrs`），
  升级不迁移数据。

## 四、验证记录

| 项 | 结果 |
|---|---|
| 后端 CI 12 段 | 12/12 PASS，**14,722 用例，0 failed / 0 skipped** |
| 后端覆盖率（`fail_under=100` 生效） | **100.00%**（45,936 语句 / 11,452 分支，Miss 0 / BrPart 0） |
| 前端全量 | **347 文件 / 7,356 用例全过** |
| 前端覆盖率 | 语句 / 分支 / 函数 / 行 **四项 100%** |
| `flake8 app/` + `scripts/` | **0** |
| 门禁脚本 | 全部通过（三层对齐 / 零断言棘轮 / 同步覆盖率 / 菜单对齐 / 单 head 迁移 / 常量同步 / 无用参数 0 / 硬编码色 146-146） |
| CI 9 作业 | 全部 success（frontend-check / backend-test / security / upgrade-rehearsal / windows-smoke / static-analysis / lint / e2e-test / stack-alignment） |
| 安装包（Windows x64 / 麒麟 ARM64） | 由 GitHub Actions `v1.18.7` tag 构建，产物与校验和见 Release 资产页 |
