---
labels: [ready-for-agent, severity-critical]
blocks: []
blocked-by: []
---

# T4 政策预览 XSS 转义

**来源**: 检测 S-4（`policy.py:926-932, 950-953`）

## 问题
`policy.title`/`policy.content` 未转义即以 text/html 内联返回（StreamingResponse），存储型 XSS。mammoth 分支拼接 title 同样受影响。

## 验收标准（TDD）
- [ ] 测试：创建标题含 `<script>alert(1)</script>` 的政策，预览响应体不含未转义 `<script>`
- [ ] content 为用户 HTML 时按纯文本渲染或经白名单净化（与前端 dompurify 策略一致）
- [ ] mammoth 分支 title 同样转义
- [ ] 全量回归通过

## 涉及文件
- `backend/app/api/v1/policy.py`
- `backend/tests/unit/api/test_policy_preview_xss.py`（新建）

## Resolution（2026-08-23）

**已修复，TDD 全绿（新增 3 测试）**

1. 无附件 HTML 预览：title/content 经 `html.escape` 转义
2. docx mammoth 分支：title 转义，mammoth 产物保持原样（不二次转义）

测试：`backend/tests/unit/api/test_policy_preview_xss.py`
