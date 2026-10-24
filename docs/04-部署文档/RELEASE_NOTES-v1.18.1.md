# Release Notes — v1.18.1（2026-10-24）

> 供 GitHub Release 正文使用；逐项变更见根目录 `CHANGELOG.md` 的 `[1.18.1]` 段。

## 一、下载与校验

| 安装包 | 适用平台 | 大小 | SHA256 |
|---|---|---|---|
| [`MRRS-Setup-1.18.1-x64.exe`](https://github.com/lzh745200/MRRS/releases/download/v1.18.1/MRRS-Setup-1.18.1-x64.exe) | Windows 10/11 x64（NSIS 安装包，含全部运行时） | 270.02 MB | `beab6f9081720bd084b2cce6491a2a984b7fdbf079be012388749d824e2eb7c9` |
| [`MRRS-Setup-1.18.1-arm64.deb`](https://github.com/lzh745200/MRRS/releases/download/v1.18.1/MRRS-Setup-1.18.1-arm64.deb) | 麒麟 V10 / 统信 ARM64（Electron） | 266.65 MB | `7afd80faa948bbccce8598ebff3a3da36a779c33013d1d95a4f7a04fe1643016` |
| [`assistance-management-system_1.18.1_arm64.deb`](https://github.com/lzh745200/MRRS/releases/download/v1.18.1/assistance-management-system_1.18.1_arm64.deb) | 麒麟 V10 / 统信 ARM64（standalone） | 98.07 MB | `14581820e7686c9f2578dd27c24588a6d36d7ef9892c360dc4525921d9ae0524` |

> 同一 Release 还附带 `SHA256SUMS-*.txt` 三个校验文件与 Windows 自动更新所需的
> `latest.yml` / `.exe.blockmap`。以上 SHA256 与 GitHub Release 资产的 `digest` 字段一致。

离线校验（Windows）：

```powershell
Get-FileHash .\MRRS-Setup-1.18.1-x64.exe -Algorithm SHA256
```

离线校验（麒麟/统信）：

```bash
sha256sum MRRS-Setup-1.18.1-arm64.deb
```

## 二、本版重点

### 1. 登录页：修掉"点了必然失败"的入口，并把等待时间说清楚

- **注册入口死链**：系统默认 `SELF_REGISTER_MODE=off`（不开放自助注册），但登录页**无条件显示**"注册账户"。
  后端其实早就提供了 `GET /api/v1/auth/public-config`，前端从未调用。
  现在按配置显隐；**取不到配置就隐藏**（fail-closed）——宁可不显示，也不给用户一个必然失败的按钮。
- **锁定/限流可见化**：被锁定时原来只有一行字。现在后端透出 `lockout_minutes` / `max_failed_attempts`，
  前端显示"请稍候 30 分 00 秒"并禁用按钮，倒计时结束自动恢复；限流显示 60s 冷却。
- **未授权本机**（403）额外给「去获取机器码」直达按钮，不用用户自己去翻菜单。
- **失败即清空密码并聚焦**：多人共用一台机器的场景下，残留密码既不方便也不安全。
- **CapsLock 提示**、**2FA 满 6 位自动提交**、**「首次使用？」三步引导**（机器码 → 权限包 → 通行码）。
- **首屏更快**：12 张背景图（3.51MB）轮播改为 1 张静态图（0.35MB），**净减 3.16MB**。

### 2. 顺手修掉的一个真 bug：后端中文错误文案全部丢失

`authStore.login` 读的是 `err.response.data.message`，而 FastAPI 的错误体是 `{detail: "..."}`。
于是所有中文提示（如"账户已锁定，请30分钟后再试"）都被丢弃，用户看到的是
`Request failed with status code 423`。现已按 `detail → message → err.message` 取值。

### 3. 质量门禁：从"段数通过"到"阈值真正生效"

发布前复验时发现 `backend/.coveragerc` 在工作区被误删 —— `fail_under=100` 不再生效，
分段执行器报告的 12/12「全绿」实际只有 **99%**。已恢复配置并补齐全部缺口：

- `FundTransaction` / `MachineCode` 的 `__repr__`（日志与审计会调用它，必须能在字段为 None 时安全输出）；
- 备份元信息解析的 str/JSON/历史 `str(dict)` 三种形态；增量包"取不到密钥指纹"分支；
- 无组织字段模型的数据变更统计分支；**单位码不一致的 409 阻断**；**密钥不一致时清理临时包**。

最终口径：**后端 45,782 语句 / 11,376 分支，Miss 0 / BrPart 0（100.00%）**；
**前端 332 文件 / 7,023 用例，行/分支/函数/语句四项 100%**。

### 4. 新增 R35 三层对齐门禁，并修掉它抓出的漂移

比对 **前端 API 路径 ↔ 后端路由**、**ORM 模型 ↔ 数据库 schema**、**前后端字段**三轴，
专治"单测全绿、真机全废"的契约漂移（历史案例：`/system/self-check` 恒 404、`OrganizationCreate` 漏 `code`）。

门禁上线即抓到两处真问题：

- `tea_plantations` / `cactus_fruit_plots` 模型仍叫 `village_id`，库里已是 `supported_village_id`
  （`r42` 迁移的注释里写着要改模型，但没改）；
- 数据上报 `subordinate dashboard` 的 schema 字段名与 service 实际返回不一致，
  被 Pydantic `extra=ignore` 吞掉。

## 三、升级说明

- **数据库**：新增迁移 `r42_align_stack_columns_001`，启动时自动执行（幂等；旧库升级后
  `tea_plantations` / `cactus_fruit_plots` 的列名与索引名对齐为 `supported_village_id`）。
- **配置**：无新增必填项。如需开放自助注册仍设 `SELF_REGISTER_MODE=controlled`。
- **兼容性**：登录接口错误语义（401/403/423/429）未变，仅前端展示方式变化；
  `public-config` 只**新增**两个字段，旧客户端不受影响。
- **数据目录**：与 1.18.0 一致（Windows `%APPDATA%\MRRS`、麒麟 `~/.local/share/mrrs`），升级不迁移数据。

## 四、验证记录

| 项 | 结果 |
|---|---|
| 后端 CI 12 段 | 12/12 PASS |
| 后端覆盖率（`fail_under=100` 生效） | 100.00%（Miss 0 / BrPart 0） |
| 前端全量 | 332 文件 / 7,023 用例全过 |
| 前端覆盖率 | 100 / 100 / 100 / 100 |
| `flake8 app/` | 0 |
| 门禁脚本 | 14 个全绿（含三层对齐、零断言棘轮、同步覆盖率、单 head 迁移） |
| 安装包（Windows x64 / 麒麟 ARM64） | 由 GitHub Actions `v1.18.1` tag 构建，产物与校验和见上方表格 |
