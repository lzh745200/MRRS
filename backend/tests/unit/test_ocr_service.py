# -*- coding: utf-8 -*-
"""OCR 服务单测（W22 · 契约 §4）

覆盖 ``app.services.ocr_service``：
- 金额解析（￥/¥/元/千分位/小数/RMB 代码、越界/非正数）；
- 日期解析（YYYY-MM-DD / YYYY年M月D日 / YYYY/MM/DD、非法日期）；
- 引擎懒加载 / 线程安全 / 初始化失败缓存降级（available False）；
- **真实引擎识别**：生成中文（无中文字体时退化为英文）凭证图片，断言识别出金额与日期。
"""

import io
import os

import pytest
from PIL import Image, ImageDraw, ImageFont

from app.services import ocr_service


def _rapidocr_installed() -> bool:
    """真实 OCR 引擎是否可用。

    2026-10-27：`rapidocr-onnxruntime 1.4.4` 的元数据是 `requires_python = "<3.13"`
    （PyPI 官方 JSON 核实），因此 CI/打包基座（cp311）能装，而 Python 3.13 环境
    `pip install -r requirements.txt` 会跳过该行（已加环境标记）。此时"真实引擎"
    用例应当 **skip 而非 fail** —— 缺依赖不是代码缺陷。
    """
    try:
        import rapidocr_onnxruntime  # noqa: F401
    except ImportError:
        return False
    return True


_RAPIDOCR_SKIP_REASON = (
    "需要 rapidocr-onnxruntime（元数据 requires_python<3.13，"
    "Python 3.13 下 pip 按环境标记跳过安装）；CI 用 cp311 会执行本用例"
)


# ── 真实图片构造（优先中文字体；无中文字体的 CI 退化为 ASCII 票据）──
_CJK_FONT_CANDIDATES = (
    r"C:\Windows\Fonts\simhei.ttf",
    r"C:\Windows\Fonts\msyh.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
)


def _build_voucher_image() -> bytes:
    """生成一张含“金额 + 日期”的凭证图片（PNG bytes）"""
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
        # 无中文字体的 CI：英文票据（RMB 代码 + ISO 日期，OCR 仍可识别）
        font = ImageFont.load_default(size=40)
        lines = ["VOUCHER", "Amount RMB 1234.56", "Date 2024-01-15"]
    canvas = Image.new("RGB", (900, 360), "white")
    drawer = ImageDraw.Draw(canvas)
    for index, line in enumerate(lines):
        drawer.text((40, 40 + index * 100), line, fill="black", font=font)
    buffer = io.BytesIO()
    canvas.save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.fixture(autouse=True)
def _preserve_ocr_engine():
    """隔离引擎状态但保留真实引擎单例。

    cv2 / onnxruntime 在同进程内二次初始化会报
    ``ImportError: cannot load module more than once per process``，
    因此真实引擎一旦创建成功就跨用例复用；模拟引擎/失败缓存在用例结束后还原。
    """
    saved_engine = ocr_service._engine
    saved_error = ocr_service._engine_error
    ocr_service._engine_error = None
    yield
    current = ocr_service._engine
    if current is None or isinstance(current, _FakeEngine):
        ocr_service._engine = saved_engine
    ocr_service._engine_error = saved_error


class _FakeEngine:
    """可编程引擎替身"""

    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.calls = 0

    def __call__(self, _image_bytes):
        self.calls += 1
        if self.error is not None:
            raise self.error
        return self.result, [0.1]


# ════════════════════════════════════════════════════════════════════
#  金额 / 日期解析
# ════════════════════════════════════════════════════════════════════
class TestParseAmount:
    @pytest.mark.parametrize("text, expected", [
        ("合计金额：￥1234.56", 1234.56),
        ("金额 ¥1,234.56 元", 1234.56),
        ("报销 6789元", 6789.0),
        ("Amount RMB 88.00", 88.0),
        ("CNY 100", 100.0),
        ("金额：￥12.5", 12.5),
    ])
    def test_parse_supported_formats(self, text, expected):
        assert ocr_service.parse_amount(text) == pytest.approx(expected)

    @pytest.mark.parametrize("text", ["", "无金额", "0元", "金额：￥9999999999999"])
    def test_parse_returns_none(self, text):
        assert ocr_service.parse_amount(text) is None

    def test_amount_value_bounds(self):
        assert ocr_service._amount_value("0") is None
        assert ocr_service._amount_value("1,234.5") == 1234.5
        assert ocr_service._amount_value(str(10 ** 13)) is None


class TestParseDate:
    @pytest.mark.parametrize("text, expected", [
        ("日期：2024-01-15", "2024-01-15"),
        ("时间 2024年1月15日", "2024-01-15"),
        ("2024/1/15 开票", "2024-01-15"),
        ("开票日期：2023-12-31 10:00", "2023-12-31"),
    ])
    def test_parse_supported_formats(self, text, expected):
        assert ocr_service.parse_date(text) == expected

    @pytest.mark.parametrize("text", ["", "没有日期", "2024-13-40", "2024/02/30"])
    def test_parse_returns_none(self, text):
        assert ocr_service.parse_date(text) is None


# ════════════════════════════════════════════════════════════════════
#  置信度
# ════════════════════════════════════════════════════════════════════
class TestConfidence:
    def test_none_and_empty(self):
        assert ocr_service._confidence(None) == 0.0
        assert ocr_service._confidence([]) == 0.0

    def test_skips_short_rows_and_non_numeric(self):
        result = [
            [[0, 0], "短行"],          # len < 3
            [[0, 0], "文本", "abc"],   # 非数字分数
            [[0, 0], "文本", 0.5],
            [[0, 0], "文本", 1.0],
        ]
        assert ocr_service._confidence(result) == pytest.approx(0.75)


# ════════════════════════════════════════════════════════════════════
#  引擎生命周期 / 降级
# ════════════════════════════════════════════════════════════════════
class TestEngineLifecycle:
    def test_reset_clears_state(self):
        ocr_service._engine = object()
        ocr_service._engine_error = "boom"
        ocr_service.reset_engine()
        assert ocr_service._engine is None
        assert ocr_service._engine_error is None

    def test_init_failure_is_cached(self, monkeypatch):
        # 显式清空（可能已有前序用例创建的引擎单例），再模拟初始化失败
        ocr_service.reset_engine()

        def boom():
            raise RuntimeError("onnxruntime missing")

        monkeypatch.setattr(ocr_service, "_create_engine", boom)
        assert ocr_service.available() is False
        # 第二次：命中缓存的 _engine_error 分支（不重复初始化）
        assert ocr_service.available() is False
        assert "onnxruntime missing" in (ocr_service._engine_error or "")
        with pytest.raises(ocr_service.OCRUnavailableError):
            ocr_service.recognize(b"fake-image")

    def test_recognize_empty_bytes(self):
        with pytest.raises(ValueError, match="图片内容为空"):
            ocr_service.recognize(b"")

    def test_recognize_engine_error_becomes_value_error(self):
        ocr_service._engine = _FakeEngine(error=RuntimeError("inference failed"))
        with pytest.raises(ValueError, match="OCR 识别失败"):
            ocr_service.recognize(b"fake-image")

    def test_recognize_with_fake_engine(self):
        # 含一条元素不足的行（len < 2，被过滤）与正常行
        ocr_service._engine = _FakeEngine(result=[
            [[0, 0], "金额：1234.56元", 0.9],
            [[0, 0]],
        ])
        result = ocr_service.recognize(b"fake-image")
        assert result["amount"] == pytest.approx(1234.56)
        assert result["date"] is None
        assert result["engine"] == ocr_service.ENGINE_NAME
        assert result["confidence"] == pytest.approx(0.9)

    def test_recognize_none_result(self):
        ocr_service._engine = _FakeEngine(result=None)
        result = ocr_service.recognize(b"fake-image")
        assert result["text"] == ""
        assert result["confidence"] == 0.0

    def test_available_true_with_fake_engine(self):
        ocr_service._engine = _FakeEngine(result=[])
        assert ocr_service.available() is True


# ════════════════════════════════════════════════════════════════════
#  真实引擎识别（本机实测）
# ════════════════════════════════════════════════════════════════════
@pytest.mark.skipif(not _rapidocr_installed(), reason=_RAPIDOCR_SKIP_REASON)
class TestRealRecognition:
    def test_real_engine_recognizes_amount_and_date(self):
        assert ocr_service.available() is True
        image_bytes = _build_voucher_image()
        result = ocr_service.recognize(image_bytes)
        assert result["engine"] == "rapidocr-onnxruntime"
        assert result["text"], "OCR 未返回任何文本"
        assert result["confidence"] > 0
        assert result["amount"] == pytest.approx(1234.56)
        assert result["date"] == "2024-01-15"
