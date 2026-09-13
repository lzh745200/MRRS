"""R2 端点层/解析层上传上限测试（遗留风险治理计划 2026-09-12 第一/二周批次）。

覆盖：
- `read_upload_with_limit`：分块累计、超限 413/自定义码与文案、边界值、
  短读即 EOF（测试替身固定返回值不再被误判为无限流）；
- `zip_total_uncompressed_size` / `ensure_zip_within_limit` / `read_zip_member`：
  压缩炸弹防护与限长成员读取；
- 端点接线：下级上报包与管控配置包在超限时返回 413（而非把整包读进内存）。
"""

import io
import zipfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException, UploadFile

import app.utils.upload_helper as uh


def _upload(content: bytes, filename="f.bin") -> UploadFile:
    return UploadFile(file=io.BytesIO(content), filename=filename)


class TestReadUploadWithLimit:
    """分块限长读取（R2 第二层核心）。"""

    @pytest.mark.asyncio
    async def test_reads_all_chunks(self):
        """多块读取（>chunk_size）→ 完整拼回。"""
        payload = b"a" * 2500
        data = await uh.read_upload_with_limit(_upload(payload), 10_000, chunk_size=1000)
        assert data == payload

    @pytest.mark.asyncio
    async def test_exact_boundary_allowed(self):
        """恰好等于上限 → 放行（``>`` 而非 ``>=``）。"""
        payload = b"b" * 1000
        data = await uh.read_upload_with_limit(_upload(payload), 1000, chunk_size=1024)
        assert data == payload

    @pytest.mark.asyncio
    async def test_over_limit_raises_413_with_label(self):
        with pytest.raises(HTTPException) as exc:
            await uh.read_upload_with_limit(
                _upload(b"c" * 500), 100, chunk_size=64, limit_label="导入文件"
            )
        assert exc.value.status_code == 413
        assert "导入文件" in exc.value.detail

    @pytest.mark.asyncio
    async def test_custom_status_and_detail_preserved(self):
        """调用方可保持既有接口语义（如头像 400 + 原文案）。"""
        with pytest.raises(HTTPException) as exc:
            await uh.read_upload_with_limit(
                _upload(b"d" * 64),
                16,
                chunk_size=8,
                status_code=400,
                error_detail="头像文件不能超过 2MB",
            )
        assert exc.value.status_code == 400
        assert exc.value.detail == "头像文件不能超过 2MB"

    @pytest.mark.asyncio
    async def test_short_read_treated_as_eof(self):
        """固定返回值的测试替身（模拟流）不会被判为无限流。"""
        fake = AsyncMock()
        fake.read = AsyncMock(return_value=b"x")  # 每次调用都返回同一字节
        data = await uh.read_upload_with_limit(fake, 1_000_000, chunk_size=64)
        assert data == b"x"
        assert fake.read.await_count == 1

    @pytest.mark.asyncio
    async def test_empty_upload(self):
        data = await uh.read_upload_with_limit(_upload(b""), 100)
        assert data == b""


class TestZipGuards:
    """压缩炸弹防护（R2 第三层）。"""

    def _zip(self, name: str, payload: bytes, override_size=None) -> zipfile.ZipFile:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(name, payload)
        buf.seek(0)
        zf = zipfile.ZipFile(buf)
        if override_size is not None:
            zf.infolist()[0].file_size = override_size
        return zf

    def test_total_size_sum(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("a.json", b"12345")
            zf.writestr("b.json", b"678")
        buf.seek(0)
        with zipfile.ZipFile(buf) as zf:
            assert uh.zip_total_uncompressed_size(zf) == 8

    def test_within_limit_returns_total(self):
        zf = self._zip("a.json", b"hello")
        assert uh.ensure_zip_within_limit(zf, max_bytes=1024) == 5

    def test_over_limit_raises_413(self):
        zf = self._zip("a.json", b"hello", override_size=999)
        with pytest.raises(HTTPException) as exc:
            uh.ensure_zip_within_limit(zf, max_bytes=100)
        assert exc.value.status_code == 413
        assert "解压后体积超过限制" in exc.value.detail

    def test_default_limit_resolved_at_runtime(self, monkeypatch):
        """默认阈值走模块常量（可被测试注入小值）。"""
        monkeypatch.setattr(uh, "ZIP_MAX_UNCOMPRESSED_BYTES", 2)
        zf = self._zip("a.json", b"hello")
        with pytest.raises(HTTPException):
            uh.ensure_zip_within_limit(zf)

    def test_read_member_ok(self):
        zf = self._zip("manifest.json", b'{"a":1}')
        assert uh.read_zip_member(zf, "manifest.json") == b'{"a":1}'

    def test_read_member_missing_key_error(self):
        zf = self._zip("manifest.json", b"{}")
        with pytest.raises(KeyError):
            uh.read_zip_member(zf, "absent.json")

    def test_read_member_over_limit(self):
        zf = self._zip("big.json", b"x" * 10, override_size=10_000)
        with pytest.raises(HTTPException) as exc:
            uh.read_zip_member(zf, "big.json", max_bytes=100)
        assert exc.value.status_code == 413
        assert "big.json" in exc.value.detail


class TestEndpointWiring:
    """端点接线：超限必须 413 前置拒绝（不是读完再拒）。"""

    def test_subordinate_report_package_over_limit(self, client_with_mocked_auth):
        import app.api.v1.subordinate_reports as sr

        with patch.object(sr, "_MAX_REPORT_PACKAGE_BYTES", 16):
            resp = client_with_mocked_auth.post(
                "/api/v1/subordinate-reports/import",
                files={"file": ("pkg.zip", b"z" * 64, "application/zip")},
            )
        assert resp.status_code == 413
        assert "下级上报包" in resp.json()["detail"]

    def test_control_package_preview_over_limit(self, client_with_mocked_auth):
        import app.api.v1.control_package as cp

        with patch.object(cp, "_MAX_CONTROL_PACKAGE_BYTES", 16):
            resp = client_with_mocked_auth.post(
                "/api/v1/control-packages/import-preview",
                files={"file": ("ctrl.zip", b"z" * 64, "application/zip")},
            )
        assert resp.status_code == 413
        assert "管控配置包" in resp.json()["detail"]

    def test_control_package_uncompressed_bomb_rejected(
        self, client_with_mocked_auth, monkeypatch
    ):
        """容器体积合规但解压后超限 → 解析层 413（压缩炸弹防护）。"""
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("manifest.json", b"x" * 4096)
        payload = buf.getvalue()

        monkeypatch.setattr(uh, "ZIP_MAX_UNCOMPRESSED_BYTES", 1024)
        resp = client_with_mocked_auth.post(
            "/api/v1/control-packages/import-preview",
            files={"file": ("ctrl.zip", payload, "application/zip")},
        )
        assert resp.status_code == 413
        assert "解压后体积超过限制" in resp.json()["detail"]


class TestOverLimitPropagation:
    """413/400 必须原样上抛，不被解析兜底 except 吞掉（R2 隐患点）。"""

    @pytest.mark.asyncio
    async def test_projects_parse_import_excel_propagates_413(self):
        from app.api.v1 import projects as pj

        with patch.object(pj.settings, "MAX_FILE_SIZE", 16):
            with pytest.raises(HTTPException) as exc:
                await pj._parse_import_excel(_upload(b"x" * 64, "a.xlsx"))
        assert exc.value.status_code == 413
        assert "Excel 导入文件" in exc.value.detail

    @pytest.mark.asyncio
    async def test_policy_import_row_limit_413(self):
        """R2 第三层：政策导入行数上限（原完全无上限）+ HTTPException 直通。"""
        from openpyxl import Workbook

        from app.services import policy_import_service as pis

        wb = Workbook()
        ws = wb.active
        ws.append(["序号", "政策标题"])
        ws.append([1, "政策A"])
        ws.append([2, "政策B"])
        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)

        db = MagicMock()
        with patch.object(pis, "MAX_ROWS", 1):
            with pytest.raises(HTTPException) as exc:
                await pis.import_policies_from_excel(
                    _upload(buf.getvalue(), "policies.xlsx"), db
                )
        assert exc.value.status_code == 413
        assert "数据行数超过限制" in exc.value.detail
        db.rollback.assert_called_once()

    @pytest.mark.asyncio
    async def test_policy_import_over_size_413(self):
        """政策导入体积上限（新增 10MB 口径）。"""
        from app.services import policy_import_service as pis

        real = pis.MAX_FILE_SIZE
        # 首 4 字节必须是 xlsx magic（PK\x03\x04）才能通过格式前置校验
        payload = b"PK\x03\x04" + b"y" * 32

        with patch.object(pis, "MAX_FILE_SIZE", 4):
            with pytest.raises(HTTPException) as exc:
                await pis.import_policies_from_excel(
                    _upload(payload, "policies.xlsx"), MagicMock()
                )
        assert exc.value.status_code == 413
        assert real == 10 * 1024 * 1024  # 口径断言：与 data_validator_service 一致
