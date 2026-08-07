

from app.llm.base import LLMClient
from app.llm.schemas import ProposedAction


class FakeLLMClient(LLMClient):
    def __init__(self, script: dict[str, ProposedAction] | None = None, default: ProposedAction | None = None):
        self.script = script or {}
        self.default = default or ProposedAction(kind="info", reply_text="(no scripted response)", resolved_by="llm")
        self.calls: list[tuple[str, list[dict]]] = []

    async def resolve(self, message: str, history: list[dict] | None = None) -> ProposedAction:
        self.calls.append((message, history or []))
        return self.script.get(message, self.default)
