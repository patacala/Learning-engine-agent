.PHONY: up down migrate seed run test lint

up:
	docker compose -f docker/docker-compose.yml up -d

down:
	docker compose -f docker/docker-compose.yml down

migrate:
	alembic upgrade head

seed:
	python scripts/seed_knowledge.py

run:
	uvicorn prosales.main:app --reload --host 0.0.0.0 --port 8000

test:
	pytest -v

lint:
	ruff check src/ tests/
	ruff format --check src/ tests/

format:
	ruff check --fix src/ tests/
	ruff format src/ tests/
