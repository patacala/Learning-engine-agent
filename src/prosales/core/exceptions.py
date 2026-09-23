class ProSalesError(Exception):
    """Base exception for ProSales."""


class EngineError(ProSalesError):
    """Error in an engine."""


class LLMError(ProSalesError):
    """Error calling LLM provider."""


class MemoryError(ProSalesError):
    """Error in memory operations."""


class KnowledgeError(ProSalesError):
    """Error in knowledge retrieval."""


class PipelineError(ProSalesError):
    """Error in the cognitive pipeline."""
