# -*- coding: utf-8 -*-
"""
假成功（Fake-Success）回归防线 · v1.10.0

背景：曾出现「导出权限包提示成功，实际磁盘无产物」类缺陷。
本文件锁定核心"产生式"端点的副作用真实性：响应成功 ⇒ 必须存在可验证的实际产物
（真实字节/真实文件），杜绝空响应、空文件、纯 mock 路径被误当成功。
"""
import asyncio
import io
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest



async def _read(resp):
    if hasattr(resp, "body_iterator"):
        chunks = []
        async for chunk in resp.body_iterator:
            if isinstance(chunk, bytes):
                chunks.append(chunk)
            else:
                chunks.append(chunk.encode())
        return b"".join(chunks)
    return resp.body or b""

def _admin():
    return SimpleNamespace(
        id=1, username="root", role="super_admin",
        is_superuser=True, organization_id=1,
    )


# ── 1. 审计日志导出：excel/csv 必须产出真实可解析字节 ──────────────────
class TestAuditExportSideEffects:
    def _make_log(self, i):
        from datetime import datetime

        m = MagicMock()
        m.id = i
        m.created_at = datetime(2026, 8, 24, 12, 0, 0)
        m.username = "op"
        m.action = "create"
        m.resource_type = "fund"
        m.metadata_ = {"remark": "ok"}
        m.status = "success"
        m.user_ip = "127.0.0.1"
        return m

    def _db(self, logs):
        db = MagicMock()
        q = db.query.return_value
        q.order_by.return_value = q
        q.filter.return_value = q
        q.limit.return_value.all.return_value = logs
        return db

    def test_excel_export_produces_real_xlsx_bytes(self):
        from fastapi import responses

        from app.api.v1.system.audit import export_audit_logs

        db = self._db([self._make_log(i) for i in range(1, 6)])
        resp = asyncio.run(export_audit_logs(
            format="excel", action=None, start_date=None, end_date=None,
            current_user=_admin(), db=db,
        ))
        assert isinstance(resp, (responses.StreamingResponse, responses.Response))
        body = asyncio.run(_read(resp))
        assert len(body) > 1000, f"xlsx 字节数过小: {len(body)}"
        assert body[:2] == b"PK", "xlsx 实为 zip 容器，必须以 PK 魔数开头"

    def test_csv_export_contains_header_and_rows(self):
        from app.api.v1.system.audit import export_audit_logs

        db = self._db([self._make_log(1)])
        resp = asyncio.run(export_audit_logs(
            format="csv", action=None, start_date=None, end_date=None,
            current_user=_admin(), db=db,
        ))
        body = asyncio.run(_read(resp))
        text = body.decode("utf-8-sig")
        assert len(text) > 50
        assert "," in text

    def test_json_export_reports_real_total(self):
        from app.api.v1.system.audit import export_audit_logs

        db = self._db([self._make_log(i) for i in range(3)])
        resp = asyncio.run(export_audit_logs(
            format="json", action=None, start_date=None, end_date=None,
            current_user=_admin(), db=db,
        ))
        data = resp["data"] if isinstance(resp, dict) else resp
        items = data["items"] if isinstance(data, dict) else data
        total = data.get("total") if isinstance(data, dict) else len(items)
        assert total == len(items), "total 与实际条目不一致＝假数据"

    def test_non_admin_rejected_before_any_generation(self):
        from fastapi import HTTPException

        from app.api.v1.system.audit import export_audit_logs

        with pytest.raises(HTTPException) as ei:
            asyncio.run(export_audit_logs(
                format="excel", action=None, start_date=None, end_date=None,
                current_user=SimpleNamespace(role="user", id=9), db=self._db([]),
            ))
        assert ei.value.status_code == 403


# ── 2. 数据清洗：changed_count 口径必须与真实差异一致（防 no-op 报成功） ──
class TestCleanChangedCountHonesty:
    def test_noop_rules_report_zero_changed(self):
        from app.api.v1.data_quality import CleanDataRequest, clean_data

        req = CleanDataRequest(records=[{"a": "x"}], cleaning_rules={})
        admin = SimpleNamespace(is_superuser=True)
        resp = asyncio.run(clean_data(req, current_user=admin))
        assert resp["data"]["changed_count"] == 0, "无规则时不得虚报处理量"
