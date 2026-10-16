# T1 后端核心/中间件/性能域（写入范围：backend/app/core/**、backend/app/middleware/**、backend/app/utils/**、backend/tests/unit/**）
新增测试文件名统一 test_core_hardening_r28*.py，避免与他人撞名。
不得触碰：backend/app/core/data_permission.py（Lead）、backend/app/api/**（他人）、backend/app/services/**（他人）。

## 待修条目
- M33 middleware/camel_to_snake.py:66-114 —— 每请求全量缓冲响应体 + 递归改键 + 二次 JSON 解析/重序列化。收敛：避免二次解析、只转换必要键（信封补全可下沉到 response.py）。
- M34 core/database.py:60-65 —— after_cursor_execute 每条 SQL 都做函数内 import。改模块级缓存引用/内联。
- M35 core/security.py:792-800 vs 712-717 —— SECURITY_HEADERS 常量零消费；中间件硬编码 4 项；HSTS/CSP/Permissions-Policy 实际缺失；X-XSS-Protection 已废弃。改为遍历常量下发并补齐应有头（CSP 取保守口径 self，别把前端打死，用测试锁定）。
- M36 main.py:128-225 —— 中间件链 15 层、8 层 BaseHTTPMiddleware。把函数式中间件改纯 ASGI、可合并的合并；保持顺序语义（CORS/CSRF/审计/维护窗口/限流仍生效）并用测试锁定。
- M37 core/logging_config.py:100-142 —— SensitiveDataFilter 只脱敏 record.msg，不覆盖 exc_info 堆栈 → PII 随异常落盘。输出异常前对 formatException 结果再脱敏。
- M38 core/config.py:177-179 —— RATE_LIMIT_ENABLED/PER_MINUTE/PER_HOUR 全仓零消费。让 core/security.check_rate_limit 回退 settings 并支持整体关闭短路（注意 services/resource_limiter.py 是另一套实现，别混）。
- M39 core/token_blacklist.py:66-76,128-136 —— is_blacklisted 每次全量 _cleanup_expired()（O(n)+加锁）；_PERMANENT 条目永不清理、无上限。改清理节流 + 永久条目加长 TTL/上限。
- M41 core/migration_helper.py:17-155 vs main.py:580-734 —— 迁移兜底两份近似实现（_sqlite_col_spec + migrate_missing_columns）并存漂移。main 版改委托、删重复。
- 复核 H9：core/audit_middleware.py 每请求一次 DB 写已在 62d6943 修为批量缓冲 —— 确认无残留问题，有则修。

## 低危（§3 核心 14 条，逐条复核后修）
- utils/common.py:150,221 DateTimeHelper 用本地墙钟且无调用方（死代码）
- utils/helpers.py:21 generate_code 本地年份
- utils/excel_report_style.py:115 报表生成时间用本地墙钟
- core/security.py:45 except (ValueError, Exception) 冗余
- core/cache.py:63,108 逐出非 LRU 且不缓存 None
- core/token_manager.py:228 refresh_access_token 丢 extra_claims（含 token_version）→ 会签发立即失效令牌（R20 L2）
- core/database_indexes.py:73 每条索引重复建 inspector
- core/redis_adapter.py:10 内存字典无锁且 REDIS_ENABLED 零消费
- core/config.py:136,151,206,208 CACHE_SIZE_LIMIT/BCRYPT_ROUNDS/METRICS_ENABLED/HEALTH_CHECK_ENABLED 零消费 → 接线或删除（删除须确认无引用）
- main.py:124 中间件顺序注释与实际不符
- utils/encryption.py:141,165 文件加解密全量读入内存 → 分块
- core/build_info.py:44 缺 _build_info.json 时同步 subprocess(5s) → 异步/超时保护（不要改 spec，那归 build 同学）

## 验收
每条：改前行为说明 + 改后断言；定向 pytest 全绿；改动文件 flake8 0；新增分支 100% 覆盖。