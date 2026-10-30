# Release Notes — v1.18.28（2026-10-30）

> 上一正式发布是 **v1.18.27**。本版是**纯重新打包**：把 v1.18.27 tag 之后、
> 尚未进入安装包的两处提交补进产物，不改任何业务逻辑。

## 一、为什么会有这一版

v1.18.27 的安装包是在提交 `7c0a9639` 上打出来的，而之后 main 上又落了两处提交：

| 提交 | 内容 | 是否影响产物 |
|---|---|---|
| `443fa087` | 补 `docs/04-部署文档/RELEASE_NOTES-v1.18.27.md` | 否（仅文档）|
| `6d162cc4` | **根组织层级误判修复** —— 市州级单位无法建根 / 被自检误报 | **是** |

也就是说，`MRRS-Setup-1.18.27-x64.exe` 里仍然是「输入 `522700`（黔南州市州级）新建根组织
返回 422」的旧行为。本版把修复真正带进安装包。

## 二、下载与校验

| 安装包 | 适用平台 |
|---|---|
| `MRRS-Setup-1.18.28-x64.exe` | Windows 10/11 x64（NSIS 安装包，含全部运行时）|
| `MRRS-Setup-1.18.28-arm64.deb` | 麒麟 V10 / 统信 UOS ARM64（Electron）|
| `assistance-management-system_1.18.28_arm64.deb` | 麒麟 V10 / 统信 UOS ARM64（standalone，无 Electron）|

同一 Release 附带 `SHA256SUMS-*.txt`（三个安装包指纹）与 `latest.yml` /
`MRRS-Setup-1.18.28-x64.exe.blockmap`（electron-builder 的 NSIS 产物，**本系统不消费**：
无自动更新逻辑，升级走覆盖安装）。

```powershell
Get-FileHash .\MRRS-Setup-1.18.28-x64.exe -Algorithm SHA256
```

> **未签名包提示**：证书尚未采购，首次运行会触发 SmartScreen（「更多信息」→「仍要运行」）。

## 三、本版带的修复（1 项，v1.18.27 安装包里没有）

### 根组织层级误判 —— 市州级单位可以建根组织了

- `api/v1/organization.py::_resolve_create_code`：只有存在上级（`parent is not None`）时才做
  「省级 → 市州级 → 县市级」相邻校验；无上级即根组织，**任一层级都可以**。
- `services/self_check_service.py::_check_org_hierarchy`：根组织不再校验层级，
  自检不再误报「根组织非省级」。

回归用例（红 → 绿全程留痕）：

- `tests/unit/test_org_root_level_r54.py`（5 例）：市州级 / 县市级 / 省级根都能建；
  有父级时跨级仍拒、相邻仍过。
- `tests/unit/test_org_root_level_selfcheck_r55.py`（5 例）：根为市州 / 县级时自检 `ok`；
  真正跨级仍 `warn`；正常链路 `ok`。

逐项细节见仓库根目录 `CHANGELOG.md` 的 `[1.18.27]` 段与其顶部
「Fixed（根组织层级误判）」小节。

## 四、验证

- 发版前 `HEAD`（`6d162cc4`）的 **PR Checks 全绿**（run `41005268405`，8/8 job：
  backend-test / frontend-check / e2e-test / windows-smoke / lint / static-analysis /
  security / upgrade-rehearsal）。
- **Nightly 全量** success（run `41022842073`）。
- `node scripts/sync-version.js --check` 通过（1.18.28 已同步 22 处目标）。
- `python scripts/sync_update_log.py --check` 通过（116 个版本段，最新 1.18.28）。
- `python scripts/check_changelog.py` 通过（当前版本已记录、格式与降序合规）。

## 五、升级方式

覆盖安装即可（无自动更新逻辑）：

1. 关闭正在运行的系统；
2. 运行 `MRRS-Setup-1.18.28-x64.exe` 覆盖安装到原目录；
3. 数据库位于 `%APPDATA%\Assistance-Management-Information-System\database\`，
   **覆盖安装不会删除数据**；升级前建议在「系统管理 → 备份管理」先做一份备份。
