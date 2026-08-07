"""
The one place money actually moves. Deliberately has zero knowledge of the
LLM or the chat layer — it accepts a raw amount string and returns an
Outcome, full stop.
"""

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models
from app.config import settings
from app.events import build_event, log_event_now
from app.money import parse_rupee_amount, compute_gold_quantity, MoneyError
from app.price_provider import CachingPriceService, PriceUnavailableError
from app.services.common import get_or_create_user


REASON_MESSAGES = {
    "AMOUNT_INVALID": "That doesn't look like a valid amount.",
    "AMOUNT_BAD_PRECISION": "Amounts can have at most 2 decimal places.",
    "AMOUNT_NOT_POSITIVE": "Amount must be greater than zero.",
    "AMOUNT_BELOW_MIN": f"Minimum purchase is \u20b9{settings.min_purchase_inr}.",
    "AMOUNT_ABOVE_MAX": f"Maximum purchase per transaction is \u20b9{settings.max_purchase_inr}.",
    "PRICE_UNAVAILABLE": "Gold price is temporarily unavailable \u2014 please try again shortly.",
}


@dataclass
class Outcome:
    success: bool
    reason_code: str | None = None
    message: str | None = None
    transaction: models.Transaction | None = None
    deduped: bool = False


def derive_purchase_idempotency_key(user_id: str, amount_str: str, window_seconds: int) -> str:

    bucket = int(datetime.now(timezone.utc).timestamp() // window_seconds)
    raw = f"purchase:{user_id}:{amount_str}:{bucket}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def _reject(db: Session, user_id: str, correlation_id: str, reason_code: str) -> Outcome:
    log_event_now(
        db, user_id, correlation_id, "purchase_rejected",
        {"reason_code": reason_code},
    )
    return Outcome(success=False, reason_code=reason_code, message=REASON_MESSAGES.get(reason_code, reason_code))


async def execute_purchase(
    db: Session,
    user_id: str,
    raw_amount: str,
    correlation_id: str,
    price_service: CachingPriceService,
    idempotency_key: str | None = None,
    txn_type: str = models.TransactionType.PURCHASE.value,
    sip_id: str | None = None,
) -> Outcome:

    get_or_create_user(db, user_id)

    log_event_now(db, user_id, correlation_id, "purchase_requested", {"raw_amount": raw_amount, "type": txn_type})

    try:
        amount = parse_rupee_amount(raw_amount)
    except MoneyError as e:
        return _reject(db, user_id, correlation_id, e.reason_code)

    if amount < settings.min_purchase_inr:
        return _reject(db, user_id, correlation_id, "AMOUNT_BELOW_MIN")
    if amount > settings.max_purchase_inr:
        return _reject(db, user_id, correlation_id, "AMOUNT_ABOVE_MAX")

    amount_str = str(amount)
    key = idempotency_key or derive_purchase_idempotency_key(user_id, amount_str, settings.purchase_dedup_window_seconds)

    existing = db.query(models.Transaction).filter_by(idempotency_key=key).first()
    if existing is not None:
        log_event_now(
            db, user_id, correlation_id, "purchase_deduped",
            {"idempotency_key": key, "existing_transaction_id": existing.id},
        )
        return Outcome(success=True, transaction=existing, deduped=True, message="Already processed — showing your existing purchase.")

    try:
        quote = await price_service.get_price()
    except PriceUnavailableError:
        return _reject(db, user_id, correlation_id, "PRICE_UNAVAILABLE")

    gold_qty = compute_gold_quantity(amount, quote.price_per_gram)

    txn = models.Transaction(
        user_id=user_id,
        type=txn_type,
        sip_id=sip_id,
        rupee_amount=amount,
        gold_price_used=quote.price_per_gram,
        gold_quantity=gold_qty,
        status=models.TransactionStatus.COMPLETED.value,
        idempotency_key=key,
        correlation_id=correlation_id,
    )
    db.add(txn)
    build_event(
        db, user_id, correlation_id, "purchase_completed",
        {
            "amount": amount_str,
            "gold_quantity": str(gold_qty),
            "price_used": str(quote.price_per_gram),
            "price_is_stale": quote.is_stale,
            "type": txn_type,
            "sip_id": sip_id,
        },
    )

    try:
        db.commit()
    except IntegrityError:

        db.rollback()
        existing = db.query(models.Transaction).filter_by(idempotency_key=key).first()
        log_event_now(
            db, user_id, correlation_id, "purchase_deduped_race",
            {"idempotency_key": key},
        )
        return Outcome(success=True, transaction=existing, deduped=True, message="Already processed — showing your existing purchase.")

    db.refresh(txn)
    return Outcome(success=True, transaction=txn)
