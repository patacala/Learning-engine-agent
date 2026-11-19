import logging
import re
from typing import Any

from learning_engine.core.enums import Language
from learning_engine.core.interfaces.engine import BaseDetector
from learning_engine.core.models.analysis import LanguageResult

logger = logging.getLogger(__name__)

# Simple rule-based language detection (no LLM needed)
ES_INDICATORS = {"hola", "busco", "quiero", "estoy", "carro", "auto", "precio", "cuánto", "cuanto", "gracias", "buenas", "necesito", "tengo", "puede", "información", "favor"}
EN_INDICATORS = {"hello", "looking", "want", "price", "car", "vehicle", "how", "much", "thanks", "need", "have", "information", "please"}
PT_INDICATORS = {"olá", "procuro", "quero", "carro", "preço", "obrigado", "preciso", "tenho"}


class LanguageDetector(BaseDetector):
    async def detect(self, text: str, context: dict[str, Any] | None = None) -> LanguageResult:
        words = set(re.findall(r'\w+', text.lower()))

        scores = {
            Language.ES: len(words & ES_INDICATORS),
            Language.EN: len(words & EN_INDICATORS),
            Language.PT: len(words & PT_INDICATORS),
        }

        best_lang = max(scores, key=scores.get)
        best_score = scores[best_lang]
        total = sum(scores.values()) or 1

        if best_score == 0:
            return LanguageResult(language=Language.ES, confidence=0.5)

        return LanguageResult(
            language=best_lang,
            confidence=min(best_score / total, 1.0),
        )
