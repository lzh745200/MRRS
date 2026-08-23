---
labels: [ready-for-agent, severity-high]
blocks: []
blocked-by: ["w5-perf-consistency/006-data-scope-single-impl.md"]
---

# W5-T7 PII 加密落地 + SQLCipher 修复（ADR-0005）

**来源**: 检测 C3/C4（`village.py:89` id_card 明文等 23 处；`encryption_service.py:181-224` aes256 死配置；`database.py:78-128` PRAGMA key 顺序错误+驱动不匹配假加密）

## 决策点（实施前与用户确认字段范围）
默认范围：身份证号、手机号。方式：SQLAlchemy TypeDecorator 自动加解密，密钥走 ENCRYPTION_KEY（已有自动供给）。存量数据写一次性迁移脚本。

## 验收标准（TDD）
- [ ] 测试：id_card 落库为密文、ORM 读取透明解密；查询按密文等值匹配
- [ ] 测试：DB 文件直接打开看不到明文 PII
- [ ] 移除 aes256 死配置或实现之（二选一，记录 ADR）
- [ ] SQLCipher：启动探测 pysqlcipher3，缺失即拒绝启用并告警；PRAGMA key 移至连接首条语句
- [ ] 全量回归通过

## 涉及文件
- `backend/app/models/village.py` 等 PII 字段模型、`services/encryption_service.py`、`core/database.py`
- `docs/adr/0005-pii-encryption.md`
