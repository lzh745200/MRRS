# W20 后端「无用/冗余代码」审计报告（只读）

- 审计对象：当前工作区后端（含本批新增 `backend/app/api/v1/data/data/bigscreen.py` 与相关改动文件）
- 审计方式：**只读**。`flake8 --select=F401,F841,F811,F821` + 自写 AST/标识符调用索引扫描（1279 个 `.py`，排除 `.venv/.venv313/backups/dist/archives` 等）。
  环境未安装 vulture/ruff（`No module named vulture` / `ruff`），故用 pyflakes（flake8 插件）+ AST 引用计数替代；对"零引用"结论采取保守判据。
- **未删除任何源码/测试，未执行 git 写操作，未跑全量测试。**

## 结论摘要

| 指标 | 结果 |
|---|---|
| `app/` 全目录 F401/F841/F811/F821 | **0** |
| 本批改动的 app 代码未使用导入/死变量 | **0** |
| `bigscreen.py` 模块级符号（87 个）未被生产代码引用 | 仅 2 个，均为 `@router.get` 装饰的端点（豁免） |
| `dashboard.py` 符号（29 个）未被生产代码引用 | 仅 3 个，均为 `@router.*` 端点（豁免） |
| 常量未使用元素（`_SUPPORT_INVESTMENT_FIELDS` / `_VILLAGE_TAG_FIELDS` 等） | **0** |
| 调试残留/注释死代码（本批文件） | **0** |
| **确定可删** | **2 处（仅新增测试文件，零行为风险）** |
| 疑似 | 无（见"豁免与保留"说明） |

## 一、确定可删（附证据 + 建议顺序）

两处均在**本批新增测试文件**，不改生产代码、不影响覆盖率与发布行为。

### 1. `backend/tests/unit/api/test_bigscreen_api.py:231` — F401 未使用导入（P2）

证据（flake8 实测）：

```
tests/unit/api/test_bigscreen_api.py:231:5: F401 'app.models.school.SchoolProject' imported but unused
```

- 位置：`_seed()` 内的 `from app.models.school import ProjectPhase, SchoolProject, SupportStatus`
- `SchoolProject` 在本文件中无任何使用（建项目走本地 `_mk_school_project` helper，不直接引用模型类）。
- 修法：改为 `from app.models.school import ProjectPhase, SupportStatus`（一行编辑）。

### 2. `backend/tests/unit/api/test_bigscreen_api.py:1369` — F841 未使用局部变量（P2）

证据（flake8 实测）：

```
tests/unit/api/test_bigscreen_api.py:1369:9: F841 local variable 'ns' is assigned to but never used
```

- 位置：`TestOverviewUnit.test_unit_overview_village_and_school_hits` 的 `ns = _seed(db)`；该用例后续只用 `client`/`db`。
- 修法：改为 `_seed(db)`（保留造数副作用）。

**建议删除顺序**：同一文件，先 #1 后 #2，一次编辑即可；改完跑 `pytest tests/unit/api/test_bigscreen_api.py -q`（44 项）验证。除这两处外，**发布期无需删除任何代码**。

## 二、重点核验（任务书 §3）

### 1) `bigscreen.py` 是否有未复用/死 helper

- 模块级符号 87 个：函数/常量全部有生产引用；**唯二生产零引用**是 `get_bigscreen_filters` / `get_bigscreen_overview`（`@router.get` 装饰器注册，属豁免，非死代码）。
- helper 调用方核验（生产引用计数）：`_text`=6、`_row_value`=13、`_row_int`=2、`_round_amount`=13、`_format_location`=4、`_format_date`=2、`_format_period`=1、`_format_completeness`=1、`_format_yes_no`=1、`_status_key`=8、`_phase_key`=3、`_pairing_stats`=3、`_scoped_project_query`=6、`_village_fund_rankings`=2 等——**无孤儿 helper**。
- 复用既有能力（非重复实现）：`_query_village_stats` / `_query_fund_stats` / `_query_project_approval_stats` / `_apply_project_scope` / `_build_yearly_trends` 均直接 import dashboard 实现；新增的 `_fund_year_rows/_project_year_rows/_pairing_stats/...` 是"带实体过滤"的聚合，dashboard 无等价 helper，属必要扩展而非重复。

### 2) 常量未使用元素

- `_SUPPORT_INVESTMENT_FIELDS`（5 项）：全部被 `_latest_support_investments()` 与 `_village_investment_section()` 的循环消费（引用计数 2）。
- `_VILLAGE_TAG_FIELDS`（8 项）：全部被 `_village_tags()` 的推导式消费（引用计数 1）。
- 其余常量（`_ALLOWED_SCOPE_TYPES`、`_RANKING_LIMIT`、`_LEADER_LIMIT`、`_DETAIL_LIMIT`、`_COVERAGE_NAME_LIMIT`、`_PROJECT_STATUS_ORDER/LABELS`、`_SCHOOL_PHASE_ORDER/LABELS/VALUE_ALIASES`、`_FUND_STATUS_LABELS`、`_SUPPORT_STATUS_LABELS`、`_TRANSITION_STATUS_LABELS`）均有引用（1~3 次）——**无未使用元素**。

### 3) `dashboard.py` 抽取 `_build_yearly_trends` 后是否有旧死代码/重复逻辑

- `_build_yearly_trends` 生产引用 4 次（定义 + `/yearly-trends` 调用 + bigscreen import/调用），两端共用。
- 原 `/yearly-trends` 内联聚合**已全部移入 helper**，端点上无残留旧逻辑；模块 29 个符号中 26 个有生产引用，其余 3 个均为 `@router.*` 端点（豁免）。
- `_query_village_stats/_query_fund_stats/_query_project_approval_stats/_apply_project_scope/_scope_village_*`、缓存与 recent-activities helper 均仍被 dashboard 端点或 bigscreen 引用，**不存在"抽取后遗留重复聚合"**。

### 4) `data/data/__init__.py`

- 7 个子路由：每个 import 1 次、`include_router` 1 次（含新增 `bigscreen_router`），**无重复 include、无未使用导入**（flake8 F401=0）。

### 5) 调试残留 / 注释死代码（本批文件）

对本批 3 个 app 文件 + 1 个测试文件 grep `print(` / `pdb` / `breakpoint` / `TODO` / `FIXME` / `_scratch` / 绝对路径：**0 命中**；本批无整段注释掉的代码块、无临时探针引用。

## 三、豁免/保留（不可删原因）

- FastAPI 路由处理函数：由 `@router.get/post/...` 装饰器注册，静态引用计数为 0 属正常。
- SQLAlchemy 模型列/`relationship("X")`、Pydantic schema 字段：注册/字符串引用，删除即破坏 mapper/schema。
- `__init__.py` 导出、Alembic migration、CLI 入口脚本：按约定保留。
- 仓库级扫描另有 **36 个"仅被测试引用"的 app 函数**（生产代码 0 引用、测试文件引用 >0；如覆盖率补充测试直接调用的 helper）。删除会破坏既有测试/覆盖率门禁，**发布期不建议处理**，可在后续版本评估"测试原地内联后再删"。
- 严格判据下 app/ 内**无"确定死函数"**；若发布后要更激进的复核，可 `pip install vulture` 后对 `backend/app` 跑 `vulture --min-confidence 80` 再人工比对（本次环境无该工具）。

## 四、本批新增/改动文件最终清单（git status 视角）

我负责的大屏批次共 4 个文件：

| 状态 | 文件 | 一句话 |
|---|---|---|
| ?? 新增 | `backend/app/api/v1/data/data/bigscreen.py` | 汇报大屏对象筛选 API（`/bigscreen/filters` + `/bigscreen/overview`，四维度、数据域收敛、100% 覆盖） |
| ?? 新增 | `backend/tests/unit/api/test_bigscreen_api.py` | 上述 API 的 44 个单测（admin/受限双视角 + 边界/异常分支） |
| M 修改 | `backend/app/api/v1/data/data/dashboard.py` | 抽取 `_build_yearly_trends` 供大屏复用，`/yearly-trends` 行为不变；跳过 NULL 年经费 |
| M 修改 | `backend/app/api/v1/data/data/__init__.py` | 注册 bigscreen router（最终路径 `/api/v1/bigscreen/*`） |

工作区当前共 **216 条**未提交条目（`git status --porcelain`），按顶层目录分布：`frontend` 124、`backend` 60、`.scratch` 15、根目录 8、`docs` 4、`scripts` 2、`docker` 2、`tests` 1 —— 除上表 4 个文件外均为并行批次（W18/W19、前端大屏等）改动，提交信息需由 Lead 汇总；完整逐文件清单以 `git status --porcelain` 为准。

## 五、方法与局限

- 工具：flake8（pyflakes）精确报 F 系问题；AST + 调用/属性/引号/import 四类引用索引做零引用筛查（1279 个 `.py`）。
- "零引用"判据保守（同名局部变量可能被计为引用），因此宁缺毋滥：只把 **flake8 实证** 的两处列为"确定可删"。
- 本次未跑全量测试（发布窗口约束），删除建议仅为测试文件的两处语法级清理，可在一次 44 项定向测试内验证。
