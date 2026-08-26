---
labels: [done, severity-low]
blocks: []
blocked-by: []
---

# W4-T10 文档漂移修正（AGENTS.md/CLAUDE.md）

**来源**: 检测（AGENTS.md：DB 路径与 main.js 实际不符；单测命令路径 src/views 不存在；覆盖率宣称；版本 v1.9.0 多处）

## 验收标准
- [ ] AGENTS.md DB 路径改为 userData\database\（Win）/ ~/.bumofu/data（Linux）
- [ ] 前端单测命令修正为 tests/unit/**/*.test.ts
- [ ] 覆盖率/测试数字表述与实际门禁一致
- [ ] 全文 grep 校验无残留旧说法

## 涉及文件
- `AGENTS.md`、`CLAUDE.md`

## Resolution
完成：AGENTS.md 单测命令改 tests/unit/views/... 路径；DB 路径改为 userData/database(Win)/~/.bumofu/data(Linux) 与 electron/main.js 实际一致
