from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql+asyncpg://learning_engine:learning_engine@localhost:5432/learning_engine"
    database_sync_url: str = "postgresql://learning_engine:learning_engine@localhost:5432/learning_engine"

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

    # CRM inbound debounce: quiet-window (seconds) to coalesce several rapid
    # messages from the same conversation into one pipeline run. 0 disables it.
    crm_debounce_seconds: float = 5.0

    # LLM Providers
    openai_api_key: str = ""
    anthropic_api_key: str = ""

    # LLM Config
    primary_llm_provider: str = "openai"
    primary_llm_model: str = "gpt-4o"
    # OpenAI Fast mode (was "Priority processing"): ~2x cost, meaningfully lower
    # tail latency/variance — confirmed empirically 2026-09-24 (stdev 95ms vs
    # 196ms, max 807ms vs 1109ms on this account). On for the main response
    # (biggest $/token, biggest latency share); off for the analyzer by default.
    # Adjust either independently via env — no code change needed.
    primary_llm_service_tier: str | None = "priority"
    analyzer_llm_model: str = "gpt-4o-mini"
    analyzer_llm_service_tier: str | None = None
    # Fase 4.2: fuse intent/sentiment/stage/contact_signals into one LLM call
    # instead of 4 parallel ones (~57% of turn latency measured 2026-09-23).
    # Flip to False to roll back to the 4-call path without a redeploy if eval
    # quality regresses — see tests/evals/.
    use_unified_analyzer: bool = True

    # RAG retrieval: hybrid (dense + lexical, RRF-fused) then an LLM reranker.
    # Either can be flipped off to fall back to pure vector top_k — see the
    # KnowledgeEngine and tests/evals/.
    use_hybrid_search: bool = True
    use_reranker: bool = True

    # App
    app_env: str = "development"
    log_level: str = "INFO"

    # CORS — explicit origins plus a regex. In dev the regex allows any
    # localhost/127.0.0.1 port (e.g. the Vite app and the Electron companion app).
    cors_origins: list[str] = ["http://localhost:5173"]
    cors_origin_regex: str = r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$"

    # Voice
    retell_api_key: str = ""  # optional global fallback; per-org keys come per-call from the CRM
    crm_webhook_url: str = ""
    # CRM API base URL — used to resolve which org owns an inbound call's dialed
    # number (reverse of crm_webhook_url, which only receives events). Authed
    # with internal_api_token as a shared LearningEngine<->CRM secret.
    crm_base_url: str = ""

    # Provisioning
    provisioning_secret: str = ""

    # Internal API token — required by internal/training endpoints (learning,
    # testing, agents, timeline, roleplay, assistant, episode). Enforced always
    # when set; when unset, requests are only allowed in development. Also
    # doubles as the signing secret for the UI session cookie (see auth.py) —
    # it's already a server-only secret of the same trust level, no need for
    # a second one.
    internal_api_token: str = ""

    # Password for the LearningEngine UI's login screen (POST /auth/login). The
    # browser never sees internal_api_token directly anymore — login exchanges
    # this password for a short-lived signed session cookie.
    ui_login_password: str = ""

    # Observability
    pipeline_version: str = "1.0.0"
    prompt_version: str = "response_v1"

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
