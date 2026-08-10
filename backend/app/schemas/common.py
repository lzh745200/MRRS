"""Common schemas."""

from typing import Generic, List, Optional, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ResponseBase(BaseModel):
    """Base response model."""

    code: int = Field(default=200, description="Response code")
    message: str = Field(default="success", description="Response message")


class DataResponse(ResponseBase, Generic[T]):
    """Generic data response."""

    data: Optional[T] = None


class ListResponse(ResponseBase, Generic[T]):
    """Generic list response."""

    data: List[T] = []
    total: int = 0


class PaginatedResponse(ResponseBase, Generic[T]):
    """Paginated response."""

    data: List[T] = []
    total: int = 0
    page: int = 1
    page_size: int = 10
    total_pages: int = 0


class ErrorResponse(BaseModel):
    """Error response model."""

    code: int = Field(description="Error code")
    message: str = Field(description="Error message")
    detail: Optional[str] = None


class SuccessResponse(ResponseBase):
    """Success response."""


class PaginationParams(BaseModel):
    """Pagination parameters."""

    page: int = Field(default=1, ge=1, description="Page number")
    page_size: int = Field(default=10, ge=1, le=100, description="Page size")

    @property
    def skip(self) -> int:
        return (self.page - 1) * self.page_size

    @property
    def limit(self) -> int:
        return self.page_size
