"""经费事件触发联动服务

监听 Project 状态变更事件，自动触发对应的经费阶段推进与数据同步。
可在项目状态流转 API 中显式调用。
"""

import logging

from sqlalchemy.orm import Session

from app.models.fund import Fund
from app.models.fund_lifecycle import PhaseStatus, ProjectFundPhase
from app.utils.time_utils import utcnow

logger = logging.getLogger(__name__)

# 项目状态 → 经费阶段映射
STATUS_PHASE_MAP = {
    "draft": 1,  # 论证立项
    "pending": 1,  # 论证立项（待审批）
    "approved": 2,  # 汇总审核
    "in_progress": 5,  # 组织实施与过程监管
    "completed": 7,  # 常态监管与项目决算
}


def on_project_status_change(db: Session, project_id: int, old_status: str, new_status: str, operator: str = ""):
    """项目状态变更时触发经费阶段联动"""
    target_phase = STATUS_PHASE_MAP.get(new_status)
    if not target_phase:
        return

    phases = (
        db.query(ProjectFundPhase)
        .filter(ProjectFundPhase.project_id == project_id)
        .order_by(ProjectFundPhase.phase)
        .all()
    )

    if not phases:
        # 自动初始化
        phases = _init_phases(db, project_id)

    # entered_at/completed_at 均为 UtcDateTime 列，必须写 aware UTC（naive 会被
    # 原样落库，把本地墙钟当 UTC 存，UTC+8 上偏早 8 小时）
    now = utcnow()

    # 将目标阶段之前的阶段全部标记完成
    for p in phases:
        if p.phase < target_phase:
            if p.status != PhaseStatus.COMPLETED.value:
                p.status = PhaseStatus.COMPLETED.value
                p.completed_at = p.completed_at or now
                p.operator = p.operator or operator
        elif p.phase == target_phase:
            if p.status in (PhaseStatus.NOT_STARTED.value, PhaseStatus.COMPLETED.value):
                p.status = PhaseStatus.IN_PROGRESS.value
                p.entered_at = now
                p.operator = operator

    # 同步更新 Fund.lifecycle_phase
    funds = db.query(Fund).filter(Fund.project_id == project_id).all()
    for f in funds:
        f.lifecycle_phase = target_phase

    db.flush()
    logger.info(f"项目 {project_id} 状态变更 {old_status} → {new_status}，经费阶段推进至 {target_phase}")


def _init_phases(db: Session, project_id: int) -> list:
    """为项目初始化 7 个阶段记录"""
    phases = []
    for i in range(1, 8):
        p = ProjectFundPhase(
            project_id=project_id,
            phase=i,
            status=PhaseStatus.NOT_STARTED.value,
        )
        db.add(p)
        phases.append(p)
    db.flush()
    return phases


class FundEventHandler:
    """向后兼容包装器 - 代理到 on_project_status_change 函数"""

    def __init__(self, db: Session = None):
        self.db = db

    def on_project_status_change(self, project_id: int, old_status: str, new_status: str, operator: str = ""):
        if self.db:
            return on_project_status_change(self.db, project_id, old_status, new_status, operator)
        return None

    @staticmethod
    def create(db: Session = None) -> "FundEventHandler":
        return FundEventHandler(db)
