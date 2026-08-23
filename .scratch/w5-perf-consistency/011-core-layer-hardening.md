---
labels: [ready-for-agent, severity-low]
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
