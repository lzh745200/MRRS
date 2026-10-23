# CONTEXT.md — 帮扶管理信息系统（MRRS）

> 领域词汇与不变量。做非平凡改动前通读一遍；发现冲突事实须在同一次变更中更新本文件。

## 系统定位

完全**离线单机**的桌面应用：军队/地方联合帮扶乡村。FastAPI 后端 + Vue 3 前端 + Electron 壳 + SQLite。
多机之间通过"数据包"（导出 ZIP → 人工携带 → 导入）协同，无中心服务器。

## 核心领域概念

| 概念 | 说明 | 关键模块 |
|------|------|----------|
| 帮扶村 (SupportedVillage) | 受援行政村，含人口/收入/11 类年度帮扶数据子表 | `backend/app/models/supported_village.py` |
| 项目 (Project) | 帮扶项目，挂组织与村 | `models/project.py` |
| 经费 (Fund) | 资金记录，有状态机 pending→planned→...→audited | `models/fund.py`, `api/v1/funds.py:_transition_status` |
| 审批流 (ApprovalWorkflow) | 通用审批任务，节点可按角色或指定人 | `services/approval_workflow_service.py` |
| 组织 (Organization) | 树形结构，数据隔离的根，level_1~level_5 | `models/organization.py` |
| 机器码 (MachineCode) | 设备指纹，激活授权依据 | `services/machine_code_service.py` |
| 通行码 (PassCode) | HMAC 绑定机器码的激活凭证 | 同上 |
| 数据包 (DataPackage) | 跨机同步载体：全量/增量 ZIP，可加密(.rrs) | `services/data_package_service.py`, `data_sync_service.py` |
| 权限包 (PermissionPackage) | 离线分发的权限配置包 | `api/v1/permission_package.py` |

## 不变量（违反即缺陷）

1. **数据隔离**：一切业务查询必须经过组织范围过滤（`filter_by_data_scope` / `apply_scope_filter`）。语义：`user`=OWN，`admin`=OWN_DEPT（本组织**及子树**），`super_admin`=ALL；角色先过 `normalize_role()`。`apply_scope_filter` 默认即此严格口径（2026-10-14 R27-H8 收口），只有组织树可见性端点（地图/大屏/统计/组织树）显式传 `admin_full_access=True` 时才让部门级 admin 看全量；`check_record_access` 在组织归属缺失（任一侧为 NULL）时 fail-closed 拒绝。
2. **fail-closed**：鉴权、加密、限流的任何前置条件缺失时拒绝操作，绝不放行。
3. **envelope 响应**：新端点一律 `success_response()` / `ok_list()`（`core/response.py`）。
4. **软删除**：核心业务模型用 `is_active` + `deleted_by`；审计类记录永不物理删除。
5. **审计留痕**：写操作调用 `write_work_log()`；审批/授权/密码类操作必须留痕。
6. **敏感数据**：身份证号等 PII 加密存储；日志与错误响应不得泄露内部细节。
7. **导航与页面权限单一源**（v1.13.0 起，v1.15.15 补充）：菜单/导航唯一权威是后端 `api/v1/menus.py`
   （`MENU_SECTIONS` + `MENU_DEFINITIONS`，v2 `version/sections/flat_keys`；当前 6 板块 / 104 key /
   84 带 path 入口 / 16 legacy）；前端禁止手写菜单段。**页面访问权限跟随路由 `meta.menuKey`**：
  需挂靠帮扶村权限的页面（含一户一档）`meta.menuKey = villages`；`households` 自 v1.15.15 起为
  纯权限兼容 key（legacy，无导航出口，旧深链仍可直达）。新增页面/入口先改 `menus.py`，再跑
  菜单对齐门禁 A~E。

## 指标字典（W18 P2-1，2026-10-17）

> 同一指标**只能有一个口径**。新增/修改指标必须在此登记，并复用对应实现
> （禁止在端点里另写一套 SQL —— W18 P0-1 即因此让两个页面相差 500 人）。

| 指标 | 定义/公式 | 数据源 | 唯一实现 | 回归 |
|------|-----------|--------|----------|------|
| 帮扶村总数 | 过滤后 count(supported_villages.id)，仅 is_active=True | supported_villages | dashboard._query_village_stats | test_w18_metric_consistency |
| 总人口 | **每村取各自最新年份**的 total_population 后求和（不是"全库最大年份"） | village_population | ORM：dashboard._query_village_stats；raw-SQL：analytics_service（W27 已同口径） | test_w18_metric_consistency.TestPopulationMetricConsistency |
| 总户数 | 同"总人口"口径（每村最新年 total_households 求和） | village_population | 同上 | 同上 |
| 人均纯收入 | **`village_income` 行式表** `per_capita_income` 的平均值；`year` 缺省取"每村各自最新年"；**必须接 data_scope**，无 scope 返回 0（fail-closed） | **village_income**（W27 起；~~annual_income~~ 已废弃：该表全仓从不写入、dev 库 0 行、年份列写死 2025） | **`services/metrics_service.avg_per_capita_income`**（dashboard / 大屏 / 统计 / 数据分析 / 成效评估 全部委托它） | test_w27_metrics_unify + test_w18_metric_consistency.TestAvgPerCapitaIncomeScope |
| 经费合计（金额） | 过滤后 sum(funds.amount)（**全状态**）；未关联村（village_id IS NULL）的经费按 funds.organization_id 判域 | funds | dashboard 经费统计（`_query_fund_stats`） | test_dashboard_trends |
| 经费条数 | 过滤后 count(funds.id)。**W27 更名**：原字段名 `total_funds` 与上面的"金额"同名异义，现统一叫 `funds_count` | funds | statistics `/summary`、`/overview`、business_metrics_service | test_soft_delete_statistics |
| 报表村总数 | **独立 count()**，不得用明细 limit(100) 后的 len() | supported_villages | reports.generate_report | test_reports_api_cov |
| 金额单位 | 后端存储与接口一律**万元**，前端按需格式化；不得混用元 | —— | —— | —— |

> **W27 核心指标收口**（2026-10-23，W26-P0-2）：检测确认"4 个指标里 3 个口径不一致"
> ——人均纯收入读了一张**从未被写入**的表、总人口在 analytics 侧仍用全库最大年、
> 经费"合计"在统计侧实为 COUNT。现已统一，并**禁止**再出现第二套实现：
> `tests/unit/test_w27_metrics_unify.py::TestIncomeMetricSingleSource` 会扫描模块，
> 一旦有人重新 `from app.models.annual_income import ...` 取指标即变红。

**防腐门禁**：scripts/check_unused_scope_params.py（防"形参收下不用"）、
test_w18_metric_consistency.py（防"两套口径"）。

## 已知架构决策（ADR）

见 `docs/adr/`（完整清单以该目录文件为准）。关键几条：
- ADR-0001 认证唯一出口（token_manager.validate_token）
- ADR-0002 数据隔离单一实现 fail-closed
- ADR-0003 组织删除守卫
- ADR-0005 PII 加密落地方式
- ADR-0006 PyInstaller onedir
- ADR-0007 前端指令体系启用
- ADR-0008 破窗恢复（机器码重置密码）安全边界
- ADR-0009 预算预警三级阈值(80提醒/90警告/100禁止拦截)
- ADR-0010 自动备份机制统一（唯一真相源）
- ADR-0011 经费编号 ZJ+年份+6位流水(flush 后按 id 序，手输不覆盖)
- ADR-0012 轻量甘特图视图

## 整改工单

`.scratch/<wave>/<NNN>-slug.md`（本地 markdown 工单，一票一文件），规则见
`docs/agents/issue-tracker.md`。
