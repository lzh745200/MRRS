# W22 工单：功能大迭代（v1.14.0）

> 状态：实现完成（代码冻结），全量门禁与构建/发布进行中。
> 契约：`000-contract.md`（本批唯一实现契约）。

## 1. 用户需求 → 交付映射（13 项）

| # | 需求 | 交付 | 状态 |
|---|---|---|---|
| 1 | 去除驻村工作台 | 删除 `views/ruralWorks/checkin/`、路由 `/rural-works/checkin`；菜单 key `checkin` 转 legacy（无导航出口） | 完成 |
| 2 | 一户一档（成员/帮扶责任人/风险类型/收入·务工·大病·住房监测指标、风险等级与预警、走访挂户、按村汇总回填年度人口、台账导出） | 新表 `households`/`household_members`/`household_risk_records`；API `/households/*`；页面 `/households`、`/households/:id`；预警规则（>90 天未走访、大病/住房不安全/突发困难）；`visit_records.household_id` + 回写 `last_visit_date`；`POST /households/rollup` 幂等回填 `village_population`；导出 xlsx/csv | 完成 |
| 3 | 影像库（村/校/项目/时间/标签归档、多期照片自动配对左右对比图、手机照片 EXIF 时间/GPS 自动归类到村） | 新表 `photo_archives`；`/media/photos/*`（EXIF 时间 + GPS 就近匹配村 ≤5km、spot_key 多期、对比图 PNG GET/POST 双入口）；页面 `/media` | 完成 |
| 4 | 汇报大屏退出功能 | `BigScreen.vue` 头部「退出大屏」→ 退全屏 + 回工作台 | 完成 |
| 5 | 验证下级录入→上报导出→上级导入接收查看 | 集成测试 `tests/integration/test_data_report_roundtrip.py`；发现并修复枚举名/值断点（`data_package_service._export_data_type`） | 完成 |
| 6 | 删除 Village/Villager 遗留表 | Alembic `w22_household_media_consumption_001` drop `villages`/`villagers`/`industries`/`sentiment_news`；4 张引用表的 `village_id` 迁移为 `supported_village_id`（含 tea_plantations/cactus_fruit_plots）并回填；删除 `models/village.py`、`api/v1/villages.py` | 完成 |
| 7 | 国际化/邮件不需要，字段翻译集成到校验规则 | 删除 `I18nManagement.vue`/`EmailSettings.vue` 及路由；菜单 key `i18n`/`email` 转 legacy；数据校验页「字段说明」Tab 提供字段中文标签（`/validation/fields`） | 完成 |
| 8 | 数据校验与校验规则去重并优化（小白可用） | 单页 `views/dataVerify/Index.vue` 三 Tab（校验执行/规则管理/字段说明）+ `RulesPanel.vue`；旧 `/data-verify/rules` redirect；菜单只保留 `data-verify` | 完成 |
| 9 | 报表模板增强（任意信息组合成规范报表、格式多样、导出打印） | 后端 `POST /report-templates/{id}/export?format=xlsx|csv|docx|pdf` + `GET …/print-data`；前端字段组合→导出→打印（`ReportOutputDialog.vue`） | 完成 |
| 10 | 数据概览清除已迁移提示 | `dataManagement/Index.vue` 删除全部「已迁移/已统一/已整合」提示文案（保留功能入口） | 完成 |
| 11 | 舆情监测改为消费帮扶 | 新表 `consumption_records` + `/consumption/*` + 页面 `/consumption`；删除 sentiment 后端（api/model/services）与前端页；`/sentiment` redirect；菜单 key `sentiment`→`consumption` | 完成 |
| 12 | 7 板块名称放大 + 折叠展开 | `DefaultLayoutSafe.vue`：板块标题 18px 加粗、默认折叠、点击展开/收起、localStorage `nav:expanded-sections` | 完成 |
| 13 | 经费凭证 OCR | `ocr_service.py`（rapidocr-onnxruntime 1.4.4 离线）+ `POST /funds/ocr-voucher`（金额/日期解析、503 降级）；前端经费凭证处 OCR 识别 | 完成 |

## 2. 交付文件概览

### 后端新增
- `models/household.py`、`schemas/household.py`、`services/household_service.py`、`api/v1/households.py`
- `models/media.py`、`schemas/media.py`、`services/media_service.py`、`api/v1/media.py`
- `models/consumption.py`、`schemas/consumption.py`、`services/consumption_service.py`、`api/v1/consumption.py`
- `services/ocr_service.py`
- `alembic/versions/w22_household_media_consumption_001.py`

### 后端修改
- `models/__init__.py`（新模型注册、删 Village/SentimentNews）、`api/v1/__init__.py`（模块注册）
- `models/rural_work.py`/`rural_task.py`/`industry.py`（village FK → supported_village）
- `models/pairing.py` + `api/v1/pairing.py`（走访挂户 + last_visit_date 回写）
- `api/v1/report_templates.py`（导出/打印端点）、`services/data_package_service.py`（枚举导出修复）
- `api/v1/funds.py`（OCR 端点）、`services/rural_work_service.py`、`schemas/rural_task.py`
- `requirements.txt`（rapidocr-onnxruntime==1.4.4）、`core/required_packages.py`（可选依赖登记）
- `assistance-backend.spec`（rapidocr/onnxruntime 数据与动态库收集）
- `docker/Dockerfile.kylin-standalone`（ARM64 过滤 OCR 依赖）

### 前端新增
- `api/households.ts`、`views/households/List.vue`、`views/households/Detail.vue`
- `api/media.ts`、`views/media/PhotoArchive.vue`
- `api/consumption.ts`、`views/consumption/List.vue`
- `views/dataVerify/Index.vue`、`views/dataVerify/components/RulesPanel.vue`
- `views/reportTemplates/components/ReportOutputDialog.vue`

### 前端修改/删除
- `router/index.ts`、`menus.py`（Lead 统一）
- `layouts/DefaultLayoutSafe.vue`（折叠放大）、`views/bigscreen/BigScreen.vue`（退出）、`views/reportTemplates/Index.vue`（导出/打印入口）、`views/dataManagement/Index.vue`（去提示）
- 删除：`views/ruralWorks/checkin/`、`views/system/I18nManagement.vue`、`views/system/EmailSettings.vue`、`views/dataVerify/RulesManagement.vue`、`views/sentiment/`、`api/sentiment.ts`

## 3. 验收 checklist（发布门禁）

- [x] 后端全量 pytest 13,710 passed / 1 skipped + 语句/分支覆盖率 100%（44,423 stmts / 10,872 branches）
- [x] 前端全量 vitest 321 文件 / 6,748 用例 + 12 组 glob 四指标 100%
- [ ] flake8（app/）/ bandit -ll / vue-tsc --noEmit / eslint src --max-warnings=0 全 0
- [ ] 17 项静态门禁 PASS（含菜单对齐 A~E、硬编码色、安全审计、Alembic 单 head、pragma、版本一致性）
- [ ] Alembic：upgrade→downgrade→upgrade 通过（新表/删表/列迁移断言）
- [ ] OCR：真实图片识别金额/日期；安装包内引擎可用（PyInstaller 打包后验证）
- [ ] 数据上报链路端到端测试通过（含幂等）
- [ ] 安装包构建 + 自包含冒烟（解包后端 /health + 运行库断言）
- [ ] 文档/PPT/项目文件结构说明更新；无用文件清理
- [ ] 提交 GitHub + tag v1.14.0 + Actions 构建成功

## 4. 决策与偏差记录

1. **旧菜单 key 处理**：`checkin`/`i18n`/`email`/`validation-rules`/`sentiment` 不删除定义，转为 `section=None + legacy=True`（无导航出口），保证历史权限包与 `allowed_menus` 兼容；`check_menu_alignment.py` 规则 C 对 legacy 豁免。
2. **tea_plantations / cactus_fruit_plots 保留**：只把 `village_id` 迁移为 `supported_village_id`（原表不删，属产业监测数据）。
3. **数据包跨机同步未登记新表**：`DATA_TYPE_MODELS` 仍为 villages/projects/funds/schools（W22 未扩展，避免多机同步顺序/冲突协议变更风险）；一户一档/影像库/消费帮扶暂不参与数据包同步（后续如需再立项）。
4. **PII**：新表 `households.helper_phone`、`household_members.id_card` 用 `EncryptedText` ORM 透明加密；无历史明文，无需回填迁移；历史迁移清单中 villagers 两列随表删除保留在迁移历史。
5. **visit 挂户语义**：历史未挂户走访（`household_id=NULL`）不出现在户详情；新走访可关联户并回写最近走访日期。
6. **数据校验页**：校验执行复用既有 `/validation/query-check`（模块+字段+运算符+值），无年度/村 scope 参数（以字段条件实现）；字段说明用 `/validation/fields`。
7. **报表模板**：「任意字段组合」复用既有 `available-fields` + 模板字段元数据；导出格式 xlsx/csv/docx/pdf；打印走浏览器 `window.print`。
8. **折叠状态键**：契约写 `nav:collapsed-sections`，实现统一为 `nav:expanded-sections`（存展开集合），文档按实现写。
9. **OCR 依赖**：`rapidocr-onnxruntime==1.4.4` 登记为运行时可选依赖（Windows 安装包内置；ARM64 构建过滤降级为 503 提示）。
10. **数据上报链路断点修复**：枚举列导出已归一为枚举值（`.value`），否则上级导入时 school 等记录整表 rejected。
