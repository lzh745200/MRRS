# part-D — deliverables/ocr-findings-detail.md HIGH 段（第 1151–1462 行）逐条核实

- 核实方式：只读 read/grep 当前工作树；**未修改任何源码/测试/配置，未运行测试**。表中行号均为**当前代码**行号（finding 原始行号可能已漂移，已在证据中注明现位置）。
- 判定口径：**LIVE**=当前代码仍存在该缺陷；**FIXED**=已修复；**FALSE_POSITIVE**=finding 判断有误；**MOOT**=文件/端点已删除。
- 计数：共 88 条 → **LIVE 85、FIXED 2（#79 #84）、FALSE_POSITIVE 1（#18）、MOOT 0**。
- 表内 `|` 已转义为 `&#124;` 以免破坏表格。

| # | 文件:行 | 判定 | 证据（当前代码行号+关键片段，≤200字） | 建议修复（≤120字） |
| --- | --- | --- | --- | --- |
| 1 | backend/app/utils/input_validator.py:24 | LIVE | 24-29 SQL_INJECTION_PATTERNS 为裸词表+(--&#124;#&#124;/*&#124;*/)；validate_sql_safe(55-71) 无长度上限。grep 全仓仅 tests/unit/test_input_validator_utils.py 引用，生产无调用点，属死代码，实际风险 0。 | 删除两个未被调用的函数；若保留则只留 SQL 记号锚定规则并加长度上限 |
| 2 | backend/app/utils/input_validator.py:51 | LIVE | 51-52：先跑 XSS 黑名单再 text.replace("<","&lt;").replace(">","&gt;")，未转义 & 与引号，&lt;script&gt; 原样通过且二次调用双重转义。同样无生产调用点（仅测试）。 | 改用 html.escape(text, quote=True) 或删除死函数；至少先转义 & 再转义尖括号 |
| 3 | backend/app/utils/package_crypto.py:86 | LIVE | 86 struct.unpack(">I", raw[offset:offset+4])[0] 无上下界，经 63 行 decrypt_data→pbkdf2_hmac，伪造 0xFFFFFFFF 即 ~4.29e9 次迭代 DoS。次要论断不成立：iterations==0 的 ValueError 被 62-65 行 except 归一化为 InvalidToken。 | 派生前校验 1e4 ≤ iterations ≤ 1e7，超范围抛 InvalidToken |
| 4 | backend/app/utils/pagination.py:143 | LIVE | 143 getattr(last_item, col_key, None)；126 行注释自称兼容标量与 ORM。标量 select（items 为 int）或末值 NULL 时 has_more=True 而 next_cursor=None。当前唯一生产调用 funds.py:473 传 select(Fund) 实体，故为潜伏缺陷。 | 标量分支回退 getattr(last_item, col_key, last_item)，并断言 has_more 时游标非空 |
| 5 | backend/app/utils/runtime_secrets.py:58 | LIVE | 58-59 JSON 损坏仅 warning、loaded 保持 {}；79-87 落盘只写两个键，抹掉 get_or_create_secret 写入的 ENCRYPTION_FERNET_KEY。另 55 行 json.load(f) or {} 对 "abc" 真值非对象，65 行 loaded.get 抛 AttributeError。 | 解析失败时拒绝覆写并显式告警；校验 isinstance(loaded, dict) 后再用 |
| 6 | backend/app/utils/runtime_secrets.py:65 | LIVE | 34-45 的 ≥32 字符强度校验只作用于 os.environ；65-66 从 runtime_secrets.json 读回的两个键不校验即写入 os.environ(76-77)。风险低（文件由本应用 token_urlsafe(48) 写、0o600），但校验目标确实被绕过。 | 对文件来源的同名键复用同一长度校验，不达标则重新生成并告警 |
| 7 | backend/app/utils/upload_helper.py:81 | LIVE | 81-87 _IMAGE_MAGIC 仅 jpg/png/gif/bmp/webp，无 jpeg；386 ext in _IMAGE_MAGIC 对 .jpeg 跳过嗅探。files.py:98 enforce_image_magic=True，DEFAULT_ALLOWED_EXTENSIONS(74-77) 同时放行 jpg 与 jpeg。 | 补 "jpeg"/"jpe" 别名（或按 MIME 归并 jpg/jpeg 后再查表） |
| 8 | backend/app/utils/upload_helper.py:165 | LIVE | 165-170 IntegrityError 分支 return winner 未 ref_count += 1 也未 commit；调用方 399-403 复用 winner.path 并删掉本次副本 → 同一物理文件被两处引用却只计 1，delete_attachment_file(502-503) 会提前归零删文件。 | 并发命中分支同样 ref_count+1 并 safe_commit 后再返回 winner |
| 9 | backend/app/utils/win_proactor_fix.py:113 | LIVE | 113-121 _silent_close 只 sock.close()；原方法 finally 中若在 shutdown()/close() 抛出，其后 self._sock=None/_protocol=None/_loop=None/server._detach()/_server=None 全被跳过，transport 停在半拆解态（仍持有已关 socket 与活协议）。 | 在 _silent_close 内补全与原 finally 等价的拆解赋值（含 server._detach()） |
| 10 | frontend/scripts/patch-vitest-coverage.cjs:94 | LIVE | 94-101 仅凭 SITE3_PATCHED 短路；132-135 升级路径不处理 SITE2；149 先写盘再 155-172 校验（160 行 SITE2_ANCHOR 仍在即 fail exit 1）→ 文件含 SITE3+SITE2_ANCHOR，npm ci 重跑命中 94 行报“已打补丁”0 退出。package.json:19 每次 postinstall 都跑。 | 短路条件改为 SITE3_PATCHED 且 SITE2_PATCHED 同时存在，否则继续修复分支 |
| 11 | frontend/src/api/approval.ts:371 | LIVE | 368-375 直接 return response（只解一层），声明 {success:number[]; failed:number[]}；后端 approval.py:724-729 实为 success:true + data{total_pending,approved,failed:number}，与本文件 75-78 的 BatchApproveResult 不一致。 | 统一返回 BatchApproveResult 形状：从 response.data 取数组并做 Array.isArray 校验 |
| 12 | frontend/src/api/backup.ts:51 | LIVE | 51-53 del(`${BASE}/${filename}`) 未 encodeURIComponent；filename 含 / ? # 或被 ../ 构造时会被解析进路由。文件名一般由后端生成，风险有限但缺编码与校验。 | del(`${BASE}/${encodeURIComponent(filename)}`)，并在调用侧拒绝空/含分隔符的名称 |
| 13 | frontend/src/api/batchOperations.ts:38 | LIVE | 38-42 params:{table_name, ids}；后端 batch_operations.py:223-226 ids: List[int] = Query(...)（需 ids=1&ids=2）。全仓无全局 paramsSerializer，axios 默认发 ids[]=1 → 422；调用点 views/batch/Index.vue:246。 | 改用 indexes:null 序列化或把 ids 放进 POST body（后端改 Body 模型） |
| 14 | frontend/src/api/export.ts:46 | LIVE | 36-39 与 46-49 都请求 ${ASYNC_EXPORT_BASE}/tasks，逐字相同；后端 async_export.py 仅 reports/villages/status/download/tasks 五路由，无 history 端点；getExportTasks 全仓无调用方（仅 ReportExport.vue:489 用 getExportHistory）。 | 删除 getExportTasks，或改名为 getExportHistory 并注明同一端点 |
| 15 | frontend/src/api/helpers/blobDownload.ts:47 | LIVE | 47-74 与 request.ts:690-727 parseContentDisposition 同构（同正则、同 indexOf("''")、同 decodeURIComponent 与 quoted 回退），仅返回值语义不同；152 行已 import 并使用后者，downloadBlobAsFile(125) 却用本地副本。 | 删除本地副本，改由 parseContentDisposition 包装（保留 null 语义） |
| 16 | frontend/src/api/helpers/blobDownload.ts:118 | LIVE | 116-119 blob = result.data as Blob 无 instanceof/类型校验；responseType:'blob' 下错误 JSON 也会成为 Blob，204 空响应或非 Blob 环境则在 triggerDownload 的 URL.createObjectURL 抛 TypeError。 | 断言前做 result.data instanceof Blob 校验并核对 content-type，失败走 onError |
| 17 | frontend/src/api/organization.ts:9 | LIVE | 8-13 删除组织把 confirm_password 放在查询串（虽已 encodeURIComponent）；secrets.ts:55/64/82 也把 version_id/key_type/keep_days 拼进 URL。查询串会进历史/代理与访问日志，敏感值仍走 URL。 | 改为请求体或自定义头传递（del/post 需支持 body 配置） |
| 18 | frontend/src/api/permissionPack.ts:47 | FALSE_POSITIVE | 后端 permission_packs.py:113-127 返回 success_response(data=[...])；拦截器 request.ts:305-309 对数组载荷另设 items；47 行 res?.data 命中的正是数组，48 行 Array.isArray 通过并返回列表。finding 假设的 {data:{items,total}} 分页信封在该端点不存在。 | 无需修复；若后端未来改分页，再把 items 提到 data 之前判断 |
| 19 | frontend/src/api/request.ts:199 | LIVE | 194-202 GET 分支无条件 config.cancelToken = new axios.CancelToken(...)，覆盖调用方 token；createCancelableRequest(645-654) 与 requestWithTimeout(657-669) 依赖该 token，故 cancel() 变成空操作、超时不再中止请求。 | 仅当 config.cancelToken 缺失时安装去重 token，或把两个 token 链接起来 |
| 20 | frontend/src/api/secrets.ts:75 | LIVE | 75 post(`/secrets/revoke/${versionId}`) 未 encodeURIComponent、未做空值/格式校验；55/64/68 同样把 version_id/key_type 直接拼串。versionId 由后端生成，可利用性低但缺 fail-fast。 | 对路径段统一 encodeURIComponent，并在 id 为空/非字符串时提前抛错 |
| 21 | frontend/src/components/FilePreview.vue:63 | LIVE | 28 行仅 import computed/ref/watch（无 onBeforeUnmount）；59-88 watch 内 await props.fetchBlob() 无请求令牌，组件卸载后仍会执行 76 行 URL.createObjectURL；release()(90-102) 只由 handleClose 调用 → 卸载/快速切换时 blob URL 泄漏。 | 加请求令牌（丢弃过期响应）并在 onBeforeUnmount(release) |
| 22 | frontend/src/components/FilePreview.vue:59 | LIVE | 63-64 只重置 loading/unsupported，objectUrl/blobRef 未清；67 行空 blob 早退与 80 行 catch 都保留上一文件的预览与下载内容，用户会看到/下载到上一个文件。 | 进入 watch 时先调用 release()，清空 objectUrl 与 blobRef 再加载 |
| 23 | frontend/src/components/MapPicker.vue:122 | LIVE | 122-126 onInputChange 原样 emit innerLng/innerLat；模板 7/17 行 v-model.number 对组件无效（ElInput 不消费 modelModifiers），清空得 ''、非数字得字符串，却按 number 类型外发，父组件拿到脏坐标。 | emit 前做 Number.isFinite 与经纬度范围校验，非法值不外发并提示 |
| 24 | frontend/src/components/MapPicker.vue:85 | LIVE | 85-93 modelValue 监视仅 if (val) 才写入，父组件重置为 null/undefined 时 innerLng/innerLat 保留旧值；94-105 的 latitude/longitude 监视同样只在非 null 时写，且原地改 props.modelValue.lng 不触发。 | 监视中处理 null/空值分支并清空内部坐标，或改为 deep 监视 |
| 25 | frontend/src/components/business/SystemStatus.vue:225 | LIVE | 225-233 onMounted 内 await refresh() 之后才 setInterval；235-240 onUnmounted 只清当时非 null 的 pollTimer。await 期间卸载 → 定时器在销毁后创建且永不清理，持续轮询并更新已卸载组件。 | 用 isUnmounted 标志在 await 后判空再建定时器，或改为 onMounted 内同步建表 |
| 26 | frontend/src/components/common/BaseChart.vue:53 | LIVE | 49-57 { deep: true } 深监听整个 option 树，53 行 setOption(newOption, true) notMerge 全量替换，会重置 dataZoom 位置/legend 选择等用户状态；数据刷新后视图跳回。 | 改为 setOption(newOption)（可加 lazyUpdate），或去掉 deep 只监听 option 身份 |
| 27 | frontend/src/components/common/BaseChart.vue:63 | LIVE | 59-67 resize 监听在 onMounted 的 nextTick 回调里注册；69-72 卸载时按“卸载那一刻的 props.autoResize”决定是否移除。tick 前卸载则监听挂在已销毁组件上；autoResize 中途变化则附加/移除不对称而泄漏。 | 用 isUnmounted 守卫回调，并无条件 removeEventListener |
| 28 | frontend/src/components/common/ChangeHistoryDialog.vue:45 | LIVE | 45-49 if (typeof v === 'object') return JSON.stringify(v) 无 try/catch；循环引用或 BigInt 抛 TypeError，模板渲染期直接中断整个对话框。 | JSON.stringify 包 try/catch，失败回退 String(v) 或占位符 |
| 29 | frontend/src/components/common/StatsCard.vue:37 | LIVE | 37-40 仅 string 走兜底，其余 props.value.toLocaleString()，无 Number.isFinite；调用方 Analysis.vue:118 {...stats.value, ...data} 合并 any 载荷，null/undefined 抛 TypeError、NaN 显示 NaN；也未固定 locale（同页 74 行用 zh-CN）。 | 用 Number.isFinite 守卫并对数字固定 toLocaleString('zh-CN') |
| 30 | frontend/src/components/dataPackage/ExportDialog.vue:92 | LIVE | 90 行已提示“正在下载文件...”，92-97 的 catch 为空注释（“下载失败不阻塞”），downloadPackage 失败（401/网络/URL 过期）时用户只看到成功提示、对话框关闭且无文件、无日志。 | catch 内 ElMessage.warning 提示可从列表手动下载，并 logger.error 记录原因 |
| 31 | frontend/src/components/dataPackage/ImportDialog.vue:60 | LIVE | 1-9 的 el-dialog 无 destroy-on-close；45 行只 import ref（无 watch）；59-60 的 fileList/selectedFile 仅在导入成功(82-83)或 on-remove(66-69)时清空 → 取消后重开仍带旧文件，“导入”按钮直接可用，易重复导入。 | 增加 watch(() => props.modelValue, v => { if (!v) { selectedFile=null; fileList=[] } }) |
| 32 | frontend/src/components/dataPackage/ImportEncryptedDialog.vue:114 | LIVE | 111-117 只 POST /data-packages/upload-encrypted；后端 data_packages.py:1321-1398 仅落盘建 pending 记录，password 完全未用；真正导入需 decrypt-preview(1423)/confirm-import(1455)，前端零调用 → 数据从未导入却提示“导入成功”。 | 串联 decrypt-preview + confirm-import（用返回的 result.id），或改文案为“仅上传/待解密” |
| 33 | frontend/src/components/funds/YearlyComparisonChart.vue:35 | LIVE | 35 行发送 department；后端 funds.py:1070-1076 只声明 year_start/year_end，FastAPI 静默忽略未知查询参数 → 图表始终未按部门过滤；73 行 watch department 只触发一次结果相同的重载。 | 后端补 department 过滤，或前端改用支持该维度的统计接口/去掉该 prop |
| 34 | frontend/src/components/map/OfflineMap.vue:85 | LIVE | 72-87 onMounted 内 await import 后才 initChart；329-333 onUnmounted 只 removeEventListener+dispose。import 期间卸载时 initChart 仍执行 92 行 echarts.init 与 126 行挂 resize，chart 在置 null 后又被赋值，永不 dispose。 | 加 isUnmounted 标志：onUnmounted 置 true，initChart 入口与 await 后各判断一次 |
| 35 | frontend/src/components/permission/MenuVisibilityPanel.vue:128 | LIVE | 127-129 selectedMenuKeys.value = checked?.checkedKeys &#124;&#124; checked 丢弃 halfCheckedKeys；模板 38 行 check-strictly="false" 下子项未全选的父节点保持半选、键不入列，保存后父菜单缺失可致子菜单不可达。 | 合并 checkedKeys 与 halfCheckedKeys（祖先键）后保存，malformed 载荷兜底 [] |
| 36 | frontend/src/components/permission/PermissionAssignmentDrawer.vue:170 | LIVE | 167-194 loadCurrentPermissions/loadMenuConfig/loadAllRoles 均无取消或用户身份校验，直接写 currentPermissions/currentMenuKeys；275-289 watch(props.user) 顺序触发；216 行保存用当时的 props.user.id → A 的慢响应可覆盖 B，甚至把 A 的权限写到 B。 | 捕获请求时的 user id，响应回来比对 props.user?.id 不一致即丢弃 |
| 37 | frontend/src/components/permission/RoleTagsPanel.vue:89 | LIVE | 87-93 catch 一视同仁 assignedRoles.value = []，403/网络/5xx 与“无角色”不可区分；90 行 (res.data &#124;&#124; res &#124;&#124; []) as RbacRole[] 不校验数组，载荷为非数组对象时 83 行 .map 会在渲染期抛错。 | catch 中区分失败并提示（保留旧值），赋值前用 Array.isArray 校验 |
| 38 | frontend/src/components/permission/RoleTagsPanel.vue:18 | LIVE | 11-19 每个 tag 都 closable 且 @close="removeRole(role)" 直接发撤销请求，无 ElMessageBox 确认；is_system 角色（15/24 行有标识）同样一击即移除。 | 撤销前加二次确认，is_system 角色再要求额外确认或隐藏关闭按钮 |
| 39 | frontend/src/composables/useAutoLock.ts:38 | LIVE | 37-43 try { AuthStorage.clearSession(); sessionStorage.setItem('auto_lock_active','1'); markLockNow() } catch { /* 静默 */ } —— 全静默无 log。历史 require() 问题已修（34-36 注释），但失败仍完全不可观测。 | catch 内 logger.error('[useAutoLock] 锁屏失败', e)（或上报） |
| 40 | frontend/src/composables/useBackupSchedule.ts:36 | LIVE | 32-38 直接对字段 padStart：*/5 2 * * * → backupTime '02:*/5'；0 2 * * 1,3,5 只判 dow!=='*' → weekly 且丢失具体星期。 | 逐字段校验为数字（非数字回退默认并标注不支持），保留 dom/dow 原值 |
| 41 | frontend/src/composables/useBackupSchedule.ts:46 | LIVE | 46-51 未校验 backupTime：'25:99' → '99 25 * * *'，'abc:xyz' → 'xyz abc * * *'，经 87-91 行原样 PUT 给后端存储，调度器拿到非法 cron 无提示。 | saveSchedule 前校验小时 0-23、分钟 0-59，非法则中止并提示 |
| 42 | frontend/src/composables/useBackupSchedule.ts:49 | LIVE | 49-50 硬编码 '* * 1' / '1 * *'：后端 0 2 * * 3 或 0 2 15 * * 经 parseCron 显示为 weekly/monthly，下一次保存即改写为周一/1 号，静默改用户计划。 | 在配置模型中保留 dom/dow 原值并回写，或与规范形式不符时禁止保存 |
| 43 | frontend/src/composables/useEventBus.ts:6 | LIVE | 6 行模块级 const eventHandlers = new Map()；8-25 只暴露 on/off/emit，无 clear()/dispose；组件漏调 off 时回调被永久引用（stale 执行+Map 无界增长）。 | 增加 clear(event?) 并暴露 dispose；或提供随组件生命周期自动 off 的封装 |
| 44 | frontend/src/composables/useEventBus.ts:21 | LIVE | 21 forEach((handler) => handler(...args)) 无逐处理器 try/catch：任一订阅者抛错即中断迭代（Map.forEach 语义），其余订阅者被静默跳过且错误冒泡到 emit 调用方。 | 逐个 handler 包 try/catch 并 logger.error 上报，保证互不影响 |
| 45 | frontend/src/composables/useKeyboardShortcuts.ts:83 | LIVE | 87 行 e.key.length===1 ? e.key.toUpperCase() : e.key 与 44 行 formatShortcut 重复实现；按住 Shift 时数字键 e.key 为 '!'，注册 {key:'1',shift:true}（'Shift+1'）永不匹配；84 行还把 metaKey 并入 Ctrl 而 Shortcut 无 meta 字段。 | 抽取唯一组合串构造函数供两处共用，Shift 场景归一化（或改用 e.code） |
| 46 | frontend/src/composables/useRouterSafe.ts:46 | LIVE | 43-50 router.resolve 判定 NotFound/matched.length===0 时 window.location.href = pathString，内部未知路由整页重载重启 SPA（再落到 NotFound），丢弃内存态且每次调用都重复。 | 内部路径改 router.push({name:'NotFound'})，仅外部 URL 才用原生跳转 |
| 47 | frontend/src/composables/useRouterSafe.ts:59 | LIVE | 59-64 router.push(path)?.catch(err => { ...window.location.href = pathString })：vue-router 4 对 aborted/cancelled 也 reject（NavigationFailure），此处一律整页重载，绕过守卫决定；可选链多余、返回值未 await。 | 仅在 chunk/动态导入类真实失败时回退原生跳转，NavigationFailure 记日志忽略 |
| 48 | frontend/src/composables/useUploadHeaders.ts:14 | LIVE | 14-18 ensureCsrf 只 getCsrfToken().then(...) 不 return，await ensureCsrf() 立即 resolve；ContractManage.vue:391、policies/Edit.vue:368 在 before-upload 中 await 它 → 上传可能带空 X-CSRF-Token 得 403。 | ensureCsrf 改为 return getCsrfToken().then(t => { if (t) csrfToken.value = t }) |
| 49 | frontend/src/composables/useVersionCheck.ts:54 | LIVE | 54 行先 localStorage.setItem(VERSION_KEY, serverVersion)，59-62 才延迟 reload；若 reload 被拦或浏览器仍给旧包，下次比对相等 → 永久停留旧代码且再无法检测。 | 改用 sessionStorage 一次性标记，或 reload 成功后再落版本 |
| 50 | frontend/src/composables/useVersionCheck.ts:61 | LIVE | 61 window.location.reload() 不绕 HTTP 缓存（注释却写“绕过浏览器缓存”），HTML/旧 JS 可再次命中缓存 → 同一不匹配反复触发刷新，缺少“每次检测至多自动刷新一次”的护栏。 | 用 location.replace(url+'?v='+ver) 破缓存，并加 sessionStorage 单次护栏 |
| 51 | frontend/src/config/regionDictionary.ts:92 | LIVE | 92 _city/_county 完全未用，95-105 对所有区域标志恒返回 false，注释却称“兼容旧版三参数调用”；调用点 ComprehensiveEntry.vue:945 传入 city/county 并把 attrs 回写表单(946-950)，每次选完省市区即把标志清零。 | 实现真实的市/县判定，或删掉未用参数并让调用方自行维护标志 |
| 52 | frontend/src/directives/permission.ts:40 | LIVE | mounted 用 el.parentNode.removeChild(el) 永久摘除（34/43/53 行三种模式皆是）；updated 只切 style.display（91/102/113）→ 元素一旦移除无法恢复，且手动删 Vue 管理的节点会在后续 patch 引发错乱。 | 两个钩子统一用 style.display 切换（外加 v-if 或后端鉴权做真正屏障） |
| 53 | frontend/src/directives/permission.ts:135 | LIVE | 135-139 仅处理 level==='view' 与 'edit'，无 else：拼错/未传 level 时两个分支都不进，元素保持可见可点（授权工具 fail-open）；文档第 15 行承诺 edit 会“隐藏/禁用”，实现只隐藏。 | 补 else 分支 fail-closed 隐藏并在 DEV 告警；或落实禁用语义并同步注释 |
| 54 | frontend/src/directives/watermark.ts:56 | LIVE | 55-64 只有 mounted/updated，无 unmounted/beforeUnmount；createWatermark 在 39 行 append 的 .watermark-layer 直接在 Vue 管理的元素内，宿主销毁后不清理，重挂载会重复叠加。 | 加 unmounted 钩子移除 .watermark-layer（并恢复 el.style.position） |
| 55 | frontend/src/layouts/DefaultLayoutSafe.vue:501 | LIVE | 501-506 在 onMounted 回调里注册 onBeforeUnmount(() => clearInterval(timer)) —— 此时无活动实例，钩子不生效（dev 警告），60s 轮询在布局销毁后继续调用 loadUnreadCount。对比 538 行顶层 onUnmounted 是正确的。 | 把 timer 提到 setup 作用域，在顶层注册 onBeforeUnmount/onUnmounted 清理 |
| 56 | frontend/src/layouts/DefaultLayoutSafe.vue:546 | LIVE | 546-556 自定义 onLock 只做 lockSession + 跳 /login，未调 markLockNow()（useAutoLock.ts:40 默认实现才调）；lockDigest.ts:25 if (!last) return false → 487 行 consumeLockDigest 恒 false，“欢迎回来”摘要永不触发。 | 跳转前调用 markLockNow()（与 consumeLockDigest 一同 import） |
| 57 | frontend/src/layouts/DefaultLayoutSafe.vue:94 | LIVE | 94-113 子菜单仅由父级 funds-admin &#124;&#124; funds-user 门控，103-112 各子项无 v-if；router/index.ts:226/232/238/256/272 等路由无 meta.menuKey，guards.ts:66 不做菜单校验，直接输 URL 可进入。 | 子项补 v-if="menuStore.canAccessMenu(...)"，并给这些路由补 meta.menuKey |
| 58 | frontend/src/main.ts:41 | LIVE | 41 行模块顶层 localStorage.getItem(THEME_STORAGE_KEY) 无 try/catch，受限存储下抛 SecurityError 会中断入口模块（白屏）；且未校验 THEME_OPTIONS，config.ts:30-36 直接 setAttribute('data-theme', 任意值) → 非法主题无 token。 | 包 try/catch 并把取值与 THEME_OPTIONS 白名单比对，非法回退 DEFAULT_THEME |
| 59 | frontend/src/main.ts:44 | LIVE | 44 行 AuthStorage.migrateFromLocalStorage() 无错误守卫，方法内部（authStorage.ts:218-258）直接读写 sessionStorage/localStorage 且无 try/catch，任一抛错（受限存储/配额）会中断入口模块，用户白屏而非降级到重新登录。 | 用 try/catch 包裹迁移调用，失败仅告警并继续挂载应用 |
| 60 | frontend/src/router/guards.ts:27 | LIVE | 26-39 只在白名单分支读 sessionStorage.auto_lock_active；42 行之后非白名单路由仅校验 token。锁屏后 AuthStorage.getToken()（authStorage.ts:67-73）仍回退 PERSIST_TOKEN，故直接访问 /dashboard（地址栏/书签/后退）无需重新输密码。 | token 存在时对所有路由统一校验锁屏标记，命中即重定向 /login?redirect= |
| 61 | frontend/src/stores/dataReport.ts:61 | LIVE | 62-98 previewReport/receiveReport/rejectReport/downloadReport（及 submitReport）均无 try/catch，失败直接 reject 出 action、不写 error；与 25-38/41-59 两个 fetch* 的处理标准不一致。 | 统一包 try/catch 将 message 写入 error 并重置 loading，再按需 rethrow |
| 62 | frontend/src/stores/funds.ts:57 | LIVE | 56-60 删除后 fundList.filter(...) 再 total.value--；total 是服务端分页总数（36 行 unwrapList(res).total），非标志位 —— 可被减成负数，删的 id 不在当前页时计数错误，且不补位造成列表与总数偏离。 | 仅当记录确实在 fundList 中命中时才递减，或直接 await fetchFunds() 重取 |
| 63 | frontend/src/stores/organization.ts:70 | LIVE | 70-77 del('/organizations/'+id) 不带 confirm_password；后端 organization.py:702 Query("")、729-730 空值即 400“二次确认失败”，该 action 永远失败（视图改用 api/organization.ts:8-13 带密码 URL，故无调用方）。 | 给 action 增加 confirmPassword 参数并透传（或删除该死代码） |
| 64 | frontend/src/stores/policy.ts:26 | LIVE | 26-27 catch { /* silent */ }；39-40 fetchPolicy 同样。请求层不再弹全局提示而依赖 error.userMessage/调用方，此处吞掉后页面与全局兜底都无提示，列表永久空/旧且无解释。 | catch 内 logger.error 并 rethrow（或把 err.userMessage 写入 store error） |
| 65 | frontend/src/stores/policy.ts:46 | LIVE | 46-71 createPolicy/updatePolicy/deletePolicy 无 try/catch，网络或服务端失败产生未处理拒绝，store 不产出任何用户提示。 | 与读操作对齐：try/catch 并暴露 error（含 err.userMessage） |
| 66 | frontend/src/stores/user.ts:62 | LIVE | 55-65 fetchUser(id) 只要拿到对象就 currentUser.value = userData（63 行），与请求的 id 无关；currentUser 是会话档案（24 行从 AuthStorage 恢复，124 行 changePassword 用 currentUser.value.id）。管理员查看他人即覆盖本人档案。 | 仅当 id 与当前登录用户一致时才写 currentUser，否则缓存到局部状态 |
| 67 | frontend/src/styles/accessibility.css:69 | LIVE | 69-70 写 --el-color-text-primary/regular；Element Plus 实为 --el-text-color-*，index.scss:146 也定义后者且 table.scss:147 等按后者消费 → 两条高对比声明被静默丢弃；--el-bg-color 也不覆盖自家 --color-bg-*。 | 改用 --el-text-color-primary/regular，并补高对比主题下的 --color-text-* 映射 |
| 68 | frontend/src/styles/components/form-page.scss:78 | LIVE | 78 color: var(--color-bg-card)（同 93/97/98），tokens-vars.scss:121 $text-white: var(--color-bg-card)；dark 主题下 --color-bg-card 为深色而标题栏底仍是 --color-primary-dark-1 → 暗底暗字。 | 文字改用 --color-text-inverse（或显式 #fff），仅背景用 --color-bg-card |
| 69 | frontend/src/styles/components/prompt.scss:162 | LIVE | 131 行 .el-notification 块内 162-165 .el-notification__title 与 68-106 行 .el-notification--success .el-notification__title 权重同为 (0,2,0) 且更靠后 → 类型色 inherit 必被覆盖。 | 把类型色规则移到 .el-notification 块之后或提高权重，并删除交叉组合选择器 |
| 70 | frontend/src/styles/dashboard-theme.scss:604 | LIVE | [data-theme="dark"] .dashboard-modern 内：605 背景用 #e5eaf3 的 --color-text-primary，606 文字用 --color-border-dark(#94a3b8)；587/596 还把 --color-border-dark/--color-border-lighter(#363637) 当文字色 → 低对比/暗底暗字。 | 文字用 --color-text-primary/--color-text-regular，背景用 --dash-bg-card 等表面令牌 |
| 71 | frontend/src/styles/print.scss:83 | LIVE | 83-95 为 th/td 设 background: var(--color-bg-card) 与 th 的 background:#f0f0f0，但全仓 grep 无 print-color-adjust/color-adjust → 浏览器默认 economy 会剥离底色并把文字强制黑色，表头灰底丢失、可读性下降。 | 在 html/body 或打印根节点加 print-color-adjust: exact（含 -webkit- 前缀） |
| 72 | frontend/src/styles/print.scss:58 | LIVE | 58-68 .print-footer{position:fixed;bottom:0} 位于 @media print 内，而 28-35 行 body 为 padding:0、无页脚占位；41 行的 padding-bottom 属于 .print-header。长报表最后几行会被页脚覆盖（分页行为各浏览器还不一致）。 | 给 body/打印容器预留 padding-bottom（≥页脚高）或把页脚移入 @page 边距盒 |
| 73 | frontend/src/styles/responsive.scss:43 | LIVE | 41-51 max-width：命名断点走 map.get($breakpoints,$breakpoint) - 1px，xs=0 → 输出 max-width:-1px 永不匹配（静默丢样式）；else 分支(47 行)原始像素不减 1，故 max-width(768px) 与 min-width(768px) 在 768px 同时命中。 | 对数值统一 - 1px 并 clamp 到 ≥0，命名 xs 特判为不产出或 0 |
| 74 | frontend/src/styles/theme-elevated.scss:371 | LIVE | 337-340 动画作用于 #main-content > *:not(.error-boundary-root) 与 .error-boundary-root > *；371-375 减弱块只写 #main-content > *（即被排除的 boundary 根）与 .stats-row > * → reduce 用户仍有 0.28s 路由淡入。 | 减弱块补 #main-content > .error-boundary-root > *（或去掉上方的 :not） |
| 75 | frontend/src/types/analytics.ts:26 | LIVE | SupportedVillage 26-35 的 7 个区域/示范标志（isThreeRegions、isBorderArea…isHundredVillageDemo）为 boolean；SupportedVillageCreate 74-81 同名字段为 number 或 undefined，Update 继承之。 | 选定一种表示（建议统一 boolean 并在 API 层映射 0/1）并同步两个接口 |
| 76 | frontend/src/utils/approvalTimeline.ts:22 | LIVE | 22 [...a,...b].sort((x,y)=>String(y.time).localeCompare(String(x.time))) 假定时间串同格式零填充；混合 ISO/空格格式/epoch 秒或毫秒会乱序，空 time 沉底，localeCompare 还受语言环境影响。 | 解析为数值时间戳（区分秒/毫秒、处理非法值）后比较，并按复合键去重 |
| 77 | frontend/src/utils/authStorage.ts:68 | LIVE | getToken(67-73)=session→PERSIST_TOKEN→legacy local；getUser(85-103)=session→PERSIST_USER；getRefreshToken(117-122)=session→PERSIST_REFRESH。三条回退链可拼出不同来源组合；clearSession(183-187) 只清 session。 | 以一份整体凭据（先 session 三元组、否则 persist 三元组）为唯一来源读写 |
| 78 | frontend/src/utils/clipboard.ts:36 | LIVE | 37 document.execCommand('copy') 返回值被丢弃，随后 39 行必报“已复制到剪贴板”；38 行 textArea.remove() 不在 finally，focus/select/execCommand 抛错时临时 textarea 残留在 DOM。 | 检查 execCommand 布尔结果并在失败时提示，textarea 移除放入 finally |
| 79 | frontend/src/utils/desensitize.ts:36 | FIXED | 已修：maskPhone 38-41、maskIdCard 48-50、maskBankCard 66-68 均加 fail-closed —— 正则未命中（+86、分隔符、尾位 X、带空格卡号）时改为 replace(/\d/g,'*') 全掩，注释亦点明原“原样返回”泄露问题。 | 无需修复 |
| 80 | frontend/src/utils/desensitize.ts:86 | LIVE | 现位于 95-98 maskMilitaryID：4 字符 id 时 slice(0,2)+'****'+slice(-2) 覆盖全部字符，输出 '12****34'，凭证每位仍可见（长度门槛只有 <4 返回原值）。 | 要求最小长度保证中段被隐藏，或对过短凭证直接固定全掩（****） |
| 81 | frontend/src/utils/echarts-theme.ts:358 | LIVE | 358-427 仅覆盖 textStyle/title/categoryAxis/valueAxis/legend/tooltip，浅色值仍在：dataZoom.dataBackground #cbd5e1(340-351)、pie.borderColor '#ffffff'(221)、logAxis/timeAxis(274/292)、toolbox.iconStyle(306)。 | 在暗色变体中显式覆盖 logAxis/timeAxis/pie/dataZoom（含 toolbox） |
| 82 | frontend/src/utils/echarts.ts:3 | LIVE | 3 行 import 与 15-30 注册列表均无 LinesChart/EffectScatterChart/VisualMapComponent/MarkLineComponent；实际使用 OfflineMap.vue:242 type:'lines'、:272 effectScatter、:182 visualMap，gantt.ts:78 markLine → 运行时静默丢弃。 | 在 import 与 echarts.use([...]) 中补齐四者（按需引入控制体积） |
| 83 | frontend/src/utils/errorHandler.ts:221 | LIVE | 221 handleError(error, showMessage: boolean 或 string='操作失败')；247 只判真值忽略字符串文案；250 type 硬编码 'error'、255 用 warning，severity(48) 从不读取；shouldRedirect(45)/redirectPath(49) 在 defaultStrategies 配置却无消费点。 | 实现字符串文案、severity 与 shouldRedirect/redirectPath，或删除这些死配置 |
| 84 | frontend/src/utils/exportUtil.ts:10 | FIXED | 已修：9-21 escapeCSVField 现含 if (typeof val === 'string' && /^[=+\-@\t\r]/.test(str)) str = "'" + str，注释标明 OWASP 公式注入，数字/布尔保持原样不破坏数值语义，再由 17-19 行做 RFC4180 引号转义。 | 无需修复 |
| 85 | frontend/src/utils/gantt.ts:15 | LIVE | 13-17 new Date(s.replace(/-/g, '/')) 对所有 '-' 生效：'2026-09-17T10:00:00Z' → '2026/09/17T10:00:00Z'（Z 被当本地时间），'…-05:00' → '…/05:00' 解析为 NaN，脏值进入 hasRange 与条形偏移。 | 仅当字符串严格匹配 ^\d{4}-\d{2}-\d{2}$ 时才替换为 '/'，其余原样交给 Date |
| 86 | frontend/src/utils/index.ts:16 | LIVE | 15-17 formatDateTime：date 为 null/undefined 时走 d.getTime() 抛 TypeError，非法日期字符串返回原串（兄弟函数 30/38/44 行都有 if(!date) return '-' 守卫）；49-50 formatCurrency 同样无 null 守卫且未判 Number.isFinite，NaN 直接渲染 'NaN'。 | 两个函数补 null/undefined 与 Number.isFinite 守卫，非法值返回 '-' |
| 87 | frontend/src/utils/roleAccess.ts:58 | LIVE | 58 isAdminUser 用原始 role 比对 ADMIN_ROLES，未 normalizeRole；85-90 hasAllowedRole 以归一化角色比对原始白名单；103 minRole 未归一化且回退 super_admin；121-134 返回原始 role、默认 'viewer'，与 35 行默认 'user' 不一致。 | 四处统一先 normalizeRole，白名单/minRole/默认值对齐同一常量源 |
| 88 | frontend/src/utils/treeNormalizer.ts:49 | LIVE | 49 /^[0-9]/.test(raw) ? `_${raw}` : raw：数字 id 0/1 变 '_0'/'_1'；唯一消费点 UserManagement.vue:535-543 喂给 el-tree-select，239 行 value:'id' 取值后经 840/853 作为 organization_id 提交 → 后端收到 '_1'。 | 保留原始 id 供 API 使用（另存 rawId 或仅 DOM id 加前缀），提交前还原数字 |

## 附：LIVE 清单（按明细顺序，85 条）

- `backend/app/utils/input_validator.py:24` — 24-29 SQL_INJECTION_PATTERNS 为裸词表+(--|#|/*|*/)
- `backend/app/utils/input_validator.py:51` — 51-52：先跑 XSS 黑名单再 text.replace("<","&lt;").replace(">","&gt;
- `backend/app/utils/package_crypto.py:86` — 86 struct.unpack(">I", raw[offset:offset+4])[0] 无上下界，经 63 行 
- `backend/app/utils/pagination.py:143` — 143 getattr(last_item, col_key, None)
- `backend/app/utils/runtime_secrets.py:58` — 58-59 JSON 损坏仅 warning、loaded 保持 {}
- `backend/app/utils/runtime_secrets.py:65` — 34-45 的 ≥32 字符强度校验只作用于 os.environ
- `backend/app/utils/upload_helper.py:81` — 81-87 _IMAGE_MAGIC 仅 jpg/png/gif/bmp/webp，无 jpeg
- `backend/app/utils/upload_helper.py:165` — 165-170 IntegrityError 分支 return winner 未 ref_count += 1 也未 
- `backend/app/utils/win_proactor_fix.py:113` — 113-121 _silent_close 只 sock.close()
- `frontend/scripts/patch-vitest-coverage.cjs:94` — 94-101 仅凭 SITE3_PATCHED 短路
- `frontend/src/api/approval.ts:371` — 368-375 直接 return response（只解一层，request.ts:555-556），声明 {succ
- `frontend/src/api/backup.ts:51` — 51-53 del(`${BASE}/${filename}`) 未 encodeURIComponent
- `frontend/src/api/batchOperations.ts:38` — 38-42 params:{table_name, ids}
- `frontend/src/api/export.ts:46` — 36-39 与 46-49 都请求 ${ASYNC_EXPORT_BASE}/tasks，逐字相同
- `frontend/src/api/helpers/blobDownload.ts:47` — 47-74 与 request.ts:690-727 parseContentDisposition 同构（同正则、同 
- `frontend/src/api/helpers/blobDownload.ts:118` — 116-119 blob = result.data as Blob 无 instanceof/类型校验
- `frontend/src/api/organization.ts:9` — 8-13 删除组织把 confirm_password 放在查询串（虽已 encodeURIComponent）
- `frontend/src/api/request.ts:199` — 194-202 GET 分支无条件 config.cancelToken = new axios.CancelToken
- `frontend/src/api/secrets.ts:75` — 75 post(`/secrets/revoke/${versionId}`) 未 encodeURIComponent
- `frontend/src/components/FilePreview.vue:63` — 28 行仅 import computed/ref/watch（无 onBeforeUnmount）
- `frontend/src/components/FilePreview.vue:59` — 63-64 只重置 loading/unsupported，objectUrl/blobRef 未清
- `frontend/src/components/MapPicker.vue:122` — 122-126 onInputChange 原样 emit innerLng/innerLat
- `frontend/src/components/MapPicker.vue:85` — 85-93 modelValue 监视仅 if (val) 才写入，父组件重置为 null/undefined 时 in
- `frontend/src/components/business/SystemStatus.vue:225` — 225-233 onMounted 内 await refresh() 之后才 setInterval
- `frontend/src/components/common/BaseChart.vue:53` — 49-57 { deep: true } 深监听整个 option 树，53 行 setOption(newOption
- `frontend/src/components/common/BaseChart.vue:63` — 59-67 resize 监听在 onMounted 的 nextTick 回调里注册
- `frontend/src/components/common/ChangeHistoryDialog.vue:45` — 45-49 if (typeof v === 'object') return JSON.stringify(v) 无 
- `frontend/src/components/common/StatsCard.vue:37` — 37-40 仅 string 走兜底，其余 props.value.toLocaleString()，无 Number.
- `frontend/src/components/dataPackage/ExportDialog.vue:92` — 90 行已提示“正在下载文件...”，92-97 的 catch 为空注释（“下载失败不阻塞”），downloadPac
- `frontend/src/components/dataPackage/ImportDialog.vue:60` — 1-9 的 el-dialog 无 destroy-on-close
- `frontend/src/components/dataPackage/ImportEncryptedDialog.vue:114` — 111-117 只 POST /data-packages/upload-encrypted
- `frontend/src/components/funds/YearlyComparisonChart.vue:35` — 35 行发送 department
- `frontend/src/components/map/OfflineMap.vue:85` — 72-87 onMounted 内 await import 后才 initChart
- `frontend/src/components/permission/MenuVisibilityPanel.vue:128` — 127-129 selectedMenuKeys.value = checked?.checkedKeys || che
- `frontend/src/components/permission/PermissionAssignmentDrawer.vue:170` — 167-194 loadCurrentPermissions/loadMenuConfig/loadAllRoles 均
- `frontend/src/components/permission/RoleTagsPanel.vue:89` — 87-93 catch 一视同仁 assignedRoles.value = []，403/网络/5xx 与“无角色”不
- `frontend/src/components/permission/RoleTagsPanel.vue:18` — 11-19 每个 tag 都 closable 且 @close="removeRole(role)" 直接发撤销请求，
- `frontend/src/composables/useAutoLock.ts:38` — 37-43 try { AuthStorage.clearSession(); sessionStorage.setIt
- `frontend/src/composables/useBackupSchedule.ts:36` — 32-38 直接对字段 padStart：*/5 2 * * * → backupTime '02:*/5'
- `frontend/src/composables/useBackupSchedule.ts:46` — 46-51 未校验 backupTime：'25:99' → '99 25 * * *'，'abc:xyz' → 'xy
- `frontend/src/composables/useBackupSchedule.ts:49` — 49-50 硬编码 '* * 1' / '1 * *'：后端 0 2 * * 3 或 0 2 15 * * 经 pars
- `frontend/src/composables/useEventBus.ts:6` — 6 行模块级 const eventHandlers = new Map()
- `frontend/src/composables/useEventBus.ts:21` — 21 forEach((handler) => handler(...args)) 无逐处理器 try/catch：任一
- `frontend/src/composables/useKeyboardShortcuts.ts:83` — 87 行 e.key.length===1 ? e.key.toUpperCase() : e.key 与 44 行 f
- `frontend/src/composables/useRouterSafe.ts:46` — 43-50 router.resolve 判定 NotFound/matched.length===0 时 window
- `frontend/src/composables/useRouterSafe.ts:59` — 59-64 router.push(path)?.catch(err => { ...window.location.h
- `frontend/src/composables/useUploadHeaders.ts:14` — 14-18 ensureCsrf 只 getCsrfToken().then(...) 不 return，await e
- `frontend/src/composables/useVersionCheck.ts:54` — 54 行先 localStorage.setItem(VERSION_KEY, serverVersion)，59-62
- `frontend/src/composables/useVersionCheck.ts:61` — 61 window.location.reload() 不绕 HTTP 缓存（注释却写“绕过浏览器缓存”），HTML/旧
- `frontend/src/config/regionDictionary.ts:92` — 92 _city/_county 完全未用，95-105 对所有区域标志恒返回 false，注释却称“兼容旧版三参数调用
- `frontend/src/directives/permission.ts:40` — mounted 用 el.parentNode.removeChild(el) 永久摘除（34/43/53 行三种模式皆
- `frontend/src/directives/permission.ts:135` — 135-139 仅处理 level==='view' 与 'edit'，无 else：拼错/未传 level 时两个分支
- `frontend/src/directives/watermark.ts:56` — 55-64 只有 mounted/updated，无 unmounted/beforeUnmount
- `frontend/src/layouts/DefaultLayoutSafe.vue:501` — 501-506 在 onMounted 回调里注册 onBeforeUnmount(() => clearInterva
- `frontend/src/layouts/DefaultLayoutSafe.vue:546` — 546-556 自定义 onLock 只做 lockSession + 跳 /login，未调 markLockNow(
- `frontend/src/layouts/DefaultLayoutSafe.vue:94` — 94-113 子菜单仅由父级 funds-admin || funds-user 门控，103-112 各子项无 v-i
- `frontend/src/main.ts:41` — 41 行模块顶层 localStorage.getItem(THEME_STORAGE_KEY) 无 try/catch
- `frontend/src/main.ts:44` — 44 行 AuthStorage.migrateFromLocalStorage() 无错误守卫，方法内部（authSt
- `frontend/src/router/guards.ts:27` — 26-39 只在白名单分支读 sessionStorage.auto_lock_active
- `frontend/src/stores/dataReport.ts:61` — 62-98 previewReport/receiveReport/rejectReport/downloadRepor
- `frontend/src/stores/funds.ts:57` — 56-60 删除后 fundList.filter(...) 再 total.value--
- `frontend/src/stores/organization.ts:70` — 70-77 del('/organizations/'+id) 不带 confirm_password
- `frontend/src/stores/policy.ts:26` — 26-27 catch { /* silent */ }
- `frontend/src/stores/policy.ts:46` — 46-71 createPolicy/updatePolicy/deletePolicy 无 try/catch，网络或
- `frontend/src/stores/user.ts:62` — 55-65 fetchUser(id) 只要拿到对象就 currentUser.value = userData（63 
- `frontend/src/styles/accessibility.css:69` — 69-70 写 --el-color-text-primary/regular
- `frontend/src/styles/components/form-page.scss:78` — 78 color: var(--color-bg-card)（同 93/97/98），tokens-vars.scss:
- `frontend/src/styles/components/prompt.scss:162` — 131 行 .el-notification 块内 162-165 .el-notification__title 与 
- `frontend/src/styles/dashboard-theme.scss:604` — [data-theme="dark"] .dashboard-modern 内：605 背景用 #e5eaf3 的 --
- `frontend/src/styles/print.scss:83` — 83-95 为 th/td 设 background: var(--color-bg-card) 与 th 的 back
- `frontend/src/styles/print.scss:58` — 58-68 .print-footer{position:fixed;bottom:0} 位于 @media print
- `frontend/src/styles/responsive.scss:43` — 41-51 max-width：命名断点走 map.get($breakpoints,$breakpoint) - 1p
- `frontend/src/styles/theme-elevated.scss:371` — 337-340 动画作用于 #main-content > *:not(.error-boundary-root) 与 
- `frontend/src/types/analytics.ts:26` — SupportedVillage 26-35 把 isThreeRegions/isBorderArea/isEthni
- `frontend/src/utils/approvalTimeline.ts:22` — 22 [...a,...b].sort((x,y)=>String(y.time).localeCompare(Stri
- `frontend/src/utils/authStorage.ts:68` — getToken(67-73)=session→PERSIST_TOKEN→legacy local
- `frontend/src/utils/clipboard.ts:36` — 37 document.execCommand('copy') 返回值被丢弃，随后 39 行必报“已复制到剪贴板”
- `frontend/src/utils/desensitize.ts:86` — 现位于 95-98 maskMilitaryID：4 字符 id 时 slice(0,2)+'****'+slice(-
- `frontend/src/utils/echarts-theme.ts:358` — 358-427 仅覆盖 textStyle/title/categoryAxis/valueAxis/legend/to
- `frontend/src/utils/echarts.ts:3` — 3 行 import 与 15-30 注册列表均无 LinesChart/EffectScatterChart/Visu
- `frontend/src/utils/errorHandler.ts:221` — 221 handleError(error, showMessage: boolean 或 string='操作失败')
- `frontend/src/utils/gantt.ts:15` — 13-17 new Date(s.replace(/-/g, '/')) 对所有 '-' 生效：'2026-09-17T
- `frontend/src/utils/index.ts:16` — 15-17 formatDateTime：date 为 null/undefined 时走 d.getTime() 抛 
- `frontend/src/utils/roleAccess.ts:58` — 58 isAdminUser 用原始 role 比对 ADMIN_ROLES，未 normalizeRole
- `frontend/src/utils/treeNormalizer.ts:49` — 49 /^[0-9]/.test(raw) ? `_${raw}` : raw：数字 id 0/1 变 '_0'/'_1