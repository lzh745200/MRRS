# 全链路探针回归资产（2026-09 深度探测循环固化）

9 个真实 HTTP 全链路探针（共 200+ 断言），覆盖 30+ 功能模块的主业务链、
并发竞态与契约语义。源自 2026-09 深度探测循环（详见
`.scratch/w14-deep-probe/002-zcode-probe-r1-r3.md`），累计发现并修复
9 个产品缺陷——本目录是这批缺陷的**常驻回归防线**。

## 运行

```bash
cd backend
.venv/Scripts/python tests/probe/run_all.py        # 全部（约 25 分钟）
.venv/Scripts/python tests/probe/run_all.py r1 r8  # 指定轮次
.venv/Scripts/python tests/probe/probe_r8_concurrency.py  # 单个
```

退出码：0 = 全部通过；1 = 有失败。每项断言实时打印 PASS/FAIL。

## 隔离契约（必读）

- 每个探针启动时设置 `BUMOFU_BACKEND_DIR_OVERRIDE` + `DATABASE_URL` +
  `UPLOAD_DIR` 指向**本次运行的临时目录**——绝不读写真实 `backend/data/`。
- ⚠️ 任何新探针都必须遵守此契约：`get_app_data_dir()` 在开发环境固定指向
  backend 根目录（与 CWD 无关），漏设 override 会把探针数据写进真实数据区。
- pytest 不会收集本目录（`python_files = test_*.py`），探针仅供手工/CI
  定期执行，不影响测试套件时长。

## 覆盖范围

| 轮次 | 文件 | 覆盖 |
|---|---|---|
| r1 | probe_r1_passcode_register.py | 组织通行码注册→登录、refresh 轮换（旧 token 吊销）、异步导出、权限包、数据同步导出 |
| r2 | probe_r2_approval_reports_map.py | 审批流全生命周期（submit/approve/submit-auto）、报表模板、地图、消息、待办、监控健康 |
| r3 | probe_r3_funds_state_yearly_rbac.py | 经费状态机守卫（附件门槛/终态拒绝）、村年度板块、RBAC、系统配置、备份调度 |
| r4 | probe_r4_policy_school_worklog_2fa.py | 政策/学校/项目/工作日志、通知偏好、2FA、个人资料、报表订阅、模板上传确认 |
| r5 | probe_r5_scholarship_incremental_marker.py | 乡村工作台、奖学金导入、增量三端点、地图坐标写入、update-logs、消息推送联动 |
| r6 | probe_r6_contract_voucher_conflict.py | 合同链、转账凭证（预算校验）、数据同步冲突解决、subordinate 级联 |
| r7 | probe_r7_help_assessment_effectiveness.py | 帮助文档全量、考核评估、成效评估 |
| r8 | probe_r8_concurrency.py | 并发：同记录写/审批竞态/并发备份/注册竞态/并发导入 |
| r9 | probe_r9_quality_analytics_chunked.py | 数据质量、分析、离线地图、机器码管理、分片上传全链、通知偏好 |

## 已知修复清单（本资产锁定的缺陷）

通行码注册改绑（阻断级）、data-sync 下载路径双源、模板三形态 500+零写入、
奖学金导入字段映射坏死（阻断级）、悬挂 village_id 500、并发备份同毫秒冲突、
通行码注册并发竞态、覆盖率墙钟黑洞——全部带单元级锁定测试
（`test_r5_probe_locks.py` / `test_backup_path_alignment.py` /
`test_coverage_gap_batch3.py` 等），本目录是**链路级**第二道防线。
