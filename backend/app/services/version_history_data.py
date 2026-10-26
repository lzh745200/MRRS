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
            "o attribute 'create_rural_work'，补全 create_rural_work + update_rural_work 签名修正 + 5 个缺失方法（get_st"
            "atistics/get_villages_for_selec…"
        ),
        "features": [
            (
                "🐛 RuralWorkService.create_rural_work 缺失 — 生产环境 AttributeError: 'RuralWorkService' object has n"
                "o attribute 'create_rural_work'，补全 create_rural_work + update_rural_work 签名修正 + 5 个缺失方法（get_st"
                "atistics/get_villages_for_selec…"
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
            "D 字体、无需字体文件），无数据时输出带\"暂无数据\"说明的有效…"
        ),
        "features": [
            (
                "🐛 报表 Word/PDF 导出为空文件：report_export_service 的 export_word/export_pdf 此前直接返回空 bytes，管理员在「数据导出 → "
                "报告导出」下载到 0 字节文件；现已用 python-docx / reportlab 实现真实公文渲染（标题/年度/生成时间/章节表格，PDF 内置 STSong-Light 中文 CI"
                "D 字体、无需字体文件），无数据时输出带\"暂无数据\"说明的有效…"
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
                "1_data/delta）直接 String() 透传给 el-descriptions。现按后端 _eval_to_dict/compare_evaluations 真实契约渲染：报告展"
                "示总分/等级/排名/三唯得分/评估时间，指标明细单独成组；年度对比只渲…"
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
            (
                "🐛 版本号不一致：运行时版本接口受根目录 .env 中 PROJECT_VERSION=1.8.0 覆盖，与 version.txt/config.py/package.json（1.8."
                "1）不一致。现已统一升至 1.8.2（四处对齐），版本接口补 code/message 信封字段"
            ),
            (
                "🐛 backend/.env 混合编码损坏：GBK 编辑器写入断字节（7 处中文词尾 '?'+非法 UTF-8），导致 alembic CLI 启动即崩（UnicodeDecodeErro"
                "r），且运行服务静默忽略该文件回退默认连接池（20+10，实测连接池耗尽、单请求 151 秒）。已重写为纯 UTF-8/LF，迁移与配置加载恢复正常"
            ),
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
                "ed 不入库并注明原因）；数据包导入与确认入库限 admin/…"
            ),
            (
                "🐛 User 模型缺少 org_id 别名：数据上报（/data-reports）与数据包接收（/data-packages/import）大量使用 current_user.org_id"
                "，但模型仅有 organization_id，导致上报创建报\"用户未关联组织\"、接收报\"未指定目标组织ID\"、一键上报组织归属回退错误。现新增 org_id property 兼容"
                "别名，上报/接收全链路组织归属正确"
            ),
            (
                "🐛 数据包导入 AttributeError: validated：import_package 结果构造误用 PackageStatusEnum.validated（枚举成员实为大写 V"
                "ALIDATED），管理员上传接收数据包必现 500。已修正为大写成员"
            ),
            (
                "🐛 数据包编码同秒冲突：_generate_package_code 使用秒级时间戳，同一组织同一秒内两次导出/接收撞 data_packages.package_code 唯一约束 → "
                "500。现改为毫秒级时间戳 + 4 位随机后缀"
            ),
            (
                "🐛 上报编码同秒冲突：_generate_report_code 同为秒级时间戳，同一秒内创建两条上报撞 data_reports.report_code 唯一约束 → 500。同样改为毫"
                "秒 + 随机后缀"
            ),
            (
                "✅ 链路验证 25/25 通过（隔离库双账号实测）：权限包 CRUD/绑定/解绑/非法key拦截/菜单收敛（7项）；下级录入→一键上报→列表可见→管理员上传接收→自动校验→预览→确认导入（"
                "导出=导入记录数）→数据保存可查→字段级自动纠正（trim修复入库/缺必填拒绝跳过）→第二包逐一接收（11项）；上报创建/提交/上级收到/待处理/审批通过/驳回流/下级状态查询（7项）"
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
                "。el-input-number（2000~2099）与 el…"
            ),
            (
                "🐛 版本号统一至 1.9.0：version.txt（唯一数据源）经 scripts/sync_version.py 同步到 config.py / 根 package.json / fr"
                "ontend/package.json / .env.example / frontend/.env.example，并手动补齐脚本未覆盖处：根目录 .env（运行时版本接口覆盖源）、el"
                "ectron/main.js 兜底、build.ps1、doc…"
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
        "description": "🐛 Windows 安装后启动报 SyntaxError: Unexpected token '}'（main process 弹窗）：",
        "features": [
            "🐛 Windows 安装后启动报 SyntaxError: Unexpected token '}'（main process 弹窗）：",
            "🐛 麒麟 Electron DEB 打不开：同一损坏的 main.js 打进 DEB → 主进程启动即崩，随恢复治愈。",
            "🐛 麒麟 standalone DEB 装完打不开 / 无菜单图标 / 无桌面快捷方式：",
            "🐛 麒麟启动脚本硬依赖未打包的 curl：start-kylin.sh 健康检查增加",
            "🐛 麒麟直接启动回退路径权限：/var/lib 对桌面用户组不可写时降级 $HOME/.assistance-management-system/；",
            "🐛 CI 内嵌 postinst 乱码路径：build-arm64.yml /opt/甯壎绠＄悊绯荤粺 → /opt/帮扶管理系统。",
            "🔒 CI 语法门禁：build-windows.yml / build-arm64.yml 在 electron-builder 打包前",
            "🔒 pre-commit 阶段新增 electron-syntax-check hook（改动 electron/*.js 时本地即时拦截）。",
            "🔒 package.json 新增 npm run check:electron；build/build:win 前置语法校验。",
            "清理死脚本 scripts/linux-postinst.sh（路径错误零引用）；",
        ],
    },
    {
        "version": "1.10.3",
        "date": "2026-08-29",
        "description": "✨ CI 补建 standalone 麒麟 DEB 流水线：此前 CI 只构建 Electron DEB，而安装指南",
        "features": [
            "✨ CI 补建 standalone 麒麟 DEB 流水线：此前 CI 只构建 Electron DEB，而安装指南",
            "🐛 环境变量三层错序开浏览器：kylin.env 声明的 AUTO_OPEN_BROWSER 是死键",
            "🧹 坏文件：全仓 2786 个文本文件 mojibake 字节级扫描（scripts/scan_mojibake.py",
            "🧹 死代码：error_handler 四个零引用 backward-compat 别名",
        ],
    },
    {
        "version": "1.10.4",
        "date": "2026-08-29",
        "description": "CI 修正",
        "features": [
            "🐛 fix(ci): standalone-deb 产物路径修正（buildx output 导出树保留 /output/ 前缀），",
        ],
    },
    {
        "version": "1.10.5",
        "date": "2026-08-29",
        "description": "UI 可读性根治 + 全站精美化",
        "features": [
            "🎨 根治\"UI 看不清\"：提示可读性修复、全站视觉统一美化、输入框规范化",
            "🧹 NUL 坏文件全清（CodeCheck 失败文件归零）",
            "🔖 版本号随 tag 联动：CI 打包前 sync 脚本把 tag 版本写入 frontend/.env.production",
        ],
    },
    {
        "version": "1.10.6",
        "date": "2026-08-29",
        "description": "全仓库死代码彻底清理(v1.10.5 为清理前基线)",
        "features": [
            "删除 87 个零引用模块文件 + data/ + interfaces/api/(~12,300 行):core 21、",
            "删除 6 个零引用模型文件 + EffectivenessIndicator/VersionHistory 两类,",
            "摘除活模块内孤儿符号 ~60 个(exceptions 11 异常类、response/security/",
            "PyInstaller spec 移除不存在的 messages_extended;删除陈旧 requirements-lock.txt",
            "依赖精简 31 项(redis/jieba/matplotlib 全家桶/scipy/python-pptx 等,全部验证",
            "测试同步:删除死模块专测 ~70 文件,混合 harness 摘除死段保留活用例",
            "删除 test-only 存活文件 73 个(44 组件、16+4 composables、7 utils、3 stores、",
            "重复实现归并:PageHeader/GlobalSearch 死副本、Skeleton/LazyImage/DataTable 两套",
            "17 个覆盖率 harness 摘除死条目,保留活代码覆盖",
            "package.json 移除 fast-check/@types/dompurify/rollup/@commitlint/*/driver.js;",
            "git rm:test_scripts/、installers/、k8s/、Dockerfile.arm64/.fpm、.qwen/.reasonix、",
            "docker/Dockerfile 删除从未可构建的 electron-builder 阶段(electron/ 无 package.json)",
        ],
    },
    {
        "version": "1.11.0",
        "date": "2026-08-30",
        "description": "全面体检修复版（安全红线 + 功能补全）",
        "features": [
            "🐛 帮助文档出厂密码文案：admin/admin123 修正为 admin/Admin@2026，",
            "🐛 Electron 导航白名单前缀绕过（W6-T3）：will-navigate /",
            "🐛 stopBackend 误杀风险（W6-T3）：优雅退出后取消强杀定时器，",
            "🐛 SHA256SUMS 行尾：CI 生成改 WriteAllText 显式 LF——WriteAllLines",
            "🔒 vcredist 移出 git + SHA256 钉扎（W6-T2，critical）：37.7MB 官方",
            "✨ Release SHA256SUMS 完整性链（W6-T5）：三个发布产物族独立命名",
            "✨ 前端产物同步逐文件哈希校验：sync-frontend-dist.{sh,bat} 由",
            "✨ PyInstaller onefile → onedir（W6-T6/ADR-0006）：冷启动实测 32.3s →",
            "🔒 Actions 全量 pin 到 commit SHA（W6-T7）：4 个 workflow 57 处 uses",
            "✨ 代码签名管线就绪（W6-T1 管线侧）：CSC secrets 配置即自动签名",
            "📝 离线升级与回滚指南（W6-T10）：备份→SHA256/签名校验→覆盖安装→",
            "🔐 secrets.json 明文回落收紧（W6-T11）：safeStorage 不可用时 0600",
        ],
    },
    {
        "version": "1.11.1",
        "date": "2026-08-30",
        "description": "Windows 安装器真机修复版",
        "features": [
            "🐛 安装器真机全部中止（截图故障）：NSIS 对双引号字符串做 C 风格转义，",
            "🐛 校验三态语义：0=匹配静默安装；1=确证不匹配弹窗中止（真实篡改信号）；",
            "📝 文档同步：AGENTS.md 新增 NSIS 转义铁律 Known Issue；工单 002 追记复盘；",
            "本机全链路实测：静默安装 exit 0 → 哈希校验通过 → redist 静默执行 →",
        ],
    },
    {
        "version": "1.11.2",
        "date": "2026-08-30",
        "description": "403 权限页根因修复 + 全站弹窗显示修复",
        "features": [
            "🐛 无组织管理员被判\"无任何组织权限\"（核心根因）：单机/未绑定组织的管理员",
            "🐛 菜单加载失败窗口期全站 403：打包版后端冷启动（onedir 8.6s）期间",
            "🐛 经费申请页 admin 403：funds-user 菜单键 roles 缺 admin/super_admin。",
            "🐛 存量旧角色名被 meta.roles 误拒：守卫校验前先 normalizeRole 归一化",
            "🐛 legacy 模型数据范围 500：villages 等无 created_by/organization_id 列的",
            "🧪 真实库双角色全量 GET 端点巡检：admin 0×403/0×500；新增回归",
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
            "🐛 冻结包内 47 个业务路由模块全部缺失：app/api/v1/init.py 此前用",
            "🐛 两个 spec 同源修复：统一 spec 补 sys.path 插入使 collect 与 CWD 无关、",
            "🐛 ARM64 postinst：补 onedir 后端主程序 chmod（旧脚本只找 onefile .exe 路径）；",
            "🐛 deb Depends 声明：补 Electron 运行库依赖（libnss3/libgbm1/libasound2 等",
            "✨ Linux 平台禁用硬件加速 + disable-dev-shm-usage：规避麒麟/飞腾 GPU 驱动",
            "✅ 本机 PyInstaller 实包验证：启动冻结 exe，此前缺失的 organizations/policies/",
            "✅ 后端全量回归全绿；YAML/JSON 门禁通过",
        ],
    },
    {
        "version": "1.11.4",
        "date": "2026-09-04",
        "description": "异常细节出站收口 + 板块导入 400 根治 + 帮扶村经费持久化修复 + 测试数据目录隔离",
        "features": [
            "🔒 异常细节出站收口（W1 不变量 #6 / W1-T8），共 4 处：",
            "🔒 泄露扫描器扩面到 services/、utils/、core/：上述第一处之所以能长期",
            "🔒 /health 不再回传迁移异常原文：该端点无需认证，原 migration.error",
            "🔒 分析统计接口数据隔离改 fail-closed：_get_analysis_data_impl 的",
            "🐛 帮扶村年度板块导入恒 400：force_investment / party_building 两个板块",
            "🐛 学校回收站恢复/彻底删除后停在空页（AGENTS.md 前端 BUG 模式 #3）：",
            "🐛 截断/损坏权限包导致未分类 500：package_crypto._parse_header 无长度校验，",
            "🐛 saveSectionData 与 saveYearlySectionData 是完全重复的实现（同一 URL），",
            "🐛 监控快照在麒麟/Linux 上整份崩溃并刷 ERROR 日志：system/monitor.py 的",
            "🐛 注册页把后端 400 报文吞成 \"Request failed with status code 400\"：",
            "⚡ 异步端点阻塞事件循环收口（性能），共 5 处：psutil.cpu_percent(interval>0) 是",
            "🐛 跨平台磁盘路径同源缺陷一并扫清：监控快照工单里的 os.environ.get(\"SystemDrive\", \"C:\\\\\")",
        ],
    },
    {
        "version": "1.11.5",
        "date": "2026-09-05",
        "description": "通行码注册大小写归一化 + 功能全链路探针验证 + 覆盖率根因修正收尾",
        "features": [
            "🐛 帮扶村年度数据「校验」端点被动态段吞掉（恒 400 未知数据分类）：路由注册顺序",
            "🐛 经费拨付被文档要求锁死（前端上传缺陷）：经费「拨付」前置要求附件类别",
            "🐛 回收站恢复项目后仍不可见（真实缺陷）：项目软删时 status 被置为",
            "🐛 注册响应缺失 refresh_token（与 LoginResponse「注册即登录」契约不一致）：",
            "🐛 大写输入的通行码被误拒（注册提示「通行码无效或已被使用」）：通行码为",
            "🔧 前端覆盖率 88.23% 门禁红因的最终定论与根治（含 CI 红→绿的完整实测链条）：",
        ],
    },
    {
        "version": "1.11.6",
        "date": "2026-09-06",
        "description": "深度探测循环（9 轮）+ 并发竞态修复 + E2E 套件入 CI 门禁",
        "features": [
            "🐛 组织通行码注册后新用户无法登录（阻断级）：组织通行码记录的",
            "🐛 data-sync 数据包下载恒 400/404（路径双源）：下载端点用相对",
            "🐛 报表模板下载/上传确认 500 + 静默零写入：fields 允许任意字符串",
            "🐛 奖学金导入全链坏死（阻断级，无测试覆盖致长期存活）：按",
            "🐛 乡村工作悬挂 village_id → 裸 500：外键目标是遗留 villages 表（前端",
            "🐛 并发备份同毫秒唯一键冲突 → 500：文件名/config_key 毫秒后缀在并发",
            "🐛 通行码注册并发竞态 → 创建 2 个用户：verify（读 pending）→建用户→",
            "🐛 覆盖率墙钟黑洞（CI #84）：/backup/schedule 的\"已过 02:00 则 +1 天\"",
            "🧪 Playwright E2E 套件复活并纳入 CI 门禁：死代码清理曾误删 helpers.ts",
            "🧪 并发探针（多线程真实 HTTP，12/12）：同记录 10 并发写、审批竞态、",
            "🧪 前后端契约交叉核对：导出后端 797 条路由，正则通配匹配前端 334 个",
            "📚 帮助文档修正出厂密码描述（Admin@2026）+ 新增管理员出厂恢复通道说明；",
        ],
    },
    {
        "version": "1.11.7",
        "date": "2026-09-06",
        "description": "探测循环收官：探针资产固化 + 发布物供应链核验",
        "features": [
            "🧪 全链路探针固化：9 轮深度探测的真实 HTTP 探针（200+ 断言，30+ 模块）",
            "📋 工单 003：报表订阅为半成品（可创建、无生成/送达消费方）——三方案",
            "🔐 v1.11.6 发布物供应链核验：三件套（exe/electron deb/standalone deb）",
            "本版安装包内容与 v1.11.6 构建一致（两次 tag 之间仅测试/文档变更），",
            "真机 UI 安装抽验仍建议人工执行一次。",
        ],
    },
    {
        "version": "1.11.8",
        "date": "2026-09-06",
        "description": "🐛 跨机器注册阻断级修复（生产双机实测反馈）：通行码自验证启用 + 组织通行码确定性化",
        "features": [
            "🐛 机器特定通行码跨机器注册 100% 失败（阻断级，生产双机实测）：管理员在",
            "🐛 组织通行码跨机器注册 100% 失败（同根因）：组织通行码为随机数且仅存",
            "注册页新增\"单位名称\"选填框（组织通行码跨机器注册时填写）。",
            "注册失败提示更新：明确组织通行码需填单位名称、机器通行码需提供本机机器码。",
            "已有部署升级本版后，此前生成的机器特定通行码立即恢复可用（HMAC 自验证",
        ],
    },
    {
        "version": "1.12.0",
        "date": "2026-09-06",
        "description": "🎨 UI 全面优化：字体统一 + 40px 舒适密度 + 布局标准化 + 认证页统一",
        "features": [
            "🔒 事务层把 SQLAlchemy 异常原文内插进响应（W1 不变量 #6 违规）：",
            "🔒 8 个端点把「关联 ID 不存在」报成 500/503：R22 对全部 33 个带 *_id",
            "🔒 2FA 中间态令牌可当正式令牌用（认证绕过，高危）：/auth/login 在双因素",
            "🔒 备用恢复码可无限复用（backup_codes 消费从不落库）：two_factor_auth.",
            "🔒 前端依赖审计阻断修复（CI security job 变红）：新增公告",
            "🐛 合同附件覆盖用户备注 / 改备注清空附件（合同管理）：合同附件此前被",
            "🐛 合同/划转凭证关联不存在的项目或经费时报 500：POST /fund-lifecycle/contracts",
            "🐛 无项目合同的详情恒 400（同资源两种口径）：ContractCreate.project_id",
            "🐛 同机第二个用户注册必挂（组织/自验证通行码跨机器注册 100% 失败）：",
            "✨ 报表订阅闭环（工单 003 方案 A+B 落地）：此前订阅可创建但无任何消费方",
            "中文字体栈统一至 tokens 单一来源（PingFang SC + Microsoft YaHei 入栈），",
            "EP 排版变量显式化：--el-font-family/--el-font-size-base: 14px 走令牌，",
        ],
    },
    {
        "version": "1.12.2",
        "date": "2026-09-11",
        "description": "🐛 R19–R31 深度探针修复 + 架构评估 P0 加固（导出/备份/迁移门禁）+ CI 前端门禁回归修复",
        "features": [
            "A1 导出任务重启自愈：recover_stale_export_tasks 在 lifespan 启动时把",
            "A2 导出/备份原子落盘：产物先写 .part 临时文件、成功后",
            "C1 备份可恢复性校验：备份落盘后校验 zip CRC（testzip）+",
            "F1 迁移单 head 门禁入 CI：scripts/check_migrations.py 校验 alembic 单 head 并接入",
            "🐛 数据上报的 report_type 必填却从不落库（静默丢弃）：R29 探针实测 ——",
            "🐛 数据包 data_types 双重编码（版本变更摘要键变成单字符）：R28 探针实测 ——",
            "🐛 通用文件上传：category 只认查询参数（表单字段静默失效）+ 全量读入内存：",
            "🐛 组织创建/更新的非法枚举值报 500（安装包验收发现）：对刚构建并安装的",
            "🐛 「驳回 → 重新提交 → 审批通过」后经费永远停在「已驳回」（审批闭环断裂）：",
            "🐛 认证出口在「直接调用」路径下崩溃（潜在 500）：get_current_user 在 P1-2",
            "🐛 帮扶村「新建成功却看不到新记录」：列表端点 GET /supported-villages",
            "🐞 CI 全红：vitest 半升级（v5 + coverage-v8 v3）打穿 postinstall 补丁：",
        ],
    },
    {
        "version": "1.12.3",
        "date": "2026-09-12",
        "description": "🛡️ 架构评估 P1/P2 整改（迁移单轨化 / 恢复演练 / CSRF ASGI 化 / 启动拆包 / 修复引导页）+ 安装包无测试门禁",
        "features": [
            "F1 迁移单轨化第一步：ENABLE_AUTO_MIGRATION 默认值 True → False",
            "C1 月度备份恢复演练：新增 restore_drill_service —— 把最新备份",
            "E1 CSRF 中间件纯 ASGI 化：从 BaseHTTPMiddleware.dispatch 改写为",
            "B1 数据域过滤下沉服务层（Phase 1）：新增 services/data_scope_query.py",
            "B3 启动钩子拆包：main.py 987 → ~710 行。14 个启动/停止钩子迁至",
            "A3+C2 Electron 修复引导页：新增 electron/recovery.html —— 后端",
            "F3 Electron 版本单一来源：appVersion 改用 app.getVersion()",
            "spec 剔除三方库测试资产：实测 sklearn 经 collect_data_files 把",
            "CI 双重门禁：新增 scripts/verify_package_no_tests.py",
            "extraResources 过滤兜底：backend 产物拷贝 filter 显式排除",
            "版本号全量对齐 1.12.3：整改提交只把根 package.json 提到 1.12.3，",
            "后端覆盖率门禁回 100%：整改引入的 6 行未覆盖",
        ],
    },
    {
        "version": "1.12.4",
        "date": "2026-09-12",
        "description": "🛠️ Windows 出包门禁编码缺陷修复 + B1 数据域下沉全量收口",
        "features": [
            "根因：scripts/verify_package_no_tests.py 输出中文，而 windows-2022（en-US）",
            "修复：① 脚本内强制 sys.stdout/stderr.reconfigure(encoding=\"utf-8\",",
            "回归：test_verify_package_no_tests_v123.py 新增 2 例子进程用",
            "出包影响：v1.12.3 的 ARM64 DEB 构建成功、Windows 构建失败；",
            "api 层收口：assessment、data_quality、import_export/export、project_milestones、",
            "services 层收口：ai_service(11)、ai/recommendation_service(5)、analytics_service(1)、",
            "结构性回归（新增 test_data_scope_entrypoint_v123.py，8 例）：",
            "并修正批量迁移后失效的 19 处测试 patch 目标",
            "后端全量：pytest tests/ -n auto --cov=app —— 11002 passed / 0 failed，",
            "打包门禁：verify_package_no_tests.py 在 PYTHONIOENCODING=cp1252 下 exit 0（修复前 exit 1）；",
            "静态/安全：flake8 0；bandit -ll 0（Medium/High 均 0）；security_audit.py --verbose 0 问题；",
        ],
    },
    {
        "version": "1.12.5",
        "date": "2026-09-12",
        "description": "🔒 深度审计加固（目录穿越 / 存储型 XSS / 并发 / 备份 fail-loud）+ D1 写锁退避重试",
        "features": [
            "core/upload_security.sanitize_filename：原实现仅替换 <>:/\"|?* 而保留 \\。",
            "api/v1/data_sync._safe_filename：在 sanitize 之后再 Path(...).name 兜底一次，",
            "api/v1/supported_village.upload_section_attachment：区块附件落在",
            "api/v1/supported_village.delete_section_attachment：原实现仅删库记录，",
            "api/v1/system/tasks：_tasks 内存字典无锁 —— 后台任务线程插入、请求线程迭代/删除",
            "services/backup_scheduler._run_scheduler_job：loop.run_until_complete 抛异常时",
            "services/db_maintenance.stop_wal_checkpoint_scheduler：停止后未复位 _wal_thread，",
            "services/immediate_backup.trigger_immediate_backup：t.start() 失败（线程资源耗尽）",
            "api/v1/system/backup._resolve_backup_file_path（新增）：下载/预览/校验/恢复四个入口",
            "services/backup_service：",
            "api/v1/school.import_schools_excel：delete=False 的临时上传副本成功/失败都不清理，",
            "services/permission_package_service：open(file_path, \"rb\").read()",
        ],
    },
    {
        "version": "1.12.6",
        "date": "2026-09-12",
        "description": "🛡️ 遗留风险治理第一批（P0 调度健壮性 / 启动 VACUUM / multipart 上限 / 备份语义）",
        "features": [
            "services/database_health_service._monitor_loop：last_integrity_check / last_quick_check /",
            "vacuum_database() 改为经 db_coordinator.exclusive_write() 执行，与批量导入等",
            "services/backup_scheduler：三类调度形态收敛为统一语义 —",
            "调度体提升为模块级函数（_schedule_daily/_schedule_weekly/_schedule_interval），",
            "services/backup_scheduler 新增 chunk_cleanup_job（每 30 分钟）：",
            "services/chunked_upload_service：新增 MAX_SESSIONS=200 会话数量上限，",
            "middleware/body_size_limit：原实现对 multipart/form-data 一律放行，",
            "services/backup_service._create_consistency_snapshot：快照失败不再回退",
            "cleanup_old_backups / cleanup_by_retention_days：文件删除失败（被下载流/",
            "api/v1/auth/users：三个 options 端点的 @cache_result 默认键包含",
            "requirements.txt：为 diskcache==5.6.3 登记 PYSEC-2026-2447 / CVE-2025-69872",
            "测试基建：tests/unit/test_pragma_reason_ratchet_f2.py 的 subprocess.run(text=True)",
        ],
    },
    {
        "version": "1.12.7",
        "date": "2026-09-13",
        "description": "🛡️ 遗留风险治理第二批（R2 上传体积上限 / R5 导出回收 / R9 导入拒绝记录 / R13 Windows CI 可见性）",
        "features": [
            "新增 utils.upload_helper.read_upload_with_limit(file, max_bytes, ...)：分块读取（1MB/块）+",
            "原写法先把 SpooledTemporaryFile 整包物化进内存再比较长度，校验只能拒绝请求、",
            "新增 zip_total_uncompressed_size(zf) / ensure_zip_within_limit(zf)（解压后总量 ≤ 200MB）",
            "policy_import_service 此前完全无上限：补 10MB 体积上限（分块读取）+ 1000 行上限，",
            "新增 async_export_service.purge_expired_exports(db) + 调度作业 export_purge_job",
            "此前 expires_at 只用于拒绝下载，无任何回收逻辑：exports/ 目录随使用频率单调增长。",
            "DataPackageService.import_package 校验失败分支不再落 file_path——该路径是 API 层",
            "/data-packages/{id}/validate、/{id}/download 对 file_path 为空返回 409（明确",
            "顺带修复真实缺陷：PackageStatusEnum 成员为大写 FAILED，原 PackageStatusEnum.failed",
            "pr-checks.yml 新增 windows-smoke 作业（windows-latest，PYTHONUTF8=1 +",
            "R7 恢复窗口与在途写请求竞态（P1）计划列为 W3–W4（10-09 前），需改造 get_db",
            "R12 剩余项（os._exit 优雅退出、_tasks 过期清理等）同列 W4。",
        ],
    },
    {
        "version": "1.12.8",
        "date": "2026-09-13",
        "description": "🛡️ 遗留风险治理第三批（R7 恢复维护窗口 / R12 低危批量 / R2 残余无界读取 / P-1~P-3 预防门禁）",
        "features": [
            "新增 app/core/maintenance.py 维护模式闸门与 MaintenanceGateMiddleware：",
            "BackupService.restore_backup 外层包维护窗口，返回值新增 maintenance_window_ms。",
            "/health 暴露 maintenance {active, reason, since, last_window_ms, last_waited_ms}。",
            "R12-2 慢请求/慢 SQL 计数器改互斥自增（裸 += 并发丢计数），统计快照加锁读。",
            "R12-3 RESTORE_DRILL_STATUS 改一致性快照（snapshot_status() + RLock），",
            "R12-4 审批提醒 stop() join 上限 1s→5s，超时后不复位 _running —— 否则",
            "R12-5 /system/shutdown 与 /system/restart(win32) 不再 os._exit(0)：",
            "R12-6 内存任务表 _tasks 增加 1 小时终态回收（创建/列表/统计/运行计数",
            "R12-7 create_background_task 无运行循环时返回 None（不再把任务挂到",
            "data_package_service（5 处 zip 打开点）、permission_package_service（4 处）、",
            "backup_service._verify_backup_recovery：原先把整个库文件读进内存再落盘校验",
            "分片上传端点：await file.read() → read_upload_with_limit（20MB）；",
        ],
    },
    {
        "version": "1.12.9",
        "date": "2026-09-30",
        "description": "🛡️ 深审缺陷批量修复（越权/数据完整性/静默失效/发布门禁）",
        "features": [
            "审计日志批量删除 fail-closed（system/audit.py）：非法 before_date 原先只",
            "错误报告归属校验（system/error_report.py）：原读不存在的 record.user_id",
            "报表订阅 IDOR（data/data/reports.py）：/{id}/download 与 /generate 收敛到",
            "政策附件路径穿越（policy.py）：写入/预览/下载三处统一做 realpath + commonpath",
            "数据包三端点补归属校验（data/data/data_packages.py）：preview、",
            "项目里程碑全端点数据域守卫（project_milestones.py）：里程碑读写、状态流转、",
            "上报归属校验（data/data/data_reports.py）：submit 原先无归属判断，任何登录",
            "综合报表导出门禁（import_export/export.py）：补 require_admin，学校/项目/经费",
            "组织模块策略跨组织读写（org_module_policy.py、control_package.py）：4 个策略",
            "上传文件名净化（utils/upload_helper.py）：文件名只取基名并过滤分隔符/控制字符，",
            "经费状态机红线（fund_service.py、funds.py）：创建强制 pending（忽略客户端",
            "校验规则补管理员门禁（validation.py）：增/改/删三个端点补 require_admin。",
        ],
    },
    {
        "version": "1.12.10",
        "date": "2026-10-02",
        "description": "🔧 跨平台 CI 双红根因修复（平台相关穿越判定 / 时区相关断言）+ 测试会话隔离契约",
        "features": [
            "归档恢复的路径穿越判定与运行平台绑定（app/services/data_tier_service.py）：",
            "审批时间轴排序断言的时区依赖（frontend/tests/unit/utils/approvalTimeline.test.ts）：",
            "Linux 上测试数据根逃逸（backend/tests/conftest.py）：conftest 用",
            "新增 backend/tests/unit/test_session_isolation_contract.py（2 用例）：以行为级断言",
            "新增 scripts/ci/scan_shared_vue_refs.py：扫描受覆盖率门禁锁定的 .vue 被多个测试文件",
        ],
    },
    {
        "version": "1.12.11",
        "date": "2026-10-02",
        "description": "🕐 时间基准统一：报表订阅 next_send_at / 到期派发彻底修复 + 时间转换单一事实源",
        "features": [
            "报表订阅 next_send_at 与到期派发（services/subscription_dispatch_service.py）：",
            "列表端点（api/v1/data/data/reports.py）：_subscription_to_response 改走同一入口，",
            "调度器（services/backup_scheduler.py）：订阅派发作业改传 utcnow()（aware UTC）。",
            "generate-now 端点：改传 utcnow()，与派发路径同基准。",
            "新增 models.base.UtcDateTime 类型（一处修复、所有出口正确）：库中 DateTime 列",
            "全模型接入：app/models/ 下 48 个文件的 195 处 DateTime(timezone=True) 与",
            "导出通道按本地渲染（避免导出件里出现 UTC 墙钟或 +00:00 文本）：",
            "清除「本地时间写进 UTC 列」的混用：fund_lifecycle（entered_at / confirmed_at /",
            "isinstance(col.type, DateTime) 识别失效（services/package_record_validator._date_fields）：",
            "backup_service.cleanup_by_retention_days 基准错位：cutoff 原用本地 naive",
            "列表端点的容错：_subscription_to_response 恢复对非法频率的容忍",
            "新增 app/utils/time_utils.py：utcnow / utcnow_naive / as_utc / as_utc_naive /",
        ],
    },
    {
        "version": "1.12.12",
        "date": "2026-10-03",
        "description": "🐞 全库缺陷排查修复（时间基准 / 契约脱节 / 竞态）+ 汇报大屏契约修复 + 冷启动优化 + 前端日期收敛 + 文档与门禁治理",
        "features": [
            "前端日期/时间格式化统一收敛到 frontend/src/utils/index.ts：此前散落在",
            "format 工具集补齐 12 个函数：formatDateTimeLocale / formatLocalDate /",
            "统一空值语义：新增内部 toDate() 归一化，空值/非法值一律走兜底文案 ——",
            "顺带修正两处\"按 UTC 字符串切片当本地时间显示\"的实现（funds/Detail、sentiment/Index",
            "移除收敛后产生的孤立辅助函数（SettingsOverview 的 pad）。",
            "订正 frontend/docs/design/{components,tokens,pages,hardcoded-colors-report}.md：",
            "订正 docs/03-开发文档/前后端契约规范.md：删除对从未存在的",
            "订正 AGENTS.md（CI 六个 job → 七个，补 windows-smoke 行与 static-analysis 检查项）、",
            "订正 resources/icons/README.md（按实际文件名重写）、backend/version.json",
            ".env.example 纳入版本单一来源：新增 scripts/sync-version.js 目标，",
            "「项目状态分布」饼图恒空：后端此前不返回任何状态字段，前端读的两个键都不存在。",
            "KPI「完成率」恒显 —：前端读 completion_rate，后端实际字段为 data_completeness（0~1）。",
        ],
    },
    {
        "version": "1.12.13",
        "date": "2026-10-05",
        "description": "🛡 R18 全维度排查修复（并发闸门 / 事件循环阻塞 / 竞态互踩 / 信息泄露）",
        "features": [
            "electron/worker-pool.js — Worker 池并发闸门永久失效：_active 被双扣",
            "api/v1/system/backup.py — 备份阻塞整个事件循环：备份（SQLite Backup API 全库拷贝 +",
            "api/v1/data_sync.py — 上传临时包同名互踩：沿用客户端原文件名（缺省固定 upload.zip），",
            "api/v1/system/health.py — 无认证端点信息面收敛：/health、/health/overview 此前回显",
            "electron/main.js — stopBackend 孤儿进程竞态：5s 兜底定时器无句柄且无条件",
            "services/backup_scheduler.py — 任务队列记录只增不减：LocalTaskQueue._tasks 的",
            "api/v1/projects.py：排序列白名单——此前 getattr(Project, sort_by) 接受任意字符串，",
            "deploy/kylin/config/kylin.env：部署模板不应自行降级安全基线——ACCESS_TOKEN_EXPIRE_MINUTES",
            "出厂管理员密码硬编码 Admin@2026（core/constants.py:24）与机器码初始密码熵不足",
            "备份双事实源：Electron 每 24h 直调备份端点，打穿后端 backup_interval_days（默认 30 天）",
            "control_package.py 512MB zip 在事件循环内同步解析（解压峰值 GB 级，admin-only）。",
            "data_package_service full 导出逐模型 query.all() + indent=2 全量驻留（内存约库体积 3-4 倍）。",
        ],
    },
    {
        "version": "1.12.14",
        "date": "2026-10-06",
        "description": "🔍 全库深度排查与修复（数据合并/权限收口/时间基准/健壮性）+ 文档与 PPT 同步",
        "features": [
            "数据同步「智能合并」策略完全失效（services/data_sync_service.py）：_import_table_data（ZIP /data-sync/import 路径）",
            "加密包合并永不更新（同文件 _should_update_record）：existing 来自 raw text() 查询是字符串，",
            "政策模块三处前端功能失效（调用了不存在的 store 方法，被 mock 掩盖）：",
            "备份计划端点越权（api/v1/system/backup.py）：PUT /system/backup/schedule 只校验\"已登录\"，",
            "出厂口令改值 + 服务端强制首登改密：FACTORY_ADMIN_PASSWORD 由 Admin@2026（10 位、低于自有策略",
            "backup_retention_days 脏值导致备份计划页 500：GET|PUT /system/backup/schedule 裸 int() 解析配置，",
            "last_backup_time 带时区偏移时整条自动备份失败：except ValueError 覆盖不到 naive - aware 的",
            "restore_drill_job 在 with get_db_context() 之外使用已关闭会话 发提醒：隐式重开不受 finally",
            "导入包解析加固（同 R18 后续）：data_sync 导入解析下沉线程池 + 解压体积闸门（1GB）+",
            "工作日历 localStorage 脏数据崩页：setup 顶层裸 JSON.parse 且不校验形态 → SyntaxError 让整条路由",
            "多个列表端点 limit/skip/page 无边界：limit=-1 在 SQLite 语义下等同\"不限量\"（一次拉全表）。",
            "BACKUP_COMPRESSION_LEVEL 非数字 → BackupService 构造即抛 ValueError、备份链路整体不可用；",
        ],
    },
    {
        "version": "1.12.15",
        "date": "2026-10-08",
        "description": "🔍 R20 全库逐文件代码审查修复（权限收口 / 数据域 / 功能失效 / 健壮性）",
        "features": [
            "report_templates 模块整体无角色守卫：任意登录用户可增删改共享报表模板并触发",
            "fund_lifecycle 资金写端点缺数据域：划转凭证（改/删/确认/附件）、合同（改/删/付款）、",
            "综合报表导出明细越权（async_export_service）：summary 计数已过滤但项目/经费明细",
            "report_templates overwrite 导入非原子（4 个模块 prepare 共性）：先删后插分两次提交，",
            "权限收敛（登录即可见 → 管理员）：system/config/export/json、system/error-reports",
            "项目导入：mode=overwrite 参数从未生效（静默变增量）→ 按数据域软删后导入；",
            "项目任务越权：任务更新/删除补 _can_modify_project（同组织非创建者可改删的缺口）。",
            "数据域遗漏：rural_work 统计 by_type / analytics 类登记（后者属服务层签名改造，",
            "功能失效：PDF 导出未转义 </&（标题含尖括号即 500）；消息模板 ≥2 个缺失变量",
            "数据正确性：数据清洗误删 SQL 关键字子串（standard→stard）→ 加词边界；",
            "一致性：organization_code 校验允许 -（与生成规则一致）；organization_code 缓存",
            "upload_security 允许扩展名 .gi → .gif；seed 出厂口令不再写入日志原文；",
        ],
    },
    {
        "version": "1.12.16",
        "date": "2026-10-14",
        "description": "🔐 安全与权限收敛 + 会话管理落地",
        "features": [
            "用户会话管理真实落地：新增 user_sessions 表（登录/2FA 时登记 jti/IP/UA/有效期），",
            "角色编码（code）后端权威化：rbac_roles 新增唯一 code 列（迁移回填），",
            "组织数据范围全面收敛：/organizations 列表、/tree、/{id}（越权 403）、",
            "修复缓存跨用户泄漏：orgs:list 缓存改为仅管理员启用，否则普通用户的受限结果会写入全局缓存。",
            "删除组织二次确认密码改走 X-Confirm-Password 请求头：查询串会原样进 access log。",
            "组织移动/改父级后 path/level 不级联刷新（树视图与数据权限视图长期背离）；",
            "用户管理：组织选择提交 422（树节点 id 前缀未还原）、空邮箱唯一约束 500、",
            "组织管理：编码框显示 200（信封遮蔽）、无法置为顶级（exclude_unset 语义）、",
            "角色管理：关联用户弹窗姓名/邮箱字段错位、查询与分页纯摆设（改前端过滤+切片）。",
        ],
    },
    {
        "version": "1.12.17",
        "date": "2026-10-16",
        "description": "🛡️ R28 全系统排查修复（门禁 / 数据域 / 服务正确性 / 前端与构建）",
        "features": [
            "用户管理数据域收口：/users 列表、待审列表、员工列表三处各自实现子树过滤",
            "管理端门禁补齐：/export/villages、/data-sync 下载与冲突/日志、/system-health/overview",
            "回收站批量操作数据域过滤：批量恢复/彻底删除先按调用者数据域收敛 ids（跨组织 id",
            "任务端点归属校验：cancel/delete 限本人或管理员；/tasks/running/count 补认证；",
            "工作日志可见性：非管理员仅见本人日志（原实现额外放行所有人的 system_auto",
            "近期活动：/messages/recent-activities 非管理员仅返回本人审计活动（不再回吐全局审计）。",
            "仪表盘近期动态数据域：/dashboard/recent-activities 的项目 / 经费 / 审批三路 feed",
            "报表导出数据域：公文报告导出（/export/report-word、/export/report-pdf）的",
            "错误细节不出站：system_health、system/metrics、/overview 等去 str(e)、",
            "匿名反馈长度上限：content ≤ 5000 字（原为无上限 TEXT，可被单请求灌入任意体积）。",
            "令牌刷新携带声明：refresh_access_token 现携带原 refresh token 的非保留声明",
            "服务层正确性：审批工作流 approve/reject 改带条件原子抢占（并发/重放零重复落账）；",
        ],
    },
    {
        "version": "1.12.18",
        "date": "2026-10-17",
        "description": "🎯 门禁说真话 + 现场可自证（P0 批次）",
        "features": [
            "系统诊断包导出（仅管理员）：GET /api/v1/system/diagnostics/summary 返回结构化摘要",
            "升级排练门禁：backend/scripts/upgrade_rehearsal.py + PR Checks 新作业",
            "测试抖动账本：scripts/ci_flake_report.py 解析 pytest-rerunfailures 的 RERUN 行",
            "原始 SQL f-string 豁免门禁：scripts/check_raw_sql_fstrings.py 用 AST 取完整语句范围，",
            "JSON 列可变性台账：26 个 JSON 列逐列声明语义（25 个\"整体替换\" / 1 个 MutableList），",
            "100% 分支门禁的随机失败：generate_password 的\"重试直到满足复杂度\"分支概率性未命中，",
            "一项\"修复\"被 CI 证伪后回退（重要教训）：曾给 tests/conftest.py 的 client fixture 加",
            "分片运行的信号噪音：逐片加 --cov-fail-under=0（此前每片都因\"片内覆盖率不满 100%\"",
            "版本号 1.12.17 → 1.12.18（node scripts/sync-version.js --check 15 处一致）。",
            "PR Checks 作业数 7 → 8（新增 upgrade-rehearsal）；static-analysis 增补原始 SQL 豁免门禁。",
        ],
    },
    {
        "version": "1.12.19",
        "date": "2026-10-17",
        "description": "🧩 功能补全 + 数据完整性修复（W17/W18 批次）",
        "features": [
            "提醒中心处置闭环：POST /reminders/{id}/handle|ignore|snooze|reopen（仅提醒接收人本人，",
            "结对帮扶与走访台账：pairing_records + visit_records（迁移 pairing_001），",
            "捐赠物资台账（后端）：donation_items（迁移 donation_item_001）+ 服务 + API",
            "指标字典（CONTEXT.md）：总人口/总户数/人均收入/经费合计/报表村数等逐条登记",
            "两道防腐门禁（已接入 CI static-analysis 与 make test-local）：",
            "启动预检（app/startup/preflight.py）：磁盘余量、数据库可写性、系统时钟落后于数据、",
            "诊断包业务段：/system/diagnostics 新增 business（备份状态 / 调度器 / 后台任务失败 /",
            "数据包导出保留策略：每日 04:10 清理超过保留期（默认 7 天）的导出文件，避免长期运行撑满磁盘。",
            "总人口两套口径（W18 P0-1）：工作台取「全库最大年份」求和，统计页取「每村各自最新年」，",
            "data_scope 形参收下不用（W18 P0-2）：_avg_per_capita_income 收了数据范围却从未参与过滤，",
            "报表总数封顶 100（W18 P1-1）：total_villages 原用明细 limit(100) 后的 len()，改为独立",
            "未关联村经费越权（W18 P1-2）：village_id IS NULL 的经费原先无条件计入所有用户合计，",
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
            "捐赠物资台账前端（w17-003 完成）：新增 views/donation/List.vue 与 api/donations.ts ——",
            "CI 分支覆盖棘轮随机变红（PR Checks backend-test）：该步骤此前再跑一遍全量 pytest",
        ],
    },
    {
        "version": "1.12.22",
        "date": "2026-10-17",
        "description": "🧾 全部遗留工单落地（004~010 七项）",
        "features": [
            "w17-004 工作移交：/handover 页（清单勾选 → 接任人 → 确认执行 → 交接单 PDF / 历史回放）；",
            "w17-005 年度数据滚动填报：yearly/{year}/prefill（逐字段三态差异）+ rollforward 批量沿用",
            "w17-006 导出物口径脚注：村/学校/项目/经费/综合报表五类导出统一「口径说明」（数据截止/过滤条件/软删/",
            "w17-007 一村（校）一档 PDF：/supported-villages/{id}/dossier.pdf 与 /schools/{id}/dossier.pdf",
            "w17-008 AI 结论可解释 + 业务数据体检：10 个 AI 端点统一返回结构化 rationale + data_scope，",
            "w17-009 金额展示与筛选记忆：MoneyText 组件（千分位/4 位小数/空值占位/人民币大写）与",
            "w17-010 大屏可配置：右上角「设置」抽屉（卡片显隐/排序、刷新频率 30s/60s/5min/关闭、汇报脱敏），",
            "前端 vue-tsc 类型错误导致 CI 构建失败：捐赠台账表格槽位 row 为 DefaultRow，直接传 DonationItem 形参",
        ],
    },
    {
        "version": "1.12.23",
        "date": "2026-10-18",
        "description": "汇报大屏对象筛选（村/校/单位）+ 在途批次收口",
        "features": [
            "汇报大屏对象维度筛选（W20）：新增 GET /api/v1/bigscreen/filters（数据域内帮扶村 / 帮扶学校 /",
            "大屏前端对象筛选：views/bigscreen/BigScreen.vue 头部筛选条（全部 / 帮扶村 / 帮扶学校 / 帮扶单位 +",
            "方案文档与用户手册：新增 docs/design/汇报大屏对象筛选与下钻方案.md（背景、现状调研、四类 scope",
            "单校成效统计端点（W18 在途收口）：GET /api/v1/schools/{school_id}/statistics，由服务端聚合",
            "W18 在途安全与数据完整性收口：数据包导出改走原生 SQL，PII 列保持密文出包（不再经",
            "测试与门禁收口：补齐 W18 遗留 19 个「实现已变、测试未跟」的失败用例与 5 个模块",
            "大屏口径修正：KPI 标签去掉冗余的 \"(万)\"（由 unit 字段承载单位）；Fund.year 为 NULL 的",
            "年度趋势聚合从 /dashboard/yearly-trends 端点抽成 _build_yearly_trends(db, data_scope, years)，",
            "删除 UserManagementRealRender.test.ts、UserManagementRender.test.ts（与专属测试重复，",
        ],
    },
    {
        "version": "1.12.24",
        "date": "2026-10-18",
        "description": "🧹 W5-T5 解包口径收口 + 分支门禁确定性",
        "features": [
            "前端 50 处 no-restricted-syntax 违规（.data.items 手写解包）全部收敛到 @/utils/unwrapList：",
            "版本兜底同步补漏：frontend/src/config/constants.ts 的 SYSTEM_VERSION 硬编码兜底随单源同步更新，",
            "backend/tests/unit/test_branch_closure_r22.py（21 项）：为 23 个历史错误/边界分支补真实行为回归",
        ],
    },
    {
        "version": "1.12.25",
        "date": "2026-10-18",
        "description": "🔧 ARM64 发布流水线彻底修复（镜像限流根因）",
        "features": [
            "ARM64 流水线失败根因：build-backend 作业独立冷启动 docker buildx build，需再次拉取",
            "修复方式（消除重复冷构建，而非绕过）：",
            "效果：ARM64 作业数减少 1 个；基础镜像只拉取一次；瞬态网络/限流失败可自动重试；",
            "本版本无运行时代码变更（仅 CI/Dockerfile），Windows 安装包与 standalone DEB 内容与 v1.12.24 一致。",
        ],
    },
    {
        "version": "1.13.0",
        "date": "2026-10-18",
        "description": "导航/菜单单一源重构 + 系统管理 6 聚合页",
        "features": [
            "导航增强：Ctrl+K 菜单搜索（板块/入口/Tab 全量可搜、键盘上下选择+回车跳转、空搜索显示收藏与最近）、",
            "系统管理 6 聚合页（/system/console/:group + 页内 ?tab=<tab key>）：",
            "导航入口补齐：汇报大屏、提醒中心、帮助中心、数据上报（上报/接收/版本）、批量操作、",
            "后端菜单 v2 单一源：MENU_SECTIONS（6 板块）+ MENU_DEFINITIONS 扁平条目",
            "左侧导航重排为 7 板块：工作台（固定第一）+ 帮扶业务 / 乡村振兴 / 工作协同 / 分析汇报 / 数据管理 / 系统管理；",
            "前端侧栏、移动端底部导航、权限面板与权限包菜单树全部改为后端菜单数据驱动，",
            "菜单过滤语义：group 任一子项可见即显示并裁剪子项；console 可见 = console.key 或任一",
            "菜单对齐门禁 scripts/check_menu_alignment.py 重写为规则 A~E（AST 解析单一源：",
            "删除前端菜单副本：src/config/menu-config.ts、src/utils/systemMenu.ts 及",
            "删除后端 3 个死菜单项：user-backup、data-quality、system-security（无独立导航出口/重复 path）。",
            "删除根目录旧 PPT 副本，docs/帮扶管理信息系统介绍.pptx 为唯一对外介绍材料。",
            "删除文档中\"前后端菜单双轨同步 / menu-config 引用 / 旧系统管理入口清单\"等过时说明。",
        ],
    },
    {
        "version": "1.13.1",
        "date": "2026-10-18",
        "description": "修复 GitHub 发布构建失败 + 安装包自包含验证",
        "features": [
            "Windows 发布构建失败（v1.13.0 未产出 Windows 安装包）：tag 构建的 smoke-test",
            "ARM64 发布构建失败（Electron ARM64 DEB 连续两版缺失）：docker/Dockerfile.kylin-standalone",
            "安装产物自包含冒烟（CI，Windows 构建作业）：electron-builder 解包后直接启动打包后端",
            "发布门禁职责划分写入 README：全量测试 = main 的 PR Checks + Nightly；tag 构建 = 发布专项门禁",
        ],
    },
    {
        "version": "1.13.2",
        "date": "2026-10-18",
        "description": "修复发布门禁依赖安装遗漏",
        "features": [
            "v1.13.1 的 smoke-test 重构遗漏依赖安装步骤：Backend release smoke subset 直接执行",
        ],
    },
    {
        "version": "1.13.3",
        "date": "2026-10-18",
        "description": "自包含冒烟步骤诊断增强（动态端口 + stdout/stderr 落盘）",
        "features": [
            "CI 自包含冒烟在 Windows runner 上超时失败（v1.13.2 唯一阻断项，本地同脚本通过）：",
        ],
    },
    {
        "version": "1.13.4",
        "date": "2026-10-18",
        "description": "修复 ARM64 后端产物主程序文件名（Electron DEB 最后一项阻断）",
        "features": [
            "ARM64 Electron DEB 仍失败（v1.13.3 注解为「缺后端主程序」）：backend-output 阶段 COPY 源路径",
        ],
    },
    {
        "version": "1.14.0",
        "date": "2026-10-18",
        "description": "功能大迭代（一户一档/影像库/消费帮扶/OCR/报表组合/导航折叠）",
        "features": [
            "一户一档：新表 households / household_members / household_risk_records，API /households/*，",
            "影像库：新表 photo_archives，API /media/photos/*，页面 /media：按村/校/项目/时间/标签归档；",
            "消费帮扶台账（替换已下线的舆情监测）：新表 consumption_records + /consumption/* + 页面 /consumption：",
            (
                "经费凭证 OCR：services/ocr_service.py（rapidocr-onnxruntime 1.4.4，完全离线 CPU）+ POST /funds/ocr-voucher"
                "："
            ),
            "报表模板组合导出：POST /report-templates/{id}/export?format=xlsx|csv|docx|pdf&year +",
            "导航体验：7 板块标题放大（18px 加粗）、默认折叠、点击展开/收起（localStorage nav:expanded-sections）。",
            "汇报大屏退出：大屏头部「退出大屏」→ 退出全屏并返回工作台。",
            "数据校验合并页：/data-verify 单页三 Tab（校验执行 / 规则管理 / 字段说明），问题清单可定位跳转与导出；",
            "数据上报链路修复：枚举列导出的枚举名与导入校验的枚举值不一致导致上级整表 rejected（学校等）；",
            "驻村工作台：删除页面/路由（无后端模块），菜单 key checkin 保留 legacy。",
            "舆情监测：删除后端 api/v1/sentiment.py、models/sentiment.py、services/sentiment/（采集/分析）与前端页面/API，",
            "国际化/邮件设置：删除 I18nManagement.vue / EmailSettings.vue 及路由；菜单 key i18n / email 保留 legacy。",
        ],
    },
    {
        "version": "1.14.1",
        "date": "2026-10-18",
        "description": "修复空库迁移链 / E2E 折叠适配 / ARM64 构建加固",
        "features": [
            "空库初始化迁移链（严重：全新安装 alembic upgrade head 必失败）：v1.14.0 删除",
            "E2E 适配 7 板块默认折叠：v1.14.0 起侧栏板块默认折叠，E2E 用例点击子菜单/断言子项前",
            "ARM64 构建 npm 网络重试加固：build-arm64.yml 的 Build Frontend 步骤由裸",
            "E2E 辅助函数新增折叠展开工具；dashboard.spec.ts / permission-packs.spec.ts 适配新导航交互。",
        ],
    },
    {
        "version": "1.14.2",
        "date": "2026-10-18",
        "description": "修复发布门禁时序缺陷（v1.14.1 构建被误拦）",
        "features": [
            "发布前置门禁误拦合法 tag 构建：v1.13.1 引入的门禁只检查「main 最近一次 completed 的",
            "说明：v1.14.1 的代码修复（空库迁移链幂等、E2E 折叠适配、ARM64 npm 重试加固）不受影响，",
        ],
    },
    {
        "version": "1.14.3",
        "date": "2026-10-18",
        "description": "ARM64 构建网络韧性加固（npm/Docker registry 抖动）",
        "features": [
            "ARM64 构建因 CI 网络抖动间歇失败（v1.14.2）：v1.14.2 的 Build Frontend 在",
            "说明：v1.14.2 已修复发布门禁时序缺陷（scripts/check_release_gate.py），Windows 安装包",
        ],
    },
    {
        "version": "1.15.0",
        "date": "2026-10-19",
        "description": "UI v2.0：精美·科学·一致性的系统级视觉重构",
        "features": [
            "设计系统 v2（Token 升级）：主色阶 --color-primary-50/100/500/600/700/900；卡片边框 --color-card-border +",
            "主题 5→3 收敛：军绿（默认）/ 深色大屏 dark-bigscreen（仅大屏页强制）/ 户外高对比 outdoor；",
            "显示偏好 4 档（localStorage ui:prefs，<html data-*> 驱动）：字号（紧凑/标准/大号，--font-scale 0.92/1/1.12）、",
            "全局模板样式与通用组件：card.scss（.app-card/.app-stat-card/.stat-trend/.num-cell）、",
            "导航体验：侧栏当前板块 3px 金色竖条、当前板块自动展开并持久化（nav:expanded-sections）、",
            "工作台：KPI 统计卡网格（28px/700/tabular-nums）+ 待办清单卡 + 图表两列 + 快捷入口/近期动态层级重排；",
            "汇报大屏：三层结构（标题时间条 / KPI 大数字 / 2–3 列图表）；data-bigscreen-distance=\"3m|6m|10m\"",
            "一户一档：列表 4 张统计卡 + 筛选/表格卡 + 三件套 + 数字列右对齐 + 删除操作收进下拉；",
            "质量门禁：tests/unit/ui/ui-tokens.test.ts（22 条 Token/主题/偏好/大屏契约静态断言）；",
            "列表页 page_size=500 超后端上限（200）导致 422：一户一档/消费帮扶/影像库/权限包页面统一改为 200，",
            "工作台 KPI 取消请求误判为错误：路由导航/卸载时 axios CanceledError 不再记录 error 日志、不置错误态、",
            "Token 重复定义覆盖：删除后置旧 --shadow-card/--radius-lg-plus 覆盖，v2 轻阴影与 8px 圆角实际生效。",
        ],
    },
    {
        "version": "1.15.1",
        "date": "2026-10-19",
        "description": "CI 后端全量并发稳健化（修复 v1.15.0 Windows 包被门禁误拦）",
        "features": [
            "PR Checks backend-test 在 4 核 runner 上偶发失败：v1.15.0 的 backend-test 使用",
            "说明：v1.15.0 的 ARM64 构建（standalone DEB + Electron DEB）已成功产出并发布 Release；",
        ],
    },
    {
        "version": "1.15.2",
        "date": "2026-10-19",
        "description": "CI 后端测试改串行（彻底规避 xdist worker 崩溃）",
        "features": [
            "PR Checks backend-test 在 ubuntu-latest 上提前退出（v1.15.0/v1.15.1）：",
            "说明：v1.15.0/v1.15.1 的 ARM64 构建均已成功产出；Windows 安装包因 backend-test 门禁误红未产出。",
        ],
    },
    {
        "version": "1.15.3",
        "date": "2026-10-19",
        "description": "CI 后端测试分段执行（单进程内存峰值治理 + 失败诊断）",
        "features": [
            "PR Checks backend-test 三连失败（v1.15.0/v1.15.1/v1.15.2）的根因治理：",
            "说明：本版本仅修 CI 执行方式，产品代码与 UI v2.0 内容与 v1.15.0 完全一致（版本号同步更新）。",
        ],
    },
    {
        "version": "1.15.4",
        "date": "2026-10-19",
        "description": "backend-test 分段覆盖率阈值修复",
        "features": [
            "backend-test 段 1（integration/security）因覆盖率阈值误判失败：v1.15.3 拆分后，段 1 只覆盖部分模块，",
        ],
    },
    {
        "version": "1.15.5",
        "date": "2026-10-19",
        "description": "CI Runner 固定 ubuntu-24.04（规避 Ubuntu 26 迁移导致的 backend-test 崩溃）",
        "features": [
            "PR Checks backend-test 连续失败（v1.15.0–v1.15.4）的根因定位与规避：",
        ],
    },
    {
        "version": "1.15.6",
        "date": "2026-10-19",
        "description": "全面体检修复：CI 稳定化 + 数据权限缓存泄漏 + 前端依赖冲突 + 构建可复现（W24）",
        "features": [
            "v1.15.5 提交误含测试残留文件：本地验证与探针脚本运行产生的",
            "保留合法的辅助脚本 scripts/run-python.js（Python 解释器解析）与 scripts/run-frontend.bat（前端启动）。",
            "P0 数据权限缓存键跨角色泄漏（backend）：villages:list / schools:list 缓存键仅含",
            "P0 前端依赖 peer 冲突导致 CI 前端安装失败（frontend）：vite@^7.3.6 与",
            "P1 日志 PII 脱敏被绕过：默认 LOG_FORMAT=json 下自定义 JsonFormatter 用",
            "P1 跨用户共享缓存泄漏 + 部署链路缺陷：按数据范围裁剪的",
            "P1 CI backend-test 稳定性重设计：新增 scripts/ci_backend_test_segment.sh，PR Checks 后端测试",
            "P1 CI 失败上报误报修复：旧 \"Report backend failure\" 把 pytest 进度行当覆盖率缺口发成",
            "P1 CI 基础设施升级：4 个 workflow 全部 action 升级到 Node24 兼容版本并重新 SHA pin",
            "P1 构建可复现性（裸 python）：新增 scripts/find-python.bat / scripts/run-python.js /",
            "P2 分页上限缺失：GET /users、GET /machine-code/organization/list 的 page_size 为裸 int",
            "P2 仓库卫生：清理 v1.15.5 误提交的测试/探针临时文件（见下），.gitignore 增加",
        ],
    },
    {
        "version": "1.15.7",
        "date": "2026-10-19",
        "description": "修复 workflow 的无效 action SHA（CI job 3 秒失败根因）",
        "features": [
            "PR Checks / 构建 Workflow 的 actions/setup-python 等 action 引用失效（v1.15.6）：",
            "说明：本版本仅修 CI 配置，产品代码与 UI v2.0 内容与 v1.15.0 完全一致；backend-test 的",
        ],
    },
    {
        "version": "1.15.8",
        "date": "2026-10-19",
        "description": "待决策项彻底落地：viewer 严格只读 + 非回环注册 fail-closed + ARM64 发布门禁 + nightly 稳定化",
        "features": [
            "viewer 角色服务端强制只读：新增集中式 ASGI 中间件 backend/app/middleware/viewer_readonly.py，",
            "ARM64 发布门禁：build-arm64.yml 两个 Release 前新增 Verify release gate is green",
            "nightly 后端稳定化：nightly-full.yml 由单步 -n auto 改为与 PR Checks 同口径的 6 段独立",
            "部署文档安全红线：补齐多机/LAN 部署必须全实例统一 PASS_CODE_SECRET、viewer 严格只读说明，",
            "非回环自助注册 fail-closed（安全决策，保留 R9 跨机注册能力）：/auth/register 在来源",
        ],
    },
    {
        "version": "1.15.9",
        "date": "2026-10-19",
        "description": "backend-test 恢复单进程全量（分段方案等效性验证失败后回退）",
        "features": [
            "分段执行无法与单进程全量等价（v1.15.3–v1.15.8 的覆盖率门禁失败根因）：",
            "说明：本版本仅修 CI 执行方式；产品代码与 UI v2.0 内容与 v1.15.0 完全一致。",
        ],
    },
    {
        "version": "1.15.10",
        "date": "2026-10-19",
        "description": "backend-test 回归 8 段执行器 + 补充精确覆盖率测试",
        "features": [
            "backend-test 采用 8 段执行器（规避单进程在 Linux runner 的 SIGSEGV）",
            "补充 2 个精确覆盖率测试（补齐 99.99% 的缺口）：",
            "说明：本版本仅修 CI 测试执行与测试补充，产品代码与 UI v2.0 内容与 v1.15.0 完全一致。",
        ],
    },
    {
        "version": "1.15.11",
        "date": "2026-10-19",
        "description": "backend-test 12 段细粒度执行（缓解 SQLAlchemy C 扩展 SEGV）+ faulthandler",
        "features": [
            "backend-test 的 SIGSEGV 进一步定位：v1.15.10 的 8 段方案中 seg5（unit root b-d-g-h-j-l-m-q-s，",
            "说明：本版本仅调整 CI 分段粒度；产品代码与 UI v2.0 内容与 v1.15.0 完全一致。",
        ],
    },
    {
        "version": "1.15.12",
        "date": "2026-10-19",
        "description": "backend-test 12 段执行器稳定版（合并 R33 后首次完整验证）",
        "features": [
            "backend-test 12 段细粒度执行（含 R33 并入后的测试面）：本版本在 R33（单位授权）代码并入",
            "说明：本版本主要验证 CI 修复与 R33 合并后的整体门禁；产品 UI v2.0 内容与 v1.15.0 一致。",
        ],
    },
    {
        "version": "1.15.13",
        "date": "2026-10-19",
        "description": "R34 发布闭环：CI 红项修复 + R33 导航入口 + 文档/PPT 更新 + 冗余清理",
        "features": [
            "PR Checks 红项修复（v1.15.12 遗留）：flake8 F401（grant_package_service.py 未使用导入）、",
            "R33 单位授权功能 UI 不可达：/system/org-grant、/system/grant-import 路由/页面/API 齐全但",
            "前端死代码清理：移除 api/fundsRecycle.ts、api/schoolsRecycle.ts 中未使用的 request",
            "前端覆盖率合并稳定性：router-index.test.ts 为 R33 两个懒加载页面补 vi.mock 桩，避免同一",
            "README / CLAUDE.md 测试规模与构建命令更新；.env.example 新增 R33 GRANT_* 配置块；",
            "PPT（docs/帮扶管理信息系统介绍.pptx）更新至 v1.15.13：版本号、测试规模（13,926 / 6,865）、",
            "安全复检：P0 无；viewer 只读、非回环注册门禁、PII 加密/日志脱敏、上传 ZIP 限长、CSRF/安全头",
            "R33 后端 5 个新模块覆盖率 100%（124 tests）；R33 前端 3 个新文件覆盖率 100%（36 tests）。",
            "API 契约：830 后端路由 vs 528 前端调用点，0 不匹配；菜单对齐 A~E 通过。",
            "Windows 构建链终审：v1.15.0 以来未产出 Windows exe 均为 PR Checks 红被 release gate 拦截",
        ],
    },
    {
        "version": "1.15.14",
        "date": "2026-10-19",
        "description": "发布版：CI 全绿后成功构建 Windows x64 完全集成安装包",
        "features": [
            "PR Checks 全绿（含 12 段后端测试与 100% 覆盖率门禁）；tag v1.15.14 触发 Build Windows Installer 成功，",
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
            "一户一档入口收敛：侧栏移除「一户一档」一级菜单，入口迁入「帮扶村管理 → 年度数据管理」页首张卡片",
            "修复帮扶村管理搜索重置行控件宽度不一致（默认宽度与固定 140px 混用）、帮扶学校/经费台账等表格列宽无法调整的体验问题。",
            "lint:check、vue-tsc --noEmit 0 错误；硬编码色值棘轮 305/305 零新增。",
            "定向单测 45 files / 1325 tests + 布局/UI token 相关 238 tests 全部通过。",
        ],
    },
    {
        "version": "1.15.17",
        "date": "2026-10-21",
        "description": "系统管理：国际化彻底清除 + 导航死链治理 + 依赖安全修复",
        "features": [
            "国际化能力彻底移除（系统为纯中文单语部署，该能力从未上线使用，前后端一并清掉）：",
            "两处导航死链：SettingsOverview.vue 快捷导航的「国际化 → /system/i18n」与",
            "导航死链门禁：src/utils/navLinks.ts + tests/unit/nav-links.test.ts。",
            "生产依赖安全漏洞（阻断发布的根因）：axios@1.20.0 传递依赖",
            "文档全量校准到 v1.15.15：README / CLAUDE.md / CONTEXT.md / AGENTS.md 与 docs/ 全量更新（版本、测试规模",
            "演示 PPT 更新至 v1.15.15：docs/build_ppt.js 源码直出 51 页（新增 R35 UI 精细化方案 C 页；版本号 / 测试规模 /",
            "新增 docs/04-部署文档/RELEASE_NOTES-v1.15.15.md（升级必读 GRANT_* / PASS_CODE_SECRET / viewer 只读 /",
            "重写 根《项目文件结构说明.md》（v1.12.11 → v1.15.15，目录树 / 文件数 / 导航 / 门径口径全面校准）。",
            "删除 12 份过期一次性文档：R28 / W18 批次报告、代码审查报告-2026-10-08、系统全面排查报告-2026-10-14、",
            "清理仓库根 ignored 临时产物（运行日志 / 一次性脚本 / 探针临时目录 / 测试残留 db / 缓存）与 .scratch/ 内",
        ],
    },
    {
        "version": "1.16.0",
        "date": "2026-10-21",
        "description": "系统管理梳理（分组导航 / 危险操作硬化）+ 离线瓦片地图 + PII 密钥跨机迁移 + 架构清理",
        "features": [
            "PII 密钥跨机迁移 API（api/v1/system/pii_key.py，R34-2 / P1-2）：多机离线同步时 PII 列以密文出包，",
            "离线瓦片地图：前端引入 Leaflet（leaflet + @types/leaflet）、新增 components/map/RasterTileLayer.vue",
            "瓦片工具链 scripts/tiles/：切片/校验/清单（MANIFEST.json）生成，verify_tiles.py --require-min N 作为门禁；",
            "ARM64 离线 OCR 出包门禁（E 区）：requirements-arm64-ocr.txt + Dockerfile 安装 headless cv2/onnxruntime，",
            "本地等价 CI 的分段测试执行器 scripts/run_backend_tests_segmented.py（12 段 + --cov-append 合并，",
            "文档数字漂移门禁 scripts/check_doc_numbers.py（端点数 / 路由模块数 / 前端测试文件数 / 后端用例数）。",
            "安全审计覆盖棘轮：scripts/security_audit.py 改为动态发现全部写路由模块，与",
            "危险操作统一二次确认：新增 composables/useDangerConfirm.ts（普通确认 / 高危录入确认两种强度），",
            "危险操作强制审计（后端补 4 处 AuditLogger.log）：",
            "权限抽屉「生效概览」（PermissionAssignmentDrawer.vue）：顶部一屏展示用户（含姓名）、",
            "设备与授权中心（MachineCodeManagement.vue）：表格支持多选 → 复制所选机器码 / 通行码；",
            "聚合页左侧分组导航（SystemConsole.vue）：系统管理 6 个聚合页由横向 tab 平铺改为「左分组 + 右内容」，",
        ],
    },
    {
        "version": "1.16.1",
        "date": "2026-10-21",
        "description": "安装包发布修复：ARM64 OCR 载荷门禁改为分级（v1.16.0 的 ARM64 产物链被拦）",
        "features": [
            "ARM64 安装包无法产出：v1.16.0 新增的「Verify OCR payload」步骤是硬失败门禁，但 PyInstaller 阶段",
            "v1.16.0 的 Release 只产出了 Windows x64 安装包（273.07 MB）；ARM64 两个 DEB 因上述门禁缺失。",
        ],
    },
    {
        "version": "1.16.2",
        "date": "2026-10-22",
        "description": "ARM64 内置 OCR 出包门禁修正 + 遗留空表安全清除（r35 迁移）",
        "features": [
            "ARM64 OCR 出包门禁误判（会让整条 ARM64 产物链失败）：v1.16.0/v1.16.1 的",
            "清除 W22 遗留的 6 张零引用表（r35_drop_legacy_tables_001，在 v1.16.0 因升级风险被移出后重做）：",
            "升级演练与迁移的显式契约：新增 backend/scripts/gate_baselines/upgrade_legacy_tables.json，",
            "迁移单测 tests/unit/test_migration_r35_legacy_tables.py（7 项）：空表删除 / 有数据改名归档 /",
            "v1.16.1 的结论更正：ARM64 内置 OCR 已生效（无需再按\"降级\"对待）；v1.16.0 的 Release 仅 Windows 包，",
        ],
    },
    {
        "version": "1.16.3",
        "date": "2026-10-22",
        "description": "单位授权改用「单位选择器」 + 权限/机构/角色/用户/注册登录操作说明",
        "features": [
            "单位授权配置不再手输数字 ID（OrgGrant.vue）：原输入框要求管理员手抄 organizations.id，",
            "新增 docs/02-用户手册/权限与组织管理操作说明.md：权限 4 层叠加模型（用户白名单 > 权限包 > 角色默认 > 系统角色）",
            "用户手册索引与《系统管理操作说明》增加交叉引用。",
            "OrgGrant.test.ts 增至 25 例：单位树拍平（层级缩进/缺名称缺编码/非法 id 兜底）、非数组输入防御、",
        ],
    },
    {
        "version": "1.16.4",
        "date": "2026-10-22",
        "description": "组织编码改用行政区划代码（3 级） + 默认关闭自助注册 + 账号解锁",
        "features": [
            "组织编码 = 行政区划代码（GB/T 2260，统一 6 位）：XX0000 省级 / XXYY00 市州级 / XXYYZZ 县市级。",
            "组织层级收敛为 3 级：OrganizationLevel 由 5 值收敛为 3 值；/organizations/types/options",
            "创建组织：编码必填、纯数字 6 位；层级由编码自动推导（显式传值必须一致，否则 422）；",
            "更新组织：编码锁定（创建后不可修改，需变更请停用后新建），返回 422 并说明原因。",
            "自助注册默认关闭：新增配置 SELF_REGISTER_MODE（默认 off），关闭时",
            "注册不再自动创建组织：self_verify_org_pass_code() 找不到组织时直接返回 None。",
            "账号解锁：新增 POST /users/{user_id}/unlock（仅管理员；清锁定计数 + 写 account_unlock 审计）。",
            "前端对齐：组织列表/详情层级标签改为「省级单位/市州级单位/县市级单位」；组织表单编码必填并提示 6 位规则。",
            "新增 backend/tests/unit/test_p1_admin_area_code.py（28 例）：编码校验三分支、层级推断三档、",
            "更新既有组织/枚举/认证/覆盖用例至新契约（编码必填、3 级枚举、默认关注册）。",
        ],
    },
    {
        "version": "1.17.0",
        "date": "2026-10-23",
        "description": "介质链路治理（查重/台账/单位码/回执） + 系统自检 + W27 全栈收敛",
        "features": [
            "整包查重：新增 services/package_import_guard.py，以整包 SHA256 为指纹查 audit_logs 台账；",
            "导入台账：导入成功写 package_import（类型/来源单位码/校验和/记录数/结果），",
            "导入回执：确认导入后写 package_receipt（接收单位码、来源单位码、记录数、冲突策略），",
            "来源单位码核对：新增 services/package_org_code.py；数据包导入时比对包内 org_code",
            "冲突策略落库：确认导入时把「逐条比对 / 以包为准」写入导入历史 details_json，事后可追溯。",
            "前端：新增 components/import/ImportPreviewDialog.vue（包信息 + 差异 + 重复告警 + 策略三选）；",
            "新增 services/self_check_service.py 与 GET /api/v1/self-check（仅管理员），一次体检 6 项：",
            "「系统设置」页新增自检卡片（components/system/SelfCheckCard.vue）：正常/提醒/异常三态，",
            "包完整性校验（core/package_integrity.py）：管控包 / 配置包 / 权限包导入强制校验 checksum；",
            "经费禁止自批（FUND_ALLOW_SELF_APPROVAL 默认 False）：创建人不得审批自己创建的经费记录。",
            "跨机业务键修复：BUSINESS_KEYS 由「仅组织」改为「组织 + 业务唯一标识」",
            "迁移 r36~r41：删除 rural_tasks / budget_records / annual_income / issues 等零引用表与列，",
        ],
    },
    {
        "version": "1.17.1",
        "date": "2026-10-24",
        "description": "版本号口径修复 + 本地安装包构建修复",
        "features": [
            "/health 版本号不再被陈旧构建指纹覆盖：_build_info.json 是 CI 构建产物（已 gitignore），",
            "scripts/build/build-installer-local.ps1 补 UTF-8 BOM：该脚本含中文且此前无 BOM，",
            "新增 docs/02-用户手册/介质数据包导入与系统自检操作说明.md：离线介质包的查重 / 来源单位码核对 /",
            "后端 12 段全量 14,364 用例全绿 + 覆盖率 100%；前端 339 文件 / 7,020 用例全绿 + 覆盖率 100%",
            "升级演练 v1.16.4(r35) → 当前(r41)：122 表数据完好、落在 head",
            "8 道棘轮门禁 + 菜单对齐 A~E + console tab 30/30 + 文档数字 + 版本一致性 + 硬编码色棘轮 154/154 全绿",
            "本地完整构建：前端 683 文件 12.27 MB、静态资源审计 0 缺失、Windows 安装包 378.1 MB",
        ],
    },
    {
        "version": "1.17.2",
        "date": "2026-10-24",
        "description": "端到端排查修复：组织创建不可用 + 自检路径错位",
        "features": [
            "创建组织在真实 HTTP 下必然失败（严重）：OrganizationCreate schema 漏掉 code 字段，",
            "系统自检端点路径错位（真机 404）：模块注册在 /api/v1/self-check（根级），",
            "tests/unit/test_p3_org_create_http_contract.py（8 例）：只走 TestClient，",
            "test_p3_self_check_api.py 增补路径契约用例：断言路由为 /api/v1/system/self-check、",
            "6 个从未接入任何页面的通用组件：AppEmpty / AppError / AppLoading /",
            "ErrorBoundary.vue 予以保留：审计脚本初判\"不可达\"是误报 ——",
            "3 个一次性 PPT 版本脚本：scripts/update_pptx_versions_20260912/20261016/20261017.py。",
            "后端 12 段全量回归（14,404 用例）+ 前端 329 文件 / 6,995 用例，覆盖率门禁均 100%。",
            "本机验证补充：vue-tsc --noEmit 0、ESLint（CI 口径 eslint src --max-warnings=0）0、",
        ],
    },
    {
        "version": "1.17.3",
        "date": "2026-10-24",
        "description": "打包环境可用性修复（前端目录自发现 + 完整性检查误报）",
        "features": [
            "打包后端在无环境变量时找不到前端（真机白屏风险，重要）：",
            "冻结运行时误报「关键文件缺失」：startup/environment.py 对 app/core/config.py 等 4 个",
            "test_static_files.py 增补 onedir 布局推导用例（上溯三级 = resources，前端在其下）；",
            "test_environment_integrity_helpers.py 增补「冻结跳过 / 开发态保留」双向用例。",
        ],
    },
    {
        "version": "1.17.4",
        "date": "2026-10-24",
        "description": "离线瓦片包导入被 10MB 请求体上限拦截（现场 413）",
        "features": [
            "导入瓦片包报「上传内容超过大小限制 (10MB)，请拆分或压缩后重试」：",
            "回归测试：backend/tests/unit/test_body_size_limit_map_tiles.py（6 项，覆盖 512MB 放行、",
            "版本号单源同步至 1.17.4（node scripts/sync-version.js --write，14 个文件）。",
        ],
    },
    {
        "version": "1.18.0",
        "date": "2026-10-24",
        "description": "离线加固批次：告警开关 / 误导口径 / 备份可迁移 / 麒麟数据目录 / 长期运行可靠性",
        "features": [
            "OFFLINE_MODE 统一开关（默认 True）：alert_service 邮件/Webhook 两通道入口先短路（INFO + return False，",
            "备份携带密钥指纹：backup_info.json 新增 key_fingerprint（SHA256 前 16 位，复用 pii_crypto.key_fingerprint()，",
            "/health 新增 clock 与 database 只读块：时钟漂移 {status, behind_days}（120s TTL 缓存、不含异常原文）；",
            "备份启动补跑（catch-up）：启动 15s 后若\"从未备份或距上次 > backup_interval_days\"立即补跑一次",
            "麒麟/离线数据目录收口：Linux/打包态数据根改为 BUMOFU_DATA_DIR → XDG_DATA_HOME/bumofu →",
            "Windows 构建脚本：新增 scripts/build/sync-frontend.ps1（robocopy 等价同步，替代失效的 bash 脚本）与",
            "安装包瘦身：assistance-backend.spec 瓦片收集改为构建开关 INCLUDE_MAP_TILES=1（默认关）；Electron 版由",
            "/api/v1/map/config 的 map_type：\"gaode\" → \"vector\"（前端零消费方）。",
            "通知偏好 3 个端点响应追加 emailChannel: \"unavailable_offline\"（只增不删）。",
            "httpx 登记运行时必需依赖（启动期硬依赖，此前缺失即 ImportError 且自检不覆盖）。",
            "scripts/check_doc_numbers.py 输出改 UTF-8（修复 Windows GBK 控制台下 ✓ 触发 UnicodeEncodeError 假红）。",
            "POST /api/v1/system/admin/restore?filename= 旧端点直接 shutil.copy2 覆盖 DB，绕过维护窗口/schema 校验/",
        ],
    },
    {
        "version": "1.18.1",
        "date": "2026-10-24",
        "description": "登录门面重构 / 三层对齐门禁 / 门禁真绿复验",
        "features": [
            "登录页公开配置扩展：GET /api/v1/auth/public-config 新增 lockout_minutes / max_failed_attempts",
            "三层对齐门禁 scripts/check_stack_alignment.py + CI job + 自测",
            "迁移 r42_align_stack_columns_001：tea_plantations / cactus_fruit_plots 的",
            "覆盖率回归测试 tests/unit/test_coverage_restore_after_merge.py（12 例）：补 repr 可安全输出、",
            "登录页重构（frontend/src/views/auth/LoginEnhanced.vue）：",
            "authStore.login 错误传播修正：原先只读 err.response.data.message，而 FastAPI 返回 detail ——",
            "MessageCenter 契约对齐：MessageListResponse 按后端实际改为 total_pages（无 unread_count），",
            "system/backup.py：去掉 BackupKeyMismatchError 分支里不可达的 if file_path:（该分支只可能由",
            "文档与 PPT 同步至 v1.18.1（PPT 新增「登录门面与门禁真绿复验」一页，全部数字按实测刷新）。",
            "注册入口死链：SELF_REGISTER_MODE 默认 off，但登录页无条件显示\"注册账户\"，",
            "100% 覆盖率门禁静默失效：backend/.coveragerc 在工作区被误删，fail_under=100 不再生效 ——",
            "行业模型与库列名漂移：r42 迁移注释写明\"模型列名改为 supported_village_id\"，但 app/models/industry.py",
        ],
    },
    {
        "version": "1.18.2",
        "date": "2026-10-25",
        "description": "瓦片底图“加载失败已切回矢量”根治（边缘 404 不再整体回退）",
        "features": [
            "422 校验错误中文化 + 不再回显 input（后端根因）：此前只注册了 pydantic 的",
            "前端统一出口保证永不显示技术原文（src/utils/getErrorMessage.ts 重写）：新增",
            "拦截器与视图层对齐：src/api/request.ts 的 _extractServerMessage / _buildUserMessage",
            "新增门禁 scripts/check_error_message_leaks.py（CI static-analysis）：扫描",
            "backend/tests/unit/test_validation_errors_i18n.py（35 项）：字段标签、类型模板、",
            "frontend/tests/unit/utils/errorMessageContract.test.ts（37 项）：10 个状态码的",
            "前端不再因边缘 404 整体回退：TileLayer 增加 bounds（只在覆盖范围内请求）+ errorTileUrl",
            "后端诊断字段：GET /api/v1/map/tile-info 新增 bbox（MANIFEST region.bbox → bbox → 贵州兜底）、",
            "回退提示带诊断：提示追加 available/tileCount/source/reason，现场可区分“没装瓦片”与“真故障”。",
            "前端 TDD：先红（组件 11 / 工具 8 失败）→ 实现 → 绿；mapTiles/RasterTileLayer/MapTileManager/api 等",
            "后端：新增 test_map_tile_info_diagnostics.py（11 项）+ 既有 map/tiles 套件合计 216 passed；",
            "打包后运行期：/map/tile-info 含 bbox/source/reason；覆盖区内瓦片 200、区外 404（前端透明处理、不回退）。",
        ],
    },
    {
        "version": "1.18.3",
        "date": "2026-10-25",
        "description": "多包瓦片覆盖并集 / 旧恢复端点下线 / 跨密钥恢复 UI / 签名门禁",
        "features": [
            "多包叠加导入后覆盖范围被最后导入包限制（P0）：MANIFEST.json 是\"最后导入包\"，",
            "旧管理员恢复端点下线（安全）：POST /api/v1/system/admin/restore 改为 410 Gone，",
            "跨密钥恢复有 UI 入口：前端恢复遇 409 且 detail 含\"密钥\"→ 展示危险勾选 +",
            "CI 签名门禁：build-windows.yml 新增 Verify installer signature —— 配置 CSC_LINK",
            "文档：API 文档标注该端点停用；瓦片指南补\"边缘 404/诊断字段\"排障；代码签名文档补 CI 接线；",
            "后端：新增 test_tile_info_coverage_bbox.py（多包并集/实测优先/非法值回退）+ 停用端点用例，",
            "前端：BackupManagementKeyMismatch.test.ts（17）+ backup.test.ts（13）30 passed；",
            "本地安装包 MRRS-Setup-1.18.3-x64.exe 打包后实测：/map/tile-info.bbox 为实测并集，",
            "electron 外壳单测长期不在版本库里：.gitignore 的 *.test.js 通配只给",
            "electron 单测此前无人执行（孤儿测试）：package.json 新增 test:electron",
            "发布门禁等待预算与实测压线：build-arm64.yml 两处 check_release_gate.py --timeout-minutes",
            "接线守卫 electron/tests/ci-wiring.test.js（4 例）：断言 test:electron 存在、",
        ],
    },
    {
        "version": "1.18.4",
        "date": "2026-10-25",
        "description": "瓦片覆盖 bbox 取最细 zoom（修正 1.18.3 概览瓦片撑大 maxBounds）",
        "features": [
            "scan_tiles_dir 的覆盖范围改为按 zoom 分组累计、取最细 zoom 的实测并集：",
            "test_tile_info_coverage_bbox.py 等 163 项相关测试全绿；flake8 0。",
            "v1.18.3 的 tag 已推送并触发过 CI；v1.18.4 为最终交付版本（1.18.3 的 bbox 取值偏大，属体验缺陷非功能故障）。",
        ],
    },
    {
        "version": "1.18.5",
        "date": "2026-10-25",
        "description": "修正 1.18.4 的 bbox 补丁未生效（真正取最细 zoom）",
        "features": [
            "scan_tiles_dir 改为按 zoom 分组累计（每个 z 目录单独合并 _scan_x_dir 的 bounds，",
            "实测（resources/map-tiles，5,623 张 z5–12）：",
            "多包叠加语义不变：同一 zoom 内仍为各包并集（有 22 项 bbox 测试覆盖，含贵阳+遵义并集用例）。",
            "test_tile_info_coverage_bbox.py / test_map_tile_info_diagnostics.py /",
            "真机（打包后端）复验：tile-info.bbox 为上述辖区量级；覆盖区内瓦片 200、区外 404。",
            "composables/useFormDraft.ts（表单草稿自动保存）：本次改动中最能直接省人力的一个 ——",
            "utils/parsePastedTable.ts（Excel 粘贴解析）：现场数据多数先在 Excel/WPS 整理好，",
            "测试：useFormDraft.test.ts 23 例、parsePastedTable.test.ts 17 例；",
            "说明：本批交付的是可复用基座；接入具体表单页（并配 useDirtyGuard 铺开）在下一批完成 ——",
            "views/policies/Edit.vue 接入 ③：草稿键按模式隔离（policies:edit:new /",
            "离开拦截接线：useDirtyGuard(isDirty) —— 此前全仓只有 projects/Edit.vue 接入，",
            "测试：Edit.test.ts 37 → 42 例（新增草稿恢复/忽略/守卫注册/卸载落盘/提交清草稿），",
        ],
    },
    {
        "version": "1.18.6",
        "date": "2026-10-25",
        "description": "仓库卫生与门禁加固（scripts 纳入 flake8、全仓 flake8 归零）",
        "features": [
            "backend/app/ flake8 归零（79 → 0）：78 处 E302/E305（app/models/ 14 个文件",
            "scripts/ flake8 归零（19 → 0）：未使用导入 4 处（run_backend_tests_segmented.py",
            "frontend/package.json 补 engines：node: ^20.19.0 || >=22.12.0",
            "密码哈希改 bcrypt 直连（app/core/security.py）：passlib 1.7.4 在 bcrypt 5.x 下",
            "MANIFEST bbox 只校验长度不校验数值（api/v1/map.py）：[\"x\",1,2,3] 这类非法 bbox",
            "消除唯一 skip（tests/unit/test_offline_log_path_w18.py）：打包态日志路径改写回归",
            "BaseChart 主题重建入口显式暴露（components/common/BaseChart.vue）：",
            "覆盖率门禁两处失效根治（scripts/run_backend_tests_segmented.py）：",
            "复验口径：后端 12 段全 PASS / 0 failed / 0 skipped，对累积数据 coverage report",
            "⑥ 分页上限改造引入的 6 处回归（本版修复；12 段复验时 seg10/seg12 各挂 1/5 例）：",
            "CI 增补 scripts/ flake8 步骤（.github/workflows/pr-checks.yml 的 lint 作业）：",
            "版本 1.18.5 → 1.18.6，node scripts/sync-version.js --write 同步 22 处目标（14 个文件已更新）。",
        ],
    },
    {
        "version": "1.18.7",
        "date": "2026-10-25",
        "description": "录入效率包收口 / 数据同步胶囊 / OCR 建议 / 视觉回归 44 页 / 发布工具加固",
        "features": [
            "批量粘贴弹窗 BulkPasteDialog（③）：粘贴 → 预览 → 逐行校验 → 确认，四步可视化；",
            "消费帮扶台账接入批量粘贴（③ 收口）：逐行校验 + 串行新增 + 失败行号原样回传，不整批回滚。",
            "草稿自动保存扩到 4 个页面（③）：学校编辑、组织编辑等页面接入 useFormDraft +",
            "顶栏数据同步状态胶囊 + 台账抽屉（④）：只读 /data-sync/logs，不新增接口；",
            "经费凭证 OCR 字段级建议（⑤）：接入转账凭证新建对话框，识别金额/日期给出建议并由人工确认",
            "VirtualList 虚拟滚动基座（⑥）：窗口算术抽成纯函数（22 例测试，双文件 100% 覆盖）。",
            "usePageSize 每页条数偏好（⑥）：偏好记忆 + 归一化，项目列表接入。",
            "视觉回归扩到 44 页（⑨）：30 个 console tab + 4 个核心表单，DOM 结构快照不比对像素。",
            "E2E 新增村庄表单断言：顶栏同步抽屉的隐藏元素污染 .first()，改用 :visible。",
            "Nightly 分组漏根目录：补跑 tests 根目录，permission_packs 覆盖率 38% → 100%。",
            "release_tag 工具链：输出改 UTF-8；工作区脏时提供 --allow-dirty 逃生口",
            "新增 PR/Nightly 覆盖率一致性门禁：防止两套口径长期漂移。",
        ],
    },
    {
        "version": "1.18.8",
        "date": "2026-10-26",
        "description": "全面收口：逐一代码体检 + 项目整理 −1880 文件 + 分段覆盖率门禁修复",
        "features": [
            "分段覆盖率门禁的 coverage combine 一直在失败，且失败信息被吞掉（scripts/run_backend_tests_segmented.py）：",
            "OrganizationService.get_ancestors() 在 path 为 NULL 时抛异常，令数据上报创建直接 500",
            "删除 .scratch/tiles-import-test/（1423 个文件）：瓦片导入测试的中间产物，",
            "删除 .qoder/（456 个文件，含 1.8 MB repowiki-metadata.json）：AI 工具生成的仓库知识库缓存。",
            "删除 .scratch/r34-final/帮扶管理信息系统介绍-原始备份.pptx（1.0 MB）：与 docs/ 正式版重复且零引用。",
            "补 .gitignore：.scratch/tmp/、.qoder/、.reasonix/、.zcode/、deliverables/releases/、",
            "未动（有引用/交付需要）：deliverables/（README/AGENTS/CHANGELOG 引用其中报告）、",
            "backend/version.json：版本 1.18.8、release_date 2026-10-26、描述与 features 全量重写为收口结论。",
            "系统介绍 PPT：版本页脚与\"数据来源\"日期同步至 v1.18.8 / 2026-10-26，保持 56 页与既有版式",
            "README / CLAUDE.md / AGENTS.md / 《项目文件结构说明.md》文件数与实测对齐。",
        ],
    },
    {
        "version": "1.18.9",
        "date": "2026-10-26",
        "description": "应用内更新日志接入唯一账本 + 发布说明一致性门禁（根治版本说明漂移）",
        "features": [
            "应用内更新日志长期不更新：update_log_service.py 里的 240 行硬编码历史被删除，",
            "同一天多个版本的顺序是随机的：created_at 只按日期写入（1.18.2–1.18.7 全是 2026-10-25），",
            "scripts/check_update_log.py 发布说明一致性门禁（已接入 pr-checks 的 static-analysis 与",
            "单元测试 tests/unit/test_update_log_sync.py：断言生成文件与 CHANGELOG 一致、",
            "backend/version.json 的 description 改为与 CHANGELOG 标题严格一致（原先为手工改写版本，",
            (
                "check_update_log.py / check_changelog.py / check_doc_numbers.py / sync-version.js --check 全部 e"
                "xit 0。"
            ),
            "更新日志相关 29 例测试通过，app/services/update_log_service.py 行+分支覆盖率 100%（92 语句 / 26 分支）。",
            "端到端实测：全新库启动后 GET /api/v1/system/update-logs 返回 96 条，首条 1.18.9、",
        ],
    },
]
