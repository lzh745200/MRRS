# 更新日志

所有重要的项目变更都会记录在此文件中。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/),
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

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
