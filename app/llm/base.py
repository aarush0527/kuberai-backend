from abc import ABC, abstractmethod

from app.llm.schemas import ProposedAction


class LLMClient(ABC):
    @abstractmethod
    async def resolve(self, message: str, history: list[dict] | None = None) -> ProposedAction:
        """
        Resolve a message (with recent conversation history, oldest first,
        as {"role": ..., "content": ...} dicts) into a ProposedAction.
        Only ever called for messages the pattern layer didn't confidently
        match — see chat_service.py.
        """
        ...
