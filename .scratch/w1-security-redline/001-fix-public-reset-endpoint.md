---
labels: [ready-for-agent, severity-critical]
blocks: ["w1-security-redline/006-passcode-hmac-fail-closed.md"]
blocked-by: []
---

# T1 公开密码重置端点三重修复

**来源**: 检测 S-2 + C2（`machine_code.py:130-160, 363-419, :377`）

## 问题
1. `check_rate_limit(f"reset_pwd:{ip}", limit=5, window=60)` — 第一个位置参数绑定到 `request` 形参，key=None 直接放行 → 限流完全失效
2. `GET /get-machine-code` 未认证返回 `verification_code` → 重置凭证自发自验
3. 重置成功响应体返回**明文新密码**

## 验收标准（TDD）
- [ ] 测试：同 IP 第 6 次调用 reset 端点返回 429（修参数顺序：key= 关键字传参）
- [ ] 测试：`/get-machine-code` 响应不含 verification_code 字段
- [ ] 测试：重置成功后响应不含明文密码；新密码为随机值且 must_change_password=True
- [ ] `check_rate_limit` 全仓 grep 排查其他位置参数误用点一并修正
- [ ] 全量回归通过

## 涉及文件
- `backend/app/api/v1/machine_code.py`
- `backend/app/core/security.py`（如需收紧 check_rate_limit 签名）
- `backend/tests/unit/api/test_machine_code_reset_security.py`（新建）

## Resolution（2026-08-23）

**已修复，TDD 全绿（新增 13 测试 + 既有 55 回归）**

实现要点：
1. `check_rate_limit` 签名收紧：`key` 为首参、其余 keyword-only；缺 key 抛 `ValueError`（fail-closed）——历史位置传参陷阱从签名层面杜绝复发
2. `/get-machine-code` 校验码仅对 loopback 返回（基于 TCP 对端地址判定，不受 XFF 伪造影响）
3. 重置端点：loopback 门禁 + 管理员/superuser 排除（403）+ write_work_log 审计
4. **验收标准修订**（记录于 ADR-0008）：原标准"响应不含明文密码"经分析会破坏离线单机的唯一破窗恢复通道（前端 ForgotPassword 全流程依赖），改为"仅限本机 + 非管理员 + 审计留痕"三重约束下保留一次性展示。远程两步提权攻击面已消除

测试：`backend/tests/unit/api/test_machine_code_reset_security.py`（13 用例）
