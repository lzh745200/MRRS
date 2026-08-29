# API 接口文档

> **版本**:v1.10.0  **更新日期**:2026-08-29
> **定位**:系统全部 HTTP 接口的清单与调用约定——**端点清单由脚本从源码自动提取**(与代码 100% 同步),业务导读人工维护。
> **适用读者**:前后端开发者、联调与集成人员。零基础请先读《需求规格说明书》§3 理解业务流程。
> **互动文档**:后端启动后(DEBUG 模式)访问 `http://127.0.0.1:8000/docs` 可在线调试(OpenAPI)。

---

## 1. 快速统计

- **85 个路由模块 / 764 个端点**(含 auth/data/system 等子包)
- 全部业务接口位于 `/api/v1` 前缀之下(下文路径均省略此前缀)

## 2. 统一调用约定(必读)

> 详细规则见《[前后端契约规范](../前后端契约规范.md)》,此处为速查。

| 约定 | 内容 |
|------|------|
| **响应格式** | 统一包裹:`{code:200, data:{...}, message:"成功", success:true}`;列表的 data 内含 `items/total/page/page_size`;前端拦截器自动解包 |
| **鉴权** | 除少数公开接口(登录/机器码校验/公开密码重置)外,一律 `Authorization: Bearer <JWT>`;管理员接口需 admin/super_admin 角色 |
| **写操作 CSRF** | POST/PUT/DELETE/PATCH 需带 `X-CSRF-Token` 头(前端自动处理) |
| **分页** | `page`(默认 1)+ `page_size`(默认 20,上限 200);响应 `data.items` + `data.total` |
| **命名** | 路径与请求体参数 snake_case;响应体同时兼容 camelCase(中间件自动转换) |
| **数据隔离** | 绝大多数接口按登录人 data_scope 自动过滤,无需(也无法)传组织参数越权查询 |
| **软删** | 列表默认只返回 `is_active=true`;`include_deleted=true` 仅管理员有效 |
| **限流** | `/auth/login` 5 次/分、`/auth/register` 3 次/分、`/auth/refresh` 10 次/分、`/auth/csrf-token` 30 次/分 |
| **loopback 门禁** | 标注"仅本机"的接口只接受 127.0.0.1 来源(机器码校验/公开密码重置/权限包导入确认) |

**鉴权列说明**(下表自动标注):`登录`=需有效 JWT;`管理员`=还需 admin/super_admin;`仅本机`=只接受本机来源;`公开`=无需登录;标注混合时以后者为准。

## 3. 模块速查(按业务域)

| 域 | 模块(前缀) |
|----|------------|
| 认证与用户 | auth(`/auth`)、users(`/users`)、user_management(`/user-management`)、rbac(`/rbac`)、two_factor(`/two-factor`)、menus(`/menus`)、permission_packs、machine_code(`/machine-code`) |
| 帮扶对象 | supported_village(`/supported-villages`)、supported_village_export、school(`/schools`)、villages(`/villages`)、village_templates、policy(`/policies`) |
| 项目与资金 | projects(`/projects`)、project_milestones、funds(`/funds`)、fund_budgets(`/fund-budgets`)、fund_lifecycle(`/fund-lifecycle`) |
| 乡村工作 | rural_works(`/rural-works`)、rural_tasks(`/rural-tasks`)、work_logs(`/work-logs`) |
| 审批协作 | approval(`/approval`)、messages(`/messages`)、feedback(`/feedback`)、todos(`/todos`)、search(`/search`) |
| 数据治理 | data/data_packages(`/data-packages`)、data/data_reports(`/data-reports`)、data_sync(`/data-sync`)、validation(`/validation`)、data_quality、import_export、batch_operations(`/batch`)、report_templates(`/report-templates`) |
| 分析展示 | data/dashboard(`/dashboard`)、data/analytics(`/analytics`)、map(`/map`)、offline_map、effectiveness(`/effectiveness`)、assessment(`/assessment`)、ai(`/ai`)、ai_enhanced(`/ai-enhanced`) |
| 组织协同 | organization(`/organizations`)、subordinate_registry(`/subordinates`)、subordinate_reports(`/subordinate-reports`)、control_package(`/control-packages`)、org_module_policy(`/org-policies`)、permission_package(`/permission-packages`) |
| 系统安全 | system/audit、system/zero_trust、system/backup、encryption、monitoring/secrets、monitoring/data_tier、system/health 等 |

## 4. 端点清单(自动生成)

<!-- 由 scripts/docs/extract_api_endpoints.py 自动生成, 共 85 个模块 / 764 个端点。
     业务说明为人工维护部分; 重新生成仅覆盖端点清单, 勿整文件覆盖。 -->

### ai.py — AI智能分析 `/ai`

| 方法 | 路径 | 说明 | 鉴权 |
|------|------|------|------|
| GET | `/ai/status` | 获取AI服务的运行状态 | 登录 |
| POST | `/ai/analyze` | 执行AI数据分析 | 登录 |
| POST | `/ai/recommendations` | 获取基于上下文的智能推荐 | 登录 |
| GET | `/ai/forecast/income` | 基于历史人均收入数据进行线性回归预测。 | 登录 |
| GET | `/ai/forecast/funds` | 根据当前时间进度和已使用经费，线性外推预测年末经费使用率， | 登录 |

### ai_enhanced.py — AI增强 `/ai-enhanced`

| 方法 | 路径 | 说明 | 鉴权 |
|------|------|------|------|
| POST | `/ai-enhanced/predict` | 趋势预测 - 使用Prophet或线性回归预测时间序列数据 | 登录 |
| POST | `/ai-enhanced/anomaly-detection` | 异常检测 - 使用Isolation Forest或统计方法检测数据中的异常值 | 登录 |
| GET | `/ai-enhanced/recommendations/projects` | 项目推荐 - 根据村庄特征推荐适合的项目 | 登录 |
| POST | `/ai-enhanced/recommendations/fund-allocation` | 资金分配建议 - 智能分配资金到多个村庄 | 登录 |
| POST | `/ai-enhanced/nlp-query` | 自然语言查询 - 将自然语言问题转换为SQL查询并返回结果 | 登录 |

### approval.py — 审批管理 `/approval`

| 方法 | 路径 | 说明 | 鉴权 |
|------|------|------|------|
| GET | `/approval` | 审批管理模块概览统计（pending/approved/rejected/total/my_pending） | 登录 |
| POST | `/approval/workflows` | 创建审批流程 | 管理员/登录 |
| GET | `/approval/workflows` | 获取审批流程列表 | 登录 |
| GET | `/approval/workflows/{workflow_id}` | 获取审批流程详情 | 登录 |
| PUT | `/approval/workflows/{workflow_id}` | 更新审批流程 | 管理员/登录 |
| DELETE | `/approval/workflows/{workflow_id}` | 删除审批流程 | 管理员/登录 |
| POST | `/approval/submit` | 提交审批申请 | 登录 |
| POST | `/approval/tasks/{task_id}/approve` | 审批通过 | 登录 |
| POST | `/approval/tasks/{task_id}/reject` | 审批拒绝 | 登录 |
| POST | `/approval/tasks/{task_id}/retry-apply` | 重试 *_apply_failed 任务的实体回写（管理员可查可修，消除「审批成功但业务状态未变」不一致） | 登录 |
| POST | `/approval/tasks/{task_id}/transfer` | 转交审批 | 登录 |
| POST | `/approval/tasks/{task_id}/withdraw` | 撤回申请 | 登录 |
| POST | `/approval/tasks/{task_id}/resubmit` | 驳回后重新提交审批（可携带更新后的变更数据） | 登录 |
| POST | `/approval/submit-auto` | 提交审批并自动通过 | 管理员/登录 |
| POST | `/approval/tasks/{task_id}/auto-approve` | 单机版快速审批单个任务 | 管理员/登录 |
| POST | `/approval/tasks/auto-approve-all` | 一键审批所有待处理任务 | 管理员/登录 |
| GET | `/approval/tasks/all` | 管理员获取所有审批任务（含分页 total） | 登录 |
| GET | `/approval/tasks/pending` | 获取待审批任务列表 | 登录 |
| POST | `/approval/tasks/batch` | 批量审批 | 登录 |
| GET | `/approval/tasks/mine` | 获取当前用户提交的审批任务（我的申请页） | 登录 |
| GET | `/approval/tasks/history` | 审批任务历史（管理员可见全部；普通用户仅可见自己提交的任务） | 登录 |
| GET | `/approval/tasks/{task_id}/diff` | 获取变更对比数据 | 登录 |
| POST | `/approval/tasks/{task_id}/remind` | 发送审批超时提醒（创建站内消息） | 登录 |
| GET | `/approval/history` | 获取审批历史 | 登录 |

### assessment.py — 考核评估 `/assessment`

| 方法 | 路径 | 说明 | 鉴权 |
|------|------|------|------|
| GET | `/assessment/village-scores` | 获取帮扶村综合成效评分（量化评分模型） | 登录 |
| GET | `/assessment/anomalies` | 检测数据异常（首页预警卡片用） | 登录 |
| GET | `/assessment/trend-prediction` | 基于历史数据的简单线性回归趋势预测 | 登录 |
| GET | `/assessment/village-comparison` | 多村横向对比（雷达图数据） | 登录 |

### auth.py — 认证 `/auth`

| 方法 | 路径 | 说明 | 鉴权 |
|------|------|------|------|
| POST | `/auth/login` | 用户登录 | 登录/公开 |
| POST | `/auth/two-factor/verify-login` | 双因素认证登录验证 | 登录/公开 |
| GET | `/auth/me` | 获取当前登录用户信息 | 登录/公开 |
| POST | `/auth/logout` | 用户登出 | 登录/公开 |
| POST | `/auth/refresh` | 刷新访问令牌 | 登录/公开 |
| GET | `/auth/csrf-token` | 获取 CSRF token | 登录/公开 |
| POST | `/auth/register` | 用户注册（通过通行码） | 含校验码 |

### rbac.py — 权限管理 `/rbac`

| 方法 | 路径 | 说明 | 鉴权 |
|------|------|------|------|
| POST | `/rbac/check` | 检查用户权限 | 登录 |
| GET | `/rbac/user/{user_id}/permissions` | 获取用户所有权限（普通用户仅可查看自己的权限，管理员可查看任意用户） | 登录 |
| GET | `/rbac/user/{user_id}/roles` | 获取用户角色（普通用户仅可查看自己的角色，管理员可查看任意用户） | 登录 |
| POST | `/rbac/roles` | 创建角色（具有事务原子性） | 管理员 |
| GET | `/rbac/roles` | 获取角色列表（分页） | 登录 |
| GET | `/rbac/roles/{role_id}` | 获取角色详情 | 登录 |
| PUT | `/rbac/roles/{role_id}` | 更新角色（具有事务原子性） | 管理员 |
| DELETE | `/rbac/roles/{role_id}` | 删除角色（具有事务原子性，系统角色不可删除） | 管理员 |
| GET | `/rbac/roles/{role_id}/users` | 获取角色关联的用户列表 | 管理员 |
| POST | `/rbac/assign/role` | 分配角色给用户（具有事务原子性） | 管理员 |
| DELETE | `/rbac/revoke/role` | 撤销用户角色（具有事务原子性） | 管理员 |
| POST | `/rbac/grant/permission` | 直接授予用户权限（支持批量，具有事务原子性） | 管理员 |
| POST | `/rbac/revoke/permission` | 批量撤销用户权限（具有事务原子性） | 管理员 |
| POST | `/rbac/save-permissions` | 原子性保存用户权限——在单个事务内完成撤销 + 授予（具有事务原子性） | 管理员 |
| GET | `/rbac/permissions` | 获取所有可用权限列表 | 登录 |
| GET | `/rbac/frontend/current-user-permissions` | 获取当前用户权限（前端组件专用） | 登录 |
| GET | `/rbac/frontend/route-permissions` | 获取路由权限配置（前端路由守卫专用） | 登录 |

### two_factor.py — 双因素认证 `/two-factor`

| 方法 | 路径 | 说明 | 鉴权 |
|------|------|------|------|
| POST | `/two-factor/enable` | 启用双因素认证 | 登录 |
| POST | `/two-factor/verify` | 验证TOTP令牌并正式启用双因素认证 | 登录 |
| POST | `/two-factor/disable` | 禁用双因素认证 | 登录 |
| GET | `/two-factor/status` | 获取双因素认证状态 | 登录 |

### user_management.py — 用户管理 `/user-management`

| 方法 | 路径 | 说明 | 鉴权 |
|------|------|------|------|
| GET | `/user-management/generate-password` | 生成随机密码 | 登录 |
| GET | `/user-management/roles` | 获取角色列表 | 登录 |
| GET | `/user-management` | 获取用户列表 | 登录 |
| POST | `/user-management` | 创建用户 | 登录 |
| PUT | `/user-management/{user_id}` | 更新用户信息 | 登录 |
| DELETE | `/user-management/{user_id}` | 删除用户(级联删除所有相关数据) | 登录 |
| POST | `/user-management/{user_id}/reset-password` | 重置用户密码 | 登录 |
| POST | `/user-management/{user_id}/assign-role` | 为用户分配角色 | 登录 |

### users.py — 用户管理 `/users`

| 方法 | 路径 | 说明 | 鉴权 |
|------|------|------|------|
| GET | `/users/me` | 获取当前登录用户的完整信息 | 登录 |
| PUT | `/users/me/profile` | 更新当前登录用户的个人资料 | 登录 |
| GET | `/users` | 用户列表 - 支持按状态、组织、角色筛选 | 管理员/登录 |
| GET | `/users/pending/list` | 获取待审核（未激活）的用户列表，供管理员审核 | 管理员/登录 |
| GET | `/users/staff-list` | 获取活跃用户列表，供任务分配等场景使用（任何登录用户均可访问） | 登录 |
| GET | `/users/{user_id}` | 获取用户详情 - 包含完整的权限和组织信息 | 管理员/登录 |
| POST | `/users` | 创建用户（支持完整的权限和组织分配） | 管理员/登录 |
| PUT | `/users/{user_id}` | 更新用户基本信息（包含权限分配） | 管理员/登录 |
| DELETE | `/users/{user_id}` | delete_user | 管理员/登录 |
| PUT | `/users/{user_id}/permissions` | 管理员分配或修改用户权限 | 管理员/登录 |
| GET | `/users/roles/options` | 获取可用的角色列表，用于创建/编辑用户时选择角色 | 管理员/登录 |
| GET | `/users/data-scopes/options` | 获取可用的数据范围选项 | 管理员/登录 |
| GET | `/users/permissions/options` | 获取可用的权限列表，用于给用户分配具体权限 | 管理员/登录 |
| POST | `/users/{user_id}/admin-reset-password` | 管理员直接重置用户密码（无需旧密码） | 管理员/登录 |
| PUT | `/users/{user_id}/password` | change_password | 登录 |
| POST | `/users/{user_id}/avatar` | 上传用户头像（仅本人或管理员） | 登录 |

### batch_operations.py — 批量操作 `/batch`

| 方法 | 路径 | 说明 | 鉴权 |
|------|------|------|------|
| POST | `/batch/update` | 批量更新（仅管理员） | 管理员/登录 |
| POST | `/batch/delete` | 批量删除（仅管理员） | 管理员/登录 |
| POST | `/batch/export` | 批量导出（仅管理员） | 管理员/登录 |
| POST | `/batch/validate` | 验证批量操作 | 登录 |
| GET | `/batch/status` | 获取批量操作状态 | 登录 |

### control_package.py — 管控配置包 `/control-packages`

| 方法 | 路径 | 说明 | 鉴权 |
|------|------|------|------|
| POST | `/control-packages/generate` | 生成管控配置包（返回下载） | 登录 |
| POST | `/control-packages/import-preview` | 预览管控配置包内容（不执行导入） | 登录 |
| POST | `/control-packages/import` | 导入并执行管控配置包 | 登录 |

### analytics.py — 数据分析 `/analytics`

| 方法 | 路径 | 说明 | 鉴权 |
|------|------|------|------|
| GET | `/analytics/dashboard` | 获取仪表盘数据 | 登录 |
| GET | `/analytics/village-analysis` | 获取帮扶村分析数据 | 登录 |
| GET | `/analytics/funding-trends` | 获取资金趋势分析 | 登录 |
| GET | `/analytics/performance-metrics` | 获取绩效指标数据 | 登录 |
| POST | `/analytics/comparison` | 获取对比分析数据 | 登录 |
| POST | `/analytics/generate-report` | 生成数据分析报表 | 登录 |
| POST | `/analytics/export` | 导出分析数据 | 登录 |
| GET | `/analytics/realtime-stats` | 获取实时统计数据 | 登录 |
| GET | `/analytics/kpi-summary` | 获取KPI汇总数据 | 登录 |
| GET | `/analytics/health` | 获取分析服务健康状态 | 登录/公开 |
| GET | `/analytics/cross-org-comparison` | 跨组织对比分析（仅 super_admin/admin 可用） | 登录 |

### dashboard.py — 仪表盘 `/dashboard`

| 方法 | 路径 | 说明 | 鉴权 |
|------|------|------|------|
| GET | `/dashboard/stats` | 获取仪表盘统计数据（带缓存，按用户组织范围过滤，refresh=true 跳过缓存） | 登录 |
| GET | `/dashboard/kpi-trends` | 返回当年 KPI：村数/人口/人均收入/经费投入（分析页与成效大屏用） | 登录 |
| GET | `/dashboard/yearly-trends` | 按最近 N 年返回: | 登录 |
| GET | `/dashboard/summary` | 仪表盘汇总接口：一次请求返回统计 + 近期动态，减少 HTTP 往返 | 登录 |
| GET | `/dashboard/recent-activities` | 获取近期动态（覆盖项目、经费、审批多类事件 + 自定义动态） | 登录 |
| POST | `/dashboard/recent-activities` | 创建自定义动态 | 登录 |
| PUT | `/dashboard/recent-activities/{activity_id}` | 更新自定义动态（仅本人或管理员） | 登录 |
| DELETE | `/dashboard/recent-activities/{activity_id}` | 删除动态（自定义动态物理删除，系统动态持久化隐藏） | 登录 |

### data_packages.py — 数据包管理 `/data-packages`

| 方法 | 路径 | 说明 | 鉴权 |
|------|------|------|------|
| POST | `/data-packages/one-click-report` | 一键生成上报数据包 | 登录 |
| GET | `/data-packages` | 获取数据包列表 | 登录 |
| GET | `/data-packages/received` | 获取已接收的上报数据包列表（仅管理员，按创建时间倒序分页） | 管理员/登录 |
| GET | `/data-packages/{package_id}` | 获取数据包详情 | 登录 |
| POST | `/data-packages/preview` | 预览导出数据的统计信息（不生成包，仅返回各数据类型记录数） | 登录 |
| POST | `/data-packages/export` | 导出数据包 | 登录 |
| POST | `/data-packages/import` | 导入数据包（仅管理员可接收） | 管理员/登录 |
| POST | `/data-packages/incremental/detect-changes` | 检测基准包之后各数据类型的变更记录数（按 updated_at 时间基准） | 登录 |
| POST | `/data-packages/incremental/export` | 基于基准包时间导出增量数据包（仅变更记录），返回下载地址 | 登录 |
| POST | `/data-packages/incremental/import` | 导入已存在于服务器上的数据包（增量或全量） | 登录 |
| POST | `/data-packages/{package_id}/validate` | 验证数据包 | 登录 |
| GET | `/data-packages/{package_id}/preview` | 预览数据包内容 | 登录 |
| POST | `/data-packages/{package_id}/confirm` | 确认导入数据（仅管理员可操作） | 管理员/登录 |
| GET | `/data-packages/{package_id}/download` | 下载数据包 | 登录 |
| DELETE | `/data-packages/{package_id}` | 删除数据包 | 登录 |
| GET | `/data-packages/{package_id}/history` | 获取数据包操作历史 | 登录 |
| POST | `/data-packages/export-encrypted` | 导出加密数据包 | 登录 |
| POST | `/data-packages/upload-encrypted` | 上传加密数据包（第一步：上传并检测加密） | 登录 |
| POST | `/data-packages/decrypt-preview/{package_id}` | 解密并预览数据包（第二步：提供密码解密） | 登录 |
| POST | `/data-packages/confirm-import/{package_id}` | 确认导入并处理冲突（第三步：选择冲突策略并导入） | 登录 |
| GET | `/data-packages/{package_id}/versions` | 获取指定数据包的所有版本 | 登录 |
| POST | `/data-packages/{package_id}/versions` | 为数据包创建新版本记录 | 登录 |
| GET | `/data-packages/{package_id}/versions/compare` | 对比数据包两个版本的变更差异 | 登录 |
| GET | `/data-packages/{package_id}/versions/{version_id}` | 获取指定版本的详细信息 | 登录 |
| DELETE | `/data-packages/{package_id}/versions/{version_id}` | 删除指定版本记录 | 登录 |

### data_quality.py — 数据质量 ``

| 方法 | 路径 | 说明 | 鉴权 |
|------|------|------|------|
| GET | `/report` | 数据质量综合报告 | 登录 |
| POST | `/full-check` | 全面数据质量检查（覆盖帮扶村、项目、经费、学校） | 登录 |

### data_reports.py — 数据上报 `/data-reports`

| 方法 | 路径 | 说明 | 鉴权 |
|------|------|------|------|
| GET | `/data-reports` | 获取数据上报列表 | 登录 |
| GET | `/data-reports/statistics` | 获取上报统计 | 登录 |
| GET | `/data-reports/dashboard` | 获取下级单位上报仪表板 | 登录 |
| GET | `/data-reports/pending` | 获取待审批的上报 | 登录 |
| GET | `/data-reports/received` | 获取接收的数据上报列表 | 登录 |
| GET | `/data-reports/{report_id}` | 获取上报详情 | 登录 |
| POST | `/data-reports` | 创建上报 | 登录 |
| POST | `/data-reports/{report_id}/submit` | 提交上报 | 登录 |
| POST | `/data-reports/{report_id}/review` | 审批上报 | 登录 |
| POST | `/data-reports/{report_id}/cancel` | 取消上报 | 登录 |
| POST | `/data-reports/{report_id}/resubmit` | 重新提交被拒绝的上报 | 登录 |
| POST | `/data-reports/{report_id}/approve` | 批准数据上报并导入数据 | 登录 |
| GET | `/data-reports/{report_id}/package` | 获取上报关联的数据包信息 | 登录 |
| GET | `/data-reports/{report_id}/preview` | 预览上报数据内容 | 登录 |
| GET | `/data-reports/{report_id}/download` | 下载上报数据包文件 | 登录 |

### reports.py — 报表管理 `/reports`

| 方法 | 路径 | 说明 | 鉴权 |
|------|------|------|------|
| POST | `/reports/export/excel` | 导出Excel报表 | 登录 |
| POST | `/reports/export/pdf` | 导出PDF报表 | 登录 |
| GET | `/reports/export/comprehensive/{year}` | 导出综合报表 | 登录 |
| GET | `/reports/analytics/filter-options` | 获取所有可用的筛选选项 | 登录 |
| POST | `/reports/analytics/filter` | 多维度筛选帮扶村 | 登录 |
| POST | `/reports/analytics/drill-down` | 数据钻取查询 | 登录 |
| POST | `/reports/analytics/compare-villages` | 对比多个帮扶村的数据 | 登录 |
| GET | `/reports/analytics/compare-years/{village_id}` | 对比同一帮扶村不同年份的数据 | 登录 |
| GET | `/reports/analytics/summary` | 获取汇总统计数据 | 登录 |
| POST | `/reports/subscriptions` | 创建报表订阅 | 登录 |
| GET | `/reports/subscriptions` | 获取当前用户的报表订阅列表 | 登录 |
| GET | `/reports/subscriptions/{subscription_id}` | 获取订阅详情 | 登录 |
| PUT | `/reports/subscriptions/{subscription_id}` | 更新订阅配置 | 登录 |
| DELETE | `/reports/subscriptions/{subscription_id}` | 删除订阅 | 登录 |
| POST | `/reports/subscriptions/{subscription_id}/toggle` | 切换订阅启用状态 | 登录 |
| POST | `/reports/generate` | 生成报表 | 登录 |
| GET | `/reports/{report_id}/download` | 下载已生成的报表文件 | 登录 |

### statistics.py — 统计分析 `/statistics`

| 方法 | 路径 | 说明 | 鉴权 |
|------|------|------|------|
| GET | `/statistics/summary` | 获取系统概览统计 | 登录 |
| GET | `/statistics/overview` | 数据总览接口 - 返回各模块概况、最后更新时间、健康评分、趋势数据 | 登录 |
| GET | `/statistics/villages/distribution` | get_villages_distribution | 登录 |
| GET | `/statistics/projects/statistics` | get_projects_statistics | 登录 |
| GET | `/statistics/funds/statistics` | get_funds_statistics | 登录 |
| GET | `/statistics/schools/statistics` | get_schools_statistics | 登录 |
| GET | `/statistics/analysis` | 数据统计分析页面聚合接口 | 登录 |
| GET | `/statistics/dashboard` | 获取仪表盘数据 | 登录 |

### data_quality.py — 数据质量 `/data-quality`

| 方法 | 路径 | 说明 | 鉴权 |
|------|------|------|------|
| POST | `/data-quality/validate` | 验证数据（按实体类型从规则库加载校验规则） | 登录 |
| POST | `/data-quality/clean` | 清洗数据 | 登录 |
| POST | `/data-quality/deduplicate` | 数据去重 | 登录 |
| POST | `/data-quality/validate-rules` | 按用户组合的规则（字段/操作符/值/与或非）校验模块数据，返回不满足的记录 | 登录 |

### data_sync.py — 数据同步 `/data-sync`

| 方法 | 路径 | 说明 | 鉴权 |
|------|------|------|------|
| POST | `/data-sync/export` | 导出增量数据包（ZIP格式，无加密） | 管理员/登录 |
| POST | `/data-sync/export-encrypted` | 导出加密数据包（.rrs格式，JSON body） | 管理员/登录 |
| GET | `/data-sync/export/download/{package_name}` | 下载导出的数据包 | 登录 |
| POST | `/data-sync/import` | 导入数据包（ZIP格式，无加密） | 管理员/登录 |
| POST | `/data-sync/import-encrypted` | 导入加密数据包（.rrs格式） | 管理员/登录 |
| GET | `/data-sync/conflicts/{sync_log_id}` | 获取冲突列表 | 登录 |
| POST | `/data-sync/resolve-conflict` | 解决冲突 | 管理员/登录 |
| GET | `/data-sync/logs` | 获取同步日志 | 登录 |

### effectiveness.py — 成效评估 `/effectiveness`

| 方法 | 路径 | 说明 | 鉴权 |
|------|------|------|------|
| POST | `/effectiveness/evaluate` | 评估村庄成效（根据年度收入/基础设施/产业数据计算三唯分数并落库） | 登录 |
| GET | `/effectiveness/report/{village_id}` | 获取评估报告 | 登录 |
| GET | `/effectiveness/compare/{village_id}` | 对比两年的评估结果 | 登录 |
| GET | `/effectiveness/rankings` | 获取排名列表 | 登录 |

### encryption.py — 数据库加密 `/encryption`

| 方法 | 路径 | 说明 | 鉴权 |
|------|------|------|------|
| POST | `/encryption/initialize` | 初始化数据库加密 | 管理员/登录 |
| POST | `/encryption/change-password` | 修改加密密码（验证旧密码后更新派生参数） | 管理员/登录 |
| GET | `/encryption/status` | 获取加密状态 | 登录 |
| POST | `/encryption/disable` | 禁用数据库加密 | 管理员/登录 |

### feedback.py — 意见反馈 `/feedback`

| 方法 | 路径 | 说明 | 鉴权 |
|------|------|------|------|
| GET | `/feedback` | 获取反馈列表（管理员接口） | 管理员/登录 |
| POST | `/feedback` | 提交意见反馈。建议登录后提交（Header: Authorization: Bearer <token>）， | 登录/公开 |

### files.py — 文件上传 `/files`

| 方法 | 路径 | 说明 | 鉴权 |
|------|------|------|------|
| POST | `/files/upload` | 上传任意业务模块的附件文件 | 登录 |

### fund_budgets.py — 经费预算 `/fund-budgets`

| 方法 | 路径 | 说明 | 鉴权 |
|------|------|------|------|
| GET | `/fund-budgets` | 获取预算列表 | 登录 |
| POST | `/fund-budgets` | 创建预算（仅管理角色） | 登录 |
| PUT | `/fund-budgets/{budget_id}` | 更新预算（仅管理角色） | 登录 |
| DELETE | `/fund-budgets/{budget_id}` | 删除预算（仅管理角色） | 登录 |
| GET | `/fund-budgets/alerts` | 获取预算预警信息（首页仪表板用） | 登录 |
| GET | `/fund-budgets/summary` | 获取预算汇总统计 | 登录 |
| GET | `/fund-budgets/transactions` | 获取经费使用明细列表 | 登录 |
| POST | `/fund-budgets/transactions` | 创建经费使用明细（仅管理角色） | 登录 |
| DELETE | `/fund-budgets/transactions/{transaction_id}` | 删除经费使用明细（仅管理角色） | 登录 |
| POST | `/fund-budgets/{budget_id}/attachments` | 上传预算相关的附件资料（批复文件/凭证/执行资料等） | 登录 |
| GET | `/fund-budgets/{budget_id}/attachments` | 获取预算上传的附件记录列表 | 登录 |

### fund_lifecycle.py — 经费生命周期 `/fund-lifecycle`

| 方法 | 路径 | 说明 | 鉴权 |
|------|------|------|------|
| GET | `/fund-lifecycle/phases/{project_id}` | 获取项目各阶段状态 | 登录 |
| POST | `/fund-lifecycle/phases/{project_id}/advance` | 推进到下一阶段（含准入校验） | 登录 |
| POST | `/fund-lifecycle/phases/{project_id}/rollback` | 退回上一阶段 | 登录 |
| POST | `/fund-lifecycle/initiate/{project_id}` | 初始化预算并生成项目报告模板 | 登录 |
| GET | `/fund-lifecycle/report-template/{project_id}` | 获取论证报告数据（经济指标 + 预算概算） | 登录 |
| POST | `/fund-lifecycle/budget-lock/{project_id}` | 锁定预算基线 | 登录 |
| GET | `/fund-lifecycle/compliance-check/{project_id}` | 合规性校验（10%预警线 / 15%否决线 + 费用标准匹配） | 登录 |
| GET | `/fund-lifecycle/budget-aggregation` | 多维度预算汇总（按年度/类型/村/单位/组织），含可视化预计算数据 | 登录 |
| POST | `/fund-lifecycle/quota-lock/{fund_id}` | 额度锁定 | 登录 |
| GET | `/fund-lifecycle/allocation-plan/{project_id}` | 拨付计划分解 | 登录 |
| GET | `/fund-lifecycle/transfer-vouchers` | 划转凭证列表 | 登录 |
| POST | `/fund-lifecycle/transfer-vouchers` | 创建划转凭证（含预算余额校验） | 登录 |
| GET | `/fund-lifecycle/transfer-vouchers/{voucher_id}` | 获取单条凭证详情 | 登录 |
| PUT | `/fund-lifecycle/transfer-vouchers/{voucher_id}` | 更新划转凭证 | 登录 |
| DELETE | `/fund-lifecycle/transfer-vouchers/{voucher_id}` | 删除凭证（仅 draft 状态） | 登录 |
| POST | `/fund-lifecycle/transfer-vouchers/{voucher_id}/confirm` | 凭证确认 | 登录 |
| POST | `/fund-lifecycle/transfer-vouchers/{voucher_id}/attachments` | 凭证附件上传（银行回单等电子化归档） | 登录 |
| GET | `/fund-lifecycle/transfer-ledger/{project_id}` | 协调台账 | 登录 |
| GET | `/fund-lifecycle/contracts` | 合同列表 | 登录 |
| POST | `/fund-lifecycle/contracts` | 创建合同 | 登录 |
| GET | `/fund-lifecycle/contracts/{contract_id}` | 获取合同详情（含付款明细） | 登录 |
| PUT | `/fund-lifecycle/contracts/{contract_id}` | 更新合同 | 登录 |
| DELETE | `/fund-lifecycle/contracts/{contract_id}` | 删除合同（仅 draft） | 登录 |
| POST | `/fund-lifecycle/contracts/{contract_id}/payments` | 登记合同付款（含多级审批集成） | 登录 |
| GET | `/fund-lifecycle/monitoring/deviation/{project_id}` | 进度-支付偏差分析（可选生成报告） | 登录 |
| GET | `/fund-lifecycle/monitoring/fund-flow/{project_id}` | 穿透式资金流查询（批量预加载，避免 N+1） | 登录 |
| GET | `/fund-lifecycle/anomalies` | 异常记录列表 | 登录 |
| POST | `/fund-lifecycle/anomalies/detect/{project_id}` | 触发智能异常检测 | 登录 |
| POST | `/fund-lifecycle/anomalies/{anomaly_id}/resolve` | 标记异常已处理 | 登录 |
| POST | `/fund-lifecycle/settlement/{project_id}` | 生成决算报告 | 登录 |
| PUT | `/fund-lifecycle/settlement/{settlement_id}` | 更新决算 | 登录 |
| POST | `/fund-lifecycle/settlement/{settlement_id}/approve` | 审批决算 | 登录 |
| GET | `/fund-lifecycle/performance/{project_id}` | 绩效评估数据 | 登录 |
| GET | `/fund-lifecycle/health/{project_id}` | 资金健康度评分（按项目聚合其下全部资金记录计算） | 登录 |
| POST | `/fund-lifecycle/health/batch` | 批量获取多项目健康度（项目列表用） | 登录 |
| GET | `/fund-lifecycle/allocation-orders` | 拨款指令列表 | 登录 |
| POST | `/fund-lifecycle/allocation-orders` | 创建拨款指令 | 登录 |
| POST | `/fund-lifecycle/allocation-orders/{order_id}/issue` | 下达拨款指令 | 登录 |
| PUT | `/fund-lifecycle/quota-adjust/{fund_id}` | 额度调整申请（紧急调整需 super_admin） | 登录 |
| GET | `/fund-lifecycle/inspection-clues/{project_id}` | 生成标准化督查线索清单（批量预加载 Fund，避免 N+1） | 登录 |
| POST | `/fund-lifecycle/settlement/{settlement_id}/verify-asset` | 资产联动校验（项目销号前置条件） | 登录 |
| GET | `/fund-lifecycle/performance-report/{project_id}` | 绩效自评报告（基于经济指标量化对比） | 登录 |
| GET | `/fund-lifecycle/feasibility-report/{project_id}` | 可行性研究报告投资估算章节 | 登录 |
| GET | `/fund-lifecycle/monitoring/fund-flow-tree/{project_id}` | 资金流向树形结构（中央拨款→单位→末端采购） | 登录 |
| POST | `/fund-lifecycle/contracts/{contract_id}/attachments` | 登记合同相关附件资料（合同扫描件/付款凭证/验收资料等） | 登录 |
| GET | `/fund-lifecycle/contracts/{contract_id}/attachments` | 获取合同上传的附件记录列表 | 登录 |

### funds.py — 经费管理 `/funds`

| 方法 | 路径 | 说明 | 鉴权 |
|------|------|------|------|
| GET | `/funds` | 查询经费列表（支持OFFSET和Keyset两种分页） | 登录 |
| GET | `/funds/{fund_id}` | 查询经费详情。 | 登录 |
| POST | `/funds` | 创建经费记录（需管理员权限） | 登录 |
| POST | `/funds/apply` | 用户经费申请 — 无需管理员权限，所有登录用户均可提交 | 登录 |
| PUT | `/funds/{fund_id}` | 更新经费记录 | 登录 |
| DELETE | `/funds/{fund_id}` | 软删经费记录（置 is_active=False，保留数据以便恢复/审计） | 登录 |
| GET | `/funds/statistics/overview` | 经费统计概览 (单次聚合查询，排除软删记录) | 登录 |
| GET | `/funds/statistics/multi-dimension` | 经费多维度统计分析 (利用冗余字段消灭全表扫描，排除软删记录) | 登录 |
| POST | `/funds/{fund_id}/approve` | approve_fund | 登录 |
| POST | `/funds/{fund_id}/reject` | reject_fund | 登录 |
| POST | `/funds/{fund_id}/allocate` | allocate_fund | 登录 |
| POST | `/funds/{fund_id}/start-use` | start_use_fund | 登录 |
| POST | `/funds/{fund_id}/complete` | complete_fund | 登录 |
| POST | `/funds/{fund_id}/audit` | audit_fund | 登录 |
| GET | `/funds/supported-village/statistics/by-type` | fund_stats_by_type | 登录 |
| GET | `/funds/supported-village/statistics/yearly-comparison` | fund_stats_yearly_comparison | 登录 |
| GET | `/funds/supported-village/statistics/utilization-rate` | fund_stats_utilization | 登录 |
| GET | `/funds/supported-village/statistics/summary` | fund_stats_summary | 登录 |
| GET | `/funds/village/{village_id}/summary` | 帮扶村经费汇总：按年度统计该村所有经费的申请/批准/拨付/使用金额 | 登录 |
| GET | `/funds/school/{school_id}/summary` | 帮扶学校经费汇总：按年度统计该校所有经费的申请/批准/拨付/使用金额 | 登录 |
| GET | `/funds/{fund_id}/history/status` | 获取经费状态变更历史 | 登录 |
| GET | `/funds/{fund_id}/approval-flow` | 获取经费审批流程：当前节点 + 状态流转节点列表 | 登录 |
| GET | `/funds/{fund_id}/history/fields` | 获取经费字段变更历史 | 登录 |
| GET | `/funds/{fund_id}/history/operations` | 获取经费操作日志 | 登录 |
| GET | `/funds/attachments/{attachment_id}/download` | 下载经费附件 | 登录 |
| GET | `/funds/attachments/{attachment_id}/preview` | 预览经费附件（支持图片/PDF/文本等常见格式） | 登录 |
| DELETE | `/funds/attachments/{attachment_id}` | 删除经费附件 | 登录 |
| GET | `/funds/{fund_id}/attachments` | 获取经费附件列表 | 登录 |
| POST | `/funds/{fund_id}/attachments` | 上传经费附件 | 登录 |

### async_export.py — 异步导出 `/async-export`

| 方法 | 路径 | 说明 | 鉴权 |
|------|------|------|------|
| POST | `/async-export/reports` | 导出报表数据 | 登录 |
| POST | `/async-export/villages` | 导出帮扶村数据 | 登录 |
| GET | `/async-export/status/{task_id}` | 查询导出任务状态 | 登录 |
| GET | `/async-export/download/{task_id}` | 下载导出文件 | 登录 |
| GET | `/async-export/tasks` | 获取导出任务列表 | 登录 |

### chunked_upload.py — 分片上传 `/chunked-upload`

| 方法 | 路径 | 说明 | 鉴权 |
|------|------|------|------|
| POST | `/chunked-upload/init` | 初始化分片上传会话 | 登录 |
| POST | `/chunked-upload/chunk/{session_id}/{chunk_index}` | 上传单个分片 | 登录 |
| GET | `/chunked-upload/progress/{session_id}` | 获取上传进度 | 登录 |
| POST | `/chunked-upload/merge/{session_id}` | 合并所有分片 | 登录 |
| DELETE | `/chunked-upload/{session_id}` | 取消上传并清理 | 登录 |

### export.py — 数据导出 `/export`

| 方法 | 路径 | 说明 | 鉴权 |
|------|------|------|------|
| GET | `/export/users` | 导出用户列表（含手机号等PII, 仅管理员） | 管理员/登录 |
| GET | `/export/villages` | export_villages | 登录 |
| GET | `/export/schools` | export_schools | 管理员/登录 |
| GET | `/export/projects` | export_projects | 管理员/登录 |
| GET | `/export/funds` | export_funds | 管理员/登录 |
| GET | `/export/comprehensive` | export_comprehensive_report | 登录 |
| GET | `/export/report-word` | 导出 Word 格式公文报告 | 管理员/登录 |
| GET | `/export/report-pdf` | 导出 PDF 格式公文报告 | 管理员/登录 |

### import_data.py — 数据导入 `/import`

| 方法 | 路径 | 说明 | 鉴权 |
|------|------|------|------|
| GET | `/import/template` | 下载导入模板 | 登录 |
| POST | `/import/villages` | 导入帮扶村数据（向后兼容，等价于 entity_type=supported_village） | 登录 |
| POST | `/import/entities` | 通用实体导入 | 登录 |
| POST | `/import/validate` | 验证导入数据（不执行实际导入） | 登录 |
| POST | `/import/preview` | 导入预览（解析 Excel 后返回数据但不入库） | 登录 |
| GET | `/import/history` | 获取导入历史 | 登录 |
| GET | `/import/history/{history_id}` | 获取导入历史详情 | 登录 |

### machine_code.py — 机器码管理 `/machine-code`

| 方法 | 路径 | 说明 | 鉴权 |
|------|------|------|------|
| GET | `/machine-code/get-machine-code` | 获取当前机器的机器码和校验码 | 仅本机/含校验码 |
| POST | `/machine-code/admin/create` | 管理员录入机器码并生成通行码 | 登录 |
| GET | `/machine-code/admin/list` | 管理员查询机器码列表 | 登录 |
| POST | `/machine-code/admin/revoke/{machine_code_id}` | 管理员撤销机器码 | 登录 |
| POST | `/machine-code/verify-machine-code` | 验证机器码和校验码是否匹配 | 含校验码 |
| POST | `/machine-code/generate-initial-password` | 为用户生成初始登录密码 | 登录/含校验码 |
| POST | `/machine-code/reset-password-with-machine-code` | 使用机器码重置用户密码 | 仅本机/含校验码 |
| GET | `/machine-code/machine-info` | 获取当前机器的详细信息（需要登录） | 登录 |
| GET | `/machine-code/organization/{org_id}/verification-code` | 获取组织的校验码 | 登录/含校验码 |
| POST | `/machine-code/organization/create` | 管理员输入校验码+选择组织→生成通行码 | 登录/含校验码 |
| GET | `/machine-code/organization/list` | 查询组织通行证码列表 | 登录/含校验码 |
| GET | `/machine-code/organization/export` | 导出组织通行证码列表为 Excel | 登录/含校验码 |
| DELETE | `/machine-code/organization/{pass_code_id}` | 删除通行码记录 | 登录 |
| GET | `/machine-code/{machine_code_id}/permissions` | 获取机器码关联的功能权限列表 | 管理员/登录 |
| POST | `/machine-code/{machine_code_id}/permissions` | 批量授予机器码功能权限 | 管理员/登录 |
| DELETE | `/machine-code/{machine_code_id}/permissions` | 批量撤销机器码功能权限 | 管理员/登录 |
| DELETE | `/machine-code/{machine_code_id}/permissions/{permission}` | 撤销机器码单个功能权限 | 管理员/登录 |
| GET | `/machine-code/user/{user_id}/effective-permissions` | 获取用户实际生效的权限（含机器码限制） | 管理员/登录 |

### map.py — 地图可视化 `/map`

| 方法 | 路径 | 说明 | 鉴权 |
|------|------|------|------|
| GET | `/map/config` | 获取地图配置 | 登录 |
| GET | `/map/markers` | 获取地图标注数据（根据用户权限过滤） | 登录 |
| GET | `/map/county-coords` | 获取铴南州12县市坐标（前端地图选点参考用） | 登录/公开 |
| GET | `/map/regions` | 获取行政区划数据（含 GeoJSON geometry），用于地图边界渲染和多级下钻 | 登录/公开 |
| PUT | `/map/markers/{marker_type}/{marker_id}/coordinates` | 管理员手动设置帮扶村/学校坐标 | 登录 |
| GET | `/map/distances` | 计算区域中心到每个帮扶点的距离和预估车程 | 登录 |
| GET | `/map/search` | 离线地图搜索：按关键词搜索帮扶村和学校 | 登录 |
| GET | `/map/tile-info` | 获取离线瓦片信息：是否可用、缩放级别范围、瓦片数量 | 登录/公开 |
| GET | `/map/tiles/{z}/{x}/{y}.png` | 提供离线瓦片文件 | 登录/公开 |

### menus.py — 菜单权限管理 `/menus`

| 方法 | 路径 | 说明 | 鉴权 |
|------|------|------|------|
| GET | `/menus/accessible` | 返回当前登录用户可访问的完整菜单树。 | 登录 |
| GET | `/menus/all` | 返回所有菜单项的完整定义，包含 roles 信息，供管理员配置使用 | 登录 |
| GET | `/menus/user-menus/{user_id}` | 获取用户的菜单权限配置详情 | 登录 |
| PUT | `/menus/user-menus/{user_id}` | 设置用户的菜单权限。 | 登录 |
| GET | `/menus/role-defaults` | 返回所有角色的默认菜单配置，用于管理员参考 | 登录 |

### messages.py — 通知设置 `/notifications`

| 方法 | 路径 | 说明 | 鉴权 |
|------|------|------|------|
| GET | `/messages` | 获取消息列表 | 登录 |
| GET | `/messages/unread-count` | 获取未读消息数量 | 登录 |
| POST | `/messages/mark-read` | 批量标记消息为已读 | 登录 |
| POST | `/messages/mark-all-read` | 标记所有消息为已读 | 登录 |
| DELETE | `/messages` | 批量删除消息 | 登录 |
| DELETE | `/messages/read` | 删除所有已读消息 | 登录 |
| GET | `/messages/stats/summary` | 获取消息统计信息 | 登录 |
| GET | `/messages/recent-activities` | 获取近期系统动态 | 登录 |
| GET | `/messages/{message_id}` | 获取单条消息详情 | 登录 |
| GET | `/notifications/preferences` | 获取通知偏好设置 | 登录 |
| PUT | `/notifications/preferences` | 统一更新通知偏好（前端扁平结构） | 登录 |
| PUT | `/notifications/preferences/site-message` | 更新站内消息设置 | 登录 |
| PUT | `/notifications/preferences/email` | 更新邮件通知设置 | 登录 |
| PUT | `/notifications/preferences/quiet-hours` | 更新免打扰时段设置 | 登录 |

### data_tier.py — 数据分级存储 `/data-tier`

| 方法 | 路径 | 说明 | 鉴权 |
|------|------|------|------|
| GET | `/data-tier/stats` | 获取存储统计信息 | 登录 |
| GET | `/data-tier/summary` | 获取存储摘要报告（管理员） | 管理员/登录 |
| GET | `/data-tier/tier/{tier}` | 获取指定分级的信息 | 登录 |
| POST | `/data-tier/archive/{model_name}` | 归档指定模型的旧数据（管理员） | 管理员/登录 |
| GET | `/data-tier/archives` | 列出归档文件（管理员） | 管理员/登录 |
| POST | `/data-tier/restore` | 从归档恢复数据（管理员） | 管理员/登录 |
| DELETE | `/data-tier/cleanup` | 清理过期归档文件（管理员） | 管理员/登录 |
| GET | `/data-tier/tier-for-record/{date}` | 根据日期确定数据分级 | 登录 |

### metrics.py — 监控指标 `/metrics`

| 方法 | 路径 | 说明 | 鉴权 |
|------|------|------|------|
| GET | `/metrics/business` | 获取业务指标 | 登录 |
| GET | `/metrics/prometheus` | 获取 Prometheus 格式的指标 | 登录/公开 |
| GET | `/metrics/performance-dashboard` | 性能监控面板 — 综合展示 HTTP 请求指标、慢请求、错误率等 | 登录 |

### secrets.py — 密钥管理 `/secrets`

| 方法 | 路径 | 说明 | 鉴权 |
|------|------|------|------|
| GET | `/secrets/versions` | 列出所有密钥版本（管理员） | 管理员/登录 |
| POST | `/secrets/rotate` | 轮换密钥（管理员） | 管理员/登录 |
| POST | `/secrets/create` | 创建新密钥（管理员） | 管理员/登录 |
| POST | `/secrets/revoke/{version_id}` | 撤销密钥（管理员） | 管理员/登录 |
| POST | `/secrets/cleanup` | 清理过期密钥（管理员） | 管理员/登录 |
| GET | `/secrets/status` | 获取密钥状态 | 登录 |

### monitoring_legacy.py — 监控 `/monitoring`

| 方法 | 路径 | 说明 | 鉴权 |
|------|------|------|------|
| GET | `/monitoring/api-performance` | 获取API性能统计 | 登录 |
| GET | `/monitoring/endpoints` | 获取各端点统计信息 | 登录 |
| GET | `/monitoring/errors` | 获取错误统计 | 登录 |
| GET | `/monitoring/resources` | 获取系统资源统计 | 登录 |

### offline_map.py — 离线地图 `/offline-map`

| 方法 | 路径 | 说明 | 鉴权 |
|------|------|------|------|
| GET | `/offline-map/tiles/{z}/{x}/{y}` | 获取地图瓦片 | 登录/公开 |
| GET | `/offline-map/status` | 获取离线地图状态 | 登录/公开 |
| POST | `/offline-map/download` | 下载指定区域的瓦片(管理员功能) | 管理员 |
| DELETE | `/offline-map/clear` | 清理瓦片缓存(管理员功能)，服务层为整体清理，不支持按缩放级别 | 管理员 |

### org_module_policy.py — 组织模块策略 `/org-policies`

| 方法 | 路径 | 说明 | 鉴权 |
|------|------|------|------|
| GET | `/org-policies/modules` | 获取所有可管控模块定义 | 登录 |
| GET | `/org-policies/current` | 获取当前用户所属组织的模块策略（供前端策略执行引擎使用） | 登录 |
| GET | `/org-policies/{org_id}` | 获取某下级组织的模块策略（含默认值填充） | 登录 |
| PUT | `/org-policies/{org_id}` | 批量设置某下级组织的模块策略 | 登录 |
| DELETE | `/org-policies/{org_id}/{module_key}` | 重置某模块策略为默认值（删除自定义记录） | 登录 |
| GET | `/org-policies/{org_id}/export` | 导出某组织的模块策略（用于管控配置包） | 登录 |

### organization.py — 组织管理 `/organizations`

| 方法 | 路径 | 说明 | 鉴权 |
|------|------|------|------|
| GET | `/organizations` | 获取组织列表（分页） | 登录 |
| GET | `/organizations/tree` | 获取组织树形结构 | 登录 |
| GET | `/organizations/statistics/summary` | 获取组织机构统计数据 | 登录 |
| GET | `/organizations/export/list` | 导出组织列表为 Excel 文件 | 登录 |
| GET | `/organizations/my-organization` | 获取当前用户所属组织 | 登录 |
| GET | `/organizations/my` | 获取当前用户所属组织（/my 别名，兼容前端调用） | 登录 |
| GET | `/organizations/subordinates` | 获取下级组织列表 | 登录 |
| GET | `/organizations/types/options` | 获取组织类型选项 | 登录/公开 |
| GET | `/organizations/{org_id}` | 获取组织详情 | 登录 |
| POST | `/organizations` | 创建组织 | 登录 |
| PUT | `/organizations/{org_id}` | 更新组织 | 登录 |
| DELETE | `/organizations/{org_id}` | 删除组织（逻辑删除：将 is_active 设为 False） | 登录 |
| GET | `/organizations/{org_id}/children` | 获取子组织 | 登录 |
| GET | `/organizations/{org_id}/ancestors` | 获取祖先组织（沿父链逐级查询，避免全表加载） | 登录 |
| POST | `/organizations/{org_id}/move` | 移动组织到新的父级 | 登录 |
| POST | `/organizations/batch-update-sort` | 批量更新组织排序 | 登录 |
| GET | `/organizations/{org_id}/members` | 获取指定组织的成员列表 | 登录 |
| POST | `/organizations/{org_id}/members` | 将指定的用户划入该组织（设置 organization_id） | 登录 |
| DELETE | `/organizations/{org_id}/members/{user_id}` | 将成员移出组织（清空 organization_id） | 登录 |
| GET | `/organizations/{org_id}/detail` | 获取组织详情，包含子组织数量、成员数量、上级组织路径等扩展信息 | 登录 |
| POST | `/organizations/{org_id}/activate` | 激活指定组织（将 is_active 设为 True） | 登录 |
| POST | `/organizations/{org_id}/deactivate` | 停用指定组织（将 is_active 设为 False） | 登录 |

### performance.py —  `/performance`

| 方法 | 路径 | 说明 | 鉴权 |
|------|------|------|------|
| GET | `/performance/slow-queries` | 获取慢查询列表 | 登录 |
| GET | `/performance/query-stats` | 获取查询统计信息 | 登录 |
| DELETE | `/performance/slow-queries` | 清空慢查询记录 | 登录 |
| GET | `/performance/cache-stats` | 获取缓存统计信息 | 登录 |
| POST | `/performance/cache/clear` | 清空缓存 | 登录 |

### permission_package.py — 权限配置包 `/permission-packages`

| 方法 | 路径 | 说明 | 鉴权 |
|------|------|------|------|
| POST | `/permission-packages/export` | 导出完整权限配置为 ZIP 包。 | 登录 |
| GET | `/permission-packages/download/{file_name}` | 下载已导出的权限配置包 ZIP 文件。 | 登录 |
| POST | `/permission-packages/import` | 上传权限配置包 ZIP 文件，进行验证并返回预览数据。 | 仅本机 |
| POST | `/permission-packages/confirm/{file_name}` | 确认导入权限配置包，将所有权限配置写入数据库。 | 仅本机 |

### permission_packs.py — 权限包管理 `/permission-packs`

| 方法 | 路径 | 说明 | 鉴权 |
|------|------|------|------|
| GET | `/permission-packs` | 获取全部权限包（含每个包绑定用户数） | 管理员/登录 |
| POST | `/permission-packs` | 创建权限包。menu_keys 必须全部是合法菜单 key。 | 管理员/登录 |
| PUT | `/permission-packs/{pack_id}` | 更新权限包（仅更新传入字段）。menu_keys 变更对绑定用户即时生效。 | 管理员/登录 |
| DELETE | `/permission-packs/{pack_id}` | 删除权限包。仍有绑定用户时拒绝删除（需先解绑）。 | 管理员/登录 |
| POST | `/permission-packs/{pack_id}/bind-users` | 把权限包批量绑定给普通用户(user/viewer)。 | 管理员/登录 |
| POST | `/permission-packs/{pack_id}/unbind-users` | 批量解绑（permission_pack_id 置 None，用户回落到角色默认菜单）。 | 管理员/登录 |

### policy.py — 政策法规 `/policies`

| 方法 | 路径 | 说明 | 鉴权 |
|------|------|------|------|
| GET | `/policies/categories` | 获取政策分类列表 —— 兼容前端两种调用方式 | 登录 |
| GET | `/policies/categories/tree` | 获取政策分类树形结构 | 登录 |
| POST | `/policies/categories` | 创建政策分类 | 登录 |
| PUT | `/policies/categories/{category_id}` | 更新政策分类 | 登录 |
| DELETE | `/policies/categories/{category_id}` | 删除政策分类 | 登录 |
| GET | `/policies/statistics` | 获取政策统计数据（前端 Category.vue 使用） | 登录 |
| GET | `/policies/import/template` | 下载政策导入模板（委托 ExcelTemplateService） | 登录/公开 |
| POST | `/policies/import` | 从 Excel 导入政策 | 登录 |
| POST | `/policies/import/excel` | 从 Excel 导入政策（旧路径兼容） | 登录 |
| GET | `/policies/export/excel` | 导出政策到 Excel | 登录 |
| GET | `/policies/export/pdf` | 导出政策列表为真实 PDF 文档 | 登录 |
| GET | `/policies/export/wps` | 导出政策列表为 WPS 兼容表格（xlsx，WPS/Excel 均可打开） | 登录 |
| GET | `/policies/types` | 获取政策类型选项 — 合并预定义类型与数据库中的实际分类 | 登录/公开 |
| GET | `/policies/options/levels` | 获取政策级别选项 | 登录/公开 |
| GET | `/policies/options/statuses` | 获取政策状态选项 | 登录/公开 |
| POST | `/policies/{policy_id}/upload` | 上传政策附件文件（支持 pdf/doc/docx/pptx） | 登录 |
| GET | `/policies/{policy_id}/preview` | 预览政策附件文件（返回文件流或HTML） | 登录 |
| GET | `/policies/{policy_id}/download` | 下载政策附件 | 登录 |
| POST | `/policies/batch-delete` | 批量删除政策 | 登录 |
| GET | `/policies` | 获取政策列表 —— 兼容前端 skip/limit 和旧 page/page_size 参数 | 登录 |
| GET | `/policies/{policy_id}/related` | 获取相关政策（仅展示已发布政策或本人创建的政策） | 登录 |
| GET | `/policies/search` | 全文检索帮扶政策（FTS5 + 关键词高亮） | 登录 |
| GET | `/policies/{policy_id}` | 获取政策详情 | 登录 |
| POST | `/policies` | 创建政策 | 登录 |
| PUT | `/policies/{policy_id}` | 更新政策 | 登录 |
| DELETE | `/policies/{policy_id}` | 删除政策（软删除） | 登录 |
| POST | `/policies/{policy_id}/publish` | 发布政策 | 登录 |
| POST | `/policies/{policy_id}/archive` | 归档政策 | 登录 |
| POST | `/policies/{policy_id}/favorite` | 收藏政策（仅能为当前登录用户收藏，忽略客户端传入的 user_id 以防 IDOR） | 登录 |
| DELETE | `/policies/{policy_id}/favorite` | 取消收藏（仅能取消当前登录用户的收藏，忽略客户端传入的 user_id 以防 IDOR） | 登录 |
| GET | `/policies/user/{user_id}/favorites` | 获取用户收藏的政策（仅允许查看自己的收藏，防止越权读取他人数据） | 登录 |

### project_milestones.py — 项目里程碑 `/projects`

| 方法 | 路径 | 说明 | 鉴权 |
|------|------|------|------|
| GET | `/projects/{project_id}/milestones` | 获取项目里程碑列表 | 登录 |
| POST | `/projects/{project_id}/milestones` | 创建项目里程碑 | 登录 |
| PUT | `/projects/{project_id}/milestones/{milestone_id}` | 更新项目里程碑 | 登录 |
| DELETE | `/projects/{project_id}/milestones/{milestone_id}` | 删除项目里程碑 | 登录 |
| GET | `/projects/{project_id}/transition-rules` | 获取项目当前可用的状态流转规则 | 登录 |
| POST | `/projects/{project_id}/transition` | 执行项目状态流转 | 登录 |
| GET | `/projects/{project_id}/change-logs` | 获取项目变更记录 | 登录 |
| GET | `/projects/dashboard/upcoming-milestones` | 获取即将到期的里程碑（首页仪表板用） | 登录 |
| GET | `/projects/dashboard/overdue-milestones` | 获取已逾期的里程碑 | 登录 |

### projects.py — 项目管理 `/projects`

| 方法 | 路径 | 说明 | 鉴权 |
|------|------|------|------|
| GET | `/projects/stats` | 返回各状态项目数量和预算汇总，供前端统计卡片一次调用获取。 | 登录 |
| GET | `/projects/export` | 导出项目列表为 Excel（或 CSV 兜底），上限 10000 条防内存溢出 | 登录 |
| GET | `/projects` | 获取项目分页列表。默认排除已取消的项目。 | 登录 |
| GET | `/projects/{project_id}` | 获取项目详情，含关联经费/任务数量。 | 登录 |
| POST | `/projects` | 创建项目。编号全局唯一，预算≥0，结束日期≥开始日期。 | 登录 |
| PUT | `/projects/{project_id}` | 更新项目。进度 0-100，状态仅限有效枚举值。 | 登录 |
| DELETE | `/projects/{project_id}` | 软删除项目。仅管理员或项目创建者可执行。 | 登录 |
| GET | `/projects/{project_id}/history/changes` | 获取项目关键字段的变更历史（Diff 留痕） | 登录 |
| GET | `/projects/{project_id}/funds` | 获取指定项目关联的经费记录。 | 登录 |
| POST | `/projects/{project_id}/funds` | 为项目添加经费记录（使用请求体传参）。 | 登录 |
| GET | `/projects/{project_id}/tasks` | 获取指定项目下的任务列表。 | 登录 |
| POST | `/projects/{project_id}/tasks` | 为项目创建任务。 | 登录 |
| PUT | `/projects/{project_id}/tasks/{task_id}` | 更新指定任务。 | 登录 |
| DELETE | `/projects/{project_id}/tasks/{task_id}` | 删除指定任务（物理删除）。 | 登录 |
| GET | `/projects/import/template` | 下载帮扶项目导入模板（委托 ExcelTemplateService） | 登录 |
| POST | `/projects/import` | 批量导入帮扶项目数据。 | 登录 |
| POST | `/projects/{project_id}/files` | 上传项目附件，支持批量上传。category 可选 research/implementation/acceptance/photo | 登录 |
| GET | `/projects/{project_id}/files` | 获取项目附件列表，可按 category 筛选 | 登录 |
| DELETE | `/projects/{project_id}/files/{file_id}` | 删除项目附件（同时删除磁盘文件）。仅管理员或项目创建者可删除。 | 登录 |
| GET | `/projects/{project_id}/files/{file_id}/download` | 下载项目附件 | 登录 |
| GET | `/projects/{project_id}/files/{file_id}/preview` | 在线预览项目附件（图片、PDF 等直接内嵌显示） | 登录 |

### reminders.py — reminders `/reminders`

| 方法 | 路径 | 说明 | 鉴权 |
|------|------|------|------|
| GET | `/reminders` | 提醒中心：审批超时/项目截止/预算预警等（按时间倒序） | 登录 |
| POST | `/reminders/scan` | 立即执行一次提醒扫描（审批超时/项目截止/预算预警）——仅管理员 | 登录 |

### report_templates.py — 报表模板管理 `/report-templates`

| 方法 | 路径 | 说明 | 鉴权 |
|------|------|------|------|
| GET | `/report-templates` | 获取报表模板列表 | 登录 |
| POST | `/report-templates` | 创建报表模板 | 登录 |
| GET | `/report-templates/available-fields` | 返回指定模块可选的字段列表，供管理员组合生成报表模板 | 登录/公开 |
| GET | `/report-templates/{template_id}` | 获取模板详情 | 登录 |
| PUT | `/report-templates/{template_id}` | 更新模板 | 登录 |
| DELETE | `/report-templates/{template_id}` | 删除模板 | 登录 |
| GET | `/report-templates/{template_id}/download` | 下载模板 Excel 文件（根据字段映射自动生成） | 登录 |
| POST | `/report-templates/{template_id}/upload` | 上传已填写的模板 Excel 文件 | 登录 |

### rural_tasks.py — 乡村工作任务 `/rural-tasks`

| 方法 | 路径 | 说明 | 鉴权 |
|------|------|------|------|
| GET | `/rural-tasks` | 获取任务列表 | 登录 |
| GET | `/rural-tasks/statistics` | 获取任务统计 | 登录 |
| GET | `/rural-tasks/{task_id}` | 获取任务详情 | 登录 |
| POST | `/rural-tasks` | 创建任务 | 登录 |
| PUT | `/rural-tasks/{task_id}` | 更新任务 | 登录 |
| DELETE | `/rural-tasks/{task_id}` | 删除任务 | 登录 |
| POST | `/rural-tasks/{task_id}/submit` | 提交任务审批 | 登录 |
| POST | `/rural-tasks/{task_id}/approve` | 审批任务 | 登录 |
| POST | `/rural-tasks/batch-delete` | 批量删除任务（非管理员仅能删除自己创建的任务），请求体统一为 {ids: [...]} | 登录 |

### rural_works.py — 乡村工作 `/rural-works`

| 方法 | 路径 | 说明 | 鉴权 |
|------|------|------|------|
| GET | `/rural-works` | 获取乡村工作列表 | 登录 |
| GET | `/rural-works/statistics/summary` | 获取乡村工作统计数据 | 登录 |
| GET | `/rural-works/villages` | 获取村庄列表（用于下拉选择） | 登录 |
| GET | `/rural-works/report/generate` | 生成工作报告汇总数据 | 登录 |
| GET | `/rural-works/years` | 获取可用年份列表 | 登录 |
| GET | `/rural-works/{work_id}` | 获取单个乡村工作详情 | 登录 |
| POST | `/rural-works` | 创建乡村工作 | 登录 |
| PUT | `/rural-works/{work_id}` | 更新乡村工作 | 登录 |
| DELETE | `/rural-works/{work_id}` | 删除乡村工作 | 登录 |
| POST | `/rural-works/batch-delete` | 批量删除乡村工作 | 登录 |

### school.py — 帮扶学校管理 `/schools`

| 方法 | 路径 | 说明 | 鉴权 |
|------|------|------|------|
| GET | `/schools/import/template` | 下载导入模板（委托 ExcelTemplateService） | 登录/公开 |
| POST | `/schools/import/excel` | 从 Excel 导入学校 | 登录 |
| POST | `/schools/scholarship/import` | 从 Excel 导入奖学金资助学生 | 登录 |
| GET | `/schools/export` | 导出学校到 Excel | 登录 |
| GET | `/schools/export/excel` | 导出学校到 Excel | 登录 |
| GET | `/schools/statistics` | 学校统计数据（含助学兴教统计） | 登录 |
| GET | `/schools/options/types` | 获取学校类型选项 | 登录/公开 |
| GET | `/schools/options/statuses` | 获取帮扶状态选项 | 登录/公开 |
| GET | `/schools/attachments/{attachment_id}/download` | 下载附件 | 登录 |
| DELETE | `/schools/attachments/{attachment_id}` | 删除附件 | 登录 |
| GET | `/schools` | 获取学校列表 | 登录 |
| GET | `/schools/{school_id}` | 获取学校详情（含已软删记录，管理员可见时附带 viewableBecause 元数据） | 登录 |
| POST | `/schools` | 创建学校 | 登录 |
| PUT | `/schools/{school_id}` | 更新学校 | 登录 |
| DELETE | `/schools/{school_id}` | 删除学校（软删除） | 登录 |
| GET | `/schools/{school_id}/attachments` | 获取学校附件列表 | 登录 |
| POST | `/schools/{school_id}/attachments` | 上传学校电子资料 | 登录 |
| GET | `/schools/{school_id}/projects` | 获取学校帮扶项目列表 | 登录 |
| POST | `/schools/{school_id}/projects` | 新增帮扶项目 | 登录 |
| PUT | `/schools/{school_id}/projects/{project_id}` | 更新帮扶项目 | 登录 |
| DELETE | `/schools/{school_id}/projects/{project_id}` | 删除帮扶项目 | 登录 |
| GET | `/schools/{school_id}/scholarship-students` | 获取资助学生列表 | 登录 |
| POST | `/schools/{school_id}/scholarship-students` | 新增资助学生 | 登录 |
| PUT | `/schools/{school_id}/scholarship-students/{student_id}` | 更新资助学生 | 登录 |
| DELETE | `/schools/{school_id}/scholarship-students/{student_id}` | 删除资助学生 | 登录 |
| POST | `/schools/{school_id}/scholarship-students/import` | 从 Excel 导入资助学生 | 登录 |

### search.py — 全局搜索 `/search`

| 方法 | 路径 | 说明 | 鉴权 |
|------|------|------|------|
| GET | `/search` | 全局关键词搜索，聚合帮扶村、项目、政策法规、资金、用户、学校六类数据。 | 登录 |

### sentiment.py — 舆情监控 `/sentiment`

| 方法 | 路径 | 说明 | 鉴权 |
|------|------|------|------|
| POST | `/sentiment/collect` | 采集新闻 | 登录 |
| POST | `/sentiment/analyze` | 批量分析新闻情感 | 登录 |
| GET | `/sentiment/news` | 获取新闻列表 | 登录 |
| GET | `/sentiment/statistics` | 获取舆情统计 | 登录 |
| GET | `/sentiment/hot-keywords` | 获取热词列表 | 登录 |
| GET | `/sentiment/alerts` | 获取预警列表 | 登录 |

### subordinate_registry.py — 下级单位管理 `/subordinates`

| 方法 | 路径 | 说明 | 鉴权 |
|------|------|------|------|
| GET | `/subordinates` | 列出所有注册的下级单位系统实例 | 登录 |
| POST | `/subordinates` | 注册新的下级单位系统实例 | 登录 |
| PUT | `/subordinates/{instance_id}` | 更新下级单位信息（授权状态、有效期等） | 登录 |
| GET | `/subordinates/{instance_id}` | 获取下级单位详情 | 登录 |
| DELETE | `/subordinates/{instance_id}` | 删除下级单位注册记录 | 登录 |

### subordinate_reports.py — 下级上报包 `/subordinate-reports`

| 方法 | 路径 | 说明 | 鉴权 |
|------|------|------|------|
| POST | `/subordinate-reports/generate-registration` | 生成注册上报包（下级单位 → 上级单位） | 登录 |
| POST | `/subordinate-reports/generate-status` | 生成状态报告包（下级单位 → 上级单位） | 登录 |
| POST | `/subordinate-reports/import` | 导入下级单位上报包（上级单位操作） | 登录 |

### supported_village.py — 帮扶村管理 `/supported-villages`

| 方法 | 路径 | 说明 | 鉴权 |
|------|------|------|------|
| GET | `/supported-villages` | 获取帮扶村列表（分页、筛选） | 登录 |
| GET | `/supported-villages/filter-options` | 获取筛选选项（部门、县市列表） | 登录 |
| GET | `/supported-villages/options/dropdown` | 获取帮扶村下拉选项（id + name + county，供前端 Select 使用） | 登录 |
| GET | `/supported-villages/import-template` | 下载导入模板（委托 ExcelTemplateService） | 登录/公开 |
| POST | `/supported-villages/import` | 从 Excel 导入帮扶村 | 登录 |
| POST | `/supported-villages/batch-delete` | 批量软删帮扶村（仅可删除当前用户有权访问的记录，二次密码确认防误删） | 登录 |
| GET | `/supported-villages/{village_id}` | 获取帮扶村详情（含已软删记录，管理员可见时附带 viewableBecause 元数据） | 登录 |
| POST | `/supported-villages` | 创建帮扶村 | 登录 |
| PUT | `/supported-villages/{village_id}` | 更新帮扶村（过渡状态变更需管理员权限 + 写入审计日志） | 登录 |
| DELETE | `/supported-villages/{village_id}` | 软删帮扶村（置 is_active=False，保留关联数据以便恢复/审计） | 登录 |
| GET | `/supported-villages/{village_id}/purge/preview` | 彻底删除预览：返回将级联删除的关联数据统计（仅管理员） | 管理员/登录 |
| POST | `/supported-villages/{village_id}/restore` | 从回收站恢复软删帮扶村（is_active 置回 True，仅管理员） | 管理员/登录 |
| POST | `/supported-villages/{village_id}/purge` | 彻底删除回收站中的帮扶村：物理删除并级联清除全部子表数据（仅管理员 + 密码确认） | 管理员/登录 |
| GET | `/supported-villages/{village_id}/yearly/{year}` | 获取帮扶村某年度全部数据（所有section） | 登录 |
| POST | `/supported-villages/{village_id}/yearly/copy` | 将某年的全部年度数据复制到另一年 | 登录 |
| POST | `/supported-villages/{village_id}/yearly/{year}/{section}` | 保存帮扶村某年度某个section的数据 | 登录 |
| DELETE | `/supported-villages/{village_id}/yearly/{year}/{section}` | 删除某板块某年度数据（物理删除 + 审计留痕；T028） | 登录 |
| GET | `/supported-villages/{village_id}/change-history` | 获取帮扶村字段级变更历史（时间倒序） | 登录 |
| POST | `/supported-villages/{village_id}/yearly/{year}/validate` | 校验帮扶村年度数据完整性。 | 登录 |
| GET | `/supported-villages/{village_id}/sections/{section}/attachments` | 获取帮扶村某区块的附件列表 | 登录 |
| POST | `/supported-villages/{village_id}/sections/{section}/attachments` | 上传帮扶村某区块的附件 | 登录 |
| GET | `/supported-villages/{village_id}/sections/{section}/attachments/{attachment_id}` | 下载帮扶村某区块的附件 | 登录 |
| DELETE | `/supported-villages/{village_id}/sections/{section}/attachments/{attachment_id}` | 删除帮扶村某区块的附件 | 登录 |
| POST | `/supported-villages/{village_id}/committee` | 保存帮扶村委数据（旧前端路径兼容入口）。 | 登录 |
| POST | `/supported-villages/{village_id}/sections/import` | 导入帮扶村单个区块数据（Excel 表头驱动解析，真实写库） | 登录 |
| POST | `/supported-villages/{village_id}/sections/import-all` | 导入帮扶村所有区块数据（按工作表名匹配板块，真实写库） | 登录 |
| GET | `/supported-villages/{village_id}/transition-funding` | 获取转移支付资金按年度明细 | 登录 |
| POST | `/supported-villages/{village_id}/transition-funding` | 保存转移支付资金数据 | 登录 |
| GET | `/supported-villages/templates/all` | 下载所有区块模板（Excel 多工作表） | 登录 |

### supported_village_export.py — 帮扶村数据导出 `/supported-villages/export`

| 方法 | 路径 | 说明 | 鉴权 |
|------|------|------|------|
| GET | `/supported-villages/export/modules` | 获取可导出的模块列表 | 登录 |
| GET | `/supported-villages/export/formats` | 获取支持的导出格式 | 登录 |
| GET | `/supported-villages/export` | 导出帮扶村数据，返回 Excel 文件下载。 | 登录 |
| GET | `/supported-villages/export/preview` | 预览导出数据——返回行数统计，不生成文件。 | 登录 |

### sync.py — 同步状态 `/sync`

| 方法 | 路径 | 说明 | 鉴权 |
|------|------|------|------|
| GET | `/sync/status` | 获取同步状态 | 登录 |
| GET | `/sync/dashboard` | 获取同步状态可视化仪表盘数据 | 登录 |

### admin.py — 系统管理 `/admin`

| 方法 | 路径 | 说明 | 鉴权 |
|------|------|------|------|
| GET | `/admin/info` | 获取系统信息 | 管理员/登录 |
| POST | `/admin/backup` | 创建数据库备份 | 管理员/登录 |
| GET | `/admin/backups` | 获取备份列表 | 管理员/登录 |
| POST | `/admin/restore` | 恢复数据库备份 | 管理员/登录 |
| DELETE | `/admin/backups/{filename}` | 删除备份文件 | 管理员/登录 |
| GET | `/admin/config` | 获取系统配置（从 system_configs 表读取，回退到默认值） | 管理员/登录 |
| PUT | `/admin/config` | 更新系统配置（持久化到 system_configs 表） | 管理员/登录 |
| POST | `/admin/clear-cache` | 清理系统缓存 | 管理员/登录 |
| GET | `/admin/logs` | 获取系统日志 | 管理员/登录 |
| POST | `/admin/db-optimize` | 执行 WAL checkpoint + PRAGMA optimize，返回优化前后空间对比 | 管理员/登录 |
| GET | `/admin/users/{user_id}/sessions` | 查看用户活跃会话（基于 token 黑名单反向推断） | 管理员/登录 |
| POST | `/admin/users/{user_id}/sessions/{session_id}/revoke` | 强制登出用户（使其全部现存 token 立即失效） | 管理员/登录 |
| POST | `/admin/users/{user_id}/two-factor/reset` | 重置用户双因素认证 | 管理员/登录 |

### audit.py — Audit Logs `/audit`

| 方法 | 路径 | 说明 | 鉴权 |
|------|------|------|------|
| DELETE | `/audit/logs/batch` | 批量删除审计日志（仅管理员）。 | 登录 |
| DELETE | `/audit/logs/{log_id}` | 删除单条审计日志 | 登录 |
| PATCH | `/audit/logs/{log_id}/remark` | 更新审计日志备注 | 登录 |
| GET | `/audit/logs/export` | 导出审计日志为 JSON / Excel / CSV 格式 | 登录 |
| GET | `/audit/logs` | get_audit_logs | 登录 |
| GET | `/audit/logs/{log_id}` | get_audit_log_detail | 登录 |
| GET | `/audit/stats` | get_audit_stats | 登录 |
| GET | `/audit/actions` | get_available_actions | 登录/公开 |
| GET | `/audit/levels` | get_available_levels | 登录/公开 |
| GET | `/audit/security/events` | get_security_events | 登录 |
| GET | `/audit/security/stats` | get_security_stats | 登录 |
| POST | `/audit/security/events/{event_id}/resolve` | resolve_security_event | 登录 |
| GET | `/audit/login-attempts` | get_login_attempts | 登录 |
| GET | `/audit/api-access` | get_api_access_logs | 登录 |
| GET | `/audit/exports` | get_export_logs | 登录 |
| GET | `/audit/user-activity/{user_id}` | get_user_activity | 登录 |

### backup.py — 备份管理 `/backup`

| 方法 | 路径 | 说明 | 鉴权 |
|------|------|------|------|
| POST | `/backup` | 创建系统数据库备份 | 登录/公开 |
| POST | `/backup/request-download` | 普通用户发起备份下载申请 → 站内消息通知全部超管，由管理员线下授权。 | 登录 |
| GET | `/backup` | 获取所有数据库备份文件列表 | 登录/公开 |
| GET | `/backup/stats` | 获取备份统计信息 | 登录 |
| GET | `/backup/dirs` | 枚举可用的备份目标目录（可移动磁盘/固定盘/网络盘），供前端备份目标选择。 | 登录 |
| PUT | `/backup/target` | 持久化备份目标目录（写入 SystemConfig） | 登录 |
| GET | `/backup/schedule` | 获取自动备份计划配置（后端调度为唯一真相源）。 | 登录 |
| PUT | `/backup/schedule` | 更新自动备份计划配置（写入 SystemConfig，后端调度热生效）。 | 登录 |
| DELETE | `/backup/{filename}` | 删除指定的备份文件 | 登录/公开 |
| GET | `/backup/download/{filename}` | 下载指定的备份文件 | 管理员/登录 |
| GET | `/backup/preview/{filename}` | 读取备份 ZIP 的文件清单与元信息（backup_info.json），供前端预览弹窗使用。 | 管理员/登录 |
| POST | `/backup/verify/{filename}` | 验证指定备份文件的完整性 | 管理员/登录 |
| POST | `/backup/restore` | 从指定的备份文件恢复系统数据 | 管理员/登录 |
| POST | `/backup/upload-restore` | 上传备份 ZIP 文件并立即用于恢复系统数据 | 管理员/登录 |

### cache.py — 缓存管理 `/cache`

| 方法 | 路径 | 说明 | 鉴权 |
|------|------|------|------|
| GET | `/cache/stats` | 获取缓存的使用统计信息 | 登录 |
| POST | `/cache/clear` | 清除系统中的所有缓存数据 | 管理员/登录 |

### config_package.py — 配置包管理 `/system/config-packages`

| 方法 | 路径 | 说明 | 鉴权 |
|------|------|------|------|
| GET | `/system/config-packages` | 获取系统中已创建的配置包列表 | 登录 |
| POST | `/system/config-packages/export` | 将当前系统配置导出为 JSON 配置包 | 管理员/登录 |
| POST | `/system/config-packages/import` | 从 JSON 配置包导入系统配置 | 管理员/登录 |
| DELETE | `/system/config-packages/{package_name}` | 删除指定的配置包记录 | 管理员/登录 |

### env.py — 运行环境 `/env`

| 方法 | 路径 | 说明 | 鉴权 |
|------|------|------|------|
| GET | `/env/check` | 检查系统运行环境 | 登录 |

### error_report.py — 错误报告 `/error-reports`

| 方法 | 路径 | 说明 | 鉴权 |
|------|------|------|------|
| POST | `/error-reports` | 上报系统错误信息 | 登录 |
| GET | `/error-reports` | 获取错误报告列表 | 登录 |
| GET | `/error-reports/stats` | 获取错误报告统计数据 | 登录 |
| GET | `/error-reports/{report_id}` | 获取指定错误报告的详细信息 | 登录 |
| PUT | `/error-reports/{report_id}` | 更新错误报告处理状态（仅本人或管理员） | 登录 |
| POST | `/error-reports/report-exception` | 简化版异常上报接口 | 登录 |

### health.py — 系统健康 `/health`

| 方法 | 路径 | 说明 | 鉴权 |
|------|------|------|------|
| GET | `/health` | System health overview with key metrics. | 登录/公开 |
| GET | `/health/overview` | System health overview with key metrics. | 登录/公开 |
| GET | `/health/database` | Check database connectivity and size. | 登录/公开 |
| GET | `/health/database-health` | 数据库健康详情（自检结果 + 统计），供前端启动后提示 | 登录/公开 |
| GET | `/health/liveness` | Kubernetes-style liveness probe. | 登录/公开 |
| GET | `/health/readiness` | Kubernetes-style readiness probe (checks DB). | 登录/公开 |
| GET | `/health/full` | Comprehensive health report with DB stats, backup status, and performance metrics. | 登录/公开 |

### help.py — 帮助中心 `/help`

| 方法 | 路径 | 说明 | 鉴权 |
|------|------|------|------|
| GET | `/help/categories` | 获取所有帮助文档分类 | 登录/公开 |
| GET | `/help/articles` | 获取帮助文档列表，支持分类筛选和关键词搜索 | 登录/公开 |
| GET | `/help/articles/{article_id}` | 获取指定帮助文档的完整内容 | 登录/公开 |
| GET | `/help/search` | 全文搜索帮助文档 | 登录/公开 |
| GET | `/help/system-info` | 获取帮扶管理信息系统简介 | 登录/公开 |

### i18n.py — 国际化 `/i18n`

| 方法 | 路径 | 说明 | 鉴权 |
|------|------|------|------|
| GET | `/i18n/languages` | 获取系统支持的语言列表 | 登录/公开 |
| GET | `/i18n/translations/{language}` | 获取指定语言的完整或命名空间内的翻译资源 | 登录/公开 |
| GET | `/i18n/translate` | 获取指定键在目标语言下的翻译文本 | 登录/公开 |
| GET | `/i18n/missing-keys` | 比较两种语言的翻译资源，找出目标语言中缺失的键 | 登录 |
| GET | `/i18n/current` | 获取当前用户的语言设置 | 登录 |

### init.py — 系统初始化 `/init`

| 方法 | 路径 | 说明 | 鉴权 |
|------|------|------|------|
| GET | `/init/status` | 检查系统是否已完成初始化 | 登录/公开 |
| POST | `/init/initialize` | 执行系统首次初始化 | 登录/公开 |
| POST | `/init/reset` | 重置系统初始化状态 | 登录 |
| GET | `/init/checklist` | 获取系统初始化前需要准备的资料清单 | 登录/公开 |

### metrics.py — 系统指标 `/metrics`

| 方法 | 路径 | 说明 | 鉴权 |
|------|------|------|------|
| GET | `/metrics` | 获取系统运行的综合指标数据 | 登录 |
| GET | `/metrics/performance` | 获取各关键性能指标的详细数据 | 登录 |
| GET | `/metrics/database` | 获取数据库相关的指标数据 | 登录 |
| GET | `/metrics/history` | 获取指定时间范围内的历史监控指标数据 | 登录 |

### monitor.py — 系统监控 `/monitor`

| 方法 | 路径 | 说明 | 鉴权 |
|------|------|------|------|
| GET | `/monitor/snapshot` | 获取当前时刻系统运行状态的实时快照 | 登录 |
| GET | `/monitor/resources` | 获取系统资源使用详细报告 | 登录 |
| GET | `/monitor/alerts` | 获取当前配置的监控告警规则 | 登录 |
| GET | `/monitor/alerts/history` | 获取系统告警历史记录 | 登录 |
| GET | `/monitor/api-stats` | 获取API接口调用统计数据 | 登录 |
| GET | `/monitor/database-size` | 获取数据库文件大小（用于系统监控面板） | 登录 |

### system.py — 系统控制 `/system`

| 方法 | 路径 | 说明 | 鉴权 |
|------|------|------|------|
| GET | `/system/info` | 获取帮扶管理信息系统的综合信息 | 登录 |
| GET | `/system/status` | 获取当前系统运行状态概览 | 登录 |
| POST | `/system/shutdown` | 触发系统安全关闭 | 管理员/登录 |
| POST | `/system/restart` | 触发系统安全重启 | 管理员/登录 |
| GET | `/system/environment` | 获取详细的系统运行环境信息 | 登录 |
| GET | `/system/version` | 获取当前系统版本及发布信息 | 登录/公开 |

### system_config.py — 系统配置 `/config`

| 方法 | 路径 | 说明 | 鉴权 |
|------|------|------|------|
| GET | `/config` | 获取所有系统配置项的键值对列表 | 登录 |
| PUT | `/config` | 批量更新多个系统配置项 | 管理员/登录 |
| GET | `/config/export/json` | 导出所有系统配置为JSON字符串 | 登录 |
| POST | `/config/import/json` | 从JSON字符串导入系统配置 | 管理员/登录 |
| GET | `/config/defaults` | 获取系统内建的所有默认配置项 | 登录/公开 |
| GET | `/config/{key}` | 获取指定配置项的值及其说明 | 登录 |
| PUT | `/config/{key}` | 更新指定配置项的值 | 管理员/登录 |
| DELETE | `/config/{key}` | 删除指定配置项 | 管理员/登录 |

### tasks.py — 后台任务 `/tasks`

| 方法 | 路径 | 说明 | 鉴权 |
|------|------|------|------|
| GET | `/tasks` | 获取所有后台任务的列表 | 登录 |
| GET | `/tasks/stats` | 获取后台任务的统计数据 | 登录 |
| GET | `/tasks/{task_id}` | 获取指定任务的详细信息和执行状态 | 登录 |
| POST | `/tasks` | 创建并启动一个后台任务 | 登录 |
| POST | `/tasks/{task_id}/cancel` | 取消指定的后台任务 | 登录 |
| DELETE | `/tasks/{task_id}` | 删除指定的任务记录 | 登录 |
| GET | `/tasks/running/count` | 获取当前正在运行中的任务数量 | 登录/公开 |

### update_logs.py — 更新日志 `/update-logs`

| 方法 | 路径 | 说明 | 鉴权 |
|------|------|------|------|
| GET | `/update-logs` | 获取系统版本更新日志列表 | 登录 |
| GET | `/update-logs/latest` | 获取最新的系统更新记录 | 登录 |
| GET | `/update-logs/{update_id}` | 获取指定更新日志的详细信息 | 登录 |
| POST | `/update-logs` | 手动创建一条系统更新日志 | 登录 |
| POST | `/update-logs/initialize` | 初始化版本历史记录 | 登录 |
| POST | `/update-logs/sync` | 同步版本历史数据 | 登录 |
| DELETE | `/update-logs/{update_id}` | 删除指定的更新日志记录 | 登录 |
| GET | `/update-logs/check/version` | 检查当前版本是否与最新记录一致 | 登录 |

### zero_trust.py — 零信任安全 `/zero-trust`

| 方法 | 路径 | 说明 | 鉴权 |
|------|------|------|------|
| GET | `/zero-trust/assessment` | 获取当前会话的零信任评估结果 | 登录 |
| GET | `/zero-trust/policies` | 获取系统配置的零信任安全策略列表 | 登录 |
| GET | `/zero-trust/policies/{policy_id}` | 获取指定安全策略的详细信息 | 登录 |
| POST | `/zero-trust/evaluate` | 评估对指定资源的访问请求是否符合零信任策略 | 登录 |
| GET | `/zero-trust/events` | 获取记录的安全事件列表（从数据库读取，持久化存储） | 登录 |
| POST | `/zero-trust/events` | 手动记录一个安全事件 | 登录 |
| GET | `/zero-trust/events/stats` | 获取安全事件的统计分析数据（从数据库读取） | 登录 |

### system_health.py — 系统健壮性 `/system-health`

| 方法 | 路径 | 说明 | 鉴权 |
|------|------|------|------|
| GET | `/system-health/overview` | 获取系统整体健康状态 | 登录 |
| POST | `/system-health/integrity-check` | 执行 SQLite 完整性校验（PRAGMA integrity_check）+ 索引数量校验 | 管理员/登录 |
| POST | `/system-health/wal-checkpoint` | 执行 WAL 检查点操作（PRAGMA wal_checkpoint） | 管理员/登录 |
| GET | `/system-health/disk-space` | 获取磁盘空间详情 | 登录 |
| GET | `/system-health/table-stats` | 获取各表记录数统计 | 登录 |
| POST | `/system-health/vacuum` | 执行 VACUUM 压缩数据库（可能耗时较长） | 管理员/登录 |

### todos.py — 待办事项 `/todos`

| 方法 | 路径 | 说明 | 鉴权 |
|------|------|------|------|
| GET | `/todos/{todo_id}` | 获取单个待办事项详情 | 登录 |
| GET | `/todos` | 获取当前用户的待办事项列表 | 登录 |
| POST | `/todos` | 创建新的待办事项 | 登录 |
| PUT | `/todos/{todo_id}` | 更新待办事项 | 登录 |
| DELETE | `/todos/{todo_id}` | 删除待办事项 | 登录 |
| PATCH | `/todos/{todo_id}/toggle` | 切换待办事项的完成状态 | 登录 |

### user_permissions.py — 用户权限管理（旧版，v1.6.0后合并至/rbac） `/user-permissions`

| 方法 | 路径 | 说明 | 鉴权 |
|------|------|------|------|
| POST | `/user-permissions/assign-organization` | 将用户分配到组织 | 登录 |
| DELETE | `/user-permissions/remove-organization` | 将用户从组织中移除 | 登录 |
| GET | `/user-permissions/user-organizations/{user_id}` | 获取用户所属的所有组织 | 登录 |
| GET | `/user-permissions/organization-users/{organization_id}` | 获取组织下的所有用户 | 登录 |
| POST | `/user-permissions/assign-role` | 为用户分配角色 | 登录 |
| DELETE | `/user-permissions/remove-role` | 移除用户的角色 | 登录 |
| GET | `/user-permissions/user-roles/{user_id}` | 获取用户的所有角色 | 登录 |
| POST | `/user-permissions/grant-permission` | 直接授予用户权限 | 登录 |
| DELETE | `/user-permissions/revoke-permission` | 撤销用户的权限 | 登录 |
| GET | `/user-permissions/user-permissions/{user_id}` | 获取用户的所有权限 | 登录 |
| POST | `/user-permissions/check-permission` | 检查用户是否拥有指定权限 | 登录 |
| GET | `/user-permissions/organization-tree` | 获取组织树 | 登录 |
| GET | `/user-permissions/accessible-organizations` | 获取当前用户可访问的所有组织ID列表 | 登录 |
| GET | `/user-permissions` | 获取当前用户权限信息（根路径） | 登录 |

### validation.py — 数据校验 `/validation`

| 方法 | 路径 | 说明 | 鉴权 |
|------|------|------|------|
| GET | `/validation/rules` | 获取校验规则列表 | 登录 |
| POST | `/validation/rules` | 创建校验规则（管理员） | 登录 |
| PUT | `/validation/rules/{rule_id}` | 更新校验规则 | 登录 |
| DELETE | `/validation/rules/{rule_id}` | 删除校验规则 | 登录 |
| POST | `/validation/validate` | 对提交数据执行校验 | 登录 |
| GET | `/validation/fields` | 返回指定模块的可查询字段列表（含中文标签），供下拉式校验面板使用 | 登录 |
| POST | `/validation/query-check` | 按条件对存量数据做查询式校验，返回匹配/不匹配明细。 | 登录 |

### village_templates.py — 模板管理 `/templates`

| 方法 | 路径 | 说明 | 鉴权 |
|------|------|------|------|
| GET | `/templates` | 获取可用模板列表 | 登录 |
| GET | `/templates/{module}` | 下载指定模块的Excel模板 | 登录 |

### villages.py — 村庄管理 `/villages`

| 方法 | 路径 | 说明 | 鉴权 |
|------|------|------|------|
| GET | `/villages` | 获取村庄列表（已优化 N+1 查询） | 登录 |
| GET | `/villages/{village_id}` | 获取单个村庄详情（已优化 N+1 查询） | 登录 |

### work_logs.py — 工作日志 `/work-logs`

| 方法 | 路径 | 说明 | 鉴权 |
|------|------|------|------|
| GET | `/work-logs` | 获取工作日志列表 | 登录 |
| POST | `/work-logs` | 创建工作日志 | 登录 |
| PUT | `/work-logs/{log_id}` | 更新工作日志 | 登录 |
| DELETE | `/work-logs/{log_id}` | 删除工作日志 | 登录 |
| GET | `/work-logs/calendar` | 获取日历视图数据（按月） | 登录 |
| GET | `/work-logs/monthly-summary` | 聚合当月工作日志生成月度总结：总条数/打卡天数/分类统计/内容列表 | 登录 |

---

## 5. 维护说明

- **端点清单**由 `python scripts/docs/extract_api_endpoints.py -o <file>` 从路由源码 AST 提取,与代码同步;接口增删后重跑脚本并替换 §4。
- **模块导读与业务说明**为人工维护部分;新增模块建议同步更新 §3 速查表。
- 响应示例与字段级说明可结合 DEBUG 模式的 `/docs`(OpenAPI)查阅。
