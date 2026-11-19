import logging
from typing import Any

from learning_engine.core.enums import ConversationStage
from learning_engine.core.interfaces.engine import BaseDetector
from learning_engine.core.models.analysis import StageResult
from learning_engine.infrastructure.llm.provider import LLMMessage, LLMProvider

logger = logging.getLogger(__name__)

STAGE_PROMPT = """Based on the conversation, determine the current sales stage.
Return JSON: {{"stage": "<stage>", "confidence": <0-1>}}

Valid stages: opening, discovery, presentation, objection_handling, negotiation, closing, post_sale

Conversation:
{conversation}

Latest message: {message}"""


class ConversationStageDetector(BaseDetector):
    def __init__(self, llm: LLMProvider, model: str = "gpt-4o-mini"):
        self.llm = llm
        self.model = model

    async def detect(self, text: str, context: dict[str, Any] | None = None) -> StageResult:
        conv_str = ""
        if context and context.get("recent_messages"):
            conv_str = "\n".join(
                f"{m.role}: {m.content}" for m in context["recent_messages"][-5:]
            )

        try:
            result = await self.llm.complete_json(
                messages=[
                    LLMMessage(role="system", content="You are a sales stage classifier."),
                    LLMMessage(
                        role="user",
                        content=STAGE_PROMPT.format(conversation=conv_str, message=text),
                    ),
                ],
                model=self.model,
            )
            return StageResult(
                stage=ConversationStage(result.get("stage", "opening")),
                confidence=float(result.get("confidence", 0.5)),
            )
        except Exception:
            logger.exception("Stage detection failed")
            return StageResult()
