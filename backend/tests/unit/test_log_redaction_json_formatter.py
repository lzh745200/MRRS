"""回归测试：JsonFormatter 必须复用 SensitiveDataFilter 脱敏后的 exc_text。

缺陷（W24 安全深审）：SensitiveDataFilter 在 filter() 阶段把**脱敏后**的堆栈写入
record.exc_text，CPython 标准 Formatter 会优先复用该字段；但自定义 JsonFormatter
直接调用 self.formatException(record.exc_info) 按 exc_info 重新渲染**原始**堆栈，
绕过脱敏。由于 LOG_FORMAT=json 是默认配置，默认部署即会把异常消息中的
身份证号/手机号明文写进 app.log。
"""

import json
import logging
import sys

from app.core.logging_config import JsonFormatter, SensitiveDataFilter


def _record_with_pii_exception():
    try:
        raise ValueError("id_card=110101199001011234 phone=13800138000")
    except ValueError:
        return logging.LogRecord(
            "test",
            logging.ERROR,
            __file__,
            1,
            "boom",
            None,
            sys.exc_info(),
        )


def test_json_formatter_reuses_redacted_exc_text():
    """经 SensitiveDataFilter 处理后的记录，JSON 日志中的堆栈不得含 PII。"""
    record = _record_with_pii_exception()
    assert SensitiveDataFilter().filter(record) is True
    assert record.exc_text  # filter 已提前渲染并脱敏

    output = json.loads(JsonFormatter().format(record))
    assert "exception" in output
    assert "110101199001011234" not in output["exception"]
    assert "13800138000" not in output["exception"]
    assert "***" in output["exception"]


def test_json_formatter_renders_exception_without_filter():
    """未经 filter 的记录（exc_text 为空）仍须输出 exception 字段（回退分支）。"""
    record = _record_with_pii_exception()
    assert not record.exc_text

    output = json.loads(JsonFormatter().format(record))
    assert "exception" in output
    assert "ValueError" in output["exception"]
