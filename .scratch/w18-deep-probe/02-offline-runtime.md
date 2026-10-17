# 离线/单机运行时 深度探测报告

> 探测时间：2026-10-17　基线：`d7246dc`（v1.12.18，R27/R28 之后）
> 维度：**装到用户机器上会怎么坏** —— Electron 壳 / 后端进程 / 现场环境。
> 纪律：只读探测，未改任何产品代码；全部引用均可在当前 HEAD 复现（逐条按 `git show HEAD:<file>` 核对行号与代码片段）。
> 实证脚本：`.scratch/w18-deep-probe/_probe_*.py`（一次性，含真实 SQLite / 真实文件系统实验）。

> **取证口径说明（重要）**：探测期间工作区有其它并行会话在改代码（git status 显示
> electron/main.js、backend/app/core/pii_crypto.py、backend/app/services/backup_service.py、
> backend/app/startup/preflight.py 等均为 dirty / untracked）。为保证**行号可复现**，
> 本报告全部行号均以 `git show HEAD:<file>`（基线 `d7246dc`）为准逐一核对过，
> 而非取工作区当时内容。凡工作区已被并行会话改动的地方，结论描述的是 **HEAD 现状**，
> 并已在 §6 列出与并行修复的重叠。

---

## 0. 结论速览

| 级别 | 条数 | 说明 |
|---|---|---|
| **P0** | 2 | 装机即坏 / 数据不可逆 |
| **P1** | 5 | 功能静默失效 / 现场不可排障 |
| **P2** | 4 | 正确性与可维护性 |
| **P3** | 5 | 打磨 |
| 合计 | 16 | |

**最该先做的 3 条**

1. **P0-1 打包态「日志写一处、Electron 看另一处」** —— 现场排障时诊断包与修复引导页都指向不存在的日志，而"日志在 userData 下"是文档四处写的假事实。
2. **P0-2 麒麟 standalone 的 HOME 指向安装目录使数据全落 /opt；且 BACKUP_DIR 从未被接收** —— 装到现场就是备份全废 + 密钥不持久 + PII 读取 500。
3. **P1-1 换机/重装后 PII 密文永久不可解，且前端静默显示密文** —— "数据看起来还在、其实字段全废"，用户当场不会发现。

---

## 1. P0 条目

### P0-1 打包态日志路径双源：写在实际目录，Electron/文档都指向另一个

**位置**

- `electron/main.js:324`（注入）：`LOG_FILE: path.join(logsDir, 'app.log')`，其中 `logsDir = path.join(getUserDataPath(), 'logs')`（`:311`）
- `backend/app/core/config.py:404-410`（覆盖）：
  ```python
  if self.CACHE_DIR.startswith("./"):
      self.CACHE_DIR = f"{data_dir}/cache"
  if self.LOG_DIR.startswith("./"):
      # 日志也放在用户数据目录下
      if getattr(sys, "frozen", False):
          self.LOG_DIR = f"{data_dir}/logs"
          self.LOG_FILE = f"{data_dir}/logs/app.log"      # ← 无条件覆盖 Electron 注入值
  ```
- `backend/app/utils/paths.py:116-121`（`data_dir` 的来源）：
  ```python
  base_dir = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
  if base_dir:
      data_dir = Path(base_dir) / "bumofu-assistance"
  else:
      data_dir = Path.home() / ".bumofu"
  ```

**现象（已实证，`_probe_frozen_env.py` / `_probe_logfile.py`）**

按 `startBackend()` 逐键注入 Electron 实际传的全部环境变量、`sys.frozen=True`、`ENVIRONMENT=production`：

```
Settings.LOG_FILE  = ...\LOCALAPPDATA\bumofu-assistance\data\logs\app.log
Electron 期望的位置 = ...\APPDATA\帮扶管理系统\logs\app.log
两者一致            = False          ← 注入被静默覆盖
```

同一实验还测出：`get_backup_path()` 也落在 `%LOCALAPPDATA%\bumofu-assistance\backups`，而不是 userData 下（见 P1-3）。

**根因**：打包态 `data_dir` 取的是 `%LOCALAPPDATA%`（`paths.py` 的兜底口径），而 Electron 的 userData 是 `%APPDATA%\帮扶管理系统`。**两套目录本就不同**，`config.py` 又用前者无条件覆盖了后者注入的值 —— 注入形同虚设。

**真实后果（谁会踩、什么时候、可不可逆）**

1. **现场排障完全失准**（必踩）：`electron/main.js:1117` 把 `app.logPath` 作为 userData 下的路径交给修复引导页；`main.js:1144` 的「打开应用日志」也开 userData 下的文件。实际日志在 `%LOCALAPPDATA%`。用户点"打开日志"得到空文件/不存在 → 这是**第一次装机失败时唯一的自助通道**。
2. **文档四处写错**：`docs/04-部署文档/OFFLINE_UPGRADE.md:14,19-24,68,91` 反复写「日志见 `%APPDATA%\帮扶管理系统\logs\app.log`」。现场按文档取日志 → 空。
3. **卸载清理口径割裂**：`build-scripts/electron-builder-nsis-hook.nsh:182-194` 只删注册表记录的 userData 与遗留 `%LOCALAPPDATA%\bumofu-assistance`；日志被归到后者，**只有用户勾选删数据时才被清**。
4. **磁盘增长点被隐藏**：应用日志是唯一的无界增长文件之一（见 P2-4），却不在诊断包/用户能找到的路径里。
5. 可逆性：路径可配置，**改代码可逆；但"现场拿不到日志"这件事在故障当时不可逆**。

**修法（含改动面）**

- `backend/app/core/config.py:404-410`：`if self.LOG_DIR.startswith("./")` 改为 `if not os.path.isabs(self.LOG_DIR)`，且**只在 LOG_FILE/LOG_DIR 仍为相对路径时才派生**；已由环境变量给绝对路径时不覆盖（LOG_FILE 单独判空）。
- 同时修 `get_app_data_dir()` 的先天分叉：新增 `APP_DATA_ROOT` 环境变量作为唯一入口，Electron 在 `startBackend()` 注入 `APP_DATA_ROOT=getUserDataPath()`；`paths.get_app_data_dir()` 优先读它，Windows 才兜底用 `LOCALAPPDATA`。
- 门禁：`scripts/check_userdata_path_consistency.py` 已存在（W18 P1-5 新增），**把它从"只校验 NSIS 钩子"扩到校验 config.py 不得覆盖 LOG_FILE** —— 一行 grep 级断言即可。
- 改动面：2 文件（config.py / main.js）+ 1 门禁脚本；约 40 行。

**验证方式**

- 单测：`monkeypatch.setenv('LOG_FILE', '<userData>/logs/app.log')` + `monkeypatch.setattr(sys, 'frozen', True)` → 断言 `Settings().LOG_FILE == os.environ['LOG_FILE']`（当前必失败）。
- 端到端：本地 `electron-builder --dir` 产出后启动，确认日志真实出现在 `%APPDATA%\帮扶管理系统\logs`，且 `/api/v1/system/diagnostics/bundle` 的 `app.log.tail` 非空。
- 现场自检：诊断包 `logs.file` 字段 + 启动时打印 resolved LOG_FILE vs Electron injected，不一致即 WARNING。

**为什么前几轮没发现**

- R27 的 M50 修的是 **worker 的路径白名单**，H11 修的是 **NSIS 卸载目录**；两者都是"某个模块的路径口径错"。**没有人把 config.py 的 `model_post_init` 与 `startBackend()` 的 env 注入放在一起比对覆盖顺序** —— 单看 config 觉得"日志放数据目录挺好"，单看 main.js 觉得"我注入了呀"。
- 测试环境永远不 `frozen`：`conftest.py` 用 `BUMOFU_BACKEND_DIR_OVERRIDE` 重定向，`sys.frozen` 恒 False，`if getattr(sys,'frozen',False)` 分支**在 CI 里靠 mock 打勾，从不真实执行**。
- 观测盲区：日志位置错了不会报错，只是"日志里没东西"——没人会怀疑日志路径。

---

### P0-2 麒麟 standalone：HOME 指向安装目录，数据全落 /opt；且 BACKUP_DIR 从未被接收

**位置**

- `backend/app/utils/paths.py:111-121`：
  ```python
  if is_bundled() or (is_linux() and not os.environ.get("BUMOFU_DEV_MODE")):
      if is_linux():
          data_dir = Path.home() / ".bumofu"        # ← 完全由 HOME 决定
  ```
- `deploy/kylin/DEBIAN/postinst:28-35`（服务用户的 HOME 就是安装目录）：
  `bash
  useradd --system --gid $APP_NAME \
          --home-dir $INSTALL_DIR \      # INSTALL_DIR=/opt/assistance-management-system
          --shell /bin/false --no-create-home $APP_NAME
  ```
- `deploy/kylin/config/kylin.env:25`：`BACKUP_DIR=/var/lib/assistance-management-system/backups`
- `backend/app/core/config.py:67-158`（Settings 字段定义）+ `utils/paths.py:156-169`（get_backup_path 只认 get_app_data_dir()/backups）

**现象（已实证）**

1. `BACKUP_DIR` **不是 Settings 字段**：
   ```
   'BACKUP_DIR' in Settings.model_fields  →  False
   ```
   全仓唯一读它的是 `backend/start.py:287`（仅用于 `_try_restore_from_backup` 的备份搜索），而 `get_backup_path()` 完全无视它。kylin.env 与 `start-kylin.sh:64` 都声明了这个变量 → **配了不生效**。
2. 模拟「HOME = 安装目录」后（`_probe_home3.py`）：
   ```
   get_app_data_dir : <INSTALL_DIR>/.bumofu
   get_backup_path  : <INSTALL_DIR>/.bumofu/backups
   kylin.env 声明的  : /var/lib/assistance-management-system/backups
   两者一致          : False
   ```
   即：`postinst:43` 精心创建的 `/var/lib/.../backups` **永远用不上**，备份实际写进 `/opt/assistance-management-system/.bumofu/backups`。
3. 该目录由 `root:root` 拥有（dpkg 解包 root 所有）→ 服务用户 `assistance-management-system` **不可写** → `BackupService.__init__` 的 `os.makedirs(self.backup_dir, exist_ok=True)`（`backup_service.py:184`）抛 PermissionError，自动备份全线失败。
4. 更糟：`runtime_secrets.json` 也走 `get_data_path()`（`runtime_secrets.py:212`）→ 落 `<INSTALL_DIR>/.bumofu/data/`。`_atomic_write_json` 的 `path.parent.mkdir(parents=True, exist_ok=True)`（`:218`）在不可写目录上抛 PermissionError，被 `_persist_runtime_secrets` 捕获后**降级为进程内密钥**（`runtime_secrets.py:100-103`）→ **每次重启 SECRET_KEY 变一次** → 已签发 JWT 全失效；`pii_crypto._load_key()` 用 `require_persisted=True`（`pii_crypto.py:48`）→ 此处 **raise RuntimeError** → **列表页任何 PII 字段读取直接 500**。

**真实后果**

- 麒麟 standalone（`docker/Dockerfile.kylin-standalone:189-193` 打包的就是 `deploy/kylin/*`）**装机即坏**：备份全废、密钥不持久、PII 读取 500。
- 一旦用户在没有正确密钥的情况下录入过数据，**历史 PII 密文不可逆**（AES-SIV 无密钥就是随机字节）。
- 可逆性：**数据不可逆**（符合 P0 定义）。

**修法**

1. `paths.get_app_data_dir()` 的 Linux 分支改为**显式环境变量优先**：`BUMOFU_DATA_DIR` → `XDG_DATA_HOME/bumofu` → `~/.local/share/bumofu`（不再用 `Path.home()/.bumofu`，因为 HOME 可能是安装目录）。
2. `deploy/kylin/config/kylin.env` 补 `BUMOFU_DATA_DIR=/var/lib/assistance-management-system`；`postinst` 的 `useradd` 改 `--home-dir /var/lib/assistance-management-system`（或补 `--create-home` 且赋权）。
3. 把 `BACKUP_DIR` 真正接进 `get_backup_path()`（env → settings → 推断，与 `get_database_path()` 同款三段链），或**删掉** kylin.env 里这个误导变量并在文档标注"备份目录由数据目录派生"。
4. `ensure_runtime_secrets` 的"降级为进程内密钥"必须 **fail-loud**（至少 CRITICAL + /health 暴露 `secrets_persisted=false`），否则用户永远不知道每次重启都在丢密钥。

- 改动面：paths.py、config.py、kylin.env、postinst、runtime_secrets.py + 门禁；约 120 行。

**验证方式**

- 单测：`monkeypatch.setenv('BUMOFU_DATA_DIR', tmp)` + `monkeypatch.setattr(paths,'is_linux',lambda: True)` → 断言 `get_app_data_dir() == tmp`（当前会返回 `Path.home()/.bumofu`）。
- 真机/容器：`docker build -f docker/Dockerfile.kylin-standalone` 后 `dpkg -i`、`systemctl start`，检查 `/var/lib/.../backups` 是否真出现 zip；检查 `runtime_secrets.json` 是否在 /var/lib 下且重启后 SECRET_KEY 不变。
- 现场自检：启动时打印 data_dir / backup_dir / secrets_file 三者绝对路径并断言均可写；诊断包加 `paths` 段。

**为什么前几轮没发现**

- R28 T5 的 H11 只把"卸载删哪个目录"从 LOCALAPPDATA 纠到 userData，**修的是 Windows 口径**；麒麟是另一条完全不同的链路（systemd + deb + HOME）。
- 麒麟部署文档的"推荐方式"是手工 `python3 -m uvicorn ...`（该文档 1248 行），**与真实发布的 Dockerfile.kylin-standalone + systemd 链路不是一回事**；审文档的人看不到 systemd 的 `User=` / HomeDirectory。
- kylin.env 是个"看起来一切齐备"的配置文件（DATABASE_URL/UPLOAD_DIR/LOG_FILE/BACKUP_DIR 全都有），**恰恰因为写得全，没人去验证每一个键是否真被消费** —— 典型的"配置即文档"陷阱。

---

## 2. P1 条目

### P1-1 换机/重装后 PII 密文永久不可解，而前端把密文当明文显示（静默）

**位置**

- `backend/app/core/pii_crypto.py:79-88`：
  ```python
  def decrypt_pii(value):
      if not is_encrypted(value): return value
      try:
          return _aessiv().decrypt(...).decode("utf-8")
      except Exception as e:
          logger.error("PII 字段解密失败（密钥不匹配或数据损坏）: %s", e)
          return value            # ← 原样返回 "enc.v1:<base64>"
  ```
- 密钥来源：`pii_crypto.py:42-55` → `runtime_secrets.get_or_create_secret(..., require_persisted=True)`，落盘位置由 `runtime_secrets.py:207-212` 决定 = `get_data_path("runtime_secrets.json")`。
- 该文件**不在**备份包内：`backup_service.py:369-398` 的 zip 成员只有 data/rural_revitalization.db、uploads/*、backup_info.json。
- 数据包导出同理（`data_package_service.py` 全文无 ENCRYPTION_KEY / PII 密钥搬运）。

**现象（已实证，`_k_enc.py` / `_k_dec.py` 两进程模拟换机）**

```
原密文: enc.v1:3aHN3I95kwLkKS7PcmWmCRtDP3qHW5puvSeH ...
解密结果: enc.v1:3aHN3I95kwLkKS7PcmWmCRtDP3qHW5puvSeH ...
失败后是否原样回显密文（前端不会报错，直接展示乱码）: True
```

**真实后果**

1. 换机/重装/迁移数据包后，villagers.id_card/phone、users.phone、schools.contact_phone 等 9 列（ADR-0005）**全部显示为 `enc.v1:...` 乱码**，页面不报错、不弹窗。
2. 用户若"修正"这些字段并保存：`EncryptedText.process_bind_param`（`models/base.py:37-40`）对已标记值**原样返回**（`encrypt_pii` 首行 `if value is None or is_encrypted(value)`）→ 密文被原样写回，**原始明文永久不可恢复**（实证：二次加密后 `again == ct`，即密文没变）。
3. 恢复演练查不出来：`restore_drill_service.py:134-157` 只做 integrity_check + 核心表 COUNT(*)，**不验证任何加密字段能否解密**。
4. 启动预检也查不出来：`startup/preflight.py:96-108` 的 `_check_encryption_key` 用 `encrypt_pii("preflight-probe")` 加密再解密**同一个自造值** —— 新密钥当然能解开自己刚加密的值，**永远返回 ok**。典型"自证式检查"。
5. 可逆性：**不可逆**（原始明文只存在于旧机磁盘）。

**修法**

1. `preflight._check_encryption_key` 改为**验证既有数据**：取一条带 `enc.v1:` 标记的既有密文尝试解密，失败即 warning + reason=key_mismatch 并写入 /health（需绕过 ORM 用裸 SQL 读密文，否则 EncryptedText 已吞异常）。
2. `decrypt_pii` 失败时**不要原样返回**：返回 None 或哨兵，让前端能区分"历史明文"与"密钥失配"。当前"原样返回"是为兼容未迁移明文，但 `is_encrypted()` 已能区分两者 —— 兼容理由不成立（既有 OCR 记录 `deliverables/ocr-findings-detail.md:612` 只把它当"改进建议"，未升级为 P0/P1）。
3. 备份包增加可选成员 `secrets/runtime_secrets.json`（**受备份密码保护**，默认不附带、加密备份时由管理员显式勾选）；或提供独立"密钥导出"管理员端点 + 文档写明"迁移必须同时带走密钥文件"。
4. 诊断包增加 `pii_key_health` 段（能否解开既有密文 + 样本条数，不出原文）。

- 改动面：pii_crypto.py、preflight.py、backup_service.py、diagnostics.py + 文档；约 150 行。

**验证方式**

- 单测：插入一行已知密文（固定密钥加密），换 ENCRYPTION_KEY 后断言 `decrypt_pii` 不返回原文、且 preflight 报 key_mismatch。
- 集成：`test_pii_encryption.py:96` 已有"DB 文件含密文标记"断言，补一条"换密钥后预检必须告警"。

**为什么前几轮没发现**

- ADR-0005 与 `CLAUDE.md:220-224` 都写了"多机离线同步部署**必须配置相同 ENCRYPTION_KEY**" —— 但这是**文档约定**，运行时没有任何机制校验它成立。而单机版用户根本没有"多机同步"的心智模型，他们认为"备份带走就是迁移"。
- `decrypt_pii` 原样返回密文是**有意的兼容设计**（ADR 明写"解密失败记日志并原样返回（不抛异常炸页面）"），审计时被归类为"设计选择"而放过 —— 但它组合上"缺密钥场景"就成了数据事故。
- preflight.py 是 W18 **同期新增**的（未跟踪文件），自证式实现是典型的"写测试时没想到要测失败路径"。

---

### P1-2 deleted_at 跨时区写脏：回收站保留期实际永久不触发

**位置**

- 列定义：`models/fund.py:145`、`models/project.py:144`、`models/school.py:102`、`models/supported_village.py:102` —— 均为 `Column(UtcDateTime(), ...)`（落库 naive UTC、读回 aware UTC）
- 写入端：`supported_village.py:961`、`funds.py:677`、`projects.py:1121`、`school.py:958`、`donation.py:305`、`pairing.py:323,422` 均已改用 `datetime.now(timezone.utc)`（正确）；`supported_village.py:802` 的批量 update 也正确。
- 判据端：`retention_service.py:46-64`
  ```python
  cutoff = datetime.now(timezone.utc) - timedelta(days=days)
  ...
  "WHERE is_active = 0 AND deleted_at IS NOT NULL AND deleted_at < :cutoff"
  ```
- 关键：`models/base.py:112-123` 的 `UtcDateTime.process_bind_param` 对 **naive 值原样落库**（`if value.tzinfo is None: return value`）—— 历史数据 / 其它写入路径一旦落了 naive 本地墙钟，就会被静默当作 UTC。

**现象（已实证，`_probe_deleted_at_tz.py`，本机 Asia/Shanghai UTC+8）**

```
落库原始值:
  id=1  2026-10-17 17:47:45.676398     ← datetime.now()      本地墙钟直接落库
  id=2  2026-10-17 09:47:45.677397     ← datetime.now(timezone.utc)  正确
读回 id=1: aware=2026-10-17 17:47:45+00:00  now_utc=2026-10-17 09:47:45  diff=-1 day, 16:00:00
```

即：**naive 本地墙钟被当成 UTC 读回，deleted_at 比真实时间"晚"了 8 小时**。

**真实后果**

1. `retention_service`（每日 04:30 由 `backup_scheduler.recycle_retention_job` 调用）判定"是否超 30 天"时，这些行的 deleted_at 被读成"未来时间" → **永远不满足 < cutoff** → 这些软删记录**永远不会被物理清除**，回收站保留策略对它们完全失效（且不报警）。
2. 前端展示"删除时间"偏早 8 小时（to_dict() 输出带 +00:00 → 浏览器按 UTC 转本地 → 比实际晚 8 小时）。
3. 可逆性：数据可修（重算 deleted_at），但**已跨年的错误时间无法从日志还原真实删除时刻**。

**修法**

1. 全仓 grep `deleted_at\s*=\s*datetime\.now\(\)`（当前 0 处，说明现存写入端已统一）；**但要扩大扫描到所有 UtcDateTime 列的赋值**，本机实测仍有 33 处裸 `= datetime.now()`（见 P2-2）。
2. 更根本：`UtcDateTime.process_bind_param` 对 naive 值不应静默放行 —— 加 **development 断言 + production WARNING 日志**，并写棘轮门禁 `scripts/check_naive_datetime_write.py`（AST 扫 `model.<UtcDateTime列> = datetime.now()`）。
3. 存量修复：一次性脚本输出"deleted_at 明显在未来（> now）"的可疑行清单供人工确认（不建议全自动 -8h，因为需按机器时区）。

- 改动面：门禁脚本 + 排查脚本 + 1 行断言；约 80 行。

**验证方式**

- 单测：mock 本地时区为 UTC+8，写一行 `datetime.now()`，断言 `retention_service` **不会**在 30 天内清掉它（现状是"永远不清"，测试应显式锁定这个错误语义以便回归时翻转）。
- 门禁：新脚本在 CI 跑 NEW == 0。

**为什么前几轮没发现**

- M31（R27）只提了 fund_service 的"年份用本地 date.today().year"；`time_utils.py` 模块文档把 deleted_at 类列视为已收口（因为 UtcDateTime 类型存在），**没人验证"写入端是不是真的用了 aware 值"**。
- 这类错误**在 UTC 主机上完全不可见**（datetime.now() 与 UTC 墙钟恰好接近），开发机/CI 全是 UTC，只有中国现场（UTC+8）才暴露 —— 本维度典型的"开发机永远复现不了"。

---

### P1-3 Windows 打包态备份目录不在 userData 下：卸载时随"删数据"一起被删

**位置**

- `backend/app/utils/paths.py:156-163`：`get_backup_path()` 的 base = `get_app_data_dir()/"backups"`（`return base` 在 :169）
- `backend/app/utils/paths.py:116-121`：Windows 打包态 `get_app_data_dir() = %LOCALAPPDATA%/bumofu-assistance`
- `backend/app/core/config.py` 的 BACKUP_DIR **不是字段**（见 P0-2 实证）
- `electron/main.js:319-334` 注入的环境变量**唯独没有 BACKUP_DIR**

**现象（已实证，`_probe_paths2.py`）**

Electron 注入了 DATABASE_URL / UPLOAD_DIR / EXPORT_DIR / CACHE_DIR / LOG_FILE，但**没注入 BACKUP_DIR**：

```
db           : ...\APPDATA\帮扶管理系统\database\rural_revitalization.db     ← userData
uploads      : ...\APPDATA\帮扶管理系统\uploads                            ← userData
backups      : ...\LOCALAPPDATA\bumofu-assistance\backups                   ← 不是 userData
```

**真实后果**

1. **卸载时备份被静默删除**：`electron-builder-nsis-hook.nsh:182-194` 询问"是否删除用户数据"，用户选"是" → 删 userData **和** `%LOCALAPPDATA%\bumofu-assistance`。用户以为只删了程序数据，其实**唯一灾备副本一起删了**。
2. **备份与数据不在同一"可搬走"单元**：用户按文档迁移 `%APPDATA%\帮扶管理系统`（`OFFLINE_UPGRADE.md:14,19-24`）→ 备份全部漏掉。
3. **OneDrive/漫游重定向场景**：`%APPDATA%` 被 OneDrive 或组策略接管时，SQLite 在网络盘上（见 P1-4），而备份在 %LOCALAPPDATA%（本地）—— 恰好是"备份比数据安全"的反向配置，但**没有任何界面说明**。
4. 可逆性：**备份被删不可逆**。

**修法**

1. `electron/main.js:319-334` 补 `BACKUP_DIR: path.join(getUserDataPath(), 'backups')`。
2. `paths.get_backup_path()` 改为三段链：BACKUP_DIR env → settings → 推断（与 `get_database_path()` 同款，AGENTS.md "Path Dual-Source" 规则已要求却漏了 backup）。
3. `check_userdata_path_consistency.py` 扩一条断言：BACKUP_DIR 必须在 Electron 注入列表里。
4. 卸载确认框文案改为列出**全部**将被删除的绝对路径（当前只列一个）。

- 改动面：main.js、paths.py、config.py、NSIS 钩子 + 门禁；约 60 行。

**验证方式**

- 单测：`monkeypatch.setenv('BACKUP_DIR', tmp)` → 断言 `get_backup_path() == tmp`（当前必失败）。
- 端到端：装包后看 `/api/v1/system/backup` 返回的 file_path 是否在 userData 下。

**为什么前几轮没发现**

- W18 P1-5 的 `check_userdata_path_consistency.py` **只校验了 NSIS 钩子与 productName**，没校验"后端所有数据类目录是否都在 userData 下"。
- AGENTS.md 的 "Path Dual-Source Bug" 规则列了 `get_database_path()` 与 `get_runtime_uploads_path()` 两个消费方，**恰好漏掉 get_backup_path()** —— 规则本身有缺口。
- 开发机 `sys.frozen=False`：`get_app_data_dir()` 走 `get_project_backend_dir()/backups`，**开发时备份与数据库天然同目录**，永远看不到这个分叉。

---

### P1-4 Windows 上 SQLite 落在 %APPDATA%（可能被 OneDrive/组策略重定向到网络盘），WAL 无任何降级

**位置**

- `backend/app/core/database.py:137-153`：
  ```python
  cursor.execute("PRAGMA journal_mode=WAL")
  cursor.execute("PRAGMA synchronous=NORMAL")
  cursor.execute("PRAGMA busy_timeout=10000")
  ```
  返回结果**全部被丢弃**（无 fetchone()）。
- `backend/app/utils/paths.py:163`（Windows）：dbDir = `path.join(getUserDataPath(), 'database')` = `%APPDATA%\帮扶管理系统\database`

**现象（已实证，`_probe_ro_db.py`）**

SQLite 在只读/受限文件系统上不会立即失败，而是**静默降级**：

```
B) 文件只读后：
   journal_mode=WAL -> ('wal',)          ← PRAGMA 仍"成功"，但……
   insert -> OperationalError attempt to write a readonly database
C) 目录不可创建：
   OperationalError unable to open database file
```

关键点：`PRAGMA journal_mode=WAL` 在**不支持 WAL 的文件系统（SMB/NFS/部分虚拟盘）上返回 'delete' 而不是 'wal'**，代码**不检查返回值** → 后续所有假设"WAL 已启用"的逻辑（并发读写、-wal 清理、backup_snapshot 合并）全部建立在错误前提上。

**真实后果**

1. `%APPDATA%` 被 OneDrive"文件和文件夹备份"接管（Win10/11 常见默认行为）→ 数据库文件可能被同步/占位（.cloud 文件）。SQLite 打开被云端"脱水"的文件会抛 SQLITE_CANTOPEN 或读到不完整页。
2. 组策略把 %APPDATA% 重定向到 `\\fileserver\profiles`（单位常见）→ SQLite 在 SMB 上，**WAL 不可用 + 文件锁语义不可靠** → 高频 `database is locked`，且断电/断网时库损坏概率显著上升。
3. 这套组合**没有任何启动检测**：`preflight._check_db_writable`（`preflight.py:46-60`）只测 `os.access(path, W_OK)`，对网络盘的 `os.access` 恒为 True。
4. 可逆性：库损坏后需从备份恢复；若备份也在同名卷（P1-3），**双双失效**。

**修法**

1. `database.py`：`mode = cursor.execute("PRAGMA journal_mode=WAL").fetchone()[0]`；mode != 'wal' → WARNING + 写入 `/health.database.journal_mode`（`system_health.py:330-358` 已有该字段：wal 分支 :336-352、非 wal 分支 :354-358，但只在被调用时读一次，**不参与启动决策**）。
2. preflight 增加 `_check_storage_kind()`：用 `drive_detect.py:18-36` 已有的 `GetDriveTypeW` 判定数据库目录所在卷是否为 network/removable，是则 warning: storage_on_network（启动横幅 + /health）。
3. 文档：Windows 部署文档增加"不要把 %APPDATA% 重定向到网络盘/OneDrive"的显式警告与检测命令。

- 改动面：database.py、preflight.py、drive_detect.py（复用）+ 文档；约 100 行。

**验证方式**

- 单测：mock `PRAGMA journal_mode` 返回 'delete' → 断言 /health 暴露 wal_unavailable。
- 现场自检：诊断包加 database.journal_mode / database.volume_type。

**为什么前几轮没发现**

- 所有测试都在 `tmp_path`（本地 NTFS）上跑，**WAL 恒可用**，PRAGMA 返回值从没被断言。
- %APPDATA% 与 OneDrive 的关系属于**操作系统部署层面**，不在任何代码 review 的视野里；R27/R28 的排查全部以"代码正确性"为轴。
- preflight 的 `_check_db_writable` 看起来覆盖了"不可写"，但网络盘恰恰是"可写但不可靠"，**os.access 天然测不出**。

---

### P1-5 自检全部是"自证式"：验证对象是刚造出来的东西，不是既有数据

**位置**

| 自检点 | 位置 | 验证对象 |
|---|---|---|
| 加密密钥预检 | `startup/preflight.py:96-108` | 刚 `encrypt_pii("preflight-probe")` 的值 |
| 备份恢复性校验 | `backup_service.py:416-465` | 刚写出的 zip 自己 |
| 恢复演练 | `restore_drill_service.py:134-157` | integrity_check + COUNT(*)，**不查内容语义** |
| 数据库完整性 | `start.py:241-279` | PRAGMA integrity_check（页级，不查业务一致） |

**现象**

`preflight._check_encryption_key` 的 `ok = decrypt_pii(token) == probe` —— token 是本次进程用当前密钥刚加密的，**只要密钥能自洽就恒 ok**。这与"既有密文能否解开"是**完全不同的问题**，而后者才是换机场景的真问题（见 P1-1）。

**真实后果**

- 换机/换密钥后：预检 ok、备份校验 ok、恢复演练 ok、integrity_check ok —— **四项全绿，但 PII 字段全是密文**。
- 现场排障时"所有自检都通过"反而**误导**：运维会认为数据完好，进而排除掉"密钥问题"这一真实原因。
- 可逆性：误判本身不可逆（延误恢复窗口）。

**修法**

每项自检改为**对既有数据取样**：
1. 密钥：取 1 条既有 `enc.v1:` 密文尝试解密（见 P1-1 修法 1）。
2. 备份校验：恢复后抽查 3 张核心表的**行数与最新时间戳**是否 ≤ 当前库（当前只 COUNT(*) 打印，不比对）。
3. 诊断包加 `selfcheck` 段：逐项 `{ok, reason, sampled_from:"existing_data"}`，明确标注"验证对象"。

- 改动面：3 文件；约 100 行。

**验证方式**

- 单测：构造"密钥已轮换但库里有旧密文"的 fixture → 断言预检 status=warning（当前会 ok）。
- 反向验证：人为删 runtime_secrets.json 后重启 → 预检必须红。

**为什么前几轮没发现**

- 「自检通过」很少被质疑。R27/R28 的重点是"有没有自检"，本轮才发现**自检的判据本身是错的** —— 这是"覆盖面 review"与"有效性 review"的差别。
- preflight.py 是本轮新增（未跟踪），其 18 个测试覆盖的是"函数能跑通"，不是"判据对不对"。

---

## 3. P2 条目（精简）

### P2-1 后端重启后 reload 失败无兜底，修复页本身也可能加载失败

**位置**：`electron/main.js:389-414`（自动重启后 loadURL）、`:533-554`（showRecoveryPage）。

`mainWindow.loadURL(...).catch()` 只记日志，**不重试也不进修复页**（`:405-408`）。而 showRecoveryPage 在 recovery.html 缺失时退回 `dialog.showErrorBox`，用户只能强杀。
**后果**：后端重启配额耗尽 → 引导页；但若引导页本身加载失败（file:// 白名单/杀软拦截），用户面对**空白窗口 + 无任何可用操作**。
**修法**：loadURL 失败 → showRecoveryPage('load-failed')；showRecoveryPage 内部再包一层 loadFile 失败 → `dialog.showMessageBoxSync` 给出日志绝对路径 + "在资源管理器打开"。改动面：1 文件 ~30 行。

### P2-2 33 处裸 datetime.now() 赋值（时区脏源面）

**位置**：`backend/app` 内 33 处（`grep '= datetime.now()'`）。多数仅用于文件名/年份（可接受），但 `notification_preference_service.py:253`（now = datetime.now().time() 与库中 UTC 时间比较）、`backup_scheduler.py:678,701`（_schedule_daily/_weekly 用本地时间算 delay，**这是对的**，但与 last_backup_time 的本地墙钟口径耦合）。
**修法**：加 AST 门禁 `check_naive_datetime_write.py`，白名单只允许"文件名时间戳/纯展示"两类。

### P2-3 调度器无"错过补跑"：机器关机跨过 02:00，当天备份永久丢失

**位置**：`backend/app/services/backup_scheduler.py:656-676`（`_schedule_daily`，threading.Timer 一次性排到下一个 HH:MM）。

threading.Timer 基于单调时钟延后；机器休眠/关机期间 Timer 不推进，恢复后若已过目标时间，_job 触发一次后**重新按"下一个 HH:MM"排**，**不补跑错过日期**。而 auto_backup_job 的间隔判定用 last_backup_time（本地墙钟文本），因此"昨天没备份"只会在今天 02:00 补一次 —— 若机器习惯性 22:00 关机、08:00 开机，**02:00 的任务永远不执行**。
**后果**：单机离线场景（正是本项目）自动备份可能**长期不落盘**，而 UI 上"自动备份=已启用"。这是本维度最隐蔽的失效。
**修法**：_schedule_daily 改为"启动时检查 last_run > 24h 则立即补跑一次"（catch-up），并把 last_run 落 SystemConfig。改动面：backup_scheduler.py ~50 行 + 单测。

### P2-4 LOG_ROTATION 是死配置，日志实际按天滚动且大小上限永不生效；crash.log 完全无轮转

**位置**：`backend/app/core/config.py:188-191` 定义 LOG_ROTATION="10 days"、LOG_RETENTION="30 days"；`logging_config.py:239` 只判 `if log_rotation:`（大小上限分支在 `:249-254` 的 else 里，永不进入）（非空即真）→ **恒走 SafeTimedRotatingFileHandler(when="midnight", backupCount=5)**，LOG_MAX_SIZE_MB 只在 else 分支用，**永不生效**；LOG_RETENTION 全仓零消费（已 grep 确认）。
**后果**：单文件可涨到任意大小，backupCount=5 只保留 5 天 —— 与配置说的"30 天/50MB"完全不符。且 `main.js:44` 的 crash.log **完全无轮转**（29 处 appendFileSync，无大小检查）。
**修法**：configure_logging 改用 maxBytes+backupCount 组合（或给 SafeTimedRotatingFileHandler 加大小上限）；crash.log 加 `statSync().size > 2MB` 时轮转。改动面：2 文件 ~40 行。

---

## 4. P3 条目（清单式）

1. **window-state.json 的显示器消失**：`electron/main.js:42` / `:619-635`（`loadWindowState` :619 / `saveWindowState` :628）保存的 bounds 可能位于副屏（x: -1920），用户拔掉副屏后窗口落在可视区外，且**无 screen.getDisplayMatching 校正**（全仓无该调用，grep 已确认）→"程序启动了但看不见"。
2. **checkPortInUse 只测 127.0.0.1**（`main.js:215`）：若某进程只绑 0.0.0.0:8000，探测可能报"空闲"→ 后端绑定失败 → 进入"启动超时"路径浪费 5 分钟。
3. **全局无条件禁用硬件加速**（`main.js:1260` 与 `:1283` 重复调用，且无开关）：老机器/国产 GPU 上大屏与地图渲染可能极慢。建议给 --disable-gpu 加环境变量逃生门。
4. **offlineMock.ts 是死代码但仍在维护**：`frontend/src/utils/offlineMock.ts` 约 577 行的触发条件 `token.startsWith('builtin-token-')` 在全仓**无生产者**（仅测试里出现）；且 `getMockResponse` 匹配 `/villages`、`/funds` 等旧路径，与前端实际调用的 `/supported-villages` 等不一致 → 即使被触发也大量落空。
5. **备份管理页恒显示"未启用"**：`backend/app/api/v1/system/backup.py:400` 读 `os.getenv("AUTO_BACKUP_ENABLED")`，全仓**无任何写入方**（backend/electron/deploy/docs 均已 grep 确认）→ `BackupManagement.vue:127` 的标签恒为"未启用"，与实际（`auto_backup` 默认 true）相反。应改读 `get_config("auto_backup")`。

---

## 5. 建议的落地批次

| 批次 | 内容 | 依赖 / 前置 | 预估 |
|---|---|---|---|
| **B1** | P0-1 日志路径收口 + APP_DATA_ROOT 单一入口 + 门禁 | 无（纯路径推导，风险低） | 半天 |
| **B2** | P1-3 备份目录进 userData（BACKUP_DIR 注入 + 三段链）+ 卸载文案列全路径 | 与 B1 同源，一起改一次 | 半天 |
| **B3** | P1-1 PII 密钥失效可见化（预检抽样既有密文 + decrypt_pii 返回哨兵 + 备份带 key_fingerprint） | **要先定设计**：备份是否携带密钥（安全 vs 可迁移） | 1-2 天 |
| **B4** | P0-2 麒麟数据目录 / BACKUP_DIR / 密钥落盘 + 真机复验 | 需麒麟 ARM64 环境；**必须先定** Linux 数据目录规范 | 1 天 |
| **B5** | P1-4 存储卷类型检测 + WAL 返回值断言 + /health 暴露 | 无 | 半天 |
| **B6** | P2-3 调度器 catch-up（单机离线最痛的静默失效） | 无 | 半天 |
| **B7** | P2-1 / P2-2 / P2-4 / P3-1~5 | 无 | 分散 |

**能合并的**：B1+B2（同属"路径单一事实源"，一次改完一次验证）；B5 与 P3-3（都涉及启动参数）。

**必须先定设计的**：

- **B3 的"备份是否带密钥"** —— 带则备份包成为密钥泄露面（当前备份可被管理员下载/拷走），不带则换机必丢 PII。建议折中：**备份包内加 key_fingerprint（SHA256 前 8 位），恢复时比对，不一致则明确报错拒绝恢复**，而不是静默带密钥。
- **B4 的 Linux 数据目录规范** —— `~/.bumofu`（paths.py）、`/var/lib/assistance-management-system`（kylin.env）、`$HOME/.assistance-management-system`（start-kylin.sh:54 的降级目录）**三套并存**，需要一次统一，否则改一处坏一处。

---

## 6. 与并行会话（W18-B）的重叠说明

探测收尾时发现工作区有另一会话正在做密钥相关修复（electron/main.js +84 行、
pii_crypto.py +10 行、backup_service.py 2 行、preflight.py 新增抽样校验）。
逐条比对后重叠情况如下（**结论仍成立，只是部分已被人抢先修**）：

| 本报告条目 | 并行会话状态 | 本报告仍新增的信息 |
|---|---|---|
| P1-1 PII 密文失解 | **部分已修**：pii_crypto.key_fingerprint() 新增；preflight 改为抽样既有密文 | ① decrypt_pii 仍原样返回密文（未改）；② 备份包仍不带密钥/指纹；③ 迁移必须带密钥仍无运行时强制 |
| P1-5 自证式自检 | **PII 一项已修**（改为抽样既有密文） | 备份恢复性校验 / 恢复演练 / integrity_check 三项仍是自证式，未动 |
| P2-2 裸 datetime.now() | **部分已修**：backup_service 的 created_at 改为 utcnow() | 其余 32 处仍在；且没有门禁防止新增 |
| P0-1 / P0-2 / P1-2 / P1-3 / P1-4 / P2-1 / P2-3 / P2-4 / P3 | **未触碰** | 全部为本报告首报 |

即：并行会话修的是「**密钥不可用时要看得见**」（体验层），本报告指出的 P0-1 / P0-2 /
P1-3 / P1-4 修的是「**数据根本不该落到那些目录/卷上**」（根因层）—— 两者不重复，
且**根因未修则体验层提示会常态化误报**（每次都弹密钥已重置）。
建议合并时把 P0-1/P1-3 的路径收口排在 W18-B 之前，否则该弹窗会在正常机器上反复出现。

## 7. 总结

本维度 16 条里，**有 11 条是"开发机永远复现不了"**：

- 4 条依赖 `sys.frozen=True`（日志路径、备份目录、app_data_dir、密钥持久化）—— CI 里 frozen 分支靠 mock 打勾；
- 3 条依赖 `timezone != UTC`（deleted_at、回收站保留、展示偏移）—— CI 全是 UTC；
- 2 条依赖**真实文件系统/卷类型**（只读、网络盘、WAL 不可用）—— 测试全在 tmp_path 的 NTFS 上；
- 2 条依赖**真实装机/卸载/换机**（备份被卸载删除、换机 PII 失解）—— 只有用户现场才发生。

这也解释了为什么 R27/R28（纯静态 + 单测）会漏掉它们：**共同特征是"代码本身看着对，错在与运行环境的耦合"**。建议下一轮把这类检查前移：

> **给每个"从环境拿值"的函数加一条"注入 vs 实际"的断言**（B1/B2 的门禁就是这个模式），
> 并**把自检判据从"自证"改成"抽样既有数据"**（B3 的核心）。

这两条能覆盖本报告约 60% 的条目，且成本远低于逐条人工 review。
