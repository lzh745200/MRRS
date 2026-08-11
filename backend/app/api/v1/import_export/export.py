from datetime import datetime
from typing import Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.permission_utils import require_admin
from app.core.security import get_current_user
from app.models.project import Fund, Project
from app.models.school import School
from app.models.user import User
from app.models.village import Village
from app.services.export_service import export_service
from app.services.report_export_service import report_export_service

router = APIRouter(prefix="/export", tags=["数据导出"])

_XLSX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
MAX_EXPORT_ROWS = 10000


def format_datetime(dt):
    if dt is None:
        return ""
    if isinstance(dt, datetime):
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    return str(dt)


@router.get("/users")
async def export_users(
    format: str = Query("xlsx", description="导出格式: xlsx"),
    keyword: Optional[str] = None,
    is_active: Optional[bool] = None,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """导出用户列表（含手机号等PII, 仅管理员）"""
    require_admin(current_user, error_message="仅管理员可导出用户数据")
    query = db.query(User)

    if keyword:
        query = query.filter(User.username.contains(keyword) | User.full_name.contains(keyword))
    if is_active is not None:
        query = query.filter(User.is_active == is_active)

    users = query.limit(MAX_EXPORT_ROWS).all()

    user_data = [
        {
            "ID": u.id,
            "用户名": u.username,
            "邮箱": u.email or "",
            "姓名": u.full_name or "",
            "角色": u.role if u.role else "无",
            "状态": "启用" if u.is_active else "禁用",
            "最后登录": format_datetime(u.last_login),
        }
        for u in users
    ]

    if format == "xlsx":
        content = export_service.export_user_list(user_data)
        filename = f"用户列表_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    else:
        raise HTTPException(status_code=400, detail="不支持的导出格式")

    return Response(
        content=content,
        media_type=_XLSX_MEDIA_TYPE,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )


@router.get("/villages")
async def export_villages(
    format: str = Query("xlsx", description="导出格式: xlsx"),
    keyword: Optional[str] = None,
    status: Optional[str] = None,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(Village)

    if keyword:
        query = query.filter(Village.name.contains(keyword))
    if status:
        query = query.filter(Village.status == status)

    villages = query.limit(MAX_EXPORT_ROWS).all()

    village_data = [
        {
            "ID": v.id,
            "名称": v.name,
            "编码": v.code,
            "省份": v.province or "",
            "城市": v.city or "",
            "区县": v.county or "",
            "人口": v.total_population or 0,
            "状态": v.status,
            "创建时间": format_datetime(v.created_at),
        }
        for v in villages
    ]

    if format == "xlsx":
        content = export_service.export_village_list(village_data)
        filename = f"村庄列表_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    else:
        raise HTTPException(status_code=400, detail="不支持的导出格式")

    return Response(
        content=content,
        media_type=_XLSX_MEDIA_TYPE,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )


@router.get("/schools")
async def export_schools(
    format: str = Query("xlsx", description="导出格式: xlsx"),
    keyword: Optional[str] = None,
    school_type: Optional[str] = None,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_admin(current_user, error_message="仅管理员可导出数据")
    query = db.query(School)

    if keyword:
        query = query.filter(School.name.contains(keyword))
    if school_type:
        query = query.filter(School.type == school_type)

    schools = query.limit(MAX_EXPORT_ROWS).all()

    school_data = [
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

    if format == "xlsx":
        content = export_service.export_school_list(school_data)
        filename = f"学校列表_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    else:
        raise HTTPException(status_code=400, detail="不支持的导出格式")

    return Response(
        content=content,
        media_type=_XLSX_MEDIA_TYPE,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )


@router.get("/projects")
async def export_projects(
    format: str = Query("xlsx", description="导出格式: xlsx"),
    keyword: Optional[str] = None,
    project_type: Optional[str] = None,
    status: Optional[str] = None,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_admin(current_user, error_message="仅管理员可导出数据")
    query = db.query(Project)

    if keyword:
        query = query.filter(Project.name.contains(keyword))
    if project_type:
        query = query.filter(Project.type == project_type)
    if status:
        query = query.filter(Project.status == status)

    projects = query.limit(MAX_EXPORT_ROWS).all()

    project_data = [
        {
            "ID": p.id,
            "名称": p.name,
            "编码": p.code,
            "类型": p.type or "",
            "状态": p.status,
            "预算": p.budget or 0,
            "进度": f"{p.progress or 0}%",
            "开始日期": format_datetime(p.start_date),
            "结束日期": format_datetime(p.end_date),
        }
        for p in projects
    ]

    if format == "xlsx":
        content = export_service.export_project_list(project_data)
        filename = f"项目列表_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    else:
        raise HTTPException(status_code=400, detail="不支持的导出格式")

    return Response(
        content=content,
        media_type=_XLSX_MEDIA_TYPE,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )


@router.get("/funds")
async def export_funds(
    format: str = Query("xlsx", description="导出格式: xlsx"),
    keyword: Optional[str] = None,
    fund_type: Optional[str] = None,
    status: Optional[str] = None,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_admin(current_user, error_message="仅管理员可导出数据")
    query = db.query(Fund)

    if keyword:
        query = query.filter(Fund.name.contains(keyword))
    if fund_type:
        query = query.filter(Fund.type == fund_type)
    if status:
        query = query.filter(Fund.status == status)

    funds = query.limit(MAX_EXPORT_ROWS).all()

    fund_data = [
        {
            "ID": f.id,
            "名称": f.name,
            "类型": f.type or "",
            "金额": f.amount,
            "来源": f.source or "",
            "用途": f.purpose or "",
            "状态": f.status,
            "经办人": f.operator or "",
            "使用日期": format_datetime(f.date),
        }
        for f in funds
    ]

    if format == "xlsx":
        content = export_service.export_fund_list(fund_data)
        filename = f"经费列表_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    else:
        raise HTTPException(status_code=400, detail="不支持的导出格式")

    return Response(
        content=content,
        media_type=_XLSX_MEDIA_TYPE,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )


@router.get("/comprehensive")
async def export_comprehensive_report(
    format: str = Query("xlsx", description="导出格式: xlsx"),
    year: Optional[int] = None,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    users_count = db.query(User).count()
    villages_count = db.query(Village).count()
    schools_count = db.query(School).count()
    projects_count = db.query(Project).count()
    from sqlalchemy import func as sql_func
    funds_count = db.query(Fund).count()
    funds_sum = db.query(sql_func.coalesce(sql_func.sum(Fund.amount), 0)).scalar()

    summary = {
        "用户总数": users_count,
        "村庄总数": villages_count,
        "学校总数": schools_count,
        "项目总数": projects_count,
        "经费记录数": funds_count,
        "经费总金额": f"{funds_sum:.2f}元",
        "生成时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    villages = db.query(Village).limit(100).all()
    village_data = [
        {
            "ID": v.id,
            "名称": v.name,
            "人口": v.total_population or 0,
            "项目数": 0,
            "产业数": 0,
        }
        for v in villages
    ]

    projects = db.query(Project).limit(100).all()
    project_data = [
        {
            "ID": p.id,
            "名称": p.name,
            "状态": p.status,
            "预算": p.budget or 0,
            "进度": f"{p.progress or 0}%",
        }
        for p in projects
    ]

    funds = db.query(Fund).limit(100).all()
    fund_data = [
        {
            "ID": f.id,
            "名称": f.name,
            "金额": f.amount,
            "状态": f.status,
            "使用日期": format_datetime(f.date),
        }
        for f in funds
    ]

    if format == "xlsx":
        content = export_service.export_comprehensive_report(summary, village_data, project_data, fund_data)
        filename = f"综合报表_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    else:
        raise HTTPException(status_code=400, detail="不支持的导出格式")

    from fastapi.responses import Response

    return Response(
        content=content,
        media_type=_XLSX_MEDIA_TYPE,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )


# ==================== 公文报告导出（Word / PDF）====================

_DOCX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
_PDF_MEDIA_TYPE = "application/pdf"

_REPORT_TYPE_MAP = {
    "summary": ("年度帮扶工作总结", "docx"),
    "fund_detail": ("帮扶资金拨付明细表", "docx"),
    "project_progress": ("帮扶项目进度统计表", "docx"),
    "school_statistics": ("帮扶学校统计表", "docx"),
    "village_summary": ("帮扶村年度汇总表", "docx"),
    "annual_summary": ("年度综合总结报告", "docx"),
}


@router.get("/report-word")
async def export_report_word(
    report_type: str = Query(..., description="报告类型: summary / fund_detail / project_progress"),
    year: Optional[int] = Query(None, description="年度，默认当前年"),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    导出 Word 格式公文报告
    """
    require_admin(current_user, error_message="仅管理员可导出数据")

    if report_type not in _REPORT_TYPE_MAP:
        raise HTTPException(status_code=400, detail=f"不支持的报告类型: {report_type}")

    if report_type == "summary":
        data = report_export_service.generate_summary_report_data(db, year)
    elif report_type == "fund_detail":
        data = report_export_service.generate_fund_detail_report_data(db, year)
    elif report_type == "project_progress":
        data = report_export_service.generate_project_progress_report_data(db, year)
    elif report_type == "school_statistics":
        data = report_export_service.generate_school_statistics_report_data(db, year)
    elif report_type == "village_summary":
        data = report_export_service.generate_village_summary_report_data(db, year)
    else:
        data = report_export_service.generate_annual_summary_report_data(db, year)

    content = report_export_service.export_word(report_type, data)
    filename = f"{_REPORT_TYPE_MAP[report_type][0]}_{data['year']}.docx"

    return Response(
        content=content,
        media_type=_DOCX_MEDIA_TYPE,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )


@router.get("/report-pdf")
async def export_report_pdf(
    report_type: str = Query(..., description="报告类型: summary / fund_detail / project_progress"),
    year: Optional[int] = Query(None, description="年度，默认当前年"),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    导出 PDF 格式公文报告
    """
    if report_type not in _REPORT_TYPE_MAP:
        raise HTTPException(status_code=400, detail=f"不支持的报告类型: {report_type}")

    if report_type == "summary":
        data = report_export_service.generate_summary_report_data(db, year)
    elif report_type == "fund_detail":
        data = report_export_service.generate_fund_detail_report_data(db, year)
    elif report_type == "project_progress":
        data = report_export_service.generate_project_progress_report_data(db, year)
    elif report_type == "school_statistics":
        data = report_export_service.generate_school_statistics_report_data(db, year)
    elif report_type == "village_summary":
        data = report_export_service.generate_village_summary_report_data(db, year)
    else:
        data = report_export_service.generate_annual_summary_report_data(db, year)

    content = report_export_service.export_pdf(report_type, data)
    filename = f"{_REPORT_TYPE_MAP[report_type][0]}_{data['year']}.pdf"

    return Response(
        content=content,
        media_type=_PDF_MEDIA_TYPE,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )
