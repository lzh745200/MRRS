"""导出单元格安全：CSV / Excel 公式注入（Formula / CSV Injection）防护。

威胁：以 ``= + - @`` 或制表符/回车开头的单元格，被 Excel/WPS 打开时可能被解析为公式
（典型利用 ``=HYPERLINK(...)``、``=cmd|' /C calc'!A0`` 一类 DDE），造成点击即执行、
数据外发或钓鱼。本项目导出的村名、项目名、备注、错误明细等字段来自用户录入，属于
不可信输入，因此所有面向 Excel 的导出统一经本模块净化，禁止各导出点各写一套。

约定：
- 只处理 ``str``；数字/日期/布尔/None 原样返回（避免把负数变成文本）。
- 转义方式为前置单引号 ``'``：Excel/WPS 打开后按文本显示，视觉上仅多一个不可见前缀，
  与 OWASP 推荐做法一致；CSV 消费方（如 pandas）读到的也是带前缀的文本，不会误执行。
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

# 以这些字符开头的单元格可能被 Excel/WPS 当作公式；\t 与 \r 是公式注入的已知绕过手法
DANGEROUS_PREFIXES: tuple[str, ...] = ("=", "+", "-", "@", "\t", "\r")

# 前置单引号：Excel 视为「强制文本」，不进入公式解析
_ESCAPE_PREFIX = "'"


def sanitize_cell(value: Any) -> Any:
    """给可能被当作公式的字符串加前置单引号；其余类型原样返回。"""
    if isinstance(value, str) and value[:1] in DANGEROUS_PREFIXES:
        return _ESCAPE_PREFIX + value
    return value


def sanitize_row(row: Sequence[Any]) -> list[Any]:
    """净化一行（list/tuple）中的每个单元格。"""
    return [sanitize_cell(value) for value in row]


def sanitize_mapping(row: Mapping[str, Any]) -> dict[str, Any]:
    """净化 dict 形式的一行（csv.DictWriter 场景）。"""
    return {key: sanitize_cell(value) for key, value in row.items()}
