.PHONY: dev test lint format migrate seed clean

dev:
	docker compose -f docker/docker-compose.yml up --build

dev-backend:
	uvicorn aloha.main:app --reload --host 0.0.0.0 --port 8000

dev-frontend:
	cd frontend && npm run dev

test:
	pytest tests/ -v

test-cov:
	pytest tests/ --cov=src/aloha --cov-report=html

lint:
	ruff check src/ tests/
	mypy src/

format:
	ruff format src/ tests/
	ruff check --fix src/ tests/

migrate:
	alembic -c src/aloha/db/alembic.ini upgrade head

migrate-new:
	alembic -c src/aloha/db/alembic.ini revision --autogenerate -m "$(MSG)"

seed:
	python scripts/seed_db.py

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name .mypy_cache -exec rm -rf {} +
	find . -type d -name .ruff_cache -exec rm -rf {} +
	rm -rf htmlcov .coverage dist build *.egg-info

install:
	pip install -e ".[dev]"
	pre-commit install
	playwright install chromium
