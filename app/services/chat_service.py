"""
The one place a chat message turns into either a real action or a reply.
Deliberately thin: every branch below just calls into money.py,
price_provider.py, purchase_service.py, or sip_service.py. 
"""

from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app import models
from app.events import log_event_now
from app.llm import pattern_layer
from app.llm.base import LLMClient
from app.llm.schemas import ProposedAction
from app.money import parse_rupee_amount, compute_gold_quantity, MoneyError
from app.price_provider import CachingPriceService, PriceUnavailableError
from app.services.common import get_or_create_user, new_correlation_id
from app.services.purchase_service import execute_purchase, Outcome as PurchaseOutcome
from app.services.sip_service import (
    create_sip,
    pause_sip,
    resume_sip,
    cancel_sip,
    resolve_monthly_start_date,
    VALID_FREQUENCIES,
    SIPOutcome,
)

DEFAULT_UNRESOLVED_REPLY = "Sorry, I'm not sure how to help with that — could you rephrase?"


@dataclass
class ChatReply:
    reply: str
    kind: str
    resolved_by: str


#Entry point

async def process_chat_message(
    db: Session,
    user_id: str,
    message: str,
    price_service: CachingPriceService,
    llm_client: LLMClient,
) -> ChatReply:
    get_or_create_user(db, user_id)
    correlation_id = new_correlation_id()
    log_event_now(db, user_id, correlation_id, "message_received", {"message": message})

    resolved = _try_resolve_pending_clarification(db, user_id, message)
    if resolved is not None:
        action, sip_id = resolved
        outcome = _dispatch_sip_action(db, user_id, action, sip_id, correlation_id)
        reply = _render_sip_action_outcome(outcome)
        log_event_now(db, user_id, correlation_id, "reply_sent", {"reply": reply, "resolved_pending_clarification": True})
        return ChatReply(reply=reply, kind=action, resolved_by="clarification")

    proposed = pattern_layer.try_match(message)
    if proposed is None:
        history = _recent_history(db, user_id)
        proposed = await llm_client.resolve(message, history)

    log_event_now(
        db, user_id, correlation_id, "intent_resolved",
        {"kind": proposed.kind, "resolved_by": proposed.resolved_by},
    )

    reply = await _dispatch(db, user_id, proposed, correlation_id, price_service)

    log_event_now(db, user_id, correlation_id, "reply_sent", {"reply": reply, "kind": proposed.kind})
    return ChatReply(reply=reply, kind=proposed.kind, resolved_by=proposed.resolved_by)


#Dispatch


async def _dispatch(
    db: Session, user_id: str, proposed: ProposedAction, correlation_id: str, price_service: CachingPriceService
) -> str:
    if proposed.kind == "purchase":
        outcome = await execute_purchase(db, user_id, proposed.amount or "", correlation_id, price_service)
        return _render_purchase_outcome(outcome)

    if proposed.kind == "sip_create":
        frequency = proposed.frequency or ""
        if frequency not in VALID_FREQUENCIES:
            return "I couldn't tell what frequency you meant — daily, weekly, or monthly?"
        start_date, anchor_day = _resolve_sip_schedule(proposed, frequency)
        outcome = create_sip(
            db, user_id, proposed.amount or "", frequency, start_date, correlation_id,
            requested_anchor_day=anchor_day,
        )
        return _render_sip_create_outcome(outcome)

    if proposed.kind in ("sip_pause", "sip_resume", "sip_cancel"):
        outcome = _dispatch_sip_action(db, user_id, proposed.kind, proposed.sip_ref, correlation_id)
        if outcome.reason_code == "SIP_AMBIGUOUS" and outcome.candidates:
            _store_pending_clarification(db, user_id, proposed.kind, outcome.candidates)
            options = "; ".join(f"₹{s.rupee_amount} {s.frequency}" for s in outcome.candidates)
            return f"You've got a few SIPs — which one did you mean? ({options})"
        return _render_sip_action_outcome(outcome)

    if proposed.kind == "price_query":
        return await _render_price_query(proposed, price_service)

    if proposed.kind in ("info", "clarify"):
        return proposed.reply_text or DEFAULT_UNRESOLVED_REPLY

    return DEFAULT_UNRESOLVED_REPLY


def _dispatch_sip_action(db: Session, user_id: str, action: str, sip_id: str | None, correlation_id: str) -> SIPOutcome:
    if action == "sip_pause":
        return pause_sip(db, user_id, sip_id, correlation_id)
    if action == "sip_resume":
        return resume_sip(db, user_id, sip_id, correlation_id)
    if action == "sip_cancel":
        return cancel_sip(db, user_id, sip_id, correlation_id)
    raise ValueError(f"unknown SIP action: {action}")



#SIP schedule resolution; deterministic date arithmetic, never the LLM's job 


def _resolve_sip_schedule(proposed: ProposedAction, frequency: str) -> tuple[date, int | None]:
    today = date.today()

    if proposed.explicit_date:
        try:
            start = date.fromisoformat(proposed.explicit_date)
        except ValueError:
            start = today
        anchor = start.day if frequency == "monthly" else None
        return start, anchor

    if proposed.day_of_month is not None and frequency == "monthly":
        anchor = proposed.day_of_month
        start = resolve_monthly_start_date(today, anchor)
        return start, anchor

    if proposed.relative_start == "yesterday":
        start = today - timedelta(days=1)
    elif proposed.relative_start == "tomorrow":
        start = today + timedelta(days=1)
    else:
        start = today

    anchor = start.day if frequency == "monthly" else None
    return start, anchor


#Pending clarification; multi-turn "which SIP did you mean" resolution


def _store_pending_clarification(db: Session, user_id: str, action: str, candidates: list[models.SIP]) -> None:
    existing = db.get(models.PendingClarification, user_id)
    if existing is not None:
        db.delete(existing)
        db.flush()
    db.add(models.PendingClarification(user_id=user_id, action=action, candidate_sip_ids=[c.id for c in candidates]))
    db.commit()


def _try_resolve_pending_clarification(db: Session, user_id: str, message: str) -> tuple[str, str] | None:

    pending = db.get(models.PendingClarification, user_id)
    if pending is None:
        return None

    lowered = message.lower()
    sips = [s for s in (db.get(models.SIP, sid) for sid in pending.candidate_sip_ids) if s is not None]

    resolved_sip_id = None

    for sip in sips:
        amount_str = str(sip.rupee_amount)
        whole_number_str = amount_str.split(".")[0]
        if amount_str in message or whole_number_str in message:
            resolved_sip_id = sip.id
            break

    if resolved_sip_id is None:
        for sip in sips:
            if sip.frequency in lowered:
                resolved_sip_id = sip.id
                break

    if resolved_sip_id is None:
   
        ordinal_words = {"first": 0, "1st": 0, "second": 1, "2nd": 1, "third": 2, "3rd": 2}
        for word, idx in ordinal_words.items():
            if word in lowered and idx < len(sips):
                resolved_sip_id = sips[idx].id
                break

    action = pending.action
    db.delete(pending)
    db.commit()

    if resolved_sip_id is None:
        return None
    return action, resolved_sip_id



# Reply rendering — deterministic templates. Amounts, quantities, ids, and dates always come from the real Outcome, never from LLM-authored text.


def _render_purchase_outcome(outcome: PurchaseOutcome) -> str:
    if not outcome.success:
        return outcome.message or "That purchase didn't go through."
    txn = outcome.transaction
    if outcome.deduped:
        return f"Looks like that already went through a moment ago — ₹{txn.rupee_amount} for {txn.gold_quantity}g of gold (txn {txn.id})."
    return f"Done — bought ₹{txn.rupee_amount} of gold at ₹{txn.gold_price_used}/g, that's {txn.gold_quantity}g. (txn {txn.id})"


def _ordinal(n: int) -> str:
    if 11 <= (n % 100) <= 13:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def _render_sip_create_outcome(outcome: SIPOutcome) -> str:
    if not outcome.success:
        return outcome.message or "I couldn't set that SIP up."
    sip = outcome.sip
    if outcome.already_existed:
        return f"You already have this SIP set up: ₹{sip.rupee_amount} {sip.frequency}, next on {sip.next_due_date}."

    parts = [f"Set up — ₹{sip.rupee_amount} {sip.frequency}, starting {sip.next_due_date}."]
    if outcome.start_clamped:
        parts.append("(starting today since the date you mentioned has already passed)")
    if sip.frequency == "monthly" and sip.anchor_day and sip.anchor_day > 28:
        parts.append(f"On months without a {_ordinal(sip.anchor_day)}, I'll run it on that month's last day instead.")
    return " ".join(parts)


def _render_sip_action_outcome(outcome: SIPOutcome) -> str:
    if not outcome.success:
        return outcome.message or "I couldn't do that."
    sip = outcome.sip
    return f"Done — your ₹{sip.rupee_amount} {sip.frequency} SIP is now {sip.status}."


async def _render_price_query(proposed: ProposedAction, price_service: CachingPriceService) -> str:
    try:
        amount = parse_rupee_amount(proposed.amount or "")
    except MoneyError:
        return "I couldn't quite tell what amount you meant."

    try:
        quote = await price_service.get_price()
    except PriceUnavailableError:
        return "Gold's price is temporarily unavailable — try again in a moment."

    quantity = compute_gold_quantity(amount, quote.price_per_gram)
    stale_note = " (using the last known price, which may be a little stale)" if quote.is_stale else ""
    return f"At today's price of \u20b9{quote.price_per_gram}/g, \u20b9{amount} would buy about {quantity}g of gold{stale_note}."


#Conversation context for the LLM tier

def _recent_history(db: Session, user_id: str, limit: int = 6) -> list[dict]:
    events = (
        db.query(models.Event)
        .filter(models.Event.user_id == user_id, models.Event.event_type.in_(["message_received", "reply_sent"]))
        .order_by(models.Event.created_at.desc())
        .limit(limit)
        .all()
    )
    events.reverse()
    history = []
    for e in events:
        if e.event_type == "message_received":
            history.append({"role": "user", "content": e.payload.get("message", "")})
        else:
            history.append({"role": "assistant", "content": e.payload.get("reply", "")})
    return history
