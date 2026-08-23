---
labels: [ready-for-agent, severity-high]
blocks: []
blocked-by: []
---

# W4-T1 pr-checks 覆盖率门禁真阻断

**来源**: 检测（`pr-checks.yml:26-27` continue-on-error 后无人消费覆盖率结果）

## 验收标准
- [ ] 移除后端 pytest 步骤的 continue-on-error，或新增独立步骤解析 coverage.xml 校验 ≥98%
- [ ] `--lf` 兜底步骤保留但不再作为唯一失败信号
- [ ] 本地模拟：人为制造覆盖率缺口/测试失败 → workflow 必须红
- [ ] Codecov 步骤补 token 说明或标注 fail_ci_if_error 现状

## 涉及文件
- `.github/workflows/pr-checks.yml`
