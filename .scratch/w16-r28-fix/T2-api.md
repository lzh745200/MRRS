# T2 后端 API 门禁/信息回吐/正确性（写入范围：backend/app/api/**，不含 api/v1/data/** 与 api/v1/ai_enhanced.py；backend/app/services/**，不含 analytics_service.py / report_export_service.py / ai/nlp_query_service.py / effectiveness_service.py / fund_health_service.py / reminder_engine.py / monitoring_service.py）
新增测试文件名统一 test_api_gates_r28*.py。
不得触碰：backend/app/core/data_permission.py（Lead，可只读调用）、backend/app/core/**（他人）、frontend/**、electron/**。

## 待修条目
- M1 import_export/export.py:118 —— /export/villages 独缺 require_admin，与同文件兄弟端点对齐。
- M2 data_sync.py:176 —— 同步包下载端点缺 require_admin（猜到包名即可下全量包）；get_conflicts:294 / get_sync_logs:341 一并收敛。
- M3 recycle_bin.py:230,255 —— 批量恢复/彻底删除无组织可达性 → 按数据域过滤 ids。
- M4 system_health.py:25,178,189 —— 只读端点无 admin 且回吐数据库绝对路径/全表名/行数、异常回显 str(e) → 加 admin + 不回吐 path + 不回显异常原文。
- M5 system/system.py:328 —— /system/environment 无 admin，泄露 python_executable/cwd/hostname/依赖版本 → 加 admin 或裁剪最小集。
- M6 system/tasks.py:290,322,345 —— cancel/delete 可操作任意用户任务（无归属校验）；/tasks/running/count 未认证；task_type 未按枚举校验 → 补归属/admin 校验 + 认证依赖 + 枚举校验。
- M7 system/metrics.py:237,251,273,330 —— 回显库路径/表名与 str(e)；/history 失败仍 success=True → 去路径/异常原文，失败置 False。
- M8 system/health.py:108-148 —— /health/full 在 async def 内同步跑 PRAGMA integrity_check（重 I/O）→ 改同步 def 或 run_in_threadpool。
- M9 messages.py:313 —— /messages/recent-activities 向任意登录用户暴露全局审计日志 → 加 admin 或按域过滤（注意前端消费方：若前端需要非管理员可见，改为按域过滤，别把页面打空）。
- M10 work_logs.py:93-106,328,388 —— system_auto 分类对所有用户可见（含他人自动留痕）→ 限定本组织/本人或仅管理员。
- M11 villages.py:124 —— get_village 返回裸 dict（列表已 ok_list）→ 改 success_response（前端文件不要改，报告里说明兼容性）。
- M12 fund_lifecycle.py:587-627 —— quota_lock 空操作：只核验+写日志、不落任何字段却返回“额度已锁定” → 落库锁定状态或改文案（选真实可落库的实现；模型无字段则明确改文案并写测试）。
- M13 fund_budgets.py:335-361 —— /transactions 返回裸数组、分页无 total；create_transaction 返回裸对象 → 统一 ok_list 信封与分页 total。
- M14 import_export/import_data.py:472-486 —— 导入预览对 project/fund/school 做全表名称扫描 → 改按导入行名称 IN 查询。
- M15 system/monitor.py:203-292 —— 告警端点静默吞异常（仅 logger.debug）且无 admin 门禁 → 改 warning/exc_info + 门禁。
- M16 monitoring/metrics.py:77 等 —— 管理员判定口径不一致（is_superuser vs is_admin）导致 role=admin 被挡（涉 monitoring_legacy.py:30/52/72/88、performance.py:32、data_quality.py:82）→ 统一 require_admin/is_admin。
- M17 auth/rbac.py:202 —— get_role 404 返回裸 JSON → 统一错误信封。
- 复核 H4（api/v1/auth/users.py:619/694/722/878/371 跨组织数据域）：R25/R26 可能已修。若未修，用 core.data_permission 的 get_data_scope / apply_scope_filter（只读调用）收口，报告写明。

## 低危 API（§3）
- feedback.py:102 匿名可写且 content 无长度上限
- analytics.py:277 /analytics/health 无认证
- encryption.py:151 /encryption/status 泄露盐位/迭代数
- system_config.py:46,185 读端点任意登录可读含路径键
- villages.py:20,89 skip/limit 无范围校验且 page=(skip//limit)+1 错算
- system_health.py:37 /overview 异常回显 str(e)
- batch_operations.py:223 /batch/validate 无 admin 且 table_name 无白名单
- subordinate_reports.py:121 db_size_mb 路径口径与 get_database_path() 分叉
- import_data.py:417,556 导入解析失败统一文案吞真实原因

## 验收
每条：改前行为 + 改后断言；定向 pytest 全绿；改动文件 flake8 0；新增分支 100% 覆盖；门禁类改动要有“非管理员 403 / 管理员 200”双向用例。