from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ScrapeRequest(BaseModel):
    pages: int = Field(default=3, ge=0, le=50)
    full: bool = Field(default=False)


class ScrapeSummaryResponse(BaseModel):
    run_id: int
    status: str
    pages: int
    books_seen: int
    inserted: int
    updated: int
    failed: int
    duration_s: float


class ScrapeErrorResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    run_id: int
    source_url: Optional[str]
    stage: str
    message: str
    created_at: datetime


class ScrapeRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    started_at: datetime
    finished_at: Optional[datetime]
    status: str
    pages_requested: Optional[int]
    books_seen: int
    inserted: int
    updated: int
    failed: int
    error: Optional[str]


class ScrapeRunDetailResponse(ScrapeRunResponse):
    errors: list[ScrapeErrorResponse] = []


class ScrapeRunPaginationResponse(BaseModel):
    items: list[ScrapeRunResponse]
    total: int
    page: int
    page_size: int
    pages: int
