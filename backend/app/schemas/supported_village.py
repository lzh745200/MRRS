"""帮扶村相关 Schema"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

# ==================== CRUD Schemas ====================


class SupportedVillageCreate(BaseModel):
    """创建帮扶村"""

    village_name: str = Field(..., min_length=1, max_length=100, description="帮扶村名称")
    province: Optional[str] = Field(None, max_length=50, description="省份")
    city: Optional[str] = Field(None, max_length=50, description="城市")
    county: Optional[str] = Field(None, max_length=50, description="县/市")
    township: Optional[str] = Field(None, max_length=50, description="乡镇")
    department: Optional[str] = Field(None, max_length=200, description="部门单位")
    support_unit: Optional[str] = Field(None, max_length=200, description="帮扶单位")
    region_scope: Optional[str] = Field(None, max_length=100, description="地区范围")
    is_three_regions: Optional[bool] = False
    is_border_area: Optional[bool] = False
    is_ethnic_area: Optional[bool] = False
    is_revolutionary_area: Optional[bool] = False
    is_key_county: Optional[bool] = False
    is_revitalization_tier: Optional[bool] = False
    is_provincial_demo: Optional[bool] = False
    is_hundred_village_demo: Optional[bool] = False
    is_tiered_development: Optional[bool] = False
    is_cross_province: Optional[bool] = False
    is_cross_city: Optional[bool] = False
    is_cross_unit_cooperation: Optional[bool] = False
    is_in_overall_plan: Optional[bool] = False
    honors: Optional[str] = Field(None, max_length=2000, description="表彰情况")
    sequence_no: Optional[int] = Field(None, ge=0, description="序号")
    latitude: Optional[float] = Field(None, ge=-90, le=90, description="纬度")
    longitude: Optional[float] = Field(None, ge=-180, le=180, description="经度")


class SupportedVillageUpdate(BaseModel):
    """更新帮扶村"""

    village_name: Optional[str] = Field(None, min_length=1, max_length=100, description="帮扶村名称")
    province: Optional[str] = Field(None, max_length=50, description="省份")
    city: Optional[str] = Field(None, max_length=50, description="城市")
    county: Optional[str] = Field(None, max_length=50, description="县/市")
    township: Optional[str] = Field(None, max_length=50, description="乡镇")
    department: Optional[str] = Field(None, max_length=200, description="部门单位")
    support_unit: Optional[str] = Field(None, max_length=200, description="帮扶单位")
    region_scope: Optional[str] = Field(None, max_length=100, description="地区范围")
    is_three_regions: Optional[bool] = None
    is_border_area: Optional[bool] = None
    is_ethnic_area: Optional[bool] = None
    is_revolutionary_area: Optional[bool] = None
    is_key_county: Optional[bool] = None
    is_revitalization_tier: Optional[bool] = None
    is_provincial_demo: Optional[bool] = None
    is_hundred_village_demo: Optional[bool] = None
    is_tiered_development: Optional[bool] = None
    is_cross_province: Optional[bool] = None
    is_cross_city: Optional[bool] = None
    is_cross_unit_cooperation: Optional[bool] = None
    is_in_overall_plan: Optional[bool] = None
    honors: Optional[str] = Field(None, max_length=2000, description="表彰情况")
    sequence_no: Optional[int] = Field(None, ge=0, description="序号")
    latitude: Optional[float] = Field(None, ge=-90, le=90, description="纬度")
    longitude: Optional[float] = Field(None, ge=-180, le=180, description="经度")
    # 过渡状态变更走 update_village 的管理员审批+审计分支（此前 schema 缺失该字段，
    # pydantic 静默丢弃导致分支不可达——bug#12）
    transition_status: Optional[str] = Field(
        None,
        description="过渡状态: none/entering/in_transition/exiting/completed",
    )


class VillagePopulationCreate(BaseModel):
    """创建人口数据

    H6：字段严格对齐 VillagePopulation 模型列（原 `households` 在模型上不存在，
    会被 `_save_section_data` 静默丢弃，实际列为 `total_households`）。
    """

    total_population: Optional[int] = Field(None, ge=0, description="总人数")
    total_households: Optional[int] = Field(None, ge=0, description="总户数")
    labor_force: Optional[int] = Field(None, ge=0, description="劳动力")
    migrant_workers: Optional[int] = Field(None, ge=0, description="外出务工人数")
    poverty_population: Optional[int] = Field(None, ge=0, description="脱贫人口")
    poverty_households: Optional[int] = Field(None, ge=0, description="脱贫户数")


class VillagePopulationUpdate(BaseModel):
    """更新人口数据（字段对齐 VillagePopulation 模型列，见 VillagePopulationCreate）"""

    total_population: Optional[int] = Field(None, ge=0, description="总人数")
    total_households: Optional[int] = Field(None, ge=0, description="总户数")
    labor_force: Optional[int] = Field(None, ge=0, description="劳动力")
    migrant_workers: Optional[int] = Field(None, ge=0, description="外出务工人数")
    poverty_population: Optional[int] = Field(None, ge=0, description="脱贫人口")
    poverty_households: Optional[int] = Field(None, ge=0, description="脱贫户数")


class VillageIncomeCreate(BaseModel):
    """创建收入数据

    H6：字段严格对齐 VillageIncome 模型列。原 `total_income` 在模型上不存在
    （模型仅有 per_capita_income / county_per_capita_income / collective_income），
    写入时会被静默丢弃，造成"以为保存成功实际未落库"。此处移除该幽灵字段并补齐
    county_per_capita_income，保持与模型单一事实源一致。
    """

    per_capita_income: Optional[float] = Field(None, ge=0, description="村人均纯收入(万元)")
    county_per_capita_income: Optional[float] = Field(None, ge=0, description="县区人均纯收入(万元)")
    collective_income: Optional[float] = Field(None, ge=0, description="村集体收入(万元)")


class VillageIncomeUpdate(BaseModel):
    """更新收入数据（字段对齐 VillageIncome 模型列，见 VillageIncomeCreate）"""

    per_capita_income: Optional[float] = Field(None, ge=0, description="村人均纯收入(万元)")
    county_per_capita_income: Optional[float] = Field(None, ge=0, description="县区人均纯收入(万元)")
    collective_income: Optional[float] = Field(None, ge=0, description="村集体收入(万元)")


class AggregateQuery(BaseModel):
    """聚合查询参数"""

    group_by: Optional[str] = None
    aggregate_field: Optional[str] = None
    aggregate_func: str = Field("count", min_length=1, max_length=20, description="聚合函数")
    year: Optional[int] = None
    filters: Optional[Dict[str, Any]] = None


# ==================== 原有 Schemas ====================


class ExportQuery(BaseModel):
    """导出查询参数"""

    year: Optional[int] = None
    village_ids: Optional[List[int]] = None
    include_sections: Optional[List[str]] = None
    format: str = Field("xlsx", min_length=1, max_length=10, description="导出格式")


class DrillDownQuery(BaseModel):
    """钻取查询参数"""

    dimension: str = Field(..., min_length=1, max_length=50, description="钻取维度")
    value: Optional[str] = Field(None, max_length=200, description="维度值")
    year: Optional[int] = None
    filters: Optional[Dict[str, Any]] = None


class ReportSubscriptionCreate(BaseModel):
    """创建报表订阅"""

    name: str = Field(..., min_length=1, max_length=100, description="订阅名称")
    report_type: str = Field(..., min_length=1, max_length=50, description="报表类型")
    format: str = Field("xlsx", min_length=1, max_length=10, description="导出格式")
    year: Optional[int] = None
    village_ids: Optional[List[int]] = None
    include_sections: Optional[List[str]] = None
    frequency: str = Field("weekly", min_length=1, max_length=20, description="发送频率")
    send_day: Optional[int] = Field(None, ge=0, le=31, description="发送日期")
    send_time: Optional[str] = Field(None, max_length=10, description="发送时间")
    email: Optional[str] = Field(None, max_length=100, description="接收邮箱（单机版保留兼容）")
    output_dir: Optional[str] = Field(None, max_length=500, description="本地输出目录（单机版）")
    output_format: str = Field("pdf", description="输出格式: pdf/excel")


class ReportSubscriptionUpdate(BaseModel):
    """更新报表订阅"""

    name: Optional[str] = Field(None, min_length=1, max_length=100, description="订阅名称")
    is_active: Optional[bool] = None
    frequency: Optional[str] = Field(None, min_length=1, max_length=20, description="发送频率")
    send_day: Optional[int] = Field(None, ge=0, le=31, description="发送日期")
    send_time: Optional[str] = Field(None, max_length=10, description="发送时间")
    email: Optional[str] = Field(None, max_length=100, description="接收邮箱")
    output_dir: Optional[str] = Field(None, max_length=500, description="本地输出目录")
    output_format: Optional[str] = Field(None, description="输出格式: pdf/excel")


class ReportSubscriptionResponse(BaseModel):
    """报表订阅响应"""

    id: int
    user_id: int
    name: str = ""
    report_type: str = ""
    format: str = "xlsx"
    frequency: str = "weekly"
    is_active: bool = True
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
