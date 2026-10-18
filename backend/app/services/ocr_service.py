"""经费凭证 OCR 服务（W22 · 契约 §4）

引擎：``rapidocr-onnxruntime``（完全离线 / CPU / 中英文；本机实测可识别中文、
金额与日期）。设计要点：

- **懒加载 + 线程安全**：首次调用才初始化引擎（模型加载约 1~2s），首次初始化
  加锁避免并发重复加载；
- **失败降级**：初始化失败缓存错误，``available()`` 返回 False，API 层据此
  返回 503 并提示手工录入（不阻断经费业务）；
- **纯函数解析**：``parse_amount`` / ``parse_date`` 从 OCR 全文解析金额与日期，
  与引擎解耦、可独立单测；
- 输出：``{text, amount, date, confidence, engine}``。

金额支持 ``￥`` / ``¥`` 前缀、千分位与小数，以及 ``元`` 后缀；
日期支持 ``YYYY-MM-DD`` / ``YYYY年M月D日`` / ``YYYY/MM/DD``。
"""

import logging
import re
import threading
from datetime import date
from typing import Any, Optional

logger = logging.getLogger(__name__)

ENGINE_NAME = "rapidocr-onnxruntime"

# 金额上限（防御性：避免把身份证号/年份串误识别为巨额金额）
_AMOUNT_MAX = 1_000_000_000_000.0

_AMOUNT_SYMBOL_RE = re.compile(r"[￥¥]\s*([0-9][0-9,]*(?:\.[0-9]{1,2})?)")
_AMOUNT_YUAN_RE = re.compile(r"([0-9][0-9,]*(?:\.[0-9]{1,2})?)\s*元")
# 英文币种代码（离线凭证/发票兼容；契约要求之外的无害扩展）
_AMOUNT_CODE_RE = re.compile(r"(?:RMB|CNY)\s*([0-9][0-9,]*(?:\.[0-9]{1,2})?)")

_DATE_PATTERNS = (
    re.compile(r"(\d{4})-(\d{1,2})-(\d{1,2})"),
    re.compile(r"(\d{4})年(\d{1,2})月(\d{1,2})日"),
    re.compile(r"(\d{4})/(\d{1,2})/(\d{1,2})"),
)

# ── 引擎单例状态（模块级；失败结果缓存，避免每次请求重复加载模型）──
_engine: Any = None
_engine_error: Optional[str] = None
_engine_lock = threading.Lock()


class OCRUnavailableError(RuntimeError):
    """OCR 引擎不可用（依赖缺失 / 模型初始化失败）"""


def _create_engine():
    """创建 OCR 引擎实例（独立函数便于测试替换初始化失败路径）"""
    from rapidocr_onnxruntime import RapidOCR

    return RapidOCR()


def _get_engine():
    """获取 OCR 引擎（懒加载；初始化失败缓存错误并抛 OCRUnavailableError）"""
    global _engine, _engine_error
    with _engine_lock:
        if _engine is not None:
            return _engine
        if _engine_error is not None:
            raise OCRUnavailableError(_engine_error)
        try:
            _engine = _create_engine()
        except Exception as exc:  # noqa: BLE001 - 引擎不可用统一降级，不向上抛原始异常
            _engine_error = f"{type(exc).__name__}: {exc}"
            logger.warning(
                "OCR 引擎初始化失败，降级为手工录入: %s", _engine_error, exc_info=True
            )
            raise OCRUnavailableError(_engine_error) from exc
        logger.info("OCR 引擎初始化成功: %s", ENGINE_NAME)
        return _engine


def available() -> bool:
    """OCR 引擎是否可用（会触发懒加载；初始化失败返回 False 并缓存错误）"""
    try:
        _get_engine()
    except OCRUnavailableError:
        return False
    return True


def reset_engine() -> None:
    """重置引擎状态（测试隔离 / 依赖安装后重试）"""
    global _engine, _engine_error
    with _engine_lock:
        _engine = None
        _engine_error = None


def _amount_value(raw: str) -> Optional[float]:
    """把匹配到的金额数字串转为 float；越界 / 非正数返回 None"""
    value = float(raw.replace(",", ""))
    if value <= 0 or value >= _AMOUNT_MAX:
        return None
    return value


def parse_amount(text: str) -> Optional[float]:
    """从 OCR 文本解析金额（优先货币符号，其次“元”后缀，最后 RMB/CNY 代码）"""
    if not text:
        return None
    match = _AMOUNT_SYMBOL_RE.search(text)
    if not match:
        match = _AMOUNT_YUAN_RE.search(text)
    if not match:
        match = _AMOUNT_CODE_RE.search(text)
    if not match:
        return None
    return _amount_value(match.group(1))


def parse_date(text: str) -> Optional[str]:
    """从 OCR 文本解析日期，返回 ISO ``YYYY-MM-DD``；非法/缺失返回 None"""
    if not text:
        return None
    for pattern in _DATE_PATTERNS:
        match = pattern.search(text)
        if match is None:
            continue
        try:
            value = date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
        except ValueError:
            return None
        return value.isoformat()
    return None


def _confidence(result: Any) -> float:
    """OCR 结果置信度均值（0~1，保留 4 位小数）"""
    scores: list[float] = []
    for item in result or []:
        if len(item) < 3:
            continue
        score = item[2]
        if isinstance(score, (int, float)):
            scores.append(float(score))
    if not scores:
        return 0.0
    return round(sum(scores) / len(scores), 4)


def recognize(image_bytes: bytes) -> dict:
    """识别凭证图片 → ``{text, amount, date, confidence, engine}``

    Raises:
        ValueError: 图片内容为空 / 引擎识别过程失败（API 层转 400）
        OCRUnavailableError: 引擎不可用（API 层转 503 降级）
    """
    if not image_bytes:
        raise ValueError("图片内容为空")
    engine = _get_engine()
    try:
        result, _elapse = engine(image_bytes)
    except Exception as exc:  # noqa: BLE001 - 识别失败统一转 ValueError（400）
        raise ValueError(f"OCR 识别失败: {exc}") from exc
    lines = [str(item[1]) for item in result or [] if len(item) >= 2]
    text = "\n".join(lines)
    return {
        "text": text,
        "amount": parse_amount(text),
        "date": parse_date(text),
        "confidence": _confidence(result),
        "engine": ENGINE_NAME,
    }
