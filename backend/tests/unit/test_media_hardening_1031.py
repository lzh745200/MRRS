# -*- coding: utf-8 -*-
"""影像库 + 机器码校验码 安全加固回归（2026-10-31）

覆盖本轮审计确认的三处问题：
1. ``resolve_upload_file`` 逐段过滤只能挡字面量 ``..``，上传目录内的符号链接
   仍可把真实路径解析到上传根之外 → 必须 400；
2. ``load_image`` 对超大像素图先解码再校验，认证用户可用 9 张巨图打爆内存 →
   解码前按像素总量拒绝；
3. ``_compose_grid`` 单元格宽度取 ``max(width)``，超宽全景图会把画布撑到数万
   像素 → 单元格宽度必须设上限；
4. ``POST /machine-code/verify-machine-code`` 是 4 位确定性校验码 oracle，原先
   无认证无限流 → 必须按来源限流（429）。
"""

import io
import os
import uuid

import pytest
from fastapi import HTTPException
from PIL import Image

from app.services import media_service


def _png_bytes(size=(100, 200), color="red"):
    buffer = io.BytesIO()
    Image.new("RGB", size, color).save(buffer, format="PNG")
    return buffer.getvalue()


def _save_upload(content, suffix=".png"):
    """写入上传目录（模拟 /files/upload 落盘），返回 /uploads URL"""
    relative = f"media_hardening_test/{uuid.uuid4().hex}{suffix}"
    path = media_service.get_runtime_uploads_path(relative)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return f"/uploads/{relative}", path


def test_resolve_upload_file_rejects_symlink_escape(tmp_path):
    """上传目录内指向外部的符号链接 → 400（resolve 后越界断言）"""
    outside = tmp_path / "outside-secret.txt"
    outside.write_text("secret", encoding="utf-8")
    relative = f"media_hardening_test/{uuid.uuid4().hex}.txt"
    link_path = media_service.get_runtime_uploads_path(relative)
    link_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.symlink(outside, link_path)
    except (OSError, NotImplementedError):  # pragma: no cover - 无符号链接权限的 Windows
        pytest.skip("当前环境不允许创建符号链接")

    with pytest.raises(HTTPException) as exc:
        media_service.resolve_upload_file(f"/uploads/{relative}")
    assert exc.value.status_code == 400
    assert "越界" in str(exc.value.detail)


def test_resolve_upload_file_still_allows_normal_relative_path():
    url, path = _save_upload(_png_bytes())
    assert media_service.resolve_upload_file(url) == path.resolve()


def test_load_image_rejects_oversized_pixels(monkeypatch):
    """像素总量超上限的图必须在 convert/load 之前拒绝（防内存放大 DoS）"""
    url, _ = _save_upload(_png_bytes(size=(100, 100)))
    monkeypatch.setattr(media_service, "MAX_IMAGE_PIXELS", 1000)
    with pytest.raises(HTTPException) as exc:
        media_service.load_image(url)
    assert exc.value.status_code == 400
    assert "尺寸过大" in str(exc.value.detail)


def test_compose_grid_caps_ultra_wide_cell():
    """超宽全景图不得把画布宽度撑到 max(width)（原实现 ~7200px 单元格）"""
    wide = Image.new("RGB", (4000, 200), "blue")
    normal = Image.new("RGB", (200, 400), "green")
    content = media_service._compose_grid([(wide, "2026-01-01"), (normal, "2026-01-02")])

    composed = Image.open(io.BytesIO(content))
    # 2 张横排：单元格宽度被 MAX_CELL_WIDTH 封顶
    assert composed.width == media_service.COMPARE_MAX_CELL_WIDTH * 2
    assert composed.height == media_service.COMPARE_CELL_HEIGHT + media_service.COMPARE_LABEL_HEIGHT
    assert composed.format == "PNG"


def test_compose_grid_keeps_small_images_unchanged():
    normal = Image.new("RGB", (200, 400), "green")
    content = media_service._compose_grid([(normal, "2026-01-01")])
    composed = Image.open(io.BytesIO(content))
    # 200x400 → 高 360 等比 180 宽，未触发宽度上限
    assert composed.width == 180


def test_verify_machine_code_is_rate_limited():
    """连续请求超过阈值 → 429；响应结构与原契约保持一致（data.is_valid）"""
    from fastapi.testclient import TestClient

    from app.core.security import _rate_limit_store
    from app.main import app

    # 限流存储是进程级内存字典，且 TestClient 来源恒为 "testclient"：
    # 不清除会污染同进程内其它用例（test_machine_code_api.py 的同端点断言）。
    _rate_limit_store.pop("verify_mc:testclient", None)
    try:
        client = TestClient(app, raise_server_exceptions=False)
        body = {"machine_code": "MC-TEST-0001", "verification_code": "1234"}
        url = "/api/v1/machine-code/verify-machine-code"

        first = client.post(url, json=body)
        assert first.status_code == 200
        assert "is_valid" in first.json()["data"]  # 限流不改变成功响应契约

        statuses = [client.post(url, json=body).status_code for _ in range(19)]
        assert statuses == [200] * 19

        limited = client.post(url, json=body)
        assert limited.status_code == 429
        assert "频繁" in limited.json()["detail"]
    finally:
        _rate_limit_store.pop("verify_mc:testclient", None)
