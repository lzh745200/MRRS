"""
数据质量管理API
"""

from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_active_user, get_db
from app.models.user import User
from app.services.data_cleaning_service import DataCleaningService
from app.services.validation_engine_service import ValidationEngine

router = APIRouter(prefix="/data-quality", tags=["数据质量"])


class ValidateDataRequest(BaseModel):
    """验证数据请求"""

    entity_type: str
    data: dict
    field_name: Optional[str] = None


class CleanDataRequest(BaseModel):
    """清洗数据请求"""

    records: list
    cleaning_rules: dict


@router.post("/validate")
async def validate_data(
    request: ValidateDataRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    验证数据（按实体类型从规则库加载校验规则）
    """
    engine = ValidationEngine(db)
    errors = engine.validate_with_db_rules(data=request.data, module=request.entity_type)

    issues = []
    for err in errors:
        # 错误消息格式兼容两种：{field}: {message} 或纯消息
        if isinstance(err, dict):
            issues.append(err)
        elif ":" in err:
            field, _, message = err.partition(":")
            issues.append({"field": field.strip(), "message": message.strip(), "severity": "error"})
        else:
            issues.append({"field": request.field_name or "", "message": err, "severity": "error"})

    return {
        "valid": not errors,
        "issues": issues,
        "message": "校验通过" if not errors else f"发现 {len(errors)} 个问题",
    }


@router.post("/clean")
async def clean_data(request: CleanDataRequest, current_user: User = Depends(get_current_active_user)):
    """
    清洗数据
    需要管理员权限
    """
    if not current_user.is_superuser:
        from fastapi import HTTPException

        raise HTTPException(status_code=403, detail="需要管理员权限")

    cleaned_records = DataCleaningService.clean_dataset(records=request.records, cleaning_rules=request.cleaning_rules)

    return {
        "original_count": len(request.records),
        "cleaned_count": len(cleaned_records),
        "cleaned_records": cleaned_records,
    }


@router.post("/deduplicate")
async def deduplicate_data(
    records: list,
    key_fields: list,
    similarity_threshold: float = Query(0.9, ge=0, le=1),
    current_user: User = Depends(get_current_active_user),
):
    """
    数据去重
    """
    unique_records = DataCleaningService.deduplicate(
        records=records,
        key_fields=key_fields,
        similarity_threshold=similarity_threshold,
    )

    return {
        "original_count": len(records),
        "unique_count": len(unique_records),
        "duplicates_removed": len(records) - len(unique_records),
        "records": unique_records,
    }



# ==================== 自定义规则校验（下拉 + 与或非） ====================


class ValidateRuleItem(BaseModel):
    """单条校验规则"""
    field: str = Field(..., description="字段名")
    operator: str = Field(..., description="操作符: eq/ne/contains/gt/lt/not_empty/is_empty")
    value: Optional[Any] = Field(None, description="比较值")
    logic: Optional[str] = Field("and", description="与上一条规则的逻辑: and/or")


class ValidateRulesRequest(BaseModel):
    entity_type: str = Field(..., description="校验模块: village/fund/project/school/rural_work")
    rules: List[ValidateRuleItem] = Field(..., min_length=1, description="规则列表")


@router.post("/validate-rules", summary="自定义规则校验（下拉+与或非组合）")
async def validate_rules(
    request: ValidateRulesRequest,
    db: Session = Depends(get_db),
):
    """按用户组合的规则（字段/操作符/值/与或非）校验模块数据，返回不满足的记录"""
    from app.models.supported_village import SupportedVillage
    from app.models.fund import Fund
    from app.models.project import Project
    from app.models.school import School
    from app.models.rural_work import RuralWork

    model_map = {
        "village": (SupportedVillage, "village_name"),
        "fund": (Fund, "name"),
        "project": (Project, "name"),
        "school": (School, "name"),
        "rural_work": (RuralWork, "name"),
    }
    if request.entity_type not in model_map:
        raise HTTPException(status_code=400, detail=f"不支持的模块: {request.entity_type}")

    model, label_field = model_map[request.entity_type]
    records = db.query(model).filter(getattr(model, "is_active", True) == True).all()  # noqa: E712

    def _match(record, rule: ValidateRuleItem) -> bool:
        value = getattr(record, rule.field, None)
        op = rule.operator
        if op == "eq":
            return str(value) == str(rule.value)
        if op == "ne":
            return str(value) != str(rule.value)
        if op == "contains":
            return rule.value is not None and str(rule.value) in str(value or "")
        if op == "gt":
            try:
                return float(value) > float(rule.value)
            except (TypeError, ValueError):
                return False
        if op == "lt":
            try:
                return float(value) < float(rule.value)
            except (TypeError, ValueError):
                return False
        if op == "not_empty":
            return value is not None and str(value).strip() != ""
        if op == "is_empty":
            return value is None or str(value).strip() == ""
        return False

    # 组合规则：整体通过 = 每条规则满足后按 logic 连接
    passed = []
    failed = []
    for rec in records:
        ok = True
        for i, rule in enumerate(request.rules):
            matched = _match(rec, rule)
            if i == 0:
                ok = matched
            elif rule.logic == "or":
                ok = ok or matched
            else:
                ok = ok and matched
        item = {
            "record_id": rec.id,
            "label": str(getattr(rec, label_field, rec.id)),
            "matched": ok,
        }
        if ok:
            passed.append(item)
        else:
            failed.append(item)

    return {
        "code": 200,
        "success": True,
        "data": {
            "total": len(records),
            "matched_count": len(passed),
            "failed_count": len(failed),
            "failed": failed[:200],
        },
        "message": f"校验完成：匹配 {len(passed)} 条，不满足 {len(failed)} 条",
    }
