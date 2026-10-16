# T3 服务层数据域与聚合正确性（写入范围：backend/app/api/v1/data/**、api/v1/ai_enhanced.py、api/v1/effectiveness.py、services/analytics_service.py、services/report_export_service.py、services/ai/nlp_query_service.py、services/effectiveness_service.py、services/fund_health_service.py、services/reminder_engine.py、services/monitoring_service.py）
新增测试文件名统一 test_scope_service_r28*.py。
不得触碰：backend/app/core/data_permission.py（Lead，只读调用）、其他 backend/app/api/**（他人）、frontend/**。
军事审计红线 S2：任意登录用户不得读跨组织聚合。

## 待修条目
- H2 api/v1/data/data/analytics.py:98/115/132/149/163/176/213/271、reports.py:243/269/300/339、statistics.py:153/203、dashboard.py:343 —— 分析/报表/统计/大屏整链路无数据域。
- H6 services/analytics_service.py:41/99/187/237/308/360/527、services/ai/nlp_query_service.py:138、services/report_export_service.py:55/90/152/215/255/283 —— 方法签名不接收 user/scope。改造：方法增 current_user 形参（fail-closed：漏传即在调用点 TypeError），内部统一走 app.core.data_permission 的 apply_scope_filter / filter_by_data_scope（只读调用），端点层透传 current_user。
  注意：apply_scope_filter 的 admin 语义正被 Lead 改为“默认严格（部门级 admin 仅本组织及子树），org-tree 端点显式 admin_full_access=True”。你写的调用点默认走严格口径；若某大屏/统计端点确需 admin 全量语义，显式传 admin_full_access=True 并在报告里列出理由。
- H13 api/v1/ai_enhanced.py:138 —— nlp_query 未传 current_user（不受数据域约束）且在 async def 内同步查库 → execute_query 增 user 形参 + 套 scoped_filter；端点改同步 def 或 run_in_threadpool。
- H7 services/effectiveness_service.py:239-362、fund_health_service.py:125-139 —— 占位实现返回写死数据（EffectivenessMetrics 常量、b"Mock report content"、_score_contract_fulfillment 恒 90.0 且 total 未参与）。改真实计算（用 total/未履约/逾期按权重扣分；趋势/报告用真实查询）；确实无法实现的端点返回 501 并写明未实现，绝不返回假数据。
- M18 fund_health_service.py:147,196 —— 资金健康分把软删经费计入 + 逐项目 N+1（每项目约 5 次查询）→ 加 is_active + 聚合查询。
- M19 reminder_engine.py:132 —— 预算告警扫描把软删经费计入 + 全表 .all() 载入内存 → 加 is_active + 下推 SQL 聚合。
- M20 ai/nlp_query_service.py:28,29,34,44,65,213 —— 模板 SQL 未过滤软删；空表 SUM 返回 NULL 时 f"{total:,.2f}" TypeError 被吞 → 补软删过滤 + or 0。
- M28 monitoring_service.py:49-73 —— 监控统计全量载入内存且 response_time_ms 为 NULL 时 .sort() TypeError；psutil.cpu_percent(interval=1) 同步阻塞 1s → SQL 端聚合 + 过滤 NULL + interval=0。
- 低危：nlp_query_service.py:23,104 省份参数含“省”字与库口径可能不一致 → 归一化。

## 验收
每条：改前行为 + 改后断言；关键：新增“部门级 admin 只拿到本组织数据 / 普通用户只拿到本人”的跨组织隔离用例（用真实 SQLite 或现有 fixture，不要 mock 掉权限函数本身）；定向 pytest 全绿；改动文件 flake8 0；新增分支 100% 覆盖。