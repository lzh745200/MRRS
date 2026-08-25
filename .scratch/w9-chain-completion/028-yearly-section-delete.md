---
labels: [done, severity-medium]
blocks: []
blocked-by: ["w0-baseline/001-freeze-baseline.md"]
---

# 028: 年度板块数据删除能力

**What to build:** 后端 DELETE /supported-villages/{id}/yearly/{year}/{section} 软性质处理+审计留痕+二次确认；前端板块卡增加删除入口。

**Acceptance criteria:**
- [ ] 删除后 completeness 校验反映缺失（pytest）
- [ ] 前端确认弹窗+刷新（vitest）
- [ ] write_work_log 留痕断言

## Resolution（v1.10.0 续批3）
后端 DELETE /yearly/{year}/{section}(404空数据防护+审计留痕)；前端板块卡删除按钮(stats非空显示)+popconfirm+刷新。flake8=0/128绿/TSC0/55绿
