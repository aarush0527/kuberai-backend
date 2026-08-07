from app.llm.base import LLMClient
from app.llm.schemas import ProposedAction

NOT_CONFIGURED_REPLY = (
    "Chat isn't set up yet on this instance — a GROQ_API_KEY is needed. "
    "The rest of the API (purchases, SIPs, price, journeys) works regardless."
)


class NotConfiguredLLMClient(LLMClient):
    """Used when no LLM provider is configured. Lets the app boot and every
    non-chat endpoint work normally; only /chat gets this honest message,
    instead of the whole app failing to start over a missing API key."""

    async def resolve(self, message: str, history: list[dict] | None = None) -> ProposedAction:
        return ProposedAction(kind="info", reply_text=NOT_CONFIGURED_REPLY, resolved_by="not_configured")
