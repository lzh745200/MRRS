"""OCR 第二轮深审修复回归 —— models / schemas 层。

覆盖（part-B #40/#45/#46/#48/#49/#50/#53/#56/#57/#60~#63）：
- Project.to_dict 默认脱敏 PII（电话/银行账号），授权路径经 mask_pii=False 取全量；
- AlertHistory.created_at 别名（告警历史不再恒为空）；
- DataReport.is_overdue 处理 SQLite naive deadline；
- message_template 渲染 AttributeError/TypeError 不再穿透；
- SystemConfig.__repr__ 不回显敏感 value；
- 模型列约束：import_export_history.org_id 可空 + SET NULL、difference_rate 精度、
  sentiment.collected_at 默认值、fund_history 时间为 aware UTC；
- schemas：permission mode 封闭集合、rural_work 日期统一 UTC、SchoolResponse ORM 转换、
  app.schemas 不再泄漏 BaseModel。
"""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.models.data_report import DataReport, ReportStatus
from app.models.monitoring import AlertHistory, AlertRule
from app.models.project import Project
from app.models.sentiment import SentimentNews
from app.models.system_config import SystemConfig


class TestProjectPiiMasking:
    """part-B #53：to_dict 默认脱敏，明文只经受控入口。"""

    def _project(self):
        return Project(
            contact_phone="13800138000",
            payer_contact="13900139000",
            payee_contact="13700137000",
            payer_account_number="6222021234567890123",
            payee_account_number="123",
        )

    def test_default_masks_phones_and_accounts(self):
        data = self._project().to_dict()
        assert data["contact_phone"] == "138****8000"
        assert data["payer_contact"] == "139****9000"
        assert data["payee_contact"] == "137****7000"
        assert data["payer_account_number"] == "****0123"
        assert data["payee_account_number"] == "***"  # 长度 <= 4 全掩码

    def test_explicit_unmasked_returns_raw(self):
        raw = self._project().to_dict(mask_pii=False)
        assert raw["contact_phone"] == "13800138000"
        assert raw["payer_account_number"] == "6222021234567890123"

    def test_to_dict_unmasked_helper(self):
        assert self._project().to_dict_unmasked()["payee_account_number"] == "123"

    def test_none_and_short_values_survive(self):
        data = Project(contact_phone=None, payer_account_number=None, payee_contact="123").to_dict()
        assert data["contact_phone"] is None
        assert data["payer_account_number"] is None
        assert data["payee_contact"] == "***"  # 短号（< 7）整体掩码


class TestAlertHistoryCreatedAtAlias:
    """part-B #50：模型暴露 created_at，消费端 order_by/isoformat 不再 AttributeError。"""

    def test_attribute_alias_read_write(self):
        ts = datetime(2024, 5, 1, tzinfo=timezone.utc)
        history = AlertHistory(rule_id=1, message="m")
        history.created_at = ts
        assert history.triggered_at == ts
        assert history.created_at == ts

    def test_order_by_alias_works(self, real_db_session):
        rule = AlertRule(name="r", metric_type="response_time", threshold=1.0, channels=["email"])
        real_db_session.add(rule)
        real_db_session.commit()
        real_db_session.add_all([
            AlertHistory(rule_id=rule.id, message="a", triggered_at=datetime(2024, 1, 1, tzinfo=timezone.utc)),
            AlertHistory(rule_id=rule.id, message="b", triggered_at=datetime(2024, 2, 1, tzinfo=timezone.utc)),
        ])
        real_db_session.commit()
        rows = real_db_session.query(AlertHistory).order_by(AlertHistory.created_at.desc()).all()
        assert [r.message for r in rows] == ["b", "a"]
        assert rows[0].created_at.isoformat().startswith("2024-02-01")


class TestDataReportOverdue:
    """part-B #40：naive deadline（SQLite 回读）不再 TypeError。"""

    def test_naive_past_deadline_is_overdue(self):
        report = DataReport(deadline=datetime(2020, 1, 1), status=ReportStatus.DRAFT.value)
        assert report.is_overdue is True

    def test_naive_future_deadline_not_overdue(self):
        future = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=1)
        report = DataReport(deadline=future, status=ReportStatus.DRAFT.value)
        assert report.is_overdue is False

    def test_aware_deadline_still_works(self):
        report = DataReport(deadline=datetime(2020, 1, 1, tzinfo=timezone.utc), status=ReportStatus.DRAFT.value)
        assert report.is_overdue is True

    def test_no_deadline_or_non_draft(self):
        assert DataReport(deadline=None, status=ReportStatus.DRAFT.value).is_overdue is False
        report = DataReport(deadline=datetime(2020, 1, 1), status=ReportStatus.SUBMITTED.value)
        assert report.is_overdue is False


class TestMessageTemplateRenderGuard:
    """part-B #49：管理员可改模板，任何渲染异常都不得穿透成 500。"""

    def _template(self, **kwargs):
        from app.models.message_template import MessageTemplate

        defaults = dict(
            code="c", name="n", title_template="{user.name}",
            content_template="{values[0]}", email_subject_template="{user.name}",
            email_body_template="{values[0]}",
        )
        defaults.update(kwargs)
        return MessageTemplate(**defaults)

    def test_attribute_error_returns_raw_template(self):
        tpl = self._template()
        assert tpl.render_title({"user": "alice"}) == "{user.name}"
        assert tpl.render_email_subject({"user": "alice"}) == "{user.name}"

    def test_type_error_returns_raw_template(self):
        tpl = self._template()
        assert tpl.render_content({"values": 5}) == "{values[0]}"
        assert tpl.render_email_body({"values": 5}) == "{values[0]}"

    def test_malformed_brace_returns_raw_template(self):
        tpl = self._template(title_template="{username", content_template="ok")
        assert tpl.render_title({"username": "x"}) == "{username"


class TestSensitiveAndConstraintModels:
    def test_system_config_repr_masks_value(self):
        cfg = SystemConfig(key="encryption_salt", value="super-secret-salt")
        text = repr(cfg)
        assert "super-secret-salt" not in text
        assert "17 chars" in text

    def test_import_export_history_org_id_set_null(self):
        from app.models.import_export_history import ImportExportHistory

        col = ImportExportHistory.__table__.c.org_id
        assert col.nullable is True
        assert next(iter(col.foreign_keys)).ondelete == "SET NULL"

    def test_difference_rate_widened(self):
        from app.models.fund_asset_verification import FundAssetVerification

        col = FundAssetVerification.__table__.c.difference_rate
        assert col.type.precision == 12
        assert col.type.scale == 2

    def test_sentiment_collected_at_has_default(self):
        col = SentimentNews.__table__.c.collected_at
        assert col.nullable is True
        assert col.default is not None
        assert col.server_default is not None

    def test_fund_history_time_defaults_are_aware_utc(self):
        from app.models.fund_history import FundFieldChange, FundStatusHistory

        for col in (
            FundStatusHistory.__table__.c.operation_time,
            FundFieldChange.__table__.c.changed_at,
        ):
            value = col.default.arg(None)
            assert value.tzinfo is not None
            assert value.utcoffset() == timedelta(0)


class TestSchemaHardening:
    def test_permission_package_mode_is_closed_set(self):
        from app.schemas.permission_package import PermissionPackageConfirmRequest

        assert PermissionPackageConfirmRequest(mode="merge").mode == "merge"
        assert PermissionPackageConfirmRequest().mode is None
        with pytest.raises(ValidationError):
            PermissionPackageConfirmRequest(mode="MERGE")

    def test_rural_work_date_normalized_to_utc(self):
        from app.schemas.rural_work import _parse_date

        parsed = _parse_date("2024-01-02")
        assert parsed.tzinfo == timezone.utc
        explicit = _parse_date("2024-01-02T03:04:05Z")
        assert explicit.tzinfo == timezone.utc

    def test_school_response_from_orm_object(self):
        from app.models.school import SchoolLevel, SchoolType
        from app.schemas.school import SchoolResponse

        now = datetime.now(timezone.utc)
        orm_like = SimpleNamespace(
            id=1, name="学校", code="S1",
            school_type=SchoolType.PRIMARY, school_level=SchoolLevel.COUNTY,
            created_at=now, updated_at=now,
        )
        resp = SchoolResponse.model_validate(orm_like)
        assert resp.id == 1
        assert resp.name == "学校"

    def test_schemas_package_does_not_leak_basemodel(self):
        """兜底分支只登记本模块定义的模型：import * 不再带出 BaseModel。

        （BaseModel 仍在包命名空间里 —— 那只是 __init__ 自身的 import，
        真正的问题是它被写进 __all__ 并随 import * 泄漏。）
        """
        import app.schemas as schemas_pkg

        assert "BaseModel" not in schemas_pkg.__all__
        # __all__ 里每个名字都必须是某个 schemas 子模块自有定义的模型
        for name in schemas_pkg.__all__:
            obj = getattr(schemas_pkg, name)
            assert getattr(obj, "__module__", "").startswith("app.schemas.")
