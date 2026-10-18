# W22-001 文档与 PPT 全量对齐（v1.14.0 功能大迭代）

> Wave：`w22-feature-batch`　｜　责任：docs-ppt（写作用域 `docs/**`、`README.md`、`CLAUDE.md`、
> `项目文件结构说明.md`、`deliverables/README.md`、`.scratch/w22-feature-batch/`）
> 契约：[000-contract.md](000-contract.md)（13 项功能）　｜　版本：**1.14.0**（2026-10-18）

## 背景

v1.14.0 功能大迭代（契约 §0 共 13 项）：

- **新增**：一户一档（households 三表 + `/households/*`）、影像库（photo_archives + EXIF/GPS/对比图）、
  消费帮扶台账（consumption_records，替换舆情监测）、经费凭证 OCR（rapidocr-onnxruntime 1.4.4 离线）、
  报表模板任意字段组合导出（xlsx/csv/docx/pdf + 打印）、数据校验三 Tab 合并页、7 板块标题放大+默认折叠
  （`nav:expanded-sections`）、汇报大屏退出按钮、数据上报链路端到端校验修复。
- **删除/下线**：驻村工作台、舆情监测、国际化/邮件设置、独立「校验规则」入口（均保留 legacy 菜单 key）、
  遗留表 villages/villagers/industries/sentiment_news（tea_plantations/cactus_fruit_plots 保留并改挂
  `supported_village_id`）。

旧文档与 PPT（v1.13.0：41 页、菜单 99 key）全面过期，需按最终代码/契约重写并删除过时说明。

## What（交付）

### 1. 文档更新（与最终代码对齐）

| 文件 | 改动要点 |
|---|---|
| `CLAUDE.md` | 项目结构（94 API 模块 / 新模型/服务/页面）；新增「W22 功能迭代」约定（一户一档/影像库/消费帮扶/OCR/报表导出/校验合并/折叠/大屏退出/遗留表清理/新依赖）；PII 清单改为 households.helper_phone + household_members.id_card（仍 9 列） |
| `README.md` | 后端技术栈加离线 OCR；前端导航加 7 板块折叠；项目结构/自包含清单（OCR 模型）更新；近期修复记录新增 v1.14.0 段 |
| `项目文件结构说明.md` | API 模块（新增 households/media/consumption、删 villages/sentiment）；schemas/models/services 新文件；views 新页面（households/media/consumption/dataVerify）与删除页面；system 子包删国际化；计数更新（141 views/25 组件/55 api/14 composables/318 测试） |
| `deliverables/README.md` | PPT 描述改为 47 页 / v1.14.0（docs 唯一副本） |
| `docs/INDEX.md`、`docs/README.md` | 版本 1.14.0；使用指南新章节入口；API 统计 91 模块/799 端点 |
| `docs/03-开发文档/前后端契约规范.md` | v1.14.0 头部；§4.1 规模（102 key 含 15 legacy / 6 板块 / 83 path）+ 下线 key 转 legacy；§4.2 六板块表加入一户一档/消费帮扶/影像库、移除驻村/舆情/校验规则；§4.4 增加板块折叠（18px/默认折叠/`nav:expanded-sections`）；§7 测试数字改为发布口径；§8 新增 W22 六项能力并改写驻村打卡/大屏退出 |
| `docs/03-开发文档/03-API文档/API接口文档.md` | 删除 sentiment/i18n/villages 三段；新增 households/media/consumption 段；funds 加 OCR 端点；report_templates 加 export/print-data；data_packages 加链路端到端说明；头部统计 91 模块/799 端点（源码扫描口径） |
| `docs/03-开发文档/07-UI设计规范/UI设计方案.md` | 侧栏结构改 v1.14.0（18px 标题/默认折叠/展开状态记忆）；大屏加退出按钮；§5.6 系统设置 Tab 精简；新增 §5.7 一户一档 / §5.8 影像库 / §5.9 消费帮扶 / §5.10 数据校验合并 / §5.11 报表模板组合规范 |
| `docs/03-开发文档/02-开发指南/UI设计规范.md` | §4.2 导航补 7 板块折叠与 localStorage 约定 |
| `docs/03-开发文档/01-架构设计/系统架构说明.md` | 层图/导览数字（94 模块 / ~110 服务 / 115 表 / 141 页）；横切机制新增离线 OCR、一户一档汇总回填、数据上报链路 |
| `docs/03-开发文档/01-架构设计/系统设计图集.md` | DDD 层新增 households/media/consumption 模块、端点 799；示例 URL 改 `/api/v1/supported-villages`；模块依赖图与前端组件树加新页面/折叠导航；附注加 v1.14.0 |
| `docs/03-开发文档/08-数据设计/02-数据字典.md` | 115 表口径；域表数 16/33/24/4/3/4/8/4/19；§2.4 改「特色产业与行政区划 3 表」并说明删 3 旧表；新增 §2.8 一户一档 / §2.9 影像库 / §2.10 消费帮扶台账；RuralWork/RuralTask 改 `supported_village_id`；命名陷阱更新 |
| `docs/03-开发文档/08-数据设计/01-数据库设计总览.md` | 域表数与 ER：删 villages/villagers/industries，茶园/刺梨园改挂 supported_villages，新增 households/成员/风险、photo_archives、consumption_records；乡村工作改挂 `supported_village_id`；命名陷阱 #1/#2 改写 |
| `docs/adr/0005-pii-encryption.md` | PII 9 列清单：villagers 两列 → households.helper_phone / household_members.id_card |
| `docs/03-开发文档/00-需求规格说明书/01-需求规格说明书.md` | §4 导航口径 v1.14.0；新增 FR-1-06 一户一档、FR-4-11 OCR、FR-6-09 上报链路、FR-8-07 影像库、FR-9-12 导航体验、FR-10 消费帮扶（3 条）；更新 FR-7-02（合并页）与 FR-7-05（报表组合）、FR-9-09（去国际化）；术语表更新 |
| `docs/02-用户手册/使用指南.md` | 版本 1.14.0；导航表（新增一户一档/消费帮扶/影像库、删驻村/舆情/校验规则、系统设置仅更新日志）；7 板块折叠说明；新增 §11 一户一档、§12 影像库、§13 消费帮扶台账、§14 数据校验合并、§15 经费凭证 OCR、§16 报表模板组合、§17 大屏退出；§4 经费/§7 数据管理更新；文末版本 |
| `docs/02-用户手册/数据分析功能使用指南.md` | 删舆情、加影像库与大屏退出 |
| `docs/02-用户手册/经费管理模块操作说明.md` | 新增 §3.5 凭证 OCR 用法 |
| `docs/02-用户手册/权限包管理与数据上报接收操作说明.md` | legacy key 权限兼容说明；数据上报链路端到端校验说明；版本 1.14.0 |
| `docs/03-开发文档/06-运维文档/技术栈说明.md` | v1.14.0；技术栈/可选依赖加 rapidocr-onnxruntime 1.4.4 |
| `docs/03-开发文档/02-开发指南/后端开发指南.md`、`04-安全文档/安全加固.md` | Village 遗留示例最小修正（改用 SupportedVillage / 加 v1.14.0 说明，不重写整章） |
| `docs/build_ppt.js` + `docs/帮扶管理信息系统介绍.pptx` | 见下 |

### 2. 删除 / 改写（过时说明）

- 删驻村工作台、舆情监测、国际化/邮件设置、独立校验规则入口在导航/手册/API/数据字典/PPT 中的全部存在性描述。
- 删数据字典 §2.4 中 `villages`/`villagers`/`industries` 三表段落；表数 114 → 115。
- 删 API 文档 `sentiment.py` / `i18n.py` / `villages.py` 段；模块速查移除 villages。
- 改命名陷阱与示例：`village_id` 指向说明、`/api/v1/villages` 示例 URL、后端开发指南 Village 测试示例。
- 不删：历史交付/审查报告（R28/W18 等，时点归档）、`CHANGELOG.md`（Lead 维护）、`000-contract.md`。

### 3. PPT（41 页 → 47 页，+6 新页）

新增：**一户一档**、**经费凭证 OCR**、**消费帮扶台账**、**数据上报链路**、**报表模板组合导出**、**影像库**。
改写：目录、03 章节页、关键数字、数据层、前端工程、后端工程、功能地图、帮扶村、资金管理、数据包协同、
数据分析与报表、系统管理、PII、测试体系、版本历程、结束页 + 全 PPT 页脚/封面/结束页版本 v1.14.0
（7 板块折叠并入前端工程页说明，不单独占页）。

## 验收 checklist

- [x] 文档与最终代码一致：菜单 102 key（15 legacy）/6 板块/83 path；新增 5 表/删 4 表；新路由/新 API/新页面齐备。
- [x] 全仓 grep 旧表述：驻村工作台/舆情/国际化/独立校验规则/Village 遗留的**过时说明**已清除或改为"已下线"说明。
- [x] `node docs/build_ppt.js` 成功；PPT 写入 `docs/`（`__dirname`），根目录无副本。
- [x] PPT 47 页、python-pptx 读页数/标题抽样正确；`scripts/ppt_overflow_check.py` 0 溢出。
- [x] 未修改代码/测试/`package.json`/`CHANGELOG.md`/版本文件；未 git 操作。
- [x] 最终测试数字（后端 13,710 passed/1 skipped、前端 6,748/321 文件、行+分支覆盖率 100%）已填入 README/PPT/本工单。

## Resolution 证据

### 菜单（最终代码解析）

```text
MENU_SCHEMA_VERSION = 2
SECTIONS = business/rural/collab/report/data/system
ENTRIES = 52（含 dashboard + 15 legacy）
TOTAL_KEYS = 102 / LEGACY = 15 / PATHS = 83
下属：checkin/i18n/email/validation-rules/sentiment → section=None + legacy=True（无导航出口）
```

### PPT 构建与验证

```text
$ node docs/build_ppt.js
DONE pages=44            # 内容页计数；实际 47 张（含封面/目录/6 章节页/结束页）
[自适应度量] 触发字号收缩 5 处：P06 数据来源 12→9pt、P11 工程纪律 12.5→10.5pt、
  P17 帮扶村要点 12.5→11pt、P32 数据来源 11→10pt、P32 测试纪律 12.5→11pt

$ backend/.venv313/Scripts/python.exe（python-pptx 1.0.2）
slides: 47
18 03 功能模块 | 一户一档：从“一村一档”细到“一户一档”
21 03 功能模块 | 经费凭证 OCR：拍一张，金额日期自动填
23 03 功能模块 | 消费帮扶台账：逐笔记录帮销成果
26 03 功能模块 | 数据上报链路：下级打包 → 上级接收 → 数据可见
28 03 功能模块 | 报表模板：任意字段组合 · 四种格式 · 一键打印
29 03 功能模块 | 影像库：照片归档 + 多期对比，现场变化看得见
contains v1.14.0 / 13,710 / 6,748 / 321 文件 / 102 菜单 key / 一户一档 / 影像库 / 消费帮扶 / OCR / nav:expanded-sections / 退出大屏: True
旧占位 13,650+/6,800+ 残留: False
文件：docs/帮扶管理信息系统介绍.pptx（975,962 bytes，2026-10-18 19:44 重新生成）

$ python scripts/ppt_overflow_check.py
文件: docs/帮扶管理信息系统介绍.pptx  共 47 页  (阈值 溢出比 >= 1.0)
>>> 合计溢出文本框: 0
```

### 数字口径

- 版本 **1.14.0**（根 `package.json` 为唯一版本源，由 Lead 的 `sync-version.js --write` 统一同步）。
- 菜单：**102 key / 15 legacy / 6 板块 / 83 个带 path 入口**（`menus.py` 解析实测）。
- DB：**115 表**（114 + 5 新表 − 4 旧表，按数据字典口径）；API：91 路由模块 / 799 端点（`@router` 扫描口径）。
- 测试（2026-10-18 发布门禁实测，串行干净运行）：后端 **13,710 passed / 1 skipped / 0 failed**，
  语句覆盖率 **100.00%**（44,423 stmts，0 miss）、分支覆盖率 **100.00%**（10,872 branches，0 partial）；
  前端 **321 文件 / 6,748 passed / 0 failed**，`src/**` 12 组 glob 四指标 100%。
- AI 代码深度审查（沿用）：376 文件 / 918 条发现。
- 上述数字已同步到 README（项目状态/测试体系/上次全量验证）、PPT（关键数字/测试体系/前端工程/净效果/结束页）与本工单。

## 状态

**已完成（2026-10-18）**。文档、PPT（47 页，0 溢出）与工单均按 v1.14.0 最终代码与实测数字对齐；
CHANGELOG/版本文件由 Lead 维护，本批未触碰代码/测试/配置（仅文档与 PPT）。
