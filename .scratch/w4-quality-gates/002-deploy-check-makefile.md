---
labels: [ready-for-agent, severity-high]
blocks: []
blocked-by: []
---

# W4-T2 deploy-check 后端门禁修复

**来源**: 检测（`Makefile:46-48` 反斜杠续行使 `|| true` 吞掉 pytest+bandit 全部失败）

## 验收标准
- [ ] 拆分为独立行：pytest 与 bandit 各自阻断；bandit 低级别告警单独容忍
- [ ] 补 flake8 到 deploy-check
- [ ] 本地验证：人为制造后端测试失败 → make deploy-check 必须非零退出
- [ ] bandit JSON 输出落盘供审计

## 涉及文件
- `Makefile`
