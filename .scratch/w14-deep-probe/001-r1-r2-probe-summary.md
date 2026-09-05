# 001 深度逐模块 HTTP 探针 R1–R4 — 注册 refresh 契约修复 + 业务/辅助模块全通过

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

## R3（8006, GET 扫测）— 无 5xx
消息/未读计数/提醒/系统配置/审计日志/登录尝试/导出审计/异步任务/反馈/数据包/同步状态
等全部正常返回；数个 404 为路径猜测噪音（docs 未暴露 OpenAPI，无法自动发现）。

## R4（8007, 前端 API 层收割真实端点 GET 大扫，~90 个）— 0 失败
覆盖：messages/notifications-preferences/reminders/audit(logs+login-attempts+exports)/
data-packages/import-history/search/help(categories,articles,system-info)/todos/
system-tasks(+stats+running-count)/backup/machine-code(admin-list,machine-info,org-list)/
map(config,county-coords,regions,tile-info,distances)/offline-map-status/sentiment/
effectiveness/approval(workflows+tasks all/pending/mine/history)/data-tier(stats,summary,
archives)/secrets(versions,status)/zero-trust(assessment,policies,events,stats)/validation/
error-reports(+stats)/i18n(languages,current)/update-logs(+latest+check-version)/env-check/
data-sync-logs/经费统计(summary,utilization-rate)/supported-villages(export modules+formats,
filter-options,templates-all)/policies(options levels+statuses,categories+tree,statistics)/
projects-stats/organizations(tree,subordinates,types-options,statistics)/schools(statistics,
options)/user-management-roles/system-monitor(snapshot,database-size,resources,alerts,
alerts-history,api-stats)/two-factor-status/rural-works(statistics,villages,years)/work-logs。
- 全部真实端点 200；guess-404 仅 3 处（/dashboard、/reports/analytics、
  /organizations/my-organization——前端另有拼接/子前缀）。

## 总结（R1–R4）
- 唯一发现的业务缺陷：注册响应缺 refresh_token → 已在 R1 修复（commit 63e7b1b，
  随 v1.11.5 发布，CI 5/5 绿）；R2–R4 无新增缺陷。
- 隔离实例与产物每次探测后清理；工作区 git 0 残留；记录同步提交入库。

