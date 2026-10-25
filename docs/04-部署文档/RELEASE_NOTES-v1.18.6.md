# Release Notes — v1.18.6（2026-10-25）

> 供 GitHub Release 正文使用；逐项变更见根目录 `CHANGELOG.md` 的 `[1.18.2]`–`[1.18.6]` 段。

## 一、下载与校验

| 安装包 | 适用平台 |
|---|---|
| `MRRS-Setup-1.18.6-x64.exe` | Windows 10/11 x64（NSIS 安装包，含全部运行时） |
| `MRRS-Setup-1.18.6-arm64.deb` | 麒麟 V10 / 统信 ARM64（Electron） |
| `assistance-management-system_1.18.6_arm64.deb` | 麒麟 V10 / 统信 ARM64（standalone，无 Electron） |

同一 Release 附带 **`SHA256SUMS-*.txt`** 校验文件，以及 Windows 自动更新所需的
`latest.yml` / `.exe.blockmap`。

> **体积与 SHA256 以 Release 资产页为准**：安装包由 GitHub Actions 现场构建，
> PyInstaller / electron-builder 产物含时间戳与压缩差异，**不是逐字节可复现**；
> 正文写死哈希会在重跑构建后失效。请以资产页的 `SHA256SUMS-*.txt` 为准。

离线校验（Windows）：

```powershell
Get-FileHash .\MRRS-Setup-1.18.6-x64.exe -Algorithm SHA256
# 与 SHA256SUMS-windows-x64.txt 逐字符比对
```

离线校验（麒麟/统信）：

```bash
sha256sum -c SHA256SUMS-electron-deb-arm64.txt
sha256sum -c SHA256SUMS-standalone-deb-arm64.txt
```

所有行必须为 `OK`；出现 `FAILED` 表示文件损坏或被篡改，请勿安装。

## 二、本版重点

### 1. 仓库卫生与门禁加固（1.18.6）

- **`backend/app/` flake8 归零（79 → 0）**：78 处 `E302/E305`（`app/models/` 14 个文件顶层定义
  之间只有 1 个空行）+ 1 处 `F401`（`models/monitoring.py` 未使用 `JSON` 导入）。纯空行/导入整理，
  无逻辑变更。
- **`scripts/` flake8 归零（19 → 0）**：未使用导入 4 处、`E401`×2 / `E302` / `E305` / `E303`
  各 1、`W292`×2、`W504`×2、`F541`×1、`E501`×5。CI lint 现同时约束 `app/`（复杂度 16）
  与 `scripts/`（复杂度 40，排除已归档脚本）。
- **覆盖率门禁两处失效根治**（`scripts/run_backend_tests_segmented.py`）：
  ① `.coveragerc` 缺失时 **fail-fast**（历史：被清理分片误删 → `fail_under` 静默失效、门禁假绿）；
  ② 覆盖率判定改为「**全部段跑完后统一 report**」，并支持 `--cov-unique`（每段独立 `data_file`
  + `combine`），避免多会话并发时固定文件名互相覆盖；清理分片一律精确匹配，
  **绝不用 `.coverage*`**（会把 `.coveragerc` 一起删掉）。

### 2. 录入效率包与性能（1.18.6）

- **表单草稿自动保存**（`useFormDraft`）：切页/刷新不丢输入，按表单维度隔离存储。
- **Excel 批量粘贴解析**（`parsePastedTable`）：从 Excel 复制多行直接粘贴录入；
  消费帮扶台账接入时逐行校验、串行新增，失败行号原样回传，不整批回滚。
- **分页硬上限**：`MAX_PAGE_SIZE` 统一为 200，4 处裸 `page_size` + 1 处 `le=500` 收口；
  新增 `coerce_page_param()` 修复「测试/内部代码直接调用端点时拿到 `Query` 对象」导致的
  `TypeError`（HTTP 校验口径不变）。
- **每页条数记忆**（`usePageSize`）：项目列表接入，偏好持久化并归一化。
- **虚拟滚动基座**（`VirtualList`）：窗口算术抽成纯函数（22 例测试），为长列表做准备；
  本轮不强行改造既有页面。

### 3. 主题、图表与场景预设（1.18.6）

- **ECharts 主题改读设计 Token**：通过 `Proxy` 登记主题依赖，5 个图表页零改动即跟随主题切换。
- **三档场景预设**（标准 / 紧凑 / 演示）：首次启动按视口自适应密度，可在外观设置中切换。

### 4. 错误体验：422 不再显示技术原文（1.18.2）

- 后端 pydantic 校验错误中文化，**不回显 `input`**（避免把用户输入原样抛回）。
- 前端统一出口 `getErrorMessage` 重写：`detail → message → err.message`，永不显示技术原文；
  拦截器与视图层对齐，可选透出 `httpStatus`。
- 新增门禁 `scripts/check_error_message_leaks.py`（CI `static-analysis`）扫描泄漏。

### 5. 地图瓦片覆盖范围（1.18.3–1.18.5）

- **多包叠加导入后覆盖范围被最后导入包限制（P0）**：`MANIFEST.json` 只保留最后导入包，
  改为**同一 zoom 内各包并集**。
- **bbox 取最细 zoom**：`scan_tiles_dir` 按 zoom 分组累计，取最细 zoom 的实测并集
  （实测 `resources/map-tiles` 5,623 张 z5–12），修正概览瓦片撑大 `maxBounds`。
- **bbox 数值校验**：`["x",1,2,3]` 这类非法 bbox 不再透传给 Leaflet；新增 `_valid_bbox()`
  校验「4 个有限数值」，排除 `bool` / `NaN` / `±inf`。

### 6. 安全与稳定性（1.18.3 / 1.18.6）

- **旧管理员恢复端点下线**：`POST /api/v1/system/admin/restore` 改为 **410 Gone**；
  跨密钥恢复在 UI 提供危险勾选 + 显式放行入口（409 语义保持）。
- **密码哈希改 bcrypt 直连**：passlib 1.7.4 在 bcrypt 5.x 下后端探测失败且**失败状态进程内永久缓存**，
  大批量收集时随机抛 `MissingBackendError`；改用 `bcrypt.hashpw/checkpw` 后产物格式不变
  （`$2b$<cost>$`），历史哈希零迁移。
- **消除唯一 skip**：打包态日志路径回归改用 `monkeypatch sys.frozen=True`，与真实打包态同分支，
  不再在开发机跳过。
- **`BaseChart` 主题重建入口显式暴露**：`defineExpose({ rebuild })`，多套件并行时归属不再漂移。

### 7. 数据层清理（1.18.6）

- **删除 26 个零引用死字段**（迁移 `r43_prune_dead_columns_001`）：有数据的列**归档不删**，
  仅移除代码与 schema 中的死字段；单 head 保持 `r43`。
- 三层对齐门禁（前端路径 ↔ 后端路由 / ORM ↔ 库 / 前后端字段）保持 **0 漂移**。

## 三、升级说明

- **数据库**：新增迁移 `r43_prune_dead_columns_001`，启动时自动执行（幂等）。
  当前为 **63 个迁移版本、单 head `r43`**。
- **配置**：无新增必填项；`MAX_PAGE_SIZE` 上限由 100 调整为 200（超限请求返回 422）。
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
| 安装包（Windows x64 / 麒麟 ARM64） | 由 GitHub Actions `v1.18.6` tag 构建，产物与校验和见 Release 资产页 |
