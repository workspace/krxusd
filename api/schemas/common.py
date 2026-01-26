from datetime import datetime
from typing import Generic, TypeVar
from pydantic import BaseModel, Field

T = TypeVar("T")


class APIResponse(BaseModel, Generic[T]):
    """Generic API response wrapper"""

    success: bool = True
    message: str = "Success"
    data: T | None = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class PaginatedResponse(BaseModel, Generic[T]):
    """Paginated response for list endpoints"""

    items: list[T]
    total: int
    page: int
    size: int
    pages: int

    @property
    def has_next(self) -> bool:
        return self.page < self.pages

    @property
    def has_prev(self) -> bool:
        return self.page > 1


class ErrorResponse(BaseModel):
    """Standard error response"""

    success: bool = False
    error_code: str
    message: str
    detail: str | None = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
