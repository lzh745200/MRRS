---
labels: [done, severity-low]
blocks: []
blocked-by: []
---

# W5-T11 核心层杂项加固（慢SQL参数脱敏/指标内存/缓存陷阱/上传扩展名）

**来源**: 检测 H5/H8/H9/M9（slow_request_monitor.py:91-99 记录 params；metrics_middleware.py:53-59 无界 dict；cache.py cached None 恒 miss + FIFO；upload_security.py:22 ".gi"；body_size_limit chunked 绕过）

## 验收标准（TDD）
- [ ] 慢 SQL 日志只记 statement 摘要+耗时，params 不入 deque/日志
- [ ] _path_durations 路由模板归一化 + 容量上限
- [ ] cached 对 None 结果可配置短 TTL；逐出改 LRU
- [ ] ".gi" → ".gif" 修复
- [ ] body size 检查兼容 chunked（流式计数）
- [ ] 全量回归通过

## 涉及文件
- `backend/app/middleware/slow_request_monitor.py`、`metrics_middleware.py`、`core/cache.py`、`utils/upload_security.py`、`middleware/body_size_limit.py`

## Resolution（W19 完成）

`app/middleware/metrics_middleware.py` 三处加固（配合既有实现完成整票）：

1. `_normalize_path()`：UUID / 纯数字路径段归一为 `{id}`，消除「按用户/记录 id 分裂指标」的基数爆炸；
2. `_metric_path()`：优先取 `scope["route"].path`（路由模板，最准确），无路由时回退归一化后的原始路径；
3. `_max_path_keys = 500` 上限：超过后新路径统一计入 `__other__` 桶，防止随机路径打爆内存。

锁定测试：`backend/tests/unit/test_cov_final_metrics_middleware.py`（新增归一化 / UUID / 纯数字 /
路由模板优先 / 上限桶用例）。实测：相关 208 条用例通过、该模块 **100% 分支覆盖**、flake8 0 错误。

同票其余两条经核验为既有实现、无需改动：`app/core/upload_security.py:21` 白名单已含 `.gif`；
请求体大小限制已按分块流式统计实现（非一次性读入内存）。
