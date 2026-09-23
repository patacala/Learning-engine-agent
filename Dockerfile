FROM python:3.12-slim

WORKDIR /app

# System deps: none required beyond the slim base (asyncpg/openai are pure-python
# wheels). Keep the image small.

COPY pyproject.toml .
COPY src/ src/
RUN pip install --no-cache-dir .

COPY alembic/ alembic/
COPY alembic.ini .
COPY scripts/ scripts/
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8000

# Container-level healthcheck (also used by compose depends_on). Uses stdlib so
# no curl is needed in the image.
HEALTHCHECK --interval=15s --timeout=5s --start-period=40s --retries=5 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health').status==200 else 1)" || exit 1

# Entrypoint runs `alembic upgrade head` then launches uvicorn.
# Multi-process for concurrency. WEB_WORKERS overrides at deploy time.
# Real DB-connection ceiling = WEB_WORKERS x (db_pool_size + db_max_overflow);
# size vs Postgres max_connections (pgbouncer recommended in front at scale).
ENTRYPOINT ["/entrypoint.sh"]
