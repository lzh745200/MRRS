---
labels: [ready-for-agent, severity-high]
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
