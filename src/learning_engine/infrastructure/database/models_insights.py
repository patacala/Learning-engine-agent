"""SQLAlchemy model for Insights (Layer 4).

Insights are generated ONLY from aggregated cluster statistics — the explanation
is a view over the memory, never the memory. A published insight carries a
behavior_rule directive that is injected into the agent's prompt.
"""

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from .models import Base


class InsightModel(Base):
    __tablename__ = "insights"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    organization_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)

    insight_text: Mapped[str] = mapped_column(Text)  # human-readable conclusion
    behavior_rule: Mapped[str] = mapped_column(Text, default="")  # directive injected into prompt
    supporting_cluster_ids: Mapped[list] = mapped_column(JSONB, default=list)
    pattern_kinds: Mapped[list] = mapped_column(JSONB, default=list)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    sample_size: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="draft", index=True)  # draft | published | dismissed
    # Embedding of behavior_rule, used to scope prompt injection to rules
    # relevant to the current message instead of always sending every rule.
    embedding = mapped_column(Vector(1536), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
