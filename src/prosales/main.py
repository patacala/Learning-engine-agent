from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from prosales.config import settings

from prosales.api.v1.endpoints.agents import router as agents_router
from prosales.api.v1.endpoints.assistant import router as assistant_router
from prosales.api.v1.endpoints.auth import router as auth_router
from prosales.api.v1.endpoints.contact import router as contact_router
from prosales.api.v1.endpoints.conversation import router as conversation_router
from prosales.api.v1.endpoints.crm_inbound import router as crm_inbound_router
from prosales.api.v1.endpoints.episode import router as episode_router
from prosales.api.v1.endpoints.health import router as health_router
from prosales.api.v1.endpoints.learning import router as learning_router
from prosales.api.v1.endpoints.management import router as management_router
from prosales.api.v1.endpoints.provisioning import router as provisioning_router
from prosales.api.v1.endpoints.roleplay import router as roleplay_router
from prosales.api.v1.endpoints.timeline import router as timeline_router
from prosales.api.v1.endpoints.testing import router as testing_router
from prosales.channels.voice.websocket import router as voice_ws_router
from prosales.infrastructure.observability import configure_logging

configure_logging()

app = FastAPI(
    title="ProSales - Sistema Cognitivo de Ventas",
    version="0.1.0",
    description="Cognitive sales system with voice-first architecture",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=settings.cors_origin_regex,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE"],
    allow_headers=["*"],
)

app.include_router(health_router, prefix="/api/v1")
app.include_router(auth_router, prefix="/api/v1")
app.include_router(conversation_router, prefix="/api/v1")
app.include_router(crm_inbound_router, prefix="/api/v1")
app.include_router(contact_router, prefix="/api/v1")
app.include_router(episode_router, prefix="/api/v1")
app.include_router(timeline_router, prefix="/api/v1")
app.include_router(learning_router, prefix="/api/v1")
app.include_router(agents_router, prefix="/api/v1")
app.include_router(testing_router, prefix="/api/v1")
app.include_router(provisioning_router, prefix="/api/v1")
app.include_router(management_router, prefix="/api/v1")
app.include_router(roleplay_router, prefix="/api/v1")
app.include_router(assistant_router, prefix="/api/v1")
app.include_router(voice_ws_router)
