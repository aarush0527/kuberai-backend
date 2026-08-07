import json
import logging

from groq import AsyncGroq

from app.config import settings
from app.llm.base import LLMClient
from app.llm.schemas import ProposedAction
from app.llm.system_prompt import SYSTEM_PROMPT
from app.llm.tools import TOOLS

logger = logging.getLogger("llm")

_UNRESOLVED_REPLY = "Sorry, I didn't quite catch that — could you rephrase?"


class GroqLLMClient(LLMClient):
    def __init__(self, api_key: str | None = None, model: str | None = None):
        self._client = AsyncGroq(api_key=api_key or settings.groq_api_key)
        self._model = model or settings.groq_model

    async def resolve(self, message: str, history: list[dict] | None = None) -> ProposedAction:
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages.extend(history or [])
        messages.append({"role": "user", "content": message})

        response = await self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
            temperature=0.2,
        )

        choice = response.choices[0].message

        if choice.tool_calls:
            call = choice.tool_calls[0]
            try:
                args = json.loads(call.function.arguments)
            except (json.JSONDecodeError, TypeError):
                logger.warning("could not parse tool call arguments", extra={"extra_fields": {"raw": call.function.arguments}})
                args = {}
            return _tool_call_to_action(call.function.name, args)

        return ProposedAction(kind="info", reply_text=choice.content or "", resolved_by="llm")


def _tool_call_to_action(name: str, args: dict) -> ProposedAction:
    if name == "propose_purchase":
        return ProposedAction(kind="purchase", amount=str(args.get("amount", "")), resolved_by="llm")

    if name == "propose_sip_create":
        return ProposedAction(
            kind="sip_create",
            amount=str(args.get("amount", "")),
            frequency=args.get("frequency"),
            day_of_month=args.get("day_of_month"),
            relative_start=args.get("relative_start"),
            explicit_date=args.get("explicit_date"),
            resolved_by="llm",
        )

    if name in ("propose_sip_pause", "propose_sip_resume", "propose_sip_cancel"):
        return ProposedAction(kind=name.replace("propose_", ""), resolved_by="llm")

    if name == "ask_clarification":
        return ProposedAction(
            kind="clarify",
            reply_text=args.get("question", "Could you clarify what you'd like to do?"),
            clarify_options=args.get("options") or [],
            resolved_by="llm",
        )

    logger.warning("unknown tool call from model", extra={"extra_fields": {"tool_name": name}})
    return ProposedAction(kind="info", reply_text=_UNRESOLVED_REPLY, resolved_by="llm")
