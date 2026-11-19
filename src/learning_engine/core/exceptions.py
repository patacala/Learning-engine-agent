class LearningEngineError(Exception):
    """Base exception for LearningEngine."""


class EngineError(LearningEngineError):
    """Error in an engine."""


class LLMError(LearningEngineError):
    """Error calling LLM provider."""


class MemoryError(LearningEngineError):
    """Error in memory operations."""


class KnowledgeError(LearningEngineError):
    """Error in knowledge retrieval."""


class PipelineError(LearningEngineError):
    """Error in the cognitive pipeline."""
