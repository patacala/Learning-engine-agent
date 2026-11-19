"""Contact endpoints — per-contact qualification for the CRM funnel."""

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from learning_engine.api.v1.dependencies import get_db_session, require_agent_context
from learning_engine.engines.contact_qualification.models import ContactQualification
from learning_engine.infrastructure.database.models import ClientModel
from learning_engine.infrastructure.database.repositories.contact_qualification import (
    SQLContactQualificationRepository,
)

router = APIRouter(prefix="/contact", tags=["contact"])


@router.get("/{external_id}/qualification")
async def get_contact_qualification(
    external_id: str,
    session: AsyncSession = Depends(get_db_session),
    x_api_key: str | None = Header(None),
) -> dict:
    """Current qualification of a contact (by the CRM's external id), org-scoped."""
    agent_context = await require_agent_context(session, x_api_key)
    org_id = agent_context.organization_id

    stmt = select(ClientModel).where(
        ClientModel.external_id == external_id,
        ClientModel.organization_id == org_id,
    )
    client = (await session.execute(stmt)).scalar_one_or_none()
    if client is None:
        raise HTTPException(status_code=404, detail="Contact not found")

    qual = await SQLContactQualificationRepository(session).get_by_client(client.id)
    if qual is None:
        # Contact exists but hasn't been qualified yet — return neutral default.
        qual = ContactQualification(client_id=client.id, organization_id=client.organization_id)
    return {"external_id": external_id, **qual.to_public()}
