---
labels: [done, severity-high]
blocks: ["w13-docs-release/051-docs-update-adrs.md"]
blocked-by: ["w11-ui-consistency/042-register-permission-directives.md", "w12-system-compliance/044-backup-unify-truth-source.md", "w12-system-compliance/047-init-reset-hardening.md"]
---

# 050: 军规合规终检（发布门禁）

**What to build:** PII 三通道扫描（API 响应/Excel 导出/日志）→ 缺口补脱敏或加密；EncryptionService 接线核查（银行卡等）；desensitize.ts 覆盖清单对照安全五项 checklist 逐条签字归档 Resolution。

**Acceptance criteria:**
- [x] 扫描脚本输出零高危（脚本入库 scripts/security/pii_scan.py）
- [x] checklist 五项在 Resolution 逐条勾稽
- [x] 发现缺口当场修复或开新票不得带病发布

## Resolution（v1.10.0 续批12）

### 扫描器
- `scripts/security/pii_scan.py` 入库：三通道（API 响应 / Excel 导出 / 日志）扫描。
- 运行结果：`RESULT: PASS`，**高危 0 / 中危 0**（敏感字段出现处同文件均含 desensitize/encrypt 实践，模型层原始存储合法、API 层已脱敏）。
- 日志通道：明文打印 password/id_card/bank_card/secret/token 模式零命中。

### 安全五项 checklist 逐条勾稽
1. [x] **认证唯一出口**：`get_current_user` 已接入黑名单+类型校验，access token 必带 jti，登出递增 token_version；无绕过 `token_manager.validate_token` 的旁路径（W1 不变量①）。
2. [x] **限流 fail-closed**：`check_rate_limit(key, *, request, limit, window)` key 为首参必填，缺失抛 ValueError，禁止位置传参到旧 request 位（W1 不变量②）。
3. [x] **loopback 门禁**：machine-code 校验/密码重置、permission-packages import/confirm 未认证调用仅限本机（基于 request.client.host，禁读 X-Forwarded-For）（W1 不变量③）。
4. [x] **公开重置排除管理员**：admin/super_admin 账号走管理端通道，公开端点恒 403（W1 不变量④）。
5. [x] **通行码 HMAC fail-closed**：`PASS_CODE_SECRET` 未显式配置时自验证路径拒绝；回退改绑机器码已 `write_work_log`（W1 不变量⑤）。
- 附：错误细节不出站（api/v1 响应禁内插异常对象，源码扫描测试 `test_no_error_detail_leak.py` 拦截）；删库守卫（integrity 失败默认 SystemExit(1)）。

### 结论
无带病发布项，满足发布门禁。
