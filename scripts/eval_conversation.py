"""Eval a single turn through the REAL production pipeline — no UI, no clicking.

This calls ``PipelineRunner.run()`` directly — the exact same class used by
``POST /conversation/message`` (real chat) and the voice channel
(``channels/voice/adapter.py``). It is NOT a reimplementation: if a turn
behaves correctly here, it behaves identically wherever this agent is actually
deployed, because it's the same function, same DB, same providers.

It also does the exact same client/conversation bookkeeping the real endpoint
does (get-or-create client, get-or-create conversation) — the pipeline itself
unconditionally persists the assistant's reply (there's no "dry run" mode in
production), so a fake/nonexistent conversation_id would just crash on the FK
constraint instead of proving anything.

Prints a layer-by-layer breakdown (analysis → strategy → learning → response)
instead of just the final reply, so "why did it say that" doesn't require
reading source code or querying the DB by hand.

Usage:
    python -m scripts.eval_conversation --agent <agent_version_id> --message "..."
    # continue the same thread for a second turn:
    python -m scripts.eval_conversation --agent <id> --message "..." --conversation <id> --client <external_id>
"""

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path
from uuid import UUID, uuid4

# Without a handler, non-fatal `logger.warning(...)` calls deep in the
# pipeline (e.g. "Pattern retrieval failed (non-fatal)") are silently
# swallowed — which looks identical to "nothing matched". Surface them.
logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select

from prosales.api.v1.dependencies import get_redis_cache
from prosales.core.models.agent import AgentContext
from prosales.infrastructure.database.connection import async_session_factory
from prosales.infrastructure.database.models import ConversationModel
from prosales.infrastructure.database.models_agent import (
    AgentModel,
    AgentVersionModel,
    OrganizationAgentModel,
    OrganizationModel,
)
from prosales.infrastructure.database.repositories.client import SQLClientRepository
from prosales.infrastructure.database.repositories.conversation import SQLConversationRepository
from prosales.services.pipeline_runner import PipelineRunner


def _hr(title: str) -> None:
    print(f"\n{'─' * 8} {title} {'─' * (60 - len(title))}")


async def _load_agent_context(session, agent_version_id: UUID) -> AgentContext:
    """Build the AgentContext directly from agent_version_id (no API key).

    Deliberately NOT the Test Playground's ``_load_test_agent_context`` — that
    helper fabricates a random ``organization_id`` when the agent has no active
    org assignment, which is harmless in the fully-isolated Test Playground but
    breaks real persistence (FK to `organizations`) here. This mirrors what
    ``AgentContextResolver.resolve()`` builds in production, with the same
    "Training agents have organization_id=None" convention (see
    core/models/agent.py) instead of inventing one.
    """
    version = (
        await session.execute(
            select(AgentVersionModel).where(AgentVersionModel.id == agent_version_id)
        )
    ).scalar_one_or_none()
    if version is None:
        print(f"Agent version {agent_version_id} not found.", file=sys.stderr)
        sys.exit(1)

    agent = (
        await session.execute(select(AgentModel).where(AgentModel.id == version.agent_id))
    ).scalar_one_or_none()
    if agent is None:
        print(f"Agent {version.agent_id} not found.", file=sys.stderr)
        sys.exit(1)

    assignment = (
        await session.execute(
            select(OrganizationAgentModel).where(
                OrganizationAgentModel.agent_version_id == agent_version_id,
                OrganizationAgentModel.is_active.is_(True),
            )
        )
    ).scalar_one_or_none()

    org = None
    if assignment is not None:
        org = (
            await session.execute(
                select(OrganizationModel).where(OrganizationModel.id == assignment.organization_id)
            )
        ).scalar_one_or_none()

    if org is None:
        print(
            "⚠️  Este agente no tiene una organización activa asignada — "
            "corriendo con organization_id=None, igual que producción lo haría "
            "para un agente sin asignar (no un valor inventado).",
            file=sys.stderr,
        )

    return AgentContext(
        organization_id=org.id if org else None,
        organization_name=org.name if org else "",
        org_capabilities=list(org.capabilities or []) if org else ["knowledge", "voice"],
        agent_id=agent.id,
        agent_version_id=version.id,
        agent_name=agent.name,
        agent_type=agent.agent_type,
        agent_capabilities=version.capabilities or [],
    )


async def run(args: argparse.Namespace) -> None:
    agent_version_id = UUID(args.agent)
    cache = get_redis_cache()

    async with async_session_factory() as session:
        agent_context = await _load_agent_context(session, agent_version_id)

        # The real pipeline (build_cognitive_graph's persist step) unconditionally
        # writes the assistant's reply to `messages`, which has a hard FK to
        # `conversations` — there is no "ephemeral" mode in production, so this
        # script doesn't pretend to have one either. It always does the exact
        # same client/conversation bookkeeping as POST /conversation/message.
        client_repo = SQLClientRepository(session)
        conv_repo = SQLConversationRepository(session)
        # client_id here is an EXTERNAL id (phone number, chat handle, ...),
        # same as the real request — the repo resolves or creates the internal
        # ClientModel and gives back its real UUID.
        client = await client_repo.get_or_create(
            args.client or f"eval-cli-{uuid4()}",
            organization_id=agent_context.organization_id,
        )
        if args.conversation:
            conversation = await conv_repo.get_by_id(UUID(args.conversation))
            if conversation is None:
                print(f"Conversation {args.conversation} not found.", file=sys.stderr)
                sys.exit(1)
        else:
            conversation = ConversationModel(
                id=uuid4(),
                client_id=client.id,
                organization_id=agent_context.organization_id,
                agent_version_id=agent_version_id,
            )
            await conv_repo.save(conversation)
        await session.commit()
        client_id, conversation_id = client.id, conversation.id

    runner = PipelineRunner(async_session_factory, cache=cache)
    result = await runner.run(
        message=args.message,
        client_id=client_id,
        conversation_id=conversation_id,
        agent_context=agent_context,
    )

    if args.json:
        print(
            json.dumps(
                {
                    "response": result.response,
                    "route": result.route,
                    "analysis": result.analysis_summary,
                    "strategy": result.strategy_summary,
                    "learning": result.learning_summary,
                    "conversation_id": str(conversation_id),
                    "client_id": str(client_id),
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return

    _hr("ANALYSIS")
    a = result.analysis_summary
    print(f"intent={a.get('intent','?')}  sentiment={a.get('sentiment','?')}  "
          f"stage={a.get('stage','?')}  urgency={a.get('urgency','?')}")

    _hr("STRATEGY")
    s = result.strategy_summary
    if s:
        print(f"type: {s['strategy_type']}")
        print(f"tactic: {s['tactic_instruction']}")
        if s.get("reasoning"):
            print(f"reasoning: {s['reasoning']}")
    else:
        print("(no strategy selected — negotiation capability off, or no analysis)")

    _hr("LEARNING (Cognitive Learning Engine)")
    ln = result.learning_summary
    if not ln or not ln.get("would_inject"):
        print("Nada aprendido coincidió con este mensaje — no se inyectó nada.")
    else:
        for p in ln.get("proven_plays", []):
            n = p.get("occurrence_count", 1)
            label = (
                f"{round(p['success_rate']*100)}% éxito en {n} casos"
                if n >= 3
                else f"visto {n} vez/veces, {round(p.get('avg_score', p['success_rate'])*100)}% efectividad"
            )
            print(f"  PLAY [{p['move_kind']} · {label}] \"{p['excerpt'][:100]}\"")
        for e in ln.get("winning_expressions", []):
            print(f'  ✓ WINNING "{e}"')
        for e in ln.get("anti_expressions", []):
            print(f'  ✗ ANTI "{e}"')
        for r in ln.get("behavior_rules", []):
            print(f"  RULE: {r}")

    _hr("RESPONSE")
    print(result.response)

    _hr("IDS (reuse with --conversation/--client to continue this thread)")
    print(f"conversation_id={conversation_id}")
    print(f"client_id={client_id}  (internal — pass the --client external id back in, not this)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--agent", required=True, help="agent_version_id (UUID)")
    parser.add_argument("--message", required=True, help="client message for this turn")
    parser.add_argument("--conversation", help="existing conversation_id to continue a thread")
    parser.add_argument(
        "--client",
        help="external client id (any string, e.g. phone number) — reuse the same "
        "value across runs to keep talking as the same customer. Random if omitted.",
    )
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
