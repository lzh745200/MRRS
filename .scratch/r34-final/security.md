# R34 最终安全复检报告（slice: security）

- 时间：2026-10-19 18:55 起；基线 **HEAD 2ad1f47（v1.15.12, origin 同步）**
- 范围：R33 单位授权安全面（签名/密钥/重放/降级/跨组织/导入路径/前端只读语义）+ 回归确认（viewer 只读、非回环注册门禁、PII 加密与日志脱敏、上传/ZIP 限长、CSRF/安全头）+ 依赖与密钥。
- 工作区状态：存在**他人未提交改动**（README.md、backend/app/services/grant_package_service.py（仅删未用 import `GrantSigningError`）、frontend/src/views/system/OrgGrant.vue、scripts/legacy/build-kylin.sh）。本报告审计 HEAD + 当前工作区；这些改动对安全面无影响（flake8/文档/前端展示）。
- 结论：**P0 = 无**。**P1 = 2 项（均在 R33 发布配置/默认开关层面，属发布决策，不是可被远程利用的漏洞）**；P2 = 7 项。R33 的密码学设计（Ed25519 + 规范化 JSON + 版本单调 + 默认仅收签名包）本身检查通过。

## 一、P0（可利用漏洞）

无。未发现可绕过认证/授权、可远程提权、可注入或可越权读取数据的缺陷。

## 二、P1（发布前必须处理）

### P1-1【R33 出厂配置下授权包导入功能不可用；且 GRANT_* 配置零文档，唯一「绕过」是打开 allow_unsigned（会摧毁签名防篡改）】

- 现象：`GRANT_PUBKEY` 默认空、`GRANT_SIGNING_KEY` 默认空、`GRANT_ALLOW_UNSIGNED` 默认 False（`backend/app/core/config.py:190-200`）。出厂配置下：
  - 导入**已签名**授权包 → 400 「本机未配置验签公钥，无法校验授权包来源」；
  - 导入**未签名**包 → 400 「授权包未签名；如确需导入请显式开启 allow_unsigned」。
  两条路径都拒绝 ⇒ R33「上级下发、下级导入」主链在出厂配置下**完全不可用**。
- 更严重的是配置无文档：全仓 `docs/`、`.env.example`、`deploy/kylin/config/kylin.env` 中 `GRANT_PUBKEY` / `GRANT_SIGNING_KEY` / `GRANT_GUARD_MODE` 出现次数均为 **0**（`grep -rn 'GRANT_' docs .env.example deploy/kylin` → 0 命中）。运维只能从源码发现变量；一旦按报错提示去开 `GRANT_ALLOW_UNSIGNED=true`，签名防篡改（R33 的核心安全属性）即失效。
- 证据（实跑探针 `.scratch/r34-final/_probe_grant_defaults.py`）：
  - `GRANT_GUARD_MODE default = off`；`GRANT_PUBKEY default empty = True`；`GRANT_ALLOW_UNSIGNED default = False`
  - `signed pkg + 出厂空公钥 -> REJECTED: 本机未配置验签公钥，无法校验授权包来源`
  - `unsigned pkg + 默认 allow_unsigned=False -> REJECTED: 授权包未签名…开启 allow_unsigned`
  - `signed pkg + 正确公钥 -> 通过验签并进入下一阶段（DB 查询）` ⇒ 算法链本身正常，缺的是部署配置。
- 根因：R33 只落地了代码与配置项，未随发布补部署文档/样例 env；且没有运维可观测的启动告警（PUBKEY 为空时无提示）。
- 建议（发布决策，非代码 bug）：① `.env.example` + `docs/04-部署文档` 增补上级/下级两套 R33 配置样例（上级仅 `GRANT_SIGNING_KEY`，下级**仅** `GRANT_PUBKEY`；明确 `GRANT_ALLOW_UNSIGNED` 永远保持 false）；② Release Notes 写明「R33 导入需先配置验签公钥」；③ 可选：启动自检在 `GRANT_SIGNING_KEY` 与 `GRANT_PUBKEY` 同时为空时不告警，在仅配了签名私钥的机器上提示「本机是上级侧」。
- 归属：Lead/运维文档（我不改文档与共享文件，未修改代码）。

### P1-2【R33「view = 写接口 403」默认不生效：`GRANT_GUARD_MODE=off`】

- 现象：写接口守卫默认关闭（`config.py:190-192`，`core/grant_guard.py:44-49` 首行短路）。即：上级把模块下发为 `view`（UI 文案「只读=可见但写接口 403」，`OrgGrant.vue:16`），但**默认部署**下这些用户仍可调用写 API（菜单可见性会被矩阵裁剪，但按钮/路由可见范围内写请求不会被 403）。
- 影响：R33 宣称的「下级只读执行」在写接口层默认不成立；`view` 单位用户可通过直接 API 调用（绕过 UI）写入其模块数据。这不是可远程利用的漏洞（用户本身有合法账号），但**产品安全承诺与默认行为不一致**，属发布前必须显式决策的点。
- 证据：`GRANT_GUARD_MODE=off`（探针输出）；守卫逐行代码 `grant_guard.py:102-135`；映射就绪度已达标（见下），因此切 `shadow`/`enforce` 不会被「未映射接口」误拦。
- 保护伞：**viewer（访客）角色的严格只读是另一套中间件，默认始终启用**（`middleware/viewer_readonly.py`，见回归确认），所以本项只影响 R33 `view` 级别（非 viewer 角色）。
- 建议：发布前决策——要么在发布说明中明确「R33 写收窄为可选能力（建议先 shadow 观察再 enforce）」，要么在部署模板里把生产环境设为 `GRANT_GUARD_MODE=shadow`（不建议直接 enforce 除非已完成灰度）。属产品/发布决策，我未改默认值。
- 归属：Lead 发布决策（配置/文档），代码无需改动。

## 三、P2（建议修复，不影响本次发布）

1. **`PUT /org-grants/{id}` 变更授权矩阵无审计日志**：`api/v1/org_grants.py:185-216` 直接改库并 `clear_cache()`，无 `write_work_log`/`AuditLogger`；对比同一文件 `import` 路径有 `write_work_log`（`:113-121`）。授权变更属提权敏感操作，军事审计场景应留痕（谁、何时、哪个单位、版本变化）。建议补 work_log（需改 api 层）。
2. **授权包导入缺「组织可达性」校验**：`import` 端点仅 `require_admin`（`org_grants.py:87`），随后 `apply_package` 按包内 `org_code` 查本地组织并应用（`grant_package_service.py:176-184`），未用 `assert_org_reachable` 限定调用者子树。跨组织包（同一签名上级为兄弟单位签发的包）可被任一 admin 应用到本机存在的其它单位。实际影响有限：包内容必须由上级私钥签名、版本必须大于目标单位当前版本，等价于「执行上级已授权的目标状态」；但在共享库/多组织机器上缺少调用者维度校验。建议：`expected_org_code` 强制取自本机配置（见 3）或导入要求 superuser。
3. **`organization_code` 未配置时跳过包目标一致性校验**：`org_grants.py:70-77` 取 `SystemConfig('organization_code')`，失败/空返回 `""` → `expected_org_code=None`（`:107`）→ `apply_package` 不做单位一致性检查。建议：下级侧要求该配置存在，或在系统设置页默认填入本机单位编号。
4. **本地 admin 可用 `PUT` 自授权，绕过「导入后只读」语义**：`PUT` 对 `assert_org_reachable` 允许的自家子树任意改矩阵并递增版本（`org_grants.py:185-216`），后端无法区分「上级配置机」与「下级执行机」。客观边界：离线单机部署中本地 admin 物理上可直接改 SQLite，所以不是真实信任边界；但 API/UI 语义与文档「导入后只读」不一致，且可被用于**本地扩权留痕缺失**。建议：加 `GRANT_LOCAL_ADMIN_EDIT` 开关或在下级模式（配了 `GRANT_PUBKEY` 且未配签名私钥）禁用 PUT。
5. **viewer 只读中间件不覆盖「GET 里的写副作用」**：`middleware/viewer_readonly.py:40-61` 只拦 POST/PUT/PATCH/DELETE。全量 AST 扫描发现 3 个有真实 DB 写入的 GET 端点：`api/v1/fund_lifecycle.py:1317-1318`（monitoring/deviation，生成偏差分析报告落库）、`api/v1/policy.py:1054`（下载计数）、`api/v1/policy.py:1296`（浏览数）。影响：viewer 可通过 GET 触发计数/报告写入（数据完整性/审计噪声，不涉越权）。建议：把副作用改为 POST，或接受并在 README 记录为例外。
6. **角色变更不吊销既有令牌（viewer 中间件依赖令牌 role 声明）**：`build_auth_claims` 把 role 写入令牌（`core/security.py:257-278`），viewer 中间件按**令牌声明**判定、旧令牌无 role 时 fail-open（`viewer_readonly.py:106-109`，注释已说明 8h 自然过期兜底）。全仓 `users.py` 仅在改密/管理员重置时 `revoke_all_tokens()`（`:993,1034`），**改角色未 bump token_version**：admin→viewer 降级后，旧令牌 8 小时内不被只读中间件识别（仍以旧角色写）。属既有的 JWT 快照问题，但 viewer 决策放大了窗口。建议：用户角色变更处调用 `user.revoke_all_tokens()`。
7. **`org_grants` 无外键/级联清理**：模型 `models/org_grant.py:40-58` 与迁移 `alembic/versions/r33_org_grants_001.py` 的 `organization_id` 无 FK；单位硬删除后残留 grant 行（无安全影响，数据卫生）。另：`parse_package` 对恶意深层嵌套 JSON 的 `RecursionError` 未捕获（`grant_package_service.py:127-134`）→ 500 而非 400；仅本机 admin 可触发，P3 级。

## 四、通过项（本回复检确认，含证据）

### 4.1 R33 密码学与授权包

- **签名算法**：Ed25519，签名对象为规范化 JSON（`sort_keys` + 紧凑分隔符 + UTF-8，`core/grant_signing.py:39-42`）；私钥/公钥均 32 字节 hex（`:60-80`）；验签异常一律返回 False（`:83-93`），无算法混淆面。
- **密钥来源**：仅来自环境配置 `settings.GRANT_SIGNING_KEY` / `GRANT_PUBKEY`（`config.py:194-200`），仓库内**无硬编码密钥**；`git grep 'BEGIN PRIVATE KEY|GRANT_SIGNING_KEY=.{8}'` 仅命中测试文件里的空串 fixture。上级签名、下级只配公钥的分权设计正确（公钥可提取但无法伪造签名，威胁模型已在模块 docstring 声明）。
- **重放/降级防护**：`apply_package` 要求 `package.version > org.grant_version`（严格大于，`grant_package_service.py:186-190`），拒绝旧包回滚扩权；导入成功后递增 `grant_version` 并 `clear_cache()`（`:196-205`）。重复导入同一版本被拒。
- **默认仅收签名包**：无签名且未显式 `allow_unsigned` → 拒绝（`:168-174`）；有签名但本机无公钥 → 拒绝（`:169-170`）。
- **导入路径/文件校验**：`POST /org-grants/import` 走 `read_upload_with_limit` 限长 1MB（`org_grants.py:44-45,92-97`，符合 check_upload_endpoints R2 门禁）；只解析 JSON 文本，无解压/落盘/路径拼接，无路径穿越面；结构校验在验签之前完成但不影响安全（多字段均为签名覆盖）。
- **读取的执行语义**：`GET /org-grants/{id}` 只返回矩阵与元信息（`org_grants.py:163-182`），签名仅作展示字段（`signed`），**不构成信任**——真正的信任判定只在导入时。`effective_grant_service` 是唯一裁决点：按组织链「深者优先」合并、`inherit_from_parent=False` 切断、环检测、同层 deny 不可被浅层翻回（`services/effective_grant_service.py:76-160`）；未下发授权（`active=False`）回落 legacy 行为。
- **跨组织越权（管理面）**：`GET/PUT/export` 均经 `_require_admin_and_reach`（`org_grants.py:54-62`：`require_admin` + `assert_org_reachable`），非超管仅本组织子树；无组织用户 `allowed_org_ids=[]` → 403。
- **R33 前端只读语义**：`OrgGrant.vue` 仅为**上级**配置页（`admin/super_admin`，`frontend/src/router/index.ts:615-625`），前端不参与裁决——危险操作全部在后端；下级侧无编辑入口。菜单可见性由后端矩阵裁剪（`api/v1/menus.py:1360-1376`：矩阵 active 时以 `visible_keys()` 为准，用户级 `allowed_menus` **只能收窄不能扩大**，工作台恒可见），前端菜单只是展示。
- **写接口映射就绪度（enforce 前提）**：`scripts/report_unmapped_write_routes.py` 实跑 → `规则条数: 83 / 写接口总数: 396 / 已归属: 396 / 未归属: 0`（exit 0）。即切 `shadow`/`enforce` 不会因未映射接口误拦。

### 4.2 回归确认（全部通过）

- **viewer 严格只读**：`middleware/viewer_readonly.py` 默认启用（`main.py:162-171` 注册，位于 Audit/RequestLogger 之内、Metrics/业务路由之外）；只拦写方法、自服务白名单（登录/刷新/改密/notification preferences/feedback），role 取自令牌声明、旧令牌 fail-open 由端点鉴权兜底；被拒写 `viewer_write_denied` 审计。**测试：`tests/security/test_viewer_readonly_enforcement.py` 14 项 + `tests/unit/middleware/test_viewer_readonly.py` 33 项（15 个测试函数，含参数化），全过**。
- **非回环注册门禁**：`_enforce_register_source_gate` 在位（`api/v1/auth/auth.py:86-127,926-927`）；`register_denied_untrusted` 审计、回环/TestClient 放行、非回环+无 `PASS_CODE_SECRET`→403。测试 `test_register_source_gate_w24.py` 11 例全过。
- **PII 加密与日志脱敏**：`core/pii_crypto.py` AES-SIV 确定性加密 + `enc.v1:` 标记 + 密钥 `require_persisted` fail-closed；`SensitiveDataFilter` + `JsonFormatter` 复用脱敏 `exc_text`（我先前的 P1 修复仍在位，`core/logging_config.py:151-158`）。测试 `test_pii_encryption.py` 7 例、`test_pii_decrypt_observability_w18.py` 5 例、`test_logging_config_cov.py` 13 例、`test_logging_redaction_cov.py` 1 例全过。
- **上传/ZIP 限长**：`utils/upload_helper.py` 分块流式 + 滚动限长 + ZIP 解压总量闸门 + 成员限长（`ZIP_MAX_UNCOMPRESSED_BYTES`、`ensure_zip_within_limit`、`read_zip_member`）均在位；`test_upload_limit_r2.py` 23 例、`test_upload_helper_a24.py` 16 例全过。
- **CSRF / 安全响应头**：`CSRFMiddleware` 默认开启（`config.py:182`，HMAC 签名 + 时间戳过期 + 豁免前缀）、`SecurityHeadersMiddleware` 下发 CSP/X-Frame-Options/nosniff/HSTS/Referrer-Policy/Permissions-Policy；`tests/unit/middleware/`（含 CSRF ASGI 15 例）与 `test_core_security.py` 9 例全过。

### 4.3 依赖与密钥

- **前端生产依赖**：`npm audit --omit=dev --json` → `{"info":0,"low":0,"moderate":0,"high":0,"critical":0,"total":0}`（prod 79 个依赖）。
- **后端依赖**：`pip-audit` 仍未安装（`No module named pip_audit`，本轮无法复跑）。人工核对关键版本：fastapi 0.136.3 / starlette 1.3.1 / PyJWT 2.15.0 / cryptography 50.0.2 / requests 2.33.0 / urllib3 2.8.0 / python-multipart 0.0.31 / pillow 12.3.0 / lxml 6.1.1 / SQLAlchemy 2.0.50 / anyio 4.14.2——与 2026-10-03 pip-audit 记录的修复口径一致（anyio/PyJWT/urllib3 均已在 requirements 注释中记录 Fix Versions）；`backend/requirements.txt` 自 9de7aea 以来**无变更**（`git diff 9de7aea..HEAD -- backend/requirements.txt` 为空）。已知项 `diskcache==5.6.3`（上游无修复，pickle RCE 面）已用 `diskcache.JSONDisk` 闭环（`api/v1/map.py:72-73`、`api/v1/data/data/dashboard.py:56-57` 复核在位）。R33 新引入的 Ed25519 使用既有 `cryptography`，无新增依赖。
- **仓库密钥扫描**：`git grep 'BEGIN .*PRIVATE KEY|GRANT_SIGNING_KEY=.{8}|GRANT_PUBKEY=.{8}'` → 仅测试文件中的空串 fixture；`git ls-files` 无 `runtime_secrets.json` / `*.key` / `secrets.json` / 真实 `.env`；`.env.example` 中 `SECRET_KEY=` / `CSRF_SECRET_KEY=` / `PASS_CODE_SECRET=` 均为空占位（安全默认）。**但 R33 的 GRANT_* 三项在 `.env.example` 完全缺失** → 已列 P1-1。

## 五、验证命令与结果（本轮实跑，均为定向测试，全量由 Lead 统一跑）

```text
# 1) R33 + viewer + 注册门禁 + 日志脱敏 + security 目录
pytest tests/security/ tests/unit/middleware/test_viewer_readonly.py \
  tests/unit/test_grant_package_r33.py tests/unit/test_org_grants_api_r33.py \
  tests/unit/test_effective_grant_service_r33.py tests/unit/test_org_grant_model_r33.py \
  tests/unit/test_grant_guard_r33.py tests/unit/test_register_source_gate_w24.py \
  tests/unit/test_log_redaction_json_formatter.py -q
→ 193 passed (24.2s, exit=0)

# 2) 中间件/CSRF/安全头/日志脱敏/上传限长/PII 加密回归
pytest tests/unit/middleware/ tests/unit/test_core_security.py \
  tests/unit/test_logging_config_cov.py tests/unit/test_logging_redaction_cov.py \
  tests/unit/test_upload_limit_r2.py tests/unit/test_upload_helper_a24.py \
  tests/unit/test_pii_encryption.py tests/unit/test_pii_decrypt_observability_w18.py -q
→ 161 passed (27.0s, exit=0)

# 3) R33 写接口映射清零（enforce 前提）
python ../scripts/report_unmapped_write_routes.py
→ 规则 83 / 写接口 396 / 已归属 396 / 未归属 0（exit 0）

# 4) R33 出厂配置行为探针（自建脚本，只读）
python .scratch/r34-final/_probe_grant_defaults.py
→ GRANT_GUARD_MODE=off；GRANT_PUBKEY/GRANT_SIGNING_KEY 空；签名包+空公钥 REJECTED；未签名包默认 REJECTED

# 5) GET 副作用全量扫描（自建 AST 脚本，只读）
python .scratch/r34-final/_scan_get_mutation2.py
→ 3 处（fund_lifecycle/monitoring/deviation + policy 下载计数 + policy 浏览数）

# 6) 依赖
cd frontend && npm audit --omit=dev --json → 0 漏洞（prod 79）
backend/.venv/Scripts/python.exe -m pip_audit --version → No module named pip_audit
git diff 9de7aea..HEAD -- backend/requirements.txt → 空
```

## 六、既有安全基线回归结论（与 R33 无关但本轮复核）

- 非回环注册门禁、viewer 只读、PII 加密、日志脱敏、上传/ZIP 限长、CSRF、安全响应头：**全部在位且定向测试通过**（见四.2）。
- 上传/限长门禁脚本（check_upload_endpoints / check_unbounded_read）由 Lead 统一全量验证，本轮未重复跑全量。

## 七、遗留风险与发布建议

1. **发布前**：P1-1（R33 配置文档 + 出厂不可用）与 P1-2（GRANT_GUARD_MODE 默认 off 的语义声明）需要 Lead 决策并在 Release Notes/部署文档中体现；两项都不需要改代码即可发布，但**不处理会让 R33 功能「出厂不可用」或「安全承诺与默认行为不一致」**。
2. **建议随后补**（P2，非阻塞）：PUT 授权审计、import 的 org 可达性/本机单位强校验、角色变更吊销令牌、GET 副作用收口、org_grants 外键清理、深层 JSON 400 化。
3. **依赖门禁**：`pip-audit` 未安装，本轮沿用人工核对 + requirements 内注明的 Fix Versions；建议 CI 恢复 pip-audit 步骤（否则后续升级无自动 CVE 门禁）。
4. 本报告为只读审计：**未修改任何代码/配置/文档，未执行 git 操作，未触碰版本号/CHANGELOG/CI**。所有临时脚本仅写在 `.scratch/r34-final/`。
