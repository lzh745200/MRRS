# Release Notes — v1.18.18（2026-10-28）

> 供 GitHub Release 正文使用；逐项变更见仓库根目录 `CHANGELOG.md` 的 `[1.18.18]` 段。
> 本版修 **5 类真缺陷**：6 个系统接口全部不可达、4 条重复路由、加密包乱码报错、
> 把内建函数当类型注解，并把技术债棘轮基线**首次下调**（mypy 1394 → 1391）。

## 一、下载与校验

| 安装包 | 适用平台 |
|---|---|
| `MRRS-Setup-1.18.18-x64.exe` | Windows 10/11 x64（NSIS 安装包，含全部运行时） |
| `MRRS-Setup-1.18.18-arm64.deb` | 麒麟 V10 / 统信 ARM64（Electron） |
| `assistance-management-system_1.18.18_arm64.deb` | 麒麟 V10 / 统信 ARM64（standalone，无 Electron） |

同一 Release 附带 `SHA256SUMS-*.txt` 与 `latest.yml` / `MRRS-Setup-1.18.18-x64.exe.blockmap`
（electron-builder 的 NSIS 产物，**本系统不消费**：无自动更新逻辑，升级走覆盖安装）。

```powershell
Get-FileHash .\MRRS-Setup-1.18.18-x64.exe -Algorithm SHA256
```

> **未签名包提示**：证书尚未采购，首次运行会触发 SmartScreen（「更多信息」→「仍要运行」）。

## 二、最严重的一条：6 个系统接口全部不可达

`app/api/v1/system/__init__.py` 的聚合器已经是 `APIRouter(prefix="/system")`，
而 `system.py` 自己**又写了** `prefix="/system"` —— 于是实际注册成：

```
/api/v1/system/system/{info, status, shutdown, restart, environment, version}
```

正确路径 `/api/v1/system/info` 等**全部 404**。这 6 个接口（含**关机/重启**）等于摆设；
因为前端取系统信息走别的途径、Electron 与自动化测试都不调它们，**一直没人发现**。
修复：`system.py` 的 prefix 改为空，由聚合器统一加。

> **修复时差点放出的雷**：`/system/shutdown`、`/system/restart` 的依赖层只有
> `Depends(get_current_user)`（**任意登录用户**），真正的管理员校验在**函数体内**。
> 它们此前不可达所以无害，路径一修通就变成"任何登录用户可关机"。
> 已实测确认函数内 `require_admin` 存在（`system.py:235` / `273` / `336`）才动手 ——
> 这条提醒我们：**修"不可达"缺陷前，必须先确认它不可达时掩盖了什么**。

## 三、4 条重复路由

`config_package` 模块的 router 自带 `prefix="/system/config-packages"`，是给
`api/v1/__init__.py` 的「子模块直挂」用的（注释写明"历史表面，勿删"），
但聚合器**又 include 了一次**，多注册出 `/api/v1/system/system/config-packages` 等 4 条。
修复后**端点总数（路径+方法口径）849 → 845** —— 减少的 4 条正是重复注册。

## 四、新增路由认证覆盖门禁

`api_v1_router` **没有全局认证依赖** —— 每个路由必须自己声明 `Depends(get_current_user)`，
少写一行就是越权入口，code review 很难发现。新门禁 `scripts/check_route_auth.py`
用 FastAPI **运行时依赖树递归判定**（能识别经角色守卫间接要求认证的路由），
白名单外的无认证路由即失败。

上线时逐个核查了全部 **58 个无认证路由，无真实漏洞**：

| 类别 | 保护机制 |
|---|---|
| 登录/登出/CSRF/公开配置 | 本身即认证入口；logout 用可选 token |
| 健康检查 | 容器探针需免认证 |
| 地图瓦片 | Leaflet `<img>` 直连带不了 token，代码注释明示"无鉴权" |
| 机器码 4 个 | 限流 5/60s + loopback + 机器码&校验码双验证 + 账号须从未激活 |
| 权限包导入 | 未登录或非管理员时限 loopback |
| 反馈 | 有意允许匿名（可选 Authorization 头关联用户） |
| shutdown | 仅 127.0.0.1/::1 + `INTERNAL_SHUTDOWN_KEY`，未配置则拒绝 |
| 系统初始化 | 初始化前无用户无法认证；`is_initialized()` 拒绝重复初始化 |
| 备份 3 个 | 函数体内自定义认证（内部密钥或登录账号） |

门禁的**已知局限**（函数体内认证检测不到）写进了白名单注释。

## 五、用户可见的乱码报错（加密数据包）

数据包版本不匹配时，原实现把 `bytes` 直接拼进 f-string，用户看到 `不支持的版本: b'9.9'`；
更糟的是非法版本字节（`b'\x02'.decode("ascii")` 是合法但**不可见**控制符）
会渲染成 `不支持的版本: `（冒号后一片空白）—— 比乱码更难排查。
现统一渲染：`不支持的版本: 9.9（本机支持 1.0）`，非法字节转义为 `\xNN`。

## 六、把内建函数当类型注解

```python
def _get_cached(self, key: str) -> Optional[any]:   # any 是内建函数，不是 typing.Any
```

`typing` 容忍任意对象，所以**不报错、零约束** —— 属静默失效的注解（比不写更误导）。
已改为 `Optional[Any]` / `Any`；全库扫描确认仅此两处真实代码。

## 七、技术债棘轮首次下调

| 指标 | v1.18.17 | v1.18.18 |
|---|---|---|
| mypy 错误数 | 1394 | **1391** ↓3 |
| 前端 `as any` | 196 | 196 |
| `except Exception` | 802 | 802 |

## 八、核查留痕（看过但**没改**的）

- mypy 高风险类别逐条核实，绝大多数是误报：`operator`（`COUNT(*)` 必返行 / 已有
  `is not None` 守卫）、`union-attr`（会话由依赖注入保证非空）、`call-arg`
  （`OrganizationStatistics.by_level` 字段确实存在）、`misc`（装饰器按
  `iscoroutinefunction` 分流）、`attr-defined`（反射/兼容层）；
- 全库 **129 处**"静默吞异常"候选逐个看上下文：15 处完全无声的**全部有注释说明**
  （dry-run 回滚、`PRAGMA optimize`、PII 脱敏失败不阻断、审计归因不阻断、worker 取消、
  mapper 探测兜底），其余是把错误**收进 `errors` 列表返回**（错误其实上报了）——
  **无一需要改动**，故不做无收益的批量改动。

## 九、验证

- 路由：`/api/v1/system/info` 存在、旧的 `/api/v1/system/system/info` 已消失；
  路由总数 **849**；路由鉴权门禁 **58 个无认证路由全在白名单**；
- 新增 4 例（`_as_text` 三种输入 + 版本消息可读性，断言不含 `b'` 且含 9.9/1.0）；
- `encrypted_package.py` 覆盖率 **100%**（81 语句 / 18 分支）；引用它的 11 个测试文件 **579 例全过**；
- flake8 全 0；`check_type_debt.py` 1391 / 196 / 802 持平 ✓；
- CI 在 tag 提交上跑完整 12 段后端 + 覆盖率 100% + 前端 + E2E + 静态分析（含棘轮与路由鉴权）。

## 十、升级注意

- **本版包含一处行为变化**：`/api/v1/system/{info,status,environment,version}` 现在真的可用
  （此前 404）；关机/重启路径修通后仍然**仅超级管理员**可执行（函数内校验已验证）；
- 无数据迁移；升级方式不变：下载对应平台安装包 → 覆盖安装，
  详见 `docs/04-部署文档/OFFLINE_UPGRADE.md`。
