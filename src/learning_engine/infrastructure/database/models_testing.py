"""SQLAlchemy models for the Test Playground.

Only saved scenarios are persisted. Test conversations themselves are never
written to the database; they run through the pipeline in isolated mode.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from .models import Base


class TestScenarioModel(Base):
    """A reusable business-context scenario for testing an agent."""

    __tablename__ = "test_scenarios"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    organization_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    company_name: Mapped[str] = mapped_column(String(255), default="")
    # documents: list of {id, title, content, category}
    documents: Mapped[list] = mapped_column(JSONB, default=list)
    # quick_facts: {key: value}
    quick_facts: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
