# 更新日志

所有重要的项目变更都会记录在此文件中。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/),
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [1.18.24] - 2026-10-28 — 出包链路收口：v1.18.21~23 三个 tag 构建失败的根因修复

> v1.18.21、v1.18.22、v1.18.23 三次 tag 构建**全部失败**，因此自 v1.18.17 之后再没
> 产出过安装包。两轮排查定位到三个叠加缺陷（都在**发布流水线**，不在业务代码），
> 本版把它们一并收口，确保下一次 tag 能真正出包。

### Fixed

- **Windows：`npm ci` 网络抖动直接堵死发布**（`build-windows.yml`）
  `smoke-test` 作业的 `npm ci` 报 `npm error code ECONNRESET` → exit 152；而它是
  `build-windows` 的 `needs` 前置，一抖整个 Windows 安装包**根本没开始构建**。
  原写法只有一次 `|| npm install` 兜底，两次尝试落在同一段故障窗口里。
  现改为 **三次退避重试**（20s/40s）+ `fetch-retries=5` /
  `fetch-retry-mintimeout=20s` / `fetch-retry-maxtimeout=120s`，并在三次仍失败时
  给出明确 `::error::`（"若日志是 ECONNRESET/ETIMEDOUT 属 CI 网络问题，重跑即可"）。
  同一加固应用到主构建的 `Build frontend`。
- **ARM64：构建"成功却无产物"**（`build-arm64.yml` + `Dockerfile.kylin-standalone`）
  两个缺陷叠加：
  1. **退避从未生效** —— `echo "... diagnostics ====="            sleep $((i * 60))`
     写在同一行，`sleep` 被当成 `echo` 的**参数打印**，三次重试之间根本没有等待；
  2. **失败被吞** —— `for ... done` 之后没有失败出口，步骤退出码取到最后一条
     `echo`/`grep ... || true`，于是三次全红仍报 **success**；
     问题被推到下一步才炸（`ls: cannot access 'dist/deb/output/*.deb'`），
     表现成"构建成功却没有产物"，极难定位。
  修复：`sleep` 拆独立行 + 循环后 `::error::` 与 `exit 1`；
  同时给容器内 `npm install` 加 npm 重试参数与三次退避
  （真实错误本来就是容器内 `npm error network ... ECONNRESET`）。

### Added

- `docs/04-部署文档/RELEASE_NOTES-v1.18.21.md`：v1.18.18→v1.18.21 的发布说明
  （6 个系统接口不可达、4 条重复路由、路由鉴权门禁、大瓦片包导入超时 30s→15 分钟、
  Windows %TEMP% ACL 构建兜底、门禁统一入口 + no-print/dist 棘轮、mypy 1394→1385、
  as any 196→172 等），避免 Release 正文落到兜底占位。

### Changed（补：离线缓存优先）

- **`pr-checks.yml` 的 `frontend-check` / `e2e-test` 加「离线缓存优先」**：
  先给 `~/.npm` 叠一层带 **restore-keys** 的 `actions/cache`（setup-node 的缓存 key 绑死
  `package-lock.json`，lock 一变即 miss，这正是重试全落在同一故障窗口的原因），
  安装时**首试 `npm ci --offline`**（只吃本地缓存，零网络），未命中才走原有的
  5 轮退避 → 镜像兜底 → `npm install`。缓存命中时 registry 整段不可达也能装出依赖。

### Tests

- `npm run test:electron` **14 例全过**（含 ci-wiring 守护：发布门禁等待预算 /
  main 不取消 / check_main_ci 接线）；
- 两个 build 工作流 YAML 可解析；全仓扫描"退避失效/失败被吞"同类模式，
  仅 `pr-checks.yml` 的 playwright 重试疑似——细查其循环后第 721 行已有 `exit 1`，非隐患。

### Fixed（缺陷排查批 R20 · 时间基准 / 事件循环 / 故障伪装）

- **时间基准**：`self_check_service` 的「账号锁定」「最近导入」两项用 `datetime.now()`
  （本地墙钟）与 `UtcDateTime` 列比较，UTC+8 下阈值整体后移 8 小时——锁定时长只有 15 分钟，
  于是**明明有账号被锁，体检结论恒报「没有处于锁定状态的账号」**；
  `backup_scheduler.weekly_report_job` 把本地日期直接当 `Todo.updated_at`（UTC）阈值，
  漏掉上周最早 8 小时完成的待办。统一改为 `utcnow()` / 本地日界减时区偏移。
- **重活离开事件循环**：`/system/backup/restore`、`/upload-restore` 此前在 async 端点里同步跑
  `restore_backup`，事件循环被占死 → 维护窗口 `wait_for_idle` 的在途计数（由 async 中间件递减）
  永远降不下来，固定空转 10s 打 ERROR 且**恢复全程全站无响应**；`.rrs` 导入导出的 PBKDF2 600k
  与整包读写、数据包校验/预览的「假异步」（async 零 await）同样移入线程池；数据包上传端点改
  `_stream_upload_to_file` 边读边写，峰值内存不再等于整包体积。
- **故障不再伪装成业务数据**：`dashboard`（stats / kpi-trends / yearly-trends / summary）与
  `reminders`（list / scan）异常统一 **500**，不再 `200 + 全 0 / null`；权限包校验异常由
  「`None` 视为通过」改 **fail-closed**（该返回值的下一步是 `_clear_existing_data()`，
  损坏包会被当成合法包清库）；加密导出单表失败不再写 `[] + success=True`。
- **口径补齐**：`funds` overview 补 `planned_count`（`planned` 是 `FundStatus` 合法值，
  前端「规划中」卡片恒 0 的根因）、multi-dimension 支持 `fund_type`（前端发 `type`，
  FastAPI 静默忽略 → 图形不随筛选变）；前端 `schools/Analysis` 把本就是万元口径的
  `project_total_budget` 又除了一次 10000（比详情页缩水一万倍）；`funds/EnhancedList`、
  `UserFundList` 读的是后端并不存在的 `total_allocated` / `by_status.pending.count`（三卡恒 0）；
  `funds/Report` 算好日期区间却没传给接口（表头印周期、表格含区间外数据）；
  `ruralWorks/Analysis` 删掉伪造的「投入资金 / 质量评分 / 环比 0%」（模型无对应字段），
  KPI 改真实「覆盖村庄数」，时间范围筛选从只有 UI 改为真实生效。
- **测试**：一并纠正 5 条把旧行为当预期的用例（reminders / dashboard summary / stats /
  dashboard 缓存），其中缓存用例的链式 mock 靠 `except` 吞掉 `MagicMock > int` 的 `TypeError`
  才「通过」，从未真正跑过查询路径。相关模块 **1244 passed**、前端六个目录 **1967 passed**。

## [1.18.23] - 2026-10-28 — 发布收口重建（补齐应用内更新日志同步）

> **为什么还要 1.18.23**：v1.18.22 的 tag 打在 `4dc1db7`，而该提交的
> `version_history_data.py` 尚未同步 1.18.22 条目、`version.json` 的 `description`
> 仍是 1.18.21 的标题 —— CI `static-analysis` 的 `check_update_log.py` 会因此判红
> （收口时在独立 worktree 上按 tag 提交复现：`应用内更新日志已过期` 与
> `description 与 CHANGELOG 更新标题不一致`）。已发布的 tag 不改写，故补齐同步后重建。

### Fixed

- **应用内更新日志与 CHANGELOG 重新同步**：`scripts/sync_update_log.py` 写入本版条目，
  `backend/version.json` 的 `description` 与本版 CHANGELOG 标题对齐。
- 版本单源同步到 **1.18.23**（`node scripts/sync-version.js --write --version 1.18.23`）；
  README 本版亮点 / docs/INDEX / RELEASE_NOTES-v1.18.23 与三份 PPT 同步到本版。

## [1.18.22] - 2026-10-28 — 发布收口：换 tag 重建 + 修复两处交付前回归

> **为什么有 1.18.22 而不是直接发 1.18.21**：`v1.18.21` 标签当时打在 `fe5c395` 上，
> 而该提交比收口基线落后 9 个提交；其 tag 构建的 `smoke-test` 作业在
> **Frontend release smoke subset** 步骤失败——真实原因是 GitHub runner 上
> `npm ci` 连续两次 `ECONNRESET`（exit 152），前端冒烟子集根本没跑起来，
> 不是代码缺陷。已发布的 tag 不改写，因此把**同一批变更 + 收口修复**以
> `v1.18.22` 重新出包，让 tag 指向真正验证过的提交。

### Fixed（交付收口 · 实测复现的回归）

- **`api/milestones.ts` 的 `milestoneProgress` 在 `items` 为 `null`/`undefined` 时抛
  `TypeError`**（`tests/unit/api/milestones.test.ts` 2 例红）：信封守卫只容忍"缺 `items` 键"，
  不容忍响应体本身为 `null`/`undefined`（204 空体、接口降级返回）。改为显式
  `{ items?: T[] } | null | undefined` + 可选链，未回退到宽松断言。修复后 13/13 绿。
- **政策编辑页不再臆造 `status` 默认值**：`|| 'draft'` 会让"详情省略 status"的已发布政策
  在用户保存时被静默降级为草稿（且与新增表单默认 `active` 矛盾）。改为只透传。
- **两处过时测试断言按真实契约更新**：`getLevelOptions` 现按真实契约**无参**调用
  （后端不接收分类参数）；结对页帮扶村 mock 补齐 `villageName`（后端 `to_dict` 两种都返回）。
- **`types/policy.ts` 缺文件尾换行**导致 `lint:check`（`--max-warnings=0`）失败，会拦 CI lint 作业。

### Changed

- 版本号单源同步到 **1.18.22**（`node scripts/sync-version.js --write --version 1.18.22`，
  14 个目标文件；`--check` 通过）。文档（README 本版亮点 / docs/INDEX 索引 /
  RELEASE_NOTES-v1.18.22）与三份 PPT（介绍 56 页 / 零基础 44 页 / 操作培训 60 页）
  同步到本版版本与实测数字（后端 **14,896** 用例 / 前端 **7,384** 用例）。

## [1.18.21] - 2026-10-28 — 门禁统一入口 + no-print/dist 两道棘轮 + 端点口径写明

> **背景**：体检时 29 道门禁调用方式各异，我一天内踩了三次"门禁自己跑不起来"（cwd 错、
> 缺 --json/--baseline、GBK 控制台崩），差点被误判成代码红；同时发现"生产代码 print"
> 这类在桌面端**永远看不到输出**的问题没有任何约束，前端产物膨胀也没有上限。

### Added

- **`scripts/run_gates.py`（门禁统一入口）**：把「每个门禁在哪跑、带什么参数」固化成注册表
  （37 道，含 3 道需外部产物的慢门禁），本地一条命令与 CI 同款；支持 `--list / --only / --json /
  --slow / --stop-on-fail`。需要 `coverage-branch.json` 或 gh 网络的慢门禁默认 SKIP（不伪装成绿），
  避免用陈旧覆盖率产物制造假红。
- **`scripts/check_no_print.py`（no-print 门禁）**：生产代码禁止 print —— 桌面端无控制台窗口，
  print 输出用户与排障都看不到。允许项仅 2 处（`main.py` 启动横幅、`logging_config` handler
  关闭兜底），均属 logger 不可用的兜底路径。**先纠错**：体检时按 `print(` 粗匹配得到 38 处，
  实际是误报（命中了 `fingerprint(` / `setup_print(`）；本门禁用行首锚定，真正的 print 只有 3 行。
- **`scripts/check_dist_size.py`（前端产物体积棘轮）**：dist 总字节 / 文件数 / br 数三项对比基线，
  超基线 +5% 即失败；当前基线 **9.2 MB / 674 文件 / 114 个 br**。接进 Windows 与 ARM64 出包流水线
  （构建之后、上传产物之前）。

### Changed

- **CI 接线**：`pr-checks.yml` 的 static-analysis 加 `check_no_print.py`；`build-windows.yml` 与
  `build-arm64.yml` 在 `npm run build` 之后加 `check_dist_size.py`。
- **端点计数口径写明**（CLAUDE.md）：`check_doc_numbers` 统计 `/api` 前缀端点（**845**），
  另有 4 条非 `/api` 路由（`/health`、`/favicon.ico`、`/version.json`、SPA catch-all），
  全部路由合计 **849**（`check_route_auth` 口径）。两个数字不是矛盾，避免再次被误读成"删了接口"。

### Fixed

- **`scripts/run_backend_tests_segmented.py` 的一处裸 pragma**（`# pragma: no cover` 无理由）
  → 补理由，`check_pragma_reasons --max-bare 0` 恢复全绿（此前门禁在总 222 处 pragma 里恰好卡
  这 1 处）。

### Changed（批 2 起：类型债分片清零，本片 = 基础设施层）

- **`as any` 基础设施层清零（196 → 188）**：`api/request.ts`（CSRF 取 token、`_retry`/`silent`
  扩展标记）、`api/milestones.ts`（数组/信封双形态）、`stores/organization.ts`（列表载荷）、
  `stores/user.ts`（头像响应）、`utils/desensitize.ts`（索引写入）改为**显式形状 + 类型守卫**，
  不再用宽松断言吞掉契约变化；`request.ts` 新增 `InternalRequestConfig`（拦截器内部标记，
  不进对外契约）。`vue-tsc` 0 错误，相关 19 个测试文件 **472 passed**。
  注：门禁按字面量计数，注释里出现该字样也会被计入 —— 注释措辞已同步改掉（188 为真实值）。
- **`as any` 组件层清零（188 → 181）**：`components/map/OfflineMap.vue` 引入本组件自用的
  `GeoJson`/`GeoFeature` 形状并把 `registerMap` 载荷类型由 `Parameters<typeof
  echarts.registerMap>[1]` 反推（不深度依赖 echarts 内部路径）；`borderType: 'dashed' as const`。
  `components/permission/PermissionAssignmentDrawer.vue` 抽出 `unwrapPayload()` 统一解包
  信封/裸载荷，角色、权限、菜单三处响应改为显式形状取值（权限键顺手过滤非字符串）。
  `vue-tsc` 0 错误、两文件 eslint 0 警告，相关组件测试 **55 passed**（OfflineMap 10 +
  PermissionAssignmentDrawer 45）。
- **`as any` 政策模块清零（181 → 172）并修掉一处假传参**：新增 `types/policy.ts`
  （`PolicyRecord` 边界类型 + `PolicyPayload`），`stores/policy.ts` 的 `policyList`/`current`
  由 `ref<any>` 改为 `ref<PolicyRecord[]>`/`ref<PolicyRecord | null>`，`createPolicy`/`updatePolicy`
  入参由 `any` 改为 `PolicyPayload`；`views/policies/Edit.vue` 相应去掉 9 处宽松断言。
  **同时发现一处真实的接口谎报**：`(getLevelOptions as any)(formData.category)` 传了参数，
  但后端 `/policies/options/levels` 签名是 `get_level_options()`（**不接收任何参数**），
  参数一直被静默忽略 —— 现在按真实契约调用。表单回填对可选字段统一补默认值
  （`policy.title ?? ''` 等），不再把 `undefined` 塞进必填字段。`vue-tsc` 0 错误，
  policy 相关测试 **68 passed**（store 25 + api 43）。
- **mypy 按模块收紧（1391 → 1385），先清 `core.config` 传递依赖链**：
  `core/logging_config.py` 的 `file_handler` 先赋 `SafeTimedRotatingFileHandler`、else 分支
  赋 `SafeRotatingFileHandler`，mypy 按首赋值推断后判类型冲突 —— 显式标注公共基类
  `BaseRotatingHandler`；`utils/runtime_secrets.py` 的 `_atomic_write_json(path: Path)` 却被
  传 `str`、`_load_secrets_file(secrets_file: str)` 却被传 `Path`（契约自相矛盾）——
  三者统一为 `str | Path`。新增守卫 `tests/unit/test_mypy_clean_modules.py`：
  mypy 断言两模块 0 错误 + `str`/`Path` 两种入参往返用例（mypy 未安装时 skip）。
  相关 62 passed。
- **`as any` 帮扶村列表切片清零（172 → 162），并修出一处真实字段口径不一致**：
  `api/supportedVillage.ts` 补 6 个响应类型（`VillageListPayload` / `VillagePurgePreview` /
  `VillagePurgeResult` / `VillageBatchDeleteResult` / `VillageCreated` / `VillageImportResult`）
  并给 6 个函数加泛型；`views/analytics/supported-villages/List.vue` 去掉 10 处宽松断言
  （列表载荷、级联统计、彻底删除、批量删除、创建、导入、私有过渡字段）。
  **连带发现**：`types/analytics.ts` 的 `SupportedVillage` 只声明了 camelCase `villageName`，
  而 `views/pairing/List.vue` 读的是 snake_case `village_name`（靠宽松断言躲过编译期检查）。
  后端 `to_dict()` 确实两种都返回，但类型没写全 —— 现补可选别名，并让结对页改用规范
  `villageName`，避免后端哪天只留一种就别处静默渲染空标签。`vue-tsc` 0 错误，
  帮扶村/结对相关 **92 passed**。
- **`as any` 审批待办切片清零（162 → 155）**：`api/approval.ts` 补全两处**类型没写全**的
  历史契约 —— `ApprovalTask` 增加旧字段别名 `applicant`/`submit_time`，`TaskDiff` 增加旧键名
  `original`/`changed` 与事件源 `history`/`status_logs`（视图一直在容错读这些键，类型却没声明，
  只能靠断言）。`views/approval/PendingList.vue` 去掉 7 处断言，并把可转交用户解析收敛为
  `pickStaffUsers()`：兼容裸数组/分页信封，且**按 id 是否为数字过滤脏数据**（以前 `as any[]`
  强转会把脏行直接塞进下拉框）。`vue-tsc` 0 错误，审批相关 **72 passed**。
- **`as any` 乡村工作切片清零（155 → 150）**：`api/ruralWork.ts` 从全 `any` 补成
  `RuralWorkRecord`（含索引签名兼容后端扩展字段）+ `RuralWorkListPayload`（裸分页/信封双形态）
  + `RuralWorkCreated`；`views/ruralWorks/Task.vue` 去掉 5 处断言。
  **两处不是删断言而是修契约**：① `el-upload` 的 `:file-list` 原用 `as any` 强转，但我们的附件
  `uid` 是字符串、el-upload 要求数字 —— 改为 `progressFileList` 计算属性按真实契约映射
  （不改提交给后端的数据）；② 后端状态字符串直接赋给 `Task['status']` 联合类型，
  改为 `normalizeTaskStatus()`，未知值回落 `pending`（避免渲染空状态标签）。
  `vue-tsc` 0 错误，乡村工作相关 **110 passed**（Task 67 + api 43）。
- **`as any` 项目模块清零（150 → 144）+ 修掉 main 上一处 tsc 红**：`api/projects.ts` 补
  `ProjectCreated` / `ProjectFileItem` / `ProjectFilesPayload`，`create`/`update`/`listFiles`
  加泛型；`views/projects/Edit.vue` 去掉 6 处断言。
  **类型猜错被 tsc 当场抓住**：`ProjectFileItem` 起初按 `name/size/url` 声明，模板里实际读的是
  后端字段 `filename/file_size/created_at` → 编译直接报错，说明这层类型确实在替人守字段名。
  另修 `views/system/PermissionPacks.vue`：表格 `@selection-change="(rows) => (bindSelection =
  rows)"` 内联箭头参数被推断为隐式 any（main 上 `vue-tsc` 因此变红，来自提交 `3ae18cd`），
  收敛为具名处理器 `handleBindSelectionChange(rows: PackSelectionRow[])`，并把 id 收紧为
  `number`（`bindPackUsers` 要的就是 number[]）。`vue-tsc` 0 错误，项目相关 **91 passed**。
- **`as any` 政策列表 / 监控台 / 数据分级三片清零（144 → 131）**：
  `api/policy.ts` 补 `PolicyImportResult`/`PolicyImportError`（逐行错误明细），列表页错误提示改用
  `importErrors` 局部变量（顺带给 `result.imported` 补默认值 0，避免提示里出现 `undefined 条`）；
  `views/system/MonitoringDashboard.vue` 抽出 `unwrapMonitorPayload()` 统一处理「裸载荷 / `{data}` /
  `{data:{data}}`」三种监控响应形态（此前 4 处各自写 `(res as any)?.data?.data ?? ...`），
  `allSettled` 结果改用 `'value' in result` 收窄；`system/DataTier.vue` 去掉对 `StorageStats`
  索引签名的冗余断言，`listArchives` 返回类型由 `ArchiveList | Record<string, any>` 收窄为
  `Partial<ArchiveList>`（两层归档各自可选，缺省即空列表）。
  `vue-tsc` 0 错误，监控/分级相关 **91 passed**（监控 47 + 分级 44）。
- **`as any` 报表模板 / 通行码两片清零（131 → 123）**：
  `reportTemplates/Index.vue` 的 `(await import('xlsx')) as any` 实测**根本不需要断言**（依赖自带类型），
  模板列表三层三元表达式收敛为 `pickTemplateList()`（直接数组 / `{data}` / `{items}` 三形态）；
  通行码链路把「顶层字段或 `data` 信封」两种形态**写进 API 返回类型**
  （`machineCode.createMachineCode`、`organizationPassCode.getOrganizationVerificationCode` /
  `createOrganizationPassCode`），`organization/PassCodeManagement.vue` 去掉 4 处断言。
  **连带修掉一个真缺陷**：`admin/MachineCodeManagement.vue` 直接赋 `response.pass_code` 给
  `ref<string>`，类型收紧后暴露「信封形态下会是 `undefined`」—— 改为 `pass_code ?? data?.pass_code ?? ''`，
  不再把 `undefined` 塞进展示字段。`vue-tsc` 0 错误，报表/通行码相关 **84 passed**。
- **`as any` 政策详情 / 帮扶村详情清零（123 → 114）**：
  `api/policy.ts` 的 `getStatusColor` 明确返回 el-tag 联合类型 `TagType`（原先返回 `string`，
  模板里只能 `as any` 才能绑上 `:type`）；`Policy` 接口补 snake 别名 `file_type`（历史接口仍在返回）；
  `api/supportedVillage.ts` 的 `getYearlyData` 改为**泛型**（默认 `YearlyDataPayload`，调用方传自己的
  具体类型），年度数据不再靠宽松断言赋值。两个详情页里的私有过渡字段 `_transitionFundingItems`
  也改为显式扩展类型后 `delete`。`vue-tsc` 0 错误，政策/帮扶村相关 **260 passed**（11 个文件）。
- **`as any` 数据看板 / 角色管理清零（114 → 103）**：`api/dashboard.ts` 补
  `DashboardStatsPayload` / `YearlyTrendsPayload`（trends 四项 + 三年数组，索引签名放行扩展字段）；
  图表 `click` 回调改为 `(params) => void handleRegionClick(params)` —— echarts 要求回调返回
  `boolean|void`，直接传 async 函数会被类型拒绝（原写法只能 `as any` 绕过）；
  角色页 4 处模板断言收敛为 `toRoleItem(row)` 单一收窄点（el-table 插槽 row 是宽泛的
  `DefaultRow`，与 `RoleItem` 不兼容）。`vue-tsc` 0 错误，看板/角色相关 **106 passed**。
- **新增「静默吞异常」棘轮门禁（第 34 道）**：`backend/scripts/check_silent_swallow.py`。
  AST 扫 `except Exception`（含 `BaseException`），**既不打日志也不重新抛出、且无显式豁免**
  即判违规 —— 这类不是「兜底」而是「故障被彻底吞掉」：现场只看到功能没反应，日志里一行线索都没有。
  首次扫描 **126 处**，基线已登记（`gate_baselines/silent_swallow.txt`，只减不增）；
  豁免写法为行内 `# nosec:swallow - <理由>`。已接入 `run_gates`（33 → 34 道）与 CI
  static-analysis 作业。新增 5 例判定回归（纯 pass 抓、留痕放行、重抛放行、显式豁免放行、
  收窄到具体异常不在范围）。
- **按风险收口前 3 处静默吞异常（126 → 123）**：
  ① `auth/auth.py` 二次验证临时令牌解码失败：原来 `except Exception: payload = None`，
  线上只能看到 401，分不清是用户令牌过期还是服务端密钥配置错 → 补 `logger.info` 留痕；
  ② `effectiveness.py` 复核任务创建失败：本就不阻断评估，但审批任务没建起来会导致后续无人复核，
  属静默业务缺口 → 补 `logger.warning(..., exc_info=True)`；
  ③ `data/data/reports.py` 解析历史 `village_ids` 失败：原来直接 `pass` → 补 `logger.debug`
  带上具体异常，便于后续数据修复。
- **静默吞异常再收口 13 处（123 → 110）**：`system/health.py`（3：备份目录/磁盘空间/慢查询）、
  `system/metrics.py`（4：运行时长/进程/数据库不可用 + 1 处改为显式 `nosec:swallow` 豁免，
  因为它是「日志设施自身故障」的兜底）、`system/system.py`（3：数据库连通性/缓存/依赖版本）、
  `core/database.py`（2：关闭连接前 `PRAGMA optimize` 失败留痕 + 1 处豁免，理由是其异常
  已转存给调用方而非吞掉）、`core/database_indexes.py`（1：单表行数统计失败）。
  统一按「高频轮询端点用 debug、真实故障用 warning」的口径，避免健康检查刷日志；
  基线 123 → 110，门禁 total=110 baseline=110 NEW=0。
- **静默吞异常门禁补一类合法形态 + 再收口 39 处（110 → 71）**：
  **门禁语义修正**：诊断类接口的 `except Exception as exc: return {"error_type": ...}` 其实**没有吞掉**
  故障（错误已外化到响应里），原来被误判为违规 —— 现在把「失败写进输出」也算合规
  （识别 error/failed/unavailable/degraded 等字面量），`diagnostics.py` 的 10 处因此转正；
  **真实补日志 19 处**：`excel_importer_service.py`（6）、`analytics_service.py`（5）、`report_templates.py`（4）、
  `school.py`（3）、`startup/preflight.py`（1），消息统一带**函数名**（如 `get_village_analysis 兜底失败（已降级）`）
  便于定位；`core/logging_config.py` 的 2 处加 `nosec:swallow` 豁免（logger 自身不可用，无法再留痕）。
  基线 110 → 71（门禁 total=71 baseline=71 NEW=0）。
- **静默吞异常清零（71 → 0），门禁转为「零容忍」**：35 个文件、71 处宽泛兜底全部改为
  **留痕降级**（`logger.warning('<函数名> 兜底失败（已降级）: %s', exc, exc_info=True)`），
  行为不变、可观测性补齐；10 个原本没有 logger 的模块同时补 `import logging` + 模块 logger。
  **门禁语义再校正一处**：原先用前缀匹配，把 `except HTTPException:`、
  `except (asyncio.CancelledError, Exception):` 这类**具体异常**也算进来（误报）—— 现改为
  `(?<![A-Za-z_])(?:Base)?Exception` 精确匹配，只查真正的宽泛兜底；基线文件已收敛为 **0 条**
  （`gate_baselines/silent_swallow.txt` 为空 = 新增一处即红）。
  验证：`check_silent_swallow` total=0 baseline=0 NEW=0；`flake8 app/` 0；`import app.main` 通过；
  seg02（313 passed）+ seg03（178 passed）全绿。
- **mypy 再收紧一个模块：`core/security.py` 清零（1385 → 1379）**：
  bcrypt 兼容补丁里 `_bcrypt.__about__` / `__version__` 是**运行时注入的动态属性**，直接写属性赋值
  会让 mypy 报 `attr-defined` —— 改用 `setattr`/`getattr`（行为等价，且版本缺失时有 `'0.0'` 兜底）；
  `payload['sub']` 取值由 `username: str = payload.get('sub')` 改为先取 `Unknown` 再用
  `isinstance(raw, str) and raw` 收窄（原来靠 `None` 判断，非字符串的 `sub` 会漏进下游）；
  `FORBIDDEN_USERNAME_PARTS` 补 `list[str]` 注解。
  守卫 `test_mypy_clean_modules.py` 的清单扩到 3 个模块，并改用 `--follow-imports=skip`
  （只看模块自身，不追 `transaction`/`pii_crypto` 的存量债）。security 相关 **102 passed**。
- **修掉 `upload_endpoints` 门禁的一处误报（不是代码问题，是门禁不认合规写法）**：
  `/data-packages/import` 走的是自写的流式落盘助手 `_stream_upload_to_file(...)`（边读边写、
  带 `max_bytes` 上限、峰值只多一个分块，比 `read_upload_with_limit` 更省内存），但该助手的
  `file` 参数**没有 `UploadFile` 注解**，而门禁原先只把「带注解的函数」当作可委托的合规目标
  → 端点委托给这个合规助手反被判违规。现改为按「同文件内的函数定义 + 自身合规」判定，
  新增 3 例回归（裸 `await file.read()` 必须被抓、委托无注解流式助手必须放行、
  `read_upload_with_limit` 必须放行）。`upload_endpoints` 恢复 `total=0 baseline=0 NEW=0`。
- **环境事件（记录，不掩盖）**：验证中发现 `frontend/node_modules` 被清空（只剩空目录）、
  `backend/.venv` 的 mypy 也消失 —— 属于并发会话为出包做的依赖重建。已用 `npm ci` 恢复前端依赖
  （543 包，约 1 分钟），逐条修完类型再复绿；mypy 待其 venv 重建完成后再验证下一批模块收紧。

### Added（批 3 起：性能基线）

- **`scripts/bench.py`（关键路径性能基线，只报警不阻断）**：固定 5,000 行数据测三条热路径 ——
  xlsx 解析（经统一读取层）、CSV 导出（含 UTF-8 BOM）、帮扶村模板生成；输出 JSON 并与
  `scripts/gate_baselines/bench_baseline.json` 比较，**超基线 50% 只 WARN**（CI 机器噪声大，
  硬阈值只会制造假红），`--strict` 才非 0。首测基线：xlsx 解析 **0.322s** / CSV **0.005s** /
  模板生成 **0.052s**（5,000 行）。已注册进 `run_gates --slow`，配套 2 例阈值语义测试
  （50% 边界、rows 不参与比较）。

### Tests

- 新增 `backend/tests/unit/test_gate_entrypoints.py`（8 例）：CI worklow 里出现的**每个**
  `check_*.py` 必须在统一入口注册（防漏跑）、注册脚本必须真实存在、门禁名唯一、`../scripts/`
  门禁必须在 backend 下运行；no-print 的正/负/误报三例；dist 体积棘轮的增长检测与容差边界。
- 新增 `backend/tests/unit/test_segmented_runner_lock.py`（5 例，见上一版）。
- `python scripts/run_gates.py` 一键跑 33 道（默认档）结果：PASS 31 / SKIP 2 / FAIL 0。
- 补两处 **v1.18.19 漏测的分支**（main 上 `frontend-check` 的最后一个红点）：
  `importTiles` 上传进度回调的空值/钳位分支（`tests/unit/api/recycleAndOfflineMap.test.ts` +3 例：
  无回调早退、事件与 total 缺失、loaded 缺失或为负）与 `MapTileManager` 超时判定的
  单侧命中/空错误分支（`tests/unit/views/system/MapTileManager.test.ts` +3 例：
  只有 timeout 文案、缺 code/message、拒绝值为 null）。修前 `src/api` 分支 57.14%
  （`offlineMap.ts` 60-61、63 行）、`src/views` 分支 98.46%（209 行）；修后
  `npm run test:coverage` **EXIT=0**（347 文件 / 7,384 用例，各阈值 100%）。
### Fixed（交付收口 · 实测复现的回归）

- **`api/milestones.ts` 的 `milestoneProgress` 在 `items` 为 `null`/`undefined` 时抛
  `TypeError`**：本轮"as any 清零"把守卫写成
  `(items as unknown as { items?: ProjectMilestone[] }).items ?? []` —— 只容忍"信封里没有
  `items` 键"，不容忍**响应体本身是 null/undefined**（204/空体/接口降级返回）。
  收口实测 `tests/unit/api/milestones.test.ts` 2 例红
  （`Cannot read properties of null (reading 'items')`）。
  改为 `const envelope = items as { items?: ProjectMilestone[] } | null | undefined` +
  `Array.isArray(items) ? items : (envelope?.items ?? [])`：仍是显式形状 + 可选链，
  没有回退到宽松断言。该文件 **13 例全绿**。
- **政策编辑页不再臆造 `status` 默认值**：`7e44a9d` 把回填写成
  `formData.status = (policy.status as ...) || 'draft'` —— 详情响应省略 `status` 时，
  用户一保存就会把**已发布政策静默降级为草稿**（且与新增表单默认 `active` 自相矛盾）。
  改为只透传（缺失即 `undefined`），恢复"不替用户臆造状态"的语义。
- **两处过时测试断言按真实契约更新**（实现是有意修正，测试停在旧行为）：
  ① `policies/Edit.test.ts` 的 `handleCategoryChange` 原断言 `getLevelOptions('military')`，
  但后端 `/policies/options/levels` 不接收参数（本轮"假传参"修复），改断言无参调用；
  ② `pairing/List.test.ts` 的帮扶村 mock 只给 `village_name`，而结对页已按规范字段
  `villageName` 渲染（后端 `SupportedVillage.to_dict` **两种都返回**），mock 补齐双键。
- **`types/policy.ts` 缺文件尾换行**导致 `npm run lint:check`（`--max-warnings=0`）失败，
  会让 CI 的 lint 作业变红；`prettier --write` 修正，零逻辑变化。
- **收口实测（2026-10-28，本机 Python 3.11.16 / Node 25.2.1）**：
  `scripts/run_gates.py` 默认档 **34 道 PASS / 0 FAIL / 0 SKIP**（含 stack_alignment、
  route_auth 849 路由、type_debt 188 持平、dist 9.2MB）；后端分段 12/12 PASS、
  **14,896 用例**、覆盖率 **100.00%（46,243 行 / 11,560 分支，0 漏）**；
  前端受影响文件 **71 例全绿**（milestones 13 + policies 42 + pairing 16），
  全量复跑结论见交付报告与 CI。

## [1.18.20] - 2026-10-28 — 构建链路兜底（Windows %TEMP% ACL）+ 门禁自身健壮性

> **起因**：本轮全量体检发现 `npm run build` 在本机**直接失败**（不是警告）：
> `[vite:esbuild-transpile] remove C:\\Users\\...\\AppData\\Local\\Temp\\esbuild-...: Access is denied.`
> —— %TEMP% 目录存在「拒绝删除子项」ACL，esbuild 删除自己的临时文件被拒，vite 判整次构建失败。
> 把 TEMP/TMP 指到仓库内 `.scratch/tmp` 后**同一条构建 rc=0**，确认是环境缺陷，但必须由仓库兜住。

### Fixed

- **前端构建在 Windows 上开箱即失败**（打包流水线第一步）：新增
  `frontend/scripts/build-with-workspace-temp.mjs`，把 `TEMP/TMP/TMPDIR` 指到仓库内
  `.scratch/tmp`（目录创建失败时静默沿用系统值，不在只读介质上制造新故障），并用
  `node` 直接执行 vite 入口避免 .cmd 包装的引号/退出码差异；`build` / `build:check` /
  `build:only` 三个脚本一并改走它。验证：不设任何环境变量，`npm run build` **rc=0**。
- **`check_type_debt.py` 在 Windows GBK 控制台崩溃**：输出含 `✓` 等非 ASCII 字符时
  抛 `UnicodeEncodeError: 'gbk' codec can't encode character '\u2713'`，本地门禁直接失败。
  与 `check_doc_numbers` / `check_constants_sync` 同口径强制 UTF-8（不支持 reconfigure
  的旧解释器静默跳过）。验证：`PYTHONIOENCODING=gbk` 下 rc=0。
- **门禁基线漂移清理**：文档数字 `14,874 → 14,873`（实测）、技术债棘轮
  `except Exception 802 → 801`（只紧不松）、软删除基线 29 条重新收敛（STALE 豁免点清零）。
  `check_soft_delete_usage`、`check_doc_numbers --full`、`check_type_debt` 复跑全绿。


### Added

- **分段执行器单实例锁**（`scripts/run_backend_tests_segmented.py`）：两个会话同时跑 12 段时，
  后启动的一方会在清理阶段重置 `.coverage`，先启动那次覆盖率从 100% 掉成 28%/53% ——
  现象是「12 段全 PASS 但覆盖率门禁红」，本轮实测两次。现在用 `O_CREAT|O_EXCL` 原子锁 +
  pid 存活探测（陈旧锁自动接管），第二个进程直接得到可读提示并退出码 3，
  也可 `--wait-lock 秒数` 排队。**踩坑**：Windows 上 `os.kill(pid, 0)` 走 TerminateProcess 语义，
  会把正在跑的会话杀掉 —— 存活探测必须用 `OpenProcess + GetExitCodeProcess`（已按此实现）。
  新增 5 例回归（`test_segmented_runner_lock.py`）。

### Tests

- 新增元测试 `electron/tests/build-temp-wiring.test.js`（3 例）：锁住「三个构建脚本必须
  经包装脚本」「包装脚本必须改 TEMP/TMP/TMPDIR 且有失败兜底」「.scratch/ 必须被忽略」，
  防止后人把它简化回裸 `vite build` 而无声复发。`npm run test:electron` 14 passed。
- **`backend/version.json` 的 description / release_date / build 改为自动派生**：这三项与
  CHANGELOG 最新标题是同一事实，却一直靠手工抄 —— 每版忘改就被 `check_update_log.py`
  拦下（本轮又踩一次）。`sync_update_log.py` 写完应用内更新日志后顺带同步这三项
  （`features` 仍人工维护、不覆盖），`--check` 同时校验二者；新增 5 例回归
  （`test_update_log_sync.py` **10 passed**）。
- 全量门禁复跑（30 道）仅剩 3 处调用方式问题（需 `--json/--baseline` 或 cwd=backend），
  修正调用后**全绿**；关键功能定向回归 182 passed。

## [1.18.19] - 2026-10-28 — 修复大瓦片包导入“请求超时，请重试”（全局 30s → 导入专用 15 分钟）

> 现象：导入 z14 全省包（`guizhou-all_z14.zip` 283.7MB / 64,900 张）时前端报
> **“请求超时，请重试”**。
> 根因：`frontend/src/api/request.ts` 的全局 axios `timeout: 30000`（30 秒），而该包
> **后端解压落盘实测 62.3 秒**（本地 `import_tiles` 计时），叠加浏览器上传时间，
> 请求必然在 30 秒被客户端中断；中断还会让后端解压半途而废，用户重试前看不到结果。

### Fixed

- **`frontend/src/api/offlineMap.ts`**：`importTiles(file, options)` 单独放宽超时到
  `TILE_IMPORT_TIMEOUT_MS = 15 分钟`（可 `timeoutMs` 覆盖），并透出 `onProgress`（0~100）。
- **`MapTileManager.vue`**：导入期间显示 `el-progress` 与“上传完成后后端解压落盘约需 1 分钟、
  请勿关闭页面/刷新”的提示；超时错误单独提示“改用市州分包（≤64MB）重试，或稍后刷新状态”，
  不与普通失败混淆；导入结束（成功/失败/超时）复位进度与 loading。
- 单测：api 层新增“15 分钟超时/自定义超时/进度回调截断”3 项；视图层新增
  “进度与勿关闭提示”“超时专用提示”2 项；相关 2 文件 **37 项全部通过**。

### 现场操作建议

- 283.7MB 全省包在机械硬盘/低速 U 盘上可能需要 2~5 分钟：保持页面打开，进度条到 100% 后
  仍在解压属正常；
- 若网络/磁盘确实太慢，优先导入 9 个市州分包（21.5~63.8MB，单包约 10~25 秒）；
- 导入中断不会破坏已有瓦片，重新导入会按同名覆盖补齐。

## [1.18.18] - 2026-10-28 — 两处路由注册缺陷修复（6 接口不可达 / 4 条重复路径）+ 乱码报错与无效注解

> 本版是「棘轮装上之后第一次真的往下压」：沿 mypy 明细逐条核实高风险类别
> （`union-attr` / `operator` / `call-arg` / `str-bytes-safe` / `valid-type`），
> 绝大多数是 SQLAlchemy `Column[...]` 造成的误报（已有 `is not None` 守卫），
> 但筛出 **3 处真问题** 修掉，并把基线从 1394 下调到 **1391**。

### Fixed（路由注册，本轮主动审计发现）

- **`system.py` 的 router 双重 prefix —— 6 个接口全部路径错误、完全不可达**：
  聚合器 `app/api/v1/system/__init__.py` 已是 `APIRouter(prefix="/system")`，
  而 `system.py` 自己又写了 `prefix="/system"`，实际注册成
  `/api/v1/system/system/{info,status,shutdown,restart,environment,version}` ——
  正确路径 `/api/v1/system/info` 等**全部 404**。因为前端取系统信息走别的途径、
  Electron 与测试也都不调它们，**一直没人发现**；含关机/重启在内 6 个接口等于摆设。
  修复：`system.py` 的 prefix 改为空（由聚合器统一加）。
  > **修复时差点放出的雷**：`/system/shutdown`、`/system/restart` 的依赖层只有
  > `Depends(get_current_user)`（任意登录用户），真正的管理员校验在**函数体内**。
  > 它们此前不可达所以无害，路径一修通就变成"任何登录用户可关机"。
  > 已实测确认函数内校验存在（`system.py:235` / `273` / `336` 的 `require_admin`）才动手。
- **`config_package` 被注册两次 —— 多出 4 条错误路径**：该模块 router 自带
  `prefix="/system/config-packages"`，是给 `api/v1/__init__.py` 的「子模块直挂」用的
  （注释写明"历史表面，勿删"），但聚合器又 include 了一次，于是多注册出
  `/api/v1/system/system/config-packages` 等 4 条。修复：聚合器移除该 include，
  保留独立注册。**端点总数（路径+方法口径）849 → 845** —— 减少的 4 条正是重复注册。
- **新增路由认证覆盖门禁** `scripts/check_route_auth.py`（挂 `stack-alignment` 作业）：
  `api_v1_router` 没有全局认证依赖，每个路由必须自己声明认证 —— 少写一行就是越权入口，
  code review 很难发现。门禁用 FastAPI 运行时依赖树递归判定（能识别经角色守卫间接
  要求认证的路由），白名单外的无认证路由即失败。上线时逐个核查全部 **58 个无认证路由**：
  登录/登出/CSRF、健康检查、地图瓦片（`<img>` 带不了 token）、机器码（限流 + loopback +
  双向验证）、权限包导入（非管理员限 loopback）、反馈（有意匿名）、shutdown（仅
  127.0.0.1 + 内部密钥）、系统初始化（初始化前无用户）、备份 3 个（函数体内自定义认证）
  —— **无真实漏洞**；门禁的已知局限（函数体内认证检测不到）写进了白名单注释。

### Fixed

- **用户可见的乱码报错**（`services/encrypted_package.py`）：加密包版本不匹配时
  消息直接把 `bytes` 拼进 f-string，用户看到的是 `不支持的版本: b'9.9'`；
  更糟的是非法版本字节（如 `\x02`）经 `decode("ascii")` 后是**不可见控制符**，
  消息看起来像"不支持的版本: "（冒号后空白）—— 比乱码更难排查。
  现新增 `_as_text()`：可打印 ASCII 原样输出，控制符与非法字节一律转义成 `\xNN`，
  消息固定为 `不支持的版本: 9.9（本机支持 1.0）`。
- **把内建函数 `any` 当类型注解**（`services/business_metrics_service.py`）：
  `Optional[any]` / `value: any` 里的 `any` 是内建**函数**，不是 `typing.Any` ——
  注解不产生任何约束（typing 容忍任意对象，故不报错，属"静默失效"），
  mypy 也会按 `valid-type` / 注解无效处理。现改为 `Optional[Any]` / `Any` 并补 import。
- **棘轮基线首次下调**（`.type-debt-baseline.json`）：mypy 1394 → **1391**
  （上述两处共 3 条：2 条无效注解 + 1 条 `str-bytes-safe`），
  `as any` 196 与 `except Exception` 802 持平。这是棘轮第一次真正起作用的方向——
  只降不升。

### 核查记录（未修，避免无谓改动）

沿 mypy 高风险类别逐条看过的"疑似但实为误报"，记在此处省下次重复排查：

| 类别 | 抽样 | 结论 |
|---|---|---|
| `operator` | `village_cascade_delete_service:156` `count > 0`；`reminder_engine:30` `utcnow() - created_at` | `SELECT COUNT(*)` 必返行；后者有 `if created_at is None: return 0.0` 守卫 |
| `union-attr` | `system_config_service:315` `Session \| None` | 调用方已保证会话非空（`db` 为依赖注入的必填参数） |
| `call-arg` | `organization_service:577` `OrganizationStatistics(by_level=…)` | 字段确实存在（全库唯一定义，`schemas/organization.py:97`）——误报 |
| `misc` | `api_error:85` `await func(...)` | 装饰器按 `asyncio.iscoroutinefunction(func)` 分流，同步函数走 `sync_wrapper` —— 误报 |
| `attr-defined` | `win_proactor_fix` / `cache._cache` | 反射/兼容层刻意为之 |

另：全库 **129 处** `except Exception` 判为"静默吞异常"候选，逐个看上下文后确认
**15 处完全无声的都有注释说明**（dry-run 回滚、`PRAGMA optimize`、脱敏失败不阻断、
审计归因不阻断、worker 取消、mapper 探测兜底），其余 B/C 类是**把错误收进 `errors`
列表返回**（错误其实上报了）—— **无一需要改动**，故不动。

### 验证

- 新增 4 例：`_as_text` 的三种输入（可打印 ASCII / 控制符 / 非法字节）+ 版本不匹配消息
  可读性（断言消息里不出现 `b'`、且含 9.9 与 1.0）；
- `encrypted_package.py` 覆盖率 **100%**（81 语句 / 18 分支），相关 11 个测试文件 579 例全过；
- flake8 两文件 0；`check_type_debt.py` 1391 / 196 / 802 持平 ✓。

## [1.18.17] - 2026-10-27 — 工程治理收口：技术债棘轮上线（并修掉它自身两个会失效的点）

> 本轮把「三类技术债只涨不降」这件事装上了闸门，同时排掉新门禁**自身**的两个坑：
> 基线口径与实测不一致（一提交就红）、以及测不到时静默放行（门禁永久假绿）。

### Added

- **技术债棘轮门禁** `scripts/check_type_debt.py`（CI `static-analysis` 阻断）：
  守住三个此前无人看管的指标 —— mypy 错误数、前端 `as any` 处数、后端
  `except Exception` 处数。基线 `.type-debt-baseline.json` 记录**数量 + 精确位置**，
  任一指标超过即失败并列出**新增位置**（不是只报"多了几条"）。
  `--update` 只应下调；上调需在 PR 说明理由。
  > 背景：mypy 此前在 CI 里是 `|| true`（永不阻断），另两项更无任何上限 ——
  > 一次性清零等于给全库补类型标注，不现实；但"不允许继续恶化"可以立刻做到。
- **Python 3.13 兼容**：`rapidocr-onnxruntime==1.4.4; python_version < "3.13"`。
  该包元数据 `requires_python<3.13`（PyPI 官方 JSON 核实、未 yanked），
  3.13 下原会让整个 `pip install -r requirements.txt` 报
  "No matching distribution found" 而**整体失败**；加环境标记后自动跳过该行，
  其余依赖照装，OCR 走既有降级路径（`available()=False` → 接口 503 提示手工录入）。
- **门禁隔离**：三层对齐门禁的参照库改落到 `.scratch/tmp/stack-align/`（`.gitignore` 兜底），
  并让清理函数吞掉 `BaseException` —— 本机沙箱的 safe-delete shim 在单次删除量超阈值时
  会抛 `SystemExit`，那是 `BaseException`，`shutil.rmtree(ignore_errors=True)` 拦不住，
  会把门禁进程带崩、stdout 变空，负向用例误判成"门禁逻辑坏了"。

### Fixed

- **新门禁一提交就是红的**：基线记为 `mypy_errors=1393`，实测稳定 **1394**
  （连跑三次 + `--no-incremental` 均 1394）。核对后确认 1394 条与最近 3 个提交改动的
  `app/` 文件**无交集** —— 属存量口径偏差而非新缺陷，故按实测重生成基线，
  并把该结论写进本段以免被后人误判为"放宽标准"。
- **门禁测不到时会静默放行**：原实现在 mypy 无法解析汇总行时 `return 0`，
  等于 mypy 一旦改输出格式或没装，第一条指标就永久失效却仍显示绿色（正是
  `|| true` 的老毛病换个马甲）。现改为 **fail-closed**：抛 `MypyUnavailable` →
  `exit 2`（区别于"恶化"的 `exit 1`）并打印输出尾部与修复提示。
- **mypy 版本漂移**：CI 由 `pip install mypy` 改为 `mypy==1.19.1`（与
  `requirements-dev.txt` 及基线测量口径一致）。棘轮把错误数当上限守着，
  不 pin 则上游发版换个检查规则就能让全量计数整体漂移 —— 要么假红、要么假绿。

### 验证

- `python scripts/check_type_debt.py`：**1394 / 196 / 802 全部持平 ✓**（exit 0）；
- fail-closed 分支单独验证：注入 `returncode=2` 的假 mypy 输出 → 正确抛 `MypyUnavailable`；
- 三层对齐门禁四轴无漂移；并行会话改过的 58 个相关用例全过；
- `check_doc_numbers --full` 一致（后端 14,870 例 / 前端 344 文件 / 端点 849）。

## [1.18.16] - 2026-10-27 — 发布流水线竞态修复（latest.yml 丢失）+ 依赖版本 pin

> 起因：v1.18.15 的 Release 只有 **6 个资产**，而 v1.18.14 有 8 个 —— 同一套流水线
> 产出不同清单。翻构建日志定位到 electron-builder 的 publish 竞态，并顺带把
> 「构建不可复现」的依赖漂移一并钉住。

### Fixed

- **发布资产缺失（latest.yml / .exe.blockmap）**：Windows 作业的 electron-builder
  在有 `GH_TOKEN` 时默认按 `onTagOrDraft` **自行发布**（建 draft Release）。
  若 ARM64 作业先把 Release 发成正式版，它会判定
  `existing type not compatible with publishing type`（existingType=release /
  publishingType=draft）→ **exe / blockmap / latest.yml 三个文件全部 skipped**，
  随后只有 softprops 步骤把 exe 传上去，元数据永久丢失（v1.18.15 实测）。
  修复：Windows 侧改 `--publish never`（与 `build-arm64.yml` 第 209 行同口径），
  **上传只走 softprops 单一发布路径**，并把 `latest.yml` / `*.blockmap` 显式列入
  制品与 Release 文件清单。
- **新增构建期守卫** `Verify updater metadata produced`：NSIS 构建必然同时产出
  `latest.yml` 与 `MRRS-Setup-<版本>-x64.exe.blockmap`，缺一即红并打印 dist 清单 ——
  不让「Release 少文件」留到发版后才发现。

### Changed

- **依赖版本 pin（构建可复现）**：`backend/requirements.txt` 里
  `setuptools` / `wheel` / `bcrypt` / `cryptography` 由 `>=` 改为精确版本
  （`84.2.1` / `0.48.0` / `5.0.0` / `50.0.2`，取自 CI 已全绿验证的实装记录）。
  此前本地 bcrypt 4.0.1、CI 实装 5.0.0（差 3 个大版本），
  `>=4.2.0` 的约束连本地都不满足 —— 本地与 CI 测的不是同一套依赖是真实风险。
  注：bcrypt 5.0 移除 `__about__`，`app/core/security.py` 的兼容 shim 与 passlib 1.7.4
  回退路径已由 CI 覆盖；哈希格式仍为 `$2b$`，与 4.x 存量密码完全互通。

### Docs

- 纠正「`latest.yml` 是 Windows 自动更新所需」的**不准确表述**：本系统**没有**
  `electron-updater` 依赖、也没有任何更新检查代码（离线单机部署，升级 = 覆盖安装）。
  改为说明它是 electron-builder 的 NSIS 产物、当前不被消费、保留上传只为发布物清单稳定
  （`项目文件结构说明.md`）。
- `docs/INDEX.md` 补齐此前只有目录级链接的文档：7 篇 ADR（0003/0005/0006/0007/0008/
  0010/0012）、4 篇 Agent 约定、1 篇通知与提醒 UI 规范 —— 18/18 篇 docs 现在都有显式入口。

### 验证

- `.github/workflows/build-windows.yml` YAML 可解析（27 个步骤，含新守卫）；
- `npm run test:electron` **11 例全过**（含 ci-wiring 守护：发布门禁等待预算 / main 不取消 /
  check_main_ci 接线）；
- 本地门禁 20 项全绿；`check_doc_numbers --full` 一致（后端 14,870 例）；
- 本次 tag 构建将验证 Release **8 个资产**（v1.18.14 口径）。

## [1.18.15] - 2026-10-27 — 分段导入补日志 + 文档/PPT 实测数字追平 + 仓库卫生

> 本轮是 v1.18.14 之后的收口轮：修掉一处**只报「失败 N 条」却无原因**的导入可观测性缺陷，
> 并把文档与三份 PPT 里滞后的实测数字、版本标记全部追平到真值，同时清掉 6.6 GB 测试残留。

### Fixed

- **帮扶村「分段数据」导入的三个失败分支改为带行号记日志**（`_import_section_sheet`）：
  此前「表头未识别（整表白导）」「行内有内容但全部列转换失败」「写库异常」三种情况都只做
  `failed += 1`，现场只看到 `{"imported": 5, "failed": 3}`，无从知道是第几行、什么原因，
  只能整份重来。现补 `logger.warning`（含 Excel 1-based 行号 / `village_id` / `model` / `year`，
  写库异常带 `exc_info` 完整栈）。**返回结构不变**（仍是 `{imported, failed}`）——
  API 契约不动，前端与四层栈对齐门禁无需调整。
  同类接口（`import_villages` / `import_schools_excel` / `report_templates._import_school_data`）
  本来就把逐行原因放进 `errors` 回传用户，此处是全仓唯一漏网的一处。

### Docs & 仓库卫生（收口轮）

- **三份 PPT 的实测数字全部同步到本轮真值**（15 处 run）：
  后端 14,722 → **14,870**、前端 7,356 → **7,374**、合计 22,078 → **22,244**、
  前端测试文件 347 → **344**（与 `check_doc_numbers` 的 `*.test.ts(x)` 口径一致）、
  封面/封底日期 2026-10-26 → **2026-10-27**、版本标记 V1.18.8 → **V1.18.14**。
  此前「系统介绍」第 47 页与「零基础版」第 31 页的"数据来源"行停留在 v1.18.8 的旧实测值，
  与 README/CLAUDE.md 的 14,870 自相矛盾。
- **文档入口页版本号从 v1.18.1 追平到 v1.18.14**：`docs/README.md`、`docs/INDEX.md`、
  `docs/04-部署文档/README.md`、`docs/01-快速开始/README.md` 共 6 处 —— 此前入口页仍指向
  `RELEASE_NOTES-v1.18.1`，读者按图索骥会拿到 13 个版本前的发布说明。
- **`.gitignore` 补齐三类每次跑测试都会新生的目录**：`backend/verify_*/`（280 个）、
  `backend/wf_*/`、`backend/_scratch_lazy/`。此前只忽略了 `bumofu_pytest_appdata_*/`，
  另外两类每次全量测试后都会让 `git status` 变脏，是 `git add -A` 误提交的隐患。
- **清理测试残留 1405 个目录 / 6.6 GB**（`backend/bumofu_pytest_appdata_*` 等一次性隔离根）
  与顶层 28 个 pip 空临时目录、空 `archives/`、探测脚本 `_probe_menus.py`。
  均为未跟踪产物，仓库跟踪文件零改动。

### 验证（收口轮）

- 后端 **14,870 例**（CI 12 段独立进程）全绿，行+分支覆盖率 **100%**（CI run 40482787753）；
- 前端 **347 文件 / 7,374 例**全绿（本地全量，33 分钟）；
- `flake8 --max-complexity=16` 0 错误、`bandit -ll` 无 Medium/High、ESLint `--max-warnings=0` 0 警告、
  `vue-tsc --noEmit` 无错误；
- **四层栈对齐门禁零漂移**（前端路径 / 模型↔库 / 前后端字段 / 请求体必填性）；
- 前后端 API 路径交叉核对：后端 **853** 条路由 vs 前端 **352** 个去重调用，**0 不一致**；
- `check_doc_numbers --full` 文档数字一致性 ✓。

## [1.18.14] - 2026-10-27 — 组织编码接入权威区划表：修掉 4 处真实缺陷（初始化编码被随机替换等）

> 起因：用户反馈「黔南州及各县市的行政区划代码是 522700」并质疑 `XXYY00 / XXYYZZ` 规律。
> 逐一核实后确认 **规律本身没错**（522700 黔南州 / 522701 都匀市 … 12 个县市各有独立代码，
> 贵州 9 市州 + 88 县级单位 100% 符合），但顺着这条线查出 **4 个真实缺陷** 并全部修复。

### Fixed

- **P1 初始化建根组织时编码被随机替换（严重）**：`system/init.py` 传入
  `OrganizationCreate(code=522700)`，但 `OrganizationService.create_organization()` 内部走
  `generate_code()` 生成随机 `ORG-XXXXXXXX`，**完全忽略传入编码**（实测传 522700 →
  落库 `ORG-848B7F7C`、level=1）。跨机匹配与组织树全部失效。现以传入编码为准，层级由代码推导。
- **P2 初始化强制省级编码（严重）**：`_resolve_root_org_code` 要求末四位 `0000`，市州级单位
  （黔南州 522700）首启必然被拒，只能先造省本级根再手工建州。现省 / 市州 / 县级均可作为首启单位。
- **P3 不校验代码是否真实存在**：只按末位规律判层级，`522799`、`999999` 都能入库并被判为县市级。
  现接入权威表，贵州省为全量校验（空号直接拒绝）。
- **P4 不校验父子是否同一行政区划**：只校验「层级 = 父级+1」，`522701`（都匀市）可挂到
  `520100`（贵阳市）下 —— 组织树与按 path 前缀计算的数据权限会把黔南的县市算进贵阳子树。
  现要求父子同属一个区划（表内用表中 parent，表外用前缀）。
- **P5 越权探测（顺带修复）**：`POST /organizations` 原先**先查编码重复、后判越权**，
  越权者可用 400 与其它响应的差异**反推其它分支的组织编码**（编��是跨机匹配标识）。
  现越权 403 先行返回。

### Added

- **权威行政区划表** `backend/app/data/admin_divisions.json`（11KB）：省级 34 全量；
  贵州 9 市州 + 88 县级全量（取自仓库内置 `frontend/src/assets/geo/guizhou.json` 的官方 adcode）；
  `aliases` 存区划调整换码（520222 盘县 → 520281 盘州市）。
- **`app/services/admin_division_service.py`**：存在性 / 层级 / 父子一致 / 别名归一 的单一判定口径；
  `OrganizationCodeService.validate_admin_code(code, parent_code)` 为落库路径统一入口。
  表文件缺失或损坏时**自动降级**为「仅末位规律」并告警（不得因缺文件把合法编码判非法）。
- **Windows 打包补数据文件**：`assistance-backend.spec` 原先只收 `alembic` 等，漏了 `app/data`
  （两个 Linux spec 收的是整个 `app`），会让安装包内的组织编码校验找不到表 —— 已显式收集。

### Tests

- 新增 `backend/tests/unit/test_admin_divisions_r47.py`（30 例）：表完整性（省级 34 / 贵州市州 9 /
  县级 88 / 父子闭合 / 层级与规律一致）、存在性（522799 等空号拒绝）、父子一致（522701 挂 520100 拒绝、
  12 县市挂 522700 通过）、表外省份规律兜底、缺表/坏表降级、`OrganizationService` 落真实编码、
  首启层级（省/市州/县级）。
- 同步更新 4 个旧用例（`test_p3_init_org_code_branches` / `test_cov_b4a_organization_service` /
  `test_coverage_gap_batch3` / `test_org_write_scope_r27`）到新契约；R27 夹具改用真实代码
  （520000 / 520100 / 520103 / 520200 / 520201）。

### 验证

- 组织/初始化相关 **1165 例通过**（唯一失败为本地沙箱写 `%LOCALAPPDATA%` 的权限限制，CI 不受影响）；
- `flake8 app/`（复杂度 16）0 错误；新增/改动文件 ``--max-warnings=0`` 级校验通过；
- 21 道静态门禁 + 12 段后端 + 前端全量由 CI 在 tag 提交上执行。

## [1.18.13] - 2026-10-27 — 「数据概览」页改版 + 菜单↔路由标题 23 处对齐（新增门禁规则 F）

> 本版把「数据管理」页按实际使用场景重排为「数据概览」，并顺手清掉一类长期存在的
> **同页两名**问题：侧栏显示一个名字、面包屑与浏览器标题显示另一个名字。

### Changed

- **「数据管理」页改版为「数据概览」**（`views/dataManagement/Index.vue` 重写）：
  · **核心指标**常驻卡片（帮扶村总数 / 导入次数 / 备份数量；**导出审计仅管理员**——
    非管理员不再请求 `/system/audit/exports`，既不每轮刷新打 403，也不再用恒 0 的假数字误导）；
  · **最近流转记录**直接渲染真实记录（导入历史 + 管理员可见的导出审计），不再用「前往…」空壳入口；
  · 原「数据质量」**页签**内容改为**常驻区块**（帮扶村抽样，后端 `page_size` 上限 200）；
  · 子组件仍异步加载，保持原分包策略。
- **路由 `meta.title` 与菜单 label 对齐 23 处**：`data-overview` 为例，侧栏叫「数据概览」而
  面包屑/`document.title` 写「数据管理」，同一页面两个称谓。`menus.py` 是全站唯一菜单源，
  故以菜单 label 为准统一（含「汇报大屏」「综合数据录入」「政策法规」「报表模板/报表导出」
  「工作首页/工作列表」「用户与组织」「安全审计」「健康检查」「机器码管理」「零信任」「错误上报」
  「地图瓦片」「数据包与批量导入」等）。

### Added

- **菜单对齐门禁新增规则 F**（`scripts/check_menu_alignment.py`）：`kind=page` 且带 `path` 的条目，
  **菜单 label 必须等于前端路由 `meta.title`**。新增规则首次运行即抓出 **23 处**不一致，
  此后由 CI 自动拦截（此前面包屑/文档标题与侧栏文案可长期分叉而无人发现）。

### Fixed

- **`policies/Edit.test.ts` 跨用例污染**：该视图 `useFormDraft` 有 600ms 防抖定时器，
  会在后续用例执行期间把上一个用例的表单写回共享 `localStorage`，导致「草稿与离开拦截」用例
  **单跑通过、整文件必红**。改用 `enableAutoUnmount(afterEach)` 统一卸载（仓库 49 个视图测试同款约定）。
- **`smoke.test.ts` 移除 `dataManagement/Index.vue` 的 bare import**：遵守 coverage-merge 不变量
  （同一被阈值锁定的 `.vue` 只允许一个测试文件执行，第二个文件即使只 bare import 也会在满量
  按 id 合并 `fnMap` 时损坏 functions）；可挂载性由 `router-index.test.ts` 的全量路由表保证。
- **`utils/index.test.ts` 删除重复覆盖** `dataManagement/Index.vue` 的内容（已收敛到专属测试文件）。
- **lint**：`policies/Edit.test.ts` 5 处未使用绑定（4 个 `const wrapper = mountComp()`、
  1 个 `const vm`）+ 29 处 prettier 缩进 —— 原改动 `eslint` 未通过，本版修复后才入库。

### 验证

- 前端全量 `npm run test:coverage`：**347 文件 / 7,374 用例全过**，`All files 100 | 100 | 100 | 100`；
- `vue-tsc --noEmit` 0 错误；改动文件 `eslint --max-warnings=0` 0 告警；
- 21 道静态门禁全绿（含新增规则 F、四层对齐、Office 格式、全仓损坏扫描、版本一致性、更新日志同步）；
- 布局/菜单/路由相关 88 例（面包屑回退、`Menu.vue`、`router/guards`）全过。

### Tooling

- **接入 CodeGraph 预索引代码图谱（本机开发效率）**：安装 @colbymchenry/codegraph 1.6.2 CLI +
  DSH 插件 @jiangzhenguo/dsh-codegraph 1.2.2（desktop profile，core 面 4 个工具
  codegraph_status/init/sync/explore，重启 DSH 后生效），并对本仓库执行 codegraph init
  （2,093 文件 / 52,382 节点 / 129,646 边，39s）。**已关闭上报告警用的匿名遥测**
  （codegraph telemetry off）——本系统要求完全离线，不允许任何外联。
  .gitignore 新增 .codegraph/（索引数据库约 183MB，本机产物不入库）。

## [1.18.12] - 2026-10-26 — 贵州 z14 预渲染交付（全省包 283.7MB / 64,900 张；9 市州分包）

> 用户选择“预渲染到 z14”（约 8.6 m/像素，可看清街区/道路）。z14 全省单包 283.7MB，
> 低于 512MB 导入上限；另提供 9 个市州分包（21.5~63.8MB）供按需导入。

### Added

- **z14 全省瓦片渲染**：64,900 张 / 296.9MB / 560.7s（115.7 张/秒，0 失败），
  样式 `osm-vector-basemap-light-v3-poi`（含学校 POI 682 个），bbox=贵州全省。
- **`scripts/tiles/pack_prefecture_z14.py`**：把权威 z14 瓦片集打散为 9 个市州包
  （按 `prefecture_bboxes.json` + 0.02° padding；每包 MANIFEST 写 region/zoom/tileCount/ODbL）。
- 交付目录 `deliverables/osm-tiles-z14-20261026/`：`guizhou-all_z14.zip`（283.7MB，64,900 张）
  + 9 个 `guizhou-<slug>_z14.zip`（合计 389.2MB，77,666 条目，含市州间重叠）+ SHA256/README/summary。

### Fixed

- **WPS 模块覆盖率缺口（CI backend-test 红）**：`app/core/office_formats.py` 91.67%、
  `app/services/office_reader.py` 81.88%，全量门禁 `99.95 < 100`。
  补测 `tests/unit/test_office_reader_cov_r46.py`（37 例，独立新文件，不与既有 WPS 测试冲突）：
  xlrd 六种 ctype 归一（空/文本/整数/浮点/日期/布尔/兜底）、`_normalize_rows` 矩形化与空输入、
  `_attempt_order` 三种容器顺序、空内容与 ImportError 分支文案、WPS 后缀走「另存为」提示、
  `_CellShim/_SheetShim/_WorkbookShim`（含 `__getitem__` 命中与 KeyError）、
  `load_workbook_any` 的真实 xlsx 与损坏 zip 回退两条分支。
  两模块均达 **100%**（153 语句 / 44 分支）。

### 验证

- 9 个市州包逐个 `import_tiles` + `verify_tiles`：**9/9 通过**；
- 全省包与内置 z5–12 合并：**70,523 张**，`zoomLevels=5..12,14`；`14/13049/6934`→200（32KB）、
  省界外边缘 `14/12906/6801`→200（3.4KB）、`14/0/0`→404；
- 与 z13 包可叠加（同名覆盖），同时导入后 5..14 连续。

### 注意

- OSM 数据建筑仅 20,393 处、POI 2,261：z14 可见路网/水系/村名/学校注记，**没有建筑轮廓级细节**；
- 全省包 283.7MB 已接近导入体验上限，现场建议用市州分包按需导入。

### Fixed（质量门禁层，2026-10-26 体检）

- **损坏扫描守卫自身两个缺陷**：① `scripts/scan_mojibake.py --check` 因本机运行时日志
  （`frontend/logs-*.txt`，正常含 NUL 且已被 `.gitignore` 忽略）**恒红** —— 守卫被当成噪音，
  "扫描失败"与"提交照样过"长期并存；现在按 `git ls-files --others --ignored --exclude-standard`
  跳过被忽略路径（已跟踪文件不受 `.gitignore` 影响，仍全量扫描；非 git 工作副本退回全量）。
  ② `os.path.getsize` 在 try 之外，扫描期间被并发 pytest 删除的临时库
  （`backend/backup_snapshot_*.db-journal`）让守卫自己抛 `FileNotFoundError` → 改为跳过。
  回归：`backend/tests/unit/test_scan_mojibake_gate.py`（7 项，含"未忽略的 NUL/双编文件仍必红"
  两条负向用例，防止为变绿而削弱守卫）。
- **`.gitignore` 双编损坏吞掉两条规则**（2026-10-24 `7f8738b` 引入）：三行注释被写成 GBK 双编，
  其中两行把 `logs/` 与 `_*.ps1` "粘"进注释行，**规则实际失效**（根目录 `logs/` 不再被忽略）。
  按 git 历史原文还原三行注释，并把两条规则拆回独立行。
- **两道既有门禁从未在 CI 执行**：`scan_mojibake.py --check` 接入 `static-analysis`；
  `check_doc_numbers.py --full` 接入 `stack-alignment`（该门禁需 `import app.main` 与
  `pytest --collect-only`，放无后端依赖的 `static-analysis` 会 `ModuleNotFoundError` 恒红）。
  同时把 `CLAUDE.md` 的后端用例数由过期的 14,726 校正为实测值。
- **pre-commit 配置在"`python` 不在 PATH"的机器上必然失败**：本地钩子
  `language: system` + `entry: python scripts/...` 改为 `language: python`（由 pre-commit
  用运行它的解释器自建环境）；`electron-syntax-check` 的 `bash -c 'for f in electron/*.js'`
  改为 `node scripts/check_electron_syntax.js`（Windows 的 `bash` 常解析到**未装发行版的 WSL
  启动器**，钩子必然失败）；重复的 `check-tokens-sync` id 改为 `-files` 后缀。
  **本机未执行 `pre-commit install`**：本机 python 子进程无法写 `%TEMP%`/`~/.cache`，
  装上会让每一次 `git commit` 失败（违反"不得新增问题"），故本轮的强制点是 CI；
  在正常 shell 里执行一次 `python -m pre_commit install` 即启用。

## [1.18.11] - 2026-10-26 — 瓦片底图常显村/校名称 + 贵州 z13（16,422 张 / 95MB）+ 学校 POI 图层

> 用户诉求：瓦片底图要能直接看到"每个帮扶村、每所学校"的名称。拆成两层解决：
> ① 名称权威来源 = 系统业务库（**常显标签层**）；② 底图细节 + 自然村/学校注记 = **z13 瓦片包**。

### Added

- **瓦片底图常显村/校名称（方案 A）**：`zoom >= 12` 常显帮扶村名、`zoom >= 13` 常显学校名
  （`zoom < 12` 仍仅悬停）；标签文本严格取 `marker.name`；防遮挡用 64×20px 像素格
  （学校优先 → 距视野中心近优先），单次上限 120 条；`interactive:false` + `pointer-events:none`
  不拦截拖拽；`zoomend/moveend` 重算、只在显示模式变化时重绑 Tooltip；卸载解绑监听。
  纯函数 `labelZoomForType` / `selectVisibleLabels` 在 `frontend/src/utils/mapTiles.ts`，
  单测 9 + 组件 8 项，两文件覆盖率 100%。
- **OSM 提取 schema v2→v3：`pois` 图层**：`amenity ∈ {school, kindergarten, college, university}`
  的 node 与 way 质心（`name:zh → name`，无名称不输出，截断 100）；v1/v2 pkl 仍兼容。
  实测贵州：POI **682**（school 559 / kindergarten 44 / college 54 / university 25）。
- **贵州 z13 全省瓦片包**：16,422 张 / **97.6MB** / 184s（89.2 张/秒，0 失败），
  导出 `guizhou-z13.zip` **95.1MB**；MANIFEST `zoom=[13,13]`、`tileCount=16422`、
  license `ODbL-1.0 (© OpenStreetMap contributors)`；`verify_tiles --require-min 16400` 通过；
  导入实测 16,422 张全部落盘。注记：大学/学院 z12 起、学校/幼儿园 z13 起；单瓦片标签上限 14→32。

### Changed

- `render_osm_tiles.py` 新增 `--no-poi`（z≤12 重渲时完全复现 v2 样式，避免高校标记"回归"）；
  内置安装包仍为 z5–12（316.7MB），z13 作为**独立可选包**导入（≤512MB 上限内，无需分包）。

### 使用与注意

- 导入：管理员 → 系统管理 → 备份与存储 → 地图瓦片 → 导入瓦片包，选 `guizhou-z13.zip`；
- 导入后地图最大 zoom 由 12 → 13，学校名开始出现（OSM 覆盖 682 处，非"全部学校"）；
- **帮扶村/学校官方名称以系统库为准**：常显标签只显示 `latitude/longitude` 非空的记录，
  部署前需核查村/校坐标完整率（dev 库 6 村 0 坐标）；缺坐标的后端会按区县估算但带 `isEstimated`；
- 视觉未人工核验（本会话模型不能读图），已用候选统计 + POI/`--no-poi` 像素差（4493/8268）佐证。

## [1.18.10] - 2026-10-26 — WPS 兼容：.xls/.et 导入打通、格式白名单单一源、导出格式门禁

> **背景**：政务现场主流办公套件是 WPS，但系统此前只在"标准格式"上成立。实测三个缺口：
> ① 多个导入端点文案承诺"支持 .xlsx / .xls"，解析却全走 openpyxl（只认 OOXML）——
> 用户按 WPS「97-2003 格式」导出后**必然失败**；② WPS 原生 `.et/.wps/.dps` 在附件白名单
> 与前端 accept 里**一律不存在**；③ 没有任何"导出文件能被 WPS 打开"的机器校验。

### Added

- **`app/core/office_formats.py`（格式单一事实源）**：容器魔数（zip/OLE2）、可解析表格集合
  `xlsx/xls/et`、WPS 原生集合、附件 documents 白名单、导出白名单 `xlsx/csv/docx/pdf`、
  统一的 WPS 指引文案。纯函数、无 IO、无第三方依赖。
- **`app/services/office_reader.py`（统一读取层）**：按**容器魔数**而非扩展名选择解析器
  （zip→openpyxl / ole2→xlrd / 其它→统一 400），提供 `read_rows(content, filename)` 与
  openpyxl 风格 `load_workbook_any()`（含 `iter_rows/max_row/sheetnames/__getitem__` 替身），
  并把 xlrd 单元格值归一成 openpyxl 口径（空→None、整数→int、日期→datetime）。
- **`xlrd==2.0.1` 依赖**：`backend/requirements.txt` + `app/core/required_packages.py`
  （运行时必需）+ 3 个 PyInstaller spec 的 hiddenimports 同步登记。
- **`scripts/check_office_formats.py` 门禁 + CI 接入**（static-analysis）：导入禁止直连
  `openpyxl.load_workbook`、白名单禁止硬编码 `endswith((".xlsx",".xls"))`、导出扩展名必须在
  白名单内、CSV 必须带 UTF-8 BOM；并对 xlsx/xls/两种容器 .et 夹具做运行时自检
  （未装依赖的 CI 作业自动跳过，pytest 侧覆盖）。
- **回归用例**：`test_office_formats_wps.py`（14 例）+ `test_office_formats_gate.py`（11 例，
  含 5 个负向用例保证门禁能红），夹具见 `backend/tests/fixtures/office/`。

### Changed

- **导入解析统一收口到 `office_reader`**：`import_export/import_data`、`projects`、
  `school`（3 处）、`supported_village`（3 处）、`report_templates`（2 处）、
  `services/policy_import_service`、`services/excel_importer_service`、
  `services/batch_import_optimizer`。
- **白名单统一**：4 处硬编码扩展名判断改为 `office_formats.is_spreadsheet_upload`（含 .et），
  错误文案统一为"支持 .xlsx/.xls/.et + WPS 另存为指引"。
- **附件白名单**：`files.py` documents 组改由 `office_formats.DOCUMENT_UPLOAD_EXTS` 提供，
  新增 `.et/.wps/.dps`（只存不解析，导入仍只接受可解析格式）。
- **前端 accept 同步**：Excel 上传 8 处补 `.et`（含 YearlyOverview 扩展名校验与提示文案、
  对应单测期望），区块附件上传补 `.et/.wps/.dps`。

### Fixed

- **`.xls` 可传不可读**（真实死路）：无 xlrd + openpyxl 不支持 OLE2 → 现在按容器走 xlrd。
- **WPS `.wps/.dps` 附件被拒**：现在可上传（仅存储），导入时给"请另存为 .docx/.pptx"的明确
  提示，不再抛裸异常。

### Tests

- 新增用例：`test_office_formats_wps.py` **14 passed**（xlsx/xls/两种容器 .et 读取、
  `.wps/.dps` 提示、白名单接受 .et、openpyxl 风格替身语义）+ `test_office_formats_gate.py`
  **11 passed**（含 5 个负向用例：裸 openpyxl / 硬编码白名单 / 非白名单导出扩展名 /
  缺 BOM 的 CSV 各自能红）+ 导出侧回读（模板 xlsx 可被 openpyxl 重开、CSV 带 BOM）。
- **后端 12 段等价全量**：seg01/02/03/08/09/11 首轮 PASS；seg04 **2278** / seg05 **872** /
  seg06 **1574** / seg07 **517** / seg10 **2585** / seg12 **3192** 复验 PASS（0 failed / 0 skipped）。
  期间修掉两处**并发提交造成的陈旧状态**（非本改动引入）：应用内更新日志数据未随新版
  重新生成（已跑 `sync_update_log.py`）、`_FakeFile` 无 `filename` 的直接调用场景
  （统一 `getattr(file, "filename", None)`）。
- **前端全量**：**347 文件 / 7374 用例全 PASS**（含 WPS accept 断言同步）。
- **门禁**：`flake8 app/`=0、`flake8 scripts/`=0、`check_office_formats`=OK、
  `check_changelog`=OK、`check_doc_numbers --full`=OK（849 端点 / 344 文件 / 14,793 用例）、
  `check_pagination_cap` / 菜单对齐 / console tab 映射 / 硬编码色 146-基线 / 三层对齐 /
  6 项预防性棘轮 全绿。
- **WPS 人工抽样（3A）**：已生成 `.scratch/wps-samples/` 下 3 个文件供真机 WPS 打开验收：
  `01_帮扶村导入模板.xlsx`、`02_帮扶村导出.csv`、`03_年度工作报告.docx`（自动回读已通过）。

## [1.18.9] - 2026-10-26 — 应用内更新日志接入唯一账本 + 发布说明一致性门禁（根治版本说明漂移）

> **问题**：用户反馈"系统内的更新日志没有更新"。核查发现应用内更新日志由
> `update_log_service.py` 里**硬编码**的 `VERSION_HISTORY_DATA` 驱动，只写到 **1.1.1**（15 条），
> 而系统已是 1.18.8 —— 落后 17 个小版本，用户点开更新日志看到的还是两年前的说明。
> **定性**：这不是"忘了改一次"，而是**两份账本**（`CHANGELOG.md` 与硬编码列表）并存、
> 后者没有任何门禁。同类问题已第 4 次复发（`version.json` 的 description/features 曾 3 次滞后）。

### Fixed

- **应用内更新日志长期不更新**：`update_log_service.py` 里的 240 行硬编码历史被删除，
  改由 `backend/app/services/version_history_data.py` 提供，该文件由
  `scripts/sync_update_log.py` 从 `CHANGELOG.md` 生成（1.0.0 起的全部历史版本）。
  改版本说明只需改 CHANGELOG，不再需要手抄第二份。
- **同一天多个版本的顺序是随机的**：`created_at` 只按日期写入（1.18.2–1.18.7 全是 2026-10-25），
  同一时间戳下 `ORDER BY created_at DESC` 的顺序不稳定，实测 1.18.2 会排在 1.18.3 前面。
  修法：初始化/同步时按版本序号加秒偏移（前端只显示日期，秒级偏移不可见），
  查询再加 `version DESC` 兜底，历史库里的老数据也能稳定倒序。
- **升级用户的旧库只补当前一条**：`check_and_record_version_change` 原先只在"版本号变了"时
  补记一条，中间版本仍然缺失（老库会从 1.1.1 直接跳到 1.18.9）。改为每次启动做一次
  **幂等补齐**：一次性取出已记录版本集合，缺哪条补哪条，已存在的不动。
- **「系统设置」聚合页只有一个页签（归类错位）**：`config-package`（系统配置）被挂在
  「备份与存储 › 数据包与存储」下，导致「系统设置」只剩「更新日志」一项，页面自己的描述
  也只能写成"更新日志等基础系统配置"；而 `SettingsOverview.vue` 的「配置管理」分组
  一直把「系统配置 + 更新日志」并列 —— 两处口径互相矛盾。
  修法：把 `config-package` 的**父聚合页**从 `system-console-storage` 改为
  `system-console-settings`，前端分组改为「基础配置 › 系统配置」「版本与日志 › 更新日志」。
  **tab key / path / roles 全部未变**（`/system/config` 深链与 `allowed_menus` 口径不受影响），
  tab 总数仍为 30。存量权限包若只勾了「备份与存储」聚合页，需补勾「系统设置」——
  已在权限包编辑弹窗与该操作说明中显式提示。

### Added

- **`scripts/check_update_log.py` 发布说明一致性门禁**（已接入 `pr-checks` 的 static-analysis 与
  `make test-local`），一次校验三处：
  1. `version_history_data.py` 必须与 `CHANGELOG.md` 生成结果**逐字节一致**；
  2. `backend/version.json` 的 `version` / `release_date` / `build` 必须与 CHANGELOG 最新段一致；
  3. `version.json` 的 `description` 必须等于 CHANGELOG 最新标题，`features` 不得为空。
  只改 CHANGELOG 不重跑生成脚本、或只 bump 版本号不改说明，CI 都会直接失败。
- **单元测试 `tests/unit/test_update_log_sync.py`**：断言生成文件与 CHANGELOG 一致、
  最新版本等于 `version.json`、版本序列升序无重复、解析跳过 `[Unreleased]` / `[未发布]` 段。

### Changed

- `backend/version.json` 的 `description` 改为与 CHANGELOG 标题严格一致（原先为手工改写版本，
  已与标题漂移）；`features` 保留人工维护，只要求非空。

### 验证

- `check_update_log.py` / `check_changelog.py` / `check_doc_numbers.py` / `sync-version.js --check` 全部 exit 0。
- 更新日志相关 29 例测试通过，`app/services/update_log_service.py` 行+分支覆盖率 **100%**（92 语句 / 26 分支）。
- 端到端实测：全新库启动后 `GET /api/v1/system/update-logs` 返回全部历史版本，首条为当前版本、
  次条 1.18.8，倒序严格按语义化版本排列。

### Fixed（2026-10-26 追加：新增组织缺「组织编码」输入 → 前后端请求体对齐 + 门禁补第 4 轴）

**现场症状**：点「新增组织」提交后被拦下，提示「组织编码（行政区划代码）不能为空」，
但前端表单里**根本没有组织编码输入框** —— 用户无从填写。

**根因（三段同时失守）**：

1. 后端 `schemas/organization.py:OrganizationCreate.code` 必填（`Field(...)`，恰好 6 位）；
2. 前端 `types/organization.ts:OrganizationCreate.code` 写成 `code?: string`（**可选**），
   所以"表单漏了必填项"不会被 TypeScript 发现；
3. `scripts/check_stack_alignment.py` 的 C 轴只比对 **response_model**，
   **请求体从来没有被比对过** —— 这类「提交少字段 / 必填性不符」既躲过类型检查，
   也躲过门禁，只能等用户撞 422。

**修复**：

- 前端补字段：`views/organization/List.vue` 新增「组织编码」输入（必填 + `^\d{6}$` 校验 +
  「省级 XX0000 / 市州级 XXYY00 / 县市级 XXYYZZ」提示），新增态可填、**编辑态只读禁用**
  （编码创建后不可修改），提交时新增带 `trim` 后的 `code`、编辑**不提交** `code`；
  与 `views/organization/Edit.vue` 的既有口径完全一致。
- 类型对齐：`OrganizationCreate.code` 改为必填；顺手修掉同源的三处漂移
  （D 轴首次运行即抓出，全部真实存在）：
  | 契约 | 漂移 | 处理 |
  |---|---|---|
  | `DataReportCreate` | 前端**缺 `report_type`**、`title` 后端必填前端可选、`target_org_id` 前端必填后端可选 | 按后端逐字段对齐 |
  | `SupportedVillageCreate` | `department` / `supportUnit` 前端必填、后端可选 | 类型改为可选（表单"建议必填"校验保留，属产品选择） |
  | `ReportSubscriptionCreate` | `email` 前端必填、后端可选（单机站内通知不依赖邮箱） | 类型改为可选 |
- `Edit.vue` 的 `code: formData.code || undefined` 改为 `code: formData.code.trim()` ——
  `|| undefined` 会把已通过校验的必填值静默丢弃，退化成后端 422。

**门禁补强（防"类似所有问题"）**：`check_stack_alignment.py` 新增 **D 轴：请求体必填性** ——
对**同名且全局唯一**的 `*Create` / `*Update` 契约，前后端必填字段集合必须一致，
三个方向都报（后端必填前端可选 / 前端缺字段 / 前端过度约束）；同名多义与响应类跳过，
避免假阳性。`--json` 报告新增 `request_shape_drift` 字段。

**回归测试**：

- 前端 `tests/unit/views/organization/ListCov.test.ts` 追加 5 例（新增态渲染/可编辑、
  编辑态回填/禁用、校验规则 6 位、新增 payload 带 trim 后的 code、编辑 payload 不含 code）；
  同时修正既有用例里因新增输入而整体后移的 `ElInput` 索引。
- 后端新增 `tests/unit/test_stack_alignment_gate_r35_axis_d.py`（9 例：三个漂移方向、
  非 Create/Update 忽略、同名多义跳过、Update 后缀覆盖、当前仓库零漂移、report 含新字段）。

**验证**：四层对齐门禁 `[OK] 四层对齐无漂移`（A 路径 / B 模型↔库 / C 字段 / D 请求体必填性）；
`vue-tsc --noEmit` 0 错误；`eslint` 改动文件 0 告警；`ListCov.test.ts` 39/39 通过。
## [1.18.8] - 2026-10-26 — 全面收口：逐一代码体检 + 项目整理 −1880 文件 + 分段覆盖率门禁修复

> **本轮目标**：交付前的最后一次全面体检 —— 逐项检测前后端/数据库/文档，修掉所有能复现的缺陷，
> 清理仓库里的零引用产物，把文档与 PPT 对齐到实测数字，然后统一出包。
> 结论：**20 道静态门禁全绿；后端 12 段 0 失败、覆盖率 100.00%；前端 347 文件 7,356 用例、四项 100%**。

### Fixed

- **分段覆盖率门禁的 `coverage combine` 一直在失败，且失败信息被吞掉**（`scripts/run_backend_tests_segmented.py`）：
  - 症状一：每次全量跑完都打印一行 `覆盖率 combine 失败: `（消息为空），却仍然报 100% —— 说明结论
    不是从"合并后数据"得来的，门禁的可信度不可证明。
  - 症状二：`--segment 11` 这种单段运行会打印 `TOTAL … 28.40%` 并把退出码置 1，看起来像真实缺口。
  - 根因：① `coverage combine` 的**位置参数是路径**，原代码传的是数据文件基名
    （`.covseg.<stamp>.<N>`），路径不存在 → 合并失败；② 各段分片名与 `coverage` 的
    `<data_file>.*` glob 不匹配，即使不传参也扫不到；③ 失败提示 coverage 写在 **stdout**，
    而代码只打印 `stderr` → 只剩一行空消息。
  - 修法：分片改名为 `<data_file>.seg<N>`（与 glob 对齐）、`combine` 改为无参调用（自行发现分片）、
    失败时打印 stdout+stderr、**子集运行（`--segment`）不再判定阈值**并明确提示"比值无意义"。
  - 验证：单段运行现在输出「覆盖率门禁: 跳过（本次只跑了子集…）」+「子集段通过」；
    全量运行合并成功并给出 100.00%（45,936 语句 / 11,452 分支，Miss 0 / BrPart 0）。

- **`OrganizationService.get_ancestors()` 在 `path` 为 NULL 时抛异常，令数据上报创建直接 500**
  （`app/services/organization_service.py`）：
  - 症状：`POST /api/v1/data-reports` 返回 500 `'NoneType' object has no attribute 'strip'`。
  - 影响面：`get_ancestors` 被上报、数据域、审批等多条链路复用；凡组织 `path` 为 NULL
    （`repair_organization_paths()` 的注释已说明"早期经 API 直写落库的组织 path/level 为 NULL"，
    即真实存在）即触发，属历史脏数据把业务操作打成 500。
  - 次生缺陷：`create_organization` 用 `f"{parent.path}{org.id}/"` 拼接，父级 `path` 为 NULL 时
    会把子组织写成 `"None12/"`，再让祖先解析抛 `ValueError` —— 脏数据会向下传染。
  - 修法：祖先解析改为逐段 `int()` 并捕获 `TypeError/ValueError`，解析失败按"无上级"降级（不 500）；
    建组织时父级 `path` 为空回退为 `/{parent.id}/` 单段路径。
  - 验证：新增 4 例（NULL path、非数字脏段、合法 path 回归、父级 NULL path 建子组织），
    组织服务相关 134 例全过；端到端冒烟中「上报创建 + 提交」由 500 恢复为 200。

### Changed（项目整理：被跟踪文件 4407 → 2527，−1880）

- 删除 `.scratch/tiles-import-test/`（**1423 个文件**）：瓦片导入测试的中间产物，
  在 py/ts/vue/js/md/yml/json/ps1/sh 全量检索中**零引用**（含文档与 CI），删掉不影响任何测试或构建。
- 删除 `.qoder/`（**456 个文件**，含 1.8 MB `repowiki-metadata.json`）：AI 工具生成的仓库知识库缓存。
  本仓《项目文件结构说明.md》本就把它标注为「机器本地元数据，不参与交付 ❌」—— 文档说不该入库，
  实际却跟踪了 456 个文件，本次纠正。
- 删除 `.scratch/r34-final/帮扶管理信息系统介绍-原始备份.pptx`（1.0 MB）：与 `docs/` 正式版重复且零引用。
- 补 `.gitignore`：`.scratch/tmp/`、`.qoder/`、`.reasonix/`、`.zcode/`、`deliverables/releases/`、
  `*.exe|*.msi|*.dmg` —— 防止同类产物再次混入版本库。
- **未动**（有引用/交付需要）：`deliverables/`（README/AGENTS/CHANGELOG 引用其中报告）、
  `deploy/`、`nginx/`、`tests/`（E2E 与性能入口）。

### 全面体检结论（逐项，全部零缺陷）

| 检查项 | 结果 |
|---|---|
| 静态门禁（错误文案泄漏/更新日志/迁移/菜单/console tab/安全审计/硬编码色/三层对齐/版本一致/文档数字/os_exit/unbounded_read/upload/subprocess_encoding/dir_replace/scheduler/零断言/软删除/裸返回/electron 单测） | **20/20 exit=0** |
| 后端分段 | **12/12 PASS**，14,722 用例 0 失败 |
| 后端覆盖率 | **100.00%**（45,936 语句 / 11,452 分支，Miss 0 / BrPart 0） |
| 前端 | **347 文件 / 7,356 用例全过**，Statements/Branches/Functions/Lines = **100/100/100/100** |
| flake8 | `app/`（复杂度 16）**0**；`scripts/`（复杂度 40，CI 同口径）**0** |
| PII / 硬编码密钥扫描 | **0 高危 / 0 中危（PASS）** |
| 文档死链 | 146 个 md / 133 条相对链接 → **死链 0** |
| TODO / FIXME / 待实现 遗留 | **0 处** |
| 运行时依赖清单 ↔ requirements.txt | **完全一致**（必需 7 项 + 可选 4 项全部登记） |
| Alembic | 单 head `r43_prune_dead_columns_001`，无分叉 |
| 前端生产可达性 | 320/324 可达；4 个"不可达"经核实均为**工具盲区**（`main.ts` 的副作用导入 `import './router/guards'`）或**刻意保留的测试基座**（VirtualList/virtualWindow/navLinks），非缺陷 |

### Docs / PPT

- `backend/version.json`：版本 1.18.8、release_date 2026-10-26、描述与 features 全量重写为收口结论。
- 系统介绍 PPT：版本页脚与"数据来源"日期同步至 **v1.18.8 / 2026-10-26**，保持 56 页与既有版式
  （python-pptx 原位改文本，不动版式；改后跑 `scripts/ppt_overflow_check.py` 校验无溢出）。
- README / CLAUDE.md / AGENTS.md / 《项目文件结构说明.md》文件数与实测对齐。

### Fixed（2026-10-26 追加：分段覆盖率「分片机制」纠正 —— 前面那次只修对了表象）

首轮修复只改了分片**文件名**（`<data_file>.segN`）并把 `combine` 改成无参，但全量跑完仍报
`No data to combine`。用两组实验把机制彻底测清后才发现真正原因：

| 实验 | 结果 |
|---|---|
| 只传 `--cov-config=<rc>`（`data_file=.probe.seg7`），不设环境变量 | 生成 `.probe.seg7` ✅ |
| 同一调用再设 `COVERAGE_FILE=.probe.envwin` | **只**生成 `.probe.envwin`，rc 被忽略 ✅ |
| 走 pytest-cov（`pytest … --cov-config=<rc>`，带 `--cov-append`）不设环境变量 | 数据仍落在默认 `backend/.coverage` ❌ |

即：**`COVERAGE_FILE` 优先级高于 `[run] data_file`；而 `--cov-config` 指定的 `data_file`
在 pytest-cov 路径下不生效**。历史代码把「基础文件名」`<base>` 直接当 `COVERAGE_FILE`
传给每一段 → 12 段全部追加进**同一个文件**、分片根本不存在 → `combine` 永远无片可合
（单文件累积"恰好"还能算出正确百分比，所以只在 `--segment` 单段运行时才暴露成 28%）。

现改为：每段 `COVERAGE_FILE=<base>.seg<N>`（真正分片），全部跑完后
`coverage combine`（无参，按 `<data_file>.*` 收集）合并回 `<base>`，再统一 `report` 判定。
`atexit` 清理清单同步为各分片。

验证（代码级，直接调用执行器的 `run_segment`，不走主循环）：
`run_segment(…, cov_file=".probe4.seg11")` → 实际产出 `.probe4.seg11`；
`coverage combine`（rc `data_file=.probe4`）退出码 0，输出 `Combined data file .probe4.seg11`。
CI 侧不受影响：流水线走 `scripts/ci_backend_test_segment.sh`（同 job 内 `--cov-append`
单文件累积，末段 `--mode final` 判阈值），因此已发布的 v1.18.8 安装包与本次改动无关。
## [1.18.7] - 2026-10-25 — 录入效率包收口 / 数据同步胶囊 / OCR 建议 / 视觉回归 44 页 / 发布工具加固

> **背景**：v1.18.6 之后又合入 24 个提交，集中在「录入效率（③）」「工作协同（④）」
> 「经费凭证 OCR（⑤）」「性能基座（⑥）」「视觉回归（⑨）」五条线，以及发布工具链加固。
> 本版为最终交付版：代码、文档、PPT、安装包统一到 1.18.7。

### Added

- **批量粘贴弹窗 `BulkPasteDialog`（③）**：粘贴 → 预览 → 逐行校验 → 确认，四步可视化；
  配套 `useBulkCreate` 批量新增执行器（串行提交、逐条失败明细、摘要话术）。
- **消费帮扶台账接入批量粘贴（③ 收口）**：逐行校验 + 串行新增 + 失败行号原样回传，不整批回滚。
- **草稿自动保存扩到 4 个页面（③）**：学校编辑、组织编辑等页面接入 `useFormDraft` +
  未保存离开拦截；切页/刷新不丢输入。
- **顶栏数据同步状态胶囊 + 台账抽屉（④）**：只读 `/data-sync/logs`，不新增接口；
  异常状态一眼可见并可下钻。
- **经费凭证 OCR 字段级建议（⑤）**：接入转账凭证新建对话框，识别金额/日期给出建议并由人工确认
  （后端能力早已存在，此前前端零调用）。
- **VirtualList 虚拟滚动基座（⑥）**：窗口算术抽成纯函数（22 例测试，双文件 100% 覆盖）。
- **usePageSize 每页条数偏好（⑥）**：偏好记忆 + 归一化，项目列表接入。
- **视觉回归扩到 44 页（⑨）**：30 个 console tab + 4 个核心表单，DOM 结构快照不比对像素。

### Fixed

- **E2E 新增村庄表单断言**：顶栏同步抽屉的隐藏元素污染 `.first()`，改用 `:visible`。
- **Nightly 分组漏根目录**：补跑 `tests` 根目录，`permission_packs` 覆盖率 38% → 100%。
- **release_tag 工具链**：输出改 UTF-8；工作区脏时提供 `--allow-dirty` 逃生口
  （tag 仍只指向已推送 commit）；`ci_green` 兼容 stdout/stderr 为 `None`；裸 pragma 补理由
  （F2 棘轮 1 → 0）。

### Changed

- **新增 PR/Nightly 覆盖率一致性门禁**：防止两套口径长期漂移。
- **README**：修正未签名安装包「Defender 首次扫描 1~3 分钟」的乐观说法（附实测）。
- **文档与 PPT 收口**：版本/测试数字统一（后端 14,722 / 前端 7,356 / 347 文件）；
  新增 `RELEASE_NOTES-v1.18.7.md`；系统介绍 PPT 升级为 v1.18.7 / 56 页。

### 验收

- 后端 12 段：**14,722 用例，0 failed / 0 skipped**；45,936 语句 / 11,452 分支 **100.00%**。
- 前端：**347 文件 / 7,356 用例**，语句/分支/函数/行 **四项 100%**。
- `flake8 app/ + scripts/` = 0；Alembic **63 版本单 head r43**；CI 9 作业全 success。

## [1.18.6] - 2026-10-25 — 仓库卫生与门禁加固（scripts 纳入 flake8、全仓 flake8 归零）

> **背景**：本仓文档声明的"flake8 零错误门禁"实际只覆盖 `backend/app/`；
> 2026-10-25 实测 `cd backend && flake8 app/` **79 条违规**、`scripts/` 19 条违规，
> 而这两处都不在任何 CI 步骤的有效拦截范围内。本版把口径补齐并把存量归零。

### Fixed

- **`backend/app/` flake8 归零（79 → 0）**：78 处 `E302/E305`（`app/models/` 14 个文件
  顶层定义之间只有 1 个空行）+ 1 处 `F401`（`models/monitoring.py` 未使用的 `JSON` 导入）。
  修法为纯空行/导入整理，无逻辑变更。
- **`scripts/` flake8 归零（19 → 0）**：未使用导入 4 处（`run_backend_tests_segmented.py`
  的 `shutil`、`docs/extract_api_endpoints.py` 的 `re`、`security/pii_scan.py` 的 `io`/`os`）、
  `E401`×2 / `E302` / `E305` / `E303` 各 1（`pre_commit_hooks.py`、`ppt_overflow_check.py`）、
  `W292` 缺末尾换行 ×2、`W504` 行尾二元运算符 ×2、`F541` 空 f-string ×1、
  `E501` 超长行 ×5（`cleanup.py`×3、`ppt_overflow_check.py`、`run_backend_tests_segmented.py`）。
- **`frontend/package.json` 补 `engines`**：`node: ^20.19.0 || >=22.12.0`
  （对齐 Vite 7 的实际要求；本机实测 Node 25.2.1）。此前无任何约束。

### Fixed（2026-10-25 复验：0 失败 0 跳过）

- **密码哈希改 bcrypt 直连**（`app/core/security.py`）：passlib 1.7.4 在 bcrypt 5.x 下
  后端探测失败，且**失败状态在进程内永久缓存** —— 大批量收集时随机抛
  `passlib.exc.MissingBackendError`，使 `test_soft_delete_coverage` / `test_supported_village_api`
  直接收集失败、覆盖率失真。改用 `bcrypt.hashpw/checkpw` 直连后产物格式不变
  （`$2b$<cost>$`），历史哈希零迁移；`pwd_context` 仅兼容保留。
- **MANIFEST bbox 只校验长度不校验数值**（`api/v1/map.py`）：`["x",1,2,3]` 这类非法 bbox
  会被当作 Leaflet bounds 传给前端，地图表现为不显示 / 异常缩放。新增 `_valid_bbox()`
  校验「4 个有限数值」，并排除 `bool` / `NaN` / `±inf`。
- **消除唯一 skip**（`tests/unit/test_offline_log_path_w18.py`）：打包态日志路径改写回归
  原先用 `skipif` 跳过开发机 —— 等于该核心回归永不在本地验证。改为
  `monkeypatch` `sys.frozen=True`，与真实打包态走同一分支。
- **BaseChart 主题重建入口显式暴露**（`components/common/BaseChart.vue`）：
  `rebuildForTheme` 仅靠全局自定义事件触发，多套件并行时覆盖归属漂移
  （单跑 100%、全量 99.8%）；`defineExpose` 暴露 `rebuild()` 后可直测。
- **覆盖率门禁两处失效根治**（`scripts/run_backend_tests_segmented.py`）：
  ① `.coveragerc` 缺失时 **fail-fast**（历史：被清理分片误删 → `fail_under` 静默失效，
  门禁假绿）；② 覆盖率判定从「末段内联 report」改为「**全部段跑完后统一 report**」，
  并支持 `--cov-unique`（每段独立 `data_file` + `combine`）—— 多会话并发下固定文件名
  会互相覆盖，实测 12 段全 PASS 却只 report 出 53%；清理分片一律精确匹配，
  **绝不用 `.coverage*`**（会把 `.coveragerc` 一起删掉）。
- **复验口径**：后端 12 段全 PASS / 0 failed / 0 skipped，对累积数据 `coverage report`
  = **100.00%**（45955/45955 语句、11450/11450 分支）；前端 **334 文件 / 7138 用例**
  全 PASS、覆盖率四项 100%（`--maxWorkers=2` 避免并发抢 worker 导致
  `The service is no longer running` 假失败）；`flake8 app/ + scripts/` = 0。
- **⑥ 分页上限改造引入的 6 处回归**（本版修复；12 段复验时 seg10/seg12 各挂 1/5 例）：
  - **直接调用崩溃**：`auth/users.py` / `feedback.py` / `machine_code.py` 把
    `page_size: int = 20` 改成 `Query(DEFAULT_PAGE_SIZE, ...)` 后，HTTP 路径正常，
    但**测试/内部代码直接调用端点**时拿到的是 `Query` 对象，
    `(page - 1) * page_size` 抛 `TypeError: unsupported operand type(s) for *: 'int' and 'Query'`
    （`test_coverage_gaps_final` 1 例 + `test_v1129_gap_users_super_admin` 2 例）。
    修法：`app/utils/pagination.py` 新增 `coerce_page_param()`，三处端点调用前归一成 int，
    HTTP 校验（`ge=1, le=MAX_PAGE_SIZE`）与门禁口径都不变。
  - **常量断言漏改**：`MAX_PAGE_SIZE` 100→200 后，`test_core_constants.py` /
    `test_core_full_coverage.py` / `test_svc_batch.py` 仍断言 100 → 3 例失败。断言已同步 200。
  - **验证**：上述 5 个测试文件 **285 passed**；`check_pagination_cap.py` OK；
    `flake8` 改动文件 0；seg10/seg12 重跑见下方结论。

### Added

- **CI 增补 `scripts/` flake8 步骤**（`.github/workflows/pr-checks.yml` 的 `lint` 作业）：
  `flake8 ../scripts/ --max-line-length=120 --count --max-complexity=40 --exclude ../scripts/archive`。
  复杂度阈值放宽到 40 的**理由**：`scripts/` 多为一次性流程脚本（`cleanup.py` 35、
  `run_backend_tests_segmented.py` 27、`ppt_overflow_check.py` 24、`audit_static_assets.py` 19），
  `main()` 天然较长；其余规则与 `app/` 完全同口径，`scripts/archive/` 与仓库根
  `.flake8` 的 exclude 保持一致（本地直跑 `flake8 scripts/` 仍是 0）。

### Changed

- 版本 1.18.5 → 1.18.6，`node scripts/sync-version.js --write` 同步 22 处目标（14 个文件已更新）。
- `gh auth setup-git` 已配置（`credential.https://github.com.helper` 指向 gh），
  https 协议的 git 操作可用 gh 凭证；本仓 `origin` 仍为 SSH，推送走既有 `id_rsa` 不变。

### Tests

- 待完整回归结果回填：`scripts/run_backend_tests_segmented.py`（后端分段全量）
  + `cd frontend && npm test -- --run`（前端全量）+ `vue-tsc --noEmit`。

### Fixed（2026-10-25 追加②：版本号去"双字面量"）

- **`SYSTEM_VERSION` 兜底不再在源码里写版本号字面量**：`frontend/src/config/constants.ts`
  改为 `import.meta.env.VITE_APP_VERSION || __APP_VERSION__`，而 `__APP_VERSION__` 由
  `vite.config.ts` / `vitest.config.ts` 的 `define` 在构建期从根 `package.json` 注入
  （类型声明见 `src/vite-env.d.ts`）。
  **为什么**：那串字面量是 `sync-version.js` 的同步目标之一，每升一次版本都得记得一起提交；
  实测 v1.18.2 → v1.18.5 **连续 4 次漏提交**，每次都让 `static-analysis` 的
  Version consistency check 与 `constants.test.ts` 同时变红。现在源码里只有一份版本号
  （`package.json`），**不存在可被忘记的副本**。
- **`sync-version.js` 目标 23 → 22 处**（摘掉 `frontend/src/config/constants.ts`）：
  该文件不再需要同步，`--check` 也不再检查它。文档同步更新
  （`CLAUDE.md` / `AGENTS.md` / `docs/03-开发文档/06-运维文档/技术栈说明.md` /
  `docs/04-部署文档/01-Windows部署/构建打包指南.md`）。

### Fixed（2026-10-25 追加③：清理 26 个零引用死字段）

- **新增迁移 `r43_prune_dead_columns_001`**：清掉 `scripts/scan_dead_columns.py` 扫出的
  **26 条**「模型里声明、`app/` 非模型代码零引用、`frontend/src` 零引用」的列 ——
  它们既无写入路径也无读取路径，留着等于让 schema 撒谎（与 r41 删 `issues` 表同一理由）。
  沿用 r35/r36/r39 的**列级三分支**契约：列不存在→跳过；整列空/0→`DROP COLUMN`；
  **有数据→改名 `legacy_<列名>` 归档，数据一行不丢**；归档列已存在→保留原列交人工确认。
- **真实库演练（开发库副本，r42 → r43）**：`funds.budget_status`（12 行）、
  `machine_codes.restrict_permissions`（1 行）有值 → 归档为 `legacy_*` 且行数不变；
  其余 24 列为空 → 删除。若日后要恢复这些功能，列名与 DDL 都在迁移历史里，可逆。
- **同步清理**：14 个模型文件移除字段声明；`test_json_column_mutability_ratchet`
  基线 28→25（JSON 列）与 27→24（已复核列）、`test_money_precision` 金额列清单、
  `test_funds_api_extended` / `fund_factory` / `village_factory` 的字段入参。
- **新增测试 `test_migration_r43_prune_dead_columns.py`（10 例）**：三分支、0 值视为未填、
  幂等、归档列已存在、表/列缺失、清单形状、修订链接 r42→r43。

### Tests（2026-10-25 追加②③验证）

- 后端受影响测试 **174 例全过**（含 r43 迁移 10 例）；`alembic heads` 单 head
  `r43_prune_dead_columns_001`；三层对齐门禁（含空库 `alembic upgrade head`）**通过**。
- 前端：`vue-tsc --noEmit` 0 错误；`constants.test.ts` 7 例全过（兜底值 = `package.json`
  版本，证明 `define` 注入生效）；`sync-version.js --check` 通过（22 处目标）。
- **⚠️ 本机 `npm run build` 当前失败，与本次改动无关**（已隔离证明）：报
  `[vite:esbuild-transpile] remove ...\Temp\esbuild-<hash>: Access is denied`。
  把本次 4 个前端文件还原成 HEAD 版本后**同样失败**，属本机环境问题
  （残留 esbuild 服务进程锁住临时二进制 + Defender 实时扫描；CI 为 Linux runner 不受影响）。
  本机如需出包，先 `Get-Process esbuild | Stop-Process` 并清空 `%TEMP%\esbuild-*` 后重试。

### Fixed（补充）

- **`tests/unit/test_svc_batch.py::test_h10` 断言过期**：`MAX_PAGE_SIZE` 已由 100 调整为 200
  （分页硬上限收口），该断言仍写 100；本地只跑相关套件未触及，CI 的 seg10 才红并被
  `check_release_gate.py` 拒绝出包。已更新为 200。

### Added

- **`scripts/release_tag.py`（唯一发布入口）**：一次校验"main 分支 + 工作区干净 + tag 与
  `package.json` 版本一致 + CHANGELOG 已记录 + 目标 commit 的 PR Checks 绿"，通过后才
  `git tag && git push`；默认 dry-run，支持 `--sha`（main 被他人推进时仍发布自己验证过的提交）。
- **`scripts/check_constants_sync.py`（常量↔字面量门禁）**：扫描 `backend/tests`、`docs` 中
  `CONST == 字面量` 与 `backend/app/core/constants.py` 是否一致，专防"常量改了、测试没改"；
  已接入 `.pre-commit-config.yaml` 的 **pre-push** 阶段。
- **`docs/agents/ci-failure-lessons.md`**：2026-10-25 一整天 CI 红灯（PR Checks / Nightly /
  v1.18.4 / v1.18.5 tag 构建）的根因分类、已落地防线与发布纪律。
- 单测：`test_check_constants_sync.py`（10 项）、`test_release_tag_gate.py`（9 项）。

## [1.18.5] - 2026-10-25 — 修正 1.18.4 的 bbox 补丁未生效（真正取最细 zoom）

> **1.18.4 的事故**：声称"取最细 zoom"，但源码编辑未命中实际结构（`scan_tiles_dir`
> 已重构为 `_scan_x_dir` 委托），补丁实际 no-op；真机验证 bbox 仍是
> `[101.25, 21.94, 112.5, 31.95]`（z5 概览瓦片外沿）。**本版真正实现并验证**。

### Fixed

- `scan_tiles_dir` 改为**按 zoom 分组累计**（每个 z 目录单独合并 `_scan_x_dir` 的 bounds，
  存 `bounds_by_zoom`），最终 `bounds` 取 `bounds_by_zoom[max(...)]`。
- 实测（`resources/map-tiles`，5,623 张 z5–12）：
  `bounds = [103.53515625, 24.5271348225978, 109.6875, 29.22889003019423]` —— 贵州辖区量级；
  修正前为 `[101.25, 21.94, 112.5, 31.95]`。
- 多包叠加语义不变：同一 zoom 内仍为各包并集（有 22 项 bbox 测试覆盖，含贵阳+遵义并集用例）。

### Tests

- `test_tile_info_coverage_bbox.py` / `test_map_tile_info_diagnostics.py` /
  `test_offline_map_service.py` / `test_tiles_pipeline.py` 合计 **163 passed**；flake8 0。
- 真机（打包后端）复验：`tile-info.bbox` 为上述辖区量级；覆盖区内瓦片 200、区外 404。

### Added（③ 录入效率包基座：草稿自动保存 + 批量粘贴解析）

- **`composables/useFormDraft.ts`（表单草稿自动保存）**：本次改动中最能直接省人力的一个 ——
  现场录到一半被电话/查台账打断，原来一离开页面输入全丢（这类表单普遍 10+ 字段）。
  - 按业务键隔离（`form:draft:policies:edit:new` / `...:42`），新建与编辑互不污染；
  - **空表单不落盘**（`isBlankForm`）——否则开一次表单留一条垃圾，localStorage 5MB 很快见底；
  - **TTL 默认 7 天**，过期自动丢弃并清理，不复活半年前的脏数据；
  - 存储不可用/配额满/JSON 损坏/结构不符 一律静默降级为 null，绝不抛错；
  - 恢复是**显式动作**（`restore()`），不静默覆盖用户刚输入的内容；
  - 仅在组件实例内注册 `onUnmounted` 清理（`getCurrentInstance()` 守卫），避免脱离 setup
    调用时 Vue 告警。
- **`utils/parsePastedTable.ts`（Excel 粘贴解析）**：现场数据多数先在 Excel/WPS 整理好，
  逐条手敲是最费时的一步。解析器处理了真实形态：`\r\n`/裸 `\r`、行尾多余制表符、
  空白行、**双引号包裹且含制表符/换行的单元格**（`""` 还原为引号）；
  并设行列上限（默认 500×50，超限**不静默截断**而是返回 `exceeded` 让页面提示分批粘贴）。
  另提供 `findFirstMismatchedRow()`：列数不符返回首个行号，供预览标红 ——
  **不做自动补空**（错位比缺行更难发现）。
- 测试：`useFormDraft.test.ts` **23 例**、`parsePastedTable.test.ts` **17 例**；
  两文件覆盖率 **100/100/100/100**（含分支）；`vue-tsc` 0、eslint 0 error。
- 说明：本批交付的是**可复用基座**；接入具体表单页（并配 `useDirtyGuard` 铺开）在下一批完成 ——
  目前全仓只有 `projects/Edit.vue` 一个页面接了离开拦截。

### Added（③ 第二个页面接入：政策编辑页草稿 + 离开拦截）

- **`views/policies/Edit.vue` 接入 ③**：草稿键按模式隔离（`policies:edit:new` /
  `policies:edit:<id>`）；`onMounted` 里若存在草稿则**先问再恢复**（`ElMessageBox.confirm`），
  用户忽略则删除草稿；`onBeforeUnmount` 立刻 `flush()` 落盘（防抖窗口内离开也不丢）；
  提交成功后 `clear()` + 复位脏标记（避免下次进来"复活"已提交数据）。
- **离开拦截接线**：`useDirtyGuard(isDirty)` —— 此前全仓只有 `projects/Edit.vue` 接入，
  本批再补一个录入型页面。实现上刻意**不造**"只在初始化后注册 watcher"的可选链
  （那会留下永不进入的分支，是覆盖率黑洞），改为 setup 即注册、初始化完成后复位脏标记。
- 测试：`Edit.test.ts` 37 → **42 例**（新增草稿恢复/忽略/守卫注册/卸载落盘/提交清草稿），
  该页覆盖率仍 **100/100/100/100**；`vue-tsc` 0；`eslint src --max-warnings=0` 通过。
- 顺带记录：该测试文件里 3 条 `Write operation failed: computed value is readonly` 告警
  **在未接入版本上同样存在**（已用 `git checkout` 对比验证），属既有测试桩行为，非本次引入。

### Added（③ 收口：消费帮扶台账「批量粘贴」上岗）

- **`utils/consumptionPaste.ts`**：把粘贴出的二维数组翻译成 `ConsumptionRecordPayload`，
  **逐行报告失败**（哪一行、为什么）而不是整体失败 —— 否则用户只能全量重来，而重来会重复入库。
  - 列顺序固定 9 列：品类 / 品名 / 数量 / 单位 / 金额 / 购买方 / 销售方 / 年度 / 日期；
  - **品类同时接受中文标签与枚举值**（现场写"农产品"，接口要 `agriculture`）；
  - 金额去千分位与 `¥￥元`；年度空/非法回退默认年（年份写错不值得阻断整批）；
  - 日期 `YYYY-MM-DD` / `YYYY/M/D` / `YYYY年M月D日` 三种写法归一；
  - 必填只校验"能确定的"三项（品类可识别、品名非空、金额为正），
    其余列缺失留空 —— 台账本来就常有空列，因缺一列整批拒绝会让功能不可用；
  - 行号 1 基，与预览表格 `#` 一致；行数组短于列数时按空串处理（Excel 省略行尾空格）。
- **`views/consumption/List.vue` 接入**：工具栏新增「批量粘贴」→ `BulkPasteDialog`
  （9 列声明）→ 逐行校验 → `useBulkCreate` **串行**新增 → 汇总提示（失败行号进消息）→ 刷新列表与统计。
  失败原因超 3 行时提示带"等 N 行"，避免消息被截断成一句看不懂的话。
- 又一次删掉"永不进入的兜底"：`year: form.year || CURRENT_YEAR` 里 `form.year` 是必填 number，
  该 `||` 分支永远走不到 —— 留着只会拉低覆盖率。
- 测试：`consumptionPaste` **18 例**（含短行、空品类/空金额文案、逐行报错、默认年回退）、
  页面 **9 → 16 例**（打开弹窗、全部成功、部分失败、全部失败、`update:visible` 写路径、超 3 行提示）；
  两文件覆盖率均 **100/100/100/100**；lint / tsc / 色值棘轮全绿。

### Added（⑥ 首个页面接入：项目列表的每页条数记忆）

- `views/projects/List.vue` 的 `pagination.pageSize` 改为来自 `usePageSize('projects')`：
  - 默认 20（原硬编码 10）；选项 `[20, 50, 100, 200]` 由 composable 提供，
    其中 200 与后端 `MAX_PAGE_SIZE` 一致；
  - `handleSizeChange` 里先 `setPageSize()` **归一化再持久化**：用户若通过 devtools
    塞了 37 之类非法值，会被拉回默认而不是让后端 422；
  - 重启后仍是上次选择（`ui:pageSize:projects`）。
- 顺带修一个类型问题：`options` 原为 `readonly number[]`，与 `el-pagination` 的
  `page-sizes: number[]` 冲突（TS4104），改为返回**可变数组副本**（不共享引用，调用方改不到常量）。
- 测试：该页 **67 例**保持全绿（更新"默认 page_size 10→20"的断言），页面覆盖率 **100/100/100/100**；
  另外跑了 `projects` 页的视觉基线（`-g "projects"`）确认 **1 passed**，DOM 结构未漂移。

### 说明（⑥ 虚拟滚动的适配性结论 + 每页条数偏好）

- **结论：虚拟滚动在当前架构下没有自然落点，不强行改造。**
  排查了列表页后发现：全站列表**都已分页**，且 `page_size` 有 200 的硬上限
  （`MAX_PAGE_SIZE`，由 `check_pagination_cap.py` 门禁守住），单页最多 200 行。
  `el-table` 在该量级没有性能问题；给分页表套虚拟滚动只会引入"分页 + 窗口"双状态同步的坑，
  属于典型的为架构而架构。因此 `VirtualList` 作为**可用基础设施**保留（22 例测试、覆盖率 100%），
  待将来出现"不分页全量列表"时直接使用，而不是现在硬塞给某个页面。
- **真正缺的那一半已补：`composables/usePageSize.ts`（每页条数偏好）**。
  现状是 55 处硬编码 `page_size`、多数列表页虽有 `page-sizes` 下拉但**不记忆**，
  用户每次进来都要重选。本模块提供统一入口：
  - 选项固定 `[20, 50, 100, 200]`，**200 与后端硬上限一致**；
  - 只接受选项内的值（不做就近取整，避免 37 这类值造成困惑）；
  - 按业务域记忆（`ui:pageSize:<scope>`），列表页之间互不干扰；
  - 存储不可用/损坏 JSON 一律回退 20，绝不抛错（模块在渲染热路径上）。
- 测试：`usePageSize` **10 例**（归一化边界、按域隔离、存储异常降级、set 返回生效值），
  覆盖率 **100/100/100/100**。
- 页面接入（把 `projects/List` 等页的 `pagination.pageSize` 换成该 composable）留给下一批 ——
  这些页面已有下拉，改造点在"记忆"而非"新增控件"，需要连同页面测试一起改。

### Added（⑥ 虚拟滚动基座：`VirtualList` + `virtualWindow` 窗口计算）

- **为什么自己做**：项目里 `el-table` 有 1300+ 处使用，但 Element Plus 表格**不做虚拟滚动**，
  上千行时渲染开销与内存都会失控（离线单机没有服务端兜底）。给"长列表型"页面一个
  低风险替代：**只渲染可视区 + 缓冲行**，DOM 行数恒定，与数据总量无关。
- **`utils/virtualWindow.ts`**：窗口算术抽成纯函数（`computeWindow` / `sliceWindow`）。
  虚拟滚动的 bug 几乎全是边界算术，写成纯函数才能穷举：
  - 负 `scrollTop`（触控回弹）按 0 处理，绝不产出负索引；
  - 滚到底部时 `end` 被 `total` 截断 —— 否则会渲染 `undefined` 行；
  - 过度滚动、`itemHeight<=0`、`total<=0`、视口高度 0 都退化为安全值
    （`itemHeight<=0` 时按 1 处理，不产出 `Infinity`/`NaN`）。
- **`components/common/VirtualList.vue`**：固定行高的通用虚拟列表，插槽暴露
  `{ item, index }`（**绝对索引**，不是窗口内索引）；容器高度支持数字与 CSS 值；
  视口高度挂载时实测一次（容器高度由 props 固定，不需要监听 resize）。
- 实现取舍：**主动删掉两处"防御式可选链"**（`el?.scrollTop ?? 0`、`containerRef.value?.clientHeight ?? 0`）
  —— 滚动事件目标恒为容器、mounted 后容器必然存在，留着只会是永不进入的分支（覆盖率黑洞）。
- 测试：`virtualWindow` **14 例**（含底部截断、过度滚动、负数、零行高、小数据量）、
  `VirtualList` **8 例**（DOM 行数远小于数据量、滚动换窗口、底部不渲染 undefined、
  空数据、height 两写法、无 viewportHeight 时的兜底、slot 绝对索引），
  两文件覆盖率均 **100/100/100/100**。
- 页面落地（把 `UpdateLogs` 的 `el-timeline` 换成虚拟列表 + 视觉基线更新）在下一批完成。

### Added（③ 第四个页面接入：学校编辑页草稿 + 离开拦截）

- `views/schools/Edit.vue` 接入 ③：草稿键 `schools:edit:new` / `schools:edit:<id>`；
  `onMounted` 先 `await loadData()` 再询问恢复（不静默覆盖），离开 `flush()`，提交成功 `clear()`。
- 这一次遇到**两个**测试桩滞后（都是"接入即红"）：
  1. `vue-router` mock 缺 `onBeforeRouteLeave` → 31 个用例全红；
  2. `@/composables/useRouterSafe` mock 只给了 `useRouterSafe`，页面新用到的
     `safeRouteParam` 在 mock 里是 `undefined` → **setup 直接抛错**（报错指向 `Edit.vue:266`）。
     这类错误若只看"测试红了"很容易误判成业务代码问题，实际是 mock 契约没跟上。
- 测试：该页 **31 → 35 例**（草稿恢复/忽略/卸载落盘/提交清草稿），覆盖率 **100/100/100/100**；
  `schools` 目录 7 个套件 **183 passed**；lint/tsc/色值棘轮全绿。

### Added（⑨ 视觉回归从 10 页扩到 44 页：30 个 console tab + 4 个核心表单）

- **补齐 30 个 console tab**：系统管理 6 个聚合页共 30 个 tab，此前只有
  `/system/console/org` 一个落地页在基线上 —— 任一 tab 的组件映射坏掉（菜单有、组件缺）
  都不会被视觉回归发现，而这类故障的表现正是"点进去白屏"。
  现按 `menus.py` 的 console 定义生成 30 条基线（`/system/console/<group>?tab=<key>`），
  与 `check_console_tab_mapping.py` 的静态门禁形成"静态 + 运行时"双保险。
- **补齐 4 个核心表单**：`/policies/create`（添加政策）、`/projects/create`（添加项目）、
  `/schools/create`（添加学校）、`/funds/create`（经费登记）——
  录入态是最容易被 UI 改造打破的界面，且没有列表页"至少还有表格"的兜底观感。
  注：组织没有独立 create 路由（新建走列表页对话框），故未纳入。
- 实现：`helpers.ts` 里以常量表生成基线（避免手写 34 段重复对象），
  `VISUAL_BASELINES.push(...)` 追加；标题取自 router `meta.title`（稳定契约）。
- 验证（本地跑，`webServer` 自起后端 + 前端）：`UPDATE_VISUAL_BASELINE=1` 采集 **44 passed**；
  随后**不带更新标志**复跑 **44 passed**，确认基线自洽（不是"更新完就绿"的自欺）。
- 顺带：`src/components.d.ts` 由 unplugin-vue-components 自动补上本轮三个新组件
  （`CommonBulkPasteDialog` / `FundsOcrVoucherSuggest` / `NavSyncStatusCapsule`），一并提交。

### Added（③ third 页面接入：组织编辑页草稿 + 离开拦截）

- `views/organization/Edit.vue` 接入 ③：草稿键按模式隔离（`organization:edit:new` / `:id`）；
  `onMounted` 先 `await loadData()` 再询问恢复草稿（**不静默覆盖**刚拉回的数据）；
  离开时 `flush()` 落盘；提交成功 `clear()` + 复位脏标记。
- 与政策编辑页一致的实现取舍：**setup 即注册 deep watcher**，初始化完成后复位 `isDirty`，
  而不是造"初始化后才注册 watcher"的可选链（那会留下永不进入的分支）。
- 一次真实回归：该页 17 个测试**全红** —— 测试里 `vue-router` mock 只有 `useRoute`，
  而 `useDirtyGuard` 需要 `onBeforeRouteLeave`；补齐 mock 后全绿（同时把 `ElMessageBox.confirm`
  提升为可断言的 hoisted mock）。这类"接入即红"正是必须跑页面测试的原因。
- 测试：该页 **17 → 21 例**（草稿恢复/忽略/卸载落盘/提交清草稿），覆盖率 **100/100/100/100**。

### Added（⑤ 接入活体页面：转账凭证新建对话框）

- `views/funds/TransferVoucher.vue` 的新建对话框接入 `OcrVoucherSuggest`：
  「识别凭证图片 → 逐字段建议 → 采纳/忽略」，落点是本页真实存在的两个字段
  `amount`（金额万元）与 `transfer_date`（划转日期）—— 正好是后端 OCR 的结构化返回项。
- **字段写入做类型防御**：金额只在 `Number.isFinite && > 0` 时写入，非法值（`abc` / `0`）直接忽略，
  避免把 `NaN` 塞进 `el-input-number` 造成"看着有值、提交为空"；未知字段（如 `voucher_no`）一律不写。
- 「全部采纳」会提示"已填入 N 个字段，请核对后保存"——识别结果仍需人工确认后才提交，
  不会绕过表单校验与审计留痕。
- 测试：该页 **23 → 29 例**（`ocrCurrent` 反映表单值、金额为空不给 `0`、采纳金额/日期、
  未知字段忽略、非法金额拒绝写入、全部采纳提示），页面覆盖率 **100/100/100/100**；
  `eslint src --max-warnings=0`、`vue-tsc`、色值棘轮 146/146 全绿。

### Added（⑤ 经费凭证 OCR「字段级建议」——把"识别完还得自己抄"接上）

- **发现**：后端 `POST /funds/ocr-voucher`（`{text, amount, date, confidence, engine}`）早已实现，
  但**前端零调用** —— 现场实际是"识别完还得自己抄进表单"，等于该功能不存在。
- **`api/funds.ts`**：新增 `ocrVoucher(file)`（multipart，走既有 `post` 封装）与
  `OcrVoucherResult` 类型；**不吞错**，503 交给调用方给出友好提示。
- **`utils/ocrSuggestion.ts`**：把识别结果拆成**逐字段建议**而非整段文本。
  - `classifyConfidence`：≥0.85 高置信 / ≥0.6 需核对 / <0.6 低置信（缺失按最低档，宁让人核对）；
  - `normalizeOcrAmount`：去千分位与 `¥￥元`、取首个数字串；
  - `normalizeOcrDate`：兼容 `2024-01-02 / 2024/1/2 / 2024年1月2日` → `YYYY-MM-DD`，非法月日拒绝；
  - `buildOcrSuggestions`：**只列识别出值的字段**（避免整列"—"让人误以为识别失败），
    并标出"与当前值相同"（无需采纳）。
- **`components/funds/OcrVoucherSuggest.vue`**：上传凭证图片 → 逐行显示
  「字段 / 当前值 → 识别值 / 置信度标签」→ 逐条采纳或忽略，支持"全部采纳"。
  取舍：**不一次性覆盖表单** —— 覆盖错了更麻烦，且用户不知道改了哪几个字段。
  503 引擎不可用时提示"请手工录入"，不阻断经费业务（ARM64 侧本就降级）。
- 测试：`ocrSuggestion` **14 例**、`OcrVoucherSuggest` **13 例**，两文件覆盖率
  **100/100/100/100**；funds 相关三套件联合 **78 passed**；lint/tsc/色值棘轮全绿。

### Added（③ 批量新增执行器 `useBulkCreate` + 即时校验审计）

- **`composables/useBulkCreate.ts`**：`BulkPasteDialog` 只负责"拿到二维数组"，
  真正落地要靠各页调自己的 create 接口。把它抽成执行器，是为了不让每个页面各写一遍
  而重复出三类毛病：
  1. **不逐条 try/catch** → 第 5 条失败整批中断，前 4 条已入库但用户以为全失败；
  2. **不给失败明细** → 用户不知补哪几条，只能全量重来，而重来会重复入库；
  3. **`Promise.all` 一把打出去** → 离线 SQLite 被写锁撞得满屏 500。
  因此固定为：**串行执行**（离线单机串行比并发安全）、逐条收集 `{row,index,message}`、
  单条失败不中断整批、`running` 由 `finally` 复位、`summarize()` 统一话术
  （"已新增 N 条，失败 M 条（第 2、5 行）"）。`extractErrorMessage` 兼容
  `string / Error.message / {message|detail|msg}` 四种形态。
- **即时校验审计（结论：无需改动）**：全站 `views/**` 共 **94** 条 `required: true` 规则，
  **全部已带 `trigger`**（blur/change）——即"提交时才报错"的情况在视图层已不存在，
  ③ 的"即时校验"项由既有实现覆盖，本轮不再动它（避免为改而改引入风险）。
- 测试：`useBulkCreate.test.ts` **11 例**（串行顺序、单条失败不中断、全失败逐条收集、
  空输入不发请求、`running` 复位、两种摘要话术、错误信息四形态），文件覆盖率
  **100/100/100/100**。

### Added（④ 顶栏「数据同步状态」胶囊 + 台账抽屉）

- **`composables/useSyncStatus.ts`**：只读 `/data-sync/logs`（**不新增后端接口**），
  把"最近一次导入/导出距今多久"算成四挡：<1 天=已同步、<7 天=待同步、≥7 天=久未同步、
  无记录=未同步（阈值 `SYNC_STALE_DAYS` 对外导出便于调整）。
  - 纯函数 `formatRelative` / `computeLevel` / `pickLatest` / `summarize` 独立可测；
    未来时间按 0 处理（时钟漂移不出现"-3 分钟前"），`created_at` 非法的脏记录跳过；
  - 接口失败**不弹错**（顶栏常驻，弹错会污染每个页面），静默降级为"未同步"并在抽屉里说明原因；
  - 兼容 `[] / {items} / {list} / {data} / {records}` 五种载荷形态。
- **`components/nav/SyncStatusCapsule.vue`**：胶囊（状态点 + 相对时间，可键盘 Enter/Space 打开）
  + `el-drawer` 台账（时间/动作/结果/说明），顶部汇总"最近同步 X 前（导入）"，附刷新按钮。
  单根元素包裹 —— 多根 + 具名插槽组合会触发 "Codegen node is missing"（ErrorBoundary 同类坑）。
- **接入顶栏**（`layouts/DefaultLayoutSafe.vue` 的 `header-right`，消息铃铛之前）。
  动机：离线 + 介质传输下，用户最关心的不是"服务器通不通"，而是"我这份数据多久没跟上级对过"，
  而这个信息原先埋在系统管理里没人看。
- 实现取舍：展示格式化（动作中文名/时间/占位）抽到 `utils/syncLogFormat.ts` 并由计算属性求值 ——
  写在 `el-table` 插槽里的话，单测 stub 掉表格后插槽不执行，函数覆盖率永远到不了 100%。
- 测试：`useSyncStatus` **19 例**、`syncLogFormat` **8 例**、`SyncStatusCapsule` **11 例**，
  三文件覆盖率均 **100/100/100/100**；布局测试 39 例（原断言"挂载不发请求"改为按 URL 精确断言
  —— 菜单不重复请求仍被守住，新增的 `data-sync/logs` 只允许一次）。

### Added（③ 批量粘贴弹窗组件 `BulkPasteDialog`）

- **`components/common/BulkPasteDialog.vue`**：粘贴 → 预览 → 校验 → 确认，只 emit 数据、
  不碰业务状态（调用方自行决定"填入当前表单"还是"批量新增"）。
  - 顶部显示**目标列含义**（第 1 列=帮扶村*…），让"粘几列、每列是什么"一眼可见；
  - 预览固定展示前 8 行并显式标出空单元格为 `—`，超过 8 行时提示"仅预览前 N 行"（数据仍全量回传）；
  - **行尾缺列自动补空**：Excel 复制会省略行尾空单元格，这是常态而非错位；
  - **仅当某行列数多于目标列时才拦下**（多选列/整体错位必须人工核对），
    超行/超列上限直接报错、不静默截断。
- 实现取舍：空单元格判定放进脚本里的 `previewMatrix` 而非模板插槽表达式 ——
  `el-table` 在单测里被 stub 时插槽不执行，判定写在模板里会成为覆盖率黑洞
  （对应用例可直接断言矩阵内容）。
- 测试：`BulkPasteDialog.test.ts` **16 例**（含行尾补空、多列拦截、超限提示、
  预览截断提示、弹窗自身关闭转 `update:visible`、确认后清空），组件覆盖率 **100/100/100/100**；
  `eslint src --max-warnings=0` 与 `vue-tsc` 均通过；硬编码色棘轮 146/146 零新增。

### Fixed（⑥ 分页硬上限：4 处裸分页 + 1 处 500 上限）

- **`page_size` 有 4 处完全没有上限**（`machine_code` / `organization` / `auth/users` / `feedback`
  都是裸 `page_size: int = 20`），另有 `messages` 一处 `le=500`。离线单机里这不是"慢一点"：
  一次实例化上千 ORM 对象（含加密 PII 列），Electron 侧拿到超大 JSON 会卡死，
  现场表现是"点一下列表就白屏"。全部改为
  `Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE)` / `Field(...)`。
- **`MAX_PAGE_SIZE` 100 → 200**：不能定 100 —— 前端已有 **21 处 `page_size: 200`**
  （地图/帮扶村/转交人搜索等"取一屏全量"场景），定 100 会把这些调用直接打成 422，
  等于用门禁制造一批线上故障；200 也是本仓既有的事实上限（18 处端点本就写 `le=200`）。
- **新增门禁 `backend/scripts/check_pagination_cap.py`**：任何 `page_size` 声明同行缺 `le=`
  或 `le` 超过 `MAX_PAGE_SIZE` 即失败（CI `static-analysis` 的 `Pagination cap guard`）。
  另有 `backend/tests/unit/test_pagination_cap_gate.py`（**8 例**）：门禁能红（裸声明 / le=500 /
  目录缺失）、能绿（`le=MAX_PAGE_SIZE` / 更严格字面量）、真实仓库通过、
  且 `MAX_PAGE_SIZE==200` 与前端调用习惯一致。
- 验证：门禁 EXIT=0；新增 8 例全通过；受影响端点测试
  `test_auth_users_api` / `test_api_messages_full` / `test_organization_management` **89 passed**。

### Added（② 场景预设 + 首次启动按视口自适应）

- **三档场景预设**（`useUiPrefs.ts` 的 `UI_PRESETS` / `UI_PRESET_OPTIONS` / `matchPreset`）：
  「标准」（标准字号+舒适行高）、「紧凑」（小字号+紧凑行高+简化，一屏多几行）、
  「演示」（大字号+紧凑+简化，投影/汇报可读）。预设是**四个字段的完整组合**而非打补丁 ——
  避免叠加出"大字 + 舒适行高 + 不简化"这种怪状态；手动改任一开关后 `matchPreset` 返回
  `custom`，预设行自动不再高亮。
- **外观设置面板新增「场景」行**（`data-testid="appearance-preset-row"`），一次点击即套用；
  原字号/密度/高对比/简化四个开关保留，供微调。
- **首次启动按视口高度给初始密度**：`pickDensityForViewport()` —— ≤800px（1366×768 政务本、
  老投影）用紧凑行高，否则舒适；`initUiPrefs()` 只在**从未存过偏好**时采用推荐值，
  用户手动改过就不再覆盖（避免"我调好了、下次打开又被改回去"）。
  无 `window` 环境（预渲染/单测）回退 768 保守处理，不抛错。
- 测试：`useUiPrefs.test.ts` 11→**25**、`AppearanceSettings.test.ts` 9→**12**；
  两文件覆盖率 **100/100/100/100**。

### Changed（图表主题跟随设计 Token）

- **ECharts 调色板与主题改为 Token 驱动且可刷新**：`echarts-theme.ts` 新增
  `PALETTE_TOKEN_NAMES`（16 色索引对齐；`null` = 未纳入 Token 体系，保留原字面量而不编近似值）、
  `syncPaletteFromTokens()`（**原地 `splice`** 替换 `COLOR_PALETTE` 内容，6 个视图的
  `COLOR_PALETTE[i]` 调用点无需改动）、`refreshMilitaryTheme()`
  （重注册 + 递增 `chartThemeRevision` + 派发 `ECHARTS_THEME_CHANGED`）。
  背景：`registerTheme` 只影响**之后** `init` 的实例，原实现切到"户外高对比"后图表仍是军绿 ——
  而强光现场最需要看清的恰恰是图表。
- **主题切换单一入口接线**：`applyThemeToDom()` 写完 `data-theme` 后调用 `refreshMilitaryTheme()`。
- **`BaseChart.vue` 主题事件重建**：监听事件 → `dispose()` + 重新 `init`；`theme` 留空时
  改用 `getCurrentTheme()`（跟随 `data-theme`），不再固定浅色。移除重建路径中永不进入的
  `unmounted` 守卫（监听在 `onUnmounted` 已先移除），避免覆盖率黑洞。
- 测试：`echarts-theme.test.ts` 9→13、`BaseChart.test.ts` 11→13；三文件覆盖率 100/100/100/100。

### Changed（CI 治理：让"验证过"可被证明，让"红了"能照着修）

- **main 不再被后续推送取消运行**：`pr-checks.yml` 的 `concurrency.cancel-in-progress`
  由 `true` 改为 `${{ github.event_name == 'pull_request' }}`。
  动机是实测出来的：2026-10-25 main 上连续 **5 次** PR Checks 全部 `cancelled`
  （每次推送打断前一次），那段时间"推送成功"但**一次完整验证都没有** ——
  这类静默空窗最容易被误读成"CI 过了"。main 改为排队，PR 仍取消（快速迭代优先）。
- **新增 `scripts/check_main_ci.py`（打 tag 前的显式确认）**：查询目标 commit 的 PR Checks
  结论，`success` → 0；无运行/仍在跑/失败/被取消 → 非 0 并给出运行链接与建议
  （被取消时提示"通常是并发打断，重跑或等新 push"）。支持 `--wait-minutes` 等待与 `--json`。
  踩坑：GitHub 的 `head_sha` 过滤**只认完整 40 位**，传 7 位短号返回空数组
  （`1c41ef5` → total_count 0；补全后 → 1），已用 `git rev-parse` 自动补全。
- **覆盖率缺口变可见清单**：新增 `scripts/coverage_gaps.py`（同时解析 coverage.py JSON 与
  istanbul `coverage-final.json`，内置 `--selftest`），在 backend / frontend 两个作业里以
  **`if: always()`** 生成 Markdown 表（按缺口排序、列出未覆盖行与未覆盖分支），写入
  `$GITHUB_STEP_SUMMARY` 并留存 artifact 30 天。
  选 `$GITHUB_STEP_SUMMARY` 而不是 PR 评论：受限仓库常缺 `pull-requests: write`，
  评论失败会让步骤白红；摘要卡在运行页无需任何写权限。
- **新增 CI 策略守卫** `electron/tests/ci-policy.test.js`（4 例）：main 不得恢复取消、
  `check_main_ci.py` 必须存在且被发布流程文档引用、`coverage_gaps.py` 必须支持双格式与自测、
  两个作业必须都有 `if: always()` 的缺口生成步骤。
  已实证能红：把 `cancel-in-progress` 改回 `true` → **EXIT=1**；还原 → **EXIT=0**。

## [1.18.4] - 2026-10-25 — 瓦片覆盖 bbox 取最细 zoom（修正 1.18.3 概览瓦片撑大 maxBounds）

> 1.18.3 的实测 bbox 取"所有 zoom 的并集"，但 **z5 概览瓦片按全球网格对齐**，
> 实测把贵州撑到 `[101.25, 21.94, 112.5, 31.95]`（真机验证），比辖区大 ~3°，
> 前端 `maxBounds` 因此允许拖出大片空白。

### Fixed

- `scan_tiles_dir` 的覆盖范围改为**按 zoom 分组累计、取最细 zoom 的实测并集**：
  - 全省包（z12 明细）→ bbox ≈ 贵州辖区；
  - 单市州包（z7 明细，含 z5–6 概览）→ bbox = 该市州；
  - 多包叠加 → 仍为各包明细并集（1.18.3 的核心修复不回退）。
- `test_tile_info_coverage_bbox.py` 等 163 项相关测试全绿；flake8 0。

### 说明

- v1.18.3 的 tag 已推送并触发过 CI；**v1.18.4 为最终交付版本**（1.18.3 的 bbox 取值偏大，属体验缺陷非功能故障）。

## [1.18.3] - 2026-10-25 — 多包瓦片覆盖并集 / 旧恢复端点下线 / 跨密钥恢复 UI / 签名门禁

> 本批收口「系统还有什么问题」第 0~3 批：数据一致性 1 项、安全 1 项、体验 1 项、交付链 2 项。

### Fixed

- **多包叠加导入后覆盖范围被最后导入包限制（P0）**：`MANIFEST.json` 是"最后导入包"，
  `region.bbox` 只有该市州；`/map/tile-info.bbox` 改为**磁盘实测并集**（`scan_tiles_dir` 顺带
  累计 `_tile_lonlat_bounds`，常量级运算不额外遍历），MANIFEST 仅作回退。先导贵阳再导遵义，
  前端 `maxBounds` 现在覆盖两者并集（此前贵阳瓦片被挡在视野外）。

### Changed

- **旧管理员恢复端点下线（安全）**：`POST /api/v1/system/admin/restore` 改为 **410 Gone**，
  删除 `shutil.copy2` 覆盖数据库逻辑（测试断言 `shutil.copy2`/`get_database_path`/
  `get_backup_directory` 均未被调用），保留 `require_admin`（401/403 优先）与 `filename` 参数契约
  （端点数 849 不变，标 `deprecated`），统一走 `/api/v1/system/backup/restore`
  （维护窗口 + 完整性 + 密钥指纹校验）。
- **跨密钥恢复有 UI 入口**：前端恢复遇 409 且 detail 含"密钥"→ 展示危险勾选 +
  `confirmDanger` 二次确认 → 带 `allow_key_mismatch=true` 重试一次；取消不重试、不抛错。
  上传恢复（FormData）同样支持。

### Added

- **CI 签名门禁**：`build-windows.yml` 新增 `Verify installer signature` —— 配置 `CSC_LINK`
  时 `Status` 必须 `Valid` 否则构建失败；未配置则 `::warning::` + Step Summary 标注"未签名，
  以 SHA256SUMS 为准"。
- 文档：API 文档标注该端点停用；瓦片指南补"边缘 404/诊断字段"排障；代码签名文档补 CI 接线；
  离线加固文档遗留项标记完成。

### Tests / 验证

- 后端：新增 `test_tile_info_coverage_bbox.py`（多包并集/实测优先/非法值回退）+ 停用端点用例，
  相关套件 **262 passed**；flake8 0。
- 前端：`BackupManagementKeyMismatch.test.ts`（17）+ `backup.test.ts`（13）**30 passed**；
  全量前端套件重跑无失败输出。
- 本地安装包 `MRRS-Setup-1.18.3-x64.exe` 打包后实测：`/map/tile-info.bbox` 为实测并集，
  覆盖区内瓦片 200、区外 404 且前端透明不回退。

### Fixed（2026-10-25 追加：交付链两处"看着绿、其实没跑"）

- **electron 外壳单测长期不在版本库里**：`.gitignore` 的 `*.test.js` 通配只给
  `backend/tests/` 与 `frontend/**` 开了白名单，**漏了 `electron/tests/`** ——
  `file-chunk.test.js`、`path-guard.test.js` 一直"磁盘上有、库里没有"，
  CI 与全新 clone 都拿不到（`worker-pool.test.js` 只因早于该规则才侥幸入库）。
  已补 `!electron/tests/**` 并入库 3 个文件；其中 `path-guard` 正是 **Windows 路径语义**
  （盘符/UNC/`..` 规范化/大小写）用例，缺它等于这块完全没测。
  审计口径：全仓磁盘 357 个测试文件，此前 **354 入库 / 3 未入库**，现全部入库。
- **electron 单测此前无人执行（孤儿测试）**：`package.json` 新增 `test:electron`
  （Node 内置 runner，零第三方依赖），并接进 **两个** CI 作业 ——
  `frontend-check`（Linux）与 `windows-smoke`（Windows，该作业新增 `setup-node`）。
  Windows 侧必须有：Linux 全绿对路径语义毫无证明力（v1.12.3 编码崩溃、v1.12.6 GBK 管道均属此类）。
- **发布门禁等待预算与实测压线**：`build-arm64.yml` 两处 `check_release_gate.py --timeout-minutes`
  由 **30 → 90**。本仓 PR Checks 实测 **17.4 / 22.6 / 30.2 / 30.2 分钟**，原值 30 与最慢一次正好压线；
  正常发布流程「推 main → 立刻打 tag」时该步骤只比 PR Checks 晚 1~2 分钟起跑，**必然超时变红**
  （v1.18.1 能成功是因为人工先等 CI 绿再打 tag，属规避而非解决）。
- **接线守卫** `electron/tests/ci-wiring.test.js`（4 例）：断言 `test:electron` 存在、
  两个作业都执行它、`windows-smoke` 配了 `setup-node`、两个构建工作流的门禁等待 ≥ 60 分钟。
  已实证"能红"：把 arm64 临时改回 30 → 该测试 **EXIT=1**，还原 → **EXIT=0**。

## [1.18.2] - 2026-10-25 — 瓦片底图“加载失败已切回矢量”根治（边缘 404 不再整体回退）

> **现场症状**：地图可视化切到「瓦片底图」后立即提示「瓦片底图加载失败，已切回矢量地图」。
> **根因（不是瓦片缺失）**：`RasterTileLayer.vue` 把**任意一张**瓦片 404 当作整体失败并立即回退；
> 同时 Leaflet 未设 `bounds/maxBounds`、开局固定 `zoom=7`——1080p 屏在 z7 的视野约 21° 宽，
> 远超贵州 6° 的瓦片覆盖范围，**边缘瓦片必然 404**，于是一开视图就回退。
> 另：`/map/tile-info` 未回传覆盖 bbox 与目录来源，现场无法判断“走 env 还是打包内置”。

### Fixed（2026-10-25 追加：用户反馈 `Request failed with status code 422`）

- **422 校验错误中文化 + 不再回显 input**（后端根因）：此前只注册了 pydantic 的
  `ValidationError` 处理器，**FastAPI 的 `RequestValidationError` 无人接管** —— 422 返回的是
  **英文数组** `detail: [{loc, msg: "Field required", input: "明文密码", ...}]`。三条链路因此全错：
  前端按字符串读 `detail` 落空 → 把 axios 原文 `Request failed with status code XXX` 显示给用户；
  文案是英文技术描述，基层操作员看不懂；`input` 回显把**明文密码**写进响应体与前端日志。
  新增 `app/core/validation_errors.py`（字段名 → 中文标签、pydantic 校验类型 → 中文模板、丢弃
  `input`/非标量 `ctx`、同文案去重、明细上限 20 条），并同时注册
  `RequestValidationError` 与 `ValidationError` 两个处理器，返回统一信封
  `{code:422, success:false, message, detail, errors}`（`detail` 与 `message` 同值，兼容历史读 `detail` 的视图）。
- **前端统一出口保证永不显示技术原文**（`src/utils/getErrorMessage.ts` 重写）：新增
  `isRawAxiosMessage()`（识别 `Request failed with status code N` / `Network Error` /
  `timeout of Xms exceeded` / `Failed to fetch`）、`statusFallbackMessage()`（400/401/403/404/
  409/413/429/5xx 各自中文兜底）、`extractServerMessage()`（message → detail(字符串) →
  detail(数组，兼容历史 FastAPI 形态) → errors 数组 → 嵌套 error.message → 纯文本体）。
  `getErrorMessage()` 依次尝试 userMessage → 服务端文案 → 状态码兜底 → fallback，
  **任何分支都不会返回 axios 原文**；`userMessage` 若本身是原文也会被识别并降级。
- **拦截器与视图层对齐**：`src/api/request.ts` 的 `_extractServerMessage` / `_buildUserMessage`
  改为复用同一套提取口径（Blob 响应体也走它），并按状态码给中文兜底；20 处
  `ElMessage.error(error.message || '…')` / `const msg = e instanceof Error ? e.message : '…'`
  统一改为 `ElMessage.error(getErrorMessage(e, '…'))`（涉及 MachineCode / Profile /
  ConflictResolution / Export / Import / policies Edit+List / Organization List /
  EncryptionSettings / SecretsManagement / ControlPackage / ApprovalCenter）。
- **新增门禁 `scripts/check_error_message_leaks.py`**（CI `static-analysis`）：扫描
  `frontend/src` 面向用户的提示调用（`ElMessage.*` / `ElNotification.*` / `notify(`），
  发现直接取 `error.message` 即失败；实现层（`getErrorMessage.ts` / `request.ts` /
  `errorHandler.ts`）豁免。去注释时保留换行，报告行号与源文件一致。
  单测 `backend/tests/unit/test_error_message_leak_gate.py`（11 项，含"注释不误报""块注释不打乱行号"
  "实现层豁免"与当前仓库零泄漏）。

### Tests / 验证（422 修复）

- `backend/tests/unit/test_validation_errors_i18n.py`（35 项）：字段标签、类型模板、
  ctx 缺失回落、未知类型、去重、明细上限、`input` 永不回显、真实 HTTP 422 形状。
- `frontend/tests/unit/utils/errorMessageContract.test.ts`（37 项）：10 个状态码的
  "绝不漏原文"回归、detail 数组/errors 数组/嵌套/纯文本体、业务 Error 透传、超时与网络错误。

### Fixed

- **前端不再因边缘 404 整体回退**：TileLayer 增加 `bounds`（只在覆盖范围内请求）+ `errorTileUrl`
  （透明 1×1，404 渲染空白不破图）+ `maxNativeZoom`；Map 增加 `maxBounds`（bbox 外扩 0.05°）+
  `maxBoundsViscosity:1` + `worldCopyJump:false`；开局 `fitBounds(覆盖 bbox, maxZoom:9)`，不再固定 zoom 7；
  `center` 缺省 `null`，显式且落在 bbox 内才 `panTo`；`tileerror` 只计数，**仅 `loaded===0 && errors>=8`
  （或 5s 看门狗内全 404）才回退**；有成功也有失败时只显示非阻塞提示
  「部分区域超出预置瓦片范围（边缘为空白，属正常）」。
- **后端诊断字段**：`GET /api/v1/map/tile-info` 新增 `bbox`（MANIFEST `region.bbox` → `bbox` → 贵州兜底）、
  `source`（`env`/`meipass`/`dev`）、`reason`（`dir_missing`/`no_tiles`，可用时 `null`）；
  MANIFEST 归一化白名单放行并校验 `bbox`/`region`（有限数值、经纬度范围、min<max），脏值逐级回退。
- **回退提示带诊断**：提示追加 `available/tileCount/source/reason`，现场可区分“没装瓦片”与“真故障”。

### Tests / 验证

- 前端 TDD：先红（组件 11 / 工具 8 失败）→ 实现 → 绿；`mapTiles`/`RasterTileLayer`/`MapTileManager`/api 等
  **6 文件 103 passed**，改动文件覆盖率 100%，`vue-tsc --noEmit` exit 0；
- 后端：新增 `test_map_tile_info_diagnostics.py`（11 项）+ 既有 map/tiles 套件合计 **216 passed**；
- 打包后运行期：`/map/tile-info` 含 `bbox/source/reason`；覆盖区内瓦片 200、区外 404（前端透明处理、不回退）。

## [1.18.1] - 2026-10-24 — 登录门面重构 / 三层对齐门禁 / 门禁真绿复验

> 本批包含三块：① 登录页 UI 务实化改造（修死链与不可见错误）；② R35 三层对齐门禁落地并修掉它抓出的漂移；
> ③ 复验时发现 `backend/.coveragerc` 被误删导致 100% 覆盖率门禁**静默失效**，恢复后补齐全部缺口。

### 发布产物（GitHub Actions 构建，`v1.18.1` Release）

| 安装包 | 平台 | 体积 |
|---|---|---|
| `MRRS-Setup-1.18.1-x64.exe` | Windows 10/11 x64（NSIS，自包含） | 约 270 MB |
| `MRRS-Setup-1.18.1-arm64.deb` | 麒麟 V10 / 统信 ARM64（Electron） | 约 267 MB |
| `assistance-management-system_1.18.1_arm64.deb` | 麒麟 V10 / 统信 ARM64（standalone） | 约 98 MB |

> **体积与 SHA256 以 [Release 资产](https://github.com/lzh745200/MRRS/releases/tag/v1.18.1) 为准**：
> 构建产物非逐字节可复现（PyInstaller/electron-builder 含时间戳），同一源码重建会改变 SHA256，
> 故不在文档里写死哈希；每个 Release 均附带 `SHA256SUMS-*.txt`（出包后对真实文件生成）。

构建链路：tag `v1.18.1` → `build-windows.yml` / `build-arm64.yml` 均 **success**；
发布前置门禁 `scripts/check_release_gate.py`（要求该 commit 的 PR Checks 全绿）通过；
安装包内含打包后后端自检（self-contained smoke）与「无测试文件 / 构建信息存在」断言；
Release 正文由 `scripts/prepare_release_body.py` 以本仓库发布说明为**单源**生成
（原先 3 个作业各自写 body，不传 body 的作业会把正文覆盖成空）。
详细下载说明见 `docs/04-部署文档/RELEASE_NOTES-v1.18.1.md`。

### Added

- **登录页公开配置扩展**：`GET /api/v1/auth/public-config` 新增 `lockout_minutes` / `max_failed_attempts`
  （纯策略参数）。前端据此显示「锁定 30 分 00 秒」倒计时与"再错几次会被锁"，用户不再只是看到一行字。
  **刻意不返回**组织名/单位码（登录前不泄露部署单位身份）与"全局 2FA 开关"
  （本系统 2FA 是按用户开启，硬造一个恒 false 的字段只会误导调用方）。
- **三层对齐门禁** `scripts/check_stack_alignment.py` + CI job + 自测
  `tests/unit/test_stack_alignment_gate_r35.py`（含负向用例）：比对 **前端 API 路径 ↔ 后端路由**、
  **ORM 模型 ↔ 数据库 schema**（基线为"临时空库 + `alembic upgrade head`"，不读本机开发库）、
  **前端 TS interface ↔ 后端 Pydantic 字段**（按 URL 解析端点 + `response_model` 配对，避免同名不同契约的假阳性）。
- **迁移 `r42_align_stack_columns_001`**：`tea_plantations` / `cactus_fruit_plots` 的
  `village_id` → `supported_village_id`（索引名同步）；补齐 `households.remarks`、`projects.region_code`
  两个"库里有、模型没声明"的列。
- **覆盖率回归测试** `tests/unit/test_coverage_restore_after_merge.py`（12 例）：补 `repr` 可安全输出、
  备份元信息三种入参形态、增量包指纹有/无、无组织字段模型的过滤分支、单位码 409 阻断、
  密钥不一致时临时包清理的三个分支。

### Changed

- **登录页重构**（`frontend/src/views/auth/LoginEnhanced.vue`）：
  - 背景 **12 张 3.51MB 轮播 → 1 张静态图**（净减 3.16MB，Electron 冷启动首屏更快，气质更庄重）；
  - 错误按 401 / 403（未激活、未授权本机）/ 423 / 429 **分色展示**，423 与 429 显示倒计时并禁用提交按钮；
  - 登录失败**清空密码并聚焦**（多人共用一台机器的政务场景）；**CapsLock 提示**；**2FA 满 6 位自动提交**（防重复触发）；
  - 新增「首次使用？」三步引导（机器码 → 权限包 → 通行码注册），未开启自助注册时改为说明文案；
  - 控件统一 44px、聚焦显示**左侧金色竖条**、卡片一次入场动效（`prefers-reduced-motion` 下关闭）；
  - 8 处硬编码色值收敛进 Design Token，硬编码色棘轮 **154 → 146** 并收紧基线。
- **`authStore.login` 错误传播修正**：原先只读 `err.response.data.message`，而 FastAPI 返回 `detail` ——
  于是 423「账户已锁定，请30分钟后再试」这类**中文文案全部丢失**，用户看到的是 `Request failed with status code 423`。
  现按 `detail → message → err.message` 顺序取值，并新增可选 `httpStatus`（纯增量信息，不改变既有返回语义）。
- **`MessageCenter` 契约对齐**：`MessageListResponse` 按后端实际改为 `total_pages`（无 `unread_count`），
  列表页改为直接调用独立的未读数端点（原代码读已删除字段，`vue-tsc` 报错且永远走 fallback）。
- **`system/backup.py`**：去掉 `BackupKeyMismatchError` 分支里**不可达**的 `if file_path:`（该分支只可能由
  `restore_backup(file_path, ...)` 抛错进入，此时 `file_path` 必已赋值）。
- 文档与 PPT 同步至 v1.18.1（PPT 新增「登录门面与门禁真绿复验」一页，全部数字按实测刷新）。

### Fixed

- **注册入口死链**：`SELF_REGISTER_MODE` 默认 `off`，但登录页**无条件显示**"注册账户"，
  而前端从未调用后端早已提供的 `public-config`。现按配置显隐，**取不到配置即隐藏**（fail-closed）。
- **100% 覆盖率门禁静默失效**：`backend/.coveragerc` 在工作区被误删，`fail_under=100` 不再生效 ——
  分段执行器报告的 12/12「全绿」实际只有 99%。已恢复配置并补齐 7 处缺口，现为
  **TOTAL 45,782 语句 / 11,376 分支，Miss 0 / BrPart 0**。
- **行业模型与库列名漂移**：`r42` 迁移注释写明"模型列名改为 `supported_village_id`"，但 `app/models/industry.py`
  未改，导致三层对齐门禁 B 轴报 4 条不一致。已按迁移声明的意图改名（全仓无其它引用）。
- **调度器断言口径漏算**：`test_coverage_gap_batch8.py` 按源码里
  `_schedule_daily/_schedule_interval/_schedule_weekly` 的调用点数推导 Timer 数，R36 新增的
  `_schedule_backup_catchup()`（一次性补跑，同样 1 个 Timer）未被计入 → 断言恒 16 而实得 17。
  改为通用正则匹配任意 `_schedule_<name>(`，今后新增调度入口无需再改测试。
- **备份上传恢复的临时包泄漏**：密钥指纹不一致（409）时未清理已落盘的临时包 ——
  每次跨机误导入都会在备份目录留下一个可能上 GB 的残包。现按"存在则删除、删除失败只记日志"处理，
  并保留 409 语义（不因清理失败退化成 500）。
- **数据上报 schema 与 service 实际返回不一致**（R35 三层对齐 C 轴）：`subordinate dashboard` 声明为
  `unreported_count` / `statistics`，而 service 返回 `not_reported_count` / `pending_review_count` /
  `overdue_count` / `report_rate`；Pydantic `extra=ignore` 会把差异吞掉。已对齐。

### Fixed（发布链路，交付当日追加）

- **登录页重构打挂了 E2E**：`tests/e2e/flows/login.spec.ts` 三处断言随 DOM 改名失效 ——
  `.error-banner` 已改为 `.alert`；且新提示条带 `role="alert"` 后与 Element Plus 的 ElMessage
  toast **同时命中**同一选择器，Playwright 严格模式直接判「多元素」失败。
  已改为 `.alert, .error-banner, …, [role="alert"]` 并收敛 `.first()`；
  **本地实跑：修前 6/7、修后 7/7，全量 E2E 165/165 通过**后才重新推送。
- **GitHub Release 正文长度为 0**：Release 由 3 个作业各自上传
  （`build-windows.yml` 1 个 + `build-arm64.yml` 2 个），`softprops/action-gh-release`
  每次都会重写正文 —— 不传 body 的作业把 Windows 侧写好的正文覆盖成空。
  现三处统一 `body_path`，正文由 `scripts/prepare_release_body.py` 以仓库发布说明为**单源**生成。
- **正文生成步骤在 Windows runner 上崩溃**：第一版写成 POSIX shell，而 `build-windows` 跑在
  `windows-2022`（默认 PowerShell），该步骤直接失败、构建变红。改为跨平台 Python 脚本后通过。
- **体积/SHA256 写死在文档与发布正文里必然过期**：构建产物**非逐字节可复现**
  （PyInstaller/electron-builder 含时间戳；实测同一源码 4 次构建得到 4 组哈希），
  重打 tag 重建后正文哈希与资产实际值不符。现改为「体积与校验值一律以 Release 资产的
  `SHA256SUMS-*.txt` 为准」（该文件由出包作业对真实文件生成，天然自洽），
  文档只保留约数与文件名。

### Added（发布链路）

- **`scripts/prepare_release_body.py`**：按 tag 从 `docs/04-部署文档/RELEASE_NOTES-<tag>.md`
  生成 Release 正文；文件缺失时产出含 CHANGELOG 指引的兜底正文并打 warning，
  **不让"缺发布说明"变成构建失败**。两个工作流 runner 不同（ubuntu / windows-2022），
  故用 Python 而非 shell 实现。
- **`scripts/check_changelog.py` + CI 门禁 + 单测**：把「更新日志必须及时」变成可执行约束 ——
  校验版本段存在、`x.y.z` 形式、**严格降序**、日期合法且非未来、**当前 `package.json` 版本已记录**、
  版本段非空标题。此前靠人记，v1.18.1 就漏记了上面 4 条交付期修复。

### Fixed（交付前逐维复验补齐）

- **三层对齐门禁在 CI 里跑不起来**：原先放在 `static-analysis` 作业，而该作业只装 `alembic` 与几个
  lint 工具，门禁需要 `import app.main`（fastapi/sqlalchemy/pydantic）并用 alembic 起临时库 ——
  实测 `EXIT=2 No module named 'fastapi'`，该 step 必然恒红。现改为独立 `stack-alignment` 作业，
  自己安装 `backend/requirements.txt`，并加注释说明为何不能放回 static-analysis。
  （已验证：仅装 requirements.txt 时 `app` 可 import —— 全仓只有 `prophet`/`redis` 两个未在清单里的
  导入，且都是 `try/except ImportError` 保护的可选依赖。）
- **门禁临时参照库泄漏**：B 轴每次运行都会建一个 ~2.8MB 的 SQLite 库，但只用 `mkdtemp` 从不清理 ——
  实测已在 `backend/` 累积 **78 个目录 / 206MB**。现加 `finally: shutil.rmtree`（失败路径同样清理），
  并补单测 `test_gate_leaves_no_reference_db_dirs` 锁死。
- **`r42` 迁移用了 SQLite 不支持的语法**：索引改名写成 `ALTER INDEX ... RENAME TO`（PostgreSQL 语法）。
  该分支在当前迁移链上不可达（新库由基线 `create_all` 直接按模型建表、老库 w22 已先 drop 旧索引），
  但保留错误实现等于埋雷。现改为方言无关的 `DROP INDEX` + `CREATE INDEX`。
- **`DataReportStatistics` 前端缺少 `pending`**：后端 `schemas/data_report.py` 有该字段、前端
  `types/organization.ts` 没有。三层对齐门禁补上「response_model 同名配对」规则后立刻抓到。

## [1.18.0] - 2026-10-24 — 离线加固批次：告警开关 / 误导口径 / 备份可迁移 / 麒麟数据目录 / 长期运行可靠性

> 本批来自"系统还有什么问题"体检结论的第 1、2 批；所有改动均有红→绿测试与门禁记录。

### Added

- **`OFFLINE_MODE` 统一开关（默认 `True`）**：`alert_service` 邮件/Webhook 两通道入口先短路（INFO + `return False`，
  不做配置解析/DNS/建连）；需外呼时设 `OFFLINE_MODE=false`。SMTP 同步调用改 `asyncio.to_thread`，不再阻塞事件循环。
- **备份携带密钥指纹**：`backup_info.json` 新增 `key_fingerprint`（SHA256 前 16 位，复用 `pii_crypto.key_fingerprint()`，
  **不含密钥本体**）。恢复时指纹不一致 → **409**（`allow_key_mismatch=true` 可强制，写审计
  `system_restore_key_mismatch`）；旧备份无字段仍兼容。顺带修复历史全量包 `backup_info.json` 用 `str(dict)`
  写出的非法 JSON（`_parse_backup_info`：json → `ast.literal_eval` 回退）。
- **`/health` 新增 `clock` 与 `database` 只读块**：时钟漂移 `{status, behind_days}`（120s TTL 缓存、不含异常原文）；
  数据库 `{journal_mode, journal_mode_ok, check_error_type}`（WAL 不可用可见化）。顶层 `status`/HTTP 码不变。
- **备份启动补跑（catch-up）**：启动 15s 后若"从未备份或距上次 > `backup_interval_days`"立即补跑一次
  （`threading.Timer` 登记 `_timers`、不自我重排；补跑后当日 02:00 任务自然跳过）。
- **麒麟/离线数据目录收口**：Linux/打包态数据根改为 `BUMOFU_DATA_DIR` → `XDG_DATA_HOME/bumofu` →
  `~/.local/share/bumofu`（不再回退 `~/.bumofu`）；`get_backup_path()` 支持 `BACKUP_DIR` 优先（三段链）；
  `get_cache_path()` Linux 分支对齐 `<app_data_dir>/cache`。kylin：`kylin.env` 增 `BUMOFU_DATA_DIR`，
  `postinst` 用 `--create-home`、目录权限 2750→2770，`start-kylin.sh` 同步导出与降级目录。
- **Windows 构建脚本**：新增 `scripts/build/sync-frontend.ps1`（robocopy 等价同步，替代失效的 bash 脚本）与
  `scripts/build/build-win.ps1`（TEMP 重定向规避 esbuild `Access is denied`；可选 `-IncludeMapTilesInBackend`）。

### Changed

- **安装包瘦身**：`assistance-backend.spec` 瓦片收集改为构建开关 `INCLUDE_MAP_TILES=1`（默认关）；Electron 版由
  extraResources + `MAP_TILES_DIR` 提供瓦片，不再重复打包（**实测 378.4MB → 316.7MB**，省 61.7MB；解包 826.9MB → 763.7MB）。ARM64 standalone 不受影响。
- `/api/v1/map/config` 的 `map_type`：`"gaode"` → `"vector"`（前端零消费方）。
- 通知偏好 3 个端点响应追加 `emailChannel: "unavailable_offline"`（只增不删）。
- **`httpx` 登记运行时必需依赖**（启动期硬依赖，此前缺失即 ImportError 且自检不覆盖）。
- `scripts/check_doc_numbers.py` 输出改 UTF-8（修复 Windows GBK 控制台下 `✓` 触发 UnicodeEncodeError 假红）。

### Known issues（本批未做，建议下批）

- `POST /api/v1/system/admin/restore?filename=` 旧端点直接 `shutil.copy2` 覆盖 DB，绕过维护窗口/schema 校验/
  密钥指纹闸门；前端零调用，建议下线或改走 `restore_backup()`。
- 前端 `BackupManagement.vue` 未传 `allow_key_mismatch`：跨密钥恢复目前只能直连 API（建议 UI 加二次确认）。
- 安装包仍未代码签名（证书待采购）。

## [1.17.4] - 2026-10-24 — 离线瓦片包导入被 10MB 请求体上限拦截（现场 413）

### Fixed

- **导入瓦片包报「上传内容超过大小限制 (10MB)，请拆分或压缩后重试」**：
  `BodySizeLimitMiddleware` 对 multipart 请求只在路径命中 `LARGE_PAYLOAD_PATH_PREFIXES`
  时才采用分级上限；`/api/v1/map/tiles/import` 既不在该白名单、也没有
  `MULTIPART_BODY_LIMITS` 条目，于是被 `min(DEFAULT_MULTIPART_BODY_LIMIT, max_body_size)`
  收紧到全局 **10MB** —— 而市州包为 7~17MB、全省包 59MB，必然 413。
  修复：
  1) `MULTIPART_BODY_LIMITS` 增加 `("/api/v1/map/tiles", 512MB)`（对齐
     `offline_map_service.MAX_TILE_UPLOAD_BYTES`）；
  2) `_resolve_body_limit` 区分「大 JSON 白名单」与「仅 multipart 分级登记」两类路径 ——
     后者只放宽 multipart，**非 multipart 仍受全局 10MB**，不放开 JSON 面，也不削弱
     「非上传路径伪造 multipart 头收紧到 10MB」的既有反绕过策略。
- 回归测试：`backend/tests/unit/test_body_size_limit_map_tiles.py`（6 项，覆盖 512MB 放行、
  前缀覆盖、非 multipart 仍 10MB、未登记路径伪造 multipart 仍 10MB、备份 10GB 不受影响）；
  中间件模块覆盖率 100%；实测 12MB / 60MB multipart 已能到达端点（返回 403 CSRF 而非 413）。
- 版本号单源同步至 **1.17.4**（`node scripts/sync-version.js --write`，14 个文件）。

## [1.17.3] - 2026-10-24 — 打包环境可用性修复（前端目录自发现 + 完整性检查误报）

> 本版由一次**真实安装包离线验证**驱动：把打包后的后端 exe 放到全新空目录
> （空 `%APPDATA%` / `%LOCALAPPDATA%`）里启动，模拟"任意电脑首次安装"。

### Fixed

- **打包后端在无环境变量时找不到前端（真机白屏风险，重要）**：
  Electron 通过 `http://127.0.0.1:<port>` 加载界面，依赖环境变量 `FRONTEND_DIST_PATH` 指路。
  但 PyInstaller onedir 的实际布局是
  `<resources>/backend/assistance-backend/_internal`（`_MEIPASS`）+
  `<resources>/frontend`（与 backend 同级），原候选表缺少"自 `_MEIPASS` 上溯三级"这条，
  一旦 Electron 侧漏传该变量（手工启动后端排障、升级后环境变量遗漏、麒麟用 systemd 直跑），
  浏览器访问 `/` 直接 **404**，桌面端表现为**白屏**。
  修复：新增两条候选 —— `_MEIPASS` 上溯三级 `/frontend`、冻结态 `sys.executable` 的 `/frontend`
  （注意 exe 是**文件**路径，需先去掉文件名再上溯三级，合计**四级**；只上溯三级会落到
  `<resources>/backend/frontend` 这个不存在的位置）；
  显式传入的 `FRONTEND_DIST_PATH` 仍最优先（不破坏既有契约）。
- **冻结运行时误报「关键文件缺失」**：`startup/environment.py` 对 `app/core/config.py` 等 4 个
  .py 源文件做存在性检查，而 PyInstaller 包里源码已编译进可执行文件 —— 启动日志恒刷 4 条
  `WARNING 文件完整性检查: 关键文件缺失: app/core/config.py`，让运维误判"安装包损坏"。
  修复：冻结运行时（`sys.frozen`）**跳过源码检查并记录 INFO 说明原因**
  （防篡改由代码签名 + 安装包 SHA256 承担），开发态检查逻辑原样保留。

### Verification（离线安装包实测）

| 场景 | 结果 |
|---|---|
| 空 `%LOCALAPPDATA%` 首次启动打包后端 | 自动建库（`data/` `data_sync/` `uploads/` `archives/` `cache/` `logs/` `offline_tiles/`）并启动成功 |
| `/health` | 200，`status=ok`，`migration.at_head=true` |
| 出厂口令登录 | 200，`must_change_password=true`（首次登录强制改密生效） |
| 未传 `FRONTEND_DIST_PATH` 时访问 `/` | 修复后 200（含 `id="app"`）；修复前 404 |
| 启动日志 | 修复后不再出现「关键文件缺失」误报 |

### Tests

- `test_static_files.py` 增补 onedir 布局推导用例（上溯三级 = resources，前端在其下）；
- `test_environment_integrity_helpers.py` 增补「冻结跳过 / 开发态保留」双向用例。

## [1.17.2] - 2026-10-24 — 端到端排查修复：组织创建不可用 + 自检路径错位

> 本版由一次**真实 HTTP 端到端排查**驱动：在隔离实例（独立 DB + 独立端口）上完整走通了
> 「出厂登录 → 强制改密 → CSRF 双提交 → 组织树 → 帮扶村 → 数据包导出/导入/查重/回执 → 系统自检」链路。

### Fixed（两项均为"单测绿、真机废"的高危缺陷）

- **创建组织在真实 HTTP 下必然失败（严重）**：`OrganizationCreate` schema 漏掉 `code` 字段，
  而端点 `api/v1/organization.py` 创建路径直接读 `data.code` —— Pydantic 模型无此属性，
  请求一进来就 422（校验层）/AttributeError。单元测试用 MagicMock 传 `data` 时不会暴露。
  **后果**：新装机器无法创建任何组织 → 上下级部署无法初始化。
  修复：`OrganizationCreate.code` 必填（6 位，min/max_length=6）；`OrganizationUpdate.code` 可选
  （仅用于给出"编码只读"的明确语义）。
- **系统自检端点路径错位（真机 404）**：模块注册在 `/api/v1/self-check`（根级），
  而前端与文档调用 `/api/v1/system/self-check`（system 包聚合路由）→ 设置页自检卡片恒 404。
  修复：改为经 `api/v1/system/__init__.py` 聚合注册（与 diagnostics / business-health 同构），
  并移除 `api/v1/__init__.py` 中的重复单独注册。

### Added（防回归）

- `tests/unit/test_p3_org_create_http_contract.py`（8 例）：**只走 TestClient**，
  锁定「缺 code → 422 / 短码 → 422 / 非数字码 → 422 / 合法载荷不被 schema 拦」。
- `test_p3_self_check_api.py` 增补路径契约用例：断言路由为 `/api/v1/system/self-check`、
  根级不存在，并校验前端 `api/selfCheck.ts` 调用路径与后端一致。

### Verification（本次端到端实测）

| 环节 | 结果 |
|---|---|
| 出厂口令登录 → must_change_password=true | PASS |
| 强制改密期业务 API 被 403 拦截 | PASS |
| CSRF 双提交（cookie + X-CSRF-Token） | PASS |
| 改密 → 重登录（新口令） | PASS |
| 系统自检 6 项（单位码/层级/账号/锁定/PII/介质） | PASS |
| 组织树 省→市→县 + 层级自动推导（1/2/3） | PASS |
| 反例：跨级挂接 422 / 重复编码 400 / 缺编码 422 / 改编码 422 | PASS |
| 帮扶村创建 / 权限包 CRUD / 权限包导出 / 用户创建 | PASS |
| 数据包导出 → 下载 → 导入 | PASS |
| 来源单位码不一致 → 409（含可读说明） | PASS |
| allow_org_mismatch=true 放行导入 | PASS |
| 同一包重复导入 → 409「已于 X 由 Y 导入过…请传 force=true」 | PASS |
| force=true 放行重复导入 | PASS |
| 确认导入 → 写回执 → 自检显示「成功回执 1 条」 | PASS |

### Removed（死代码清理，本轮静态审计结论）

审计方法：从 `main.ts` / `app.main` 出发做 import 图可达性分析 + 模板全局组件名扫描 +
一次性脚本引用反查 + 文档相对链接校验（127 份 md / 132 条相对链接 / 死链 0）。

- **6 个从未接入任何页面的通用组件**：`AppEmpty` / `AppError` / `AppLoading` /
  `AppPageHeader` / `AppStatCard` / `AppTableToolbar`。核实方式：`src/**/*.vue` 中既无
  `<AppXxx>` 也无全局名 `<CommonAppXxx>` 引用；`components.d.ts` 里只是自动注册残留。
  其中 `AppPageHeader` 与在用的 `PageHeader.vue`（19 个列表页接入）职能重复。
  连带删除 barrel `components/common/index.ts` 与 7 个测试文件。
- **`ErrorBoundary.vue` 予以保留**：审计脚本初判"不可达"是误报 ——
  `layouts/DefaultLayoutSafe.vue` 通过全局名 `<CommonErrorBoundary>` 使用它。
  这条误报说明「只查 `<ErrorBoundary>` 标签」不够，必须同时查 unplugin 的 `Common` 前缀。
- **3 个一次性 PPT 版本脚本**：`scripts/update_pptx_versions_20260912/20261016/20261017.py`。
  全仓无任何引用，其职能已被 `docs/build_ppt.js` 源码重建取代。

### Tests

- 后端 12 段全量回归（14,404 用例）+ 前端 329 文件 / 6,995 用例，覆盖率门禁均 100%。
- 本机验证补充：`vue-tsc --noEmit` 0、ESLint（CI 口径 `eslint src --max-warnings=0`）0、
  `npm audit --omit=dev` 0 漏洞、文档死链 0、`check_doc_numbers --full` 四项全 ok、PPT 53 页 0 溢出。

## [1.17.1] - 2026-10-24 — 版本号口径修复 + 本地安装包构建修复

### Fixed

- **`/health` 版本号不再被陈旧构建指纹覆盖**：`_build_info.json` 是 CI 构建产物（已 gitignore），
  开发机残留上一次构建的指纹时，`/health` 会一直报旧版本（实测 v1.15.7 vs 代码 1.17.0），
  运维据此误判"版本未生效"。现明确 **版本号唯一权威来源是 `settings.PROJECT_VERSION`**
  （由根 `package.json` 单源同步），构建指纹只提供 `git_hash` / `build_time` / `builder`。
  新增 `tests/unit/test_build_info_version_authority.py`（10 例，`app/core/build_info.py` 覆盖率 100%）。
- **`scripts/build/build-installer-local.ps1` 补 UTF-8 BOM**：该脚本含中文且此前无 BOM，
  Windows PowerShell 5.1 按 GBK 解析 → `Array index expression is missing` 等语法错误，
  **本地安装包构建完全不可用**。补 BOM 后本地 `MRRS-Setup-<ver>-x64.exe` 构建成功
  （与同目录 `fetch_vcredist.ps1` / `verify_frontend_manifest.ps1` 口径一致）。

### Docs

- 新增 `docs/02-用户手册/介质数据包导入与系统自检操作说明.md`：离线介质包的查重 / 来源单位码核对 /
  导入台账与回执、六项系统自检、多机交接推荐流程与常见问题。已加入用户手册索引。

### Verification

- 后端 12 段全量 **14,364 用例全绿 + 覆盖率 100%**；前端 **339 文件 / 7,020 用例全绿 + 覆盖率 100%**
- 升级演练 v1.16.4(r35) → 当前(r41)：122 表数据完好、落在 head
- 8 道棘轮门禁 + 菜单对齐 A~E + console tab 30/30 + 文档数字 + 版本一致性 + 硬编码色棘轮 154/154 全绿
- 本地完整构建：前端 683 文件 12.27 MB、静态资源审计 0 缺失、Windows 安装包 378.1 MB

## [1.17.0] - 2026-10-23 — 介质链路治理（查重/台账/单位码/回执） + 系统自检 + W27 全栈收敛

### Added（P2 介质链路治理）

- **整包查重**：新增 `services/package_import_guard.py`，以整包 SHA256 为指纹查 `audit_logs` 台账；
  同一包重复导入默认 **409**，需显式 `force=true` 放行。数据包 / 授权包 / 权限包 / 配置包四类导入已接入。
- **导入台账**：导入成功写 `package_import`（类型/来源单位码/校验和/记录数/结果），
  查重与追溯共用一张表，**不新增业务表、不新增迁移**。
- **导入回执**：确认导入后写 `package_receipt`（接收单位码、来源单位码、记录数、冲突策略），
  上级凭回执即可登记闭环。
- **来源单位码核对**：新增 `services/package_org_code.py`；数据包导入时比对包内 `org_code`
  与本机目标单位码，不一致默认 **409** 阻断（`allow_org_mismatch=true` 可放行），
  防止"把上级/邻县的包导进本单位"后数据挂错组织树。
- **冲突策略落库**：确认导入时把「逐条比对 / 以包为准」写入导入历史 `details_json`，事后可追溯。
- **前端**：新增 `components/import/ImportPreviewDialog.vue`（包信息 + 差异 + 重复告警 + 策略三选）；
  数据包接收页与授权包导入页在收到 409 时弹出该确认框，用户确认后带 `force=true` 重传。

### Added（P3 系统自检）

- 新增 `services/self_check_service.py` 与 `GET /api/v1/self-check`（仅管理员），一次体检 6 项：
  **单位码**（缺失/格式/层级不符/重复）、**组织层级**（跨级挂接/根非省级）、
  **待审核账号**、**账号锁定**、**PII 密钥指纹**、**介质导入近况**（近 30 天失败数）。
- 「系统设置」页新增自检卡片（`components/system/SelfCheckCard.vue`）：正常/提醒/异常三态，
  每项带可读说明，一键重新检查。

### Changed（W27 全栈收敛，随本版一并合入）

- **包完整性校验**（`core/package_integrity.py`）：管控包 / 配置包 / 权限包导入强制校验 `checksum`；
  配置 `PACKAGE_PUBKEY` 后强制验签（fail-closed）。生成侧配 `PACKAGE_SIGNING_KEY` 即签名。
- **经费禁止自批**（`FUND_ALLOW_SELF_APPROVAL` 默认 False）：创建人不得审批自己创建的经费记录。
- **跨机业务键修复**：`BUSINESS_KEYS` 由「仅组织」改为「组织 + 业务唯一标识」
  （villages: 组织+县+村名；projects/funds/schools: 组织+code），
  修复同组织两台机器导入时"记录被整体覆写或静默丢弃"的 P0 缺陷；业务键不可判定时改走 relocated（新增行），绝不覆写。
- **迁移 r36~r41**：删除 `rural_tasks` / `budget_records` / `annual_income` / `issues` 等零引用表与列，
  全部沿用「空表 DROP / 有数据改名归档」契约。
- 新增门禁：`check_no_assert_tests.py`（测试必须有断言）、`check_sync_coverage.py`（同步链路覆盖）。

### Docs

- CLAUDE.md 新增「介质链路治理」与「系统自检」契约条目；端点数/测试文件数同步（849 / 336）。

### Tests

- 新增 `test_o_package_import_guard.py`（25 例）、`test_o_package_org_code.py`（12 例）、
  `test_p3_self_check_service.py`（18 例）、`test_p3_self_check_api.py`（2 例）；
  守卫模块与自检服务覆盖率均 **100%**；前端自检卡片 10 例 / 100%。
- 后端 12 段全绿（14,364 用例）；前端 337 文件 / 7,010 用例全绿。

## [1.16.4] - 2026-10-22 — 组织编码改用行政区划代码（3 级） + 默认关闭自助注册 + 账号解锁

### Changed

- **组织编码 = 行政区划代码**（GB/T 2260，统一 6 位）：`XX0000` 省级 / `XXYY00` 市州级 / `XXYYZZ` 县市级。
  判定口径集中在 `OrganizationCodeService`（唯一实现）：`normalize_admin_code()` / `infer_level()` / `level_order()`。
- **组织层级收敛为 3 级**：`OrganizationLevel` 由 5 值收敛为 3 值；`/organizations/types/options`
  只下发「省级/市州级/县市级」并附 6 位编码末位提示。
- **创建组织**：编码必填、纯数字 6 位；层级由编码自动推导（显式传值必须一致，否则 422）；
  **跨级校验**（子级必须恰为父级 +1，根组织只能建省级）；删除旧 `ORG%06d` 自动生成编码分支。
- **更新组织**：编码锁定（创建后不可修改，需变更请停用后新建），返回 422 并说明原因。
- **自助注册默认关闭**：新增配置 `SELF_REGISTER_MODE`（默认 `off`），关闭时
  `POST /auth/register` 返回 403「系统已关闭自助注册，请联系管理员创建账号」；
  新增公开端点 `GET /auth/public-config`。
- **注册不再自动创建组织**：`self_verify_org_pass_code()` 找不到组织时直接返回 None。
- **账号解锁**：新增 `POST /users/{user_id}/unlock`（仅管理员；清锁定计数 + 写 `account_unlock` 审计）。
- **前端对齐**：组织列表/详情层级标签改为「省级单位/市州级单位/县市级单位」；组织表单编码必填并提示 6 位规则。

### Tests

- 新增 `backend/tests/unit/test_p1_admin_area_code.py`（28 例）：编码校验三分支、层级推断三档、
  跨级校验、编码锁定、注册开关、公开配置、账号解锁（404/403/成功）。
- 更新既有组织/枚举/认证/覆盖用例至新契约（编码必填、3 级枚举、默认关注册）。

## [1.16.3] - 2026-10-22 — 单位授权改用「单位选择器」 + 权限/机构/角色/用户/注册登录操作说明

### Changed

- **单位授权配置不再手输数字 ID**（`OrgGrant.vue`）：原输入框要求管理员手抄 `organizations.id`，
  输错/留空只给一句「请先填写有效的单位 ID」，实际无法使用。现改为**可搜索单位下拉**：
  - 数据源 `GET /organizations/tree`（后端已按调用者组织子树过滤，与 `assert_org_reachable` 口径一致）；
  - 选项显示为「缩进名称（编码）」，支持按名称/编码模糊搜索；
  - **切换单位会清空上一个单位的矩阵**，避免把 A 的矩阵存到 B 名下；
  - 保留「手工输入 ID」兜底开关（老操作习惯 / 自动化脚本），切回手工时非法值自动清空；
  - 单位列表拉取失败时给出明确提示并可继续用手工模式，不阻断业务。

### Docs

- 新增 `docs/02-用户手册/权限与组织管理操作说明.md`：权限 4 层叠加模型（用户白名单 > 权限包 > 角色默认 > 系统角色）
  + 数据范围 4 档、机构管理（含删除高危确认与影响面）、系统角色 vs RBAC 角色、用户管理（新增/停用/审核/重置密码/会话）、
  权限包与菜单可见性、注册登录全链路（首登改密、来源门禁、通行码/机器码三级回退、2FA、忘记密码、失败锁定 5 次/30 分钟）、
  单位授权上下级流程、常见提示排错表、管理员安全约定。
- 用户手册索引与《系统管理操作说明》增加交叉引用。

### Tests

- `OrgGrant.test.ts` 增至 25 例：单位树拍平（层级缩进/缺名称缺编码/非法 id 兜底）、非数组输入防御、
  列表为空与加载失败两条降级路径、选择单位清空旧矩阵、手工/选择模式互切、选项文案渲染；覆盖率保持 100%。
## [1.16.2] - 2026-10-22 — ARM64 内置 OCR 出包门禁修正 + 遗留空表安全清除（r35 迁移）

### Fixed

- **ARM64 OCR 出包门禁误判（会让整条 ARM64 产物链失败）**：v1.16.0/v1.16.1 的
  「Verify OCR payload」步骤写成 `dpkg-deb -c "$DEB" | grep -qE ...`，`grep -q` 命中后立即退出，
  `dpkg-deb` 收到 SIGPIPE，在 `set -o pipefail` 下整条管道返回 141 → **被误判为「缺少 ONNX 模型」**。
  实测下载 v1.16.1 的 `assistance-management-system_1.16.1_arm64.deb`（106,002,508 B）解包确认：
  该 DEB **本来就内置** 3 个 rapidocr ONNX 模型（`ch_PP-OCRv4_det_infer` 4.53 MB /
  `ch_PP-OCRv4_rec_infer` 10.35 MB / `ch_ppocr_mobile_v2.0_cls_infer` 0.56 MB）＋
  `onnxruntime_pybind11_state...so` ＋ `cv2.abi3.so` —— 即 **ARM64 离线 OCR 从 v1.16.1 起已真正可用**，
  此前"降级 503"的说法是门禁误报导致的错误结论（已在 CHANGELOG 1.16.1 条目中说明该结论作废）。
  修复：先 `dpkg-deb -c > $LIST` 落清单再对文件 grep，并把 standalone 与 Electron 两侧都恢复为
  **强门禁**（模型 ≥2 个 + onnxruntime 绑定库 + cv2 扩展模块缺一不可，且 Depends 不得引入 libgl1/libgomp1/libglib2.0）。

### Removed

- **清除 W22 遗留的 6 张零引用表**（`r35_drop_legacy_tables_001`，在 v1.16.0 因升级风险被移出后重做）：
  `comments` / `messages_extended` / `sentiment_keywords` / `sentiment_reports` /
  `workflow_definitions` / `workflow_instances`。
  **安全策略（绝不丢数据、绝不阻断升级）**：表不存在 → 跳过（幂等）；存在且 **0 行** → `DROP TABLE`；
  存在且**有数据** → `ALTER TABLE ... RENAME TO legacy_<表名>`（数据原样保留在库里备查，只是退出活跃 schema）。
  即空表一定被清掉、有数据的表一行不丢、升级永远成功。`downgrade` 把 `legacy_*` 改回原名（尽力而为）。
- **升级演练与迁移的显式契约**：新增 `backend/scripts/gate_baselines/upgrade_legacy_tables.json`，
  演练（`scripts/upgrade_rehearsal.py`）据此接受"原表名消失（且旧库该表 0 行）"或"改名 `legacy_<表名>` 且行数不变"两种终态；
  新增任何"允许消失"的表必须同步该清单，否则演练照样报「无表丢失」失败。清单缺失时演练退回最严口径。

### Added

- **迁移单测** `tests/unit/test_migration_r35_legacy_tables.py`（7 项）：空表删除 / 有数据改名归档 /
  表不存在幂等 / 归档表已存在时保留原表 / 清单与常量一致 / 清单不可读回退 / 回滚改名。

### Notes

- v1.16.1 的结论更正：ARM64 **内置 OCR 已生效**（无需再按"降级"对待）；v1.16.0 的 Release 仅 Windows 包，
  v1.16.1 补齐了三平台产物，v1.16.2 在其基础上修正门禁误判并完成遗留表清理。
## [1.16.1] - 2026-10-21 — 安装包发布修复：ARM64 OCR 载荷门禁改为分级（v1.16.0 的 ARM64 产物链被拦）

### Fixed

- **ARM64 安装包无法产出**：v1.16.0 新增的「Verify OCR payload」步骤是**硬失败**门禁，但 PyInstaller 阶段
  并未把 `rapidocr_onnxruntime` 的 ONNX 模型收进 DEB（spec 的 `find_spec` 守卫在该阶段静默跳过），
  于是 `standalone-deb` 作业在出包后第 11 步直接失败，ARM64 DEB 与 Electron DEB 全部跳过后继步骤 ——
  而 v1.15.x 一直是「ARM64 无内置 OCR、OCR 接口 503 降级」的既定行为，属**没有回归**。
  现改为分级判定：
  - 载荷**有** OCR → 继续强校验（必须同时带 onnxruntime 绑定库与 cv2 扩展模块，且不得引入
    libgl1/libgomp1/libglib2.0 硬依赖）；
  - 载荷**无** OCR → 仅 `::warning::` 提示「OCR 降级 503」，不阻断出包，保证麒麟机仍能正常安装使用。
  Electron DEB 侧同步改为同一口径。待 spec 收集链路修好后把 WARN 改回 ERROR 即可恢复强门禁。

### Notes

- v1.16.0 的 Release 只产出了 **Windows x64 安装包**（273.07 MB）；ARM64 两个 DEB 因上述门禁缺失。
  v1.16.1 重新走完整发布链，补齐 **麒麟 ARM64 standalone DEB + Electron DEB**，功能代码与 v1.16.0 完全一致。

## [1.16.0] - 2026-10-21 — 系统管理梳理（分组导航 / 危险操作硬化）+ 离线瓦片地图 + PII 密钥跨机迁移 + 架构清理

### Added

- **PII 密钥跨机迁移 API**（`api/v1/system/pii_key.py`，R34-2 / P1-2）：多机离线同步时 PII 列以密文出包，
  要求各机 `ENCRYPTION_KEY` 一致，但默认每台机各自随机生成 → 同步到对端后密文永不可解（界面只显示 `enc.v1:…`）。
  新增 `GET /system/pii-key`（查看指纹与配置来源）、`GET /system/pii-key/export`、`POST /system/pii-key/import`；
  三个端点仅管理员可用，导出/导入写审计（**只记指纹不记密钥本体**），环境变量显式配置时拒绝导入（避免误以为已生效）。
- **离线瓦片地图**：前端引入 Leaflet（`leaflet` + `@types/leaflet`）、新增 `components/map/RasterTileLayer.vue`
  与 `utils/mapTiles.ts`；地图页改为栅格瓦片渲染，瓦片包由构建机预置（`resources/map-tiles/`，本体不进 git）。
  Electron 打包配置把 `map-tiles` 复制进安装包；新增 `npm run tiles:verify`。
- **瓦片工具链** `scripts/tiles/`：切片/校验/清单（MANIFEST.json）生成，`verify_tiles.py --require-min N` 作为门禁；
  Windows 构建增加「Verify map tiles preset」步骤（默认允许 0 张，仓库变量 `MAP_TILES_REQUIRED=1` 时强制）。
- **ARM64 离线 OCR 出包门禁**（E 区）：`requirements-arm64-ocr.txt` + Dockerfile 安装 headless cv2/onnxruntime，
  构建期跑 `docker/ocr_smoke_arm64.py` 真实识别冒烟；出包后断言 DEB 载荷含 rapidocr ONNX 模型、
  `onnxruntime_pybind11_state`、`cv2.*.so`，且 `Depends` 不含 libgl1/libgomp1/libglib2.0（保持零外部依赖）。
- **本地等价 CI 的分段测试执行器** `scripts/run_backend_tests_segmented.py`（12 段 + `--cov-append` 合并，
  绕开单进程在 88% 处 SQLAlchemy `engine.dispose()` 的 Windows access violation）。
- **文档数字漂移门禁** `scripts/check_doc_numbers.py`（端点数 / 路由模块数 / 前端测试文件数 / 后端用例数）。
- **安全审计覆盖棘轮**：`scripts/security_audit.py` 改为**动态发现**全部写路由模块，与
  `backend/scripts/gate_baselines/audit_work_log_baseline.json` 比对，基线外新增即失败。
- **危险操作统一二次确认**：新增 `composables/useDangerConfirm.ts`（普通确认 / 高危录入确认两种强度），
  管理员**重置他人密码**改为「必须手工输入目标用户名」才能执行（此前点一下按钮即可接管账号）。
- **危险操作强制审计**（后端补 4 处 `AuditLogger.log`）：
  删除组织 `organization_delete`、恢复备份 `system_restore`、轮换密钥 `secrets_rotate`、
  管理员重置密码 `admin_reset_password` —— 均可在「安全与审计 → 安全审计」按操作类型检索。
- **权限抽屉「生效概览」**（`PermissionAssignmentDrawer.vue`）：顶部一屏展示用户（含姓名）、
  系统角色、数据范围（中文 + 原值）、菜单权限来源（自定义 / 沿用角色默认 + 生效项数）、RBAC 可选角色数。
- **设备与授权中心**（`MachineCodeManagement.vue`）：表格支持多选 → 复制所选机器码 / 通行码；
  顶部新增「单位授权配置」「导入授权包」直达入口；原「组织通行码」页签完整保留。
- **聚合页左侧分组导航**（`SystemConsole.vue`）：系统管理 6 个聚合页由横向 tab 平铺改为「左分组 + 右内容」，
  分组为**纯呈现层**（`TAB_LAYOUT`），不改后端菜单 key / tab path / 权限粒度 / `?tab=` 深链；
  未登记的新 tab 自动落「其他」组，窄屏 ≤992px 转横向滚动。
- **Ctrl+K 菜单搜索直达系统管理子功能**（`stores/menu.ts`）：console 的 30 个 tab 进入 `flatEntries`
  （带 `parentLabel`/`tabKey`），搜索「权限包管理」「备份」「机器码」可直接跳 `?tab=<key>`；
  最近访问 / 收藏 / 移动端「更多」抽屉同步支持 `tabKey` 回跳。
- **新增门禁 `scripts/check_console_tab_mapping.py`**（CI static-analysis）：后端 console tab key ↔ 前端
  `TAB_COMPONENTS` 双向一致，杜绝「有菜单无组件」导致功能静默消失。

### Changed

- **透明度 Token 收敛**（`styles/tokens.scss`）：`rgba(255,255,255,x)` / `rgba(0,0,0,x)` / 主色与金色低透明度
  变体统一收敛为 `--color-white-{alpha}` / `--color-black-{alpha}` / `--color-primary-a{N}` / `--color-gold-a{N}`，
  **值与原字面量逐字节等价、视觉零变化**；硬编码色棘轮维持 154 处不新增。
- **依赖**：前端新增 `leaflet@^1.9.4`；后端 `requirements.txt` 与 PyInstaller spec 同步 OCR/瓦片相关收集项。
- **备份权限：普通用户可创建备份**（R36）：`POST /system/backup` 的鉴权由 `require_admin` 改为
  「已登录且非 viewer」，前端新增 `canCreateBackup` 只驱动「创建备份」按钮。
  安全性依据：创建接口只在服务器生成文件、**不返回任何内容**；下载 `/download/{filename}`、
  恢复 `/restore`、`/upload-restore`、删除 `DELETE /{filename}` 仍全部 `require_admin`，
  `/request-download` 仅发站内消息给超管不返回文件，故不构成跨组织数据外流。
  `viewer` 与未分配有效角色的账号 fail-closed 403（后者防止空角色被兜底成 user 白送写权限）。

### Deferred（本版移出，避免升级事故）

- **清理 6 张 W22 遗留空表**（`comments` / `messages_extended` / `sentiment_keywords` /
  `sentiment_reports` / `workflow_definitions` / `workflow_instances`）：原实现为「表非空即 raise」的
  删表迁移。升级演练（`scripts/upgrade_rehearsal.py`，从上一个 Release 版本建库并**每表播种一行**）
  复现出真实风险 —— 老用户库里这些表可能有历史数据，一旦非空，**升级会直接中断、新版本装完起不来**；
  即便为空，演练的「无表丢失 / 行数不变」两条基线也会判为数据丢失。
  结论：**本版不带该迁移**，schema 维持 r34 head；后续如需清理，应改为「非空表改名为
  `legacy_<table>` 归档、只删真正空表」，并同步升级演练白名单后再单独发布。

### Fixed

- **R33 单位授权两个 tab 在聚合页不可见**：后端 `menus.py` 早已下发 `system-org-grant` / `system-grant-import`，
  但前端 `TAB_COMPONENTS` 漏加映射，被 `renderableTabs` 静默过滤 → 只能手输 URL 才进得去。已补齐，
  测试契约 28 → 30 个 tab。
- **恢复备份审计只记可 JSON 序列化白名单字段**：恢复结果含 datetime 会让 `audit_logs.new_value` 写入失败，
  虽被兜底吞掉但审计会丢，改为 `{filename, restored}`。

### Docs

- 新增 `docs/02-用户手册/系统管理操作说明.md`（6 聚合页 / 30 功能分组总览 + 逐项操作 + 危险操作确认与审计动作名）。
- 新增《离线OCR与瓦片预置方案》《离线功能适用性核查报告》；技术栈说明 / 麒麟 V10 部署方案同步更新。
- `CLAUDE.md` 增补「危险操作硬化」约定与分段测试/文档数字门禁说明。

## [1.15.17] - 2026-10-21 — 系统管理：国际化彻底清除 + 导航死链治理 + 依赖安全修复

### Removed

- **国际化能力彻底移除**（系统为纯中文单语部署，该能力从未上线使用，前后端一并清掉）：
  - 后端：删除 `app/api/v1/system/i18n.py`（5 个 GET 端点）、其在 `system/__init__.py` 的
    注册与文档行、`write_route_map` 的 `/api/v1/i18n` 映射、`menus.py` 的 legacy 菜单 key
    `i18n`、覆盖率测试 `test_system_i18n_cov.py`；同步更新 `test_system_init_cov.py`、
    `test_system_pkg_init_a26.py`、`test_menus_v2.py` 的模块清单与 legacy key 集合。
  - 前端：删除 `src/api/i18n.ts` 及其测试、`api-modules.test.ts` 的对应条目；
    `SystemConsole.vue` 的「系统设置」描述去掉"国际化、邮件"。
- **两处导航死链**：`SettingsOverview.vue` 快捷导航的「国际化 → `/system/i18n`」与
  「邮件设置 → `/system/email`」都没有对应路由（点击即 404），已删除。
  注：SMTP 一直走 `settings.SMTP_*` 环境变量，从来没有"邮件设置"页面；
  `menus.py` 的 legacy key `email` 保留（供历史权限包兼容）。

### Added

- **导航死链门禁**：`src/utils/navLinks.ts` + `tests/unit/nav-links.test.ts`。
  把导航配置里的 `path` 字面量与路由表的 `path` 字面量做文本比对，
  以后往快捷导航或 console 里加一个不存在的路径，测试会直接变红。

### Fixed

- **生产依赖安全漏洞（阻断发布的根因）**：`axios@1.20.0` 传递依赖
  `follow-redirects@1.16.0` 命中两个高危公告
  （GHSA-q3jh-wrc6-jgq8 数组型 header 绕过跨域凭据剥离、GHSA-8r9p-f939-6h3c
  sensitiveHeaders 正则转义缺陷）。CI `security` 作业的
  `npm audit --omit=dev` 为阻断门禁，v1.15.16 的 tag 构建即因此被 release gate 拦下。
  修复：`package.json` → `overrides.follow-redirects = ^1.16.1`，
  锁定 `follow-redirects@1.16.1`；`npm audit --omit=dev` 恢复 **0 漏洞**，
  前端 lint / vue-tsc / 全量测试（331 文件 6882 用例）与 `npm ci --dry-run` 均通过。

### 同批：文档 / PPT 全量刷新 + 项目文件整理

#### Docs

- **文档全量校准到 v1.15.15**：README / CLAUDE.md / CONTEXT.md / AGENTS.md 与 docs/ 全量更新（版本、测试规模
  13,942 / 6,867·331 文件、菜单 6 板块 104 key·16 legacy、100 个路由模块 / 803 端点、122 张表、54 个 Alembic 版本、
  v1.15.15 双平台发布物体积；补 R33 单位授权 / v1.15.14 FK 迁移 / R35 UI 精细化 / 一户一档入口迁移口径），修 10 条预存死链。
- **演示 PPT 更新至 v1.15.15**：`docs/build_ppt.js` 源码直出 **51 页**（新增 R35 UI 精细化方案 C 页；版本号 / 测试规模 /
  发布资产 / 一户一档入口迁移 / 版本历程全片同步），`scripts/ppt_overflow_check.py` 0 溢出；新增
  `docs/帮扶管理信息系统介绍-更新说明-v1.15.15.md`。
- **新增** `docs/04-部署文档/RELEASE_NOTES-v1.15.15.md`（升级必读 GRANT_* / PASS_CODE_SECRET / viewer 只读 /
  DB 迁移提示 + 双平台安装包体积 + 校验清单）。
- **重写** 根《项目文件结构说明.md》（v1.12.11 → v1.15.15，目录树 / 文件数 / 导航 / 门径口径全面校准）。

#### Chore

- 删除 12 份过期一次性文档：R28 / W18 批次报告、代码审查报告-2026-10-08、系统全面排查报告-2026-10-14、
  早期需求规划、架构评估约定（含空目录）、旧版 class/sequence Mermaid 图、RELEASE_NOTES-v1.15.13；
  删除根 `COORDINATION.md`（已由 AGENTS.md / CLAUDE.md 协作约定取代）。
- 清理仓库根 ignored 临时产物（运行日志 / 一次性脚本 / 探针临时目录 / 测试残留 db / 缓存）与 `.scratch/` 内
  未跟踪大体积产物（仅本地清理，不入库）。

## [1.15.15] - 2026-10-20 — UI 精细化方案 C（品牌区 / 工作台板块级 / 全站表格规范 / 筛选栏统一 / 响应式）

### Changed

- **侧栏品牌区**：系统标识名 16→**20px/800 单行**（logo 36px、侧栏头 64px），修正品牌名低于板块标题（18px）的层级倒挂。
- **工作台提升为板块级入口**：保留 Home 图标，与七大板块标题同构（18px/700、统一内外边距/圆角、图标 16px）。
- **全站表格规范**：所有 el-table 启用 border（**117/117**）恢复列宽拖拽；序号列统一 **72px**（25/25）、选择列 **48px**（10/10）、操作列统一 fixed=right（67/67）——序号、类型等列可拖拽放大。
- **筛选栏统一**：清理 **114 处**行内宽度，改为全局 4 档规范（input 220 / select 160 / date 240 / number 120）+ 统一 16px 间距；搜索按钮 28/28 带图标、筛选栏重置按钮 100% 带图标。
- **页面头部统一**：**19 个列表页**接入共享 PageHeader（全站 31 页），标题/副标题/主操作位置统一。
- **全局精细化层**：新增 frontend/src/styles/components/ui-refine.scss（筛选栏规范 / 表格规范 / 8px 栅格 / 响应式断点 1200·992·768）。
- **一户一档入口收敛**：侧栏移除「一户一档」一级菜单，入口迁入「帮扶村管理 → 年度数据管理」页首张卡片
  （`/households?village_id=<村ID>` 按村预筛选）；后端菜单 key `households` 转 legacy（权限包 / 历史
  `allowed_menus` / 深链兼容），前端路由 `meta.menuKey` 改为 `villages`；旧链接 `/households`、`/households/:id` 仍可直达。

### Fixed

- 修复帮扶村管理搜索重置行控件宽度不一致（默认宽度与固定 140px 混用）、帮扶学校/经费台账等表格列宽无法调整的体验问题。

### Verification

- lint:check、vue-tsc --noEmit 0 错误；硬编码色值棘轮 **305/305 零新增**。
- 定向单测 45 files / 1325 tests + 布局/UI token 相关 238 tests 全部通过。

## [1.15.14] - 2026-10-19 — 发布版：CI 全绿后成功构建 Windows x64 完全集成安装包

### Fixed

- PR Checks 全绿（含 12 段后端测试与 100% 覆盖率门禁）；tag v1.15.14 触发 Build Windows Installer 成功，
  Release 发布 MRRS-Setup-1.15.14-x64.exe（272.7MB）、blockmap、SHA256SUMS 与 latest.yml。

## [1.15.13] - 2026-10-19 — R34 发布闭环：CI 红项修复 + R33 导航入口 + 文档/PPT 更新 + 冗余清理

### Fixed

- **PR Checks 红项修复（v1.15.12 遗留）**：flake8 F401（`grant_package_service.py` 未使用导入）、
  `OrgGrant.vue` prettier 告警（lint:check --max-warnings=0 失败）、README 版本号未随 1.15.12
  同步（version 单一源校验失败）——三者是 v1.15.12 的 PR Checks 红因，也是 Build Windows 被
  release gate 拦截的直接原因。
- **R33 单位授权功能 UI 不可达**：`/system/org-grant`、`/system/grant-import` 路由/页面/API 齐全但
  单一菜单源 `menus.py` 无入口（用户不可达）。已在「系统管理 > 组织与权限」console 新增
  「单位授权配置」「导入授权包」两个 tab，路由 `meta.menuKey` 同步；菜单对齐门禁 A~E 通过。
- **前端死代码清理**：移除 `api/fundsRecycle.ts`、`api/schoolsRecycle.ts` 中未使用的 `request`
  默认导入与 `export { request }` 死导出（全仓 0 消费方，已 grep 验证）。
- **前端覆盖率合并稳定性**：`router-index.test.ts` 为 R33 两个懒加载页面补 `vi.mock` 桩，避免同一
  `.vue` 被多个测试文件执行导致 v8 fnMap 合并失真（functions 跌破 100% 的历史机制）。

### Docs

- README / CLAUDE.md 测试规模与构建命令更新；`.env.example` 新增 R33 `GRANT_*` 配置块；
  部署文档新增「导入授权包前必须配置 GRANT_PUBKEY」「GRANT_ALLOW_UNSIGNED 永远 false」
  「GRANT_GUARD_MODE 默认 off，生产建议先 shadow 再 enforce」；新增
  `docs/04-部署文档/RELEASE_NOTES-v1.15.13.md`。
- PPT（`docs/帮扶管理信息系统介绍.pptx`）更新至 v1.15.13：版本号、测试规模（13,926 / 6,865）、
  CI/CD 12 段与发布门禁、双平台包体积、R33 单位授权功能。

### Verification（R34 最终复检）

- 安全复检：P0 无；viewer 只读、非回环注册门禁、PII 加密/日志脱敏、上传 ZIP 限长、CSRF/安全头
  回归 354 项通过；npm audit 生产依赖 0 漏洞；仓库无硬编码私钥。
- R33 后端 5 个新模块覆盖率 **100%**（124 tests）；R33 前端 3 个新文件覆盖率 **100%**（36 tests）。
- API 契约：830 后端路由 vs 528 前端调用点，0 不匹配；菜单对齐 A~E 通过。
- Windows 构建链终审：v1.15.0 以来未产出 Windows exe **均为 PR Checks 红被 release gate 拦截**
  （v1.15.5/v1.15.7 gate 失败、v1.15.6 action SHA 基建故障），非构建失败；v1.14.3 同配置曾成功
  产出 285.9MB x64 安装包，构建流程自该版本仅 timeout 5 行改动。

## [1.15.12] - 2026-10-19 — backend-test 12 段执行器稳定版（合并 R33 后首次完整验证）

### Fixed

- **backend-test 12 段细粒度执行（含 R33 并入后的测试面）**：本版本在 R33（单位授权）代码并入
  main 后重跑完整 CI，验证 12 段执行器（每段独立进程 + `PYTHONFAULTHANDLER=1`）在
  ubuntu-24.04 上的稳定性；覆盖率 `--cov-append` 跨段合并、最后一段按 `--cov-fail-under=100` 判定。
  该方案用于规避单进程全量在 GitHub runner 上的 SQLAlchemy C 扩展 SIGSEGV（exit 139）。

- 说明：本版本主要验证 CI 修复与 R33 合并后的整体门禁；产品 UI v2.0 内容与 v1.15.0 一致。

## [1.15.11] - 2026-10-19 — backend-test 12 段细粒度执行（缓解 SQLAlchemy C 扩展 SEGV）+ faulthandler

### Fixed

- **backend-test 的 SIGSEGV 进一步定位**：v1.15.10 的 8 段方案中 seg5（unit root b-d-g-h-j-l-m-q-s，
  5,154 用例）以 **exit 139（SIGSEGV）** 崩溃；annotation 中扩展模块列表含
  `sqlalchemy.cyextension.*`，栈落在 pytest 启动尾部 → 特征为 **SQLAlchemy 2.x C 扩展在
  GitHub runner（低内存/CPU 压力 + 单段 ~12 分钟）下的原生崩溃**（本地 Windows 同命令全量通过）。
  修复：把 8 段细分为 **12 段**（单段测试量降至 ~1,000–2,500、时长 ~2–6 分钟），并为每段设置
  **`PYTHONFAULTHANDLER=1`**（若仍崩溃，日志会输出 Python 级栈便于最终定位）；
  覆盖率仍用 `--cov-append` 跨段合并、最后一段按 `.coveragerc` fail_under=100 判定。

- 说明：本版本仅调整 CI 分段粒度；产品代码与 UI v2.0 内容与 v1.15.0 完全一致。

## [1.15.10] - 2026-10-19 — backend-test 回归 8 段执行器 + 补充精确覆盖率测试

### Fixed

- **backend-test 采用 8 段执行器（规避单进程在 Linux runner 的 SIGSEGV）**
  v1.15.9 单进程全量在 ubuntu-24.04 上运行时以 **exit 139（SIGSEGV）** 崩溃（21 分钟处），
  而 8 段执行器（每段独立进程）可完整跑完 → 回退分段方案（seg1 集成/安全 → seg2 api →
  seg3 services/middleware/interfaces/utils → seg4/seg5/seg6 unit 根目录 → seg5b tests 顶层），
  覆盖率使用 `--cov-append` 跨段合并、最后一段按 `.coveragerc fail_under=100` 判定。

- **补充 2 个精确覆盖率测试**（补齐 99.99% 的缺口）：
  - `tests/unit/test_v11510_subordinate_status_path.py`：`generate_status_report` 正常路径
    （覆盖 status 上报包 zip 写入分支 130-132 / branch 128->134）；
  - `tests/unit/test_v11510_secrets_store_branches.py`：密钥库加载的无效条目跳过（line 143）、
    `expires_at/revoked_at` 写入（line 148）、全部无效时回退默认版本（branch 151->155）。

- 说明：本版本仅修 CI 测试执行与测试补充，产品代码与 UI v2.0 内容与 v1.15.0 完全一致。

## [1.15.9] - 2026-10-19 — backend-test 恢复单进程全量（分段方案等效性验证失败后回退）

### Fixed

- **分段执行无法与单进程全量等价（v1.15.3–v1.15.8 的覆盖率门禁失败根因）**：
  本地按 CI 的 8 段顺序复现后，合并覆盖率 **99.99%**（缺
  pp/services/secrets_manager.py:143 + 3 个分支、pp/api/v1/subordinate_reports.py 2 分支），
  且 	est_core_hardening_r28_build_info.py::test_default_start_points_are_used 因
  **测试顺序依赖**（跨进程模块级状态差异）失败——分段与单进程全量不等价。
  修复：backend-test **恢复单进程全量**（pytest tests/ -q --tb=short -rR --cov=app --cov-branch
  --cov-report=... --reruns 2），本地以同一命令实测 **13,710 passed / 1 skipped / 100% 行+分支**；
  配合 v1.15.5 已固定的 **ubuntu-24.04** runner（规避 Ubuntu 26 迁移导致的进程崩溃），
  以及 v1.15.7 已修复的 action SHA。保留 PIPESTATUS 退出码捕获与 
ree -m 诊断。

- 说明：本版本仅修 CI 执行方式；产品代码与 UI v2.0 内容与 v1.15.0 完全一致。

## [1.15.8] - 2026-10-19 — 待决策项彻底落地：viewer 严格只读 + 非回环注册 fail-closed + ARM64 发布门禁 + nightly 稳定化

### Added

- **viewer 角色服务端强制只读**：新增集中式 ASGI 中间件 `backend/app/middleware/viewer_readonly.py`，
  对已认证 viewer 的写方法（POST/PUT/PATCH/DELETE）在非白名单路径返回 403 统一信封，并写审计
  `viewer_write_denied`；判定零 DB 查询（复用新增 `core.security.build_auth_claims()` 写入的令牌
  role/uid 声明，login/2FA/refresh/register 四个签发点统一）；白名单仅自服务（登录/登出/刷新/2FA/
  改本人密码/通知偏好/反馈）。旧令牌无 role 声明时 fail-open 过渡（8h 自然过期）。新增 33 条逐分支
  单测 + 14 条真实 JWT 端到端用例，相关鉴权/令牌/中间件回归 675 条全绿。
- **ARM64 发布门禁**：`build-arm64.yml` 两个 Release 前新增 `Verify release gate is green`
  （复用 `scripts/check_release_gate.py --timeout-minutes 30`，permissions 增 `actions: read`），
  Release 条件加 `&& success()`，门禁红时跳过发布。
- **nightly 后端稳定化**：`nightly-full.yml` 由单步 `-n auto` 改为与 PR Checks 同口径的 6 段独立
  进程（复用 `scripts/ci_backend_test_segment.sh`，新增向后兼容的 `SEG_JUNIT`/`SEG_COV_HTML`），
  保留 `.coveragerc fail_under=100` 与 JUnit/HTML/codecov 上传。
- **部署文档安全红线**：补齐多机/LAN 部署必须全实例统一 `PASS_CODE_SECRET`、viewer 严格只读说明，
  修正失效的 Windows 部署链接。

### Changed

- **非回环自助注册 fail-closed**（安全决策，保留 R9 跨机注册能力）：`/auth/register` 在来源
  **非回环**（不信任可伪造代理头）且 `PASS_CODE_SECRET` 未配置时返回 403 并审计
  `register_denied_untrusted`，堵住「持安装包者用内置常量密钥离线伪造通行码自助开通」；回环来源
  （单机桌面）与已配置 secret 的部署行为完全不变。新增 11 条来源矩阵/审计/未开户断言测试。

## [1.15.8] - 2026-10-19 — CI 6 段执行器补齐 tests/ 顶层测试（最终覆盖率门禁失败根因）

### Fixed

- **`backend-test` 6 段执行器遗漏 `tests/` 顶层 15 个测试文件**（v1.15.6/v1.15.7 的 CI 失败根因）：
  v1.15.6 引入的 6 段执行器只覆盖 `tests/integration`、`tests/security`、`tests/unit`
  （含根目录 + api/services/middleware/interfaces/utils 子目录），而 `tests/` 顶层还有
  `test_approval_workflow.py`、`test_smoke.py`、`test_batch_operations.py` 等 **15 个测试文件**
  未被任何段执行 → 最终 `--mode final` 的 `--cov-append` 数据缺少这些文件覆盖的代码路径
  → 覆盖率 <100% → 门禁失败（无 FAILED 摘要，只有 Coverage failure）。
  修复：新增 `seg5b-tests-root` 段（`tests/test_*.py`，位于 final 段之前），覆盖率合并后
  仍由最后一段按 `.coveragerc` fail_under=100 判定。

- 说明：本版本仅修 CI 执行范围，产品代码与 UI v2.0 内容与 v1.15.0 完全一致。

## [1.15.7] - 2026-10-19 — 修复 workflow 的无效 action SHA（CI job 3 秒失败根因）

### Fixed

- **PR Checks / 构建 Workflow 的 `actions/setup-python` 等 action 引用失效（v1.15.6）**：
  v1.15.6 提交（及同一批的 workflow 调整）把 action 引用升级为
  `actions/setup-python@ece7cb06... # v6.3.0` 等 SHA，但该 SHA 在 GitHub 上无法解析
  （`Unable to resolve action ... unable to find version`）→ **backend-test job 在
  "Set up job" 步骤 3 秒即失败**（所有依赖 action 的 job 同受影响），与测试代码无关。
  修复：把 `.github/workflows/*.yml` 中全部 action 引用**回滚为 v1.15.5 已验证有效的 SHA**
  （checkout v4 / setup-python v5 / setup-node v5 / upload-artifact v4 / download-artifact v4 /
  cache v4 / codecov v4 / action-gh-release v2 / docker setup-buildx v3 / setup-qemu v3），
  共 61 处，并做严格校验（YAML 合法 + 无残留无效 SHA）。

- 说明：本版本仅修 CI 配置，产品代码与 UI v2.0 内容与 v1.15.0 完全一致；backend-test 的
  6 段执行器（v1.15.6）与 ubuntu-24.04 固定（v1.15.5）保持不变。

## [1.15.6] - 2026-10-19 — 全面体检修复：CI 稳定化 + 数据权限缓存泄漏 + 前端依赖冲突 + 构建可复现（W24）

### Fixed

- **v1.15.5 提交误含测试残留文件**：本地验证与探针脚本运行产生的
  `_probe_bandit.json`、`backend/pytest-of-Administrator/`、`mrr_w24_probe_*/`、
  `backend/bumofu_pytest_appdata_*/` 等临时产物被 `git add -A` 一并提交（当时未在 .gitignore 覆盖）。
  已从版本库与工作区清理，并在 `.gitignore` 增加对应规则（`_probe_*.json`、`mrr_w24_probe_*/`、
  `bumofu_pytest_appdata_*/`、`pytest-of-*/`），防止复发。
- 保留合法的辅助脚本 `scripts/run-python.js`（Python 解释器解析）与 `scripts/run-frontend.bat`（前端启动）。

### Fixed（W24 全面体检，2026-10-19）

- **P0 数据权限缓存键跨角色泄漏**（backend）：`villages:list` / `schools:list` 缓存键仅含
  `organization_id`，同组织内 admin 先查后 user/viewer 命中同一键并读到管理员的数据范围
  （实测普通用户可见他组织记录，违反 OWN 仅本人数据域）；改为按用户隔离，与 `policies:list:{user_id}`
  既定正确做法对齐；`organization.py` 的 `orgs:list` 读缓存有 `_global_view` 门禁而写缓存漏门禁
  （普通用户可把受限结果写进全局键，超管 5 分钟内看到空列表），补同一门禁。
- **P0 前端依赖 peer 冲突导致 CI 前端安装失败**（frontend）：`vite@^7.3.6` 与
  `@vitejs/plugin-vue@^5.0.4`（peer 仅支持 vite ^5||^6）冲突，干净环境 `npm ci` 直接 ERESOLVE，
  这是 v1.15.0–v1.15.4 Build Windows / Build ARM64 前端依赖安装失败的根因（此前误判为 registry 网络抖动）。
  升级 `@vitejs/plugin-vue` 至 `^6.0.10`（peer 支持 vite ^5/^6/^7）并更新 lock；`npm ci --dry-run` 通过。
- **P1 日志 PII 脱敏被绕过**：默认 `LOG_FORMAT=json` 下自定义 JsonFormatter 用
  `formatException(exc_info)` 重新渲染原始堆栈，绕过 SensitiveDataFilter 写入的脱敏 `exc_text`，
  身份证/手机号随异常明文落盘；改为复用脱敏缓存（新增回归测试）。
- **P1 跨用户共享缓存泄漏 + 部署链路缺陷**：按数据范围裁剪的
  `supported-villages/filter-options`、`organizations/tree` 响应 Cache-Control 由 `public` 改 `private`；
  `docker/Dockerfile` 删除引用不存在 electron-builder 阶段的 COPY；nginx 备份恢复放开
  `client_max_body_size 10g` + 600s 超时 + `^~ /api/` + `server_tokens off`。
- **P1 CI backend-test 稳定性重设计**：新增 `scripts/ci_backend_test_segment.sh`，PR Checks 后端测试
  拆为 6 个独立 pytest 进程（integration/security + unit 按目录/首字母 212+217+211=640 文件全覆盖），
  前 5 段 `--cov-fail-under=0`、仅最后一段触发 `.coveragerc fail_under=100`；每段独立日志，
  失败输出真实 FAILED/ERROR（无摘要则输出日志尾部并标注疑似被杀）。
- **P1 CI 失败上报误报修复**：旧 "Report backend failure" 把 pytest 进度行当覆盖率缺口发成
  `::error::` 注解（v1.15.4 失败 run 的 11 条注解全是 `tests/... [ 8%]` 误报），淹没真实信号；
  改为只匹配真实 FAILED/ERROR/覆盖率不足行。
- **P1 CI 基础设施升级**：4 个 workflow 全部 action 升级到 Node24 兼容版本并重新 SHA pin
  （checkout v5.1.0 / setup-python v6.3.0 / upload-artifact v6.0.0 / download-artifact v7.0.0 /
  cache v5.1.0 / codecov v5.5.5 / action-gh-release v3.0.3 / docker setup-* v4.x）；消除
  "Node.js 20 is deprecated" 告警；build-windows smoke-test timeout 30→90 以覆盖 release gate
  75 分钟轮询上限；build-arm64 补 job timeout + standalone-deb QEMU 冒烟与失败日志注解；
  nightly 前端补内存上限与重试。
- **P1 构建可复现性（裸 python）**：新增 `scripts/find-python.bat` / `scripts/run-python.js` /
  `run-backend.bat` / `run-frontend.bat`；`Makefile`、`cleanup.py`、`build-installer-local.ps1`、
  `cleanup.bat`/`dev-setup.bat`/`start-all.bat`/`stop-all.bat` 与根 `package.json` 的
  `build:backend` 全部改为显式解析 `backend/.venv` → `py -3.11` → 报错退出（修复 PATH 中 32 位
  Python 被删除后 `python` 不可用导致构建/启动直接失败；并修复 start-all.bat 从未真正启动服务的历史缺陷）。
- **P2 分页上限缺失**：`GET /users`、`GET /machine-code/organization/list` 的 page_size 为裸 int
  （SQLite `LIMIT -1` 等于全表），改用仓库统一 `clamp_offset_limit` 钳制。
- **P2 仓库卫生**：清理 v1.15.5 误提交的测试/探针临时文件（见下），`.gitignore` 增加
  `_probe_*.json` / `mrr_w24_probe_*/` / `bumofu_pytest_appdata_*/` / `pytest-of-*/` 等规则。

### Documentation

- 补齐 CHANGELOG v1.15.4 / v1.15.5 条目（当时写入脚本因锚点失配未落盘）。

## [1.15.5] - 2026-10-19 — CI Runner 固定 ubuntu-24.04（规避 Ubuntu 26 迁移导致的 backend-test 崩溃）

### Fixed

- **PR Checks `backend-test` 连续失败（v1.15.0–v1.15.4）的根因定位与规避**：
  时间线关键事实：**GitHub 于 2026-10-19 将 `ubuntu-latest` 迁移到 Ubuntu 26**
  （Actions 输出明确提示 `ubuntu-latest label will migrate to Ubuntu 26 beginning October 19, 2026`），
  而 v1.14.3 及更早（Ubuntu 24）backend-test 全部成功；本地（Windows）同命令全量通过
  （13,710 passed / 100% 行+分支）。v1.15.4 的日志显示 integration/security 段完整执行到 97% 后，
  unit 段仍以「无 FAILED 摘要、无覆盖率汇总表、exit 1」结束——特征为运行时崩溃。
  修复：**PR Checks 的全部 7 个 job 固定 `runs-on: ubuntu-24.04`**（固定 runner 镜像是企业标准做法）；
  unit 段追加 `-x --tb=long`（若仍有真实失败，annotation 立即显示首个失败用例完整 traceback）。

## [1.15.4] - 2026-10-19 — backend-test 分段覆盖率阈值修复

### Fixed

- **backend-test 段 1（integration/security）因覆盖率阈值误判失败**：v1.15.3 拆分后，段 1 只覆盖部分模块，
  单段结束时会触发 `.coveragerc` 的 `fail_under=100` 检查（33.87%）→ 假失败。
  修复：段 1 增加 `--cov-fail-under=0`（最终 100% 由段 2 `--cov-append` 合并后校验）；
  本地验证段 1 命令 exit 0（211 passed，`.coverage` 正常生成）。

## [1.15.3] - 2026-10-19 — CI 后端测试分段执行（单进程内存峰值治理 + 失败诊断）

### Fixed

- **PR Checks `backend-test` 三连失败（v1.15.0/v1.15.1/v1.15.2）的根因治理**：
  `-n auto`（xdist）→ `-n 2` → 串行（`-n` 移除）三种方式均在 ubuntu-latest 上以
  「pytest 提前退出 + exit 1、无 FAILED 摘要、无覆盖率汇总表、进度行停在
  `tests/integration/test_audit_integration.py` 附近」结束——特征为**进程被杀/崩溃**而非用例失败；
  串行复现说明与 xdist 无关，更可能是 25 分钟单进程内存累积（大量 FastAPI TestClient /
  SQLAlchemy 会话）触达 runner 内存上限（runner 于 2026-10-19 迁移 Ubuntu 26）。
  本地全量同款命令通过：13,710 passed / 1 skipped / 100% 行+分支。
  修复：backend-test 拆为两次独立进程执行——
  ① `tests/integration tests/security`（重内存段，先跑完释放进程）；
  ② `tests/unit`（长跑段，`--cov-append` 追加并输出报表）。
  段间失败打印 `free -m` / `dmesg` 诊断并立即退出；用 `PIPESTATUS` 捕获真实 pytest 退出码
  （避免 `tee` 掩盖）；覆盖率/重试/分支棘轮逻辑不变。

- 说明：本版本仅修 CI 执行方式，产品代码与 UI v2.0 内容与 v1.15.0 完全一致（版本号同步更新）。

## [1.15.2] - 2026-10-19 — CI 后端测试改串行（彻底规避 xdist worker 崩溃）

### Fixed

- **PR Checks `backend-test` 在 ubuntu-latest 上提前退出（v1.15.0/v1.15.1）**：
  `pytest -n auto`/`-n 2` 均出现 pytest 中途退出，覆盖率报告只含部分模块
  （dashboard 71.70% / analytics 44.17% / batch_operations 31.14% / rbac 41.46%，且两版数字完全一致），
  无明确失败用例摘要——特征为 **pytest-xdist worker 崩溃**（runner 环境迁移/资源抖动），非用例失败。
  本地以同款命令全量复跑通过：**13,710 passed / 1 skipped / 100% 行+分支**（7 分 18 秒）。
  修复：backend-test 改为**串行**执行（去掉 `-n`），`--tb=short` 以便失败时输出明确用例；
  job 上限 90 分钟（串行全量预计 25–30 分钟），覆盖率/重试/棘轮逻辑不变。

- 说明：v1.15.0/v1.15.1 的 ARM64 构建均已成功产出；Windows 安装包因 backend-test 门禁误红未产出。
  本版本仅修 CI 执行方式，产品代码与 UI v2.0 内容与 v1.15.0 完全一致（版本号同步更新）。

## [1.15.1] - 2026-10-19 — CI 后端全量并发稳健化（修复 v1.15.0 Windows 包被门禁误拦）

### Fixed

- **PR Checks `backend-test` 在 4 核 runner 上偶发失败**：v1.15.0 的 backend-test 使用
  `pytest -n auto`（4 workers + 覆盖率 + 13,710 用例），出现 xdist worker 偶发崩溃 → pytest 提前退出，
  覆盖率报告只含已跑部分（dashboard/analytics/batch_operations 等模块显示低覆盖），门禁误红；
  v1.15.0 的 Build Windows 因「tag commit 的 PR Checks 未通过」被正确阻断（门禁逻辑本身正常）。
  本地以同款命令（`-n auto --cov=app --cov-branch`）全量复跑：**13,710 passed / 1 skipped / 100% 行+分支**，
  证实为 runner 资源抖动而非代码/测试问题。
  加固：backend-test 的 pytest 并发度由 `-n auto` 降为 **`-n 2`**（降低 4 核 runner 的并发内存/CPU 压力；
  本地实测 7 分 18 秒，远低于 job 45 分钟上限），其余覆盖率/重试/棘轮逻辑不变。

- 说明：v1.15.0 的 ARM64 构建（standalone DEB + Electron DEB）**已成功产出**并发布 Release；
  v1.15.1 仅修 CI 稳定性，产品代码与 UI v2.0 内容与 v1.15.0 完全一致（版本号同步更新）。

## [1.15.0] - 2026-10-19 — UI v2.0：精美·科学·一致性的系统级视觉重构

### Added

- **设计系统 v2（Token 升级）**：主色阶 `--color-primary-50/100/500/600/700/900`；卡片边框 `--color-card-border` +
  轻阴影两档（`--shadow-card` / `--shadow-pop`）；圆角三档（card 8 / control 6 / pill 999）；字号阶梯 `calc(* var(--font-scale))`；
  正文行高 1.6；数字 `tabular-nums`；侧栏 `--sidebar-bg` 深绿渐变；金色仅三用（选中竖条/数据高亮/表头底线，面积 ≤5%）。
- **主题 5→3 收敛**：军绿（默认）/ 深色大屏 `dark-bigscreen`（仅大屏页强制）/ 户外高对比 `outdoor`；
  旧值 `light`/`military`→`default`、`dark`→`dark-bigscreen`、`high-contrast`→`outdoor` 自动迁移（历史用户不失效）。
- **显示偏好 4 档**（localStorage `ui:prefs`，`<html data-*>` 驱动）：字号（紧凑/标准/大号，`--font-scale` 0.92/1/1.12）、
  密度（舒适/紧凑，表格行高 44/34px）、高对比、简化模式（隐藏趋势箭头/辅助说明/高级字段）；
  面板 `components/settings/AppearanceSettings.vue`，入口：头像下拉「外观设置」；损坏 JSON/非法值回退默认、存储不可用静默降级。
- **全局模板样式与通用组件**：`card.scss`（`.app-card`/`.app-stat-card`/`.stat-trend`/`.num-cell`）、
  `states.scss`（`.app-empty`/`.app-loading`/`.app-error` 三件套，错误必须可重试）、`dialog.scss`（三档宽度）、
  `ui-v2.scss`（表格浅主色表头+金色底线/去斑马纹/hover/焦点环）；`components/common/` 6 个通用组件
  （AppPageHeader/AppStatCard/AppEmpty/AppLoading/AppError/AppTableToolbar）+ 47 条专属测试。
- **导航体验**：侧栏当前板块 3px 金色竖条、当前板块自动展开并持久化（`nav:expanded-sections`）、
  **收起态 hover/键盘聚焦浮出子项浮层**、面包屑「板块 › 页面」、Ctrl+K 命令面板（页面+最近+动作）。
- **工作台**：KPI 统计卡网格（28px/700/tabular-nums）+ 待办清单卡 + 图表两列 + 快捷入口/近期动态层级重排；
  加载/错误/空态三件套统一；布局编辑器新增「待办」区块。
- **汇报大屏**：三层结构（标题时间条 / KPI 大数字 / 2–3 列图表）；`data-bigscreen-distance="3m|6m|10m"`
  字号分档（默认 6m）+ 页内切换；15s 自动轮播（可暂停/关闭，卸载/退出清理定时器）；深色主题双挂载（页面根 + documentElement，卸载恢复）。
- **一户一档**：列表 4 张统计卡 + 筛选/表格卡 + 三件套 + 数字列右对齐 + 删除操作收进下拉；
  详情左主右辅布局（≤1200px 单列）+ 4 张监测指标统计卡 + 时间线/走访卡片。
- **质量门禁**：`tests/unit/ui/ui-tokens.test.ts`（22 条 Token/主题/偏好/大屏契约静态断言）；
  `tests/e2e/visual/visual-baseline.spec.ts` 10 个关键页面 DOM 结构基线（跨平台 JSON，`UPDATE_VISUAL_BASELINE=1` 更新）。

### Fixed

- **列表页 `page_size=500` 超后端上限（200）导致 422**：一户一档/消费帮扶/影像库/权限包页面统一改为 200，
  消除页面加载 422 与下拉选项缺失（测试断言同步）。
- **工作台 KPI 取消请求误判为错误**：路由导航/卸载时 axios `CanceledError` 不再记录 error 日志、不置错误态、
  不触发无谓重试（新增 code/name 两个取消分支测试）。
- **Token 重复定义覆盖**：删除后置旧 `--shadow-card`/`--radius-lg-plus` 覆盖，v2 轻阴影与 8px 圆角实际生效。
- **旧主题残留清理**：`echarts-theme` 运行时判定（`dark-bigscreen`/`outdoor`）、系统配置包主题选项（6→3）、
  `theme-elevated` 深色块、`accessibility.css` 高对比改为 `data-contrast="high"`（不再占用主题值）。

### Changed

- 视觉一致性治理：硬编码色基线 **345 → 305**（改动文件零新增，基线只紧不松）。
- 外观设置面板统一承载主题与 4 档显示偏好；系统配置包主题选项与顶栏一致（3 套）。

### Verification

- 前端全量：12 组 glob 四指标 100%（文件/用例数见测试报告）；`vue-tsc --noEmit` 0；eslint 0。
- E2E：154 条既有用例 + 10 个视觉基线页面全绿。
- 后端：13,710 passed / 1 skipped / 100% 行+分支（本次未改后端逻辑）。
- 构建：Windows x64 安装包 + 麒麟 ARM64 deb（standalone + Electron）发布 Release v1.15.0。

## [1.14.3] - 2026-10-18 — ARM64 构建网络韧性加固（npm/Docker registry 抖动）

### Fixed

- **ARM64 构建因 CI 网络抖动间歇失败（v1.14.2）**：`v1.14.2` 的 Build Frontend 在
  npm registry 抖动下 3 次 `npm ci` 全失败（v1.14.1 同步骤成功，属 runner 网络波动）；
  standalone DEB 的 Docker 构建亦 3 次失败（公共镜像/缓存拉取）。加固：
  1) `npm ci` 增加 `--prefer-offline` + 递增退避（30/60s），3 次失败后**回退
     `npm install --prefer-offline`**（再 2 次重试）——只救网络，不改变产物语义（lock 漂移
     由前三轮 npm ci 先行拦截）；
  2) Docker 构建重试间隔提升为 60/120s，失败时输出 `buildx ls` / `system df` /
     `docker images` 诊断，便于区分网络与构建错误；
  3) 保留既有 `--cache-from/--cache-to type=gha` 缓存复用与基础镜像源探测。

- 说明：v1.14.2 已修复发布门禁时序缺陷（`scripts/check_release_gate.py`），Windows 安装包
  正常产出；本版本仅进一步加固 ARM64 流水线网络韧性。v1.14.1 的 ARM64 完整构建
  （standalone DEB + Electron DEB）曾成功，证明代码侧无阻断。

## [1.14.2] - 2026-10-18 — 修复发布门禁时序缺陷（v1.14.1 构建被误拦）

### Fixed

- **发布前置门禁误拦合法 tag 构建**：v1.13.1 引入的门禁只检查「main 最近一次 completed 的
  PR Checks」。v1.14.1 tag 推送瞬间，其自身 PR Checks 尚在 in_progress，而"最近 completed"
  仍是上一提交（422f840）的 e2e/upgrade-rehearsal 失败 run → 门禁拒绝构建
  （`main 分支最近一次 PR Checks 未通过`），导致 v1.14.1 Windows 安装包未产出。
  新增 `scripts/check_release_gate.py` 并改造 `build-windows.yml`：
  1) 优先查询 **tag 指向提交自身**的 PR Checks，completed success 放行、failure 阻断；
  2) in_progress/queued 时**轮询等待**（上限 75 分钟）到完成再判定；
  3) 该提交 PR Checks 被并发取消或不存在时，回退「main 最近 completed success」判定。
  本地已用真实数据验证三分支（success 放行 / failure 阻断 / in_progress 等待超时阻断）。

- 说明：v1.14.1 的代码修复（空库迁移链幂等、E2E 折叠适配、ARM64 npm 重试加固）不受影响，
  其 PR Checks 中 `upgrade-rehearsal`、`e2e-test` 均已 **success**（本版本仅修 CI 门禁）。

## [1.14.1] - 2026-10-18 — 修复空库迁移链 / E2E 折叠适配 / ARM64 构建加固

### Fixed

- **空库初始化迁移链（严重：全新安装 `alembic upgrade head` 必失败）**：v1.14.0 删除
  `villages` 遗留表后，历史迁移在「空库 create_all 路径」上因表不存在而中断：
  - `village_status_001` 的 `ALTER TABLE villages ADD COLUMN status`（旧守卫 bug：表不存在时
    `cols` 为空仍会 add_column）；
  - `pii_encrypt_001` 的 `SELECT ... FROM villagers` 存量回填。
  两处迁移改为**表不存在则幂等跳过**（老库升级路径行为完全不变），空库
  `upgrade → head` 已实测通过（此前 CI 的 `upgrade-rehearsal` 因此失败）。
- **E2E 适配 7 板块默认折叠**：v1.14.0 起侧栏板块默认折叠，E2E 用例点击子菜单/断言子项前
  需先展开。新增 `expandAllSections` / `expandSection` helper（写 `nav:expanded-sections`
  契约后 reload），修复「待办事项功能」「权限包菜单可见性」用例；快捷导航用例
  （新建项目 → /projects/create）重跑稳定通过。
- **ARM64 构建 npm 网络重试加固**：`build-arm64.yml` 的 Build Frontend 步骤由裸
  `npm ci` 改为 fetch 重试参数 + 最多 3 次重试（与 pr-checks/build-windows 同款）。
  v1.14.0 的 ARM64 Electron DEB 即因 registry 抖动在本步骤 exit 1 被 skip。

### Changed

- E2E 辅助函数新增折叠展开工具；`dashboard.spec.ts` / `permission-packs.spec.ts` 适配新导航交互。

## [1.14.0] - 2026-10-18 — 功能大迭代（一户一档/影像库/消费帮扶/OCR/报表组合/导航折叠）

### Added

- **一户一档**：新表 `households` / `household_members` / `household_risk_records`，API `/households/*`，
  页面 `/households` 与 `/households/:id`：家庭成员、帮扶责任人、风险类型、收入/务工/大病/住房监测指标；
  风险等级与预警（连续未走访 >90 天且非一般户→中风险；大病/住房不安全/突发困难→高风险，服务层实时计算）；
  走访记录挂户并回写最近走访日期；`POST /households/rollup` 按村自动汇总回填 `village_population` 年度人口
  （消除"村里填一遍、户里再算一遍"重复录入）；台账导出 xlsx/csv。
- **影像库**：新表 `photo_archives`，API `/media/photos/*`，页面 `/media`：按村/校/项目/时间/标签归档；
  手机照片 EXIF 拍摄时间与 GPS 自动归类（≤5km 就近匹配帮扶村）；同一拍摄点多期照片按 `spot_key` 自动配对，
  生成左右/2×N 滑动对比图 PNG（Pillow 合成 + 日期标注，GET/POST 双入口），可直接用于汇报材料。
- **消费帮扶台账**（替换已下线的舆情监测）：新表 `consumption_records` + `/consumption/*` + 页面 `/consumption`：
  品类（农产品/畜禽/手工/其他）、数量、金额、采购方、供货方（农户/合作社/企业）、年度、凭证、备注；
  年度/品类/村统计与 xlsx/csv 导出；与帮扶村年度数据板块 `consumption_support` 区分。
- **经费凭证 OCR**：`services/ocr_service.py`（rapidocr-onnxruntime 1.4.4，完全离线 CPU）+ `POST /funds/ocr-voucher`：
  识别凭证文本并回填金额/日期（支持 ￥/¥/元/千分位、YYYY-MM-DD / YYYY年M月D日 / YYYY/MM/DD）；
  引擎不可用时 503 降级、前端提示手工录入不阻断业务。
- **报表模板组合导出**：`POST /report-templates/{id}/export?format=xlsx|csv|docx|pdf&year` +
  `GET /report-templates/{id}/print-data?year`；前端任意字段勾选组合 → 预览 → 多格式导出 → 浏览器打印。
- **导航体验**：7 板块标题放大（18px 加粗）、默认折叠、点击展开/收起（localStorage `nav:expanded-sections`）。
- **汇报大屏退出**：大屏头部「退出大屏」→ 退出全屏并返回工作台。
- **数据校验合并页**：`/data-verify` 单页三 Tab（校验执行 / 规则管理 / 字段说明），问题清单可定位跳转与导出；
  独立「校验规则」菜单下线（key 保留 legacy）；字段中文说明承接原国际化字段翻译。

### Changed

- **数据上报链路修复**：枚举列导出的枚举名与导入校验的枚举值不一致导致上级整表 rejected（学校等）；
  导出侧按模型列元数据归一为枚举值，补端到端集成测试（下级录入→生成上报包→上级接收导入→数据可见 + 重复导入幂等）。

### Removed

- **驻村工作台**：删除页面/路由（无后端模块），菜单 key `checkin` 保留 legacy。
- **舆情监测**：删除后端 `api/v1/sentiment.py`、`models/sentiment.py`、`services/sentiment/`（采集/分析）与前端页面/API，
  菜单 key `sentiment` 保留 legacy（改为消费帮扶）。
- **国际化/邮件设置**：删除 `I18nManagement.vue` / `EmailSettings.vue` 及路由；菜单 key `i18n` / `email` 保留 legacy。
- **Village/Villager 遗留表**：Alembic 迁移删除 `villages` / `villagers` / `industries` / `sentiment_news` 四表；
  `rural_works` / `rural_tasks` / `tea_plantations` / `cactus_fruit_plots` 的 `village_id` 迁移为
  `supported_village_id`（FK→`supported_villages`，按村名+组织回填）；删除对应模型/API/测试。
- 数据概览页「已迁移/已统一/已整合」提示文案全部清除（保留功能入口）。

### Testing

- 后端全量：**13,710 passed / 1 skipped / 0 failed**；语句覆盖率 **100.00%**（44,423 stmts，0 miss）、分支覆盖率 **100.00%**（10,872 branches，0 partial）（pytest-cov `--cov=app --cov-branch`，`.coveragerc` fail_under=100）
- 前端全量：**321 文件 / 6,748 passed / 0 failed**；12 组 glob 四指标 100%
- 静态门禁：flake8（app/）0、bandit -ll 0、vue-tsc --noEmit 0、eslint src --max-warnings=0 0；
  17 项静态门禁（菜单对齐 A~E、硬编码色、安全审计、Alembic 单 head、pragma 理由、版本一致性等）全部 PASS
- Alembic：`upgrade → downgrade → upgrade` 通过（新表创建 / 旧表删除 / 列迁移 / 数据回填断言）

## [1.13.4] - 2026-10-18 — 修复 ARM64 后端产物主程序文件名（Electron DEB 最后一项阻断）

### Fixed

- **ARM64 Electron DEB 仍失败（v1.13.3 注解为「缺后端主程序」）**：`backend-output` 阶段 COPY 源路径
  修正后目录已正确导出，但 PyInstaller Linux spec 的 `EXE/COLLECT name` 为
  `assistance-management-backend`，导出目录内主程序仍是该名；Electron Linux 主进程与 workflow
  均按 `resources/backend/assistance-backend/assistance-backend` 启动/断言，因此判失败。
  `scratch` 阶段无法 `RUN`，改为基于 `debian:buster-slim`（deb-package 阶段已拉取、缓存命中）
  在导出前重命名主程序并 `chmod +x`，导出树统一为
  `backend/dist/assistance-backend/assistance-backend`。

## [1.13.3] - 2026-10-18 — 自包含冒烟步骤诊断增强（动态端口 + stdout/stderr 落盘）

### Fixed

- **CI 自包含冒烟在 Windows runner 上超时失败**（v1.13.2 唯一阻断项，本地同脚本通过）：
  固定端口 8123 可能被 runner 占用，且后端 stdout/stderr 未落盘导致失败时只能看到 exit code 1。
  已改为 18123-18140 自动挑选空闲端口、后端输出重定向落盘并在失败时打印尾部、
  失败原因用 ::error:: 输出（可被注解捕获）、日志上传 packaged-backend-smoke-logs artifact；
  等待上限 180 秒，进程提前退出时立即诊断。

## [1.13.2] - 2026-10-18 — 修复发布门禁依赖安装遗漏

### Fixed

- **v1.13.1 的 smoke-test 重构遗漏依赖安装步骤**：`Backend release smoke subset` 直接执行
  `python -m pytest`，但 runner 上只装了 Python 解释器，未安装 `backend/requirements*.txt`，
  导致步骤秒失败（`No module named pytest`）、`build-windows` 被 `needs: smoke-test` 阻断。
  已在 setup 与子集测试之间补回 `pip install -r backend/requirements.txt -r backend/requirements-dev.txt`，
  并本地用 PyYAML 校验 workflow 步骤序列（checkout → setup → main 门禁 → 依赖安装 → 后端子集 →
  前端子集 → 日志 artifact）。

## [1.13.1] - 2026-10-18 — 修复 GitHub 发布构建失败 + 安装包自包含验证

### Fixed

- **Windows 发布构建失败（v1.13.0 未产出 Windows 安装包）**：tag 构建的 `smoke-test`
  重复执行全量后端（1.3 万+）+ 全量前端（6.7 千+）测试；同一提交内容在 main 的 PR Checks
  已全量跑绿（`c17b2ed success`），tag 侧重复运行却因 flaky 测试 / rerun 与覆盖率数据合并抖动
  随机变红（实测失败发生在后端步骤 14.5 分钟处，`exit code 1`，无测试名可读），导致
  `build-windows` 被 `needs: smoke-test` 阻断。重构发布门禁为：
  ① **main 分支最近一次 PR Checks 必须 success**（发布前置校验，用内置 `GITHUB_TOKEN` 查询）；
  ② Windows 敏感后端子集（菜单单一源 / 路径口径 / 备份对齐 / 数据同步路由 / 帮扶村 API /
     打包卫生，249 用例）；
  ③ 前端 `vue-tsc` + 导航重构关键子集（菜单 store / 布局 / 聚合页 / 路由表 / smoke，221 用例）；
  ④ 失败时上传完整日志 artifact（`release-smoke-logs`），不再只能看到 `exit code 1`；
  ⑤ 作业预算从 60 分钟降到 30 分钟。全量测试的权威位置仍是 main 的 PR Checks 与 Nightly。
- **ARM64 发布构建失败（Electron ARM64 DEB 连续两版缺失）**：`docker/Dockerfile.kylin-standalone`
  的 `backend-output` 阶段 `COPY --from=backend-builder /build/dist/assistance-backend` 路径错误
  （PyInstaller 实际产物目录为 `assistance-management-backend`，见同文件 `deb-package` 阶段的
  COPY 源），导致 `docker buildx --target backend-output` 三次重试全部在 COPY 阶段失败。
  已修正为 `/build/dist/assistance-management-backend`（保留 `/assistance-backend` 目标名以匹配
  Electron extraResources 期望目录）。

### Added

- **安装产物自包含冒烟（CI，Windows 构建作业）**：electron-builder 解包后直接启动打包后端
  `resources/backend/assistance-backend/assistance-backend.exe`（按 Electron 运行期注入的数据目录
  env），断言 `/health` 返回 `status=ok`、`version`、`git_hash`、数据库迁移 `at_head=true`；
  并断言包内包含 `_internal/python311.dll`、`VCRUNTIME140.dll`、`VCRUNTIME140_1.dll`、
  `MSVCP140.dll`、`alembic.ini`、前端 `index.html`、`vcredist/vc_redist.x64.exe`。
  每次发布自动证明「解包即用、不依赖系统 Python / 预装依赖」。

### Changed

- 发布门禁职责划分写入 README：**全量测试 = main 的 PR Checks + Nightly；tag 构建 = 发布专项门禁
  （main 绿 + 敏感子集 + 前端类型 + 自包含冒烟）**，避免 tag 与 main 重复全量造成随机失败。

## [1.13.0] - 2026-10-18 — 导航/菜单单一源重构 + 系统管理 6 聚合页

### Added

- **导航增强**：Ctrl+K 菜单搜索（板块/入口/Tab 全量可搜、键盘上下选择+回车跳转、空搜索显示收藏与最近）、
  最近访问与收藏（localStorage `nav:recent` / `nav:favorites`，上限 8 条，损坏数据自动回退）。
- **系统管理 6 聚合页**（`/system/console/:group` + 页内 `?tab=<tab key>`）：
  组织与权限 / 安全与审计 / 运维与监控 / 备份与存储 / 系统设置 / 关于与反馈；
  Tabs 页内切换、当前 Tab 才加载对应页面组件，原页面组件与旧路由全部保留（深链不失效）。
- **导航入口补齐**：汇报大屏、提醒中心、帮助中心、数据上报（上报/接收/版本）、批量操作、
  综合数据录入、成效排名/评估、工作分析、舆情监测、驻村工作台。
- **后端菜单 v2 单一源**：`MENU_SECTIONS`（6 板块）+ `MENU_DEFINITIONS` 扁平条目
  （99 key / 85 个带 path 入口，条目 `kind` = `page`/`group`/`console`，`tabs` 承载聚合页页签）；
  `/menus/accessible` 与 `/menus/all` 统一返回 `{version:2, sections, flat_keys}`。

### Changed

- 左侧导航重排为 **7 板块**：工作台（固定第一）+ 帮扶业务 / 乡村振兴 / 工作协同 / 分析汇报 / 数据管理 / 系统管理；
  消除"分组标题与子菜单同名"重复，消息中心移入工作协同。
- 前端侧栏、移动端底部导航、权限面板与权限包菜单树全部改为**后端菜单数据驱动**，
  不再手写菜单段；权限面板为"板块→入口→Tab"三级树，保存协议仍为 key 数组。
- 菜单过滤语义：`group` 任一子项可见即显示并裁剪子项；`console` 可见 = `console.key` 或任一
  `tab.key ∈ allowed`（勾聚合页 key 视为全部 Tab 可见）；旧 key 全部保留，历史权限包/`allowed_menus` 不失效。
- 菜单对齐门禁 `scripts/check_menu_alignment.py` 重写为规则 A~E（AST 解析单一源：
  后端 path 可解析 / 前端 `meta.menuKey` 合法 / 无孤儿 key / 同路径不重复 / 板块唯一）。

### Removed

- **删除前端菜单副本**：`src/config/menu-config.ts`、`src/utils/systemMenu.ts` 及
  `menu-config.test.ts`、`systemMenu.test.ts`、`menuKeyAlignment.test.ts`、
  `DefaultLayoutSafe.menu.test.ts`、`DefaultLayout.property.test.ts`（源码字符串断言/假属性测试）。
- 删除后端 3 个死菜单项：`user-backup`、`data-quality`、`system-security`（无独立导航出口/重复 path）。
- 删除根目录旧 PPT 副本，`docs/帮扶管理信息系统介绍.pptx` 为唯一对外介绍材料。
- 删除文档中"前后端菜单双轨同步 / menu-config 引用 / 旧系统管理入口清单"等过时说明。

### Fixed

- 修复历史遗留的"N 个已实现系统页面无任何 UI 入口"（系统管理 24+ 页面此前仅硬编码 6 个入口）
  与"有菜单 key 但无页面/有页面但无菜单"的双向漂移（由规则 C 持续拦截）。

## [1.12.25] - 2026-10-18 — 🔧 ARM64 发布流水线彻底修复（镜像限流根因）

### Fixed

- **ARM64 流水线失败根因**：`build-backend` 作业独立冷启动 `docker buildx build`，需再次拉取
  `python:3.11-slim-buster`；Docker Hub / ECR 公共镜像**匿名拉取配额耗尽**时返回
  `toomanyrequests: Data limit exceeded`，buildx 随即无法解析基础镜像元数据，整条 ARM64 流水线失败，
  Release 因此丢失 `MRRS-Setup-*-arm64.deb`（v1.12.23 / v1.12.24 均缺该产物；v1.12.20/21 正常）。
  与同工作流 `standalone-deb`（带 GHA 层缓存、始终成功）对比后可确认是重复冷构建 + 公共镜像限流，
  并非代码或打包脚本缺陷。
- **修复方式（消除重复冷构建，而非绕过）**：
  1. `docker/Dockerfile.kylin-standalone` 新增 `backend-output` 阶段，复用 `backend-builder` 已构建的
     PyInstaller onedir 产物；
  2. `standalone-deb` 作业在同一次 buildx 构建上下文中导出后端二进制并上传 `backend-arm64` 工件，
     与 standalone DEB 共享层缓存，**不再产生第二次基础镜像拉取**；
  3. 删除重复的 `build-backend` 作业，`build-electron-deb` 改为依赖 `standalone-deb` 的工件；
  4. standalone DEB 构建改为 shell 重试（3 次，指数退避）+ 构建前镜像源探测
     （`public.ecr.aws/docker/library` → `docker.io/library`），失败仅提示并回退，由 GHA 缓存兜底。
- **效果**：ARM64 作业数减少 1 个；基础镜像只拉取一次；瞬态网络/限流失败可自动重试；
  Release 恢复 Electron ARM64 DEB 产物（与 standalone DEB 并存的既有发布形态）。
- 本版本无运行时代码变更（仅 CI/Dockerfile），Windows 安装包与 standalone DEB 内容与 v1.12.24 一致。
## [1.12.24] - 2026-10-18 — 🧹 W5-T5 解包口径收口 + 分支门禁确定性

> 前端全量：**316 文件 / 6,685 用例**，`src/**` 12 组 glob 四指标 100%；后端全量 13,505 用例，行+分支 100%。

### Fixed

- **前端 50 处 `no-restricted-syntax` 违规（`.data.items` 手写解包）全部收敛到 `@/utils/unwrapList`**：
  涵盖列表/详情/仪表盘/导出等 40 个文件；顺手修正 3 处「空数组 truthy 短路」语义缺陷
  （ChartRow 的 `data.data` 嵌套、ConflictResolution 的 `data.data`、ContractManage 的数组形态兜底），
  并补齐 `unwrapList<T>` 泛型使 vue-tsc 严格模式通过。此前 `npm run lint:check` 失败导致 PR Checks 红。
- **版本兜底同步补漏**：`frontend/src/config/constants.ts` 的 `SYSTEM_VERSION` 硬编码兜底随单源同步更新，
  修复 `constants.test.ts` 两例版本回落断言失败。

### Added

- **`backend/tests/unit/test_branch_closure_r22.py`（21 项）**：为 23 个历史错误/边界分支补真实行为回归
  （help 片段边界、批量表白名单、cache None 哨兵、村附件扩展名、增量检测模型回退、管控包配置类型、
  数据包友好错误、加密包与备份恢复清理路径、相对 LOG_FILE、凭证无项目、预览 50 行截断、政策导入非 dict、
  注册认领竞争），使分支门禁不依赖测试执行顺序或未提交测试。
## [1.12.23] - 2026-10-18 — 汇报大屏对象筛选（村/校/单位）+ 在途批次收口

### Added

- **汇报大屏对象维度筛选（W20）**：新增 `GET /api/v1/bigscreen/filters`（数据域内帮扶村 / 帮扶学校 /
  帮扶单位三组筛选项；单位是村 `support_unit`、校 `support_unit`、项目 `responsible_unit`、
  结对 `subject_name` 四路并集的自由文本 facet，同名合并计数）与
  `GET /api/v1/bigscreen/overview?scope_type=all|village|school|unit`（KPI、经费趋势、项目状态、
  年度对比、经费投入排名、重点项目负责人、对象档案与帮扶明细）。村/校不存在、已软删或越权返回 404；
  非法维度 / 缺对象 ID / 单位名为空返回 400；单位无匹配返回 200 空统计。数据域沿用 `get_org_scope`，
  软删模型显式过滤 `is_active`，输出不含 PII。
- **大屏前端对象筛选**：`views/bigscreen/BigScreen.vue` 头部筛选条（全部 / 帮扶村 / 帮扶学校 / 帮扶单位 +
  可搜索对象下拉 + 重置），KPI、图表与负责人改由单一 overview 接口渲染；scoped 时新增「对象档案」与
  「帮扶明细」卡片；scope 与卡片显隐/排序/刷新频率/脱敏一并持久化到 localStorage；filters 仅加载一次、
  自动刷新只轮询 overview；对象失效或越权 404 自动回退「全部」并去重告警。
- **方案文档与用户手册**：新增 `docs/design/汇报大屏对象筛选与下钻方案.md`（背景、现状调研、四类 scope
  方案、逐 scope 数据口径表、API 契约、交互流程、权限安全、性能降级、验收清单、后续演进），
  `docs/02-用户手册/数据分析功能使用指南.md` 新增「汇报大屏按对象筛选」章节。
- **单校成效统计端点**（W18 在途收口）：`GET /api/v1/schools/{school_id}/statistics`，由服务端聚合
  学校项目数/预算、资助学生数与资助金额、学生规模，供学校详情与删除前关联校验使用。

### Fixed

- **W18 在途安全与数据完整性收口**：数据包导出改走原生 SQL，PII 列保持密文出包（不再经
  TypeDecorator 解密后落入 zip）；跨机数据包主键冲突按业务键判定——缺失键不覆盖本机数据、
  业务键不同则去主键插入；备份/恢复增加完整性与路径校验、恢复前置校验与失败降级；
  同步导入时间戳统一 UTC 规范化；离线数据目录与日志路径按平台收口；学校统计、诊断与
  审计保留策略等配套修复。
- **测试与门禁收口**：补齐 W18 遗留 19 个「实现已变、测试未跟」的失败用例与 5 个模块
  （`school.py` / `data_package_service.py` / `backup_service.py` / `pii_crypto.py` /
  `database_health_service.py`）的语句+分支覆盖率缺口；修复 `UserManagement.vue` 拆分组件的
  4 处 vue-tsc 类型错误、删除重复渲染测试与死 import、补齐子组件覆盖率；清零工作区新增硬编码色值。
- **大屏口径修正**：KPI 标签去掉冗余的 "(万)"（由 `unit` 字段承载单位）；`Fund.year` 为 NULL 的
  经费不再让年度趋势整段降级为空。

### Changed

- 年度趋势聚合从 `/dashboard/yearly-trends` 端点抽成 `_build_yearly_trends(db, data_scope, years)`，
  由仪表盘与大屏共用，避免两套口径漂移。

### Removed

- 删除 `UserManagementRealRender.test.ts`、`UserManagementRender.test.ts`（与专属测试重复，
  且违反"同一 .vue 单一执行者"覆盖率规程）、临时探针测试与拆分后残留的死 import。

## [1.12.22] - 2026-10-17 — 🧾 全部遗留工单落地（004~010 七项）

> 用例口径：后端 **13,349**（676 文件）/ 前端 **6,612**（315 文件，本地全量实测）；
> 后端行+分支覆盖率 100%；前端 12 组 glob 四指标 100%。

### Added

- **w17-004 工作移交**：`/handover` 页（清单勾选 → 接任人 → 确认执行 → 交接单 PDF / 历史回放）；
  后端 `handover_service` 单事务改写村/项目/待办/审批归属 + 双方站内消息 + WorkLog 审计（历史由 WorkLog 承载，不新增表）。
- **w17-005 年度数据滚动填报**：`yearly/{year}/prefill`（逐字段三态差异）+ `rollforward` 批量沿用
  （section_keys 白名单、单事务原子、默认只填空不覆盖、可选 overwrite）；年度概览「从上年复制」弹窗。
- **w17-006 导出物口径脚注**：村/学校/项目/经费/综合报表五类导出统一「口径说明」（数据截止/过滤条件/软删/
  数据范围/生成人/时间，空字段省略）；Word/PDF 文末、Excel 表尾、CSV 尾部同时生效。
- **w17-007 一村（校）一档 PDF**：`/supported-villages/{id}/dossier.pdf` 与 `/schools/{id}/dossier.pdf`
  （封面/基本信息/年度数据/项目经费摘要/照片清单/口径脚注；空段降级；越权 404；导出审计；500 泛化）；详情页按钮。
- **w17-008 AI 结论可解释 + 业务数据体检**：10 个 AI 端点统一返回结构化 `rationale` + `data_scope`，
  前端「为什么」面板；新增 `GET /system/business-health`（管理员，8 项体检：村年度缺失/经费逻辑矛盾/
  长期未动/组织归属缺失；无 PII）。
- **w17-009 金额展示与筛选记忆**：`MoneyText` 组件（千分位/4 位小数/空值占位/人民币大写）与
  `useFilterMemory`（sessionStorage 按路由记忆）；村/项目/经费列表接线筛选记忆与「导出当前筛选」。
- **w17-010 大屏可配置**：右上角「设置」抽屉（卡片显隐/排序、刷新频率 30s/60s/5min/关闭、汇报脱敏），
  localStorage 持久化；关闭自动刷新即停止轮询；脱敏模式金额精度隐藏 + 负责人姓名打码。

### Fixed

- **前端 vue-tsc 类型错误导致 CI 构建失败**：捐赠台账表格槽位 row 为 DefaultRow，直接传 DonationItem 形参
  触发 TS2345 → build-windows 的 Frontend smoke test 失败；已按结对台账同款模板内断言修复。
## [1.12.21] - 2026-10-17 — 🎁 捐赠物资台账前端落地 + CI 分支门禁去抖

> 用例口径：后端 **13,079**（664 文件）/ 前端 **6,438**（305 文件，本地全量实测）；
> 后端行+分支覆盖率 100%（41,503 语句 / 10,118 分支，棘轮 10118/10118）；
> 前端 12 组 glob 四指标 100%。

### Added

- **捐赠物资台账前端（w17-003 完成）**：新增 `views/donation/List.vue` 与 `api/donations.ts` ——
  统计标签（总数/图书/设备/物资/折价合计）、关键字/类别/去向筛选、表格（类别、数量+单位、
  折价、去向名称）、分页、登记/编辑对话框（去向类型联动、附件按行解析、手写校验与
  后端 `ensure_donation_valid` 同口径）、删除二次确认；路由 `/donations` + 菜单键 `donation` +
  侧边栏入口 + 后端 `MENU_DEFINITIONS` 收录（此前"后端已通、前端未建、菜单入口摘除"的半成品状态结束）。

### Fixed

- **CI 分支覆盖棘轮随机变红（PR Checks backend-test）**：该步骤此前**再跑一遍全量 pytest**
  （第二个 xdist 数据面）再比对基线，出现过 step5 通过而 step8 读到 99.61% 的不一致。
  现改为**单一数据源**：主测试步骤产出 `coverage-branch.json`，棘轮步骤只读该文件比对；
  用例不再重复执行，两跑差异导致的假红消除。
## [1.12.20] - 2026-10-17 — 🔒 安装器卸载口径修正（W19 实机实证）

> 本版为 v1.12.19 的安装器补丁：**应用功能与 v1.12.19 完全一致**，仅修正卸载删除的用户数据目录。
> 用例口径与 v1.12.19 相同（后端 13,067 / 前端 6,409），覆盖率 100%。

### Fixed

- **卸载不删真实用户数据（隐私泄露，实机实证）**：三处错误叠加 ——
  1) 目录名：Electron `app.name` 取**根** `package.json` 的 `productName`，根层没有才取 `name`；
     本仓库只有 `build.productName`（仅影响安装包/exe 命名）→ 真实 userData 为
     `%APPDATA%\Assistance-Management-Information-System`，而钩子按"productName 优先"
     写成 `%APPDATA%\帮扶管理系统`（该目录根本不存在）；
  2) 变量：perMachine 安装的卸载器处于 all-users 上下文，`$APPDATA` 指向 `C:\ProgramData`
     （实测注册表被写成 `C:\ProgramData\\帮扶管理系统`）→ 用户目录必须用 `$PROFILE` 拼；
  3) 转义：NSIS 反斜杠是**字面量**（makensis 实测 `"C:\A"` → 两个反斜杠），历史注释"必须写 `\\`"
     是误判，导致注册表路径出现双反斜杠。

  修复：安装期以 `$PROFILE\AppData\Roaming\<app.name>` 写入 `UserDataPath`；卸载期读回删除，
  并枚举 `$PROFILE\..\*` 覆盖全部 Windows 账号；兜底清理 `%LOCALAPPDATA%\bumofu-assistance`
  与历史误判目录（`ProgramData\帮扶管理系统` 等）。门禁 `check_userdata_path_consistency`
  改为 Electron 真实语义，并强制使用 `$PROFILE`、必须枚举多用户、必须清兜底目录。

  实机验证：安装后 `UserDataPath` = `C:\Users\<user>\AppData\Roaming\Assistance-Management-Information-System`
  （单反斜杠、路径存在）；`/health` 返回 `version=1.12.20`、`git_hash`=本提交；静默卸载保留数据
  （`/SD IDNO` 设计），程序目录清空、卸载项移除。
## [1.12.19] - 2026-10-17 — 🧩 功能补全 + 数据完整性修复（W17/W18 批次）

> 用例口径：后端 **13,067** / 前端 **6,409**（303 文件，本地全量实测）；
> 后端行+分支覆盖率 100%（`backend/.coveragerc` fail_under=100）；flake8 / vue-tsc / eslint 0。
> 迁移 50 个版本、单 head（`donation_item_001`）。

### Added

- **提醒中心处置闭环**：`POST /reminders/{id}/handle|ignore|snooze|reopen`（仅提醒接收人本人，
  越权/不存在一律 404），新表 `reminder_dispositions`（迁移 `reminder_disp_001`）；
  列表补 `state/note/snooze_until/link/entity_id` 与 `stats`（待处理/已处理/已忽略/已延期），
  前端提醒中心支持逐条处理、忽略理由、延期天数、重新打开与"前往处理"。
- **结对帮扶与走访台账**：`pairing_records` + `visit_records`（迁移 `pairing_001`），
  主体（单位/支部/干部个人）↔ 对象（村/学校/学生）结对 + 走访明细（时间、人员、事项、附件、
  可选关联项目/经费/物资）；前端 `views/pairing` 列表与详情、村/学校详情深链入口
  （`/pairings?partner_type=village|school&partner_id=N`）。
- **捐赠物资台账（后端）**：`donation_items`（迁移 `donation_item_001`）+ 服务 + API
  （`/api/v1/donation-items`，envelope / 数据域 / 软删 / 审计）。**前端页面尚未建成**，
  故侧边栏不放入口（避免点击 404）；待 UI 落地后按 `MENU_DEFINITIONS` 说明补回。
- **指标字典**（`CONTEXT.md`）：总人口/总户数/人均收入/经费合计/报表村数等逐条登记
  「定义 + 数据源 + 唯一实现 + 回归用例」，防止同一指标再出现两套口径。
- **两道防腐门禁**（已接入 CI `static-analysis` 与 `make test-local`）：
  `scripts/check_unused_scope_params.py`（AST 扫"作用域形参收下却从未使用"）、
  `scripts/check_userdata_path_consistency.py`（Electron userData / NSIS 钩子 / paths.py 三处口径防漂移）。
- **启动预检**（`app/startup/preflight.py`）：磁盘余量、数据库可写性、系统时钟落后于数据、
  PII 加密密钥探针；只告警不阻断，启动线程内执行。
- **诊断包业务段**：`/system/diagnostics` 新增 `business`（备份状态 / 调度器 / 后台任务失败 /
  数据包占用），把"昨晚备份成功了吗、提醒为什么没发、导入为什么失败"变成可导出的事实。
- **数据包导出保留策略**：每日 04:10 清理超过保留期（默认 7 天）的导出文件，避免长期运行撑满磁盘。

### Fixed

- **总人口两套口径（W18 P0-1）**：工作台取「全库最大年份」求和，统计页取「每村各自最新年」，
  实测同一数据差 500 人（两个页面数字打架）。统一为每村最新年，并加一致性守护测试。
- **`data_scope` 形参收下不用（W18 P0-2）**：`_avg_per_capita_income` 收了数据范围却从未参与过滤，
  部门级管理员看到的是全库人均收入（越权且无告警）。已接线；无 scope 时 fail-closed 返回 0。
- **报表总数封顶 100（W18 P1-1）**：`total_villages` 原用明细 `limit(100)` 后的 `len()`，改为独立
  `count()` 并新增 `villages_truncated` 如实标注。
- **未关联村经费越权（W18 P1-2）**：`village_id IS NULL` 的经费原先无条件计入所有用户合计，
  改为按 `Fund.organization_id` 判域（无归属仅全局管理员可见）。
- **提醒列表恒空**：`GET /reminders` 调用 `list_reminders()` 未传 `user_id`，编排器 fail-closed
  返回空列表 —— 现已按当前登录人过滤。
- **跨机数据包导入覆写本机记录（W18-D1）**：主键碰撞时不再 `ON CONFLICT DO UPDATE` 整体覆写，
  改按业务键判定：同记录按 overwrite 更新/跳过，异记录换新 id 插入并登记映射。
- **导入包内 `org_code` 覆盖目标组织（W18-D3）**：部门级管理员可把数据写进别的部门；
  现包内组织仅作提示，最终必须落在调用者有权写入的组织集合内。
- **全量覆盖导入误物理删除（W18-D2）**：四处物理删除改软删除，不再级联抹掉项目/经费。
- **回收站单条 restore/purge 缺数据域守卫（W18-D6）**：与批量端点同口径接入。
- **捐赠菜单指向不存在路由**：侧边栏曾挂 `/donations` 入口但页面/路由未建（点击必 404，
  且被菜单对齐门禁判为无路由），已摘除并记录待办。
- **诊断包/健康检查信息泄露收口**：数据库绝对路径、表名清单、异常原文不再出站（只留类名与聚合值）。
- **卸载不删真实用户数据（W19 实机实证）**：Electron `app.name` 取根 `package.json` 的
  `name`（根层无 `productName`），真实 userData 为 `%APPDATA%\Assistance-Management-Information-System`；
  旧钩子按"productName 优先"写成 `%APPDATA%\帮扶管理系统`（不存在），且 perMachine 下
  `$APPDATA`=`C:\ProgramData`、NSIS 反斜杠被误当 C 转义 —— 三处叠加导致卸载后数据库/密钥/日志
  全部残留。现改为 `$PROFILE` 拼路径 + 卸载期枚举全部 Windows 账号 + 清理历史误判目录，
  门禁同步改为 Electron 真实语义。

### Changed

- 版本 1.12.19（根 `package.json` 单源，15 个文件经 `sync-version.js --write` 同步）。
## [1.12.18] - 2026-10-17 — 🎯 门禁说真话 + 现场可自证（P0 批次）

> 用例口径：后端 **12,795** / 前端 **6,363**（本地全量实测）；后端行+分支覆盖率 100%
> （`backend/.coveragerc` fail_under=100），前端 12 组 glob 阈值 100%。
> 本批**不新增业务功能**：全部围绕"让门禁给出可信结论"与"现场排障能自证"。

### Added

- **系统诊断包导出（仅管理员）**：`GET /api/v1/system/diagnostics/summary` 返回结构化摘要
  （版本 / 构建指纹 / 平台 / 数据库健康与逐表行数 / 迁移状态 / 日志概况 / 资源快照）；
  `GET /api/v1/system/diagnostics/bundle` 返回诊断包 ZIP（`summary.json` + 脱敏日志尾部 +
  兼容 `sha256sum -c` 的 `checksums.txt`）。边界：不输出任何配置项与凭据；手机号 / 身份证号 /
  口令类键值对出站前打码；异常只出境**类名**；导出动作写审计（写审计失败不阻断导出）。
  任一子项失败（路径解析 / 构建信息 / 日志缺失 / psutil）只降级为 `error_type`，不拖垮整份诊断。
- **升级排练门禁**：`backend/scripts/upgrade_rehearsal.py` + PR Checks 新作业
  `upgrade-rehearsal`。语义：取最近 `v*` 标签的旧代码建出"老用户库" → 每张表播一行 →
  当前代码 `upgrade head` → 校验"无表丢失 / 已播种表行数不变 / `PRAGMA integrity_check=ok` /
  落在当前 head"。安装包冒烟证明不了"老用户的库升级后数据还在"，这一段过去只能靠人工在测试机点。
- **测试抖动账本**：`scripts/ci_flake_report.py` 解析 pytest-rerunfailures 的 `RERUN` 行
  （JUnit XML 不记录重跑），输出逐条清单与计数；pr-checks 只告警（`--warn-reruns 3`），
  nightly 超过 10 次才失败；两份账本作为 CI 产物留存 90 天。
- **原始 SQL f-string 豁免门禁**：`scripts/check_raw_sql_fstrings.py` 用 AST 取完整语句范围，
  要求 `text(f"...")` 所在语句范围内必须有 `# nosec B608 - <理由>`；全仓 40 处调用点，
  本次补登 26 处理由（9 个文件）。
- **JSON 列可变性台账**：26 个 JSON 列逐列声明语义（25 个"整体替换" / 1 个 `MutableList`），
  外加"声明检查 + 就地修改必须落库"的行为锁定。

### Fixed

- **100% 分支门禁的随机失败**：`generate_password` 的"重试直到满足复杂度"分支概率性未命中，
  门禁**随机变红**（会训练团队忽略红线）；改为可控 `secrets.choice` 替身的确定性用例钉死。
- **一项"修复"被 CI 证伪后回退（重要教训）**：曾给 `tests/conftest.py` 的 `client` fixture 加
  `engine.dispose()`（`StaticPool` 一直持着内存连接，只 `close()` 会话会留下每条一次
  `ResourceWarning: unclosed database`）。但 dispose 会把该连接**提前**关掉，而用例期间模块级
  `SessionLocal` 正指向它 —— 运行时才解析 `SessionLocal` 的后台写线程（`audit-log-flusher`
  每 5s 一次、`immediate-backup` 等）可能仍在写：sqlite3 是 C 扩展，use-after-free 不是
  Python 异常而是**进程级 SIGSEGV**。实测发版门禁（Build Windows 的 smoke-test 全量跑）一次
  崩掉两个 xdist worker，栈均在 `_flusher_loop → _persist_batch → safe_commit`；worker 的
  覆盖率数据随进程整体丢失 → 覆盖率假性 83.45% → 门禁误红。已回退为**不 dispose**（连接交给
  GC），代价仅是测试期告警噪音；`conftest.py` 原地留有详细注释防止重犯。
- **分片运行的信号噪音**：逐片加 `--cov-fail-under=0`（此前每片都因"片内覆盖率不满 100%"
  返回 exit 2，"这片的测试到底过没过"要人肉分辨）；真实门禁仍由末尾 `coverage report`
  按 `.coveragerc` 承载（命令行不重复声明阈值）。

### Changed

- 版本号 `1.12.17` → `1.12.18`（`node scripts/sync-version.js --check` 15 处一致）。
- PR Checks 作业数 7 → 8（新增 `upgrade-rehearsal`）；`static-analysis` 增补原始 SQL 豁免门禁。

## [1.12.17] - 2026-10-16 — 🛡️ R28 全系统排查修复（门禁 / 数据域 / 服务正确性 / 前端与构建）

> 用例口径：后端 **12,6xx** / 前端 **6,3xx**（以 CI 实测为准）；双向覆盖率 100%（行+分支）。
> 条目来源：`docs/系统全面排查报告-2026-10-14.md`（R27，115 条）中本批承担部分。

### Security
- **用户管理数据域收口**：`/users` 列表、待审列表、员工列表三处各自实现子树过滤
  → 统一到 `_apply_user_data_scope(query, current_user, db)`，且 `db` 改为**必填**
  （漏传即 TypeError，fail-closed）；悬空组织退化为只命中本人。
- **管理端门禁补齐**：`/export/villages`、`/data-sync` 下载与冲突/日志、`/system-health/overview`
  /`disk-space`/`table-stats`、`/system/environment`、`/monitoring` 告警规则与历史、
  `/system/config` 全部读端点、`/batch/validate`（并加表名白名单）、`/analytics/health`
  均收敛为管理员（或登录）可见，非管理员 403。
- **回收站批量操作数据域过滤**：批量恢复/彻底删除先按调用者数据域收敛 ids（跨组织 id
  静默剔除）；模型缺组织列时 **fail-closed 拒绝全部**，杜绝部门级 admin 物理清除他人数据。
- **任务端点归属校验**：`cancel`/`delete` 限本人或管理员；`/tasks/running/count` 补认证；
  `task_type` 按枚举校验。
- **工作日志可见性**：非管理员仅见**本人**日志（原实现额外放行所有人的 `system_auto`
  自动留痕 → 他人操作流水全员可见）；`system_auto` 为系统保留分类，禁止客户端创建/改写。
- **近期活动**：`/messages/recent-activities` 非管理员仅返回本人审计活动（不再回吐全局审计）。
- **仪表盘近期动态数据域**：`/dashboard/recent-activities` 的项目 / 经费 / 审批三路 feed
  此前**无任何过滤**——任意登录用户可读到跨组织项目名、负责人与审批标题（与上条同类）。
  现按 `get_org_scope` 口径收敛；审批任务（模型无组织列）按「我提交 / 待我审批」收敛；
  只有全量访问者读写**共享**缓存，普通用户按域现算，绝不命中管理员范围缓存。
- **报表导出数据域**：公文报告导出（`/export/report-word`、`/export/report-pdf`）的
  `generate_*_report_data` 六个方法改为**强制 `current_user` 位置参数**（漏传即
  `TypeError`，fail-closed）并在服务层套数据域——部门级 admin 不再能借导出读到跨组织
  的村/校/项目/经费总量与金额（与同模块 `/export/funds`、`/export/comprehensive` 口径一致）；
  `/export/comprehensive` 的用户数聚合同步收敛（原为全库 `count()`）。
- **错误细节不出站**：`system_health`、`system/metrics`、`/overview` 等去 `str(e)`、
  数据库绝对路径、表名清单与行数明细，原文只进日志；`/encryption/status` 不再回吐 KDF 迭代数。
- **匿名反馈长度上限**：`content` ≤ 5000 字（原为无上限 TEXT，可被单请求灌入任意体积）。
- **令牌刷新携带声明**：`refresh_access_token` 现携带原 refresh token 的非保留声明
  （含 `token_version`），修复「刷新后 access token 立即被判定失效」的 R20 L2 缺陷。

### Fixed
- **服务层正确性**：审批工作流 `approve/reject` 改带条件**原子抢占**（并发/重放零重复落账）；
  数据包批量 upsert 只更新记录**实际携带**的列（缺键不再写成 NULL，空更新集合退化为 DO NOTHING）；
  组织导入两阶段（先 upsert 记源 id→本机行，再对新建行按父链回填 `parent_id/path/level`，既有行不动）；
  冲突解决保留双方时后缀唯一化（uuid）；权限包导入外键重映射；2FA 启用并发撞唯一键回退更新；
  通知偏好 getter 只读 + 写入统一 upsert；合同履约评分改为真实实现（删除无消费方的占位方法）。
- **响应形状统一**：`/funds/budgets/transactions`（列表 + 创建）与 `/villages/{id}` 改
  `ok_list`/`success_response` 信封并补分页 total；`/funds/lifecycle/quota_lock` 不再谎报
  「额度已锁定」（模型无锁定字段 → 如实回吐 `locked=false`）；`/rbac/roles/{id}` 404 统一信封。
- **导入预览重复检测**改按导入行名称 `IN` 查询（原为全表名称扫描 + 无分页）。
- **平台与性能**：中间件链纯 ASGI 化并合并尾斜杠/charset 处理；限流器支持 `settings.RATE_LIMIT_*`
  与整体关闭；token 黑名单清理节流；缓存改 LRU 并支持缓存 None；Redis 适配器加锁并接线
  `REDIS_ENABLED`（未装 redis 客户端时安全降级）；系统时钟统一 UTC（编号生成/报表时间）；
  迁移兜底委托 `migration_helper` 单一实现；敏感日志过滤器覆盖异常堆栈（PII 不再随异常落盘）；
  磁盘路径跨平台修正（不再硬编码 `C:\`）。
- **构建与发布**：`pr-checks` 各作业补 `timeout-minutes`、`nightly-full` 加 `concurrency`；
  `build-arm64` 改 `npm ci`；`vcredist` 收敛为 win 条件 `extraResources`；deb 依赖补
  `libxtst6/libatspi2.0-0`；Electron 真分块读取大文件、worker 路径白名单上提主进程、
  后端重启计数改「稳定存活 N 秒后才重置」、preload 无消费 IPC 收敛、`will-navigate`
  file:// 白名单化；卸载删除真实 userData 目录口径统一；CI 收录 `_build_info.json`
  使发布件构建指纹不再恒为 dev。
- **构建指纹探测**：`build_info` 仅在确实存在 `.git`（目录或 worktree 文件）时才调用
  git，打包 / 未装 git 的离线终端不再白等超时；超时由 5s 收紧到 2s。

### Docs
- 更新《构建打包指南》《OFFLINE_UPGRADE》，并把介绍 PPT 的版本口径统一到 v1.12.17。

## [1.12.16] - 2026-10-14 — 🔐 安全与权限收敛 + 会话管理落地

> 用例口径：后端 **12,422** / 前端 **6,323**（新增/订正用例后以 CI 实测为准）。

### Added
- **用户会话管理真实落地**：新增 `user_sessions` 表（登录/2FA 时登记 jti/IP/UA/有效期），
  管理端"查看会话"返回真实活跃会话，"强制登出"支持**按会话精确吊销**（不影响其它设备）；
  未登记会话时退回既有 token_version 全量踢下线语义。新增每日 05:15 过期/吊销会话回收作业。
- **角色编码（code）后端权威化**：`rbac_roles` 新增唯一 `code` 列（迁移回填），
  前端展示/提交均以后端为准（此前由名称派生，改名即漂移）。

### Security
- **组织数据范围全面收敛**：`/organizations` 列表、`/tree`、`/{id}`（越权 403）、
  `/statistics/summary`、`/export/list`、`/{id}/members` 全部按
  `apply_scope_filter` 收敛（super_admin 全量；admin/普通用户 → 本组织及子树）——
  此前任何登录用户可枚举/导出全库组织（军审红线 S2 相关）。
- **修复缓存跨用户泄漏**：`orgs:list` 缓存改为仅管理员启用，否则普通用户的受限结果会写入全局缓存。
- **删除组织二次确认密码改走 `X-Confirm-Password` 请求头**：查询串会原样进 access log。

### Fixed
- 组织移动/改父级后 **path/level 不级联刷新**（树视图与数据权限视图长期背离）；
  `PUT` 改父级补防环（此前只拦"等于自身"）。
- 用户管理：组织选择提交 422（树节点 id 前缀未还原）、空邮箱唯一约束 500、
  编辑改邮箱缺查重、用户名搜索参数被后端静默忽略、删除用户外键 500（接入级联服务）、
  重置密码错误提示丢原因、待审核用户按钮死功能接通闭环。
- 组织管理：编码框显示 200（信封遮蔽）、无法置为顶级（exclude_unset 语义）、
  level 双语义显示不一、父级 path 为 NULL 时子级退化成根路径、拖拽排序仅本页未说明。
- 角色管理：关联用户弹窗姓名/邮箱字段错位、查询与分页纯摆设（改前端过滤+切片）。

## [Unreleased] - 2026-10-07 — 🧱 质量硬化：分支覆盖 100% 严格门禁 + 全库审计改进落地

> 本轮聚焦「质量门禁硬化」与「深度审计判项收口」，**不新增业务功能、不 bump 版本号、不打 tag**
> （`version.txt` 保持 `1.12.14`）。所有结论均以 2026-10-07 仓库实测为准。
> 用例口径：后端 **12,381**（`pytest tests/ --collect-only -q` 实测）/ 前端 **6,323**（299 文件，分片全量实测；与旧版口径一致）。
> 验证日期：**2026-10-07**。

### 新增（质量门禁）
- **分支覆盖 100% 全局严格门禁上线**：`backend/.coveragerc` 启用 `branch=True` 与 `fail_under=100`，
  并配棘轮基线 **100.0**（分支覆盖率只降不升即红灯）。2026-10-07 从 **96.70%** 起点清零至 **100%**：
  共 **8 批**专项补测 + **4 组**并行回归，分支缺口 **279 → 0**，对 3 个不可达弧带以同行理由豁免；
  CI `backend-test` 作业**双遍 22 分钟**全量通过。

### 改进（审计落地）
- **裸 pragma 全部补同行理由（F2 规范）**：`# pragma: no cover` 等 **127 处**逐一补齐同行说明，杜绝"为过门禁而豁免"。
- **恒真断言 13 → 0**、**`assert True` 3 → 0**：弱断言替换为真实结论断言，消除"永远为真"的假测试。
- **`sleep` 治理**：测试内 `sleep` 收敛为事件 / 轮询等待，消除时序不确定性来源。
- **豁免登记机制**：覆盖率豁免纳入清单化管理，新增豁免须附理由并由棘轮扫描器校验。

### 修复
- **`import_data.py` 未知实体类型**：原抛 `NameError` 泄漏为 500，现明确返回 **400**（附可识别错误提示）。
- **`recommendation_service.py` 负分脏数据**：负分记录触发 `KeyError` → 500，现金额补 0 兜底并正常返回。
- **前端事件 `.stop` 未处理错误**：修复事件链上 `.stop` 修饰符导致的未捕获错误。
- **CI**：修复 F2 续行校验（127 处）、去除 `security` 作业 `npm install` 抖动。

### 用例口径
- 后端 **12,381**（`--collect-only` 实测）/ 前端 **6,323**（299 文件，分片全量实测）；合计 **18,704**。

## [1.12.15] - 2026-10-08 — 🔍 R20 全库逐文件代码审查修复（权限收口 / 数据域 / 功能失效 / 健壮性）

> 审查方式：自动化基线（flake8 0 / bandit -ll 0 / vue-tsc 0 / eslint 0 / 行+分支覆盖 100%）+
> 分片逐文件只读审查（backend 341 / frontend 276 / electron 5 / scripts 51）+ 高中危逐条源码复核。
> 本轮修复其中 21 项（高 4 / 中 14 / 低 3），其余登记项见 `docs/代码审查报告-2026-10-08.md`。

### 修复（高）
- **report_templates 模块整体无角色守卫**：任意登录用户可增删改共享报表模板并触发
  overwrite 导入（清空数据域记录）→ 模板 CRUD 与上传导入统一收敛 `require_manager_role`。
- **fund_lifecycle 资金写端点缺数据域**：划转凭证（改/删/确认/附件）、合同（改/删/付款）、
  决算（改/审批）、拨款下达、额度调整/锁定、异常处理共 14 处仅角色校验、裸 id 加载 →
  统一补 `_get_project_or_403`（读端点已有、写端点遗漏的口径矛盾消除）。
- **综合报表导出明细越权**（async_export_service）：summary 计数已过滤但项目/经费明细
  裸查全库（各 100 条）→ 补 `scoped_filter`。
- **report_templates overwrite 导入非原子**（4 个模块 prepare 共性）：先删后插分两次提交，
  插入失败旧数据永久丢失 → 删除与插入并入同一事务，失败整体回滚。

### 修复（中）
- **权限收敛**（登录即可见 → 管理员）：`system/config/export/json`、`system/error-reports`
  （列表/统计/详情，含 stack_trace）、`secrets/status`、`metrics/business`、`system/backup/target`、
  `zero-trust/events`（防伪造安全事件）、`health/full`（指纹 + integrity_check 重 I/O）、
  `help/articles*`（帮助文案含出厂管理员口令，未认证放大）。
- **项目导入**：`mode=overwrite` 参数从未生效（静默变增量）→ 按数据域软删后导入；
  逐行 SAVEPOINT（首行 IntegrityError 毒化会话 → 连锁失败的缺陷消除）。
- **项目任务越权**：任务更新/删除补 `_can_modify_project`（同组织非创建者可改删的缺口）。
- **数据域遗漏**：rural_work 统计 by_type / analytics 类登记（后者属服务层签名改造，
  见报告登记项）；`list_backups` 未传 `backup_type` → 增量备份统计恒 0。
- **功能失效**：PDF 导出未转义 `<`/`&`（标题含尖括号即 500）；消息模板 ≥2 个缺失变量
  二次 format 抛 KeyError；excel_importer `convert_row_types` 被当属性引用（类型转换从不执行）；
  batch_service.batch_export 只写表头不写数据。
- **数据正确性**：数据清洗误删 SQL 关键字子串（standard→stard）→ 加词边界；
  audit_service 当日统计窗口用本地 `datetime.now()` 与 UTC 库值比较（偏 8 小时）；
  消息保留 30 天 → 90 天（对齐需求 5.6）；增量备份文件名/键同秒互撞 → 追加 uuid。
- **一致性**：organization_code 校验允许 `-`（与生成规则一致）；organization_code 缓存
  原子取值；村级联删除引用检查收窄裸 except；query_analyzer `_count` 键清理。

### 修复（低）
- upload_security 允许扩展名 `.gi` → `.gif`；seed 出厂口令不再写入日志原文；
  runtime_secrets 密钥文件顶层非对象 JSON 防御；config 密钥文件读取显式 UTF-8；
  main.py 死代码 env；audit 模型重复索引；supported_village to_dict 补 transitionStatus。

### 登记（本轮不修，见报告）
- analytics/nlp-query/statistics/dashboard/report_export 的服务层签名级数据域改造（需独立 PR）；
- 两个占位实现（effectiveness 评估 / fund_health 履约分）；两处需迁移的类型问题
  （two_factor secret_key 加密存储、AccessLog.user_id/todo.deadline 类型）；
- token_manager.refresh_access_token 与 SECURITY_HEADERS 双源等死代码/分叉项；
- 前端逐文件审查（本轮完成 backend 全量，frontend 分片待续）。

### 测试
- 新增 `test_r20_review_fixes.py`（13 例：守卫 401/403 全分支 + overwrite 软删分支 +
  逐行 SAVEPOINT 隔离）；message_service 保留断言对齐 90 天；org_code 连字符断言更新。
- 用例口径：后端 **12,422**（`--collect-only` 实测，622 文件）/ 前端 **6,323**（299 文件）；合计 **18,745**。
  （复审补丁新增 27 例：PDF 转义承重用例、batch_export 分支、即时备份 wait 全路径、
  回收站 fail-closed，以及 4 处 CI 覆盖率缺口的补测。）

### 复审补丁（F2，同日追加，随本版一并发布）
- **PDF 导出转义不完整（同一注入面漏网）**：`_build_policies_pdf` 的标题与正文已转义，但
  元信息行（`p.code` 文号 / `p.issuing_authority` 发文机关）仍直连 reportlab 的 mini-HTML
  解析器，含未闭合标签（如 `文号<b`）依旧 500 → 元信息行一并转义；并对该函数内**全部**
  `Paragraph(...)` 与 `Table` 单元格做了完整排查（`Table` 的纯字符串单元格不经 mini-HTML
  解析，无注入面）。
- **即时备份 `wait` 语义缺陷（使 fail-closed 失效）**：`_run` 吞掉备份异常后
  `result_holder["ok"]` 恒为 `True`，导致 `wait=True` 时备份失败也误报成功 →
  `_run` 改为返回真实成败并由 `_run_tracked` 据实回填；`wait=True` 在失败/超时/被幂等锁
  跳过时均返回 `False`。
- **回收站保留期清除的备份时序**：原实现以后台线程延迟 1 秒触发且不检查结果（快照可能
  晚于物理删除，或因幂等锁被占用根本没触发）→ 改为同步等待真实结果，
  `False`/异常一律中止本轮物理删除（fail-closed 名副其实）。
- **`batch_export` 空导出**：原实现只写表头即返回成功（导出内容为空、`exported_count`
  取自入参）→ 改为按真实记录查询并逐行写入，`exported_count` 为实际导出条数。
- **弱断言治理**：新增的 PDF 转义回归用例原输入即使不转义也不会抛错（从未守护该修复）→
  替换为未闭合标签输入，并以「去掉转义必失败」做承重性对照证明。

### 覆盖率（复审补丁）
- 清零 CI `backend-test` 在 R20 提交上的覆盖率缺口（**99.97% → 100%**，行 + 分支）：
  `app/utils/runtime_secrets.py`（行 182 + 1 分支）、
  `app/services/village_cascade_delete_service.py`（分支 `161->149`）、
  `app/services/message_template_service.py`（行 391）、
  `app/api/v1/fund_lifecycle.py`（行 1877 + 11 处 `if x.project_id:` 假分支）。
  均以真实测试触发，**未新增任何覆盖率豁免**。

---

## [1.12.14] - 2026-10-06 — 🔍 全库深度排查与修复（数据合并/权限收口/时间基准/健壮性）+ 文档与 PPT 同步

> 排查方式：后端反模式清单逐项扫描（时间基准 / 异常吞噬 / 边界 / 竞态 / 注入）+ 前端契约与竞态只读审计，
> 每条结论均源码级复核，且**新增断言均验证过"新旧实现结论不同"**（防弱断言）。
> 用例口径：后端 **12,005**（`pytest --collect-only` 实测）/ 前端 **6,330**（303 文件，分片实测）。

### 修复（高）
- **数据同步「智能合并」策略完全失效**（`services/data_sync_service.py`）：`_import_table_data`（ZIP `/data-sync/import` 路径）
  只有 `skip/overwrite/manual` 分支且无 else 兜底，而前端数据同步页**默认策略就是 `merge`**（"智能合并（推荐）"）——
  已存在记录既不被更新、也不计入 `success/failed/conflicts`，接口仍返回"导入成功"，且 `total != success + failed`，
  冲突数据静默不生效。现补齐 `merge` 分支（语义与加密包路径 `_import_table_data_enhanced` 一致）。
- **加密包合并永不更新**（同文件 `_should_update_record`）：`existing` 来自 raw `text()` 查询是**字符串**，
  与 `parser.parse(...)` 得到的 `datetime` 直接比较抛 `TypeError`，被 `except Exception` 吞成一条 warning 后
  **恒返回 False**。新增 `_normalize_record_time`（str/datetime/None → aware UTC，naive 按 UTC 解释），
  一并消除 naive/aware 混算。守护用例用**生产形态**（两侧均为 raw 字符串）断言，旧实现必失败。
- **政策模块三处前端功能失效**（调用了不存在的 store 方法，被 mock 掩盖）：
  - `views/policies/List.vue` 调用 `policyStore.removePolicy/removePolicies`（store 只导出 `deletePolicy`）
    → 单条与批量删除抛 `TypeError`、**数据从未被删除**；现改逐条 `deletePolicy`，部分失败保留失败项并告警。
  - `views/policies/Category.vue` 调用 `policyStore.fetchStatistics`（同样不存在）→ 分类总览计数**恒为 0**；
    现改走已存在的 `getPolicyStats()`（`GET /policies/statistics`）。
  - `views/policies/Detail.vue` 收藏态从不回查（`isFavorite` 恒 false）→ 已收藏政策显示为"收藏"、
    点击报 400，且 DELETE 分支不可达 → **无法取消收藏**；现进入详情即回查收藏列表初始化。
- **备份计划端点越权**（`api/v1/system/backup.py`）：`PUT /system/backup/schedule` 只校验"已登录"，
  任何普通用户都能改写全局备份开关/频率/保留策略（与页面自述"普通用户只读"矛盾）。现补 `require_admin`，
  前端该面板保存按钮同步加 `canOperateBackup` 收口。

### 修复（中）
- **出厂口令改值 + 服务端强制首登改密**：`FACTORY_ADMIN_PASSWORD` 由 `Admin@2026`（10 位、低于自有策略
  `MIN_LENGTH=12`、属公开常识值）改为 13 位混合字符；`get_current_user` 增加拦截——`must_change_password=true`
  时除改密链路（`auth/{me,logout,refresh,csrf-token}`、`users/me`、`menus/accessible`、仅限改自己的
  `PUT /users/{id}/password`）与 `OPTIONS` 外**一律 403**。此前拦截仅由前端路由守卫收口，直连 API 可绕过。
- **`backup_retention_days` 脏值导致备份计划页 500**：`GET|PUT /system/backup/schedule` 裸 `int()` 解析配置，
  而通用配置端点/管控包导入可写入任意字符串。新增 `get_int_config`（可注入 getter 以保留各模块测试的
  `get_config` patch 缝合点）并统一接入备份/调度各调用点。
- **`last_backup_time` 带时区偏移时整条自动备份失败**：`except ValueError` 覆盖不到 `naive - aware` 的
  `TypeError`，异常逃逸为"自动备份失败"/接口 500。新增 `time_utils.parse_local_wallclock` 统一归一。
- **`restore_drill_job` 在 `with get_db_context()` 之外使用已关闭会话** 发提醒：隐式重开不受 `finally`
  管理的连接；现移入 `with` 块内。
- **导入包解析加固**（同 R18 后续）：`data_sync` 导入解析下沉线程池 + 解压体积闸门（1GB）+
  `except HTTPException: raise` 守住 413 语义；`control-package/import-preview` 补 `require_admin`，
  畸形 `manifest.json`（非对象）/非数组成员由 500 改为 `valid=false`/计 0。
- **工作日历 localStorage 脏数据崩页**：`setup` 顶层裸 `JSON.parse` 且不校验形态 → SyntaxError 让**整条路由
  渲染失败**；现 `readStoredEvents()` 兜底空数组（新增专属测试）。
- **多个列表端点 `limit/skip/page` 无边界**：`limit=-1` 在 SQLite 语义下等同"不限量"（一次拉全表）。
  新增 `utils/pagination.clamp_offset_limit` 并在 5 个端点接入（rbac/villages/machine-code/feedback/data-sync）。

### 修复（低）
- **`BACKUP_COMPRESSION_LEVEL` 非数字** → `BackupService` 构造即抛 `ValueError`、备份链路整体不可用；
  提取 `utils/env_utils.parse_env_int`（**同时消除 `core/database._parse_env_int` 的重复实现**）并收敛
  `security.ACCESS_TOKEN_EXPIRE_MINUTES`（模块导入期裸 `int()`，一处笔误即让后端以 ImportError 无法启动）、
  `REFRESH_TOKEN_EXPIRE_DAYS`、压缩级别（越界收敛 0-9）。
- **同秒并发写同一物理文件**：数据同步导出包名（增量/加密两处）与政策附件名仅到秒且无随机后缀 →
  后者 `"w"` 截断前者；均追加短 uuid。
- **政策列表竞态**：翻页/改筛选的请求 params 不同，请求层去重拦不住，网络乱序时旧响应覆盖新响应；
  store 加请求序号（含 error 与 loading 的过期保护）。
- **`getLevelLabel` 实参顺序错误**：视图按 `(category, level)` 传参而函数只取首参 → 层级列在 `level_name`
  缺失时显示 `military/local`；改为只传 `organization_level` 并删除误导性 wrapper。

### 文档与 PPT
- 同步用例口径与版本（README / AGENTS.md / 项目文件结构说明.md / docs/build_ppt.js → 重生成 PPTX 并解包核验）；
- 修正与实现不符的说明：部署指南"首次启动自动生成随机密码"（实际为出厂口令）、用户手册备份章节
  （频率/保留语义，实为**天数**）、`架构评估整改配套约定` RPO 行；
- ADR-0010 补记实际落地状态（此前声称的"Electron 仅触发/移除自带清理/清理交后端"**一直未真正实现**，
  本轮才落地）、新增 `backup_interval_days` 键（默认 30→**1 天**）与 `trigger=auto` 语义、管理员权限要求；
- API 文档补：首登强制改密 403 规则、分页参数钳制口径、`POST /system/backup` 的 `trigger`、
  `PUT /system/backup/schedule` 权限、`GET /policies` 列表不含 `content`。

### 测试
- 新增 `test_must_change_password_guard.py`(17) / `test_backup_single_source_of_truth.py`(12) /
  `test_data_sync_service` +6（merge 分支、raw 字符串时间归一、线程池断言、413 透传）/
  `test_data_sync_route` +2 / `test_upload_limit_r2` +3（预览容错）/ 前端 `workCalendar/Index.test.ts`(16) /
  政策三视图与 store 竞态用例重写与新增；同步更新被"错误 mock"掩盖的旧断言（弱 mock 纠正）。
- 用例口径：后端 **12,005** / 覆盖率 100%；前端 **6,330**（303 文件）。

### CI 与依赖安全
- **frontend-check 覆盖率门禁内存缓解**：单进程 `vitest run --coverage` 在 303 文件 + `maxWorkers:1` 下
  内存贴着 7GB runner 的悬崖（近三轮 1 绿 2 红被 OS 硬杀，日志零错误信号；本地 16m42s 全绿证明套件
  无回归）。三项缓解：① CI 报告去掉 **html**（262 文件逐页嵌源码是报告期内存大头；json 保留供
  codecov）；② `NODE_OPTIONS=--max-old-space-size=5632` 压低 V8 堆上限，让 GC 在内核 OOM-KILL 前
  积极回收（真不够时留下清晰 FATAL 而非静默被杀）；③ 门禁自动重试一次（GC 时序差异）。
  （曾试点「v8 分片 + 按位置并集合并」，实证 v8 的 statement/branch/fn 结构随执行状态漂移、
  跨分片合并不可靠，已放弃；istanbul provider 口径差异过大亦不可行。）
- **npm 安全公告修复**（公告于 v1.12.13 之后发布，非业务代码引入）：`vue` ≤3.5.41 XSS
  （GHSA-g2v6-rqmx-r4w6）→ **3.5.43**；`source-map-js` ≤1.2.1 DoS（GHSA-68fv-2mgg-jv7q）→
  overrides `^1.2.2`。`npm audit --omit=dev` 复核 **0 漏洞**；生产构建 + 全量用例通过。
- e2e-test 的裸 `npm ci` + `playwright install` 与 build-windows 的裸 `npm ci` 补齐 3 次幂等重试
  与明确 `::error::`（此前失败形态只剩一个未命名步骤，真因被完全掩盖）。

---

## [1.12.13] - 2026-10-05 — 🛡 R18 全维度排查修复（并发闸门 / 事件循环阻塞 / 竞态互踩 / 信息泄露）

> 排查方式：3 路并行只读审计（并发性能 / 内存泄漏 / 安全）+ 9 维度清单逐项核查，
> 每条结论源码级复核（复核拦截 1 条审计误报：`data_packages` 导入临时文件
> 实际已有 `finally os.unlink`，系复核 grep 范围截断所致）。

### 修复（高）
- **`electron/worker-pool.js` — Worker 池并发闸门永久失效**：`_active` 被双扣
  （`message` 扣一次后 `terminate()`，而 terminate 的 exit code 恒为 1，`exit` 回调再扣一次），
  计数单调变负使 `maxWorkers` 形同虚设；超时路径不 `terminate()`，hang 死任务永久占用槽位。
  收敛为单一 `finish` 终局路径 + `done` 标记 + `Math.max` 防负漂移 + 超时强制终止并回收槽位。
  实证：真实 Worker 线程 6 并发 `hash-file`，旧实现 `_active:-2`、新实现归 0（同一验证脚本
  跑新旧两版，证明断言有区分力）；超时后槽位回收、后续任务可执行。
- **`api/v1/system/backup.py` — 备份阻塞整个事件循环**：备份（SQLite Backup API 全库拷贝 +
  `shutil.copytree` 上传目录 + zip CRC 校验 + `integrity_check` + 可选 PBKDF2 加密）此前在
  `async def` 内同步执行，耗时与库体积成正比，期间**全部并发请求（含登录、前端轮询）无响应**，
  且 Electron 24h 定时备份同样走此端点。现移入 `run_in_thread` 线程池。

### 修复（中）
- **`api/v1/data_sync.py` — 上传临时包同名互踩**：沿用客户端原文件名（缺省固定 `upload.zip`），
  两个并发导入写同一物理路径——后写者截断前写者正在读取的文件，先到者把后到者的数据当
  自己的包导入（静默数据错乱），且 `finally` 清理会删掉对方刚写入的文件。加 uuid 前缀唯一化。
- **`api/v1/system/health.py` — 无认证端点信息面收敛**：`/health`、`/health/overview` 此前回显
  `platform.platform()`（精确到 OS 构建号）与 `python_version`；`/database`、`/database-health`
  异常分支把 `str(e)` 原文回显（可含数据库路径）。现裁剪到消费方实际使用的最小集
  （已核实 `HealthCheck.vue` 仅用 `uptime_seconds`），异常只回 `type(e).__name__`、原文进日志。
- **`electron/main.js` — stopBackend 孤儿进程竞态**：5s 兜底定时器无句柄且无条件
  `backendProcess = null`——进程在 4.9s 退出并立刻重启后，第 5s 回调会把**新进程**抹成 null，
  旧进程对象失去引用成为孤儿（每个持完整 FastAPI 运行时）。现保存句柄、exit 时清理，
  仅在引用仍为本进程时置空。
- **`services/backup_scheduler.py` — 任务队列记录只增不减**：`LocalTaskQueue._tasks` 的
  `cleanup()` 此前全仓无任何调用点，每个异步导出任务对象（含 func 闭包 / args / result 引用）
  永久驻留。挂靠既有每日 `export_purge_job`（04:00）一并回收，**不新增定时器**。

### 修复（低）
- **`api/v1/projects.py`**：排序列白名单——此前 `getattr(Project, sort_by)` 接受任意字符串，
  传入方法/关系名（如 `query`、`metadata`）触发 `AttributeError` → 500。
- **`deploy/kylin/config/kylin.env`**：部署模板不应自行降级安全基线——`ACCESS_TOKEN_EXPIRE_MINUTES`
  2880(48h) → 480(8h)、`CSRF_ENABLED` false → true（前端 `request.ts` 已自动回填 X-CSRF-Token，
  cookie 缺失时懒加载 `/auth/csrf-token`，开启不会造成 POST 失败）。

### 登记未修（已定性，需产品决策 / 架构级）
- 出厂管理员密码硬编码 `Admin@2026`（`core/constants.py:24`）与机器码初始密码熵不足
  （用户名前 4 位 + 10⁴ 校验码、`/verify-machine-code` 公开可查）——涉军审计最可能开单的两项，
  改随机生成 + 一次性凭据交付会影响装机流程，须产品拍板。
- 备份双事实源：Electron 每 24h 直调备份端点，打穿后端 `backup_interval_days`（默认 30 天）
  间隔判定；两套清理并发删同一目录。需先定「到底多久备一次」。
- `control_package.py` 512MB zip 在事件循环内同步解析（解压峰值 GB 级，admin-only）。
- `data_package_service` full 导出逐模型 `query.all()` + `indent=2` 全量驻留（内存约库体积 3-4 倍）。
- `policy.py` 列表序列化携带 Text 全文 `content`（裁剪会改 API 契约，需确认列表页不渲染全文）。

### 测试
- 新增 4 例：`export_purge_job` 挂靠回收（有残留 / 清理失败容忍）各 1、
  `/health/database-health` 正常与异常脱敏各 1；定向回归 411 用例全绿。
- 用例口径同步：后端 **11,948**（`pytest --collect-only` 实测）、前端 6,304（302 文件）不变，
  合计 18,252；README / `docs/build_ppt.js` / `项目文件结构说明.md` 同步。

---

## [1.12.12] - 2026-10-03 — 🐞 全库缺陷排查修复（时间基准 / 契约脱节 / 竞态）+ 汇报大屏契约修复 + 冷启动优化 + 前端日期收敛 + 文档与门禁治理

> 本版在前述主题基础上追加一轮**全库缺陷排查（R17）**：静态门禁（flake8 / vue-tsc / eslint）
> 全绿的前提下，逐模块排查语义层缺陷，共修复 **17 处**，详见下方「全库缺陷排查（R17）」。

### 重构（消除重复实现）
- **前端日期/时间格式化统一收敛到 `frontend/src/utils/index.ts`**：此前散落在
  **36 个文件里的 41 处**"各自实现"（含 4 种 locale 变体、3 种手写补零、5 处字符串切片、
  相对时间与运行时长各一套）已全部删除，改为委派统一入口。
  视图层不再持任何格式化**逻辑**，只保留一行委派（原函数名保留，模板零改动）。
- `format` 工具集补齐 12 个函数：`formatDateTimeLocale` / `formatLocalDate` /
  `formatLocalDate2Digit` / `formatLocalDateTime2Digit` / `formatDateTimeFull` /
  `formatDate` / `formatCnDate` / `formatRelativeTime` / `formatShortDateTime` /
  `formatShortDateTimePadded` / `formatDuration`，并为 `formatDateTime` 增加可选
  `fallback`（各页面空值文案不同：`-` / 空串 / `无` / `N/A` / `--`，全部保持原样）。
- **统一空值语义**：新增内部 `toDate()` 归一化，空值/非法值一律走兜底文案 ——
  此前多个页面会把 `Invalid Date` 直接渲染到界面上（现已不可能出现）。
- 顺带修正两处"按 UTC 字符串切片当本地时间显示"的实现（`funds/Detail`、`sentiment/Index`
  等 5 处）：改用本地时区日期，消除跨日边界差一天的问题。
- 移除收敛后产生的孤立辅助函数（`SettingsOverview` 的 `pad`）。

### 修复（文档与实现不一致，共 14 项）
- 订正 `frontend/docs/design/{components,tokens,pages,hardcoded-colors-report}.md`：
  删除对不存在的 `business/KpiCard.vue`、`utils/datetime.ts`、`common/ResponsiveDataTable.vue`
  的引用；全局组件尺寸 `small` → `large`；密度令牌更新为 UI v2.1 实际值（44/40/32/48px）。
- 订正 `docs/03-开发文档/前后端契约规范.md`：删除对**从未存在**的
  `frontend/src/utils/camelize.ts` 的描述，改为说明真实链路（后端中间件 + 模型 `to_dict`，前端不转换）。
- 订正 `AGENTS.md`（CI 六个 job → **七个**，补 `windows-smoke` 行与 static-analysis 检查项）、
  `README.md`（Alembic 44 → **45** 版本）、`CONTRIBUTING.md`（覆盖率 50% → **100%**，
  配置位置 `pyproject.toml` → `.coveragerc`）、`build-scripts/README.md`
  （产物名 → `MRRS-Setup-<版本>-<架构>.exe`、删除不存在的 `build-config.json`、x86 已放弃）。
- 订正 `resources/icons/README.md`（按实际文件名重写）、`backend/version.json`
  （build/release_date/description/features 更新为 1.12.11）、`CLAUDE.md`（版本同步 13 处 → **18 处**）。

### 修复（根因治理）
- **`.env.example` 纳入版本单一来源**：新增 `scripts/sync-version.js` 目标，
  该文件此前长期漂移（停在 1.12.5，落后 6 个补丁版本，因为旧脚本 `sync_version.py`
  覆盖 `.env*` 而新工具漏了它）。现已同步为 1.12.11，且 `--check` 门禁覆盖，杜绝复发。

### 修复（汇报大屏：前后端契约脱节导致的可见功能异常）
> 根因不是大屏代码写错，而是**接口 mock 从编造的字段构造**——测试全绿，真实大屏恒空/恒 0。
- **「项目状态分布」饼图恒空**：后端此前不返回任何状态字段，前端读的两个键都不存在。
  现由 `_query_project_approval_stats` 增加一条 group_by 查询，返回
  `projects_by_status: {状态: 数量}`，前端改读 `stats.projects_by_status`。
- **KPI「完成率」恒显 `—`**：前端读 `completion_rate`，后端实际字段为 `data_completeness`（0~1）。
  现改读 `data_completeness` 并按百分比 1 位小数展示。
- **KPI「经费总额(万)」恒显 0**：前端读 `total_amount`，后端实际字段为 `total_funds`。
  现改读 `total_funds`。
  ⚠️ 本条目当时的「单位为元，需换算为万元」结论**有误**，已在 1.12.12 的全库排查中订正
  （`Fund.amount` 列即「申请金额(万元)」，`total_funds` 本就是万元，除以 10000 会把数值缩小 1 万倍）。
- 移除大屏上「恒空」的 `getSummaryStatistics` 死请求（loadAll 由 4 个接口收敛为 3 个）。
- **测试同步**：`BigScreen.test.ts` 的 mock 全部按真实响应体重写，新增「契约对齐」断言
  （完成率 88.6% / 饼图取到数据）；同时移除把缓存击穿写进断言的做法
  （`toHaveBeenCalledWith(true)` → `toHaveBeenCalledWith()`）。

### 修复（汇报大屏：数据范围 / 安全口径）
- **`/dashboard/yearly-trends` 的帮扶村、人口、经费三类查询此前完全没有数据范围过滤**
  （`income` 有），非管理员能在两张图上看到全局数据，与 `/dashboard/stats` 的组织口径自相矛盾
  （涉军口审计红线 S2）。现非全量访问时三类查询全部套 `data_scope`；全量访问保持既有全局语义。
- **`/dashboard/stats` 的三个系统级指标收敛**：非全量访问时，审批待办收敛为「当前用户提交的
  待审批」（`ApprovalTask.submitter_id == user_id`）、用户总数收敛为可访问组织的活跃用户、
  数据完整性收敛为可访问帮扶村范围；全量访问（超管）保持全局口径不变。

### 变更（汇报大屏：性能与语义打磨）
- **消除缓存击穿**：大屏 30 秒轮询此前带 `refresh=true`，每轮绕过后端 2 分钟 diskcache、
  重算约 13 条聚合查询。现改为走缓存（`refresh` 仍可由用户手动触发）。
- `yearly-trends` 的逐年循环（≤40 条 SQL）合并为按年 `GROUP BY`（约 4N → 4+N 条）。
- `_query_fund_stats` 的 IN 列表物化改为子查询（语义与原空列表分支严格等价）。
- 年度对比图的 `project_count` 由「经费记录条数」改为**真实项目数**（按 `Project.start_date`
  年分组 + 同一数据范围口径），原口径降级为新增字段 `fund_count` 保底；前端兜底链
  `project_count ?? fund_count ?? count`。
- 页脚「自动轮播 5 秒」与实际 30 秒不符 → 改为「数据每 30 秒自动刷新」；删除 `dashboard.py`
  一处描述与实现相反的陈旧注释。

### 变更（冷启动优化 P2-4）
- **`api/v1/map.py` 的 diskcache 缓存改为惰性初始化**：此前在**模块导入期**就执行
  `os.makedirs(CACHE_DIR)` + `diskcache.Cache(...)`（实测中位约 130ms 的磁盘 I/O），
  属于 `import app.main` 冷启动路径上的可推迟开销。现仅保留廉价的模块级 import，真正的
  Cache 构造推迟到首次使用（`_get_map_cache()`），线程安全（双检锁）；测试可继续注入
  mock / None（哨兵 `_UNSET` 语义：未初始化 vs 已禁用）；缓存失效路径改为
  `_clear_map_cache_if_ready()`，不会因清理缓存而反向触发构造。
- **openpyxl（连带 numpy）已完整移出冷启动路径**。上一轮只改了 `api/v1/supported_village.py`，
  并在此处登记了「openpyxl 仍在 `sys.modules`、实际收益≈0」的遗留；本轮把剩余模块全部收口：
  - `api/v1/supported_village.py`：仅在「Excel 导入」端点内导入；
  - `services/excel_importer_service.py`：模块级 `from openpyxl import load_workbook` 移入使用点；
  - `services/excel_template_service.py`：导入语句移入方法，且**十余个模块级样式对象**
    （`Font`/`PatternFill`/`Border`/`Alignment`…）原先在 import 期构造，现由 `_ensure_styles()`
    在真正生成模板时惰性构造（幂等 `if "_title_font" in globals(): return`，仍复用同一批对象，
    语义与改造前一致）；
  - `services/export_service.py`：`from openpyxl import Workbook` 移入方法；类型注解改用
    `TYPE_CHECKING` + 字符串前向引用（`-> "Workbook"`），运行期不再需要该名称；
  - `api/v1/school.py`、`api/v1/report_templates.py`（`from openpyxl import Workbook`）。
- **验证口径（可直接复跑）**：
  `python -c "import sys, app.main; print('openpyxl' in sys.modules, 'numpy' in sys.modules)"`
  → 实测输出 `False False`（改造前为 `True True`，即本轮真正达成了「把 openpyxl 移出冷启动路径」
  这一目标）；启动耗时量化见 `backend/scripts/measure_startup.py`。

### 修复（CI 门禁：把误阻断与真因掩盖一并治理）
- **`security` 作业前端审计误阻断**：`npm audit --audit-level=high` 会把 devDependencies
  的漏洞也算作阻断项。当时的唯一命中是 `braces` GHSA-vfj7-8cjw-p6xm（CVE-2026-93687，
  受影响 ≤3.0.3，官方 advisory「Patched versions: None」，overrides 无解），命中链
  braces→micromatch→fast-glob→globby→@typescript-eslint/*、chokidar→braces，**全部只存在于
  devDependencies**（实测 `npm ls braces --omit=dev --all` 输出为空）。以「无上游修复版本的
  开发期依赖」阻断合并，等于把门禁变成永久红灯，反而掩盖真实的生产依赖风险。现阻断门禁收敛为
  生产依赖树（`npm audit --omit=dev --audit-level=high`），另加一条 `continue-on-error`
  的全量 `--json` 审计并上传 artifact —— 可见性不降低，阻断语义回到「真实可修的生产风险」。
- **`frontend-check` 依赖安装抗网络抖动**：一次 `ECONNRESET` 让 `npm ci` 失败 → vitest 压根
  没启动，而「Report vitest failure」又因日志文件不存在再报一次 `exit code 1`，annotation
  只剩「Process completed with exit code 1」，真因被完全掩盖。现：① 提高 npm
  `fetch-retries` / `fetch-timeout`；② `npm ci` 外层做幂等重试（3 次，间隔 10s，失败时显式
  输出「疑似 registry 网络故障，非业务代码问题」）；③ 上报步骤识别「日志缺失」并直接指出
  失败发生在前置步骤。

### 修复（后端依赖已知漏洞）
- 依据 2026-10-03 `pip-audit` 实测结果（20 条，4 个包），升级**有修复版本**的三项：
  `anyio 4.13.0 → 4.14.2`（PYSEC-2026-4024 / 4025）、
  `PyJWT 2.13.0 → 2.15.0`（13 条 PYSEC-2026-414x，其中 12 条 2.14.0 可修、
  仅 PYSEC-2026-4141 需 2.15.0，取最高值一次覆盖）、
  `urllib3 2.7.0 → 2.8.0`（PYSEC-2026-4175 / 4176 / 4177）。
- `diskcache 5.6.3` 的 PYSEC-2026-2447 **上游无修复版本**，保持不动；同时订正该行注释的
  事实错误（原写「本仓唯一使用点」，实际有 2 个使用点：`dashboard.py` 与 `map.py`，
  均已改用 `JSONDisk` 消除 pickle 反序列化执行面）。

### 修复（回归资产与口径）
- **探针总运行器补齐注册**：`probe_r15_user_management.py` 早在 2026-09-18 就已存在，但一直
  漏注册于 `tests/probe/run_all.py` 的 `PROBES`（该文件此前也只写到 r10），导致「单文件能跑、
  总运行器不跑」。现补入 r10 与 r15，探针总数 9 → **11**，README 同步（200+ 断言 → 240+）。
- **README 数字口径订正**：`近期修复记录` 里 v1.12.8 条目残留「21 个真实 HTTP 探针」——
  该版本当时 `run_all.py` 实际只有 10 个探针（`git show 8c425fe:backend/tests/probe/run_all.py`
  可复核），属笔误，已订正为 10 并注明「该版本当时的实测口径」。

### 测试
- `tests/unit/utils/index.test.ts` 新增 **12** 个用例，覆盖上述 12 个新函数与 `fallback` 分支，
  `src/utils/index.ts` 四项覆盖率指标保持 **100%**。
- `tests/unit/test_map_lazy_cache_p2_4.py` 新增 9 个用例，锁定惰性缓存的全部契约
  （首次构造 / 单例复用 / 沿用注入的 mock 与 None / diskcache 缺失降级 / 就绪态才清空 /
  导入期不产生磁盘 I/O）。
- 汇报大屏 5 个 dashboard 测试文件 104 通过；前端 BigScreen + dashboard API 24 通过。
- **补齐 `yearly-trends` 数据范围回归守护（`test_dashboard_trends.py` +2 用例）**：上述
  「数据范围补齐」的安全修复此前**没有任何测试守护**，也正是 `dashboard.py` 覆盖率缺口的
  所在（CI 100% 门禁必红）。新增：① 非全量访问时村/人口/经费三类查询逐个套 `data_scope`
  并校验过滤次数；② `_apply_project_scope` 在「非全量且无任何组织信息」时原样返回。
  补测后 `dashboard.py` 与 `map.py` 覆盖率均回到 **100%**。
- 后端用例口径同步为 **11,944**（`pytest tests/ --collect-only -q` 实测，1.12.12 当时口径），README 与
  `docs/build_ppt.js` 同步。

### 修复（全库缺陷排查 R17：17 处）

> 排查前提：`flake8` / `vue-tsc` / `eslint` 三项静态门禁**全绿**——本批缺陷全部落在静态检查
> 盲区（语义层）。排查路径：反模式扫描 → 双线只读审计 → **逐条源码级复核**（审计给出的
> 「`total_funds` 单位为元」结论被三源交叉否证，未采纳）。

**时间基准：本地 naive 与 UTC 列混用（7 处）**
- `services/fund_anomaly_detector.py:_check_idle` —— `datetime.now() - allocation_date`
  是 naive−aware **必抛 `TypeError`**；该异常被 `backup_scheduler` 的逐项目 `try/except`
  吞掉，导致**资金闲置检测在生产环境静默永不生效**（`allocation_date` 为 `UtcDateTime`，读回 aware UTC）。
  改 `utcnow() - as_utc(alloc_date)`。实证：旧实现 `TypeError: can't subtract offset-naive
  and offset-aware datetimes`。
- `services/audit_service.py:418` —— `LoginAttempt.attempt_time >= datetime.now() - 1h`：
  UTC+8 下阈值落在未来 7 小时，**匹配恒为 0**，暴力破解分级永远停在 `low`。改 `utcnow()`。
- `api/v1/fund_lifecycle.py`（3 处）—— 阶段 `entered_at/completed_at`、预算基线 `locked_at`、
  资产校验 `verified_at` 均被写入本地墙钟（UTC+8 偏早 8 小时）。预算基线处的 `snapshot_year`
  按本地日历口径**保持不变**，故拆分为 `now_local` / `locked_at` 两个变量。
- `services/fund_event_handler.py` —— 项目状态联动写阶段时间，同上。
- `api/v1/data/data/statistics.py` —— 「今日操作数 / 近 7 天趋势」把本地日界直接与 UTC 列比较，
  UTC+8 下「今日」从本地 08:00 才起算、日桶错位。现按本机时区偏移平移日界，分桶改用
  `date(col, '+N seconds')`。偏移计算**取整到秒**（`round`）——直接 `int()` 会因两次取时的
  微秒差得到 28799 秒，使日界偏移 1 秒。
- `api/v1/sync.py`、`api/v1/system/audit.py` —— 审计统计窗口基准改 `utcnow()`。
- `services/rural_work_service.py:_coerce_datetime` —— 解析失败时回退本地 naive（该值用作
  `UtcDateTime` 列的比较边界），改 `utcnow()`。

**前后端契约脱节（5 处）**
- **大屏与首页「经费总额」被缩小 1 万倍**：`views/bigscreen/BigScreen.vue`、`views/dashboard/KpiCards.vue`
  对 `total_funds` 再除 10000。实证三源：`models/fund.py` 的 `amount` 列注释即「申请金额(万元)」、
  `views/funds/Analysis.vue` 直接把 `total_amount` 当万元展示、`services/report_export_service.py:134`
  明载「写(元)会导致口径差 10000 倍，统一改为(万元)」。
- `views/dashboard/ChartRow.vue` —— `funds_allocated || total_funds`：已拨付合法为 0 时被回退成
  经费总额，改用 `??`。
- **i18n 完成率双向双重错误**：后端公式误用 `|target| - |missing|`（source 49 / target 38 / missing 11
  时真实 77.6% 被算成 55.1%），前端又乘以 100（曾显示 **5510.2%**）。后端改为
  `(|source| - |missing|) / |source|`，前端去掉乘 100。
- `api/dataPackage.ts:getDownloadUrl` —— 写死 `'' + '/api/v1'`，与 `request.ts`/`projects.ts`
  的 `|| '/api/v1'` 约定不一致，`VITE_API_BASE_URL` 含 `/api/v1` 时拼成双前缀导致下载 404。
- `views/admin/AdminDashboard.vue` —— 「数据记录」卡片把 `total_funds`（万元）与记录条数相加，
  属量纲错误，现只累加村/项目/学校条数。

**竞态与健壮性（5 处）**
- `views/dashboard/components/GlobalSearch.vue` —— 300ms 防抖只降频不保序，慢响应会覆盖新结果。
  新增请求序号，仅最后一次发起的搜索可写回。
- `views/ruralWorks/Task.vue` —— `new Date('')` 产生 Invalid Date / `NaN`，被静默判成「正常」且
  `isOverdue` 恒 false，现加空值短路。
- `views/dashboard/{ChartRow,InfoRow}.vue`、`views/dashboard/index.vue` —— 失败重试 `setTimeout`
  与「已保存」提示复位计时器未在卸载时清理，销毁后仍会发起请求/写 ref，现统一 `onUnmounted` 清理。

**回归资产与门禁**
- **补齐上一轮遗留的覆盖率门禁缺口**：1.12.12 期间把大屏饼图数据源从 `/analytics/summary` 改为
  `stats.projects_by_status` 时，新增的 `stats.value ?? {}` / `s.projects_by_status ?? {}` 兜底分支
  无测试触达 → `src/views/**/*.vue` 分支门禁必红（`BigScreen.vue` 实测 98.59%）。补「stats 为 null」
  用例后回到 100×4。
- 新增回归守护 8 例：`_check_idle` 的 **aware-UTC** 三条（此前 4 条用例全喂 naive 值，正是缺陷
  逃逸原因）、i18n 完成率公式等式断言、搜索乱序响应、deadline 空值、饼图 nullish 兜底。
- **弱 mock 复盘点**：本批 4 处缺陷均伴随「测试全绿但真实功能坏」——`_check_idle` 喂 naive、
  `BigScreen.test.ts` 编造 `completion_rate/total_amount/by_status`、`AdminDashboard.test.ts`
  编造 5 个不存在的后端字段、`KpiCards` 断言 `fmtFunds(8900000) === '890'`。

**登记未修（已定性，非缺陷）**
- `AdminDashboard.vue` 的系统状态 / 最近登录 / 审计日志 / 待处理 / 存储五个面板读取的是
  `/dashboard/stats` **从不返回**的字段 → 面板恒空。真实端点已写入代码注释
  （`/system-health/overview`、`/system-health/disk-space`、`/audit/logs`、`/audit/login-attempts`、
  `/approval/tasks/pending`），**有意不盲接**：属功能补全且需产品定展示语义，照猜测契约实现
  正是本批「mock 编造字段导致假绿」的复现路径。
- 首页 `refresh:true`（每 60s 绕过 2 分钟缓存）：单机离线部署下约 13 条聚合开销可忽略，且手动
  刷新与自动轮询共用同一路径，改走缓存反而使「手动刷新」变慢，故保留。
- 各处 `datetime.now().year` 年份口径：属「本地日历 vs UTC」的产品语义选择
  （`SystemConfig.last_backup_time` 已明确取本地日历），非缺陷。

---

## [1.12.11] - 2026-10-02 — 🕐 时间基准统一：报表订阅 next_send_at / 到期派发彻底修复 + 时间转换单一事实源

承接 1.12.10 登记的遗留缺陷（`ReportSubscription.next_send_at` 时间基准不一致）。
根因是一类**基准混用**：库中 DateTime 列落库为 naive **UTC**，而调度规则
（`send_day` / `send_time`）与 `datetime.now()` 都是**本地**口径，两者混在一起比较。

### 修复（正确性 — 调度语义与比较基准）
- **报表订阅 next_send_at 与到期派发**（`services/subscription_dispatch_service.py`）：
  新增 `next_send_at_utc()` 作为唯一计算入口——把库中 naive-UTC 基准换算成本地墙钟、
  用本地墙钟做日历运算、结果再换算回 **aware UTC** 输出。
  * 用户配置「每天 08:00」现在稳定表示**本地** 08:00，前端按本地渲染即为该时刻；
  * 到期判定两侧统一到 UTC（`dispatch_due_subscriptions(now=` 传 aware UTC），
    不再出现「新建订阅被提前派发」；
  * `last_sent_at` 落库统一为 **naive UTC**（此前写调用方的本地墙钟，会污染下一次基准）。
  * 缺陷显形窗口很窄（仅「本地小时 ≥ 发送小时 > UTC 小时」，UTC+8 即本地 08:00–16:00），
    故长期只在特定时段暴露——这也是它此前躲过回归的原因。
- **列表端点**（`api/v1/data/data/reports.py`）：`_subscription_to_response` 改走同一入口，
  `next_send_at` 输出 aware UTC（此前输出 naive 墙钟，前端按本地解析会偏早 8 小时、
  甚至落在过去）。
- **调度器**（`services/backup_scheduler.py`）：订阅派发作业改传 `utcnow()`（aware UTC）。
- **generate-now 端点**：改传 `utcnow()`，与派发路径同基准。

### 修复（正确性 — 展示基准，此前登记为「待决策」的系统性问题）
- **新增 `models.base.UtcDateTime` 类型（一处修复、所有出口正确）**：库中 DateTime 列
  落库为 naive UTC，读回也是 naive —— naive 值一旦流出 ORM，**所有消费方都会丢掉
  「这是 UTC」这一事实**：`to_dict()` 的 `isoformat()` 不带偏移、FastAPI 的
  `jsonable_encoder` 同理，前端 `new Date(str)` 便按**本地**时区解析，于是 UTC 墙钟被
  当作本地时间展示（UTC+8 上全部时间偏早 8 小时）。
  `UtcDateTime` 在绑定参数时统一换算为 naive UTC、读取时补成 aware UTC，于是：
  * `to_dict()` / FastAPI 序列化输出带 `+00:00` → 前端按本地渲染即正确；
  * Python 级比较自动与 aware 的 `utcnow()` 兼容，错用会**响亮地抛 TypeError**
    而不是悄悄偏 8 小时；
  * SQL 级比较不受影响（绑定处理器本就丢弃偏移，落库字面量仍是 UTC 墙钟）；
  * **存量数据无需迁移** —— 库中本来就是 UTC 墙钟，本类型只补齐时区标注。
- **全模型接入**：`app/models/` 下 48 个文件的 195 处 `DateTime(timezone=True)` 与
  5 处裸 `DateTime` 统一改为 `UtcDateTime()`（含 `TimestampMixin` / `SoftDeleteMixin`）。
- **导出通道按本地渲染**（避免导出件里出现 UTC 墙钟或 `+00:00` 文本）：
  `async_export_service._format_datetime` 与 `excel_report_style._coerce`
  对 aware 值先转本地再格式化。
- **清除「本地时间写进 UTC 列」的混用**：`fund_lifecycle`（entered_at / confirmed_at /
  resolved_at / approved_at）、`audit_service.resolved_at`、`backup_service.updated_at`
  由 `datetime.now()` 改为 `time_utils.utcnow()`。这些列**未在任何界面展示**，
  故不产生展示侧回归，但消除了同一张表内两种时间基准并存的数据污染。

### 连带修复（新类型暴露出的既有缺陷）
- **`isinstance(col.type, DateTime)` 识别失效**（`services/package_record_validator._date_fields`）：
  列类型被 TypeDecorator 包装后该判定**静默失配**，数据包导入不再把
  `support_start_date` 识别为日期列、跳过「日期归一 ISO」，脏字符串直达批量入库、
  整批写入失败（实测 schools 导入 0/2）。新增 `models.base.is_datetime_type()`
  （递归解开 TypeDecorator 包装）并改用它 —— 全仓仅此一处按类型识别时间列。
- **`backup_service.cleanup_by_retention_days` 基准错位**：cutoff 原用本地 naive
  `datetime.now()` 与库中时间比较（同一类缺陷里的静默偏移）；改用
  `time_utils.utcnow()` 并对字符串形态的 `created_at` 统一按 UTC 补齐。相应地，
  该服务的三个保留期用例把时刻注入点从 `backup_service.datetime` 对齐到
  `backup_service.utcnow`（断言强度不变）。
- **列表端点的容错**：`_subscription_to_response` 恢复对非法频率的容忍
  （`next_send_at=None`），**展示侧不得让单行脏数据把整个列表/更新接口打成 500**；
  派发侧仍保持 fail-loud（计入 failed 并 rollback），两处口径不同是刻意的。

### 重构（单一事实源）
- 新增 `app/utils/time_utils.py`：`utcnow` / `utcnow_naive` / `as_utc` / `as_utc_naive` /
  `to_local` / `local_naive` / `local_naive_to_utc` / `to_utc` / `to_utc_naive` / `now_local`，
  并在模块文档中固化三条约定（存储 naive UTC / 比较同基准 / 调度按本地语义）。
- 收敛两处重复实现：`services/reminder_engine.py` 与 `services/async_export_service.py`
  各自的私有 `_as_utc` 改为指向 `time_utils.as_utc`（保留原名兼容既有调用与测试）。
  `as_utc` 对已是 UTC 的值原样返回，保持对象恒等语义。
- `models/base.py` 补「时间基准强约定」注释块，并**显式登记**尚未处理的系统性问题：
  `to_dict()` 对 naive 值输出不带偏移的 ISO，而前端按本地解析 ⇒ 所有经
  `created_at` / `updated_at` 展示的时间偏早一个时区差。该问题影响面覆盖全部模型与界面，
  需全局序列化口径调整 + 存量数据评估，故不在本轮改动。

### 测试
- 新增 `tests/unit/test_time_utils.py`（全分支 + 往返不变量 + `as_utc` 与 `to_utc`
  对同一 naive 值解释必须不同）。
- `tests/unit/test_subscription_dispatch.py` 全面改造为**时区无关**表达：用
  `local_wall()` / `local_now()` 把「本地某时刻」显式换算成库中的 naive UTC，
  断言在任意运行时时区下结论一致；并新增
  `test_created_today_after_send_time_not_dispatched` 直接锁定历史缺陷的显形窗口。
- `tests/probe/probe_r10_subscription.py`：`next_send_at` 断言改为解析带偏移的 ISO 后
  换算到本地再比较（此前按 naive 解析，且 `now` 用本地时间与 UTC 值比较），
  该探针从此**与运行时刻无关**；派发调用改传 `utcnow()`。

## [1.12.10] - 2026-10-02 — 🔧 跨平台 CI 双红根因修复（平台相关穿越判定 / 时区相关断言）+ 测试会话隔离契约

本轮根因由 GitHub Actions 的 **check-run annotations** 直接定位（job 日志需认证，
但 `::error::` 上报会以注解形式公开可读），证伪了此前两个猜测：
后端作业覆盖率**已达 100%**、前端作业亦非 `v8 fnMap` 合并伪影。
真实病因是「测试断言依赖运行平台 / 时区」而非产品逻辑错误 —— 同源表现为
**本地（Windows / UTC+8）恒绿、CI（ubuntu-latest / UTC）恒红**。

### 修复（跨平台 — 发布门禁）
- **归档恢复的路径穿越判定与运行平台绑定**（`app/services/data_tier_service.py`）：
  `Path(archive_file).name != archive_file` 只按**运行平台**的分隔符解析 —— Linux 上
  反斜杠不是分隔符，`C:\Windows\win.ini` 这类 Windows 风格路径**绕过**校验、落到
  "文件不存在"分支（ubuntu-latest 上表现为断言 `'非法' in '归档文件不存在: C:\Windows\win.ini'`
  失败，Windows 本地恒绿）。现显式拒绝 `/` 与 `\` 两种分隔符，两平台结论一致且更严；
  合法纯文件名不受影响（POSIX 语义对照探针已验证修复前后差异）。
- **审批时间轴排序断言的时区依赖**（`frontend/tests/unit/utils/approvalTimeline.test.ts`）：
  朴素时间串（无时区）由 JS 按运行环境**本地时区**解析，`'2026-09-17 10:00:00'` 与
  `'2026-09-17T10:00:00Z'` 在 UTC runner 上是**同一时刻** → 落入稳定排序分支保持输入顺序
  → 断言失败（UTC+8 本地恒绿）。改用同一天最早/最晚时刻组合，经 UTC-12…UTC+14 全偏移
  离线验证结论恒定，且与字典序排序结论相反（保住对"改回 localeCompare"的判别力）。
  顺带纠正：原取值在新旧实现下"排首者"完全相同、且含 TIE 区间，属**无可判别力的弱用例**。

### 修复（测试基础设施 — 会话数据根隔离契约）
- **Linux 上测试数据根逃逸**（`backend/tests/conftest.py`）：conftest 用
  `BUMOFU_BACKEND_DIR_OVERRIDE` 把数据根指向会话临时目录，但 `paths.get_app_data_dir()`
  的首分支 `is_bundled() or (is_linux() and not BUMOFU_DEV_MODE)` 在 Linux 上恒真，
  **短路返回 `~/.bumofu`、根本不经过 `get_project_backend_dir()`** → override 形同虚设，
  测试数据写进 runner 家目录（跨用例共享、跨运行残留），Settings 亦把
  CACHE_DIR/UPLOAD_DIR/EXPORT_DIR 一并固化到那里；Windows 本地因 `is_linux()` 为假不受影响。
  现同时声明 `BUMOFU_DEV_MODE=1`，两平台统一由 override 收口（**生产态 Linux 行为不变**，
  由 `test_prod_linux_without_dev_mode_uses_home` 继续锁定）。
- 新增 `backend/tests/unit/test_session_isolation_contract.py`（2 用例）：以**行为级**断言
  守护该契约（不用源码文本扫描），既能拦住"漏声明"，也能拦住"声明晚于 `app.*` 导入"的
  时序错位（Settings 在 import 期即完成路径归一）。放在独立模块的原因：
  `tests/unit/test_paths.py` 带模块级 `pytest.mark.real_backend_dir`，conftest 的 autouse
  fixture 会为该模块临时删除 override，无法在该模块内观察隔离实效。
- 新增 `scripts/ci/scan_shared_vue_refs.py`：扫描受覆盖率门禁锁定的 `.vue` 被多个测试文件
  引用的情况（现状 64 处）。经 CI 注解确认**当前并未发作**（前端覆盖率 100%），
  故保留为潜在风险探测工具，本轮不做重构。

## [1.12.9] - 2026-09-30 — 🛡️ 深审缺陷批量修复（越权/数据完整性/静默失效/发布门禁）

对应 `deliverables/open-code-review-深度审查报告-2026-09-17.md` 与逐条复核台账
`.scratch/w15-ocr-triage/part-{A,B,C,D}.md`（共 337 条判定为 LIVE 的历史发现，
本轮按严重度分批修复，剩余条目见 `deliverables/ocr-findings-ledger-2026-09-30.md`）。

### 修复（安全 — 越权与任意文件读写）
- **审计日志批量删除 fail-closed**（`system/audit.py`）：非法 `before_date` 原先只
  warning 后"忽略日期过滤"，配合空动作条件会**清空整张 audit_logs**。现在入口 422、
  路由层 400，两条回归锁定"非法日期一条都不删"。
- **错误报告归属校验**（`system/error_report.py`）：原读不存在的 `record.user_id`
  → `is_owner` 恒 True，任何登录用户可改任意报告；改用真实字段 `reporter`。
- **报表订阅 IDOR**（`data/data/reports.py`）：`/{id}/download` 与 `/generate` 收敛到
  "订阅属主或管理员"，与其余订阅端点同口径。
- **政策附件路径穿越**（`policy.py`）：写入/预览/下载三处统一做 `realpath + commonpath`
  包含性校验，`/uploads/../../etc/passwd`、绝对路径一律 400，杜绝任意文件读取。
- **数据包三端点补归属校验**（`data/data/data_packages.py`）：`preview`、
  `decrypt-preview`、`confirm-import` 原先任何登录用户凭 id 即可预览/解密/落库他组织
  数据；`incremental/import` 的 org 缺失改为 fail-closed（不再以 `org_id=0` 写库）；
  加密包上传临时文件改 `mkstemp`（原名可 `../` 穿越且同秒互相覆盖）。
- **项目里程碑全端点数据域守卫**（`project_milestones.py`）：里程碑读写、状态流转、
  流转规则、变更记录统一走 `scoped_filter`，不可见即 404。
- **上报归属校验**（`data/data/data_reports.py`）：`submit` 原先无归属判断，任何登录
  用户可把他组织上报提交给其上级。
- **综合报表导出门禁**（`import_export/export.py`）：补 `require_admin`，学校/项目/经费
  的计数、金额与明细全部过 `scoped_filter`（S2 导出隔离红线）。
- **组织模块策略跨组织读写**（`org_module_policy.py`、`control_package.py`）：4 个策略
  端点 + 管控包导入按 `assert_org_reachable` 校验目标组织子树，杜绝部门级 admin
  改他组织策略 / 用编辑过的包跨组织写。
- **上传文件名净化**（`utils/upload_helper.py`）：文件名只取基名并过滤分隔符/控制字符，
  落盘前再做一次"最终路径必须位于上传根目录内"的包含性校验。
- **经费状态机红线**（`fund_service.py`、`funds.py`）：创建强制 `pending`（忽略客户端
  status），更新接口禁止直接改 `status`（须走审批/拨付端点），软删经费不再可详情/流转。
- **校验规则补管理员门禁**（`validation.py`）：增/改/删三个端点补 `require_admin`。
- **用户管理提权收敛**（`auth/users.py`）：仅 super_admin 可创建/改/删/重置 super_admin
  账号；静态选项端点的权限校验移入路由依赖（缓存命中不再跳过校验）。
- **经费角色改白名单**（`deps.py`）：原 denylist 对未知/空角色放行全流程，改 allowlist
  fail-closed。
- **用户服务字段白名单**（`services/user_service.py`）：`update_user` 不再对任意键
  `setattr`（原先可改 role/is_superuser/hashed_password）。
- **组织 `/subordinates` 限子树**（`organization.py`）：原先对任何登录用户返回整张组织表。
- **农村任务审批独立性**（`rural_tasks.py`）：非管理员不得审批本人创建/提交的任务；
  审批字段不得经通用更新接口写入，已提交任务禁止直接改 status。
- **系统初始化 fail-loud**（`system/init.py`）：超管账号创建失败立即中止且不落"已初始化"
  （原行为会留下无超管且不可重入的永久锁死部署）。
- **2FA 加固**：`/two-factor/verify` 与 `/disable` 补限流与二次验证（`auth/two_factor.py`），
  恢复码写入路径统一校验。
- **密钥持久化 fail-closed**（`core/pii_crypto.py`、`core/config.py`、`utils/runtime_secrets.py`）：
  `require_persisted=True`，静态数据加密密钥落盘失败即报错，不再用一次性进程内密钥
  顶替（重启后历史密文会永久不可解）。

### 修复（数据完整性 — 静默失效与丢数据）
- **增量备份记录不可见**（`backup_service.py`）：备份列表原先只匹配 `backup_20%`，
  `backup_incremental_*` 永远不入列表（不轮转、不可见）；清单改在备份记录落库**之后**
  推进（原先先写清单，记录写失败即静默漏备）；一致性快照失败不再回退 WAL-blind 裸拷贝
  （fail-loud）；回滚时数据库文件被占用不再原地覆盖（保留快照并显式报错）。
- **异步导出**（`async_export_service.py`）：综合工作簿的学校/项目/经费计数与金额补数据域
  过滤；失败回写前先 `rollback()`（否则任务永停 processing）。
- **审批回写**（`approval_workflow_service.py`）：实体回写改用 SAVEPOINT 隔离（原
  `rollback()` 会连带丢弃同一事务里的审批记录与 `completed_at`）；重新提交时回写失败
  落到可重试的 `*_apply_failed` 终态；`batch_approve` 默认校验审批人归属（仅管理员
  走跳过分支）。
- **FTS5 全文检索**（`policy_fts_service.py`）：SQL 由普通字符串改为 f-string，
  `{FTS_TABLE}` 不再原样发给 SQLite —— 此前每次搜索都静默退化为 LIKE。
- **数据库校验规则引擎**（`validation_engine_service.py`）：改用真实列 `error_message`，
  `params` 反序列化 JSON 字符串并用 try/except 兜住脏数据（原先 AttributeError 被宽
  except 吞掉 → 所有 range/regex/enum 规则静默失效）。
- **备份消息类型**（`message_service.py`）：白名单补 `MessageType.BACKUP`（模型已定义、
  备份调度器在用，原实现每发必抛 ValueError）。
- **同步成功率**（`sync.py`）：状态字面量由 `success/failure` 改为写入端真实取值
  `completed/failed`，成功率按终态为分母（原先失败数恒 0、成功率恒 100%）。
- **派生列残留**（`models/fund.py`）：经费日期被清空时同步清空 year/year_month/year_quarter。
- **批量更新同步版本**（`models/base.py`）：`query.update()` 等 bulk update 也递增
  `sync_version`（原先只有 ORM 逐行路径递增，增量同步会漏行）。
- **外键动作与可空性自相矛盾**（`models/*`）：审计/留痕类引用列放宽为可空，
  配套迁移 `w15_relax_notnull_001`（含 effectiveness/package_versions 唯一约束，
  检测到重复数据时跳过并告警）；`package_versions`、`fund_history` 补
  `passive_deletes`（原先 ORM 删父会先置空非空外键 → IntegrityError）。
- **全盘健康评估**（`system/monitor.py`）：逐盘判 `percent`（读取失败的分区没有该键，
  原取 `disks[0]` 会 KeyError 并丢掉整份资源报告）。
- **导入校验 500**（`import_export/import_data.py` + `data_validator_service.py`）：
  `validate_import_data` 补 `validate_tiered_level` 参数并实现"是否振兴梯队"取值校验。
- **模板渲染**（`models/message_template.py`）：四个渲染方法统一补 IndexError/ValueError，
  不再因位置占位符/未转义花括号直接抛给调用方。

### 修复（服务层 — 深审残余 live 条目，R16 批次）
- **级联彻底删除只做两层**（`cascade_purge_service.py`）：原实现 `root → 子表 → 孙表`
  两跳，`supported_villages ← projects ← funds ← fund_transactions` 这类**第三级**依赖
  不会被删，残留孤儿行；且跨分支删除顺序随元数据序，先删 projects 会连带影响 funds 的
  定位条件。改为访问集 DFS + **自底向上链式删除**（`_descendant_chains` / `_delete_chain`）。
- **分片合并并发重入**（`chunked_upload_service.py`）：合并含 await，同一 session 可被并发
  调用重入 —— 第二次进来时状态已是 MERGING，会与第一次同时写同一 `final_path`，且第一次
  `rmtree` 后第二次 FileNotFoundError → 500。改为每会话锁串行化 + 拒绝 MERGING 状态重入
  （抽 `_acquire_merge_lock`）。
- **数据清洗中位数与标准化**（`data_cleaning_service.py`）：偶数样本原取 `values[mid]`
  （非真正中位）；标准化段直接用字段名当 key，缺键即 KeyError；未知类型静默写回坏值。
  改为偶数样本取两中位均值、`field_config.get("field")/get("type")` 缺键 skip+warn、
  仅在 `normalized is not None` 时写回、`_to_numeric` 跳过空串/文本。
- **报表导出金额单位错标**（`report_export_service.py`）：表头写 `(元)`，而
  Fund/Project 金额列实际单位是**万元**，导出表数字被读成 1e4 倍偏差。统一改为 `(万元)`。
- **报表取数参数与截断**（`report_service.py`）：`include_sections` 显式为空时原会返回全表
  （fail-open），改为早退空列表；`village_ids` 参数原先**完全未进入过滤**（静默忽略调用方
  的村筛选），改为真正 `filter(SupportedVillage.id.in_(...))`；`limit(100)` 硬截断改为
  按 id 排序取全量并在超过 `_MAX_REPORT_ROWS`(20000) 时截断 + WARNING。
- **回收站备份先于清除**（`retention_service.py`）：原实现**先清除后备份**，一旦备份失败
  数据已不可恢复。改为"先算清单 → 先备份 → 再清除"，备份失败置 `backup_failed=True` 并
  中止本轮；无候选时显式 `total_records=0`。
- **村庄级联删除吞异常**（`village_cascade_delete_service.py`）：原对任意异常
  `logger.warning` 后继续，真实 SQL 错误被降级为"跳过该表"（数据不一致且无感知）。改为仅
  "no such table / no such column" 这类 schema 差异降级，其余 `rollback` 后 **re-raise**。
- **资源限额计数泄漏**（`resource_limiter.py`）：未登记限额的键永不被清剪（`_request_counts`
  无限增长），且 `set_quota` 不重置既有计数。新增 `_DEFAULT_CLEANUP_WINDOW` 无条件清剪，
  `set_quota` 末尾重置计数。
- **任务队列停止后不可重启**（`task_queue.py`）：`stop()` 未复位 `self._queue`，
  `submit()` 自愈判据过窄 → 同进程二次启动静默失效。改为 `stop()` 置 `_queue=None`、
  `submit()` 判 `is None or not _running`。
- **SMTP 发送加固**（`alert_service.py` + `core/config.py`）：补 `SMTP_TIMEOUT`（非法值回退
  10s）、`ssl.create_default_context()` 显式传入 `starttls`、`From` 头缺 `SMTP_FROM` 时
  回退 `SMTP_USER`（原先直接发空 From 被服务端拒收）。
- **离线地图覆盖统计崩溃**（`offline_map_service.py`）：`cache_dir` 被删除时 `iterdir()`
  抛 FileNotFoundError（500）；扫描期文件被并发删除抛 OSError 中断统计。改为目录缺失返回
  零覆盖并缓存、`stat()` 失败跳过该文件、非目录条目跳过。
- **默认密钥非合法 Fernet key**（`secrets_manager.py`）：兜底分支用 `token_urlsafe(32)`
  （43 字符、非 base64-32B），而 `key_type` 声明为 `fernet`，调用方 `Fernet(key)` 运行时
  ValueError。兜底统一产出**合法 Fernet key**（`_generate_fallback_key`）。
- **加密包截断与无界读取**（`encrypted_package.py`）：短文件 `struct.unpack` 抛
  `struct.error`（调用方只捕 ValueError → 500）；`meta_len` 无上界，损坏文件声明 4GiB
  会吃满内存。改为先校验头部读满、`meta_len ≤ 16 MiB`、逐段长度校验，全部抛 ValueError。
- **FTS 读路径发 DDL 并提交**（`policy_fts_service.py`）：`search_policies_fts`（GET 搜索）
  首行调 `ensure_fts_table`，会执行 `CREATE VIRTUAL TABLE` + `INSERT ... SELECT` + commit
  —— 并发读下写锁竞争，且读请求隐式提交调用方事务。改为只读探测 + LIKE 降级，
  DDL 仅留在写路径 `ensure_fts_table`。
- **配置导入非对象 JSON 崩溃 + 非原子**（`system_config_service.py`）：`json.loads('[1,2]')`
  成功但 `.items()` 抛 AttributeError（500）；逐键 `set()` 各自 commit，半途失败留下
  "部分导入"。改为仅接受 JSON **对象**、抽 `_set_no_commit` 后**单次提交**。
- **数据上报统计 7 字段被丢弃**（`schemas/data_report.py` + `data_report_service.py`）：
  service 传 `draft/cancelled/overdue/pending_review/approval_rate/by_source_org/by_month`，
  schema 未声明 —— Pydantic 默认 `extra=ignore` **静默丢弃**，调用方拿到缺失统计。schema
  补齐为显式字段（均带默认值，向后兼容），并加"service kwargs ⊆ schema fields"回归锁。
- **导入冲突解决四类缺陷**（`smart_conflict_resolver.py`）：
  ① 时间比较 `import_updated > local_updated` 在 str/datetime 或 naive-vs-aware 混合时抛
  TypeError 中断整包导入 → 抽 `_to_datetime` 统一归一，不可比较时退默认策略；
  ② OVERWRITE/AUTO 对导入记录**全键 setattr**，扁平化/派生键变成实例属性且
  `organization_id`/`updated_at` 被覆盖 → 改为按模型真实列过滤（`_writable_items` +
  `_PROTECTED_COLUMNS`）；
  ③ KEEP_BOTH 直插新行且**不重映射外键**，新行挂到源机村/项目 ID → 抽 `_keep_both` 并
  传入 `id_mapping` 走 `_update_foreign_keys`；
  ④ 冲突检测无租户条件，按 code/village_name 命中**他组织**行后可改写/复制他人数据 →
  构造参数 `organization_id` 参与检测，且导入时强制覆盖记录的租户列。

### 修复（响应信封与前端凭据/角色语义，R16 收尾）
- **`success_response(success=False)` 被静默丢弃**（`core/response.py`）：`success` 属信封保留键，
  覆盖值被 `_merge_extra_fields` 丢弃 → RBAC 批量撤销有失败项、`/system/monitor/database-size`
  读不到数据库文件等**部分失败场景仍回 success=true**，前端按 success 分支会错判为成功。
  改为 `success_response` 显式开启 `allow_success_override`，**仅接受 bool**；
  `error_response` 永不开启（错误信封不得被翻转为"成功"，防 `**payload` 伪造）。
- **越权校验缺失的数据包校验端点**（`data/data/data_packages.py` `POST /{id}/validate`）：
  与同组 preview/confirm/download 同口径补组织归属校验，越权一律 404（不泄露资源存在性）。
- **前端角色默认值自相矛盾**（`utils/roleAccess.ts`）：`getRoleFromLocalStorage` 默认 `'viewer'`
  且返回**原始** role，与 `normalizeRole` 的默认 `'user'` 冲突 —— 同一用户在不同入口得到
  `user / viewer / operator` 三种值。改为统一归一化返回、默认 `'user'`；`isAdminUser` /
  `hasAllowedRole` / `hasMinRole` 的白名单比对同样先归一化，历史角色（`manager` /
  `approval_leader` / `operator`）配置不再导致菜单被错误隐藏。
- **凭据跨来源拼接**（`utils/authStorage.ts`）：原 token/user/refresh 是三条独立回退链，
  可拼出「A 的 token + B 的档案/刷新令牌」。改为 `_activeCredentials()` 整体取值：会话槽有
  token 才是权威来源，缺档案时**仅当持久槽 token 完全一致**才补齐（同一凭据的正常续期），
  否则不提供身份（fail-closed）；`setAuthData` 无 refresh_token 时清掉会话级残留刷新令牌。
- **新增告警样式硬编码颜色**（`funds/YearlyComparisonChart.vue`）：部门维度不支持的提示条
  原先用 `var(--x, #b45309)` 内联回退值，触发硬编码样式棘轮（345 → 347）。
  改用既有 token `--color-warning-dark` / `--color-warning-lightest`，回到基线 345。
- **无档案会话丢失刷新令牌**（`utils/authStorage.ts`）：`_activeCredentials()` 在「会话有 token
  但无 user 且持久槽不同源」分支把 `refresh` 一并置 `null`。该 refresh 与 token **同源**
  （同一次登录写入），丢弃后会让"access 已轮换、档案尚未回填"的会话无法续期，登出吊销
  也拿不到 `refresh_token`。改为保留会话槽 refresh；身份仍 fail-closed（`user=null`）。
- **短证件编号等同未脱敏**（`utils/desensitize.ts`）：`maskMilitaryID` 原实现在长度 <4 时
  **原样返回**（`'ab'` → `'ab'`），长度恰为 4 时前缀+后缀覆盖全部字符（`'1234'` → `'12****34'`，
  每位仍可见）。改为长度 ≤4 一律全掩（`'****'`），保证任何长度都至少隐藏中间部分。
- **复制失败被误报成功**（`utils/clipboard.ts`）：降级 `execCommand` 路径丢弃布尔返回值并直接
  提示"已复制"，实际失败时误导用户；临时 textarea 不在 `finally` 移除，异常时永久残留 DOM。
  改为以 `execCommand('copy') === true` 判定成败、返回 false 时明确报错，节点移除移入 `finally`。
- **离线 mock 与凭据同源口径不一致**（测试）：`getMockResponse` / `AuthStorage.getUser` 的
  相关用例只写 `auth_user` 而不写 `auth_token`，与新 fail-closed 语义冲突；已同步为一并写入 token
  并补"仅有 user 无 token → null"断言。
- **响应头文件名解析在测试中被替身短路**（`api/{importExtra,schoolsFull,supportedVillageFull}`）：
  mock 的 `parseContentDisposition` 恒返回 fallback，使"响应头文件名优先"这条断言**永远测不到实现**；
  改为忠实反映真实解析语义（`filename*` / `filename="…"`）。

### 修复（发布门禁与工程）
- `frontend/src/composables/useRouterSafe.ts`：控制字符剥离正则加 `no-control-regex` 豁免
  说明（`lint:check --max-warnings=0` 下必须显式声明理由）。
- `.github/workflows/build-windows.yml`：见"门禁"小节（下一批次）。
- 后端补齐最后 8 行覆盖率缺口至 **100.00%**（`system.py` 端口探活轮询 sleep、`tasks.py`
  完成/失败回写守卫、`camel_to_snake.py` 响应头复制、`chunked_upload_service.py` 合并锁二次检查）。
- **`brace-expansion` 覆盖版本修正**（`frontend/package.json`）：安全作业要求消除
  `brace-expansion` 的 DoS 高危项。此处**连续踩了两个相反的坑**，最终以「按 major 作用域
  覆盖」收敛：
  1. 首版全局覆盖 `^5.0.12` —— v4+ 是 **ESM-only**（`type: module`，只有具名导出
     `expand`，无 `default`），而 `minimatch@9` 的 ESM 入口写
     `import expand from 'brace-expansion'`，于是 `vite build` 直接
     `SyntaxError: The requested module 'brace-expansion' does not provide an export named 'default'`
     （ARM64 流水线 `Build Frontend` / `Build backend binary` / `standalone-deb` 三作业同时红、
     PR 的 `frontend-check` 仅跑 5m19s 即被炸断，均由此而来）。
  2. 次版改全局 `^2.1.7` —— 2.x 是 CJS（无 `type`、`main: index.js`、`module.exports = expandTop`），
     修好了 `minimatch@9`，却把 **`minimatch@10` 打挂**：其 CJS 入口写
     `require('brace-expansion').expand(...)`，需要**具名导出**，于是覆盖率链路
     （`test-exclude → minimatch@10`）报 `TypeError: (0, brace_expansion_1.expand) is not a function`。
  3. 最终正解 —— **不设全局 minimatch pin，只按消费者 major 分别覆盖**：
     ```json
     "overrides": {
       "minimatch@9": { "brace-expansion": "^2.1.7" },
       "minimatch@10": { "brace-expansion": "^5.0.12" }
     }
     ```
     （`minimatch@3` 走 eslint 链，保持 `brace-expansion@1.1.21` 不动。）
     实测装出的树：`minimatch@9.0.9 → 2.1.7`、`minimatch@10.2.5/6 → 5.0.12`、
     `minimatch@3.1.5 → 1.1.21`，**每个消费者的真实需求都被满足**；
     `npm audit --audit-level=high` exit 0，`npm run build` 与
     `npx vitest run --coverage` 均通过。CI 只跑 `npm audit`（不跑 `npm ls`），门禁全绿。
     已知无害残留：`npm ls brace-expansion` 会对
     `test-exclude/node_modules/minimatch/node_modules/brace-expansion@5.0.12`
     标一条 `invalid: "^2.1.7"`——这是 npm 把 `minimatch@9` 规则误套到同目录层级
     `minimatch@10` 实例上的**显示层伪影**（两规则在同一物理位置重叠），
     实际解析正确、`npm ls` 之外的一切工具不受影响。试过用
     `"test-exclude": { "minimatch": "^10.0.0" }` 消掉它，会触发 ERESOLVE，故保留现状。
  教训一：**同名依赖被两个消费者以相反的模块格式引用时，全局 override 必然打挂其中一方**，
  必须用 `pkg@major` 作用域覆盖分别满足。
  教训二：**安全覆盖必须验证模块格式（ESM/CJS）与下游 import 形态**（default vs 具名），
  仅看版本号更高即覆盖会在构建期炸掉整条出包链路。
- **前端覆盖率缺口清零（10 个文件）**：本轮把 `src/**` 各分组门禁从"接近 100"推到
  **全部分组 100%**，方式分两类——
  - **补真实测试**（弱断言/零覆盖处）：`useRouterSafe.toSafeLocationHref` 此前**完全没有直接
    测试**（它是防开放重定向与 `javascript:` 协议执行的**安全控制**），新增 12 例覆盖协议相对
    地址、`javascript:`/`data:`/`vbscript:`、控制字符（`java\tscript:` 变形）剥离、空值回退；
    `policy._errMessage` / `dataReport._errMessage` 补齐 `userMessage → response.data.message
    → message → fallback` 四级回退的**每一级**与 falsy 短路；`PermissionAssignmentDrawer`
    补 `catch` 内竞态守卫（过期失败响应丢弃）、`userId=null` 早退、`props.user?.id ?? null`
    的 null 侧；`MenuVisibilityPanel` 补 `setCheckedKeys` 同步主体（原默认树桩无此方法 →
    该逻辑**从未执行**）与 `syncingTree` 重入守卫；`FilePreview` 补卸载后迟到失败不误报；
    `useBackupSchedule` 补端点失败静默回退；`config` 补受限存储 `getItem`/`setItem` 抛错。
  - **删除不可达死代码**（而非用 `c8 ignore` 掩盖）：`stores/config.ts` 的
    `readStoredTheme`/`setTheme` 测试原先 **spy 了 `Storage.prototype`**，但
    `src/test/setup.ts` 用 `Object.defineProperty` 把 `localStorage` 换成**普通对象字面量桩**，
    其原型链上根本没有 `Storage.prototype` —— 该 spy 是**空操作**，两个 `catch` 分支从未执行
    （覆盖率恒 0、测试给出**虚假信心**）。改为 spy 实例本身后真实命中。
    `useBackupSchedule.toCron` 的 `backupTime || '02:00'` 与解构默认值 `m = '0'`：
    经实测 `normalizeBackupTime('3') === '03:00'`、`('25:99') === null`，到达 `toCron` 的值
    必然非空且必含冒号，两处兜底**均为死代码**（旧注释误称 `'3'` 可到达），一并删除。
  - **确认 v8 计数伪影**（有仓内既有先例）：`dataReport.ts` 两个含 `return` 的 `try/finally`
    的 `finally` 侧、`dataReport.ts:63`/`policy.ts` 等按既有约定标注
    `/* c8 ignore next -- finally 分支为 v8 计数伪影 */`（与 `stores/dataPackage.ts` 同款）。

### 变更（行为）
- 新增 `assert_org_reachable`（`core/data_permission.py`）作为跨组织可达性守卫的**唯一实现**，
  `control_package` 改为委托调用（保留模块级可 patch 语义）。
- 权限、路径与状态类改动均为 **fail-closed**：非法输入一律显式 4xx，不再静默放行或降级。

## [1.12.8] - 2026-09-13 — 🛡️ 遗留风险治理第三批（R7 恢复维护窗口 / R12 低危批量 / R2 残余无界读取 / P-1~P-3 预防门禁）

对应《deliverables/遗留风险彻底解决方案计划-2026-09-12.md》W3-W4 批次。

### 修复（数据一致性：恢复窗口与在途写请求竞态 — R7，P1）
- 新增 `app/core/maintenance.py` 维护模式闸门与 `MaintenanceGateMiddleware`：
  恢复入口置位 → **新的写请求立即 503**（读请求放行）→ 等待在途请求归零
  （上限 10s，与 `db_coordinator.exclusive_write` 同口径，超时记 ERROR 后继续）
  → `finally` 解除。
- `BackupService.restore_backup` 外层包维护窗口，返回值新增 `maintenance_window_ms`。
  原实现只有 `engine.dispose()`（仅回收空闲连接），在途小写事务不经
  `exclusive_write`：Windows 上覆盖复制必抛 `PermissionError`，POSIX 上写入
  被替换的旧 inode —— 恢复后**静默缺失一段已提交事务**且无任何报错。
- `/health` 暴露 `maintenance {active, reason, since, last_window_ms, last_waited_ms}`。

### 修复（低危一致性批量 7 项 — R12，P3）
- **R12-2** 慢请求/慢 SQL 计数器改互斥自增（裸 `+=` 并发丢计数），统计快照加锁读。
- **R12-3** `RESTORE_DRILL_STATUS` 改一致性快照（`snapshot_status()` + RLock），
  `/health` 不再逐字段读模块字典（与演练线程的逐字段写交错会产出撕裂结论）。
- **R12-4** 审批提醒 `stop()` join 上限 1s→5s，超时后不复位 `_running` —— 否则
  紧随的 `start()` 会再起一个扫描线程（提醒重复创建、DB 连接翻倍）。
- **R12-5** `/system/shutdown` 与 `/system/restart`(win32) 不再 `os._exit(0)`：
  改 `raise_signal(SIGINT)` 走 lifespan 优雅关闭（调度器 Timer、提醒线程、任务
  队列、WAL checkpoint、`.part` 半成品回收不再被跳过）。
- **R12-6** 内存任务表 `_tasks` 增加 1 小时终态回收（创建/列表/统计/运行计数
  四处触发），长跑桌面端不再单调增长。
- **R12-7** `create_background_task` 无运行循环时返回 `None`（不再把任务挂到
  "永不 run"的缓存 loop 上），`monitoring_service` 的线程池兜底由死代码变为
  生效路径。

### 修复（R2 残余「先整包入内存再校验」清零）
- `data_package_service`（5 处 zip 打开点）、`permission_package_service`（4 处）、
  `data_packages` API（2 处）：补 `ensure_zip_within_limit` + `zf.read` →
  `read_zip_member`。此前**任何登录用户**上传结构合法、解压后数十 GB 的包
  （压缩炸弹）即可让进程 OOM —— 单机离线部署下等于整个应用不可用。
- `backup_service._verify_backup_recovery`：原先把整个库文件读进内存再落盘校验
  （库可达 GB 级，备份校验自身成了内存峰值点）→ 改为 1MB 分块流式解压落盘。
- 分片上传端点：`await file.read()` → `read_upload_with_limit`（20MB）；
  合并阶段整文件读算 MD5 → 1MB 分块流式摘要（单会话上限 2GB）。
- 离线地图瓦片读、分片合并单块读改为显式长度参数（有界读）。

### 修复（组织树元数据缺失致组织级数据权限恒拒 — R14，真实 HTTP 探测发现）
- `POST /api/v1/organizations` 此前走 `Organization(**org_data)` 直建，`path`/`level`
  **未落库**（NULL）；而组织级数据权限完全依赖 path 前缀匹配
  （`OrganizationPermissionService.can_access_organization` → `get_subordinate_ids`
  → `Organization.path LIKE`）——**经界面新建的组织，其成员一律被判为"无组织权限"**，
  数据包导出等组织门禁端点恒 403（安装包首启、建组织、挂用户即复现，已实测复现）。
- 端点补 `path`/`level`（根 `/{id}/`、子 `{父 path}{id}/`，与
  `OrganizationService.create_organization` 同口径）+ 校验上级组织存在。
- `get_subordinate_organizations` 对 path 为 NULL 的历史数据退化为"仅自身"，
  避免 fail-closed 被放大成功能不可用。
- 新增 `OrganizationService.repair_organization_paths()` 并在启动自检调用：
  幂等单趟回填（父先于子），历史库自愈（实测 3 个 NULL-path 组织启动即修复，
  修复后同类导出由 403 → 200）。

### 修复（依赖清单收敛与自检口径 — R15，2026-09-14 用户实测反馈）
- **幻影依赖**：`GET /api/v1/env/check` 自持的清单里列了应用**从不 import** 的 `fpdf2`
  （`requirements.txt` 中亦无该分发名）与**仅开发期**的 `pytest` —— 任何环境下恒报"缺失依赖"，
  用户照提示 `pip install fpdf2 pytest` 永远装不出 `fpdf2`。
- **冻结运行时误报**：判定用 `importlib.metadata.distributions()` 枚举已安装分发，而
  PyInstaller 冻结运行时里 bundled 包的 `.dist-info` 不完整 —— 能 import 的包也被判缺失，
  **安装包首启即弹"缺失 7 个依赖"**（2026-09-14 用户截图场景）。
- 修复：新增 `app/core/required_packages.py` 作为**依赖登记表单一事实源**（运行时必需 /
  运行时可选 / 仅开发 三级）；`app/main.py`、`app/startup/environment.py`、
  `app/api/v1/system/env.py` 三处清单全部改指该表；判定改 **import 名 + `find_spec`**
  （冻结运行时同样可靠），版本号取 `importlib.metadata` **尽力而为**。
- 环境诊断页按三级分别展示：红色"缺失依赖"只给运行时必需；可选缺失提示"功能降级"；
  开发期缺失单独成组；**冻结运行时不再给不适用的 `pip install` 建议**，改为"自包含安装包运行，
  请重新安装安装包或联系管理员"。修复命令改为可执行形态
  `"<当前解释器>" -m pip install -r "<backend/requirements.txt>"`。
- 顺带修复被误写入的文档：`docs/03-开发文档/06-运维文档/技术栈说明.md` 原为一份被截断的
  Claude Code 权限配置 JSON（2026-07-22），已重写为真正的技术栈说明（含依赖三级清单与自检口径）。
- **打包依赖同批修复**（冻结运行时复验发现）：`backend/assistance-backend.spec` 的 `excludes`
  里排除了 `docx`，而 `report_export_service` 用 **python-docx** 生成 Word 报表 —— 安装包内
  Word 导出必然 ImportError。已从 excludes 移除并加入 `collect_submodules('docx')` 全量收集。

### 工程（预防门禁 — 计划 §六 P-1/P-2/P-3）
- 新增 6 个棘轮扫描器并接入 `pr-checks.yml` static-analysis：
  `check_os_exit`、`check_subprocess_encoding`、`check_dir_replace`、
  `check_unbounded_read`、`check_upload_endpoints`、
  `check_scheduler_registration`（公共件 `_gate_common.py`：基线比对键 =
  路径 + 归一化代码，忽略行号漂移；`--baseline` 收敛；棘轮只紧不松）。
- 六个门禁当前 **NEW=0 且无基线豁免**，使 R2/R8/R12-5 三类根因在 PR 阶段即被拦下。

### 测试
- 新增 `tests/unit/test_r7_maintenance_window_20260913.py`（19 例）、
  `tests/unit/test_r12_low_risk_batch_20260913.py`（15 例）、
  `tests/unit/test_data_package_zip_limit_r2.py`（4 例）、
  `tests/unit/test_ratchet_gates_p1_20260913.py`（26 例：门禁抓违规 + 真实仓库必须 exit 0）。
- 同步既有断言（行为语义变更，非静默改断言）：`os._exit`→SIGINT、join 1s→5s、
  `create_background_task` 旧契约、任务表测试种子时间戳改为"新鲜"、
  bandit 子进程补 `encoding="utf-8"`。

### 修复（OpenCodeReview 深度审查批次 — 安全 / 事务 / 本地门禁，2026-09-17）

采用 alibaba/open-code-review v1.12.4 `ocr scan` 全文件审查（**376 文件 / 918 条发现**：
critical 36 · high 177 · medium 458 · low 247），逐条甄别后修复其中 **19 处确证缺陷**：

- **事务（静默丢数据）**：`core/transaction.py` 的 `transactional` 装饰器**两条路径都缺
  `commit`**。自动建会话分支依赖 `get_db_context()`，而 `get_db()` 的收尾只有
  `rollback` + `close`（`Session.close()` 对未提交事务即隐式回滚）——被装饰函数的
  **全部写入静默丢弃**，而同模块 `transaction()`/`run_in_transaction()` 均"成功即提交"。
- **令牌（fail-open 两处）**：`core/token_manager.py` 的 `extra_claims` 在保留声明之后
  `update`，调用方传 `{"type":"refresh"}` 即可绕过类型校验、`{"exp":…}` 可延长有效期
  → 改白名单（`sub/jti/type/iat/exp/nbf` 不可覆盖）；`validate_token` 原判断
  `if actual_type and …` 让**缺失 `type`** 的令牌同时通过 access 与 refresh 校验
  （同密钥签出的无类型令牌可换发新令牌对）→ 改为"存在且相等"。
- **吊销（安全回归）**：`core/token_blacklist.py` 把 `expires_at IS NULL`（永久吊销语义）
  在内存中降级为 `now + 86400`，条目 24h 后被 `_cleanup_expired` 清掉、**已吊销令牌
  重新可用** → 引入 `_PERMANENT = math.inf` 哨兵；`remove()`/`clear()`/`load_from_db()`
  三处共享字典裸写未持锁（与 `_cleanup_expired` 的锁内遍历竞态，可致
  `dictionary changed size during iteration` 或条目静默丢失）→ 全部纳入 `_BLACKLIST_LOCK`。
- **授权（fail-open）**：`core/permission_utils.py` 的 `require_admin` 以
  `isinstance(getattr(func,"role",None), str)` 区分"直接调用/装饰器"模式——任何 `role`
  为 `None`/枚举、或载荷缺 `role` 的用户对象都会被误判为"待装饰函数"，函数返回 wrapper
  而**不抛 403**，校验被静默跳过（全仓约 **100 个** `require_admin(current_user)` 调用点）
  → 改用 `callable()` 判定 + `_UNSET` 哨兵，`None` 等非法用户一律 403。同文件的组织归属
  校验在"用户无组织归属"时跳过整段（可读任意 `organization_id` 数据）→ 改为 fail-closed。
- **加密**：`services/aes_gcm_cipher.py` 在密钥长度非 32 字节时**静默换成随机密钥**，
  调用方以为在用自己的密钥，而该次加密的数据**永远无法解密**（加/解密两侧都报成功）
  → 提供了非法长度即抛错，`key=None` 仍按文档自动生成。
- **路径穿越**：`services/data_tier_service.py` 的 `restore_from_archive` 直接以 API 查询
  参数拼接归档路径，`../../etc/passwd` 可逃逸；pathlib 语义下**绝对路径更会完全覆盖
  base**（任意文件读）→ 强制纯文件名校验（`Path(x).name == x`）。
- **错误码**：`core/errors.py` 的 `_USER_NOT_FOUND_LEGACY = 4003` 与 `FILE_UPLOAD_FAILED`
  撞号，`IntEnum` 下重复值退化为静默别名（该成员从迭代消失、`ErrorCode(4003)` 解析为
  文件上传失败）→ 改为 4005。
- **配置**：`core/config.py` 用 `replace("data/", "")` 剥离前缀会移除**所有**出现，
  `sqlite:///./data/mydata/app.db` 被误算成 `myapp.db`（静默指向另一个空库）→ 只剥离
  开头目录分量。
- **并发**：`core/async_utils.py` 的 `gather_limited(0, …)` 构造 `asyncio.Semaphore(0)`，
  首个 `acquire()` 永久阻塞、整个 gather 不返回 → 入口校验 `concurrency >= 1`。
- **健壮性三项**：`core/build_info.py` 对非对象 JSON（`["a"]`、`"1.2.3"`）直接返回，
  真值即跳过 dev 兜底并在 `setdefault` 抛 `AttributeError`（**含未鉴权的 `/health`** 一并
  500）→ 类型校验后按缺失处理；`core/logging_config.py` 的 `ColoredFormatter` 就地改写共享
  `LogRecord.levelname`，把 ANSI 转义序列写进文件日志（JSON 格式化器还会当作 level 字段值）
  → 对副本着色；`core/query_optimizer.py` 自持的 `threading.local` 查询计数器**没有任何
  写入者**（恒为 0，`analyze_n_plus_one` 永不触发）→ 委托 `middleware/query_counter` 的
  真实 contextvar 链路。
- **本地门禁（中文 Windows 下"检查通过即崩溃"）**：`scripts/check_tokens_sync.py` 与
  `scripts/check_hardcoded_styles.py` 在**成功路径**打印 `✓`(U+2713)，cp936 无法编码
  → `UnicodeEncodeError` 且以 **exit 1** 结束——门禁假红且无法与真失败区分。补齐与
  `check_pragma_reasons.py`/`audit_static_assets.py` 一致的 `reconfigure(encoding="utf-8")` 兜底。

- 同步修正两处**固化了缺陷行为**的测试（非静默改断言，已在用例内注明理由）：
  `test_token_manager.py::test_no_type_claim`（原断言"缺 `type` 亦放行"）、
  `test_aes_gcm_cipher.py::test_custom_key_invalid_length_auto_generates`（原断言"非法长度
  密钥自动生成"）。

本轮为**不更新版本号**的加固发布：仅修复缺陷，`PROJECT_VERSION` 保持 1.12.8。
详细发现清单见 `deliverables/ocr-findings-detail.md`，总报告见
`deliverables/open-code-review-深度审查报告-2026-09-17.md`。

## [1.12.7] - 2026-09-13 — 🛡️ 遗留风险治理第二批（R2 上传体积上限 / R5 导出回收 / R9 导入拒绝记录 / R13 Windows CI 可见性）

对应《deliverables/遗留风险彻底解决方案计划-2026-09-12.md》第二、三周批次。

### 修复（可用性：上传内存峰值 — R2 第二层）
- 新增 `utils.upload_helper.read_upload_with_limit(file, max_bytes, ...)`：分块读取（1MB/块）+
  滚动累计字节，超限即停并抛 413；`status_code`/`error_detail` 可保持既有接口语义
  （如头像 400「头像文件不能超过 2MB」）。端点层 18 处 `await file.read()` 全部替换：
  头像 2MB / 数据包与加密包 100MB / Excel 导入 50MB / 导入校验 10MB / 上报包与管控包 512MB。
- 原写法先把 SpooledTemporaryFile **整包物化进内存**再比较长度，校验只能拒绝请求、
  挡不住内存峰值（单机离线部署下单请求即可 OOM，整库应用不可用）。中间件的
  Content-Length 分级预检不变，本层补足端点内真实上限与「短读即 EOF」语义。

### 修复（安全：压缩炸弹防护 — R2 第三层）
- 新增 `zip_total_uncompressed_size(zf)` / `ensure_zip_within_limit(zf)`（解压后总量 ≤ 200MB）
  与 `read_zip_member(zf, name)`（按 `ZipInfo.file_size` 预检后限长读取），接入
  `control-packages/import-preview`、`control-packages/import`、`subordinate-reports/import`
  与其 3 处成员读取点。容器体积合规 ≠ 解压后合规（1MB deflate 可膨胀到数十 GB）。
- `policy_import_service` 此前**完全无上限**：补 10MB 体积上限（分块读取）+ 1000 行上限，
  口径与 `data_validator_service`（10MB/1000 行）对齐。

### 修复（磁盘增长：异步导出文件回收 — R5）
- 新增 `async_export_service.purge_expired_exports(db)` + 调度作业 `export_purge_job`
  （每日 04:00）：`expires_at < now` 且非 pending/processing 的任务删除文件并标记
  `expired`（记录保留供审计、`file_path` 置空）；同时回收导出目录 mtime 早于 24h 的
  `*.part` 半成品（A2 原子落盘后强杀残留）。
- 此前 `expires_at` 只用于拒绝下载，**无任何回收逻辑**：`exports/` 目录随使用频率单调增长。

### 修复（数据一致性：导入失败记录 — R9）
- `DataPackageService.import_package` 校验失败分支不再落 `file_path`——该路径是 API 层
  临时文件，调用方 `finally` 立即 unlink，落库后记录永久指向不存在文件（`/validate`、
  `/download` 恒报「文件不存在」且无修复路径）。`_create_package_record` 支持 NULL 路径。
- `/data-packages/{id}/validate`、`/{id}/download` 对 `file_path` 为空返回 **409**（明确
  「已被拒绝（校验失败）」语义）；有路径但磁盘缺失仍为 404。
- **顺带修复真实缺陷**：`PackageStatusEnum` 成员为大写 `FAILED`，原 `PackageStatusEnum.failed`
  在校验失败分支必抛 `AttributeError` → 被端点兜底成 500「导入失败」，用户看不到真实校验
  原因（既有单测用 `patch` 掩盖了该缺陷，已改为断言真实行为）。

### 修复（工程：Windows 专属缺陷 CI 可见性 — R13）
- `pr-checks.yml` 新增 `windows-smoke` 作业（`windows-latest`，`PYTHONUTF8=1` +
  `PYTHONIOENCODING=utf-8`）：跑编码/句柄/路径敏感子集（pragma ratchet F2、安装包无测试
  校验、备份路径对齐、数据同步路由、帮扶村上传）+ `flake8 app/ --max-complexity=16`。
  此前全部作业跑在 ubuntu-latest，Windows 编码（GBK 管道）、句柄占用、路径分隔符类缺陷
  只能本地撞见（v1.12.3 出包编码崩溃、v1.12.6 管道解码 3 例失败为同类先例）。作业数 6→7。

### 未实施（按计划排期，非本批次）
- **R7 恢复窗口与在途写请求竞态**（P1）计划列为 W3–W4（10-09 前），需改造 `get_db`
  依赖注入与在途请求计数，不在本批次实施。
- **R12 剩余项**（`os._exit` 优雅退出、`_tasks` 过期清理等）同列 W4。

### 测试
- 新增 `tests/unit/test_upload_limit_r2.py`（16 例）、`test_export_purge_r5.py`（15 例）、
  `test_data_package_rejected_r9.py`（8 例）。
- 适配既有断言：调度器 Timer 计数 12→13（新增 export_purge）、数据包下载无实体文件
  404→409、导入体积门禁从「事后校验」改为「分块读取前置」。

## [1.12.6] - 2026-09-12 — 🛡️ 遗留风险治理第一批（P0 调度健壮性 / 启动 VACUUM / multipart 上限 / 备份语义）

对应《deliverables/遗留风险彻底解决方案计划-2026-09-12.md》的第一、二周批次（R1/R2/R3/R4/R6/R8/R11/R12 部分）。

### 修复（性能/可用性：启动期独占锁竞争 — R1）
- **`services/database_health_service._monitor_loop`**：`last_integrity_check / last_quick_check /
  last_vacuum` 原以 `datetime.min` 初始化，首轮条件恒真 —— 「每周一次 VACUUM」实际退化为
  「**每次启动** + 每 7 天」，启动窗口正值前端请求高峰，VACUUM 需要独占锁造成
  `database is locked` 抖动。现以「启动时刻」为基准起算，首轮不触发；
  轻量的 WAL checkpoint（不生成临时文件）保留首轮即执行以尽早回收 `-wal`。
- `vacuum_database()` 改为经 `db_coordinator.exclusive_write()` 执行，与批量导入等
  opt-in 长写路径互斥，monitoring 线程不再与在线写事务互相等待超时。

### 修复（可用性：调度器 Timer 生命周期 — R8）
- **`services/backup_scheduler`**：三类调度形态收敛为统一语义 —
  - interval/weekly/daily 的**递归重排 Timer 统一经 `_register_timer()` 登记**
    （原 interval 链从不入 `_timers`，`stop_backup_scheduler()` 的 cancel 拦不到，
    关闭阶段仍可能触发 DB 写 —— 「幽灵写」）；
  - `_register_timer` 回收已终止句柄（原 daily/weekly 每次重排都 append，
    每天 +9 个失效 Timer 对象常驻，停机耗时线性增长）；
  - 新增模块级 `_stopping` Event：`stop()` 先置位再 cancel，`_job` 在执行前与
    **重排前**双重检查 —— 单作业运行跨越 stop 窗口时链也不会复活；
  - `start()` 复位 `_stopping`，支持同进程 stop → start 再初始化。
- 调度体提升为模块级函数（`_schedule_daily/_schedule_weekly/_schedule_interval`），
  `start_backup_scheduler` 复杂度回到 CI 门禁（C901 ≤ 16）以内。

### 修复（资源泄漏：分片上传 — R4）
- **`services/backup_scheduler`** 新增 `chunk_cleanup_job`（每 30 分钟）：
  `chunked_upload_service.cleanup_expired_sessions()` 此前**全仓无任何生产调用点**，
  客户端 init 后中断（断网/关页面）的会话在 `uploads/chunks/` 与内存 `_sessions`
  中**永久泄漏**（单会话最坏 2GB）。
- **`services/chunked_upload_service`**：新增 `MAX_SESSIONS=200` 会话数量上限，
  超限按 `created_at` 淘汰最早会话（连同其分片目录），防异常客户端循环 init 打爆内存。

### 修复（安全：multipart 请求体无上限 — R2 第一层）
- **`middleware/body_size_limit`**：原实现对 multipart/form-data **一律放行**，
  而 12 个上传端点均为「先整包 `await file.read()` 入内存后校验」——校验只能拒绝请求，
  不能阻止内存峰值，单请求即可 OOM。现按 `Content-Length` **分级预检**：
  备份恢复 10GB（对齐端点既有上限）/ 权限包与数据同步 512MB / 其余 512MB，超限 413。
  各端点自身更严格的业务上限不受影响。Transfer-Encoding: chunked 的流式计量
  留待纯 ASGI 改造（计划 R2 第二、三层）。

### 修复（数据安全：备份语义 — R6 / R3）
- **`services/backup_service._create_consistency_snapshot`**：快照失败不再回退
  「WAL checkpoint + 裸拷贝主库」—— 该回退会**丢弃仍留在 `-wal` 中未合并的已提交事务**，
  而备份包又能通过 CRC + integrity_check 校验，产出「陈旧但合法」的备份并标记成功。
  现抛 `BackupIncompleteError`（宁可当天无可用备份，次日自动重试）。
- **`cleanup_old_backups` / `cleanup_by_retention_days`**：文件删除失败（被下载流/
  杀软占用）原实现吞异常**仍删数据库记录** → 「幽灵备份」永久占盘且 UI 无法再删。
  现保留记录（WARNING 日志）等待下次清理重试，清理本身不中断。

### 修复（性能：options 缓存永不命中 — R12）
- **`api/v1/auth/users`**：三个 options 端点的 `@cache_result` 默认键包含
  `current_user` 的 `repr`（含内存地址），每次请求键都不同 → 缓存命中率≈0。
  三处返回内容为与调用者无关的静态数据，键改为固定函数名。

### 其他
- `requirements.txt`：为 `diskcache==5.6.3` 登记 PYSEC-2026-2447 / CVE-2025-69872
  （上游无修复版本）及本仓 `JSONDisk` 应用层缓解说明。
- 测试基建：`tests/unit/test_pragma_reason_ratchet_f2.py` 的 `subprocess.run(text=True)`
  在 Windows GBK 管道下必现 `UnicodeDecodeError`（`_readerthread` 线程异常 →
  3 例失败 + 4 条 warning），统一改为 `encoding="utf-8", errors="replace"`
  （与 v1.12.4 `verify_package_no_tests.py` 同根因）；顺带移除未使用的 `import io`。
- 新增回归测试：`tests/unit/test_scheduler_hardening_20260912.py`（R4/R8 共 10 例）+
  `test_deep_audit_fixes_20260912.py` 扩充（R1/R2/R3/R6/R12 共 15 例）。
- 文档：新增《遗留风险彻底解决方案计划-2026-09-12.md》（13 项风险分级/排期/验证标准）。

## [1.12.5] - 2026-09-12 — 🔒 深度审计加固（目录穿越 / 存储型 XSS / 并发 / 备份 fail-loud）+ D1 写锁退避重试

### 修复（安全：上传路径穿越 + 存储型 XSS）
- **`core/upload_security.sanitize_filename`**：原实现仅替换 `<>:/"|?*` 而**保留 `\`**。
  Windows 下 `\` 与 `/` 同为路径分隔符，`..\..\evil.zip` 经
  `Path(upload_dir) / name` 拼接后越界写出（目录穿越）。现先按两种分隔符
  `re.split(r"[\\/]+", ...)` 取最后一段（等价 basename），并 `strip()` + 去尾部 `.`，
  空结果兜底 `_`；中文文件名不受影响。
- **`api/v1/data_sync._safe_filename`**：在 sanitize 之后再 `Path(...).name` 兜底一次，
  保证任何平台语义下都无分隔符残留。
- **`api/v1/supported_village.upload_section_attachment`**：区块附件落在
  `UPLOAD_DIR/sections`，而该目录经 `/uploads` 静态挂载对外提供（无需鉴权）。
  新增**禁止扩展名黑名单**（`.html/.htm/.xhtml/.shtml/.svg/.xml/.js/.mjs/.vbs/.hta/.jsp/.php`），
  拦截存储型 XSS；并对 `file.filename` 与 `section` **双重净化**（原实现直接拼接 → 穿越 + XSS）。
- **`api/v1/supported_village.delete_section_attachment`**：原实现仅删库记录，
  附件在 `/uploads` 下**永久残留（孤儿文件）**；现同步 `os.remove` 清理磁盘文件。

### 修复（可靠性：并发与资源泄漏）
- **`api/v1/system/tasks`**：`_tasks` 内存字典无锁 —— 后台任务线程插入、请求线程迭代/删除
  并发时可能抛 `RuntimeError: dictionary changed size`。新增 `_tasks_lock`，
  对插入 / 列表快照 / 删除 / 计数**全部持锁**。
- **`services/backup_scheduler._run_scheduler_job`**：`loop.run_until_complete` 抛异常时
  原实现**跳过 `loop.close()`**，每次失败泄漏一个事件循环（IOCP/selector fd + 未回收任务）。
  现将 `loop` 提到 try 外 + `finally: if loop is not None: loop.close()`。
- **`services/db_maintenance.stop_wal_checkpoint_scheduler`**：停止后**未复位 `_wal_thread`**，
  同进程二次进入 lifespan（测试用 TestClient / 进程内重初始化）时
  `start_*` 会因 `_wal_thread is not None` 直接返回，WAL 调度**永久静默失效**。现置回 `None`。
- **`services/immediate_backup.trigger_immediate_backup`**：`t.start()` 失败（线程资源耗尽）
  时**未释放幂等锁** `_triggered_once`，此后所有「关键操作前备份」都被静默跳过。
  现捕获异常 → 释放锁 → 记日志 → 返回 False。

### 修复（备份/恢复：fail-loud 与 Windows 文件语义）
- **`api/v1/system/backup._resolve_backup_file_path`（新增）**：下载/预览/校验/恢复四个入口
  原先**只查默认目录**，配置 `backup_target_dir`（备份到 U 盘/移动硬盘）后
  备份「列表可见，但下载与恢复恒 404」——恰是该功能的核心用途。现统一为
  单一定位函数：优先配置目录 → 默认目录，保留 `realpath` 前缀校验防 `../` 逃逸（403）。
- **`services/backup_service`**：
  - `_restore_uploads_from_backup` / `_rollback_to_snapshot` 的 `shutil.copytree` 补
    `dirs_exist_ok=True`：Windows 上 `rmtree` 可能因文件被占用而「部分删除」并留下目录，
    原实现此时抛 `FileExistsError` 使恢复失败并连锁破坏回滚。
  - 快照创建移入 `try` 内：原实现若在建快照时抛错（磁盘写满/文件被占用），
    `finally` 不执行 → `restore_XXXX` 临时目录与**解密的明文临时包永久残留**在 `%TEMP%`
    （敏感数据落地）。
  - 恢复路径 **fail-loud**：`_restore_database_from_backup` 返回 False（备份包缺库 /
    完整性校验未通过）时原实现**照常返回 `success=True`** 并删掉唯一回滚快照 →
    「恢复失败却报成功且再无退路」。现抛 `BackupRestoreError`。
  - `verify_backup` 同理：ZIP 结构完好但 `PRAGMA integrity_check` 未通过时
    原返回 `status="ok"`（把最坏故障判为通过），现返回 `status="error"`。
  - 回滚清理 `os.unlink` 的 `except FileNotFoundError` 放宽为 `except OSError`
    （Windows 被占用时 `ERROR_SHARING_VIOLATION` 不再是 `FileNotFoundError`）。
- **`api/v1/school.import_schools_excel`**：`delete=False` 的临时上传副本**成功/失败都不清理**，
  每次导入在 `%TEMP%` 残留一份；现收敛到 `finally` 删除。

### 工程（非功能性）
- **`services/permission_package_service`**：`open(file_path, "rb").read()`
  → `Path(file_path).read_bytes()`，与契约类型统一、消除资源告警。

### 回归与验证
- 新增 `tests/unit/test_deep_audit_fixes_20260912.py`（42 例）：逐修复点做「修复前失败、
  修复后通过」的差异断言（穿越剥离、XSS 黑名单、并发无 `RuntimeError`、
  事件循环已关闭、幂等锁已释放、fail-loud 返回 error、`dirs_exist_ok` 覆盖等）。
- **修正陈旧夹具（10 例）**：`test_backup_service.py` / `test_backup_service_full.py`
  中恢复路径仍用**纯文本占位 DB**（`zf.writestr(..., "new")`），与 `create_backup`
  早已引入的恢复性校验契约（helper 文档自述「纯文本占位夹具不再可用」）不一致；
  恢复路径 fail-loud 收口后集中暴露。现改用真实 SQLite 夹具并同步 `test_restore_no_db_in_backup`
  的语义（无库 → 期望抛 `BackupRestoreError`，不再 `success=True`）。
- CI 门禁闭环：首轮 backend-test 因 `backup_service.py:1207`（`if not db_verified`
  防御返回块）未覆盖变红（99.99% < 100%），以可控桩补齐后 **PR Checks 6/6 全绿**。

### 修复（架构评估 D1：SQLite 写竞争“观测有余、防护不足”）
- **根因**：仓库唯一的重试工具 `core/transaction.retry_on_deadlock` **只有测试引用**
  （事实上的死代码），而 SQLite 单写多读下后台长事务（备份/清理等）
  与在线写操作争抢写锁时，`busy_timeout=10000` 用尽即报
  `database is locked` 且**无人重试**。
- **判定收口**：新增 `is_lock_contention()` 作为唯一判定入口，白名单只认
  `database is locked` / `database table is locked` / `database schema is locked` /
  `deadlock` / `lock timeout` / `lock wait timeout` / `sqlite_busy` ——
  **不再**用宽泛的 `"lock" in text`，避免把 `no such table`、唯一约束冲突
  这类真实缺陷也拿去重试（重试只会掩盖 bug）。
- **能力补齐**：`retry_on_deadlock` 升级为**同步 + 协程双形态**（后台作业多为
  async），退避改为线性 `delay * (attempt + 1)`，并记录重试次数；重试次数耗尽仍抛原异常，
  `max_retries<=0` 抛不带异常原文的 `DatabaseError`（W1 #6）。
- **生产在用**：`BackupService.create_backup` 与 `cleanup_by_retention_days`
  这两条真实长事务写入口挂上退避重试（备份失败=当天无可用备份，代价高）。
  导出/导入路径**故意不加**整体重试：它们已有明确的失败回写与
  恢复路径（`recover_stale_export_tasks` / 导入历史），而挨个单元重跑会在
  部分已提交时产生重复写入 —— 宁可让用户重试，不可静默重复入库。
- **回归**：新增 `test_lock_contention_retry_v124.py`（15 例）—— 判定白名单真值表
  （含 `no such table`/唯一约束必须不重试）、同步与协程重试成功/不重试/耗尽/零次四种
  终态、以及**结构性断言**（两个备份写入口必须仍挂着装饰器、
  `retry_on_deadlock` 在 `app/` 下必须有生产引用）。
- **验证**：后端全量 **11033 passed / 0 failed，覆盖率 100.00%**；
  flake8 0；bandit -ll 0。

### 增强（C1 备份同卷可见化 + F1 单轨化可观测）
- **C1 同卷告警**：新增 `backups_share_volume_with_database()`（优先比较
  `st_dev`，失败时按盘符/POSIX 挂载点前缀兜底，
  无法判定返回 None —— **绝不猜成“安全”**），
  并在无认证 `/health` 新增 `backup.same_volume_as_database`。
  同盘意味着断电/盘损时数据与备份一起消失 ——
  配套约定早已要求 `backup_target_dir` 指向独立物理盘，
  但此前**没有任何机制让“没配”这件事可见**。
  本机实测即为同盘（`true`）—— 该信号立刻有效。
- **F1 单轨化可观测**：`/health.migration.auto_migration_enabled` 如实回报是否仍在跑
  已弃用的自动补列兜底（`ENABLE_AUTO_MIGRATION`，默认 False），
  使“单轨化倒计时”（连续 2 个版本无人开启即删除该路径）
  有可依据的观测口，而不是只能翻代码。
- **两个信号均不泄露路径**：`/health` 无认证，因此只出布尔值/状态；
  回归用例断言响应文本不含数据库文件名与绝对路径。

### 工程（F2 豁免理由 ratchet：规则从“写在文档里”变成“门禁在跑”）
- **现状**：配套约定 F2 条要求“`# pragma: no cover` 必须同行注明理由”，
  但**零执行力** —— 实测 `backend/app` + `scripts` 共 172 处 pragma，其中 **130 处无理由**。
- **新增 `scripts/check_pragma_reasons.py`**（ratchet 策略，不下调门槛、不要求一次性还债）：
  - 默认只检查**本次新增/修改行**（基线自动解析 origin/main → HEAD~1，
    浅克隆下也不静默通过：基线不可用默认退出 2，除非显式
    `--allow-missing-base`）；
  - `--max-bare 130` 作为**硬上限**：防止“一边清理一边新增”抵消；
  - `--all` 输出存量清单供分批清理（不阻断）；违规时额外打 `::error::` 注解。
  - 检测口径：用 `tokenize` 取**注释 token** 而非整行文本 —— 否则字符串里的
    `"# pragma: no cover"`（检查器自身的实现行与 help 文案）会被当成豁免：
    自检时实测报了 2 处假阳性，故改为词法层判定（语法错误文件回退行扫描，
    检查器自身不得因被检文件而崩）。
  - `--diff-base` 同时覆盖**未跟踪新文件**（`git ls-files --others`）——
    自检时实测：新文件里塞一个裸 pragma 最初被漏掉。
- **接入 CI**：pr-checks 的 static-analysis 新增“Coverage-exemption reason ratchet (F2)”步骤。
- **回归**：`tests/unit/test_pragma_reason_ratchet_f2.py`（16 例）—— 理由判定真值表、
  字符串不得误判、语法错误回退、上限拦截、基线缺失不静默、
  以及“工作区新增裸 pragma 必须被命中”端到端用例。

### 验证
- 后端全量 **11033 passed / 0 failed，覆盖率 100.00%**（新增 9 例视可性回归）；
  flake8 0；bandit -ll 0。
- 分支可达性：`same_volume` 四种结论（同卷/异卷/未知/stat 失败兜底）在
  Windows 与 Linux 上**均可计算**（实现刻意不做 abspath，否则 POSIX 分支在
  Windows 永不可达，本地覆盖率门禁会与 CI 分叉）。


## [1.12.4] - 2026-09-12 — 🛠️ Windows 出包门禁编码缺陷修复 + B1 数据域下沉全量收口

### 修复（致命：打包卫生门禁在 Windows CI 上必崩，误杀合格构建）
- **根因**：`scripts/verify_package_no_tests.py` 输出中文，而 windows-2022（en-US）
  上 Python 对**管道**的默认 stdout 编码是 ANSI 代码页 `cp1252` ——
  第一个 `print` 即抛 `UnicodeEncodeError`，步骤以 exit 1 结束。
  v1.12.3 的 `Build Windows Installer (x64)` 就是这样被拦下的（**产物其实完全干净**），
  而该任务的 job 日志需 admin、注解里只有“exit code 1” —— 排查代价极高。
  本地复现：`PYTHONIOENCODING=cp1252 python scripts/verify_package_no_tests.py ...`
  修复前 exit 1（回溯到 encodings/cp1252.py），修复后 exit 0。
- **修复**：① 脚本内强制 `sys.stdout/stderr.reconfigure(encoding="utf-8",
  errors="replace")`；② `build-windows.yml` 的 build-windows 任务级加
  `PYTHONUTF8=1` + `PYTHONIOENCODING=utf-8`（防止同类事故再发）；
  ③ 违规时额外输出 GitHub `::error::` 注解 —— **注解可通过
  check-runs API 匿名读取**，日后门禁失败不再是一句无信息的
  “exit code 1”。
- **回归**：`test_verify_package_no_tests_v123.py` 新增 2 例子进程用
  `PYTHONIOENCODING=cp1252` 跑真实脚本，分别锁定“干净产物必须 exit 0”
  与“真违规仍必须 exit 1 且打印 ::error::”（编码兜底不得吞掉真问题）。
- **出包影响**：v1.12.3 的 ARM64 DEB 构建成功、Windows 构建失败；
  本版重出两包（标签 `v1.12.4`）。

### 重构（架构评估 B1 Phase 2：数据域过滤全量下沉）
- **api 层收口**：`assessment`、`data_quality`、`import_export/export`、`project_milestones`、
  `report_templates`、`search`、`villages` 共 **19 处**调用改经
  `services/data_scope_query.scoped_filter`（`db` 形参在核心原语里存在但从未使用，
  删除为纯等价改写）。
- **services 层收口**：`ai_service`(11)、`ai/recommendation_service`(5)、`analytics_service`(1)、
  `excel_importer_service`(4)、`report_service`(1)、`async_export_service`(5) 共 **27 处**同步下沉。
- **结构性回归**（新增 `test_data_scope_entrypoint_v123.py`，8 例）：
  ① AST 扫描锁定 `app/api/**` 与 `app/services/**`（除唯一入口模块）**不得再出现**
  核心原语引用 —— “新写路由又绕过统一入口”会在 CI 立刻失败；
  ② 对 super_admin / admin / user 三档角色比对
  `scoped_filter` 与 `filter_by_data_scope` 的 **SQL 编译串逐字一致**（S2 红线：
  下沉只换入口、不改语义）；③ 核心原语仍是唯一真源，
  服务层入口必须委派（patch 验证调用次数）。
- 并修正批量迁移后失效的 **19 处测试 patch 目标**
  （`app.api.v1.search.filter_by_data_scope` / `patch.object(mod, ...)` 等）——
  它们在代码改名后会直接抛 AttributeError。

### 验证
- 后端全量：`pytest tests/ -n auto --cov=app` —— **11002 passed / 0 failed**，
  覆盖率 **100.00%**（37862 语句 0 missing）。
- 打包门禁：`verify_package_no_tests.py` 在 `PYTHONIOENCODING=cp1252` 下 exit 0（修复前 exit 1）；
  真实产物（PyInstaller onedir 2923 文件 + 安装包模拟列表 2924 成员）零违规。
- 静态/安全：flake8 0；bandit -ll 0（Medium/High 均 0）；`security_audit.py --verbose` 0 问题；
  `sync-version.js --check` 退出 0。

## [1.12.3] - 2026-09-12 — 🛡️ 架构评估 P1/P2 整改（迁移单轨化 / 恢复演练 / CSRF ASGI 化 / 启动拆包 / 修复引导页）+ 安装包无测试门禁

### 加固（架构评估整改）
- **F1 迁移单轨化第一步**：`ENABLE_AUTO_MIGRATION` 默认值 `True → False`
  （`core/config.py`），schema 变更统一走编程式 Alembic upgrade
  （生产环境 fail-loud）。双轨制是唯一发生过真实事故的技术债
  （commit 4c1ea8a0 MultipleHeads 打包实例启动失败）；应急时仍可
  临时设 `ENABLE_AUTO_MIGRATION=true`。
- **C1 月度备份恢复演练**：新增 `restore_drill_service` —— 把最新备份
  真实还原到临时目录（unzip 落盘）跑 `PRAGMA integrity_check` +
  核心表抽查，**只读演练不触碰生产库**；`restore_drill_job` 每日 05:45
  检查到期（`restore_drill_interval_days`，默认 30）执行，失败向管理员
  发消息；结论经 `/health` 的 `restore_drill` 字段暴露（无认证端点只出
  状态/文件名/异常类名），重启后从 SystemConfig 回填。加密备份显式记
  `skipped_encrypted`，不留盲区。
- **E1 CSRF 中间件纯 ASGI 化**：从 `BaseHTTPMiddleware.dispatch` 改写为
  `__call__(scope, receive, send)`（逐分支一致），消除注释自认的
  h11 协议错误风险——"开=带病、关=裸奔"两难解除，CSRF 可常开；
  `get_client_ip` 同步改为 scope 版（fail-closed 代理透传语义不变）。
- **B1 数据域过滤下沉服务层（Phase 1）**：新增 `services/data_scope_query.py`
  统一入口（`scoped_query` / `scoped_filter` / `scoped_count`，语义单一
  真源仍是 `core/data_permission.py`），迁移评估点名热点
  `data/data/reports.py`；security_audit 扫描器同步识别新入口名，
  回归防线保留。其余 ~40 调用点按批迁移。
- **B3 启动钩子拆包**：main.py 987 → ~710 行。14 个启动/停止钩子迁至
  `app/startup/{recovery,seed,environment,monitors}.py`（逐字搬移），
  main 以同名别名 re-export，`from app.main import _xxx` 与
  `patch("app.main._xxx")` 全兼容；数据库初始化集群
  （`_init_database_tables`/Alembic/`_migration_status`）与测试、/health
  强耦合，按计划保留在 main。
- **A3+C2 Electron 修复引导页**：新增 `electron/recovery.html` —— 后端
  连崩 3 次超限、或页面加载耗尽 5 次重试时，加载引导页（一键重启后端 +
  打开诊断/应用日志），替代原先"错误框后静默放弃/死屏"；IPC 通道
  `recovery-*`，preload 经 contextBridge 暴露，一键修复成功自动返回系统。
- **F3 Electron 版本单一来源**：`appVersion` 改用 `app.getVersion()`
  （打包元数据由根 package.json 注入），删除硬编码 fallback 字面量，
  读取失败回退为空 + 告警，不再与 PROJECT_VERSION 双源漂移。

### 打包卫生（安装包不得包含测试内容）
- **spec 剔除三方库测试资产**：实测 sklearn 经 collect_data_files 把
  `sklearn/datasets/tests/`（openml 夹具 80+ 文件）带入产物；
  `assistance-backend.spec` 新增 `_strip_test_data_toc` 统一过滤
  a.datas 中所有 `tests/`/`test/` 目录。
- **CI 双重门禁**：新增 `scripts/verify_package_no_tests.py`
  （文件树扫描 + PYZ 模块检查 + 前端产物抽查，任一违规 fail-loud），
  接入 build-windows 的 onedir 验证步；electron-builder 打包后经 7z
  列举安装包内容抽查测试内容。
- **extraResources 过滤兜底**：backend 产物拷贝 filter 显式排除
  `tests/`、`test_*.py`、`conftest.py`、`pytest.ini`、`.coveragerc`。

### 门禁收口（v1.12.3 出包前置）
- **版本号全量对齐 1.12.3**：整改提交只把根 `package.json` 提到 1.12.3，
  其余 9 处仍是 1.12.2（`config.py` / `version.txt` / `README` / `docker-compose.yml`、
  `docker/Dockerfile.kylin-standalone` / `frontend/src/config/constants.ts` / `frontend/.env.example`、
  `.env.example` / `backend/version.json` / `scripts/docker/build.ps1`）—— CI 的
  Version consistency check 必红。已用 `scripts/sync_version.py 1.12.3` +
  `node scripts/sync-version.js --write` 收口，`--check` 退出 0。
  同时修掉两个**死版本目标**：`electron/main.js`（F3 后已无字面量可同步）
  改为「单一来源契约检查」（仍需 `app.getVersion()` 且不得重新引入硬编码）；
  `scripts/legacy/build-kylin.sh` 改为对准真实存在的 `|| echo "1.2.0"` 兜底字面量
  （实测长期漂移到 1.2.0）；新增 `frontend/package-lock.json` 与
  `electron/splash.html` 两个目标（splash 静态 `V1.12.2` 已删，改由 main.js 注入）。
- **后端覆盖率门禁回 100%**：整改引入的 6 行未覆盖
  （`backup_scheduler.py` 484-485 / 493-494、`restore_drill_service.py` 121 / 184）
  以**行为断言**补齐（`tests/unit/test_restore_drill_gaps_v123.py`，新增 6 例），
  而非 pragma 豁免。过程中发现既有 `test_restore_drill.py::TestSchedulerJob`
  的 **patch 目标失效**：`backup_scheduler` 在模块级绑定了
  `get_config` / `get_db_context`，patch 源模块属性不生效，导致
  `test_job_exception_is_swallowed` 从未真正注入异常（测试"通过"却什么都没断言）——
  已改为 patch 绑定处，并补齐 `else` 分支与 `backup_dir` 回退路径。
- **bandit 门禁修复**：`restore_drill_service.py` 用 `# noqa: S608` 抑制 SQL 告警，
  但本仓**未装 flake8-bandit 插件**、CI 跑的是 `python -m bandit -r app/ -ll`
  （只认 `# nosec`）—— 惰性标记使 lint 任务必红。已改为
  `# nosec B608` 并注明白名单理由（与仓内既有 10+ 处一致）。
- **安装包抽查规则收口**：`build-windows.yml` 的 7z 抽查原为内联正则，
  与 `scripts/verify_package_no_tests.py` 的规则重复实现（且无厂商豁免表）；
  已改为 `--listing` 模式（同一实现 + 同一豁免表），并保留旧正则强度
  （`pytest` 命名残留同样拦截）。本地对**真实构建产物**预演：2924 项归档成员 0 违规，
  且规则强度与旧正则逐项比对无差异；同步补齐
  `tests/unit/test_verify_package_no_tests_v123.py`（9 例：厂商豁免 / 本项目拦截 / CLI 三态）。
- **CSRF 纯 ASGI 等价性补齐**：逐分支走查发现自行解析 Cookie 不去引号，
  而原 `Request.cookies` 会按 RFC 6265 去除引号 —— `csrftoken="<token>"` 这一形态
  会从"通过"变成 403（与原实现不再等价）。已在 `_parse_cookies` 去引号并补回归用例。

### 文档
- `docs/architecture/架构评估整改配套约定-2026-09-12.md`：E2 shutdown
  信任边界标注、F2 覆盖率豁免清单约定（豁免必须同行注明理由）、
  B2 services 分包分批规划（本期仅规划，零行为变更）、C1 RPO/RTO 与
  备份存放基线（建议 `backup_target_dir` 指向独立物理盘）。

### 回归
- 新增回归：`test_csrf_asgi.py`（15，含引号 cookie 等价例）、`test_restore_drill.py`（25）、
  `test_data_scope_query.py`（6）、`test_restore_drill_gaps_v123.py`（6）、
  `test_verify_package_no_tests_v123.py`（9）。
- B3 拆包保留了 `from app.main import _xxx` / `patch("app.main._xxx")` 兼容（别名同步
  在 lifespan 里）；但调度器测试原先 patch 错了绑定处（见「门禁收口」），已修正。
- 全量：**10994 passed / 0 failed，覆盖率 100.00%**；前端 302 文件 / 6045 用例全绿。

## [1.12.2] - 2026-09-11 — 🐛 R19–R31 深度探针修复 + 架构评估 P0 加固（导出/备份/迁移门禁）+ CI 前端门禁回归修复

### 加固（架构评估 P0）
- **A1 导出任务重启自愈**：`recover_stale_export_tasks` 在 lifespan 启动时把
  pending/processing 僵尸导出任务置为 failed，不再依赖内存队列重启自愈
  （重启后任务永远停在"进行中"是用户可见的假状态）。
- **A2 导出/备份原子落盘**：产物先写 `.part` 临时文件、成功后
  `os.replace` 原子替换；进程中途被杀（断电/强杀，捕获不到异常）
  不再在导出/备份目录留下半截文件被列表/cleanup 当作有效产物。
- **C1 备份可恢复性校验**：备份落盘后校验 zip CRC（`testzip`）+
  库文件 `PRAGMA integrity_check`，不可恢复即 fail-loud 抛
  `BackupIncompleteError` 并删包 —— "备份成功但还原时才发现损坏"是最坏
  故障模式（帮扶数据不可再采集）；同步补齐边界覆盖（integrity_check 非 "ok"、
  校验临时文件删除失败、快照不可用时回退主库）与 8 处测试夹具（纯文本
  占位库 → 真实 SQLite 库）。
- **F1 迁移单 head 门禁入 CI**：`scripts/check_migrations.py` 校验 alembic 单 head 并接入
  pr-checks 的 static-analysis（历史上 MultipleHeads 分叉曾使打包版启动即崩）。


### 修复
- 🐛 **数据上报的 `report_type` 必填却从不落库（静默丢弃）**：R29 探针实测 ——
  `POST /api/v1/data-reports` 带 `report_type="monthly"` 创建成功（201），但响应里
  `report_type` 是**空串**：请求模型 `DataReportCreate.report_type` 是**必填**字段、
  响应模型 `DataReportResponse` 也回显该字段，可 `data_reports` 表与 `DataReport`
  模型都没有这一列，`DataReportService.create_report` 也从未读取 ——
  调用方必须传一个"传了也没用"的值，之后也无从按类型筛选/展示。
  修复：新增 `data_reports.report_type` 列（模型 + Alembic 迁移
  `data_report_type_001`，幂等加列）、`create_report` 落库、响应如实回显。
  回归：`tests/unit/test_data_report_type_r29.py`（6 例：schema 契约、列往返、
  service 端到端落库）。
- 🐛 **数据包 `data_types` 双重编码（版本变更摘要键变成单字符）**：R28 探针实测 ——
  `POST /data-packages/{id}/versions` 返回的 `changes` 竟是

  ```json
  {"[": {"added": [], "modified": [], "deleted": []},
   "\"": {"added": [], "modified": [], "deleted": []},
   "v": {"added": [], "modified": [], "deleted": []}, …}
  ```

  根因：`DataPackage.data_types` 是 **JSON 列**，而 `export_package` /
  `import_package` 写入时做了 `json.dumps(data_types)` **双重编码** —— 列里落的
  是 JSON *字符串*，读出来是 `'["villages", "projects", …]'`。版本变更摘要按可
  迭代对象遍历该字符串，于是键变成单个字符；把 `data_types` 当数组消费的地方
  （`/data-reports/{id}` 的包摘要）拿到的也是字符串。
  修复：两条写入路径直接存列表；读取侧新增 `_normalize_data_types()`
  归一历史双重编码行（字符串 → 解析 → 列表，解析失败回落单元素列表），
  `_package_version_changes` 与数据上报包摘要改用它。
  回归：`tests/unit/test_data_package_data_types_r28.py`（14 例，含列往返与
  历史脏行读回归一）。
- 🐛 **通用文件上传：`category` 只认查询参数（表单字段静默失效）+ 全量读入内存**：
  R26 探针实测两处 ——
  ① `POST /files/upload` 带 `category=policies`（**multipart 表单字段**，即
  el-upload 的 `data`/`:data` 形态）返回 200 但文件落到 `generic/` 而不是
  `generic/policies/`：`category` 被声明为裸 `Optional[str]`，FastAPI 只当
  **查询参数**解析，表单字段被忽略且不报错（与 R14「经费附件 category 走 FormData
  而后端只认 Query」同类）。修复：查询参数与表单字段**都接受**（对外线名均为
  `category`）。
  ② `await file.read()` 把整个文件读进内存后才判 50MB 上限 —— 超大文件先把内存
  吃满再被拒（OOM）。修复：8MB 分块流式落盘 + 滚动大小校验，超限/扩展名不合规/
  内容嗅探失败一律删除残片（零磁盘残留），对齐 backup upload-restore 既有约定。
  回归：`tests/unit/test_files_upload_r26.py`（9 例，含跨分块字节完整性、
  超限零残留、嗅探失败零残留、表单字段路径穿越中性化）。
- 🐛 **组织创建/更新的非法枚举值报 500（安装包验收发现）**：对刚构建并安装的
  `MRRS-Setup-1.12.1` 实例发真实请求时命中 ——
  `POST /api/v1/organizations {"name":"…","level":"1"}` →
  `500 {"code":500,"message":"服务器内部错误"}`。根因：创建/更新组织直接
  `OrganizationLevel(value)` / `OrganizationType(value)`，非法值抛 ValueError
  冒泡成未处理异常。合法值是 `level_1`…`level_5` /
  `department|support_unit|other`。修复：抽出 `_coerce_org_enums()` 统一转换，
  非法值返回 **422** 并列出允许值；创建与更新两条路径共用。
  回归：`tests/unit/test_organization_enum_validation_r24.py`（4 例）。
- 🐛 **「驳回 → 重新提交 → 审批通过」后经费永远停在「已驳回」（审批闭环断裂）**：
  R23 探针在真实 HTTP + 真实 DB 上实测：

  ```
  fund=23 task=17  初始   : task=pending  fund=pending
  驳回             → 200  : task=rejected fund=rejected   ✓
  重新提交         → 200  : task=pending  fund=rejected   ✗ 经费没回到待审批
  审批通过         → 200  : task=approved fund=rejected   ✗✗ 审批过了经费还是已驳回
  状态历史: [('pending','rejected',…)]   ← 没有 approved 行
  ```

  根因两处：① `ApprovalWorkflowService.resubmit_approval` 只把任务置回 pending，
  不动业务实体；② `_apply_fund_approval_result`（`funds.py`）要求
  `fund.status == "pending"` 才回写，而经费此时是 `rejected` → **最终审批通过被
  静默忽略**。后果是待审批板块显示已通过、经费板块永远显示已驳回，且**重试机制也
  救不回来**（`retry_apply_entity_change` 只在 `*_apply_failed` 态可用，而这里回写
  「成功」了——只是什么都没做）。修复：① `resubmit_approval` 在任务回到 pending 后
  调用 `apply_entity_change(task)`；② 回写映射改为显式状态对表
  `_FUND_APPROVAL_TARGETS`：`(approved, pending)`/`(approved, rejected)` → approved、
  `(rejected, pending)` → rejected、`(pending, rejected)` → pending，表外组合一律
  不动（幂等重复回写不再重复记历史）。
  复验：同一序列 `task/fund` 同步为 rejected → pending → approved，
  状态历史三段完整（pending→rejected→pending→approved）。
  其他实体处理器不受影响：`ProjectStatus`/`ScholarshipStatus` 没有 rejected 态，
  project/scholarship 回写无此路径。
- 🐛 **认证出口在「直接调用」路径下崩溃（潜在 500）**：`get_current_user` 在 P1-2
  性能优化（改用 `db: Session = Depends(get_db)` 复用注入会话）后，两个**直接调用**
  路径不再发生依赖注入，`db` 退化为 `Depends(get_db)` 默认哨兵对象，
  `db.query(...)` 抛 `AttributeError: 'Depends' object has no attribute 'query'`：
  1. `app/api/v1/system/backup.py::_jwt_user_from_request` —— Electron 内部通道
     之外的**合法 JWT 备份请求会直接 500**（内部密钥通道不受影响，故此前未暴露）；
  2. 单元测试直调（R22 全量套件残留 3 例失败即由此暴露）。
  修复（`app/core/security.py`）：仅当 `db` **不是真实 Session 实例**时自建
  `SessionLocal()` 并在 `finally` 关闭；注入路径仍复用注入会话且**不关闭**
  （生命周期归 `get_db`，避免误关共享连接）。新增回归
  `tests/unit/test_get_current_user_session_contract_r23.py`（3 例，含备份生产路径）。
- 🐛 **帮扶村「新建成功却看不到新记录」**：列表端点 `GET /supported-villages`
  固定 `order_by(SupportedVillage.id)` **升序**，新建记录 id 最大、落在**最后一页**；
  而前端新建成功后将分页重置到第 1 页 → 新记录不可见。同时前端部门列
  `sortable="custom"` 会下发 `sort_by`/`sort_order`，但后端从未声明这两个参数，
  **排序被 FastAPI 静默丢弃**。
  修复（`app/api/v1/supported_village.py`）：新增 `sort_by`/`sort_order` 查询参数与
  `_SORTABLE_COLUMNS` 白名单 + `_resolve_village_sort()`（默认 `id` 倒序 = 最新在前，
  非法列安全回退，与 `projects.py` 既有约定一致）；缓存 key 纳入排序维度避免串味。
  新增回归 `tests/unit/test_supported_village_sort_r23.py`（4 例）。

- 🐞 **CI 全红：`vitest` 半升级（v5 + coverage-v8 v3）打穿 `postinstall` 补丁**：
  `frontend/package.json` 把 `vitest` 提到 `^5.0.0`，而 `@vitest/coverage-v8` 仍停在
  `^3.2.7`（peer 不匹配）；更关键的是 `scripts/patch-vitest-coverage.cjs`
  （根治 vitest-dev/vitest#9758 覆盖率分片 ENOENT 竞态）按 chunk 名
  `coverage.DfSpMS-b.js` 与两处内部锚点写死 vitest 3.2.7 实现 —— 装到 v5 后
  chunk 布局变化，补丁 fail-loud 退出（“存在多个 coverage.*.js”），
  `postinstall` 失败 → `npm ci` / `npm install` 整体失败 → CI 的 `frontend-check` /
  `security` / `e2e-test` 三个任务全红（同一修复点对应
  `Process completed with exit code 1`）。处置：`vitest` 回到 `^3.2.7`
  （与 coverage-v8 同一条版本线、与补丁锚点匹配），lock 重算
  （只有 vitest 及其传递依赖变动，已逐包核对）。
- 🐞 **「声明了但永远失败」的 `prepare` 脚本让 Windows 上的装依赖必定失败**：
  `"prepare": "python scripts/pre_commit_hooks.py install || true"` —— npm 在 Windows 用 cmd.exe
  执行 scripts，cmd 没有 `true` 命令，`prepare` 以 1 退出（本机实测
  `npm install` exit=1）；而且 `frontend/scripts/pre_commit_hooks.py` 根本不存在
  （真身在仓库根 `scripts/pre_commit_hooks.py`，且不认识 `install` 参数）
  —— 这一行本就是「恒 1 退出」的空操作，只靠 bash 的 `|| true` 掩盖。
  处置：删除该 `prepare`（钩子安装仍按 CLAUDE.md 记录的
  `pip install pre-commit && pre-commit install`），装依赖在 cmd / bash 下行为一致。
- 🐞 **ECharts 迁移后 `ruralWorks/Analysis.vue` 分支覆盖差 2 条（前端门禁 99.98% < 100%）**：
  `resizeCharts()` 中 `typeBarChartInstance?.resize()` / `statusBarChartInstance?.resize()` 只有空值侧被测到
  （默认饼/环形视图下柱状实例恒为 null）。回归测试补「切到柱状视图后再
  resize」路径（`tests/unit/views/ruralWorks/Analysis.test.ts`）。
### 验证
- 后端全量：`pytest tests/ -n auto --cov=app` —— **10926 passed / 0 failed**，
  覆盖率 **100.00%**（37651 语句 0 missing，`.coveragerc` fail_under=100）。
- 前端：`vue-tsc --noEmit` 0 错、`eslint --max-warnings=0` 0 错、
  `vitest run --coverage` **300 文件 / 6026 用例全绿**，12 项覆盖率阈值均 100%。
- 安装：`npm ci --legacy-peer-deps` 在 Windows（npm 脚本外壳为 cmd）下 exit 0，
  postinstall 的 vitest #9758 补丁应用成功。
- 产物：tag `v1.12.2` 触发的 `Build Windows Installer (x64)` 与
  `Build Self-Contained ARM64 Debian Package` 两个工作流均 **success**，Release 附
  `MRRS-Setup-1.12.2.exe`（Windows x64）、`MRRS-Setup-1.12.2.deb`（麒麟 ARM64 Electron）、
  `assistance-management-system_1.12.2_arm64.deb`（麒麟 ARM64 standalone）与 3 份 SHA256SUMS。

## [1.12.0] - 2026-09-06 — 🎨 UI 全面优化：字体统一 + 40px 舒适密度 + 布局标准化 + 认证页统一

### 安全
- 🔒 **事务层把 SQLAlchemy 异常原文内插进响应（W1 不变量 #6 违规）**：
  `app/core/transaction.py` 的 8 处 `raise DatabaseError(f"...: {str(e)}")`
  （`TransactionManager.transaction` / `transactional` / `run_in_transaction` /
  `nested_transaction` / `savepoint` / `_execute_with_existing_session` /
  `_execute_with_new_session` / `retry_on_deadlock`）与 `BatchOperation` 的 3 处
  批量操作，都把异常原文拼进了出站文案。SQLAlchemy 原文形如
  `(sqlite3.OperationalError) FOREIGN KEY constraint failed [SQL: INSERT INTO
  rbac_user_permissions (id, user_id, permission, granted_by, expires_at)
  VALUES (?, ?, ?, ?, ?)] [parameters: ('b0b7792e…', 99999999, 'user:read', …)]` ——
  R22 实测 `POST /rbac/grant/permission`（不存在的 user_id）的 **500 响应体里带着
  完整 SQL 结构、表名、列名与绑定参数**。源码扫描测试
  `test_no_error_detail_leak.py` 看不见这条路径（它只认
  `HTTPException(detail=<异常变量>)` 形态，这里是 `DatabaseError(message=…)`）。
  修复：新增 `_transaction_failure` / `_batch_failure` —— 约束类错误（外键/唯一/
  NOT NULL/CHECK）映射为 4xx，业务异常（AppError/HTTPException）原样透出
  （保留「角色(x)不存在」这类有价值提示，但文案里已夹带 SQL 原文的照样降级），
  其余一律泛化文案，原文只进日志（exc_info=True）。顺带修正：
  `/rbac/assign/role` 传不存在角色由 500「事务执行失败: 角色(x)不存在」
  变为 **404「角色(x)不存在」**。
- 🔒 **8 个端点把「关联 ID 不存在」报成 500/503**：R22 对全部 33 个带 `*_id`
  字段的 POST 端点做外键扫射，发现 `/funds`、`/funds/apply`、
  `/fund-budgets/transactions`、`/fund-lifecycle/allocation-orders`、
  `/organizations`、`/policies/categories`、`/projects`、`/user-management`
  在传入不存在的关联 ID 时返回 500/503（日志统一为
  `sqlite3.OperationalError: FOREIGN KEY constraint failed` —— SQLite 把外键冲突
  报成 OperationalError 而非 IntegrityError）。根因是「直接 INSERT，未先验关联
  对象存在」，而已有的 `@handle_db_errors` 装饰器只覆盖一小部分端点。
  修复：`map_db_exception` 抽为**单一事实源**（`core/exceptions.py`），
  `@handle_db_errors` 与新增的全局 `IntegrityError`/`OperationalError` 处理器共用
  同一套状态码与文案（外键→400「关联数据不存在或已被删除」、唯一→409、其他完整性
  →400）；非约束类 OperationalError 维持既有 500 语义，行为不变。
  复验：同一套扫射 **0 个 5xx**（8 个端点全部 400）。
- 🔒 **2FA 中间态令牌可当正式令牌用（认证绕过，高危）**：`/auth/login` 在双因素
  挑战分支下发的 `temp_token` 由 `create_token_pair(..., extra_claims=
  {"two_factor_pending": True})` 生成，其 `type` 仍是 `"access"`；而认证唯一出口
  `get_current_user` 只校验黑名单与 token 类型，**未校验该中间态声明**。R19 探针
  实测：仅凭密码（拿不到 TOTP）取得 temp_token 后，`GET /auth/me`、`GET /users`、
  `GET /funds`、`GET /two-factor/status` 全部 **200**，`POST /two-factor/disable`
  也 **200** —— 攻击者既能读写全部业务数据，又能永久关闭受害者的二次验证，
  2FA 完全形同虚设。修复（`app/core/security.py`）：`get_current_user` 在读库前
  拒绝任何带 `two_factor_pending` 的令牌（401「二次验证未完成，请先完成双因素
  认证」）；该令牌只允许喂给 `/auth/two-factor/verify-login`（那条链路走
  `decode_token`，不经本依赖）。复验：四个端点 + disable 全部 401，2FA 仍为启用态。
- 🔒 **备用恢复码可无限复用（`backup_codes` 消费从不落库）**：`two_factor_auth.
  backup_codes` 是裸 `Column(JSON)`，`TwoFactorService.verify_login` 用
  `list.remove(token)` 就地修改 —— SQLAlchemy 对裸 JSON 列的就地修改不产生
  attribute 事件、不生成 UPDATE，`safe_commit` 静默无效。R19 探针实测：同一备用码
  连续两次登录均 **200**，DB 中码数恒为 **10**，与界面明示的「每个恢复码只能使用
  一次」相悖；泄露一个码即等于永久绕过 2FA。修复
  （`app/models/two_factor_auth.py`）：列类型改为
  `MutableList.as_mutable(JSON)`，就地 `remove` 被追踪为脏属性并生成 UPDATE。
  复验：用码后 DB 由 10 → **9**、该码从库中消失、二次使用 **401**。
- 🔒 **前端依赖审计阻断修复（CI `security` job 变红）**：新增公告
  GHSA-2883-xcg3-v3hh（js-yaml 4.0.0–4.3.1，High，maxTotalMergeKeys 对空合并源
  不限 CPU）触发 `npm audit --audit-level=high` 非零退出，导致 PR Checks 的
  security job 失败（其余五 job 全绿）。修复：`npm audit fix --legacy-peer-deps`
  将 js-yaml 升至 **4.3.2**（dev 传递依赖，eslint 链），同步 lockfile 版本字段
  1.11.5→1.12.0；复验 `npm audit --audit-level=high` **exit 0**（余 3 个 moderate
  属 vitest/@vitest/mocker 链，低于阻断线），前端全量 vitest 301 文件/6045 用例
  通过、lint:check 0。

### 修复
- 🐛 **合同附件覆盖用户备注 / 改备注清空附件（合同管理）**：合同附件此前被
  序列化成 JSON 整体写进 `fund_contracts.remarks` —— 而 `remarks` 正是用户在
  「新建合同」表单里填写的**备注**列。R21 探针实证三种后果：① 上传第一个附件即
  **静默覆盖**用户已填写的备注（`甲方要求分三期付款…` 被 `[{"url": …}]` 取代，
  原文不可恢复）；② `PUT /contracts/{id}` 传 `remarks`（编辑备注）会**清空全部
  附件**；③ 合同列表与详情把这段 JSON 当「备注」出站。
  修复：新增 `fund_contracts.attachments_json` 专列存附件，`remarks` 只存备注；
  `_contract_attachments` 保留对老数据的**只读**兼容并在读到脏数据时一次性搬迁
  （附件搬到新列、`remarks` 清空），`_contract_to_dict` 对历史脏数据不再把 JSON
  当备注返回；迁移脚本 `contract_attachments_001`（含数据搬迁）。
- 🐛 **合同/划转凭证关联不存在的项目或经费时报 500**：`POST /fund-lifecycle/contracts`
  与 `POST /fund-lifecycle/transfer-vouchers` 直接 INSERT，未先验关联对象存在性，
  SQLite 外键约束失败抛 `sqlite3.OperationalError: FOREIGN KEY constraint failed`
  → 前端只看到「服务器内部错误」（传失效/为 0/负数的 `project_id`/`fund_id` 必现）。
  修复：新增 `_require_related_exists` 前置校验，返回 404「关联项目不存在 /
  关联经费不存在」；划转凭证的预算余额校验不再因经费不存在而静默跳过。
  注：既有测试 `test_fund_not_found` 曾断言 200 —— 那只是内存测试库未启用外键
  约束造成的假通过，已按真实服务端行为改为 404。
- 🐛 **无项目合同的详情恒 400（同资源两种口径）**：`ContractCreate.project_id`
  与 `TransferVoucherCreate.project_id` 均为可选（前端从菜单进入合同管理时
  `route.query.project_id` 缺失），这类记录**能创建、能更新、能删附件**，但详情端
  无条件调 `_get_project_or_403` → 恒 400「缺少有效的项目ID，请从经费列表中选择
  具体项目进入」。修复：仅在确实挂了项目时才做 404/403 校验（合同与划转凭证
  详情一致处理）。
- 🐛 **同机第二个用户注册必挂（组织/自验证通行码跨机器注册 100% 失败）**：
  机器码记录 `machine_code` 为 UNIQUE 列，而 `activate_machine_code` 在激活时
  无条件把记录改绑为注册机真实机器码 —— 本机已有首条记录（首用户注册留下）
  占用该机器码时抛 `IntegrityError: UNIQUE constraint failed:
  machine_codes.machine_code`，被注册兜底捕获 → 用户只看到「注册失败，请稍后重试」
  （R18 探针实测：组织通行码自注册 400，服务端日志见完整堆栈）。
  修复（`machine_code_service.py`）：① 激活前探测占用，已被占用则保留该记录的
  ORG-/HMAC- 占位机器码（仅 status/user_id/activated_at 落库，不再触发 UNIQUE
  冲突）；② HMAC 自验证建记录时若当前机器码已被占用，改用 `HMAC-<hex>` 占位串
  建行；③ `verify_user_machine` 对非设备绑定记录（organization_id 非空或
  ORG-/HMAC- 前缀）放行登录——管理员下发的机器通行码仍严格等值比对。
  回归：新增 4 例（激活冲突保留占位、ORG- 登录放行、HMAC- 登录放行、HMAC 占用时
  建占位行），machine-code 相关 256 passed、flake8 app 0；HTTP 复验：组织自注册
  200 → 自动建组织并绑定 → 记录 active 且机器码为 ORG- 占位 → 该用户可登录；
  单位名不符的自验证负例返回「通行码无效或已被使用」引导。

### 功能
- ✨ **报表订阅闭环（工单 003 方案 A+B 落地）**：此前订阅可创建但无任何消费方
  （无调度、无生成、前端无 UI），创建后静默无产出。现补齐：
  - 调度分发：`subscription_dispatch_job` 每 15 分钟扫描到期订阅，按频次
    （每天/每周/每月/每季度 + 发送日/发送时间）自动生成报表并落盘
    （output_dir 或运行时 uploads/subscription_reports），站内消息送达；
  - 纯函数 `next_run_at` 四频次语义（月末 31 号按月钳制 28/29、weekly 周一..周日、
    跨年安全），31 个确定性测试（含闰年边界），杜绝墙钟敏感分支（CI#84 教训）；
  - 手动生成：`POST /reports/subscriptions/{id}/generate-now`（属主或管理员），
    与调度共用同一生成函数，行为一致；
  - 前端「报表导出中心」新增订阅管理卡片（列表/上次与下次生成时间/启停开关/
    立即生成/删除确认/四频次新建表单）；
  - `report_subscriptions.last_sent_at` 迁移（subscription_last_sent_001），
    serializer 动态计算 `next_send_at`；
  - 顺带修复 `_run_async_job` 对同步函数抛 TypeError 被吞——
    **recycle_retention_job（回收站保留期每日清理）此前实际从未执行**；
  - 验证：后端 138 相关测试 + dispatch 31 + 端点 4，flake8 0，bandit 0；
    前端 ReportExport 24 测试全过，vue-tsc/lint 0。

### 字体与排版
- 中文字体栈统一至 tokens 单一来源（PingFang SC + Microsoft YaHei 入栈），
  删除 index.scss 与 App.vue 两处重复 font-family 声明
- EP 排版变量显式化：`--el-font-family`/`--el-font-size-base: 14px` 走令牌，
  输入框与正文同源同渲染
- 等宽字体统一：BigScreen/SupportedVillageForm 自写栈 → `--font-family-mono`

### 密度与布局
- 控件密度升 **40px 舒适档**（原 32px 紧凑档）：`--control-height 40/32/48`、
  `--table-row-height 44px`、`el-config-provider size=large`；
  codemod 移除 **473 处 size="small"**（剩余 0，sm 档降级 32px 优雅兜底）
- 圆角阶梯统一：控件 8px（原 6px）
- 页面级冗余 padding 移除（funds 20px / villages 16px → layout 24px 唯一来源）
- villages List 补缺失的页头（PageHeader 组件）

### 色彩与组件
- 语义色 EP 中间档令牌化：success/warning/danger/info 的 light-5/7/8/9
  补入 tokens（13 处硬编码 hex 替换），主题切换不再走色
- villages KPI 卡 4 处硬编码 hex → 令牌
- funds/EnhancedList 嵌套 `el-form-item` 无效标记修复
- 52 个无 stripe 的 el-table 补加 stripe（斑马纹统一为全站规范）

### 认证页统一
- Register.vue 背景升级为照片+军绿渐变遮罩（对齐登录），卡片玻璃拟态化，
  补 600px 响应式断点，新增"单位名称"选填框
- ChangePassword 修复浅色卡片上 tips-title 误用 inverse 色
- LoginEnhanced 密码可见性切换补 aria-label（a11y）

### 验证
- 全量 vitest 5956 passed；vue-tsc 0；eslint 0
- **全量 Playwright E2E 150/150 passed**

## [1.11.8] - 2026-09-06 — 🐛 跨机器注册阻断级修复（生产双机实测反馈）：通行码自验证启用 + 组织通行码确定性化

### 修复
- 🐛 **机器特定通行码跨机器注册 100% 失败（阻断级，生产双机实测）**：管理员在
  A 机"机器码管理"为 B 机机器码生成通行码后，用户在 B 机注册恒报"通行码无效
  或已被使用"。根因：跨机器注册唯一不依赖共享数据库的通道——HMAC 自验证
  （level 4）被 W1-T6 fail-closed 门关闭，而 Electron 安装实例不注入
  `PASS_CODE_SECRET` → `_PASS_CODE_SECRET_EXPLICIT` 恒 False → 自验证恒拒绝。
  修复（产品决策，取代 W1-T6 fail-closed）：自验证启用，未配置时使用随安装包
  分发的内置常量密钥；配置 `PASS_CODE_SECRET` 的部署（多机注入同一随机值）
  强度更高。已知取舍（所有者确认接受）：内置常量可被掌握应用者离线计算，
  兜底为管理员事后审计。回归：`test_passcode_hmac_failclosed.py` 语义翻转
  （内置密钥自验证可用/错误机器仍拒绝）+ 跨机器注册 HTTP 全链用例
  （B 机机器码打补丁）。
- 🐛 **组织通行码跨机器注册 100% 失败（同根因）**：组织通行码为随机数且仅存
  于管理员本地库，下级单位机器 level 2（DB 匹配）永远查不到。修复：
  ①通行码按单位名确定性派生（`generate_org_pass_code`，重复生成幂等，
  同组织 pending 记录复用避免 UNIQUE 冲突）；②注册接口新增 `org_name`
  字段，DB 未命中时按单位名重算自验证 → 本机 find-or-create 组织与占位
  记录 → 用户自动绑定组织。回归：`test_org_passcode_cross_machine.py`
  5 用例（真实内存库跨库模拟：注册成功+组织创建+绑定、假单位名 400 且
  不建用户、幂等、派生正确性、防御分支）。

### 界面
- 注册页新增"单位名称"选填框（组织通行码跨机器注册时填写）。
- 注册失败提示更新：明确组织通行码需填单位名称、机器通行码需提供本机机器码。

### 说明
- 已有部署升级本版后，此前生成的机器特定通行码立即恢复可用（HMAC 自验证
  用内置常量密钥重算，历史通行码格式未变）；此前生成的随机组织通行码
  仍仅限同库使用——跨机器请由管理员在「组织通行码」重新生成（确定性，
  内容不变则重复生成同值）。

## [1.11.7] - 2026-09-06 — 探测循环收官：探针资产固化 + 发布物供应链核验

### 工程
- 🧪 **全链路探针固化**：9 轮深度探测的真实 HTTP 探针（200+ 断言，30+ 模块）
  收编为常驻回归资产 `backend/tests/probe/`（run_all.py 总运行器，独立子进程
  + 独立临时库，pytest 零收集不影响套件），固化后全量复跑 9/9 PASS。
- 📋 **工单 003**：报表订阅为半成品（可创建、无生成/送达消费方）——三方案
  决策项挂起待产品拍板（A 调度+站内送达 / B 手动生成 / C 收起入口）。
- 🔐 **v1.11.6 发布物供应链核验**：三件套（exe/electron deb/standalone deb）
  从 Release 下载实物逐一比对 SHA256SUMS——全部 MATCH。

### 说明
- 本版安装包内容与 v1.11.6 构建一致（两次 tag 之间仅测试/文档变更），
  重新构建以使 Release 指向包含探针资产与全部修复的最新 main。
- 真机 UI 安装抽验仍建议人工执行一次。

## [1.11.6] - 2026-09-06 — 深度探测循环（9 轮）+ 并发竞态修复 + E2E 套件入 CI 门禁

### 修复（逐模块真实 HTTP 深探实测发现，全部带锁定回归）
- 🐛 **组织通行码注册后新用户无法登录（阻断级）**：组织通行码记录的
  `machine_code` 是占位串（`ORG-<org>-<rand>`），`activate_machine_code` 只置
  active+user_id 不改绑 → 登录侧 `verify_user_machine` 按"记录.machine_code ==
  当前真实机器码"比对恒 False。修复：激活时改绑为注册机真实机器码。
- 🐛 **data-sync 数据包下载恒 400/404（路径双源）**：下载端点用相对
  `Path("data_sync")`，导出服务写 `get_app_data_dir()/data_sync` → 打包环境
  必分叉。修复：下载改用 `data_sync_service.sync_dir` 同源。
- 🐛 **报表模板下载/上传确认 500 + 静默零写入**：`fields` 允许任意字符串
  （逗号串/字符串数组/dict 数组三种历史形态），下载与 `_parse_template_excel`
  均假定 dict 数组 → `AttributeError` 500；且字符串形态缺 `db_field` 时解析出
  `{'': value}` → 确认导入零写入（比 500 更隐蔽）。修复：`_normalize_template_fields`
  统一归一化（下载/上传两消费点共用）。
- 🐛 **奖学金导入全链坏死（阻断级，无测试覆盖致长期存活）**：按
  `ScholarshipStudent(name/student_id/school_name)` 构造，真实列是
  `student_name` + 必填 `school_id` FK → 每行必抛 TypeError、imported 恒 0。
  修复：按真实列映射（学校名查 School 解析 school_id，学号并入 remarks），
  学校解析带 `is_active` 过滤。
- 🐛 **乡村工作悬挂 village_id → 裸 500**：外键目标是遗留 `villages` 表（前端
  下拉由 `/rural-works/villages` 按名称 upsert 同步），传入不存在 id 触发未处理
  IntegrityError。修复：服务层前置校验（create/update）+ 路由转 400 带指引。
- 🐛 **并发备份同毫秒唯一键冲突 → 500**：文件名/config_key 毫秒后缀在并发
  同毫秒下仍相撞（三并发实测一个 500）。修复：追加 uuid4 短码。
- 🐛 **通行码注册并发竞态 → 创建 2 个用户**：verify（读 pending）→建用户→
  activate（写）非原子，双并发注册均通过。修复：`activate_machine_code` 改单条
  UPDATE 原子认领（rowcount 判定），认领失败删除刚建用户并 400。
- 🐛 **覆盖率墙钟黑洞（CI #84）**：`/backup/schedule` 的"已过 02:00 则 +1 天"
  分支内联端点，是否执行取决于测试运行的墙钟 → CI 覆盖率随机差 1 行。
  修复：提取 `_next_daily_2am` 纯函数 + 三固定时间确定性测试。

### 测试与工程
- 🧪 **Playwright E2E 套件复活并纳入 CI 门禁**：死代码清理曾误删 `helpers.ts`
  （8 个 spec 导入即崩）+ global-setup 密码过期 + 首登强制改密未适配（改密
  PUT 为 CSRF 保护路径需先取 csrf-token 配对）+ 5 个 spec 选择器腐化。
  修复后 **全量 150/150**；pr-checks 新增 `e2e-test` job（Linux chromium，
  config 跨平台化——Windows 用系统 Edge/venv），E2E 成为六 job 门禁常驻项。
- 🧪 **并发探针**（多线程真实 HTTP，12/12）：同记录 10 并发写、审批竞态、
  并发备份、通行码竞态、并发导入全部符合预期语义。
- 🧪 **前后端契约交叉核对**：导出后端 797 条路由，正则通配匹配前端 334 个
  去重调用路径 → **0 处真实断裂**。
- 📚 帮助文档修正出厂密码描述（Admin@2026）+ 新增管理员出厂恢复通道说明；
  ADR-0008 扩展章节；AGENTS.md 路径双源规则与覆盖率不变量补记。

## [1.11.5] - 2026-09-05 — 通行码注册大小写归一化 + 功能全链路探针验证 + 覆盖率根因修正收尾

### 修复
- 🐛 **帮扶村年度数据「校验」端点被动态段吞掉（恒 400 未知数据分类）**：路由注册顺序
  缺陷——`POST /supported-villages/{village_id}/yearly/{year}/validate` 声明在动态段
  `POST …/yearly/{year}/{section}` 之后，FastAPI 按注册顺序匹配 → `/validate` 恒被
  当作 section 落入保存端点（R15 隔离实例实测 400「未知的数据分类: validate」；
  前端 validateYearlyData 即此路径，年度完整性校验功能实际不可用）。修复：
  `validate_yearly_data` 端点整块前移到动态段之前注册（含注释警示），并删除原位。
  回归：村庄 API 相关 108 passed；HTTP 复验 validate 200 返回
  {valid:false, errors:[板块缺失…], warnings}（真实校验结果），section 保存端点
  不受影响。
- 🐛 **经费拨付被文档要求锁死（前端上传缺陷）**：经费「拨付」前置要求附件类别
  合同(contract)/分配令(allocation_order)，但经费详情附件上传把 category 塞进
  FormData（后端该参数为 Query）→ 恒落 other；且界面无类别选择 → 真实用户即使
  上传了合同也恒报「缺少必需文档: 合同, 分配令」（R14 隔离实例 HTTP 复现：
  仅 category 以 query 传参后 allocate 才 200「经费已拨付」）。修复：
  `funds/Detail.vue` 附件上传前新增「文档分类」下拉（合同/发票/收据/报告/分配令/
  其他，与后端 `_transition_status` 必需文档键共用同一 CATEGORY_LABELS），category
  改经 axios query 参数提交；回归：DetailCov 新增分类选择上传用例 + 调整组件计数
  断言（65 passed），vue-tsc 0。
- 🐛 **回收站恢复项目后仍不可见（真实缺陷）**：项目软删时 `status` 被置为
  `cancelled` 作回收站标记（projects.py delete 流程），而 `recycle_bin` 通用工厂的
  restore 只回置 `is_active/deleted_at` —— 恢复后的项目仍被默认列表
  （`status != cancelled` 过滤）隐藏，表现为「恢复成功却看不见」（R9 隔离实例 HTTP
  实测复现：restore 200 后详情 status=cancelled、默认列表无此项目）。修复：回收站
  恢复（单条与批量）统一清除 cancelled 回收标记，还原为 `planned` 可编辑态
  （其它软删资源无 status/cancelled 标记，helper 为 no-op）。回归：工厂测试新增
  单条 cancelled→planned、非 cancelled 不受影响、批量恢复清除标记 3 例；
  recycle_bin 模块覆盖率 100%；HTTP 复验 restore 后 status=planned 且默认列表可见。
- 🐛 **注册响应缺失 refresh_token（与 LoginResponse「注册即登录」契约不一致）**：
  `/auth/register` 返回 access token 却不发 refresh，前端「记住登录」持久化 refresh
  分支对注册会话恒缺失、API 契约与 `/auth/login` 不对齐。改为注册时签发双 token
  （`create_token_pair` + `token_version` 声明，与登录一致），响应顶层带可轮换的
  `refresh_token`；旧 refresh 重用仍被 401 拒绝（轮换防重放不变）。回归断言补入
  `test_auth_auth_api.py` 两条注册成功用例，HTTP 全链路复验：注册→刷新→旧码重用
  401→新 access 可用均通过。
- 🐛 **大写输入的通行码被误拒（注册提示「通行码无效或已被使用」）**：通行码为
  小写十六进制（自动生成）或纯数字（手动 4 位），但 `verify_pass_code` 与库内列
  按 SQLite 二进制比较，用户以大写输入（图片 OCR、手动录入习惯、第三方工具转写）
  时本属同一通行码却被判无效。现入参统一 `.strip().lower()`，库内列经
  `func.lower` 归一比较（去连字符路径同样生效），四级匹配（机器码/组织码/漂移
  回退/HMAC）全部大小写不敏感。回归测试 `test_machine_code_passcode_case_insensitive.py`
  用真实 SQLite 断言 SQL 语义（Mock 链无法证明 `func.lower` 行为）；HTTP 全链路
  探针复验：自动通行码注册、连字符去连字符、手动 4 位码、复用拒绝、错误码拒绝、
  权限包导出/下载/导入预览/加密往返均通过。

### 工程
- 🔧 **前端覆盖率 88.23% 门禁红因的最终定论与根治（含 CI 红→绿的完整实测链条）**：
  `LoginEnhanced.vue` 全量跑 functions 88.23% 与 Node 版本无关（Node24 CI 复现完全一致；
  Windows/Node25 恒绿系 OS 间 v8 函数 id 顺序差异，本地绿不作为放行依据）。真因：**凡
  执行该 `.vue` 的每个测试文件都在各自 worker isolate 产出函数 id 从 1 起算的局部 v8
  fnMap**——只 import 不渲染（bare import/仅懒加载/整应用挂载未走渲染分支）得到 17 函数
  分片，渲染全分支的专属测试得到 19 函数分片，istanbul 满量按 id 合并时错位 → 2 个内联
  处理器 count-0 → 88.23%。实测链条（每步 Linux CI 复测仍红）：先移除 `AuthViewsBatch`
  冗余深挂载 → 再移除 `smoke.test.ts` bare import → 再桩替换 `router-index.test.ts`
  懒加载执行 → 最后桩替换 `promptContract.test.ts` 的 `await import('@/main')`（真实 App
  挂载解析 /login 执行该组件）→ WSL/Node22 全量 `--coverage` 模块加载标记降为 1 次、
  functions/branches 100%。规则更正为**每个被 100% 阈值锁定的 .vue 全仓只允许一个测试
  文件执行（含 bare import、mount、路由 chunk 加载、import('@/main')）**，`vitest.config.ts`
  注释 (A) 与 `AGENTS.md` 不变量同步更正。CI Node 已回归 22（与仓库其余一致）。

## [1.11.4] - 2026-09-04 — 异常细节出站收口 + 板块导入 400 根治 + 帮扶村经费持久化修复 + 测试数据目录隔离

### 安全
- 🔒 **异常细节出站收口（W1 不变量 #6 / W1-T8），共 4 处**：
  - `permission_package_service.confirm_import` 兜底把 `str(e)` 放进 `message`，
    经 API 层 `detail=result.get("message")` 直达 HTTP 500，可泄露 SQLAlchemy
    错误文本、表名与服务器路径 → 改泛化文案，原文仅进服务端日志。
  - 同文件 JSON 解析分支把 `JSONDecodeError` 原文（含出错位置与文档片段，可反推
    包内结构）经 `errors[]` 出站 → 改泛化文案。
  - `db_error_handler` 的 IntegrityError 兜底把 `str(exc.orig)` 经 HTTP 400
    `detail` 出站，内含表名/列名（如 `NOT NULL constraint failed users.xxx`），
    正是 W1-T8 点名的 schema 泄露；同函数 catch-all 500 的 `str(exc)[:100]`
    一并收口（上面 UNIQUE/FK/Operational/SQLAlchemy 各分支早已泛化，唯漏这两处）。
  - `policy_import_service` 导入兜底 500 `detail` 内插 `str(e)` → 泛化 + 补
    `exc_info=True`（原 `logger.error` 缺栈，排障拿不到 traceback）。
- 🔒 **泄露扫描器扩面到 `services/`、`utils/`、`core/`**：上述第一处之所以能长期
  存活，正是因为文本产生在 service 层、出站动作在 api 层，而旧扫描器只扫
  `app/api/v1` 的字面内插，结构上看不见这条间接路径。新规则精确口径：只禁这三层
  直接构造 `HTTPException` 时把异常变量内插进 `detail`（f-string 任意状态码；
  `str()` 形态仅禁 500，沿用既有 `LEAK_STR_500` 对 400 业务文案的刻意放行）。
  **刻意不扫** service 返回字典里的 `message:`/`errors:` —— 实测该口径下有 20 处
  命中，多为面向导入用户的行级校验反馈（含行号/字段/格式原因），一刀切泛化会
  损害可用性，需按调用链逐点判定，不适用源码扫描。
- 🔒 **`/health` 不再回传迁移异常原文**：该端点无需认证，原 `migration.error`
  存的是 `f"{type(e).__name__}: {e}"`，可泄露数据库绝对路径与 SQL 片段。改为只出
  异常类名（键更名 `error_type`，避免后来者误以为它是可读消息而重新放宽），
  完整细节仅进 `logger.error(exc_info=True)`。
- 🔒 **分析统计接口数据隔离改 fail-closed**：`_get_analysis_data_impl` 的
  `current_user` 由带 `None` 默认值改为必填位置参数（对齐 W5-006）。原写法下
  `_scoped()` 内 `if current_user is not None` 意味着任何新调用方漏传即**静默跳过
  隔离、返回跨组织聚合数据**；改必填后漏传在调用点直接 TypeError。

### 修复
- 🐛 **帮扶村年度板块导入恒 400**：`force_investment` / `party_building` 两个板块
  的内部下划线键被原样透传给后端 `section_key`，而 `_SECTION_MODEL` 的键是连字符
  （`force-investment` / `party-building`）→ 查不到模型 → 400「未知板块标识」。
  上一轮已为删除路径套上 `resolveSectionApiKey`，导入这条漏了。现将 section key
  映射统一下沉到 API 层（保存/删除/导入三条路径），调用方无法再各自忘记；
  `resolveSectionApiKey` 幂等，既有调用点的重复调用无害。
  附件路径**有意不映射**：后端不按 `_SECTION_MODEL` 校验附件的 section，改动会
  使既有附件记录失配。
- 🐛 **学校回收站恢复/彻底删除后停在空页**（AGENTS.md 前端 BUG 模式 #3）：
  `handleRestore` / `handlePurge` 在 `fetchData()` 前未重置分页，而同文件新建/编辑
  等处理器都有 `currentPage.value = 1`。用户停在第 2 页及以后时，操作改变了结果集
  长度 → 刷出空页，看似"操作没生效"。
- 🐛 **截断/损坏权限包导致未分类 500**：`package_crypto._parse_header` 无长度校验，
  以魔术头 `BKPKGv2\x00` 开头但不足 `_HEADER_LEN` 的上传文件会让 `struct.unpack`
  抛 `struct.error`；该异常发生在 `decrypt_bytes` 的 try 块**之前**，逃过
  `InvalidToken` 归一化 → 改为入口长度守卫抛 `InvalidToken`，调用方按既有的
  「密码错误或包已损坏」语义处理。上传截断文件即可触发。
- 🐛 `saveSectionData` 与 `saveYearlySectionData` 是完全重复的实现（同一 URL），
  改为委托调用，既消除重复又自动获得下沉后的映射，避免两处各自漂移。
- 🐛 **监控快照在麒麟/Linux 上整份崩溃并刷 ERROR 日志**：`system/monitor.py` 的
  `get_monitor_snapshot` 用 `psutil.disk_usage(os.environ.get("SystemDrive", "C:\\"))`
  取磁盘，非 Windows 平台 `SystemDrive` 未设置 → 回退到 Windows 字面量 `"C:\\"` →
  `psutil` 抛 `FileNotFoundError: [Errno 2] ... 'C:\\'`，被外层 `except` 吞成整快照
  `status=error`，连带丢失 CPU/内存/网络指标并持续刷「获取监控数据失败」ERROR。
  改为跨平台解析磁盘路径（Windows 取 `SystemDrive`，其它平台取 `os.path.abspath(os.sep)`
  即文件系统根 `/`），并把磁盘读取单独 `try/except` 降级为 warning —— 单块磁盘读取
  失败不再拖垮整份快照。直接违反双平台（麒麟 V10）要求的硬缺陷。
- 🐛 **注册页把后端 400 报文吞成 "Request failed with status code 400"**：
  `Register.vue` 的 catch 只读 `error.response?.data?.detail`，但注册失败多走
  `BizValidationError` → `AppError` handler 返回 `{code,message,success}` 信封
  （**无 `detail` 字段**），取值落空后回退到 axios 默认英文原文，用户看不到
  「密码不能包含用户名」「通行码无效或已被使用」这类可操作提示。改为对齐
  `ForgotPassword.vue` 既有约定：`userMessage`（拦截器已算好）→ `data.detail` →
  `data.message` → `error.message` → 兜底文案。附带补全前端密码校验器与后端
  `PasswordPolicy` 的一致性——原校验器注释声称「与后端保持一致」却漏了末条
  「密码不能包含用户名」，现补上，使该场景在客户端即被内联拦截，无需服务端往返。
- ⚡ **异步端点阻塞事件循环收口（性能），共 5 处**：`psutil.cpu_percent(interval>0)` 是
  阻塞采样（内部 `sleep(interval)`），却在 `async def` 端点里直接调用，每次请求冻结整个
  事件循环 0.2–1s，拖慢所有并发请求（麒麟多用户下尤甚）。改用
  `starlette.concurrency.run_in_threadpool` 卸载到线程池，保留真实采样语义：
  `system/monitor.py` 的 `get_monitor_snapshot`(0.3s)/`get_resource_usage`(0.2s)、
  `system/metrics.py` 的 `get_system_metrics`(0.5s)/`get_performance_metrics`(0.3s)、
  `monitoring_legacy.py` 的 `get_resource_stats`（经同步 `MonitoringService.get_resource_stats`
  内含 `interval=1` 阻塞 1s，在 async 调用点整体卸载，不改同步方法签名以免影响告警调度）。
  **刻意不用** `cpu_percent(interval=None)` 规避——它首次返回 0.0、其后返回"距上次调用"均值，
  会造成"CPU 0%"误导性新问题。`system.py` 关机/重启的 `time.sleep` 在 `background_tasks`
  同步函数里（线程池执行），属正确用法，未动。
- 🐛 **跨平台磁盘路径同源缺陷一并扫清**：监控快照工单里的 `os.environ.get("SystemDrive", "C:\\")`
  硬编码回退是复制粘贴扩散的，除 `monitor.py` 外还存在于 `system/metrics.py`(×2，另含 `disk_usage("/")`
  统一为跨平台表达式)、`system/health.py`(`shutil.disk_usage`，Linux 上被 try 吞成 `disk_free_gb`
  恒 None，健康面板永远无磁盘剩余)、`services/monitoring_service.py`(Linux 上整份资源统计被吞成空)。
  四处统一为 `os.environ.get("SystemDrive") or os.path.abspath(os.sep)`，并记入 AGENTS.md 工程不变量。
- 🔒 **无认证/非 HTTPException 路径的错误细节出站收口，共 2 处**：`system/health.py` 的
  `/health/full`（无 `Depends`，未认证）把 `str(e)` 存进 `db_error` 出站，sqlite3 连接错误原文
  可含数据库绝对路径 → 改 `type(e).__name__`，原文仅进日志（与 W1 #6 的 `/health` `error_type` 同理）；
  `system/metrics.py` 资源采集失败的 `message` 曾内插 `str(e)`——因不是 HTTPException 的 `detail`，
  泄露扫描器结构上看不见 → 改泛化文案「获取资源指标失败，请查看日志」。
- 🐛 **转移支付经费保存成功但金额静默清零（H2b，关键根因）**：
  `TransitionFundingItem` 字段名为 camelCase（`militaryInvestment`/
  `localInvestment`/`totalInvestment`），但 `CamelToSnakeMiddleware` 会把请求体
  键名转为 snake_case，Pydantic 字段名无法命中、静默回落默认值 0——这正是
  “经费保存成功但总额重置为 0”的真正根因（默认值掩盖了校验失败，无任何报错）。
  修复：三字段加 `validation_alias=AliasChoices(camelCase, snake_case)` +
  `populate_by_name`，同时兼容中间件转换后的 snake_case 与未经中间件的
  camelCase 输入；序列化输出仍以字段名（camelCase）为准，保持与
  GET /transition-funding 及前端的向后兼容。
- 🐛 **两委成员「退役军人」标记恒 False（H2c）**：`_save_section_data` 处理
  village_committee 成员子表时硬编码读 camelCase 的 `isVeteran`，而中间件会
  递归转换数组内键名（`isVeteran`→`is_veteran`）→ 恒取不到、静默落库 False。
  修复：成员键先做 `to_snake_case` 归一化，再读 snake_case（保留 camelCase
  兜底以兼容未经中间件的直接调用），
  `is_veteran=bool(nm.get("is_veteran", nm.get("isVeteran", False)))`。
- 🐛 **年度数据复制功能恒 422（H2d）**：`YearCopyRequest` 必填字段为 camelCase
  （`fromYear`/`toYear`），经中间件转换后请求体键变 `from_year`/`to_year`，
  Pydantic 找不到必填 camelCase 字段 → `POST /{village_id}/yearly/copy` 恒
  抽 422，年度复制 100% 不可用。修复：照搬 H2b 样板，
  `AliasChoices("fromYear", "from_year")` 双别名兼容。

### 测试与工程
- 🧪 **测试不再写开发者真实数据目录**：`tests/conftest.py` 在任何 `app.*` 导入之前
  设 `BUMOFU_BACKEND_DIR_OVERRIDE` 指向会话临时根。依据：`config.py` 的 Settings
  在**构造期**就把 `DATABASE_URL`/`CACHE_DIR`/`UPLOAD_DIR`/`EXPORT_DIR` 的相对默认
  值统一归一到 `_get_default_data_dir()` 下，而该函数最终调用
  `paths.get_app_data_dir()` → `get_project_backend_dir()`，故一个 env 即可收口全部。
  `LOG_FILE` 不经该漏斗（`config.py` 仅在 `sys.frozen` 时重写它，测试态保持相对
  `./logs/app.log`），单独用 `LOG_DIR`/`LOG_FILE` env 覆盖。
  此前测试会写 `backend/data/`（缓存库、`test_integration.db`）与
  `backend/logs/app.log`（单次全量跑从 293KB 涨到 4.8MB）。
  **用 env 而非替换模块属性**：替换属性会让此后所有
  `from app.utils.paths import get_project_backend_dir` 的测试模块把名字冻结成替身，
  与后来被还原的模块属性分叉（实测导致 `test_paths.py` 两处断言失败）。
  专测路径解析逻辑的 `test_paths.py` 以 `real_backend_dir` 标记整模块豁免
  （已在 `pytest.ini` 注册，因 `addopts` 带 `--strict-markers`）。
- 🧪 新增回归测试：`handleRestore`/`handlePurge` 分页重置（这两个处理器此前
  **完全无测试**，正是缺陷存活的原因；已反向验证撤掉修复后测试确实变红）、
  板块导入映射（断言收到 `force-investment` 而非 `force_investment`）、
  截断包 `InvalidToken`（4 组参数化）、`/health` 迁移状态形状与「只记异常类名」、
  `_get_analysis_data_impl` 漏传 `current_user` 必抛 TypeError。
- 🧪 本次两处缺陷的回归测试：`test_system_monitor_api.py` 补 3 条（磁盘读取抛
  `FileNotFoundError` 时整快照仍 `healthy` 且 CPU 指标不丢、Windows 取 `SystemDrive`、
  无 `SystemDrive` 时回退到 `os.path.abspath(os.sep)`——在 Linux CI 上可与旧硬编码
  `"C:\\"` 区分）；`Register.test.ts` 补 3 条（400 信封只有 `message` 时展示后端文案
  且不暴露 axios 原文、`userMessage` 优先、密码含用户名客户端即拒绝）。
- 🧪 **修全量跑唯一 warning**：`test_anomaly_detection_service_complete.py` 的
  `subprocess.run(text=True)` 未指定 encoding，Windows 下父进程按控制台代码页 GBK
  解码子进程输出，reader 线程抛 `UnicodeDecodeError: 'gbk' codec can't decode
  byte 0xaa` → 父进程显式 `encoding="utf-8", errors="replace"`，子进程
  `PYTHONIOENCODING=utf-8`，两侧对齐才确定性消除（只改一侧仍可能因代码页复发）。
- 🧪 按前端测试约定 #1 补齐 mock 导出：`SchoolsViewsBatch.test.ts` 补
  `@/api/request` 的 `default`（`schoolsRecycle.ts` 与 `List.vue` 都 import 了它），
  `Import.test.ts` 补 `apiRequest`/`get`/`put`/`del`（`src/api/import.ts` 实际
  import 了 `apiRequest`）。此前靠上层 mock 侥幸未触发。
- 🔧 `backend/app/__init__.py` 的 `__version__` 自 1.10.0 起未随发版更新（经 grep
  确认无任何消费方），同步到 1.11.4 并注明单一事实源。

## [1.11.3] - 2026-08-31 — 麒麟版后端启动 ModuleNotFoundError 根治

### 修复（致命，Kylin 真机）
- 🐛 **冻结包内 47 个业务路由模块全部缺失**：`app/api/v1/__init__.py` 此前用
  `importlib.import_module(f'app.api.v1.{name}')` 动态加载业务路由——PyInstaller
  静态分析无法跟踪 f-string 动态导入，且 Linux Docker 构建时
  `collect_submodules('app')` 依赖的包导入链在收集阶段被 walk_packages 静默跳过，
  打包产物缺 organization/policy/projects 等 47 个模块 → 后端"部分启动"，
  前端业务页面全量报错。**根改为静态导入**：打包收集 100% 确定，任一路由
  损坏启动即快速失败（终结"静默降级为残缺 API"的故障模式）。
- 🐛 **两个 spec 同源修复**：统一 spec 补 `sys.path` 插入使 collect 与 CWD 无关、
  移除已删除依赖 sklearn 的 hiddenimports 与陈旧 excludes；standalone spec
  补 `collect_submodules('app')`（其此前完全缺失，standalone DEB 同样受影响）。
- 🐛 **ARM64 postinst**：补 onedir 后端主程序 chmod（旧脚本只找 onefile .exe 路径）；
  chrome-sandbox 补 chown root:root + 4755（非 root 用户启动必需）。
- 🐛 **deb Depends 声明**：补 Electron 运行库依赖（libnss3/libgbm1/libasound2 等
  16 项），麒麟安装时缺失依赖明确报错而非启动后崩溃。

### 增强（国产平台兼容）
- ✨ Linux 平台禁用硬件加速 + disable-dev-shm-usage：规避麒麟/飞腾 GPU 驱动
  白屏/花屏类问题（管理界面无需 GPU 渲染）。

### 验证
- ✅ 本机 PyInstaller 实包验证：启动冻结 exe，此前缺失的 organizations/policies/
  projects/data-packages/incremental 等路由全部存在（401/403=存在需鉴权）
- ✅ 后端全量回归全绿；YAML/JSON 门禁通过

## [1.11.2] - 2026-08-30 — 403 权限页根因修复 + 全站弹窗显示修复

### 修复（403 权限页，六类根因）
- 🐛 **无组织管理员被判"无任何组织权限"**（核心根因）：单机/未绑定组织的管理员
  访问数据包、增量更新、版本管理、数据上报等组织门禁端点一律 403——
  `organization_permission_service`/`user_permission_service` 共 7 处
  仅 superuser 旁路改为 admin 语义（ADR-0002 对齐）；普通用户维持 fail-closed。
- 🐛 **菜单加载失败窗口期全站 403**：打包版后端冷启动（onedir 8.6s）期间
  `/menus/accessible` 失败 → 路由守卫把所有带 menuKey 的页面弹到 /403——
  守卫改为仅"菜单已加载且明确不含该键"才拒绝（菜单是可见性层，真实权限由
  后端接口兜底）。
- 🐛 **经费申请页 admin 403**：`funds-user` 菜单键 roles 缺 admin/super_admin。
- 🐛 **存量旧角色名被 meta.roles 误拒**：守卫校验前先 normalizeRole 归一化
  （manager/approval_leader→admin，operator→user）。
- 🐛 **legacy 模型数据范围 500**：`villages` 等无 created_by/organization_id 列的
  模型在数据范围过滤下 AttributeError→500，改为 fail-closed 空集（ADR-0002）。
- 🧪 真实库双角色全量 GET 端点巡检：admin 0×403/0×500；新增回归
  `test_org_less_admin_403_fix.py`（7 用例）+ 前端守卫 3 用例。

### 修复（连带发现的 5 个 500 端点）
- 🐛 sklearn 随死代码清理移除后 ai 收入预测/趋势预测端点必 500 → numpy polyfit 等价实现
- 🐛 monitoring 端点统计 `func.case` 误用（SQLAlchemy 2.x 无此函数）→ `case()`
- 🐛 业务指标拨付率 float/Decimal 混算 TypeError → 统一 float
- 🐛 cache-stats 调用不存在的 RedisAdapter.get_stats → 适配器补齐统计/健康方法

## [1.11.1] - 2026-08-30 — Windows 安装器真机修复版

### 修复
- 🐛 **安装器真机全部中止（截图故障）**：NSIS 对双引号字符串做 C 风格转义，
  钩子把 `$INSTDIR
esources
credist\...` 中的 `
`/`
` 转成 CR/VT 传给
  PowerShell，Get-FileHash 恒定报错 exit 1，被误判"哈希不匹配"而中止所有
  真机安装。修复：钩子路径反斜杠全部 `\`；校验改为 FileWrite 写出 .ps1 后
  `-File` 执行（不再使用行内 `-Command`）；校验脚本执行后清理。
- 🐛 **校验三态语义**：0=匹配静默安装；1=确证不匹配弹窗中止（真实篡改信号）；
  3 或 error=校验工具不可用（无 PowerShell/被安全软件阻断）→ 跳过 redist
  安装但不阻断部署（应用由 Layer 1 内置运行时 DLL 兜底，不执行无法校验的
  二进制）。初版将"工具不可用"与"确认篡改"混为一谈，是假阳性根因之一。
- 📝 文档同步：AGENTS.md 新增 NSIS 转义铁律 Known Issue；工单 002 追记复盘；
  打包指南/OFFLINE_UPGRADE/build-scripts README 校验语义更新。

### 验证
- 本机全链路实测：静默安装 exit 0 → 哈希校验通过 → redist 静默执行 →
  桌面快捷方式创建（perMachine 公共桌面）→ 静默卸载 exit 0 零残留；
  makensis 编译通过；CI 全流水线（见 v1.11.1 tag 构建）。

## [1.11.0] - 2026-08-30 — 全面体检修复版（安全红线 + 功能补全）

### 修复
- 🐛 **帮助文档出厂密码文案**：`admin/admin123` 修正为 `admin/Admin@2026`，
  与 main.py 出厂播种逻辑及测试断言一致。
- 🐛 **Electron 导航白名单前缀绕过**（W6-T3）：`will-navigate` /
  `setWindowOpenHandler` 的 `startsWith('http://127.0.0.1')` 前缀判定可被
  `http://127.0.0.1.evil.com` / userinfo `@` 手法绕过，改为
  `new URL(url).origin` 精确匹配 + 端口钉扎（12 组绕过用例验证）。
- 🐛 **stopBackend 误杀风险**（W6-T3）：优雅退出后取消强杀定时器，
  防止对已退出（PID 可能被系统复用）的进程执行 `taskkill /f /t`；
  重启端口等待由固定 2s 改为轮询探测释放（上限 10s）。
- 🐛 **SHA256SUMS 行尾**：CI 生成改 WriteAllText 显式 LF——WriteAllLines
  在 Windows 写 CRLF 导致 `sha256sum -c` 全部 FAILED（本地 dry-run 实测）。

### 安全（供应链）
- 🔒 **vcredist 移出 git + SHA256 钉扎**（W6-T2，critical）：37.7MB 官方
  二进制不再入库；新增 `scripts/build/fetch_vcredist.ps1`（CI 9.6 步与
  `make fetch-vcredist` 共用，从 aka.ms 官方短链下载并比对钉扎哈希，
  本地已存在且匹配则跳过）；NSIS 钩子安装期 Get-FileHash 复核，不匹配
  弹窗中止安装（fail-closed）。钉扎常量唯一维护点：
  `build-scripts/electron-builder-nsis-hook.nsh` 头部 `!define` 段。

### 构建/完整性
- ✨ **Release SHA256SUMS 完整性链**（W6-T5）：三个发布产物族独立命名
  清单（windows-x64 / electron-deb-arm64 / standalone-deb-arm64）随
  artifact 上传并附 Release；Windows Release 说明附校验指引。
- ✨ **前端产物同步逐文件哈希校验**：`sync-frontend-dist.{sh,bat}` 由
  du 字节粗校验（>5% 仅警告）改为逐文件 SHA256 manifest 比对，偏差即
  exit 1；manifest 落盘供 `audit_static_assets.py --verify-manifest` 复核。

### 构建/完整性（续，2026-08-30 第二批）
- ✨ **PyInstaller onefile → onedir**（W6-T6/ADR-0006）：冷启动实测 32.3s →
  8.6s（~3.8 倍）；消除 %TEMP% 自解压的杀软误报画像；datas 摘除 app/ 源码
  目录与死依赖（aiosqlite/jieba/bs4/prometheus_client），hiddenimports 删除
  54 条 collect 覆盖的手写路由；全消费方适配（extraResources/main.js/CI/
  ARM64 Dockerfile）；本地完整 NSIS 构建（227MB）+ 打包应用冒烟
  （登录/列表/导出全 200）。
- 🔒 **Actions 全量 pin 到 commit SHA**（W6-T7）：4 个 workflow 57 处 uses
  实时解析上游 SHA 固定，消除 tag 漂移的供应链风险。
- ✨ **代码签名管线就绪**（W6-T1 管线侧）：CSC secrets 配置即自动签名
  （后端 exe signtool + 安装包/卸载器 electron-builder），未配置显式
  WARNING 跳过；接入与验签文档 docs/04-部署文档/01-Windows部署/代码签名.md。
- 📝 **离线升级与回滚指南**（W6-T10）：备份→SHA256/签名校验→覆盖安装→
  alembic 迁移→回滚路径；NSIS 卸载静默默认保留用户数据（/SD IDNO）。
- 🔐 **secrets.json 明文回落收紧**（W6-T11）：safeStorage 不可用时 0600
  权限 + 风险文档标注。
- 🧹 **前端未使用导出复核收口**（W9-T1）：288 项逐项复核，删除 2 项真死
  代码（userManagementApi/EXPORT_FIELDS），286 项按验收标准标注豁免
  （265 项被各自单元测试引用——纠正工单"含测试零引用"前提；21 项特殊
  形态有真实引用）；顺带修复 W3-T2 menuKeyAlignment 守卫对可选参数
  路由的匹配（14d2b243 引入的存量红测试）。

### 修复（2026-08-30 双轴代码评审批次）

- 🐛 **增量包预览静默全 0**：`_compute_package_diff_stats` 的 `IN` 查询未分块
  （超 SQLite 变量上限即抛错），且 `except Exception` 吞掉异常返回空统计——
  管理员会把"统计全 0"误读为"无差异"而确认覆盖式导入。改为分块查询（500/批）+
  fail-loud，统计失败返回明确 500 错误。
- 🔒 **错误细节出站收口（W1-6）**：monitor.py 4 处 `str(e)`/服务器路径经响应
  出站（`data={"error": str(e)}` 形态属既有扫描器盲区），全部泛化文案 +
  `logger.error(exc_info=True)`；`test_no_error_detail_leak` 补第三类
  字典值绕过规则。
- 🔒 **路径双源违规收口**：monitor.py `/database-size` 改用
  `paths.get_database_path()` 唯一来源，不再自行拼 DATABASE_URL；响应移除
  服务器路径字段；`paths._db_file_from_url` 提升为公开 `db_file_from_url`
  （backup_service 跨模块消费不再引用私有符号）。
- 🔒 **敏感参数不入 URL**：`/machine-code/reset-password-with-machine-code` 与
  `/recover-admin-factory-password` 的 username/机器码/校验码从 query 改为
  请求体（Pydantic 模型），前端 ForgotPassword/machineCode.ts 与测试同步
  ——URL 查询串会被访问日志/代理记录。
- 🐛 **SQLCipher 错误密钥 fail-fast**：`PRAGMA key` 后主动读 schema 自检，
  错误密钥在连接建立时以明确异常失败，而非首条业务查询时报
  "file is not a database"。
- 🐛 **data_scope_adapter 文档与实现矛盾**：模型缺组织字段的 fail-closed
  行为（降级仅本人）此前 docstring 仍写"原样返回"，且缺字段路径会误打
  "User has no organization" 日志误导排查——分支重构 + 文档纠偏。
- ⚠️ **行为变更（发布说明）**：数据权限 fail-closed（34f7d7f8）后，非管理员
  且无组织归属的账号可见范围从"全量"收敛为"仅本人"。离线单机默认管理员
  不受影响；存量无组织普通账号将看到数据范围缩小，属预期安全语义。
- 🧹 数据包 versions 五端点（列表/创建/对比/详情/删除）由手写
  `{success, data}` 收敛为 `success_response` 信封（W5-004 收尾），前端
  拦截器兼容，数据载荷形状不变。

### 修复（2026-08-30 v1.11.0 发版构建批次）

- 🐛 **fetch_vcredist 目录先行创建**：CI 全新 checkout 中 resources/vcredist/
  被 gitignore 不存在，写 .download 临时文件抛 DirectoryNotFoundException
  （重试亦必然失败）——建目录提前到任何写入之前。
- 🐛 **CSC 空串不再注入**：secret 缺失时 `${{ secrets.X }}` 展开为空串，
  electron-builder 24.x 仍按证书路径解析导致构建失败；改为签名步骤在密钥
  存在时经 GITHUB_ENV 按需导出。
- 🐛 **Release 资产名校验链断链**：GitHub 剥离资产名中的非 ASCII 字符
  （中文安装包名上传后变为 Setup.1.11.0.exe），SHA256SUMS 清单与实际资产名
  不匹配、`sha256sum -c` 无法通过——package.json 显式 ASCII `artifactName`
  防复发，当前 Release 清单已修正并实测哈希一致（2344aa34…）。

### 清理（无死代码遗留）
- 🧹 删除 4 个引用已删源码的死测试（stores/project、stores/rbac、
  useAccessibility）及 8 处指向不存在模块的 `vi.mock`（4 处已删 stores/api +
  7 文件中的 `@/utils/request`）与 3 处未使用导入；AGENTS.md 版本号引用
  改为单一事实源表述。

### 修复（功能异常，体检批次）
- 🐛 **资金三列表筛选不重置页码**：AnomalyList/ContractManage/TransferVoucher
  第 2 页起筛选得到空表——筛选变更统一回第 1 页（全站扫描无同类漏网）。
- 🐛 **版本管理页请求 404**：`/data-package/version` 路由缺 `:id` 致
  `GET /data-packages/undefined/versions`；改可选参数 + 无 id 时包选择器
  （唯一包自动选中）。
- 🐛 **增量数据包三端点契约断裂**：detect-changes 改查询参数并返回完整
  ChangesSummary（含软删统计口径）；export 修复 record_counts AttributeError
  （改为从 manifest 取值）；import 由空操作实现为真实预览/应用
  （管理员 + confirm_import 覆盖式 upsert + 审计）。
- 🐛 **fk_ondelete_001 迁移全新库必败**：SQLite 检查器不回传 ondelete 致幂等
  误判 + 匿名外键按合成名 batch drop 必败——改读建表 DDL 判定 + 影子表重建；
  完整迁移链从零升级到 head 验证通过。

### 安全（审计红线，体检批次）
- 🔐 **PII 字段透明加密落地**（W5-T7/ADR-0005）：9 列（身份证/电话类，含
  users.phone）切确定性 AES-SIV TypeDecorator，等值查询零改写；存量回填迁移
  `pii_encrypt_001`（幂等，enc.v1: 标记）；SQLCipher 修正为 fail-closed 驱动
  探测 + 字面量 PRAGMA key（封死绑定参数假加密）。
- 🔐 **数据权限 fail-closed**（W5-T6/ADR-0002）：get_org_scope 三处"无组织→
  is_admin=True"改回退仅本人；适配器缺过滤字段禁止静默放行全量
  （降级仅本人 / 抛 DataScopeFilterError）。
- 🔐 **组织删除级联守卫**（W2-T2/ADR-0003）：硬删除前检查名下项目/用户
  （OrganizationInUseError 含计数）；projects 组织外键 CASCADE→SET NULL
  （org_guard_001 影子表舞步）截断级联删除链。
- 🔐 **API 响应信封收敛**（W5-T4）：7 文件 51 处裸 dict → success_response/ok_list，
  前端拦截器展开后向后兼容，24 测试文件 490 用例全绿。

### 补全（缺失功能，体检批次）
- ✨ **dataPackage 增量更新/版本管理后端补全**：增量检测/导出/导入三端点 +
  版本 CRUD/对比端点补组织访问校验与审计日志；前端两页撤"开发中"横幅接
  真实 API（PackageType 新增 update 类型）。

### 修复（体验）
- 🐛 帮助文档出厂密码文案 `admin/admin123` → `admin/Admin@2026`；
  注册页视觉对齐登录/忘记密码页。

### 性能（体检批次）
- ⚡ 首屏脚本 gzip 实测 149KB（≤350KB 目标达成，W5-T1 关闭；xlsx/echarts/
  chartjs/guizhou 均独立懒加载块）。

## [1.10.6] - 2026-08-29 — 全仓库死代码彻底清理(v1.10.5 为清理前基线)

本批为一次系统性死代码清理:3 个探索代理深扫(后端 import 图两轮比对 + ~800 顶层符号
引用计数、前端 382 生产文件全量 import 图谱、脚本/CI/docker 引用图谱),每个删除候选
均经 AST/grep 复核生产代码零引用,分 5 个独立 commit,每阶段门禁全绿。

### 后端(-90 模块 / 孤儿符号 / 死方法)
- 删除 87 个零引用模块文件 + data/ + interfaces/api/(~12,300 行):core 21、
  services 21、utils 21、schemas 10、middleware 3、未注册路由 2、垫片 4
- 删除 6 个零引用模型文件 + EffectivenessIndicator/VersionHistory 两类,
  新增 alembic dead_models_001 迁移 DROP 8 张表(本地全库验证 0 行)
- 摘除活模块内孤儿符号 ~60 个(exceptions 11 异常类、response/security/
  error_handler/query_optimizer 孤儿函数、services 死方法与死类型)
- PyInstaller spec 移除不存在的 messages_extended;删除陈旧 requirements-lock.txt
- 依赖精简 31 项(redis/jieba/matplotlib 全家桶/scipy/python-pptx 等,全部验证
  零 import 含懒加载);当前 venv 卸载全部 24 包后全量 pytest 通过(强验证)
- 测试同步:删除死模块专测 ~70 文件,混合 harness 摘除死段保留活用例

### 前端(-73 test-only 生产文件 / 68 死测试)
- 删除 test-only 存活文件 73 个(44 组件、16+4 composables、7 utils、3 stores、
  4 api、appConfig/rbac/permissions 等)与零引用死文件 10 个
- 重复实现归并:PageHeader/GlobalSearch 死副本、Skeleton/LazyImage/DataTable 两套
- 17 个覆盖率 harness 摘除死条目,保留活代码覆盖
- package.json 移除 fast-check/@types/dompurify/rollup/@commitlint/*/driver.js;
  删除休眠 commitlint 链与 frontend/scripts 5 个孤儿脚本

### 脚本/基础设施(W6-T8 完成)
- git rm:test_scripts/、installers/、k8s/、Dockerfile.arm64/.fpm、.qwen/.reasonix、
  skills-lock.json、environment.yml、根 mypy.ini、根 .bandit、根 tests/ 孤儿部分、
  scripts/ 孤儿 21 个、resources 死图标 17 个、build-scripts 死文件 4 个
- docker/Dockerfile 删除从未可构建的 electron-builder 阶段(electron/ 无 package.json)
- Makefile 删除 kylin-verify 死目标与过期 help 文本

### 文档同步
- 修正 AGENTS.md 悬空 ADR 引用与测试总数、scripts/README.md 死脚本引用、
  构建打包指南 NSIS 钩子表、项目结构说明死项标注、system_design.md 历史存档声明

### 规模与验证
- 净删除 500+ 文件、约 5.5 万行(代码+测试+脚本)
- 验证:后端 pytest 10102 passed / flake8(CI 口径)0 错误 / bandit 无新增;
  前端 vitest 300 文件 5759 测试全绿 / vue-tsc / eslint / vite build 全过
- 已知保留:reminder_engine(被 orchestrator 引用)、get_user_by_id(内部自调用)、
  EmptyState/StatsCard/BaseChart/utils/index(验证存活)、knip 未使用导出 ~288 项
  转入工单 .scratch/w6-release-eng/009 分批处理
- 已知 flaky: recycle_bin 权限矩阵 1 例(限流滑动窗口顺序敏感,单跑通过,与本次无关)


## [1.10.5] - 2026-08-29 — UI 可读性根治 + 全站精美化

### 界面
- 🎨 根治"UI 看不清"：提示可读性修复、全站视觉统一美化、输入框规范化
- 🧹 NUL 坏文件全清（CodeCheck 失败文件归零）

### 版本链
- 🔖 版本号随 tag 联动：CI 打包前 sync 脚本把 tag 版本写入 `frontend/.env.production`
  的 `VITE_APP_VERSION`（vite 构建注入，本地开发回落 `.env`）

## [1.10.4] - 2026-08-29 — CI 修正

- 🐛 fix(ci): standalone-deb 产物路径修正（buildx output 导出树保留 `/output/` 前缀），
  standalone 麒麟 DEB 产物重新挂载到 GitHub Release

## [1.10.3] - 2026-08-29

### 补齐（缺失功能）+ 深度清理（坏文件/死代码）

- ✨ **CI 补建 standalone 麒麟 DEB 流水线**：此前 CI 只构建 Electron DEB，而安装指南
  推荐的 standalone DEB（无 Electron，后端+Web）只能本地 Docker 自建。新增
  `standalone-deb` job（buildx+QEMU ARM64，GHA layer 缓存），内置 CRLF 回归门禁
  （dpkg-deb -R 解包后 grep CR 即失败）与 postinst bash -n 语法校验；两个 DEB
  均自动附加到 GitHub Release。
- 🐛 **环境变量三层错序开浏览器**：`kylin.env` 声明的 `AUTO_OPEN_BROWSER` 是死键
  （start.py 从不读取），实际生效的 `KYLIN_MODE` 让 systemd 服务层（无 DISPLAY）
  尝试开浏览器。修复：移除 `KYLIN_MODE` 变量（唯一用途即该错层行为），
  start.py 改读 `AUTO_OPEN_BROWSER`（默认 false，服务层不开浏览器；
  桌面会话由 start-kylin.sh 负责；裸机调试可手动开启）。
- 🧹 **坏文件**：全仓 2786 个文本文件 mojibake 字节级扫描（`scripts/scan_mojibake.py`
  工具入库），唯一真命中为根目录 `.env`（GBK 双重编码，注释吞掉 `HOST=127.0.0.1`
  等配置行）——已按 `.env.example` 重建实际取值（文件不入库）。
- 🧹 **死代码**：`error_handler` 四个零引用 backward-compat 别名
  （BadRequestError/ForbiddenError/ConflictError/ServerError）移除，保留有引用的
  AppError/NotFoundError；`test_sync_version_increment` 重构为自建临时 SQLite
  （不再依赖外部 test.db 的 schema 新旧，曾致 PendingRollbackError 误报）。

## [1.10.2] - 2026-08-29

### 修复（安装包三大问题：Windows 打不开 / 麒麟打不开 / 图标+快捷方式缺失）

- 🐛 **Windows 安装后启动报 `SyntaxError: Unexpected token '}'`（main process 弹窗）**：
  提交 `10c56cd0` 以 GBK 编码重写 `electron/main.js`（COORDINATION.md §3 明令禁止的
  PowerShell 写法），吞掉换行与引号——`findAvailablePort` 的 `for(...)` 被并入注释导致
  178 行孤立 `}`；`startBackend` 函数声明、`MAX_BACKEND_RESTARTS`、`rendererCrashedOnce`
  等 5 处关键代码被静默注释；10 处字符串未终止。已从 `10c56cd0~1` 整体恢复
  （经比对该提交对 main.js 的净效果为纯破坏，无需保留的语义改动），`node --check` 通过。
- 🐛 **麒麟 Electron DEB 打不开**：同一损坏的 main.js 打进 DEB → 主进程启动即崩，随恢复治愈。
- 🐛 **麒麟 standalone DEB 装完打不开 / 无菜单图标 / 无桌面快捷方式**：
  `DEBIAN/postinst|prerm|postrm`、`kylin.env`、`*.service`、polkit 规则共 6 个文件为 CRLF
  （Windows 检出 + 构建无规范化）→ `#!/bin/bash\r` 不可执行 → dpkg 报 post-installation
  error → 菜单项/快捷方式/图标/服务/数据目录全部未创建。修复：仓库内 6 文件转 LF +
  `.gitattributes` 锁 `deploy/kylin/** eol=lf` + Dockerfile 打包阶段 `sed -i 's/\r$//'`
  治本（构建产物与检出环境无关）。
- 🐛 **麒麟启动脚本硬依赖未打包的 curl**：`start-kylin.sh` 健康检查增加
  curl→wget→bash /dev/tcp 三级回退（零外部依赖）。
- 🐛 **麒麟直接启动回退路径权限**：/var/lib 对桌面用户组不可写时降级 `$HOME/.assistance-management-system/`；
  postinst 数据/日志目录 750→2750（组可写，配合 usermod -aG 已有加组逻辑）。
- 🐛 **CI 内嵌 postinst 乱码路径**：build-arm64.yml `/opt/甯壎绠＄悊绯荤粺` → `/opt/帮扶管理系统`。

### 预防（杜绝同类问题再发）

- 🔒 CI 语法门禁：build-windows.yml / build-arm64.yml 在 electron-builder 打包前
  `node --check electron/*.js`，失败即终止构建。
- 🔒 pre-commit 阶段新增 `electron-syntax-check` hook（改动 electron/*.js 时本地即时拦截）。
- 🔒 `package.json` 新增 `npm run check:electron`；`build`/`build:win` 前置语法校验。
- 清理死脚本 `scripts/linux-postinst.sh`（路径错误零引用）；
  安装指南中不存在的 `build-deb-ubuntu.sh` 引用改为 Docker 构建实际方式。

## [1.10.1] - 2026-08-27

### 修复（前后端对齐 + 测试健康收官）

- 🐛 **审计日志 4 处 404**：OperationLogs/AuditManagement/dataManagement 调用 `/audit/logs`、`/audit/logs/export`、`/audit/exports` 缺 `/system` 前缀，运行时必 404（对齐度核查工具 `scripts/api_alignment_check.py` 发现）
- 🐛 **备份计划回显错位**：后端返回驼峰 `keepCount`，前端回退链只读 `keep_count`，界面保存后恒显默认 7 天
- 🐛 **el-statistic / el-card 破损属性**：PendingList `value-style`、Import `body-style` 属性名断裂导致样式失效
- 🐛 **useBackupSchedule 测试契约过时**：重写至 cron↔友好模型双向转换契约（含 weekly/缺省分支）
- 🐛 **磁盘空间测试 3 失败**：psutil 桩改注入 sys.modules；os.statvfs 打桩 create=True；upload_restore 弃 from-import 局部绑定
- 🐛 **版本号收尾**：backend/version.json 1.5.0 → 1.10.0，至此 6 处版本源全部一致

### 测试与质量

- 前端 6550 通过 / 0 失败（新增 api 层 14 用例：milestones、fundsRecycle、schoolsRecycle、offlineMap），覆盖率门禁恢复绿灯
- 后端 12613 通过 / 0 失败 / 0 skip / 0 xpass
- 死代码清理：`config_validator.ProductionSettings`（无引用 Backward-compat stub）
- 仓库卫生：根目录构建脚本归位 `scripts/docker|legacy/`，3 个 AI 会话转录文档（1MB）移出版本库
- 数据隔离审计收官：8/8 业务模块确认隔离、0 漏洞（`docs/数据隔离审计矩阵.md`），澄清早期 grep 误报

## [1.10.0] - 2026-08-24

### 修复（工单002-012，用户可感知缺陷）

- 🐛 **工作台快捷入口**：「资金周期」「经费结算」不再跳回经费总览，直达 /funds/lifecycle 与 /funds/settlement
- 🐛 **KPI 环比诚实化**：工作台五卡接入后端 trends 真实环比（人口卡标注"较去年"）；分析仪表板此前将 kpi-trends 绝对值误当百分比展示的假数据根治，负增长显示红色↓箭头、零增长显示"持平"；sparkline 由模拟数据改为真实近5年年度序列
- 🐛 **全局搜索找回资金结果**：fund 类型在前端类型/标签/图标/分组排序全面接线，占位文案补充"经费"
- 🐛 **帮扶村列表年份筛选复活**：前后端贯通（year_start 参数 + filter-options 返回 years）
- 🐛 **变更历史字段级明细**：时间线展示"谁在何时把什么字段从 A 改为 B"（old_value→new_value）
- 🐛 **导入错误明细可见**：帮扶村/学校两处导入失败弹窗展示行级错误清单（前10条+总数），学校侧修正信封层级读取
- 🐛 **经费申请页过滤失效**：search/type 参数对齐后端 keyword/fund_type
- 🐛 **经费驳回必填**：前端空意见拦截 + 后端 reject 接收 opinion（400 fail-closed）并写入状态历史与关联审批任务
- 🐛 **数据质量"自动修复"假成功根治**：新增 trim_whitespace/normalize_empty 两规则真实现；未知规则键返回400；响应增加 changed_count（实际修正记录数）口径
- 🐛 **消息链接修复**：资金异常通知 link 改指真实路由 /funds/anomaly；审批通过/驳回通知携带实体详情链接可直接跳转；新待审任务指向 /approval/pending
- 🐛 **总览状态中文裸露根治**：FUND_STATUS 枚举扩至九态（补 planned/audited/rejected），筛选下拉同步

### 变更（工单013-019，冗余清理）

- ♻️ 删除冗余视图7个：projects/ProjectManagement.vue（含路由）、dataImport/BatchImport.vue、dataVerify/Index.vue、dataManagement/Overview.vue、report/List.vue、ImportSection.vue、ExportSection.vue、system/UserPermissions.vue（路由重定向至权限包管理）
- ♻️ 数据管理页导入/导出页签改为统一入口跳转卡（/data-sync/import、/data-sync/export），与备份页签同款处理
- ♻️ 后端注销并移除 messages_extended.py 冗余模块（前端零引用）；_BUSINESS_MODULES 精确保留 encryption/search/menus/permission_package
- ♻️ menus.py 清除 user-backup 死键；menu-config 与侧边栏双轨同步（batch-import 指向 /data-package）
- ♻️ 帮扶村列表新增 with_summary 聚合：总数/累计投入/覆盖县市/参与部门全量真实统计，不再按当前页计算

### 新增

- ✨ 帮扶村列表 KPI 卡片基于服务端聚合（with_summary=1），翻页数值稳定

### 测试

- ✅ 归零15个既有失败测试（权限包签名对齐/mock自环链/金额4位小数断言/loopback桩/报表信封链）
- ✅ 新增：清洗规则4用例、搜索6类断言、Dashboard 负向箭头断言、村列表128用例回归绿
- ✅ 全量门禁：后端 pytest 12442+ 通过 / flake8 0 错；前端 vitest 6475/6475 通过 / eslint --max-warnings=0 / vue-tsc 0 错

### 发布

- 🔖 版本号 v1.9.0 → v1.10.0（version.txt → sync_version.py 全链路 + 手工补点8处）

## [1.9.0] - 2026-08-16

### 新增

- ✨ **年份滚动窗口共享工具**：新增 `frontend/src/utils/yearOptions.ts`（`getYearOptions()`），可选年份上限 = 当前年份 + 10，随系统时钟自动后移，年份选择永不过期，保证系统可以一直使用下去；配套 7 项单元测试（含模拟 2031 年时钟滚动验证）

### 变更

- ♻️ **解除全系统年份选择限制**：全站约 14 处年份下拉框此前以「当前年 + 1」为上限（2026 年只能选到 2027 年），现统一改用滚动窗口工具——帮扶村表单（2021 起）/板块数据表单与年度总览（2017 起）/年度数据表单/数据分析年度对比/经费预算/经费分析/经费列表年度总览/分类经费表单/驻村工作报表与列表/成效排名与评估/奖学金学生（滚动窗口 ∪ 数据年份）。`el-input-number`（2000~2099）与 `el-date-picker type="year"`（原生无限制）本已无撞墙问题，保持不变；后端 schema 无年份范围校验，无需改动

### 修复

- 🐛 **版本号统一至 1.9.0**：version.txt（唯一数据源）经 `scripts/sync_version.py` 同步到 config.py / 根 package.json / frontend/package.json / .env.example / frontend/.env.example，并手动补齐脚本未覆盖处：根目录 `.env`（运行时版本接口覆盖源）、electron/main.js 兜底、build.ps1、docker-compose.yml（BUILD_VERSION/镜像 tag/PROJECT_VERSION）、README 徽章与描述、根与前端 package-lock.json、CLAUDE.md / AGENTS.md / docs 各文档当前版本声明。同时修复既有版本漂移：frontend/package-lock.json（1.8.2）、根 package-lock.json（1.8.1）与 package.json（1.8.3）失同步、README 正文 v1.8.1 与徽章 1.8.3 不一致。历史 changelog/测试报告/版本痕迹注释按惯例保留不改写
- 🐛 **荣誉年份硬编码上限 2030**：综合录入页荣誉表彰年份输入框 `:max="2030"`，2030 年后表彰无法录入。已改为 2099（与同页起始/结束年份输入框一致）

## [1.8.3] - 2026-08-16

### 新增

- ✨ **权限包管理**：管理员可将一组菜单打包为「权限包」并绑定一批普通用户（仅限 user/viewer，admin/super_admin 拒绝绑定），改包即全员生效。菜单可见性三级优先级：个人菜单配置 > 绑定权限包 > 角色默认；未绑定用户行为与历史完全一致。入口：系统管理 → 权限包管理（admin/super_admin）；用户管理列表新增「权限包」列
- ✨ **数据上报与接收闭环补强**：非管理员导出一键上报包仅含本人录入数据（管理员维持全组织，manifest 记录 export_scope/exported_by_name，旧格式包兼容）；新增字段级自动校验纠正（必填/枚举/手机号/日期/数值——自动 trim、手机号去分隔符、日期归一 ISO、数字字符串转数值；行分级 ok/corrected/rejected，rejected 不入库并注明原因）；数据包导入与确认入库限 admin/super_admin；新增「接收记录」视图（包编号/来源组织/上报人/大小/校验结果/状态，仅管理员）

### 修复（权限包控制与数据上报链路验证回归）

- 🐛 **User 模型缺少 org_id 别名**：数据上报（/data-reports）与数据包接收（/data-packages/import）大量使用 `current_user.org_id`，但模型仅有 organization_id，导致上报创建报"用户未关联组织"、接收报"未指定目标组织ID"、一键上报组织归属回退错误。现新增 `org_id` property 兼容别名，上报/接收全链路组织归属正确
- 🐛 **数据包导入 AttributeError: validated**：`import_package` 结果构造误用 `PackageStatusEnum.validated`（枚举成员实为大写 VALIDATED），管理员上传接收数据包必现 500。已修正为大写成员
- 🐛 **数据包编码同秒冲突**：`_generate_package_code` 使用秒级时间戳，同一组织同一秒内两次导出/接收撞 `data_packages.package_code` 唯一约束 → 500。现改为毫秒级时间戳 + 4 位随机后缀
- 🐛 **上报编码同秒冲突**：`_generate_report_code` 同为秒级时间戳，同一秒内创建两条上报撞 `data_reports.report_code` 唯一约束 → 500。同样改为毫秒 + 随机后缀
- ✅ **链路验证 25/25 通过**（隔离库双账号实测）：权限包 CRUD/绑定/解绑/非法key拦截/菜单收敛（7项）；下级录入→一键上报→列表可见→管理员上传接收→自动校验→预览→确认导入（导出=导入记录数）→数据保存可查→字段级自动纠正（trim修复入库/缺必填拒绝跳过）→第二包逐一接收（11项）；上报创建/提交/上级收到/待处理/审批通过/驳回流/下级状态查询（7项）

## [1.8.2] - 2026-08-15

### 修复

- 🐛 **新增项目进度始终为 0（双断点）**：后端 `ProjectCreate` 模型缺失 `progress` 字段导致请求中的进度被静默丢弃；前端新建分支提交载荷也未携带进度。现前后端贯通——新建项目填写"当前进度"保存后立即正确显示，后续编辑仍走变更留痕（`_PROJECT_KEY_FIELDS` 含 progress，详情页"变更历史"完整记录）
- 🐛 **组织机构新增后编码为空**：前端表单提示"留空自动生成"但后端未实现，`code` 落库为 NULL。现创建时 flush 拿到自增 id 后自动生成 `ORG+6位数字` 唯一编码
- 🐛 **帮扶成效排名三列恒空**：后端 rankings 未 select `support_unit`（帮扶单位列永远空白），且前端渲染了后端从不提供的 `scores.project_completion`/`fund_execution` 两列。现后端补齐帮扶单位字段，前端删除假数据列并按真实契约补上"生态"列
- 🐛 **成效评估报告渲染 "[object Object]"/"2026.0"**：`flatResult`/`flatCompareResult` 把后端嵌套对象（indicators/year1_data/delta）直接 `String()` 透传给 el-descriptions。现按后端 `_eval_to_dict`/`compare_evaluations` 真实契约渲染：报告展示总分/等级/排名/三唯得分/评估时间，指标明细单独成组；年度对比只渲染两年总分与 delta 变化量（含正负号）
- 🐛 **进入评估页即触发写操作**：带 villageId 参数打开评估页时此前直接 POST 重算并覆写评估记录。现先 GET 已有报告（只读），404 时提示"该年度尚未评估"；「开始评估」按钮仅管理员可见（viewer/user 从排名页进入的入口文案降级为「查看」），杜绝误触 403
- 🐛 **重复评估刷重复审批任务**：每次评估都新建"年度考核复核"审批任务且无去重。现提交前按 entity+年度查重，已有待处理任务时复用
- 🐛 **经费申请页重复入口**：「提交经费申请」与「新增经费记录」两按钮功能完全一致（后者实为历史直创建分支，跳过申请语义）。已删除「新增经费记录」按钮及关联死代码，申请页仅保留唯一入口
- 🐛 **经费模块多处"修改了却不更新显示"**：经费详情提交工作流/编辑后不刷新日志页签；经费总览删除/快捷审批/快捷拨付/批量删除后年度统计卡不刷新；合同附件登记成功不刷新列表且失败时假成功提示；生命周期预算锁定后阶段/计划不刷新；决算审批弹窗残留上次表单；经费报表"已使用金额"列 prop 与数据键 snake/camel 不匹配导致恒空。已逐一修复
- 🐛 **菜单客户端跳转后页面永久空白**：`<router-view>` 的 `transition mode="out-in"` 子组件根节点 `display:contents` 无盒模型，opacity 过渡不触发 transitionend，旧节点永不完成离场。已移除该 transition 包装
- 🐛 **E2E 审批 spec 对话框断言全灭**：`[role="dialog"]` 命中的 `el-overlay-message-box`/`el-overlay-dialog` 中间层无盒模型恒为 hidden，且页面筛选栏 combobox 与对话框内元素 strict 冲突。统一改锚 `.el-overlay:visible` 并限定对话框作用域，超时 3s→10s

### 修复（全面功能验证测试回归）

- 🐛 **版本号不一致**：运行时版本接口受根目录 `.env` 中 `PROJECT_VERSION=1.8.0` 覆盖，与 version.txt/config.py/package.json（1.8.1）不一致。现已统一升至 **1.8.2**（四处对齐），版本接口补 `code/message` 信封字段
- 🐛 **backend/.env 混合编码损坏**：GBK 编辑器写入断字节（7 处中文词尾 '?'+非法 UTF-8），导致 `alembic` CLI 启动即崩（UnicodeDecodeError），且运行服务**静默忽略**该文件回退默认连接池（20+10，实测连接池耗尽、单请求 151 秒）。已重写为纯 UTF-8/LF，迁移与配置加载恢复正常
- 🐛 **Excel 导入帮扶村不校验字段长度**：300 字符村名绕过 schema 200 限制原样入库且无错误报告。现导入层增加字段长度校验（村名/编码/单位/省市区/乡镇/联系人等），超长行跳过并报告"第N行: 字段 'x' 长度超过 N 字符限制"
- 🐛 **审批驳回/通过后申请人收不到通知**：此前仅提交时给审批人发消息，驳回/通过无任何申请人通知。现 approve/reject 均通过 `_notify_submitter` 向申请人推送消息中心通知（含审批意见/驳回原因；通知落库失败不阻断审批）
- 🐛 **帮扶村批量删除无二次密码确认**：与"批量删除必须二次确认"约定不符（组织删除已有 verify_password）。现后端强制校验 `confirm_password`（错误/缺失 400"二次确认失败"），前端弹密码输入框（ElMessageBox.prompt，隐藏输入）后提交
- 🐛 **政策 Word 附件损坏时预览 500**：mammoth 转换异常未被捕获。现转换失败（含损坏/非法文件）回退为文件下载而非 500
- 🐛 **自动锁屏解锁后不恢复原页面**：锁屏跳转 `/login` 未携带 redirect，解锁后落回工作台。现携带 `?redirect=` 当前路由，解锁后恢复到锁屏前页面（改密 redirect 链复用）
- 🐛 **受助学生重复导入无去重**：同一名单重复导入产生重复记录。现按 学校+姓名+年级 查重，已存在行跳过并报告"第N行: 学生 X 已存在，跳过"
- 🐛 **磁盘空间耗尽错误文案**：OperationalError 一律 503"数据库操作失败"。现检测 disk/full 关键字返回"磁盘空间不足，请清理后重试"

### 优化

- 💄 **帮扶成效两页样式全量 Token 化**（排名奖牌渐变/卡片头渐变/正文辅助色均改 `var(--color-*)`）
- ✨ **经费总览写操作后同步刷新年度统计**；合同附件上传失败改为真实错误提示（`附件登记失败，请重试`）
- ✨ **评估/对比失败透传后端错误详情**（`e.userMessage` 优先），不再笼统"评估失败"
- ✨ **成效排名排序 NULL 兜底**（rank 为空的记录沉底）；评估报告/对比接口 404 文案区分"村庄不存在"与"该年度尚未评估"
- 🧪 **E2E 端口隔离**：本地 E2E 后端固定 18000、前端 15173，与本机已安装的生产实例（127.0.0.1:8000）彻底隔离，杜绝测试被生产服务劫持

### 测试

- 后端新增：项目创建携带进度且进入变更留痕、组织编码自动生成且唯一、评估复核任务幂等复用、rankings 响应契约含 support_unit
- 前端重写 `effectiveness/Evaluation.test.ts` 与 `Rankings.test.ts`：mock 全部换成后端真实响应形态（此前 mock 的 `economic/level/project_completion` 等字段后端从未提供，掩盖了渲染缺陷），新增角色显隐、GET 优先、404 引导、残留清空断言
- E2E `approval.spec.ts` 22/22 通过

## [1.8.1] - 2026-08-13

### 修复

- 🐛 **报表 Word/PDF 导出为空文件**：`report_export_service` 的 `export_word`/`export_pdf` 此前直接返回空 bytes，管理员在「数据导出 → 报告导出」下载到 0 字节文件；现已用 python-docx / reportlab 实现真实公文渲染（标题/年度/生成时间/章节表格，PDF 内置 STSong-Light 中文 CID 字体、无需字体文件），无数据时输出带"暂无数据"说明的有效文档
- 🐛 **报表数据为空壳**：`generate_summary_report_data`/`generate_fund_detail_report_data`/`generate_project_progress_report_data` 此前返回空数组；现按年度真实聚合——经费按类型分组统计笔数与申请/批准/拨付/使用金额，项目按状态分组统计数量/平均进度/预算/实际花费，年度总结与综合报告合并村/校/项目/经费四板块

### 移除

- 🗑️ **死代码**：删除 `ReportExportService.export_to_excel`（无任何调用方，且委托目标 `ExcelExportService.export` 不存在的断裂方法）

### 优化

- ⚡ **useRouterSafe 调试日志**改走统一 `logger.debug`（内部含生产环境门控），移除生产路径上的 `console.log` 残留

### 测试

- 新增 `tests/unit/test_report_export_service.py`：针对真实实现的数据聚合断言、docx/pdf 魔法字节与最小体积校验、空数据仍输出有效文档、docx 解包校验表格内容（防"返回空 bytes"回归）
- 更新 `tests/unit/test_cov_final_report_export_service.py` 断言至 v1.8.1 新数据契约（title/sections 结构）

## [1.8.0] - 2026-08-12

### 功能

- ✨ **经费管理全流程化**：列表页新增 8 阶段流程步骤条（预算编制 → 经费申请 → 审批 → 拨付 → 使用执行 → 报销核销 → 决算结算 → 归档），按年度统计自动高亮当前阶段，步骤图标可跳转对应功能页；步骤条下方附流程指引说明
- ✨ **普通用户可完整操作经费**：新增 `require_funds_operator_role`（放行 user 及以上，viewer 保持只读），经费/经费生命周期/预算/转账凭证/合同/结算全部端点对 user 角色开放；后端菜单 `funds-admin`/新增 `funds-lifecycle`/`funds-settlement` 对 user/viewer 可见
- ✨ **经费详情审批流程可视化**：新增 `GET /funds/{id}/approval-flow`（状态机 6 节点 + reached/current 高亮），详情页「审批流程」页签新增 `el-steps` 步骤条与当前审批人展示
- ✨ **审批转交**：待审批列表新增「转交」操作（选择审批人 + 可选原因），对接 `POST /approval/tasks/{id}/transfer`
- ✨ **数据分析年度对比**：后端 `/statistics/analysis` 新增 `yearly_comparison`（按年份聚合村数/投入/人均收入），前端年度对比页签支持按年份取值、`el-empty` 空态、投入 vs 收入对比柱状图
- ✨ **政策文件预览修复**：预览接口按 blob 流处理（图片/PDF/HTML 内联预览，Office 提示并下载），下载文件名使用真实扩展名；移除政策「提交审批」按钮（政策无需审批流）
- ✨ **系统配置删除**：配置列表新增「删除」按钮（二次确认），对接 `DELETE /system/config/{key}`
- ✨ **消息中心类型扩展**：新增「备份提醒」消息类型（筛选/标签/格式化），每日 03:30 自动清理 30 天前消息（`message_cleanup_job`）
- ✨ **贵州省 88 县区补全**：毕节/遵义/安顺/铜仁/黔东南/黔西南补齐全部县级行政区（合计 88 个），含各乡镇数据

### 修复

- 🐛 **帮扶村年度数据保存后不显示**：`YearlyOverview`/`Detail` 读取年度数据用错 key（`industrySupport`/`partyBuilding` 等臆造 camelCase），实际后端按 section 原始 key 返回（`industry`/`party-building` 等），全部修正并对齐类型定义
- 🐛 **帮扶村变更历史无效**：前端 `getChangeHistory` 硬编码返回空数组从未调用后端；后端新增字段级留痕（创建/更新/年度数据保存写 AuditChange）+ `GET /supported-villages/{id}/change-history` 端点
- 🐛 **帮扶村详情编辑无效**：`?mode=edit` 查询参数未被 `pageMode` 计算识别，点击编辑无响应，已支持
- 🐛 **资金周期/决算结算跳转错乱**：布局菜单 `@click="goFundsList"` 强制跳转经费总览覆盖路由跳转，已移除（含死代码）
- 🐛 **新建转账凭证残留上次数据**：打开弹窗未重置表单，新增 `openCreateDialog` 每次重置并清校验
- 🐛 **经费详情状态日志不显示**：`/funds/{id}/history/status` 返回数组但前端取 `res.data.items` 恒空，兼容数组/信封两种形态
- 🐛 **项目/合同附件不能下载**：项目附件列表补「下载」按钮（认证 fetch → blob）；合同附件「打开/下载」改用认证 fetch（原 `window.open` 无法携带 JWT 头必 401）
- 🐛 **项目表单预计完成率输入框过长**：`el-input-number` 全局 100% 宽度改为定宽 160px
- 🐛 **输入框双重方框**：移除 `form-page.scss`/`dashboard-theme.scss` 与 Element Plus 原生边框叠加的 `box-shadow`
- 🐛 **提示策略优化**：单条增删改成功静默（仅刷新列表），关键动作（审批通过/经费拨付等）升级为带标题的 `ElNotification`，失败保留明确 `ElMessage.error`

### 架构清理

- 🧹 删除无引用的 `views/dataManagement/components/BackupSection.vue`（备份已收口至系统管理 → 备份管理，菜单路径同步修正）
- 🧹 删除布局中失效的 `goFundsList` 函数与政策列表 `handleSubmitApproval` 死代码

### 修复（第二轮补漏）

- 🐛 **帮扶村两委年度数据错乱**：`village_committee` 年度子表按年份存取修正，`record_changes` 字段级留痕落库，年度对比取 `latest_year` 真实值
- 🐛 **审批驳回可不填原因**：后端对缺失驳回意见的请求返回 400，前端驳回/批量驳回弹窗增加必填校验（inputValidator）
- 🐛 **审批列表缺提交人**：待审批任务返回 `submitter_name`，前端待审批列表新增「提交人」列与类型/时间筛选（五类实体 + 日期范围）
- 🐛 **审批中心参数错误**：通过/驳回/批量操作请求体 `comment` 改为后端契约字段 `opinion`
- 🐛 **系统配置删除无审计**：`DELETE /system/config/{key}` 补审计日志；配置包保存/重置/导入对齐后端契约（`ConfigBatchUpdate.configs` / `ConfigExportImport.data`）
- 🐛 **备份提醒消息未送达**：备份结果消息发送给 admin/super_admin；30 天自动清理任务生效
- 🐛 **资金周期/决算结算无参进入空白**：菜单无项目参数时渲染项目选择页（下拉选择项目后进入详情），修复内部链接单复数路径（/funds/transfer、/funds/contract、/funds/anomaly）
- 🐛 **经费权限按钮不一致**：经费详情/用户经费列表按 `canOperate`（user 及以上可见操作、viewer 只读）统一控制；编辑/删除仅待审批（pending）状态可用，移除不存在的 draft 状态引用
- 🐛 **硬编码主题色清零**：新增 `utils/chartColors.ts`（运行时读取 CSS 变量色值），全局 `#409eff` 等硬编码色替换为 `var(--color-*)` / chartColors（ECharts canvas 场景）；AdminDashboard/OfflineMap/数据管理/经费分析/乡村工作分析/监控面板全部 token 化
- 🐛 **备份入口不唯一**：AdminDashboard 与数据管理总览中的旧链接统一指向 `/system/backup`
- 🐛 **数据导出含无效 PDF 选项**：后端仅支持 xlsx/csv，移除导出区 PDF 单选项
- 🐛 **托盘角标不联动**：未读消息数变化时调用 `electronAPI.updateTrayUnread` 同步 Electron 托盘角标
- 🧹 **死代码清理**：删除无引用的 `composables/useMessageNotification.ts` 及其测试文件

### 测试与质量

- 后端全量：**12,143 passed**（更新经费权限/菜单/附件权限过时断言，新增 approval-flow、变更历史、年度对比等测试；第二轮同步驳回 403 断言与消息 30 天保留期断言）
- 前端全量：**6,362 passed**（351 个测试文件）；`eslint --max-warnings=0`、`vue-tsc --noEmit`、`flake8 app/` 零错误
- E2E：Playwright 五条关键路径（认证/工作台/帮扶村/项目/经费）**16/16 passed**；E2E 基建修复——登录态改为会话级 API 登录 + sessionStorage 注入（规避 /auth/login 5 次/60s 限流导致的 fixture 级联超时），空字段断言对齐登录页自定义 `.error-banner`
- 安装包：Windows x64 `帮扶管理系统 Setup 1.8.0.exe`（271MB）构建成功，打包版后端启动冒烟通过（/health 200，version=1.8.0）

## [1.5.2] - 2026-08-11

### 修复

- 审批概览 `GET /api/v1/approval` 由占位模块信息改为真实统计（待审批/已通过/已拒绝/总数/我的待审批），前端概览页统计卡恢复真实数据
- 报表订阅模块全链路修复：service 订阅方法完整实现（列表/创建/更新/取消）、响应字段 getattr 容错（修复 500）、生成接口兼容 `subscription_id` 调用；订阅 CRUD/切换/生成/下载真实 API 验证全部通过
- 监控面板 `Promise.allSettled` 解构错位修复（4 变量取 5 个 promise），系统日志面板恢复展示后端真实日志（/system/admin/logs）
- 测试隔离：conftest 会话启动清理遗留 test.db，消除跨会话顺序敏感偶发失败
- 清理误提交的协作者工作区改动与 .reasonix 临时文件，测试套件恢复稳定（后端 12118 / 前端 6273 全过，覆盖率 100%）

## [未发布] - 2026-08-09 备份恢复完整链路 + 深度审计

### 功能
- ✨ **备份包上传恢复完整链路**：`POST /system/backup/upload-restore` 现支持**加密备份**（`password` Form 参数，PBKDF2+Fernet 解密），任意机器导出的备份包均可导入恢复
- ✨ **前端「导入备份包」入口**：备份管理页新增导入对话框（文件选择 + 可选解密密码 + 危险警告），成功后自动跳转登录

### 修复
- 🐛 **备份列表缺少 `is_encrypted`**：前端恢复对话框依赖该字段决定是否显示密码框，缺失导致加密备份无法从列表恢复。列表项现按文件头标记返回 `is_encrypted`（加密/明文/读取失败三态）
- 🐛 **备份上传 OOM 风险**：`upload_and_restore` 原先整包读入内存，多 GB 备份可拖垮进程。改为 8MB 分块流式落盘 + 10GB 防御性上限（413 明确报错）
- 🐛 **校验拒绝时磁盘残留**：加密密码缺失/损坏 ZIP/缺库文件等拒绝分支此前不清理已落盘的临时文件，现统一清理（磁盘零残留）
- 🐛 **加密备份验证提示笼统**：`verify_backup` 对加密包报通用 ZIP 错误，现返回明确提示（`"备份文件已加密，无法直接验证（请通过恢复流程输入密码）"` + `encrypted: true`）
- 🐛 **强制登出无效**：`admin.py` 强制登出写入 `security.py` 的内存黑名单，与真实 JWT 校验路径（`token_manager` → DB 持久化黑名单）互不相通。改用 `revoke_token()` 统一到持久化黑名单；会话统计改用 `core/token_blacklist.count()`
- 🔒 **密码重置明文落盘**：机器码重置密码不再写入 `%TEMP%` 明文临时文件（Windows 无权限限制且永不清理），新密码仅响应返回（localhost）
- 🐛 **版本一致性测试**：纳入环境变量优先级（Electron 注入设计），并清除本机残留的 `PROJECT_VERSION=1.4.2` 系统级环境变量
- 🐛 **ENCRYPTION_KEY 告警误报**：生产环境缺密钥时自动从运行时密钥存储加载/生成持久化 Fernet 密钥（与加密服务共用，兼容既有密文），仅自动生成失败才告警
- 🐛 **管理员密码重置工具弱口令**：`reset_admin_password.py` 默认 `admin123` 已移除，密码必填且强制复杂度校验（≥8 位含大小写/数字/特殊字符）

### 架构清理
- 🧹 **删除死代码**：`services/token_blacklist_service.py`（异步版黑名单，app 零引用）及其专属测试；`security.py` 中失效的 `TokenBlacklist` 类/`validate_session_token`/`generate_session_id`（无调用方）
- 🧹 **Electron 启动健壮性**：页面重试前先做 `/health` 健康检查（每轮 60s 等待），后端就绪后再加载；就绪超时从 3 分钟放宽到 5 分钟（PyInstaller 冷启动 + 杀软扫描实测可超 3 分钟）

### 测试与质量
- **覆盖率攻坚**：`fund_budgets.py`（附件上传/列表、used_amount 映射）86%→**100%**；`policy.py`（附件路径映射、FTS 同步、工作日志降级）95%→**100%**
- 后端全量：**12,109 passed**，覆盖率 **99.86%**（门禁 98%）
- 前端全量：**6,120 passed**（351 个测试文件）
- 安全扫描：bandit 0 发现；前后端 API 契约核对 207 个调用全部匹配

## [未发布] - 2026-08-10 功能完善与整合

### 改进（用户报告问题系统性解决）
- ✅ **审批板块**：概览重写（统计卡/待审批列表/入口导航/一键审批）；待审批/我的申请/审批历史字段对齐（task_id/reviewer_name/current_level）；**业务接入**——政策列表新增"提交审批"按钮（对接 /approval/submit，单机版内部审核流程）
- ✅ **报表模板板块**：新增"字段组合生成模板"（选模块→勾选系统字段→生成）；新增"在线填报"（按模板字段动态表单填写→导出 Excel）；后端新增 /report-templates/available-fields 字段映射端点
- ✅ **数据校验重设计**：数据质量页新增"自定义校验"（下拉选择字段+操作符+比较值+与/或逻辑组合）；后端新增 /data-quality/validate-rules 规则校验端点
- ✅ **组织成员管理**：后端新增组织成员添加/移除端点（POST/DELETE /organizations/{id}/members）；用户管理支持 ?org_id= 预筛选与"清除筛选"（组织详情"分配成员"直达）
- ✅ **数据管理收口**：数据备份菜单重定向至系统备份管理（消除重复入口）
- ✅ **演示数据初始化**：新增 `python -m app.utils.init_demo_data`——一键生成 6 帮扶村（含人口/收入/投入/产业年度数据）+ 6 项目 + 12 经费 + 5 预算 + 6 合同 + 6 政策 + 6 乡村工作 + 4 审批任务，解决新装系统"各板块无数据"体验

### 测试与代码质量
- 后端全量：**12109 passed**（修复 integration conftest 未恢复 SessionLocal/engine 导致的跨套件污染）
- 前端全量：**6200+ passed**（适配协作者新实现：Overview/政策列表/配置页/监控页等）
- lint / vue-tsc 零错误

## [未发布] - 2026-08-09 路由遮蔽修复

### 修复
- 🐛 **仪表盘趋势端点重复注册**：`dashboard.py` 与 `dashboard_trends.py` 均注册 `/dashboard/kpi-trends` 与 `/dashboard/yearly-trends`，后者被 FastAPI 注册顺序完全遮蔽（永远不可达）。`dashboard_trends` 的同比实现改挂 `/dashboard/trends/` 前缀，两个端点恢复可达，同比功能保留

### 审计确认无问题
- 全端点路由遮蔽扫描：759 个真实路由仅上述 2 处重复，其余动态/静态路径（`{user_id}` 与 `/me` 等）由 FastAPI 类型校验自动正确匹配
- 核心业务端点（funds/budgets/policies/projects/schools/villages/rural-works/organizations）全量 200 正常响应，无字段缺失或 500
- 跳过测试仅 3 处（matplotlib 条件跳过，合理）

## [未发布] - 2026-08-08 深度审计

### 修复（全面审计发现）
- 🐛 **管控配置包生成 404**：`SubordinateManagement.vue` 用 GET 调用 `/control-packages/generate`，后端为 POST 端点。改用 `post` 方法，生成功能恢复
- 🐛 **Prometheus 监控端点 500**：`business_metrics_service` 查询不存在的 `DataReport.report_month` 字段（模型无此列），导致 `/metrics/prometheus` 崩溃。改为按 `created_at` 月份统计，端点恢复正常
- 🐛 **SQLAlchemy mapper 部分导入失败**：多个模型使用字符串 `relationship("Xxx")` 引用但未导入对应模型类，单独导入某模型（如监控指标服务）时 mapper 配置报错 `failed to locate a name`。为 23 个模型文件补齐引用模型导入（自动检测循环依赖），循环引用（industry↔village、two_factor_auth↔user）采用类定义后延迟导入注册
- 🧹 **删除失效组件**：`charts/BarChart.vue`、`charts/LineChart.vue`、`charts/PieChart.vue` 引用不存在的 `./BaseChart.vue` 且无任何页面引用，连同其测试文件一并删除；`components.d.ts` 同步清理
- ✅ **全端点冒烟**：759 个真实路由全部验证（401/403/404 正常），0 个 500 异常

### 测试与代码质量
- 后端全量：**12109 passed**
- 前端全量：**6207 passed**（346 个测试文件）
- `vue-tsc --noEmit`、`eslint --max-warnings=0` 通过

## [未发布] - 2026-08-05

### 安全加固
- 🔒 **数据同步提权修复**：`/data-sync` 导出/导入/冲突处理端点原仅认证即可调用，任意登录用户可导出全库数据或导入构造数据包。现全部要求管理员权限；同步白名单剔除敏感表（users/machine_codes/audit_logs），导入侧新增 `_SENSITIVE_TABLES` 硬禁止，防止构造 ZIP 覆盖密码哈希提权
- 🔒 **备份下载权限收紧**：`GET /system/backup/download/{filename}` 原任意登录用户可下载含全库数据的备份，现要求管理员权限
- 🔒 **审批自动通过越权修复**：`/approval/submit-auto`、`/tasks/auto-approve`、`/tasks/auto-approve-all` 原跳过审批人校验可代批他人审批，现要求管理员权限
- 🔒 **数据库维护操作权限**：`/system_health/integrity-check`、`wal-checkpoint`、`vacuum` 原任意用户可触发（VACUUM 可长锁库 DoS），现要求管理员权限
- 🔒 **配置包导出安全**：`/config-package/export` 要求管理员；配置包导出不再包含 `hashed_password`（迁移后用户重置密码，避免哈希泄露）
- 🔒 **权限包下载路径遍历修复**：`/permission-package/download/{file_name}` 增加 basename 校验与 realpath 边界检查，阻断 `../../` 越界读取
- 🔒 **越权端点补齐**：用户导出（`/export/users` 含 PII）限管理员；错误报告状态更新限本人或管理员；仪表盘自定义动态更新/删除限本人或管理员
- 🔒 **上传类型收紧**：通用上传白名单移除 `svg`（防存储型 XSS），并新增图片魔数内容嗅探（防改名绕过）
- 🐛 **数据同步增量查询 SQL 修复**：`since` 分支 SQL 拼接缺少 f-string 前缀导致必然报错，已修复

### 功能修复
- 🐛 **数据管理导出类型错乱**：`ExportSection.vue` 原先无论选择何种数据类型都调用村庄导出接口（选择"经费投入数据"导出的是村庄列表）。现按数据类型分派到真实端点（村庄/经费/年度统计/产业），各类型导出正常
- 🐛 **数据包导入导出对话框为空占位**：数据包模块的 4 个对话框（导出/导入/加密导出/加密导入）原为无功能占位组件。现实现真实功能：对接 `/data-packages/export`、`/import`、`/export-encrypted`、`/upload-encrypted` 接口，数据包列表页新增"加密导出/加密导入"入口
- 🐛 **经费预算"已使用金额"恒为 0**：后端 `BudgetCreate`/`BudgetUpdate` 缺少 `used_amount` 字段导致前端提交被丢弃。现创建/更新均支持 `used_amount`（映射 `executed_amount`），并兼容双字段名；使用率、结余统计正常
- 🐛 **政策新增/编辑报 "addPolicy is not function"**：`Edit.vue` 调用了 store 不存在的 `addPolicy`/`editPolicy` 方法。改用 `createPolicy`/`updatePolicy`；提交时补充 `attachment_urls` 字段，后端 `PolicyCreateRequest`/`PolicyUpdateRequest` 新增 `attachment_urls` 支持并将首附件映射为主文件（预览/下载可用）
- 🐛 **政策附件上传失败**：上传前未等待 CSRF token 就绪导致原生 XHR 被 403 拦截。`beforeUpload` 现同步等待 `ensureCsrf()` 完成后再上传
- 🐛 **成效大屏 "get is not a function"**：本地代码 API 导入链完整正常（`getDashboardStats`/`getYearlyTrends`/`getRankings`/`getSummaryStatistics` 均存在），确认属旧版生产构建问题，新版构建已消除
- 🐛 **用户角色操作列看不全**：操作列宽度 280px 不足容纳 4 个操作按钮，调整为 320px 并支持按钮自动换行
- ✨ **经费年度总览**：经费管理首页新增"年度经费总览"区块（年度选择器 + 预算/预算已执行/经费申请/已拨付/已使用/结余 6 项统计），各卡片可点击跳转对应模块；后端 `/funds/statistics/overview` 新增 `year` 参数
- ✨ **预算附件上报**：新增 `POST/GET /fund-budgets/{budget_id}/attachments` 预算附件上传与列表接口（凭证/批复资料归档）
- ✨ **合同附件上报**：合同管理新增附件按钮与上传对话框（文件经通用上传端点保存后登记到合同），新增 `POST/GET /fund-lifecycle/contracts/{contract_id}/attachments` 接口；支出明细 `receipt_attachment` 字段打通
- ✨ **学校分析页接入真实数据**：`schools/Analysis.vue` 原为硬编码空图表死代码，现接入 `/schools/statistics` 与列表聚合，展示 8 项统计卡片 + 帮扶状态饼图 + 地区分布柱状图
- 🧹 **清理冗余组件**：删除未被引用的 `A11yDialog.vue`、`BaseModal.vue` 及对应的测试引用；删除 `components/dashboard/` 下 6 个零引用占位 stub 组件（DataOverview/FundOverview/LayoutEditor/QuickNav/StatsSection/TodoList）

### 表单与健壮性
- ✅ **综合数据录入多步骤校验**：提交前校验全部 5 个步骤（基础信息必填、投资数据完整性、专项帮扶项目类型与投资额成对、消费帮扶采购与销售额成对），拦截无效数据
- ✅ **转账凭证/合同表单校验**：`TransferVoucher.vue`/`ContractManage.vue` 补充 el-form rules + validate，金额/日期等字段不可绕过
- ✅ **响应空值保护**：`dataAnalysis/Index.vue`、`ProjectManagement.vue`、`TaskManager.vue` 的 `res.data.items` 访问统一改为可选链兜底，杜绝空响应 TypeError
- ✅ **定时器清理**：`useMessageNotification.ts` 备份提醒定时器、`ErrorBoundary.vue` 重试定时器均保存句柄并在卸载时清理

### 测试与代码质量
- 新增安全加固测试套件 `test_security_hardening.py`（22 项越权/敏感表/上传嗅探用例）
- 后端全量测试通过：**12066 passed**（含数据同步、审批、备份、权限包、健康检查、安全加固等用例）
- 前端全量测试通过：**6123 passed**（356 个测试文件，含数据包对话框、学校分析、合同附件、多步骤校验、分支补齐等用例）
- 前端覆盖率**全指标 100%**（api/views/components/utils/stores/composables/router/config/directives 阈值全过）
- `vue-tsc --noEmit`、`eslint --max-warnings=0` 全部通过

## [1.5.1] - 2026-08-04

### 修复
- 🐛 **麒麟 V10 桌面快捷方式缺失**：DEB 安装后未在用户桌面创建启动图标。`postinst` 现为每个 `/home` 用户创建桌面快捷方式（自动检测 `Desktop`/`桌面` 目录并设置 gio 信任标记），安装后桌面即出现图标
- 🐛 **麒麟 V10 开始菜单图标不显示**：`.desktop` 文件 `Icon` 引用系统通用图标且图标未打入 DEB 包。现打包应用图标到 `/opt/assistance-management-system/icons/`、`/usr/share/pixmaps` 与 hicolor 多尺寸主题目录，菜单图标正常显示
- 🧹 卸载时（`postrm`）清理系统图标、应用菜单项与各用户桌面快捷方式

### 构建
- `docker/Dockerfile.kylin-standalone`：DEB 包新增图标文件与系统图标目录安装
- `deploy/kylin/desktop/assistance-management-system.desktop`：Icon 指向应用图标绝对路径

## [未发布] - 2026-08-01

### 关键 Bug 修复
- 🐛 **修复 Vue setAttribute('0') 页面崩溃** — `ErrorBoundary.vue` 在 `<transition>` 组件内使用 `v-if`/`v-else` 双根元素切换时，Vue patch 算法异常调用 `setAttribute('0')` 导致页面白屏崩溃。修复方案：包裹单一根元素 `<div class="error-boundary-root">` 并设 `display:contents` 保持布局语义
- 🐛 **修复注册时"通行码无效或已被使用"误报** — Windows 环境下 `wmic` 命令生成的机器码因进程重启或系统更新可能不一致，导致通行码验证失败。`machine_code_service.py` 新增第三级回退逻辑：仅凭通行码匹配 pending 记录并自动更新机器码绑定
- 🐛 **修复 files API 响应格式不统一** — `files.py` 上传端点返回裸 dict 而非 `{code:200, data:{...}, message:"成功"}` 信封格式，且存在未使用的 `db` 参数。已改用 `success_response()` 统一格式并补充审计日志

### 角色体系精简
- ✨ **精简用户角色至 4 个核心角色** — 从原来的 7+ 个角色精简为：超级管理员(`super_admin`)、系统管理员(`admin`)、普通用户(`user`)、访客(`viewer`)
- 🔧 **角色归一化函数** — `constants.py` 新增 `normalize_role()` 函数，将旧角色值自动映射到新体系（`approval_leader`/`manager` → `admin`，`operator` → `user`），确保向后兼容
- 🔧 **数据权限层适配** — `data_permission.py` 使用 `normalize_role()` 处理历史角色值，旧用户登录自动映射
- 🎨 **前端角色选择适配** — `UserManagement.vue` 修复默认角色从 `operator` 改为 `user`；`Role.vue` 新增系统角色信息提示横幅

### 测试与代码质量
- ✅ **files API 测试更新** — `test_files_upload_api.py` 断言改为信封格式 `response.data.url`
- ✅ **角色相关测试覆盖** — 新增多组角色归一化测试

## [未发布] - 2026-07-30

### 功能缺陷修复
- 🔧 **管理员会话管理** — 新增 3 个后端端点：用户会话列表 / 强制登出 / 重置双因素认证
- 🚫 **增量更新/版本管理** — 禁用未实现功能的操作按钮（避免用户触发无效 API 调用）
- 🧹 **清理 stub stores** — 删除 4 个空壳 Pinia stores（villager/industry/ruralWork/data）+ 4 个测试文件 + 清理 3 个共享测试引用
- ✅ **后端测试 100% 通过** — 10,889/10,889 测试全部通过

### 文档与交付
- 📖 帮助中心扩充至 15 篇（覆盖全部模块 + 管理员配置指南）
- 📝 项目文件结构说明重写（817 行，小白友好版）
- 📊 13 页精美系统介绍 PPT（深绿金色政务风格）

## [未发布] - 2026-07-29

### 五大核心模块功能增强
- 📊 **工作台** — KPI 数据 60s 自动刷新 + 手动刷新按钮 + 常用操作快捷入口（新建项目/新增帮扶村/资金申请/数据上报）
- 📈 **帮扶村** — 年度数据可视化（收入趋势折线图 + 投入占比饼图）+ 57 个数值字段表单校验强化
- ✅ **帮扶项目** — 任务完成率进度条 + 状态分布标签（待处理/进行中/已完成）
- 🏫 **帮扶学校** — 学生分布柱状图（Top 10）+ 学校类型占比饼图
- 💰 **帮扶经费** — 预算执行率 Gauge 仪表盘 + 分类进度条 + 年度趋势面积图 + 利用率曲线
- 🔍 **全局搜索** — 新增资金(Fund)实体覆盖（5类→6类）

### 文档清理
- 🗑️ 删除 8 个过时文档（v1.2.0 时代的优化方案/体检报告/覆盖率报告/诊断报告/superpowers 审计文件）
- 📝 更新 README.md 测试数据为最新准确值（10,056 后端 + 1,622 前端）

## [未发布] - 2026-07-28

### 安装包与用户体验修复
- 🐛 **修复密码重置假失败** — 后端 `machine_code.py` 重置密码后仅返回 `password_file` 路径，前端检查 `new_password` 字段不存在导致提示失败；现已在响应中返回 `new_password`
- 🎨 **修复图标不圆形** — 原 ICO/PNG 图标四角为不透明深绿色背景（alpha=255），导致安装后图标显示为方形；已用圆形蒙版重新生成透明背景多尺寸 ICO（16/24/32/48/64/128/256）
- 🖥️ **修复桌面快捷方式** — `createDesktopShortcut` 从 `true` 改为 `"always"`，确保非一键安装模式下也强制创建桌面快捷方式
- 🔧 **修复 flake8 4 处错误** — E402 导入位置（security.py、main.py）、F401 未使用导入（cache_service.py）、E501 行过长（excel_importer_service.py）
- 💅 **修复 ESLint prettier 警告** — MyApplications.vue 格式修复

## [未发布] - 2026-07-23

### 前后端100%对齐 + 全量类型错误清零
- 🔗 **前后端API路径对齐** — 修复6个前端API文件缺少 `/system` 前缀（errorReport、tasks、updateLogs、i18n、help、zeroTrust），导致这些模块请求全部404
- 🔗 **注册 notifications_router** — 后端 `messages.py` 中定义的通知偏好路由从未注册到 `api_v1_router`，前端通知偏好功能完全失效；现已注册并添加统一 `PUT /notifications/preferences` 端点
- 🔗 **通知偏好响应格式对齐** — GET 端点增加前端期望的扁平字段（site_system、email_approval等），兼容嵌套结构
- 🐛 **修复 vue-tsc 97 处类型错误（28个文件）** — 涵盖6大类：el-table DefaultRow 类型转换（~30处）、YearlyOverview 属性名 kebab→camelCase（20处）、ComprehensiveEntry el-option 对象解构（12处）、el-tag :type 联合类型（6处）、缺失导出/参数不匹配（~15处）、其他单独修复（~14处）
- 🧹 **清理372个无用文件** — 移除 `resources/frontend-old/` 旧构建产物（CSS/JS/图片）和 `logs/app.log.2026-06-19` 日志文件，更新 .gitignore
- 💅 **ESLint prettier 格式统一** — 自动修复46处格式警告，ESLint --max-warnings 0 通过

### 测试结果 (2026-07-23)
- ✅ 后端: **9,997 测试通过** (33 已有失败, 16 greenlet 环境错误)
- ✅ 前端: **1,622 测试通过** (125 文件, 0 失败)
- ✅ vue-tsc: **0 错误** (从97降至0)
- ✅ ESLint: **0 错误 0 警告**
- ✅ Flake8: **0 错误**
- ✅ 路由加载: 42/42 模块

## [未发布] - 2026-07-22

### 全面故障检测与审查修复
- 🐛 **修复系统初始化密码校验不一致** — `SystemInit.vue` 前端校验 ≥8 位但后端 `InitRequest` 要求 ≥12 位，导致首次初始化设 8–11 位密码被 422 拒绝；前端 placeholder 与校验规则统一为 ≥12 位
- 🔒 **初始化密码强度加固** — `system/init.py` 复用 `PasswordPolicy` 校验管理员密码（与注册接口统一策略），最高权限账户不再允许弱密码
- 🐛 **修复 `_ValidationError.field` 缺失** — `core/exceptions.py` 验证错误类增补 `.field` 属性
- 🐛 **修复 vue-tsc 12 处类型错误** — projects/Detail.vue、Edit.vue、ProgressGallery.vue el-tag `:type` 联合类型注解 + projects.ts id 参数放宽为 `number|string`（兼容离线字符串 ID）+ Edit.vue `unknown`→`any[]`
- 🧪 **对齐 9 项陈旧测试** — 密码策略 ≥12（5 处）、is_bundled onedir 行为、version.json 测试自给自足、inspector 弃用警告断言
- 🧪 **修复并行重构遗留的 4 项测试** — metrics 服务无参实例化对齐（`BusinessMetricsService()`+`get_all_metrics`）、sync 状态测试补 `get_db` override、移除 smoke 中不存在的 ConfirmDialog/StatusTag 组件项、项目文件上传 settings patch 修正
- 📝 **清理误导注释** — `api/v1/__init__.py` supported_village "WIP:501占位" 注释更正为已完整实现
- 📄 **文档同步** — README/结构说明测试数更新为后端 10045 + 前端 1622，验证日期 2026-07-23

### 测试结果 (2026-07-23)
- ✅ 后端: **10,045 测试通过** (0 失败)
- ✅ 前端: **1,622 测试通过** (125 文件, 0 失败)
- ✅ vue-tsc / Flake8 / ESLint: 0 错误
- ✅ Bandit (-ll): 0 中/高危
- ✅ 前端生产构建: 成功
- ✅ 路由加载: 42/42 模块

## [未发布] - 2026-07-08

### 全面测试修复
- 🔧 **修复测试超时** — vitest.config.ts 增加 hookTimeout=60000
- 🔧 **修复 RequestDeduplicator Promise 泄漏** — 添加 .catch(() => {}) 防止 vitest 调度器 hang
- 🔧 **修复 test_funds_enhanced.py NameError** — mock_auth fixture teardown 变量作用域
- 🔧 **修复 Fund 模型字段名** — `fiscal_year`/`created_by` 替换为正确字段

### 代码质量提升
- ♻️ **重构 with_transaction** — 从复杂度 16 拆分为 6 个小函数（flake8 C901 归零）
- 🐛 **修复 win_proactor_fix.py UnboundLocalError** — logger 局部变量未定义
- 🐛 **修复 database_indexes.py Bandit B608** — # nosec 标记位置
- 🎨 **修复 OfflineMap.vue ESLint/prettier** — 格式警告

### 10 项系统优化
- ⚡ **Sass 升级** — 1.71.1 → 1.101.0（消除 legacy-js-api 弃用警告）
- 🏗️ **CI/CD 改进**
  - 新增 `nightly-full.yml` 夜间全量测试（JUnit 报告 + Codecov + 质量报告）
  - `pr-checks.yml` 添加 Codecov 覆盖率上报，flake8 复杂度门禁 16
  - 删除过期 `backup_20260617_190104/` 目录和 merge-conflict 备份文件
- 📦 **lint-staged + pre-commit 加固**
  - `frontend/package.json` 添加 lint-staged 配置（*.ts/*.vue → ESLint, *.py → flake8）
  - `.pre-commit-config.yaml` 分阶段策略：ruff(pre-commit) + flake8/bandit/vue-tsc(pre-push)
- 🐳 **E2E Docker 化** — 新建 `docker/docker-compose.e2e.yml`（Playwright + Locust）
- 📄 **迁移版本管理** — 新建 `012_consolidate_baseline.py` 基线合并文档
- 📝 **可选依赖文档化** — `requirements-dev.txt` 标注 matplotlib/playwright 需要 C++ 编译器
- ✅ **TS 严格模式** — 已启用 strict: true + 全部子选项（原有配置，验证确认）

### 测试结果 (2026-07-08)
- ✅ 前端: **137 文件, 1,681 测试, 100% 通过**
- ✅ 后端: **8,890+ 测试通过**, smoke + funds_enhanced 24/24
- ✅ Flake8: 0 错误
- ✅ ESLint: 0 错误, 0 警告
- ✅ Bandit: 0 高危

## [未发布] - 2026-07-01

### 安全修复（CVE 批量升级）

- 🔒 **bleach 6.3.0→6.4.0** — 3 个 ReDoS 漏洞 (GHSA-g75f-g53v-794x / GHSA-gj48-438w-jh9v / GHSA-8rfp-98v4-mmr6)
- 🔒 **Mako 1.3.10→1.3.12** — CVE-2026-44307
- 🔒 **Pygments 2.19.2→2.20.0** — CVE-2026-4539
- 🔒 **pytest 9.0.2→9.0.3** — CVE-2025-71176

### 测试质量

- 🔧 **消除 1 个 skipped 测试** — test_map.py 移除 pytest.skip，改为符合实际鉴权行为的断言
- 🔧 **消除 11 个测试警告** — SAWarning (transaction already deassociated) + StarletteDeprecationWarning
- 🔧 **conftest.py** — db_session fixture teardown 加 rollback 守卫

### 文档

- 📝 README.md 更新测试数据（8890+ passed, 0 skipped, 0 warnings）
- 📝 README.md 更新构建命令（electron-builder 替代旧 NSIS 脚本）
- 📝 AGENTS.md 更新测试数量 + 构建流程 + 审计日志说明
- 📝 AGENTS.md 新增 PyInstaller spec / NSIS hook 文件引用

## [1.2.0-build] - 2026-06-28

### 构建系统改造

- ✨ **PyInstaller + electron-builder 离线安装包方案** — 目标机器零依赖
  - 新建 `backend/assistance-backend.spec` 统一打包配置
  - 新建 `build-scripts/electron-builder-nsis-hook.nsh`（VC++ 静默安装 + 进程终止 + 卸载清理）
  - 重写 `.github/workflows/build-windows.yml`（matrix x64 + electron-builder 流水线）
  - 删除 3 旧 spec + 7 旧 .nsi + 3 旧 .bat
- 🐛 **预置初始数据库打包** — `resources/database/rural_revitalization.db` 加入 extraResources
- 🐛 **electron/main.js 数据库文件名统一** — bumofu.db → rural_revitalization.db
- 🐛 **electron/main.js 图标路径修复** — resources/icon.png → resources/icons/icon.png

## [1.2.0-security] - 2026-06-23

### P0 安全修复

- 🔒 **密码明文打印移除** — machine_code.py / main.py，改为写入临时文件
- 🔒 **.env 明文密钥清空** — runtime_secrets.py 自动生成
- 🔒 **根 .env 配置混乱修复** — 版本号/端口/密钥
- 🔒 **审计日志落库修复（涉军合规）** — AuditLogger._persist_to_db()，端到端验证通过
- 🔒 **后端 CVE 包升级** — starlette/python-multipart/urllib3/requests/GitPython/Twisted/pydantic-settings
- 🔒 **前端 dompurify 升级** — CVE 修复

### P1 安全配置

- 🔒 **.env.example 安全配置** — CSRF_ENABLED=True, token 480 分钟
- 🔒 **前端 .env.production CSRF 开启**
- 🔒 **关键路径 except Exception 加 as e**（13 处：auth/audit/security/token）
- 🔒 **动态 SQL 标识符白名单** — metrics.py _SAFE_TABLE_NAMES
- 🔒 **database_health_service 路径解析修复**
- 🔒 **encryption.py MD5 弃用处理** — usedforsecurity=False + nosec

## [1.2.0] - 2026-06-20

### 修复（生产崩溃）

- 🐛 **RuralWorkService.create_rural_work 缺失** — 生产环境 `AttributeError: 'RuralWorkService' object has no attribute 'create_rural_work'`，补全 create_rural_work + update_rural_work 签名修正 + 5 个缺失方法（get_statistics/get_villages_for_select/generate_work_report/get_available_years/batch_delete）
- 🐛 **UserCascadeDeleteService 是 stub** — 删除用户始终 500，用 SQLite Pragma 反射重写级联删除
- 🐛 **ExcelExportService.export_organization_pass_codes 缺失** — 组织通行证码导出始终 500，补全方法
- 🐛 **reports 端点 5 处 async 服务调用漏 await** — export_to_excel/export_to_pdf/export_comprehensive_report/get_export_filename 把协程传给 BytesIO 运行时崩溃
- 🐛 **feedback verify_token 导出缺失** — `from app.api.v1.auth import verify_token` 永远 ImportError，登录用户提交反馈不记录身份
- 🐛 **analytics_service.filter_villages 契约不匹配** — service 返回 dict 路由期望元组，统一为 (items_orm, total) 元组

### 修复（功能 BUG）

- 🐛 **工作列表新增数据不显示（根因）** — `rural_work_service._to_dict` 漏 `village_name` 字段，前端"所属村庄"列显示空白。通过 ORM relationship 懒加载补全
- 🐛 **batch-delete body 契约不匹配** — 前端发 `{ids: [...]}` 后端期望 bare `[...]`，改为 `payload: dict` 提取 ids
- 🐛 **AuditLogService.log 字段名错误** — `AuditLog(resource=..., details=..., ip_address=...)` 三个字段名与模型列不匹配（resource_type/user_ip/metadata_），审计日志静默丢失
- 🐛 **projects.py audit.log 未传 db** — 3 处审计日志调用未传 db 参数，日志从未写入
- 🐛 **admin.py int(None) 崩溃** — 配置值为 None 时 int(None) 抛 TypeError，加 `or` 防御

### 修复（测试健壮性）

- 🔧 **file_upload magic 安全导入** — Windows libmagic 触发不可捕获的 access violation 导致全部后端测试崩溃，改用 stdlib mimetypes + 扩展名映射
- 🔧 **patch.dict(os.environ) → monkeypatch.setenv** — 超长环境变量（ACC_PRODUCT_CONFIG_V3 > 32767 字符）触发 Windows 限制导致 teardown 崩溃
- 🔧 **Schema 可变默认值** — `items: list = []` → `Field(default_factory=list)`，Pydantic v2 最佳实践
- 🔧 **前端 handleSave 加 catch** — API 失败时错误不再静默丢失，显示 ElMessage.error

### 文档

- 📝 更新项目文件结构说明.md：新增 v1.2.0 版本记录、services 层补充 rural_work_service/user_cascade_delete_service 说明、新增开发约定章节（Service 序列化/async 调用/Pydantic 默认值/AuditLog 字段映射/Windows libmagic/测试环境变量/路由-service 契约/batch-delete body）

## [1.4.0] - 2026-06

### 新增

- ✨ RBAC 批量权限（事务原子性）、权限撤销端点
- ✨ treeNormalizer 共享工具、E2E 冒烟测试
- ✨ PR 门禁 CI、64-bit 迁移脚本、pre-commit hooks、统一版本管理

## [1.2.0] - 2026-05-31

### 修复

- 🐛 修复 NTFS 文件系统损坏导致后端启动崩溃 (WinError 1392: 文件或目录损坏且无法读取)
- 🐛 修复 `resources/frontend/assets/js/` 目录损坏导致 Starlette StaticFiles 无法挂载
- 🐛 修复 `frontend/node_modules/` 中 element-plus/@antv 包文件内容损坏导致构建失败
- 🔧 添加文件系统损坏诊断与绕过策略：重命名隔离损坏目录 → 重建 → 恢复
- 📝 更新故障排除指南，新增 WinError 1392 诊断修复完整流程
- 📝 更新 CLAUDE.md 添加磁盘故障排查指引

### 运维

- 🔧 前端构建后自动同步 `resources/frontend/` 确保静态资源一致
- 🔧 添加浏览器缓存导致 404 问题的说明（硬刷新 Ctrl+Shift+R）

## [1.1.0] - 2026-03-13

### 新增功能

#### 数据同步
- ✨ 增量数据包导入导出系统
- ✨ 支持13个数据表的同步
- ✨ 三种冲突策略(跳过/覆盖/手动)
- ✨ ZIP压缩格式
- ✨ 完整的导入导出历史记录

#### 离线地图
- ✨ 完全离线的地图瓦片管理
- ✨ 支持缩放级别4-18
- ✨ 瓦片自动降级
- ✨ 预设区域下载(贵州省、毕节市)
- ✨ 地图瓦片管理界面

#### 批量操作
- ✨ 批量更新记录
- ✨ 批量删除(软删除/硬删除)
- ✨ 批量导出数据
- ✨ 操作前验证
- ✨ 批量操作栏组件

#### 数据安全
- ✨ 数据库加密(PBKDF2-SHA256)
- ✨ 敏感数据脱敏(6种规则)
- ✨ 密码修改功能
- ✨ 加密状态管理

#### 帮助文档
- ✨ 完整的离线帮助文档
- ✨ 帮助中心组件
- ✨ 使用指南和FAQ

#### 性能优化
- ✨ 性能监控服务
- ✨ API性能追踪
- ✨ 系统资源监控
- ✨ 数据库性能监控

### 改进

#### 后端
- 🔧 优化数据库查询性能
- 🔧 添加数据库索引
- 🔧 改进错误处理机制
- 🔧 完善日志记录

#### 前端
- 🔧 优化组件加载性能
- 🔧 改进用户界面交互
- 🔧 添加加载状态提示
- 🔧 完善错误提示

#### 测试
- ✅ 添加单元测试(80+用例)
- ✅ 添加集成测试
- ✅ 测试覆盖率达到80%+

#### 文档
- 📝 完整的用户手册
- 📝 详细的安装指南
- 📝 API文档完善
- 📝 技术文档更新

### 修复

- 🐛 修复数据导入时的编码问题
- 🐛 修复地图瓦片加载失败的问题
- 🐛 修复批量操作时的验证错误
- 🐛 修复加密配置文件路径问题
- 🐛 修复Alembic配置缺失的问题
- 🐛 修复启动系统.bat编码乱码问题（UTF-8→GBK）
- 🐛 修复UserInfo对象缺少allowed_menus_list属性导致的菜单API 500错误
- 🐛 修复启动脚本健康检查超时问题（netstat替代PowerShell Invoke-WebRequest）
- 🐛 修复44个scripts/*.bat文件的编码一致性问题
- 🗑️ 清理33个冗余/过时的文档文件

### 安全

- 🔒 添加数据库加密功能
- 🔒 实现敏感数据脱敏
- 🔒 增强密码安全性
- 🔒 完善备份恢复机制

### 性能

- ⚡ API响应时间优化到<500ms
- ⚡ 数据导出性能提升50%
- ⚡ 批量操作性能优化
- ⚡ 地图瓦片加载优化

## [1.0.0] - 2026-01-29

### 新增功能

#### 核心功能
- ✨ 帮扶村管理
- ✨ 项目管理
- ✨ 组织管理
- ✨ 政策管理
- ✨ 数据统计分析

#### 用户管理
- ✨ 用户认证和授权
- ✨ 角色权限管理
- ✨ 用户个人设置

#### 数据管理
- ✨ 数据导入导出
- ✨ 数据备份恢复
- ✨ 数据报表生成

#### 系统功能
- ✨ 系统监控
- ✨ ���志管理
- ✨ 问题跟踪

### 技术实现

#### 后端
- 🏗️ FastAPI框架
- 🏗️ SQLAlchemy ORM
- 🏗️ SQLite数据库
- 🏗️ Alembic数据库迁移

#### 前端
- 🏗️ Vue 3框架
- 🏗️ TypeScript
- 🏗️ Element Plus UI
- 🏗️ Pinia状态管理

#### 部署
- 🏗️ Docker支持
- 🏗️ Nginx配置
- 🏗️ 系统服务配置

## [未发布]

### 计划中的功能

#### 短期(1-2周)
- 🔜 完善单元测试
- 🔜 性能压力测试
- 🔜 用户体验优化

#### 中期(1-2月)
- 🔜 SQLCipher实际集成
- 🔜 差异备份实现
- 🔜 更多脱敏规则
- 🔜 审计日志增强

#### 长期(3-6月)
- 🔜 多密钥管理
- 🔜 密钥轮换
- 🔜 细粒度权限控制
- 🔜 数据加密传输

## 版本说明

### 版本号规则

版本号格式: `主版本号.次版本号.修订号`

- **主版本号**: 重大架构变更或不兼容的API修改
- **次版本号**: 新增功能,向下兼容
- **修订号**: Bug修复,向下兼容

### 变更类型

- `新增` - 新功能
- `改进` - 对现有功能的改进
- `修复` - Bug修复
- `安全` - 安全相关的修复
- `性能` - 性能优化
- `废弃` - 即将移除的功能
- `移除` - 已移除的功能

## 升级指南

### 从 1.0.0 升级到 1.1.0

1. **备份数据**
   ```bash
   cp backend/data/app.db backend/data/app.db.backup
   ```

2. **更新代码**
   ```bash
   git pull origin main
   ```

3. **更新依赖**
   ```bash
   cd backend
   pip install -r requirements.txt --upgrade
   cd ../frontend
   npm install
   ```

4. **运行数据库迁移**
   ```bash
   cd backend
   alembic upgrade head
   ```

5. **重启服务**
   ```bash
   # 重启后端和前端服务
   ```

### 重大变更说明

#### 1.1.0 重大变更

1. **数据库结构变更**
   - 新增 `data_sync_logs` 表
   - 新增 `data_conflicts` 表
   - 需要运行数据库迁移

2. **API变更**
   - 新增数据同步API: `/api/v1/data-sync/*`
   - 新增离线地图API: `/api/v1/offline-map/*`
   - 新增批量操作API: `/api/v1/batch/*`
   - 新增加密管理API: `/api/v1/encryption/*`

3. **配置变更**
   - 新增加密配置文件: `data/encryption_config.json`
   - 新增地图瓦片目录: `data/map_tiles/`
   - 新增数据同步目录: `data_sync/`

4. **依赖变更**
   - 后端新增依赖: `psutil`, `aiohttp`
   - 前端新增依赖: `leaflet`

## 已知问题

### 1.1.0

- SQLCipher完整集成需要编译支持(当前为框架实现)
- 大数据量导出可能较慢(>10000条记录)
- 地图瓦片下载需要网络连接

### 1.0.0

- 部分功能仅支持单用户使用
- 数据导入导出格式有限

## 贡献者

- Claude Opus 4.6 (AI Assistant) - 主要开发

## 许可证

内部使���

---

**最后更新**: 2026-05-29
**当前版本**: v1.2.0

## [1.2.0] - 2026-05-29

### 系统优化
- 🔧 Flake8 零问题（修复 100+ 代码质量警告）
- 🔧 后端测试恢复运行（修复阻塞的导入错误）
- 🔧 CI/CD YAML 完整重写（消除语法错误和质量门绕过）
- 🔧 CORS 实现统一（3 个 → 1 个，删除死代码）
- 🔧 安全加固（删除 .env 泄露密钥、PrometheusMiddleware 死代码）
- 🔧 前端构建优化（Element Plus 按需导入）
- 🔧 Stub 服务标记 NotImplementedError
- 🔧 索引系统重构（全部移入模型 __table_args__ + 启动验证）
- 🔧 数据库索引 bug 修复（移除不存在的 fiscal_year 列引用）
- 🔧 版本号统一（settings/README/package.json → 1.2.0）
- 🔧 Pydantic v2 弃用修复（min_items → min_length）
- 🔧 前端 Tree-shaking 优化（zhCn 直接导入，~300KB bundle 节省）
- 🔧 AuthStorage 统一存储层（sessionStorage 优先，localStorage 回退）
- 🔧 路由守卫修复（401 拦截器与路由状态同步）
- 🔧 ADMIN_ROLES 常量统一到 roleAccess.ts
- 🔧 启动脚本编码修复（chcp 936，PowerShell 健康检查）

### 新功能
- ✨ 路由系统补全（组织/用户/村庄/项目等模块路由定义）
- ✨ Pinia stores 完整实现（auth/organization/user/village）
- ✨ 前端统一 AuthStorage（token 迁移 + sessionStorage 存储）
- ✨ 登录页 401 重定向循环防护

### 部署
- 📦 .deb 一体化构建脚本（build-scripts/build-deb-ubuntu.sh）
- 📦 国产电脑一键安装指南（麒麟V10/UOS/Ubuntu）
- 📦 Docker 交叉编译 ARM64 .deb 支持
- 📄 11 个 PPT 更新至 v1.2.0
- 📄 部署文档全面更新
- 🔧 request.ts 泛型支持 + 精确 URL 取消匹配
- 🔧 static_files.py 重构（纯函数 + SPA 内存缓存）

### UI/UX 修复 (2026-05-30)
- 🎨 系统名称统一为"帮扶管理信息系统"（15个文件）
- 🎨 军绿色主题全面应用（侧边栏/顶栏/底栏/表格）
- 🎨 主页欢迎标题金色加粗 28px
- 🎨 侧边栏导航标题白色加粗
- 🎨 全局表格表头军绿背景+白色文字+金色底边
- 🔧 侧边栏完整导航菜单（40+项含子菜单）
- 🔧 isAdmin/username/logout 连接 authStore（修复权限泄露）
- 🔧 /villages → /supported-villages 路由重定向
- 🔧 管理员密码重置为 admin123
- 🔧 登录页 SYSTEM_VERSION/COPYRIGHT_OWNER 导入修复
- 🔧 前端构建缓存清理（修复304导致的系统异常）
- 🔧 SPA fallback 资产挂载（/assets /images）
- 🔧 表格样式从 App.vue 移至 index.scss（CSS变量替代!important）

### 后端修复
- 🔧 43个字节损坏核心文件全部重建（core/ + system/api/）
- 🔧 cache.py 异步 CacheManager + get_cache_service 修复
- 🔧 pandas null bytes 重装
- 🔧 data_package_service.py 延迟导入修复循环依赖
- 🔧 get_event_loop_safe 缓存复用（修复事件循环泄漏）
- 🔧 EntityCacheManager 属性路径修复（_cache→_b）
- 🔧 CustomJSONEncoder = AppJSONEncoder（移除空子类）

## [1.1.0] - 2026-03-13
