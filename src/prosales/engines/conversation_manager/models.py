from pydantic import BaseModel, Field

from prosales.core.enums import ConversationPath


class RouteDecision(BaseModel):
    path: ConversationPath = ConversationPath.FULL_PATH
    skip_nodes: list[str] = Field(default_factory=list)
    reasoning: str = ""
