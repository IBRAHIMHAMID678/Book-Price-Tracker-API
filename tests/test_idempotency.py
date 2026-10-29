from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.book import Book


@pytest.mark.asyncio
async def test_scraper_idempotency(
    client: AsyncClient,
    db_session: AsyncSession,
    listing_page_html: str,
    detail_page_html: str,
):
    # Ensure clean state for idempotency test
    await db_session.execute(delete(Book))
    await db_session.commit()

    async def mock_get(url: str):
        if "catalogue/page-" in url:
            return Response(200, text=listing_page_html)
        return Response(200, text=detail_page_html)

    with patch("app.scraper.client.ScraperClient.get", new_callable=AsyncMock) as mocked_get:
        mocked_get.side_effect = mock_get

        # First run: should insert books
        resp1 = await client.post("/scrape", json={"pages": 1, "full": False})
        assert resp1.status_code == 200
        summary1 = resp1.json()
        assert summary1["status"] == "succeeded"
        assert summary1["books_seen"] == 20
        assert summary1["inserted"] == 20
        assert summary1["updated"] == 0

        # Verify count in DB
        count_query = select(func.count()).select_from(Book)
        count_res1 = await db_session.execute(count_query)
        initial_count = count_res1.scalar_one()
        assert initial_count == 20

        # Second run: same fixtures -> zero duplicate rows, count unchanged
        resp2 = await client.post("/scrape", json={"pages": 1, "full": False})
        assert resp2.status_code == 200
        summary2 = resp2.json()
        assert summary2["status"] == "succeeded"
        assert summary2["books_seen"] == 20
        assert summary2["inserted"] == 0
        assert summary2["updated"] == 20

        # Verify count in DB is still exactly 20
        count_res2 = await db_session.execute(count_query)
        after_count = count_res2.scalar_one()
        assert after_count == initial_count
