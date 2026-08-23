---
labels: [done, severity-high]
blocks: []
blocked-by: ["w0-baseline/001-freeze-baseline.md"]
---

# 015: 孤儿视图清除×4 + 双区段跳转化

**What to build:** 删 BatchImport.vue（进度条逻辑移植 DataImport.vue）、dataVerify/Index.vue、dataManagement/Overview.vue、report/List.vue；ImportSection/ExportSection 改为跳转 /data-sync/*；dataManagement 备份占位卡移除。

**Acceptance criteria:**
- [ ] 四文件与路由引用零残留
- [ ] DataImport 上传具备 onUploadProgress 进度条（vitest）
- [ ] dataManagement 页签跳转可用
- [ ] 前端全量回归绿

## Resolution（v1.10.0）
7孤儿视图+2区段组件删除,tab改跳转卡,进度条移植因request封装限制未做(记录)
