from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import get_scrape_service
from app.core.exceptions import ScrapeLockError, ScrapeRunNotFoundError
from app.schemas.scrape import (
    ScrapeRequest,
    ScrapeRunDetailResponse,
    ScrapeRunPaginationResponse,
    ScrapeSummaryResponse,
)
from app.services.scrape_service import ScrapeService

router = APIRouter(prefix="/scrape", tags=["scrape"])


@router.post("", response_model=ScrapeSummaryResponse)
async def trigger_scrape(
    request: ScrapeRequest = ScrapeRequest(),
    service: ScrapeService = Depends(get_scrape_service),
) -> ScrapeSummaryResponse:
    try:
        return await service.run_scrape(pages=request.pages, full=request.full)
    except ScrapeLockError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


@router.get("/runs", response_model=ScrapeRunPaginationResponse)
async def list_scrape_runs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    service: ScrapeService = Depends(get_scrape_service),
) -> ScrapeRunPaginationResponse:
    return await service.list_runs(page=page, page_size=page_size)


@router.get("/runs/{run_id}", response_model=ScrapeRunDetailResponse)
async def get_scrape_run(
    run_id: int,
    service: ScrapeService = Depends(get_scrape_service),
) -> ScrapeRunDetailResponse:
    try:
        return await service.get_run(run_id)
    except ScrapeRunNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
