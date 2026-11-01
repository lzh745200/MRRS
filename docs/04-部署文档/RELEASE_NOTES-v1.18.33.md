# v1.18.33 发布说明（2026-11-01）

> 本版主题：**把全面审查报告里的「立即 5 项 + 短期 7 项」全部落地**。
> 这些项的共同特征是「不报错、但会拖垮系统或让结果悄悄错位」：长事务冻结事件循环、
> 主键冲突后外键挂错、导出被静默截断、决算金额固化、公式注入、管理面缺组织边界。
> 逐条给出根因与现场识别方法，便于同类问题自查。

## 一、谁需要升级

| 角色 | 影响 |
|------|------|
| 县级管理员 / 业务员 | **建议升级**：大批量数据包导入期间系统会整体卡住（最长 120 秒，连 `/health` 都没响应）；导出超 1 万行时少行但没有提示；决算生成后追加支出不会重算结余。 |
| 负责数据交换的岗位 | **必须升级**：数据包确认导入遇到同 id 不同内容会换新主键，但项目/经费等子表仍指向旧 id —— 返回 success=True，数据却挂错或丢失。 |
| 安全 / 审计 | **必须升级**：机器码管理面（列表/撤销）此前可跨组织读取 pass_code 与绑定用户名；审计日志删除/改备注只校验部门级管理员；备份默认明文且创建不写审计。 |
| 运维 | **建议升级**：JSON 日志新增 `request_id`，可与响应头 `X-Request-ID` 串联排查；`/system/metrics` 新增业务计数；Electron 不再默认批准摄像头/麦克风/定位。 |

## 二、修复与新增清单（根因 → 改法 → 现场识别）

### 1. 数据包确认导入冻结事件循环（API-02）

- **根因**：`confirm_import` / `confirm_import_with_conflict_resolution` 声明为 `async def`，
  函数体却是 zip 解析 + 逐行 upsert + `db_coordinator.exclusive_write(timeout=120)` 的同步重活。
- **改法**：拆出 `_confirm_import_sync` / `_confirm_import_with_conflict_resolution_sync`，
  用 `run_in_thread`（线程池 10）执行；`import_package` 的 checksum 计算同样下放线程池。
- **现场识别**：导入进行中刷新其它页面转圈、`/health` 超时。

### 2. 主键冲突换新 id 后子表外键不重写（API-01）

- **根因**：换 id 分支只插入新行，没有把 `{表名: {旧id: 新id}}` 回传给子表。
- **改法**：`_bulk_upsert_records` 增加 `remap` 收集映射；新增 `_fk_targets`（按 ORM 外键元数据）
  与 `_apply_fk_remap` 在写子表前改写引用；`DATA_TYPE_MODELS` 顺序保证父先于子。
- **现场识别**：导入成功但项目挂在同 id 的另一个村/组织下，或经费找不到对应项目。

### 3. CSV/Excel 公式注入

- **根因**：导出单元格直接写库值，`=HYPERLINK(...)` 等打开即被 Excel/WPS 当公式执行。
- **改法**：新增 `app/utils/export_safety.py`（`sanitize_cell/row/mapping`，仅字符串加 `'` 前缀，
  数字/日期不变），接入全部导出路径（通用导出、一户一档、消费帮扶、报表模板、审计、批量导出等）。
- **现场识别**：导出的 CSV 用文本编辑器看，危险单元格前应有一个单引号。

### 4. 机器码管理面无组织边界

- **根因**：`/machine-code/admin/list` 与 `/admin/revoke/{id}` 只判角色，无组织范围，
  返回字段含 machine_code / pass_code / 绑定用户名。
- **改法**：列表按 `_scoped_org_ids`（超管不限，其余本组织+子树，空集 fail-closed 返回空）过滤；
  撤销前 `assert_org_reachable`；服务层空列表返回空集而不是全表。
- **现场识别**：部门级管理员此前能看到别的单位的通行码。

### 5. 备份默认明文且创建/删除无审计

- **根因**：`POST /system/backups` 不传密码即落明文 `.db`，创建/删除不写审计。
- **改法**：默认用 `INTERNAL_BACKUP_KEY` 加密；创建/删除/恢复全写 `AuditLogger`；
  遗留 `POST /system/admin/backup`（裸 `shutil.copy2`）加弃用标记。
- **现场识别**：备份文件应为加密包（需要密码/密钥才能恢复），审计页能看到 `backup.*` 记录。

### 6. 导出静默截断

- **改法**：`/export/*` 五个端点在超上限（1 万行）时返回
  `X-Export-Truncated/X-Export-Total/X-Export-Returned/X-Export-Limit`，前端统一弹
  「仅导出前 N 条（共 M 条），请缩小筛选范围后重试」。
- **现场识别**：导出条数明显少于列表总数时会有提示，不再无声少行。

### 7. 决算结余固化

- **改法**：新增 `services/fund_settlement_service.py`（`recalculate_settlement_totals` /
  `refresh_project_settlements`，只重算**非 APPROVED** 决算），接入经费增删改与决算审批前。
- **现场识别**：追加支出后重开决算，`total_remaining` 应随支出变化；已审批决算不动。

### 8. 报表模板导入按村名裸查

- **改法**：导入按调用者组织过滤村、排除 `is_active=False`；未填组织时回填村组织；
  新建项目补 `organization_id`（否则非超管导入后自己看不到）。
- **现场识别**：同名村不再挂到别的乡镇/已删除村。

### 9. 审计日志缺请求关联 ID

- **改法**：`JsonFormatter` 从 `request_id_var` 取上下文写入 `request_id`（后台线程/启动期省略）。
- **现场识别**：日志行里多一个 `request_id`，与响应头 `X-Request-ID` 相同。

### 10. 新增：组织模块策略执行点（shadow）+ 前端接线

- 后端中间件 `org_module_policy_gate` 把 `OrgModulePolicy.edit_mode` 真正接到写请求上，
  `ORG_MODULE_POLICY_MODE=off|shadow|enforce` **默认 shadow**（只记 WARNING +
  响应头 `X-Org-Module-Policy: would-block`，不改行为）；5 秒 TTL 缓存，异常 fail-open。
- 前端登录成功 / 2FA 成功 / 布局挂载三处拉取策略，`visibility=hidden` 的菜单终于会隐藏。

### 11. 新增：Electron 权限处理器

- 默认拒绝，仅放行 `notifications` / `clipboard-sanitized-write` / `fullscreen`（大屏页需要）；
  摄像头 / 麦克风 / 定位 / 屏幕捕获不再被默认批准。

### 12. 新增：业务指标与签名校验

- `core/business_metrics.py`（进程内计数，重启归零）：数据包导入成功/失败、导出按格式、
  备份创建/恢复、权限包导入；`GET /system/metrics` 新增 `business` 段。
- `scripts/verify_installer_signature.ps1` 递归校验全部 exe；`build-windows.yml` 在发布前调用
  （有 `CSC_LINK` 时自动带 `-RequireSignature` 作为硬门禁）。

## 三、验证记录

| 项 | 结果 |
|----|------|
| 后端全量（12 段） | **12/12 PASS，15,523 passed**；覆盖率门禁 100% |
| 前端全量 | **348 files / 7,487 tests passed** |
| main PR Checks | run 41299746190 **9/9 job success** |
| tag 构建 | `v1.18.33` → run 41302341399（Windows）/ 41302341498（ARM64）均 success |
| 发布资产 | Windows 283,564,668 B；ARM64 Electron 282,094,704 B；ARM64 standalone 105,094,284 B（SHA256 见 `SHA256SUMS-*.txt`） |
| 冻结自检 | `[OK] difflib`、`app.*` 全部收录、`FROZEN_MODULE_CHECK_PASS` |
| 冷启动冒烟 | liveness / health / version.json 全 200 |

## 四、升级注意

1. 先备份（系统管理 → 备份与存储 → 创建备份），记录备份密码/密钥。
2. 覆盖安装对应架构的包；麒麟包 `sudo dpkg -i`，Windows 运行安装程序。
3. 升级后确认：登录页显示 1.18.33；`GET /api/v1/health` 全项 ok；导出超限能看到提示。
4. 首启后 30 分钟内保留旧包，便于按《离线升级与回滚指南》回滚。

## 五、已知限制与待确认

- **安装包未签名**：本版未配置代码签名证书，`NotSigned`；完整性以 Release 的
  `SHA256SUMS-*.txt` 为准。证书到位后 `-RequireSignature` 即为发版硬门禁。
- **组织模块策略默认 shadow**：不会真正拦截写请求，需观察 1~2 周后再切 `enforce`
  （避免存量配置问题一次性暴露成 403）。
- **权限包匿名导入仅限空库首装**：已有账号的机器需管理员登录后导入（防提权收紧）。
- **本地 NSIS 卸载器生成**在本开发机不可用（非交互会话无法完成提权 stub 执行），
  最终安装包以 GitHub Actions tag 构建为准。
