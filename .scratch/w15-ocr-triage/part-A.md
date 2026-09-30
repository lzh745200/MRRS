# OCR HIGH 段（明细 246-550 行）逐条核实 —— part A

- 范围：deliverables/ocr-findings-detail.md 第 246~550 行，共 98 条。
- 核实方式：只读阅读当前代码（行号已按符号重新定位），未修改任何源码/测试/配置。
- 判定计数：LIVE 92、FIXED 2（#26、#60）、FALSE_POSITIVE 2（#30、#31）、MOOT 2（#7、#8）。
- 备注：#31/#32/#33/#34 原描述中的『变成 5xx』不成立（BusinessError 默认 status_code=400，core/exceptions.py:88-93、164-170）。
| # | 文件:行 | 判定 | 证据（当前代码行号+关键片段） | 建议修复 |
|---|---|---|---|---|
| 1 | backend/app/api/v1/ai_enhanced.py:81-146 | LIVE | 5 个端点仍为 async def（81/98/114/126/139），全文件 await / run_in_threadpool 命中 0；104-110 直接同步调用 detect_anomalies（IsolationForest/Prophet 阻塞） | 改 def 或 run_in_threadpool 卸载 |
| 2 | backend/app/api/v1/approval.py:1001-1017 | LIVE | get_task_diff 仅依赖 get_current_user（1004），无 is_admin/提交人/审批人校验，1012 直接 service.get_task_diff(task_id) 返回 change_data/original_data | 加归属或管理员校验 |
| 3 | backend/app/api/v1/auth/auth.py:851-916 | LIVE | 852 create_user 已提交；858-867 只在认领返回 False 分支 db.delete；858/872 抛异常仍落 911 通用 except：仅 logger+400，无 rollback/删除 → 孤儿账号 | 用 created_user 跟踪并清理 |
| 4 | backend/app/api/v1/auth/auth.py:309-373 | LIVE | 311-321 有 429 限流，但 361-373 验证码错误仅写审计+401，不调 get_lockout_service().record_failed，不 revoke temp_token，验证次数无上限 | 失败计入锁定阈值并吊销 temp_token |
| 5 | backend/app/api/v1/auth/two_factor.py:46-66 | LIVE | /verify 全文件无 check_rate_limit/get_client_ip，56 失败仅 400，无尝试计数与锁定 | 加限流与失败锁定 |
| 6 | backend/app/api/v1/auth/two_factor.py:69-78 | LIVE | /disable 仅 get_current_active_user，75 直接 disable_two_factor，无 TOTP/备用码/密码二次确认 | 关闭前要求二次因子验证 |
| 7 | backend/app/api/v1/auth/user_management.py:235 | MOOT | 文件不存在（ENOENT）；auth/__init__.py:5 注明该路由 2026-09-14 下线 | — |
| 8 | backend/app/api/v1/auth/user_management.py:288 | MOOT | 同上（整文件已删除） | — |
| 9 | backend/app/api/v1/auth/users.py:695-712 | LIVE | 698 @cache_result(key_builder=..."role-options")，core/cache.py:112-116 命中即返回，703 require_admin 在函数体内被跳过；同型 716/734 | 把 require_admin 提到路由依赖 |
| 10 | backend/app/api/v1/auth/users.py:768-796 | LIVE | admin_reset_password 仅 776 require_admin，778 按 id 取目标后 791-793 改密+revoke_all_tokens，无 is_superuser(目标) 守卫 | 增加目标超管保护 |
| 11 | backend/app/api/v1/auth/users.py:483-535 | LIVE | 483-485 role 仅校验属于 VALID_ROLES（含 super_admin），无 is_superuser(current_user) 限制，523 role=role 直接落库 | 限制 admin 创建 super_admin |
| 12 | backend/app/api/v1/auth/users.py:612-626 | LIVE | delete_user 仅 614 require_admin + 620 禁止删自己，623 db.delete(user)，无目标角色/最后一个超管保护 | 增加目标角色守卫 |
| 13 | backend/app/api/v1/batch_operations.py:223-245 | LIVE | /batch/validate 仍无 require_admin（对比 209/286），仅把 organization_id/is_superuser 传服务；batch_service.py:236 在 organization_id 为 None 时不加过滤 → 无组织用户可跨组织枚举 | 加 require_admin 或 fail-closed |
| 14 | backend/app/api/v1/control_package.py:109-114 | LIVE | 78/82 只校验 admin+组织可达，113 db.query(SystemConfig).all() 全量导出全局配置，无 superuser 门禁/键白名单 | 限 superuser 或键白名单 |
| 15 | backend/app/api/v1/control_package.py:274-285 | LIVE | 231 仅 is_admin；279-284 逐 key 写全局 SystemConfig（existing.value=str(value) 或新增），无 allow-list/superuser 门禁 | 加 is_superuser + 白名单 |
| 16 | backend/app/api/v1/data/data/analytics.py:84-100 | LIVE | 87-88 接收 date_range/filters，98 只传 db 给 get_dashboard_overview，94/99 缓存键仅 dashboard:{user_id} | 透传参数并纳入缓存键 |
| 17 | backend/app/api/v1/data/data/dashboard.py:579-584 | LIVE | 580 activities=get_recent_activities(...) 返回 success_response 信封（core/response.py:150 起含 data 键），582 activities.get("items", []) 恒为空 | 改读 activities["data"]["items"] |
| 18 | backend/app/api/v1/data/data/dashboard.py:686-716 | LIVE | 695 缓存键固定 dashboard_recent_activities；621/642 只过滤 is_active 无数据范围；602 自定义动态无过滤；842 HiddenDashboardActivity 全局写入 | 按用户/组织隔离并套 data_scope |
| 19 | backend/app/api/v1/data/data/data_packages.py:358-386 | LIVE | /preview 366 get_org_with_fallback 直接采用 data.org_id，380-382 按其计数，无 can_access_organization（对比 /export 413） | 复用 /export 的 403 校验 |
| 20 | backend/app/api/v1/data/data/data_packages.py:1423-1446 | LIVE | decrypt_and_preview_package 无包查询、无 can_access_organization/require_admin，1436 直接解密预览 | 先查包并做组织/管理员校验 |
| 21 | backend/app/api/v1/data/data/data_packages.py:1455-1504 | LIVE | confirm-import 无包查询/require_admin/can_access，1473 直接 confirm_import_with_conflict_resolution 覆盖业务数据 | 同 confirm_import 的校验 |
| 22 | backend/app/api/v1/data/data/data_packages.py:857-897 | LIVE | 864 if org_id and not can_access... → org_id 为空即跳过校验；895 org_id=org_id or 0 以 0 写库 | 拒绝无组织数据包 |
| 23 | backend/app/api/v1/data/data/data_quality.py:31-56 | LIVE | 48-56 except Exception 后仍 success_response(200) 并回传 "error": str(e) | 改 HTTPException 500 且不外泄 |
| 24 | backend/app/api/v1/data/data/data_reports.py:45-74 | LIVE | 65/67 已按页查询，70 total=len(reports) 只是当前页条数 | 增加同条件 count 查询 |
| 25 | backend/app/api/v1/data/data/data_reports.py:101-125 | LIVE | 113-115 分页查询，121 total=len(reports) 同缺陷 | 同上 |
| 26 | backend/app/api/v1/data/data/reports.py:701-717 | FIXED | 非超管/非 admin 时 712-716 对订阅查询追加 ReportSubscription.user_id == current_user.id，越权读他人订阅已不可行 | — |
| 27 | backend/app/api/v1/data/data/statistics.py:609-749 | LIVE | _scoped 仅用于 618/632/640/657；681-695 分类、698-706 消费、715-723 就业、735-749 county_data 只有 is_active → 跨组织聚合 | 全部套 _scoped |
| 28 | backend/app/api/v1/data/data/statistics.py:58-102,234-240 | LIVE | 234 sv_count 过滤 is_active，78-91 四字段/坐标计数与 94/99 人口收入 distinct 均无 is_active；792 直接返回 completeness（仅 240 健康分 min(100,..)） | 各子计数补 is_active 或钳制 |
| 29 | backend/app/api/v1/data_quality.py:108-114 | LIVE | 签名 records: list、key_fields: list（无 Body()/Pydantic 模型，对比 22-35 的 *Request）→ FastAPI 绑定为查询参数，JSON body 请求 422 | 改 Pydantic Body 模型 |
| 30 | backend/app/api/v1/data_quality.py:177 | FALSE_POSITIVE | RuralWork 确无 is_active 列，但 .filter(True) 不会 500：SQLAlchemy WhereHavingImpl._coerce_consts=True（coercions.py:921-930、624-630）把 True 编译为 true()，等价无过滤；该模型本无软删语义 | 可选：显式构造条件（非缺陷） |
| 31 | backend/app/api/v1/data_sync.py:97-113 | FALSE_POSITIVE | 400 确实被 112 捕获，但 BusinessError 默认 status_code=400（core/exceptions.py:88-93），handler 回显 exc.status_code（164-170）→ 响应仍 400 且消息保留，非 finding 所述 5xx 丢失状态码 | 可选：用 from e 保留链路 |
| 32 | backend/app/api/v1/data_sync.py:158-190 | LIVE | 189 except Exception 吞掉 168/182 的 400 与 184 NotFoundException(404)：404 被包装成 BusinessError(默认 400)，状态码由 404 变 400（非 finding 所述 5xx） | 前置 except HTTPException: raise |
| 33 | backend/app/api/v1/data_sync.py:193-224 | LIVE | 208 file_path = await _save_upload_file(...)，写盘中途失败时 file_path 仍 None，221-224 finally 不清理半成品（扩展名校验已在 helper:64 早于 open；400 状态仍保留） | 先定路径再写，失败即清理 |
| 34 | backend/app/api/v1/data_sync.py:227-260 | LIVE | 243 赋值在保存返回之后，写盘失败泄漏半成品文件；255 通用 except 同样包装 400（状态仍是 400） | 同上 |
| 35 | backend/app/api/v1/data_sync.py:276-282 | LIVE | conflict_id: int、resolution: str、merged_data: Optional[dict]=None 无 Body()/模型 → 查询参数，前端 JSON body 会 422 且 merged_data 无法传递 | 建请求模型绑定 body |
| 36 | backend/app/api/v1/deps.py:41-52 | LIVE | 49-51 仅 role == viewer 拒绝（denylist）；normalize_role 对未知值原样返回 → Guest/typo/None 一律放行经费全流程 | 改 allowlist，失败关闭 |
| 37 | backend/app/api/v1/feedback.py:137-142 | LIVE | 138-140 只传 user_name（非 WorkLog 列，被 work_log_service.py:95 _WORKLOG_COLS 过滤）、无 user_id → 82-89 warning+return None，反馈审计恒不落库 | 传 user_id 与 username= |
| 38 | backend/app/api/v1/fund_budgets.py:175-220 | LIVE | update_budget(184)/delete_budget(215) 仅 _require_manager 后按 id 取记录，无 apply_data_scope/check_record_access（对比 124/234/258/308） | 加 check_record_access |
| 39 | backend/app/api/v1/fund_budgets.py:379-401 | LIVE | 386 仅 _require_manager，387 按 id 取 FundTransaction 后 395/400 回滚预算与 Fund 余额，无数据范围校验 | 加 check_record_access |
| 40 | backend/app/api/v1/fund_budgets.py:463-493 | LIVE | 476 setattr(budget,"remarks",json.dumps(existing))，480-493 从 remarks 解析附件；196-197 的 PUT 写普通文本即摧毁附件列表 | 独立附件列/表 |
| 41 | backend/app/api/v1/fund_budgets.py:342-365 | LIVE | 343 读预算 → 345-349 用内存值算 projected 校验 → 354 赋值；357-365 Fund 同；无 with_for_update/原子 UPDATE | 原子 UPDATE + rowcount 校验 |
| 42 | backend/app/api/v1/fund_lifecycle.py:200-240 | LIVE | 208 仅 _require_manager；210-217 直接按 project_id 查询与 _init_phases，未调用 _get_project_or_403(63-77) → 跨组织推进，不存在项目触发 FK 500 | 先 _get_project_or_403 |
| 43 | backend/app/api/v1/fund_lifecycle.py:243-290 | LIVE | 251 仅 _require_manager，253-257 按原始 project_id 读写 ProjectFundPhase 并改 Fund.lifecycle_phase，无项目级校验 | 同上 |
| 44 | backend/app/api/v1/fund_lifecycle.py:390-420,1403-1420 | LIVE | lock_budget(397)/detect_anomalies(1410) 均只有 _require_manager，无项目 404/403 校验 | 同上 |
| 45 | backend/app/api/v1/fund_lifecycle.py:661-668,778-798 | LIVE | TransferVoucherUpdate.status 可传（667），794-795 无条件 setattr → {"status":"confirmed"} 绕过 821-846 的 /confirm（不写 confirmed_by/at） | 白名单字段或限定状态机 |
| 46 | backend/app/api/v1/fund_lifecycle.py:1235-1298 | LIVE | 1256 写 f.deviation_rate，1298 返回前只有 1281 db.flush()；get_db（core/database.py:174-186）close 不提交 → 偏差率丢失 | 提交（safe_commit） |
| 47 | backend/app/api/v1/funds.py:400-407 | LIVE | _get_fund_or_404 仅 403 apply_scope_filter，无 Fund.is_active；而 450/705/755/1053 等均过滤软删 → 详情/流转/附件可操作软删经费 | 加 is_active 过滤 |
| 48 | backend/app/api/v1/import_export/async_export.py:101-147,202-238,292-332 | LIVE | 101/202/292 均为 async def，132 export_report_sync、215 get_export_task、308 get_user_export_tasks 全是同步阻塞调用，无 run_in_threadpool | 改 def 或卸载线程池 |
| 49 | backend/app/api/v1/import_export/chunked_upload.py:65-86 | LIVE | 29 file_size 仅 gt=0；72 create_session 在 >2GB 抛 ValueError（service:252-254）未被捕获，且无 ValueError 处理器（exceptions.py 只注册 AppError/Pydantic/DB）→ 500 | schema 约束或转 400 |
| 50 | backend/app/api/v1/import_export/chunked_upload.py:89-122 | LIVE | 114 upload_chunk 的 ValueError（service:350-373 会话过期/序号/大小/哈希）未捕获 → 500 | try/except ValueError 转 400 |
| 51 | backend/app/api/v1/import_export/chunked_upload.py:147-170 | LIVE | 161 merge_chunks 的 ValueError（service:425-470）未捕获 → 500；162 if not file_path 因服务只 raise 或返回路径而不可达 | 同上，并删除死分支 |
| 52 | backend/app/api/v1/import_export/export.py:328,340 | LIVE | 328 db.query(Project).limit(100).all()、340 Fund 同，无 is_active/scoped_filter/排序（对比 291-300 计数与 206/250 口径） | 加同样过滤 |
| 53 | backend/app/api/v1/import_export/import_data.py:223-254 | LIVE | 42 _IMPORT_MAX_FILE_SIZE=10MB 用于 404/531；253 /entities 仍读 settings.MAX_FILE_SIZE（config.py:194=50MB），下游 validate_file_size 10MB 拒绝 → 各端点状态码/行为不一致 | 统一用模块常量 |
| 54 | backend/app/api/v1/map.py:399-508 | LIVE | 414-416 命中缓存直接 return cached（裸 dict），冷路径 508 return success_response(data=result)，同一请求两种形状 | 缓存即包装信封 |
| 55 | backend/app/api/v1/map.py:438-439 | LIVE | 439 _get_coords(v.latitude, v.longitude, v.county) 省略 id/name（对比 210/462/547 传 v.id/v.village_name）；129/145 的 MD5 种子 record_id:name:county 相同 → 同县无坐标村坍缩为同一点 | 传 v.id 与村名 |
| 56 | backend/app/api/v1/map.py:410-435 | LIVE | 411 缓存键仅 map_distances:{user_id}，431-435 结果由 data_scope 决定；无 id 时回退 0 共享键 | 缓存键纳入数据范围 |
| 57 | backend/app/api/v1/messages.py:154-164 | LIVE | 159 %Y-%m-%d 解析为 00:00:00，message_service.py:221-222 用 created_at <= end_date → 当天消息被排除；164 非法值返回 None 静默忽略 | 用当日 23:59:59 边界 |
| 58 | backend/app/api/v1/monitoring/data_tier.py:75-91 | LIVE | 78-79 before_days: int = 365、batch_size: int = 1000 无 Query(ge/le)，负值使 before_date 落到未来 | 加 ge/le 约束 |
| 59 | backend/app/api/v1/monitoring/data_tier.py:214-223 | LIVE | 216 max_age_days 无下界，负值使 cutoff 移到未来，223 cleanup_old_archives 删除全部归档 | 要求正数 |
| 60 | backend/app/api/v1/monitoring/data_tier.py:175-211 | FIXED | 服务层已守卫：data_tier_service.py:282-283 if not archive_file or Path(archive_file).name != archive_file: return 0, 非法归档文件名，路径穿越不可达 | — |
| 61 | backend/app/api/v1/monitoring/metrics.py:38-48 | LIVE | /prometheus 无任何认证依赖（对比 22-26/51-59 的 get_current_active_user 与超管校验） | 加认证或爬虫令牌 |
| 62 | backend/app/api/v1/monitoring/secrets.py:80-93 | LIVE | 82 keep_days: int = 90 无约束；secrets_manager.py:169 cutoff=now-keep_days*86400，179 的 revoked_at<cutoff and created_at<cutoff 在负值时对全部非活跃版本成立 → 全删 | 加下界校验 |
| 63 | backend/app/api/v1/monitoring_legacy.py:19-36 | LIVE | async def 内 35 直接调用同步 MonitoringService.get_api_performance_stats（SQLAlchemy），对比 91 的 run_in_threadpool | 卸载线程池 |
| 64 | backend/app/api/v1/monitoring_legacy.py:39-56 | LIVE | 55 同步 get_endpoint_stats 直接在事件循环执行 | 同上 |
| 65 | backend/app/api/v1/monitoring_legacy.py:59-75 | LIVE | 74 同步 get_error_stats 直接在事件循环执行 | 同上 |
| 66 | backend/app/api/v1/organization.py:698-715 | LIVE | 702 confirm_password: str = Query("") 明文密码走 URL，进入访问日志/浏览器历史 | 改 JSON body |
| 67 | backend/app/api/v1/organization.py:512-526 | LIVE | 520-523 只用 include_self 过滤 parent_id（False→非根，True→全表），完全未使用 current_user | 按调用者组织子树过滤 |
| 68 | backend/app/api/v1/policy.py:587-599,1190-1204,1208-1235,1238-1256 | LIVE | 导出/相关/搜索/详情查询均无 Policy.is_active（仅 1109 列表与 1434 软删有），软删政策仍可读 | 补 is_active 过滤 |
| 69 | backend/app/api/v1/projects.py:1698-1707,1758-1768,1843-1868 | LIVE | 模板必填列加 *（excel_template_service.py:416-419）；1758-1768 只 strip 不剥 *，1699-1707 缺 项目编号/项目负责人/关联村庄/组织编码 且用 负责人/所属村庄/项目代码；1856 if not data.get("name"): continue → 模板导入 0 条；1848 example_hints 与模板示例不符 | 归一化表头并对齐别名 |
| 70 | backend/app/api/v1/recycle_bin.py:230-252 | LIVE | 236 bulk update 已限定 is_active==False，但 244-245 状态重置仍用 model.id.in_(ids) 全量 → 在库且 status=cancelled 的记录被改成 planned；242/246 两次 commit | 仅对实际恢复 id 重置并单事务 |
| 71 | backend/app/api/v1/recycle_bin.py:255-300 | LIVE | 262-273 循环内 svc.purge（cascade_purge_service.py:136 内部 safe_commit）无逐条容错，异常直接 500 且 278-295 审计/备份不执行；total==0 仍触发全量备份 | 逐条 try/except + finally 审计 |
| 72 | backend/app/api/v1/report_templates.py:405-426 | LIVE | update_template 仅 408 get_current_user，416-417 盲目 setattr，未复用 346-354 的 VALID_TEMPLATE_TYPES/MODULES 白名单，也无归属校验 | 加归属校验与白名单 |
| 73 | backend/app/api/v1/report_templates.py:1223-1298 | LIVE | upload_filled_template 仅 1229 get_current_user，1239 按 id 取模板，1275-1292 confirm 模式分发 _import_*（含 overwrite 删除），无归属/管理员校验 | 校验模板归属与角色 |
| 74 | backend/app/api/v1/report_templates.py:568-576,519 | LIVE | download_template 在 519 写 row=3 的 (必填)；解析器 570 min_row=3 视为首数据行，575 判空因该行非空不跳过，582 必填校验反而通过 → 回传模板产出假首行 | 注释行移出数据区或从第4行解析 |
| 75 | backend/app/api/v1/rural_tasks.py:225-250 | LIVE | 235 model_dump(exclude_unset=True) + 236-237 无条件 setattr；RuralTaskUpdate 暴露 status/result/progress/actual_*，可绕过 /submit、/approve | 白名单可写字段 |
| 76 | backend/app/api/v1/subordinate_reports.py:41-45,87-91 | LIVE | 两个生成端点仅 get_current_active_user（对比 155 的 import 有角色校验）；50 导出全部用户 PII，98 导出全局统计 | 加管理员/组织范围校验 |
| 77 | backend/app/api/v1/supported_village.py:521-547 | LIVE | 534 缓存键 villages:list:{organization_id}:{page}:{page_size}:{hash(参数)} 不含 data_scope/用户，547 结果由 apply_scope_filter(current_user) 决定 → 同组织不同范围互相命中 | 键纳入数据范围或非 admin 不缓存 |
| 78 | backend/app/api/v1/system/__init__.py:38-43 | LIVE | try 同时包住 import 与 include_router，42-43 仅 warning（全文件同型）→ 模块缺陷时端点静默缺失且丢栈 | 只包 import 并 fail-fast |
| 79 | backend/app/api/v1/system/audit.py:40-61 | LIVE | 42-53 对 v 直接 for 迭代：字符串 "12" → [1,2]；55-61 actions 同型 "login" → 逐字符；标量会 TypeError（validator 内非 ValueError → 500） | 归一为单元素列表 |
| 80 | backend/app/api/v1/system/cache.py:32-44 | LIVE | 34 len(backend._store)、42-44 迭代 _store，而 core/cache.py 所有读写都在 self._lock 内（25/39/45/50/57）→ 字典变更竞态 | 加锁取快照 |
| 81 | backend/app/api/v1/system/config_package.py:158-167 | LIVE | 166 svc.set(key, str(value) ...) 先 stringify；SystemConfigService.set 已对 bool/dict/list 归一（168-171 json.dumps）→ dict 变 Python repr，get_json 解析失败 | 去掉外层 str() |
| 82 | backend/app/api/v1/system/init.py:97-118 | LIVE | /initialize 无认证依赖（仅 100 get_db），117 读 is_initialized 后 131-177 多步写入，无原子守卫，可并发双跑 | 加锁或条件更新 |
| 83 | backend/app/api/v1/system/init.py:105,176-178 | LIVE | 文档称步骤1创建根组织单位，但 113-178 无 Organization 创建，177 svc.set_initialized(org_id=1) 硬编码 | 真建根组织或用现有 id |
| 84 | backend/app/api/v1/system/metrics.py:167-196 | LIVE | 173/184/195 均为 warning if x>80 else critical if x>95 → critical 永不触发（>95 仍 warning） | 先判高阈值 |
| 85 | backend/app/api/v1/system/metrics.py:293-300 | LIVE | 297 order_by(created_at.asc()).limit(500) 取窗口内最早 500 条，丢弃最新采样 | 改 desc 或子查询取最新 |
| 86 | backend/app/api/v1/system/system.py:234-256 | LIVE | 245 Popen 拉起新进程后 250 才 _graceful_shutdown()，父进程仍持端口（Windows SO_EXCLUSIVEADDRUSE）→ 子进程绑定竞态 | 先优雅关闭再延迟拉起 |
| 87 | backend/app/api/v1/system/system_config.py:46-66 等 | LIVE | 47 async def 内 56 svc.get_all() 等同步 SQLAlchemy（含 safe_commit）直接在事件循环，本模块端点同型 | 改 def 或 run_in_threadpool |
| 88 | backend/app/api/v1/system/system_config.py:130-147 | LIVE | 144 svc.import_config；service:257-265 只捕 JSONDecodeError/TypeError，非对象 JSON（如 [1,2]）在 261 .items() 抛 AttributeError → 500 | 校验为 JSON 对象 |
| 89 | backend/app/api/v1/system/system_config.py:207-224 | LIVE | 210 value: str = Query(...)、211 description: Query(None) → 配置值/说明进 URL 日志 | 改 JSON body |
| 90 | backend/app/api/v1/system/tasks.py:230-257 | LIVE | _execute_task 读写 _tasks 未持 _tasks_lock（74 定义，125/146/176/313/322 持有）→ 撕裂读，取消后被回写成 COMPLETED | 锁内重读并终态短路 |
| 91 | backend/app/api/v1/system/update_logs.py:231-243 | LIVE | 235-236 db.delete+commit 后 241 仍读 record.version；SessionLocal 未设 expire_on_commit=False（database.py:67）→ ObjectDeletedError 500 | 删除前取版本 |
| 92 | backend/app/api/v1/system/update_logs.py:278-283 | LIVE | except 分支返回 success: True 且带 str(e)（280-282），调用方无法区分失败 | 返回失败并仅记日志 |
| 93 | backend/app/api/v1/system/zero_trust.py:254-337 | LIVE | 256 total_score=100 起，仅 273/308 两处硬扣分；262/278/287/297/313 的因子分只 append 不累加 → score 恒 100/90，level 恒 trusted | 累加因子分 |
| 94 | backend/app/api/v1/system/zero_trust.py:441-450 | LIVE | /events 仅 447 get_current_user，453-468 无过滤查询 SecurityEvent（/events/stats 同型） | 加管理员或本人过滤 |
| 95 | backend/app/api/v1/system_health.py:91-110 | LIVE | 94 for idx_name, _, _ in EXTRA_INDEXES 取到的是表名（database_indexes.py:15 元组为 (表名,索引名,列)），与真实索引名比对 → missing 恒非空 | 取第二个元素 |
| 96 | backend/app/api/v1/todos.py:205-261 | LIVE | 227 exclude_unset 不排除显式 null，TodoUpdate 字段 Optional（39-46）→ 写 NULL 进 nullable=False（models/todo.py:30/33/34）→ IntegrityError 被 255-261 兜成 500 | 拒绝非空字段的显式 null |
| 97 | backend/app/api/v1/validation.py:213-238 | LIVE | 222 params = json.loads(rule.params) if rule.params else {} 无 try/except，脏数据使整个 /validate 500 | try/except 并降级 |
| 98 | backend/app/api/v1/validation.py:241-248 | LIVE | 247-248 未知 rule_type 时 handler 为 None 直接 return False（视为通过），无日志告警 | 记录告警或显式抛错 |
