# v1.18.31 发布说明（2026-10-31）

> 本版主题：**瓦片地图「缩放看不到全省、没有图注」** 的现场问题修复，外加**打包态后端启动健壮性**（P0）与一轮全库类型 / 测试收口。

## 一、地图瓦片：任何单个瓦片包导入后都能看到全省

现场反馈：导入 z13/z14 瓦片包后地图缩放看不到全貌、右侧没有图注。根因有两条叠加：

1. 旧 z13/z14 包与会话安装包**不含 z5–8 概览层**，可用最低层级被抬到 13/14，前端最多只能再降 2 档；
2. `maxBounds` 用的是**测量覆盖 bbox**，只导入市州包时它与全省无关，缩放到全省会被弹回。

本版改动：

- **每个瓦片包内置 z5–8 全省概览**（31 张 / 约 0.8 MB）；安装包恢复内置 z5–12（5,623 张 / 60.0 MB）——新装环境即使不导入任何包，也能在地图页缩放查看全省。
- **视图范围解耦**：`tileViewBbox = 覆盖 bbox ∪ 全省 bbox`，不再被市州包锁死；新增「全省视图」按钮；缺少概览时给出明确提示与补装包名。
- **右侧图例 / 图注**（默认展开、可收起）：帮扶村、学校、乡镇/县市注记、道路/水系/行政界符号说明 + 瓦片数/层级/来源 + © OpenStreetMap contributors；新增比例尺控件。
- **性能**：瓦片扫描改用 `os.scandir`（7 万张实测 8.6s → 0.38s）；`/map/tile-info` 与导入后统计改走线程池，扫描期间不阻塞事件循环。

补装建议：已有 z13/z14 包的环境，额外导入 `guizhou-overview_z5-8.zip` 即可获得全省概览。

## 二、打包态后端启动健壮性（P0）

**问题**：安装包内的后端在缓存目录不可写 / 残留 `-wal` 状态异常时，会在**模块导入期**构造 `diskcache.Cache` 抛异常，导致整个后端启动失败（现场表现为双击后长时间无窗口、8000 端口不监听）。

**修复**：

- 仪表盘缓存改为**懒初始化**（首次使用时才建库），并给 `diskcache.Cache` 加 `timeout=2`；
- 初始化阶段的**任何异常**都降级为「直查数据库」，且只尝试一次，绝不拖垮启动；
- 配套 11 项单测覆盖：只读库 / 打不开库 / 拒绝访问 / 磁盘满 / makedirs 失败 / 正常路径 / 降级后三函数 no-op。

**实测**：安装包内 `assistance-backend.exe` 在**默认缓存目录**下 10 秒内 `/api/v1/health/liveness` 返回 200，`/health` 全项 ok（`migration.at_head=true`、`journal_mode=wal`），桌面端主窗口正常渲染到登录页，`admin` 账号登录返回 200。

**独立复核（发布流水线干净 Windows runner）**：`Smoke test packaged backend (self-contained)` 步骤从 `dist/electron/win-unpacked` 启动同一份打包后端，输出 `打包后端自包含冒烟通过: version=1.18.31 git_hash=18428cb migration_head=fk_machine_codes_created_by_001`，`GET /health 200 OK`，日志含 `Application startup complete` 与 `Uvicorn running on http://127.0.0.1:18123`；该步骤与「Verify installer signature」「Generate SHA256SUMS」同为发布必过项。

## 三、业务缺陷修复

- **组织树节点字段恒为空**：`_build_tree` 漏传 `type` / `org_type` / `contact_email`，树接口这三个字段一直为空，现按 ORM 原值透传。
- **智能推荐读不存在的列**：`match_policies` 访问 `Policy` 并不存在的 `scope` / `province` / `city`，真库一旦有 active 政策即 `AttributeError`（单测用 MagicMock 掩盖了 schema 漂移），改为 `getattr` 降级为纯关键词匹配并补回归用例。
- **组织根节点层级**：首启单位允许省 / 市州 / 县级任一层级作为根（`522700` 这类市州级根组织的报错已修），子节点仍必须**严格 parent+1**。
- **学校导入**：年级字段判重与落库口径统一（此前判重 strip、落库不 strip，Excel 带空格时判重失效并写入脏值）；资助学生导入去 N+1（1,000 行 413 ms → 10.4 ms）。Excel 缺学校编码的行改为跳过并回报行号，不再整批失败。
- **审批历史序列化下沉服务层**：避免模块级辅助函数被「裸 dict 返回」门禁误判，响应契约不变。

## 四、质量收口

- **类型检查**：启用 pydantic mypy 插件，全仓 mypy 错误从 851 条连续收敛到 **300 条以下**（运行期行为零变化，逐文件带说明）。
- **测试**：后端 15,291 例、前端 349 个测试文件、Electron 外壳用例；新增「核心链路闭环」端到端 8 例（认证网关 / 组织树 / 跨级挂接 / 自检 / 帮扶村生命周期 / 审计 / 导出）与多处覆盖率收口。
- **门禁**：本地 40 道门禁 + CI 9 个作业（backend-test 12 段独立进程、覆盖率 100% 门槛、frontend-check、lint、static-analysis、stack-alignment、security、e2e、windows-smoke、upgrade-rehearsal）。

## 五、产物与校验

| 平台 | 文件 | 大小 | SHA256 |
| --- | --- | --- | --- |
| Windows x64（NSIS 安装包） | `MRRS-Setup-1.18.31-x64.exe` | 283.5 MB | `62cb4eabc8a715e83d33dab20196e6739f6d1f06336115541200316243849f17` |
| 麒麟 / Linux ARM64（Electron deb） | `MRRS-Setup-1.18.31-arm64.deb` | 282.0 MB | `908b363313cd6e23e8f1f912402c27ea3fbef5f53127ea7e305282deb0e64024` |
| 麒麟 / Linux ARM64（自包含 deb，无 Electron） | `assistance-management-system_1.18.31_arm64.deb` | 105.0 MB | `c0bd1c028287fcbf29b2cdb6695951e3c8b7f0cfebfdb035884615f86abf0aa6` |

> v1.18.30 缺失的 ARM64 Electron deb（当时 `Prepare resources` 阶段误调 PyInstaller 校验而失败）本版已补齐，三个产物齐全。

下载安装包与对应的 `SHA256SUMS-*.txt` 到同一目录后执行：

```bash
sha256sum -c SHA256SUMS-*.txt
```

所有行必须为 `OK`；出现 `FAILED` 表示文件损坏或被篡改，请勿安装。

## 六、升级说明

- 直接覆盖安装即可，无需手工迁移：启动时自动执行 Alembic 迁移并自检（`/health` 的 `migration.at_head` 应为 `true`）。
- 已有 z13/z14 瓦片包可继续使用；如需全省概览，追加导入 `guizhou-overview_z5-8.zip`。
- 默认账号 `admin`，首次登录**强制修改密码**（出厂口令见部署文档）。
