"""审计日志哈希链（可选，默认关）。

只对 audit_logs 的**关键字段**做规范化 JSON 哈希，避免把 ORM 对象/时间戳
序列化差异带进链。用途是“可检测单条篡改”，不是阻止本机高权限用户删库。
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable

CHAIN_FIELDS = (
    "user_id",
    "username",
    "action",
    "resource_type",
    "resource_id",
    "new_value",
    "status",
    "level",
)


def payload_dict(row: Any) -> dict:
    return {field: getattr(row, field, None) for field in CHAIN_FIELDS}


def compute_payload_hash(row: Any) -> str:
    canonical = json.dumps(
        payload_dict(row), sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def verify_chain(rows: Iterable[Any]) -> tuple[bool, int | None]:
    """校验按 id 升序的审计行；返回 (是否完整, 首个断链 id)。"""
    previous = None
    for row in rows:
        expected = compute_payload_hash(row)
        if getattr(row, "payload_hash", None) != expected:
            return False, getattr(row, "id", None)
        if getattr(row, "prev_hash", None) != previous:
            return False, getattr(row, "id", None)
        previous = expected
    return True, None
