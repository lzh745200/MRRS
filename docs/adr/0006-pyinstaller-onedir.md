# ADR-0006: PyInstaller onedir 化（后端打包从 onefile 迁移到目录模式）

- 状态：已采纳（2026-08-30，W6-T6 实施）
- 关联工单：`.scratch/w6-release-eng/006-pyinstaller-onedir.md`
- 关联检测：M4（onefile 每次启动解压 %TEMP% → 首启超 3 分钟 + 杀软误报画像）、
  S1 关联（单一 85MB 自解压 exe 是杀软误报的典型画像）

## 背景

后端 `assistance-backend.spec` 原为 onefile 模式（EXE 内嵌全部二进制 +
`runtime_tmpdir=None`）。每次启动时引导器把 ~85MB 内容解压到随机
`%TEMP%/_MEIxxxx` 目录，带来：

1. **冷启动慢**：解压完成后 Python 才能开始初始化（实测见下）；
2. **杀软误报画像**：往 %TEMP% 释放可执行内容的单文件 exe 是典型恶意软件
   行为模式，军队场景白名单审批困难；
3. **打包冗余**：`datas` 打包整个 `app/` 源码目录与 `collect_submodules('app')`
   的字节码双份；hiddenimports 约 60 条手写项与 collect 重复，且含已删依赖
   （jieba/bs4/prometheus_client/aiosqlite）。

## 决策

1. **onedir 目录模式**：`EXE(exclude_binaries=True)` + `COLLECT(...)`，
   产物为 `backend/dist/assistance-backend/{assistance-backend.exe, _internal/}`。
   安装包内后端目录结构固定，白名单可按目录哈希清单审批。
2. **PyInstaller 6 的 onedir 同样设置 `sys._MEIPASS`**（指向 `_internal/`），
   代码中 `_MEIPASS` 相对定位（map.py、static_files.py、main.py 的 alembic.ini
   定位）无需改动；`backend/utils/paths.py` 本就按 `sys.frozen` 双模式防御。
3. **datas 摘除 `app/` 源码目录**：app 包经 `collect_submodules('app')` 进入
   PYZ 字节码；alembic `env.py` 的 `import app.models` 由冻结导入解析。
   `alembic/`（版本脚本按路径扫描）与 `alembic.ini` 必须保留为数据文件。
4. **hiddenimports 收敛**：仅保留「延迟导入/动态发现易漏」的第三方项
   （uvicorn 组件、passlib handlers、anyio backend、sqlalchemy 方言、
   reportlab 三件、sklearn 两件、pythonjsonlogger、numpy 多线程数组核心等）；
   删除已删依赖（aiosqlite/jieba/bs4/prometheus_client）与 54 条被
   `collect_submodules('app')` 覆盖的 `app.api.v1.*` 手写项。
   **prophet 保留条件化处理**：`trend_prediction_service`（被
   ai_enhanced/assessment 引用）函数级延迟导入 prophet，requirements 注释
   明确"安装困难时跳过、系统自动降级"——spec 按存在性条件收集其数据文件
   （数据文件无法被 Analysis 自动发现），不再放入 hiddenimports
   （工单原文"已删依赖 prophet"与现状不符，prophet 仍是活的可选依赖）。
5. **消费方适配**：
   - `package.json` extraResources：`backend/dist/assistance-backend`（目录）
     → `backend/assistance-backend`（目录）；
   - `electron/main.js getBackendExePath()`：优先 onedir 路径
     `resources/backend/assistance-backend/<exe>`，保留 onefile 旧布局回退
     （兼容开发期手工构建的单文件产物）；
   - `build-windows.yml` 产物验证步骤按目录结构校验；
   - `docker/Dockerfile.backend-arm64`（与 Windows 共用本 spec）：产物校验、
     GLIBC 检查（引导器 exe 代表性最高）、output stage 拷贝整目录；
   - `build-arm64.yml`：artifact 目录上传 + prepare 重建目录结构（含 exec 位
     恢复与结构守卫）+ postinst `find` 方式 chmod 兼容两种布局；
   - 麒麟 standalone（`backend_linux_arm64_standalone.spec`）本就是独立 spec
     且为 onedir，不受本次改动影响。

## 冷启动实测（2026-08-30，Windows x64，同机同测法）

从进程 spawn 到 `/health` 返回 200 的墙钟时间（含全部启动逻辑：
alembic 检查、种子数据、uvicorn 监听）：

| 打包模式 | 产物 | 冷启动到就绪 |
|----------|------|--------------|
| onefile（基线，v1.10.0 产物） | 85MB 单 exe | **32.3 s** |
| onedir（本次，v1.10.6 构建） | 37MB exe + 242MB `_internal/` | **8.6 s（约 3.8 倍提升）** |

> 基线 exe 为旧版本产物，版本间代码差异对结果影响远小于解压开销本身；
> 解压（~85MB → %TEMP%）是 onefile 模式的固有成本。

## 后果

- 正面：冷启动 ~3.8 倍提升；消除 %TEMP% 自解压（杀软误报画像显著减弱）；
  打包内容去重（app 源码目录不再双份；死依赖不再混入）；单一目录便于
  白名单按清单审批与增量更新。
- 代价：安装包内文件数增多（NSIS 压缩后体积相当）；所有消费方需感知目录
  布局（本次已全部适配并加结构守卫）；杀软仍可能对整个目录报警——彻底
  解决需代码签名（W6-T1，证书采购后接入）。
