"""
数据校验规则 API
管理员可配置字段级校验规则，前端动态读取并实时校验
"""

import json
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from ...core.database import get_db
from ...core.security import get_current_user
from ...models.validation_rule import RuleType, ValidationRule
from app.core.response import success_response
from app.core.transaction import safe_commit
from app.services.work_log_service import write_work_log

router = APIRouter(prefix="/validation", tags=["数据校验"])


# ---- Schemas ----


class ValidationRuleCreate(BaseModel):
    module: str
    field: str
    rule_type: RuleType
    params: Optional[str] = None
    error_message: str = "数据校验失败"
    description: Optional[str] = None
    is_active: bool = True
    priority: int = 100


class ValidationRuleUpdate(BaseModel):
    module: Optional[str] = None
    field: Optional[str] = None
    rule_type: Optional[RuleType] = None
    params: Optional[str] = None
    error_message: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    priority: Optional[int] = None


class ValidationRuleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    module: str
    field: str
    rule_type: str
    params: Optional[str] = None
    error_message: str
    description: Optional[str] = None
    is_active: bool
    priority: int


# ---- Endpoints ----


@router.get("/rules", response_model=List[ValidationRuleOut])
async def list_rules(
    module: Optional[str] = Query(default=None, description="按模块筛选"),
    is_active: Optional[bool] = Query(default=None, description="是否启用"),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取校验规则列表"""
    query = db.query(ValidationRule)
    if module:
        query = query.filter(ValidationRule.module == module)
    if is_active is not None:
        query = query.filter(ValidationRule.is_active == is_active)
    rules = query.order_by(ValidationRule.module, ValidationRule.priority).all()
    return rules


@router.post("/rules", response_model=ValidationRuleOut)
async def create_rule(
    rule_in: ValidationRuleCreate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """创建校验规则（管理员）"""
    # 校验 params 是否为合法 JSON
    if rule_in.params:
        try:
            json.loads(rule_in.params)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="params 必须为合法 JSON 字符串")

    rule = ValidationRule(
        module=rule_in.module,
        field=rule_in.field,
        rule_type=rule_in.rule_type,
        params=rule_in.params,
        error_message=rule_in.error_message,
        description=rule_in.description,
        is_active=rule_in.is_active,
        priority=rule_in.priority,
        created_by=current_user.id,
    )
    db.add(rule)
    safe_commit(db)
    db.refresh(rule)
    write_work_log(db, "validation", "create_rule", rule.id,
                   f"创建校验规则: {rule.module}.{rule.field}", user_id=current_user.id,
                   username=getattr(current_user, "username", ""))
    return rule


@router.put("/rules/{rule_id}", response_model=ValidationRuleOut)
async def update_rule(
    rule_id: int,
    rule_in: ValidationRuleUpdate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """更新校验规则"""
    rule = db.query(ValidationRule).filter(ValidationRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="规则不存在")

    if rule_in.params is not None:
        try:
            json.loads(rule_in.params)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="params 必须为合法 JSON 字符串")

    update_data = rule_in.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(rule, key, value)

    safe_commit(db)
    db.refresh(rule)
    write_work_log(db, "validation", "update_rule", rule.id,
                   f"更新校验规则: {rule.module}.{rule.field}", user_id=current_user.id,
                   username=getattr(current_user, "username", ""), detail=str(update_data))
    return rule


@router.delete("/rules/{rule_id}")
async def delete_rule(
    rule_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """删除校验规则"""
    rule = db.query(ValidationRule).filter(ValidationRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="规则不存在")
    rule_name = f"{rule.module}.{rule.field}"
    db.delete(rule)
    safe_commit(db)
    write_work_log(db, "validation", "delete_rule", rule_id,
                   f"删除校验规则: {rule_name}", user_id=current_user.id,
                   username=getattr(current_user, "username", ""))
    return success_response(message="规则已删除")


# 字段中文标签映射（覆盖常用模块字段）
FIELD_LABELS: dict = {
    # 帮扶村
    "department": "部门单位",
    "support_unit": "帮扶单位",
    "village_name": "帮扶村名称",
    "county": "所在县/市",
    "region_scope": "地区范围",
    "transition_fund_military_total": "部队合计投入(万元)",
    "transition_fund_local_total": "协调地方投入(万元)",
    "per_capita_income": "人均纯收入",
    "collective_income": "村集体收入",
    "total_households": "总户数",
    "total_population": "总人数",
    # 学校
    "name": "名称",
    "student_count": "学生人数",
    "teacher_count": "教师人数",
    "class_count": "班级数量",
    "principal": "校长姓名",
    "contact_phone": "联系电话",
    # 项目 / 经费
    "budget": "预算金额",
    "actual_cost": "实际投入",
    "investment": "投入金额",
    "planned_investment": "计划投入",
    "year": "年份",
}


@router.post("/validate")
async def validate_data(
    module: str,
    data: dict,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    对提交数据执行校验
    返回 {valid: bool, errors: [{field, field_label, rule_type, message}]}
    """
    rules = (
        db.query(ValidationRule)
        .filter(ValidationRule.module == module, ValidationRule.is_active == True)  # noqa: E712
        .order_by(ValidationRule.priority)
        .all()
    )
    errors = []
    for rule in rules:
        field_value = data.get(rule.field)
        params = json.loads(rule.params) if rule.params else {}
        error = _check_rule(rule, field_value, params, data)
        if error:
            field_label = FIELD_LABELS.get(rule.field, rule.field)
            # 如果 error_message 是泛化的默认值，自动补充字段名
            message = rule.error_message
            if message == "数据校验失败":
                message = f"{field_label}校验失败"
            errors.append(
                {
                    "field": rule.field,
                    "field_label": field_label,
                    "rule_type": rule.rule_type.value,
                    "message": message,
                }
            )
    return success_response(data={"valid": len(errors) == 0, "errors": errors})


def _check_rule(rule: ValidationRule, value, params: dict, full_data: dict) -> bool:
    """检查单条规则，返回 True 表示校验失败"""
    if rule.rule_type == RuleType.required:
        return value is None or (isinstance(value, str) and value.strip() == "")
    if value is None:
        return False
    handler = _RULE_HANDLERS.get(rule.rule_type)
    return handler(value, params, full_data) if handler else False


def _check_positive(value, params, full_data):
    try:
        return float(value) <= 0
    except (ValueError, TypeError):
        return True


def _check_non_negative(value, params, full_data):
    try:
        return float(value) < 0
    except (ValueError, TypeError):
        return True


def _check_max_length(value, params, full_data):
    return len(str(value)) > params.get("max", 255)


def _check_min_length(value, params, full_data):
    return len(str(value)) < params.get("min", 0)


def _check_range(value, params, full_data):
    try:
        v = float(value)
        min_v = params.get("min")
        max_v = params.get("max")
        if min_v is not None and v < float(min_v):
            return True
        if max_v is not None and v > float(max_v):
            return True
    except (ValueError, TypeError):
        return True
    return False


def _check_regex(value, params, full_data):
    import re
    return not re.match(params.get("pattern", ""), str(value))


def _check_date_format(value, params, full_data):
    from datetime import datetime
    fmt = params.get("format", "%Y-%m-%d")
    try:
        datetime.strptime(str(value), fmt)
    except ValueError:
        return True
    return False


def _check_file_type(value, params, full_data):
    allowed = params.get("allowed", [])
    if isinstance(value, str):
        ext = value.rsplit(".", 1)[-1].lower() if "." in value else ""
        return ext not in allowed
    return False


def _check_enum_values(value, params, full_data):
    allowed = params.get("values", [])
    return str(value) not in [str(v) for v in allowed]


def _check_cross_field(value, params, full_data):
    other_field = params.get("other_field")
    operator = params.get("operator", "<=")
    if other_field and other_field in full_data:
        try:
            v1 = float(value)
            v2 = float(full_data[other_field])
            if operator == "<=" and v1 > v2:
                return True
            if operator == ">=" and v1 < v2:
                return True
            if operator == "<" and v1 >= v2:
                return True
            if operator == ">" and v1 <= v2:
                return True
            if operator == "==" and v1 != v2:
                return True
        except (ValueError, TypeError):
            return True
    return False


_RULE_HANDLERS = {
    RuleType.positive: _check_positive,
    RuleType.non_negative: _check_non_negative,
    RuleType.max_length: _check_max_length,
    RuleType.min_length: _check_min_length,
    RuleType.range: _check_range,
    RuleType.regex: _check_regex,
    RuleType.date_format: _check_date_format,
    RuleType.file_type: _check_file_type,
    RuleType.enum_values: _check_enum_values,
    RuleType.cross_field: _check_cross_field,
}


# ==================== 小白友好：下拉式条件查询校验 ====================
# 前端通过「字段 + 运算符 + 值 + 与/或」组合条件，对指定模块的存量数据
# 做查询式校验（匹配/不匹配一目了然），无需理解规则引擎。

class QueryCondition(BaseModel):
    """单条查询条件"""
    field: str = Field(..., description="字段名（FIELD_LABELS 中文标签展示）")
    operator: str = Field(..., description="eq/ne/gt/gte/lt/lte/contains/not_contains/empty/not_empty")
    value: Optional[str] = Field(None, description="比较值（empty/not_empty 时忽略）")


class QueryCheckRequest(BaseModel):
    """条件查询校验请求"""
    module: str = Field(..., description="数据模块: village/school/project/fund")
    conditions: List[QueryCondition] = Field(..., min_length=1, description="条件列表（≥1 条）")
    logic: str = Field("and", description="多条件组合逻辑: and=全部满足 / or=任一满足")
    limit: int = Field(200, ge=1, le=1000)


# 模块 → 模型映射（条件校验对象）
_QUERY_CHECK_MODELS = {}


def _get_query_model(module: str):
    if module not in _QUERY_CHECK_MODELS:
        from app.models.fund import Fund
        from app.models.project import Project
        from app.models.school import School
        from app.models.supported_village import SupportedVillage

        _QUERY_CHECK_MODELS.update({
            "village": SupportedVillage,
            "school": School,
            "project": Project,
            "fund": Fund,
        })
    return _QUERY_CHECK_MODELS.get(module)


def _apply_query_condition(cond: QueryCondition, row) -> bool:
    """对单行记录应用单条条件，返回是否满足"""
    value = getattr(row, cond.field, None)
    op = cond.operator
    if value is None:
        return op == "empty"

    if op == "empty":
        return str(value).strip() == ""
    if op == "not_empty":
        return str(value).strip() != ""

    target = (cond.value or "").strip()
    if op == "contains":
        return target.lower() in str(value).lower()
    if op == "not_contains":
        return target.lower() not in str(value).lower()

    # 数值比较：双方可转 float 时按数值比较，否则按字符串
    try:
        v_num = float(value)
        t_num = float(target)
        numeric = True
    except (ValueError, TypeError):
        numeric = False

    if op in ("eq", "ne"):
        if numeric and target:
            match = v_num == t_num
        else:
            match = str(value).strip() == target
        return match if op == "eq" else not match
    if op in ("gt", "gte", "lt", "lte"):
        if not numeric or not target:
            return False
        if op == "gt":
            return v_num > t_num
        if op == "gte":
            return v_num >= t_num
        if op == "lt":
            return v_num < t_num
        return v_num <= t_num
    return False


@router.get("/fields", summary="获取模块可校验字段（中文标签）")
async def list_validation_fields(
    module: str = Query("village", description="数据模块: village/school/project/fund"),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """返回指定模块的可查询字段列表（含中文标签），供下拉式校验面板使用"""
    model = _get_query_model(module)
    if model is None:
        raise HTTPException(status_code=400, detail=f"不支持的模块: {module}")
    fields = [
        {"key": c.name, "label": FIELD_LABELS.get(c.name, c.name)}
        for c in model.__table__.columns
        if not c.name.startswith("_")
    ]
    return success_response(data={"module": module, "fields": fields})


@router.post("/query-check", summary="条件查询校验（小白友好：字段+运算符+值组合）")
async def query_check(
    data: QueryCheckRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """按条件对存量数据做查询式校验，返回匹配/不匹配明细。

    前端以中文标签下拉选择字段与运算符，组合「与/或」逻辑，即可快速
    查出不符合条件（或符合条件）的记录，无需理解规则引擎。
    """
    model = _get_query_model(data.module)
    if model is None:
        raise HTTPException(status_code=400, detail=f"不支持的模块: {data.module}（可选 village/school/project/fund）")

    # 校验字段存在性（给出中文提示）
    valid_columns = {c.name for c in model.__table__.columns}
    for cond in data.conditions:
        if cond.field not in valid_columns:
            raise HTTPException(
                status_code=400,
                detail=f"字段「{FIELD_LABELS.get(cond.field, cond.field)}」在 {data.module} 模块中不存在",
            )
    if data.logic not in ("and", "or"):
        raise HTTPException(status_code=400, detail="logic 仅支持 and（全部满足）/ or（任一满足）")

    from app.core.data_scope_adapter import apply_scope_filter

    query = db.query(model)
    query = apply_scope_filter(query, current_user, model, db=db)
    # 软删过滤（模型有 is_active 时）
    if hasattr(model, "is_active"):
        query = query.filter(model.is_active == True)  # noqa: E712
    rows = query.limit(data.limit).all()

    results = []
    matched_count = 0
    for row in rows:
        if data.logic == "and":
            ok = all(_apply_query_condition(c, row) for c in data.conditions)
        else:
            ok = any(_apply_query_condition(c, row) for c in data.conditions)
        if ok:
            matched_count += 1
        results.append({
            "id": getattr(row, "id", None),
            "matched": ok,
            "values": {c.field: str(getattr(row, c.field, "") or "") for c in data.conditions},
        })

    return success_response(data={
        "module": data.module,
        "logic": data.logic,
        "condition_count": len(data.conditions),
        "total": len(rows),
        "matched": matched_count,
        "unmatched": len(rows) - matched_count,
        "results": results,
        "message": (
            f"共 {len(rows)} 条记录，满足条件 {matched_count} 条，不满足 {len(rows) - matched_count} 条"
        ),
    })
