#!/bin/sh
# Backend container entrypoint: apply DB migrations, then start the API.
# Migrations are idempotent (alembic upgrade head). If you run MULTIPLE api
# replicas, move this to a one-off deploy step instead of the entrypoint to
# avoid concurrent-migration races.
set -e

echo "[entrypoint] Running database migrations (alembic upgrade head)..."
alembic upgrade head

echo "[entrypoint] Starting uvicorn with ${WEB_WORKERS:-4} worker(s)..."
exec uvicorn learning_engine.main:app --host 0.0.0.0 --port 8000 --workers "${WEB_WORKERS:-4}"
