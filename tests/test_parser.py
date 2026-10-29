from decimal import Decimal
from unittest.mock import AsyncMock

import httpx
import pytest

from app.core.exceptions import ParseError
from app.scraper.client import ScraperClient, is_retryable_exception
from app.scraper.parser import (
    extract_slug_from_url,
    parse_detail_page,
    parse_listing_page,
)
from app.scraper.runner import ScraperRunner


def test_parse_listing_page(listing_page_html: str):
    base_url = "https://books.toscrape.com/catalogue/page-1.html"
    book_urls, next_url = parse_listing_page(listing_page_html, base_url)

    assert len(book_urls) == 20
    assert (
        book_urls[0] == "https://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html"
    )
    assert next_url == "https://books.toscrape.com/catalogue/page-2.html"


def test_parse_detail_page(detail_page_html: str):
    source_url = "https://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html"
    data = parse_detail_page(detail_page_html, source_url)

    assert data["source_url"] == source_url
    assert data["title"] == "A Light in the Attic"
    assert data["slug"] == "a-light-in-the-attic_1000"
    assert data["price"] == Decimal("51.77")
    assert data["currency"] == "GBP"
    assert data["rating"] == 3
    assert data["in_stock"] is True
    assert data["stock_count"] == 22
    assert "In stock (22 available)" in data["availability_raw"]
    assert data["category"] == "Poetry"
    assert data["description"] is not None
    assert len(data["description"]) > 50
    assert data["upc"] == "a897fe39b1053632"
    assert (
        data["image_url"]
        == "https://books.toscrape.com/media/cache/fe/72/fe72f0532301ec28892ae79a629a293c.jpg"
    )


def test_extract_slug():
    url1 = "https://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html"
    assert extract_slug_from_url(url1) == "a-light-in-the-attic_1000"

    url2 = "https://books.toscrape.com/catalogue/simple-book/index.html"
    assert extract_slug_from_url(url2) == "simple-book"


def test_parse_detail_page_missing_title():
    html = """
    <html><body>
        <p class="price_color">£10.00</p>
        <p class="star-rating One"></p>
        <ul class="breadcrumb"><li>1</li><li>2</li><li><a>Category</a></li></ul>
    </body></html>
    """
    with pytest.raises(ParseError, match="Missing title"):
        parse_detail_page(html, "https://example.com/book_1/index.html")


def test_parse_detail_page_empty_title():
    html = """
    <html><body>
        <h1>   </h1>
        <p class="price_color">£10.00</p>
        <p class="star-rating One"></p>
        <ul class="breadcrumb"><li>1</li><li>2</li><li><a>Category</a></li></ul>
    </body></html>
    """
    with pytest.raises(ParseError, match="Empty title"):
        parse_detail_page(html, "https://example.com/book_1/index.html")


def test_parse_detail_page_missing_price():
    html = """
    <html><body>
        <h1>Sample Title</h1>
        <p class="star-rating One"></p>
        <ul class="breadcrumb"><li>1</li><li>2</li><li><a>Category</a></li></ul>
    </body></html>
    """
    with pytest.raises(ParseError, match="Missing price"):
        parse_detail_page(html, "https://example.com/book_1/index.html")


def test_parse_detail_page_invalid_price():
    html = """
    <html><body>
        <h1>Sample Title</h1>
        <p class="price_color">NotAPrice</p>
        <p class="star-rating One"></p>
        <ul class="breadcrumb"><li>1</li><li>2</li><li><a>Category</a></li></ul>
    </body></html>
    """
    with pytest.raises(ParseError, match="Invalid price"):
        parse_detail_page(html, "https://example.com/book_1/index.html")


def test_parse_detail_page_missing_rating():
    html = """
    <html><body>
        <h1>Sample Title</h1>
        <p class="price_color">£10.00</p>
        <ul class="breadcrumb"><li>1</li><li>2</li><li><a>Category</a></li></ul>
    </body></html>
    """
    with pytest.raises(ParseError, match="Missing star-rating"):
        parse_detail_page(html, "https://example.com/book_1/index.html")


def test_parse_detail_page_missing_category():
    html = """
    <html><body>
        <h1>Sample Title</h1>
        <p class="price_color">£10.00</p>
        <p class="star-rating One"></p>
        <ul class="breadcrumb"><li>1</li></ul>
    </body></html>
    """
    with pytest.raises(ParseError, match="Missing category"):
        parse_detail_page(html, "https://example.com/book_1/index.html")


def test_parse_detail_page_empty_category():
    html = """
    <html><body>
        <h1>Sample Title</h1>
        <p class="price_color">£10.00</p>
        <p class="star-rating One"></p>
        <ul class="breadcrumb"><li>1</li><li>2</li><li><a>   </a></li></ul>
    </body></html>
    """
    with pytest.raises(ParseError, match="Empty category"):
        parse_detail_page(html, "https://example.com/book_1/index.html")


def test_retryable_exceptions():
    assert is_retryable_exception(httpx.ConnectTimeout("timeout")) is True
    assert is_retryable_exception(httpx.NetworkError("network")) is True
    assert is_retryable_exception(ValueError("error")) is False

    req = httpx.Request("GET", "http://test")
    resp_404 = httpx.Response(404, request=req)
    assert (
        is_retryable_exception(httpx.HTTPStatusError("not found", request=req, response=resp_404))
        is False
    )

    resp_429 = httpx.Response(429, request=req)
    assert (
        is_retryable_exception(
            httpx.HTTPStatusError("rate limited", request=req, response=resp_429)
        )
        is True
    )

    resp_500 = httpx.Response(500, request=req)
    assert (
        is_retryable_exception(
            httpx.HTTPStatusError("server error", request=req, response=resp_500)
        )
        is True
    )


@pytest.mark.asyncio
async def test_scraper_client_lifecycle():
    mock_transport = httpx.MockTransport(lambda request: httpx.Response(200, text="OK"))
    async with httpx.AsyncClient(transport=mock_transport) as h_client:
        async with ScraperClient(client=h_client) as s_client:
            res = await s_client.get("http://testserver")
            assert res.status_code == 200
            assert res.text == "OK"


@pytest.mark.asyncio
async def test_scraper_runner(listing_page_html: str, detail_page_html: str):
    async def mock_get(url: str):
        if "page-" in url:
            return httpx.Response(200, text=listing_page_html)
        return httpx.Response(200, text=detail_page_html)

    client = ScraperClient(client=httpx.AsyncClient())
    client.get = AsyncMock(side_effect=mock_get)

    batches: list[list[dict]] = []

    async def on_batch(batch: list[dict]) -> tuple[int, int]:
        batches.append(batch)
        return len(batch), 0

    errors: list[tuple[str, str, str | None]] = []

    async def on_error(stage: str, msg: str, url: str | None) -> None:
        errors.append((stage, msg, url))

    runner = ScraperRunner(
        client=client,
        on_batch=on_batch,
        on_error=on_error,
        base_url="https://books.toscrape.com",
    )
    result = await runner.run(pages_to_scrape=1, full=False)

    assert result["pages"] == 1
    assert result["books_seen"] == 20
    assert result["inserted"] == 20
    assert result["updated"] == 0
    assert result["failed"] == 0
    assert len(batches) == 1
    assert len(batches[0]) == 20


@pytest.mark.asyncio
async def test_scraper_runner_detail_404_and_parse_error(listing_page_html: str):
    async def mock_get(url: str):
        if "page-" in url:
            return httpx.Response(200, text=listing_page_html)
        if "a-light-in-the-attic" in url:
            return httpx.Response(404, text="Not Found")
        return httpx.Response(200, text="<html><body>Malformed</body></html>")

    client = ScraperClient(client=httpx.AsyncClient())
    client.get = AsyncMock(side_effect=mock_get)

    errors = []

    async def on_error(stage: str, msg: str, url: str | None) -> None:
        errors.append((stage, msg, url))

    async def on_batch(batch: list[dict]) -> tuple[int, int]:
        return len(batch), 0

    runner = ScraperRunner(
        client=client,
        on_batch=on_batch,
        on_error=on_error,
        base_url="https://books.toscrape.com",
        max_consecutive_failures=50,
    )
    result = await runner.run(pages_to_scrape=1, full=False)

    assert result["books_seen"] == 0
    assert result["failed"] == 20
    assert len(errors) == 20


@pytest.mark.asyncio
async def test_scraper_runner_listing_404():
    # Listing page 404 is recorded and skipped
    async def mock_get(url: str):
        return httpx.Response(404, text="Not Found")

    client = ScraperClient(client=httpx.AsyncClient())
    client.get = AsyncMock(side_effect=mock_get)

    errors = []

    async def on_error(stage: str, msg: str, url: str | None) -> None:
        errors.append((stage, msg, url))

    async def on_batch(batch: list[dict]) -> tuple[int, int]:
        return 0, 0

    runner = ScraperRunner(
        client=client,
        on_batch=on_batch,
        on_error=on_error,
        base_url="https://books.toscrape.com",
    )
    result = await runner.run(pages_to_scrape=1, full=False)

    assert result["books_seen"] == 0
    assert result["failed"] == 1
    assert any(e[0] == "fetch_listing" for e in errors)


@pytest.mark.asyncio
async def test_scraper_runner_consecutive_failures():
    async def mock_get(url: str):
        raise httpx.ConnectError("Connection failed")

    client = ScraperClient(client=httpx.AsyncClient())
    client.get = AsyncMock(side_effect=mock_get)

    async def on_batch(batch: list[dict]) -> tuple[int, int]:
        return 0, 0

    runner = ScraperRunner(
        client=client,
        on_batch=on_batch,
        base_url="https://books.toscrape.com",
    )
    runner.max_consecutive_failures = 2

    with pytest.raises(RuntimeError, match="consecutive failures"):
        await runner.run(pages_to_scrape=5)
