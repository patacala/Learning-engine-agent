import logging
from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo

from prosales.core.interfaces.engine import BaseEngine
from prosales.infrastructure.llm.provider import LLMMessage

logger = logging.getLogger(__name__)

DEFAULT_SYSTEM_TEMPLATE = """You are a sales assistant for a vehicle dealership.

PERSONALITY:
- Tone: {tone}
- Instructions: {personality_instructions}

LANGUAGE: Respond in {language}. Keep it natural and conversational.

CONSTRAINTS:
- Maximum {max_sentences} sentences
- Never mention you are an AI
- Stay in character as a helpful sales consultant
- Be conversational, not formal
- If there is conversation history, acknowledge it naturally. Don't restart as if meeting for the first time
- Never use filler phrases like "aja", "como no", "claro" at the start -- the voice layer handles those"""

CONTEXT_TEMPLATE = """RELEVANT CONTEXT:
{facts}
{knowledge}
{conversation_summary}"""


class PromptBuilder(BaseEngine):
    """Builds the final prompt with all context, personality, and instructions."""

    def __init__(self, prompt_provider=None, style_provider=None, pattern_retriever=None):
        self.prompt_provider = prompt_provider
        self.style_provider = style_provider
        self.pattern_retriever = pattern_retriever

    async def process(self, state: dict[str, Any]) -> dict[str, Any]:
        personality = state.get("personality")
        context = state.get("context")
        analysis = state.get("analysis")
        response_plan = state.get("response_plan")
        strategy = state.get("strategy")
        plan = state.get("plan")
        ctx = state.get("agent_context")
        identity = state.get("identity")

        # Build personality section — STATIC only (brand/conversation/voice/
        # identity), stable per agent_version_id, so it stays in the cacheable
        # system_msg below. `emotion` (mood) is dynamic — derived from the
        # client's sentiment each turn — and moves to the per-turn context_msg
        # further down; see personality.py's compile_static_*/compile_emotion_*
        # split (Fase 4 latency: OpenAI prompt caching needs an exact-matching
        # prefix, which mixing emotion in here used to break almost immediately).
        tone = personality.compile_static_tone() if personality else "Profesional y cercano"
        instructions = personality.compile_static_instructions() if personality else []
        personality_str = "\n".join(f"- {i}" for i in instructions) if instructions else "Be helpful"

        mood_tone = personality.compile_emotion_tone() if personality else ""
        mood_instructions = personality.compile_emotion_instructions() if personality else []
        mood_str = ""
        if mood_tone or mood_instructions:
            mood_lines = "\n".join(f"- {i}" for i in mood_instructions)
            mood_str = f"\nCURRENT MOOD: {mood_tone}\n{mood_lines}".rstrip()

        # Language
        lang = analysis.language.language if analysis else "es"
        lang_map = {"es": "Spanish", "en": "English", "pt": "Portuguese", "fr": "French"}
        language = lang_map.get(lang, "Spanish")

        # Max sentences
        max_sentences = response_plan.max_sentences if response_plan else 3

        # Plan instruction
        plan_str = ""
        if plan and plan.next_action:
            plan_str = f"\nGOAL: {plan.goal}\nNEXT ACTION: {plan.next_action.prompt_instruction}"

        # Build system message from agent templates or default
        lookup_id = ctx.agent_version_id if ctx else None

        # Learned style (Cognitive Learning Engine): from state, or the provider.
        style_profile = state.get("style_profile")
        if style_profile is None and self.style_provider and lookup_id:
            style_profile = await self.style_provider.get(lookup_id)

        # Learned plays / expressions / behavior rules (Cognitive Learning Engine).
        # Computed BEFORE strategy_str below, because a real trained play for
        # this exact situation should replace the generic Strategy instruction,
        # not just compete with it in the same prompt — a soft "prioritize this"
        # framing wasn't enough in practice (verified with scripts/eval_conversation.py:
        # the LLM kept following STRATEGY's imperative wording over a "guidance" list).
        learning_ctx = state.get("learning_context")
        if learning_ctx is None and self.pattern_retriever and lookup_id:
            try:
                # Scope proven plays to the selected strategy's move kinds, if any.
                move_kinds = None
                if strategy and getattr(strategy, "strategy_type", None):
                    from prosales.engines.strategy.evidence_bridge import move_kinds_for_strategy

                    move_kinds = move_kinds_for_strategy(strategy.strategy_type) or None

                # Infer the client's current state to retrieve contextually-fitting plays.
                client_state = None
                if analysis:
                    from prosales.engines.moves.states import infer_client_state

                    client_state = infer_client_state(
                        str(analysis.sentiment.sentiment),
                        str(analysis.stage.stage),
                        str(analysis.intent.intent),
                    )
                learning_ctx = await self.pattern_retriever.retrieve(
                    lookup_id,
                    move_kinds=move_kinds,
                    client_state=client_state,
                    message=state.get("current_message"),
                    message_embedding=state.get("message_embedding"),
                )
            except Exception as e:  # noqa: BLE001 — reuse is best-effort, never block a reply
                logger.warning("Pattern retrieval failed (non-fatal): %s", e)

        # Strategy instruction — generic starting point (built-in catalog unless
        # this agent has custom strategies configured). SUPPRESSED when a real
        # trained play matches this situation (learning_ctx.proven_plays already
        # only contains clusters that cleared MIN_SUCCESS for this exact
        # move_kinds/client_state) — the specific evidence-based play replaces
        # the generic one instead of merely outranking it in the same prompt.
        strategy_str = ""
        has_matching_play = bool(learning_ctx and learning_ctx.proven_plays)
        if strategy and strategy.tactic_instruction and not has_matching_play:
            strategy_str = f"\nSTRATEGY (punto de partida genérico): {strategy.tactic_instruction}"

        # system_msg is now STATIC ONLY (no strategy/plan/mood/learning — those
        # are per-turn and vary every time, see below) so it stays byte-identical
        # across turns of the same agent and OpenAI's automatic prompt caching
        # can actually match its prefix (needs >=1024 tokens, exact match).
        system_msg = await self._build_system_message(
            lookup_id, tone, personality_str, language, max_sentences, identity,
        )
        system_msg = self._append_style(system_msg, style_profile)  # also static (agent-level)

        # Context section — everything here is per-turn dynamic already
        # (facts/knowledge/summary), plus mood/strategy/plan/learning moved in
        # from system_msg above: same content sent to the model, just grouped
        # with the other things that change every turn instead of poisoning
        # the static prefix.
        # Current date/time — dynamic per-turn (belongs in context_msg, not the
        # cacheable system_msg). The LLM has no clock of its own; without this
        # it guesses a date near its training cutoff instead of "now".
        now_utc = datetime.now(UTC)
        org_tz_name = ctx.timezone if ctx else "UTC"
        datetime_str = f"Current date/time (UTC): {now_utc.strftime('%Y-%m-%d %H:%M')}"
        if org_tz_name != "UTC":
            now_local = now_utc.astimezone(ZoneInfo(org_tz_name))
            datetime_str += (
                f"\nCurrent date/time ({org_tz_name}): {now_local.strftime('%Y-%m-%d %H:%M %Z')}"
            )

        facts_str = ""
        if context and context.critical_facts:
            facts_str = "Client facts:\n" + "\n".join(
                f"- {f['key']}: {f['value']}" for f in context.critical_facts
            )

        knowledge_str = ""
        if response_plan and response_plan.supporting_points:
            knowledge_str = "Product knowledge:\n" + "\n".join(
                f"- {p}" for p in response_plan.supporting_points
            )

        summary_str = context.conversation_summary if context else ""

        context_msg = CONTEXT_TEMPLATE.format(
            facts=facts_str,
            knowledge=knowledge_str,
            conversation_summary=summary_str,
        ).strip()
        context_msg = f"{datetime_str}\n{context_msg}".strip()
        if mood_str:
            context_msg = f"{context_msg}\n{mood_str}".strip()
        if strategy_str:
            context_msg = f"{context_msg}\n{strategy_str}".strip()
        if plan_str:
            context_msg = f"{context_msg}\n{plan_str}".strip()
        context_msg = self._append_learning(context_msg, learning_ctx)

        # Build messages
        messages = [LLMMessage(role="system", content=system_msg)]

        if context_msg:
            messages.append(LLMMessage(role="system", content=context_msg))

        # Add recent conversation
        if context and context.recent_messages:
            for msg in context.recent_messages[-6:]:
                messages.append(LLMMessage(role=str(msg.role), content=msg.content))

        # Add current message
        messages.append(LLMMessage(role="user", content=state["current_message"]))

        # Expose what was actually retrieved/injected — previously computed
        # here and discarded, forcing callers (Test Playground, eval tooling)
        # to re-query independently to find out what happened. Additive key:
        # no other node reads "learning_context" from output, so this is safe.
        return {"prompt_messages": messages, "learning_context": learning_ctx}

    async def _build_system_message(
        self, lookup_id, tone, personality_str, language, max_sentences, identity=None,
    ) -> str:
        """Build system message from agent templates or default.

        STATIC content only — no strategy/plan (those are per-turn, live in
        context_msg now, see process()). Keeping this 100% stable per
        agent_version_id lets OpenAI's automatic prompt caching match its
        prefix across turns.
        """
        if not (self.prompt_provider and lookup_id):
            base = DEFAULT_SYSTEM_TEMPLATE.format(
                tone=tone,
                personality_instructions=personality_str,
                language=language,
                max_sentences=max_sentences,
            )
            return self._append_identity_blocks(base, identity)

        templates = await self.prompt_provider.get(lookup_id)

        if not templates:
            base = DEFAULT_SYSTEM_TEMPLATE.format(
                tone=tone,
                personality_instructions=personality_str,
                language=language,
                max_sentences=max_sentences,
            )
            return self._append_identity_blocks(base, identity)

        # Assemble from components
        parts = []

        # Role component
        role = templates.get("role")
        if role:
            parts.append(role)
        elif identity:
            parts.append(f"You are {identity.name}. {identity.description}")
        else:
            parts.append("You are a helpful assistant.")

        # Personality
        parts.append(f"\nPERSONALITY:\n- Tone: {tone}\n- Instructions: {personality_str}")

        # Identity context (principles, values, beliefs)
        if identity and identity.prompt_context:
            parts.append(f"\nIDENTITY:\n{identity.prompt_context}")

        # Language constraints
        if identity and identity.language_context:
            parts.append(f"\nLANGUAGE CONSTRAINTS:\n{identity.language_context}")

        parts.append(f"\nLANGUAGE: Respond in {language}. Keep it natural and conversational.")

        # Constraints
        constraints = templates.get("constraints")
        if constraints:
            parts.append(f"\nCONSTRAINTS:\n{constraints}")
        else:
            parts.append(f"\nCONSTRAINTS:\n- Maximum {max_sentences} sentences\n- Never mention you are an AI")

        # Voice
        voice_tmpl = templates.get("voice")
        if voice_tmpl:
            parts.append(f"\nVOICE STYLE:\n{voice_tmpl}")

        # Rules
        rules_tmpl = templates.get("rules")
        if rules_tmpl:
            parts.append(f"\nRULES:\n{rules_tmpl}")

        # Output
        output_tmpl = templates.get("output")
        if output_tmpl:
            parts.append(f"\nOUTPUT FORMAT:\n{output_tmpl}")

        return "\n".join(parts)

    def _append_learning(self, base: str, learning_ctx) -> str:
        """Append proven plays / winning & anti expressions / behavior rules."""
        if not learning_ctx or learning_ctx.is_empty():
            return base
        block = learning_ctx.to_prompt_block()
        return f"{base}\n\n{block}" if block else base

    def _append_style(self, base: str, style_profile) -> str:
        """Append the learned style directive (if any) to the system message."""
        if not style_profile:
            return base
        block = style_profile.to_prompt_block()
        if not block:
            return base
        return f"{base}\n\n{block}"

    def _append_identity_blocks(self, base: str, identity) -> str:
        """Append identity prompt_context and language_context to default template."""
        if not identity:
            return base
        parts = [base]
        if identity.prompt_context:
            parts.append(f"\nIDENTITY:\n{identity.prompt_context}")
        if identity.language_context:
            parts.append(f"\nLANGUAGE CONSTRAINTS:\n{identity.language_context}")
        return "\n".join(parts)
