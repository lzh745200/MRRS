"""
数据质量管理API
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
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
