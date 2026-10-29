import asyncio
from collections.abc import Callable, Coroutine
from datetime import datetime, timezone
from typing import Any, Optional

import httpx

from app.config import settings
from app.core.exceptions import ParseError
from app.core.logging import logger
from app.scraper.client import ScraperClient
from app.scraper.parser import parse_detail_page, parse_listing_page


class ScraperRunner:
    def __init__(
        self,
        client: ScraperClient,
        on_batch: Callable[[list[dict[str, Any]]], Coroutine[Any, Any, tuple[int, int]]],
        on_error: Optional[Callable[[str, str, Optional[str]], Coroutine[Any, Any, Any]]] = None,
        base_url: Optional[str] = None,
        max_consecutive_failures: int = 20,
    ) -> None:
        self.client = client
        self.on_batch = on_batch
        self.on_error = on_error
        self.base_url = (base_url or settings.SCRAPE_BASE_URL).rstrip("/")
        self.consecutive_failures = 0
        self.max_consecutive_failures = max_consecutive_failures

    async def _record_error(
        self, stage: str, message: str, source_url: Optional[str] = None
    ) -> None:
        logger.warning(f"Scraper error in stage '{stage}' for '{source_url}': {message}")
        if self.on_error:
            await self.on_error(stage, message, source_url)

    async def run(self, pages_to_scrape: int = 3, full: bool = False) -> dict[str, int]:
        total_pages = 50 if full or pages_to_scrape == 0 else min(pages_to_scrape, 50)
        books_seen = 0
        total_inserted = 0
        total_updated = 0
        total_failed = 0

        pending_batch: list[dict[str, Any]] = []

        for page_num in range(1, total_pages + 1):
            if self.consecutive_failures >= self.max_consecutive_failures:
                raise RuntimeError(
                    f"Scrape aborted after {self.consecutive_failures} consecutive failures"
                )

            page_url = f"{self.base_url}/catalogue/page-{page_num}.html"
            try:
                resp = await self.client.get(page_url)
                if resp.status_code == 404:
                    total_failed += 1
                    self.consecutive_failures += 1
                    await self._record_error("fetch_listing", "Page not found (404)", page_url)
                    continue

                book_urls, _ = parse_listing_page(resp.text, page_url)
                self.consecutive_failures = 0
            except Exception as e:
                total_failed += 1
                self.consecutive_failures += 1
                await self._record_error("fetch_listing", str(e), page_url)
                if self.consecutive_failures >= self.max_consecutive_failures:
                    raise RuntimeError(
                        f"Scrape aborted after {self.consecutive_failures} consecutive failures"
                    )
                continue

            # Fetch detail pages concurrently using client's semaphore
            async def fetch_and_parse(book_url: str) -> Optional[dict[str, Any]]:
                try:
                    detail_resp = await self.client.get(book_url)
                    if detail_resp.status_code == 404:
                        await self._record_error(
                            "fetch_detail", "Book page not found (404)", book_url
                        )
                        return None

                    book_data = parse_detail_page(detail_resp.text, book_url)
                    book_data["scraped_at"] = datetime.now(timezone.utc)
                    return book_data
                except ParseError as pe:
                    await self._record_error("parse_detail", str(pe), book_url)
                    return None
                except (httpx.HTTPError, Exception) as exc:
                    await self._record_error("fetch_detail", str(exc), book_url)
                    return None

            tasks = [fetch_and_parse(url) for url in book_urls]
            results = await asyncio.gather(*tasks)

            for res in results:
                if res is not None:
                    books_seen += 1
                    self.consecutive_failures = 0
                    pending_batch.append(res)
                else:
                    total_failed += 1
                    self.consecutive_failures += 1
                    if self.consecutive_failures >= self.max_consecutive_failures:
                        raise RuntimeError(
                            f"Scrape aborted after {self.consecutive_failures} consecutive failures"
                        )

            # Insert in batches of 100
            while len(pending_batch) >= 100:
                batch = pending_batch[:100]
                pending_batch = pending_batch[100:]
                ins, upd = await self.on_batch(batch)
                total_inserted += ins
                total_updated += upd

        # Flush any remaining items
        if pending_batch:
            ins, upd = await self.on_batch(pending_batch)
            total_inserted += ins
            total_updated += upd

        return {
            "pages": total_pages,
            "books_seen": books_seen,
            "inserted": total_inserted,
            "updated": total_updated,
            "failed": total_failed,
        }
