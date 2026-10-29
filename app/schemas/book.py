from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    field_validator,
    model_validator,
)


class BookSortField(str, Enum):
    id = "id"
    price = "price"
    rating = "rating"
    title = "title"


class SortOrder(str, Enum):
    asc = "asc"
    desc = "desc"


class BookQueryParams(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
    category: Optional[str] = None
    min_price: Optional[Decimal] = Field(default=None, ge=0)
    max_price: Optional[Decimal] = Field(default=None, ge=0)
    sort: BookSortField = BookSortField.id
    order: SortOrder = SortOrder.asc

    @model_validator(mode="after")
    def validate_price_range(self) -> "BookQueryParams":
        if self.min_price is not None and self.max_price is not None:
            if self.min_price > self.max_price:
                raise ValueError("min_price cannot be greater than max_price")
        return self


class BookBase(BaseModel):
    title: str = Field(..., min_length=1)
    price: Decimal = Field(..., ge=0)
    currency: str = Field(default="GBP", min_length=3, max_length=3)
    rating: int = Field(..., ge=1, le=5)
    in_stock: bool
    stock_count: Optional[int] = Field(default=None, ge=0)
    availability_raw: str = Field(default="In stock")
    category: str = Field(..., min_length=1)
    description: Optional[str] = None
    upc: Optional[str] = None
    image_url: Optional[str] = None
    slug: Optional[str] = None

    @field_validator("availability_raw", mode="before")
    @classmethod
    def default_availability_raw(cls, v: Any) -> str:
        if v is None or (isinstance(v, str) and not v.strip()):
            return "In stock"
        return str(v)


class BookCreate(BookBase):
    source_url: str = Field(..., min_length=1)


class BookUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1)
    price: Optional[Decimal] = Field(default=None, ge=0)
    currency: Optional[str] = Field(default=None, min_length=3, max_length=3)
    rating: Optional[int] = Field(default=None, ge=1, le=5)
    in_stock: Optional[bool] = None
    stock_count: Optional[int] = Field(default=None, ge=0)
    availability_raw: Optional[str] = None
    category: Optional[str] = Field(default=None, min_length=1)
    description: Optional[str] = None
    upc: Optional[str] = None
    image_url: Optional[str] = None
    slug: Optional[str] = None

    @field_validator("availability_raw", mode="before")
    @classmethod
    def default_patch_availability_raw(cls, v: Any) -> Optional[str]:
        if v is None:
            return "In stock"
        if isinstance(v, str) and not v.strip():
            return "In stock"
        return str(v)


class BookResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    price: Decimal
    currency: str
    rating: int
    in_stock: bool
    stock_count: Optional[int]
    category: str
    description: Optional[str]
    source_url: str
    image_url: Optional[str]
    scraped_at: datetime

    @field_serializer("price")
    def serialize_price(self, price: Decimal) -> str:
        return f"{price:.2f}"


class BookPaginationResponse(BaseModel):
    items: list[BookResponse]
    total: int
    page: int
    page_size: int
    pages: int
