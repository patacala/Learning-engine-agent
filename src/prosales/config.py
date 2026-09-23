from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql+asyncpg://prosales:prosales@localhost:5432/prosales"
    database_sync_url: str = "postgresql://prosales:prosales@localhost:5432/prosales"

    # DB connection pool (per worker). Real ceiling = workers x (pool_size + max_overflow).
    db_pool_size: int = 20
    db_max_overflow: int = 20
    db_pool_timeout: int = 30

    # Concurrency limits
    background_max_concurrency: int = 8  # cap on live-learning background tasks
    llm_max_retries: int = 3
    llm_timeout_seconds: float = 60.0
    web_workers: int = 4

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # LLM Providers
    openai_api_key: str = ""
    anthropic_api_key: str = ""

    # LLM Config
    primary_llm_provider: str = "openai"
    primary_llm_model: str = "gpt-4o"
    analyzer_llm_model: str = "gpt-4o-mini"

    # App
    app_env: str = "development"
    log_level: str = "INFO"

    # CORS — explicit origins plus a regex. In dev the regex allows any
    # localhost/127.0.0.1 port (e.g. the Vite app and the Electron companion app).
    cors_origins: list[str] = ["http://localhost:5173"]
    cors_origin_regex: str = r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$"

    # Voice
    retell_api_key: str = ""
    crm_webhook_url: str = ""

    # Provisioning
    provisioning_secret: str = ""

    # Internal API token — required by internal/training endpoints (learning,
    # testing, agents, timeline, roleplay, assistant, episode). Enforced always
    # when set; when unset, requests are only allowed in development.
    internal_api_token: str = ""

    # Observability
    pipeline_version: str = "1.0.0"
    prompt_version: str = "response_v1"

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
