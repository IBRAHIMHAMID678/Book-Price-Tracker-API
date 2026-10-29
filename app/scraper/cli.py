import argparse
import asyncio
import json
import sys

from app.db.session import async_session_factory
from app.repositories.book_repository import BookRepository
from app.services.scrape_service import ScrapeService


async def main_async(pages: int, full: bool) -> int:
    async with async_session_factory() as session:
        repository = BookRepository(session)
        service = ScrapeService(repository)
        try:
            summary = await service.run_scrape(pages=pages, full=full)
            sys.stdout.write(json.dumps(summary.model_dump()) + "\n")
            sys.stdout.flush()
            return 0
        except Exception as e:
            sys.stderr.write(f"Scrape failed: {e}\n")
            sys.stderr.flush()
            return 1


def main() -> None:
    parser = argparse.ArgumentParser(description="Book scraper CLI")
    parser.add_argument(
        "--pages",
        type=int,
        default=3,
        help="Number of pages to scrape (0 means all 50 pages)",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        default=False,
        help="Force scraping all 50 pages",
    )
    args = parser.parse_args()

    exit_code = asyncio.run(main_async(pages=args.pages, full=args.full))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
