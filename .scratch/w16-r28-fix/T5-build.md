# T5 构建/发布链 + 文档 PPT（写入范围：electron/**、build-scripts/**、.github/workflows/**、scripts/**、package.json、docs/**、README.md、CHANGELOG.md、*.pptx）
不得触碰：backend/**、frontend/**（package.json 与 frontend/package.json 是两个文件：根 package.json 你可以改，frontend/package.json 归他人，只报告）。

## 待修条目
- M49 electron/main.js:1016-1040 —— read-file-chunked 名为分块实为整文件驻留内存（chunks.join('')，base64 放大 1.33×）→ 改真正的游标/分块读取。
- M50 electron/worker-tasks.js:22-27 —— worker 路径白名单根目录用 LOCALAPPDATA+bumofu-assistance（与真实 userData 不一致）→ 加密/解密/哈希对真实数据一律 forbidden-path；hash-file 根本没调 validatePath → 路径校验上提到主进程 IPC 层，根目录由主进程注入。
- M51 electron/main.js:348-381（重置点 361-363）—— 后端“就绪即重置重启计数” → MAX_BACKEND_RESTARTS=3 形同虚设 → 改“稳定存活 N 秒才重置”。
- M52 electron/preload.js:9-68 —— 暴露约 20 个 IPC，前端实际仅消费 2 个（onNavigate/updateTrayUnread）→ 先 grep frontend/src 确认零消费，再删无调用方 IPC。
- M53 scripts/sync-version.js vs scripts/sync_version.py —— 两套工具两套目标集；复核 package-lock.json / frontend/.env.example 是否已纳入；统一单一工具/目标集。注意：node scripts/sync-version.js --check 当前 EXIT=0，别改坏。
- M54 .github/workflows/build-arm64.yml —— ARM64 deb 无打包卫生/产物校验（Windows 有 verify_package_no_tests 双层门禁）→ 平移同一校验（scripts/verify_package_no_tests.py / verify_deb_smoke.sh）。
- M55 package.json:41-46 vs 61-67 —— frontend/dist 同时打进 asar 与 resources（双份）；build-windows.yml:110-122 “Sync frontend to resources” 是死步骤 → files 移除 frontend/dist/**/*，删 sync 步骤（必须先用证据确认 electron 运行时只读 resources/frontend，改错会白屏）。
- M56 electron/main.js:636-648,1198-1201 —— will-navigate 无条件放行任意 file://；Linux root 下追加 --no-sandbox（与 sandbox:true 声明并存）→ file:// 白名单化；root 场景文档标注。
- H11 build-scripts/electron-builder-nsis-hook.nsh:159 + electron/main.js:60,157-163 —— 卸载“删除用户数据”目标目录错误（%LOCALAPPDATA%\bumofu-assistance vs 真实 app.getPath('userData')=%APPDATA%\<productName>）→ 数据库/uploads/secrets.json/logs 实际不删（敏感数据残留）。改钩子删除真实目录或 main.js 显式固定 userData；同步 build-scripts/README.md:75；三处口径（main.js:60、钩子:160、backend/app/utils/paths.py:6）必须一致 —— backend 文件归他人，只给补丁建议。
- H12 backend/assistance-backend.spec:45-49 —— _build_info.json 由 CI 生成但 spec datas 未收录 → 发布件指纹恒 dev。spec 在 backend/ 下属他人 scope：**只给出精确补丁（行号+片段）发给 lead**，不要直接改。

## 低危构建（§3）
- pr-checks.yml 全部作业无 timeout-minutes；nightly-full.yml 无 concurrency
- build-arm64.yml:84,110 用 npm install 而非 npm ci
- package.json:68 extraResources 无条件引用 Windows 专用且被 gitignore 的 resources/vcredist
- electron/main.js:5,947,160 死代码（execSync/checkVCRuntime 恒真/database 预置分支）
- package.json:134 deb depends 缺 libxtst6/libatspi2.0-0
- 只报告不改：frontend/package.json:6 description 双重编码乱码 + scripts/scan_mojibake.py 未接入任何 CI；backend/requirements.txt:4,41 无上界 >=

## 文档与 PPT
- 先修文档中已被本轮改动影响的部分（卸载目录口径、版本双工具说明、构建指南）。
- PPT：docs/帮扶管理信息系统介绍.pptx 与根目录同名文件 —— 用 python-pptx 盘点页数与版本口径；版本号统一到 v1.12.17（本轮发布版本，Lead 最终确认；若不确定先问 lead）。scripts/ppt_overflow_check.py 可做溢出检查。
- CHANGELOG.md 追加 v1.12.17 段落（先写你负责的条目，Lead 最后合并全量清单）。

## 验收
每条：改前行为 + 改后断言；electron 改动至少 node --check 通过；CI YAML 用 python -c yaml.safe_load 校验；不引入新 npm 依赖。