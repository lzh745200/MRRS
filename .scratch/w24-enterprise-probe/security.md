# W24 企业级探测 · 安全深度审计与加固报告（task-3 / security-probe）

- 时间：2026-10-19
- 基线：git main（探测开始时 HEAD 5a182cd，v1.15.4）；后端 `backend/.venv/Scripts/python.exe`；Node 25/npm 11
- 审计范围（写入范围）：`backend/app/core`、`backend/app/middleware`、`backend/app/utils`、`electron/main.js`、`electron/preload.js`、`docker/`、`nginx/`
- 结论：**未发现 P0（可直接接管/绕过认证读到数据）缺陷**；修复 4 项 P1（含 1 项真实日志 PII 泄漏、1 项构建不可用、2 项配置红线），另有 1 项 P1、约 10 项 P2 需 Lead/产品决策，见下。

## 一、P0（必须本次修复）

无。

## 二、P1（应修）

### P1-1【已修复】JSON 文件日志绕过 PII 脱敏：异常堆栈里的身份证/手机号明文落盘

- 现象：默认配置 `LOG_FORMAT=json` 时，任何带异常堆栈的 ERROR 日志（如 DB IntegrityError 回显用户输入）在 `app.log` 中明文写出身份证号/手机号；`record.message` 已脱敏但 `exception` 字段未脱敏。
- 证据（修复前复现脚本输出）：
  - 命令：`cd .; backend\.venv\Scripts\python.exe .scratch\w24-enterprise-probe/repro_log_redaction.py`（脚本已留档，可复跑）
  - 结果：`exc_text redacted: True`，但 `LEAK_IN_JSON_LOG: True`；JSON 的 `exception` 字段含 `id_card=110101199001011234 phone=13800138000`。
- 根因：`SensitiveDataFilter.filter()` 把脱敏后的堆栈写入 `record.exc_text`（CPython 标准 `Formatter.format()` 会复用该缓存），但自定义 `JsonFormatter.format()` 直接调用 `self.formatException(record.exc_info)` 按 `exc_info` **重新渲染原始堆栈**，绕过了脱敏；`logging_config.py:111-115` 的注释声称依赖标准 Formatter 行为，而本类是自定义 Formatter，该假设不成立。
- 修复：`backend/app/core/logging_config.py:154-158` —— `log_entry["exception"] = record.exc_text or self.formatException(record.exc_info)`（优先复用脱敏缓存，无缓存时回退原渲染，保持既有单元测试断言）。
- 验证：
  - 复现脚本复跑：`LEAK_IN_JSON_LOG: False`，输出中身份证/手机号均为 `***`。
  - 新增回归测试 `backend/tests/unit/test_log_redaction_json_formatter.py`（2 例：脱敏复用 + 无 filter 回退分支）。
  - `pytest tests/unit/test_cov_gap_r32_core.py tests/unit/test_log_redaction_json_formatter.py tests/unit/test_logging_config_cov.py -q --cov=app.core.logging_config --cov-branch --cov-fail-under=0` → 27 passed；logging_config 语句 0 miss，分支仅剩 31->35（既有 SafeTimedRotatingFileHandler 平台分支，基线说明属非本次改动，全量套件覆盖）。
- 影响面：所有含异常堆栈的日志（登录/导入/DB 错误），属真实现网 PII 落盘风险，修复成本 1 行。

### P1-2【已修复】`docker/Dockerfile` 引用不存在的 `electron-builder` 构建阶段 → 文档化 Docker 部署与 `make test-e2e-docker` 必然构建失败

- 现象：`docker/Dockerfile` 第 120-123 行（原）为 `COPY --from=electron-builder /app/electron/dist/ ...`，但本文件只有 `frontend-builder` / `backend-builder` / `runtime` 三个阶段；BuildKit 把 `electron-builder` 当作外部镜像名去 registry 拉取，本地无同名镜像时 build 直接失败。
- 证据：`git grep -n -- '--from=' docker/Dockerfile`（修复前含 electron-builder）；`git log -S electron-builder` 显示该阶段已于 W6-T8 删除（CHANGELOG 记录「删除从未可构建的 electron-builder 阶段」），COPY 遗漏未删。构建入口 `docker-compose.yml:18`（`dockerfile: docker/Dockerfile`，`target: runtime`）与 `Makefile:63-71` 的 e2e 路径均受影响。
- 修复：删除该 4 行（改留注释说明），`docker/Dockerfile:120-126`。
- 验证：`Select-String docker/Dockerfile -Pattern '--from='` → 仅 `backend-builder`、`frontend-builder` 两个已定义阶段（第 114/118 行）；`^FROM ` 仅 3 个已定义阶段。**限制**：本机无 Docker CLI（`docker --version` → CommandNotFound），未能实际执行 `docker build`，建议由 Lead 在有 Docker 的机器/CI 上跑一次 `docker build -f docker/Dockerfile --target runtime .` 复核。

### P1-3【已修复】按用户数据范围裁剪的 API 响应被标 `Cache-Control: public`（跨用户/跨组织缓存泄漏红线）

- 现象：`backend/app/middleware/cache_headers.py` 对 `/api/v1/supported-villages/filter-options` 与 `/api/v1/organizations/tree` 下发 `public, max-age=300`。两者响应均按当前用户数据范围裁剪（`filter-options` 仅返回本组织及子树的部门/县市，见 `supported_village.py:666-709`；`organizations/tree` 普通用户收敛到本组织子树，见 `organization.py:349-377`）。`public` 允许任何共享缓存（反代/企业代理/多用户浏览器配置）跨用户复用响应 → A 组织数据可能返回给 B 组织（军审 S2 跨组织红线）。
- 修复：两条规则改为 `private, max-age=300`（静态资源 `/assets/`、`/images/` 保持 `public`），`backend/app/middleware/cache_headers.py:16-27`；同步更新既有断言并新增回归测试 `test_user_scoped_filter_options_not_public`（`backend/tests/unit/middleware/test_all_middleware.py:80-92`）。
- 验证：`pytest tests/unit/middleware/ -q` → 39 passed；合并 80 例定向运行后 `cache_headers.py` 覆盖率 100%（17 stmts / 10 branch）。
- 说明：`/organizations/tree` 路由自身还设置 `no-store`（`organization.py:271-276,357`），实际生效风险主要在 `filter-options`；本修复为纵深防御并消除静态规则层的错误语义。

### P1-4【已修复】nginx 部署下备份恢复/大包导入被 nginx 层拒绝（100M 上限）与默认 60s 超时

- 现象：`nginx/nginx.conf` 全局 `client_max_body_size 100M`，而备份恢复单包上限为 10GB（`backend/app/middleware/body_size_limit.py:55-62` 对 `/api/v1/system/backup` 放行 10GB；`system/backup.py` `_MAX_RESTORE_UPLOAD_BYTES` 同为 10GB），权限包/数据同步 512MB——经 nginx（`docker-compose.yml` 的 `production` profile）访问时 restore 在 nginx 层直接 413；大包导入/恢复为长耗时请求，`proxy_read_timeout` 默认 60s 会 504。
- 修复：
  - `nginx/conf.d/assistance.conf:20-34`：`location ^~ /api/`（`^~` 防止下方正则静态资源 location 抢匹配 API 下载并追加 public 缓存头）、`client_max_body_size 10g`、`proxy_read_timeout/proxy_send_timeout 600s`；
  - `nginx/nginx.conf:26-30`：全局仍 100M（避免任意路径可推 10GB），新增 `server_tokens off`。
- 验证：静态审查（行号如上）；本机未安装 nginx（无 `nginx -t` 条件），建议部署机执行 `nginx -t` 后重启复核。

### P1-5【未修复·需产品/安全决策】通行码注册回退可被「持有安装包者」自助开通**已激活**账号（多机/LAN 部署）

- **风险等级：P1（多机/LAN/经 nginx 暴露部署）｜P3（默认单机 127.0.0.1 桌面部署）**。
- **触发条件（必须同时满足，缺一不成立）**：
  1. 后端监听面不是回环（`HOST=0.0.0.0`，或经 nginx/局域网访问；默认配置 `HOST=127.0.0.1`，默认单机桌面**不满足**）；
  2. 部署未配置 `PASS_CODE_SECRET`（默认空 → 使用随安装包分发的内置常量密钥，见证据链 1）；
  3. 攻击者能请求 `GET /api/v1/machine-code/get-machine-code`（该端点无需认证，且对非回环请求也返回 machine_code，见证据链 3）；
  4. 攻击者能调用 `POST /api/v1/auth/register`（仅 3 次/分钟/IP 限流，可慢速持续尝试）。
- **影响边界（不夸大）**：可自助创建 **is_active=True** 的普通账号（role=user、数据范围 OWN=只能读写自己创建的数据，**不能读他人/跨组织数据**）；可绕过「管理员开户」审计、占用用户名/邮箱、以 user 角色写入其有权创建的业务对象；可重复注册多账号。**不会直接造成数据泄露、也不会提权**——自助重置/降级管理员通道已被 403 拒绝（`api/v1/machine_code.py:445-456`）。

- 现象链（4 处叠加）：
  1. `PASS_CODE_SECRET` 默认空 → `machine_code_service.py:35-36` 使用**随安装包分发的内置常量密钥** `bumofu-assistance-passcode-v1`；注释明确「掌握应用者可为自己机器离线计算通行码自注册」（`machine_code_service.py:329-334`，2026-09-06 产品决策）。
  2. 通行码 = `HMAC-SHA256(密钥, machine_code)` 截断（`machine_code_service.py:268-295`），确定性、可离线重算。
  3. `GET /api/v1/machine-code/get-machine-code` 无需认证且对**非回环**请求也返回 machine_code（仅 verification_code 限回环，`api/v1/machine_code.py:160-194`）→ 远程攻击者可直接取到目标机器码。
  4. `/auth/register` 第 4 级 HMAC 自验证通过后创建 `is_active=True` 用户并直接返回令牌（`auth/auth.py:888-903, 920-931`），**无管理员审批**；仅 3 次/分钟/IP 限流（`auth/auth.py:858-871`）。
- 影响：多机协同/`HOST=0.0.0.0` 部署下，LAN 内任何能访问 API 的攻击者可用「安装包内置常量 + 公开机器码接口」自助注册 active 账号（默认 role=user、数据范围 OWN，不能直接读他人数据，但可写入业务数据、占用账号、绕过管理员开户审计）；单机 `HOST=127.0.0.1` 桌面部署影响小。
- 根因：跨机注册可用性（产品反馈 R9）压过 fail-closed 安全基线；`PASS_CODE_SECRET` 未在部署模板强制。
- **决策归属：Product Decision（产品负责人）+ 安全负责人共同拍板** —— 本质是「跨机注册可用性（ADR-0004 / 2026-09-06 产品决策，R9 生产反馈驱动）」与「注册闸门强度」的取舍；安全侧只能给出风险量化，不能单方面改产品语义。技术落地由 api/service 层负责人执行（不在 security-probe 的写入范围）。
- 建议选项（按推荐顺序，均不改变正常跨机注册体验）：
  1. **部署强制**：所有多机/发布模板强制 `PASS_CODE_SECRET=<随机≥32 位>`（目前 `deploy/kylin/config/kylin.env`、`.env.example` 只有注释无强制），并在生产启动自检里对「多机部署 + 未配置」告警/拒绝；
  2. **注册审批**：`/auth/register` 创建的账号改为 `is_active=False`（进入管理员审核队列），跨机注册体验不变但重获开户审批闸门；
  3. **公开面收口**：`get-machine-code` 对非回环请求不再返回 machine_code（或加来源白名单/限流），抬高自动化利用门槛；
  4. **可选**：`ENVIRONMENT=production` 且未配置 `PASS_CODE_SECRET` 时，HMAC 自验证路径 fail-closed（会牺牲无预录通行码的跨机注册，需产品确认）。

## 三、P2（建议，未修改）

1. **CSRF 退化路径 + 豁免面**：`csrf_middleware.py:273-283` 保留「cookie 与 header 明文相等即通过」的旧版回退（可被可控 cookie/XSS 绕过 HMAC 签名）；`_CSRF_EXEMPT_PATH_PREFIXES`（同文件 45-55）豁免 `/api/v1/auth/login|register|shutdown`。评估：本系统认证走 `Authorization: Bearer`（localStorage）而非 cookie，CSRF 天然影响低，且 `compare_digest` 常量时间比较正确；建议删除明文回退或按 `DEBUG` 开关收口，并评估 login 豁免（登录 CSRF）。
2. **CORS 生产含 dev 源**：`config.py:162-165` 默认 `CORS_ORIGINS` 含 `127.0.0.1:5173/localhost:5173`（Vite dev），打包生产仍允许该源带凭证请求；建议 `ENVIRONMENT=production` 时过滤 dev 源（dev 走 Vite 代理为同源，不受影响）。
3. **Electron 可再加两处硬化**：`electron/main.js` 无 `session.setPermissionRequestHandler`（渲染进程理论上可请求 camera/mic/geolocation/notification，虽被后端 `Permissions-Policy` 头拦截）；`setWindowOpenHandler`（main.js:755-768）对同源 URL 返回 `action: allow`（建议一律 deny 并导航同窗口）。现有基线已达标：`nodeIntegration:false / contextIsolation:true / webSecurity:true / sandbox:true`（main.js:703-709）、`will-navigate` 精确 origin+端口白名单与 file:// 目录白名单（716-753）、preload 仅暴露 6 个通道（`electron/preload.js:25-45`）、IPC 路径白名单 `path-guard.js`（含密钥文件名黑名单）。
4. **上传 magic 校验不一致**：`utils/upload_helper.py:315` `enforce_image_magic` 默认 False，仅 `api/v1/files.py:98` 传 True；funds/policy/projects 等附件以扩展名白名单为准。风险被「`X-Content-Type-Options: nosniff` + 附件 attachment 下载 + 不接受 svg」压低，建议统一开启图片 magic 嗅探。
5. **`/uploads` 静态挂载无鉴权**：`core/static_files.py:49` 直接 `StaticFiles(directory=uploads_dir)`，附件 URL 可被同机/LAN 未认证访问；当前由「HOST 默认 127.0.0.1 + 文件名 uuid 前缀不可枚举」缓解。若多机部署改 `0.0.0.0`，建议改为鉴权下载端点（或保留但写入部署文档风险声明）。
6. **ZIP 条目数量无上限**：`upload_helper.ensure_zip_within_limit` 只按解压后总字节限制（200MB），未限制条目数（海量 0 字节条目可放大 CPU/元数据内存）。建议补条目数上限（如 10000）。
7. **依赖 CVE 复核方式退化**：本机 venv 未安装 `pip-audit`（`python -m pip_audit` → No module named pip_audit），本轮无法复跑；`backend/requirements.txt:16-18,36-39,93-97,115-117` 记录了 2026-10-03 pip-audit 结果与处置（anyio 4.14.2 / PyJWT 2.15.0 / urllib3 2.8.0 均已按 Fix Versions 升级；diskcache 5.6.3 上游无修复，已用 JSONDisk 闭环 pickle RCE 面）。前端 `npm audit --omit=dev --json` 实测 **0 漏洞**（metadata: low/moderate/high/critical 全 0）。建议 CI 恢复 pip-audit 门禁。
8. **版本同步目标失效（docker 元数据陈旧）**：`scripts/sync-version.js:139-161` 的 `Dockerfile (echo banner)`/`Dockerfile.runtime (LABEL version)` 目标写的是仓库根 `Dockerfile`/`Dockerfile.runtime`（不存在，`optional:true` 静默跳过；实际文件在 `docker/` 下）→ `docker/Dockerfile.runtime:24` LABEL 仍为 1.10.0、`docker/Dockerfile:134` 启动横幅仍 v1.10.0，永远不会被单源同步。属 scripts 范围，建议 Lead 指派修正 target 路径（或删除死目标），我这侧不改脚本以免与版本同步作业冲突。
9. **`.env.example` 两份默认不一致**：根 `.env.example:9` `ENVIRONMENT=development`、`:120` `ENABLE_AUTO_MIGRATION=true`，而 `backend/.env.example:24` 为 production（且生产基线自动生成加密密钥只在 production 分支执行）；复制根示例当 .env 会让生产部署跑在 development 语义下。建议统一。
10. **出厂口令 + 首登强制改密**：`core/constants.py:27` `FACTORY_ADMIN_PASSWORD` 为公开文档值（离线单机首发可用性设计）；服务端强制改密已在 `security.py:288-303,430-434` fail-closed 拦截（含直连 API），属可接受设计；建议在部署文档强调保密部署必须设置 `DEFAULT_ADMIN_PASSWORD`。
11. **审计中间件 JWT 只解码不验签（设计如此）**：`core/audit_middleware.py:118-137` 用 `verify_exp:False` 解析用于归因，属审计归因用途，非鉴权路径，无越权影响；仅提示勿复用该函数做授权判断。

## 四、审计覆盖与未发现问题的面（取证结论）

- 认证/会话：`security.py` 密码策略/哈希（bcrypt rounds 12、72 字节截断）、JWT（PyJWT、HS256、access/refresh type 区分、`two_factor_pending` 禁用、jti 黑名单、token_version fail-closed、首登强制改密服务端兜底）均通过；登录锁定（`lockout_service` 原子递增）、登录 5 次/分 IP 限流、refresh 轮换+吊销+用户态校验、登出 bump token_version 均存在。`token_blacklist` 内存+DB 双写、永久条目上限与节流清理正确。
- 密钥/配置：仓库无硬编码真实密钥（`grep password|secret|api_key = 字面量` 仅命中公开出厂口令常量）；`.env` 不入库（`.gitignore` 覆盖）；运行期密钥 `runtime_secrets.json` 强度≥32、原子写、Unix 0o600、损坏拒绝覆写、静态加密密钥 `require_persisted=True` fail-closed；PII 透明加密 AES-SIV 确定性加密、密钥 SHA-512 派生、解密失败可观测（指纹/统计）。
- 授权：`core/data_permission.py` fail-closed（无组织降级 OWN、`check_record_access` 组织两侧 NULL 拒绝、`apply_scope_filter` 默认严格、`admin_full_access` 仅显式）、`is_admin` 单一入口（仅 super_admin/admin/is_superuser）、`require_admin` 装饰器用 inspect 判定防 Mock 绕过。
- Web 安全：安全响应头单一事实源（CSP `script-src 'self'`、X-Frame-Options DENY、nosniff、Referrer-Policy、Permissions-Policy、HSTS；`security.py:731-791`，测试 `test_core_security` 9 例通过）；全局异常处理器不泄漏堆栈（`exceptions.py:164-219`）；BodySizeLimit 按真实字节流限长（伪造 Content-Length 无效，`_StreamingBodyGuard`）；维护闸门写请求 503。
- 文件/上传：`upload_helper.py` 分块流式落盘+滚动限长+残片清理、basename 净化（Windows `` 与 `/` 双分隔符）、`commonpath` 落盘越界兜底、SHA-256 去重引用计数；ZIP 解压前总量闸门+成员限长（数据包/权限包/管控包/上报包/备份全覆盖）。未发现 `extractall` 路径穿越（`backup_service._safe_extractall` 单独审查）。
- 注入面：`shell=True` 0 处；`eval/exec` 0 处；无 lxml/XML 解析调用（XXE 面实质不存在）、无模板渲染注入面；`urllib/外部抓取` 0 处（唯一 httpx 为告警 webhook 且 URL 来自管理员配置）；SQL 原始 f-string 均有 `nosec B608` + 白名单（既有门禁 NEW=0）；`subprocess` 调用点（机器码 wmic/powershell、重启）无 shell 且参数列表化。
- Web 安全未发现项：`/docs`/`/openapi.json` 仅在 DEBUG 开启（`main.py:118-120`），默认 production 关闭。

## 五、变更文件清单（本次已修改）

| 文件 | 变更 | 对应发现 |
| --- | --- | --- |
| `backend/app/core/logging_config.py` | JsonFormatter 复用脱敏 exc_text | P1-1 |
| `backend/tests/unit/test_log_redaction_json_formatter.py` | 新增 2 条回归测试 | P1-1 |
| `backend/app/middleware/cache_headers.py` | 用户范围 API 缓存 public→private | P1-3 |
| `backend/tests/unit/middleware/test_all_middleware.py` | 断言更新 + 新增 filter-options 回归 | P1-3 |
| `docker/Dockerfile` | 删除未定义 electron-builder 阶段 COPY | P1-2 |
| `nginx/nginx.conf` | server_tokens off + 注释 | P1-4 |
| `nginx/conf.d/assistance.conf` | ^~ /api/ + 10g body + 长超时 | P1-4 |
| `.scratch/w24-enterprise-probe/repro_log_redaction.py` | P1-1 复现脚本（留档） | P1-1 |

## 六、自验命令与结果（本轮实跑）

1. `pytest tests/unit/middleware/ tests/security/ tests/unit/test_log_redaction_json_formatter.py tests/unit/test_logging_config_cov.py tests/unit/test_logging_redaction_cov.py tests/unit/test_ocr_20260917_middleware.py tests/unit/test_core_security.py -q` → **99 passed**（含 CSRF ASGI 15 例、security 目录 9 例）。
1b. **`pytest tests/security/ -v` 全量复跑（cache_headers/logging_config 改动落地后）→ 9 passed**：test_audit 3 例（bandit 高危、参数化查询、密钥文件权限）+ test_data_isolation 6 例（data_scope/is_admin/is_superuser/filter_by_data_scope 存在性 + 管理员放行/普通用户隔离两行为例），3.53s，exit=0。
1c. 改动未被并行会话覆盖校验：`git diff HEAD -- backend/app/core/logging_config.py backend/app/middleware/cache_headers.py backend/tests/unit/middleware/test_all_middleware.py backend/tests/unit/test_log_redaction_json_formatter.py docker/Dockerfile nginx/` → **输出为空**（工作区与 HEAD `9de7aea` 一致，4 项修复均在位，逐行 grep 标记复核通过）。
2. `pytest tests/unit/middleware/ tests/unit/test_log_redaction_json_formatter.py tests/unit/test_logging_config_cov.py tests/unit/test_ocr_20260917_middleware.py -q --cov=app.middleware.cache_headers --cov=app.core.logging_config --cov-branch --cov-fail-under=0` → `cache_headers.py` 100%、logging_config 语句 0 miss（仅 31->35 平台分支属既有）。
3. `flake8 app/core/logging_config.py app/middleware/cache_headers.py --max-line-length=120 --max-complexity=16` → 0。
4. `python .scratch/w24-enterprise-probe/repro_log_redaction.py` → `LEAK_IN_JSON_LOG: False`。
5. `npm audit --omit=dev --json`（frontend）→ `{"info":0,"low":0,"moderate":0,"high":0,"critical":0,"total":0}`。
6. `docker --version` → CommandNotFound（Docker CLI 不可用，docker 构建未能实跑）；`nginx -t` 无 nginx 可执行文件（未实跑）。

## 七、遗留风险与建议

- P1-5（通行码自注册）是本次最大未决安全面，涉及 api/service 层与既有产品决策，需 Lead 决策后由对应负责人处理。
- docker/nginx 两处修复为静态验证，需在具备 Docker/nginx 的环境做一次冒烟（`docker build --target runtime`、`nginx -t`）。
- **协作异常（重要，已由 Lead 查明）**：外部提交 `9de7aea` 由另一个并行 AI 会话执行 `git add -A` 造成（非本 agent；我全程未执行任何 git 操作），已 **push 到 origin/main**，消息中未说明夹带的改动。该提交除各 agent 修复外，还误纳入 `_probe_bandit.json`（4804 行）、`backend/bumofu_pytest_appdata_*/**/runtime_secrets.json`（测试生成的运行期密钥样例）、`backend/pytest-of-Administrator/**` 等测试残留，与「不 commit / 不改版本号」硬约束冲突；Lead 已记录并将在最终报告中统一说明/整理，本 agent 未改写历史提交。
- 我的 7 处改动已被该提交纳入但**内容完好**：`git diff HEAD` 为空 + 逐行标记复核（见六.1c）；后续如需重建干净提交，直接保留这些文件当前内容即可。
- 未覆盖说明：本轮未重复跑全量 pytest/vitest（Lead 已在跑）；前端代码不在我的写入范围（仅审计了其消费的服务端语义）。
