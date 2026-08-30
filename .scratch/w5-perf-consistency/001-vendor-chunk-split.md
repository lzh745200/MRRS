---
labels: [done, severity-high]
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

## Resolution（2026-08-30）

**实测已达标，无需再拆。** 生产构建（npm run build）后首屏脚本集合
（index + vue-core + vendor + vue-router + pinia + lodash + axios + element-plus-icons，
即 dist/index.html 引用的全部同步脚本）gzip 合计 **149KB**（brotli 更低），
远低于 ≤350KB 目标。xlsx（951KB）、echarts（682KB）、chartjs（192KB）、
guizhou 地区数据（539KB）均已在独立懒加载 chunk。chart.js 整体删除后
还会再减一个 192KB 懒加载块（归 W11 UI 图表统一工单）。
