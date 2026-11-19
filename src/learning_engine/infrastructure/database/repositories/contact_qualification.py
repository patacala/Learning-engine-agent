"""Repository for per-contact qualification."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from learning_engine.engines.contact_qualification.models import ContactQualification
from learning_engine.infrastructure.database.models_contact_qualification import (
    ContactQualificationModel,
)

_FIELDS = (
    "temperature",
    "status",
    "readiness",
    "bant",
    "signals",
    "facts",
    "suggested_transition",
    "last_conversation_id",
)


def _to_dto(m: ContactQualificationModel) -> ContactQualification:
    return ContactQualification(
        id=m.id,
        client_id=m.client_id,
        organization_id=m.organization_id,
        temperature=m.temperature,
        status=m.status,
        readiness=m.readiness,
        bant=m.bant or {},
        signals=m.signals or {},
        facts=m.facts or {},
        suggested_transition=m.suggested_transition,
        last_conversation_id=m.last_conversation_id,
    )


class SQLContactQualificationRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_client(self, client_id: UUID) -> ContactQualification | None:
        stmt = select(ContactQualificationModel).where(
            ContactQualificationModel.client_id == client_id
        )
        m = (await self.session.execute(stmt)).scalar_one_or_none()
        return _to_dto(m) if m else None

    async def upsert(self, qual: ContactQualification) -> ContactQualification:
        stmt = select(ContactQualificationModel).where(
            ContactQualificationModel.client_id == qual.client_id
        )
        existing = (await self.session.execute(stmt)).scalar_one_or_none()
        if existing is None:
            model = ContactQualificationModel(
                client_id=qual.client_id,
                organization_id=qual.organization_id,
                **{f: getattr(qual, f) for f in _FIELDS},
            )
            self.session.add(model)
            await self.session.flush()
            qual.id = model.id
            return qual

        for f in _FIELDS:
            setattr(existing, f, getattr(qual, f))
        existing.updated_at = datetime.utcnow()
        await self.session.flush()
        qual.id = existing.id
        return qual
