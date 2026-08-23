---
labels: [done, severity-critical]
blocks: []
blocked-by: ["w1-security-redline/001-fix-public-reset-endpoint.md"]
---

# T6 通行码 HMAC fail-closed（ADR-0004）

**来源**: 检测 P0-2（`machine_code_service.py:29-32, 512-533, 479-506`）

## 问题
HMAC 密钥默认硬编码 `"bumofu-assistance-passcode-v1"` 且全仓库无部署配置 → 拿到源码者可自助计算合法通行码；自验证通过直接建记录激活。

## 决策（ADR-0004）
`PASS_CODE_SECRET` 未显式配置时禁用 HMAC 自验证路径（level-4 fallback 整体下线），仅保留管理员预录入通行码。启动日志 WARNING 提示。

## 验收标准（TDD）
- [ ] 测试：环境变量缺省时 `verify_pass_code_hmac` 返回 None/失败，不创建记录
- [ ] 测试：显式设置密钥时原行为保留（向后兼容）
- [ ] level-3 回退改绑机器码行为补审计日志（write_work_log）
- [ ] 全量回归通过

## 涉及文件
- `backend/app/services/machine_code_service.py`
- `docs/adr/0004-passcode-hmac-fail-closed.md`（新建）
- `backend/tests/unit/services/test_passcode_hmac_failclosed.py`（新建）
