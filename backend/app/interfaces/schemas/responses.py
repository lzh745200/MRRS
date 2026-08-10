"""
统一响应模型

提供API统一响应格式，供各路由模块使用。
"""

from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ResponseModel(BaseModel):
    """通用响应模型"""

    code: int = Field(default=200, description="响应状态码")
    data: Optional[Any] = Field(default=None, description="响应数据")
    message: str = Field(default="success", description="响应消息")
    success: bool = Field(default=True, description="是否成功（与 success_response 信封对齐，前端 res.success 判断依赖）")


class BaseResponse(BaseModel, Generic[T]):
    """
    泛型响应模型

    支持泛型类型参数，用于response_model声明。
    提供success/error工厂方法。
    """

    code: int = Field(default=200, description="响应状态码")
    data: Optional[T] = Field(default=None, description="响应数据")
    message: str = Field(default="success", description="响应消息")

    @classmethod
    def success(cls, data: Any = None, message: str = "success", code: int = 200):
        """创建成功响应"""
        return cls(code=code, data=data, message=message)

    @classmethod
    def error(cls, message: str = "error", code: int = 400, data: Any = None):
        """创建错误响应"""
        return cls(code=code, data=data, message=message)
