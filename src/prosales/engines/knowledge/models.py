from pydantic import BaseModel, Field


class KnowledgeResult(BaseModel):
    documents: list[dict] = Field(default_factory=list)
    query_used: str = ""
