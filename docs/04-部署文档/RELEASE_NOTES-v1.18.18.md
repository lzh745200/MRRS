# Release Notes — v1.18.18（2026-10-28）

> 供 GitHub Release 正文使用；逐项变更见仓库根目录 `CHANGELOG.md` 的 `[1.18.18]` 段。
> 本版是技术债棘轮上线后**第一次真的往下压**：沿 mypy 明细核实高风险类别，
> 修掉 3 处真问题，基线 1394 → **1391**。

## 一、下载与校验

| 安装包 | 适用平台 |
|---|---|
| `MRRS-Setup-1.18.18-x64.exe` | Windows 10/11 x64（NSIS 安装包，含全部运行时） |
| `MRRS-Setup-1.18.18-arm64.deb` | 麒麟 V10 / 统信 ARM64（Electron） |
| `assistance-management-system_1.18.18_arm64.deb` | 麒麟 V10 / 统信 ARM64（standalone，无 Electron） |

同一 Release 附带 `SHA256SUMS-*.txt`（三个安装包指纹）与 `latest.yml` /
`MRRS-Setup-1.18.18-x64.exe.blockmap`（electron-builder 的 NSIS 产物，**本系统不消费**：
无自动更新逻辑，升级走覆盖安装）。

```powershell
Get-FileHash .\MRRS-Setup-1.18.18-x64.exe -Algorithm SHA256
```

> **未签名包提示**：证书尚未采购，首次运行会触发 SmartScreen（「更多信息」→「仍要运行」）。

## 二、本版修了什么

### 1. 用户可见的乱码报错（加密数据包）

数据包版本不匹配时，原实现把 `bytes` 直接拼进 f-string：

```
不支持的版本: b'9.9'            ← 用户看不懂
```

更麻烦的是**非法版本字节**：`b'\x02'.decode("ascii")` 是合法的不可见控制符，
消息会渲染成 `不支持的版本: `（冒号后一片空白）—— 比乱码更难排查。

现在统一经 `_as_text()` 渲染：

```
不支持的版本: 9.9（本机支持 1.0）      ← 可读
不支持的版本: \x02（本机支持 1.0）     ← 非法字节转义，仍可定位
```

可打印 ASCII 原样输出；控制符与非 ASCII 字节一律转义为 `\xNN`；该函数本身绝不抛错
（错误消息渲染失败会掩盖真正的错误）。

### 2. 把内建函数当类型注解（业务指标服务）

```python
def _get_cached(self, key: str) -> Optional[any]:   # any 是内建函数，不是 typing.Any
def _set_cached(self, key: str, value: any):
```

`typing` 容忍任意对象，所以**不报错、也没有任何约束** —— 属于"静默失效"的注解，
比不写注解更误导（读者以为有类型约束）。已改为 `Optional[Any]` / `Any` 并补 import。
全库扫描确认只有这两处（其余命中是文档字符串与生成的更新日志）。

### 3. 棘轮基线首次下调

| 指标 | v1.18.17 | v1.18.18 |
|---|---|---|
| mypy 错误数 | 1394 | **1391** ↓3 |
| 前端 `as any` | 196 | 196 |
| `except Exception` | 802 | 802 |

这是棘轮**第一次真正起作用的方向**（只降不升）。

## 三、核查留痕（看过但**没改**的，避免下次重复排查）

沿 mypy 高风险类别逐条核实，绝大多数是误报：

| 类别 | 抽样 | 结论 |
|---|---|---|
| `operator` | `village_cascade_delete_service:156` `count > 0` | `SELECT COUNT(*)` 必返行，另有 try/except 兜底 |
| `operator` | `reminder_engine:30` `utcnow() - created_at` | 上一行有 `if created_at is None: return 0.0` 守卫 |
| `union-attr` | `system_config_service:315` `Session \| None` | 会话由依赖注入保证非空 |
| `call-arg` | `organization_service:577` `OrganizationStatistics(by_level=…)` | 字段确实存在（全库唯一定义），误报 |
| `misc` | `api_error:85` `await func(...)` | 装饰器按 `iscoroutinefunction` 分流，同步函数不走这里 |
| `attr-defined` | `win_proactor_fix` / `cache._cache` | 反射与向后兼容层，刻意为之 |

另对全库 **129 处**"静默吞异常"候选逐个看上下文：**15 处完全无声的全部有注释说明**
（dry-run 回滚、`PRAGMA optimize`、PII 脱敏失败不阻断、审计归因不阻断、worker 取消、
mapper 探测兜底），其余是把错误**收进 `errors` 列表返回**（错误其实上报了）。
**无一需要改动**，故不动 —— 不做无收益的批量改动。

## 四、验证

- 新增 4 例：`_as_text` 三种输入（可打印 / 控制符 / 非法字节）+ 版本不匹配消息可读性
  （断言不含 `b'`、含 `9.9` 与 `1.0`）；
- `encrypted_package.py` 覆盖率 **100%**（81 语句 / 18 分支）；引用它的 11 个测试文件 **579 例全过**；
- flake8 两文件 0 错误；`check_type_debt.py` 1391 / 196 / 802 持平 ✓；
- CI 在 tag 提交上跑完整 12 段后端 + 覆盖率 100% + 前端 + E2E + 静态分析（含棘轮）。

## 五、升级注意

- 功能行为与 v1.18.17 一致；本版只改错误文案、注解与基线，**无数据迁移**；
- 升级方式不变：下载对应平台安装包 → 覆盖安装（数据库与上传目录不受影响），
  详见 `docs/04-部署文档/OFFLINE_UPGRADE.md`。
