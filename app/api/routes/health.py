from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.api.deps import get_book_service
from app.services.book_service import BookService


class HealthResponse(BaseModel):
    status: str
    database: str


router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def get_health(
    service: BookService = Depends(get_book_service),
) -> HealthResponse:
    try:
        ok = await service.check_health()
        if not ok:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database unavailable",
            )
        return HealthResponse(status="ok", database="ok")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database error: {exc}",
        ) from exc
