---
labels: [ready-for-agent, severity-critical]
blocks: []
blocked-by: []
---

# T2 关闭未认证任意文件写入（permission_package /import）

**来源**: 检测 S-1（`permission_package.py:120-145`）

## 问题
`POST /import` 无认证依赖、无 localhost 限制（对比 `/confirm`:181 有）；`file.filename` 仅 endswith(".zip") 即 join → `../../x.zip` 路径遍历写文件。同文件 :99 download 已有正确净化可参照。

## 验收标准（TDD）
- [ ] 测试：匿名调用 `/import` 返回 401（与 /confirm 同样的门禁）
- [ ] 测试：filename=`../evil.zip` 或含反斜杠路径分隔符时返回 400，且磁盘无越界写入
- [ ] 净化逻辑抽公共函数供 import/confirm 复用
- [ ] 全量回归通过

## 涉及文件
- `backend/app/api/v1/permission_package.py`
- `backend/tests/unit/api/test_permission_package_upload_safety.py`（新建）

## Resolution（2026-08-23）

**已修复，TDD 全绿（新增 7 测试）**

1. `/import` 补齐门禁：未认证调用仅限本机（`_client_is_loopback` 基于 TCP 对端地址），已认证管理员不限——与 `/confirm` 策略对齐，保留离线首导场景
2. 新增 `_resolve_package_upload_path()`：basename 等价 + 反斜杠拒绝 + realpath 越界校验，`/import` 与 `/confirm` 共用
3. **额外发现并修复**：`/confirm` 原样 join `file_name` 且 finally 无条件 unlink → `%5C` 遍历可致任意文件删除；现已封堵

测试：`backend/tests/unit/api/test_permission_package_upload_safety.py`
