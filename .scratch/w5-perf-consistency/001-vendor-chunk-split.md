---
labels: [ready-for-agent, severity-high]
blocks: []
blocked-by: []
---

# W5-T1 vendor 拆分与首屏瘦身（目标 gzip ≤350KB）

**来源**: 检测 P1-1（`vite.config.ts:330-332` 兜底 vendor 吞掉 xlsx 动态导入；element-plus 735KB 整包 modulepreload；首屏 1.92MB）

## 验收标准
- [ ] manualChunks 函数式分组：xlsx/driver.js 独立 chunk 且不落 vendor（恢复动态导入收益）
- [ ] element-plus 恢复按需分包（循环依赖警告定向抑制）
- [ ] 构建产物实测：vendor 无 xlsx/lodash/core-js；index.html 不 modulepreload 重型 chunk
- [ ] 首屏关键 JS gzip ≤ 350KB（记录前后对比数据）
- [ ] npm run build + 全量 vitest 绿

## 涉及文件
- `frontend/vite.config.ts`
