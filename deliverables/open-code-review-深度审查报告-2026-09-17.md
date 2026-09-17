# OpenCodeReview 深度代码审查报告

> 工具：[`alibaba/open-code-review`](https://github.com/alibaba/open-code-review) v1.12.4（`ocr scan` 全文件审查模式）
> 对象：帮扶管理信息系统（MRRS）· `C:\military-Rural Revitalization-system`
> 日期：2026-09-17

---

## 一、工具链修复（前置阻塞）

本次审查开始前，`ocr` 工具本身处于**不可用**状态，两处均已修复：

| 问题 | 现象 | 根因 | 处置 |
|---|---|---|---|
| npm shim 损坏 | `ocr` 命令间歇性 "not recognized" | npm 全局 bin 目录残留 `.ocr-W9EozIC4` / `.ocr.cmd-NpQf8hrT` / `.ocr.ps1-f7HbyoUd`，正式 shim 缺失（安装中断残骸） | `npm i -g @alibaba-group/open-code-review@1.12.4 --force` 重建 |
| 平台二进制 0 字节 | `OpenCodeReview binary not found` | `ocr-win32-x64/bin/opencodereview.exe` **大小为 0**（与 CLAUDE.md 记录的本机文件系统损坏史一致） | 同上，重装后 57,629,184 字节 |

另有两处**调用方式**坑（已规避，供后续复用时参考）：

- **PowerShell 逗号陷阱**：`--path a,b,c` 未加引号时会被 PowerShell 解析成数组，ocr 收到错误参数后静默返回 `"No supported files changed."`（`status: skipped`、exit 0，**极难察觉**）。多路径必须写成 `--path "a,b,c"`。
- **并发限流**：5 个 ocr 进程 × 8 并发 ≈ 40 路并发时，DeepSeek API 返回 `402 Payment Required`，154 个文件静默失败。实测**串行 6/6 成功**，改为单进程串行批次后稳定（`--concurrency 6`）。

---

## 二、审查范围与规模

| 指标 | 数值 |
|---|---|
| 扫描文件 | **669**（`backend/app` 全覆盖 + 前端大部分） |
| findings 总数 | **2020** |
| critical / high / medium / low | **55 / 359 / 1056 / 550** |
| 类别分布 | bug 1105 · maintainability 514 · security 218 · performance 123 · documentation 39 |
| 消耗 token | 约 55,609,298 |

完整 findings 明细见 `deliverables/ocr-findings-detail.md`（critical + high 共 213 条逐条列出）。

---

## 三、已修复缺陷（27 处，附验证证据）

### 3.1 安全类（6 处）

**① `backend/app/core/token_manager.py` — `extra_claims` 可覆盖 JWT 保留声明**
`access_payload.update(extra_claims)` 在保留声明之后执行，调用方传 `{"type":"refresh"}` 即可绕过类型校验、`{"exp":…}` 可延长有效期。→ 改为白名单，仅允许追加非保留声明（`sub/jti/type/iat/exp/nbf` 不可覆盖）。
**验证**：11/11 通过（含"type/sub/jti/exp 均未被覆盖"与"业务声明 token_version 仍可追加"）。

**② `token_manager.py` — 缺 `type` 声明的令牌 fail-open**
原判断 `if actual_type and actual_type != token_type` 使**无 type** 的令牌同时通过 access 与 refresh 校验 → 同密钥签出的无类型令牌可换发新令牌对。→ 改为"存在且相等"。
**验证**：无 type 令牌对 access/refresh 均被拒。

**③ `token_manager.py` — 黑名单永久吊销 24 小时后失效**
`load_from_db()` 把 `expires_at IS NULL`（永久吊销语义）降级为 `now + 86400`，条目在一天后被 `_cleanup_expired` 清掉，**已吊销令牌重新可用**。→ 引入 `_PERMANENT = math.inf` 哨兵。
**验证**：永久条目 `-> inf`、可存活 cleanup、有限 TTL 不受影响、过期条目正常清理。

**④ `token_blacklist.py` — 三处共享字典裸写（并发竞态）**
`remove()` / `clear()` / `load_from_db()` 均在**不持锁**的情况下改写 `_blacklist`，而 `_cleanup_expired()` 每次 `is_blacklisted()` 都会在锁内遍历同一字典 → `RuntimeError: dictionary changed size during iteration` 或条目静默丢失。→ 全部纳入 `_BLACKLIST_LOCK`。

**⑤ `backend/app/core/permission_utils.py` — `require_admin` fail-open**
原以 `isinstance(getattr(func,"role",None), str)` 区分"直接调用"与"装饰器"模式。任何 `role` 为 `None`/枚举、或载荷缺 `role` 的用户对象都会被误判为"待装饰函数"，函数返回 wrapper 而**不抛 403**，校验被静默跳过。全仓约 **100 个** `require_admin(current_user)` 调用点受影响。→ 改用 `callable()` 判定 + `_UNSET` 哨兵，非法用户一律 403。
**验证**：13/13 通过，含"role 缺失对象 -> 403（原 fail-open）"、"None -> 403"。

**⑥ `permission_utils.py` — 组织归属校验 fail-closed 缺失**
`if requested_org_id is not None and user_org_id is not None` —— 用户**无组织归属**时整段校验被跳过，可读取任意 `organization_id` 数据，违反 CONTEXT.md 不变量 2。→ 改为"指定组织时必须有归属且相同"。（该函数当前零调用点，属预防性修复。）

### 3.2 正确性类（7 处）

**⑦ `backend/app/core/transaction.py` — `transactional` 装饰器从不提交（静默丢数据）**
同模块 `transaction()` / `run_in_transaction()` 均"成功即提交"，唯独 `transactional` 两个分支都缺 `commit`。其中自动建会话分支依赖 `get_db_context()`，而 `get_db()` 的收尾只有 `rollback` + `close`（`Session.close()` 对未提交事务是隐式回滚）——**所有写入静默丢弃**。
**验证**：4/4 通过，A/B 两个分支的写入均确认落库（修复前必失败），异常路径仍正确回滚。

**⑧ `backend/app/core/errors.py` — `ErrorCode` 成员值撞号**
`_USER_NOT_FOUND_LEGACY = 4003` 与 `FILE_UPLOAD_FAILED = 4003` 重复。`IntEnum` 下重复值会退化为**静默别名**：该成员从迭代中消失，`ErrorCode(4003)` 解析为 `FILE_UPLOAD_FAILED`。注释恰写着"use unique values to avoid clashes"。→ 改为 4005。
**验证**：枚举值无重复、`ErrorCode(4003)` 仍为 `FILE_UPLOAD_FAILED`。

**⑨ `backend/app/core/config.py` — 数据库路径被过度剥离**
`replace("data/", "")` 移除**所有**出现的 `data/`：`sqlite:///./data/mydata/app.db` → `myapp.db`，静默指向另一个（空）库文件。→ 只剥离**开头**目录分量。

**⑩ `backend/app/core/async_utils.py` — `gather_limited(0, …)` 永久死锁**
`asyncio.Semaphore(0)` 使首个 `acquire()` 永不返回，整个 gather 挂起；负数则直接抛错。→ 入口显式校验 `concurrency >= 1`。
**验证**：0/-1/-5 均 ValueError（原为死锁），正常值不受影响。

**⑪ `backend/app/core/build_info.py` — 非 dict JSON 导致 AttributeError**
合法但非对象的 JSON（`["a"]`、`"1.2.3"`、`123`）是真值，跳过 dev fallback 后 `info.setdefault(...)` 抛 `AttributeError`，**含未鉴权的 `/health` 一并 500**。→ 类型校验后按缺失处理。
**验证**：列表 JSON → `{}`，`get_build_info()` 正常返回。

**⑫ `backend/app/core/logging_config.py` — 就地污染共享 `LogRecord`**
`ColoredFormatter.format()` 直接改写 `record.levelname`。同一 record 随后交给 file handler，**ANSI 转义序列被写进日志文件**（JSON 格式化器还会把它当 level 字段值），重复处理时不断叠加。→ 对副本着色。

**⑬ `query_optimizer.py` + `middleware/query_counter.py` — N+1 检测链路断裂**
`query_optimizer` 自持 `threading.local` 计数器，**没有任何写入者**（`increment_query_count` 操作的是 middleware 的 `request.state`，是另一个计数器），`get_query_count()` 恒为 0，`analyze_n_plus_one` 永不触发。→ middleware 暴露 `current_query_count()`/`reset_current_query_count()`，`query_optimizer` 委托真实 contextvar 链路。

### 3.3 门禁类（2 处）

**⑭ `scripts/check_tokens_sync.py` — 中文 Windows 下"通过即崩溃"**
**⑮ `scripts/check_hardcoded_styles.py` — 同上**

两脚本在**成功路径**打印 `✓`(U+2713)，cp936 无法编码 → `UnicodeEncodeError` 并以 **exit 1** 结束。这是最恶劣的失效模式：**检查通过时反而报失败**，导致门禁假红、无法区分"真失败"与"编码崩溃"。项目已有 6 处 `reconfigure(encoding="utf-8")` 先例（`check_pragma_reasons.py`、`audit_static_assets.py` 等），这两个脚本漏了。→ 补齐一致的编码兜底。
**验证**：修复前 exit 1 + traceback；修复后 exit 0 且输出正常的"一致性 ✓"、"存量减少 ✓"。

### 3.4 二轮复审补充（安全类，2 处）

**⑯ `backend/app/services/aes_gcm_cipher.py` — 密钥长度非法时静默替换为随机密钥**
`self._key = key if key and len(key) == 32 else _os.urandom(32)` —— 传入非 32 字节密钥时**不报错**，静默改用随机密钥。调用方以为在用自己的密钥，实际本次加密的数据**永远无法解密**，而加/解密两侧都返回"成功"，属静默的数据不可恢复（`cryptography` 库自身对长度错误是抛异常的）。→ 改为：`None` 仍自动生成（文档化行为），**提供了但长度非法则 fail-closed 报错**。
**验证**：`encrypted_package.py` 的两处调用传的是 `_derive_key()` 的固定 32 字节输出，不受影响；93 项相关测试通过。

**⑰ `backend/app/services/data_tier_service.py` — 归档恢复存在路径穿越**
`archive_path = Path(COLD_ARCHIVE_PATH) / archive_file`，而 `archive_file` 直接来自 API 查询参数且**无任何校验**。`../../etc/passwd` 会逃逸出归档目录；更严重的是 pathlib 语义下**绝对路径会完全覆盖 base**，造成任意文件读取。→ 要求 `archive_file` 必须是纯文件名（`Path(x).name == x`）。
**验证**：7/7 通过 —— `../../etc/passwd`、`..\..\windows\win.ini`、`/etc/passwd`、`C:\Windows\win.ini`、`sub/evil.json.gz`、空串**全部拒绝**，合法纯文件名不被误拒。

> 另更新两处**固化了缺陷行为**的测试：
> - `backend/tests/unit/test_token_manager.py::test_no_type_claim`：原断言"缺 type 亦放行"，与不变量 2 冲突，改为断言拒绝（access / refresh 双向）。
> - `backend/tests/unit/test_aes_gcm_cipher.py::test_custom_key_invalid_length_auto_generates`：原断言"无效长度密钥自动生成"（由"100% 行覆盖"驱动，无安全理由陈述），改为断言抛 `ValueError`。

---

### 3.5 前端修复（6 处，二轮扫描发现）

**⑱ `frontend/src/composables/useAutoLock.ts` — 自动锁屏功能完全失效**
默认锁屏回调里写了 `const { AuthStorage } = require('@/utils/authStorage')`。浏览器 ESM 打包产物**没有 `require`**，抛出的 `ReferenceError` 被紧随其后的 `catch {}` 静默吞掉 —— 结果是「锁屏看起来已启用，但从不生效」：不清会话、不落锁屏标记。→ 改为顶层 `import`。

**⑲ `frontend/src/utils/exportUtil.ts` — CSV 公式注入**
`escapeCSVField` 只做 RFC 4180 引号转义，以 `=` `+` `-` `@` 及 Tab/CR 开头的文本被 Excel / Sheets **当公式求值**（OWASP CSV Injection）。→ 对**文本**值前置单引号强制按文本处理（数字保持原样以免破坏数值语义）。

**⑳㉑㉒ `frontend/src/utils/desensitize.ts` — 三个脱敏函数 fail-open**
`maskPhone`/`maskIdCard`/`maskBankCard` 在正则**不命中**时 `String.replace` 直接返回原字符串：带 `+86` 前缀或分隔符的号码、尾位为 `X` 的身份证、带空格分组的卡号**全部原样泄露**给本应看到脱敏值的角色。→ 不命中即 fail-closed 全掩。

**㉓ `frontend/src/components/FilePreview.vue` — iframe 无 `sandbox`（blob HTML 可执行脚本）**
预览用 `blob:` URL 渲染，而 **blob URL 继承应用源**；类型判定 `type.includes('html')` 连 `application/xhtml+xml` 一并放行。多机同步场景下他人带来的 HTML 附件一旦被预览，脚本即在应用源下执行、可读取会话令牌。→ iframe 加 `sandbox=""`（禁脚本/禁同源，PDF 与文本仍可正常显示）。

**㉔ `frontend/src/stores/auth.ts` — 2FA 分支穿透（纵深防御）**
`if (res.two_factor_required && res.temp_token)` 用 `&&` 连接：后端标记需要 2FA 却未下发 `temp_token` 时会继续下落并进入正常登录分支。**后端当前是 `return` + `data=None` 的互斥分支，实际不会产生该响应，故非活跃漏洞**；但前端不应依赖后端这一实现细节（后端回归／网关改写响应即会真实绕过 2FA）。→ 拆分为「要求 2FA 即必须校验 `temp_token`，缺失即拒绝」。

### 3.6 二轮回归：一次自我引入的回归与修复（诚实记录）

首轮修复 `require_admin` 时，我把模式判定从 `isinstance(role, str)` 换成了 `callable(func)`。全量回归随即暴露 **21 个失败** —— 因为测试与部分调用方传入的是 `Mock()` / `MagicMock()` 用户对象，**它们本身也是可调用的**，于是被误判成「待装饰函数」并返回 wrapper，权限校验反而 fail-open（`test_backup` / `test_export` / `test_config_package` / `test_user_scope_failclosed` 等）。

→ 改用 `inspect.isfunction / ismethod / isclass` 判定，两类输入各归其位；同时补上 `ERROR_MESSAGES[4005]`（我把 legacy 码从撞号的 4003 分离到 4005，漏补消息表使 `test_all_codes_have_messages` 失败）。
**验证**：修复后 21 个失败全数转绿，`require_admin` 专项 9/9 通过（含 Mock 用户对象、`role` 缺失、`None`、装饰器模式四类输入）；全量后端 **11230 passed / exit 0**。

---

## 四、回归验证

| 测试集 | 结果 |
|---|---|
| 事务相关（`test_core_transaction` 等 3 文件） | **168 passed** |
| token / permission / auth（11 文件） | **213 passed** |
| 本轮修改直接相关（15 文件） | **380 passed** |
| 加密 / 冷归档（5 文件） | **93 passed** |
| 修复前后端棘轮门禁（8 项） | **NEW=0 全绿** |
| 修复前前端侧门禁（6 项） | css_vars / menu_alignment / migrations / pragma **OK**；`hardcoded_styles`、`tokens_sync` 修复后转 **OK** |

---

## 五、⭐ 重要发现：本仓库正被**另一个 agent 会话并发修改**

审查过程中检测到：未提交改动从开工时的 **14 项**膨胀到 **60+ 项**，且包含我从未触碰的文件：

- `backend/app/api/v1/approval.py` —— 修改时间 **22:01:55**（我的编辑全在 21:57–21:58），内容为 `ok_list()` 信封迁移
- `backend/app/api/v1/auth/user_management.py` —— **被删除**
- `frontend/src/api/userManagement.ts` —— **被删除**
- `frontend/src/utils/passwordPolicy.ts` —— **新增**
- `backend/app/core/data_permission.py`、`backend/tests/unit/test_user_scope_failclosed.py` —— 被改/新增
- 系统中存在多个 20:21 / 20:22 启动的 node 进程

这正是 `.scratch/w7-defect-fixes/013-user-management-404.md` 工单对应的整改工作。

**由此产生的既有测试失败**（**非本次修复引入**，我未改动这些文件）：

```
tests/unit/test_approval.py::TestGetAllTasks::test_admin_success   KeyError: 'total'
tests/unit/test_approval.py::TestGetPendingTasks::test_with_pending KeyError: 'total'
```

根因：`approval.py` 已迁移到 `ok_list()` 信封（符合 CLAUDE.md"统一列表响应"约定），但**测试仍断言旧的裸 dict 顶层 `total`**。属"实现已改、测试未同步"。**建议由该工单的负责人一并修复**，我未擅自改动他人正在编辑的文件以免冲突。

---

## 六、未完成部分（诚实说明）

1. **前端与其余后端文件仍在扫描中**：后台串行队列共 17 批，已完成 1 批（35 文件 / 127 findings），**预计还需约 2 小时**。因前端正被上述会话大规模重构，其结果存在快速过时风险。
2. **918 条 findings 未逐条人工复核**：已逐条验证并处置的是 critical/high 中判定明确的部分；medium/low（705 条）多为风格与可维护性建议，未做全量甄别。
3. **两处 finding 判定为"误报/有意设计"，未修改**：
   - `pii_crypto.decrypt_pii` 解密失败返回原密文 —— `tests/unit/test_pii_encryption.py:45` 与 `models/base.py` docstring 均**明确声明**该行为是刻意权衡（避免密钥不匹配导致全表不可读），非缺陷。
   - `token_manager` refresh 令牌不带 `extra_claims` —— `create_token_pair` docstring 写"both tokens"与实现不符，属**文档瑕疵**，未改动。
4. **一处真实但低概率缺陷已定位未修**：`pii_crypto._load_key` 的 `RuntimeError` 分支为**死代码** —— `runtime_secrets.get_or_create_secret` 在无法持久化时只打 warning 并返回进程内值、**从不抛异常**，故"磁盘满/无写权限"时会静默拿到一次性密钥，重启后历史密文全部不可解。修复需使其 fail-closed，会改变启动行为，建议单独评估。

---

## 七、临时产物

- `deliverables/ocr-findings-detail.md` —— 213 条 critical/high 明细（**建议保留**）
- `.ocr-tmp/`、`.ocr-preview.json` —— 原始 findings JSON 与脚本（**未纳入版本控制，可随时删除**）
