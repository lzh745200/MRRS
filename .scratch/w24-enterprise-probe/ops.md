# W24 ops-probe 报告 — 构建 / 发布 / 运维 / 文档生产就绪

- 负责人：ops-probe（task-4）｜时间：2026-10-19
- 基线：HEAD=9de7aea（并行会话提交）＋工作区 v1.15.6 收口进行中；本报告不涉及版本号/CHANGELOG。
- 写入范围：scripts/、build-scripts/、docs/、.github/、deploy/、Makefile、Electron 构建配置。
- 未执行：git commit/push、全量 pytest/vitest、PyInstaller/electron-builder 完整构建、真实备份恢复。
- 取证：本机无 Docker、gh 未认证；CI 证据来自 GitHub 公开仓库匿名 API（check-runs/annotations；job logs 需 admin，403 不可读）。

## P0（本次必须修复，已全部落地）

### P0-1 PR Checks 后端测试「约 24 分钟进程消失」→ 6 段独立进程重设计
现象：PR Checks 最近 5 次 main 提交（v1.15.0~v1.15.4）全部 failure，唯一红点为 backend-test
的 Backend tests + coverage；其余 7 个 job 全 success。
证据（v1.15.4 HEAD 5a182cd，check run 117879054254）：该 step 03:44:57Z→04:09:09Z = 24m12s
后 failure；注解 10 条全为 pytest 进度行（tests/integration/xxx.py ... [ 8%]），无 FAILED、
无覆盖率汇总；仅剩 Process completed with exit code 1。与 v1.15.3/v1.15.4 注释记录的同签名一致。
根因：单进程长时间累积 TestClient/SQLAlchemy 会话与覆盖率数据，触达 runner 内存上限被杀；
被 OS 杀时不产生 FAILED 摘要，旧诊断步骤又把进度行当覆盖率缺口 → 真因被淹没。
修复：新增 scripts/ci_backend_test_segment.sh（独立进程、每段独立日志 $RUNNER_TEMP/pytest-seg-<name>.log、
--cov-append；first/partial/final 三种覆盖率模式；失败时输出真实 FAILED/ERROR，无摘要则输出日志尾部
并标注疑似被杀；附 free/dmesg/OOM 证据）。pr-checks.yml 拆 6 段顺序执行：
1) integration+security；2) unit/api；3) unit/services+middleware+interfaces+utils；
4) unit 根 test_{a,e,f,i,n,o,p,t,u,w,y,z}*.py（212）；5) test_{b,d,g,h,j,l,m,q,s}*.py（217）；
6) test_{c,r,v}*.py（211，--mode final）。前 5 段 --cov-fail-under=0，第 6 段不加该参数，
仍由 backend/.coveragerc fail_under=100 单一来源判定。
覆盖完整性：root 三段并集 212+217+211=640 == tests/unit 顶层 test_*.py 实际 640，无重复；
另有 api 17/services 6/middleware 2/interfaces 1/utils 1 由 seg2/seg3 目录递归覆盖 → 666 全覆盖。
验证（本机 Git bash 5.2.37 真实执行）：bash -n exit 0；first 段 76 passed；partial 段 45 passed；
final 段小样本 exit 1 且日志出现 Coverage failure: total of 24.45 is less than fail-under=100.00
（证明最终段确实触发全局门槛）；失败段（不存在目标）exit 1 并输出 ::error:: 含 pytest 错误尾部。
风险：串行 6 段预计 30~40 分钟（timeout 90 有余量）；若仍 OOM，新诊断会直接给出被杀段与日志尾部。

### P0-2 Report backend failure 把 pytest 进度行误报成覆盖率缺口
证据：旧实现 grep -E ".py " $LOG | grep -vE " 100%| 100.00%"，v1.15.4 的 11 条 failure
注解全部是进度行（单 step 错误注解上限约 10 条被占满），真实信号被淹没。
修复：逐段读 pytest-seg-*.log，优先 grep 真实信号（^(FAILED|ERROR) /INTERNALERROR/MemoryError/
worker crashed/Killed/Out of memory/Coverage failure/Required test coverage）；覆盖率缺口只匹配
最终段 ^(app/|TOTAL) 的 term-missing 行且排除 100%；flaky ledger 汇总全部段日志；pytest 日志 artifact
改为 pytest-seg-*.log。验证：pyyaml 解析通过；final 段样本含 Coverage failure 行可被新 grep 命中。

### P0-3 构建脚本裸 python 不可复现（PATH 指向已删除 32 位安装）
证据：cmd /c py --version → Unable to create process using ...Python311\python.exe；stderr
No Python at ...Python311-32\python.exe；where python 无结果。backend/.venv/Scripts/python.exe 可用
（Python 3.11.16）；根 .venv 的 pyvenv 已损坏。
修复：新增 scripts/find-python.bat（MRRS_PYTHON → backend\.venv\Scripts\python.exe → py -3.11 →
报错退出并打印修复指引，导出 PYTHON_EXE）；新增 scripts/run-python.js（Node 侧等价解析器，供 npm 脚本）；
cleanup.bat/dev-setup.bat 改用解析后的绝对路径；cleanup.py 计划任务不再写裸 pythonw（新增
_resolve_pythonw()）；build-installer-local.ps1 删除硬编码根路径改由 $PSScriptRoot 推导，并在
PyInstaller 前显式检查 backend\.venv\Scripts\python.exe；Makefile 平台化默认解释器、venv 用
BOOTSTRAP_PY（py -3.11 / python3.11）且缺失时显式报错、去掉裸 pip/uvicorn/pip-audit、修正
check_migrations 解释器路径、新增 make python-check。
验证：node scripts/run-python.js --print → ...\backend\.venv\Scripts\python.exe（exit 0）；
--version → Python 3.11.16；find-python.bat 成功路径 errorlevel 0、隔离目录模拟失败 exit 1 + 指引；
cleanup.py py_compile OK 且 _resolve_pythonw() 返回 pythonw 绝对路径；模拟 os.system 捕获到
schtasks /tr 内为 pythonw 与 cleanup.py 的绝对路径；ps1 无硬编码路径。
待 Lead 应用（package.json 属共享文件，未改）：第 16 行 build:backend 建议改为
cd backend && node ../scripts/run-python.js -m PyInstaller assistance-backend.spec --clean --noconfirm

### P0-4 start-all.bat 从未真正启动服务
证据：修复前脚本输出 [2/3] 启动后端服务 后仅 cd 到项目根，随后等待端口 60 秒，无任何启动命令；
而 README 声称会打开两个命令行窗口（后端和前端）。
修复：新增 scripts/run-backend.bat / run-frontend.bat（各自开窗、显式解析 Python/npm、
支持 MRRS_DRY_RUN=1 干跑）；start-all.bat 改为调用二者；stop-all.bat 加 chcp 65001 使窗口标题
清理规则与新标题（UTF-8）一致。验证：MRRS_DRY_RUN=1 跑两个 launcher 均打印正确命令且 exit 0；
echo 0 | scripts\cleanup.bat 的菜单/resolver 集成通过。

## P1（应修，本次已修）

### P1-1 Node20 弃用 actions → Node24 版本 + 保持 SHA pin（4 个 workflow）
影响：checkout@v4、setup-python@v5、upload-artifact@v4、download-artifact@v4、cache@v4、
softprops/action-gh-release@v2、codecov-action@v4、docker/setup-qemu@v3、setup-buildx@v3。
映射（raw action.yml 验证 runs.using=node24，git ls-remote 取 peeled commit SHA）：
- actions/checkout v5.1.0 = fbc6f3992d24b796d5a048ff273f7fcc4a7b6c09
- actions/setup-python v6.3.0 = ece7cb06caefa5fff74198d8649806c4678c61a1
- actions/upload-artifact v6.0.0 = b7c566a772e6b6bfb58ed0dc250532a479d7789f（v5 仍 node20）
- actions/download-artifact v7.0.0 = 37930b1c2abaa49bbe596cd826c3c89aef350131（v6 仍 node20）
- actions/cache v5.1.0 = caa296126883cff596d87d8935842f9db880ef25
- codecov/codecov-action v5.5.5 = 0fb7174895f61a3b6b78fc075e0cd60383518dac（composite，无 node）
- softprops/action-gh-release v3.0.3 = efb35369e0ad2afab669f228072c1b0d510eae64
- docker/setup-qemu-action v4.4.0 = 99012661954931238ded8c8b007157a8430204e1
- docker/setup-buildx-action v4.4.1 = f87e5991a6d7451dcb8d9637bfbc97413f497069
setup-node 原 pin a0853c24 即 v5.0.0（node24），未动。已核对各新版本关键输入存在
（name/path/retention-days/platforms/files/directory/flags/fail_ci_if_error），避免输入改名失败。
验证：4 个 workflow pyyaml 全部 OK；无旧 SHA 残留；所有 uses 均为 40 位 SHA（无浮动 tag）。

### P1-2 build-windows smoke-test timeout 与 release gate 轮询上限冲突
evidence：check_release_gate.py 默认 --timeout-minutes 75，而 smoke-test job timeout-minutes 为 30
→ tag commit 的 PR Checks 仍在跑时 job 会先被 timeout 杀掉，丢掉可读的 ::error::。
修复：smoke-test timeout 30 → 90（75 等待 + 依赖安装/冒烟约 10），注释写明原因。
另确认：build-windows 的 build-windows job 有 needs: smoke-test + if: success()，Release 步骤在其
内部 → 门禁红时不会产出 Windows 包（v1.15.4 smoke-test 失败属正确级联拦截，不是独立 bug）。

### P1-3 build-arm64 两个 job 缺失 timeout
build-frontend / build-electron-deb 均无 timeout-minutes（GitHub 默认 360），已补 30 / 60。

### P1-4 ARM64 standalone-deb 早期失败不可诊断（E）
现象：v1.15.4 standalone-deb 在 Build standalone Kylin DEB (retry, cache-first) 失败，注解仅
ARM64 standalone DEB 构建失败（已重试 3 次）。
分析：job 03:44:39Z→03:50:20Z = 5m41s（含 3 次尝试与 60+120s 退避）→ 每次 docker build 在 <1 分钟
内失败，不符合 pip/npm 编译型失败特征；镜像源探测成功（无探测失败 warning）说明 manifest 可读，
问题在真正构建阶段；高度怀疑 runner 迁移 Ubuntu 26（2026-10-19）后 arm64 binfmt/QEMU 未就绪。
修复（可观测性）：新增 Verify QEMU ARM64 emulation (fail fast)（docker buildx inspect --bootstrap
+ docker run --platform linux/arm64 ${BASE_REGISTRY}/busybox uname -m，失败输出含拉取错误尾部的
::error:: 并立即退出）；两次 buildx 构建每次尝试 tee 到 $RUNNER_TEMP/{kylin-build,backend-output}-
attempt-N.log 并加 --progress=plain，失败时把 error/failed/cannot/denied/no space/invalid/unsupported/
not found 行打成 ::error::，保留原 docker 诊断；新增 failure 时上传 build logs artifact（14 天）。
未验证/风险：本机无 Docker，GitHub job logs 需 admin（403）；本次是让下次失败可直接定位，不是盲改根因。

### P1-5 nightly 前端覆盖率内存悬崖（与 pr-checks 同源）
修复：nightly-full.yml frontend-full 的 Full test + coverage 增加 NODE_OPTIONS=--max-old-space-size=5632，
整门禁 2 次重试（15s 退避、清 coverage），失败上传 vitest-nightly.log artifact。pyyaml 验证通过。

## P2（建议，未改/仅记录）
1. build-arm64 两个 Release 步骤没有 release gate（Windows 侧有；ARM64 构建成功即发布，即使 PR Checks 红）。
2. build-windows/build-arm64 顶层 permissions: contents: write 被全部 job 继承，只读 job 可收窄。
3. codecov 无 token（公开仓库匿名可用；转私有需 CODECOV_TOKEN；当前 continue-on-error 非阻断）。
4. nightly backend-full 仍 -n auto（xdist），与「约 24 分钟进程被杀」同源风险；本次未改，建议观察后复用 6 段脚本。
5. cleanup.py 末尾 print 含 ✅，非 UTF-8 控制台（GBK）会 UnicodeEncodeError（任务已创建，仅打印崩溃）。
6. docs 历史报告类文档（R28/W18B/系统全面排查报告）仍引用已不存在脚本，按记录保留未改写。
7. docker/、nginx/ 配置未验证：本机无 docker，docker compose config 无法执行；建议 CI 或装 docker 机器补验。
8. action 大版本跳变（checkout v5/setup-python v6/upload-artifact v6/download-artifact v7/cache v5/
   softprops v3/docker setup-* v4）首次 CI 实跑是最终验证；回退只需恢复对应 SHA（见 P1-1 映射）。

## 范围外发现（需 Lead/对应负责人处理）
1. package.json:16 build:backend 仍为裸 python → 建议改为
   cd backend && node ../scripts/run-python.js -m PyInstaller assistance-backend.spec --clean --noconfirm
2. CLAUDE.md/AGENTS.md/项目文件结构说明.md 与 v1.15.4 实际不一致（根文档不在 write scope）：
   - CLAUDE.md 写后端 11244 用例（Lead 实测约 13550）；
   - 把 backend/scripts/check_*.py 写成 scripts/check_*.py；
   - 引用不存在的 build-scripts\build_windows_complete.bat 与 bash build-scripts/build-linux-arm64.sh
     （build-scripts/README 已声明该目录只有 2 个文件；入口是 scripts/build/build-installer-local.ps1 与
     make build-kylin-arm64）。
3. v1.15.6 版本号同步（package.json/CHANGELOG/README/.env.example/version.txt/backend/version.json/
   config.py/.gitignore）由并行会话改动，本报告未触碰，由 Lead 收口。

## 本次修改文件清单
新增：scripts/find-python.bat、scripts/run-python.js、scripts/run-backend.bat、scripts/run-frontend.bat、
scripts/ci_backend_test_segment.sh
修改：
- .github/workflows/pr-checks.yml（6 段 backend-test、Report 误报修复、action pin）
- .github/workflows/build-windows.yml（smoke-test timeout 90、action pin）
- .github/workflows/build-arm64.yml（timeout、QEMU 冒烟、build 日志与注解、action pin）
- .github/workflows/nightly-full.yml（前端内存/重试/日志 artifact、action pin）
- scripts/cleanup.bat、dev-setup.bat、start-all.bat、stop-all.bat
- scripts/cleanup.py（计划任务解释器绝对路径）
- scripts/build/build-installer-local.ps1（去硬编码根路径 + 显式 Python）
- scripts/README.md、Makefile
- docs/01-快速开始/启动指南.md（重写为当前真实入口）
- docs/04-部署文档/README.md（.deb 构建改为 make/docker 现行链路）
- docs/04-部署文档/02-Linux部署/麒麟V10离线部署完整方案.md（5 处已删除脚本 → make 目标）
- docs/03-开发文档/04-安全文档/安全加固.md（CORS/速率限制真实文件位置）
- docs/adr/0006-pyinstaller-onedir.md（paths.py 路径纠正）

## 自验命令与结果
- workflow：pyyaml safe_load × 4 → 4/4 OK（jobs 3/2/3/8）；action pin 断言全 40 位 SHA、无旧 SHA。
- 分段脚本：bash -n exit 0；Git bash 实跑 first/partial/final/失败 四场景（见 P0-1）。
- 覆盖完整性：glob 并集 640 == 实际 640，无重复；+子目录 26 → 666。
- Python 解析器：node run-python.js --print / --version；find-python.bat 成功与失败路径。
- Makefile：静态扫描确认 0 处裸 python/pip/uvicorn 调用（均为 $(PYTHON) -m 模块调用）。
- cleanup.py：py_compile OK；_resolve_pythonw() → pythonw 绝对路径；模拟 schtasks 命令无裸 python。
- ps1：grep 确认无硬编码路径、显式检查 venv python。
- docs：7 类旧路径扫描，现役文档 0 处（仅保留「历史脚本已删除」说明）。
- start-all 干跑：MRRS_DRY_RUN=1 跑 run-backend/run-frontend 均 exit 0。

## 遗留风险 / 未验证
1. 全量 pytest/vitest 未跑（按要求）；6 段方案真实 CI 耗时/稳定性需 Lead 推送后验证。
2. PyInstaller/electron-builder 完整构建未跑；package.json build:backend 修复需 Lead 应用后验证。
3. Docker 不可用 → compose/nginx/Dockerfile 构建链未实跑；ARM64 standalone-deb 根因待 CI 复跑注解确认。
4. action 大版本升级首次 CI 实跑为最终验证；不兼容时按 P1-1 映射回退 SHA。
5. 并行会话仍在改动工作区；若其覆盖 .github/workflows，以本报告 + git diff 复核。