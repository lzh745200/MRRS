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


