# v1.18.38 发布说明 — 全量缺陷收口（数据隔离/恢复/导入/资源）

发布日期：2026-11-07

## 谁需要升级

- **使用数据包上报/接收的单位**：本版修正未归属组织记录的默认隔离口径，并给数据包增加
  逐文件 SHA256 校验；增量导出此前存在 500，本版一并修复。
- **需要恢复历史版本备份的单位**：恢复后自动执行数据库迁移，并明确提示附件是否需要人工核对；
  备份验证不再把“找不到数据库文件”误判为通过。
- **使用 Excel 填报导入 / 预览 / 校验的经办人**：三条入口统一解析与 1000 行上限，
  预览增加文件内查重与全量模式提示。
- **使用政策附件、项目批量操作、自动备份的运维人员**：孤儿附件回收、批量操作逐条计数、
  自动备份默认含附件、每日轻量数据库维护均已补齐。

## 本版改动

### 1. 数据隔离与完整性

- 数据包导出请求新增 `include_unassigned`（默认 false）与 `unassigned_counts`；
  默认仍按组织隔离，需要上报历史 NULL 记录时必须显式勾选。
- 修复增量导出（`/data-packages/incremental/export`）因请求模型缺少 `include_unassigned`
  导致的 500；一键上报与增量导出统一透传该开关。
- `manifest.data_checksums` 记录每个 `data/<type>.json` 的 SHA256，导入时逐文件校验；
  旧包无校验和时告警，记录数不符继续阻断。
- 资金 Excel 导入的 `project_code` 增加组织可达校验：跨组织项目行直接拒绝。

### 2. 导入与恢复闭环

- `/validate`、`/preview` 与 `/import` 统一使用 `ExcelImporterService.parse_excel`
  （表头探测/示例行/英文表头一致），统一 1000 行上限与县/梯次校验；预览增加 `mode`、
  文件内查重与失败提示。
- `/import/entities` 新增 `validate_county` / `validate_tiered_level` 兼容开关（默认 true），
  历史脏数据可按需关闭对应校验。
- 备份恢复后自动执行 `alembic upgrade head`（无版本但已有业务表时 stamp），失败回滚
  pre_restore 快照；不含 uploads 的备份返回 `attachments_need_review` 与明确文案。
- 备份验证兼容历史库成员路径（`data/assistance.db`、`data/assistance_management.db` 等），
  缺少数据库文件时 fail-closed。

### 3. 资源与一致性

- 数据库健康检查 6 处 SQLite 连接改为 `contextlib.closing`，异常路径不再泄漏句柄；
  `/system/admin/db-optimize` 改为同步端点（线程池执行）并确保关闭连接。
- 每日 03:10 注册轻量数据库维护（`PRAGMA optimize + WAL checkpoint + integrity_check`，
  线程池执行，不执行 VACUUM）。
- `data_sync` 的 `skip` 不再计入 `success`，新增 `skipped` 计数。
- 项目批量恢复/彻底删除改为逐条收集：部分失败继续处理，提示成功/失败数并保留失败项。
- 政策附件新增孤儿回收：后端只删除 `policies` 目录、UUID 文件名且未被任何政策引用的文件；
  前端只回收本次新上传且已移除的 URL，并修正上传 `category=policies`，使清理请求不再恒 400。
- 自动备份与即时备份默认包含 uploads（`AUTO_BACKUP_INCLUDE_UPLOADS=true`），
  避免恢复后库与附件错位；大附件部署可显式关闭。

### 4. 文档与演示材料

- `CHANGELOG.md` 1.18.38 段逐条记录本版修复与验证。
- PPT 演示材料版本标识与统计数字更新到 v1.18.38。

## 安装与信任（重要）

自签名不是公共 CA 证书，**未信任根证书的机器上签名状态会显示为 UnknownError / NotTrusted**，
这是预期行为，不影响程序运行；按下列任一方式信任后可显示为 Valid：

1. **域环境（推荐）**：用 GPO 把 `MRRS-Internal-CodeSigning.cer` 下发到
   「受信任的根证书颁发机构」与「受信任的发布者」。
2. **单机（管理员 PowerShell）**：
   ```powershell
   certutil -addstore -f Root MRRS-Internal-CodeSigning.cer
   certutil -addstore -f TrustedPublisher MRRS-Internal-CodeSigning.cer
   ```
3. **核验签名**：
   ```powershell
   Get-AuthenticodeSignature .\MRRS-Setup-1.18.38-x64.exe |
     Select-Object Status, @{n='Signer';e={$_.SignerCertificate.Subject}},
                   @{n='Thumbprint';e={$_.SignerCertificate.Thumbprint}}
   ```
   期望签名者为 `CN=MRRS Internal Code Signing, O=MRRS, C=CN`，
   指纹为 `8203900B6DA54201A49BDAF923B2F20D76CA35A1`。

> 安装为 perMachine（所有用户），需要管理员权限。未信任证书时 Windows 仍可能提示
> 「未知发布者」，完成信任后重新运行即可。

## 验证记录

| 项目 | 结果 |
|---|---|
| 后端全量（12 段独立进程） | **15,712 passed**；合并覆盖率 **100.00%** |
| 前端全量 vitest | **7,520 passed**，覆盖率 100% |
| Electron 外壳单测 | 23 passed |
| 静态门禁 | flake8 / 三层对齐 / 文档数字 / CHANGELOG / 棘轮全部通过 |

## 已知边界

- 孤儿附件删除端点对所有已登录用户开放（与政策编辑权限一致），但只接受 `policies` 目录下
  UUID16 文件名且未被任何政策引用的文件；文件名不可猜，风险可接受。
- `data_checksums` 只能发现截断/损坏，不能防“篡改后重算哈希”；数据包本身未签名，
  真实性仍依赖介质与导入台账。
- 无 `alembic_version` 的极老备份按启动同口径 `stamp head`；若该库缺后续列，历史迁移
  不会补齐（与启动行为一致）。
- 预览逐行校验的 `row_number` 在内部恒为 1，前端按行渲染，不影响使用。
- 安装包按设计不含离线地图瓦片；瓦片由构建机拷入或安装后经
  `POST /api/v1/map/tiles/import` 导入。

## 升级步骤

1. 备份当前数据库与 uploads（本版恢复链路已带自动迁移，但仍建议先人工备份）。
2. 运行 `MRRS-Setup-1.18.38-x64.exe`（管理员权限），按向导升级安装。
3. 首次启动会自动执行数据库迁移；如从极老版本升级，迁移耗时可能较长，请勿中途断电。
4. 验证：登录后检查 `/version.json` 为 1.18.38，抽查数据包导出/导入、Excel 填报导入、
   政策附件与备份恢复页面。
