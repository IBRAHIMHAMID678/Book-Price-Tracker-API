from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.api.deps import get_book_service
from app.core.exceptions import (
    BookNotFoundError,
    CheckViolationError,
    DuplicateSourceUrlError,
)
from app.schemas.book import (
    BookCreate,
    BookPaginationResponse,
    BookQueryParams,
    BookResponse,
    BookUpdate,
)
from app.services.book_service import BookService

router = APIRouter(prefix="/books", tags=["books"])


@router.get("", response_model=BookPaginationResponse)
async def list_books(
    params: Annotated[BookQueryParams, Query()],
    service: BookService = Depends(get_book_service),
) -> BookPaginationResponse:
    return await service.list_books(
        page=params.page,
        page_size=params.page_size,
        category=params.category,
        min_price=params.min_price,
        max_price=params.max_price,
        sort=params.sort,
        order=params.order,
    )


@router.get("/{book_id}", response_model=BookResponse)
async def get_book(
    book_id: int,
    service: BookService = Depends(get_book_service),
) -> BookResponse:
    try:
        return await service.get_book(book_id)
    except BookNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.post("", response_model=BookResponse, status_code=status.HTTP_201_CREATED)
async def create_book(
    book_in: BookCreate,
    service: BookService = Depends(get_book_service),
) -> BookResponse:
    try:
        return await service.create_book(book_in)
    except DuplicateSourceUrlError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except CheckViolationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


@router.patch("/{book_id}", response_model=BookResponse)
async def patch_book(
    book_id: int,
    book_in: BookUpdate,
    service: BookService = Depends(get_book_service),
) -> BookResponse:
    try:
        return await service.update_book(book_id, book_in)
    except BookNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except CheckViolationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


@router.delete("/{book_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_book(
    book_id: int,
    service: BookService = Depends(get_book_service),
) -> Response:
    try:
        await service.delete_book(book_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except BookNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
