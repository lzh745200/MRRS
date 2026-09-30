"""Pydantic schemas."""

from __future__ import annotations

import importlib
import logging
from typing import List

from pydantic import BaseModel

logger = logging.getLogger(__name__)

__all__: List[str] = []

# Optional modules to load
_OPTIONAL_MODULES = [
    "auth",
    "fund",
    "policy",
    "project",
    "school",
    "user",
    "village",
]


def _register_schema(module_name: str) -> None:
    """Register schema from module."""
    try:
        module = importlib.import_module(f"{__name__}.{module_name}")
    except Exception as exc:  # pragma: no cover
        logger.error("Failed to import schema %s: %s", module_name, exc)
        return

    exported = getattr(module, "__all__", None)
    if exported:
        for name in exported:
            globals()[name] = getattr(module, name)
            __all__.append(name)
        return

    for attr_name in dir(module):
        attr = getattr(module, attr_name)
        # 只登记**本模块定义**的模型：模块级 import 进来的 BaseModel 本身、
        # 以及兄弟模块的类型同样满足 issubclass(..., BaseModel)，会把
        # BaseModel 与无关模型塞进 __all__，import * 直接泄漏（深审 LIVE）。
        if (
            isinstance(attr, type)
            and issubclass(attr, BaseModel)
            and attr is not BaseModel
            and getattr(attr, "__module__", None) == module.__name__
        ):
            globals()[attr_name] = attr
            __all__.append(attr_name)


for _module in _OPTIONAL_MODULES:
    _register_schema(_module)

del _OPTIONAL_MODULES
