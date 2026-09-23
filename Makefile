.PHONY: up down migrate seed run test lint eval

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

# Fase 3 (eval suite): runs tests/evals/scenarios/*.yaml through the real
# pipeline + LLM-as-judge. Fails (nonzero exit) if any scenario fails — meant
# as a pre-publish / CI gate, not just a report. Requires AGENT=<agent_version_id>.
eval:
	@if [ -z "$(AGENT)" ]; then \
		echo "Usage: make eval AGENT=<agent_version_id>"; exit 1; \
	fi
	python -m scripts.eval_suite --agent $(AGENT)

lint:
	ruff check src/ tests/
	ruff format --check src/ tests/

format:
	ruff check --fix src/ tests/
	ruff format src/ tests/
