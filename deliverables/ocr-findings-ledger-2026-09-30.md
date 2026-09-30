# OCR 深审发现处置台账（2026-09-30）

> 来源：`deliverables/open-code-review-深度审查报告-2026-09-17.md`（alibaba/open-code-review v1.12.4，
> 扫描 669 文件 / 2,020 findings：critical 55 · high 359 · medium 1056 · low 550）。
> 逐条复核明细见 `deliverables/ocr-triage-2026-09-30/part-{A,B,C,D}.md`（含当前代码行号与关键片段证据）。

## 一、复核结论总览

| 区间 | 条目 | LIVE（仍存在） | 已修复 | 误报 | 文件已删除 |
|---|---|---|---|---|---|
| part-A（critical + high 前半） | 98 | 92 | 2 | 2 | 2 |
| part-B（high 中段） | 85 | 74 | 11 | 0 | 0 |
| part-C（high 后段） | 87 | 86 | 0 | 1 | 0 |
| part-D（前端与工具） | 88 | 85 | 2 | 1 | 0 |
| **合计** | **358** | **337** | **15** | **4** | **2** |

> 说明：明细文件只覆盖 critical + high 中已逐条列出的 358 条；其余 medium/low 未做逐条人工甄别。

## 二、v1.12.9 本轮已修复（按主题，约 110 条）

> 修复条目逐条对应下方主题；完整变更见 `CHANGELOG.md` 的 `[1.12.9]` 段落。
> 验证口径（R16 收尾后实测）：后端 **11,843 用例全通过 + 覆盖率 100.00%**、
> 前端 302 文件 / 6,221 用例全绿、flake8 0、bandit 0 high、
> 11 项棘轮门禁 NEW=0、Alembic 单 head（45 版本）、`lint:check --max-warnings=0` 通过。

### 服务层深审残余（R16 新增批次，16 项）
级联彻底删除只走两跳（`cascade_purge_service` 改 DFS 自底向上链式删除）、
分片合并并发重入（`chunked_upload_service` 每会话锁 + 拒绝 MERGING 重入）、
数据清洗中位数/标准化、报表导出金额单位错标（元→万元）、报表取数参数与截断、
回收站"先清除后备份"（改先备份）、村庄级联删除吞异常、资源限额计数泄漏、
任务队列停止后不可重启、SMTP 发送加固、离线地图覆盖统计崩溃、
默认密钥非合法 Fernet key、加密包截断与无界读取、
FTS 读路径发 DDL 并提交、配置导入非对象 JSON + 非原子、数据上报统计 7 字段被丢弃、
导入冲突解决四类缺陷（时间比较/全键 setattr/KEEP_BOTH 不重映射外键/冲突检测无租户条件）。

### 响应信封与前端凭据/角色语义（R16 收尾，8 项）
`success_response(success=False)` 被静默丢弃（部分失败场景恒回 success=true）、
数据包 `/{id}/validate` 端点缺组织归属校验（越权读 → 404）、
前端角色默认值自相矛盾（`viewer` vs `normalizeRole` 的 `user`，且返回原始历史角色）、
凭据跨来源拼接（可拼出「A 的 token + B 的档案/刷新令牌」）、
**无档案会话丢失刷新令牌**（`_activeCredentials` 该分支把同源 refresh 一并置 null，
致"access 已轮换、档案未回填"的会话无法续期）、
**短证件编号等同未脱敏**（`maskMilitaryID` 长度 <4 原样返回、=4 时前后缀覆盖全部字符）、
**复制失败被误报成功**（`clipboard` 降级路径丢弃 `execCommand` 布尔返回值、临时节点不在 `finally` 移除）、
**测试替身短路真实解析**（`parseContentDisposition` mock 恒返回 fallback，使"响应头文件名优先"
断言永远测不到实现；离线 mock/凭据用例与 fail-closed 口径不一致）。

### 越权 / 任意文件读写
审计批量删除 fail-closed（非法日期不再清空全表）、错误报告归属改读 `reporter`、
报表订阅下载与生成 IDOR、数据包 preview/decrypt-preview/confirm-import 归属校验、
政策附件 `realpath+commonpath` 包含性校验、上传文件名净化与落盘前复核、
组织模块策略 4 端点与管控包导入补 `assert_org_reachable`、综合报表导出补 `require_admin`
并全量过数据域过滤、上报提交归属校验、项目里程碑全端点数据域守卫、组织 `/subordinates`
限子树、农村任务禁止自审与审批字段直改、用户服务字段白名单、系统初始化 fail-loud。

### 提权 / 凭据 / 密钥
仅 super_admin 可管理 super_admin 账号（含缓存命中路径）、2FA 限流与二次验证、
经费角色改 allowlist、校验规则端点补 `require_admin`、
`ENCRYPTION_KEY`/PII 密钥 `require_persisted=True` fail-closed。

### 数据完整性 / 静默失效
备份增量记录可见性与清单推进顺序、快照 fail-loud、回滚保护；
异步导出数据域过滤与失败回滚；审批回写 SAVEPOINT 与失败终态；
FTS5 SQL f-string；校验引擎列名与 JSON 反序列化；`MessageType.BACKUP` 白名单；
同步成功率状态字面量；经费派生年月季清空；bulk update 递增 `sync_version`；
审计/留痕外键可空性 + 迁移 `w15_relax_notnull_001`（含两处唯一约束）；
监控逐盘健康评估；导入校验参数缺失（500）；消息模板渲染异常兜底。

### 其它
中间件（请求体限长、缓存头、XFF、驼峰转换、指标双计数、慢 SQL 参数脱敏）、
核心层（信封 kwargs 覆盖、金额 NaN/精度、迁移异常类型、错误处理可观测性、
批量更新同步版本）、服务层（分析 SQL 表名、业务指标完成态、组织导出字段映射、
导入导出历史元数据、Excel 全量导入原子性、报表模板中途提交、组织重挂 path/level、
用户/村庄级联删除回滚、备份清理与保留期）、前端（区域属性静默清空、`useRouterSafe`
开放重定向、菜单可见性树状态同步、`prompt.scss` keyframes、数据包加密导入链路等）。

## 三、仍待处置（未完成部分）

以下条目已在明细表中标记为 LIVE，**尚未在 v1.12.9 修复**，按主题归并（详见 part 文件）：

| 主题 | 代表条目 |
|---|---|
| 权限/越权残余 | `fund_lifecycle` 阶段推进与锁预算归属、`fund_budgets` 预算改删范围、`data_sync` resolve-conflict、`report_templates` confirm 导入、`control_package` 全量 SystemConfig 导出与任意配置键导入、`monitoring/secrets` keep_days 下界（已修）/ 其余密钥端点 |
| 系统端点健壮性 | `system/tasks` 无锁写状态、`system/cache` 无锁读、`system/config_package` str() 破坏 JSON、`system/metrics` 阈值倒置、`system_health` 索引校验取错元素、`update_logs` 删后读版本、`todos` 显式 null（已修）、`chunked_upload` ValueError |
| 数据范围与缓存 | `statistics` 分类/消费/就业/县区聚合（部分已修）、`dashboard` 动态缓存与近期动态、`map` 缓存键与同县坍缩、`supported_village` 列表缓存键 |
| 通知/邮件/分析 | `alert_service` SMTP 上下文与超时、`ai/nlp_query` 省份捕获/错误回传/NULL 格式化、`recommendation` 空省市匹配、`retention`、`restore_drill` 假达标、`smart_conflict` 字符串时间比较 |
| 模型/约束残余 | `import_export_history` 组织级联删除、`sentiment` 可空性与迁移不一致、`monitoring` 告警历史时间列、`fund_asset_verification` 差异率精度 |
| 前端残余 | `ImportEncryptedDialog` 链路、`PermissionAssignmentDrawer` 串用户、`stores/user` 越权覆盖、`stores/organization` 删组织 400、`FilePreview` blob 泄漏、`DefaultLayoutSafe` 定时器/锁屏摘要/经费 menuKey、`useKeyboardShortcuts` Shift 组合、`useBackupSchedule` cron 解析 等 |
| 性能 | `village_templates` async 内同步生成 Excel、`villages` 4×selectinload 逐行解密、`audit_middleware` 事件循环内同步落库、`trend_prediction` 超时后 shutdown(wait)、`slow_request_monitor` 参数入日志 |

> 处置原则建议：先做"越权/数据泄露"与"静默失效"两类（用户可感知且影响数据可信），
> 再做健壮性与性能类；每条修复须配回归测试，并保持本项目"非法输入 fail-closed"的统一语义。

## 四、复现与验证入口

- 逐条证据：`deliverables/ocr-triage-2026-09-30/part-{A,B,C,D}.md`
- 预防门禁：`scripts/check_*.py`（8 项，接入 pr-checks `static-analysis`），本地全绿：
  `cd backend && .venv/Scripts/python.exe scripts/check_os_exit.py` 等 6 项 + 根目录 6 项前端侧门禁。
- 全量回归：后端 `pytest tests/ -q`；前端 `npm test -- --run`；覆盖率门禁见 `backend/.coveragerc`
  （fail_under=100）与 `frontend/vitest.config.ts`（12 组 glob ×100%）。
