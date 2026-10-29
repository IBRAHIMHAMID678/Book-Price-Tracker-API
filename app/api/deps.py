from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.repositories.book_repository import BookRepository
from app.services.book_service import BookService
from app.services.scrape_service import ScrapeService


def get_book_repository(
    session: AsyncSession = Depends(get_db_session),
) -> BookRepository:
    return BookRepository(session)


def get_book_service(
    repository: BookRepository = Depends(get_book_repository),
) -> BookService:
    return BookService(repository)


def get_scrape_service(
    repository: BookRepository = Depends(get_book_repository),
) -> ScrapeService:
    return ScrapeService(repository)
