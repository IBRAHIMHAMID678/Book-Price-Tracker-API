import math
from decimal import Decimal
from typing import Optional

from app.core.exceptions import BookNotFoundError, DuplicateSourceUrlError
from app.repositories.book_repository import BookRepository
from app.schemas.book import (
    BookCreate,
    BookPaginationResponse,
    BookResponse,
    BookSortField,
    BookUpdate,
    SortOrder,
)


class BookService:
    def __init__(self, repository: BookRepository) -> None:
        self.repository = repository

    async def list_books(
        self,
        page: int = 1,
        page_size: int = 20,
        category: Optional[str] = None,
        min_price: Optional[Decimal] = None,
        max_price: Optional[Decimal] = None,
        sort: BookSortField = BookSortField.id,
        order: SortOrder = SortOrder.asc,
    ) -> BookPaginationResponse:
        if min_price is not None and max_price is not None and min_price > max_price:
            raise ValueError("min_price cannot be greater than max_price")

        books, total = await self.repository.list_books(
            page=page,
            page_size=page_size,
            category=category,
            min_price=min_price,
            max_price=max_price,
            sort=sort.value,
            order=order.value,
        )

        pages = math.ceil(total / page_size) if total > 0 else 0
        items = [BookResponse.model_validate(b) for b in books]

        return BookPaginationResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            pages=pages,
        )

    async def get_book(self, book_id: int) -> BookResponse:
        book = await self.repository.get_by_id(book_id)
        if book is None:
            raise BookNotFoundError("Book not found")
        return BookResponse.model_validate(book)

    async def create_book(self, book_in: BookCreate) -> BookResponse:
        existing = await self.repository.get_by_source_url(book_in.source_url)
        if existing is not None:
            raise DuplicateSourceUrlError("Book with this source_url already exists")

        book_data = book_in.model_dump()
        if not book_data.get("slug"):
            # Generate slug from title or URL
            book_data["slug"] = book_data["title"].lower().replace(" ", "-")

        created = await self.repository.create(book_data)
        return BookResponse.model_validate(created)

    async def update_book(self, book_id: int, book_in: BookUpdate) -> BookResponse:
        book = await self.repository.get_by_id(book_id)
        if book is None:
            raise BookNotFoundError("Book not found")

        update_data = book_in.model_dump(exclude_unset=True)
        updated = await self.repository.update(book, update_data)
        return BookResponse.model_validate(updated)

    async def delete_book(self, book_id: int) -> None:
        book = await self.repository.get_by_id(book_id)
        if book is None:
            raise BookNotFoundError("Book not found")
        await self.repository.delete(book)

    async def check_health(self) -> bool:
        return await self.repository.check_health()
