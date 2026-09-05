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
