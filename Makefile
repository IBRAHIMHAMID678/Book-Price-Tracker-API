.PHONY: up down test lint scrape

up:
	docker compose up --build -d

down:
	docker compose down -v

test:
	docker compose exec app pytest -q --cov=app/scraper --cov=app/api --cov-report=term-missing

lint:
	docker compose exec app ruff check .

scrape:
	docker compose exec app python -m app.scraper.cli --pages 3
