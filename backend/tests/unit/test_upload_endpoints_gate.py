# -*- coding: utf-8 -*-
"""上传端点限长门禁的回归用例（含 2026-10-28 修正的「无注解助手」误报）。

## 为什么

门禁 `check_upload_endpoints.py` 要求带 `UploadFile` 的端点显式限长。但流式落盘助手常写成
`async def _stream_upload_to_file(file, dest, max_bytes, ...)`（`file` 没有 `UploadFile` 注解），
原实现只把「带注解的函数」当作可委托的合规目标，于是**端点委托给这个合规助手**会被误判为
违规 —— 实测 `app/api/v1/data/data/data_packages.py` 的 `/data-packages/import` 就是这样被误报。

本文件锁住三种情形，防止再退化。
"""

import importlib.util
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"


def _load_gate():
    # 门禁脚本 `from _gate_common import ...`：需把 scripts 目录加入 sys.path
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    spec = importlib.util.spec_from_file_location(
        "check_upload_endpoints", SCRIPTS / "check_upload_endpoints.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


UNBOUNDED = """
from fastapi import UploadFile

async def upload_x(file: UploadFile):
    data = await file.read()
    return data
"""

DELEGATED_TO_UNANNOTATED_HELPER = """
from fastapi import UploadFile

async def _stream_upload_to_file(file, dest, max_bytes: int, error_detail: str) -> int:
    total = 0
    while True:
        chunk = await file.read(1024)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise ValueError(error_detail)
        dest.write(chunk)
    return total

async def upload_y(file: UploadFile):
    return await _stream_upload_to_file(file, None, 100, "too big")
"""

GUARDED = """
from fastapi import UploadFile
from app.utils.upload_limits import read_upload_with_limit

async def upload_z(file: UploadFile):
    return await read_upload_with_limit(file, 1024)
"""


class TestUploadEndpointGate:
    def test_unbounded_read_is_flagged(self):
        gate = _load_gate()
        hits = gate.scan_text("app/api/v1/x.py", UNBOUNDED)
        assert hits and "upload_x" in hits[0]

    def test_delegating_to_unannotated_streaming_helper_is_compliant(self):
        gate = _load_gate()
        assert gate.scan_text("app/api/v1/x.py", DELEGATED_TO_UNANNOTATED_HELPER) == []

    def test_guarded_read_is_compliant(self):
        gate = _load_gate()
        assert gate.scan_text("app/api/v1/x.py", GUARDED) == []
