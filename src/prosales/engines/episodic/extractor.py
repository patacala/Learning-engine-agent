"""EpisodeExtractor — deterministic fact extraction from events. No LLM calls."""

import logging
from collections import Counter
from datetime import datetime, timezone
from uuid import UUID, uuid4

from prosales.engines.episodic.models import Episode
from prosales.infrastructure.database.models import EventModel
from prosales.infrastructure.database.repositories.conversation import SQLConversationRepository
from prosales.infrastructure.database.repositories.event import SQLEventRepository

logger = logging.getLogger(__name__)


class EpisodeExtractor:
    """Extracts observable facts from conversation events. Deterministic, no LLM."""

    def __init__(
        self,
        event_repo: SQLEventRepository,
        conversation_repo: SQLConversationRepository,
    ):
        self.event_repo = event_repo
        self.conversation_repo = conversation_repo

    async def extract(self, conversation_id: UUID) -> Episode:
        """Extract an Episode from conversation events."""
        # Load conversation
        conversation = await self.conversation_repo.get_by_id(conversation_id)
        if not conversation:
            raise ValueError(f"Conversation {conversation_id} not found")

        # Load all events for this conversation
        events = await self.event_repo.get_by_conversation(conversation_id)

        # Classify events
        analyzer_events = [e for e in events if e.event_type == "analyzer.completed"]
        strategy_events = [e for e in events if e.event_type == "strategy.selected"]
        pipeline_events = [e for e in events if e.event_type == "pipeline.completed"]

        # Count messages
        messages = await self.conversation_repo.get_messages(conversation_id, limit=1000)
        message_count = len(messages)

        # Extract facts
        intents = self._collect_values(analyzer_events, "intent")
        sentiments = self._collect_values(analyzer_events, "sentiment")

        now = datetime.now(timezone.utc)

        return Episode(
            id=uuid4(),
            conversation_id=conversation_id,
            client_id=conversation.client_id,
            organization_id=conversation.organization_id,
            started_at=conversation.created_at,
            closed_at=now,
            duration_seconds=self._calc_duration(events, conversation.created_at),
            message_count=message_count,
            dominant_intent=self._dominant_value(intents),
            dominant_sentiment=self._dominant_value(sentiments),
            sentiment_shifts=self._count_sentiment_shifts(analyzer_events),
            final_stage=conversation.stage or "",
            objections_detected=self._collect_objections(analyzer_events),
            strategies_used=self._collect_strategies(strategy_events),
            urgency_signals=self._collect_signals(analyzer_events, "urgency"),
            risk_signals=self._collect_signals(analyzer_events, "risk"),
        )

    def _collect_values(self, events: list[EventModel], key: str) -> list[str]:
        """Collect non-empty values for a key from event data."""
        values = []
        for e in events:
            val = e.data.get(key, "")
            if val:
                values.append(str(val))
        return values

    def _dominant_value(self, values: list[str]) -> str:
        """Most frequent value in a list."""
        if not values:
            return ""
        counter = Counter(values)
        return counter.most_common(1)[0][0]

    def _count_sentiment_shifts(self, analyzer_events: list[EventModel]) -> int:
        """Count sentiment changes between consecutive analyzer events."""
        sentiments = [e.data.get("sentiment", "") for e in analyzer_events if e.data.get("sentiment")]
        if len(sentiments) < 2:
            return 0
        shifts = sum(1 for i in range(1, len(sentiments)) if sentiments[i] != sentiments[i - 1])
        return shifts

    def _collect_objections(self, analyzer_events: list[EventModel]) -> list[str]:
        """Collect unique objection-related intents."""
        objections = set()
        for e in analyzer_events:
            intent = e.data.get("intent", "")
            if "objection" in str(intent).lower():
                # Include detail if available, else just "objection"
                detail = e.data.get("intent_detail", str(intent))
                objections.add(str(detail))
        return sorted(objections)

    def _collect_strategies(self, strategy_events: list[EventModel]) -> list[str]:
        """Collect unique strategy types applied."""
        strategies = set()
        for e in strategy_events:
            st = e.data.get("strategy_type", "")
            if st:
                strategies.add(str(st))
        return sorted(strategies)

    def _collect_signals(self, analyzer_events: list[EventModel], key: str) -> list[str]:
        """Collect notable urgency/risk signals."""
        signals = set()
        for e in analyzer_events:
            val = e.data.get(key, "")
            if val and str(val).lower() not in ("none", "low", "normal", ""):
                signals.add(str(val))
        return sorted(signals)

    def _calc_duration(self, events: list[EventModel], conversation_start: datetime) -> float:
        """Calculate duration from conversation start to last event."""
        if not events:
            return 0.0
        last_ts = max(e.timestamp for e in events)
        start = conversation_start
        if start and last_ts:
            delta = (last_ts - start).total_seconds()
            return max(0.0, delta)
        return 0.0
