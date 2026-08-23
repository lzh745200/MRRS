---
labels: [ready-for-agent, severity-medium]
blocks: []
blocked-by: []
---

# W4-T7 移除 sklearn sys.modules 注入 + 顺序耦合治理

**来源**: 检测（`tests/unit/conftest.py:5-22` MagicMock sklearn/scipy；`conftest.py:89-107` _POLLUTION_SENSITIVE 官方顺序依赖清单；`conftest_extended.py:31` 缺 sqlalchemy.event 导入的地雷）

## 验收标准
- [ ] requirements-dev 补真实 scikit-learn/scipy 或预测测试显式 skipif + 标注（移除 sys.modules 注入）
- [ ] _POLLUTION_SENSITIVE 清单逐文件消除：修复 mock 链使其不再依赖先跑
- [ ] 引入 pytest-randomly 冒烟验证一轮随机顺序
- [ ] conftest_extended.py 补导入或删除死代码
- [ ] 全量测试全绿

## 涉及文件
- `backend/tests/conftest.py`、`backend/tests/unit/conftest.py`、`backend/tests/conftest_extended.py`
