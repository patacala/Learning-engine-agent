"""Seed learned knowledge for the "sales pro" agent from the Aura (Audi Miami South) prompt.

One-off, idempotent seed. Converts the objection-handling database and a few soft
conversational guidelines from that prompt into LearningEngine' LEARNED layer (not
static prompt text):

- ``behavior_rules`` (published insights) — generalized directives the LLM applies
  in its own voice every turn. This is the PRIMARY channel: it never gets recited
  verbatim, so it stays human/on-brand instead of robotic.
- ``proven_plays`` (positive pattern_clusters) — one representative excerpt per
  objection family, surfaced ONLY when the client's inferred state matches
  (``condition_profile.works_when``), via ``PatternRetriever``.

Deliberately NOT seeded here: identity/personality/words_never_use/hard guardrails
(max-attempt rules, AI disclosure, price disclaimers) — those are DECLARED config,
not learning; provision them via the agents/management endpoints if needed. Also
not seeded: a pile of ``winning_expressions`` — that channel is a global top-3,
non-contextual and verbatim, so seeding many would surface the wrong one, out of
context, and recited literally (exactly the robotic effect this seed avoids).

Idempotent: re-running clears prior seed artifacts (tagged ``"seed:aura"`` in
``pattern_kinds`` / ``condition_profile``) for the resolved agent before inserting.

Usage:
    python -m scripts.seed_aura_learning
"""

import asyncio
import sys
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from learning_engine.config import settings
from learning_engine.engines.insights.models import Insight
from learning_engine.engines.moves.states import ClientState
from learning_engine.infrastructure.database.models_agent import (
    AgentModel,
    AgentVersionModel,
    OrganizationAgentModel,
)
from learning_engine.infrastructure.database.models_insights import InsightModel
from learning_engine.infrastructure.database.models_performance import PatternClusterModel
from learning_engine.infrastructure.database.repositories.insights import SQLInsightsRepository

SEED_TAG = "seed:aura"

# --- behavior_rules: generalized directives, applied in the agent's own voice ---
BEHAVIOR_RULES = [
    # Price / budget objections
    (
        "Ante objecion de precio, valida la decision, pregunta si compara contra "
        "otro modelo o marca, y reencuadra hacia el pago mensual de lease antes de "
        "hablar del precio total."
    ),
    (
        "Si el cliente dice que no puede pagarlo ahora, pregunta si prefiere lease "
        "o financiamiento antes de asumir que esta fuera de su alcance, y menciona "
        "opciones pre-owned/CPO como alternativa de precio."
    ),
    (
        "Si el cliente dice que otros dealers son mas baratos, no compitas en "
        "precio ni hables mal de la competencia: reencuadra hacia la experiencia "
        "total (servicio, relacion, soporte post-venta) e invita a visitar."
    ),
    (
        "Si el cliente pide un mejor precio, no niegues ni prometas descuento: "
        "explica que el numero final depende de configuracion, trade-in y "
        "financiamiento, y ofrece agendar con un especialista para numeros exactos."
    ),
    # Timing / delay objections
    (
        "Si el cliente dice que lo tiene que pensar, valida sin presionar y "
        "pregunta si la duda es de presupuesto o de timing para identificar la "
        "objecion real antes de insistir con la cita."
    ),
    (
        "Si el cliente dice que no esta listo aun, no presiones: pregunta cuando "
        "se imagina dando el paso y ofrece un test drive sin compromiso como "
        "puente de bajo riesgo."
    ),
    (
        "Si el cliente pide que lo llamen despues en vez de seguir ahora, propone "
        "agendar un horario especifico en vez de un seguimiento generico."
    ),
    # Third-party objections
    (
        "Si el cliente necesita consultar con su pareja o familia antes de "
        "decidir, ofrece enviar informacion para revisar juntos o invitar a ambos "
        "a un test drive conjunto."
    ),
    # Lack of need / low interest
    (
        "Si el cliente dice que no le interesa o que solo esta mirando, no "
        "insistas: ofrece un resumen breve sin presion y deja la puerta abierta "
        "para cuando este listo."
    ),
    (
        "Si el cliente ya tiene un Audi y esta contento, no empujes una compra: "
        "menciona el servicio y especiales de servicio, y mantente disponible "
        "para cuando quiera actualizar."
    ),
    # Trust / hesitation
    (
        "Si el cliente menciona malas experiencias previas en dealers, reconoce "
        "el punto con empatia genuina y ofrece un ambiente sin presion en vez de "
        "argumentar o minimizar su experiencia."
    ),
    (
        "Si el cliente pregunta si es una persona real o una IA, se honesto de "
        "inmediato: identificate como asistente y ofrece conectar con el equipo "
        "humano si lo prefiere."
    ),
    # Competition
    (
        "Si el cliente menciona que esta viendo otras marcas o dealers, no "
        "compares negativamente: pregunta que le atrae de esas opciones para "
        "entender que le importa y recomendar en base a eso."
    ),
    # Service-specific
    (
        "Si el cliente objeta el precio del servicio, justifica con piezas "
        "originales y tecnicos certificados (protegen garantia y valor de "
        "reventa) antes de mencionar especiales de servicio disponibles."
    ),
    # Soft conversational guidelines (energy matching, never assume)
    (
        "Ajusta el ritmo de la conversacion a la energia del cliente: si esta "
        "apurado o listo, ve directo al punto; si es analitico, da mas detalle; "
        "si esta confundido, simplifica un tema a la vez."
    ),
    (
        "Nunca asumas informacion del cliente que no ha dado explicitamente "
        "(modelo, presupuesto, timeline): pregunta en vez de suponer, y no "
        "repitas preguntas que ya respondio."
    ),
    (
        "Cuando el cliente este listo para el siguiente paso, ofrece agendar "
        "como una consecuencia natural de la conversacion, no como una tactica "
        "de venta forzada."
    ),
]

# --- proven_plays: one representative cluster per objection family, surfaced ---
# --- only when the inferred client_state matches (contextual retrieval) ------
PROVEN_PLAYS = [
    {
        "move_kind": "objection_handling",
        "canonical_excerpt": (
            "Entiendo, es una decision grande. Cuando dices que es caro, "
            "lo comparas con otro modelo o con otra marca? Podemos ver opciones "
            "de lease que hacen el pago mensual mas manejable de lo que parece."
        ),
        "client_state": ClientState.DESCONFIADO.value,
    },
    {
        "move_kind": "reframe",
        "canonical_excerpt": (
            "El pago mensual suele sorprender comparado con el precio de lista. "
            "Estas pensando en lease, financiamiento, o de contado? Eso cambia "
            "bastante el numero."
        ),
        "client_state": ClientState.COMPARANDO.value,
    },
    {
        "move_kind": "objection_handling",
        "canonical_excerpt": (
            "Tiene sentido tomarte el tiempo. Usualmente cuando alguien lo "
            "quiere pensar es por presupuesto o por timing, te suena familiar "
            "alguno de los dos?"
        ),
        "client_state": ClientState.INDECISO.value,
    },
    {
        "move_kind": "rapport",
        "canonical_excerpt": (
            "Te entiendo completamente, y aprecio que lo compartas. Aqui "
            "buscamos un ambiente sin presion, tu marcas el ritmo y nosotros "
            "respondemos tus preguntas."
        ),
        "client_state": ClientState.FRUSTRADO.value,
    },
    {
        "move_kind": "social_proof",
        "canonical_excerpt": (
            "Es inteligente comparar opciones. Que es lo que mas te atrae de "
            "esas otras marcas? Eso me ayuda a mostrarte el Audi que mejor "
            "encaja con lo que buscas."
        ),
        "client_state": ClientState.COMPARANDO.value,
    },
    {
        "move_kind": "urgency",
        "canonical_excerpt": (
            "Eso funciona. Las ofertas de lease actuales vencen a fin de mes, "
            "asi que si quieres asegurar el precio de hoy podemos agendar una "
            "visita antes de esa fecha. Sin presion de tu lado."
        ),
        "client_state": ClientState.INDECISO.value,
    },
]


async def _resolve_agent_version(session: AsyncSession) -> AgentVersionModel:
    """Resolve the "sales pro" agent's version to seed. Falls back to the first
    agent in the DB by creation date if no exact name match exists."""
    stmt = select(AgentModel).where(AgentModel.name.ilike("sales pro"))
    agent = (await session.execute(stmt)).scalars().first()
    if agent is None:
        stmt = select(AgentModel).order_by(AgentModel.created_at.asc())
        agent = (await session.execute(stmt)).scalars().first()
    if agent is None:
        raise RuntimeError("No agent found in the database to seed.")

    stmt = (
        select(AgentVersionModel)
        .where(AgentVersionModel.agent_id == agent.id)
        .order_by(AgentVersionModel.is_published.desc(), AgentVersionModel.version_number.desc())
    )
    version = (await session.execute(stmt)).scalars().first()
    if version is None:
        raise RuntimeError(f"Agent {agent.name!r} ({agent.id}) has no versions.")

    print(f"Resolved agent: {agent.name!r} (agent_id={agent.id}) -> version {version.id}")
    return version


async def _resolve_organization_id(session: AsyncSession, agent_version_id):
    stmt = select(OrganizationAgentModel.organization_id).where(
        OrganizationAgentModel.agent_version_id == agent_version_id
    )
    return (await session.execute(stmt)).scalars().first()


async def _clear_prior_seed(session: AsyncSession, agent_version_id) -> None:
    """Remove artifacts from a previous run of this seed (idempotency).

    Filters in Python after a scoped fetch rather than a JSONB path operator,
    to stay independent of dialect-specific containment/astext syntax.
    """
    await session.execute(
        delete(InsightModel).where(
            InsightModel.agent_version_id == agent_version_id,
            InsightModel.pattern_kinds.contains([SEED_TAG]),
        )
    )

    stmt = select(PatternClusterModel).where(
        PatternClusterModel.agent_version_id == agent_version_id
    )
    clusters = (await session.execute(stmt)).scalars().all()
    stale_ids = [
        c.id for c in clusters if (c.condition_profile or {}).get("seed") == SEED_TAG
    ]
    if stale_ids:
        await session.execute(
            delete(PatternClusterModel).where(PatternClusterModel.id.in_(stale_ids))
        )


async def seed(session: AsyncSession) -> dict[str, int]:
    version = await _resolve_agent_version(session)
    organization_id = await _resolve_organization_id(session, version.id)

    await _clear_prior_seed(session, version.id)

    insights_repo = SQLInsightsRepository(session)
    for rule in BEHAVIOR_RULES:
        await insights_repo.save(
            Insight(
                organization_id=organization_id,
                insight_text="Regla de manejo de objeciones/tono seedeada desde el prompt Aura.",
                behavior_rule=rule,
                supporting_cluster_ids=[],
                pattern_kinds=[SEED_TAG],
                confidence=0.8,
                sample_size=0,
                status="published",
            ),
            agent_version_id=version.id,
        )

    for play in PROVEN_PLAYS:
        cluster = PatternClusterModel(
            id=uuid4(),
            agent_version_id=version.id,
            organization_id=organization_id,
            move_kind=play["move_kind"],
            polarity="positive",
            canonical_excerpt=play["canonical_excerpt"],
            occurrence_count=1,
            positive_count=1,
            negative_count=0,
            success_rate=0.8,
            avg_score=0.8,
            condition_profile={"seed": SEED_TAG, "works_when": {play["client_state"]: 1}},
            rank=1,
        )
        session.add(cluster)

    await session.commit()
    return {
        "agent_version_id": str(version.id),
        "behavior_rules": len(BEHAVIOR_RULES),
        "proven_plays": len(PROVEN_PLAYS),
    }


async def main():
    engine = create_async_engine(settings.database_url)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        counts = await seed(session)
        print(
            f"Seed complete for agent_version_id={counts['agent_version_id']}: "
            f"{counts['behavior_rules']} behavior_rules, "
            f"{counts['proven_plays']} proven_plays."
        )

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
