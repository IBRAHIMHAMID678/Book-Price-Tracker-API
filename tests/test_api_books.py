from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import CheckViolationError
from app.models.book import Book


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["database"] == "ok"


@pytest.mark.asyncio
async def test_health_check_unhealthy(client: AsyncClient):
    with patch(
        "app.services.book_service.BookService.check_health",
        new_callable=AsyncMock,
    ) as mock_health:
        mock_health.return_value = False
        resp = await client.get("/health")
        assert resp.status_code == 503
        assert resp.json()["detail"] == "Database unavailable"

        mock_health.side_effect = Exception("Connection lost")
        resp2 = await client.get("/health")
        assert resp2.status_code == 503
        assert "Database error" in resp2.json()["detail"]


@pytest.mark.asyncio
async def test_root_endpoint(client: AsyncClient):
    response = await client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Book Price Tracker API"
    assert data["docs"] == "/docs"


@pytest.mark.asyncio
async def test_create_and_get_book(client: AsyncClient):
    payload = {
        "title": "Test Book One",
        "price": "29.99",
        "currency": "GBP",
        "rating": 4,
        "in_stock": True,
        "stock_count": 15,
        "availability_raw": "In stock (15 available)",
        "category": "Science",
        "description": "A book about science.",
        "upc": "testupc12345",
        "source_url": "https://books.toscrape.com/catalogue/test-book-one_9999/index.html",
        "image_url": "https://books.toscrape.com/media/test.jpg",
    }
    resp = await client.post("/books", json=payload)
    assert resp.status_code == 201
    created = resp.json()
    assert created["id"] is not None
    assert created["title"] == payload["title"]
    assert created["price"] == "29.99"
    assert created["rating"] == 4
    book_id = created["id"]

    get_resp = await client.get(f"/books/{book_id}")
    assert get_resp.status_code == 200
    book_data = get_resp.json()
    assert book_data["id"] == book_id
    assert book_data["title"] == payload["title"]
    assert book_data["price"] == "29.99"


@pytest.mark.asyncio
async def test_create_book_null_availability_raw(client: AsyncClient, db_session: AsyncSession):
    payload = {
        "title": "Null Availability Book",
        "price": "14.99",
        "rating": 3,
        "in_stock": True,
        "availability_raw": None,
        "category": "Poetry",
        "source_url": "https://books.toscrape.com/catalogue/null-avail_1111/index.html",
    }
    resp = await client.post("/books", json=payload)
    assert resp.status_code == 201
    created = resp.json()
    assert created["id"] is not None
    book_id = created["id"]

    stmt = select(Book).where(Book.id == book_id)
    res = await db_session.execute(stmt)
    book = res.scalar_one()
    assert book.availability_raw == "In stock"


@pytest.mark.asyncio
async def test_create_duplicate_source_url(client: AsyncClient):
    payload = {
        "title": "Duplicate URL Book",
        "price": "19.99",
        "rating": 5,
        "in_stock": True,
        "category": "Travel",
        "source_url": "https://books.toscrape.com/catalogue/duplicate_8888/index.html",
    }
    resp1 = await client.post("/books", json=payload)
    assert resp1.status_code == 201

    resp2 = await client.post("/books", json=payload)
    assert resp2.status_code == 409
    assert "detail" in resp2.json()


@pytest.mark.asyncio
async def test_create_invalid_rating_check(client: AsyncClient):
    payload = {
        "title": "Invalid Rating Book",
        "price": "9.99",
        "rating": 9,
        "in_stock": True,
        "category": "Travel",
        "source_url": "https://books.toscrape.com/catalogue/invalid-rating_7777/index.html",
    }
    resp = await client.post("/books", json=payload)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_and_patch_route_exceptions(client: AsyncClient):
    with patch(
        "app.services.book_service.BookService.create_book",
        new_callable=AsyncMock,
    ) as mock_create:
        mock_create.side_effect = CheckViolationError("rating between 1 and 5 check failed")
        resp = await client.post(
            "/books",
            json={
                "title": "T",
                "price": "10.00",
                "source_url": "https://books.toscrape.com/catalogue/chk_1/index.html",
            },
        )
        assert resp.status_code == 422

    with patch(
        "app.services.book_service.BookService.update_book",
        new_callable=AsyncMock,
    ) as mock_update:
        mock_update.side_effect = CheckViolationError("rating check failed")
        resp = await client.patch("/books/1", json={"price": "20.00"})
        assert resp.status_code == 422


@pytest.mark.asyncio
async def test_patch_book(client: AsyncClient):
    payload = {
        "title": "Original Title",
        "price": "10.00",
        "rating": 2,
        "in_stock": True,
        "category": "Fiction",
        "source_url": "https://books.toscrape.com/catalogue/patch-book_7777/index.html",
    }
    resp = await client.post("/books", json=payload)
    assert resp.status_code == 201
    book_id = resp.json()["id"]

    patch_resp = await client.patch(
        f"/books/{book_id}",
        json={"price": "15.50", "rating": 4, "in_stock": False},
    )
    assert patch_resp.status_code == 200
    patched = patch_resp.json()
    assert patched["price"] == "15.50"
    assert patched["rating"] == 4
    assert patched["in_stock"] is False
    assert patched["title"] == "Original Title"


@pytest.mark.asyncio
async def test_delete_book(client: AsyncClient):
    payload = {
        "title": "To Be Deleted",
        "price": "5.00",
        "rating": 1,
        "in_stock": False,
        "category": "Mystery",
        "source_url": "https://books.toscrape.com/catalogue/delete-book_6666/index.html",
    }
    resp = await client.post("/books", json=payload)
    assert resp.status_code == 201
    book_id = resp.json()["id"]

    del_resp = await client.delete(f"/books/{book_id}")
    assert del_resp.status_code == 204

    get_resp = await client.get(f"/books/{book_id}")
    assert get_resp.status_code == 404
    assert get_resp.json()["detail"] == "Book not found"


@pytest.mark.asyncio
async def test_not_found_endpoints(client: AsyncClient):
    get_resp = await client.get("/books/999999")
    assert get_resp.status_code == 404
    assert get_resp.json()["detail"] == "Book not found"

    patch_resp = await client.patch("/books/999999", json={"title": "Non-existent"})
    assert patch_resp.status_code == 404

    del_resp = await client.delete("/books/999999")
    assert del_resp.status_code == 404


@pytest.mark.asyncio
async def test_validation_errors(client: AsyncClient):
    resp = await client.get("/books?min_price=50&max_price=10")
    assert resp.status_code == 422

    resp2 = await client.get("/books?page_size=500")
    assert resp2.status_code == 422

    resp3 = await client.get("/books?page=0")
    assert resp3.status_code == 422


@pytest.mark.asyncio
async def test_filter_and_pagination(client: AsyncClient):
    for i in range(1, 6):
        await client.post(
            "/books",
            json={
                "title": f"Category Book {i}",
                "price": f"{i * 10}.00",
                "rating": i,
                "in_stock": True,
                "category": "Travel" if i <= 3 else "Classics",
                "source_url": f"https://books.toscrape.com/catalogue/filter-book-{i}_555{i}/index.html",
            },
        )

    resp = await client.get("/books?category=Travel")
    assert resp.status_code == 200
    data = resp.json()
    assert all(b["category"] == "Travel" for b in data["items"])

    resp_price = await client.get("/books?min_price=20&max_price=40")
    assert resp_price.status_code == 200
    data_price = resp_price.json()
    for b in data_price["items"]:
        assert 20.00 <= float(b["price"]) <= 40.00

    resp_sort = await client.get("/books?page=1&page_size=2&sort=price&order=desc")
    assert resp_sort.status_code == 200
    data_sort = resp_sort.json()
    assert len(data_sort["items"]) <= 2
    assert data_sort["page"] == 1
    assert data_sort["page_size"] == 2
