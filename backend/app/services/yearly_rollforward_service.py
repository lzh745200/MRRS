"""年度数据滚动填报服务（复制上年 + 逐字段差异 + 批量沿用）。

口径与既有年度接口一致：
- 板块白名单：YEARLY_SECTION_MODELS 的 key（population/income/force-investment/
  industry/infrastructure/party-building/medical/consumption/employment/education/committee），
  与 GET /supported-villages/{id}/yearly/{year} 返回的 section key 完全一致；
  批量沿用只接受白名单内的板块，未知板块由 normalize_section_keys 抛
  UnknownSectionError（API 层转 400）。
- 字段白名单：只写板块模型的业务列；id/supported_village_id/year/created_at/updated_at
  元数据列永不参与沿用（_SKIP_FIELDS）。
- 空值判定（_is_empty）：None、空白字符串、数值 0 视为“空”
  —— 板块模型数值列的默认值就是 0，即“未填报”；布尔 False 同样视为空。
- 写入语义（二选一，由 overwrite 显式选择，前端二次确认后提交）：
  * 默认 overwrite=False（fill_empty / 只填空）：仅当本年度字段为空、上年字段有值时写入；
    本年度已有非空值一律保留，不覆盖。
  * overwrite=True（覆盖）：所选板块中上年有值的字段覆盖本年度值。
- 事务原子：所有板块在同一 Session 事务内写入，由 API 层统一 safe_commit；
  任一板块失败由 API 层回滚，不落半套数据。
- 数据域：所有查询强制 supported_village_id == village_id，跨村不串数据；
  村庄可见性由 API 层 _get_village_or_404 统一校验（与其它年度接口同口径）。
- 无上年数据：不抛异常、不写库，返回 hasPreviousData=False 与友好 message。
"""

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.supported_village import (
    ConsumptionSupport,
    EducationSupport,
    EmploymentSupport,
    ForceInvestment,
    IndustrySupport,
    InfrastructureImprovement,
    MedicalSupport,
    PartyBuildingSupport,
    VillageCommitteeInfo,
    VillageCommitteeMember,
    VillageIncome,
    VillagePopulation,
)
from app.utils.common import dict_keys_to_camel

logger = logging.getLogger(__name__)

# ── 板块白名单（与既有 GET /yearly/{year} 的 section key 单一映射源）──
YEARLY_SECTION_MODELS: Dict[str, Any] = {
    "population": VillagePopulation,
    "income": VillageIncome,
    "force-investment": ForceInvestment,
    "industry": IndustrySupport,
    "infrastructure": InfrastructureImprovement,
    "party-building": PartyBuildingSupport,
    "medical": MedicalSupport,
    "consumption": ConsumptionSupport,
    "employment": EmploymentSupport,
    "education": EducationSupport,
    "committee": VillageCommitteeInfo,
}

# 板块中文标题（前端「从上年复制」弹窗分组展示用）
YEARLY_SECTION_TITLES: Dict[str, str] = {
    "population": "人口数据",
    "income": "收入数据",
    "force-investment": "力量投入",
    "industry": "产业帮扶",
    "infrastructure": "基础设施",
    "party-building": "党建帮扶",
    "medical": "医疗帮扶",
    "consumption": "消费帮扶",
    "employment": "就业帮扶",
    "education": "教育帮扶",
    "committee": "村委会情况",
}

# 不参与沿用的元数据列（主键/外键/年度/审计时间戳/增量同步版本号）
# sync_version 是 TimestampMixin 的增量同步元数据（before_update 自增），
# 复制它既无业务意义，也会干扰多机同步的版本判定，故一并排除。
_SKIP_FIELDS = frozenset({
    "id", "supported_village_id", "year", "created_at", "updated_at", "sync_version",
})

# 村委会成员可沿用字段（子表不是板块模型列，单独白名单）
_MEMBER_FIELDS = ("name", "position", "phone", "is_veteran", "remark")

# 字段差异状态：copy=可沿用，keep=本年度已有值保留，blank=上年空缺需重填
STATUS_COPY = "copy"
STATUS_KEEP = "keep"
STATUS_BLANK = "blank"


class RollforwardError(ValueError):
    """滚动沿用请求校验错误（API 层统一转 400）。"""


class UnknownSectionError(RollforwardError):
    """section_keys 含白名单之外的板块。"""


class InvalidFromYearError(RollforwardError):
    """来源年份与目标年份相同（无意义复制）。"""


def _is_empty(value: Any) -> bool:
    """判断字段是否为空（未填报）。

    None / 空白字符串 / 数值 0 / 布尔 False 视为空；其余（含非零数值、非空字符串、
    列表等）视为有值。数值 0 视为空是业务口径：板块模型数值列默认值即 0，
    表示“未填报”，否则本年度默认 0 会把所有可沿用字段误判为“已有值”。
    """
    if value is None:
        return True
    if isinstance(value, bool):
        return not value
    if isinstance(value, (int, float)):
        return value == 0
    if isinstance(value, str):
        return not value.strip()
    return False


def _field_label(column: Any) -> str:
    """列的中文标签：优先 Column.comment，缺失时回退列名。"""
    comment = getattr(column, "comment", None)
    return comment.strip() if comment else column.name


def _field_columns(model: Any) -> List[Any]:
    """板块模型中参与沿用的业务列（剔除元数据列）。"""
    return [column for column in model.__table__.columns if column.name not in _SKIP_FIELDS]


def _field_status(has_previous: bool, has_current: bool) -> str:
    """计算单字段差异状态。"""
    if not has_previous:
        return STATUS_BLANK
    if has_current:
        return STATUS_KEEP
    return STATUS_COPY


def _load_row(db: Session, model: Any, village_id: int, year: int) -> Optional[Any]:
    """按（村庄, 年份）取板块行；强制村庄过滤，跨村不串数据。"""
    return (
        db.query(model)
        .filter(model.supported_village_id == village_id, model.year == year)
        .first()
    )


def _load_members(db: Session, committee_row: Optional[Any]) -> List[VillageCommitteeMember]:
    """读取村委会成员列表（按 id 稳定排序）。"""
    if committee_row is None or committee_row.id is None:
        return []
    return (
        db.query(VillageCommitteeMember)
        .filter(VillageCommitteeMember.committee_info_id == committee_row.id)
        .order_by(VillageCommitteeMember.id)
        .all()
    )


def _members_snapshot(db: Session, committee_row: Optional[Any]) -> List[Dict[str, Any]]:
    """村委会成员快照（内部 snake_case 字典，供差异展示与按白名单写库）。"""
    return [
        {
            "name": member.name,
            "position": member.position,
            "phone": member.phone,
            "is_veteran": member.is_veteran,
            "remark": member.remark,
        }
        for member in _load_members(db, committee_row)
    ]


def _replace_members(
    db: Session,
    committee_row: Any,
    village_id: int,
    members: List[Dict[str, Any]],
) -> None:
    """整体替换村委会成员（删除旧成员 → 按成员白名单写入新成员）。"""
    db.query(VillageCommitteeMember).filter(
        VillageCommitteeMember.committee_info_id == committee_row.id
    ).delete()
    for member in members:
        db.add(
            VillageCommitteeMember(
                committee_info_id=committee_row.id,
                supported_village_id=village_id,
                **{field: member.get(field) for field in _MEMBER_FIELDS},
            )
        )


def _members_meta(
    previous_members: List[Dict[str, Any]],
    current_members: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """村委会成员差异元信息（与普通字段同构，status 沿用三态）。"""
    has_previous = bool(previous_members)
    has_current = bool(current_members)
    return {
        "field": "members",
        "label": "村委会成员",
        "previousValue": [dict_keys_to_camel(member) for member in previous_members],
        "currentValue": [dict_keys_to_camel(member) for member in current_members],
        "hasPreviousValue": has_previous,
        "hasCurrentValue": has_current,
        "status": _field_status(has_previous, has_current),
    }


def normalize_section_keys(section_keys: List[str]) -> List[str]:
    """校验并规范化板块白名单。

    - 去重保序；
    - 兼容前端内部下划线 key（force_investment/party_building → 连字符）；
    - 空列表 / 含未知板块 / 非字符串项 → 抛 RollforwardError（子类）。
    """
    if not section_keys:
        raise RollforwardError("section_keys 不能为空")
    normalized: List[str] = []
    unknown: List[Any] = []
    for raw in section_keys:
        if not isinstance(raw, str) or not raw.strip():
            unknown.append(raw)
            continue
        key = raw.strip().replace("_", "-")
        if key not in YEARLY_SECTION_MODELS:
            unknown.append(raw)
        elif key not in normalized:
            normalized.append(key)
    if unknown:
        raise UnknownSectionError(
            "未知的年度数据板块: "
            + ", ".join(str(item) for item in unknown)
            + "；可用板块: "
            + ", ".join(YEARLY_SECTION_MODELS)
        )
    return normalized


def build_prefill(
    db: Session,
    *,
    village_id: int,
    year: int,
    from_year: int,
) -> Dict[str, Any]:
    """构建「从上年复制」预填数据与逐字段差异元信息。

    返回结构（camelCase）：villageId/year/fromYear/hasPreviousData/sections/summary/message；
    sections[*].fields[*] 逐字段给出 previousValue/currentValue/hasPreviousValue/
    hasCurrentValue/status，status 为 copy（可沿用）/keep（本年度已有值保留）/
    blank（上年空缺需重填）；村委会板块额外附带 members 虚拟字段（成员子表差异）。
    """
    sections: List[Dict[str, Any]] = []
    copyable_total = 0
    kept_total = 0
    blank_total = 0
    available_sections = 0
    for section_key, model in YEARLY_SECTION_MODELS.items():
        previous_row = _load_row(db, model, village_id, from_year)
        current_row = _load_row(db, model, village_id, year)
        fields: List[Dict[str, Any]] = []
        copyable = 0
        kept = 0
        blank = 0
        for column in _field_columns(model):
            previous_value = getattr(previous_row, column.name) if previous_row is not None else None
            current_value = getattr(current_row, column.name) if current_row is not None else None
            has_previous = previous_row is not None and not _is_empty(previous_value)
            has_current = current_row is not None and not _is_empty(current_value)
            status = _field_status(has_previous, has_current)
            if status == STATUS_COPY:
                copyable += 1
            elif status == STATUS_KEEP:
                kept += 1
            else:
                blank += 1
            fields.append({
                "field": column.name,
                "label": _field_label(column),
                "previousValue": previous_value,
                "currentValue": current_value,
                "hasPreviousValue": has_previous,
                "hasCurrentValue": has_current,
                "status": status,
            })
        if model is VillageCommitteeInfo:
            member_meta = _members_meta(
                _members_snapshot(db, previous_row),
                _members_snapshot(db, current_row),
            )
            if member_meta["status"] == STATUS_COPY:
                copyable += 1
            elif member_meta["status"] == STATUS_KEEP:
                kept += 1
            else:
                blank += 1
            fields.append(member_meta)
        sections.append({
            "key": section_key,
            "title": YEARLY_SECTION_TITLES[section_key],
            "hasPreviousData": previous_row is not None,
            "fields": fields,
            "copyableCount": copyable,
            "keptCount": kept,
            "blankCount": blank,
        })
        if previous_row is not None:
            available_sections += 1
        copyable_total += copyable
        kept_total += kept
        blank_total += blank

    has_previous = available_sections > 0
    if not has_previous:
        message = f"{from_year} 年没有可沿用的年度数据，所有板块需手工填写"
    elif copyable_total == 0 and kept_total == 0:
        message = f"{from_year} 年虽存在记录但没有可沿用的有效字段，请手工填写"
    elif copyable_total == 0:
        message = (
            f"{from_year} 年的字段本年度均已填写"
            f"（保留 {kept_total} 项本年度值），无需沿用"
        )
    else:
        message = (
            f"可从 {from_year} 年沿用 {copyable_total} 项字段到 {year} 年"
            f"（{available_sections} 个板块有上年数据，本年度已填写 {kept_total} 项将保留）"
        )
    return {
        "villageId": village_id,
        "year": year,
        "fromYear": from_year,
        "hasPreviousData": has_previous,
        "sections": sections,
        "summary": {
            "sectionCount": len(sections),
            "availableSectionCount": available_sections,
            "copyableFieldCount": copyable_total,
            "keptFieldCount": kept_total,
            "blankFieldCount": blank_total,
        },
        "message": message,
    }


def _apply_section(
    db: Session,
    *,
    model: Any,
    previous_row: Any,
    village_id: int,
    year: int,
    overwrite: bool,
) -> Dict[str, Any]:
    """沿用单个板块：创建/复用本年度行，按字段白名单写入。

    返回 {"created", "writtenFields", "keptFields", "memberCount"}。
    """
    current_row = _load_row(db, model, village_id, year)
    created = current_row is None
    if created:
        current_row = model()
        current_row.supported_village_id = village_id
        current_row.year = year
        db.add(current_row)
    written_fields: List[str] = []
    kept_fields: List[str] = []
    for column in _field_columns(model):
        previous_value = getattr(previous_row, column.name)
        if _is_empty(previous_value):
            continue
        if not overwrite and not _is_empty(getattr(current_row, column.name)):
            kept_fields.append(column.name)
            continue
        setattr(current_row, column.name, previous_value)
        written_fields.append(column.name)
    member_count = 0
    if model is VillageCommitteeInfo:
        previous_members = _members_snapshot(db, previous_row)
        if previous_members:
            current_members = _members_snapshot(db, current_row)
            if not overwrite and current_members:
                kept_fields.append("members")
            else:
                if current_row.id is None:
                    db.flush()
                _replace_members(db, current_row, village_id, previous_members)
                written_fields.append("members")
                member_count = len(previous_members)
    return {
        "created": created,
        "writtenFields": written_fields,
        "keptFields": kept_fields,
        "memberCount": member_count,
    }


def apply_rollforward(
    db: Session,
    *,
    village_id: int,
    year: int,
    from_year: int,
    section_keys: List[str],
    overwrite: bool = False,
) -> Dict[str, Any]:
    """批量沿用上年年度数据（一次提交多个板块，调用方统一 commit 保证原子）。

    overwrite=False（默认）只填空、不覆盖本年度已有非空值；overwrite=True
    以所选板块的上年值覆盖本年度值（二选一语义，见模块 docstring）。
    无上年数据的板块记入 skippedSections 并继续处理其余板块；全都没有上年数据时
    返回 hasPreviousData=False、appliedFields=0，不写库也不抛异常。
    """
    if from_year == year:
        raise InvalidFromYearError("来源年份和目标年份不能相同")
    normalized = normalize_section_keys(section_keys)
    sections: Dict[str, Any] = {}
    created_sections: List[str] = []
    applied_sections: List[str] = []
    skipped_sections: List[Dict[str, str]] = []
    applied_fields = 0
    kept_fields = 0
    for section_key in normalized:
        model = YEARLY_SECTION_MODELS[section_key]
        previous_row = _load_row(db, model, village_id, from_year)
        if previous_row is None:
            skipped_sections.append({"section": section_key, "reason": "no_previous_data"})
            continue
        stats = _apply_section(
            db,
            model=model,
            previous_row=previous_row,
            village_id=village_id,
            year=year,
            overwrite=overwrite,
        )
        sections[section_key] = stats
        if stats["created"]:
            created_sections.append(section_key)
        if stats["writtenFields"]:
            applied_sections.append(section_key)
        applied_fields += len(stats["writtenFields"])
        kept_fields += len(stats["keptFields"])
    return {
        "villageId": village_id,
        "year": year,
        "fromYear": from_year,
        "mode": "overwrite" if overwrite else "fill_empty",
        "hasPreviousData": bool(sections),
        "appliedFields": applied_fields,
        "keptFields": kept_fields,
        "createdSections": created_sections,
        "appliedSections": applied_sections,
        "skippedSections": skipped_sections,
        "sections": sections,
    }
