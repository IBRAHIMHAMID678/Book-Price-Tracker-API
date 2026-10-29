import asyncio
import random
from typing import Any, Optional

import httpx
from tenacity import (
    AsyncRetrying,
    retry_if_exception,
    stop_after_attempt,
    wait_random_exponential,
)

from app.config import settings

USER_AGENT = "BookPriceTracker/1.0 (+https://github.com/yourname/book-price-tracker)"


def is_retryable_exception(exc: BaseException) -> bool:
    if isinstance(exc, (httpx.TimeoutException, httpx.TransportError)):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        if exc.response.status_code == 404:
            return False
        if exc.response.status_code == 429 or exc.response.status_code >= 500:
            return True
    return False


class ScraperClient:
    def __init__(
        self,
        concurrency: Optional[int] = None,
        timeout: Optional[float] = None,
        client: Optional[httpx.AsyncClient] = None,
    ) -> None:
        self.concurrency = concurrency or settings.SCRAPE_CONCURRENCY
        self.semaphore = asyncio.Semaphore(self.concurrency)
        self.timeout_sec = timeout or settings.SCRAPE_TIMEOUT
        self._external_client = client is not None
        if client is not None:
            self._client = client
        else:
            self._client = httpx.AsyncClient(
                headers={"User-Agent": USER_AGENT},
                timeout=httpx.Timeout(10.0, read=self.timeout_sec),
                follow_redirects=True,
                limits=httpx.Limits(max_connections=10, max_keepalive_connections=10),
            )

    async def __aenter__(self) -> "ScraperClient":
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.close()

    async def close(self) -> None:
        if not self._external_client:
            await self._client.aclose()

    async def get(self, url: str) -> httpx.Response:
        # Cap concurrency
        async with self.semaphore:
            # 100 ms ± 50 ms jittered delay before each request
            delay = random.uniform(0.05, 0.15)
            await asyncio.sleep(delay)

            retryer = AsyncRetrying(
                stop=stop_after_attempt(3),
                wait=wait_random_exponential(multiplier=1, max=10),
                retry=retry_if_exception(is_retryable_exception),
                reraise=True,
            )

            async for attempt in retryer:
                with attempt:
                    response = await self._client.get(url)
                    if response.status_code != 404:
                        response.raise_for_status()
                    return response

            raise RuntimeError(f"Failed to fetch {url} after retries")
