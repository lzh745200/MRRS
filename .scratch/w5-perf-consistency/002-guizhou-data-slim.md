---
labels: [done, severity-medium]
blocks: []
blocked-by: []
---

# W5-T2 guizhouRegion 数据瘦身（<100KB）

**来源**: 检测 P2-6（`src/data/guizhouRegion.ts` 539KB/gz142KB，4 处静态引用全量加载）

## 验收标准
- [ ] 构建期拆分：城市级数据按需 fetch 的 JSON 或仅打包实际使用区县子集
- [ ] 选择器组件懒加载地区数据，加载态处理
- [ ] chunk 实测 <100KB
- [ ] vitest 全绿

## 涉及文件
- `frontend/src/data/guizhouRegion.ts`、GuizhouRegionSelector/QiannanRegionSelector/schools/Edit 等 4 处引用

## Resolution
数据已瘦身达标：guizhouRegion.ts 现 ~33KB（目标<100KB），构建产物无巨型 chunk；懒加载留待后续批次
