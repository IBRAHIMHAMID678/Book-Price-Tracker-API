# Book Price Tracker API

A production-grade REST API backed by PostgreSQL that extracts, stores, and tracks book data scraped idempotently from [books.toscrape.com](https://books.toscrape.com).

---

## Overview

The Book Price Tracker API is built with asynchronous Python (FastAPI + asyncpg + Async SQLAlchemy). It scrapes book listings and detail pages, stores price tracking data with exact decimal precision, guarantees idempotent upserts, and provides clean REST endpoints for book querying, filtering, pagination, and scrape job orchestration.

---

## Features

- **Asynchronous Architecture:** Full async pipeline from HTTP scraping (`httpx`) to database operations (`SQLAlchemy 2.0` + `asyncpg`).
- **Precision Pricing:** `price` stored as `NUMERIC(10,2)` in PostgreSQL and `Decimal` in Python, serialized as Decimal-safe strings.
- **Strict Layered Design:** Clean separation of concerns: `routes → services → repositories → models`.
- **Idempotent Upsert:** Re-scraping the same pages updates records without producing duplicate rows using PostgreSQL's `INSERT ... ON CONFLICT (source_url) DO UPDATE ...`.
- **Concurrency Guard:** Prevents overlapping scraper runs via PostgreSQL advisory locks (`pg_try_advisory_lock`).
- **Resilient Scraper:** Jittered concurrency limiting, exponential backoff retries via `tenacity`, and graceful error tracking.
- **Alembic Migrations:** Database schema generated and managed strictly via migration scripts.
- **Containerized:** Multi-stage Docker build running under a non-root `appuser` (UID 1000).

---

## Tech Stack

- **Language:** Python 3.12
- **Framework:** FastAPI 0.115.6 + Uvicorn 0.34.0
- **Database:** PostgreSQL 16 (via `asyncpg` 0.30.0 + `SQLAlchemy` 2.0.36)
- **Migrations:** Alembic 1.14.0
- **Data Validation & Settings:** Pydantic 2.10.4 + Pydantic-Settings 2.7.0
- **Scraping:** HTTPX 0.28.1 + BeautifulSoup4 4.12.3 + lxml 5.3.0
- **Resilience:** Tenacity 9.0.0
- **Testing & Quality:** Pytest 8.3.4, Pytest-Asyncio 0.25.0, Pytest-Cov 6.0.0, Ruff 0.8.4

---

## Project Structure

```
book-price-tracker/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── db/
│   │   ├── __init__.py
│   │   ├── session.py
│   │   └── base.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── book.py
│   │   └── scrape_run.py
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── book.py
│   │   └── scrape.py
│   ├── repositories/
│   │   ├── __init__.py
│   │   └── book_repository.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── book_service.py
│   │   └── scrape_service.py
│   ├── api/
│   │   ├── __init__.py
│   │   ├── deps.py
│   │   └── routes/
│   │       ├── __init__.py
│   │       ├── books.py
│   │       ├── scrape.py
│   │       └── health.py
│   ├── scraper/
│   │   ├── __init__.py
│   │   ├── client.py
│   │   ├── parser.py
│   │   ├── runner.py
│   │   └── cli.py
│   └── core/
│       ├── __init__.py
│       ├── logging.py
│       └── exceptions.py
├── alembic/
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       └── 0001_initial.py
├── alembic.ini
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── fixtures/
│   │   ├── listing_page.html
│   │   └── detail_page.html
│   ├── test_parser.py
│   ├── test_api_books.py
│   ├── test_api_scrape.py
│   └── test_idempotency.py
├── scripts/
│   └── entrypoint.sh
├── Dockerfile
├── docker-compose.yml
├── .dockerignore
├── .gitignore
├── .env.example
├── requirements.txt
├── requirements-dev.txt
├── pyproject.toml
├── Makefile
└── README.md
```

---

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) & [Docker Compose](https://docs.docker.com/compose/)
- Alternatively, Python 3.12+ and PostgreSQL 16+ for local native execution.

---

## Quick Start

The service runs with a single command on a clean machine with no `.env` file required:

```bash
docker compose up --build -d
```

The application runs at `http://localhost:8000` with interactive OpenAPI documentation at `http://localhost:8000/docs`.

To tear down:
```bash
docker compose down -v
```

---

## Environment Variables & Credentials

All credentials in `docker-compose.yml` use `${VAR:-default}` syntax. The default values (user `books`, password `books_dev_pw`, database `books`) are strictly development defaults and require zero setup. In staging or production, create a `.env` file (or set environment variables) to override them. `.env` is git-ignored and never committed.

| Variable | Description | Default | Required |
|---|---|---|---|
| `DATABASE_URL` | PostgreSQL asyncpg connection string | `postgresql+asyncpg://books:books_dev_pw@localhost:5432/books` | Yes |
| `APP_ENV` | Application environment (`dev`, `prod`, `test`) | `dev` | No |
| `LOG_LEVEL` | Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) | `INFO` | No |
| `SCRAPE_BASE_URL` | Target base URL | `https://books.toscrape.com` | No |
| `SCRAPE_CONCURRENCY` | Maximum concurrent HTTP scraper requests | `8` | No |
| `SCRAPE_TIMEOUT` | Scraper HTTP client timeout in seconds | `20` | No |
| `POSTGRES_USER` | PostgreSQL container username (dev default) | `books` | No |
| `POSTGRES_PASSWORD` | PostgreSQL container password (dev default) | `books_dev_pw` | No |
| `POSTGRES_DB` | PostgreSQL container database name (dev default) | `books` | No |

---

## API Reference

All endpoints are mounted directly without path prefixes.

### 1. Root Endpoint
`GET /`

```bash
curl -s http://localhost:8000/
```

Response (`200 OK`):
```json
{
  "name": "Book Price Tracker API",
  "docs": "/docs"
}
```

---

### 2. Health Check
`GET /health`

```bash
curl -s http://localhost:8000/health
```

Response (`200 OK`):
```json
{
  "status": "ok",
  "database": "ok"
}
```

---

### 3. List Books
`GET /books`

Query parameters:
- `page` (int, default: 1, min: 1)
- `page_size` (int, default: 20, min: 1, max: 100)
- `category` (string, case-insensitive match)
- `min_price` (decimal, min: 0)
- `max_price` (decimal, min: 0, must be >= min_price)
- `sort` (`id` | `price` | `rating` | `title`, default: `id`)
- `order` (`asc` | `desc`, default: `asc`)

```bash
curl -s "http://localhost:8000/books?category=Travel&min_price=10&max_price=50&page=1&page_size=20&sort=price&order=asc"
```

Response (`200 OK`):
```json
{
  "items": [
    {
      "id": 1,
      "title": "It's Only the Himalayas",
      "price": "45.17",
      "currency": "GBP",
      "rating": 2,
      "in_stock": true,
      "stock_count": 19,
      "category": "Travel",
      "description": "Whether you are a seasoned traveller...",
      "source_url": "https://books.toscrape.com/catalogue/its-only-the-himalayas_981/index.html",
      "image_url": "https://books.toscrape.com/media/cache/27/a5/27a53d0425bcda51ec034562479aa101.jpg",
      "scraped_at": "2026-10-29T12:00:00Z"
    }
  ],
  "total": 11,
  "page": 1,
  "page_size": 20,
  "pages": 1
}
```

---

### 4. Get Book by ID
`GET /books/{book_id}`

```bash
curl -s http://localhost:8000/books/1
```

Response (`200 OK`):
```json
{
  "id": 1,
  "title": "It's Only the Himalayas",
  "price": "45.17",
  "currency": "GBP",
  "rating": 2,
  "in_stock": true,
  "stock_count": 19,
  "category": "Travel",
  "description": "Whether you are a seasoned traveller...",
  "source_url": "https://books.toscrape.com/catalogue/its-only-the-himalayas_981/index.html",
  "image_url": "https://books.toscrape.com/media/cache/27/a5/27a53d0425bcda51ec034562479aa101.jpg",
  "scraped_at": "2026-10-29T12:00:00Z"
}
```

Response (`404 Not Found`):
```json
{
  "detail": "Book not found"
}
```

---

### 5. Create Book
`POST /books`

```bash
curl -s -X POST http://localhost:8000/books \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Clean Code",
    "price": "35.50",
    "currency": "GBP",
    "rating": 5,
    "in_stock": true,
    "stock_count": 12,
    "category": "Technology",
    "source_url": "https://books.toscrape.com/catalogue/clean-code_9999/index.html"
  }'
```

Response (`201 Created`):
```json
{
  "id": 41,
  "title": "Clean Code",
  "price": "35.50",
  "currency": "GBP",
  "rating": 5,
  "in_stock": true,
  "stock_count": 12,
  "category": "Technology",
  "description": null,
  "source_url": "https://books.toscrape.com/catalogue/clean-code_9999/index.html",
  "image_url": null,
  "scraped_at": "2026-10-29T12:00:00Z"
}
```

---

### 6. Update Book (Partial)
`PATCH /books/{book_id}`

```bash
curl -s -X PATCH http://localhost:8000/books/1 \
  -H "Content-Type: application/json" \
  -d '{
    "price": "39.99",
    "rating": 4
  }'
```

Response (`200 OK`):
```json
{
  "id": 1,
  "title": "It's Only the Himalayas",
  "price": "39.99",
  "currency": "GBP",
  "rating": 4,
  "in_stock": true,
  "stock_count": 19,
  "category": "Travel",
  "description": "Whether you are a seasoned traveller...",
  "source_url": "https://books.toscrape.com/catalogue/its-only-the-himalayas_981/index.html",
  "image_url": "https://books.toscrape.com/media/cache/27/a5/27a53d0425bcda51ec034562479aa101.jpg",
  "scraped_at": "2026-10-29T12:00:00Z"
}
```

---

### 7. Delete Book
`DELETE /books/{book_id}`

```bash
curl -s -X DELETE http://localhost:8000/books/1 -w "%{http_code}\n"
```

Response: `204 No Content` (Empty body).

---

### 8. Trigger Scrape
`POST /scrape`

```bash
curl -s -X POST http://localhost:8000/scrape \
  -H "Content-Type: application/json" \
  -d '{"pages": 2, "full": false}'
```

Response (`200 OK`):
```json
{
  "run_id": 1,
  "status": "succeeded",
  "pages": 2,
  "books_seen": 40,
  "inserted": 40,
  "updated": 0,
  "failed": 0,
  "duration_s": 4.15
}
```

If another scrape is currently running (`409 Conflict`):
```json
{
  "detail": "A scrape is already running."
}
```

---

### 9. List Scrape Runs
`GET /scrape/runs`

```bash
curl -s "http://localhost:8000/scrape/runs?page=1&page_size=10"
```

Response (`200 OK`):
```json
{
  "items": [
    {
      "id": 1,
      "started_at": "2026-10-29T12:00:00Z",
      "finished_at": "2026-10-29T12:00:04Z",
      "status": "succeeded",
      "pages_requested": 2,
      "books_seen": 40,
      "inserted": 40,
      "updated": 0,
      "failed": 0,
      "error": null
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 10,
  "pages": 1
}
```

---

### 10. Get Scrape Run Details
`GET /scrape/runs/{run_id}`

```bash
curl -s http://localhost:8000/scrape/runs/1
```

Response (`200 OK`):
```json
{
  "id": 1,
  "started_at": "2026-10-29T12:00:00Z",
  "finished_at": "2026-10-29T12:00:04Z",
  "status": "succeeded",
  "pages_requested": 2,
  "books_seen": 40,
  "inserted": 40,
  "updated": 0,
  "failed": 0,
  "error": null,
  "errors": []
}
```

---

## Running the Scraper

### Via API
Trigger a scrape for 3 pages:
```bash
curl -s -X POST http://localhost:8000/scrape \
  -H "Content-Type: application/json" \
  -d '{"pages": 3}'
```

To scrape all 50 pages:
```bash
curl -s -X POST http://localhost:8000/scrape \
  -H "Content-Type: application/json" \
  -d '{"full": true}'
```

### Via CLI
Run inside Docker container:
```bash
docker compose exec app python -m app.scraper.cli --pages 3
```

Scrape all 50 pages via CLI:
```bash
docker compose exec app python -m app.scraper.cli --pages 0
```

---

## Idempotency Note

The scraper ensures strict data idempotency using PostgreSQL's `ON CONFLICT (source_url) DO UPDATE SET`:
- `source_url` serves as the natural unique key.
- Re-running the scraper on previously scraped pages inserts **zero duplicate rows**.
- Existing records have their mutable attributes updated, and `(xmax = 0)` identifies inserts vs updates.
- Scrape runs track `books_seen`, `inserted`, `updated`, and `failed` accurately.

---

## Running Tests

Execute test suite with coverage report:
```bash
docker compose exec app pytest -q --cov=app/scraper --cov=app/api --cov-report=term-missing
```

Or via Makefile:
```bash
make test
```

Check code quality with Ruff:
```bash
docker compose exec app ruff check .
```

---

## Design Decisions

- **PostgreSQL Advisory Locks:** Used `pg_try_advisory_lock(918273645)` on a dedicated checkout connection to enforce single-job execution concurrency without external brokers like Redis or Celery.
- **Async End-to-End:** Built entirely using async FastAPI, Async SQLAlchemy, asyncpg, and httpx to prevent thread pool exhaustion and blocking event loops.
- **Decimal Representation:** Used `NUMERIC(10,2)` in PostgreSQL and `Decimal` in Python to prevent floating-point rounding errors on currency calculations.
- **Deterministic Pagination:** Ordered by primary sort criteria with a secondary tiebreak on `Book.id` matching the requested sort direction (`Book.id DESC` for desc, `Book.id ASC` for asc) to guarantee stable page boundaries.
- **Decoupled Architecture:** Strict dependency inversion (`Routes → Services → Repositories → Models`) ensures easy testability and isolated database rollback fixtures.

---

## Limitations

- Scrapes static HTML pages from `books.toscrape.com`; does not execute client-side JavaScript.
- **Concurrency & Rate Limiting:** Default concurrency is 8 workers (configurable via `SCRAPE_CONCURRENCY`) with 50–150ms jittered delays to crawl politely.
- Long-running scrape jobs over all 50 pages run synchronously on the HTTP request thread when triggered via the POST endpoint.

---

## License

MIT License.
