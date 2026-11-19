"""MoveExtractor — the LLM anchors and classifies; code extracts the verbatim text.

Given parsed evidence turns, the LLM identifies multi-turn conversational moves
and returns ONLY turn indices + classification. This module then reads the exact
excerpt from the evidence, guaranteeing the memory is real text, never a summary.
"""

import logging

from learning_engine.engines.evidence.models import EvidenceSource
from learning_engine.engines.moves.models import ConversationMove, MoveAnchor
from learning_engine.engines.moves.states import MOVE_KINDS, NEGATIVE_AFTER_STATES, ClientState
from learning_engine.infrastructure.llm.provider import LLMMessage, LLMProvider

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """Eres un analista experto en ventas. Recibes una conversación numerada por turnos (cada línea empieza con su índice y el hablante). Tu trabajo es identificar los MOVIMIENTOS DE CONVERSACIÓN del agente.

Un movimiento es una acción de venta completa que puede abarcar VARIOS turnos consecutivos (por ejemplo: validar la preocupación → hacer una pregunta → reencuadrar). No trocees un movimiento en frases sueltas.

Por cada movimiento devuelve EXACTAMENTE:
- start_turn_index / end_turn_index: rango de turnos (índices tal como aparecen) que componen el movimiento. Deben incluir al menos un turno del agente.
- move_kind: uno de {kinds}
- goal: qué intentaba lograr el agente (resolver objeción, agendar cita, descubrir necesidad...)
- client_state_before: estado mental del cliente ANTES del movimiento
- client_state_after: estado mental del cliente DESPUÉS (según su reacción real en los turnos siguientes)
- polarity: "positive" si el movimiento acercó al cliente a comprar; "negative" si lo alejó (anti-patrón)
- outcome_label: qué pasó concretamente (ej: "acepto_agendar", "objecion_resuelta", "se_enfrio", "abandono")
- confidence: 0.0-1.0
- conditions: objeto con "works_when" (lista de condiciones donde este movimiento funciona: estado del cliente, etapa, tipo de objeción, tipo de producto) — puede ir vacío

Estados del cliente válidos: {states}

NO inventes ni parafrasees las frases del agente: solo devuelve los índices; el sistema extraerá el texto exacto.

Responde SOLO con JSON válido:
{{
  "moves": [
    {{"start_turn_index": 1, "end_turn_index": 3, "move_kind": "objection_handling", "goal": "...", "client_state_before": "desconfiado", "client_state_after": "tranquilo", "polarity": "positive", "outcome_label": "objecion_resuelta", "confidence": 0.9, "conditions": {{"works_when": ["cliente desconfiado", "objecion de precio"]}}}}
  ]
}}"""


class MoveExtractor:
    def __init__(self, llm_provider: LLMProvider):
        self.llm = llm_provider

    async def extract(self, source: EvidenceSource) -> list[ConversationMove]:
        if not source.turns:
            return []

        messages = self._build_prompt(source)
        try:
            result = await self.llm.complete_json(messages=messages, temperature=0.2)
        except Exception as e:  # noqa: BLE001
            logger.error("Move extraction failed: %s", e)
            return []

        return self._anchor(source, result)

    def _build_prompt(self, source: EvidenceSource) -> list[LLMMessage]:
        numbered = "\n".join(
            f"[{t.turn_index}] {('Agente' if t.speaker == 'agent' else 'Cliente')}: {t.text}"
            for t in source.turns
        )
        system = _SYSTEM_PROMPT.format(
            kinds=", ".join(MOVE_KINDS), states=", ".join(ClientState.values())
        )
        return [
            LLMMessage(role="system", content=system),
            LLMMessage(role="user", content=f"Conversación:\n{numbered}"),
        ]

    def _anchor(self, source: EvidenceSource, result: dict) -> list[ConversationMove]:
        """Turn LLM anchors into fully-materialized moves with verbatim excerpts."""
        raw = result.get("moves", [])
        if not isinstance(raw, list):
            logger.warning("Move extractor got non-list moves: %s", type(raw))
            return []

        max_index = max((t.turn_index for t in source.turns), default=0)
        moves: list[ConversationMove] = []
        for item in raw:
            try:
                anchor = MoveAnchor(**item)
            except Exception as e:  # noqa: BLE001
                logger.warning("Skipping invalid move: %s — %s", item, e)
                continue

            start = max(0, min(anchor.start_turn_index, max_index))
            end = max(start, min(anchor.end_turn_index, max_index))
            excerpt = source.excerpt(start, end)
            if not excerpt.strip():
                continue

            # Derive polarity from the after-state as a guardrail against the LLM.
            polarity = anchor.polarity
            if anchor.client_state_after in NEGATIVE_AFTER_STATES:
                polarity = "negative"

            # Guardrail against the LLM: it's told conditions/works_when "puede ir
            # vacío" and often skips it, leaving the move unable to ever compete
            # in PatternRetriever's contextual filter (_matches_state) against
            # clusters that DO have it tagged — regardless of how good the move
            # actually is. Deterministically fall back to the move's own
            # client_state_before, which is always known and is exactly the
            # condition this evidence demonstrates the play works from.
            conditions = dict(anchor.conditions or {})
            if not conditions.get("works_when") and anchor.client_state_before:
                conditions["works_when"] = [anchor.client_state_before]

            moves.append(
                ConversationMove(
                    evidence_source_id=source.id,
                    agent_version_id=source.agent_version_id,
                    organization_id=source.organization_id,
                    start_turn_index=start,
                    end_turn_index=end,
                    move_kind=anchor.move_kind if anchor.move_kind in MOVE_KINDS else "discovery",
                    goal=anchor.goal,
                    client_state_before=anchor.client_state_before,
                    client_state_after=anchor.client_state_after,
                    transcript_excerpt=excerpt,
                    polarity=polarity,
                    outcome_label=anchor.outcome_label,
                    confidence=anchor.confidence,
                    conditions=conditions,
                )
            )
        return moves
