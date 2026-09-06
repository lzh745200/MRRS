# 002 ZCode 会话真实 HTTP 探针 R1–R3 — 通行码改绑/路径双源/模板下载三缺陷修复

- 状态: done
- 波次: w14-deep-probe（独立会话，编号独立于 001 的 R1-R4 与 R14-R16）
- 日期: 2026-09-05
- 触发: 用户「持续逐模块深探与修复循环」

## 本会话 R1：组织通行码注册 / refresh 轮换 / 异步导出 / 权限包 / 数据同步导出
- 🐛 **组织通行码注册后新用户无法登录**（阻断级）：组织通行码记录 machine_code
  是占位串 `ORG-<org>-<rand>`，`activate_machine_code` 只置 active+user_id
  不改绑 → 登录侧 `verify_user_machine` 按"记录.machine_code==当前真实机器码"
  恒 False。修复 `30251579`：activate 增 `current_machine_code` 参数完成改绑
  （锁定测试 test_coverage_gap_batch3 两用例）。
- 🐛 **data-sync 下载端点路径双源**：相对 `Path("data_sync")` vs 服务写
  `get_app_data_dir()/data_sync` → 打包环境下载恒 400/404。修复 `30251579`：
  下载改用 `data_sync_service.sync_dir` 同源；test_data_sync_route 3 处
  chdir 接缝迁移。探针 25/25 全绿。

## 本会话 R2：审批流 / 报表模板 / 地图离线瓦片 / 消息待办 / 监控健康
- 🐛 **报表模板下载 500**：创建端点 `fields: Optional[str]` 允许任意字符串，
  下载端点假定 dict 数组直接 `.get` → 逗号字符串形态 AttributeError→500
  （用户可触发）。修复 `4e9072b0`：下载前归一化三形态（逗号串/字符串数组/
  dict 数组）。
- 🐛 **CI #73 覆盖率差 1 行**：归一化的 `isinstance(str)` 分支仅当 fields 存为
  JSON 引号字符串时可达（safe_json_loads 对逗号裸串自行切列表）→ 463 行恒
  count-0 → 99.9973% < 100 门禁。修复 `ec82653e`：补 JSON 引号串形态用例。
- ⚠️ 排查教训：本地用系统 python(starlette 0.36.3) 误复现 data_packages 4 例
  失败——解释器用错假象；CI/venv 用钉死的 1.3.1，venv 全量 xdist 10684 全过。
  **后端验证必须用 .venv/Scripts/python**。
- 探针 41/41 全绿（审批全生命周期含 submit-auto、地图/瓦片、消息未读/已读、
  待办 CRUD、监控健康、审计日志 /system/audit/logs）。

## 本会话 R3：经费状态机 / 村年度板块 / RBAC / 系统配置调度 / 数据包链
- **零产品缺陷**，五链路全部按设计工作（探针 47/47 全绿）：
  - 经费状态机守卫全部正确：approve 需 ≥1 附件；allocate 需 contract+
    allocation_order 两附件（缺则 400 带明细）；终态后流转 400；completed 全链
    planned→approved→allocated→in_use→completed。
  - 村年度板块：连字符 section（force-investment）保存/回读（camelCase：
    totalPopulation）、未知 section 400、validate、copy（from_year/to_year 别名
    兼容）、delete。
  - RBAC：角色 id 为顶层 `role_id` **UUID 字符串**；assign/成员/权限查询/更新/
    删除全通。
  - 系统配置挂 /system/config；备份计划回读 camelCase（keepCount/nextRun）。
  - 数据包链：preview→export→import(org_id 走 **query** 参数) 回环通；空组织表
    时 get_org_with_fallback 穷尽回退 → 正确 fail-loud 400（非缺陷）。
  - 前端契约核验：ReceivePackage 本地导入不传 org_id 是正确设计（后端回退
    current_user.org_id property）。

## CI 记录
- #69-73 红→绿轨迹：lint(prettier 漏跑, `090e377`) → security(npm audit
  postcss-selector-parser DoS, `f3f6e8c`) → coverage(463 行, `ec82653`)。
- #74 五 job 全绿（backend-test/frontend-check/lint/security/static-analysis）。

## 本会话 R4：政策/学校/项目/工作日志/通知/2FA/资料/报表订阅/模板上传确认
- 🐛 **模板上传确认链两缺陷**（R2 病根的第三/四处消费点）：upload→
  _parse_template_excel 直接 field.get('db_field') — 字符串形态 500；且缺
  db_field 时解析出 {'': value} → 确认导入**零写入**（静默丢数据，比 500
  更隐蔽）。修复 `542b7959`：提取 _normalize_template_fields 共享 helper
  （下载/上传两消费点统一），字符串形态 excel_header=db_field=该串，dict
  形态缺 db_field 以 excel_header 兜底；锁定测试=逗号模板 confirm 真实落库。
- 契约核验（非缺陷）：2FA verify 字段名 `token`（非 code）；/users/me 返回
  `name`（非 full_name）；报表订阅挂 /reports/subscriptions（data 包无额外
  前缀）；政策/学校/项目/工作日志(日历+月度总结)/通知偏好全链 200。
- 探针 40/40 全绿；回归 215+709 passed；CI #76 五 job 全绿。

## 本会话 R5：乡村工作台/奖学金导入/增量三端点/地图坐标/update-logs/消息推送联动
- 🐛 **奖学金导入全链坏死**（阻断级，无测试覆盖致长期存活）：按
  ScholarshipStudent(name/student_id/school_name) 构造，真实列是
  student_name + 必填 school_id FK → 每行必抛 TypeError → imported=0。
  修复 `dbc4319b`：学校名查 School 解析 school_id、学号并入 remarks；
  `f8643835` 学校解析补 is_active 过滤（软删扫描门禁 + 语义）。
- 🐛 **乡村工作悬挂 village_id → 500**：FK 目标是遗留 villages 表（前端
  下拉由 /rural-works/villages 按名称 upsert 同步），悬挂 id 触发未处理
  IntegrityError。修复：服务层 _validate_village_id（create/update）+
  路由 ValueError→400 带指引。
- 契约核验（非缺陷）：增量三端点（detect-changes/试运行 import）、地图
  坐标写入与 200 越界 400、update-logs 挂 /system（空库 latest 404）、
  审批提交 → 未读数联动、奖学金按列位置解析（B 列姓名起）。
- 探针 32/32 全绿；锁定测试 test_r5_probe_locks 5 用例（真实内存库）；
  回归 334+89 passed；CI #79 五 job 全绿。

## 本会话 R6：合同链/转账凭证链/数据同步冲突解决/subordinate 级联
- **零产品缺陷**（探针 30/30 全绿）：
  - 合同链：创建→列表→详情→更新→重复编号 400→付款登记→明细可见。
  - 转账凭证链：创建（预算余额校验内）→ 超额 400 → 确认 → 附件 → 划转台账。
  - 数据同步冲突：导出→skip 导入→本地修改制造差异→manual 重导入→冲突列表
    →resolve-conflict(取本地) 全链通（strategy 为 Form 字段）。
  - subordinate 级联：allow_subordinate_generation=True 通行码生成/列表标记/
    注册→登录（含 R1 改绑修复回归）全通。
- ⚠️ 排查教训：并行会话已将 get_app_data_dir() dev 分支改为固定指向 backend
  （修"CWD 决定数据目录"问题），探针必须用官方接缝
  BUMOFU_BACKEND_DIR_OVERRIDE=临时目录 实现隔离，否则 data_sync/backups
  写入项目目录。SSE 后端无实现（消息实时性为前端轮询），报表订阅无生成端点
  （仅 create/list/detail）——两项记为观察项非缺陷。

## 本会话 R7：前后端契约交叉核对 + 帮助文档/考核评估/成效评估长尾
- **契约核对（程序化）**：导出后端 797 条路由，正则通配匹配前端 334 个去重
  API 调用路径 → **0 处真实断裂**。4 条疑似均为误报：3 条 `${qs}` 查询串
  模板被当路径段（/secrets/* 后端路由实际存在）+ 1 条 blobDownload.ts 的
  注释示例（/data/download）。
- **零产品缺陷**（探针 15/15 全绿）：帮助文档 30 篇（列表/详情抽样/搜索/
  分类过滤）；考核评估（村庄得分/异常/趋势预测/村对比 village_ids 逗号
  传参）；成效评估（双年 evaluate→report(year)→compare(year1,year2)→
  rankings(year)）。
- ⚠️ 契约形态观察（非缺陷，前端已适配）：部分端点返回 {success,data} 无
  code 信封（如 /system/help/articles）；effectiveness 系列年份均为必填
  Query。

## 本会话 R8：并发场景探测 + 前端 Playwright E2E 复活
- 🐛 **并发备份同毫秒唯一键冲突 → 500**：三并发同毫秒创建，毫秒后缀仍相撞
  （R3 修复未覆盖并发窗口）。修复 `008b2804`：文件名/config_key 追加 uuid4
  短码（清理为 DB 记录驱动，无文件名解析，安全）。
- 🐛 **通行码注册并发竞态**：verify(读 pending)→create_user→activate(写)
  非原子 → 双注册均成功、2 用户共用一条机器码记录。修复：activate 改单条
  UPDATE 原子认领（rowcount 判定），认领失败删刚建用户 + 400。
- 🐛 **E2E 套件结构性坏死**：死代码清理(af388677)误删 helpers.ts（8 个
  spec 导入即崩）+ global-setup 密码过期 + 首登强制改密未适配 + 5 个 spec
  选择器腐化。修复：恢复 helpers、global-setup 重写（CSRF 配对改密自适应
  + E2E 专用密码经 TEST_PASSWORD 传递）、语义选择器替换。**全量 150/150**。
- 并发探针复跑 12/12（同记录 10 并发写/审批竞态/并发备份/注册竞态/并发导入
  全部符合预期语义）；后端回归 355 passed；CI 保持绿。

## R8 追记（2026-09-06）：E2E 适配与 CI 时钟黑洞
- E2E 适配三轮迭代：① 首登强制改密自适应（改密 PUT 是 CSRF 保护路径，
  需先取 csrf-token 配对）；② E2E 专用密码不得含用户名（PasswordPolicy
  拦"E2e#Admin2026!"→'密码不能包含用户名'）；③ permission-packs 硬编码
  Admin@2026 改读 TEST_PASSWORD。全量 E2E 150/150。
- 🐛 **覆盖率墙钟黑洞**（CI #84）：/backup/schedule 的"已过 02:00 则 +1 天"
  分支内联端点，是否执行取决于测试运行的墙钟——本地 02:00 前覆盖、CI(UTC)
  02:00 后缺 1 行 → 门禁随机红。修复 `548d3dc8`：提取 _next_daily_2am
  纯函数 + 三固定时间确定性测试。CI #85 五 job 全绿。

## 本会话 R9：E2E 纳入 CI + 长尾模块扫尾
- **E2E 纳入门禁**：pr-checks 新增 e2e-test job（Linux chromium，config 跨
  平台化——Win 用系统 Edge/venv python，Linux 用 chromium/系统 python；
  后端 webServer 由 workflow pip install 依赖后直启）。**首跑 150 用例
  一次通过，CI 六 job 全绿**（`28aeb85b`）。
- **零产品缺陷**（长尾探针 22/22 全绿）：数据质量（/data-quality 挂载前缀
  特例）、分析五端点、离线地图状态/清理、机器码管理 CRUD（录入/列表/校验/
  吊销）、**分片上传全链 init→chunk→merge 内容一致**（契约：chunk_size 由
  服务端决定，客户端须按响应值切片）、通知偏好 PUT/回读。
- 教训：配置文件做转义敏感的字符串替换时，用行号切片或整体重写，
  不要用跨行锚点匹配（本次 playwright.config 两处补丁三次才落对）。

## 收官（2026-09-06）：三件事落地
1. **探针固化**：9 轮探针脚本 → `backend/tests/probe/`（run_all.py 总运行器
   + README 隔离契约），固化后全量复跑 9/9 PASS；pytest 零收集不影响套件
   （`674191fe`）。
2. **订阅工单**：报表订阅"可创建、无消费方"半成品立为工单 003（三方案
   决策项待产品拍板），不做猜测性实现。
3. **v1.11.6 发布物实物核验**：从 GitHub Release 下载三件套并逐一比对
   SHA256SUMS——exe / electron deb / standalone deb **全部 MATCH**
   （下载共 ~413MB，deb 曾两次中断均以断点续传完成）。
   真机 UI 安装抽验仍建议人工执行一次。
