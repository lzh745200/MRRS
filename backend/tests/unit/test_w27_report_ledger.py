"""W27 回归：上报台账跨机传递（W26-P0-6）。

## 缺陷
`data_reports` 不在任何同步链（`data_package_service.DATA_TYPE_MODELS` /
`data_sync_service._SYNC_TABLE_LABELS` 都没有它），`data_report_service` 是唯一创建点
—— 多机部署下**上级机永远收不到下级上报**，「接收/待审批/批准」全链不成立。

## 为什么不能直接搬行
`data_reports` 有 6 个外键（source_org_id / target_org_id → organizations、
submitted_by / reviewed_by / created_by → users、package_id → data_packages），
指向**本机自增 ID**。目标机同一组织/用户是不同 ID，直接搬行会 FK 违约或错绑。

## 本方案
导出**规范化台账**（组织编码 = 行政区划代码，见 v1.16.4；用户用 username），
导入端解析回本机 ID；按 `report_code`（UNIQUE）幂等 upsert。
无法解析的行跳过并记日志 —— 台账是审计材料，宁可少一条也不绑错人。
"""

from unittest.mock import MagicMock

import pytest

from app.services.data_sync_service import DataSyncService


def _svc():
    svc = object.__new__(DataSyncService)
    svc.logger = MagicMock()
    return svc


class TestExportReportLedger:
    def test_normalizes_ids_to_codes_and_usernames(self):
        svc = _svc()
        orgs = [MagicMock(id=1, code="520000"), MagicMock(id=2, code="520100")]
        users = [MagicMock(id=7, username="zhangsan")]
        rep = MagicMock(
            report_code="RPT-1", source_org_id=1, target_org_id=2, status="pending",
            title="t", report_type="monthly", description="d", comment=None,
            rejection_reason=None, deadline=None, submitted_at=None,
            submitted_by=7, reviewed_at=None, reviewed_by=None, created_at=None,
        )
        db = MagicMock()
        db.query.side_effect = [
            MagicMock(all=lambda: orgs),
            MagicMock(all=lambda: users),
            MagicMock(all=lambda: [rep]),
        ]

        rows = svc._export_report_ledger(db)

        assert len(rows) == 1
        row = rows[0]
        assert row["report_code"] == "RPT-1"
        assert row["source_org_code"] == "520000"
        assert row["target_org_code"] == "520100"
        assert row["submitted_by_username"] == "zhangsan"
        # 不得泄漏本地 ID
        assert "source_org_id" not in row
        assert "submitted_by" not in row

    def test_missing_code_becomes_none(self):
        svc = _svc()
        rep = MagicMock(
            report_code="R2", source_org_id=9, target_org_id=9, status="pending",
            title=None, report_type=None, description=None, comment=None,
            rejection_reason=None, deadline=None, submitted_at=None,
            submitted_by=None, reviewed_at=None, reviewed_by=None, created_at=None,
        )
        db = MagicMock()
        db.query.side_effect = [
            MagicMock(all=lambda: []),
            MagicMock(all=lambda: []),
            MagicMock(all=lambda: [rep]),
        ]
        rows = svc._export_report_ledger(db)
        assert rows[0]["source_org_code"] is None


class TestImportReportLedger:
    def _db(self, orgs, users, existing=None):
        db = MagicMock()
        db.query.side_effect = [orgs, users, MagicMock(**{"filter.return_value.first.return_value": existing})]
        return db

    def test_resolves_codes_to_local_ids(self):
        svc = _svc()
        orgs = [MagicMock(id=11, code="520000"), MagicMock(id=22, code="520100")]
        users = [MagicMock(id=5, username="zhangsan")]
        created = {}

        def fake_query(model):
            q = MagicMock()
            if model.__name__ == "Organization":
                return MagicMock(all=lambda: orgs)
            if model.__name__ == "User":
                return MagicMock(all=lambda: users)
            q.filter.return_value.first.return_value = None
            return q

        db = MagicMock()
        db.query.side_effect = fake_query
        db.add.side_effect = lambda obj: created.setdefault("obj", obj)

        rows = [{
            "report_code": "RPT-1", "source_org_code": "520000",
            "target_org_code": "520100", "status": "pending", "title": "t",
            "submitted_by_username": "zhangsan",
        }]
        applied = svc._import_report_ledger(db, rows)

        assert applied == 1
        obj = created["obj"]
        assert obj.source_org_id == 11   # 本机映射后的 ID
        assert obj.target_org_id == 22
        assert obj.submitted_by == 5
        assert obj.report_code == "RPT-1"

    def test_skips_rows_with_unresolvable_org(self):
        """目标机没有该组织编码 → 跳过（不绑错人），不抛异常。"""
        svc = _svc()
        orgs = [MagicMock(id=11, code="520000")]
        users = []

        def fake_query(model):
            if model.__name__ == "Organization":
                return MagicMock(all=lambda: orgs)
            if model.__name__ == "User":
                return MagicMock(all=lambda: users)
            return MagicMock()

        db = MagicMock()
        db.query.side_effect = fake_query

        applied = svc._import_report_ledger(db, [{
            "report_code": "R2", "source_org_code": "520000",
            "target_org_code": "999999", "status": "pending",
        }])
        assert applied == 0
        db.add.assert_not_called()

    def test_skips_incomplete_rows(self):
        svc = _svc()
        db = MagicMock()
        db.query.side_effect = [MagicMock(all=lambda: []), MagicMock(all=lambda: [])]
        assert svc._import_report_ledger(db, [{"report_code": "R3"}]) == 0

    def test_empty_ledger_returns_zero(self):
        svc = _svc()
        assert svc._import_report_ledger(MagicMock(), []) == 0

    def test_idempotent_upsert_by_report_code(self):
        """按 report_code 幂等：已存在则更新，不新增行。"""
        svc = _svc()
        existing = MagicMock()
        orgs = [MagicMock(id=1, code="A"), MagicMock(id=2, code="B")]
        users = []

        def fake_query(model):
            if model.__name__ == "Organization":
                return MagicMock(all=lambda: orgs)
            if model.__name__ == "User":
                return MagicMock(all=lambda: users)
            q = MagicMock()
            q.filter.return_value.first.return_value = existing
            return q

        db = MagicMock()
        db.query.side_effect = fake_query

        applied = svc._import_report_ledger(db, [{
            "report_code": "R4", "source_org_code": "A",
            "target_org_code": "B", "status": "approved",
        }])
        assert applied == 1
        db.add.assert_not_called()          # 走更新而非新增
        assert existing.status == "approved"

    def test_non_dict_rows_ignored(self):
        svc = _svc()
        db = MagicMock()
        db.query.side_effect = [MagicMock(all=lambda: []), MagicMock(all=lambda: [])]
        assert svc._import_report_ledger(db, ["garbage", 123]) == 0

    def test_invalid_iso_datetime_is_ignored(self):
        """时间字段不是合法 ISO 串时按 None 处理（不让整条台账失败）。"""
        svc = _svc()
        orgs = [MagicMock(id=1, code="A"), MagicMock(id=2, code="B")]
        users = []

        def fake_query(model):
            if model.__name__ == "Organization":
                return MagicMock(all=lambda: orgs)
            if model.__name__ == "User":
                return MagicMock(all=lambda: users)
            q = MagicMock()
            q.filter.return_value.first.return_value = None
            return q

        db = MagicMock()
        db.query.side_effect = fake_query
        captured = {}
        db.add.side_effect = lambda obj: captured.setdefault("obj", obj)

        applied = svc._import_report_ledger(db, [{
            "report_code": "R-BAD-DATE",
            "source_org_code": "A",
            "target_org_code": "B",
            "status": "pending",
            "deadline": "not-an-iso-date",
            "submitted_at": "2024-13-99T99:99:99",
        }])

        assert applied == 1
        assert captured["obj"].deadline is None
        assert captured["obj"].submitted_at is None


class TestApplyReportLedger:
    """`_apply_report_ledger`：台账失败**不得阻断**整包导入。"""

    def test_no_ledger_is_noop(self):
        svc = _svc()
        result = {"errors": []}
        svc._apply_report_ledger(MagicMock(), {}, result)
        assert result == {"errors": []}
        assert "report_ledger_applied" not in result

    def test_success_records_count(self):
        svc = _svc()
        svc._import_report_ledger = MagicMock(return_value=3)
        result = {"errors": []}
        svc._apply_report_ledger(MagicMock(), {"report_ledger": [{"x": 1}]}, result)
        assert result["report_ledger_applied"] == 3
        assert result["errors"] == []

    def test_failure_is_captured_not_raised(self):
        """台账导入抛错 → 记进 errors 并写日志，不向上抛（整包业务数据继续）。"""
        svc = _svc()
        svc._import_report_ledger = MagicMock(side_effect=RuntimeError("bad ledger"))
        result = {"errors": []}
        svc._apply_report_ledger(MagicMock(), {"report_ledger": [{"x": 1}]}, result)

        assert len(result["errors"]) == 1
        assert "导入上报台账失败" in result["errors"][0]
        assert "bad ledger" in result["errors"][0]
        assert "report_ledger_applied" not in result
        svc.logger.error.assert_called_once()


class TestWiring:
    def test_export_and_import_hooks_exist(self):
        import inspect

        from app.services import data_sync_service as mod

        src = inspect.getsource(mod.DataSyncService.export_incremental)
        assert "_export_report_ledger" in src
        # W27 第 12 轮：导入侧抽成 `_apply_report_ledger`（便于单测覆盖失败分支）
        src2 = inspect.getsource(mod.DataSyncService.import_package)
        assert "_apply_report_ledger" in src2
        assert "_import_report_ledger" in inspect.getsource(
            mod.DataSyncService._apply_report_ledger
        )
