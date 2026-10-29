import math
import time
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import text

from app.core.exceptions import ScrapeLockError, ScrapeRunNotFoundError
from app.core.logging import logger
from app.db.session import engine
from app.repositories.book_repository import BookRepository
from app.schemas.scrape import (
    ScrapeErrorResponse,
    ScrapeRunDetailResponse,
    ScrapeRunPaginationResponse,
    ScrapeRunResponse,
    ScrapeSummaryResponse,
)
from app.scraper.client import ScraperClient
from app.scraper.runner import ScraperRunner

ADVISORY_LOCK_ID = 918273645


class ScrapeService:
    def __init__(self, repository: BookRepository) -> None:
        self.repository = repository

    async def run_scrape(
        self,
        pages: int = 3,
        full: bool = False,
        client: Optional[ScraperClient] = None,
    ) -> ScrapeSummaryResponse:
        # Hold a dedicated connection across the run to scope the advisory lock
        lock_conn = await engine.connect()
        locked = False
        try:
            lock_res = await lock_conn.execute(
                text("SELECT pg_try_advisory_lock(:lock_id)"),
                {"lock_id": ADVISORY_LOCK_ID},
            )
            locked = bool(lock_res.scalar_one())
            if not locked:
                raise ScrapeLockError("A scrape is already running.")

            start_time = time.monotonic()
            actual_pages = 50 if full or pages == 0 else min(pages, 50)
            run = await self.repository.create_scrape_run(pages_requested=actual_pages)

            async def on_batch(batch: list[dict]) -> tuple[int, int]:
                return await self.repository.upsert_batch(batch)

            async def on_error(stage: str, message: str, source_url: Optional[str]) -> None:
                await self.repository.add_scrape_error(
                    run_id=run.id,
                    stage=stage,
                    message=message,
                    source_url=source_url,
                )

            scrape_client = client or ScraperClient()
            try:
                runner = ScraperRunner(
                    client=scrape_client,
                    on_batch=on_batch,
                    on_error=on_error,
                )
                result = await runner.run(pages_to_scrape=pages, full=full)

                duration_s = round(time.monotonic() - start_time, 2)
                finished_at = datetime.now(timezone.utc)

                await self.repository.update_scrape_run(
                    run,
                    finished_at=finished_at,
                    status="succeeded",
                    books_seen=result["books_seen"],
                    inserted=result["inserted"],
                    updated=result["updated"],
                    failed=result["failed"],
                )

                return ScrapeSummaryResponse(
                    run_id=run.id,
                    status="succeeded",
                    pages=result["pages"],
                    books_seen=result["books_seen"],
                    inserted=result["inserted"],
                    updated=result["updated"],
                    failed=result["failed"],
                    duration_s=duration_s,
                )
            except Exception as e:
                duration_s = round(time.monotonic() - start_time, 2)
                finished_at = datetime.now(timezone.utc)
                logger.error(f"Scrape run {run.id} failed: {e}", exc_info=True)

                await self.repository.update_scrape_run(
                    run,
                    finished_at=finished_at,
                    status="failed",
                    error=str(e),
                )
                raise
            finally:
                if client is None:
                    await scrape_client.close()
        finally:
            try:
                if locked:
                    await lock_conn.execute(
                        text("SELECT pg_advisory_unlock(:lock_id)"),
                        {"lock_id": ADVISORY_LOCK_ID},
                    )
            finally:
                await lock_conn.close()

    async def get_run(self, run_id: int) -> ScrapeRunDetailResponse:
        run = await self.repository.get_scrape_run(run_id)
        if run is None:
            raise ScrapeRunNotFoundError("Scrape run not found")

        errors = [ScrapeErrorResponse.model_validate(err) for err in run.errors]
        run_data = ScrapeRunResponse.model_validate(run).model_dump()
        return ScrapeRunDetailResponse(**run_data, errors=errors)

    async def list_runs(self, page: int = 1, page_size: int = 20) -> ScrapeRunPaginationResponse:
        runs, total = await self.repository.list_scrape_runs(page=page, page_size=page_size)
        pages = math.ceil(total / page_size) if total > 0 else 0
        items = [ScrapeRunResponse.model_validate(r) for r in runs]
        return ScrapeRunPaginationResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            pages=pages,
        )
