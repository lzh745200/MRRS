# -*- coding: utf-8 -*-
"""应用内「更新日志」数据（自动生成，请勿手工编辑）。

来源：仓库根目录 ``CHANGELOG.md``（唯一账本）。
生成：``python3 scripts/sync_update_log.py``
校验：``python3 scripts/sync_update_log.py --check``（CI 门禁，不一致即失败）

改版本说明请改 CHANGELOG.md，然后重跑生成脚本；直接改本文件会被门禁拦下。
"""

VERSION_HISTORY_DATA = [
    {
        "version": "1.0.0",
        "date": "2026-01-29",
        "description": "✨ 帮扶村管理",
        "features": [
            "✨ 帮扶村管理",
            "✨ 项目管理",
            "✨ 组织管理",
            "✨ 政策管理",
            "✨ 数据统计分析",
            "✨ 用户认证和授权",
            "✨ 角色权限管理",
            "✨ 用户个人设置",
            "✨ 数据导入导出",
            "✨ 数据备份恢复",
            "✨ 数据报表生成",
            "✨ 系统监控",
        ],
    },
    {
        "version": "1.1.0",
        "date": "2026-03-13",
        "description": "✨ 增量数据包导入导出系统",
        "features": [
            "✨ 增量数据包导入导出系统",
            "✨ 支持13个数据表的同步",
            "✨ 三种冲突策略(跳过/覆盖/手动)",
            "✨ ZIP压缩格式",
            "✨ 完整的导入导出历史记录",
            "✨ 完全离线的地图瓦片管理",
            "✨ 支持缩放级别4-18",
            "✨ 瓦片自动降级",
            "✨ 预设区域下载(贵州省、毕节市)",
            "✨ 地图瓦片管理界面",
            "✨ 批量更新记录",
            "✨ 批量删除(软删除/硬删除)",
        ],
    },
    {
        "version": "1.2.0",
        "date": "2026-06-20",
        "description": (
            "🐛 RuralWorkService.create_rural_work 缺失 — 生产环境 AttributeError: 'RuralWorkService' object has n"
            "o attribute 'create_rural_work'…"
        ),
        "features": [
            (
                "🐛 RuralWorkService.create_rural_work 缺失 — 生产环境 AttributeError: 'RuralWorkService' object has n"
                "o attribute 'create_rural_work'…"
            ),
            "🐛 UserCascadeDeleteService 是 stub — 删除用户始终 500，用 SQLite Pragma 反射重写级联删除",
            "🐛 ExcelExportService.export_organization_pass_codes 缺失 — 组织通行证码导出始终 500，补全方法",
            (
                "🐛 reports 端点 5 处 async 服务调用漏 await — export_to_excel/export_to_pdf/export_comprehensive_report"
                "/get_export_filename 把协程传给 BytesIO 运行时崩溃"
            ),
            (
                "🐛 feedback verify_token 导出缺失 — from app.api.v1.auth import verify_token 永远 ImportError，登录用户提交反"
                "馈不记录身份"
            ),
            "🐛 analytics_service.filter_villages 契约不匹配 — service 返回 dict 路由期望元组，统一为 (items_orm, total) 元组",
            (
                "🐛 工作列表新增数据不显示（根因） — rural_work_service._to_dict 漏 village_name 字段，前端\"所属村庄\"列显示空白。通过 ORM relat"
                "ionship 懒加载补全"
            ),
            "🐛 batch-delete body 契约不匹配 — 前端发 {ids: [...]} 后端期望 bare [...]，改为 payload: dict 提取 ids",
            (
                "🐛 AuditLogService.log 字段名错误 — AuditLog(resource=..., details=..., ip_address=...) 三个字段名与模型列不匹配"
                "（resource_type/user_ip/metadata_），审计日志静默丢失"
            ),
            "🐛 projects.py audit.log 未传 db — 3 处审计日志调用未传 db 参数，日志从未写入",
            "🐛 admin.py int(None) 崩溃 — 配置值为 None 时 int(None) 抛 TypeError，加 or 防御",
            (
                "🔧 file_upload magic 安全导入 — Windows libmagic 触发不可捕获的 access violation 导致全部后端测试崩溃，改用 stdlib mime"
                "types + 扩展名映射"
            ),
        ],
    },
    {
        "version": "1.5.1",
        "date": "2026-08-04",
        "description": (
            "🐛 麒麟 V10 桌面快捷方式缺失：DEB 安装后未在用户桌面创建启动图标。postinst 现为每个 /home 用户创建桌面快捷方式（自动检测 Desktop/桌面 目录并设置 gio"
            " 信任标记），安装后桌面即出现图标"
        ),
        "features": [
            (
                "🐛 麒麟 V10 桌面快捷方式缺失：DEB 安装后未在用户桌面创建启动图标。postinst 现为每个 /home 用户创建桌面快捷方式（自动检测 Desktop/桌面 目录并设置 gio"
                " 信任标记），安装后桌面即出现图标"
            ),
            (
                "🐛 麒麟 V10 开始菜单图标不显示：.desktop 文件 Icon 引用系统通用图标且图标未打入 DEB 包。现打包应用图标到 /opt/assistance-management-s"
                "ystem/icons/、/usr/share/pixmaps 与 hicolor 多尺寸主题目录，菜单图标正常显示"
            ),
            "🧹 卸载时（postrm）清理系统图标、应用菜单项与各用户桌面快捷方式",
            "docker/Dockerfile.kylin-standalone：DEB 包新增图标文件与系统图标目录安装",
            "deploy/kylin/desktop/assistance-management-system.desktop：Icon 指向应用图标绝对路径",
        ],
    },
    {
        "version": "1.5.2",
        "date": "2026-08-11",
        "description": "审批概览 GET /api/v1/approval 由占位模块信息改为真实统计（待审批/已通过/已拒绝/总数/我的待审批），前端概览页统计卡恢复真实数据",
        "features": [
            "审批概览 GET /api/v1/approval 由占位模块信息改为真实统计（待审批/已通过/已拒绝/总数/我的待审批），前端概览页统计卡恢复真实数据",
            (
                "报表订阅模块全链路修复：service 订阅方法完整实现（列表/创建/更新/取消）、响应字段 getattr 容错（修复 500）、生成接口兼容 subscription_id 调用；订阅"
                " CRUD/切换/生成/下载真实 API 验证全部通过"
            ),
            "监控面板 Promise.allSettled 解构错位修复（4 变量取 5 个 promise），系统日志面板恢复展示后端真实日志（/system/admin/logs）",
            "测试隔离：conftest 会话启动清理遗留 test.db，消除跨会话顺序敏感偶发失败",
            "清理误提交的协作者工作区改动与 .reasonix 临时文件，测试套件恢复稳定（后端 12118 / 前端 6273 全过，覆盖率 100%）",
        ],
    },
    {
        "version": "1.8.0",
        "date": "2026-08-12",
        "description": (
            "✨ 经费管理全流程化：列表页新增 8 阶段流程步骤条（预算编制 → 经费申请 → 审批 → 拨付 → 使用执行 → 报销核销 → 决算结算 → 归档），按年度统计自动高亮当前阶段，步骤图标"
            "可跳转对应功能页；步骤条下方附流程指引说明"
        ),
        "features": [
            (
                "✨ 经费管理全流程化：列表页新增 8 阶段流程步骤条（预算编制 → 经费申请 → 审批 → 拨付 → 使用执行 → 报销核销 → 决算结算 → 归档），按年度统计自动高亮当前阶段，步骤图标"
                "可跳转对应功能页；步骤条下方附流程指引说明"
            ),
            (
                "✨ 普通用户可完整操作经费：新增 require_funds_operator_role（放行 user 及以上，viewer 保持只读），经费/经费生命周期/预算/转账凭证/合同/结算全"
                "部端点对 user 角色开放；后端菜单 funds-admin/新增 funds-lifecycle/funds-settlement 对 user/viewer 可见"
            ),
            (
                "✨ 经费详情审批流程可视化：新增 GET /funds/{id}/approval-flow（状态机 6 节点 + reached/current 高亮），详情页「审批流程」页签新增 el"
                "-steps 步骤条与当前审批人展示"
            ),
            "✨ 审批转交：待审批列表新增「转交」操作（选择审批人 + 可选原因），对接 POST /approval/tasks/{id}/transfer",
            (
                "✨ 数据分析年度对比：后端 /statistics/analysis 新增 yearly_comparison（按年份聚合村数/投入/人均收入），前端年度对比页签支持按年份取值、el-em"
                "pty 空态、投入 vs 收入对比柱状图"
            ),
            "✨ 政策文件预览修复：预览接口按 blob 流处理（图片/PDF/HTML 内联预览，Office 提示并下载），下载文件名使用真实扩展名；移除政策「提交审批」按钮（政策无需审批流）",
            "✨ 系统配置删除：配置列表新增「删除」按钮（二次确认），对接 DELETE /system/config/{key}",
            "✨ 消息中心类型扩展：新增「备份提醒」消息类型（筛选/标签/格式化），每日 03:30 自动清理 30 天前消息（message_cleanup_job）",
            "✨ 贵州省 88 县区补全：毕节/遵义/安顺/铜仁/黔东南/黔西南补齐全部县级行政区（合计 88 个），含各乡镇数据",
            (
                "🐛 帮扶村年度数据保存后不显示：YearlyOverview/Detail 读取年度数据用错 key（industrySupport/partyBuilding 等臆造 camelCase"
                "），实际后端按 section 原始 key 返回（industry/party-building 等），全部修正并对齐类型定义"
            ),
            (
                "🐛 帮扶村变更历史无效：前端 getChangeHistory 硬编码返回空数组从未调用后端；后端新增字段级留痕（创建/更新/年度数据保存写 AuditChange）+ GET /supp"
                "orted-villages/{id}/change-history 端点"
            ),
            "🐛 帮扶村详情编辑无效：?mode=edit 查询参数未被 pageMode 计算识别，点击编辑无响应，已支持",
        ],
    },
    {
        "version": "1.8.1",
        "date": "2026-08-13",
        "description": (
            "🐛 报表 Word/PDF 导出为空文件：report_export_service 的 export_word/export_pdf 此前直接返回空 bytes，管理员在「数据导出 → "
            "报告导出」下载到 0 字节文件；现已用 python-docx / reportlab 实现真实公文渲染（标题/年度/生成时间/章节表格，PDF 内置 STSong-Light 中文 CI"
            "D 字体、无需字体文件）…"
        ),
        "features": [
            (
                "🐛 报表 Word/PDF 导出为空文件：report_export_service 的 export_word/export_pdf 此前直接返回空 bytes，管理员在「数据导出 → "
                "报告导出」下载到 0 字节文件；现已用 python-docx / reportlab 实现真实公文渲染（标题/年度/生成时间/章节表格，PDF 内置 STSong-Light 中文 CI"
                "D 字体、无需字体文件）…"
            ),
            (
                "🐛 报表数据为空壳：generate_summary_report_data/generate_fund_detail_report_data/generate_project_progr"
                "ess_report_data 此前返回空数组；现按年度真实聚合——经费按类型分组统计笔数与申请/批准/拨付/使用金额，项目按状态分组统计数量/平均进度/预算/实际花费，年度总结与综合报告"
                "合并村/校/项目/经费四板块"
            ),
            "🗑️ 死代码：删除 ReportExportService.export_to_excel（无任何调用方，且委托目标 ExcelExportService.export 不存在的断裂方法）",
            "⚡ useRouterSafe 调试日志改走统一 logger.debug（内部含生产环境门控），移除生产路径上的 console.log 残留",
            (
                "新增 tests/unit/test_report_export_service.py：针对真实实现的数据聚合断言、docx/pdf 魔法字节与最小体积校验、空数据仍输出有效文档、docx"
                " 解包校验表格内容（防\"返回空 bytes\"回归）"
            ),
            "更新 tests/unit/test_cov_final_report_export_service.py 断言至 v1.8.1 新数据契约（title/sections 结构）",
        ],
    },
    {
        "version": "1.8.2",
        "date": "2026-08-15",
        "description": (
            "🐛 新增项目进度始终为 0（双断点）：后端 ProjectCreate 模型缺失 progress 字段导致请求中的进度被静默丢弃；前端新建分支提交载荷也未携带进度。现前后端贯通——新建项"
            "目填写\"当前进度\"保存后立即正确显示，后续编辑仍走变更留痕（_PROJECT_KEY_FIELDS 含 progress，详情页\"变更历史\"完整记录）"
        ),
        "features": [
            (
                "🐛 新增项目进度始终为 0（双断点）：后端 ProjectCreate 模型缺失 progress 字段导致请求中的进度被静默丢弃；前端新建分支提交载荷也未携带进度。现前后端贯通——新建项"
                "目填写\"当前进度\"保存后立即正确显示，后续编辑仍走变更留痕（_PROJECT_KEY_FIELDS 含 progress，详情页\"变更历史\"完整记录）"
            ),
            "🐛 组织机构新增后编码为空：前端表单提示\"留空自动生成\"但后端未实现，code 落库为 NULL。现创建时 flush 拿到自增 id 后自动生成 ORG+6位数字 唯一编码",
            (
                "🐛 帮扶成效排名三列恒空：后端 rankings 未 select support_unit（帮扶单位列永远空白），且前端渲染了后端从不提供的 scores.project_complet"
                "ion/fund_execution 两列。现后端补齐帮扶单位字段，前端删除假数据列并按真实契约补上\"生态\"列"
            ),
            (
                "🐛 成效评估报告渲染 \"[object Object]\"/\"2026.0\"：flatResult/flatCompareResult 把后端嵌套对象（indicators/year"
                "1_data/delta）直接 String() 透传给 el-descriptions。"
            ),
            (
                "🐛 进入评估页即触发写操作：带 villageId 参数打开评估页时此前直接 POST 重算并覆写评估记录。现先 GET 已有报告（只读），404 时提示\"该年度尚未评估\"；「开始评估"
                "」按钮仅管理员可见（viewer/user 从排名页进入的入口文案降级为「查看」），杜绝误触 403"
            ),
            "🐛 重复评估刷重复审批任务：每次评估都新建\"年度考核复核\"审批任务且无去重。现提交前按 entity+年度查重，已有待处理任务时复用",
            "🐛 经费申请页重复入口：「提交经费申请」与「新增经费记录」两按钮功能完全一致（后者实为历史直创建分支，跳过申请语义）。已删除「新增经费记录」按钮及关联死代码，申请页仅保留唯一入口",
            (
                "🐛 经费模块多处\"修改了却不更新显示\"：经费详情提交工作流/编辑后不刷新日志页签；经费总览删除/快捷审批/快捷拨付/批量删除后年度统计卡不刷新；合同附件登记成功不刷新列表且失败时假成功"
                "提示；生命周期预算锁定后阶段/计划不刷新；决算审批弹窗残留上次表单；经费报表\"已使用金额\"列 prop 与数据键 snake/camel 不匹配导致恒空。已逐一修复"
            ),
            (
                "🐛 菜单客户端跳转后页面永久空白：<router-view> 的 transition mode=\"out-in\" 子组件根节点 display:contents 无盒模型，opaci"
                "ty 过渡不触发 transitionend，旧节点永不完成离场。已移除该 transition 包装"
            ),
            (
                "🐛 E2E 审批 spec 对话框断言全灭：[role=\"dialog\"] 命中的 el-overlay-message-box/el-overlay-dialog 中间层无盒模型恒为"
                " hidden，且页面筛选栏 combobox 与对话框内元素 strict 冲突。统一改锚 .el-overlay:visible 并限定对话框作用域，超时 3s→10s"
            ),
            "💄 帮扶成效两页样式全量 Token 化（排名奖牌渐变/卡片头渐变/正文辅助色均改 var(--color-*)）",
            "✨ 经费总览写操作后同步刷新年度统计；合同附件上传失败改为真实错误提示（附件登记失败，请重试）",
        ],
    },
    {
        "version": "1.8.3",
        "date": "2026-08-16",
        "description": (
            "✨ 权限包管理：管理员可将一组菜单打包为「权限包」并绑定一批普通用户（仅限 user/viewer，admin/super_admin 拒绝绑定），改包即全员生效。菜单可见性三级优先级：个"
            "人菜单配置 > 绑定权限包 > 角色默认；未绑定用户行为与历史完全一致。入口：系统管理 → 权限包管理（admin/super_admin）；用户管理列表新增「权限包」列"
        ),
        "features": [
            (
                "✨ 权限包管理：管理员可将一组菜单打包为「权限包」并绑定一批普通用户（仅限 user/viewer，admin/super_admin 拒绝绑定），改包即全员生效。菜单可见性三级优先级：个"
                "人菜单配置 > 绑定权限包 > 角色默认；未绑定用户行为与历史完全一致。入口：系统管理 → 权限包管理（admin/super_admin）；用户管理列表新增「权限包」列"
            ),
            (
                "✨ 数据上报与接收闭环补强：非管理员导出一键上报包仅含本人录入数据（管理员维持全组织，manifest 记录 export_scope/exported_by_name，旧格式包兼容）；新"
                "增字段级自动校验纠正（必填/枚举/手机号/日期/数值——自动 trim、手机号去分隔符、日期归一 ISO、数字字符串转数值；行分级 ok/corrected/rejected，reject"
                "ed 不入库并注明原因）；"
            ),
        ],
    },
    {
        "version": "1.9.0",
        "date": "2026-08-16",
        "description": (
            "✨ 年份滚动窗口共享工具：新增 frontend/src/utils/yearOptions.ts（getYearOptions()），可选年份上限 = 当前年份 + 10，随系统时钟自动"
            "后移，年份选择永不过期，保证系统可以一直使用下去；配套 7 项单元测试（含模拟 2031 年时钟滚动验证）"
        ),
        "features": [
            (
                "✨ 年份滚动窗口共享工具：新增 frontend/src/utils/yearOptions.ts（getYearOptions()），可选年份上限 = 当前年份 + 10，随系统时钟自动"
                "后移，年份选择永不过期，保证系统可以一直使用下去；配套 7 项单元测试（含模拟 2031 年时钟滚动验证）"
            ),
            (
                "♻️ 解除全系统年份选择限制：全站约 14 处年份下拉框此前以「当前年 + 1」为上限（2026 年只能选到 2027 年），现统一改用滚动窗口工具——帮扶村表单（2021 起）/板块数据"
                "表单与年度总览（2017 起）/年度数据表单/数据分析年度对比/经费预算/经费分析/经费列表年度总览/分类经费表单/驻村工作报表与列表/成效排名与评估/奖学金学生（滚动窗口 ∪ 数据年份）"
                "。"
            ),
            (
                "🐛 版本号统一至 1.9.0：version.txt（唯一数据源）经 scripts/sync_version.py 同步到 config.py / 根 package.json / fr"
                "ontend/package.json / .env.example / frontend/.env.example…"
            ),
            "🐛 荣誉年份硬编码上限 2030：综合录入页荣誉表彰年份输入框 :max=\"2030\"，2030 年后表彰无法录入。已改为 2099（与同页起始/结束年份输入框一致）",
        ],
    },
    {
        "version": "1.10.0",
        "date": "2026-08-24",
        "description": "🐛 工作台快捷入口：「资金周期」「经费结算」不再跳回经费总览，直达 /funds/lifecycle 与 /funds/settlement",
        "features": [
            "🐛 工作台快捷入口：「资金周期」「经费结算」不再跳回经费总览，直达 /funds/lifecycle 与 /funds/settlement",
            (
                "🐛 KPI 环比诚实化：工作台五卡接入后端 trends 真实环比（人口卡标注\"较去年\"）；分析仪表板此前将 kpi-trends 绝对值误当百分比展示的假数据根治，负增长显示红色↓箭"
                "头、零增长显示\"持平\"；sparkline 由模拟数据改为真实近5年年度序列"
            ),
            "🐛 全局搜索找回资金结果：fund 类型在前端类型/标签/图标/分组排序全面接线，占位文案补充\"经费\"",
            "🐛 帮扶村列表年份筛选复活：前后端贯通（year_start 参数 + filter-options 返回 years）",
            "🐛 变更历史字段级明细：时间线展示\"谁在何时把什么字段从 A 改为 B\"（old_value→new_value）",
            "🐛 导入错误明细可见：帮扶村/学校两处导入失败弹窗展示行级错误清单（前10条+总数），学校侧修正信封层级读取",
            "🐛 经费申请页过滤失效：search/type 参数对齐后端 keyword/fund_type",
            "🐛 经费驳回必填：前端空意见拦截 + 后端 reject 接收 opinion（400 fail-closed）并写入状态历史与关联审批任务",
            (
                "🐛 数据质量\"自动修复\"假成功根治：新增 trim_whitespace/normalize_empty 两规则真实现；未知规则键返回400；响应增加 changed_count（实际"
                "修正记录数）口径"
            ),
            "🐛 消息链接修复：资金异常通知 link 改指真实路由 /funds/anomaly；审批通过/驳回通知携带实体详情链接可直接跳转；新待审任务指向 /approval/pending",
            "🐛 总览状态中文裸露根治：FUND_STATUS 枚举扩至九态（补 planned/audited/rejected），筛选下拉同步",
            (
                "♻️ 删除冗余视图7个：projects/ProjectManagement.vue（含路由）、dataImport/BatchImport.vue、dataVerify/Index.vu"
                "e、dataManagement/Overview.vue、report/List.vue、ImportSection.vue、ExportSection.vue、system/UserP"
                "ermissions.vue（路由重定向至权限包管理）"
            ),
        ],
    },
    {
        "version": "1.10.1",
        "date": "2026-08-27",
        "description": (
            "🐛 审计日志 4 处 404：OperationLogs/AuditManagement/dataManagement 调用 /audit/logs、/audit/logs/export、"
            "/audit/exports 缺 /system 前缀，运行时必 404（对齐度核查工具 scripts/api_alignment_check.py 发现）"
        ),
        "features": [
            (
                "🐛 审计日志 4 处 404：OperationLogs/AuditManagement/dataManagement 调用 /audit/logs、/audit/logs/export、"
                "/audit/exports 缺 /system 前缀，运行时必 404（对齐度核查工具 scripts/api_alignment_check.py 发现）"
            ),
            "🐛 备份计划回显错位：后端返回驼峰 keepCount，前端回退链只读 keep_count，界面保存后恒显默认 7 天",
            "🐛 el-statistic / el-card 破损属性：PendingList value-style、Import body-style 属性名断裂导致样式失效",
            "🐛 useBackupSchedule 测试契约过时：重写至 cron↔友好模型双向转换契约（含 weekly/缺省分支）",
            (
                "🐛 磁盘空间测试 3 失败：psutil 桩改注入 sys.modules；os.statvfs 打桩 create=True；upload_restore 弃 from-import 局"
                "部绑定"
            ),
            "🐛 版本号收尾：backend/version.json 1.5.0 → 1.10.0，至此 6 处版本源全部一致",
            "前端 6550 通过 / 0 失败（新增 api 层 14 用例：milestones、fundsRecycle、schoolsRecycle、offlineMap），覆盖率门禁恢复绿灯",
            "后端 12613 通过 / 0 失败 / 0 skip / 0 xpass",
            "死代码清理：config_validator.ProductionSettings（无引用 Backward-compat stub）",
            "仓库卫生：根目录构建脚本归位 scripts/docker|legacy/，3 个 AI 会话转录文档（1MB）移出版本库",
            "数据隔离审计收官：8/8 业务模块确认隔离、0 漏洞（docs/数据隔离审计矩阵.md），澄清早期 grep 误报",
        ],
    },
    {
        "version": "1.10.2",
        "date": "2026-08-29",
        "description": (
            "🐛 Windows 安装后启动报 SyntaxError: Unexpected token '}'（main process 弹窗）：提交 10c56cd0 以 GBK 编码重写 ele"
            "ctron/main.js（COORDINATION.md §3 明令禁止的PowerShell 写法），吞掉换行与引号——findAvailablePort 的 for(...) 被并入"
            "注释导致178 行孤立 }；"
        ),
        "features": [
            (
                "🐛 Windows 安装后启动报 SyntaxError: Unexpected token '}'（main process 弹窗）：提交 10c56cd0 以 GBK 编码重写 ele"
                "ctron/main.js（COORDINATION.md §3 明令禁止的PowerShell 写法），吞掉换行与引号——findAvailablePort 的 for(...) 被并入"
                "注释导致178 行孤立 }；"
            ),
            "🐛 麒麟 Electron DEB 打不开：同一损坏的 main.js 打进 DEB → 主进程启动即崩，随恢复治愈。",
            (
                "🐛 麒麟 standalone DEB 装完打不开 / 无菜单图标 / 无桌面快捷方式：DEBIAN/postinst|prerm|postrm、kylin.env、*.service、p"
                "olkit 规则共 6 个文件为 CRLF（Windows 检出 + 构建无规范化）→ #!/bin/bash\\r 不可执行 → dpkg 报 post-installationerro"
                "r → 菜单项/快捷方式/图标/服务/数据目录全部未创建。"
            ),
            "🐛 麒麟启动脚本硬依赖未打包的 curl：start-kylin.sh 健康检查增加curl→wget→bash /dev/tcp 三级回退（零外部依赖）。",
            (
                "🐛 麒麟直接启动回退路径权限：/var/lib 对桌面用户组不可写时降级 $HOME/.assistance-management-system/；postinst 数据/日志目录 750"
                "→2750（组可写，配合 usermod -aG 已有加组逻辑）。"
            ),
            "🐛 CI 内嵌 postinst 乱码路径：build-arm64.yml /opt/甯壎绠＄悊绯荤粺 → /opt/帮扶管理系统。",
            (
                "🔒 CI 语法门禁：build-windows.yml / build-arm64.yml 在 electron-builder 打包前node --check electron/*.js"
                "，失败即终止构建。"
            ),
            "🔒 pre-commit 阶段新增 electron-syntax-check hook（改动 electron/*.js 时本地即时拦截）。",
            "🔒 package.json 新增 npm run check:electron；build/build:win 前置语法校验。",
            "清理死脚本 scripts/linux-postinst.sh（路径错误零引用）；安装指南中不存在的 build-deb-ubuntu.sh 引用改为 Docker 构建实际方式。",
        ],
    },
    {
        "version": "1.10.3",
        "date": "2026-08-29",
        "description": (
            "✨ CI 补建 standalone 麒麟 DEB 流水线：此前 CI 只构建 Electron DEB，而安装指南推荐的 standalone DEB（无 Electron，后端+Web"
            "）只能本地 Docker 自建。新增standalone-deb job（buildx+QEMU ARM64，GHA layer 缓存）…"
        ),
        "features": [
            (
                "✨ CI 补建 standalone 麒麟 DEB 流水线：此前 CI 只构建 Electron DEB，而安装指南推荐的 standalone DEB（无 Electron，后端+Web"
                "）只能本地 Docker 自建。新增standalone-deb job（buildx+QEMU ARM64，GHA layer 缓存）…"
            ),
            (
                "🐛 环境变量三层错序开浏览器：kylin.env 声明的 AUTO_OPEN_BROWSER 是死键（start.py 从不读取），实际生效的 KYLIN_MODE 让 systemd 服"
                "务层（无 DISPLAY）尝试开浏览器。"
            ),
            (
                "🧹 坏文件：全仓 2786 个文本文件 mojibake 字节级扫描（scripts/scan_mojibake.py工具入库），唯一真命中为根目录 .env（GBK 双重编码，注释吞掉 "
                "HOST=127.0.0.1等配置行）——已按 .env.example 重建实际取值（文件不入库）。"
            ),
            (
                "🧹 死代码：error_handler 四个零引用 backward-compat 别名（BadRequestError/ForbiddenError/ConflictError/Serv"
                "erError）移除，保留有引用的AppError/NotFoundError；"
            ),
        ],
    },
    {
        "version": "1.10.4",
        "date": "2026-08-29",
        "description": "CI 修正",
        "features": [
            (
                "🐛 fix(ci): standalone-deb 产物路径修正（buildx output 导出树保留 /output/ 前缀），standalone 麒麟 DEB 产物重新挂载到 Gi"
                "tHub Release"
            ),
        ],
    },
    {
        "version": "1.10.5",
        "date": "2026-08-29",
        "description": "UI 可读性根治 + 全站精美化",
        "features": [
            "🎨 根治\"UI 看不清\"：提示可读性修复、全站视觉统一美化、输入框规范化",
            "🧹 NUL 坏文件全清（CodeCheck 失败文件归零）",
            (
                "🔖 版本号随 tag 联动：CI 打包前 sync 脚本把 tag 版本写入 frontend/.env.production的 VITE_APP_VERSION（vite 构建注入，本地"
                "开发回落 .env）"
            ),
        ],
    },
    {
        "version": "1.10.6",
        "date": "2026-08-29",
        "description": "全仓库死代码彻底清理(v1.10.5 为清理前基线)",
        "features": [
            (
                "删除 87 个零引用模块文件 + data/ + interfaces/api/(~12,300 行):core 21、services 21、utils 21、schemas 10、mi"
                "ddleware 3、未注册路由 2、垫片 4"
            ),
            (
                "删除 6 个零引用模型文件 + EffectivenessIndicator/VersionHistory 两类,新增 alembic dead_models_001 迁移 DROP 8 "
                "张表(本地全库验证 0 行)"
            ),
            (
                "摘除活模块内孤儿符号 ~60 个(exceptions 11 异常类、response/security/error_handler/query_optimizer 孤儿函数、servic"
                "es 死方法与死类型)"
            ),
            "PyInstaller spec 移除不存在的 messages_extended;删除陈旧 requirements-lock.txt",
            (
                "依赖精简 31 项(redis/jieba/matplotlib 全家桶/scipy/python-pptx 等,全部验证零 import 含懒加载);当前 venv 卸载全部 24 包后"
                "全量 pytest 通过(强验证)"
            ),
            "测试同步:删除死模块专测 ~70 文件,混合 harness 摘除死段保留活用例",
            (
                "删除 test-only 存活文件 73 个(44 组件、16+4 composables、7 utils、3 stores、4 api、appConfig/rbac/permission"
                "s 等)与零引用死文件 10 个"
            ),
            "重复实现归并:PageHeader/GlobalSearch 死副本、Skeleton/LazyImage/DataTable 两套",
            "17 个覆盖率 harness 摘除死条目,保留活代码覆盖",
            (
                "package.json 移除 fast-check/@types/dompurify/rollup/@commitlint/*/driver.js;删除休眠 commitlint 链与 "
                "frontend/scripts 5 个孤儿脚本"
            ),
            (
                "git rm:test_scripts/、installers/、k8s/、Dockerfile.arm64/.fpm、.qwen/.reasonix、skills-lock.json、e"
                "nvironment.yml、根 mypy.ini、根 .bandit、根 tests/ 孤儿部分、scripts/ 孤儿 21 个、resources 死图标 17 个、build-sc"
                "ripts 死文件 4 个"
            ),
            (
                "docker/Dockerfile 删除从未可构建的 electron-builder 阶段(electron/ 无 package.json)构建打包指南 NSIS 钩子表、项目结构说明"
                "死项标注、system_design.md 历史存档声明"
            ),
        ],
    },
    {
        "version": "1.11.0",
        "date": "2026-08-30",
        "description": "全面体检修复版（安全红线 + 功能补全）",
        "features": [
            "🐛 帮助文档出厂密码文案：admin/admin123 修正为 admin/Admin@2026，与 main.py 出厂播种逻辑及测试断言一致。",
            (
                "🐛 Electron 导航白名单前缀绕过（W6-T3）：will-navigate /setWindowOpenHandler 的 startsWith('http://127.0.0.1"
                "') 前缀判定可被http://127.0.0.1.evil.com / userinfo @ 手法绕过，改为new URL(url).origin 精确匹配 + 端口钉扎（12 组绕过用"
                "例验证）。"
            ),
            (
                "🐛 stopBackend 误杀风险（W6-T3）：优雅退出后取消强杀定时器，防止对已退出（PID 可能被系统复用）的进程执行 taskkill /f /t；重启端口等待由固定 2s 改为"
                "轮询探测释放（上限 10s）。"
            ),
            (
                "🐛 SHA256SUMS 行尾：CI 生成改 WriteAllText 显式 LF——WriteAllLines在 Windows 写 CRLF 导致 sha256sum -c 全部 FA"
                "ILED（本地 dry-run 实测）。"
            ),
            (
                "🔒 vcredist 移出 git + SHA256 钉扎（W6-T2，critical）：37.7MB 官方二进制不再入库；新增 scripts/build/fetch_vcredist"
                ".ps1（CI 9.6 步与make fetch-vcredist 共用，从 aka.ms 官方短链下载并比对钉扎哈希，本地已存在且匹配则跳过）；NSIS 钩子安装期 Get-FileHa"
                "sh 复核，不匹配弹窗中止安装（fail-closed）。"
            ),
            (
                "✨ Release SHA256SUMS 完整性链（W6-T5）：三个发布产物族独立命名清单（windows-x64 / electron-deb-arm64 / standalone-d"
                "eb-arm64）随artifact 上传并附 Release；Windows Release 说明附校验指引。"
            ),
            (
                "✨ 前端产物同步逐文件哈希校验：sync-frontend-dist.{sh,bat} 由du 字节粗校验（>5% 仅警告）改为逐文件 SHA256 manifest 比对，偏差即exit"
                " 1；manifest 落盘供 audit_static_assets.py --verify-manifest 复核。"
            ),
            (
                "✨ PyInstaller onefile → onedir（W6-T6/ADR-0006）：冷启动实测 32.3s →8.6s（~3.8 倍）；消除 %TEMP% 自解压的杀软误报画像；"
                "datas 摘除 app/ 源码目录与死依赖（aiosqlite/jieba/bs4/prometheus_client），hiddenimports 删除54 条 collect 覆盖的"
                "手写路由；"
            ),
            "🔒 Actions 全量 pin 到 commit SHA（W6-T7）：4 个 workflow 57 处 uses实时解析上游 SHA 固定，消除 tag 漂移的供应链风险。",
            (
                "✨ 代码签名管线就绪（W6-T1 管线侧）：CSC secrets 配置即自动签名（后端 exe signtool + 安装包/卸载器 electron-builder），未配置显式WAR"
                "NING 跳过；接入与验签文档 docs/04-部署文档/01-Windows部署/代码签名.md。"
            ),
            "📝 离线升级与回滚指南（W6-T10）：备份→SHA256/签名校验→覆盖安装→alembic 迁移→回滚路径；NSIS 卸载静默默认保留用户数据（/SD IDNO）。",
            (
                "🔐 secrets.json 明文回落收紧（W6-T11）：safeStorage 不可用时 0600权限 + 风险文档标注。代码（userManagementApi/EXPORT_FIE"
                "LDS），286 项按验收标准标注豁免（265 项被各自单元测试引用——纠正工单\"含测试零引用\"前提；21 项特殊形态有真实引用）；顺带修复 W3-T2 menuKeyAlignmen"
                "t 守卫对可选参数路由的匹配（14d2b243 引入的存量红测试）。"
            ),
        ],
    },
    {
        "version": "1.11.1",
        "date": "2026-08-30",
        "description": "Windows 安装器真机修复版",
        "features": [
            (
                "🐛 安装器真机全部中止（截图故障）：NSIS 对双引号字符串做 C 风格转义，钩子把 $INSTDIRPowerShell，Get-FileHash 恒定报错 exit 1，被误判\"哈希"
                "不匹配\"而中止所有真机安装。修复：钩子路径反斜杠全部 \\；校验改为 FileWrite 写出 .ps1 后-File 执行（不再使用行内 -Command）；校验脚本执行后清理。"
            ),
            (
                "🐛 校验三态语义：0=匹配静默安装；1=确证不匹配弹窗中止（真实篡改信号）；3 或 error=校验工具不可用（无 PowerShell/被安全软件阻断）→ 跳过 redist安装但不阻断"
                "部署（应用由 Layer 1 内置运行时 DLL 兜底，不执行无法校验的二进制）。初版将\"工具不可用\"与\"确认篡改\"混为一谈，是假阳性根因之一。"
            ),
            (
                "📝 文档同步：AGENTS.md 新增 NSIS 转义铁律 Known Issue；工单 002 追记复盘；打包指南/OFFLINE_UPGRADE/build-scripts READM"
                "E 校验语义更新。"
            ),
        ],
    },
    {
        "version": "1.11.2",
        "date": "2026-08-30",
        "description": "403 权限页根因修复 + 全站弹窗显示修复",
        "features": [
            (
                "🐛 无组织管理员被判\"无任何组织权限\"（核心根因）：单机/未绑定组织的管理员访问数据包、增量更新、版本管理、数据上报等组织门禁端点一律 403——organization_permis"
                "sion_service/user_permission_service 共 7 处仅 superuser 旁路改为 admin 语义（ADR-0002 对齐）；普通用户维持 fail-c"
                "losed。"
            ),
            (
                "🐛 菜单加载失败窗口期全站 403：打包版后端冷启动（onedir 8.6s）期间/menus/accessible 失败 → 路由守卫把所有带 menuKey 的页面弹到 /403——守"
                "卫改为仅\"菜单已加载且明确不含该键\"才拒绝（菜单是可见性层，真实权限由后端接口兜底）。"
            ),
            "🐛 经费申请页 admin 403：funds-user 菜单键 roles 缺 admin/super_admin。",
            "🐛 存量旧角色名被 meta.roles 误拒：守卫校验前先 normalizeRole 归一化（manager/approval_leader→admin，operator→user）。",
            (
                "🐛 legacy 模型数据范围 500：villages 等无 created_by/organization_id 列的模型在数据范围过滤下 AttributeError→500，改为 "
                "fail-closed 空集（ADR-0002）。"
            ),
            "🧪 真实库双角色全量 GET 端点巡检：admin 0×403/0×500；新增回归test_org_less_admin_403_fix.py（7 用例）+ 前端守卫 3 用例。",
            "🐛 sklearn 随死代码清理移除后 ai 收入预测/趋势预测端点必 500 → numpy polyfit 等价实现",
            "🐛 monitoring 端点统计 func.case 误用（SQLAlchemy 2.x 无此函数）→ case()",
            "🐛 业务指标拨付率 float/Decimal 混算 TypeError → 统一 float",
            "🐛 cache-stats 调用不存在的 RedisAdapter.get_stats → 适配器补齐统计/健康方法",
        ],
    },
    {
        "version": "1.11.3",
        "date": "2026-08-31",
        "description": "麒麟版后端启动 ModuleNotFoundError 根治",
        "features": [
            (
                "🐛 冻结包内 47 个业务路由模块全部缺失：app/api/v1/init.py 此前用importlib.import_module(f'app.api.v1.{name}') 动态加载"
                "业务路由——PyInstaller静态分析无法跟踪 f-string 动态导入，且 Linux Docker 构建时collect_submodules('app') 依赖的包导入链在收集"
                "阶段被 walk_packages 静默跳过…"
            ),
            (
                "🐛 两个 spec 同源修复：统一 spec 补 sys.path 插入使 collect 与 CWD 无关、移除已删除依赖 sklearn 的 hiddenimports 与陈旧 exc"
                "ludes；standalone spec补 collect_submodules('app')（其此前完全缺失，standalone DEB 同样受影响）。"
            ),
            (
                "🐛 ARM64 postinst：补 onedir 后端主程序 chmod（旧脚本只找 onefile .exe 路径）；chrome-sandbox 补 chown root:root "
                "+ 4755（非 root 用户启动必需）。"
            ),
            "🐛 deb Depends 声明：补 Electron 运行库依赖（libnss3/libgbm1/libasound2 等16 项），麒麟安装时缺失依赖明确报错而非启动后崩溃。",
            "✨ Linux 平台禁用硬件加速 + disable-dev-shm-usage：规避麒麟/飞腾 GPU 驱动白屏/花屏类问题（管理界面无需 GPU 渲染）。",
        ],
    },
    {
        "version": "1.11.4",
        "date": "2026-09-04",
        "description": "异常细节出站收口 + 板块导入 400 根治 + 帮扶村经费持久化修复 + 测试数据目录隔离",
        "features": [
            "🔒 异常细节出站收口（W1 不变量 #6 / W1-T8），共 4 处",
            (
                "🔒 泄露扫描器扩面到 services/、utils/、core/：上述第一处之所以能长期存活，正是因为文本产生在 service 层、出站动作在 api 层，而旧扫描器只扫app/api"
                "/v1 的字面内插，结构上看不见这条间接路径。"
            ),
            (
                "🔒 /health 不再回传迁移异常原文：该端点无需认证，原 migration.error存的是 f\"{type(e).name}: {e}\"，可泄露数据库绝对路径与 SQL 片段。"
                "改为只出异常类名（键更名 error_type，避免后来者误以为它是可读消息而重新放宽），完整细节仅进 logger.error(exc_info=True)。"
            ),
            (
                "🔒 分析统计接口数据隔离改 fail-closed：_get_analysis_data_impl 的current_user 由带 None 默认值改为必填位置参数（对齐 W5-006）"
                "。原写法下_scoped() 内 if current_user is not None 意味着任何新调用方漏传即静默跳过隔离、返回跨组织聚合数据；改必填后漏传在调用点直接 TypeErr"
                "or。"
            ),
            (
                "🐛 帮扶村年度板块导入恒 400：force_investment / party_building 两个板块的内部下划线键被原样透传给后端 section_key，而 _SECTION_"
                "MODEL 的键是连字符（force-investment / party-building）→ 查不到模型 → 400「未知板块标识」。上一轮已为删除路径套上 resolveSectio"
                "nApiKey，导入这条漏了。"
            ),
            (
                "🐛 学校回收站恢复/彻底删除后停在空页（AGENTS.md 前端 BUG 模式 #3）：handleRestore / handlePurge 在 fetchData() 前未重置分页，而"
                "同文件新建/编辑等处理器都有 currentPage.value = 1。用户停在第 2 页及以后时，操作改变了结果集长度 → 刷出空页，看似\"操作没生效\"。"
            ),
            (
                "🐛 截断/损坏权限包导致未分类 500：package_crypto._parse_header 无长度校验，以魔术头 BKPKGv2\\x00 开头但不足 _HEADER_LEN 的上传"
                "文件会让 struct.unpack抛 struct.error；"
            ),
            "🐛 saveSectionData 与 saveYearlySectionData 是完全重复的实现（同一 URL），改为委托调用，既消除重复又自动获得下沉后的映射，避免两处各自漂移。",
            (
                "🐛 监控快照在麒麟/Linux 上整份崩溃并刷 ERROR 日志：system/monitor.py 的get_monitor_snapshot 用 psutil.disk_usage(o"
                "s.environ.get(\"SystemDrive\", \"C:\\\\\"))取磁盘…"
            ),
            (
                "🐛 注册页把后端 400 报文吞成 \"Request failed with status code 400\"：Register.vue 的 catch 只读 error.respon"
                "se?.data?.detail，但注册失败多走BizValidationError → AppError handler 返回 {code,message,success} 信封（无 d"
                "etail 字段），取值落空后回退到 axios 默认英文原文…"
            ),
            (
                "⚡ 异步端点阻塞事件循环收口（性能），共 5 处：psutil.cpu_percent(interval>0) 是阻塞采样（内部 sleep(interval)），却在 async def"
                " 端点里直接调用，每次请求冻结整个事件循环 0.2–1s，拖慢所有并发请求（麒麟多用户下尤甚）。"
            ),
            (
                "🐛 跨平台磁盘路径同源缺陷一并扫清：监控快照工单里的 os.environ.get(\"SystemDrive\", \"C:\\\\\")硬编码回退是复制粘贴扩散的，除 monitor."
                "py 外还存在于 system/metrics.py(×2，另含 disk_usage(\"/\")统一为跨平台表达式)、system/health.py(shutil.disk_usag"
                "e，Linux 上被 try 吞成 disk_free_gb恒 None…"
            ),
        ],
    },
    {
        "version": "1.11.5",
        "date": "2026-09-05",
        "description": "通行码注册大小写归一化 + 功能全链路探针验证 + 覆盖率根因修正收尾",
        "features": [
            (
                "🐛 帮扶村年度数据「校验」端点被动态段吞掉（恒 400 未知数据分类）：路由注册顺序缺陷——POST /supported-villages/{village_id}/yearly/{ye"
                "ar}/validate 声明在动态段POST …/yearly/{year}/{section} 之后…"
            ),
            (
                "🐛 经费拨付被文档要求锁死（前端上传缺陷）：经费「拨付」前置要求附件类别合同(contract)/分配令(allocation_order)，但经费详情附件上传把 category 塞进F"
                "ormData（后端该参数为 Query）→ 恒落 other；"
            ),
            (
                "🐛 回收站恢复项目后仍不可见（真实缺陷）：项目软删时 status 被置为cancelled 作回收站标记（projects.py delete 流程），而 recycle_bin 通用工"
                "厂的restore 只回置 is_active/deleted_at —— 恢复后的项目仍被默认列表（status != cancelled 过滤）隐藏…"
            ),
            (
                "🐛 注册响应缺失 refresh_token（与 LoginResponse「注册即登录」契约不一致）：/auth/register 返回 access token 却不发 refresh"
                "，前端「记住登录」持久化 refresh分支对注册会话恒缺失、API 契约与 /auth/login 不对齐。"
            ),
            (
                "🐛 大写输入的通行码被误拒（注册提示「通行码无效或已被使用」）：通行码为小写十六进制（自动生成）或纯数字（手动 4 位），但 verify_pass_code 与库内列按 SQLite 二"
                "进制比较，用户以大写输入（图片 OCR、手动录入习惯、第三方工具转写）时本属同一通行码却被判无效。"
            ),
            (
                "🔧 前端覆盖率 88.23% 门禁红因的最终定论与根治（含 CI 红→绿的完整实测链条）：LoginEnhanced.vue 全量跑 functions 88.23% 与 Node 版本无"
                "关（Node24 CI 复现完全一致；Windows/Node25 恒绿系 OS 间 v8 函数 id 顺序差异，本地绿不作为放行依据）。"
            ),
        ],
    },
    {
        "version": "1.11.6",
        "date": "2026-09-06",
        "description": "深度探测循环（9 轮）+ 并发竞态修复 + E2E 套件入 CI 门禁",
        "features": [
            (
                "🐛 组织通行码注册后新用户无法登录（阻断级）：组织通行码记录的machine_code 是占位串（ORG-<org>-<rand>），activate_machine_code 只置act"
                "ive+user_id 不改绑 → 登录侧 verify_user_machine 按\"记录.machine_code ==当前真实机器码\"比对恒 False。修复：激活时改绑为注册机"
                "真实机器码。"
            ),
            (
                "🐛 data-sync 数据包下载恒 400/404（路径双源）：下载端点用相对Path(\"data_sync\")，导出服务写 get_app_data_dir()/data_sync"
                " → 打包环境必分叉。修复：下载改用 data_sync_service.sync_dir 同源。"
            ),
            (
                "🐛 报表模板下载/上传确认 500 + 静默零写入：fields 允许任意字符串（逗号串/字符串数组/dict 数组三种历史形态），下载与 _parse_template_excel均假定"
                " dict 数组 → AttributeError 500；且字符串形态缺 db_field 时解析出{'': value} → 确认导入零写入（比 500 更隐蔽）。"
            ),
            (
                "🐛 奖学金导入全链坏死（阻断级，无测试覆盖致长期存活）：按ScholarshipStudent(name/student_id/school_name) 构造，真实列是student_na"
                "me + 必填 school_id FK → 每行必抛 TypeError、imported 恒 0。修复：按真实列映射（学校名查 School 解析 school_id，学号并入 rem"
                "arks），学校解析带 is_active 过滤。"
            ),
            (
                "🐛 乡村工作悬挂 village_id → 裸 500：外键目标是遗留 villages 表（前端下拉由 /rural-works/villages 按名称 upsert 同步），传入不存"
                "在 id 触发未处理IntegrityError。修复：服务层前置校验（create/update）+ 路由转 400 带指引。"
            ),
            "🐛 并发备份同毫秒唯一键冲突 → 500：文件名/config_key 毫秒后缀在并发同毫秒下仍相撞（三并发实测一个 500）。修复：追加 uuid4 短码。",
            (
                "🐛 通行码注册并发竞态 → 创建 2 个用户：verify（读 pending）→建用户→activate（写）非原子，双并发注册均通过。修复：activate_machine_code "
                "改单条UPDATE 原子认领（rowcount 判定），认领失败删除刚建用户并 400。"
            ),
            (
                "🐛 覆盖率墙钟黑洞（CI #84）：/backup/schedule 的\"已过 02:00 则 +1 天\"分支内联端点，是否执行取决于测试运行的墙钟 → CI 覆盖率随机差 1 行。修"
                "复：提取 _next_daily_2am 纯函数 + 三固定时间确定性测试。"
            ),
            (
                "🧪 Playwright E2E 套件复活并纳入 CI 门禁：死代码清理曾误删 helpers.ts（8 个 spec 导入即崩）+ global-setup 密码过期 + 首登强制改密未"
                "适配（改密PUT 为 CSRF 保护路径需先取 csrf-token 配对）+ 5 个 spec 选择器腐化。"
            ),
            "🧪 并发探针（多线程真实 HTTP，12/12）：同记录 10 并发写、审批竞态、并发备份、通行码竞态、并发导入全部符合预期语义。",
            "🧪 前后端契约交叉核对：导出后端 797 条路由，正则通配匹配前端 334 个去重调用路径 → 0 处真实断裂。",
            "📚 帮助文档修正出厂密码描述（Admin@2026）+ 新增管理员出厂恢复通道说明；ADR-0008 扩展章节；AGENTS.md 路径双源规则与覆盖率不变量补记。",
        ],
    },
    {
        "version": "1.11.7",
        "date": "2026-09-06",
        "description": "探测循环收官：探针资产固化 + 发布物供应链核验",
        "features": [
            (
                "🧪 全链路探针固化：9 轮深度探测的真实 HTTP 探针（200+ 断言，30+ 模块）收编为常驻回归资产 backend/tests/probe/（run_all.py 总运行器，独立子"
                "进程+ 独立临时库，pytest 零收集不影响套件），固化后全量复跑 9/9 PASS。"
            ),
            "📋 工单 003：报表订阅为半成品（可创建、无生成/送达消费方）——三方案决策项挂起待产品拍板（A 调度+站内送达 / B 手动生成 / C 收起入口）。",
            (
                "🔐 v1.11.6 发布物供应链核验：三件套（exe/electron deb/standalone deb）从 Release 下载实物逐一比对 SHA256SUMS——全部 MATCH"
                "。"
            ),
            "本版安装包内容与 v1.11.6 构建一致（两次 tag 之间仅测试/文档变更），重新构建以使 Release 指向包含探针资产与全部修复的最新 main。",
            "真机 UI 安装抽验仍建议人工执行一次。",
        ],
    },
    {
        "version": "1.11.8",
        "date": "2026-09-06",
        "description": "🐛 跨机器注册阻断级修复（生产双机实测反馈）：通行码自验证启用 + 组织通行码确定性化",
        "features": [
            (
                "🐛 机器特定通行码跨机器注册 100% 失败（阻断级，生产双机实测）：管理员在A 机\"机器码管理\"为 B 机机器码生成通行码后，用户在 B 机注册恒报\"通行码无效或已被使用\"。根因"
                "：跨机器注册唯一不依赖共享数据库的通道——HMAC 自验证（level 4）被 W1-T6 fail-closed 门关闭…"
            ),
            (
                "🐛 组织通行码跨机器注册 100% 失败（同根因）：组织通行码为随机数且仅存于管理员本地库，下级单位机器 level 2（DB 匹配）永远查不到。修复：①通行码按单位名确定性派生（gene"
                "rate_org_pass_code，重复生成幂等，同组织 pending 记录复用避免 UNIQUE 冲突）；"
            ),
            "注册页新增\"单位名称\"选填框（组织通行码跨机器注册时填写）。",
            "注册失败提示更新：明确组织通行码需填单位名称、机器通行码需提供本机机器码。",
            (
                "已有部署升级本版后，此前生成的机器特定通行码立即恢复可用（HMAC 自验证用内置常量密钥重算，历史通行码格式未变）；此前生成的随机组织通行码仍仅限同库使用——跨机器请由管理员在「组织通行码"
                "」重新生成（确定性，内容不变则重复生成同值）。"
            ),
        ],
    },
    {
        "version": "1.12.0",
        "date": "2026-09-06",
        "description": "🎨 UI 全面优化：字体统一 + 40px 舒适密度 + 布局标准化 + 认证页统一",
        "features": [
            (
                "🔒 事务层把 SQLAlchemy 异常原文内插进响应（W1 不变量 #6 违规）：app/core/transaction.py 的 8 处 raise DatabaseError(f"
                "\"...: {str(e)}\")（TransactionManager.transaction / transactional / run_in_transaction /nested"
                "_transaction / savepoint / _execute…"
            ),
            (
                "🔒 8 个端点把「关联 ID 不存在」报成 500/503：R22 对全部 33 个带 *_id字段的 POST 端点做外键扫射，发现 /funds、/funds/apply、/fund-"
                "budgets/transactions、/fund-lifecycle/allocation-orders、/organizations、/policies/categories、/pr"
                "ojects、/user-management在传入不存在的关联…"
            ),
            (
                "🔒 2FA 中间态令牌可当正式令牌用（认证绕过，高危）：/auth/login 在双因素挑战分支下发的 temp_token 由 create_token_pair(..., extra_"
                "claims={\"two_factor_pending\": True}) 生成，其 type 仍是 \"access\"；而认证唯一出口get_current_user 只校验黑名单与"
                " token 类型，未校验该中间态声明。"
            ),
            (
                "🔒 备用恢复码可无限复用（backup_codes 消费从不落库）：two_factor_auth.backup_codes 是裸 Column(JSON)，TwoFactorServic"
                "e.verify_login 用list.remove(token) 就地修改 —— SQLAlchemy 对裸 JSON 列的就地修改不产生attribute 事件、不生成 UPDATE"
                "，safe_commit 静默无效。"
            ),
            (
                "🔒 前端依赖审计阻断修复（CI security job 变红）：新增公告GHSA-2883-xcg3-v3hh（js-yaml 4.0.0–4.3.1，High，maxTotalMerg"
                "eKeys 对空合并源不限 CPU）触发 npm audit --audit-level=high 非零退出，导致 PR Checks 的security job 失败（其余五 job 全"
                "绿）。"
            ),
            (
                "🐛 合同附件覆盖用户备注 / 改备注清空附件（合同管理）：合同附件此前被序列化成 JSON 整体写进 fund_contracts.remarks —— 而 remarks 正是用户在「新"
                "建合同」表单里填写的备注列。R21 探针实证三种后果：① 上传第一个附件即静默覆盖用户已填写的备注（甲方要求分三期付款… 被 [{\"url\": …}] 取代，原文不可恢复）；"
            ),
            (
                "🐛 合同/划转凭证关联不存在的项目或经费时报 500：POST /fund-lifecycle/contracts与 POST /fund-lifecycle/transfer-vouch"
                "ers 直接 INSERT，未先验关联对象存在性…"
            ),
            (
                "🐛 无项目合同的详情恒 400（同资源两种口径）：ContractCreate.project_id与 TransferVoucherCreate.project_id 均为可选（前端从菜"
                "单进入合同管理时route.query.project_id 缺失），这类记录能创建、能更新、能删附件，但详情端无条件调 _get_project_or_403 → 恒 400「缺少有效的"
                "项目ID，请从经费列表中选择具体项目进入」。"
            ),
            (
                "🐛 同机第二个用户注册必挂（组织/自验证通行码跨机器注册 100% 失败）：机器码记录 machine_code 为 UNIQUE 列，而 activate_machine_code 在激"
                "活时无条件把记录改绑为注册机真实机器码 —— 本机已有首条记录（首用户注册留下）占用该机器码时抛 IntegrityError: UNIQUE constraint failed:mach"
                "ine_codes.machine_code…"
            ),
            "✨ 报表订阅闭环（工单 003 方案 A+B 落地）：此前订阅可创建但无任何消费方（无调度、无生成、前端无 UI），创建后静默无产出。现补齐",
            (
                "中文字体栈统一至 tokens 单一来源（PingFang SC + Microsoft YaHei 入栈），删除 index.scss 与 App.vue 两处重复 font-famil"
                "y 声明"
            ),
            (
                "EP 排版变量显式化：--el-font-family/--el-font-size-base: 14px 走令牌，输入框与正文同源同渲染--table-row-height 44px、e"
                "l-config-provider size=large；"
            ),
        ],
    },
    {
        "version": "1.12.2",
        "date": "2026-09-11",
        "description": "🐛 R19–R31 深度探针修复 + 架构评估 P0 加固（导出/备份/迁移门禁）+ CI 前端门禁回归修复",
        "features": [
            (
                "A1 导出任务重启自愈：recover_stale_export_tasks 在 lifespan 启动时把pending/processing 僵尸导出任务置为 failed，不再依赖内"
                "存队列重启自愈（重启后任务永远停在\"进行中\"是用户可见的假状态）。"
            ),
            (
                "A2 导出/备份原子落盘：产物先写 .part 临时文件、成功后os.replace 原子替换；进程中途被杀（断电/强杀，捕获不到异常）不再在导出/备份目录留下半截文件被列表/cleanu"
                "p 当作有效产物。"
            ),
            (
                "C1 备份可恢复性校验：备份落盘后校验 zip CRC（testzip）+库文件 PRAGMA integrity_check，不可恢复即 fail-loud 抛BackupIncompl"
                "eteError 并删包 —— \"备份成功但还原时才发现损坏\"是最坏故障模式（帮扶数据不可再采集）；"
            ),
            (
                "F1 迁移单 head 门禁入 CI：scripts/check_migrations.py 校验 alembic 单 head 并接入pr-checks 的 static-analysi"
                "s（历史上 MultipleHeads 分叉曾使打包版启动即崩）。"
            ),
            (
                "🐛 数据上报的 report_type 必填却从不落库（静默丢弃）：R29 探针实测 ——POST /api/v1/data-reports 带 report_type=\"monthly"
                "\" 创建成功（201），但响应里report_type 是空串：请求模型 DataReportCreate.report_type 是必填字段、响应模型 DataReportRespon"
                "se 也回显该字段…"
            ),
            (
                "🐛 数据包 data_types 双重编码（版本变更摘要键变成单字符）：R28 探针实测 ——POST /data-packages/{id}/versions 返回的 changes 竟"
                "是json{\"[\": {\"added\": [], \"modified\": [], \"deleted\": []},\"\\\"\": {\"added\": [], \"mo"
                "dified\": [], \"deleted\": []},\"v\": {\"added\": [],…"
            ),
            (
                "🐛 通用文件上传：category 只认查询参数（表单字段静默失效）+ 全量读入内存：R26 探针实测两处 ——① POST /files/upload 带 category=polici"
                "es（multipart 表单字段，即el-upload 的 data/:data 形态）返回 200 但文件落到 generic/ 而不是generic/policies/：catego"
                "ry 被声明为裸 Optional[str]…"
            ),
            (
                "🐛 组织创建/更新的非法枚举值报 500（安装包验收发现）：对刚构建并安装的MRRS-Setup-1.12.1 实例发真实请求时命中 ——POST /api/v1/organization"
                "s {\"name\":\"…\",\"level\":\"1\"} →500 {\"code\":500,\"message\":\"服务器内部错误\"}。"
            ),
            (
                "🐛 「驳回 → 重新提交 → 审批通过」后经费永远停在「已驳回」（审批闭环断裂）：R23 探针在真实 HTTP + 真实 DB 上实测：fund=23 task=17 初始 : task="
                "pending fund=pending驳回 → 200 : task=rejected fund=rejected ✓重新提交 → 200 : task=pending fund=rej"
                "ected ✗ 经费没回到待审批审批通过 → 200 : tas…"
            ),
            (
                "🐛 认证出口在「直接调用」路径下崩溃（潜在 500）：get_current_user 在 P1-2性能优化（改用 db: Session = Depends(get_db) 复用注入会话"
                "）后，两个直接调用路径不再发生依赖注入，db 退化为 Depends(get_db) 默认哨兵对象，db.query(...) 抛 AttributeError: 'Depends' ob"
                "ject has no attribute 'query'"
            ),
            (
                "🐛 帮扶村「新建成功却看不到新记录」：列表端点 GET /supported-villages固定 order_by(SupportedVillage.id) 升序，新建记录 id 最大、"
                "落在最后一页；而前端新建成功后将分页重置到第 1 页 → 新记录不可见。同时前端部门列sortable=\"custom\" 会下发 sort_by/sort_order，但后端从未声明这"
                "两个参数，排序被 FastAPI 静默丢弃。"
            ),
            (
                "🐞 CI 全红：vitest 半升级（v5 + coverage-v8 v3）打穿 postinstall 补丁：frontend/package.json 把 vitest 提到 ^5."
                "0.0，而 @vitest/coverage-v8 仍停在^3.2.7（peer 不匹配）；"
            ),
        ],
    },
    {
        "version": "1.12.3",
        "date": "2026-09-12",
        "description": "🛡️ 架构评估 P1/P2 整改（迁移单轨化 / 恢复演练 / CSRF ASGI 化 / 启动拆包 / 修复引导页）+ 安装包无测试门禁",
        "features": [
            (
                "F1 迁移单轨化第一步：ENABLE_AUTO_MIGRATION 默认值 True → False（core/config.py），schema 变更统一走编程式 Alembic upg"
                "rade（生产环境 fail-loud）。双轨制是唯一发生过真实事故的技术债（commit 4c1ea8a0 MultipleHeads 打包实例启动失败）；应急时仍可临时设 ENABLE"
                "_AUTO_MIGRATION=true。"
            ),
            (
                "C1 月度备份恢复演练：新增 restore_drill_service —— 把最新备份真实还原到临时目录（unzip 落盘）跑 PRAGMA integrity_check +核心表抽"
                "查，只读演练不触碰生产库；restore_drill_job 每日 05:45检查到期（restore_drill_interval_days，默认 30）执行，失败向管理员发消息；"
            ),
            (
                "E1 CSRF 中间件纯 ASGI 化：从 BaseHTTPMiddleware.dispatch 改写为call(scope, receive, send)（逐分支一致），消除注释自认的"
                "h11 协议错误风险——\"开=带病、关=裸奔\"两难解除，CSRF 可常开；get_client_ip 同步改为 scope 版（fail-closed 代理透传语义不变）。"
            ),
            (
                "B1 数据域过滤下沉服务层（Phase 1）：新增 services/data_scope_query.py统一入口（scoped_query / scoped_filter / scop"
                "ed_count，语义单一真源仍是 core/data_permission.py），迁移评估点名热点data/data/reports.py；security_audit 扫描器同步识别"
                "新入口名，回归防线保留。其余 ~40 调用点按批迁移。"
            ),
            (
                "B3 启动钩子拆包：main.py 987 → ~710 行。14 个启动/停止钩子迁至app/startup/{recovery,seed,environment,monitors}.p"
                "y（逐字搬移），main 以同名别名 re-export，from app.main import _xxx 与patch(\"app.main._xxx\") 全兼容；"
            ),
            (
                "A3+C2 Electron 修复引导页：新增 electron/recovery.html —— 后端连崩 3 次超限、或页面加载耗尽 5 次重试时，加载引导页（一键重启后端 +打开诊断"
                "/应用日志），替代原先\"错误框后静默放弃/死屏\"；IPC 通道recovery-*，preload 经 contextBridge 暴露，一键修复成功自动返回系统。"
            ),
            (
                "F3 Electron 版本单一来源：appVersion 改用 app.getVersion()（打包元数据由根 package.json 注入），删除硬编码 fallback 字面量，"
                "读取失败回退为空 + 告警，不再与 PROJECT_VERSION 双源漂移。"
            ),
            (
                "spec 剔除三方库测试资产：实测 sklearn 经 collect_data_files 把sklearn/datasets/tests/（openml 夹具 80+ 文件）带入产物；"
                "assistance-backend.spec 新增 _strip_test_data_toc 统一过滤a.datas 中所有 tests//test/ 目录。"
            ),
            (
                "CI 双重门禁：新增 scripts/verify_package_no_tests.py（文件树扫描 + PYZ 模块检查 + 前端产物抽查，任一违规 fail-loud），接入 bui"
                "ld-windows 的 onedir 验证步；electron-builder 打包后经 7z列举安装包内容抽查测试内容。"
            ),
            (
                "extraResources 过滤兜底：backend 产物拷贝 filter 显式排除tests/、test_*.py、conftest.py、pytest.ini、.coverager"
                "c。"
            ),
            (
                "版本号全量对齐 1.12.3：整改提交只把根 package.json 提到 1.12.3，其余 9 处仍是 1.12.2（config.py / version.txt / README"
                " / docker-compose.yml、docker/Dockerfile.kylin-standalone / frontend/src/config/constants.ts / "
                "frontend/.env.example、.env.examp…"
            ),
            (
                "后端覆盖率门禁回 100%：整改引入的 6 行未覆盖（backup_scheduler.py 484-485 / 493-494、restore_drill_service.py 121 "
                "/ 184）以行为断言补齐（tests/unit/test_restore_drill_gaps_v123.py，新增 6 例），而非 pragma 豁免。"
            ),
        ],
    },
    {
        "version": "1.12.4",
        "date": "2026-09-12",
        "description": "🛠️ Windows 出包门禁编码缺陷修复 + B1 数据域下沉全量收口",
        "features": [
            (
                "根因：scripts/verify_package_no_tests.py 输出中文，而 windows-2022（en-US）上 Python 对管道的默认 stdout 编码是 ANS"
                "I 代码页 cp1252 ——第一个 print 即抛 UnicodeEncodeError，步骤以 exit 1 结束。"
            ),
            (
                "修复：① 脚本内强制 sys.stdout/stderr.reconfigure(encoding=\"utf-8\",errors=\"replace\")；② build-window"
                "s.yml 的 build-windows 任务级加PYTHONUTF8=1 + PYTHONIOENCODING=utf-8（防止同类事故再发）；"
            ),
            (
                "回归：test_verify_package_no_tests_v123.py 新增 2 例子进程用PYTHONIOENCODING=cp1252 跑真实脚本，分别锁定“干净产物必须 ex"
                "it 0”与“真违规仍必须 exit 1 且打印 ::error::”（编码兜底不得吞掉真问题）。"
            ),
            "出包影响：v1.12.3 的 ARM64 DEB 构建成功、Windows 构建失败；本版重出两包（标签 v1.12.4）。",
            (
                "api 层收口：assessment、data_quality、import_export/export、project_milestones、report_templates、searc"
                "h、villages 共 19 处调用改经services/data_scope_query.scoped_filter（db 形参在核心原语里存在但从未使用，删除为纯等价改写）。"
            ),
            (
                "services 层收口：ai_service(11)、ai/recommendation_service(5)、analytics_service(1)、excel_importer_s"
                "ervice(4)、report_service(1)、async_export_service(5) 共 27 处同步下沉。"
            ),
            (
                "结构性回归（新增 test_data_scope_entrypoint_v123.py，8 例）：① AST 扫描锁定 app/api/ 与 app/services/（除唯一入口模块）不"
                "得再出现核心原语引用 —— “新写路由又绕过统一入口”会在 CI 立刻失败；"
            ),
            (
                "并修正批量迁移后失效的 19 处测试 patch 目标（app.api.v1.search.filter_by_data_scope / patch.object(mod, ...) 等）"
                "——它们在代码改名后会直接抛 AttributeError。"
            ),
        ],
    },
    {
        "version": "1.12.5",
        "date": "2026-09-12",
        "description": "🔒 深度审计加固（目录穿越 / 存储型 XSS / 并发 / 备份 fail-loud）+ D1 写锁退避重试",
        "features": [
            (
                "core/upload_security.sanitize_filename：原实现仅替换 <>:/\"|?* 而保留 \\。Windows 下 \\ 与 / 同为路径分隔符，..\\.."
                "\\evil.zip 经Path(upload_dir) / name 拼接后越界写出（目录穿越）。"
            ),
            "api/v1/data_sync._safe_filename：在 sanitize 之后再 Path(...).name 兜底一次，保证任何平台语义下都无分隔符残留。",
            (
                "api/v1/supported_village.upload_section_attachment：区块附件落在UPLOAD_DIR/sections，而该目录经 /uploads 静态"
                "挂载对外提供（无需鉴权）。新增禁止扩展名黑名单（.html/.htm/.xhtml/.shtml/.svg/.xml/.js/.mjs/.vbs/.hta/.jsp/.php），拦截存储型"
                " XSS；"
            ),
            (
                "api/v1/supported_village.delete_section_attachment：原实现仅删库记录，附件在 /uploads 下永久残留（孤儿文件）；现同步 os.re"
                "move 清理磁盘文件。"
            ),
            (
                "api/v1/system/tasks：_tasks 内存字典无锁 —— 后台任务线程插入、请求线程迭代/删除并发时可能抛 RuntimeError: dictionary changed"
                " size。新增 _tasks_lock，对插入 / 列表快照 / 删除 / 计数全部持锁。"
            ),
            (
                "services/backup_scheduler._run_scheduler_job：loop.run_until_complete 抛异常时原实现跳过 loop.close()，每次"
                "失败泄漏一个事件循环（IOCP/selector fd + 未回收任务）。现将 loop 提到 try 外 + finally: if loop is not None: loop.clo"
                "se()。"
            ),
            (
                "services/db_maintenance.stop_wal_checkpoint_scheduler：停止后未复位 _wal_thread，同进程二次进入 lifespan（测试用 "
                "TestClient / 进程内重初始化）时start_* 会因 _wal_thread is not None 直接返回，WAL 调度永久静默失效。现置回 None。"
            ),
            (
                "services/immediate_backup.trigger_immediate_backup：t.start() 失败（线程资源耗尽）时未释放幂等锁 _triggered_once"
                "，此后所有「关键操作前备份」都被静默跳过。现捕获异常 → 释放锁 → 记日志 → 返回 False。"
            ),
            (
                "api/v1/system/backup._resolve_backup_file_path（新增）：下载/预览/校验/恢复四个入口原先只查默认目录，配置 backup_target_di"
                "r（备份到 U 盘/移动硬盘）后备份「列表可见，但下载与恢复恒 404」——恰是该功能的核心用途。现统一为单一定位函数：优先配置目录 → 默认目录，保留 realpath 前缀校验防 .."
                "/ 逃逸（403）。"
            ),
            "services/backup_service",
            (
                "api/v1/school.import_schools_excel：delete=False 的临时上传副本成功/失败都不清理，每次导入在 %TEMP% 残留一份；现收敛到 finall"
                "y 删除。"
            ),
            (
                "services/permission_package_service：open(file_path, \"rb\").read()→ Path(file_path).read_bytes"
                "()，与契约类型统一、消除资源告警。（事实上的死代码），而 SQLite 单写多读下后台长事务（备份/清理等）与在线写操作争抢写锁时，busy_timeout=10000 用尽即报data"
                "base is locked 且无人重试。"
            ),
        ],
    },
    {
        "version": "1.12.6",
        "date": "2026-09-12",
        "description": "🛡️ 遗留风险治理第一批（P0 调度健壮性 / 启动 VACUUM / multipart 上限 / 备份语义）",
        "features": [
            (
                "services/database_health_service._monitor_loop：last_integrity_check / last_quick_check /last_v"
                "acuum 原以 datetime.min 初始化，首轮条件恒真 —— 「每周一次 VACUUM」实际退化为「每次启动 + 每 7 天」，启动窗口正值前端请求高峰，VACUUM 需要独占锁"
                "造成database is locked 抖动。"
            ),
            (
                "vacuum_database() 改为经 db_coordinator.exclusive_write() 执行，与批量导入等opt-in 长写路径互斥，monitoring 线程不再与"
                "在线写事务互相等待超时。"
            ),
            "services/backup_scheduler：三类调度形态收敛为统一语义 —",
            (
                "调度体提升为模块级函数（_schedule_daily/_schedule_weekly/_schedule_interval），start_backup_scheduler 复杂度回到 "
                "CI 门禁（C901 ≤ 16）以内。"
            ),
            (
                "services/backup_scheduler 新增 chunk_cleanup_job（每 30 分钟）：chunked_upload_service.cleanup_expired"
                "_sessions() 此前全仓无任何生产调用点，客户端 init 后中断（断网/关页面）的会话在 uploads/chunks/ 与内存 _sessions中永久泄漏（单会话最坏 2GB"
                "）。"
            ),
            (
                "services/chunked_upload_service：新增 MAX_SESSIONS=200 会话数量上限，超限按 created_at 淘汰最早会话（连同其分片目录），防异常客"
                "户端循环 init 打爆内存。"
            ),
            (
                "middleware/body_size_limit：原实现对 multipart/form-data 一律放行，而 12 个上传端点均为「先整包 await file.read() 入内"
                "存后校验」——校验只能拒绝请求，不能阻止内存峰值，单请求即可 OOM。现按 Content-Length 分级预检：备份恢复 10GB（对齐端点既有上限）/ 权限包与数据同步 512MB "
                "/ 其余 512MB，超限 413。"
            ),
            (
                "services/backup_service._create_consistency_snapshot：快照失败不再回退「WAL checkpoint + 裸拷贝主库」—— 该回退会丢弃"
                "仍留在 -wal 中未合并的已提交事务，而备份包又能通过 CRC + integrity_check 校验，产出「陈旧但合法」的备份并标记成功。现抛 BackupIncompleteErr"
                "or（宁可当天无可用备份，次日自动重试）。"
            ),
            (
                "cleanup_old_backups / cleanup_by_retention_days：文件删除失败（被下载流/杀软占用）原实现吞异常仍删数据库记录 → 「幽灵备份」永久占盘且 U"
                "I 无法再删。现保留记录（WARNING 日志）等待下次清理重试，清理本身不中断。"
            ),
            (
                "api/v1/auth/users：三个 options 端点的 @cache_result 默认键包含current_user 的 repr（含内存地址），每次请求键都不同 → 缓存命中"
                "率≈0。三处返回内容为与调用者无关的静态数据，键改为固定函数名。"
            ),
            (
                "requirements.txt：为 diskcache==5.6.3 登记 PYSEC-2026-2447 / CVE-2025-69872（上游无修复版本）及本仓 JSONDisk 应"
                "用层缓解说明。"
            ),
            (
                "测试基建：tests/unit/test_pragma_reason_ratchet_f2.py 的 subprocess.run(text=True)在 Windows GBK 管道下必"
                "现 UnicodeDecodeError（_readerthread 线程异常 →3 例失败 + 4 条 warning）…"
            ),
        ],
    },
    {
        "version": "1.12.7",
        "date": "2026-09-13",
        "description": "🛡️ 遗留风险治理第二批（R2 上传体积上限 / R5 导出回收 / R9 导入拒绝记录 / R13 Windows CI 可见性）",
        "features": [
            (
                "新增 utils.upload_helper.read_upload_with_limit(file, max_bytes, ...)：分块读取（1MB/块）+滚动累计字节，超限即停并抛 "
                "413；status_code/error_detail 可保持既有接口语义（如头像 400「头像文件不能超过 2MB」）。"
            ),
            (
                "原写法先把 SpooledTemporaryFile 整包物化进内存再比较长度，校验只能拒绝请求、挡不住内存峰值（单机离线部署下单请求即可 OOM，整库应用不可用）。中间件的Content"
                "-Length 分级预检不变，本层补足端点内真实上限与「短读即 EOF」语义。"
            ),
            (
                "新增 zip_total_uncompressed_size(zf) / ensure_zip_within_limit(zf)（解压后总量 ≤ 200MB）与 read_zip_memb"
                "er(zf, name)（按 ZipInfo.file_size 预检后限长读取）…"
            ),
            (
                "policy_import_service 此前完全无上限：补 10MB 体积上限（分块读取）+ 1000 行上限，口径与 data_validator_service（10MB/1000"
                " 行）对齐。"
            ),
            (
                "新增 async_export_service.purge_expired_exports(db) + 调度作业 export_purge_job（每日 04:00）：expires_at"
                " < now 且非 pending/processing 的任务删除文件并标记expired（记录保留供审计、file_path 置空）；同时回收导出目录 mtime 早于 24h 的*."
                "part 半成品（A2 原子落盘后强杀残留）。"
            ),
            "此前 expires_at 只用于拒绝下载，无任何回收逻辑：exports/ 目录随使用频率单调增长。",
            (
                "DataPackageService.import_package 校验失败分支不再落 file_path——该路径是 API 层临时文件，调用方 finally 立即 unlink，落库"
                "后记录永久指向不存在文件（/validate、/download 恒报「文件不存在」且无修复路径）。_create_package_record 支持 NULL 路径。"
            ),
            (
                "/data-packages/{id}/validate、/{id}/download 对 file_path 为空返回 409（明确「已被拒绝（校验失败）」语义）；有路径但磁盘缺失仍为 "
                "404。"
            ),
            (
                "顺带修复真实缺陷：PackageStatusEnum 成员为大写 FAILED，原 PackageStatusEnum.failed在校验失败分支必抛 AttributeError → 被"
                "端点兜底成 500「导入失败」，用户看不到真实校验原因（既有单测用 patch 掩盖了该缺陷，已改为断言真实行为）。"
            ),
            (
                "pr-checks.yml 新增 windows-smoke 作业（windows-latest，PYTHONUTF8=1 +PYTHONIOENCODING=utf-8）：跑编码/句柄/"
                "路径敏感子集（pragma ratchet F2、安装包无测试校验、备份路径对齐、数据同步路由、帮扶村上传）+ flake8 app/ --max-complexity=16。"
            ),
            "R7 恢复窗口与在途写请求竞态（P1）计划列为 W3–W4（10-09 前），需改造 get_db依赖注入与在途请求计数，不在本批次实施。",
            (
                "R12 剩余项（os._exit 优雅退出、_tasks 过期清理等）同列 W4。test_data_package_rejected_r9.py（8 例）。404→409、导入体积门禁从"
                "「事后校验」改为「分块读取前置」。"
            ),
        ],
    },
    {
        "version": "1.12.8",
        "date": "2026-09-13",
        "description": "🛡️ 遗留风险治理第三批（R7 恢复维护窗口 / R12 低危批量 / R2 残余无界读取 / P-1~P-3 预防门禁）",
        "features": [
            (
                "新增 app/core/maintenance.py 维护模式闸门与 MaintenanceGateMiddleware：恢复入口置位 → 新的写请求立即 503（读请求放行）→ 等待在途"
                "请求归零（上限 10s，与 db_coordinator.exclusive_write 同口径，超时记 ERROR 后继续）→ finally 解除。"
            ),
            (
                "BackupService.restore_backup 外层包维护窗口，返回值新增 maintenance_window_ms。原实现只有 engine.dispose()（仅回收空闲连"
                "接），在途小写事务不经exclusive_write：Windows 上覆盖复制必抛 PermissionError，POSIX 上写入被替换的旧 inode —— 恢复后静默缺失一段已提"
                "交事务且无任何报错。"
            ),
            "/health 暴露 maintenance {active, reason, since, last_window_ms, last_waited_ms}。",
            "R12-2 慢请求/慢 SQL 计数器改互斥自增（裸 += 并发丢计数），统计快照加锁读。",
            (
                "R12-3 RESTORE_DRILL_STATUS 改一致性快照（snapshot_status() + RLock），/health 不再逐字段读模块字典（与演练线程的逐字段写交错会产"
                "出撕裂结论）。"
            ),
            "R12-4 审批提醒 stop() join 上限 1s→5s，超时后不复位 _running —— 否则紧随的 start() 会再起一个扫描线程（提醒重复创建、DB 连接翻倍）。",
            (
                "R12-5 /system/shutdown 与 /system/restart(win32) 不再 os._exit(0)：改 raise_signal(SIGINT) 走 lifesp"
                "an 优雅关闭（调度器 Timer、提醒线程、任务队列、WAL checkpoint、.part 半成品回收不再被跳过）。"
            ),
            "R12-6 内存任务表 _tasks 增加 1 小时终态回收（创建/列表/统计/运行计数四处触发），长跑桌面端不再单调增长。",
            (
                "R12-7 create_background_task 无运行循环时返回 None（不再把任务挂到\"永不 run\"的缓存 loop 上），monitoring_service 的线程"
                "池兜底由死代码变为生效路径。"
            ),
            (
                "data_package_service（5 处 zip 打开点）、permission_package_service（4 处）、data_packages API（2 处）：补 ens"
                "ure_zip_within_limit + zf.read →read_zip_member。此前任何登录用户上传结构合法、解压后数十 GB 的包（压缩炸弹）即可让进程 OOM —— 单"
                "机离线部署下等于整个应用不可用。"
            ),
            (
                "backup_service._verify_backup_recovery：原先把整个库文件读进内存再落盘校验（库可达 GB 级，备份校验自身成了内存峰值点）→ 改为 1MB 分块流式解"
                "压落盘。"
            ),
            (
                "分片上传端点：await file.read() → read_upload_with_limit（20MB）；合并阶段整文件读算 MD5 → 1MB 分块流式摘要（单会话上限 2GB）。"
                "未落库（NULL）；而组织级数据权限完全依赖 path 前缀匹配（OrganizationPermissionService.can_access_organization → get_s"
                "ubordinate_ids→ Organization.pat…"
            ),
        ],
    },
    {
        "version": "1.12.9",
        "date": "2026-09-30",
        "description": "🛡️ 深审缺陷批量修复（越权/数据完整性/静默失效/发布门禁）",
        "features": [
            (
                "审计日志批量删除 fail-closed（system/audit.py）：非法 before_date 原先只warning 后\"忽略日期过滤\"，配合空动作条件会清空整张 audit"
                "_logs。现在入口 422、路由层 400，两条回归锁定\"非法日期一条都不删\"。"
            ),
            (
                "错误报告归属校验（system/error_report.py）：原读不存在的 record.user_id→ is_owner 恒 True，任何登录用户可改任意报告；改用真实字段 re"
                "porter。"
            ),
            "报表订阅 IDOR（data/data/reports.py）：/{id}/download 与 /generate 收敛到\"订阅属主或管理员\"，与其余订阅端点同口径。",
            (
                "政策附件路径穿越（policy.py）：写入/预览/下载三处统一做 realpath + commonpath包含性校验，/uploads/../../etc/passwd、绝对路径一律 "
                "400，杜绝任意文件读取。"
            ),
            (
                "数据包三端点补归属校验（data/data/data_packages.py）：preview、decrypt-preview、confirm-import 原先任何登录用户凭 id 即可"
                "预览/解密/落库他组织数据；incremental/import 的 org 缺失改为 fail-closed（不再以 org_id=0 写库）；加密包上传临时文件改 mkstemp（原名"
                "可 ../ 穿越且同秒互相覆盖）。"
            ),
            "项目里程碑全端点数据域守卫（project_milestones.py）：里程碑读写、状态流转、流转规则、变更记录统一走 scoped_filter，不可见即 404。",
            "上报归属校验（data/data/data_reports.py）：submit 原先无归属判断，任何登录用户可把他组织上报提交给其上级。",
            (
                "综合报表导出门禁（import_export/export.py）：补 require_admin，学校/项目/经费的计数、金额与明细全部过 scoped_filter（S2 导出隔离红线"
                "）。"
            ),
            (
                "组织模块策略跨组织读写（org_module_policy.py、control_package.py）：4 个策略端点 + 管控包导入按 assert_org_reachable 校验目"
                "标组织子树，杜绝部门级 admin改他组织策略 / 用编辑过的包跨组织写。"
            ),
            "上传文件名净化（utils/upload_helper.py）：文件名只取基名并过滤分隔符/控制字符，落盘前再做一次\"最终路径必须位于上传根目录内\"的包含性校验。",
            (
                "经费状态机红线（fund_service.py、funds.py）：创建强制 pending（忽略客户端status），更新接口禁止直接改 status（须走审批/拨付端点），软删经费不再"
                "可详情/流转。"
            ),
            (
                "校验规则补管理员门禁（validation.py）：增/改/删三个端点补 require_admin。账号；静态选项端点的权限校验移入路由依赖（缓存命中不再跳过校验）。fail-close"
                "d。setattr（原先可改 role/is_superuser/hashed_password）。审批字段不得经通用更新接口写入，已提交任务禁止直接改 status。（原行为会留下无超管"
                "且不可重入的永久锁死部署）。恢复码写入路径统一校验。"
            ),
        ],
    },
    {
        "version": "1.12.10",
        "date": "2026-10-02",
        "description": "🔧 跨平台 CI 双红根因修复（平台相关穿越判定 / 时区相关断言）+ 测试会话隔离契约",
        "features": [
            (
                "归档恢复的路径穿越判定与运行平台绑定（app/services/data_tier_service.py）：Path(archive_file).name != archive_file "
                "只按运行平台的分隔符解析 —— Linux 上反斜杠不是分隔符…"
            ),
            (
                "审批时间轴排序断言的时区依赖（frontend/tests/unit/utils/approvalTimeline.test.ts）：朴素时间串（无时区）由 JS 按运行环境本地时区解析，"
                "'2026-09-17 10:00:00' 与'2026-09-17T10:00:00Z' 在 UTC runner 上是同一时刻 → 落入稳定排序分支保持输入顺序→ 断言失败（UTC+8"
                " 本地恒绿）。"
            ),
            (
                "Linux 上测试数据根逃逸（backend/tests/conftest.py）：conftest 用BUMOFU_BACKEND_DIR_OVERRIDE 把数据根指向会话临时目录，但"
                " paths.get_app_data_dir()的首分支 is_bundled() or (is_linux() and not BUMOFU_DEV_MODE) 在 Linux 上恒真"
                "…"
            ),
            (
                "新增 backend/tests/unit/test_session_isolation_contract.py（2 用例）：以行为级断言守护该契约（不用源码文本扫描），既能拦住\"漏声明"
                "\"，也能拦住\"声明晚于 app.* 导入\"的时序错位（Settings 在 import 期即完成路径归一）。"
            ),
            (
                "新增 scripts/ci/scan_shared_vue_refs.py：扫描受覆盖率门禁锁定的 .vue 被多个测试文件引用的情况（现状 64 处）。经 CI 注解确认当前并未发作（前"
                "端覆盖率 100%），故保留为潜在风险探测工具，本轮不做重构。"
            ),
        ],
    },
    {
        "version": "1.12.11",
        "date": "2026-10-02",
        "description": "🕐 时间基准统一：报表订阅 next_send_at / 到期派发彻底修复 + 时间转换单一事实源",
        "features": [
            (
                "报表订阅 next_send_at 与到期派发（services/subscription_dispatch_service.py）：新增 next_send_at_utc() 作为唯一计"
                "算入口——把库中 naive-UTC 基准换算成本地墙钟、用本地墙钟做日历运算、结果再换算回 aware UTC 输出。"
            ),
            (
                "列表端点（api/v1/data/data/reports.py）：_subscription_to_response 改走同一入口，next_send_at 输出 aware UTC（此"
                "前输出 naive 墙钟，前端按本地解析会偏早 8 小时、甚至落在过去）。"
            ),
            "调度器（services/backup_scheduler.py）：订阅派发作业改传 utcnow()（aware UTC）。",
            "generate-now 端点：改传 utcnow()，与派发路径同基准。",
            (
                "新增 models.base.UtcDateTime 类型（一处修复、所有出口正确）：库中 DateTime 列落库为 naive UTC，读回也是 naive —— naive 值一旦流"
                "出 ORM，所有消费方都会丢掉「这是 UTC」这一事实：to_dict() 的 isoformat() 不带偏移、FastAPI 的jsonable_encoder 同理，前端 new D"
                "ate(str) 便按本地时区解析…"
            ),
            (
                "全模型接入：app/models/ 下 48 个文件的 195 处 DateTime(timezone=True) 与5 处裸 DateTime 统一改为 UtcDateTime()（含 "
                "TimestampMixin / SoftDeleteMixin）。"
            ),
            (
                "导出通道按本地渲染（避免导出件里出现 UTC 墙钟或 +00:00 文本）：async_export_service._format_datetime 与 excel_report_sty"
                "le._coerce对 aware 值先转本地再格式化。"
            ),
            (
                "清除「本地时间写进 UTC 列」的混用：fund_lifecycle（entered_at / confirmed_at /resolved_at / approved_at）、audit"
                "_service.resolved_at、backup_service.updated_at由 datetime.now() 改为 time_utils.utcnow()。"
            ),
            (
                "isinstance(col.type, DateTime) 识别失效（services/package_record_validator._date_fields）：列类型被 TypeD"
                "ecorator 包装后该判定静默失配，数据包导入不再把support_start_date 识别为日期列、跳过「日期归一 ISO」，脏字符串直达批量入库、整批写入失败（实测 school"
                "s 导入 0/2）。"
            ),
            (
                "backup_service.cleanup_by_retention_days 基准错位：cutoff 原用本地 naivedatetime.now() 与库中时间比较（同一类缺陷里的静"
                "默偏移）；改用time_utils.utcnow() 并对字符串形态的 created_at 统一按 UTC 补齐。"
            ),
            (
                "列表端点的容错：_subscription_to_response 恢复对非法频率的容忍（next_send_at=None），展示侧不得让单行脏数据把整个列表/更新接口打成 500；派发"
                "侧仍保持 fail-loud（计入 failed 并 rollback），两处口径不同是刻意的。"
            ),
            (
                "新增 app/utils/time_utils.py：utcnow / utcnow_naive / as_utc / as_utc_naive /to_local / local_nai"
                "ve / local_naive_to_utc / to_utc / to_utc_naive / now_local，并在模块文档中固化三条约定（存储 naive UTC / 比较同基准"
                " / 调度按本地语义）。"
            ),
        ],
    },
    {
        "version": "1.12.12",
        "date": "2026-10-03",
        "description": "🐞 全库缺陷排查修复（时间基准 / 契约脱节 / 竞态）+ 汇报大屏契约修复 + 冷启动优化 + 前端日期收敛 + 文档与门禁治理",
        "features": [
            (
                "前端日期/时间格式化统一收敛到 frontend/src/utils/index.ts：此前散落在36 个文件里的 41 处\"各自实现\"（含 4 种 locale 变体、3 种手写补零"
                "、5 处字符串切片、相对时间与运行时长各一套）已全部删除，改为委派统一入口。视图层不再持任何格式化逻辑，只保留一行委派（原函数名保留，模板零改动）。"
            ),
            (
                "format 工具集补齐 12 个函数：formatDateTimeLocale / formatLocalDate /formatLocalDate2Digit / formatLoca"
                "lDateTime2Digit / formatDateTimeFull /formatDate / formatCnDate / formatRelativeTime / formatS"
                "hortDateTime /formatShortDateTim…"
            ),
            "统一空值语义：新增内部 toDate() 归一化，空值/非法值一律走兜底文案 ——此前多个页面会把 Invalid Date 直接渲染到界面上（现已不可能出现）。",
            "顺带修正两处\"按 UTC 字符串切片当本地时间显示\"的实现（funds/Detail、sentiment/Index等 5 处）：改用本地时区日期，消除跨日边界差一天的问题。",
            "移除收敛后产生的孤立辅助函数（SettingsOverview 的 pad）。",
            (
                "订正 frontend/docs/design/{components,tokens,pages,hardcoded-colors-report}.md：删除对不存在的 business/"
                "KpiCard.vue、utils/datetime.ts、common/ResponsiveDataTable.vue的引用；全局组件尺寸 small → large；密度令牌更新为 U"
                "I v2.1 实际值（44/40/32/48px）。"
            ),
            (
                "订正 docs/03-开发文档/前后端契约规范.md：删除对从未存在的frontend/src/utils/camelize.ts 的描述，改为说明真实链路（后端中间件 + 模型 to_d"
                "ict，前端不转换）。"
            ),
            (
                "订正 AGENTS.md（CI 六个 job → 七个，补 windows-smoke 行与 static-analysis 检查项）、README.md（Alembic 44 → 45 "
                "版本）、CONTRIBUTING.md（覆盖率 50% → 100%…"
            ),
            (
                "订正 resources/icons/README.md（按实际文件名重写）、backend/version.json（build/release_date/description/fea"
                "tures 更新为 1.12.11）、CLAUDE.md（版本同步 13 处 → 18 处）。"
            ),
            (
                ".env.example 纳入版本单一来源：新增 scripts/sync-version.js 目标，该文件此前长期漂移（停在 1.12.5，落后 6 个补丁版本，因为旧脚本 sync_"
                "version.py覆盖 .env* 而新工具漏了它）。现已同步为 1.12.11，且 --check 门禁覆盖，杜绝复发。"
            ),
            (
                "「项目状态分布」饼图恒空：后端此前不返回任何状态字段，前端读的两个键都不存在。现由 _query_project_approval_stats 增加一条 group_by 查询，返回pro"
                "jects_by_status: {状态: 数量}，前端改读 stats.projects_by_status。"
            ),
            (
                "KPI「完成率」恒显 —：前端读 completion_rate，后端实际字段为 data_completeness（0~1）。现改读 data_completeness 并按百分比 1 "
                "位小数展示。现改读 total_funds。"
            ),
        ],
    },
    {
        "version": "1.12.13",
        "date": "2026-10-05",
        "description": "🛡 R18 全维度排查修复（并发闸门 / 事件循环阻塞 / 竞态互踩 / 信息泄露）",
        "features": [
            (
                "electron/worker-pool.js — Worker 池并发闸门永久失效：_active 被双扣（message 扣一次后 terminate()，而 terminate 的 "
                "exit code 恒为 1，exit 回调再扣一次），计数单调变负使 maxWorkers 形同虚设；超时路径不 terminate()，hang 死任务永久占用槽位。"
            ),
            (
                "api/v1/system/backup.py — 备份阻塞整个事件循环：备份（SQLite Backup API 全库拷贝 +shutil.copytree 上传目录 + zip CRC"
                " 校验 + integrity_check + 可选 PBKDF2 加密）此前在async def 内同步执行，耗时与库体积成正比，期间全部并发请求（含登录、前端轮询）无响应，且 Elec"
                "tron 24h 定时备份同样走此端点。"
            ),
            (
                "api/v1/data_sync.py — 上传临时包同名互踩：沿用客户端原文件名（缺省固定 upload.zip），两个并发导入写同一物理路径——后写者截断前写者正在读取的文件，先到者把"
                "后到者的数据当自己的包导入（静默数据错乱），且 finally 清理会删掉对方刚写入的文件。加 uuid 前缀唯一化。"
            ),
            (
                "api/v1/system/health.py — 无认证端点信息面收敛：/health、/health/overview 此前回显platform.platform()（精确到 OS 构"
                "建号）与 python_version；/database、/database-health异常分支把 str(e) 原文回显（可含数据库路径）。"
            ),
            (
                "electron/main.js — stopBackend 孤儿进程竞态：5s 兜底定时器无句柄且无条件backendProcess = null——进程在 4.9s 退出并立刻重启后，"
                "第 5s 回调会把新进程抹成 null，旧进程对象失去引用成为孤儿（每个持完整 FastAPI 运行时）。现保存句柄、exit 时清理，仅在引用仍为本进程时置空。"
            ),
            (
                "services/backup_scheduler.py — 任务队列记录只增不减：LocalTaskQueue._tasks 的cleanup() 此前全仓无任何调用点，每个异步导出任务"
                "对象（含 func 闭包 / args / result 引用）永久驻留。挂靠既有每日 export_purge_job（04:00）一并回收，不新增定时器。"
            ),
            (
                "api/v1/projects.py：排序列白名单——此前 getattr(Project, sort_by) 接受任意字符串，传入方法/关系名（如 query、metadata）触发 A"
                "ttributeError → 500。"
            ),
            (
                "deploy/kylin/config/kylin.env：部署模板不应自行降级安全基线——ACCESS_TOKEN_EXPIRE_MINUTES2880(48h) → 480(8h)、C"
                "SRF_ENABLED false → true（前端 request.ts 已自动回填 X-CSRF-Token，cookie 缺失时懒加载 /auth/csrf-token，开启不会造"
                "成 POST 失败）。"
            ),
            (
                "出厂管理员密码硬编码 Admin@2026（core/constants.py:24）与机器码初始密码熵不足（用户名前 4 位 + 10⁴ 校验码、/verify-machine-code"
                " 公开可查）——涉军审计最可能开单的两项，改随机生成 + 一次性凭据交付会影响装机流程，须产品拍板。"
            ),
            "备份双事实源：Electron 每 24h 直调备份端点，打穿后端 backup_interval_days（默认 30 天）间隔判定；两套清理并发删同一目录。需先定「到底多久备一次」。",
            "control_package.py 512MB zip 在事件循环内同步解析（解压峰值 GB 级，admin-only）。",
            (
                "data_package_service full 导出逐模型 query.all() + indent=2 全量驻留（内存约库体积 3-4 倍）。/health/database-hea"
                "lth 正常与异常脱敏各 1；定向回归 411 用例全绿。合计 18,252；README / docs/build_ppt.js / 项目文件结构说明.md 同步。"
            ),
        ],
    },
    {
        "version": "1.12.14",
        "date": "2026-10-06",
        "description": "🔍 全库深度排查与修复（数据合并/权限收口/时间基准/健壮性）+ 文档与 PPT 同步",
        "features": [
            (
                "数据同步「智能合并」策略完全失效（services/data_sync_service.py）：_import_table_data（ZIP /data-sync/import 路径）只有"
                " skip/overwrite/manual 分支且无 else 兜底，而前端数据同步页默认策略就是 merge（\"智能合并（推荐）\"）——已存在记录既不被更新、也不计入 succes"
                "s/failed/conflicts，接口仍返回\"导入成功\"…"
            ),
            (
                "加密包合并永不更新（同文件 _should_update_record）：existing 来自 raw text() 查询是字符串，与 parser.parse(...) 得到的 dat"
                "etime 直接比较抛 TypeError，被 except Exception 吞成一条 warning 后恒返回 False。"
            ),
            "政策模块三处前端功能失效（调用了不存在的 store 方法，被 mock 掩盖）",
            (
                "备份计划端点越权（api/v1/system/backup.py）：PUT /system/backup/schedule 只校验\"已登录\"，任何普通用户都能改写全局备份开关/频率/保"
                "留策略（与页面自述\"普通用户只读\"矛盾）。现补 require_admin，前端该面板保存按钮同步加 canOperateBackup 收口。"
            ),
            (
                "出厂口令改值 + 服务端强制首登改密：FACTORY_ADMIN_PASSWORD 由 Admin@2026（10 位、低于自有策略MIN_LENGTH=12、属公开常识值）改为 13 位"
                "混合字符；get_current_user 增加拦截——must_change_password=true时除改密链路（auth/{me,logout,refresh,csrf-token"
                "}、users/me、menus/accessible、仅限改自…"
            ),
            (
                "backup_retention_days 脏值导致备份计划页 500：GET|PUT /system/backup/schedule 裸 int() 解析配置，而通用配置端点/管控包导入"
                "可写入任意字符串。新增 get_int_config（可注入 getter 以保留各模块测试的get_config patch 缝合点）并统一接入备份/调度各调用点。"
            ),
            (
                "last_backup_time 带时区偏移时整条自动备份失败：except ValueError 覆盖不到 naive - aware 的TypeError，异常逃逸为\"自动备份失败"
                "\"/接口 500。新增 time_utils.parse_local_wallclock 统一归一。"
            ),
            "restore_drill_job 在 with get_db_context() 之外使用已关闭会话 发提醒：隐式重开不受 finally管理的连接；现移入 with 块内。",
            (
                "导入包解析加固（同 R18 后续）：data_sync 导入解析下沉线程池 + 解压体积闸门（1GB）+except HTTPException: raise 守住 413 语义；cont"
                "rol-package/import-preview 补 require_admin，畸形 manifest.json（非对象）/非数组成员由 500 改为 valid=false/计 0"
                "。"
            ),
            (
                "工作日历 localStorage 脏数据崩页：setup 顶层裸 JSON.parse 且不校验形态 → SyntaxError 让整条路由渲染失败；现 readStoredEvents"
                "() 兜底空数组（新增专属测试）。"
            ),
            (
                "多个列表端点 limit/skip/page 无边界：limit=-1 在 SQLite 语义下等同\"不限量\"（一次拉全表）。新增 utils/pagination.clamp_off"
                "set_limit 并在 5 个端点接入（rbac/villages/machine-code/feedback/data-sync）。"
            ),
            (
                "BACKUP_COMPRESSION_LEVEL 非数字 → BackupService 构造即抛 ValueError、备份链路整体不可用；提取 utils/env_utils.pars"
                "e_env_int（同时消除 core/database._parse_env_int 的重复实现）并收敛security.ACCESS_TOKEN_EXPIRE_MINUTES（模块导入"
                "期裸 int()…"
            ),
        ],
    },
    {
        "version": "1.12.15",
        "date": "2026-10-08",
        "description": "🔍 R20 全库逐文件代码审查修复（权限收口 / 数据域 / 功能失效 / 健壮性）",
        "features": [
            (
                "report_templates 模块整体无角色守卫：任意登录用户可增删改共享报表模板并触发overwrite 导入（清空数据域记录）→ 模板 CRUD 与上传导入统一收敛 require"
                "_manager_role。"
            ),
            (
                "fund_lifecycle 资金写端点缺数据域：划转凭证（改/删/确认/附件）、合同（改/删/付款）、决算（改/审批）、拨款下达、额度调整/锁定、异常处理共 14 处仅角色校验、裸 id"
                " 加载 →统一补 _get_project_or_403（读端点已有、写端点遗漏的口径矛盾消除）。"
            ),
            "综合报表导出明细越权（async_export_service）：summary 计数已过滤但项目/经费明细裸查全库（各 100 条）→ 补 scoped_filter。",
            "report_templates overwrite 导入非原子（4 个模块 prepare 共性）：先删后插分两次提交，插入失败旧数据永久丢失 → 删除与插入并入同一事务，失败整体回滚。",
            (
                "权限收敛（登录即可见 → 管理员）：system/config/export/json、system/error-reports（列表/统计/详情，含 stack_trace）、secre"
                "ts/status、metrics/business、system/backup/target、zero-trust/events（防伪造安全事件）、health/full（指纹 + in"
                "tegrity_check 重 I/O）、help/articl…"
            ),
            "项目导入：mode=overwrite 参数从未生效（静默变增量）→ 按数据域软删后导入；逐行 SAVEPOINT（首行 IntegrityError 毒化会话 → 连锁失败的缺陷消除）。",
            "项目任务越权：任务更新/删除补 _can_modify_project（同组织非创建者可改删的缺口）。",
            (
                "数据域遗漏：rural_work 统计 by_type / analytics 类登记（后者属服务层签名改造，见报告登记项）；list_backups 未传 backup_type → 增"
                "量备份统计恒 0。"
            ),
            (
                "功能失效：PDF 导出未转义 </&（标题含尖括号即 500）；消息模板 ≥2 个缺失变量二次 format 抛 KeyError；excel_importer convert_row_t"
                "ypes 被当属性引用（类型转换从不执行）；batch_service.batch_export 只写表头不写数据。"
            ),
            (
                "数据正确性：数据清洗误删 SQL 关键字子串（standard→stard）→ 加词边界；audit_service 当日统计窗口用本地 datetime.now() 与 UTC 库值比较"
                "（偏 8 小时）；消息保留 30 天 → 90 天（对齐需求 5.6）；增量备份文件名/键同秒互撞 → 追加 uuid。"
            ),
            (
                "一致性：organization_code 校验允许 -（与生成规则一致）；organization_code 缓存原子取值；村级联删除引用检查收窄裸 except；query_analy"
                "zer _count 键清理。"
            ),
            (
                "upload_security 允许扩展名 .gi → .gif；seed 出厂口令不再写入日志原文；runtime_secrets 密钥文件顶层非对象 JSON 防御；config 密钥"
                "文件读取显式 UTF-8；main.py 死代码 env；audit 模型重复索引；supported_village to_dict 补 transitionStatus。"
            ),
        ],
    },
    {
        "version": "1.12.16",
        "date": "2026-10-14",
        "description": "🔐 安全与权限收敛 + 会话管理落地",
        "features": [
            (
                "用户会话管理真实落地：新增 user_sessions 表（登录/2FA 时登记 jti/IP/UA/有效期），管理端\"查看会话\"返回真实活跃会话，\"强制登出\"支持按会话精确吊销（"
                "不影响其它设备）；未登记会话时退回既有 token_version 全量踢下线语义。新增每日 05:15 过期/吊销会话回收作业。"
            ),
            "角色编码（code）后端权威化：rbac_roles 新增唯一 code 列（迁移回填），前端展示/提交均以后端为准（此前由名称派生，改名即漂移）。",
            (
                "组织数据范围全面收敛：/organizations 列表、/tree、/{id}（越权 403）、/statistics/summary、/export/list、/{id}/member"
                "s 全部按apply_scope_filter 收敛（super_admin 全量；admin/普通用户 → 本组织及子树）——此前任何登录用户可枚举/导出全库组织（军审红线 S2 相关）"
                "。"
            ),
            "修复缓存跨用户泄漏：orgs:list 缓存改为仅管理员启用，否则普通用户的受限结果会写入全局缓存。",
            "删除组织二次确认密码改走 X-Confirm-Password 请求头：查询串会原样进 access log。",
            "组织移动/改父级后 path/level 不级联刷新（树视图与数据权限视图长期背离）；PUT 改父级补防环（此前只拦\"等于自身\"）。",
            (
                "用户管理：组织选择提交 422（树节点 id 前缀未还原）、空邮箱唯一约束 500、编辑改邮箱缺查重、用户名搜索参数被后端静默忽略、删除用户外键 500（接入级联服务）、重置密码错误提示丢"
                "原因、待审核用户按钮死功能接通闭环。"
            ),
            (
                "组织管理：编码框显示 200（信封遮蔽）、无法置为顶级（exclude_unset 语义）、level 双语义显示不一、父级 path 为 NULL 时子级退化成根路径、拖拽排序仅本页未说"
                "明。"
            ),
            "角色管理：关联用户弹窗姓名/邮箱字段错位、查询与分页纯摆设（改前端过滤+切片）。",
        ],
    },
    {
        "version": "1.12.17",
        "date": "2026-10-16",
        "description": "🛡️ R28 全系统排查修复（门禁 / 数据域 / 服务正确性 / 前端与构建）",
        "features": [
            (
                "用户管理数据域收口：/users 列表、待审列表、员工列表三处各自实现子树过滤→ 统一到 _apply_user_data_scope(query, current_user, db)，且"
                " db 改为必填（漏传即 TypeError，fail-closed）；悬空组织退化为只命中本人。"
            ),
            (
                "管理端门禁补齐：/export/villages、/data-sync 下载与冲突/日志、/system-health/overview/disk-space/table-stats、/s"
                "ystem/environment、/monitoring 告警规则与历史、/system/config 全部读端点、/batch/validate（并加表名白名单）、/analytics"
                "/health均收敛为管理员（或登录）可见，非管理员 403。"
            ),
            (
                "回收站批量操作数据域过滤：批量恢复/彻底删除先按调用者数据域收敛 ids（跨组织 id静默剔除）；模型缺组织列时 fail-closed 拒绝全部，杜绝部门级 admin 物理清除他人数据"
                "。"
            ),
            "任务端点归属校验：cancel/delete 限本人或管理员；/tasks/running/count 补认证；task_type 按枚举校验。",
            "工作日志可见性：非管理员仅见本人日志（原实现额外放行所有人的 system_auto自动留痕 → 他人操作流水全员可见）；system_auto 为系统保留分类，禁止客户端创建/改写。",
            "近期活动：/messages/recent-activities 非管理员仅返回本人审计活动（不再回吐全局审计）。",
            (
                "仪表盘近期动态数据域：/dashboard/recent-activities 的项目 / 经费 / 审批三路 feed此前无任何过滤——任意登录用户可读到跨组织项目名、负责人与审批标题（"
                "与上条同类）。现按 get_org_scope 口径收敛；审批任务（模型无组织列）按「我提交 / 待我审批」收敛；只有全量访问者读写共享缓存，普通用户按域现算，绝不命中管理员范围缓存。"
            ),
            (
                "报表导出数据域：公文报告导出（/export/report-word、/export/report-pdf）的generate_*_report_data 六个方法改为强制 current"
                "_user 位置参数（漏传即TypeError…"
            ),
            (
                "错误细节不出站：system_health、system/metrics、/overview 等去 str(e)、数据库绝对路径、表名清单与行数明细，原文只进日志；/encryption/"
                "status 不再回吐 KDF 迭代数。"
            ),
            "匿名反馈长度上限：content ≤ 5000 字（原为无上限 TEXT，可被单请求灌入任意体积）。",
            (
                "令牌刷新携带声明：refresh_access_token 现携带原 refresh token 的非保留声明（含 token_version），修复「刷新后 access token 立"
                "即被判定失效」的 R20 L2 缺陷。"
            ),
            (
                "服务层正确性：审批工作流 approve/reject 改带条件原子抢占（并发/重放零重复落账）；数据包批量 upsert 只更新记录实际携带的列（缺键不再写成 NULL，空更新集合退化为"
                " DO NOTHING）；组织导入两阶段（先 upsert 记源 id→本机行，再对新建行按父链回填 parent_id/path/level，既有行不动）；冲突解决保留双方时后缀唯一化（"
                "uuid）；权限包导入外键重映射；"
            ),
        ],
    },
    {
        "version": "1.12.18",
        "date": "2026-10-17",
        "description": "🎯 门禁说真话 + 现场可自证（P0 批次）",
        "features": [
            (
                "系统诊断包导出（仅管理员）：GET /api/v1/system/diagnostics/summary 返回结构化摘要（版本 / 构建指纹 / 平台 / 数据库健康与逐表行数 / 迁移状"
                "态 / 日志概况 / 资源快照）；GET /api/v1/system/diagnostics/bundle 返回诊断包 ZIP（summary.json + 脱敏日志尾部 +兼容 sha"
                "256sum -c 的 checksums.txt）。"
            ),
            (
                "升级排练门禁：backend/scripts/upgrade_rehearsal.py + PR Checks 新作业upgrade-rehearsal。语义：取最近 v* 标签的旧代码建"
                "出\"老用户库\" → 每张表播一行 →当前代码 upgrade head → 校验\"无表丢失 / 已播种表行数不变 / PRAGMA integrity_check=ok /落在当前 "
                "head\"。"
            ),
            (
                "测试抖动账本：scripts/ci_flake_report.py 解析 pytest-rerunfailures 的 RERUN 行（JUnit XML 不记录重跑），输出逐条清单与计数"
                "；pr-checks 只告警（--warn-reruns 3），nightly 超过 10 次才失败；两份账本作为 CI 产物留存 90 天。"
            ),
            (
                "原始 SQL f-string 豁免门禁：scripts/check_raw_sql_fstrings.py 用 AST 取完整语句范围，要求 text(f\"...\") 所在语句范围内"
                "必须有 # nosec B608 - <理由>；全仓 40 处调用点，本次补登 26 处理由（9 个文件）。"
            ),
            "JSON 列可变性台账：26 个 JSON 列逐列声明语义（25 个\"整体替换\" / 1 个 MutableList），外加\"声明检查 + 就地修改必须落库\"的行为锁定。",
            (
                "100% 分支门禁的随机失败：generate_password 的\"重试直到满足复杂度\"分支概率性未命中，门禁随机变红（会训练团队忽略红线）；改为可控 secrets.choice "
                "替身的确定性用例钉死。"
            ),
            (
                "一项\"修复\"被 CI 证伪后回退（重要教训）：曾给 tests/conftest.py 的 client fixture 加engine.dispose()（StaticPool 一直"
                "持着内存连接，只 close() 会话会留下每条一次ResourceWarning: unclosed database）。"
            ),
            (
                "分片运行的信号噪音：逐片加 --cov-fail-under=0（此前每片都因\"片内覆盖率不满 100%\"返回 exit 2，\"这片的测试到底过没过\"要人肉分辨）；真实门禁仍由末尾"
                " coverage report按 .coveragerc 承载（命令行不重复声明阈值）。"
            ),
            "版本号 1.12.17 → 1.12.18（node scripts/sync-version.js --check 15 处一致）。",
            "PR Checks 作业数 7 → 8（新增 upgrade-rehearsal）；static-analysis 增补原始 SQL 豁免门禁。",
        ],
    },
    {
        "version": "1.12.19",
        "date": "2026-10-17",
        "description": "🧩 功能补全 + 数据完整性修复（W17/W18 批次）",
        "features": [
            (
                "提醒中心处置闭环：POST /reminders/{id}/handle|ignore|snooze|reopen（仅提醒接收人本人，越权/不存在一律 404），新表 reminder_d"
                "ispositions（迁移 reminder_disp_001）；"
            ),
            (
                "结对帮扶与走访台账：pairing_records + visit_records（迁移 pairing_001），主体（单位/支部/干部个人）↔ 对象（村/学校/学生）结对 + 走访明细"
                "（时间、人员、事项、附件、可选关联项目/经费/物资）；前端 views/pairing 列表与详情、村/学校详情深链入口（/pairings?partner_type=village|sc"
                "hool&partner_id=N）。"
            ),
            (
                "捐赠物资台账（后端）：donation_items（迁移 donation_item_001）+ 服务 + API（/api/v1/donation-items，envelope / 数据"
                "域 / 软删 / 审计）。前端页面尚未建成，故侧边栏不放入口（避免点击 404）；待 UI 落地后按 MENU_DEFINITIONS 说明补回。"
            ),
            "指标字典（CONTEXT.md）：总人口/总户数/人均收入/经费合计/报表村数等逐条登记「定义 + 数据源 + 唯一实现 + 回归用例」，防止同一指标再出现两套口径。",
            (
                "两道防腐门禁（已接入 CI static-analysis 与 make test-local）：scripts/check_unused_scope_params.py（AST 扫\"作"
                "用域形参收下却从未使用\"）、scripts/check_userdata_path_consistency.py（Electron userData / NSIS 钩子 / paths."
                "py 三处口径防漂移）。"
            ),
            "启动预检（app/startup/preflight.py）：磁盘余量、数据库可写性、系统时钟落后于数据、PII 加密密钥探针；只告警不阻断，启动线程内执行。",
            (
                "诊断包业务段：/system/diagnostics 新增 business（备份状态 / 调度器 / 后台任务失败 /数据包占用），把\"昨晚备份成功了吗、提醒为什么没发、导入为什么失败"
                "\"变成可导出的事实。"
            ),
            "数据包导出保留策略：每日 04:10 清理超过保留期（默认 7 天）的导出文件，避免长期运行撑满磁盘。",
            "总人口两套口径（W18 P0-1）：工作台取「全库最大年份」求和，统计页取「每村各自最新年」，实测同一数据差 500 人（两个页面数字打架）。统一为每村最新年，并加一致性守护测试。",
            (
                "data_scope 形参收下不用（W18 P0-2）：_avg_per_capita_income 收了数据范围却从未参与过滤，部门级管理员看到的是全库人均收入（越权且无告警）。已接线；"
                "无 scope 时 fail-closed 返回 0。"
            ),
            (
                "报表总数封顶 100（W18 P1-1）：total_villages 原用明细 limit(100) 后的 len()，改为独立count() 并新增 villages_truncate"
                "d 如实标注。"
            ),
            (
                "未关联村经费越权（W18 P1-2）：village_id IS NULL 的经费原先无条件计入所有用户合计，改为按 Fund.organization_id 判域（无归属仅全局管理员可见"
                "）。返回空列表 —— 现已按当前登录人过滤。改按业务键判定：同记录按 overwrite 更新/跳过，异记录换新 id 插入并登记映射。现包内组织仅作提示，最终必须落在调用者有权写入的组织"
                "集合内。且被菜单对齐门禁判为无路由），已摘除并记录待办。"
            ),
        ],
    },
    {
        "version": "1.12.20",
        "date": "2026-10-17",
        "description": "🔒 安装器卸载口径修正（W19 实机实证）",
        "features": [
            "卸载不删真实用户数据（隐私泄露，实机实证）：三处错误叠加 ——",
        ],
    },
    {
        "version": "1.12.21",
        "date": "2026-10-17",
        "description": "🎁 捐赠物资台账前端落地 + CI 分支门禁去抖",
        "features": [
            (
                "捐赠物资台账前端（w17-003 完成）：新增 views/donation/List.vue 与 api/donations.ts ——统计标签（总数/图书/设备/物资/折价合计）、关键"
                "字/类别/去向筛选、表格（类别、数量+单位、折价、去向名称）、分页、登记/编辑对话框（去向类型联动、附件按行解析、手写校验与后端 ensure_donation_valid 同口径）、删除"
                "二次确认；"
            ),
            (
                "CI 分支覆盖棘轮随机变红（PR Checks backend-test）：该步骤此前再跑一遍全量 pytest（第二个 xdist 数据面）再比对基线，出现过 step5 通过而 ste"
                "p8 读到 99.61% 的不一致。现改为单一数据源：主测试步骤产出 coverage-branch.json，棘轮步骤只读该文件比对；用例不再重复执行，两跑差异导致的假红消除。"
            ),
        ],
    },
    {
        "version": "1.12.22",
        "date": "2026-10-17",
        "description": "🧾 全部遗留工单落地（004~010 七项）",
        "features": [
            (
                "w17-004 工作移交：/handover 页（清单勾选 → 接任人 → 确认执行 → 交接单 PDF / 历史回放）；后端 handover_service 单事务改写村/项目/待办/"
                "审批归属 + 双方站内消息 + WorkLog 审计（历史由 WorkLog 承载，不新增表）。"
            ),
            (
                "w17-005 年度数据滚动填报：yearly/{year}/prefill（逐字段三态差异）+ rollforward 批量沿用（section_keys 白名单、单事务原子、默认只填空"
                "不覆盖、可选 overwrite）；年度概览「从上年复制」弹窗。"
            ),
            (
                "w17-006 导出物口径脚注：村/学校/项目/经费/综合报表五类导出统一「口径说明」（数据截止/过滤条件/软删/数据范围/生成人/时间，空字段省略）；Word/PDF 文末、Excel "
                "表尾、CSV 尾部同时生效。"
            ),
            (
                "w17-007 一村（校）一档 PDF：/supported-villages/{id}/dossier.pdf 与 /schools/{id}/dossier.pdf（封面/基本信息/年"
                "度数据/项目经费摘要/照片清单/口径脚注；空段降级；越权 404；导出审计；500 泛化）；详情页按钮。"
            ),
            (
                "w17-008 AI 结论可解释 + 业务数据体检：10 个 AI 端点统一返回结构化 rationale + data_scope，前端「为什么」面板；新增 GET /system/bu"
                "siness-health（管理员，8 项体检：村年度缺失/经费逻辑矛盾/长期未动/组织归属缺失；无 PII）。"
            ),
            (
                "w17-009 金额展示与筛选记忆：MoneyText 组件（千分位/4 位小数/空值占位/人民币大写）与useFilterMemory（sessionStorage 按路由记忆）；村/项"
                "目/经费列表接线筛选记忆与「导出当前筛选」。"
            ),
            (
                "w17-010 大屏可配置：右上角「设置」抽屉（卡片显隐/排序、刷新频率 30s/60s/5min/关闭、汇报脱敏），localStorage 持久化；关闭自动刷新即停止轮询；脱敏模式金额"
                "精度隐藏 + 负责人姓名打码。"
            ),
            (
                "前端 vue-tsc 类型错误导致 CI 构建失败：捐赠台账表格槽位 row 为 DefaultRow，直接传 DonationItem 形参触发 TS2345 → build-windo"
                "ws 的 Frontend smoke test 失败；已按结对台账同款模板内断言修复。"
            ),
        ],
    },
    {
        "version": "1.12.23",
        "date": "2026-10-18",
        "description": "汇报大屏对象筛选（村/校/单位）+ 在途批次收口",
        "features": [
            (
                "汇报大屏对象维度筛选（W20）：新增 GET /api/v1/bigscreen/filters（数据域内帮扶村 / 帮扶学校 /帮扶单位三组筛选项；单位是村 support_unit、校"
                " support_unit、项目 responsible_unit、结对 subject_name 四路并集的自由文本 facet…"
            ),
            (
                "大屏前端对象筛选：views/bigscreen/BigScreen.vue 头部筛选条（全部 / 帮扶村 / 帮扶学校 / 帮扶单位 +可搜索对象下拉 + 重置），KPI、图表与负责人改"
                "由单一 overview 接口渲染；scoped 时新增「对象档案」与「帮扶明细」卡片；scope 与卡片显隐/排序/刷新频率/脱敏一并持久化到 localStorage；filters "
                "仅加载一次、自动刷新只轮询 overview；"
            ),
            (
                "方案文档与用户手册：新增 docs/design/汇报大屏对象筛选与下钻方案.md（背景、现状调研、四类 scope方案、逐 scope 数据口径表、API 契约、交互流程、权限安全、性能"
                "降级、验收清单、后续演进），docs/02-用户手册/数据分析功能使用指南.md 新增「汇报大屏按对象筛选」章节。"
            ),
            (
                "单校成效统计端点（W18 在途收口）：GET /api/v1/schools/{school_id}/statistics，由服务端聚合学校项目数/预算、资助学生数与资助金额、学生规模，供"
                "学校详情与删除前关联校验使用。"
            ),
            (
                "W18 在途安全与数据完整性收口：数据包导出改走原生 SQL，PII 列保持密文出包（不再经TypeDecorator 解密后落入 zip）；跨机数据包主键冲突按业务键判定——缺失键不覆盖"
                "本机数据、业务键不同则去主键插入；备份/恢复增加完整性与路径校验、恢复前置校验与失败降级；同步导入时间戳统一 UTC 规范化；离线数据目录与日志路径按平台收口；学校统计、诊断与审计保留策略"
                "等配套修复。"
            ),
            (
                "测试与门禁收口：补齐 W18 遗留 19 个「实现已变、测试未跟」的失败用例与 5 个模块（school.py / data_package_service.py / backup_ser"
                "vice.py / pii_crypto.py /database_health_service.py）的语句+分支覆盖率缺口；"
            ),
            "大屏口径修正：KPI 标签去掉冗余的 \"(万)\"（由 unit 字段承载单位）；Fund.year 为 NULL 的经费不再让年度趋势整段降级为空。",
            (
                "年度趋势聚合从 /dashboard/yearly-trends 端点抽成 _build_yearly_trends(db, data_scope, years)，由仪表盘与大屏共用，避免"
                "两套口径漂移。"
            ),
            (
                "删除 UserManagementRealRender.test.ts、UserManagementRender.test.ts（与专属测试重复，且违反\"同一 .vue 单一执行者\"覆"
                "盖率规程）、临时探针测试与拆分后残留的死 import。"
            ),
        ],
    },
    {
        "version": "1.12.24",
        "date": "2026-10-18",
        "description": "🧹 W5-T5 解包口径收口 + 分支门禁确定性",
        "features": [
            (
                "前端 50 处 no-restricted-syntax 违规（.data.items 手写解包）全部收敛到 @/utils/unwrapList：涵盖列表/详情/仪表盘/导出等 40 个"
                "文件；顺手修正 3 处「空数组 truthy 短路」语义缺陷（ChartRow 的 data.data 嵌套、ConflictResolution 的 data.data、Contract"
                "Manage 的数组形态兜底）…"
            ),
            (
                "版本兜底同步补漏：frontend/src/config/constants.ts 的 SYSTEM_VERSION 硬编码兜底随单源同步更新，修复 constants.test.ts 两"
                "例版本回落断言失败。"
            ),
            (
                "backend/tests/unit/test_branch_closure_r22.py（21 项）：为 23 个历史错误/边界分支补真实行为回归（help 片段边界、批量表白名单、ca"
                "che None 哨兵、村附件扩展名、增量检测模型回退、管控包配置类型、数据包友好错误、加密包与备份恢复清理路径、相对 LOG_FILE、凭证无项目、预览 50 行截断、政策导入非 dic"
                "t、注册认领竞争），使分支门禁不依赖测试执行顺序或未提交测试。"
            ),
        ],
    },
    {
        "version": "1.12.25",
        "date": "2026-10-18",
        "description": "🔧 ARM64 发布流水线彻底修复（镜像限流根因）",
        "features": [
            (
                "ARM64 流水线失败根因：build-backend 作业独立冷启动 docker buildx build，需再次拉取python:3.11-slim-buster；Docker Hu"
                "b / ECR 公共镜像匿名拉取配额耗尽时返回toomanyrequests: Data limit exceeded，buildx 随即无法解析基础镜像元数据，整条 ARM64 流水线失"
                "败…"
            ),
            "修复方式（消除重复冷构建，而非绕过）",
            (
                "效果：ARM64 作业数减少 1 个；基础镜像只拉取一次；瞬态网络/限流失败可自动重试；Release 恢复 Electron ARM64 DEB 产物（与 standalone DEB "
                "并存的既有发布形态）。"
            ),
            "本版本无运行时代码变更（仅 CI/Dockerfile），Windows 安装包与 standalone DEB 内容与 v1.12.24 一致。",
        ],
    },
    {
        "version": "1.13.0",
        "date": "2026-10-18",
        "description": "导航/菜单单一源重构 + 系统管理 6 聚合页",
        "features": [
            (
                "导航增强：Ctrl+K 菜单搜索（板块/入口/Tab 全量可搜、键盘上下选择+回车跳转、空搜索显示收藏与最近）、最近访问与收藏（localStorage nav:recent / nav:"
                "favorites，上限 8 条，损坏数据自动回退）。"
            ),
            (
                "系统管理 6 聚合页（/system/console/:group + 页内 ?tab=<tab key>）：组织与权限 / 安全与审计 / 运维与监控 / 备份与存储 / 系统设置 / "
                "关于与反馈；Tabs 页内切换、当前 Tab 才加载对应页面组件，原页面组件与旧路由全部保留（深链不失效）。"
            ),
            "导航入口补齐：汇报大屏、提醒中心、帮助中心、数据上报（上报/接收/版本）、批量操作、综合数据录入、成效排名/评估、工作分析、舆情监测、驻村工作台。",
            (
                "后端菜单 v2 单一源：MENU_SECTIONS（6 板块）+ MENU_DEFINITIONS 扁平条目（99 key / 85 个带 path 入口，条目 kind = page/g"
                "roup/console，tabs 承载聚合页页签）；/menus/accessible 与 /menus/all 统一返回 {version:2, sections, flat_keys"
                "}。"
            ),
            "左侧导航重排为 7 板块：工作台（固定第一）+ 帮扶业务 / 乡村振兴 / 工作协同 / 分析汇报 / 数据管理 / 系统管理；消除\"分组标题与子菜单同名\"重复，消息中心移入工作协同。",
            "前端侧栏、移动端底部导航、权限面板与权限包菜单树全部改为后端菜单数据驱动，不再手写菜单段；权限面板为\"板块→入口→Tab\"三级树，保存协议仍为 key 数组。",
            (
                "菜单过滤语义：group 任一子项可见即显示并裁剪子项；console 可见 = console.key 或任一tab.key ∈ allowed（勾聚合页 key 视为全部 Tab 可见"
                "）；旧 key 全部保留，历史权限包/allowed_menus 不失效。"
            ),
            (
                "菜单对齐门禁 scripts/check_menu_alignment.py 重写为规则 A~E（AST 解析单一源：后端 path 可解析 / 前端 meta.menuKey 合法 / "
                "无孤儿 key / 同路径不重复 / 板块唯一）。"
            ),
            (
                "删除前端菜单副本：src/config/menu-config.ts、src/utils/systemMenu.ts 及menu-config.test.ts、systemMenu.tes"
                "t.ts、menuKeyAlignment.test.ts、DefaultLayoutSafe.menu.test.ts、DefaultLayout.property.test.ts（源码"
                "字符串断言/假属性测试）。"
            ),
            "删除后端 3 个死菜单项：user-backup、data-quality、system-security（无独立导航出口/重复 path）。",
            "删除根目录旧 PPT 副本，docs/帮扶管理信息系统介绍.pptx 为唯一对外介绍材料。",
            (
                "删除文档中\"前后端菜单双轨同步 / menu-config 引用 / 旧系统管理入口清单\"等过时说明。与\"有菜单 key 但无页面/有页面但无菜单\"的双向漂移（由规则 C 持续拦截"
                "）。"
            ),
        ],
    },
    {
        "version": "1.13.1",
        "date": "2026-10-18",
        "description": "修复 GitHub 发布构建失败 + 安装包自包含验证",
        "features": [
            (
                "Windows 发布构建失败（v1.13.0 未产出 Windows 安装包）：tag 构建的 smoke-test重复执行全量后端（1.3 万+）+ 全量前端（6.7 千+）测试；同一提"
                "交内容在 main 的 PR Checks已全量跑绿（c17b2ed success），tag 侧重复运行却因 flaky 测试 / rerun 与覆盖率数据合并抖动随机变红（实测失败发生"
                "在后端步骤 14.5 分钟处，exit code 1…"
            ),
            (
                "ARM64 发布构建失败（Electron ARM64 DEB 连续两版缺失）：docker/Dockerfile.kylin-standalone的 backend-output 阶段 "
                "COPY --from=backend-builder /build/dist/assistance-backend 路径错误（PyInstaller 实际产物目录为 assistance"
                "-management-backend…"
            ),
            (
                "安装产物自包含冒烟（CI，Windows 构建作业）：electron-builder 解包后直接启动打包后端resources/backend/assistance-backend/as"
                "sistance-backend.exe（按 Electron 运行期注入的数据目录env），断言 /health 返回 status=ok、version、git_hash、数据库迁移 "
                "at_head=true；"
            ),
            (
                "发布门禁职责划分写入 README：全量测试 = main 的 PR Checks + Nightly；tag 构建 = 发布专项门禁（main 绿 + 敏感子集 + 前端类型 + 自包含"
                "冒烟），避免 tag 与 main 重复全量造成随机失败。"
            ),
        ],
    },
    {
        "version": "1.13.2",
        "date": "2026-10-18",
        "description": "修复发布门禁依赖安装遗漏",
        "features": [
            (
                "v1.13.1 的 smoke-test 重构遗漏依赖安装步骤：Backend release smoke subset 直接执行python -m pytest，但 runner 上只装"
                "了 Python 解释器，未安装 backend/requirements*.txt，导致步骤秒失败（No module named pytest）、build-windows 被 nee"
                "ds: smoke-test 阻断。"
            ),
        ],
    },
    {
        "version": "1.13.3",
        "date": "2026-10-18",
        "description": "自包含冒烟步骤诊断增强（动态端口 + stdout/stderr 落盘）",
        "features": [
            (
                "CI 自包含冒烟在 Windows runner 上超时失败（v1.13.2 唯一阻断项，本地同脚本通过）：固定端口 8123 可能被 runner 占用，且后端 stdout/stder"
                "r 未落盘导致失败时只能看到 exit code 1。"
            ),
        ],
    },
    {
        "version": "1.13.4",
        "date": "2026-10-18",
        "description": "修复 ARM64 后端产物主程序文件名（Electron DEB 最后一项阻断）",
        "features": [
            (
                "ARM64 Electron DEB 仍失败（v1.13.3 注解为「缺后端主程序」）：backend-output 阶段 COPY 源路径修正后目录已正确导出，但 PyInstaller"
                " Linux spec 的 EXE/COLLECT name 为assistance-management-backend，导出目录内主程序仍是该名；"
            ),
        ],
    },
    {
        "version": "1.14.0",
        "date": "2026-10-18",
        "description": "功能大迭代（一户一档/影像库/消费帮扶/OCR/报表组合/导航折叠）",
        "features": [
            (
                "一户一档：新表 households / household_members / household_risk_records，API /households/*，页面 /househol"
                "ds 与 /households/:id：家庭成员、帮扶责任人、风险类型、收入/务工/大病/住房监测指标；风险等级与预警（连续未走访 >90 天且非一般户→中风险；大病/住房不安全/突发困"
                "难→高风险，服务层实时计算）；走访记录挂户并回写最近走访日期；"
            ),
            (
                "影像库：新表 photo_archives，API /media/photos/*，页面 /media：按村/校/项目/时间/标签归档；手机照片 EXIF 拍摄时间与 GPS 自动归类（≤"
                "5km 就近匹配帮扶村）；同一拍摄点多期照片按 spot_key 自动配对，生成左右/2×N 滑动对比图 PNG（Pillow 合成 + 日期标注，GET/POST 双入口），可直接用于汇"
                "报材料。"
            ),
            (
                "消费帮扶台账（替换已下线的舆情监测）：新表 consumption_records + /consumption/* + 页面 /consumption：品类（农产品/畜禽/手工/其他）、"
                "数量、金额、采购方、供货方（农户/合作社/企业）、年度、凭证、备注；年度/品类/村统计与 xlsx/csv 导出；与帮扶村年度数据板块 consumption_support 区分。"
            ),
            (
                "经费凭证 OCR：services/ocr_service.py（rapidocr-onnxruntime 1.4.4，完全离线 CPU）+ POST /funds/ocr-voucher"
                "：识别凭证文本并回填金额/日期（支持 ￥/¥/元/千分位、YYYY-MM-DD / YYYY年M月D日 / YYYY/MM/DD）；引擎不可用时 503 降级、前端提示手工录入不阻断业务。"
            ),
            (
                "报表模板组合导出：POST /report-templates/{id}/export?format=xlsx|csv|docx|pdf&year +GET /report-templat"
                "es/{id}/print-data?year；前端任意字段勾选组合 → 预览 → 多格式导出 → 浏览器打印。"
            ),
            "导航体验：7 板块标题放大（18px 加粗）、默认折叠、点击展开/收起（localStorage nav:expanded-sections）。",
            "汇报大屏退出：大屏头部「退出大屏」→ 退出全屏并返回工作台。",
            (
                "数据校验合并页：/data-verify 单页三 Tab（校验执行 / 规则管理 / 字段说明），问题清单可定位跳转与导出；独立「校验规则」菜单下线（key 保留 legacy）；字段中文"
                "说明承接原国际化字段翻译。"
            ),
            (
                "数据上报链路修复：枚举列导出的枚举名与导入校验的枚举值不一致导致上级整表 rejected（学校等）；导出侧按模型列元数据归一为枚举值，补端到端集成测试（下级录入→生成上报包→上级接收导入"
                "→数据可见 + 重复导入幂等）。"
            ),
            "驻村工作台：删除页面/路由（无后端模块），菜单 key checkin 保留 legacy。",
            (
                "舆情监测：删除后端 api/v1/sentiment.py、models/sentiment.py、services/sentiment/（采集/分析）与前端页面/API，菜单 key s"
                "entiment 保留 legacy（改为消费帮扶）。"
            ),
            (
                "国际化/邮件设置：删除 I18nManagement.vue / EmailSettings.vue 及路由；菜单 key i18n / email 保留 legacy。rural_wor"
                "ks / rural_tasks / tea_plantations / cactus_fruit_plots 的 village_id 迁移为supported_village_id（F"
                "K→supported_villages，按村名+组织回填）；"
            ),
        ],
    },
    {
        "version": "1.14.1",
        "date": "2026-10-18",
        "description": "修复空库迁移链 / E2E 折叠适配 / ARM64 构建加固",
        "features": [
            (
                "空库初始化迁移链（严重：全新安装 alembic upgrade head 必失败）：v1.14.0 删除villages 遗留表后，历史迁移在「空库 create_all 路径」上因表不"
                "存在而中断"
            ),
            (
                "E2E 适配 7 板块默认折叠：v1.14.0 起侧栏板块默认折叠，E2E 用例点击子菜单/断言子项前需先展开。新增 expandAllSections / expandSection h"
                "elper（写 nav:expanded-sections契约后 reload），修复「待办事项功能」「权限包菜单可见性」用例；快捷导航用例（新建项目 → /projects/create"
                "）重跑稳定通过。"
            ),
            (
                "ARM64 构建 npm 网络重试加固：build-arm64.yml 的 Build Frontend 步骤由裸npm ci 改为 fetch 重试参数 + 最多 3 次重试（与 pr-"
                "checks/build-windows 同款）。v1.14.0 的 ARM64 Electron DEB 即因 registry 抖动在本步骤 exit 1 被 skip。"
            ),
            "E2E 辅助函数新增折叠展开工具；dashboard.spec.ts / permission-packs.spec.ts 适配新导航交互。",
        ],
    },
    {
        "version": "1.14.2",
        "date": "2026-10-18",
        "description": "修复发布门禁时序缺陷（v1.14.1 构建被误拦）",
        "features": [
            (
                "发布前置门禁误拦合法 tag 构建：v1.13.1 引入的门禁只检查「main 最近一次 completed 的PR Checks」。v1.14.1 tag 推送瞬间，其自身 PR Che"
                "cks 尚在 in_progress，而\"最近 completed\"仍是上一提交（422f840）的 e2e/upgrade-rehearsal 失败 run → 门禁拒绝构建（mai"
                "n 分支最近一次 PR Checks 未通过）…"
            ),
            (
                "说明：v1.14.1 的代码修复（空库迁移链幂等、E2E 折叠适配、ARM64 npm 重试加固）不受影响，其 PR Checks 中 upgrade-rehearsal、e2e-test"
                " 均已 success（本版本仅修 CI 门禁）。"
            ),
        ],
    },
    {
        "version": "1.14.3",
        "date": "2026-10-18",
        "description": "ARM64 构建网络韧性加固（npm/Docker registry 抖动）",
        "features": [
            (
                "ARM64 构建因 CI 网络抖动间歇失败（v1.14.2）：v1.14.2 的 Build Frontend 在npm registry 抖动下 3 次 npm ci 全失败（v1.14"
                ".1 同步骤成功，属 runner 网络波动）；standalone DEB 的 Docker 构建亦 3 次失败（公共镜像/缓存拉取）。加固"
            ),
            (
                "说明：v1.14.2 已修复发布门禁时序缺陷（scripts/check_release_gate.py），Windows 安装包正常产出；本版本仅进一步加固 ARM64 流水线网络韧性。"
                "v1.14.1 的 ARM64 完整构建（standalone DEB + Electron DEB）曾成功，证明代码侧无阻断。"
            ),
        ],
    },
    {
        "version": "1.15.0",
        "date": "2026-10-19",
        "description": "UI v2.0：精美·科学·一致性的系统级视觉重构",
        "features": [
            (
                "设计系统 v2（Token 升级）：主色阶 --color-primary-50/100/500/600/700/900；卡片边框 --color-card-border +轻阴影两档（-"
                "-shadow-card / --shadow-pop）；圆角三档（card 8 / control 6 / pill 999）；字号阶梯 calc(* var(--font-scale)"
                ")；正文行高 1.6；数字 tabular-nums；"
            ),
            (
                "主题 5→3 收敛：军绿（默认）/ 深色大屏 dark-bigscreen（仅大屏页强制）/ 户外高对比 outdoor；旧值 light/military→default、dark→da"
                "rk-bigscreen、high-contrast→outdoor 自动迁移（历史用户不失效）。"
            ),
            (
                "显示偏好 4 档（localStorage ui:prefs，<html data-*> 驱动）：字号（紧凑/标准/大号，--font-scale 0.92/1/1.12）、密度（舒适/紧"
                "凑，表格行高 44/34px）、高对比、简化模式（隐藏趋势箭头/辅助说明/高级字段）；面板 components/settings/AppearanceSettings.vue，入口：头像"
                "下拉「外观设置」；"
            ),
            (
                "全局模板样式与通用组件：card.scss（.app-card/.app-stat-card/.stat-trend/.num-cell）、states.scss（.app-empty/."
                "app-loading/.app-error 三件套，错误必须可重试）、dialog.scss（三档宽度）、ui-v2.scss（表格浅主色表头+金色底线/去斑马纹/hover/焦点环）；"
            ),
            (
                "导航体验：侧栏当前板块 3px 金色竖条、当前板块自动展开并持久化（nav:expanded-sections）、收起态 hover/键盘聚焦浮出子项浮层、面包屑「板块 › 页面」、Ctr"
                "l+K 命令面板（页面+最近+动作）。"
            ),
            (
                "工作台：KPI 统计卡网格（28px/700/tabular-nums）+ 待办清单卡 + 图表两列 + 快捷入口/近期动态层级重排；加载/错误/空态三件套统一；布局编辑器新增「待办」区块"
                "。"
            ),
            (
                "汇报大屏：三层结构（标题时间条 / KPI 大数字 / 2–3 列图表）；data-bigscreen-distance=\"3m|6m|10m\"字号分档（默认 6m）+ 页内切换；15"
                "s 自动轮播（可暂停/关闭，卸载/退出清理定时器）；深色主题双挂载（页面根 + documentElement，卸载恢复）。"
            ),
            "一户一档：列表 4 张统计卡 + 筛选/表格卡 + 三件套 + 数字列右对齐 + 删除操作收进下拉；详情左主右辅布局（≤1200px 单列）+ 4 张监测指标统计卡 + 时间线/走访卡片。",
            (
                "质量门禁：tests/unit/ui/ui-tokens.test.ts（22 条 Token/主题/偏好/大屏契约静态断言）；tests/e2e/visual/visual-baseli"
                "ne.spec.ts 10 个关键页面 DOM 结构基线（跨平台 JSON，UPDATE_VISUAL_BASELINE=1 更新）。"
            ),
            "列表页 page_size=500 超后端上限（200）导致 422：一户一档/消费帮扶/影像库/权限包页面统一改为 200，消除页面加载 422 与下拉选项缺失（测试断言同步）。",
            (
                "工作台 KPI 取消请求误判为错误：路由导航/卸载时 axios CanceledError 不再记录 error 日志、不置错误态、不触发无谓重试（新增 code/name 两个取消分支"
                "测试）。"
            ),
            (
                "Token 重复定义覆盖：删除后置旧 --shadow-card/--radius-lg-plus 覆盖，v2 轻阴影与 8px 圆角实际生效。theme-elevated 深色块、acc"
                "essibility.css 高对比改为 data-contrast=\"high\"（不再占用主题值）。"
            ),
        ],
    },
    {
        "version": "1.15.1",
        "date": "2026-10-19",
        "description": "CI 后端全量并发稳健化（修复 v1.15.0 Windows 包被门禁误拦）",
        "features": [
            (
                "PR Checks backend-test 在 4 核 runner 上偶发失败：v1.15.0 的 backend-test 使用pytest -n auto（4 workers + "
                "覆盖率 + 13,710 用例），出现 xdist worker 偶发崩溃 → pytest 提前退出，覆盖率报告只含已跑部分（dashboard/analytics/batch_oper"
                "ations 等模块显示低覆盖），门禁误红；"
            ),
            (
                "说明：v1.15.0 的 ARM64 构建（standalone DEB + Electron DEB）已成功产出并发布 Release；v1.15.1 仅修 CI 稳定性，产品代码与 U"
                "I v2.0 内容与 v1.15.0 完全一致（版本号同步更新）。"
            ),
        ],
    },
    {
        "version": "1.15.2",
        "date": "2026-10-19",
        "description": "CI 后端测试改串行（彻底规避 xdist worker 崩溃）",
        "features": [
            (
                "PR Checks backend-test 在 ubuntu-latest 上提前退出（v1.15.0/v1.15.1）：pytest -n auto/-n 2 均出现 pytest 中"
                "途退出，覆盖率报告只含部分模块（dashboard 71.70% / analytics 44.17% / batch_operations 31.14% / rbac 41.46%，且两"
                "版数字完全一致）…"
            ),
            (
                "说明：v1.15.0/v1.15.1 的 ARM64 构建均已成功产出；Windows 安装包因 backend-test 门禁误红未产出。本版本仅修 CI 执行方式，产品代码与 UI v"
                "2.0 内容与 v1.15.0 完全一致（版本号同步更新）。"
            ),
        ],
    },
    {
        "version": "1.15.3",
        "date": "2026-10-19",
        "description": "CI 后端测试分段执行（单进程内存峰值治理 + 失败诊断）",
        "features": [
            (
                "PR Checks backend-test 三连失败（v1.15.0/v1.15.1/v1.15.2）的根因治理：-n auto（xdist）→ -n 2 → 串行（-n 移除）三种方式"
                "均在 ubuntu-latest 上以「pytest 提前退出 + exit 1、无 FAILED 摘要、无覆盖率汇总表、进度行停在tests/integration/test_audit"
                "_integration.py 附近」结束——特征为进程被杀/崩…"
            ),
            "说明：本版本仅修 CI 执行方式，产品代码与 UI v2.0 内容与 v1.15.0 完全一致（版本号同步更新）。",
        ],
    },
    {
        "version": "1.15.4",
        "date": "2026-10-19",
        "description": "backend-test 分段覆盖率阈值修复",
        "features": [
            (
                "backend-test 段 1（integration/security）因覆盖率阈值误判失败：v1.15.3 拆分后，段 1 只覆盖部分模块，单段结束时会触发 .coveragerc "
                "的 fail_under=100 检查（33.87%）→ 假失败。"
            ),
        ],
    },
    {
        "version": "1.15.5",
        "date": "2026-10-19",
        "description": "CI Runner 固定 ubuntu-24.04（规避 Ubuntu 26 迁移导致的 backend-test 崩溃）",
        "features": [
            (
                "PR Checks backend-test 连续失败（v1.15.0–v1.15.4）的根因定位与规避：时间线关键事实：GitHub 于 2026-10-19 将 ubuntu-late"
                "st 迁移到 Ubuntu 26（Actions 输出明确提示 ubuntu-latest label will migrate to Ubuntu 26 beginning Octobe"
                "r 19, 2026）…"
            ),
        ],
    },
    {
        "version": "1.15.6",
        "date": "2026-10-19",
        "description": "全面体检修复：CI 稳定化 + 数据权限缓存泄漏 + 前端依赖冲突 + 构建可复现（W24）",
        "features": [
            (
                "v1.15.5 提交误含测试残留文件：本地验证与探针脚本运行产生的_probe_bandit.json、backend/pytest-of-Administrator/、mrr_w24_p"
                "robe_*/、backend/bumofu_pytest_appdata_*/ 等临时产物被 git add -A 一并提交（当时未在 .gitignore 覆盖）。"
            ),
            "保留合法的辅助脚本 scripts/run-python.js（Python 解释器解析）与 scripts/run-frontend.bat（前端启动）。",
            (
                "P0 数据权限缓存键跨角色泄漏（backend）：villages:list / schools:list 缓存键仅含organization_id，同组织内 admin 先查后 user"
                "/viewer 命中同一键并读到管理员的数据范围（实测普通用户可见他组织记录，违反 OWN 仅本人数据域）；改为按用户隔离，与 policies:list:{user_id}既定正确做法对"
                "齐；"
            ),
            (
                "P0 前端依赖 peer 冲突导致 CI 前端安装失败（frontend）：vite@^7.3.6 与@vitejs/plugin-vue@^5.0.4（peer 仅支持 vite ^5|"
                "|^6）冲突，干净环境 npm ci 直接 ERESOLVE，这是 v1.15.0–v1.15.4 Build Windows / Build ARM64 前端依赖安装失败的根因（此前误判"
                "为 registry 网络抖动）。"
            ),
            (
                "P1 日志 PII 脱敏被绕过：默认 LOG_FORMAT=json 下自定义 JsonFormatter 用formatException(exc_info) 重新渲染原始堆栈，绕过 S"
                "ensitiveDataFilter 写入的脱敏 exc_text，身份证/手机号随异常明文落盘；改为复用脱敏缓存（新增回归测试）。"
            ),
            (
                "P1 跨用户共享缓存泄漏 + 部署链路缺陷：按数据范围裁剪的supported-villages/filter-options、organizations/tree 响应 Cache-Co"
                "ntrol 由 public 改 private；docker/Dockerfile 删除引用不存在 electron-builder 阶段的 COPY；"
            ),
            (
                "P1 CI backend-test 稳定性重设计：新增 scripts/ci_backend_test_segment.sh，PR Checks 后端测试拆为 6 个独立 pytest "
                "进程（integration/security + unit 按目录/首字母 212+217+211=640 文件全覆盖），前 5 段 --cov-fail-under=0、仅最后一段触发"
                " .coveragerc fail_under=100；"
            ),
            (
                "P1 CI 失败上报误报修复：旧 \"Report backend failure\" 把 pytest 进度行当覆盖率缺口发成::error:: 注解（v1.15.4 失败 run 的 "
                "11 条注解全是 tests/... [ 8%] 误报），淹没真实信号；改为只匹配真实 FAILED/ERROR/覆盖率不足行。"
            ),
            (
                "P1 CI 基础设施升级：4 个 workflow 全部 action 升级到 Node24 兼容版本并重新 SHA pin（checkout v5.1.0 / setup-python "
                "v6.3.0 / upload-artifact v6.0.0 / download-artifact v7.0.0 /cache v5.1.0 / codecov v5.5.5 / ac"
                "tion-gh-release v3.0.3 / docker…"
            ),
            (
                "P1 构建可复现性（裸 python）：新增 scripts/find-python.bat / scripts/run-python.js /run-backend.bat / run-"
                "frontend.bat；Makefile、cleanup.py、build-installer-local.ps1、cleanup.bat/dev-setup.bat/start-all"
                ".bat/stop-all.bat 与根 package.jso…"
            ),
            (
                "P2 分页上限缺失：GET /users、GET /machine-code/organization/list 的 page_size 为裸 int（SQLite LIMIT -1 等于"
                "全表），改用仓库统一 clamp_offset_limit 钳制。"
            ),
            (
                "P2 仓库卫生：清理 v1.15.5 误提交的测试/探针临时文件（见下），.gitignore 增加_probe_*.json / mrr_w24_probe_*/ / bumofu_py"
                "test_appdata_*/ / pytest-of-*/ 等规则。"
            ),
        ],
    },
    {
        "version": "1.15.7",
        "date": "2026-10-19",
        "description": "修复 workflow 的无效 action SHA（CI job 3 秒失败根因）",
        "features": [
            (
                "PR Checks / 构建 Workflow 的 actions/setup-python 等 action 引用失效（v1.15.6）：v1.15.6 提交（及同一批的 workflo"
                "w 调整）把 action 引用升级为actions/setup-python@ece7cb06... # v6.3.0 等 SHA…"
            ),
            (
                "说明：本版本仅修 CI 配置，产品代码与 UI v2.0 内容与 v1.15.0 完全一致；backend-test 的6 段执行器（v1.15.6）与 ubuntu-24.04 固定（v"
                "1.15.5）保持不变。"
            ),
        ],
    },
    {
        "version": "1.15.8",
        "date": "2026-10-19",
        "description": "待决策项彻底落地：viewer 严格只读 + 非回环注册 fail-closed + ARM64 发布门禁 + nightly 稳定化",
        "features": [
            (
                "viewer 角色服务端强制只读：新增集中式 ASGI 中间件 backend/app/middleware/viewer_readonly.py，对已认证 viewer 的写方法（POS"
                "T/PUT/PATCH/DELETE）在非白名单路径返回 403 统一信封，并写审计viewer_write_denied；"
            ),
            (
                "ARM64 发布门禁：build-arm64.yml 两个 Release 前新增 Verify release gate is green（复用 scripts/check_releas"
                "e_gate.py --timeout-minutes 30，permissions 增 actions: read），Release 条件加 && success()，门禁红时跳过发布。"
            ),
            (
                "nightly 后端稳定化：nightly-full.yml 由单步 -n auto 改为与 PR Checks 同口径的 6 段独立进程（复用 scripts/ci_backend_te"
                "st_segment.sh，新增向后兼容的 SEG_JUNIT/SEG_COV_HTML），保留 .coveragerc fail_under=100 与 JUnit/HTML/codec"
                "ov 上传。"
            ),
            "部署文档安全红线：补齐多机/LAN 部署必须全实例统一 PASS_CODE_SECRET、viewer 严格只读说明，修正失效的 Windows 部署链接。",
            (
                "非回环自助注册 fail-closed（安全决策，保留 R9 跨机注册能力）：/auth/register 在来源非回环（不信任可伪造代理头）且 PASS_CODE_SECRET 未配置时"
                "返回 403 并审计register_denied_untrusted，堵住「持安装包者用内置常量密钥离线伪造通行码自助开通」；回环来源（单机桌面）与已配置 secret 的部署行为完全不"
                "变。新增 11 条来源矩阵/审计/未开户断言测试。"
            ),
        ],
    },
    {
        "version": "1.15.9",
        "date": "2026-10-19",
        "description": "backend-test 恢复单进程全量（分段方案等效性验证失败后回退）",
        "features": [
            (
                "分段执行无法与单进程全量等价（v1.15.3–v1.15.8 的覆盖率门禁失败根因）：本地按 CI 的 8 段顺序复现后，合并覆盖率 99.99%（缺\u0007pp/services/s"
                "ecrets_manager.py:143 + 3 个分支、\u0007pp/api/v1/subordinate_reports.py 2 分支）…"
            ),
            "说明：本版本仅修 CI 执行方式；产品代码与 UI v2.0 内容与 v1.15.0 完全一致。",
        ],
    },
    {
        "version": "1.15.10",
        "date": "2026-10-19",
        "description": "backend-test 回归 8 段执行器 + 补充精确覆盖率测试",
        "features": [
            (
                "backend-test 采用 8 段执行器（规避单进程在 Linux runner 的 SIGSEGV）v1.15.9 单进程全量在 ubuntu-24.04 上运行时以 exit 13"
                "9（SIGSEGV） 崩溃（21 分钟处）…"
            ),
            "补充 2 个精确覆盖率测试（补齐 99.99% 的缺口）",
            "说明：本版本仅修 CI 测试执行与测试补充，产品代码与 UI v2.0 内容与 v1.15.0 完全一致。",
        ],
    },
    {
        "version": "1.15.11",
        "date": "2026-10-19",
        "description": "backend-test 12 段细粒度执行（缓解 SQLAlchemy C 扩展 SEGV）+ faulthandler",
        "features": [
            (
                "backend-test 的 SIGSEGV 进一步定位：v1.15.10 的 8 段方案中 seg5（unit root b-d-g-h-j-l-m-q-s，5,154 用例）以 exi"
                "t 139（SIGSEGV） 崩溃；"
            ),
            "说明：本版本仅调整 CI 分段粒度；产品代码与 UI v2.0 内容与 v1.15.0 完全一致。",
        ],
    },
    {
        "version": "1.15.12",
        "date": "2026-10-19",
        "description": "backend-test 12 段执行器稳定版（合并 R33 后首次完整验证）",
        "features": [
            (
                "backend-test 12 段细粒度执行（含 R33 并入后的测试面）：本版本在 R33（单位授权）代码并入main 后重跑完整 CI，验证 12 段执行器（每段独立进程 + PYTH"
                "ONFAULTHANDLER=1）在ubuntu-24.04 上的稳定性；覆盖率 --cov-append 跨段合并、最后一段按 --cov-fail-under=100 判定。"
            ),
            "说明：本版本主要验证 CI 修复与 R33 合并后的整体门禁；产品 UI v2.0 内容与 v1.15.0 一致。",
        ],
    },
    {
        "version": "1.15.13",
        "date": "2026-10-19",
        "description": "R34 发布闭环：CI 红项修复 + R33 导航入口 + 文档/PPT 更新 + 冗余清理",
        "features": [
            (
                "PR Checks 红项修复（v1.15.12 遗留）：flake8 F401（grant_package_service.py 未使用导入）、OrgGrant.vue prettier "
                "告警（lint:check --max-warnings=0 失败）、README 版本号未随 1.15.12同步（version 单一源校验失败）——三者是 v1.15.12 的 PR "
                "Checks 红因…"
            ),
            (
                "R33 单位授权功能 UI 不可达：/system/org-grant、/system/grant-import 路由/页面/API 齐全但单一菜单源 menus.py 无入口（用户不可达"
                "）。已在「系统管理 > 组织与权限」console 新增「单位授权配置」「导入授权包」两个 tab，路由 meta.menuKey 同步；菜单对齐门禁 A~E 通过。"
            ),
            (
                "前端死代码清理：移除 api/fundsRecycle.ts、api/schoolsRecycle.ts 中未使用的 request默认导入与 export { request } 死导出"
                "（全仓 0 消费方，已 grep 验证）。"
            ),
            (
                "前端覆盖率合并稳定性：router-index.test.ts 为 R33 两个懒加载页面补 vi.mock 桩，避免同一.vue 被多个测试文件执行导致 v8 fnMap 合并失真（fu"
                "nctions 跌破 100% 的历史机制）。"
            ),
            (
                "README / CLAUDE.md 测试规模与构建命令更新；.env.example 新增 R33 GRANT_* 配置块；部署文档新增「导入授权包前必须配置 GRANT_PUBKEY」"
                "「GRANT_ALLOW_UNSIGNED 永远 false」「GRANT_GUARD_MODE 默认 off，生产建议先 shadow 再 enforce」；新增docs/04-部署文档"
                "/RELEASE_NOTES-v1.15.13.md。"
            ),
            (
                "PPT（docs/帮扶管理信息系统介绍.pptx）更新至 v1.15.13：版本号、测试规模（13,926 / 6,865）、CI/CD 12 段与发布门禁、双平台包体积、R33 单位授权"
                "功能。"
            ),
        ],
    },
    {
        "version": "1.15.14",
        "date": "2026-10-19",
        "description": "发布版：CI 全绿后成功构建 Windows x64 完全集成安装包",
        "features": [
            (
                "PR Checks 全绿（含 12 段后端测试与 100% 覆盖率门禁）；tag v1.15.14 触发 Build Windows Installer 成功，Release 发布 MRR"
                "S-Setup-1.15.14-x64.exe（272.7MB）、blockmap、SHA256SUMS 与 latest.yml。"
            ),
        ],
    },
    {
        "version": "1.15.15",
        "date": "2026-10-20",
        "description": "UI 精细化方案 C（品牌区 / 工作台板块级 / 全站表格规范 / 筛选栏统一 / 响应式）",
        "features": [
            "侧栏品牌区：系统标识名 16→20px/800 单行（logo 36px、侧栏头 64px），修正品牌名低于板块标题（18px）的层级倒挂。",
            "工作台提升为板块级入口：保留 Home 图标，与七大板块标题同构（18px/700、统一内外边距/圆角、图标 16px）。",
            (
                "全站表格规范：所有 el-table 启用 border（117/117）恢复列宽拖拽；序号列统一 72px（25/25）、选择列 48px（10/10）、操作列统一 fixed=righ"
                "t（67/67）——序号、类型等列可拖拽放大。"
            ),
            (
                "筛选栏统一：清理 114 处行内宽度，改为全局 4 档规范（input 220 / select 160 / date 240 / number 120）+ 统一 16px 间距；搜索按钮"
                " 28/28 带图标、筛选栏重置按钮 100% 带图标。"
            ),
            "页面头部统一：19 个列表页接入共享 PageHeader（全站 31 页），标题/副标题/主操作位置统一。",
            (
                "全局精细化层：新增 frontend/src/styles/components/ui-refine.scss（筛选栏规范 / 表格规范 / 8px 栅格 / 响应式断点 1200·992"
                "·768）。"
            ),
            (
                "一户一档入口收敛：侧栏移除「一户一档」一级菜单，入口迁入「帮扶村管理 → 年度数据管理」页首张卡片（/households?village_id=<村ID> 按村预筛选）；后端菜单 key"
                " households 转 legacy（权限包 / 历史allowed_menus / 深链兼容），前端路由 meta.menuKey 改为 villages；旧链接 /househol"
                "ds、/households/:id 仍可直达。"
            ),
            "修复帮扶村管理搜索重置行控件宽度不一致（默认宽度与固定 140px 混用）、帮扶学校/经费台账等表格列宽无法调整的体验问题。",
        ],
    },
    {
        "version": "1.15.17",
        "date": "2026-10-21",
        "description": "系统管理：国际化彻底清除 + 导航死链治理 + 依赖安全修复",
        "features": [
            "国际化能力彻底移除（系统为纯中文单语部署，该能力从未上线使用，前后端一并清掉）",
            (
                "两处导航死链：SettingsOverview.vue 快捷导航的「国际化 → /system/i18n」与「邮件设置 → /system/email」都没有对应路由（点击即 404），已"
                "删除。注：SMTP 一直走 settings.SMTP_* 环境变量，从来没有\"邮件设置\"页面；menus.py 的 legacy key email 保留（供历史权限包兼容）。"
            ),
            (
                "导航死链门禁：src/utils/navLinks.ts + tests/unit/nav-links.test.ts。把导航配置里的 path 字面量与路由表的 path 字面量做文本比"
                "对，以后往快捷导航或 console 里加一个不存在的路径，测试会直接变红。"
            ),
            (
                "生产依赖安全漏洞（阻断发布的根因）：axios@1.20.0 传递依赖follow-redirects@1.16.0 命中两个高危公告（GHSA-q3jh-wrc6-jgq8 数组型 he"
                "ader 绕过跨域凭据剥离、GHSA-8r9p-f939-6h3csensitiveHeaders 正则转义缺陷）。"
            ),
            (
                "文档全量校准到 v1.15.15：README / CLAUDE.md / CONTEXT.md / AGENTS.md 与 docs/ 全量更新（版本、测试规模13,942 / 6,86"
                "7·331 文件、菜单 6 板块 104 key·16 legacy、100 个路由模块 / 803 端点、122 张表、54 个 Alembic 版本、v1.15.15 双平台发布物体积"
                "；"
            ),
            (
                "演示 PPT 更新至 v1.15.15：docs/build_ppt.js 源码直出 51 页（新增 R35 UI 精细化方案 C 页；版本号 / 测试规模 /发布资产 / 一户一档入口迁"
                "移 / 版本历程全片同步），scripts/ppt_overflow_check.py 0 溢出；新增docs/帮扶管理信息系统介绍-更新说明-v1.15.15.md。"
            ),
            (
                "新增 docs/04-部署文档/RELEASE_NOTES-v1.15.15.md（升级必读 GRANT_* / PASS_CODE_SECRET / viewer 只读 /DB 迁移提示"
                " + 双平台安装包体积 + 校验清单）。"
            ),
            "重写 根《项目文件结构说明.md》（v1.12.11 → v1.15.15，目录树 / 文件数 / 导航 / 门径口径全面校准）。",
            (
                "删除 12 份过期一次性文档：R28 / W18 批次报告、代码审查报告-2026-10-08、系统全面排查报告-2026-10-14、早期需求规划、架构评估约定（含空目录）、旧版 cla"
                "ss/sequence Mermaid 图、RELEASE_NOTES-v1.15.13；删除根 COORDINATION.md（已由 AGENTS.md / CLAUDE.md 协作约定"
                "取代）。"
            ),
            "清理仓库根 ignored 临时产物（运行日志 / 一次性脚本 / 探针临时目录 / 测试残留 db / 缓存）与 .scratch/ 内未跟踪大体积产物（仅本地清理，不入库）。",
        ],
    },
    {
        "version": "1.16.0",
        "date": "2026-10-21",
        "description": "系统管理梳理（分组导航 / 危险操作硬化）+ 离线瓦片地图 + PII 密钥跨机迁移 + 架构清理",
        "features": [
            (
                "PII 密钥跨机迁移 API（api/v1/system/pii_key.py，R34-2 / P1-2）：多机离线同步时 PII 列以密文出包，要求各机 ENCRYPTION_KEY 一"
                "致，但默认每台机各自随机生成 → 同步到对端后密文永不可解（界面只显示 enc.v1:…）。"
            ),
            (
                "离线瓦片地图：前端引入 Leaflet（leaflet + @types/leaflet）、新增 components/map/RasterTileLayer.vue与 utils/map"
                "Tiles.ts；地图页改为栅格瓦片渲染，瓦片包由构建机预置（resources/map-tiles/，本体不进 git）。Electron 打包配置把 map-tiles 复制进安装包；"
                "新增 npm run tiles:verify。"
            ),
            (
                "瓦片工具链 scripts/tiles/：切片/校验/清单（MANIFEST.json）生成，verify_tiles.py --require-min N 作为门禁；Windows 构建"
                "增加「Verify map tiles preset」步骤（默认允许 0 张，仓库变量 MAP_TILES_REQUIRED=1 时强制）。"
            ),
            (
                "ARM64 离线 OCR 出包门禁（E 区）：requirements-arm64-ocr.txt + Dockerfile 安装 headless cv2/onnxruntime，构建期"
                "跑 docker/ocr_smoke_arm64.py 真实识别冒烟；"
            ),
            (
                "本地等价 CI 的分段测试执行器 scripts/run_backend_tests_segmented.py（12 段 + --cov-append 合并，绕开单进程在 88% 处 SQ"
                "LAlchemy engine.dispose() 的 Windows access violation）。"
            ),
            "文档数字漂移门禁 scripts/check_doc_numbers.py（端点数 / 路由模块数 / 前端测试文件数 / 后端用例数）。",
            (
                "安全审计覆盖棘轮：scripts/security_audit.py 改为动态发现全部写路由模块，与backend/scripts/gate_baselines/audit_work_lo"
                "g_baseline.json 比对，基线外新增即失败。"
            ),
            (
                "危险操作统一二次确认：新增 composables/useDangerConfirm.ts（普通确认 / 高危录入确认两种强度），管理员重置他人密码改为「必须手工输入目标用户名」才能执行（"
                "此前点一下按钮即可接管账号）。"
            ),
            (
                "危险操作强制审计（后端补 4 处 AuditLogger.log）：删除组织 organization_delete、恢复备份 system_restore、轮换密钥 secrets_ro"
                "tate、管理员重置密码 admin_reset_password —— 均可在「安全与审计 → 安全审计」按操作类型检索。"
            ),
            (
                "权限抽屉「生效概览」（PermissionAssignmentDrawer.vue）：顶部一屏展示用户（含姓名）、系统角色、数据范围（中文 + 原值）、菜单权限来源（自定义 / 沿用角色默"
                "认 + 生效项数）、RBAC 可选角色数。"
            ),
            (
                "设备与授权中心（MachineCodeManagement.vue）：表格支持多选 → 复制所选机器码 / 通行码；顶部新增「单位授权配置」「导入授权包」直达入口；原「组织通行码」页签完整"
                "保留。"
            ),
            (
                "聚合页左侧分组导航（SystemConsole.vue）：系统管理 6 个聚合页由横向 tab 平铺改为「左分组 + 右内容」，分组为纯呈现层（TAB_LAYOUT），不改后端菜单 key"
                " / tab path / 权限粒度 / ?tab= 深链；未登记的新 tab 自动落「其他」组，窄屏 ≤992px 转横向滚动。"
            ),
        ],
    },
    {
        "version": "1.16.1",
        "date": "2026-10-21",
        "description": "安装包发布修复：ARM64 OCR 载荷门禁改为分级（v1.16.0 的 ARM64 产物链被拦）",
        "features": [
            (
                "ARM64 安装包无法产出：v1.16.0 新增的「Verify OCR payload」步骤是硬失败门禁，但 PyInstaller 阶段并未把 rapidocr_onnxruntime"
                " 的 ONNX 模型收进 DEB（spec 的 find_spec 守卫在该阶段静默跳过），于是 standalone-deb 作业在出包后第 11 步直接失败…"
            ),
        ],
    },
    {
        "version": "1.16.2",
        "date": "2026-10-22",
        "description": "ARM64 内置 OCR 出包门禁修正 + 遗留空表安全清除（r35 迁移）",
        "features": [
            (
                "ARM64 OCR 出包门禁误判（会让整条 ARM64 产物链失败）：v1.16.0/v1.16.1 的「Verify OCR payload」步骤写成 dpkg-deb -c \"$DE"
                "B\" | grep -qE ...，grep -q 命中后立即退出，dpkg-deb 收到 SIGPIPE，在 set -o pipefail 下整条管道返回 141 → 被误判为「缺少"
                " ONNX 模型」。"
            ),
            (
                "清除 W22 遗留的 6 张零引用表（r35_drop_legacy_tables_001，在 v1.16.0 因升级风险被移出后重做）：comments / messages_exten"
                "ded / sentiment_keywords / sentiment_reports /workflow_definitions / workflow_instances。"
            ),
            (
                "升级演练与迁移的显式契约：新增 backend/scripts/gate_baselines/upgrade_legacy_tables.json，演练（scripts/upgrade_r"
                "ehearsal.py）据此接受\"原表名消失（且旧库该表 0 行）\"或\"改名 legacy_<表名> 且行数不变\"两种终态；新增任何\"允许消失\"的表必须同步该清单，否则演练照样"
                "报「无表丢失」失败。清单缺失时演练退回最严口径。"
            ),
            (
                "迁移单测 tests/unit/test_migration_r35_legacy_tables.py（7 项）：空表删除 / 有数据改名归档 /表不存在幂等 / 归档表已存在时保留原表 "
                "/ 清单与常量一致 / 清单不可读回退 / 回滚改名。"
            ),
        ],
    },
    {
        "version": "1.16.3",
        "date": "2026-10-22",
        "description": "单位授权改用「单位选择器」 + 权限/机构/角色/用户/注册登录操作说明",
        "features": [
            (
                "单位授权配置不再手输数字 ID（OrgGrant.vue）：原输入框要求管理员手抄 organizations.id，输错/留空只给一句「请先填写有效的单位 ID」，实际无法使用。现改为可"
                "搜索单位下拉"
            ),
            (
                "新增 docs/02-用户手册/权限与组织管理操作说明.md：权限 4 层叠加模型（用户白名单 > 权限包 > 角色默认 > 系统角色）+ 数据范围 4 档、机构管理（含删除高危确认与影响"
                "面）、系统角色 vs RBAC 角色、用户管理（新增/停用/审核/重置密码/会话）、权限包与菜单可见性、注册登录全链路（首登改密、来源门禁、通行码/机器码三级回退、2FA、忘记密码、失败锁"
                "定 5 次/30 分钟）、单位授权上下级流程、常见提示排错表、管…"
            ),
            "用户手册索引与《系统管理操作说明》增加交叉引用。",
            (
                "OrgGrant.test.ts 增至 25 例：单位树拍平（层级缩进/缺名称缺编码/非法 id 兜底）、非数组输入防御、列表为空与加载失败两条降级路径、选择单位清空旧矩阵、手工/选择模式"
                "互切、选项文案渲染；覆盖率保持 100%。"
            ),
        ],
    },
    {
        "version": "1.16.4",
        "date": "2026-10-22",
        "description": "组织编码改用行政区划代码（3 级） + 默认关闭自助注册 + 账号解锁",
        "features": [
            (
                "组织编码 = 行政区划代码（GB/T 2260，统一 6 位）：XX0000 省级 / XXYY00 市州级 / XXYYZZ 县市级。判定口径集中在 OrganizationCodeSe"
                "rvice（唯一实现）：normalize_admin_code() / infer_level() / level_order()。"
            ),
            (
                "组织层级收敛为 3 级：OrganizationLevel 由 5 值收敛为 3 值；/organizations/types/options只下发「省级/市州级/县市级」并附 6 位编码"
                "末位提示。"
            ),
            "创建组织：编码必填、纯数字 6 位；层级由编码自动推导（显式传值必须一致，否则 422）；跨级校验（子级必须恰为父级 +1，根组织只能建省级）；删除旧 ORG%06d 自动生成编码分支。",
            "更新组织：编码锁定（创建后不可修改，需变更请停用后新建），返回 422 并说明原因。",
            (
                "自助注册默认关闭：新增配置 SELF_REGISTER_MODE（默认 off），关闭时POST /auth/register 返回 403「系统已关闭自助注册，请联系管理员创建账号」；新"
                "增公开端点 GET /auth/public-config。"
            ),
            "注册不再自动创建组织：self_verify_org_pass_code() 找不到组织时直接返回 None。",
            "账号解锁：新增 POST /users/{user_id}/unlock（仅管理员；清锁定计数 + 写 account_unlock 审计）。",
            "前端对齐：组织列表/详情层级标签改为「省级单位/市州级单位/县市级单位」；组织表单编码必填并提示 6 位规则。",
            (
                "新增 backend/tests/unit/test_p1_admin_area_code.py（28 例）：编码校验三分支、层级推断三档、跨级校验、编码锁定、注册开关、公开配置、账号解锁"
                "（404/403/成功）。"
            ),
            "更新既有组织/枚举/认证/覆盖用例至新契约（编码必填、3 级枚举、默认关注册）。",
        ],
    },
    {
        "version": "1.17.0",
        "date": "2026-10-23",
        "description": "介质链路治理（查重/台账/单位码/回执） + 系统自检 + W27 全栈收敛",
        "features": [
            (
                "整包查重：新增 services/package_import_guard.py，以整包 SHA256 为指纹查 audit_logs 台账；同一包重复导入默认 409，需显式 force"
                "=true 放行。数据包 / 授权包 / 权限包 / 配置包四类导入已接入。"
            ),
            "导入台账：导入成功写 package_import（类型/来源单位码/校验和/记录数/结果），查重与追溯共用一张表，不新增业务表、不新增迁移。",
            "导入回执：确认导入后写 package_receipt（接收单位码、来源单位码、记录数、冲突策略），上级凭回执即可登记闭环。",
            (
                "来源单位码核对：新增 services/package_org_code.py；数据包导入时比对包内 org_code与本机目标单位码，不一致默认 409 阻断（allow_org_mis"
                "match=true 可放行），防止\"把上级/邻县的包导进本单位\"后数据挂错组织树。"
            ),
            "冲突策略落库：确认导入时把「逐条比对 / 以包为准」写入导入历史 details_json，事后可追溯。",
            (
                "前端：新增 components/import/ImportPreviewDialog.vue（包信息 + 差异 + 重复告警 + 策略三选）；数据包接收页与授权包导入页在收到 409 时"
                "弹出该确认框，用户确认后带 force=true 重传。"
            ),
            (
                "新增 services/self_check_service.py 与 GET /api/v1/self-check（仅管理员），一次体检 6 项：单位码（缺失/格式/层级不符/重复）、组"
                "织层级（跨级挂接/根非省级）、待审核账号、账号锁定、PII 密钥指纹、介质导入近况（近 30 天失败数）。"
            ),
            "「系统设置」页新增自检卡片（components/system/SelfCheckCard.vue）：正常/提醒/异常三态，每项带可读说明，一键重新检查。",
            (
                "包完整性校验（core/package_integrity.py）：管控包 / 配置包 / 权限包导入强制校验 checksum；配置 PACKAGE_PUBKEY 后强制验签（fail-"
                "closed）。生成侧配 PACKAGE_SIGNING_KEY 即签名。"
            ),
            "经费禁止自批（FUND_ALLOW_SELF_APPROVAL 默认 False）：创建人不得审批自己创建的经费记录。",
            (
                "跨机业务键修复：BUSINESS_KEYS 由「仅组织」改为「组织 + 业务唯一标识」（villages: 组织+县+村名；projects/funds/schools: 组织+code）"
                "，修复同组织两台机器导入时\"记录被整体覆写或静默丢弃\"的 P0 缺陷；业务键不可判定时改走 relocated（新增行），绝不覆写。"
            ),
            (
                "迁移 r36~r41：删除 rural_tasks / budget_records / annual_income / issues 等零引用表与列，全部沿用「空表 DROP / 有数据"
                "改名归档」契约。test_p3_self_check_service.py（18 例）、test_p3_self_check_api.py（2 例）；守卫模块与自检服务覆盖率均 100%；"
                "前端自检卡片 10 例 / 100%。"
            ),
        ],
    },
    {
        "version": "1.17.1",
        "date": "2026-10-24",
        "description": "版本号口径修复 + 本地安装包构建修复",
        "features": [
            (
                "/health 版本号不再被陈旧构建指纹覆盖：_build_info.json 是 CI 构建产物（已 gitignore），开发机残留上一次构建的指纹时，/health 会一直报旧版本（"
                "实测 v1.15.7 vs 代码 1.17.0），运维据此误判\"版本未生效\"。"
            ),
            (
                "scripts/build/build-installer-local.ps1 补 UTF-8 BOM：该脚本含中文且此前无 BOM，Windows PowerShell 5.1 按 GB"
                "K 解析 → Array index expression is missing 等语法错误，本地安装包构建完全不可用。"
            ),
            (
                "新增 docs/02-用户手册/介质数据包导入与系统自检操作说明.md：离线介质包的查重 / 来源单位码核对 /导入台账与回执、六项系统自检、多机交接推荐流程与常见问题。已加入用户手册索引"
                "。"
            ),
        ],
    },
    {
        "version": "1.17.2",
        "date": "2026-10-24",
        "description": "端到端排查修复：组织创建不可用 + 自检路径错位",
        "features": [
            (
                "创建组织在真实 HTTP 下必然失败（严重）：OrganizationCreate schema 漏掉 code 字段，而端点 api/v1/organization.py 创建路径直接读"
                " data.code —— Pydantic 模型无此属性，请求一进来就 422（校验层）/AttributeError。单元测试用 MagicMock 传 data 时不会暴露。后果：新"
                "装机器无法创建任何组织 → 上下级部署无法初始化。"
            ),
            (
                "系统自检端点路径错位（真机 404）：模块注册在 /api/v1/self-check（根级），而前端与文档调用 /api/v1/system/self-check（system 包聚合路"
                "由）→ 设置页自检卡片恒 404。修复：改为经 api/v1/system/init.py 聚合注册（与 diagnostics / business-health 同构），并移除 api"
                "/v1/init.py 中的重复单独注册。"
            ),
            (
                "tests/unit/test_p3_org_create_http_contract.py（8 例）：只走 TestClient，锁定「缺 code → 422 / 短码 → 422 /"
                " 非数字码 → 422 / 合法载荷不被 schema 拦」。"
            ),
            (
                "test_p3_self_check_api.py 增补路径契约用例：断言路由为 /api/v1/system/self-check、根级不存在，并校验前端 api/selfCheck.t"
                "s 调用路径与后端一致。"
            ),
            (
                "6 个从未接入任何页面的通用组件：AppEmpty / AppError / AppLoading /AppPageHeader / AppStatCard / AppTableToolb"
                "ar。核实方式：src//*.vue 中既无<AppXxx> 也无全局名 <CommonAppXxx> 引用；components.d.ts 里只是自动注册残留。"
            ),
            (
                "ErrorBoundary.vue 予以保留：审计脚本初判\"不可达\"是误报 ——layouts/DefaultLayoutSafe.vue 通过全局名 <CommonErrorBoun"
                "dary> 使用它。这条误报说明「只查 <ErrorBoundary> 标签」不够，必须同时查 unplugin 的 Common 前缀。"
            ),
            (
                "3 个一次性 PPT 版本脚本：scripts/update_pptx_versions_20260912/20261016/20261017.py。全仓无任何引用，其职能已被 docs/"
                "build_ppt.js 源码重建取代。"
            ),
            "后端 12 段全量回归（14,404 用例）+ 前端 329 文件 / 6,995 用例，覆盖率门禁均 100%。",
            (
                "本机验证补充：vue-tsc --noEmit 0、ESLint（CI 口径 eslint src --max-warnings=0）0、npm audit --omit=dev 0 漏洞"
                "、文档死链 0、check_doc_numbers --full 四项全 ok、PPT 53 页 0 溢出。"
            ),
        ],
    },
    {
        "version": "1.17.3",
        "date": "2026-10-24",
        "description": "打包环境可用性修复（前端目录自发现 + 完整性检查误报）",
        "features": [
            (
                "打包后端在无环境变量时找不到前端（真机白屏风险，重要）：Electron 通过 http://127.0.0.1:<port> 加载界面，依赖环境变量 FRONTEND_DIST_PATH"
                " 指路。但 PyInstaller onedir 的实际布局是<resources>/backend/assistance-backend/_internal（_MEIPASS）+<res"
                "ources>/frontend（与 backend 同级）…"
            ),
            (
                "冻结运行时误报「关键文件缺失」：startup/environment.py 对 app/core/config.py 等 4 个.py 源文件做存在性检查，而 PyInstaller 包"
                "里源码已编译进可执行文件 —— 启动日志恒刷 4 条WARNING 文件完整性检查: 关键文件缺失: app/core/config.py，让运维误判\"安装包损坏\"。"
            ),
            "test_static_files.py 增补 onedir 布局推导用例（上溯三级 = resources，前端在其下）；",
            "test_environment_integrity_helpers.py 增补「冻结跳过 / 开发态保留」双向用例。",
        ],
    },
    {
        "version": "1.17.4",
        "date": "2026-10-24",
        "description": "离线瓦片包导入被 10MB 请求体上限拦截（现场 413）",
        "features": [
            (
                "导入瓦片包报「上传内容超过大小限制 (10MB)，请拆分或压缩后重试」：BodySizeLimitMiddleware 对 multipart 请求只在路径命中 LARGE_PAYLOAD"
                "_PATH_PREFIXES时才采用分级上限；"
            ),
            (
                "回归测试：backend/tests/unit/test_body_size_limit_map_tiles.py（6 项，覆盖 512MB 放行、前缀覆盖、非 multipart 仍 1"
                "0MB、未登记路径伪造 multipart 仍 10MB、备份 10GB 不受影响）；中间件模块覆盖率 100%；实测 12MB / 60MB multipart 已能到达端点（返回 40"
                "3 CSRF 而非 413）。"
            ),
            "版本号单源同步至 1.17.4（node scripts/sync-version.js --write，14 个文件）。",
        ],
    },
    {
        "version": "1.18.0",
        "date": "2026-10-24",
        "description": "离线加固批次：告警开关 / 误导口径 / 备份可迁移 / 麒麟数据目录 / 长期运行可靠性",
        "features": [
            (
                "OFFLINE_MODE 统一开关（默认 True）：alert_service 邮件/Webhook 两通道入口先短路（INFO + return False，不做配置解析/DNS/建连"
                "）；需外呼时设 OFFLINE_MODE=false。SMTP 同步调用改 asyncio.to_thread，不再阻塞事件循环。"
            ),
            (
                "备份携带密钥指纹：backup_info.json 新增 key_fingerprint（SHA256 前 16 位，复用 pii_crypto.key_fingerprint()，不含密"
                "钥本体）。恢复时指纹不一致 → 409（allow_key_mismatch=true 可强制，写审计system_restore_key_mismatch）；旧备份无字段仍兼容。"
            ),
            (
                "/health 新增 clock 与 database 只读块：时钟漂移 {status, behind_days}（120s TTL 缓存、不含异常原文）；数据库 {journal_mo"
                "de, journal_mode_ok, check_error_type}（WAL 不可用可见化）。顶层 status/HTTP 码不变。"
            ),
            (
                "备份启动补跑（catch-up）：启动 15s 后若\"从未备份或距上次 > backup_interval_days\"立即补跑一次（threading.Timer 登记 _timers"
                "、不自我重排；补跑后当日 02:00 任务自然跳过）。"
            ),
            (
                "麒麟/离线数据目录收口：Linux/打包态数据根改为 BUMOFU_DATA_DIR → XDG_DATA_HOME/bumofu →~/.local/share/bumofu（不再回退 "
                "~/.bumofu）；get_backup_path() 支持 BACKUP_DIR 优先（三段链）；get_cache_path() Linux 分支对齐 <app_data_dir>/"
                "cache。"
            ),
            (
                "Windows 构建脚本：新增 scripts/build/sync-frontend.ps1（robocopy 等价同步，替代失效的 bash 脚本）与scripts/build/bui"
                "ld-win.ps1（TEMP 重定向规避 esbuild Access is denied；可选 -IncludeMapTilesInBackend）。"
            ),
            (
                "安装包瘦身：assistance-backend.spec 瓦片收集改为构建开关 INCLUDE_MAP_TILES=1（默认关）；Electron 版由extraResources + "
                "MAP_TILES_DIR 提供瓦片，不再重复打包（实测 378.4MB → 316.7MB，省 61.7MB；解包 826.9MB → 763.7MB）。ARM64 standalone"
                " 不受影响。"
            ),
            "/api/v1/map/config 的 map_type：\"gaode\" → \"vector\"（前端零消费方）。",
            "通知偏好 3 个端点响应追加 emailChannel: \"unavailable_offline\"（只增不删）。",
            "httpx 登记运行时必需依赖（启动期硬依赖，此前缺失即 ImportError 且自检不覆盖）。",
            "scripts/check_doc_numbers.py 输出改 UTF-8（修复 Windows GBK 控制台下 ✓ 触发 UnicodeEncodeError 假红）。",
            (
                "POST /api/v1/system/admin/restore?filename= 旧端点直接 shutil.copy2 覆盖 DB，绕过维护窗口/schema 校验/密钥指纹闸门；前"
                "端零调用，建议下线或改走 restore_backup()。"
            ),
        ],
    },
    {
        "version": "1.18.1",
        "date": "2026-10-24",
        "description": "登录门面重构 / 三层对齐门禁 / 门禁真绿复验",
        "features": [
            (
                "登录页公开配置扩展：GET /api/v1/auth/public-config 新增 lockout_minutes / max_failed_attempts（纯策略参数）。前端据此显"
                "示「锁定 30 分 00 秒」倒计时与\"再错几次会被锁\"，用户不再只是看到一行字。刻意不返回组织名/单位码（登录前不泄露部署单位身份）与\"全局 2FA 开关\"（本系统 2FA 是按"
                "用户开启，硬造一个恒 false 的字段只会误导调用方）。"
            ),
            (
                "三层对齐门禁 scripts/check_stack_alignment.py + CI job + 自测tests/unit/test_stack_alignment_gate_r35."
                "py（含负向用例）：比对 前端 API 路径 ↔ 后端路由、ORM 模型 ↔ 数据库 schema（基线为\"临时空库 + alembic upgrade head\"…"
            ),
            (
                "迁移 r42_align_stack_columns_001：tea_plantations / cactus_fruit_plots 的village_id → supported_vi"
                "llage_id（索引名同步）；补齐 households.remarks、projects.region_code两个\"库里有、模型没声明\"的列。"
            ),
            (
                "覆盖率回归测试 tests/unit/test_coverage_restore_after_merge.py（12 例）：补 repr 可安全输出、备份元信息三种入参形态、增量包指纹有/"
                "无、无组织字段模型的过滤分支、单位码 409 阻断、密钥不一致时临时包清理的三个分支。"
            ),
            "登录页重构（frontend/src/views/auth/LoginEnhanced.vue）",
            (
                "authStore.login 错误传播修正：原先只读 err.response.data.message，而 FastAPI 返回 detail ——于是 423「账户已锁定，请30分钟"
                "后再试」这类中文文案全部丢失，用户看到的是 Request failed with status code 423。"
            ),
            (
                "MessageCenter 契约对齐：MessageListResponse 按后端实际改为 total_pages（无 unread_count），列表页改为直接调用独立的未读数端点（原"
                "代码读已删除字段，vue-tsc 报错且永远走 fallback）。"
            ),
            (
                "system/backup.py：去掉 BackupKeyMismatchError 分支里不可达的 if file_path:（该分支只可能由restore_backup(file_pa"
                "th, ...) 抛错进入，此时 file_path 必已赋值）。"
            ),
            "文档与 PPT 同步至 v1.18.1（PPT 新增「登录门面与门禁真绿复验」一页，全部数字按实测刷新）。",
            (
                "注册入口死链：SELF_REGISTER_MODE 默认 off，但登录页无条件显示\"注册账户\"，而前端从未调用后端早已提供的 public-config。现按配置显隐，取不到配置即隐"
                "藏（fail-closed）。"
            ),
            (
                "100% 覆盖率门禁静默失效：backend/.coveragerc 在工作区被误删，fail_under=100 不再生效 ——分段执行器报告的 12/12「全绿」实际只有 99%。已恢"
                "复配置并补齐 7 处缺口，现为TOTAL 45,782 语句 / 11,376 分支，Miss 0 / BrPart 0。"
            ),
            (
                "行业模型与库列名漂移：r42 迁移注释写明\"模型列名改为 supported_village_id\"，但 app/models/industry.py未改，导致三层对齐门禁 B 轴报 "
                "4 条不一致。已按迁移声明的意图改名（全仓无其它引用）。"
            ),
        ],
    },
    {
        "version": "1.18.2",
        "date": "2026-10-25",
        "description": "瓦片底图“加载失败已切回矢量”根治（边缘 404 不再整体回退）",
        "features": [
            (
                "422 校验错误中文化 + 不再回显 input（后端根因）：此前只注册了 pydantic 的ValidationError 处理器，FastAPI 的 RequestValidatio"
                "nError 无人接管 —— 422 返回的是英文数组 detail: [{loc, msg: \"Field required\", input: \"明文密码\", ...}]。"
            ),
            (
                "前端统一出口保证永不显示技术原文（src/utils/getErrorMessage.ts 重写）：新增isRawAxiosMessage()（识别 Request failed with"
                " status code N / Network Error /timeout of Xms exceeded / Failed to fetch）、statusFallbackMessa"
                "ge()（400/401/403/404/409/413/429…"
            ),
            (
                "拦截器与视图层对齐：src/api/request.ts 的 _extractServerMessage / _buildUserMessage改为复用同一套提取口径（Blob 响应体也走"
                "它），并按状态码给中文兜底；20 处ElMessage.error(error.message || '…') / const msg = e instanceof Error ? e.m"
                "essage : '…'统一改为 ElMessage.error…"
            ),
            (
                "新增门禁 scripts/check_error_message_leaks.py（CI static-analysis）：扫描frontend/src 面向用户的提示调用（ElMessa"
                "ge.* / ElNotification.* / notify(），发现直接取 error.message 即失败；实现层（getErrorMessage.ts / request.ts"
                " /errorHandler.ts）豁免。"
            ),
            (
                "前端不再因边缘 404 整体回退：TileLayer 增加 bounds（只在覆盖范围内请求）+ errorTileUrl（透明 1×1，404 渲染空白不破图）+ maxNativeZo"
                "om；Map 增加 maxBounds（bbox 外扩 0.05°）+maxBoundsViscosity:1 + worldCopyJump:false；开局 fitBounds(覆盖 "
                "bbox, maxZoom:9)，不再固定 zoom 7；"
            ),
            (
                "后端诊断字段：GET /api/v1/map/tile-info 新增 bbox（MANIFEST region.bbox → bbox → 贵州兜底）、source（env/meipas"
                "s/dev）、reason（dir_missing/no_tiles，可用时 null）；MANIFEST 归一化白名单放行并校验 bbox/region（有限数值、经纬度范围、min<m"
                "ax），脏值逐级回退。"
            ),
            "回退提示带诊断：提示追加 available/tileCount/source/reason，现场可区分“没装瓦片”与“真故障”。",
        ],
    },
    {
        "version": "1.18.3",
        "date": "2026-10-25",
        "description": "多包瓦片覆盖并集 / 旧恢复端点下线 / 跨密钥恢复 UI / 签名门禁",
        "features": [
            (
                "多包叠加导入后覆盖范围被最后导入包限制（P0）：MANIFEST.json 是\"最后导入包\"，region.bbox 只有该市州；/map/tile-info.bbox 改为磁盘实测并"
                "集（scan_tiles_dir 顺带累计 _tile_lonlat_bounds，常量级运算不额外遍历），MANIFEST 仅作回退。先导贵阳再导遵义，前端 maxBounds 现在覆盖"
                "两者并集（此前贵阳瓦片被挡在视野外）。"
            ),
            (
                "旧管理员恢复端点下线（安全）：POST /api/v1/system/admin/restore 改为 410 Gone，删除 shutil.copy2 覆盖数据库逻辑（测试断言 shut"
                "il.copy2/get_database_path/get_backup_directory 均未被调用），保留 require_admin（401/403 优先）与 filename "
                "参数契约（端点数 849 不变，标 deprecated）…"
            ),
            (
                "跨密钥恢复有 UI 入口：前端恢复遇 409 且 detail 含\"密钥\"→ 展示危险勾选 +confirmDanger 二次确认 → 带 allow_key_mismatch=tru"
                "e 重试一次；取消不重试、不抛错。上传恢复（FormData）同样支持。"
            ),
            (
                "CI 签名门禁：build-windows.yml 新增 Verify installer signature —— 配置 CSC_LINK时 Status 必须 Valid 否则构建失败"
                "；未配置则 ::warning:: + Step Summary 标注\"未签名，以 SHA256SUMS 为准\"。"
            ),
            "文档：API 文档标注该端点停用；瓦片指南补\"边缘 404/诊断字段\"排障；代码签名文档补 CI 接线；离线加固文档遗留项标记完成。",
            (
                "electron 外壳单测长期不在版本库里：.gitignore 的 *.test.js 通配只给backend/tests/ 与 frontend/ 开了白名单，漏了 electron/"
                "tests/ ——file-chunk.test.js、path-guard.test.js 一直\"磁盘上有、库里没有\"，CI 与全新 clone 都拿不到（worker-pool.t"
                "est.js 只因早于该规则才侥幸入库）。"
            ),
            (
                "electron 单测此前无人执行（孤儿测试）：package.json 新增 test:electron（Node 内置 runner，零第三方依赖），并接进 两个 CI 作业 ——fr"
                "ontend-check（Linux）与 windows-smoke（Windows，该作业新增 setup-node）。Windows 侧必须有：Linux 全绿对路径语义毫无证明力（v"
                "1.12.3 编码崩溃、v1.12.6 GBK 管道均属此类）。"
            ),
            (
                "发布门禁等待预算与实测压线：build-arm64.yml 两处 check_release_gate.py --timeout-minutes由 30 → 90。本仓 PR Checks"
                " 实测 17.4 / 22.6 / 30.2 / 30.2 分钟，原值 30 与最慢一次正好压线；"
            ),
            (
                "接线守卫 electron/tests/ci-wiring.test.js（4 例）：断言 test:electron 存在、两个作业都执行它、windows-smoke 配了 setup"
                "-node、两个构建工作流的门禁等待 ≥ 60 分钟。已实证\"能红\"：把 arm64 临时改回 30 → 该测试 EXIT=1，还原 → EXIT=0。"
            ),
        ],
    },
    {
        "version": "1.18.4",
        "date": "2026-10-25",
        "description": "瓦片覆盖 bbox 取最细 zoom（修正 1.18.3 概览瓦片撑大 maxBounds）",
        "features": [
            "scan_tiles_dir 的覆盖范围改为按 zoom 分组累计、取最细 zoom 的实测并集",
            "test_tile_info_coverage_bbox.py 等 163 项相关测试全绿；flake8 0。",
            "v1.18.3 的 tag 已推送并触发过 CI；v1.18.4 为最终交付版本（1.18.3 的 bbox 取值偏大，属体验缺陷非功能故障）。",
        ],
    },
    {
        "version": "1.18.5",
        "date": "2026-10-25",
        "description": "修正 1.18.4 的 bbox 补丁未生效（真正取最细 zoom）",
        "features": [
            (
                "scan_tiles_dir 改为按 zoom 分组累计（每个 z 目录单独合并 _scan_x_dir 的 bounds，存 bounds_by_zoom），最终 bounds 取 bo"
                "unds_by_zoom[max(...)]。"
            ),
            (
                "实测（resources/map-tiles，5,623 张 z5–12）：bounds = [103.53515625, 24.5271348225978, 109.6875, 29.2"
                "2889003019423] —— 贵州辖区量级；修正前为 [101.25, 21.94, 112.5, 31.95]。"
            ),
            "多包叠加语义不变：同一 zoom 内仍为各包并集（有 22 项 bbox 测试覆盖，含贵阳+遵义并集用例）。",
            (
                "test_tile_info_coverage_bbox.py / test_map_tile_info_diagnostics.py /test_offline_map_service."
                "py / test_tiles_pipeline.py 合计 163 passed；flake8 0。"
            ),
            "真机（打包后端）复验：tile-info.bbox 为上述辖区量级；覆盖区内瓦片 200、区外 404。",
            (
                "composables/useFormDraft.ts（表单草稿自动保存）：本次改动中最能直接省人力的一个 ——现场录到一半被电话/查台账打断，原来一离开页面输入全丢（这类表单普遍 10+"
                " 字段）。"
            ),
            (
                "utils/parsePastedTable.ts（Excel 粘贴解析）：现场数据多数先在 Excel/WPS 整理好，逐条手敲是最费时的一步。解析器处理了真实形态：\\r\\n/裸 "
                "\\r、行尾多余制表符、空白行、双引号包裹且含制表符/换行的单元格（\"\" 还原为引号）；并设行列上限（默认 500×50，超限不静默截断而是返回 exceeded 让页面提示分批粘贴）"
                "。"
            ),
            (
                "测试：useFormDraft.test.ts 23 例、parsePastedTable.test.ts 17 例；两文件覆盖率 100/100/100/100（含分支）；vue-tsc"
                " 0、eslint 0 error。"
            ),
            "说明：本批交付的是可复用基座；接入具体表单页（并配 useDirtyGuard 铺开）在下一批完成 ——目前全仓只有 projects/Edit.vue 一个页面接了离开拦截。",
            (
                "views/policies/Edit.vue 接入 ③：草稿键按模式隔离（policies:edit:new /policies:edit:<id>）；onMounted 里若存在草稿则"
                "先问再恢复（ElMessageBox.confirm），用户忽略则删除草稿；onBeforeUnmount 立刻 flush() 落盘（防抖窗口内离开也不丢）；提交成功后 clear() "
                "+ 复位脏标记（避免下次进来\"复活\"已提交数据）。"
            ),
            (
                "离开拦截接线：useDirtyGuard(isDirty) —— 此前全仓只有 projects/Edit.vue 接入，本批再补一个录入型页面。实现上刻意不造\"只在初始化后注册 wat"
                "cher\"的可选链（那会留下永不进入的分支，是覆盖率黑洞），改为 setup 即注册、初始化完成后复位脏标记。"
            ),
            (
                "测试：Edit.test.ts 37 → 42 例（新增草稿恢复/忽略/守卫注册/卸载落盘/提交清草稿），该页覆盖率仍 100/100/100/100；vue-tsc 0；eslint s"
                "rc --max-warnings=0 通过。在未接入版本上同样存在（已用 git checkout 对比验证），属既有测试桩行为，非本次引入。逐行报告失败（哪一行、为什么）而不是整体失败"
                " —— 否则用户只能全量重来，而重来会重复入库。"
            ),
        ],
    },
    {
        "version": "1.18.6",
        "date": "2026-10-25",
        "description": "仓库卫生与门禁加固（scripts 纳入 flake8、全仓 flake8 归零）",
        "features": [
            (
                "backend/app/ flake8 归零（79 → 0）：78 处 E302/E305（app/models/ 14 个文件顶层定义之间只有 1 个空行）+ 1 处 F401（mode"
                "ls/monitoring.py 未使用的 JSON 导入）。修法为纯空行/导入整理，无逻辑变更。"
            ),
            (
                "scripts/ flake8 归零（19 → 0）：未使用导入 4 处（run_backend_tests_segmented.py的 shutil、docs/extract_api_e"
                "ndpoints.py 的 re、security/pii_scan.py 的 io/os）、E401×2 / E302 / E305 / E303 各 1（pre_commit_hook"
                "s.py、ppt_overflow_check.py）、W292…"
            ),
            (
                "frontend/package.json 补 engines：node: ^20.19.0 || >=22.12.0（对齐 Vite 7 的实际要求；本机实测 Node 25.2.1）。"
                "此前无任何约束。"
            ),
            (
                "密码哈希改 bcrypt 直连（app/core/security.py）：passlib 1.7.4 在 bcrypt 5.x 下后端探测失败，且失败状态在进程内永久缓存 —— 大批量收"
                "集时随机抛passlib.exc.MissingBackendError，使 test_soft_delete_coverage / test_supported_village_api直"
                "接收集失败、覆盖率失真。"
            ),
            (
                "MANIFEST bbox 只校验长度不校验数值（api/v1/map.py）：[\"x\",1,2,3] 这类非法 bbox会被当作 Leaflet bounds 传给前端，地图表现为不"
                "显示 / 异常缩放。新增 _valid_bbox()校验「4 个有限数值」，并排除 bool / NaN / ±inf。"
            ),
            (
                "消除唯一 skip（tests/unit/test_offline_log_path_w18.py）：打包态日志路径改写回归原先用 skipif 跳过开发机 —— 等于该核心回归永不在本地"
                "验证。改为monkeypatch sys.frozen=True，与真实打包态走同一分支。"
            ),
            (
                "BaseChart 主题重建入口显式暴露（components/common/BaseChart.vue）：rebuildForTheme 仅靠全局自定义事件触发，多套件并行时覆盖归属漂移"
                "（单跑 100%、全量 99.8%）；defineExpose 暴露 rebuild() 后可直测。"
            ),
            (
                "覆盖率门禁两处失效根治（scripts/run_backend_tests_segmented.py）：① .coveragerc 缺失时 fail-fast（历史：被清理分片误删 → f"
                "ail_under 静默失效，门禁假绿）；"
            ),
            (
                "复验口径：后端 12 段全 PASS / 0 failed / 0 skipped，对累积数据 coverage report= 100.00%（45955/45955 语句、11450/"
                "11450 分支）；前端 334 文件 / 7138 用例全 PASS、覆盖率四项 100%（--maxWorkers=2 避免并发抢 worker 导致The service is no"
                " longer running 假失败）；"
            ),
            "⑥ 分页上限改造引入的 6 处回归（本版修复；12 段复验时 seg10/seg12 各挂 1/5 例）",
            (
                "CI 增补 scripts/ flake8 步骤（.github/workflows/pr-checks.yml 的 lint 作业）：flake8 ../scripts/ --max-l"
                "ine-length=120 --count --max-complexity=40 --exclude ../scripts/archive。"
            ),
            (
                "版本 1.18.5 → 1.18.6，node scripts/sync-version.js --write 同步 22 处目标（14 个文件已更新）。https 协议的 git 操作可"
                "用 gh 凭证；本仓 origin 仍为 SSH，推送走既有 id_rsa 不变。+ cd frontend && npm test -- --run（前端全量）+ vue-tsc --n"
                "oEmit。"
            ),
        ],
    },
    {
        "version": "1.18.7",
        "date": "2026-10-25",
        "description": "录入效率包收口 / 数据同步胶囊 / OCR 建议 / 视觉回归 44 页 / 发布工具加固",
        "features": [
            (
                "批量粘贴弹窗 BulkPasteDialog（③）：粘贴 → 预览 → 逐行校验 → 确认，四步可视化；配套 useBulkCreate 批量新增执行器（串行提交、逐条失败明细、摘要话术）"
                "。"
            ),
            "消费帮扶台账接入批量粘贴（③ 收口）：逐行校验 + 串行新增 + 失败行号原样回传，不整批回滚。",
            "草稿自动保存扩到 4 个页面（③）：学校编辑、组织编辑等页面接入 useFormDraft +未保存离开拦截；切页/刷新不丢输入。",
            "顶栏数据同步状态胶囊 + 台账抽屉（④）：只读 /data-sync/logs，不新增接口；异常状态一眼可见并可下钻。",
            "经费凭证 OCR 字段级建议（⑤）：接入转账凭证新建对话框，识别金额/日期给出建议并由人工确认（后端能力早已存在，此前前端零调用）。",
            "VirtualList 虚拟滚动基座（⑥）：窗口算术抽成纯函数（22 例测试，双文件 100% 覆盖）。",
            "usePageSize 每页条数偏好（⑥）：偏好记忆 + 归一化，项目列表接入。",
            "视觉回归扩到 44 页（⑨）：30 个 console tab + 4 个核心表单，DOM 结构快照不比对像素。",
            "E2E 新增村庄表单断言：顶栏同步抽屉的隐藏元素污染 .first()，改用 :visible。",
            "Nightly 分组漏根目录：补跑 tests 根目录，permission_packs 覆盖率 38% → 100%。",
            (
                "release_tag 工具链：输出改 UTF-8；工作区脏时提供 --allow-dirty 逃生口（tag 仍只指向已推送 commit）；ci_green 兼容 stdout/std"
                "err 为 None；裸 pragma 补理由（F2 棘轮 1 → 0）。"
            ),
            "新增 PR/Nightly 覆盖率一致性门禁：防止两套口径长期漂移。新增 RELEASE_NOTES-v1.18.7.md；系统介绍 PPT 升级为 v1.18.7 / 56 页。",
        ],
    },
    {
        "version": "1.18.8",
        "date": "2026-10-26",
        "description": "全面收口：逐一代码体检 + 项目整理 −1880 文件 + 分段覆盖率门禁修复",
        "features": [
            "分段覆盖率门禁的 coverage combine 一直在失败，且失败信息被吞掉（scripts/run_backend_tests_segmented.py）",
            (
                "OrganizationService.get_ancestors() 在 path 为 NULL 时抛异常，令数据上报创建直接 500（app/services/organization"
                "_service.py）"
            ),
            (
                "删除 .scratch/tiles-import-test/（1423 个文件）：瓦片导入测试的中间产物，在 py/ts/vue/js/md/yml/json/ps1/sh 全量检索中零引"
                "用（含文档与 CI），删掉不影响任何测试或构建。"
            ),
            (
                "删除 .qoder/（456 个文件，含 1.8 MB repowiki-metadata.json）：AI 工具生成的仓库知识库缓存。本仓《项目文件结构说明.md》本就把它标注为「机器本"
                "地元数据，不参与交付 ❌」—— 文档说不该入库，实际却跟踪了 456 个文件，本次纠正。"
            ),
            "删除 .scratch/r34-final/帮扶管理信息系统介绍-原始备份.pptx（1.0 MB）：与 docs/ 正式版重复且零引用。",
            (
                "补 .gitignore：.scratch/tmp/、.qoder/、.reasonix/、.zcode/、deliverables/releases/、*.exe|*.msi|*.dmg"
                " —— 防止同类产物再次混入版本库。"
            ),
            "未动（有引用/交付需要）：deliverables/（README/AGENTS/CHANGELOG 引用其中报告）、deploy/、nginx/、tests/（E2E 与性能入口）。",
            "backend/version.json：版本 1.18.8、release_date 2026-10-26、描述与 features 全量重写为收口结论。",
            (
                "系统介绍 PPT：版本页脚与\"数据来源\"日期同步至 v1.18.8 / 2026-10-26，保持 56 页与既有版式（python-pptx 原位改文本，不动版式；改后跑 scrip"
                "ts/ppt_overflow_check.py 校验无溢出）。"
            ),
            "README / CLAUDE.md / AGENTS.md / 《项目文件结构说明.md》文件数与实测对齐。",
        ],
    },
    {
        "version": "1.18.9",
        "date": "2026-10-26",
        "description": "应用内更新日志接入唯一账本 + 发布说明一致性门禁（根治版本说明漂移）",
        "features": [
            (
                "应用内更新日志长期不更新：update_log_service.py 里的 240 行硬编码历史被删除，改由 backend/app/services/version_history_da"
                "ta.py 提供，该文件由scripts/sync_update_log.py 从 CHANGELOG.md 生成（1.0.0 起的全部历史版本）。改版本说明只需改 CHANGELOG，不"
                "再需要手抄第二份。"
            ),
            (
                "同一天多个版本的顺序是随机的：created_at 只按日期写入（1.18.2–1.18.7 全是 2026-10-25），同一时间戳下 ORDER BY created_at DESC "
                "的顺序不稳定，实测 1.18.2 会排在 1.18.3 前面。修法：初始化/同步时按版本序号加秒偏移（前端只显示日期，秒级偏移不可见），查询再加 version DESC 兜底，历史库里的"
                "老数据也能稳定倒序。"
            ),
            (
                "升级用户的旧库只补当前一条：check_and_record_version_change 原先只在\"版本号变了\"时补记一条，中间版本仍然缺失（老库会从 1.1.1 直接跳到 1.18"
                ".9）。改为每次启动做一次幂等补齐：一次性取出已记录版本集合，缺哪条补哪条，已存在的不动。"
            ),
            (
                "「系统设置」聚合页只有一个页签（归类错位）：config-package（系统配置）被挂在「备份与存储 › 数据包与存储」下，导致「系统设置」只剩「更新日志」一项，页面自己的描述也只能写成"
                "\"更新日志等基础系统配置\"；而 SettingsOverview.vue 的「配置管理」分组一直把「系统配置 + 更新日志」并列 —— 两处口径互相矛盾。"
            ),
            "scripts/check_update_log.py 发布说明一致性门禁（已接入 pr-checks 的 static-analysis 与make test-local），一次校验三处",
            (
                "单元测试 tests/unit/test_update_log_sync.py：断言生成文件与 CHANGELOG 一致、最新版本等于 version.json、版本序列升序无重复、解析跳"
                "过 [Unreleased] / [未发布] 段。"
            ),
            (
                "backend/version.json 的 description 改为与 CHANGELOG 标题严格一致（原先为手工改写版本，已与标题漂移）；features 保留人工维护，只要求非"
                "空。所以\"表单漏了必填项\"不会被 TypeScript 发现；请求体从来没有被比对过 —— 这类「提交少字段 / 必填性不符」既躲过类型检查，也躲过门禁，只能等用户撞 422。"
            ),
            (
                "前端补字段：views/organization/List.vue 新增「组织编码」输入（必填 + ^\\d{6}$ 校验 +「省级 XX0000 / 市州级 XXYY00 / 县市级 X"
                "XYYZZ」提示），新增态可填、编辑态只读禁用（编码创建后不可修改），提交时新增带 trim 后的 code、编辑不提交 code；与 views/organization/Edit.vu"
                "e 的既有口径完全一致。"
            ),
            (
                "类型对齐：OrganizationCreate.code 改为必填；顺手修掉同源的三处漂移（D 轴首次运行即抓出，全部真实存在）：| 契约 | 漂移 | 处理 ||---|---|---|"
                "| DataReportCreate | 前端缺 report_type、title 后端必填前端可选、target_org_id 前端必填后端可选 | 按后端逐字段对齐 || Suppo"
                "rtedVillageCreate | department /…"
            ),
            (
                "Edit.vue 的 code: formData.code || undefined 改为 code: formData.code.trim() ——|| undefined 会把已通过"
                "校验的必填值静默丢弃，退化成后端 422。"
            ),
            (
                "前端 tests/unit/views/organization/ListCov.test.ts 追加 5 例（新增态渲染/可编辑、编辑态回填/禁用、校验规则 6 位、新增 payload"
                " 带 trim 后的 code、编辑 payload 不含 code）；同时修正既有用例里因新增输入而整体后移的 ElInput 索引。"
            ),
            (
                "后端新增 tests/unit/test_stack_alignment_gate_r35_axis_d.py（9 例：三个漂移方向、非 Create/Update 忽略、同名多义跳过、U"
                "pdate 后缀覆盖、当前仓库零漂移、report 含新字段）。"
            ),
        ],
    },
    {
        "version": "1.18.10",
        "date": "2026-10-26",
        "description": "WPS 兼容：.xls/.et 导入打通、格式白名单单一源、导出格式门禁",
        "features": [
            (
                "app/core/office_formats.py（格式单一事实源）：容器魔数（zip/OLE2）、可解析表格集合xlsx/xls/et、WPS 原生集合、附件 documents 白名"
                "单、导出白名单 xlsx/csv/docx/pdf、统一的 WPS 指引文案。纯函数、无 IO、无第三方依赖。"
            ),
            (
                "app/services/office_reader.py（统一读取层）：按容器魔数而非扩展名选择解析器（zip→openpyxl / ole2→xlrd / 其它→统一 400），提供 "
                "read_rows(content, filename) 与openpyxl 风格 load_workbook_any()（含 iter_rows/max_row/sheetnames/g"
                "etitem 替身）…"
            ),
            (
                "xlrd==2.0.1 依赖：backend/requirements.txt + app/core/required_packages.py（运行时必需）+ 3 个 PyInstalle"
                "r spec 的 hiddenimports 同步登记。"
            ),
            (
                "scripts/check_office_formats.py 门禁 + CI 接入（static-analysis）：导入禁止直连openpyxl.load_workbook、白名单禁止"
                "硬编码 endswith((\".xlsx\",\".xls\"))、导出扩展名必须在白名单内、CSV 必须带 UTF-8 BOM；并对 xlsx/xls/两种容器 .et 夹具做运行时自"
                "检（未装依赖的 CI 作业自动跳过，pytest 侧覆盖）。"
            ),
            (
                "回归用例：test_office_formats_wps.py（14 例）+ test_office_formats_gate.py（11 例，含 5 个负向用例保证门禁能红），夹具见 b"
                "ackend/tests/fixtures/office/。"
            ),
            (
                "导入解析统一收口到 office_reader：import_export/import_data、projects、school（3 处）、supported_village（3 处）、"
                "report_templates（2 处）、services/policy_import_service、services/excel_importer_service、services/"
                "batch_import_optimizer。"
            ),
            (
                "白名单统一：4 处硬编码扩展名判断改为 office_formats.is_spreadsheet_upload（含 .et），错误文案统一为\"支持 .xlsx/.xls/.et + W"
                "PS 另存为指引\"。"
            ),
            (
                "附件白名单：files.py documents 组改由 office_formats.DOCUMENT_UPLOAD_EXTS 提供，新增 .et/.wps/.dps（只存不解析，导入仍"
                "只接受可解析格式）。"
            ),
            "前端 accept 同步：Excel 上传 8 处补 .et（含 YearlyOverview 扩展名校验与提示文案、对应单测期望），区块附件上传补 .et/.wps/.dps。",
            ".xls 可传不可读（真实死路）：无 xlrd + openpyxl 不支持 OLE2 → 现在按容器走 xlrd。",
            "WPS .wps/.dps 附件被拒：现在可上传（仅存储），导入时给\"请另存为 .docx/.pptx\"的明确提示，不再抛裸异常。",
            (
                "新增用例：test_office_formats_wps.py 14 passed（xlsx/xls/两种容器 .et 读取、.wps/.dps 提示、白名单接受 .et、openpyxl"
                " 风格替身语义）+ test_office_formats_gate.py11 passed（含 5 个负向用例：裸 openpyxl / 硬编码白名单 / 非白名单导出扩展名 /缺 BO"
                "M 的 CSV 各自能红）+ 导出侧回读（模板 xlsx 可被…"
            ),
        ],
    },
    {
        "version": "1.18.11",
        "date": "2026-10-26",
        "description": "瓦片底图常显村/校名称 + 贵州 z13（16,422 张 / 95MB）+ 学校 POI 图层",
        "features": [
            (
                "瓦片底图常显村/校名称（方案 A）：zoom >= 12 常显帮扶村名、zoom >= 13 常显学校名（zoom < 12 仍仅悬停）；标签文本严格取 marker.name；防遮挡用 "
                "64×20px 像素格（学校优先 → 距视野中心近优先），单次上限 120 条；interactive:false + pointer-events:none不拦截拖拽；zoomend/m"
                "oveend 重算、只在显示模式变化时重绑 Tooltip；"
            ),
            (
                "OSM 提取 schema v2→v3：pois 图层：amenity ∈ {school, kindergarten, college, university}的 node 与 way "
                "质心（name:zh → name，无名称不输出，截断 100）；v1/v2 pkl 仍兼容。实测贵州：POI 682（school 559 / kindergarten 44 / col"
                "lege 54 / university 25）。"
            ),
            (
                "贵州 z13 全省瓦片包：16,422 张 / 97.6MB / 184s（89.2 张/秒，0 失败），导出 guizhou-z13.zip 95.1MB；MANIFEST zoom=["
                "13,13]、tileCount=16422、license ODbL-1.0 (© OpenStreetMap contributors)；verify_tiles --require-"
                "min 16400 通过；导入实测 16,422 张全部落盘。"
            ),
            (
                "render_osm_tiles.py 新增 --no-poi（z≤12 重渲时完全复现 v2 样式，避免高校标记\"回归\"）；内置安装包仍为 z5–12（316.7MB），z13 作为"
                "独立可选包导入（≤512MB 上限内，无需分包）。"
            ),
            "导入：管理员 → 系统管理 → 备份与存储 → 地图瓦片 → 导入瓦片包，选 guizhou-z13.zip；",
            "导入后地图最大 zoom 由 12 → 13，学校名开始出现（OSM 覆盖 682 处，非\"全部学校\"）；",
            (
                "帮扶村/学校官方名称以系统库为准：常显标签只显示 latitude/longitude 非空的记录，部署前需核查村/校坐标完整率（dev 库 6 村 0 坐标）；缺坐标的后端会按区县估算但"
                "带 isEstimated；"
            ),
            "视觉未人工核验（本会话模型不能读图），已用候选统计 + POI/--no-poi 像素差（4493/8268）佐证。",
        ],
    },
    {
        "version": "1.18.12",
        "date": "2026-10-26",
        "description": "贵州 z14 预渲染交付（全省包 283.7MB / 64,900 张；9 市州分包）",
        "features": [
            (
                "z14 全省瓦片渲染：64,900 张 / 296.9MB / 560.7s（115.7 张/秒，0 失败），样式 osm-vector-basemap-light-v3-poi（含学校 "
                "POI 682 个），bbox=贵州全省。"
            ),
            (
                "scripts/tiles/pack_prefecture_z14.py：把权威 z14 瓦片集打散为 9 个市州包（按 prefecture_bboxes.json + 0.02° pa"
                "dding；每包 MANIFEST 写 region/zoom/tileCount/ODbL）。"
            ),
            (
                "交付目录 deliverables/osm-tiles-z14-20261026/：guizhou-all_z14.zip（283.7MB，64,900 张）+ 9 个 guizhou-<"
                "slug>_z14.zip（合计 389.2MB，77,666 条目，含市州间重叠）+ SHA256/README/summary。"
            ),
            (
                "WPS 模块覆盖率缺口（CI backend-test 红）：app/core/office_formats.py 91.67%、app/services/office_reader.py"
                " 81.88%，全量门禁 99.95 < 100。"
            ),
            "OSM 数据建筑仅 20,393 处、POI 2,261：z14 可见路网/水系/村名/学校注记，没有建筑轮廓级细节；",
            "全省包 283.7MB 已接近导入体验上限，现场建议用市州分包按需导入。",
            (
                "损坏扫描守卫自身两个缺陷：① scripts/scan_mojibake.py --check 因本机运行时日志（frontend/logs-*.txt，正常含 NUL 且已被 .giti"
                "gnore 忽略）恒红 —— 守卫被当成噪音，\"扫描失败\"与\"提交照样过\"长期并存；"
            ),
            (
                ".gitignore 双编损坏吞掉两条规则（2026-10-24 7f8738b 引入）：三行注释被写成 GBK 双编，其中两行把 logs/ 与 _*.ps1 \"粘\"进注释行，规则实"
                "际失效（根目录 logs/ 不再被忽略）。按 git 历史原文还原三行注释，并把两条规则拆回独立行。"
            ),
            (
                "两道既有门禁从未在 CI 执行：scan_mojibake.py --check 接入 static-analysis；check_doc_numbers.py --full 接入 sta"
                "ck-alignment（该门禁需 import app.main 与pytest --collect-only，放无后端依赖的 static-analysis 会 ModuleNotFo"
                "undError 恒红）。"
            ),
            (
                "pre-commit 配置在\"python 不在 PATH\"的机器上必然失败：本地钩子language: system + entry: python scripts/... 改为 l"
                "anguage: python（由 pre-commit用运行它的解释器自建环境）；"
            ),
        ],
    },
    {
        "version": "1.18.13",
        "date": "2026-10-27",
        "description": "「数据概览」页改版 + 菜单↔路由标题 23 处对齐（新增门禁规则 F）",
        "features": [
            (
                "「数据管理」页改版为「数据概览」（views/dataManagement/Index.vue 重写）：· 核心指标常驻卡片（帮扶村总数 / 导入次数 / 备份数量；导出审计仅管理员——非"
                "管理员不再请求 /system/audit/exports，既不每轮刷新打 403，也不再用恒 0 的假数字误导）；· 最近流转记录直接渲染真实记录（导入历史 + 管理员可见的导出审计），"
                "不再用「前往…」空壳入口；"
            ),
            (
                "路由 meta.title 与菜单 label 对齐 23 处：data-overview 为例，侧栏叫「数据概览」而面包屑/document.title 写「数据管理」，同一页面两个称谓"
                "。menus.py 是全站唯一菜单源…"
            ),
            (
                "菜单对齐门禁新增规则 F（scripts/check_menu_alignment.py）：kind=page 且带 path 的条目，菜单 label 必须等于前端路由 meta.tit"
                "le。新增规则首次运行即抓出 23 处不一致，此后由 CI 自动拦截（此前面包屑/文档标题与侧栏文案可长期分叉而无人发现）。"
            ),
            (
                "policies/Edit.test.ts 跨用例污染：该视图 useFormDraft 有 600ms 防抖定时器，会在后续用例执行期间把上一个用例的表单写回共享 localStorag"
                "e，导致「草稿与离开拦截」用例单跑通过、整文件必红。改用 enableAutoUnmount(afterEach) 统一卸载（仓库 49 个视图测试同款约定）。"
            ),
            (
                "smoke.test.ts 移除 dataManagement/Index.vue 的 bare import：遵守 coverage-merge 不变量（同一被阈值锁定的 .vue 只允"
                "许一个测试文件执行，第二个文件即使只 bare import 也会在满量按 id 合并 fnMap 时损坏 functions）；可挂载性由 router-index.test.ts 的全"
                "量路由表保证。"
            ),
            "utils/index.test.ts 删除重复覆盖 dataManagement/Index.vue 的内容（已收敛到专属测试文件）。",
            (
                "lint：policies/Edit.test.ts 5 处未使用绑定（4 个 const wrapper = mountComp()、1 个 const vm）+ 29 处 pretti"
                "er 缩进 —— 原改动 eslint 未通过，本版修复后才入库。"
            ),
            (
                "接入 CodeGraph 预索引代码图谱（本机开发效率）：安装 @colbymchenry/codegraph 1.6.2 CLI +DSH 插件 @jiangzhenguo/dsh-co"
                "degraph 1.2.2（desktop profile，core 面 4 个工具codegraph_status/init/sync/explore，重启 DSH 后生效）…"
            ),
        ],
    },
    {
        "version": "1.18.14",
        "date": "2026-10-27",
        "description": "组织编码接入权威区划表：修掉 4 处真实缺陷（初始化编码被随机替换等）",
        "features": [
            (
                "P1 初始化建根组织时编码被随机替换（严重）：system/init.py 传入OrganizationCreate(code=522700)，但 OrganizationService."
                "create_organization() 内部走generate_code() 生成随机 ORG-XXXXXXXX，完全忽略传入编码（实测传 522700 →落库 ORG-848B7F7"
                "C、level=1）。跨机匹配与组织树全部失效。"
            ),
            (
                "P2 初始化强制省级编码（严重）：_resolve_root_org_code 要求末四位 0000，市州级单位（黔南州 522700）首启必然被拒，只能先造省本级根再手工建州。现省 / "
                "市州 / 县级均可作为首启单位。"
            ),
            "P3 不校验代码是否真实存在：只按末位规律判层级，522799、999999 都能入库并被判为县市级。现接入权威表，贵州省为全量校验（空号直接拒绝）。",
            (
                "P4 不校验父子是否同一行政区划：只校验「层级 = 父级+1」，522701（都匀市）可挂到520100（贵阳市）下 —— 组织树与按 path 前缀计算的数据权限会把黔南的县市算进贵阳子"
                "树。现要求父子同属一个区划（表内用表中 parent，表外用前缀）。"
            ),
            (
                "P5 越权探测（顺带修复）：POST /organizations 原先先查编码重复、后判越权，越权者可用 400 与其它响应的差异反推其它分支的组织编码（编��是跨机匹配标识）。现越权 "
                "403 先行返回。"
            ),
            (
                "权威行政区划表 backend/app/data/admin_divisions.json（11KB）：省级 34 全量；贵州 9 市州 + 88 县级全量（取自仓库内置 frontend"
                "/src/assets/geo/guizhou.json 的官方 adcode）；aliases 存区划调整换码（520222 盘县 → 520281 盘州市）。"
            ),
            (
                "app/services/admin_division_service.py：存在性 / 层级 / 父子一致 / 别名归一 的单一判定口径；OrganizationCodeService."
                "validate_admin_code(code, parent_code) 为落库路径统一入口。表文件缺失或损坏时自动降级为「仅末位规律」并告警（不得因缺文件把合法编码判非法）。"
            ),
            (
                "Windows 打包补数据文件：assistance-backend.spec 原先只收 alembic 等，漏了 app/data（两个 Linux spec 收的是整个 app），会让"
                "安装包内的组织编码校验找不到表 —— 已显式收集。"
            ),
            (
                "新增 backend/tests/unit/test_admin_divisions_r47.py（30 例）：表完整性（省级 34 / 贵州市州 9 /县级 88 / 父子闭合 / 层级"
                "与规律一致）、存在性（522799 等空号拒绝）、父子一致（522701 挂 520100 拒绝、12 县市挂 522700 通过）、表外省份规律兜底、缺表/坏表降级、Organizati"
                "onService 落真实编码、首启层级（省/市州/县级）。"
            ),
            (
                "同步更新 4 个旧用例（test_p3_init_org_code_branches / test_cov_b4a_organization_service /test_coverage_"
                "gap_batch3 / test_org_write_scope_r27）到新契约；R27 夹具改用真实代码（520000 / 520100 / 520103 / 520200 / 52"
                "0201）。"
            ),
        ],
    },
    {
        "version": "1.18.15",
        "date": "2026-10-27",
        "description": "分段导入补日志 + 文档/PPT 实测数字追平 + 仓库卫生",
        "features": [
            (
                "帮扶村「分段数据」导入的三个失败分支改为带行号记日志（_import_section_sheet）：此前「表头未识别（整表白导）」「行内有内容但全部列转换失败」「写库异常」三种情况都只做f"
                "ailed += 1，现场只看到 {\"imported\": 5, \"failed\": 3}，无从知道是第几行、什么原因，只能整份重来。"
            ),
            (
                "三份 PPT 的实测数字全部同步到本轮真值（15 处 run）：后端 14,722 → 14,870、前端 7,356 → 7,374、合计 22,078 → 22,244、前端测试文件 "
                "347 → 344（与 check_doc_numbers 的 *.test.ts(x) 口径一致）、封面/封底日期 2026-10-26 → 2026-10-27、版本标记 V1.18."
                "8 → V1.18.14。"
            ),
            (
                "文档入口页版本号从 v1.18.1 追平到 v1.18.14：docs/README.md、docs/INDEX.md、docs/04-部署文档/README.md、docs/01-快速开"
                "始/README.md 共 6 处 —— 此前入口页仍指向RELEASE_NOTES-v1.18.1，读者按图索骥会拿到 13 个版本前的发布说明。"
            ),
            (
                ".gitignore 补齐三类每次跑测试都会新生的目录：backend/verify_*/（280 个）、backend/wf_*/、backend/_scratch_lazy/。此前只忽"
                "略了 bumofu_pytest_appdata_*/，另外两类每次全量测试后都会让 git status 变脏，是 git add -A 误提交的隐患。"
            ),
            (
                "清理测试残留 1405 个目录 / 6.6 GB（backend/bumofu_pytest_appdata_* 等一次性隔离根）与顶层 28 个 pip 空临时目录、空 archives"
                "/、探测脚本 _probe_menus.py。均为未跟踪产物，仓库跟踪文件零改动。"
            ),
        ],
    },
    {
        "version": "1.18.16",
        "date": "2026-10-27",
        "description": "发布流水线竞态修复（latest.yml 丢失）+ 依赖版本 pin",
        "features": [
            (
                "发布资产缺失（latest.yml / .exe.blockmap）：Windows 作业的 electron-builder在有 GH_TOKEN 时默认按 onTagOrDraft 自"
                "行发布（建 draft Release）。"
            ),
            (
                "新增构建期守卫 Verify updater metadata produced：NSIS 构建必然同时产出latest.yml 与 MRRS-Setup-<版本>-x64.exe.blo"
                "ckmap，缺一即红并打印 dist 清单 ——不让「Release 少文件」留到发版后才发现。"
            ),
            (
                "依赖版本 pin（构建可复现）：backend/requirements.txt 里setuptools / wheel / bcrypt / cryptography 由 >= 改为精确"
                "版本（84.2.1 / 0.48.0 / 5.0.0 / 50.0.2，取自 CI 已全绿验证的实装记录）。"
            ),
            (
                "纠正「latest.yml 是 Windows 自动更新所需」的不准确表述：本系统没有electron-updater 依赖、也没有任何更新检查代码（离线单机部署，升级 = 覆盖安装）。改"
                "为说明它是 electron-builder 的 NSIS 产物、当前不被消费、保留上传只为发布物清单稳定（项目文件结构说明.md）。"
            ),
            (
                "docs/INDEX.md 补齐此前只有目录级链接的文档：7 篇 ADR（0003/0005/0006/0007/0008/0010/0012）、4 篇 Agent 约定、1 篇通知与提醒"
                " UI 规范 —— 18/18 篇 docs 现在都有显式入口。"
            ),
        ],
    },
    {
        "version": "1.18.17",
        "date": "2026-10-27",
        "description": "工程治理收口：技术债棘轮上线（并修掉它自身两个会失效的点）",
        "features": [
            (
                "技术债棘轮门禁 scripts/check_type_debt.py（CI static-analysis 阻断）：守住三个此前无人看管的指标 —— mypy 错误数、前端 as any "
                "处数、后端except Exception 处数。基线 .type-debt-baseline.json 记录数量 + 精确位置，任一指标超过即失败并列出新增位置（不是只报\"多了几条\""
                "）。--update 只应下调；上调需在 PR 说明理由。"
            ),
            (
                "Python 3.13 兼容：rapidocr-onnxruntime==1.4.4; python_version < \"3.13\"。该包元数据 requires_python<3."
                "13（PyPI 官方 JSON 核实、未 yanked），3.13 下原会让整个 pip install -r requirements.txt 报\"No matching distri"
                "bution found\" 而整体失败；"
            ),
            (
                "门禁隔离：三层对齐门禁的参照库改落到 .scratch/tmp/stack-align/（.gitignore 兜底），并让清理函数吞掉 BaseException —— 本机沙箱的 sa"
                "fe-delete shim 在单次删除量超阈值时会抛 SystemExit，那是 BaseException，shutil.rmtree(ignore_errors=True) 拦不住，"
                "会把门禁进程带崩、stdout 变空…"
            ),
            (
                "新门禁一提交就是红的：基线记为 mypy_errors=1393，实测稳定 1394（连跑三次 + --no-incremental 均 1394）。核对后确认 1394 条与最近 3 个"
                "提交改动的app/ 文件无交集 —— 属存量口径偏差而非新缺陷，故按实测重生成基线，并把该结论写进本段以免被后人误判为\"放宽标准\"。"
            ),
            (
                "门禁测不到时会静默放行：原实现在 mypy 无法解析汇总行时 return 0，等于 mypy 一旦改输出格式或没装，第一条指标就永久失效却仍显示绿色（正是|| true 的老毛病换个马甲"
                "）。现改为 fail-closed：抛 MypyUnavailable →exit 2（区别于\"恶化\"的 exit 1）并打印输出尾部与修复提示。"
            ),
            (
                "mypy 版本漂移：CI 由 pip install mypy 改为 mypy==1.19.1（与requirements-dev.txt 及基线测量口径一致）。棘轮把错误数当上限守着，不"
                " pin 则上游发版换个检查规则就能让全量计数整体漂移 —— 要么假红、要么假绿。"
            ),
        ],
    },
    {
        "version": "1.18.18",
        "date": "2026-10-28",
        "description": "两处路由注册缺陷修复（6 接口不可达 / 4 条重复路径）+ 乱码报错与无效注解",
        "features": [
            (
                "system.py 的 router 双重 prefix —— 6 个接口全部路径错误、完全不可达：聚合器 app/api/v1/system/init.py 已是 APIRouter(p"
                "refix=\"/system\")，而 system.py 自己又写了 prefix=\"/system\"…"
            ),
            (
                "config_package 被注册两次 —— 多出 4 条错误路径：该模块 router 自带prefix=\"/system/config-packages\"，是给 api/v1/i"
                "nit.py 的「子模块直挂」用的（注释写明\"历史表面，勿删\"），但聚合器又 include 了一次，于是多注册出/api/v1/system/system/config-packag"
                "es 等 4 条。修复：聚合器移除该 include，保留独立注册。"
            ),
            (
                "新增路由认证覆盖门禁 scripts/check_route_auth.py（挂 stack-alignment 作业）：api_v1_router 没有全局认证依赖，每个路由必须自己声明"
                "认证 —— 少写一行就是越权入口，code review 很难发现。门禁用 FastAPI 运行时依赖树递归判定（能识别经角色守卫间接要求认证的路由），白名单外的无认证路由即失败。"
            ),
            (
                "用户可见的乱码报错（services/encrypted_package.py）：加密包版本不匹配时消息直接把 bytes 拼进 f-string，用户看到的是 不支持的版本: b'9.9"
                "'；更糟的是非法版本字节（如 \\x02）经 decode(\"ascii\") 后是不可见控制符，消息看起来像\"不支持的版本: \"（冒号后空白）—— 比乱码更难排查。"
            ),
            (
                "把内建函数 any 当类型注解（services/business_metrics_service.py）：Optional[any] / value: any 里的 any 是内建函数，"
                "不是 typing.Any ——注解不产生任何约束（typing 容忍任意对象，故不报错，属\"静默失效\"），mypy 也会按 valid-type / 注解无效处理。现改为 Optio"
                "nal[Any] / Any 并补 import。"
            ),
            (
                "棘轮基线首次下调（.type-debt-baseline.json）：mypy 1394 → 1391（上述两处共 3 条：2 条无效注解 + 1 条 str-bytes-safe），as"
                " any 196 与 except Exception 802 持平。这是棘轮第一次真正起作用的方向——只降不升。"
            ),
        ],
    },
    {
        "version": "1.18.19",
        "date": "2026-10-28",
        "description": "修复大瓦片包导入“请求超时，请重试”（全局 30s → 导入专用 15 分钟）",
        "features": [
            (
                "frontend/src/api/offlineMap.ts：importTiles(file, options) 单独放宽超时到TILE_IMPORT_TIMEOUT_MS = 15 分"
                "钟（可 timeoutMs 覆盖），并透出 onProgress（0~100）。"
            ),
            (
                "MapTileManager.vue：导入期间显示 el-progress 与“上传完成后后端解压落盘约需 1 分钟、请勿关闭页面/刷新”的提示；超时错误单独提示“改用市州分包（≤64MB"
                "）重试，或稍后刷新状态”，不与普通失败混淆；导入结束（成功/失败/超时）复位进度与 loading。"
            ),
            "单测：api 层新增“15 分钟超时/自定义超时/进度回调截断”3 项；视图层新增“进度与勿关闭提示”“超时专用提示”2 项；相关 2 文件 37 项全部通过。",
            "283.7MB 全省包在机械硬盘/低速 U 盘上可能需要 2~5 分钟：保持页面打开，进度条到 100% 后仍在解压属正常；",
            "若网络/磁盘确实太慢，优先导入 9 个市州分包（21.5~63.8MB，单包约 10~25 秒）；",
            "导入中断不会破坏已有瓦片，重新导入会按同名覆盖补齐。",
        ],
    },
    {
        "version": "1.18.20",
        "date": "2026-10-28",
        "description": "构建链路兜底（Windows %TEMP% ACL）+ 门禁自身健壮性",
        "features": [
            (
                "前端构建在 Windows 上开箱即失败（打包流水线第一步）：新增frontend/scripts/build-with-workspace-temp.mjs，把 TEMP/TMP/TMP"
                "DIR 指到仓库内.scratch/tmp（目录创建失败时静默沿用系统值，不在只读介质上制造新故障），并用node 直接执行 vite 入口避免 .cmd 包装的引号/退出码差异；"
            ),
            (
                "check_type_debt.py 在 Windows GBK 控制台崩溃：输出含 ✓ 等非 ASCII 字符时抛 UnicodeEncodeError: 'gbk' codec can"
                "'t encode character '\\u2713'，本地门禁直接失败。与 check_doc_numbers / check_constants_sync 同口径强制 UTF-8（"
                "不支持 reconfigure的旧解释器静默跳过）。"
            ),
            (
                "门禁基线漂移清理：文档数字 14,874 → 14,873（实测）、技术债棘轮except Exception 802 → 801（只紧不松）、软删除基线 29 条重新收敛（STALE 豁"
                "免点清零）。check_soft_delete_usage、check_doc_numbers --full、check_type_debt 复跑全绿。"
            ),
            (
                "分段执行器单实例锁（scripts/run_backend_tests_segmented.py）：两个会话同时跑 12 段时，后启动的一方会在清理阶段重置 .coverage，先启动那次"
                "覆盖率从 100% 掉成 28%/53% ——现象是「12 段全 PASS 但覆盖率门禁红」，本轮实测两次。"
            ),
            (
                "新增元测试 electron/tests/build-temp-wiring.test.js（3 例）：锁住「三个构建脚本必须经包装脚本」「包装脚本必须改 TEMP/TMP/TMPDIR "
                "且有失败兜底」「.scratch/ 必须被忽略」，防止后人把它简化回裸 vite build 而无声复发。npm run test:electron 14 passed。"
            ),
            (
                "backend/version.json 的 description / release_date / build 改为自动派生：这三项与CHANGELOG 最新标题是同一事实，却一直靠手"
                "工抄 —— 每版忘改就被 check_update_log.py拦下（本轮又踩一次）。"
            ),
            "全量门禁复跑（30 道）仅剩 3 处调用方式问题（需 --json/--baseline 或 cwd=backend），修正调用后全绿；关键功能定向回归 182 passed。",
        ],
    },
    {
        "version": "1.18.21",
        "date": "2026-10-28",
        "description": "门禁统一入口 + no-print/dist 两道棘轮 + 端点口径写明",
        "features": [
            (
                "scripts/run_gates.py（门禁统一入口）：把「每个门禁在哪跑、带什么参数」固化成注册表（37 道，含 3 道需外部产物的慢门禁），本地一条命令与 CI 同款；支持 --li"
                "st / --only / --json /--slow / --stop-on-fail。需要 coverage-branch.json 或 gh 网络的慢门禁默认 SKIP（不伪装成绿"
                "），避免用陈旧覆盖率产物制造假红。"
            ),
            (
                "scripts/check_no_print.py（no-print 门禁）：生产代码禁止 print —— 桌面端无控制台窗口，print 输出用户与排障都看不到。允许项仅 2 处（ma"
                "in.py 启动横幅、logging_config handler关闭兜底），均属 logger 不可用的兜底路径。"
            ),
            (
                "scripts/check_dist_size.py（前端产物体积棘轮）：dist 总字节 / 文件数 / br 数三项对比基线，超基线 +5% 即失败；当前基线 9.2 MB / 674"
                " 文件 / 114 个 br。接进 Windows 与 ARM64 出包流水线（构建之后、上传产物之前）。"
            ),
            (
                "CI 接线：pr-checks.yml 的 static-analysis 加 check_no_print.py；build-windows.yml 与build-arm64.yml 在"
                " npm run build 之后加 check_dist_size.py。"
            ),
            (
                "端点计数口径写明（CLAUDE.md）：check_doc_numbers 统计 /api 前缀端点（845），另有 4 条非 /api 路由（/health、/favicon.ico、/"
                "version.json、SPA catch-all），全部路由合计 849（check_route_auth 口径）。两个数字不是矛盾，避免再次被误读成\"删了接口\"。"
            ),
            (
                "scripts/run_backend_tests_segmented.py 的一处裸 pragma（# pragma: no cover 无理由）→ 补理由，check_pragma_r"
                "easons --max-bare 0 恢复全绿（此前门禁在总 222 处 pragma 里恰好卡这 1 处）。"
            ),
            (
                "as any 基础设施层清零（196 → 188）：api/request.ts（CSRF 取 token、_retry/silent扩展标记）、api/milestones.ts（数组/"
                "信封双形态）、stores/organization.ts（列表载荷）、stores/user.ts（头像响应）、utils/desensitize.ts（索引写入）改为显式形状 + 类型"
                "守卫，不再用宽松断言吞掉契约变化；"
            ),
            (
                "as any 组件层清零（188 → 181）：components/map/OfflineMap.vue 引入本组件自用的GeoJson/GeoFeature 形状并把 register"
                "Map 载荷类型由 Parameters<typeofecharts.registerMap>[1] 反推（不深度依赖 echarts 内部路径）；borderType: 'dashed'"
                " as const。"
            ),
            (
                "as any 政策模块清零（181 → 172）并修掉一处假传参：新增 types/policy.ts（PolicyRecord 边界类型 + PolicyPayload），stores/"
                "policy.ts 的 policyList/current由 ref<any> 改为 ref<PolicyRecord[]>/ref<PolicyRecord | null>…"
            ),
            (
                "mypy 按模块收紧（1391 → 1385），先清 core.config 传递依赖链：core/logging_config.py 的 file_handler 先赋 SafeTime"
                "dRotatingFileHandler、else 分支赋 SafeRotatingFileHandler，mypy 按首赋值推断后判类型冲突 —— 显式标注公共基类BaseRotatin"
                "gHandler；"
            ),
            (
                "as any 帮扶村列表切片清零（172 → 162），并修出一处真实字段口径不一致：api/supportedVillage.ts 补 6 个响应类型（VillageListPayloa"
                "d / VillagePurgePreview /VillagePurgeResult / VillageBatchDeleteResult / VillageCreated / Vill"
                "ageImportResult）并给 6 个函数加泛型；"
            ),
            (
                "as any 审批待办切片清零（162 → 155）：api/approval.ts 补全两处类型没写全的历史契约 —— ApprovalTask 增加旧字段别名 applicant/su"
                "bmit_time，TaskDiff 增加旧键名original/changed 与事件源 history/status_logs（视图一直在容错读这些键，类型却没声明，只能靠断言）。"
            ),
        ],
    },
    {
        "version": "1.18.22",
        "date": "2026-10-28",
        "description": "发布收口：换 tag 重建 + 修复两处交付前回归",
        "features": [
            (
                "api/milestones.ts 的 milestoneProgress 在 items 为 null/undefined 时抛TypeError（tests/unit/api/mile"
                "stones.test.ts 2 例红）：信封守卫只容忍\"缺 items 键\"，不容忍响应体本身为 null/undefined（204 空体、接口降级返回）。"
            ),
            (
                "政策编辑页不再臆造 status 默认值：|| 'draft' 会让\"详情省略 status\"的已发布政策在用户保存时被静默降级为草稿（且与新增表单默认 active 矛盾）。改为只透"
                "传。"
            ),
            (
                "两处过时测试断言按真实契约更新：getLevelOptions 现按真实契约无参调用（后端不接收分类参数）；结对页帮扶村 mock 补齐 villageName（后端 to_dict 两种"
                "都返回）。"
            ),
            "types/policy.ts 缺文件尾换行导致 lint:check（--max-warnings=0）失败，会拦 CI lint 作业。",
            (
                "版本号单源同步到 1.18.22（node scripts/sync-version.js --write --version 1.18.22，14 个目标文件；--check 通过）。文"
                "档（README 本版亮点 / docs/INDEX 索引 /RELEASE_NOTES-v1.18.22）与三份 PPT（介绍 56 页 / 零基础 44 页 / 操作培训 60 页）同"
                "步到本版版本与实测数字（后端 14,896 用例 / 前端 7,…"
            ),
        ],
    },
    {
        "version": "1.18.23",
        "date": "2026-10-28",
        "description": "发布收口重建（补齐应用内更新日志同步）",
        "features": [
            (
                "应用内更新日志与 CHANGELOG 重新同步：scripts/sync_update_log.py 写入本版条目，backend/version.json 的 description 与"
                "本版 CHANGELOG 标题对齐。"
            ),
            (
                "版本单源同步到 1.18.23（node scripts/sync-version.js --write --version 1.18.23）；README 本版亮点 / docs/IND"
                "EX / RELEASE_NOTES-v1.18.23 与三份 PPT 同步到本版。"
            ),
        ],
    },
    {
        "version": "1.18.24",
        "date": "2026-10-28",
        "description": "出包链路收口：v1.18.21~23 三个 tag 构建失败的根因修复",
        "features": [
            (
                "Windows：npm ci 网络抖动直接堵死发布（build-windows.yml）smoke-test 作业的 npm ci 报 npm error code ECONNRESET "
                "→ exit 152；而它是build-windows 的 needs 前置，一抖整个 Windows 安装包根本没开始构建。原写法只有一次 || npm install 兜底，两次尝试落"
                "在同一段故障窗口里。"
            ),
            "ARM64：构建\"成功却无产物\"（build-arm64.yml + Dockerfile.kylin-standalone）两个缺陷叠加",
            (
                "docs/04-部署文档/RELEASE_NOTES-v1.18.21.md：v1.18.18→v1.18.21 的发布说明（6 个系统接口不可达、4 条重复路由、路由鉴权门禁、大瓦片包导"
                "入超时 30s→15 分钟、Windows %TEMP% ACL 构建兜底、门禁统一入口 + no-print/dist 棘轮、mypy 1394→1385、as any 196→172 "
                "等），避免 Release 正文落到兜底占位。"
            ),
            (
                "上一版把 fetch-timeout 降到 60s、外层轮数压到 7 次，仍没算到 npm 内部重试：fetch-retries 5 × fetch-timeout 60s 让单次外层尝试"
                "就吃掉约 5 分钟，7 次外层尝试≈35 分钟，实测 a7e5de9 的安装步骤跑了 30+ 分钟仍未结束。"
            ),
            (
                "frontend-check 的安装步骤跑了 45 分 09 秒，正好撞上该作业 timeout-minutes: 45，于是整条 job 结论成了 cancelled —— 日志看起来像"
                "\"被外部取消\"，实际是超时，既掩盖真因又空耗 45 分钟。算术很清楚：5 轮 × fetch-timeout 300s + 双镜像 × 3 轮= 最坏 11 次 × 5 分钟，本就超过"
                "任何合理的 job 预算。"
            ),
            (
                "npm ci 不认 --registry：它沿用 package-lock.json 里写死的 resolved URL（本仓 506 个包指向 registry.npmjs.org），所"
                "以\"默认源失败后切镜像\"那三次尝试仍然全部打到原源，与默认源一起红 —— 这是本轮最后一个隐性缺陷。"
            ),
            (
                "镜像按列表尝试，且首选境外友好源：GitHub runner 在境外，访问registry.npmmirror.com（中国节点）常被重置。现在先 https://registry.yar"
                "npkg.com（npm 同源 CDN、内容一致），再退回 npmmirror；每个镜像切换前 npm ping 探活。"
            ),
            (
                "always 模式会误伤特殊源：实测 --replace-registry-host=always 把cdn.sheetjs.com（xlsx@0.20.3，npm 系源没有）与腾讯镜像的"
                "包一并改写到 npmmirror，直接 E404。改用默认的 npm 模式 —— 只重写默认源 host，特殊源原样直连。"
            ),
            (
                "pr-checks.yml 的 frontend-check / e2e-test 加「离线缓存优先」：先给 ~/.npm 叠一层带 restore-keys 的 actions/cach"
                "e（setup-node 的缓存 key 绑死package-lock.json，lock 一变即 miss，这正是重试全落在同一故障窗口的原因），安装时首试 npm ci --offli"
                "ne（只吃本地缓存，零网络）…"
            ),
            "npm run test:electron 14 例全过（含 ci-wiring 守护：发布门禁等待预算 /main 不取消 / check_main_ci 接线）；",
            (
                "两个 build 工作流 YAML 可解析；全仓扫描\"退避失效/失败被吞\"同类模式，仅 pr-checks.yml 的 playwright 重试疑似——细查其循环后第 721 行已有"
                " exit 1，非隐患。"
            ),
            (
                "时间基准：self_check_service 的「账号锁定」「最近导入」两项用 datetime.now()（本地墙钟）与 UtcDateTime 列比较，UTC+8 下阈值整体后移 8"
                " 小时——锁定时长只有 15 分钟，于是明明有账号被锁，体检结论恒报「没有处于锁定状态的账号」；"
            ),
        ],
    },
    {
        "version": "1.18.25",
        "date": "2026-10-29",
        "description": "收口重建：合并双写者分支 + 修掉最后一处过时断言",
        "features": [
            (
                "前端 lint:check 门禁 29 处 prettier 警告清零：frontend-check 在npm run lint:check（--max-warnings=0）红，✖ 29"
                " problems (0 errors, 29 warnings)，全部是格式问题（模板换行、空行、文件尾缺换行）。npm run lint 自动修复后lint:check 与 type-"
                "check 均退出 0。"
            ),
            (
                "Critical｜refresh 完全绕过 token_version 吊销：validate_token 只验签名 / jti 黑名单 / type，不比对版本，而 access 链路有"
                "该校验。登出或强退后，未随登出提交的 refresh（其他设备 / 被窃）仍能换发带「新版本号」的合法 access。"
            ),
            (
                "Critical｜permission_package 的可选认证手写解码绕开全部校验：黑名单 / token_version /is_active / 首登改密四项全不查，却被「重写全库"
                " RBAC」的 /import、/confirm 使用，且 is_admin 时跳过本机来源限制 —— 已吊销令牌可远程改写整库权限。改为复用 get_current_user 完整链路（"
                "401/403 → None）。"
            ),
            (
                "Critical｜学校分析页图表恒空：请求 page_size=1000 而后端上限 200，每次进入都 422，被同一 try 吞掉只弹「加载学校分析数据失败」。改为按 200 分页拉全"
                "量 + 页数上限防御。"
            ),
            (
                "Critical｜权限 / 角色变更零审计：rbac.py 8 个写路由 AuditLogger 出现 0 次。新增 _audit_permission_change()，覆盖 assig"
                "n/revoke role 与 grant/revoke/save permissions。"
            ),
            (
                "禁用账号立即失效：is_active 原先只在 get_current_active_user 校验，而绝大多数端点依赖get_current_user —— 禁用后未过期 access "
                "仍全权限。新增 _reject_inactive_user()，一经禁用即 403。"
            ),
            (
                "审计 details 含 datetime 时整条记录静默丢失：new_value 直写 Column(JSON)、引擎无json_serializer，驱动写出抛 TypeError 被"
                "吞 —— 带日期的操作恰好最需审计。新增 _json_safe_value() 入库前 round-trip（default=str）。"
            ),
            (
                "批量更新 / 删除的组织过滤 fail-open：操作者未绑定组织时原条件整体短路 → 可按裸 id跨组织改删（违反 ADR-0002）。改为三分支，无组织账号直接拒绝；新增 2 条负向用"
                "例。"
            ),
            "软删除记录永久占用唯一编码：重建同编码报「已存在」却在列表看不到。查重区分活跃 / 已软删���，后者给出可行动指引（彻底修复需 partial unique index，留待迁移批次）。",
            (
                "前端三处：dashboard 的 saveLayout 缺 try（deep watcher 抛异常却仍提示已保存）、SystemConsole / dataVerify 的 router"
                ".replace 未 catch、Role.vue 删除失败吞掉后端原因。"
            ),
            (
                "审计写入回滚调用方业务事务（会丢业务数据却返回 200）：AuditLogService.log 原先在调用方 Session 上 add + safe_commit，失败时 db.rol"
                "lback() 会把尚未提交的业务写入一并回滚，而异常被吞掉、端点照样返回 200 —— 调用方完全不知道数据没落库。"
            ),
            (
                "/system/env 任意登录用户可读依赖与运行环境 → 收紧为 require_admin()（与 system/diagnostics 一致）。让测试静默失效（已修 3 处：r16 "
                "双重失效、report_templates 覆盖版本缺 finally、recommendation 整类复制两遍）。"
            ),
        ],
    },
    {
        "version": "1.18.26",
        "date": "2026-10-29",
        "description": "全库审计收口：认证/权限 Critical + 维护窗口 fail-open + 类型债下降",
        "features": [
            "PII 8 列全部 VARCHAR(256)（原 5 列 VARCHAR(20)）；",
            "冗余索引 8 个已删除，重复组归零；",
            "created_by 外键 SET NULL 已补；",
            (
                "数据零丢失（users 2 / projects 6 / supported_villages 6 / audit_logs 216 / machine_codes 1）。不再抛异常 → "
                "写入失败被谎报为成功。改为用返回值判断。safeRemoveItem 吞异常后语义反转。给 safeRemoveItem 加 boolean 返回值并让调用点据此提前返回。"
            ),
            (
                "mypy 869 → 851：13 个文件 18 处空容器补显式注解（var-annotated 清零一半）：by_type/action_counts/by_severity/count"
                "s/warnings/errors/name_map/row_map/ancestors …这些是 x = {} / x = [] 的空字面量，mypy 无法推断元素类型。"
            ),
            "setItem × 10 → safeSetItem(key, value, kind)（失败返回 false，不阻断）",
            "removeItem × 12 → safeRemoveItem(key, kind)",
            "getItem × 6（含 safeGet(() => sessionStorage, ...) 形式）→ safeGetItem(key, kind)",
            "删除模块内本地 safeGet 定义，统一用共享实现（避免两套语义）",
            (
                "新增 utils/safeStorage.ts（共享安全存储）：safeGetItem / safeSetItem / safeRemoveItem /isStorageAvailable"
                "，读取异常返回 null（fail-closed）、写入异常静默丢弃。接上三处在关键路径上的裸读取"
            ),
            (
                "main.py::_init_database_tables 补审计结论注释：该函数顺序是 create_all →alembic upgrade → _migrate_missing_c"
                "olumns（受 ENABLE_AUTO_MIGRATION 控制），补列不会“先跑并让 upgrade 整段跳过”（原审计建议成立的前提不准确）；"
            ),
            (
                "把 migration_evidence 门禁接进统一入口（修 test_gate_entrypoints 唯一红点）：scripts/check_migration_self_evide"
                "nce.py 已存在且自跑为绿（47 个改 schema 的迁移全部有自证测试、未登记 0 个），pr-checks.yml 也在跑它…"
            ),
        ],
    },
    {
        "version": "1.18.27",
        "date": "2026-10-30",
        "description": "迁移落地修复（老库未升级 + 外键迁移误判 + 覆盖率缺口）",
        "features": [
            "_resolve_create_code：仅当 parent is not None 时做相邻校验；",
            "_check_org_hierarchy：根组织不再校验层级（县级根不得再建下级 由相邻校验自然覆盖）；",
            (
                "同步修正两处过时断言（test_root_must_be_province_code → test_root_may_be_any_level、test_root_not_province"
                "_warns → test_root_not_province_is_ok）；"
            ),
            "清理 init.py 里「根组织必须是省级编码」的过时 docstring。",
            (
                "test_org_root_level_r54.py（5 例）：市州级/县市级/省级根都必须能建；有父级时跨级仍拒、相邻仍过。RED 时 2 failed（正是用户症状），修复后 5 pa"
                "ssed。"
            ),
            (
                "test_org_root_level_selfcheck_r55.py（5 例）：根为市州/县级时自检 ok；省级根不回归；真正跨级仍 warn；正常链 ok。RED 时 2 faile"
                "d，修复后 5 passed。"
            ),
            "版本号 1.18.26 → 1.18.27（node scripts/sync-version.js --write 同步 22 处目标）。",
        ],
    },
    {
        "version": "1.18.28",
        "date": "2026-10-30",
        "description": "重新打包发布（补上根组织层级修复的安装包）",
        "features": [
            (
                "本版相对 v1.18.27 只包含两处提交：443fa087（补 RELEASE_NOTES-v1.18.27.md）与6d162cc4（根组织层级误判修复）。修复细节见下方 [1.18."
                "27] 段的「Fixed（根组织层级误判 —— 市州级单位无法建根/被自检误报）」小节。"
            ),
            (
                "为什么要重打：v1.18.27 的安装包是在 7c0a9639 打出来的，当时上述修复还没进仓库；也就是说 MRRS-Setup-1.18.27-x64.exe 里仍是「市州级单位无法建根"
                "」的旧行为。本版把修复真正带进产物，不改任何业务逻辑。"
            ),
            "版本号 1.18.27 → 1.18.28（node scripts/sync-version.js --write 同步 22 处目标）。",
        ],
    },
    {
        "version": "1.18.29",
        "date": "2026-10-30",
        "description": "全库并发收口：导出线程化/权限边界/初始化门禁/调度器与桌面退出",
        "features": [
            "check_doc_numbers --update：前端测试文件 348→349、后端用例 15060→15103。",
            "check_type_debt：mypy 错误 847（基线 851，改善 4），as any / except Exception 持平。",
            (
                "数据同步/Excel 导入：普通与加密导出整体移入线程池，ZIP 内 data.json 分块流式写入，不再在事件循环上做同步 SQL、序列化、压缩与 PBKDF2；SQLAlchemy "
                "Session 不再跨线程复用。Excel 导入恢复 import_data_async 语义后在后台线程执行，避免把异步包装参数误传同步实现。"
            ),
            "数据包导出：改为逐表逐行流式创建 ZIP，manifest 记录实际条数；恢复包解压增加总量/单成员上限，防解压炸弹。",
            "审批权限边界：自动审批、批量审批、任务历史/变更对比等“跳过审批人”能力统一收敛到超级管理员；部门级 admin 不再享有全局审批能力。",
            "项目权限：可见但非创建人/非管理员的更新与删除明确返回 403，不再被 DB 错误处理器降级成 500。",
            "系统初始化：匿名首次初始化收紧为“本机 + 空库 + 可选引导令牌”；重置接口密码改走请求体；补齐门禁回归。",
            "备份安全：创建备份统一管理员门槛；target_dir 只允许默认目录或服务端配置目录，且不得落入静态下载目录；备份计划 cron 非法时返回固定提示，异常原文不出站。",
            "调度器：自动备份改由后端 cron 唯一驱动并支持热重排；修复测试假时钟缺少 datetime.combine 的契约，所有定时任务登记数量随新增任务自动推导。",
            "错误语义：提醒扫描失败上抛为 500，统计看板审计查询失败上抛为 500，不再伪装成“新增 0 条 / 0 条操作”。",
            "请求体上限：非 multipart JSON 不再继承上传路径的“不限量”策略，防止普通写端点灌大 JSON 打爆内存。",
            (
                "前端：网络重试只保留幂等 GET/HEAD，避免 POST 中断重发造成重复业务记录；同一统计端点可跳过去重取消；Electron 退出等待后端优雅停止，减少孤儿进程；Excel/PDF "
                "导出在桌面端退化为同源 iframe 打印。"
            ),
        ],
    },
    {
        "version": "1.18.30",
        "date": "2026-10-31",
        "description": "修复 ARM64 安装后后端启动即崩（difflib 打包漏收）",
        "features": [
            (
                "P1-U3：系统自检「去处理」直达落点：SelfCheckCard.vue 给每个自检项锚到它该被修的页面（组织单位码/组织层级 → org?tab=organizations；待审核账号"
                "/账号锁定 → org?tab=users-orgs；PII 密钥 → security?tab=secrets；介质导入近况 → /data-package）。仅非正常项显示入口，ok "
                "项不给（避免噪音）。"
            ),
            (
                "P1-U4：顶栏「待导入更新包」角标：离线场景上级送来的介质里可能有增量包，「到了没导出」过去只能靠人记得去看。现进入应用时只读 GET /data-packages 数 type=upd"
                "ate 的包，>0 才出现角标，点击跳 /data-package/update；无权限/404 一律归 0，不影响布局（不轮询）。"
            ),
            (
                "P1/P3 已核实无需新做（记录以免重复投入）：① 恢复演练早就在跑：backup_scheduler.py 每日拉起 restore_drill_job（is_drill_due 默认 "
                "30 天）；② time.sleep 没有阻塞事件循环的实例：全部位于同步上下文（logging 轮转重试、端口探测的启动前循环、Starlette BackgroundTasks 线程池"
                "、模拟任务后台线程）…"
            ),
            (
                "P0 三道棘轮（发版前必跑）：① frozen_smoke（check_frozen_smoke.py）—— 冻结产物必须通过 BACKEND_IMPORT_CHECK=1导入自检，并用随"
                "机端口真实起服务（/health 200 + 受保护端点 401）；产物不存在自动 SKIP。这正是 v1.18.23~26 连红 3 次 tag 的根因门禁。"
            ),
            (
                "P3：性能基线加 20000 行档 + 噪声地板：bench.py 支持 --rows 5000,20000 多档，基线写入 tiers（同时保留顶层首档，向后兼容旧读者）；新增 MIN_"
                "ABS_SECONDS=0.05噪声地板：毫秒级路径（5,000 行 CSV 导出 ~5ms）两侧都低于地板就跳过比较，避免「机器抖动 50%」被当成性能回归（实测消除了一次假 WARN）"
                "。"
            ),
            (
                "P1：密钥轮换后 PII 加解密自检：新增 pii_crypto.self_check()（加密→解密往返，失败即抛），并接到 POST /api/v1/secrets/rotate ——"
                " 自检失败返回 500「密钥轮换后 PII 加解密自检失败，请勿继续写入」，而不是像以前那样回「轮换成功」。成因：PII 解密失败是逐字段静默降级（原样回密文），现场看到的是「数据变乱码」"
                "。5 例回归。"
            ),
            "预查一次 (student_name, grade) 对，按 school_id 过滤；",
            "循环内改查内存集合（O(1)），插入后把新行加入集合。",
            "12 处把异常降级为 error_type 返回给调用方（体检/预检单项失败不中断整轮），是可观测的降级而非吞掉；",
            (
                "3 处（diagnostics.py:366 / backup_service.py / village_cascade_delete_service.py）本身就有 logger.err"
                "or/warning，只是注释没写理由。"
            ),
            "后端全量 GET 巡检：432 个路由 → 发现并修复 1 个真缺陷（/menus/accessible 的 user 形态健壮性，见上一条）；修复后 0 个 5xx。",
            (
                "后端写端点巡检：255 个 POST/PUT/PATCH（排除危险操作）→ 0 个 5xx。test_cov_final_organization.py::test_is_active_d"
                "efaulted_when_absent 仍用is_superuser=False 的用户建根（520000），被 403 拦截。该用例意图是验证 is_active 默认值而非建根权限 "
                "→ 用户改为超管，守卫另测。"
            ),
        ],
    },
]
