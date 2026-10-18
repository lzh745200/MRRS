# -*- coding: utf-8 -*-
"""经费凭证 OCR API 单测（W22 · 契约 §2 ``POST /funds/ocr-voucher``）

覆盖 ``app.api.v1.funds`` 新增 OCR 端点：
- 引擎可用 → 返回 `{text, amount, date, confidence, engine}`；
- 引擎不可用 / 识别时不可用 → 503 降级（message 提示手工录入）；
- 图片为空 / 非图片 / 识别失败 → 400；超过大小上限 → 413；
- 真实引擎端到端识别（生成凭证图片，断言金额与日期）。
"""

import io
import os
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw, ImageFont

from app.api.v1 import funds as funds_module
from app.core.security import get_current_user
from app.services import ocr_service


_CJK_FONT_CANDIDATES = (
    r"C:\Windows\Fonts\simhei.ttf",
    r"C:\Windows\Fonts\msyh.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
)


def _build_voucher_image() -> bytes:
    font = None
    for path in _CJK_FONT_CANDIDATES:
        if os.path.exists(path):
            try:
                font = ImageFont.truetype(path, 40)
                break
            except OSError:  # pragma: no cover - 字体损坏的极端环境
                continue
    if font is not None:
        lines = ["帮扶经费凭证", "金额：￥1234.56", "日期：2024-01-15"]
    else:
        font = ImageFont.load_default(size=40)
        lines = ["VOUCHER", "Amount RMB 1234.56", "Date 2024-01-15"]
    canvas = Image.new("RGB", (900, 360), "white")
    drawer = ImageDraw.Draw(canvas)
    for index, line in enumerate(lines):
        drawer.text((40, 40 + index * 100), line, fill="black", font=font)
    buffer = io.BytesIO()
    canvas.save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.fixture
def ocr_app():
    app = FastAPI()
    app.include_router(funds_module.router)
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id=1, username="ocr-tester", role="admin", is_superuser=True
    )
    return app


@pytest.fixture
def client(ocr_app):
    return TestClient(ocr_app)


@pytest.fixture(autouse=True)
def _preserve_ocr_engine():
    """隔离引擎状态但保留真实引擎单例（同进程二次初始化 cv2/onnxruntime 会失败）"""
    saved_engine = ocr_service._engine
    saved_error = ocr_service._engine_error
    ocr_service._engine_error = None
    yield
    if ocr_service._engine is None:
        ocr_service._engine = saved_engine
    ocr_service._engine_error = saved_error


def _upload(client, content: bytes, filename: str = "voucher.png"):
    return client.post(
        "/funds/ocr-voucher",
        files={"file": (filename, content, "image/png")},
    )


class TestOcrVoucherApi:
    def test_success_with_stubbed_engine(self, client, monkeypatch):
        monkeypatch.setattr(funds_module.ocr_service, "available", lambda: True)
        expected = {
            "text": "金额：￥1234.56\n日期：2024-01-15",
            "amount": 1234.56,
            "date": "2024-01-15",
            "confidence": 0.98,
            "engine": "rapidocr-onnxruntime",
        }
        monkeypatch.setattr(funds_module.ocr_service, "recognize", lambda _content: expected)
        response = _upload(client, _build_voucher_image())
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["message"] == "识别成功"
        assert body["data"] == expected

    def test_engine_unavailable_returns_503(self, client, monkeypatch):
        monkeypatch.setattr(funds_module.ocr_service, "available", lambda: False)
        response = _upload(client, b"any-bytes")
        assert response.status_code == 503
        body = response.json()
        assert body["success"] is False
        assert body["code"] == 503
        assert "OCR 引擎不可用" in body["message"]

    def test_empty_image_returns_400(self, client, monkeypatch):
        monkeypatch.setattr(funds_module.ocr_service, "available", lambda: True)
        response = _upload(client, b"")
        assert response.status_code == 400
        assert "内容为空" in response.json()["detail"]

    def test_non_image_returns_400(self, client, monkeypatch):
        monkeypatch.setattr(funds_module.ocr_service, "available", lambda: True)
        response = _upload(client, b"not-an-image")
        assert response.status_code == 400
        assert "不是有效的图片文件" in response.json()["detail"]

    def test_oversize_returns_413(self, client, monkeypatch):
        monkeypatch.setattr(funds_module.ocr_service, "available", lambda: True)
        monkeypatch.setattr(funds_module, "_OCR_VOUCHER_MAX_BYTES", 64)
        response = _upload(client, b"x" * 256)
        assert response.status_code == 413

    def test_recognize_unavailable_returns_503(self, client, monkeypatch):
        monkeypatch.setattr(funds_module.ocr_service, "available", lambda: True)

        def raise_unavailable(_content):
            raise ocr_service.OCRUnavailableError("engine crashed")

        monkeypatch.setattr(funds_module.ocr_service, "recognize", raise_unavailable)
        response = _upload(client, _build_voucher_image())
        assert response.status_code == 503
        assert "OCR 引擎不可用" in response.json()["message"]

    def test_recognize_value_error_returns_400(self, client, monkeypatch):
        monkeypatch.setattr(funds_module.ocr_service, "available", lambda: True)

        def raise_value_error(_content):
            raise ValueError("OCR 识别失败: bad image")

        monkeypatch.setattr(funds_module.ocr_service, "recognize", raise_value_error)
        response = _upload(client, _build_voucher_image())
        assert response.status_code == 400
        assert "OCR 识别失败" in response.json()["detail"]

    def test_real_engine_end_to_end(self, client):
        """真实引擎端到端：上传凭证图片 → 识别出金额与日期"""
        response = _upload(client, _build_voucher_image())
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["engine"] == "rapidocr-onnxruntime"
        assert data["text"]
        assert data["amount"] == pytest.approx(1234.56)
        assert data["date"] == "2024-01-15"
        assert data["confidence"] > 0
