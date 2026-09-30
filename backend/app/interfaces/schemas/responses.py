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


def _base_response_success(cls, data: Any = None, message: str = "success", code: int = 200):
    """创建成功响应（BaseResponse.success 的实现，类体外绑定，见下）。"""
    return cls(code=code, data=data, message=message, success=True)


def _base_response_error(cls, message: str = "error", code: int = 400, data: Any = None):
    """创建错误响应（BaseResponse.error 的实现，类体外绑定，见下）。"""
    return cls(code=code, data=data, message=message, success=False)


class BaseResponse(ResponseModel, Generic[T]):
    """
    泛型响应模型

    支持泛型类型参数，用于response_model声明。
    提供success/error工厂方法（在类体外绑定）。

    字段与 ResponseModel 对齐（继承同一基类）——此前 BaseResponse 缺
    success 字段，与 success_response 信封不一致，前端 res.success 判断会
    得到 undefined（深审 #26）。
    """

    data: Optional[T] = Field(default=None, description="响应数据")


# 工厂方法必须在类体之外绑定：Pydantic v2 中与字段同名的类方法会被字段
# 取代（BaseResponse.success 变成字段描述符，调用直接 AttributeError）。
# 类体外赋值不参与模型构建，字段与工厂方法可以共存：
#   BaseResponse.success(data=...)  → 工厂（类属性）
#   BaseResponse(...).success       → 字段值（实例 __dict__）
BaseResponse.success = classmethod(_base_response_success)  # type: ignore[attr-defined]
BaseResponse.error = classmethod(_base_response_error)  # type: ignore[attr-defined]
