import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient, Response


@pytest.mark.asyncio
async def test_scrape_api_flow(client: AsyncClient, listing_page_html: str, detail_page_html: str):
    async def mock_get(url: str):
        if "catalogue/page-" in url:
            return Response(200, text=listing_page_html)
        return Response(200, text=detail_page_html)

    with patch("app.scraper.client.ScraperClient.get", new_callable=AsyncMock) as mocked_get:
        mocked_get.side_effect = mock_get

        resp = await client.post("/scrape", json={"pages": 1, "full": False})
        assert resp.status_code == 200
        summary = resp.json()
        assert summary["status"] == "succeeded"
        assert summary["pages"] == 1
        assert summary["books_seen"] == 20
        assert summary["inserted"] >= 0
        run_id = summary["run_id"]

        # List runs
        runs_resp = await client.get("/scrape/runs")
        assert runs_resp.status_code == 200
        runs_data = runs_resp.json()
        assert runs_data["total"] >= 1
        assert any(r["id"] == run_id for r in runs_data["items"])

        # Get run detail
        detail_resp = await client.get(f"/scrape/runs/{run_id}")
        assert detail_resp.status_code == 200
        run_detail = detail_resp.json()
        assert run_detail["id"] == run_id
        assert run_detail["status"] == "succeeded"
        assert "errors" in run_detail


@pytest.mark.asyncio
async def test_sequential_scrape_runs(
    client: AsyncClient, listing_page_html: str, detail_page_html: str
):
    async def mock_get(url: str):
        if "catalogue/page-" in url:
            return Response(200, text=listing_page_html)
        return Response(200, text=detail_page_html)

    with patch("app.scraper.client.ScraperClient.get", new_callable=AsyncMock) as mocked_get:
        mocked_get.side_effect = mock_get

        resp1 = await client.post("/scrape", json={"pages": 1, "full": False})
        assert resp1.status_code == 200
        assert resp1.json()["status"] == "succeeded"

        resp2 = await client.post("/scrape", json={"pages": 1, "full": False})
        assert resp2.status_code == 200
        assert resp2.json()["status"] == "succeeded"


@pytest.mark.asyncio
async def test_parallel_scrape_conflict(
    client: AsyncClient, listing_page_html: str, detail_page_html: str
):
    async def slow_get(url: str):
        await asyncio.sleep(0.2)
        if "catalogue/page-" in url:
            return Response(200, text=listing_page_html)
        return Response(200, text=detail_page_html)

    with patch("app.scraper.client.ScraperClient.get", new_callable=AsyncMock) as mocked_get:
        mocked_get.side_effect = slow_get

        task1 = client.post("/scrape", json={"pages": 1, "full": False})
        task2 = client.post("/scrape", json={"pages": 1, "full": False})

        resps = await asyncio.gather(task1, task2)
        status_codes = sorted([r.status_code for r in resps])
        assert status_codes == [200, 409]


@pytest.mark.asyncio
async def test_scrape_run_not_found(client: AsyncClient):
    resp = await client.get("/scrape/runs/999999")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Scrape run not found"
