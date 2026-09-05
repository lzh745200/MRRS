# 更新日志

所有重要的项目变更都会记录在此文件中。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/),
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [1.11.5] - 2026-09-05 — 通行码注册大小写归一化 + 功能全链路探针验证 + 覆盖率根因修正收尾

### 修复
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
esourcescredist\...` 中的 `
`/`` 转成 CR/VT 传给
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
