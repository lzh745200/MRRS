---
labels: [done, severity-high]
blocks: []
blocked-by: []
---

# W5-T4 后端 envelope 收敛（重灾区四模块）

**来源**: 检测 L-1（approval.py 20+ 处手写 dict、auth/rbac.py 14 处裸 success、user_permissions.py 11 处、machine_code.py；另有裸 Pydantic 返回：todos/rural_tasks/messages/work_logs/organization/project_milestones/validation）

## 验收标准
- [ ] 四大重灾区全部改 success_response()/ok_list()
- [ ] 裸 Pydantic 返回端点包 envelope
- [ ] 对应前端调用点同步适配（_unwrapList 已兼容，重点验证无二次 .data）
- [ ] 相关测试断言改为 data 路径并全绿

## 涉及文件
- `backend/app/api/v1/{approval,auth/rbac,user_permissions,machine_code,todos,rural_tasks,messages,work_logs,organization,project_milestones,validation}.py`

## Resolution（2026-08-30）

**已完成，提交 101ec12c。** 7 个文件 51 处裸 dict 响应收敛为 success_response/ok_list：
user_permissions(14)、auth/rbac(16)、system/monitor(6)、system/admin(7)、encryption(4)、
offline_map(3)、approval(1 create-workflow)。前端经 axios 拦截器 data 展开后向后兼容，
24 个测试文件 490 用例全绿（2 处精确形状断言同步更新）。

遗留（有意保留）：admin.py GET /info（response_model 约束）、help.py/system/backup.py/
machine_code.py（并行会话在途文件，待后续轮次）、approval.py 其余裸 dict 端点、
data_packages.py 裸 pydantic 返回与 versions 端点裸 {success,data}（前端+测试依赖现状，
属 W5-005 前端收敛联动项）。
