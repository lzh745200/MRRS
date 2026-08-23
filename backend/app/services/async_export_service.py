"""异步导出服务 — 大文件后台导出 + 进度追踪.

修复记录（2026-08-14，此前三个问题导致"导出不可用"）：
1. 异步任务只创建 ExportTask 记录、从不提交任务队列 → 任务永远 pending，
   下载永远报"导出任务正在处理中"；
2. 同步导出依赖调用方预置 query_params["items"]，但 API 从不传 → 导出空工作簿；
3. /async-export/reports 同样依赖 items → 报表导出为空文件。

现在：服务按实体类型真实查库（与 /export/* 端点同口径），
异步任务经 ``app.services.task_queue.task_queue`` 后台执行，
由独立数据库会话生成 Excel 文件、落盘并更新
ExportTask 状态（pending → processing → completed/failed）。
"""

import logging
import uuid as _uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.core.transaction import safe_commit
from app.models.export_task import ExportStatus, ExportTask
from app.services.export_service import ExcelExportService
from app.services.task_queue import task_queue

logger = logging.getLogger(__name__)

ASYNC_THRESHOLD = 5000  # 超过此记录数使用异步导出
MAX_EXPORT_ROWS = 10000

_ENTITY_MODELS = {
    "supported_villages": ("app.models.supported_village", "SupportedVillage"),
    "supported_village": ("app.models.supported_village", "SupportedVillage"),
    "projects": ("app.models.project", "Project"),
    "funds": ("app.models.fund", "Fund"),
    "schools": ("app.models.school", "School"),
    "policies": ("app.models.policy", "Policy"),
}

# 报表类型 → 导出实体（与 /export/report-word 的报表类型命名兼容）
_REPORT_TYPE_TO_ENTITY = {
    "village_summary": "supported_villages",
    "fund_analysis": "funds",
    "project_progress": "projects",
    "school_statistics": "schools",
    "annual_summary": "comprehensive",
    "comprehensive": "comprehensive",
    # 兼容旧别名
    "supported_villages": "supported_villages",
    "funds": "funds",
    "projects": "projects",
    "schools": "schools",
}


def _format_datetime(value: Any) -> str:
    """将日期/时间值格式化为字符串（导出用）。"""
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    return str(value)


def _get_export_dir() -> Path:
    """获取导出文件目录（不存在则创建）。"""
    from app.core.config import settings

    export_dir = Path(settings.EXPORT_DIR)
    export_dir.mkdir(parents=True, exist_ok=True)
    return export_dir


def _load_user(db: Session, user_id: Optional[int]):
    """按 user_id 加载用户（用于数据权限过滤；失败返回 None）。"""
    if not user_id:
        return None
    from app.models.user import User

    return db.query(User).filter(User.id == user_id).first()


def _fetch_village_records(db: Session, user: Any, params: Dict) -> List[Dict[str, Any]]:
    """真实查询帮扶村数据（与 /export/villages 同口径）。"""
    from app.core.data_permission import filter_by_data_scope
    from app.models.supported_village import SupportedVillage

    query = db.query(SupportedVillage).filter(SupportedVillage.is_active.is_(True))
    if user is not None:
        query = filter_by_data_scope(query, SupportedVillage, user, db=db)

    if params.get("keyword"):
        query = query.filter(SupportedVillage.village_name.contains(params["keyword"]))
    if params.get("status"):
        query = query.filter(SupportedVillage.transition_status == params["status"])
    if params.get("department"):
        query = query.filter(SupportedVillage.department == params["department"])
    if params.get("support_unit"):
        query = query.filter(SupportedVillage.support_unit == params["support_unit"])
    if params.get("village_name"):
        query = query.filter(SupportedVillage.village_name.contains(params["village_name"]))
    if params.get("region_scope"):
        query = query.filter(SupportedVillage.region_scope == params["region_scope"])
    if params.get("is_three_regions") is not None:
        query = query.filter(SupportedVillage.is_three_regions.is_(bool(params["is_three_regions"])))
    if params.get("is_border_area") is not None:
        query = query.filter(SupportedVillage.is_border_area.is_(bool(params["is_border_area"])))
    if params.get("is_revitalization_tier") is not None:
        query = query.filter(
            SupportedVillage.is_revitalization_tier.is_(bool(params["is_revitalization_tier"]))
        )

    villages = query.order_by(SupportedVillage.id).limit(MAX_EXPORT_ROWS).all()
    return [
        {
            "ID": v.id,
            "名称": v.name,
            "编码": v.sequence_no or "",
            "省份": v.province or "",
            "城市": v.city or "",
            "区县": v.county or "",
            "部门": v.department or "",
            "帮扶单位": v.support_unit or "",
            "状态": v.transition_status or "",
            "创建时间": _format_datetime(v.created_at),
        }
        for v in villages
    ]


def _fetch_fund_records(db: Session, user: Any, params: Dict) -> List[Dict[str, Any]]:
    """真实查询经费数据（与 /export/funds 同口径）。"""
    from app.core.data_permission import filter_by_data_scope
    from app.models.fund import Fund

    query = db.query(Fund).filter(Fund.is_active == True)  # noqa: E712
    if user is not None:
        query = filter_by_data_scope(query, Fund, user, db=db)

    if params.get("keyword"):
        query = query.filter(Fund.name.contains(params["keyword"]))
    if params.get("fund_type"):
        query = query.filter(Fund.type == params["fund_type"])
    if params.get("status"):
        query = query.filter(Fund.status == params["status"])

    funds = query.order_by(Fund.id.desc()).limit(MAX_EXPORT_ROWS).all()
    return [
        {
            "ID": f.id,
            "名称": f.name,
            "类型": f.type or "",
            "金额": f.amount,
            "来源": f.source or "",
            "用途": f.purpose or "",
            "状态": f.status,
            "经办人": f.operator or "",
            "使用日期": _format_datetime(f.date),
        }
        for f in funds
    ]


def _fetch_project_records(db: Session, user: Any, params: Dict) -> List[Dict[str, Any]]:
    """真实查询项目数据（与 /export/projects 同口径）。"""
    from app.core.data_permission import filter_by_data_scope
    from app.models.project import Project

    query = db.query(Project).filter(Project.is_active == True)  # noqa: E712
    if user is not None:
        query = filter_by_data_scope(query, Project, user, db=db)

    if params.get("keyword"):
        query = query.filter(Project.name.contains(params["keyword"]))
    if params.get("project_type"):
        query = query.filter(Project.type == params["project_type"])
    if params.get("status"):
        query = query.filter(Project.status == params["status"])

    projects = query.order_by(Project.id).limit(MAX_EXPORT_ROWS).all()
    return [
        {
            "ID": p.id,
            "名称": p.name,
            "编码": p.code,
            "类型": p.type or "",
            "状态": p.status,
            "预算": p.budget or 0,
            "进度": f"{p.progress or 0}%",
            "开始日期": _format_datetime(p.start_date),
            "结束日期": _format_datetime(p.end_date),
        }
        for p in projects
    ]


def _fetch_school_records(db: Session, user: Any, params: Dict) -> List[Dict[str, Any]]:
    """真实查询学校数据（与 /export/schools 同口径）。"""
    from app.core.data_permission import filter_by_data_scope
    from app.models.school import School

    query = db.query(School).filter(School.is_active == True)  # noqa: E712
    if user is not None:
        query = filter_by_data_scope(query, School, user, db=db)

    if params.get("keyword"):
        query = query.filter(School.name.contains(params["keyword"]))
    if params.get("school_type"):
        query = query.filter(School.type == params["school_type"])

    schools = query.order_by(School.id).limit(MAX_EXPORT_ROWS).all()
    return [
        {
            "ID": s.id,
            "名称": s.name,
            "编码": s.code,
            "类型": s.type or "",
            "城市": s.city or "",
            "学生数": s.student_count or 0,
            "教师数": s.teacher_count or 0,
            "状态": s.support_status.value if s.support_status else "",
        }
        for s in schools
    ]


_FETCHERS = {
    "supported_villages": "_fetch_village_records",
    "supported_village": "_fetch_village_records",
    "funds": "_fetch_fund_records",
    "projects": "_fetch_project_records",
    "schools": "_fetch_school_records",
}


def _get_fetcher(entity_type: str):
    """按实体类型获取记录查询函数（动态解析，便于测试替换）。"""
    name = _FETCHERS.get(entity_type, "_fetch_village_records")
    return globals()[name]


def _build_comprehensive_workbook(db: Session, user: Any) -> bytes:
    """生成综合报表工作簿（与 /export/comprehensive 同口径）。"""
    from sqlalchemy import func as sql_func

    from app.core.data_permission import filter_by_data_scope
    from app.models.fund import Fund
    from app.models.project import Project
    from app.models.school import School
    from app.models.supported_village import SupportedVillage
    from app.models.user import User

    users_count = db.query(User).count()
    village_q = db.query(SupportedVillage).filter(SupportedVillage.is_active.is_(True))
    if user is not None:
        village_q = filter_by_data_scope(village_q, SupportedVillage, user, db=db)
    villages_count = village_q.count()
    schools_count = db.query(School).filter(School.is_active == True).count()  # noqa: E712
    projects_count = db.query(Project).filter(Project.is_active == True).count()  # noqa: E712
    funds_count = db.query(Fund).filter(Fund.is_active == True).count()  # noqa: E712
    funds_sum = (
        db.query(sql_func.coalesce(sql_func.sum(Fund.amount), 0))
        .filter(Fund.is_active == True)  # noqa: E712
        .scalar()
    )

    summary = {
        "用户总数": users_count,
        "村庄总数": villages_count,
        "学校总数": schools_count,
        "项目总数": projects_count,
        "经费记录数": funds_count,
        "经费总金额": f"{float(funds_sum or 0):.2f}元",
        "生成时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    village_data = [
        {
            "ID": v.id,
            "名称": v.name,
            "人口": 0,
            "项目数": 0,
            "产业数": 0,
        }
        for v in village_q.order_by(SupportedVillage.id).limit(100).all()
    ]
    project_data = [
        {
            "ID": p.id,
            "名称": p.name,
            "状态": p.status,
            "预算": p.budget or 0,
            "进度": f"{p.progress or 0}%",
        }
        for p in db.query(Project).filter(Project.is_active == True).limit(100).all()  # noqa: E712
    ]
    fund_data = [
        {
            "ID": f.id,
            "名称": f.name,
            "金额": f.amount,
            "状态": f.status,
            "使用日期": _format_datetime(f.date),
        }
        for f in db.query(Fund).filter(Fund.is_active == True).limit(100).all()  # noqa: E712
    ]

    return ExcelExportService().export_comprehensive_report(
        summary, village_data, project_data, fund_data
    )


def _build_workbook(entity_type: str, records: List[Dict[str, Any]], db: Session) -> bytes:
    """按实体类型生成对应 Excel 工作簿。"""
    excel = ExcelExportService()
    if entity_type in ("supported_villages", "supported_village"):
        return excel.export_village_list(records)
    if entity_type == "funds":
        return excel.export_fund_list(records)
    if entity_type == "projects":
        return excel.export_project_list(records)
    if entity_type == "schools":
        return excel.export_school_list(records)
    # 未知类型回退为村庄列表格式（与旧行为一致）
    return excel.export_village_list(records)


def _run_export_task(task_id: str) -> None:
    """后台导出执行体：独立会话查数据、生成文件、落盘并更新任务状态。

    该函数在任务队列的工作线程中运行（同步函数，由 run_in_executor 调度）。
    """
    from app.core.database import SessionLocal

    db = SessionLocal()
    try:
        task = db.query(ExportTask).filter(ExportTask.task_id == task_id).first()
        if not task:
            logger.warning("异步导出任务不存在 task_id=%s", task_id)
            return

        task.status = ExportStatus.PROCESSING.value
        task.started_at = datetime.now(timezone.utc)
        safe_commit(db)

        user = _load_user(db, task.user_id)
        params = task.query_params or {}
        entity_type = _REPORT_TYPE_TO_ENTITY.get(task.export_type, task.export_type)

        if entity_type == "comprehensive":
            content = _build_comprehensive_workbook(db, user)
            record_count = 0  # 综合报表按"摘要+明细"计，记录数不适用
        else:
            fetcher = _get_fetcher(entity_type)
            records = fetcher(db, user, params)
            content = _build_workbook(entity_type, records, db)
            record_count = len(records)

        export_dir = _get_export_dir()
        file_name = task.file_name or f"{task.export_type}_{task_id}.xlsx"
        file_path = export_dir / f"{task_id}_{file_name}"
        file_path.write_bytes(content)

        task.file_path = str(file_path)
        task.file_name = file_name
        task.file_size = len(content)
        task.record_count = record_count
        task.status = ExportStatus.COMPLETED.value
        task.completed_at = datetime.now(timezone.utc)
        task.error_message = None
        safe_commit(db)
        logger.info("异步导出完成 task_id=%s file=%s size=%d", task_id, file_path, len(content))
    except Exception as exc:  # noqa: BLE001 — 任务级兜底，必须回写失败状态
        logger.exception("异步导出任务执行失败 task_id=%s", task_id)
        try:
            task = db.query(ExportTask).filter(ExportTask.task_id == task_id).first()
            if task:
                task.status = ExportStatus.FAILED.value
                task.error_message = str(exc)
                task.completed_at = datetime.now(timezone.utc)
                safe_commit(db)
        except Exception:
            logger.exception("异步导出任务失败状态回写失败 task_id=%s", task_id)
    finally:
        db.close()


class AsyncExportService:
    """异步导出服务：封装导出任务的创建、查询、下载与真实数据导出。"""

    def __init__(self, db: Session):
        self.db = db

    # ── 阈值判断 ──

    def should_use_async(self, entity_type: str, query_params: Dict) -> bool:
        count = self.estimate_record_count(entity_type, query_params)
        return count > ASYNC_THRESHOLD

    # ── 记录数估算 ──

    def estimate_record_count(self, entity_type: str, query_params: Dict) -> int:
        _ = query_params  # 未来可用于构建筛选条件
        models = _ENTITY_MODELS
        if entity_type not in models:
            return 0
        module_path, model_name = models[entity_type]
        import importlib

        try:
            mod = importlib.import_module(module_path)
            model = getattr(mod, model_name)
            return self.db.query(model).count()
        except Exception as e:
            logger.warning("estimate_record_count failed: %s", e)
            return 0

    # ── 同步导出（真实查库）──

    def export_supported_villages_sync(
        self, db: Session, user: Any, query_params: Dict
    ) -> Tuple[bytes, str, int]:
        """同步导出帮扶村数据，返回 (content, filename, count)。"""
        records = _fetch_village_records(db, user, query_params or {})
        content = ExcelExportService().export_village_list(records)
        filename = f"帮扶村导出_{datetime.now().strftime('%Y%m%d%H%M%S')}.xlsx"
        return content, filename, len(records)

    def export_report_sync(
        self,
        report_type: str,
        query_params: Dict,
        db: Session,
        user: Any,
    ) -> Tuple[bytes, str, int]:
        """按报表类型真实查库导出，返回 (content, filename, count)。"""
        entity_type = _REPORT_TYPE_TO_ENTITY.get(report_type, report_type)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{report_type}_report_{ts}.xlsx"

        if entity_type == "comprehensive":
            content = _build_comprehensive_workbook(db, user)
            return content, filename, 0

        fetcher = _get_fetcher(entity_type)
        records = fetcher(db, user, query_params or {})
        content = _build_workbook(entity_type, records, db)
        return content, filename, len(records)

    # ── 异步导出 ──

    async def export_supported_villages_async(
        self,
        user_id: int,
        query_params: Dict,
    ) -> ExportTask:
        """创建异步导出任务并提交到任务队列，返回 ExportTask 记录。"""
        task_id = str(_uuid.uuid4())
        record_count = self.estimate_record_count("supported_villages", query_params)
        export_task = ExportTask(
            user_id=user_id,
            task_id=task_id,
            export_type="supported_villages",
            query_params=query_params,
            file_name=f"帮扶村导出_{datetime.now().strftime('%Y%m%d%H%M%S')}.xlsx",
            file_size=0,
            record_count=record_count,
            status=ExportStatus.PENDING.value,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
        )
        self.db.add(export_task)
        safe_commit(self.db)
        self.db.refresh(export_task)

        # 提交后台执行（队列未启动时自动启动 worker）
        await task_queue.submit(
            _run_export_task, task_id, name="async-export-villages"
        )
        return export_task

    # ── 任务查询 ──

    def get_export_task(self, task_id: str) -> Optional[ExportTask]:
        return self.db.query(ExportTask).filter(ExportTask.task_id == task_id).first()

    def get_export_file(self, task_id: str) -> Optional[Tuple[bytes, str]]:
        task = self.db.query(ExportTask).filter(ExportTask.task_id == task_id).first()
        if not task or not task.file_path:
            return None
        try:
            with open(task.file_path, "rb") as f:
                return f.read(), task.file_name
        except FileNotFoundError:
            return None

    def get_user_export_tasks(
        self,
        user_id: int,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None,
    ) -> Tuple[List[ExportTask], int]:
        q = self.db.query(ExportTask).filter(ExportTask.user_id == user_id)
        if status:
            q = q.filter(ExportTask.status == status)
        total = q.count()
        tasks = (
            q.order_by(ExportTask.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return tasks, total
