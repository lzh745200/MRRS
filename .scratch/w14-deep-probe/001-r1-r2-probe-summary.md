# 001 深度逐模块 HTTP 探针 R1–R4 — 注册 refresh 契约修复 + 业务/辅助模块全通过

- 状态: done
- 波次: w14-deep-probe
- 日期: 2026-09-05
- 触发: 用户「不许停下」→ 持续逐模块真实 HTTP 验证循环（goal-2d04c23b）

## R1 发现与修复
- 🐛 `/auth/register` 返回 access 却无顶层 `refresh_token`（login 有）→「注册即登录」
  契约不一致、记住登录 refresh 持久化分支对新会话恒缺失。
- 修复: commit `63e7b1b` — `auth.py` register_user 改 `create_token_pair`（含
  token_version 声明），LoginResponse 顶层返回 refresh_token；`test_auth_auth_api.py`
  两条注册成功用例改 mock create_token_pair 并断言 refresh；CHANGELOG 1.11.5 补条目。
- 验证: auth 相关 63 passed；flake8 app 0；隔离实例(probe_r1, 8004) HTTP 全链路：
  组织通行码注册 → 响应含 refresh → /auth/refresh 200 → 旧 refresh 重用 401 → 新
  access 可用(machine-info 200)；机器码/组织绑定落库正确（machine_codes org 绑
  user_id=3、users.organization_id=1）。

## R1 其他通过项
- 组织通行码全链（校验码→生成→注册 level-2 回退）PASS
- 异步导出 villages（force_async → status completed → download 5599B → tasks 列表）PASS
- 权限包 export→import 预览→confirm 落库（organizations_updated=1 等）PASS
- data-sync /export（Query 参数，非 body）→ 包 4249B + download 200 PASS

## R2 业务模块（probe_r2, 8005）— 全部 PASS 无缺陷
- 列表信封: supported-villages/funds/projects/policies/schools/organizations/users/
  work-logs/menus-accessible 全 code=200
- 政策导出 excel/pdf/wps 200；经费 excel（/export/funds）200
- 普通用户（通行码注册,refresh 已含）: policies 列表/创建(id 11)/详情/删除 全 200
- 备份: POST /system/backup 创建 backup_id=22 → 列表含该项 200

## 备注
- 探针均用 VACUUM INTO 克隆 dev 库 + 重设 admin 密码，端口 8004/8005 隔离实例，
  完成后产物与进程全部清理；工作区 git 0 残留。

## R3（8006, GET 扫测）— 无 5xx
消息/未读计数/提醒/系统配置/审计日志/登录尝试/导出审计/异步任务/反馈/数据包/同步状态
等全部正常返回；数个 404 为路径猜测噪音（docs 未暴露 OpenAPI，无法自动发现）。

## R4（8007, 前端 API 层收割真实端点 GET 大扫，~90 个）— 0 失败
覆盖：messages/notifications-preferences/reminders/audit(logs+login-attempts+exports)/
data-packages/import-history/search/help(categories,articles,system-info)/todos/
system-tasks(+stats+running-count)/backup/machine-code(admin-list,machine-info,org-list)/
map(config,county-coords,regions,tile-info,distances)/offline-map-status/sentiment/
effectiveness/approval(workflows+tasks all/pending/mine/history)/data-tier(stats,summary,
archives)/secrets(versions,status)/zero-trust(assessment,policies,events,stats)/validation/
error-reports(+stats)/i18n(languages,current)/update-logs(+latest+check-version)/env-check/
data-sync-logs/经费统计(summary,utilization-rate)/supported-villages(export modules+formats,
filter-options,templates-all)/policies(options levels+statuses,categories+tree,statistics)/
projects-stats/organizations(tree,subordinates,types-options,statistics)/schools(statistics,
options)/user-management-roles/system-monitor(snapshot,database-size,resources,alerts,
alerts-history,api-stats)/two-factor-status/rural-works(statistics,villages,years)/work-logs。
- 全部真实端点 200；guess-404 仅 3 处（/dashboard、/reports/analytics、
  /organizations/my-organization——前端另有拼接/子前缀）。

## 总结（R1–R4）
- 唯一发现的业务缺陷：注册响应缺 refresh_token → 已在 R1 修复（commit 63e7b1b，
  随 v1.11.5 发布，CI 5/5 绿）；R2–R4 无新增缺陷。
- 隔离实例与产物每次探测后清理；工作区 git 0 残留；记录同步提交入库。

## R5（8008, 写路径探针）— 无后端缺陷
- todos 全链（create id=2 裸对象返回 → detail → patch toggle completed=true →
  put 改名 → delete 200 → get 404）PASS；注意该接口返回裸对象无信封（前端按
  unwrap 读取，契约一致）。
- 错误上报：POST /system/error-reports 建 report_id=1 + 列表可见 PASS。
- 提醒：POST /reminders/scan 200（新增 0 条，无到期数据属预期）；列表 200。
- 消息：mark-read 空表 422 属契约（min_length=1，前端只传真实 id）；mark-all-read
  200（18 条已读）；unread-count 归 0；本轮无未读可测单条标记。
- 通知偏好：GET 嵌套+扁平双结构（扁平为端点附加字段）；PUT 契约=扁平字段
  （UpdateNotificationPreferencesRequest），service 落模型真实列
  （email_approval 等 9 列）；R5c 精确验证 flip False → flat/nest 双 False →
  restore True 全 PASS。早期误报源于探针按嵌套载荷 PUT（未知字段被忽略），非缺陷。
- 搜索 GET /search?q=学校 → 200 空结果（无匹配数据）。
- 结论：R5 无新增缺陷、无代码改动。

## R6（8009, 学校/乡村工作写路径 + PII + 软删除）— 无功能缺陷
- 学校全链：POST /schools 创建（信封 data.id=1）→ 详情 → PUT 更新 student_count 150
  → 列表 1 条 → DELETE 软删 → 默认列表 0 → admin ?include_deleted=true 可见且
  is_active=false/is_deleted=true。
- PII 加密端到端：contact_phone 写入后 DB 原文为 enc.v1: 前缀密文；详情接口读回
  明文一致（EncryptedText 透明加解密验证通过）。
- 乡村工作全链：POST /rural-works 创建（RW-890BDB65 编号自动生成）→ PUT progress/
  status（in_progress）→ 按 status 过滤列表 → DELETE → GET 404。
- 观察（无功能影响）：schools 序列化给 is_deleted/is_active（snake），未提供
  isDeleted（camel）；全前端无该字段消费者（grep 0 命中），AGENTS「双键」表述
  在该模块不成立，仅记录不修。
- 结论：R6 无新增缺陷、无代码改动。

## R7（8010, 项目/里程碑链）— 无功能缺陷
- 项目全链：POST 创建（201，自动编号 PRJ-20260905-XXXXXX + approval_task_id）→ 详情
  → PUT 更新 budget/status → stats → 列表 → DELETE。
- 软删语义澄清：项目 DELETE 同时置 is_active=False **且 status='cancelled'**；列表
  默认过滤 cancelled（include_cancelled）+ 过滤 is_active（include_deleted），故回收站
  视图需双传 include_deleted=true&include_cancelled=true（实测双传后 total=9 含全部
  软删行；只传 include_deleted 仍 6）。前端 projects/List.vue 回收站分支本就双传
  （代码 420-425 行）→ 前后端语义一致，非缺陷。
- 里程碑链：POST /projects/{id}/milestones（Date 序列 YYYY-MM-DD）创建 → 列表 →
  PUT status=completed/actual_date → DELETE 全通过（create 为裸对象响应，信封解析
  属探针误读）。
- 日期契约：项目 start_date 等要求 YYYY-MM-DD（自定义校验，422 文案清晰）。
- 结论：R7 无新增缺陷、无代码改动。

## R8（8011, 经费预算链）— 无功能缺陷
- 预算全链：POST /fund-budgets 创建（裸 BudgetResponse，http 200 id=7）→ 按
  year+category 过滤列表命中 → summary → alerts → PUT used_amount=25000（前端兼容
  字段→executed_amount=25000.0 生效）→ DELETE → 列表不可见。
- 预算流水：POST /fund-budgets/transactions（amount=5000,purpose,date）→ GET 按
  budget_id 过滤列表 count=1 → DELETE 200 全通过。
- 结论：R8 无新增缺陷、无代码改动。

## R9（8012, 回收站闭环）— 发现并修复真实缺陷（commit 5469ff7）
- 🐛 **恢复项目后仍不可见**：项目软删把 status 置 cancelled 作回收标记，通用
  recycle_bin.restore 只回置 is_active/deleted_at → 默认列表（status!=cancelled）
  过滤 → 「恢复成功却看不见」（HTTP 实测：restore 200 后 status=cancelled、
  默认列表无）。修复：单条/批量恢复统一清除 cancelled 标记还原 planned
  （_reset_cancelled_status_marker，其它模型 no-op）；recycle_bin 模块覆盖率 100%，
  37 passed；HTTP 复验 restore 后 status=planned 且默认列表可见。
- purge 二次确认需真实密码（守卫生效）：传 Admin@12345 后彻底删除成功且记录消失；
- 经费删除守卫「仅允许删除 pending 状态经费」属状态机设计（dev 经费均非 pending
  → 400 正确），非缺陷；经费回收站仅对可删（pending）记录有意义。
- 学校/村庄恢复闭环全部 PASS（schools 恢复回默认列表、purge preview 级联统计 0）。

## R10（8013, 数据包回环）— 无功能缺陷
- 全链验证：POST /data-packages/export（org 绑定 + path=/1/ 后）200 生成 package
  （EXP-ORG-MAIN-…zip）→ GET download 200（416B）→ POST /import 200 建接收包
  （status=validated）→ GET preview 200 → POST confirm 200（imported_counts {} 空包
  语义正确：dev 数据未归属组织）→ list/received 均 200；全程无 5xx。
- 一次 403「无权限访问组织数据」溯源为探针直插组织缺 path（组织树按
  path LIKE 计算层级，根组织 path=/1/）→ 服务语义正确，非缺陷；one-click-report
  走 get_org 回退不受影响（200 zip）。
- 结论：R10 无新增缺陷、无代码改动。

## R11（8014, 审批流程链）— 无功能缺陷
- 概览 GET /approval（root）200；项目创建自动生成审批任务（project 新增任务
  id7/8，entity_type=project/entity_id 关联）；GET /approval/tasks/all 与
  /tasks/pending 返回任务列表（data 为数组而非 items —— 探针首轮解析误读）。
- 通过：POST /approval/tasks/7/approve {opinion} → 200 approved（overview
  approved_count=1）；拒绝：字段契约为 opinion（comment 被忽略→400「驳回必须填写
  原因」守卫正确）→ 200 rejected（rejected_count=1）；pending_count 同步递减。
- 注意：项目新建审批后的实体状态为 draft（创建流程落 draft，通过后不自动改
  planned——单机版审批回写语义，与前端流程一致）。
- 结论：R11 无新增缺陷、无代码改动。

## R12（8015, 系统配置/配置包/批量操作）— 无功能缺陷
- 系统配置：GET /system/config（4 键）→ /export/json（200 json）→ /defaults 200；
  PUT 键更新无目标键可测（配置集小，跳过）。
- 配置包：GET /system/config-packages（空列表 200）→ POST …/export 200（JSON
  2572B，内容为配置快照）→ 列表可见。
- 批量恢复：项目软删 2 条 → POST /projects/batch-restore {ids} → 「已恢复 2 条」、
  默认列表可见（cancelled 标记随 R9 修复一并清除）。
- 村庄批量删除语义澄清：POST /supported-villages/batch-delete（带 confirm_password
  密码二次确认，缺密码 400 守卫正确）= 软删（is_active=0/deleted_at）+ 生成
  「帮扶村批量删除：N 条」审批任务（approval_task_id）；彻底清除走审批/回收站
  password purge。与「回收站可恢复 + 审计留痕」设计一致，非缺陷。
- 结论：R12 无新增缺陷、无代码改动。

## R13（8016, 导入模板/预览/校验管线）— 无功能缺陷
- 模板下载 GET /import/template?entity_type= 五种实体（supported_village 9277B/
  project 8646B/fund 8491B/school 8646B/policy 8369B）均 200 xlsx。
- 空模板预览 POST /import/preview（multipart）→ 结构化结果 total 0 行 200；
- 无效文件（junk.xlsx）：预览 → 400 清晰文案（非 500）；导入 /import/entities →
  200 信封 + error_count=1 + 行级 errors（IMPORT_999，内容为文件级解析原因——
  按项目既定策略属面向用户的导入反馈，不出 HTTPException detail）；
- /import/history 200。
- 结论：R13 无新增缺陷、无代码改动。

## R14（8017, 经费状态机链）— 发现并修复前端缺陷（commit cba24f8）
- 后端守卫验证正确：申请→(需附件)审批→(需 contract+allocation_order 类别文档)
  拨付→使用→完成→审计；非法流转恒 400「状态流转非法：当前状态 X，不允许变更为
  Y」；缺文档 400 提示含缺失类别中文名。
- 🐛 缺陷（前端）：funds/Detail.vue 上传 category 放 FormData（后端参数为 Query）
  → 恒落 other；界面无类别选择 → 真实用户无法满足拨付文档要求（拨付按钮死路）。
  复现关键证据：category 经 query（?category=contract）上传后 allocate 200
  「经费已拨付」；FormData 上传恒 other。
- 修复：Detail.vue 统一 CATEGORY_LABELS + 「文档分类」下拉（默认 other）+
  category 经 axios params(query) 提交；DetailCov 适配与新增用例（65 passed）；
  vue-tsc 0。
- 结论：R14 后端状态机无缺陷；前端上传链路缺陷已修复。

## R15（8018, 帮扶村年度板块）— 发现并修复路由顺序缺陷（commit 42f8669）
- yearly 读取/复制通过：GET …/yearly/2025 200（10 板块含 force-investment 等）；
  POST yearly/copy 2025→2026「已复制 6 个数据组」；GET 2026 含全部板块。
- 🐛 POST …/yearly/{year}/validate 恒 400「未知的数据分类: validate」——路由顺序：
  动态段 …/{year}/{section}（保存）先注册于 /validate，FastAPI 匹配把 validate 当
  section；前端 validateYearlyData 即此 URL → 年度校验功能不可用。
  修复：validate_yearly_data 整块前移注册 + 顺序警示注释；村庄 API 测试 108
  passed；HTTP 复验 validate 200 → {valid:false, errors:[板块未录入…], warnings}
  真实语义；section 保存端点无回归。
- 附件列表（income/population/industry/infrastructure 四板块）200。
- 结论：R15 路由顺序缺陷已修复。

## R16（8019, 机器码自助重置通道）— 无功能缺陷
- loopback 机器码含 verification_code；verify-machine-code 正确对 200 is_valid=true；
  错误码 200 data.is_valid=false（信封语义正确，探针首次断言误读）。
- 公开重置安全基线全验证：管理员被拒 403（含「恢复出厂密码」引导）；普通用户全链：
  重置 → 返回 16 位强随机新密码（仅响应返回）→ 旧密码登录 401 → 新密码登录 200
  （提示「首次登录请修改密码」must_change_password 置位）；操作前须 CSRF
  （cookie+raw header，公开端点同受保护）。
- 结论：R16 无新增缺陷、无代码改动。

## R17（CI 失败构建修复：security job）— 已修复并全绿（commit 96c7257）
- 现象：并发会话推送 6c69172/5df0faf 后 PR Checks 失败；逐 job 定位仅
  **security** 失败（其余五项含新增 e2e-test 全绿），失败步骤为
  “Frontend dependency audit”（npm audit --audit-level=high 阻断）。
- 根因：新增高危公告 **GHSA-2883-xcg3-v3hh**（js-yaml 4.0.0–4.3.1，
  maxTotalMergeKeys 对空合并源不限 CPU）。
- 修复：npm audit fix --legacy-peer-deps（直连因 vite peer ERESOLVE 失败，
  CI 亦用 --legacy-peer-deps）→ js-yaml 4.3.2；lockfile 版本字段同步 1.12.0。
- 验证：npm audit --audit-level=high exit 0（余 3 moderate 为 vitest 链，
  低于阻断线）；npm ls js-yaml 4.3.2；lint:check 0；**前端全量 vitest
  301 文件 / 6045 用例通过**；CI PR Checks **6/6 success**。

## R18（8020, 跨机器注册新语义）— 发现并修复真实缺陷（commit 25e65658）
- ✅ 通过：HMAC 自验证注册（内置常量密钥形态）200，记录 active 且绑定用户；
- 🐛 **同机第二个用户注册必挂**：组织通行码自注册 400「注册失败，请稍后重试」，
  服务端日志 IntegrityError: UNIQUE constraint failed: machine_codes.machine_code
  （activate_machine_code 无条件把 org 占位记录改绑为当前机器码，而首用户记录已
  占用该机器码）。同机多用户（单机版主场景）100% 无法用组织/自验证通行码注册。
- 修复（machine_code_service.py）：① 激活前探测占用，冲突则保留 ORG-/HMAC- 占位
  机器码；② HMAC 建记录占用时改用 HMAC-<hex>；③ verify_user_machine 对
  organization_id 非空或 ORG-/HMAC- 前缀记录放行登录（机器通行码仍严格比对）。
- 回归：新增 4 例 + 既有 rebind 用例补前提，machine-code 相关 256 passed、
  flake8 app 0；HTTP 复验：组织自注册 200 → 自动建组织并绑定 → 记录 ORG- 占位
  active → 该用户登录 200；单位名不符负例返回通行码无效引导（不再兜底 400）。


## R19（8021, 双因素认证全链路）— 发现并修复两处高危真实缺陷
- 探针 24 项断言，全程真实 HTTP + 真实 DB 校验；修复前 23/24，修复后 **24/24 全绿**。
- 🔴 **缺陷 1（认证绕过）：2FA 中间态令牌可直接当正式访问令牌用。**
  `/auth/login` 在 2FA 挑战分支用 `create_token_pair(..., extra_claims=
  {"two_factor_pending": True})` 签发 `temp_token`，其 `type` 仍是 `"access"`；
  `get_current_user` 只查黑名单 + token 类型，**不认这个中间态声明**。实测仅凭密码
  （无需 TOTP）拿 temp_token：`GET /auth/me` 200、`GET /users` 200、`GET /funds`
  200、`POST /two-factor/disable` **200（二次验证被永久关闭）**。
  修复：`app/core/security.py` 在读库前拒绝带 `two_factor_pending` 的令牌。
  复验：四个端点 + disable 全 401（「二次验证未完成，请先完成双因素认证」），
  status 仍为 enabled=true。
- 🔴 **缺陷 2（恢复码可无限复用）：`backup_codes` 消费从未落库。**
  列是裸 `Column(JSON)`，`verify_login` 用 `list.remove(token)` 就地改 ——
  SQLAlchemy 对裸 JSON 列的就地修改不产生 attribute 事件、不生成 UPDATE，
  `safe_commit` 静默无效。实测：同一备用码连续两次登录均 200，DB 码数恒为 10。
  修复：列改 `MutableList.as_mutable(JSON)`。复验：用码后 DB 10 → **9**，
  该码从库中消失，二次使用 401。
- 已确认无缺陷项（不误报）：enable 返回 secret/二维码 dataURL/10 个恢复码；
  错码 verify 400、重复 enable 400、无配置 verify 400、未认证 enable 401；
  伪造 temp_token 401、普通令牌冒充 temp 401、错验证码 401、temp_token 成功后被
  吊销 401；正确 TOTP 换取正式双令牌且 `/auth/me` 可用；备用码跨会话计数正确；
  disable 后登录直通。
- 探针自身更正：一度误判「2FA 设置页无 UI 入口」——PowerShell 的
  `-Path "frontend/src/**/*.vue"` 中 `**` 只匹配一层，漏掉了三层深的
  `views/auth/Profile.vue`；实际入口为「个人中心 → 账户安全 → 绑定MFA →
  `/profile/two-factor`」，**非缺陷**，未改动任何前端文件。
- 回归锁定：新增 `backend/tests/unit/test_two_factor_security_r19.py`（8 例，含
  文件型 SQLite 的真实落盘断言——内存库会掩盖缺陷 2）。


## R20（8022, 权限配置包 export→download→import→confirm 往返）— 无功能缺陷
- 探针 16 项断言全绿，覆盖用户最初投诉的「导出权限包却没有生成」这一条主线。
- 语义往返（真实 HTTP + 真实磁盘 + 真实 DB 状态）：
  创建角色 `R20_ROUNDTRIP_ROLE` → 导出（**文件真实落盘** 1375B，与响应
  `file_size` 一致；ZIP 内 7 个条目，`data/roles.json` 确实含该角色，非空包）
  → 删除该角色（列表确认为空）→ 上传预览（`role_count:1`）
  → 确认导入（`roles_created:1`）→ 角色**已恢复**（往返语义成立）。
- 守护项全部有效：篡改 `data/roles.json` 的包直接 `/confirm` 被 400
  「内容校验失败」（未预览 + 校验和不匹配双重拦截），注入的 `INJECTED_ROLE`
  未落库；非 `.zip` 上传 400；下载路径穿越 404；未认证导出 401/403。
- 确认导入后包文件被清理（`permission_package.py` 的 `finally: os.unlink`），
  再下载得 404 —— **属设计行为**（源码注释「Clean up the uploaded file after
  import, success or failure」），非缺陷。
- 观察项（非缺陷）：开发库与原库的 `rbac_roles` / `rbac_user_roles` /
  `rbac_role_permissions` / `permission_packs` 四表均为 0 行 —— RBAC 角色由
  `POST /rbac/roles` **按需创建**，代码中无启动期种子；因此首次导出的包
  `roles:[]` 属**源数据为空**，不是导出丢数据。真正的往返验证已用自建角色证明。


## R21（8023, 经费合同 /contracts 全链路）— 发现并修复三处真实缺陷
- 探针修复前 15/17 → 修复后 **17/17 全绿**（真实 HTTP + 真实 DB 状态校验）。
- 🐛 **缺陷 1（静默丢数据）：合同附件把用户备注整体覆盖。**
  `POST /fund-lifecycle/contracts/{id}/attachments` 把附件数组 JSON 写进
  `fund_contracts.remarks` —— 而 `remarks` 就是「新建合同」表单里的**备注**列。
  实测：创建时填「甲方要求分三期付款，验收后付尾款」→ 登记 1 个附件后详情与列表
  的 `remarks` 变成 `[{"url": "/uploads/r21/contract_scan.pdf", ...}]`，**用户原文
  丢失且不可恢复**；列表接口同样把这段 JSON 当备注出站。
- 🐛 **缺陷 2（反向清空）：编辑备注会清空全部附件。**
  `PUT /contracts/{id}` 传 `remarks`（编辑表单的自然行为）后，
  `GET /contracts/{id}/attachments` 由 1 条变 0 条 —— 附件与备注共用一列，
  写入即互删。
- 🐛 **缺陷 3（用户输入错报成服务端故障）：关联项目/经费不存在时报 500。**
  `POST /contracts`（`project_id: 999999` / `0` / `-5`）与
  `POST /transfer-vouchers`（`fund_id: 999999`）直接 INSERT，SQLite 外键失败抛
  `OperationalError: FOREIGN KEY constraint failed` → 500「服务器内部错误」
  （日志 `app.core.transaction: safe_commit: commit failed` 定位）。
- 🐛 **缺陷 4（同资源两种口径）：无项目的合同能创建、能更新，详情却恒 400。**
  `ContractCreate.project_id` 可选（前端从菜单进入合同管理时 `route.query.project_id`
  缺失，实测创建成功 `project_id=None`），但详情端无条件调 `_get_project_or_403`
  → 400「缺少有效的项目ID，请从经费列表中选择具体项目进入」；同一资源的
  PUT/DELETE/附件端却无此校验。划转凭证详情同样问题。
- 修复：
  ① 新增 `fund_contracts.attachments_json` 专列（模型 + 迁移
  `contract_attachments_001` 含脏数据搬迁），附件写自己的列，`remarks` 只存备注；
  `_contract_attachments` 对老数据只读兼容 + 读到即搬迁（附件入新列、remarks 清空），
  `_contract_to_dict` 不再把历史 JSON 当备注出站；
  ② 新增 `_require_related_exists` 前置校验 → 404「关联项目/经费不存在」；
  ③ 合同/凭证详情仅在确实挂了项目时才做 404/403 校验。
- 复验（HTTP）：备注上传附件后保持原文（详情 + 列表）、改备注后附件仍在（1 条）、
  历史脏数据（remarks 整体是附件数组）被识别并搬迁且不再回显 JSON、
  无项目合同详情 200、坏项目/坏经费 404（不再 500）、不存在合同仍 404。
- 回归：新增 `tests/unit/test_contract_attachments_r21.py`（23 例）；
  `test_fund_not_found` 旧断言 200 属"内存测试库未开外键约束"的假通过，已改 404；
  `app/api/v1/fund_lifecycle.py` 与 `app/models/fund_lifecycle.py` 可覆盖集 100%；
  flake8 --max-complexity=16 对改动文件 0。


## R22（8024, 全端点外键扫射 + RBAC 事务出口）— 发现并修复两类系统性缺陷
- 做法：先用进程内 schema 内省列出**全部 36 个带 `*_id` 字段的 POST 端点**，
  再按模型字段类型合成"能过校验的最小 payload"、把每个 `*_id` 一律喂 99999999，
  最后看谁返回 5xx。这是把 R21 的单点发现（合同关联不存在 → 500）铺成一次
  系统性排查，而不是逐个模块碰运气。
- 🔴 **缺陷 1（8 个端点）：关联 ID 不存在 → 500/503。**
  命中：`/funds`、`/funds/apply`、`/fund-budgets/transactions`、
  `/fund-lifecycle/allocation-orders`、`/organizations`（parent_id）、
  `/policies/categories`（parent_id）、`/projects`（village_id，返 **503**）、
  `/user-management`（organization_id）。
  日志统一为 `sqlite3.OperationalError: FOREIGN KEY constraint failed`
  —— 注意 SQLite 把外键冲突报成 **OperationalError** 而非 IntegrityError，
  所以只 catch IntegrityError 的既有装饰器（`@handle_db_errors`）覆盖不到。
  修复：`map_db_exception` 抽为单一事实源（`core/exceptions.py`），
  `@handle_db_errors` 与新增全局 `IntegrityError`/`OperationalError` 处理器共用；
  非约束类 OperationalError 维持既有 500 语义（不动真实故障的语义）。
  复验：同一套扫射 **0 个 5xx**，8 个端点全部 400「关联数据不存在或已被删除」。
- 🔴 **缺陷 2（信息泄露，W1 #6 违规）：事务层把 SQLAlchemy 原文拼进响应体。**
  继续追"目标不存在却返回 200"的端点时发现：`POST /rbac/grant/permission`
  与 `/rbac/save-permissions`（user_id=99999999）返回 **500，响应体里带完整
  INSERT 语句、表名、列名与绑定参数**：

  ```
  {"code":500,"message":"事务执行失败: (sqlite3.OperationalError) FOREIGN KEY constraint failed
   [SQL: INSERT INTO rbac_user_permissions (id, user_id, permission, granted_by, expires_at)
    VALUES (?, ?, ?, ?, ?) RETURNING created_at, updated_at]
   [parameters: ('b0b7792e…', 99999999, 'user:read', '1', None)]"}
  ```

  根因：`app/core/transaction.py` 8 处 `DatabaseError(f"...: {str(e)}")` +
  `BatchOperation` 3 处。`test_no_error_detail_leak.py` 看不见 —— 它只认
  `HTTPException(detail=<异常变量>)` 形态，这里是 `DatabaseError(message=…)`。
  修复：`_transaction_failure`/`_batch_failure` —— 约束类 → 4xx；业务异常
  （AppError/HTTPException）原样透出但做夹带检测；其余泛化；原文只进日志。
  复验：grant/save 均 **400「关联数据不存在或已被删除」**（无 SQL）；
  `/rbac/assign/role` 传不存在角色由 500「事务执行失败: 角色(x)不存在」
  变为 **404「角色(x)不存在」**（业务文案保住、状态码语义修正）。
- 未判为缺陷的观察项（记录备查，未改代码）：
  - `POST /subordinates`（organization_id=99999999）→ 200 且落库一条
    `organizationId=99999999` 的下级实例 —— 该表无外键，语义上可能是
    "下级先注册、组织后同步"，属设计选择，未动；
  - `POST /approval/submit-auto`（entity_id=99999999）→ 200 并生成一条
    approval_task（自动通过）—— 对不存在实体生成审批任务属边界场景，
    影响有限，未动；
  - `POST /control-packages/generate`（organization_id=99999999）→ 200。
  - 开发库 `rbac_roles` 等 4 张 RBAC 表为空属源数据为空（角色按需创建），
    非导出丢数据（R20 已用自建角色证明往返）。
