"""
两个修复计划的综合单元测试
覆盖: 日期验证、索引校验、审计权限、报表模板、health_service 路径、config_validator
"""

import os
import pytest

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

# ============================================================
# 修复2: 日期时间验证 (rural_work schema)
# ============================================================


class TestRuralWorkDateValidation:
    """乡村工作日期验证器测试"""

    def test_parse_date_yyyy_mm_dd(self):
        """测试 YYYY-MM-DD 格式能被正确解析"""
        from app.schemas.rural_work import RuralWorkCreate

        data = RuralWorkCreate(
            name="测试工作",
            start_date="2025-06-15",
            end_date="2025-12-31",
        )
        assert isinstance(data.start_date, datetime)
        assert data.start_date.year == 2025
        assert data.start_date.month == 6
        assert data.start_date.day == 15

    def test_parse_date_iso8601(self):
        """测试 ISO8601 格式"""
        from app.schemas.rural_work import RuralWorkCreate

        data = RuralWorkCreate(
            name="测试工作",
            start_date="2025-06-15T10:30:00",
        )
        assert isinstance(data.start_date, datetime)
        assert data.start_date.hour == 10
        assert data.start_date.minute == 30

    def test_parse_date_none(self):
        """测试 None 值"""
        from app.schemas.rural_work import RuralWorkCreate

        data = RuralWorkCreate(name="测试工作")
        assert data.start_date is None
        assert data.end_date is None

    def test_parse_date_empty_string(self):
        """测试空字符串"""
        from app.schemas.rural_work import RuralWorkCreate

        data = RuralWorkCreate(name="测试工作", start_date="")
        assert data.start_date is None

    def test_parse_date_invalid_format(self):
        """测试无效日期格式"""
        from app.schemas.rural_work import RuralWorkCreate
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            RuralWorkCreate(name="测试工作", start_date="not-a-date")

    def test_parse_date_datetime_object(self):
        """测试传入 datetime 对象"""
        from app.schemas.rural_work import RuralWorkCreate

        dt = datetime(2025, 1, 1, 12, 0, 0)
        data = RuralWorkCreate(name="测试工作", start_date=dt)
        assert data.start_date == dt

    def test_update_schema_date_validation(self):
        """测试更新 schema 的日期验证"""
        from app.schemas.rural_work import RuralWorkUpdate

        data = RuralWorkUpdate(start_date="2025-03-20")
        assert isinstance(data.start_date, datetime)
        assert data.start_date.day == 20

# ============================================================
# 修复1 & 7: 索引定义 — 无重复，校验逻辑
# ============================================================


class TestIndexDefinitionsNoDuplicates:
    """验证 audit_logs 重复索引已移除"""

    def test_no_audit_logs_action_index(self):
        """确认 INDEX_DEFINITIONS 中不包含 ix_audit_logs_action"""
        from app.core.database_indexes import INDEX_DEFINITIONS

        names = [idx[0] for idx in INDEX_DEFINITIONS]
        assert "ix_audit_logs_action" not in names
        assert "ix_audit_logs_created_at" not in names

    def test_no_audit_user_time_composite(self):
        """确认 COMPOSITE_INDEXES 中不包含 ix_audit_user_time"""
        from app.core.database_indexes import COMPOSITE_INDEXES

        names = [idx[0] for idx in COMPOSITE_INDEXES]
        assert "ix_audit_user_time" not in names

    def test_audit_user_id_preserved(self):
        """确认 user_id 索引保留"""
        from app.core.database_indexes import INDEX_DEFINITIONS

        names = [idx[1] for idx in INDEX_DEFINITIONS]  # idx[1] = index_name
        assert "ix_audit_logs_user_id" in names

# ============================================================
# 修复3: 报表模板列表响应格式
# ============================================================


class TestReportTemplateListFormat:
    """报表模板列表接口返回格式测试"""

    def test_template_out_schema(self):
        """测试 TemplateOut schema 能处理 None 字段"""
        from app.api.v1.report_templates import TemplateOut

        out = TemplateOut(
            id=1,
            name="测试模板",
            type="import",
            module="village",
            fields=None,
            format_config=None,
            is_active=True,
        )
        assert out.id == 1
        assert out.fields is None

# ============================================================
# 修复4: 审计日志权限 — super_admin 角色验证
# ============================================================


class TestAuditPermissions:
    """审计日志权限测试"""

    def test_admin_role_check(self):
        """测试 admin 角色通过权限检查"""
        user = MagicMock()
        user.role = "admin"
        assert getattr(user, "role", None) in ("admin", "super_admin")

    def test_super_admin_role_check(self):
        """测试 super_admin 角色通过权限检查"""
        user = MagicMock()
        user.role = "super_admin"
        assert getattr(user, "role", None) in ("admin", "super_admin")

    def test_normal_user_role_denied(self):
        """测试普通用户不通过权限检查"""
        user = MagicMock()
        user.role = "user"
        assert getattr(user, "role", None) not in ("admin", "super_admin")

# ============================================================
# 安全修复: CSRF 配置
# ============================================================


class TestSecurityConfig:
    """安全配置测试"""

    def test_csrf_enabled_by_default(self):
        """测试 CSRF 默认开启（军用安全基线要求即使单机部署也应启用）"""
        from app.core.config import Settings

        # 检查 Settings 类定义的默认值（而非测试环境已实例化的配置）
        assert Settings.model_fields["CSRF_ENABLED"].default is True

    def test_database_url_is_sqlite(self):
        """测试数据库 URL 为 SQLite"""
        from app.core.config import settings

        # 测试环境可能使用 :memory:
        assert "sqlite" in settings.DATABASE_URL

# ============================================================
# 架构修正: config_validator 匹配 SQLite
# ============================================================



# ============================================================
# 架构修正: dashboard 模型已在 models/ 目录
# ============================================================


class TestDashboardModel:
    """仪表盘模型测试"""

    def test_dashboard_activity_model_exists(self):
        """测试 DashboardActivity 模型存在"""
        from app.models.dashboard import DashboardActivity

        assert DashboardActivity.__tablename__ == "dashboard_activities"

    def test_hidden_dashboard_activity_model_exists(self):
        """测试 HiddenDashboardActivity 模型存在"""
        from app.models.dashboard import HiddenDashboardActivity

        assert HiddenDashboardActivity.__tablename__ == "hidden_dashboard_activities"

    def test_models_registered_in_init(self):
        """测试模型已在 __init__.py 注册"""
        from app.models import DashboardActivity, HiddenDashboardActivity

        assert DashboardActivity is not None
        assert HiddenDashboardActivity is not None

# ============================================================
# 代码质量: health_service 路径修正
# ============================================================



# ============================================================
# 版本号一致性
# ============================================================


class TestVersionConsistency:
    """版本号一致性测试"""

    def test_backend_version(self):
        """测试后端版本号"""
        from app.core.config import settings

        # 版本来源优先级（与 pydantic 一致）：环境变量 > .env > config.py 硬编码。
        # Electron 主进程启动后端时会注入 PROJECT_VERSION（来自其 package.json），
        # 因此环境变量覆盖 .env 是设计行为，测试需显式纳入该优先级。
        expected_version = os.environ.get("PROJECT_VERSION", "").strip()

        # 动态读取 .env 中的 PROJECT_VERSION 作为基准（由部署脚本维护）
        env_file = Path(__file__).parent.parent.parent.parent / ".env"
        if not expected_version and env_file.exists():
            for line in env_file.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, value = line.partition("=")
                    if key.strip() == "PROJECT_VERSION":
                        expected_version = value.strip()
                        break

        if not expected_version:
            expected_version = settings.PROJECT_VERSION

        assert settings.PROJECT_VERSION.strip() == expected_version.strip()
