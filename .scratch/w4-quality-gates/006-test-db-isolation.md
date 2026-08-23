---
labels: [ready-for-agent, severity-medium]
blocks: []
blocked-by: []
---

# W4-T6 测试 DB 隔离统一（内存库 + worker 隔离）

**来源**: 检测（`conftest.py:14` 强制共享文件库 test.db，CI -n auto 曾损坏开发库；:670-678 autouse create_all 打共享库）

## 验收标准
- [ ] conftest 默认改 `sqlite:///`（内存）+ xdist 按 worker 命名（file:memMode 或 tmp_path per worker）
- [ ] 删除会话级共享 test.db 逻辑
- [ ] 全量测试（含 -n auto）连续两轮全绿
- [ ] 真文件库场景用显式 marker/fixture 隔离

## 涉及文件
- `backend/tests/conftest.py`
