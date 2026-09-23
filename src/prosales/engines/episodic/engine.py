"""EpisodicMemoryEngine — service for closing conversations and persisting episodes."""

import logging
from datetime import datetime

from prosales.engines.episodic.extractor import EpisodeExtractor
from prosales.engines.episodic.models import Episode
from prosales.infrastructure.database.models import EpisodicMemoryModel
from prosales.infrastructure.database.repositories.episodic import SQLEpisodicRepository

logger = logging.getLogger(__name__)


class EpisodicMemoryEngine:
    """Service for extracting and persisting conversation episodes.

    Not a pipeline engine (no BaseEngine). Called from API endpoints.
    """

    def __init__(
        self,
        extractor: EpisodeExtractor,
        episodic_repo: SQLEpisodicRepository,
        vector_store=None,
    ):
        self.extractor = extractor
        self.episodic_repo = episodic_repo
        self.vector_store = vector_store

    async def close_conversation(self, conversation_id) -> Episode:
        """Extract episode from events, persist, optionally embed."""
        episode = await self.extractor.extract(conversation_id)

        # Persist
        model = self._to_model(episode)

        # Generate embedding if vector_store available
        if self.vector_store:
            try:
                text = self._episode_to_text(episode)
                embedding = await self.vector_store.embed_text(text)
                model.embedding = embedding
            except Exception as e:
                logger.warning("Embedding generation failed (non-fatal): %s", e)

        await self.episodic_repo.save(model)

        return episode

    def _to_model(self, episode: Episode) -> EpisodicMemoryModel:
        """Convert Episode DTO to database model."""
        return EpisodicMemoryModel(
            id=episode.id,
            conversation_id=episode.conversation_id,
            client_id=episode.client_id,
            organization_id=episode.organization_id,
            started_at=episode.started_at,
            closed_at=episode.closed_at,
            duration_seconds=episode.duration_seconds,
            message_count=episode.message_count,
            dominant_intent=episode.dominant_intent,
            dominant_sentiment=episode.dominant_sentiment,
            sentiment_shifts=episode.sentiment_shifts,
            final_stage=episode.final_stage,
            objections_detected=episode.objections_detected,
            strategies_used=episode.strategies_used,
            urgency_signals=episode.urgency_signals,
            risk_signals=episode.risk_signals,
            outcome=episode.outcome,
            outcome_notes=episode.outcome_notes,
        )

    def _episode_to_text(self, episode: Episode) -> str:
        """Text representation for embedding generation."""
        parts = [
            f"Conversación: intent={episode.dominant_intent}, sentiment={episode.dominant_sentiment}",
            f"Stage: {episode.final_stage}",
        ]
        if episode.objections_detected:
            parts.append(f"Objeciones: {', '.join(episode.objections_detected)}")
        if episode.strategies_used:
            parts.append(f"Estrategias: {', '.join(episode.strategies_used)}")
        if episode.urgency_signals:
            parts.append(f"Urgencia: {', '.join(episode.urgency_signals)}")
        if episode.risk_signals:
            parts.append(f"Riesgo: {', '.join(episode.risk_signals)}")
        parts.append(f"Outcome: {episode.outcome}")
        return ". ".join(parts)
