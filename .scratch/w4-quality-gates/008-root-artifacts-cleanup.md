---
labels: [ready-for-agent, severity-low]
blocks: []
blocked-by: []
---

# W4-T8 仓库卫生：根目录遗留物清理 + make clean 扩展

**来源**: 检测（根目录 17 个 vitest 日志/json、test.db、.coverage；`Makefile:66-71` clean 不扫根目录）

## 验收标准
- [ ] 删除根目录 vitest-*.{log,json}、test.db、.coverage 及 frontend 下同类
- [ ] make clean 增加根目录清理段
- [ ] .gitignore 补 `data_sync/`、根目录 `vitest-*`
- [ ] git status 干净（不误删被跟踪文件）

## 涉及文件
- 根目录、`Makefile`、`.gitignore`
