# 001 深度逐模块 HTTP 探针 R1/R2 — 注册 refresh 契约修复 + 业务模块全通过

- 状态: done
- 波次: w14-deep-probe
- 日期: 2026-09-05
- 触发: 用户「不许停下」→ 持续逐模块真实 HTTP 验证循环（goal-2d04c23b）

## R1 发现与修复
- 🐛 `/auth/register` 返回 access 却无顶层 `refresh_token`（login 有）→「注册即登录」
  契约不一致、记住登录 refresh 持久化分支对新会话恒缺失。
- 修复: commit `63e7b1b` — `auth.py` register_user 改 `create_token_pair`（含
  token_version 声明），LoginResponse 顶层返回 refresh_token；`test_auth_auth_api.py`
  两条注册成功用例改 mock create_token_pair 并断言 refresh；CHANGELOG 1.11.5 补条目。
- 验证: auth 相关 63 passed；flake8 app 0；隔离实例(probe_r1, 8004) HTTP 全链路：
  组织通行码注册 → 响应含 refresh → /auth/refresh 200 → 旧 refresh 重用 401 → 新
  access 可用(machine-info 200)；机器码/组织绑定落库正确（machine_codes org 绑
  user_id=3、users.organization_id=1）。

## R1 其他通过项
- 组织通行码全链（校验码→生成→注册 level-2 回退）PASS
- 异步导出 villages（force_async → status completed → download 5599B → tasks 列表）PASS
- 权限包 export→import 预览→confirm 落库（organizations_updated=1 等）PASS
- data-sync /export（Query 参数，非 body）→ 包 4249B + download 200 PASS

## R2 业务模块（probe_r2, 8005）— 全部 PASS 无缺陷
- 列表信封: supported-villages/funds/projects/policies/schools/organizations/users/
  work-logs/menus-accessible 全 code=200
- 政策导出 excel/pdf/wps 200；经费 excel（/export/funds）200
- 普通用户（通行码注册,refresh 已含）: policies 列表/创建(id 11)/详情/删除 全 200
- 备份: POST /system/backup 创建 backup_id=22 → 列表含该项 200

## 备注
- 探针均用 VACUUM INTO 克隆 dev 库 + 重设 admin 密码，端口 8004/8005 隔离实例，
  完成后产物与进程全部清理；工作区 git 0 残留。
