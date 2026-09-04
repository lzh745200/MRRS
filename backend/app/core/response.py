"""
统一响应格式
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class PaginationMeta:
    """分页元信息"""
    page: int = 1
    page_size: int = 10
    total: int = 0
    total_pages: int = 0
    has_next: bool = False
    has_prev: bool = False

    @classmethod
    def from_pagination(cls, page: int, page_size: int, total: int) -> PaginationMeta:
        """从分页参数创建元信息"""
        if page_size <= 0:
            total_pages = 0
        else:
            total_pages = math.ceil(total / page_size) if total > 0 else 0
        has_next = page < total_pages
        has_prev = page > 1
        return cls(
            page=page,
            page_size=page_size,
            total=total,
            total_pages=total_pages,
            has_next=has_next,
            has_prev=has_prev,
        )

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "page": self.page,
            "page_size": self.page_size,
            "total": self.total,
            "total_pages": self.total_pages,
            "has_next": self.has_next,
            "has_prev": self.has_prev,
        }


def paginated_response(
    data: List[Any],
    pagination: PaginationMeta,
    message: str = "success",
) -> Dict:
    """生成分页响应"""
    resp = success_response(data=data, message=message)
    resp["meta"] = {"pagination": pagination.to_dict()}
    return resp


def ok_list(
    items: List[Any],
    total: int,
    page: int = 1,
    page_size: int = 20,
    message: str = "成功",
    extra: Optional[Dict] = None,
    **kwargs,
) -> Dict:
    """
    生成统一列表 envelope：{code:200, data:{items,total,page,page_size}, message}。

    前端 _unwrapList 据此取 data.items / data.total。
    所有业务列表接口应使用本函数，避免 bare {total,page,page_size,items} 与 envelope 混用。

    extra: 需要并入 data 的附加字段（如 summary 统计）。
    注意：不要用 **kwargs 传附加数据 —— success_response 会把它们放到响应顶层
    而非 data 内，前端读 data.summary 将得到 undefined（2026-09-02 修复）。
    """
    data: Dict = {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }
    if extra:
        # 类型守卫：extra 契约为 Dict（并入 data 层，如 summary 统计）。
        # 传入非 dict 时忽略，避免 data.update(非dict) 抛 ValueError → 500
        # （ok_list 回归修复：原新增 extra 形参未做类型校验）。
        if isinstance(extra, dict):
            data.update(extra)
    return success_response(
        data=data,
        message=message,
        **kwargs,
    )


def error_response(
    code: int = 400,
    message: str = "error",
    errors: Any = None,
    detail: Any = None,
    **kwargs,
) -> Dict:
    """
    生成标准错误响应。

    Args:
        code: HTTP 状态码
        message: 错误消息
        errors: 详细错误列表（Pydantic 验证错误等）
        detail: 详细信息
        **kwargs: 其他字段

    Returns:
        标准错误响应字典
    """
    resp = {
        "code": code,
        "message": message,
        "success": False,
    }
    if errors is not None:
        resp["errors"] = errors
    if detail is not None:
        resp["detail"] = detail
    resp.update(kwargs)
    return resp


def success_response(
    data: Any = None,
    message: str = "success",
    **kwargs,
) -> Dict:
    """
    生成标准成功响应。

    Args:
        data: 响应数据
        message: 成功消息
        **kwargs: 其他字段

    Returns:
        标准成功响应字典
    """
    resp = {
        "code": 200,
        "message": message,
        "success": True,
    }
    if data is not None:
        resp["data"] = data
    resp.update(kwargs)
    return resp


def not_found_response(message: str = "资源不存在", detail: Any = None) -> Dict:
    """生成未找到响应 (404)"""
    return error_response(code=404, message=message, detail=detail)


def forbidden_response(message: str = "无权限访问") -> Dict:
    """生成禁止访问响应 (403)"""
    return error_response(code=403, message=message)


def server_error_response(message: str = "服务器内部错误", detail: Any = None) -> Dict:
    """生成服务器错误响应 (500)"""
    return error_response(code=500, message=message, detail=detail)


# 向后兼容别名
ErrorResponse = error_response
