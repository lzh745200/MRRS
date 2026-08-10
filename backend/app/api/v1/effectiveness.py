"""
成效评估API
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_active_user, get_db
from app.core.data_scope_adapter import apply_scope_filter
from app.core.permission_utils import is_admin
from app.models.user import User
from app.models.village import Village
from app.services.effectiveness_service import EffectivenessService
from app.core.response import success_response

router = APIRouter(prefix="/effectiveness", tags=["成效评估"])


class EvaluateRequest(BaseModel):
    """评估请求"""

    village_id: int
    year: int


@router.post("/evaluate")
async def evaluate_village(
    request: EvaluateRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    评估村庄成效（根据年度收入/基础设施/产业数据计算三唯分数并落库）
    需要管理角色权限
    """
    if not is_admin(current_user):
        raise HTTPException(status_code=403, detail="需要管理员权限")

    result = EffectivenessService.evaluate_village(
        db=db, village_id=request.village_id, year=request.year, user_id=current_user.id
    )

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    # 年度考核闭环：评估完成后提交"复核"审批任务（若配置了 assessment 工作流）
    review_task_id = None
    try:
        from app.services.approval_workflow_service import ApprovalWorkflowService

        svc = ApprovalWorkflowService(db)
        task = svc.submit_approval(
            entity_type="assessment",
            entity_id=request.village_id,
            submitter_id=current_user.id,
            title=f"年度考核复核-村{request.village_id}-{request.year}年",
            change_data={"year": request.year, "score": result.get("total_score")},
        )
        if task:
            review_task_id = task.id
    except Exception:
        # 复核任务创建失败不阻断评估
        review_task_id = None

    if review_task_id:
        result["review_task_id"] = review_task_id
        result["review_status"] = "pending_review"

    return result


@router.get("/report/{village_id}")
async def get_evaluation_report(
    village_id: int,
    year: int = Query(..., description="年份"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """获取评估报告"""
    village = apply_scope_filter(
        db.query(Village).filter(Village.id == village_id),
        current_user, Village, db=db
    ).first()
    if not village:
        raise HTTPException(status_code=404, detail="评估报告不存在")

    report = EffectivenessService.get_evaluation_report(db=db, village_id=village_id, year=year)

    if not report:
        raise HTTPException(status_code=404, detail="评估报告不存在")

    return report


@router.get("/compare/{village_id}")
async def compare_evaluations(
    village_id: int,
    year1: int = Query(..., description="年份1"),
    year2: int = Query(..., description="年份2"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """对比两年的评估结果"""
    village = apply_scope_filter(
        db.query(Village).filter(Village.id == village_id),
        current_user, Village, db=db
    ).first()
    if not village:
        raise HTTPException(status_code=404, detail="评估报告不存在")

    comparison = EffectivenessService.compare_evaluations(db=db, village_id=village_id, year1=year1, year2=year2)

    if "error" in comparison:
        raise HTTPException(status_code=400, detail=comparison["error"])

    return comparison


@router.get("/rankings")
async def get_rankings(
    year: int = Query(..., description="年份"),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """获取排名列表"""
    from app.models.effectiveness import EffectivenessEvaluation

    query = (
        db.query(EffectivenessEvaluation, Village.name)
        .join(Village, EffectivenessEvaluation.village_id == Village.id)
        .filter(EffectivenessEvaluation.year == year)
    )
    query = apply_scope_filter(query, current_user, Village, db=db)
    evaluations = query.order_by(EffectivenessEvaluation.rank).limit(limit).all()

    return success_response(data={
        "year": year,
        "rankings": [
            {
                "rank": eval.rank,
                "village_id": eval.village_id,
                "village_name": village_name,
                "total_score": eval.total_score,
                "grade": eval.grade,
                # 前端 Rankings.vue 分项得分列（economic/social/...）
                "scores": {
                    "economic": eval.economic_score,
                    "social": eval.social_score,
                    "ecological": eval.ecological_score,
                },
            }
            for eval, village_name in evaluations
        ],
    })
