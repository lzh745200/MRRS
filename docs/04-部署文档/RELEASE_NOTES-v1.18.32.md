# v1.18.32 发布说明（2026-11-01）

> 本版主题：**时间口径、数据归属、越权读取**三条主线上的 8 项"静默错"收口。
> 这些缺陷的共同特征是**不报错、不白屏**——接口照常返回 200，但数字或可见范围是错的，
> 因此很晚才被发现。逐条给出根因与现场识别方法，便于同类问题自查。

## 一、谁需要升级

| 角色 | 影响 |
|------|------|
| 县级管理员 / 业务员 | **必须升级**：Excel 导入项目/资金/学校后，非超管账号在自己列表里看不到记录（幽灵台账）；政策搜索把"字段没返回"显示成红色「禁用」；资金审批的核定金额被申请额覆盖（含 0 元核定的场景）。 |
| 系统管理员 | **建议升级**：审计页「今日操作数」在北京时间 0–8 点会把前一天算进今天；同步仪表盘趋势按 UTC 分桶；个人中心「最后登录时间」早 8 小时。 |
| 所有用户 | 登录页在关闭自助注册时的引导文案不再自相矛盾（机器码用途说明）。 |
| 安全 / 审计 | **必须升级**：`/sync/status`、`/sync/dashboard` 此前任意登录用户可读（包名、记录数、操作人、磁盘余量）；批量导出在"账号未绑定组织"时可整库导出。 |

## 二、修复清单（根因 → 改法）

### 1. 今日操作数按 UTC 零点清零

- **根因**：`AuditLog.created_at` 是 UTC 墙钟列，统计边界却写 `utcnow().replace(hour=0, ...)`。
  UTC+8 下"今天"从北京时间 08:00 才开始：0–8 点的操作落在 UTC 的前一天，被算进**昨天**的统计里。
- **改法**：本地零点 `datetime.now().replace(hour=0,...)` → `to_utc_naive()` → 与 UTC 列比较。
- **现场识别**：早上 8 点前打开审计页，「今日操作数」明显偏少（昨天偏多）。

### 2. 同步仪表盘趋势日期按 UTC 分桶

- **根因**：`log.created_at.strftime("%Y-%m-%d")` 直接切 UTC 日期。
- **改法**：`to_local(log.created_at).strftime("%Y-%m-%d")`。
- **现场识别**：北京时间 0–8 点的同步记录出现在"昨天"的柱子上。

### 3. `/auth/me` 最后登录时间早 8 小时

- **根因**：UTC 列直接 `strftime` 成字符串返回，前端当本地时间渲染。
- **改法**：`to_local(user.last_login)`。

### 4. 90 天未走访预警晚一天

- **根因**：`last_visit_date` 是本地日历语义的 Date 列，参照日却取 `datetime.now(timezone.utc).date()`。
- **改法**：`datetime.now().date()`。UTC+8 的 0–8 点不再少算一天。

### 5. 批量导出可整库导出（S2 红线）

- **根因**：`if not is_superuser and organization_id is not None and org_col is not None:` ——
  账号未绑定组织时 `organization_id` 为 `None`，整个条件为假，**组织过滤被跳过**。
- **改法**：拆成两层判定，非超管 + 模型有组织列 + 账号无组织 → 直接返回
  `{"success": False, "error": "账号未绑定组织，禁止批量导出"}`（fail-closed）。
  `validate_batch` 同口径。
- **现场识别**：部门级管理员导出的行数 = 全库行数。

### 6. Excel 导入的"幽灵台账"

- **根因**：`_import_projects` / `_import_funds` / `_import_schools` 只写业务字段，
  没写 `organization_id` / `created_by`（帮扶村导入路径一直有写）。
  列表按组织过滤 → 导入成功但列表为空。
- **改法**：三条路径统一补归属字段；模板未填 `organization_code` 时回落到调用者本组织。
- **现场识别**：导入结果页显示成功 N 行，回到列表只有 0 行；超管账号能看到。

### 7. 同步日志历史不按类型过滤

- **根因**：前端传 `{action, page, page_size}`，后端契约是 `{sync_type, limit}`，三个参数全被忽略。
- **改法**：前端改传 `{sync_type: 'export' | 'import', limit: 20}`。
- **现场识别**：导出页的历史里混着导入记录。

### 8. 其余展示层修复

- 包体积缺 `size` 字段时显示 `-`（不再 `NaN MB`）。
- 资金审批 `approved_amount || amount || 0` → `??`，0 元核定不再被申请额覆盖。
- 政策搜索 `status` 缺失渲染 `—`（不再误判成红色「禁用」），并按 FTS 实际字段映射分类/部门/日期。
- 登录页第 3 步标题按 `self_register_enabled` 切换，并说明机器码用于设备绑定/换机重置。

### 9. 权限收紧

`/sync/status`、`/sync/dashboard` 加管理员门禁，非管理员返回 **403**（此前 200 + 运维数据）。

## 三、升级步骤

1. **备份**：系统管理 → 备份与存储 → 创建备份（记下备份密码）。
2. **覆盖安装**对应架构的包：
   - Windows x64：运行 `MRRS-Setup-1.18.32-x64.exe`
   - 麒麟 / 国产 ARM64：`sudo dpkg -i MRRS-Setup-1.18.32-arm64.deb`（桌面版）
     或 `sudo dpkg -i assistance-management-system_1.18.32_arm64.deb`（standalone Web）
3. **验证**（3 分钟）：
   - 登录页可见版本号 1.18.32；`GET /api/v1/health` 全项 ok。
   - 用**非超管**账号导入一条项目，立刻在项目列表能看到（本版核心回归点）。
   - 审计页「今日操作数」与当天实际操作条数一致（0–8 点验证最准）。
   - 用普通账号访问 `GET /api/v1/sync/status` 应返回 **403**。
4. 升级后 30 分钟内不要卸载旧包，便于回滚（见 `OFFLINE_UPGRADE.md`）。

## 四、避坑指南（本轮踩到的坑，后续改动必看）

1. **UTC 列 + 本地日历语义**：凡是"今天/本月/最近 N 天"的统计，边界必须
   `本地零点 → to_utc_naive()`；展示类字段必须 `to_local()`。禁止 `utcnow()` 直接当"今天"。
   `models.base.UtcDateTime` 包装后 `isinstance(col.type, DateTime)` 会**静默失配**，判定用
   `models.base.is_datetime_type()`。
2. **fail-closed 写法**：`A and B is not None and ...` 这种复合条件最容易在"缺字段"时整体为假，
   把安全过滤跳过。数据域过滤必须是"没拿到组织 → 拒绝"，不能"没拿到组织 → 不过滤"。
3. **导入路径必须写归属字段**：新增任何导入实体时，`organization_id` / `created_by` 与手工创建
   保持同源；否则数据成为只有超管可见的"幽灵台账"。
4. **前端查询参数要与后端签名逐字对齐**：`action`/`sync_type`、`page_size`/`limit` 这类差异
   不会报错，只会静默失效。新增查询前先在 `app/api/v1/**` 里搜函数签名。
5. **`||` 与 `??`**：金额、数量、评分等"0 是合法值"的字段一律用 `??`；`||` 只用于字符串兜底。
6. **改端点权限会连带打挂既有测试**：`/sync/*` 收紧后，原有用例的 mock 用户没有 role →
   403。收紧权限时必须同步检查 `tests/unit/*sync*` 与 `tests/integration` 中直接构造 client 的夹具。
7. **覆盖率门禁是分支级 100%**：新增 `if/elif` 或三元的每个分支都必须有用例，
   尤其是"账号无组织"这类异常分支；只测 happy path 会在 CI 的 `backend-test` 段直接红。
8. **`--cov-fail-under` 不要写在命令行**：会屏蔽 `backend/.coveragerc` 的单一口径。

## 五、测试与验证依据

- 后端：CI 同构 12 段全量回归（`ENVIRONMENT=test`，Python 3.11.16），失败用例 0。
- 前端：3 分片全量（`npx vitest run --shard=i/3`），失败用例 0。
- 改动视图行/分支覆盖率：5 个文件均 100%（`LoginEnhanced` / `Export` / `Import` / `Detail` / `Search`）。
- 静态门禁：`flake8 app/ --max-complexity=16` 0 错、`vue-tsc --noEmit` 0 错、
  `check_menu_alignment` / `sync-version --check` 通过。
- 打包态冒烟：`python scripts/verify_frozen_modules.py` 校验冻结模块（含 `difflib` + 全部 `app.*`）。

完整日志与命令见 `docs/03-开发文档/09-审计报告/2026-11-01-回归测试报告-v1.18.32.md`。

## 六、本版构建与产物（2026-11-01）

- **源码冻结点**：`76a48b09`；annotated tag `v1.18.32` 已推送。
- **PR Checks**：run `41261848814`，**9/9 success**（12 段后端全量 + 前端覆盖率 + E2E +
  Windows smoke + 静态/安全/门禁）。
- **Windows x64 构建**：run `41263377714` success（8m51s）。
- **ARM64 构建**：run `41263377839` success（28m26s）。
- **Release**：`https://github.com/lzh745200/MRRS/releases/tag/v1.18.32`，共 8 个资产。

| CI 资产 | 大小（bytes） | SHA256 |
|---|---:|---|
| `MRRS-Setup-1.18.32-x64.exe` | 283,537,167 | `4c495825c034eb560a3f908c95fcb1546ac9a2756a358f8158b9e4b2b613bfc9` |
| `MRRS-Setup-1.18.32-arm64.deb` | 282,029,866 | `d05f3a506face767baf962da9708c831c96cf2d163e5924e1c2dbdeb16f1c3e0` |
| `assistance-management-system_1.18.32_arm64.deb` | 105,074,352 | `b2f31129d8ce3ce6866811204624dc6114dc28e51c8b93ae717c40d5427d1388` |

- **本地同 commit 构建**：`dist/electron/MRRS-Setup-1.18.32-x64.exe`（318 MB，
  SHA256 `435a606f0ccb046f139b9aa024fac8caeace8c0f25f63a2d8aa274681c13a5e1`）；
  前端 `version.json` = 1.18.32 / buildTime `2026-11-01T02:34:06Z`。
- **载荷冒烟**：解包 8,478 个文件 → 内置后端（隔离 APPDATA、端口 18033）`/health` 200：
  `version=1.18.32`、`migration.at_head=true`、`journal_mode=wal`、`clock.status=ok`。
  证据：`deliverables/smoke-health-1.18.32.json`。
- **安装验证**：
  - v1.18.30 的 NSIS 安装副本曾在本机 Program Files 实测可运行（`/health` 200、
    `/version.json` 200），证据 `deliverables/install-smoke-v1.18.30.log`；
  - 本执行环境仍禁止向 Program Files 写入：`v1.18.32` 安装器静默执行返回 0 但不落盘，
    故 **NSIS 注册安装/卸载冒烟未完成**，需在普通 Windows 桌面人工复验；
  - ARM64 仅有 CI 产物与校验和，未在真实 ARM64 设备安装。
