from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import func, literal_column, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import CheckViolationError, DuplicateSourceUrlError
from app.models.book import Book
from app.models.scrape_run import ScrapeError, ScrapeRun


class BookRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, book_id: int) -> Optional[Book]:
        result = await self.session.execute(select(Book).where(Book.id == book_id))
        return result.scalar_one_or_none()

    async def get_by_source_url(self, source_url: str) -> Optional[Book]:
        result = await self.session.execute(select(Book).where(Book.source_url == source_url))
        return result.scalar_one_or_none()

    async def list_books(
        self,
        page: int = 1,
        page_size: int = 20,
        category: Optional[str] = None,
        min_price: Optional[Decimal] = None,
        max_price: Optional[Decimal] = None,
        sort: str = "id",
        order: str = "asc",
    ) -> tuple[list[Book], int]:
        query = select(Book)
        count_query = select(func.count()).select_from(Book)

        if category is not None:
            cat_filter = func.lower(Book.category) == category.lower()
            query = query.where(cat_filter)
            count_query = count_query.where(cat_filter)

        if min_price is not None:
            min_filter = Book.price >= min_price
            query = query.where(min_filter)
            count_query = count_query.where(min_filter)

        if max_price is not None:
            max_filter = Book.price <= max_price
            query = query.where(max_filter)
            count_query = count_query.where(max_filter)

        total_result = await self.session.execute(count_query)
        total = total_result.scalar_one()

        sort_column = getattr(Book, sort, Book.id)
        if order.lower() == "desc":
            query = query.order_by(sort_column.desc(), Book.id.desc())
        else:
            query = query.order_by(sort_column.asc(), Book.id.asc())

        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)

        result = await self.session.execute(query)
        items = list(result.scalars().all())
        return items, total

    async def create(self, book_data: dict[str, Any]) -> Book:
        now = datetime.now(timezone.utc)
        book = Book(
            **book_data,
            created_at=now,
            updated_at=now,
            scraped_at=now,
        )
        self.session.add(book)
        try:
            await self.session.commit()
            await self.session.refresh(book)
            return book
        except IntegrityError as exc:
            await self.session.rollback()
            pgcode = getattr(exc.orig, "pgcode", None) or getattr(exc.orig, "sqlstate", None)
            if pgcode == "23505":
                raise DuplicateSourceUrlError("Book with this source_url already exists") from exc
            if pgcode == "23514":
                raise CheckViolationError("Database check constraint violated") from exc
            raise

    async def update(self, book: Book, update_data: dict[str, Any]) -> Book:
        for key, value in update_data.items():
            if value is not None:
                setattr(book, key, value)
        book.updated_at = datetime.now(timezone.utc)
        self.session.add(book)
        try:
            await self.session.commit()
            await self.session.refresh(book)
            return book
        except IntegrityError as exc:
            await self.session.rollback()
            pgcode = getattr(exc.orig, "pgcode", None) or getattr(exc.orig, "sqlstate", None)
            if pgcode == "23505":
                raise DuplicateSourceUrlError("Book with this source_url already exists") from exc
            if pgcode == "23514":
                raise CheckViolationError("Database check constraint violated") from exc
            raise

    async def delete(self, book: Book) -> None:
        await self.session.delete(book)
        await self.session.commit()

    async def upsert_batch(self, books_data: list[dict[str, Any]]) -> tuple[int, int]:
        if not books_data:
            return 0, 0

        stmt = pg_insert(Book).values(books_data)
        update_dict = {
            "price": stmt.excluded.price,
            "rating": stmt.excluded.rating,
            "in_stock": stmt.excluded.in_stock,
            "stock_count": stmt.excluded.stock_count,
            "availability_raw": stmt.excluded.availability_raw,
            "category": stmt.excluded.category,
            "description": func.coalesce(stmt.excluded.description, Book.description),
            "upc": func.coalesce(stmt.excluded.upc, Book.upc),
            "image_url": func.coalesce(stmt.excluded.image_url, Book.image_url),
            "scraped_at": stmt.excluded.scraped_at,
            "updated_at": func.now(),
        }

        # Unconditional update ensures re-scrapes update metadata and return xmax
        stmt = stmt.on_conflict_do_update(
            index_elements=["source_url"],
            set_=update_dict,
        ).returning(literal_column("xmax = 0").label("inserted"))

        result = await self.session.execute(stmt)
        rows = result.fetchall()
        await self.session.commit()

        inserted = sum(1 for r in rows if r.inserted)
        updated = sum(1 for r in rows if not r.inserted)
        return inserted, updated

    async def check_health(self) -> bool:
        stmt = text("SELECT 1")
        result = await self.session.execute(stmt)
        return result.scalar_one() == 1

    async def create_scrape_run(self, pages_requested: Optional[int]) -> ScrapeRun:
        run = ScrapeRun(
            pages_requested=pages_requested,
            started_at=datetime.now(timezone.utc),
            status="running",
        )
        self.session.add(run)
        await self.session.commit()
        await self.session.refresh(run)
        return run

    async def update_scrape_run(self, run: ScrapeRun, **kwargs: Any) -> ScrapeRun:
        for key, value in kwargs.items():
            setattr(run, key, value)
        self.session.add(run)
        await self.session.commit()
        await self.session.refresh(run)
        return run

    async def add_scrape_error(
        self,
        run_id: int,
        stage: str,
        message: str,
        source_url: Optional[str] = None,
    ) -> ScrapeError:
        error = ScrapeError(
            run_id=run_id,
            stage=stage,
            message=message,
            source_url=source_url,
            created_at=datetime.now(timezone.utc),
        )
        self.session.add(error)
        await self.session.commit()
        await self.session.refresh(error)
        return error

    async def get_scrape_run(self, run_id: int) -> Optional[ScrapeRun]:
        result = await self.session.execute(
            select(ScrapeRun).where(ScrapeRun.id == run_id).options(selectinload(ScrapeRun.errors))
        )
        return result.scalar_one_or_none()

    async def list_scrape_runs(
        self,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[ScrapeRun], int]:
        count_query = select(func.count()).select_from(ScrapeRun)
        total_result = await self.session.execute(count_query)
        total = total_result.scalar_one()

        offset = (page - 1) * page_size
        query = select(ScrapeRun).order_by(ScrapeRun.id.desc()).offset(offset).limit(page_size)
        result = await self.session.execute(query)
        items = list(result.scalars().all())
        return items, total
