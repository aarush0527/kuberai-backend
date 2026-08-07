from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.dependencies import get_db, get_price_service, get_llm_client
from app.services.chat_service import process_chat_message

router = APIRouter(tags=["chat"])


class ChatRequest(BaseModel):
    user_id: str
    message: str


@router.post("/chat")
async def chat(
    req: ChatRequest,
    db=Depends(get_db),
    price_service=Depends(get_price_service),
    llm_client=Depends(get_llm_client),
):
    result = await process_chat_message(db, req.user_id, req.message, price_service, llm_client)
    return {"reply": result.reply, "kind": result.kind, "resolved_by": result.resolved_by}
