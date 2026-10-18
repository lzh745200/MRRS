# W22 契约：功能大迭代（v1.14.0）

> 本文件是本批所有实施者的唯一契约。字段/路径/表名/页面/路由/菜单 key 以本文为准；
> 偏离前必须先通知 Lead 并同步修改本文。

## 0. 目标（用户需求 → 实现项映射）

| # | 需求 | 实现 |
|---|---|---|
| 1 | 去除驻村工作台 | 删除 `views/ruralWorks/checkin/`、路由 `/rural-works/checkin`、菜单 key `checkin`（无后端模块） |
| 2 | 一户一档 + 风险预警 + 走访挂户 + 汇总回填 + 台账导出 | 新表 `households` / `household_members` / `household_risk_records`；`visit_records.household_id`；API `/households/*`；前端 `views/households/` |
| 3 | 影像库（归档/对比图/EXIF 归类） | 新表 `photo_archives`；API `/media/photos/*`（含对比图生成）；前端 `views/media/PhotoArchive.vue` |
| 4 | 汇报大屏退出按钮 | `BigScreen.vue` 顶部新增「退出大屏」（回工作台） |
| 5 | 数据上报链路（下级上报导出→上级导入接收查看） | 端到端集成测试 + 修复；不改协议 |
| 6 | 删除 Village/Villager 遗留表 | 删除 `models/village.py`、`api/v1/villages.py`；`rural_works/rural_tasks.village_id` → `supported_village_id`（数据回填后删列）；Alembic drop `villagers`/`villages`/`industries` |
| 7 | 国际化/邮件不需要；字段翻译集成到校验规则 | 删除 `views/system/I18nManagement.vue`、`EmailSettings.vue`、路由 `/system/i18n`、`/system/email`、菜单 key `i18n`（后端无独立模块）；字段中文标签映射移入数据校验页的「字段说明」 |
| 8 | 数据校验与校验规则重复 → 合并并优化 | 单页 `views/dataVerify/Index.vue`（Tabs：校验执行/规则管理/字段说明），删除独立 `/data-verify/rules` 路由（redirect 到 `?tab=rules`），菜单只留 `data-verify` |
| 9 | 报表模板增强（任意字段组合、多格式、导出打印） | 后端新增通用导出端点；前端 `reportTemplates/Index.vue` 增强：字段勾选→格式（Excel/CSV/Word/PDF）→导出→打印 |
| 10 | 数据概览清除已迁移提示 | `views/dataManagement/Index.vue` 删除迁移提示区块 |
| 11 | 舆情监测 → 消费帮扶 | 删除 sentiment 后端（api/models/services/表）与前端页；新增 `consumption_records` 表 + `/consumption/*` + `views/consumption/List.vue`；路由 `/sentiment` redirect `/consumption`；菜单 key `sentiment`→`consumption` |
| 12 | 7 板块名称放大 + 折叠展开 | `DefaultLayoutSafe.vue`：板块标题字号加大、默认折叠、点击标题展开/收起（记住状态 localStorage） |
| 13 | 经费凭证 OCR | `services/ocr_service.py`（引擎见 §7）+ `POST /funds/ocr-voucher`；前端经费详情凭证处「OCR 识别」按钮回填金额/日期 |

## 1. 数据模型（新表/改造/删除）

所有新表包含 `organization_id`（FK organizations SET NULL）、`created_by`、`is_active`、`created_at`/`updated_at`（与全库一致）。

### 1.1 households（一户一档）
- `supported_village_id` FK supported_villages CASCADE，必填
- `household_code` String(64) 户编号（村内唯一，可空）
- `household_name` String(64) 户主姓名，必填
- `address` String(255)
- `household_type` String(20)：`general` 一般户 / `poverty` 脱贫户 / `monitor` 监测户（默认 general）
- `risk_type` String(32)：`none` / `income_drop` 收入骤减 / `illness` 大病 / `housing` 住房 / `sudden` 突发困难 / `multiple`
- `risk_level` String(10)：`low` / `medium` / `high`（默认 low）
- `helper_name` String(64) 帮扶责任人
- `helper_phone` EncryptedText(64)（PII，禁止裸 SQL）
- `annual_income` Numeric(14,2)（元）
- `migrant_workers` Integer 务工人数
- `has_serious_illness` Boolean 大病
- `housing_safe` Boolean 住房安全
- `last_visit_date` Date 最近走访日期（走访挂户时回写）
- `monitoring_note` Text

### 1.2 household_members（家庭成员）
- `household_id` FK households CASCADE，必填
- `name` String(64) 必填；`relation` String(32) 与户主关系
- `id_card` EncryptedText(64)、`gender` String(10)、`birth_year` Integer
- `education` String(32)、`health_status` String(32)（健康/慢性病/大病/残疾）
- `employment_status` String(32)（务工/务农/学生/无劳动能力）
- `income` Numeric(14,2) 个人年收入（元）
- `is_special_support` Boolean 是否兜底保障对象

### 1.3 household_risk_records（风险/预警记录）
- `household_id` FK CASCADE；`risk_type` String(32)；`risk_level` String(10)
- `reason` String(500)；`detected_at` UtcDateTime；`status` String(10) `open`/`closed`
- `closed_at` UtcDateTime；`closed_note` String(500)

预警规则（服务层，供前端展示）：
- 收入下降：本年度 `annual_income` 低于上一年度同类记录（household 只有当前值 → 用 `household_income_history`？**简化**：以 `household_risk_records` 中人工登记/自动检测记录为准；自动规则基于 `last_visit_date` 与 `annual_income` 与村年度数据不可比。本批实现两条确定性规则：
  1) **连续未走访**：`last_visit_date` 为空或距今天 > 90 天且 household_type != general → medium；
  2) **突发困难/大病/住房不安全**：`has_serious_illness=true` 或 `housing_safe=false` 或 `risk_type in (sudden, multiple)` → high。
  「收入下降」以 `household_risk_records` 人工登记类型 `income_drop` 呈现（前端可一键登记）。
- 预警列表 API 返回规则命中清单（不落库），前端展示并可一键登记为 risk record。

### 1.4 photo_archives（影像库）
- `file_url` String(500) 必填（复用 `/files/upload` 返回的 URL）
- `file_name` String(255)；`file_size` Integer；`mime_type` String(100)
- `village_id` FK supported_villages SET NULL、`school_id` FK schools SET NULL、`project_id` FK projects SET NULL（三选一或空）
- `tag` String(50)（可选标签）；`spot_key` String(100)（拍摄点标识，用于多期对比；默认取 GPS 量化串或用户输入）
- `taken_at` UtcDateTime（优先 EXIF DateTimeOriginal）；`gps_lat`/`gps_lng` Numeric(10,6)
- `uploader_id` Integer；`shot_source` String(20)（`exif`/`manual`）

### 1.5 consumption_records（消费帮扶台账）
- `supported_village_id` FK supported_villages SET NULL（可空）
- `category` String(32)：`agriculture` 农产品 / `livestock` 畜禽 / `handicraft` 手工 / `other`
- `item_name` String(200) 必填；`quantity` Numeric(14,2)；`unit` String(20)；`amount` Numeric(14,2)（元，必填）
- `buyer` String(200) 采购方（单位）；`seller` String(200) 供货方（农户/合作社）；`seller_type` String(20)：`farmer`/`cooperative`/`enterprise`
- `year` Integer 必填；`record_date` Date；`voucher_url` String(500)
- `remarks` Text

### 1.6 改造
- `visit_records.household_id` Integer FK households SET NULL，可空（走访挂户；填了则回写 `households.last_visit_date`）
- `rural_works` / `rural_tasks`：新增 `supported_village_id` FK supported_villages SET NULL；回填（按 `villages.name` 与 `supported_villages.village_name` 同组织匹配）；删除 `village_id` 列与 `Village` relationship，改 `relationship("SupportedVillage")` 或去掉 relationship（简化：去掉 relationship，保留 id 列，前端用村名通过 id 查询）。
- 删除：`villages`、`villagers`、`industries`、`sentiment_news` 表（Alembic drop）。

### 1.7 Alembic
新增单迁移 `backend/alembic/versions/w22_household_media_consumption.py`：
- 建 4 张新表 + visit_records.household_id + rural 两表新列/回填/删旧列
- drop 4 张旧表（注意 SQLite ALTER 限制：drop column 需 batch_alter_table）
- downgrade 可逆（重建旧表最小结构或 raise；要求 CI `check_migrations.py` 单 head 通过、`upgrade_rehearsal` 通过）

## 2. 后端 API 契约

### /households（登录用户，数据域沿用 get_org_scope/filter_by_org_ids）
- `GET /households?page&page_size&village_id&risk_level&household_type&keyword` → `ok_list`；items 含 `village_name`、`member_count`、`risk_alerts`（规则命中）
- `POST /households`、`GET/PUT/DELETE /households/{id}`（软删 is_active=false，管理员 include_deleted 复用 `enforce_admin_include_deleted`）
- `GET /households/{id}/members`、`POST/PUT/DELETE /households/{id}/members/{member_id}`
- `GET /households/alerts?level` → 预警清单（规则命中 + open 风险记录）
- `POST /households/{id}/risk-records`、`PUT /households/risk-records/{id}/close`
- `POST /households/rollup?village_id&year` → 按户汇总回填 `VillagePopulation`（总户数/总人口/脱贫户数/监测户数；只写当年度，null year 取当前年；返回写回字段摘要）
- `GET /households/export?format=xlsx|csv&village_id&risk_level` → 文件下载（导出当前筛选台账，含成员数/风险）

### /media/photos
- `GET /media/photos?page&page_size&village_id&school_id&project_id&tag&date_from&date_to` → ok_list
- `POST /media/photos`（file_url 等注册）→ 创建归档记录；后端读 EXIF（Pillow）补 taken_at/gps，GPS 就近匹配村（半径 5km，按 supported_villages.latitude/longitude）
- `PUT/DELETE /media/photos/{id}`（软删）
- `GET /media/photos/compare?spot_key=` → `[{id,file_url,taken_at}]`（同拍摄点多期）
- `POST /media/photos/compare-image`（body: ids[]）→ 返回 PNG（Pillow 左右拼接 + 日期标注）；`GET` 版本便于下载

### /consumption
- `GET /consumption?page&page_size&year&category&village_id&keyword` → ok_list（含 village_name）
- `GET /consumption/statistics?year` → `{total_amount, record_count, by_category:[...], by_village:[...]}`
- `POST/PUT/DELETE /consumption/{id}`（软删）
- `GET /consumption/export?format=xlsx|csv&year&category` → 下载

### /reports（报表模板增强）
- 保留现有 `/report-templates/*`
- 新增 `POST /report-templates/{id}/export?format=xlsx|csv|docx|pdf&year`（按模板字段组合生成；复用 report_export_service 的 Word/PDF 与 openpyxl/csv）
- `GET /report-templates/{id}/print-data?year` → 前端打印用 JSON（复用导出数据组装）

### /funds/ocr-voucher
- `POST /funds/ocr-voucher`（multipart image）→ `{text, amount, date, confidence, engine}`；识别金额（正则：￥/元/小写数字）与日期（YYYY-MM-DD/YYYY年M月D日）
- 引擎不可用 → 503 `{"message":"OCR 引擎不可用..."}`（前端提示手工录入，不阻断）

### 其他
- 删除 `/api/v1/villages` 路由（前端无消费方，仅 offlineMock；保留前端 `/villages` redirect）
- 删除 `/api/v1/sentiment/*` 与 sentiment models/services
- 数据上报链路：不新增接口，补集成测试验证 `/data-packages/report`（下级生成上报包）→ `/data-packages/receive`/`/import`（上级导入）→ 列表/数据查询可见

## 3. 前端页面与路由/菜单

| 页面 | 路由 | 菜单 key | 板块 |
|---|---|---|---|
| 一户一档列表/详情 | `/households`、`/households/:id` | `households` | 帮扶业务（村之后） |
| 影像库 | `/media` | `media-library` | 分析汇报（大屏之后） |
| 消费帮扶 | `/consumption`（旧 `/sentiment` redirect） | `consumption` | 帮扶业务（政策之后） |
| 数据校验（合并） | `/data-verify`（`?tab=rules`；旧 `/data-verify/rules` redirect） | `data-verify` | 数据管理 |
| 报表模板（增强） | `/report/templates` | `report-templates` | 分析汇报 |
| 大屏退出 | 无新路由 | — | — |
| 删除 | `/rural-works/checkin`、`/system/i18n`、`/system/email` | 删 `checkin`/`i18n` | — |

- 菜单：Lead 统一改 `backend/app/api/v1/menus.py`（v2 sections/console tabs）与 `frontend/src/router/index.ts`；队友不要改这两处，只在汇报中给需求。
- 7 板块折叠：`DefaultLayoutSafe.vue` 板块标题放大（16px→18px/加粗），默认折叠（localStorage `nav:collapsed-sections` 记录展开集合），点击切换；console/group 子项保持原逻辑。
- 大屏退出：`BigScreen.vue` 头部新增按钮 `退出大屏` → `pushSafe('/dashboard')`；若全屏则先退出全屏。
- 数据概览：删除 `dataManagement/Index.vue` 内「已迁移」提示卡片/文案。
- 校验页优化：Tabs（校验执行/规则管理/字段说明）；校验执行 = 选择模块+范围 → 一键校验 → 问题列表（可点行跳转/行内编辑或用现有编辑入口）；字段说明 = 原 i18n 字段中文映射表（只读）。

## 4. OCR 方案
- 首选 `rapidocr-onnxruntime`（离线、CPU、中英文；已在本机 pip 安装验证）。服务封装 `services/ocr_service.py`：懒加载引擎（首次调用初始化，失败缓存错误）、图片字节→numpy/PIL→识别→文本/金额/日期解析；提供 `available()`。
- 依赖登记：`backend/requirements.txt` 增加 `rapidocr-onnxruntime`（版本钉住实测可用版本）；PyInstaller spec 增加 hiddenimports/collect（onnxruntime、rapidocr 模型文件）——由 Lead 处理打包并验证安装包内可识别。
- 若 CI/打包环境拉取失败：以 `requirements-ocr.txt` 可选依赖 + 运行时 `available()` 降级（API 返回 503、前端提示手工录入），但本机发布包必须内置可用。

## 5. 测试与门禁（硬约束）
- 后端：新模块/改动模块 `--cov=<module> --cov-branch` 100%；新增 API/服务测试；Alembic 迁移测试（upgrade head + 回填断言 + downgrade）；PII 列必须走 ORM（EncryptedText），禁止裸 SQL 写。
- 前端：新增/改动的 `.vue`/`.ts` 四指标 100%；**单一执行者规程**（同一 .vue 只允许一个测试文件真实执行；新增页面各自专属测试；layout/bigscreen 由既有唯一执行者测试补充）。
- 不得新增硬编码色值（用 var(--token)）；不得新增裸 `db.commit()`（用 safe_commit）；软删模型查询带 is_active；数据域统一 get_org_scope/filter_by_org_ids。
- 全量门禁（Lead 最终跑）：后端全量+覆盖率 100%、前端全量+12 组 100%、flake8/bandit/vue-tsc/eslint/17 项静态门禁、菜单对齐 A~E、版本一致性。

## 6. 文件权属（并行写作用域，禁止越界）

| 责任方 | 允许修改 |
|---|---|
| backend-household | `backend/app/models/household.py`(新)、`backend/app/schemas/household.py`(新)、`backend/app/services/household_service.py`(新)、`backend/app/api/v1/households.py`(新)、`backend/tests/unit/test_households*.py` |
| backend-media | `backend/app/models/media.py`(新 photo_archives)、`backend/app/schemas/media.py`(新)、`backend/app/services/media_service.py`(新，含 EXIF/GPS/对比图)、`backend/app/services/ocr_service.py`(新)、`backend/app/api/v1/media.py`(新)、`backend/app/api/v1/funds.py`（仅追加 OCR 端点）、`backend/tests/unit/test_media*.py`、`test_ocr*.py` |
| backend-core | `backend/app/models/consumption.py`(新)、`schemas/consumption.py`、`services/consumption_service.py`、`api/v1/consumption.py`、删除 `api/v1/sentiment.py`/`models/sentiment.py`/`services/sentiment/`、删除 `api/v1/villages.py`/`models/village.py`、改 `models/rural_work.py`/`rural_task.py`（FK/relationship）、`api/v1/report_templates.py`（追加导出端点）、`services/report_export_service.py`（如需）、`backend/tests/unit/test_consumption*.py`、`test_rural_work_village_migration*.py`、`test_report_template_export*.py`、`tests/integration/test_data_report_roundtrip*.py`、删除/更新 sentiment/villager 相关既有测试 |
| frontend-household | `frontend/src/api/households.ts`(新)、`views/households/**`(新)、`tests/unit/views/households/**`、`tests/unit/api/households.test.ts` |
| frontend-media-consumption | `frontend/src/api/media.ts`(新)、`api/consumption.ts`(新)、`views/media/**`(新)、`views/consumption/**`(新)、删除 `views/sentiment/`、`api/sentiment.ts`、对应测试（新增/删除） |
| frontend-cleanup | `views/ruralWorks/checkin/`(删除)、`views/system/I18nManagement.vue`(删除)、`views/system/EmailSettings.vue`(删除)、`views/dataVerify/Index.vue`(新，合并页；删除/合并 RulesManagement.vue)、`views/reportTemplates/Index.vue`(增强)、`views/dataManagement/Index.vue`(去提示)、`views/bigscreen/BigScreen.vue`(退出按钮)、`layouts/DefaultLayoutSafe.vue`(折叠放大)、对应测试 |
| Lead | `backend/app/models/__init__.py`、`backend/alembic/versions/w22_*.py`、`backend/app/api/v1/menus.py`、`frontend/src/router/index.ts`、`backend/assistance-backend.spec`、`backend/requirements*.txt`、版本/CHANGELOG/文档/PPT、最终集成与门禁 |

## 7. 版本
目标 **1.14.0**。完成后：全量验证 → 文档/PPT/结构说明 → 删除无用文件夹 → 提交推送 → tag → 构建安装包 → 验证 Release。
